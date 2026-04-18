import unittest
from unittest.mock import patch

from brain import chat_runtime


def _detect_mode(_prompt: str, _context: str) -> str:
    return "chat"


def _build_prompts(prompt: str, _context: str, _mode: str) -> tuple[str, str]:
    return "SYS", f"USER::{prompt}"


def _clean_reply(text: str) -> str:
    return str(text or "").strip()


def _looks_bad(_text: str) -> tuple[bool, str]:
    return False, ""


def _error_reply(_cfg: dict, reason: str, detail: str = "") -> str:
    return f"ERR:{reason}:{detail}"


def _emotion(_text: str) -> str:
    return "neutral"


class ChatRuntimeImageBridgeTests(unittest.TestCase):
    def setUp(self):
        self.llm_config = {"model": "deepseek-chat", "vision": False}
        self.models_config = {
            "deepseek-chat": {"model": "deepseek-chat", "vision": False},
            "gpt-4o": {"model": "gpt-4o", "vision": True},
        }

    def test_think_uses_local_image_context_without_switching_to_vision_model(self):
        llm_calls = []
        openai_calls = []

        def _llm_call(cfg, messages, **kwargs):
            llm_calls.append((cfg, messages, kwargs))
            return {"content": "ok", "usage": {}}

        def _openai_call(cfg, messages, **kwargs):
            openai_calls.append((cfg, messages, kwargs))
            return {"content": "should-not-run", "usage": {}}

        with patch.object(
            chat_runtime,
            "_build_uploaded_image_context",
            return_value="[LOCAL_IMAGE_CONTEXT]\n图片1：- 画面理解：设置页截图。",
        ):
            result = chat_runtime.think(
                "帮我看这个报错",
                images=["abc123"],
                llm_config=self.llm_config,
                models_config=self.models_config,
                detect_mode_fn=_detect_mode,
                build_think_prompts_fn=_build_prompts,
                llm_call_fn=_llm_call,
                llm_call_openai_fn=_openai_call,
                clean_llm_reply_fn=_clean_reply,
                looks_bad_reply_fn=_looks_bad,
                explicit_chat_error_reply_fn=_error_reply,
                detect_emotion_fn=_emotion,
            )

        self.assertEqual(result["reply"], "ok")
        self.assertEqual(openai_calls, [])
        self.assertEqual(len(llm_calls), 1)
        cfg, messages, kwargs = llm_calls[0]
        self.assertEqual(cfg["model"], "deepseek-chat")
        self.assertEqual(messages[0]["content"], "SYS")
        self.assertIn("[LOCAL_IMAGE_CONTEXT]", messages[1]["content"])
        self.assertNotIn("image_url", str(messages))
        self.assertEqual(kwargs["max_tokens"], 2000)

    def test_think_stream_keeps_streaming_for_image_turns_after_local_bridge(self):
        stream_calls = []

        def _stream_call(cfg, messages, **kwargs):
            stream_calls.append((cfg, messages, kwargs))
            yield "chunk-1"
            yield {"_usage": {"prompt_tokens": 7, "completion_tokens": 3}}

        with patch.object(
            chat_runtime,
            "_build_uploaded_image_context",
            return_value="[LOCAL_IMAGE_CONTEXT]\n图片1：- 可见文字：Traceback...",
        ):
            chunks = list(
                chat_runtime.think_stream(
                    "解释下这张图",
                    images=["abc123"],
                    llm_config=self.llm_config,
                    models_config=self.models_config,
                    detect_mode_fn=_detect_mode,
                    build_think_prompts_fn=_build_prompts,
                    think_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("think fallback should not run")),
                    llm_call_stream_fn=_stream_call,
                )
            )

        self.assertEqual(chunks[0], "chunk-1")
        self.assertEqual(chunks[-1], {"_done": True, "usage": {"prompt_tokens": 7, "completion_tokens": 3}})
        self.assertEqual(len(stream_calls), 1)
        cfg, messages, kwargs = stream_calls[0]
        self.assertEqual(cfg["model"], "deepseek-chat")
        self.assertIn("[LOCAL_IMAGE_CONTEXT]", messages[1]["content"])
        self.assertEqual(kwargs["timeout"], 25)

    def test_think_injects_explicit_fallback_when_local_analysis_unavailable(self):
        llm_calls = []

        def _llm_call(cfg, messages, **kwargs):
            llm_calls.append((cfg, messages, kwargs))
            return {"content": "ok", "usage": {}}

        with patch("core.vision.build_uploaded_image_prompt_context", side_effect=Exception("boom")):
            chat_runtime.think(
                "读一下图片里的字",
                images=["abc123"],
                llm_config=self.llm_config,
                models_config=self.models_config,
                detect_mode_fn=_detect_mode,
                build_think_prompts_fn=_build_prompts,
                llm_call_fn=_llm_call,
                llm_call_openai_fn=lambda *_args, **_kwargs: {"content": "", "usage": {}},
                clean_llm_reply_fn=_clean_reply,
                looks_bad_reply_fn=_looks_bad,
                explicit_chat_error_reply_fn=_error_reply,
                detect_emotion_fn=_emotion,
            )

        self.assertEqual(len(llm_calls), 1)
        self.assertIn("当前本地图片分析暂不可用", llm_calls[0][1][1]["content"])


if __name__ == "__main__":
    unittest.main()
