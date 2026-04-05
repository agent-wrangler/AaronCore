import json
import unittest
from unittest.mock import patch

from brain import codex_cli_runtime as runtime


class _FakeWebSocket:
    def __init__(self, incoming):
        self._incoming = list(incoming)
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def send(self, payload):
        self.sent.append(json.loads(payload))

    def recv(self, timeout=None):
        del timeout
        if not self._incoming:
            raise AssertionError("No more websocket messages queued.")
        message = self._incoming.pop(0)
        return json.dumps(message, ensure_ascii=False)


class CodexCliRuntimeStreamTests(unittest.TestCase):
    def test_codex_cli_call_stream_emits_deltas_and_usage(self):
        ws = _FakeWebSocket(
            [
                {"id": "1", "result": {"userAgent": "probe", "codexHome": "C:\\Users\\36459\\.codex", "platformFamily": "windows", "platformOs": "windows"}},
                {"id": "2", "result": {"thread": {"id": "thread-1"}}},
                {"id": "3", "result": {"turn": {"id": "turn-1", "status": "inProgress", "items": [], "error": None}}},
                {"method": "item/reasoning/textDelta", "params": {"threadId": "thread-1", "turnId": "turn-1", "itemId": "rs-1", "delta": "thinking...", "contentIndex": 0}},
                {"method": "item/agentMessage/delta", "params": {"threadId": "thread-1", "turnId": "turn-1", "itemId": "msg-1", "delta": "Hel"}},
                {"method": "item/completed", "params": {"threadId": "thread-1", "turnId": "turn-1", "item": {"type": "agentMessage", "id": "msg-1", "text": "Hello"}}},
                {"method": "thread/tokenUsage/updated", "params": {"threadId": "thread-1", "turnId": "turn-1", "tokenUsage": {"last": {"inputTokens": 10, "cachedInputTokens": 6, "outputTokens": 4, "reasoningOutputTokens": 2}}}},
                {"method": "turn/completed", "params": {"threadId": "thread-1", "turn": {"id": "turn-1", "status": "completed", "error": None}}},
            ]
        )

        with patch.object(runtime, "validate_codex_cli_login", return_value=(True, "")), patch.object(
            runtime, "_find_codex_bin", return_value="codex.cmd"
        ), patch.object(runtime, "_ensure_app_server_url", return_value="ws://127.0.0.1:8768"), patch.object(
            runtime, "_open_app_server_connection", return_value=ws
        ):
            chunks = list(
                runtime.codex_cli_call_stream(
                    {"model": "gpt-5.4-mini", "transport": "codex_cli"},
                    [{"role": "user", "content": "hello"}],
                )
            )

        self.assertEqual(chunks[0], {"_thinking_content": "thinking..."})
        self.assertEqual(chunks[1:3], ["Hel", "lo"])
        self.assertEqual(
            chunks[-1],
            {
                "_usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "prompt_cache_hit_tokens": 6,
                    "prompt_cache_miss_tokens": 4,
                    "reasoning_output_tokens": 2,
                }
            },
        )
        self.assertEqual([item["method"] for item in ws.sent], ["initialize", "thread/start", "turn/start"])

    def test_codex_cli_call_stream_uses_completed_message_when_no_delta_arrives(self):
        ws = _FakeWebSocket(
            [
                {"id": "1", "result": {"userAgent": "probe", "codexHome": "C:\\Users\\36459\\.codex", "platformFamily": "windows", "platformOs": "windows"}},
                {"id": "2", "result": {"thread": {"id": "thread-1"}}},
                {"id": "3", "result": {"turn": {"id": "turn-1", "status": "inProgress", "items": [], "error": None}}},
                {"method": "item/completed", "params": {"threadId": "thread-1", "turnId": "turn-1", "item": {"type": "agentMessage", "id": "msg-1", "text": "Hello"}}},
                {"method": "turn/completed", "params": {"threadId": "thread-1", "turn": {"id": "turn-1", "status": "completed", "error": None}}},
            ]
        )

        with patch.object(runtime, "validate_codex_cli_login", return_value=(True, "")), patch.object(
            runtime, "_find_codex_bin", return_value="codex.cmd"
        ), patch.object(runtime, "_ensure_app_server_url", return_value="ws://127.0.0.1:8768"), patch.object(
            runtime, "_open_app_server_connection", return_value=ws
        ):
            chunks = list(
                runtime.codex_cli_call_stream(
                    {"model": "gpt-5.4-mini", "transport": "codex_cli"},
                    [{"role": "user", "content": "hello"}],
                )
            )

        self.assertEqual(chunks[0], "Hello")
        self.assertEqual(chunks[-1], {"_usage": {}})

    def test_codex_cli_call_stream_falls_back_to_exec_before_any_delta(self):
        with patch.object(runtime, "validate_codex_cli_login", return_value=(True, "")), patch.object(
            runtime, "_find_codex_bin", return_value="codex.cmd"
        ), patch.object(runtime, "_ensure_app_server_url", return_value="ws://127.0.0.1:8768"), patch.object(
            runtime, "_open_app_server_connection", side_effect=RuntimeError("boom")
        ), patch.object(
            runtime,
            "_codex_exec_call",
            return_value={"content": "Fallback reply", "usage": {"completion_tokens": 1}},
        ):
            chunks = list(
                runtime.codex_cli_call_stream(
                    {"model": "gpt-5.4-mini", "transport": "codex_cli"},
                    [{"role": "user", "content": "hello"}],
                )
            )

        self.assertEqual(chunks, ["Fallback reply", {"_usage": {"completion_tokens": 1}}])


if __name__ == "__main__":
    unittest.main()
