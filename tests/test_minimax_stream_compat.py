import json
import unittest
from unittest.mock import patch

import brain as brain_module
import core.reply_formatter as reply_formatter_module


class _FakeStreamResponse:
    def __init__(self, lines=None, status_code=200, text=""):
        self._lines = list(lines or [])
        self.status_code = status_code
        self.text = text

    def iter_lines(self, decode_unicode=True):
        for line in self._lines:
            yield line


class MiniMaxOpenAICompatTests(unittest.TestCase):
    def test_openai_stream_deduplicates_minimax_cumulative_chunks(self):
        cfg = {
            "model": "MiniMax-M2.7",
            "base_url": "https://api.minimaxi.com/v1",
            "api_key": "test",
        }
        messages = [{"role": "user", "content": "hello"}]
        stream_resp = _FakeStreamResponse(
            lines=[
                'data: {"choices":[{"delta":{"reasoning_details":[{"text":"Let me"}]}}]}',
                'data: {"choices":[{"delta":{"reasoning_details":[{"text":"Let me think"}]}}]}',
                'data: {"choices":[{"delta":{"content":"He"}}]}',
                'data: {"choices":[{"delta":{"content":"Hello"}}]}',
                "data: [DONE]",
            ]
        )

        with patch.object(brain_module, "_post_with_network_strategy", return_value=stream_resp):
            chunks = list(brain_module._llm_stream_openai(cfg, messages, tools=[]))

        thinking = "".join(
            str(chunk.get("_thinking_content") or "")
            for chunk in chunks
            if isinstance(chunk, dict) and "_thinking_content" in chunk
        )
        visible = "".join(chunk for chunk in chunks if isinstance(chunk, str))

        self.assertEqual(thinking, "Let me think")
        self.assertEqual(visible, "Hello")
        self.assertEqual(chunks[-1], {"_usage": {}})

    def test_unified_reply_with_tools_preserves_reasoning_details_in_followup_history(self):
        seen_messages = []

        def fake_llm_call(_cfg, messages, **_kwargs):
            seen_messages.append(messages)
            has_tool_result = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
            if not has_tool_result:
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_demo_1",
                            "type": "function",
                            "function": {"name": "demo_tool", "arguments": "{}"},
                        }
                    ],
                    "reasoning_details": [{"text": "Need to inspect first."}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 1},
                }
            return {"content": "Done.", "usage": {"prompt_tokens": 2, "completion_tokens": 1}}

        def fake_tool_executor(_name, _args, _context):
            return {"success": True, "response": "ok"}

        bundle = {"user_input": "continue", "l1": [], "l4": {}, "dialogue_context": ""}

        with patch.object(reply_formatter_module, "_llm_call", side_effect=fake_llm_call), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            result = reply_formatter_module.unified_reply_with_tools(bundle, [], fake_tool_executor)

        assistant_messages = [
            message
            for message in seen_messages[1]
            if isinstance(message, dict) and message.get("role") == "assistant" and message.get("tool_calls")
        ]

        self.assertEqual(result["reply"], "Done.")
        self.assertEqual(assistant_messages[0]["reasoning_details"][0]["text"], "Need to inspect first.")

    def test_unified_reply_with_tools_stream_passes_thinking_and_preserves_followup_reasoning(self):
        seen_messages = []

        def fake_stream(_cfg, messages, **_kwargs):
            seen_messages.append(messages)
            has_tool_result = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
            if not has_tool_result:
                yield {"_thinking_content": "Inspecting the task."}
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_demo_stream_1",
                            "type": "function",
                            "function": {"name": "demo_tool", "arguments": json.dumps({}, ensure_ascii=False)},
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 4, "completion_tokens": 1}}
                return
            yield "Done."
            yield {"_usage": {"prompt_tokens": 2, "completion_tokens": 1}}

        def fake_tool_executor(_name, _args, _context):
            return {"success": True, "response": "ok"}

        bundle = {"user_input": "continue", "l1": [], "l4": {}, "dialogue_context": ""}

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_llm_call", return_value={"content": "", "usage": {}}
        ), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], fake_tool_executor))

        thinking_chunks = [
            chunk for chunk in chunks if isinstance(chunk, dict) and "_thinking_content" in chunk
        ]
        assistant_messages = [
            message
            for message in seen_messages[1]
            if isinstance(message, dict) and message.get("role") == "assistant" and message.get("tool_calls")
        ]

        self.assertEqual(thinking_chunks[0]["_thinking_content"], "Inspecting the task.")
        self.assertEqual(assistant_messages[0]["reasoning_details"][0]["text"], "Inspecting the task.")
        self.assertTrue(any(isinstance(chunk, str) and chunk == "Done." for chunk in chunks))

    def test_unified_reply_with_tools_stream_attaches_uploaded_image_context_on_first_turn(self):
        seen_messages = []

        def fake_stream(_cfg, messages, **_kwargs):
            seen_messages.append(messages)
            yield "Done."
            yield {"_usage": {"prompt_tokens": 2, "completion_tokens": 1}}

        bundle = {
            "user_input": "what is in this screenshot",
            "image": "abc123",
            "images": ["abc123"],
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch(
            "core.vision.build_uploaded_image_prompt_context",
            return_value="[LOCAL_IMAGE_CONTEXT]\nImage 1: settings screen.",
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], lambda *_args: {}))

        self.assertIn("[LOCAL_IMAGE_CONTEXT]", seen_messages[0][-1]["content"])
        self.assertNotIn("image_url", str(seen_messages[0]))
        self.assertTrue(any(isinstance(chunk, str) and chunk == "Done." for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
