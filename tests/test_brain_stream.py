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
