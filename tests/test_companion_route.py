import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import companion as companion_module
from routes.chat_post_reply import update_companion_reply_state


ROOT = Path(__file__).resolve().parents[1]


class CompanionRouteTests(unittest.TestCase):
    def setUp(self):
        companion_module.reset_state()
        app = FastAPI()
        app.include_router(companion_module.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        companion_module.reset_state()

    def test_state_defaults(self):
        response = self.client.get("/companion/state")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["activity"], "idle")
        self.assertEqual(data["last_reply_summary"], "")
        self.assertFalse(data["tts_playing"])
        self.assertFalse(data["voice_mode"])

    def test_voice_and_tts_updates_are_reflected_in_state(self):
        self.client.post("/companion/voice_mode", json={"enabled": True})
        self.client.post("/companion/tts_status", json={"playing": True})
        update_companion_reply_state(
            companion_module,
            "hello\nworld",
            detect_emotion=lambda _text: "calm",
        )

        response = self.client.get("/companion/state")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["voice_mode"])
        self.assertTrue(data["tts_playing"])
        self.assertEqual(data["last_reply_full"], "hello world")
        self.assertEqual(data["last_reply_summary"], companion_module.last_reply)
        self.assertEqual(data["emotion"], "calm")
        self.assertTrue(data["last_reply_id"])

    def test_agent_final_includes_companion_router(self):
        text = (ROOT / "agent_final.py").read_text(encoding="utf-8")
        self.assertIn("from routes.companion import router as _companion_router", text)
        self.assertIn("app.include_router(_companion_router)", text)
