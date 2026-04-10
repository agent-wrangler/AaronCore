import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendSendButtonStateTests(unittest.TestCase):
    def test_composer_returns_directly_between_stop_and_send(self):
        text = (ROOT / "static/js/chat/composer.js").read_text(encoding="utf-8")
        self.assertNotIn("function _enterSettlingMode()", text)
        self.assertNotIn("settling-mode", text)
        self.assertIn("_setSendButtonA11yState(btn, 'input.stop'", text)
        self.assertIn("_setSendButtonA11yState(btn, 'input.send'", text)

    def test_stream_does_not_switch_to_middle_settling_state_on_reply(self):
        text = (ROOT / "static/js/chat/stream.js").read_text(encoding="utf-8")
        self.assertNotRegex(text, re.compile(r"currentEvent==='reply'.*?_enterSettlingMode\(\);", re.S))

    def test_i18n_no_longer_exposes_finishing_copy(self):
        text = (ROOT / "static/js/i18n.js").read_text(encoding="utf-8")
        self.assertIn("'input.stop':", text)
        self.assertNotIn("'input.finishing':", text)

    def test_backend_no_longer_emits_reply_visible_and_attaches_background_tasks(self):
        text = (ROOT / "routes/chat.py").read_text(encoding="utf-8")
        self.assertNotIn('yield {"event": "reply_visible"', text)
        self.assertIn("return EventSourceResponse(event_stream(), ping=2, background=background_tasks)", text)


if __name__ == "__main__":
    unittest.main()
