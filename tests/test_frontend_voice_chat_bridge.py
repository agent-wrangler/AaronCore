import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendVoiceChatBridgeTests(unittest.TestCase):
    def test_stream_runtime_dispatches_reply_final_event(self):
        text = (ROOT / "static/js/chat/stream-runtime.js").read_text(encoding="utf-8")
        self.assertIn("aaroncore:assistant-reply-final", text)
        self.assertIn("window.dispatchEvent(new CustomEvent(", text)

    def test_voice_js_uses_reply_event_tts_and_backend_fallback(self):
        text = (ROOT / "static/js/chat/voice.js").read_text(encoding="utf-8")
        self.assertIn("aaroncore:assistant-reply-final", text)
        self.assertIn("aaroncore:chat-request-state", text)
        self.assertIn("suppressReplyPlayback", text)
        self.assertIn("native-barge", text)
        self.assertIn("function _armBargeInListening(", text)
        self.assertIn("function _disarmBargeInListening(", text)
        self.assertIn("function _submitBargeInTranscript(", text)
        self.assertIn("_armBargeInListening(650)", text)
        self.assertIn("window.pywebview&&window.pywebview.api", text)
        self.assertIn("voice_bridge_status", text)
        self.assertIn("voice_listen_start", text)
        self.assertIn("voice_listen_stop", text)
        self.assertIn("voice_speak", text)
        self.assertIn("aaroncore-native-voice-state", text)
        self.assertIn("aaroncore-native-voice-result", text)
        self.assertIn("speechSynthesis", text)
        self.assertIn("/companion/state", text)
        self.assertIn("/companion/tts_status", text)
        self.assertIn("function _interruptVoiceCycleAndRelisten()", text)
        self.assertIn("typeof _stopGeneration==='function'", text)
        self.assertIn("if(_voiceMode&&_interruptVoiceCycleAndRelisten()) return;", text)

    def test_stream_and_composer_emit_chat_request_state_events(self):
        process_text = (ROOT / "static/js/chat/process.js").read_text(encoding="utf-8")
        composer_text = (ROOT / "static/js/chat/composer.js").read_text(encoding="utf-8")
        stream_text = (ROOT / "static/js/chat/stream.js").read_text(encoding="utf-8")
        self.assertIn("function _dispatchChatRequestState(", process_text)
        self.assertIn("aaroncore:chat-request-state", process_text)
        self.assertIn("_dispatchChatRequestState('stopping'", composer_text)
        self.assertIn("_dispatchChatRequestState('started'", stream_text)
        self.assertIn("_dispatchChatRequestState('completed'", stream_text)
        self.assertIn("_dispatchChatRequestState('aborted'", stream_text)
        self.assertIn("_dispatchChatRequestState('error'", stream_text)
