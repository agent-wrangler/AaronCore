import json
import time
import unittest
from unittest.mock import patch

import brain as brain_module


class _FakeStreamResponse:
    def __init__(self, lines=None, status_code=200, text=""):
        self._lines = list(lines or [])
        self.status_code = status_code
        self.text = text
        self.closed = False

    def iter_lines(self, decode_unicode=True):
        for line in self._lines:
            if self.closed:
                return
            if isinstance(line, BaseException):
                raise line
            yield line

    def close(self):
        self.closed = True


class _FakeJsonResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload


class _SlowStreamResponse:
    def __init__(self, *, delay_s: float, lines=None, status_code=200, text=""):
        self.delay_s = delay_s
        self._lines = list(lines or [])
        self.status_code = status_code
        self.text = text
        self.closed = False

    def iter_lines(self, decode_unicode=True):
        time.sleep(self.delay_s)
        if self.closed:
            return
        for line in self._lines:
            if self.closed:
                return
            yield line

    def close(self):
        self.closed = True


class BrainStreamTests(unittest.TestCase):
    def test_think_does_not_load_persona_file_for_plain_chat(self):
        captured = {}

        def _fake_llm_call(cfg, messages, temperature=0.7, max_tokens=2000, timeout=25):
            captured["messages"] = messages
            return {"content": "模型回复"}

        with patch.object(brain_module.json, "load", side_effect=AssertionError("think should not load persona.json")):
            with patch.object(brain_module, "llm_call", side_effect=_fake_llm_call):
                result = brain_module.think("你叫什么")

        self.assertEqual(result["reply"], "模型回复")
        self.assertEqual(captured["messages"][0]["role"], "system")
        self.assertIn("你是当前对话助手", captured["messages"][0]["content"])
        self.assertIn("你叫什么", captured["messages"][1]["content"])

    def test_think_stream_does_not_load_persona_file_for_plain_chat(self):
        captured = {}

        def _fake_llm_call_stream(cfg, messages, temperature=0.7, max_tokens=2000, timeout=25):
            captured["messages"] = messages
            yield "模"
            yield "型"

        with patch.object(brain_module.json, "load", side_effect=AssertionError("think_stream should not load persona.json")):
            with patch.object(brain_module, "llm_call_stream", side_effect=_fake_llm_call_stream):
                chunks = list(brain_module.think_stream("在吗"))

        self.assertEqual(chunks[:2], ["模", "型"])
        self.assertEqual(chunks[-1], {"_done": True, "usage": {}})
        self.assertEqual(captured["messages"][0]["role"], "system")
        self.assertIn("你是当前对话助手", captured["messages"][0]["content"])
        self.assertIn("在吗", captured["messages"][1]["content"])

    def test_openai_stream_retries_when_stream_returns_no_content(self):
        cfg = {"model": "test-model", "base_url": "https://example.com/v1", "api_key": "test"}
        messages = [{"role": "user", "content": "我的意思是记录下来的文档存在本地吧"}]

        stream_resp = _FakeStreamResponse(lines=["data: [DONE]"])
        retry_resp = _FakeJsonResponse(
            {
                "choices": [{"message": {"content": "对，就在你本地磁盘上，不会丢。"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 7},
            }
        )

        with patch.object(brain_module, "_post_with_network_strategy", side_effect=[stream_resp, retry_resp]):
            chunks = list(brain_module._llm_stream_openai(cfg, messages, tools=[]))

        self.assertTrue(any(isinstance(chunk, str) and "本地磁盘" in chunk for chunk in chunks))
        self.assertEqual(chunks[-1].get("_usage", {}).get("completion_tokens"), 7)

    def test_openai_empty_completion_recovery_stays_stream_shaped(self):
        cfg = {"model": "test-model", "base_url": "https://example.com/v1", "api_key": "test"}
        messages = [{"role": "user", "content": "store locally"}]
        recovered_text = (
            "Recovered locally. "
            "Recovered locally. "
            "Recovered locally. "
            "Recovered locally."
        )

        stream_resp = _FakeStreamResponse(lines=["data: [DONE]"])
        retry_resp = _FakeJsonResponse(
            {
                "choices": [{"message": {"content": recovered_text}}],
                "usage": {"prompt_tokens": 9, "completion_tokens": 7},
            }
        )

        with patch.object(brain_module, "_post_with_network_strategy", side_effect=[stream_resp, retry_resp]):
            chunks = list(brain_module._llm_stream_openai(cfg, messages, tools=[]))

        visible = [chunk for chunk in chunks if isinstance(chunk, str)]

        self.assertGreater(len(visible), 1)
        self.assertEqual("".join(visible), recovered_text)
        self.assertFalse(any(isinstance(chunk, dict) and chunk.get("_stream_reset") for chunk in chunks))
        self.assertEqual(chunks[-1].get("_usage", {}).get("completion_tokens"), 7)

    def test_stream_idle_watchdog_times_out_when_provider_goes_silent(self):
        resp = _SlowStreamResponse(delay_s=0.06, lines=["data: [DONE]"])

        with self.assertRaises(TimeoutError):
            list(brain_module._stream_runtime._iter_lines_with_idle_watchdog(resp, idle_timeout_s=0.02))

    def test_openai_stream_resets_partial_visible_text_before_stream_recovery(self):
        cfg = {"model": "test-model", "base_url": "https://example.com/v1", "api_key": "test"}
        messages = [{"role": "user", "content": "hello"}]
        recovered_text = "Recovered answer. Recovered answer. Recovered answer. Recovered answer."

        stream_resp = _FakeStreamResponse(
            lines=[
                'data: {"choices":[{"delta":{"content":"Half answer. "}}]}',
                RuntimeError("stream exploded"),
            ]
        )
        retry_resp = _FakeJsonResponse(
            {
                "choices": [{"message": {"content": recovered_text}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            }
        )

        with patch.object(brain_module, "_post_with_network_strategy", side_effect=[stream_resp, retry_resp]):
            chunks = list(brain_module._llm_stream_openai(cfg, messages, tools=[]))

        reset_index = next(
            i for i, chunk in enumerate(chunks) if isinstance(chunk, dict) and chunk.get("_stream_reset")
        )
        streamed_tail = [
            chunk
            for chunk in chunks[reset_index + 1 :]
            if isinstance(chunk, str)
        ]

        self.assertEqual(chunks[0], "Half answer. ")
        self.assertEqual(chunks[reset_index].get("_stream_reset", {}).get("reason"), "stream_exception_fallback")
        self.assertGreater(len(streamed_tail), 1)
        self.assertEqual("".join(streamed_tail), recovered_text)
        self.assertEqual(chunks[-1].get("_usage", {}).get("completion_tokens"), 2)

    def test_openai_incomplete_stream_preserves_accumulated_tool_batch_before_recovery(self):
        cfg = {"model": "test-model", "base_url": "https://example.com/v1", "api_key": "test"}
        messages = [{"role": "user", "content": "inspect both"}]

        stream_resp = _FakeStreamResponse(
            lines=[
                'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"folder_explore","arguments":"{\\"query\\":\\"src\\"}"}}]}}]}',
                'data: {"choices":[{"delta":{"tool_calls":[{"index":1,"id":"call_2","type":"function","function":{"name":"search_text","arguments":"{\\"query\\":\\"TODO\\"}"}}]}}]}',
            ]
        )

        with patch.object(brain_module, "_post_with_network_strategy", return_value=stream_resp):
            chunks = list(brain_module._llm_stream_openai(cfg, messages, tools=[]))

        tool_calls = next(chunk["_tool_calls"] for chunk in chunks if isinstance(chunk, dict) and chunk.get("_tool_calls"))

        self.assertEqual([item["function"]["name"] for item in tool_calls], ["folder_explore", "search_text"])
        self.assertFalse(any(isinstance(chunk, dict) and chunk.get("_stream_reset") for chunk in chunks))

    def test_anthropic_incomplete_stream_preserves_accumulated_tool_batch_before_recovery(self):
        cfg = {"model": "claude-test", "base_url": "https://api.anthropic.com", "api_key": "test"}
        messages = [{"role": "user", "content": "inspect both"}]

        stream_resp = _FakeStreamResponse(
            lines=[
                'data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"call_1","name":"folder_explore","input":{"query":"src"}}}',
                'data: {"type":"content_block_start","index":1,"content_block":{"type":"tool_use","id":"call_2","name":"search_text","input":{"query":"TODO"}}}',
            ]
        )

        with patch.object(brain_module, "_post_with_network_strategy", return_value=stream_resp):
            chunks = list(brain_module._llm_stream_anthropic(cfg, messages, tools=[]))

        tool_calls = next(chunk["_tool_calls"] for chunk in chunks if isinstance(chunk, dict) and chunk.get("_tool_calls"))

        self.assertEqual([item["function"]["name"] for item in tool_calls], ["folder_explore", "search_text"])
        self.assertFalse(any(isinstance(chunk, dict) and chunk.get("_stream_reset") for chunk in chunks))

    def test_openai_stream_resets_partial_visible_text_when_stream_ends_without_done(self):
        cfg = {"model": "test-model", "base_url": "https://example.com/v1", "api_key": "test"}
        messages = [{"role": "user", "content": "hello"}]

        stream_resp = _FakeStreamResponse(
            lines=[
                'data: {"choices":[{"delta":{"content":"Half answer. "}}]}',
            ]
        )
        retry_resp = _FakeJsonResponse(
            {
                "choices": [{"message": {"content": "Recovered after EOF."}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            }
        )

        with patch.object(brain_module, "_post_with_network_strategy", side_effect=[stream_resp, retry_resp]):
            chunks = list(brain_module._llm_stream_openai(cfg, messages, tools=[]))

        reset_index = next(
            i for i, chunk in enumerate(chunks) if isinstance(chunk, dict) and chunk.get("_stream_reset")
        )

        self.assertEqual(chunks[0], "Half answer. ")
        self.assertEqual(chunks[reset_index].get("_stream_reset", {}).get("reason"), "stream_incomplete_fallback")
        self.assertEqual(chunks[reset_index + 1], "Recovered after EOF.")
        self.assertEqual(chunks[-1].get("_usage", {}).get("completion_tokens"), 2)

    def test_anthropic_stream_resets_partial_visible_text_before_stream_recovery(self):
        cfg = {"model": "claude-test", "base_url": "https://api.anthropic.com", "api_key": "test"}
        messages = [{"role": "user", "content": "hello"}]

        stream_resp = _FakeStreamResponse(
            lines=[
                'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}',
                'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Half anthropic. "}}',
                RuntimeError("anthropic stream exploded"),
            ]
        )
        retry_resp = _FakeJsonResponse(
            {
                "content": [{"type": "text", "text": "Recovered anthropic."}],
                "usage": {"input_tokens": 6, "output_tokens": 3},
            }
        )

        with patch.object(brain_module, "_post_with_network_strategy", side_effect=[stream_resp, retry_resp]):
            chunks = list(brain_module._llm_stream_anthropic(cfg, messages, tools=[]))

        reset_index = next(
            i for i, chunk in enumerate(chunks) if isinstance(chunk, dict) and chunk.get("_stream_reset")
        )

        self.assertEqual(chunks[0], "Half anthropic. ")
        self.assertEqual(chunks[reset_index].get("_stream_reset", {}).get("reason"), "stream_exception_fallback")
        self.assertEqual(chunks[reset_index + 1], "Recovered anthropic.")
        self.assertEqual(chunks[-1].get("_usage", {}).get("completion_tokens"), 3)

    def test_codex_cli_stream_uses_incremental_transport(self):
        cfg = {"model": "gpt-5.4-mini", "transport": "codex_cli", "base_url": "codex://local"}
        messages = [{"role": "user", "content": "hello"}]

        with patch.object(
            brain_module._codex_cli_runtime,
            "codex_cli_call_stream",
            return_value=iter(["Hel", "lo", {"_usage": {"completion_tokens": 2}}]),
        ), patch.object(
            brain_module._codex_cli_runtime,
            "codex_cli_call",
            side_effect=AssertionError("llm_call_stream should not use the blocking codex exec path"),
        ):
            chunks = list(brain_module.llm_call_stream(cfg, messages))

        self.assertEqual(chunks, ["Hel", "lo", {"_usage": {"completion_tokens": 2}}])

    def test_openai_stream_surfaces_balance_errors_as_visible_reply(self):
        cfg = {"model": "MiniMax-M2.7", "base_url": "https://api.minimaxi.com/v1", "api_key": "test"}
        messages = [{"role": "user", "content": "hello"}]
        error_payload = {
            "type": "error",
            "error": {
                "type": "insufficient_balance_error",
                "message": "insufficient balance",
                "http_code": "429",
            },
        }

        stream_resp = _FakeStreamResponse(status_code=429, text=json.dumps(error_payload, ensure_ascii=False))
        retry_resp = _FakeJsonResponse(error_payload, status_code=429)

        with patch.object(brain_module, "_post_with_network_strategy", side_effect=[stream_resp, retry_resp]):
            chunks = list(brain_module._llm_stream_openai(cfg, messages, tools=[]))

        visible = "".join(chunk for chunk in chunks if isinstance(chunk, str))

        self.assertIn("余额不足", visible)
        self.assertEqual(chunks[-1].get("_usage", {}), {})

    def test_openai_stream_surfaces_context_limit_errors_as_visible_reply(self):
        cfg = {"model": "MiniMax-M2.7", "base_url": "https://api.minimaxi.com/v1", "api_key": "test"}
        messages = [{"role": "user", "content": "hello"}]
        error_payload = {
            "type": "error",
            "error": {
                "type": "bad_request_error",
                "message": "invalid params, context window exceeds limit (2013)",
                "http_code": "400",
            },
        }

        stream_resp = _FakeStreamResponse(status_code=400, text=json.dumps(error_payload, ensure_ascii=False))
        retry_resp = _FakeJsonResponse(error_payload, status_code=400)

        with patch.object(brain_module, "_post_with_network_strategy", side_effect=[stream_resp, retry_resp]):
            chunks = list(brain_module._llm_stream_openai(cfg, messages, tools=[]))

        visible = "".join(chunk for chunk in chunks if isinstance(chunk, str))

        self.assertIn("上下文太长", visible)
        self.assertEqual(chunks[-1].get("_usage", {}), {})
