import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendAwarenessRetiredTests(unittest.TestCase):
    def test_awareness_script_no_longer_polls_backend_route(self):
        text = (ROOT / "static/js/awareness.js").read_text(encoding="utf-8")
        self.assertNotIn("/awareness/pending", text)
        self.assertIn("function startPolling() {}", text)
        self.assertIn("localStorage.removeItem(STORAGE_KEY)", text)

    def test_output_html_uses_retired_awareness_stub_version(self):
        text = (ROOT / "output.html").read_text(encoding="utf-8")
        self.assertIn('/static/js/awareness.js?v=20260410retired1', text)


if __name__ == "__main__":
    unittest.main()
