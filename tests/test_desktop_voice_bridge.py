import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DesktopVoiceBridgeTests(unittest.TestCase):
    def test_desktop_exposes_native_voice_bridge(self):
        text = (ROOT / "desktop.py").read_text(encoding="utf-8")
        self.assertIn("window.expose(voice_bridge_status)", text)
        self.assertIn("window.expose(voice_listen_start)", text)
        self.assertIn("window.expose(voice_listen_stop)", text)
        self.assertIn("window.expose(voice_speak)", text)
        self.assertIn("window.expose(voice_speak_stop)", text)

    def test_desktop_dispatches_native_voice_events(self):
        text = (ROOT / "desktop.py").read_text(encoding="utf-8")
        self.assertIn("aaroncore-native-voice-state", text)
        self.assertIn("aaroncore-native-voice-result", text)
        self.assertIn("aaroncore-native-voice-error", text)
        self.assertIn("System.Speech.Recognition.SpeechRecognitionEngine", text)
        self.assertIn("System.Speech.Synthesis.SpeechSynthesizer", text)
