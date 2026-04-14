import json
import unittest
from unittest.mock import patch

import brain as brain_module


class _FakeStreamResponse:
    def __init__(self, lines=None, status_code=200, text=""):
        self._lines = list(lines or [])
        self.status_code = status_code
        self.text = text

    def iter_lines(self, decode_unicode=True):
        for line in self._lines:
            yield line


class _FakeJsonResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload


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
