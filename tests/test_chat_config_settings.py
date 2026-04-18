import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient

import routes.chat as chat_module
import routes.settings as settings_module
import storage.state_loader as state_loader


class ChatConfigSettingsTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._chat_config_file = Path(self._tmpdir.name) / "chat_config.json"
        self._original_chat_config_file = state_loader.CHAT_CONFIG_FILE
        state_loader.CHAT_CONFIG_FILE = self._chat_config_file

    def tearDown(self):
        state_loader.CHAT_CONFIG_FILE = self._original_chat_config_file
        self._tmpdir.cleanup()

    def _build_client(self):
        app = FastAPI()
        app.include_router(settings_module.router)
        return TestClient(app)

    def test_get_chat_config_returns_balanced_defaults(self):
        client = self._build_client()

        response = client.get("/chat/config")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["config"]["l1_recent_token_budget_preset"], "balanced")
        self.assertEqual(payload["config"]["l1_recent_token_budget"], 4000)
        self.assertFalse(payload["config"]["vision_auto_enabled"])
        self.assertEqual(
            [item["id"] for item in payload["presets"]],
            ["save", "balanced", "deep", "immersive"],
        )

    def test_post_chat_config_persists_selected_preset(self):
        client = self._build_client()

        response = client.post("/chat/config", json={"preset": "immersive"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["config"]["l1_recent_token_budget_preset"], "immersive")
        self.assertEqual(payload["config"]["l1_recent_token_budget"], 8000)
        persisted = json.loads(self._chat_config_file.read_text(encoding="utf-8"))
        self.assertEqual(
            persisted,
            {
                "l1_recent_token_budget_preset": "immersive",
                "l1_recent_token_budget": 8000,
                "vision_auto_enabled": False,
            },
        )

    def test_post_chat_config_falls_back_to_balanced_for_invalid_preset(self):
        client = self._build_client()

        response = client.post("/chat/config", json={"l1_recent_token_budget_preset": "unknown"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["config"]["l1_recent_token_budget_preset"], "balanced")
        self.assertEqual(payload["config"]["l1_recent_token_budget"], 4000)
        self.assertFalse(payload["config"]["vision_auto_enabled"])

    def test_post_chat_config_can_enable_vision_autostart(self):
        client = self._build_client()

        response = client.post("/chat/config", json={"vision_auto_enabled": True})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["config"]["vision_auto_enabled"])
        persisted = json.loads(self._chat_config_file.read_text(encoding="utf-8"))
        self.assertEqual(
            persisted,
            {
                "l1_recent_token_budget_preset": "balanced",
                "l1_recent_token_budget": 4000,
                "vision_auto_enabled": True,
            },
        )

    def test_chat_uses_runtime_chat_config_budget(self):
        seen_budgets = []
        history_state = {"history": []}
        state_loader.save_chat_config({"l1_recent_token_budget_preset": "deep"})

        def fake_load_history():
            return [dict(item) for item in history_state["history"]]

        def fake_save_history(history):
            history_state["history"] = [dict(item) for item in history]

        def fake_get_recent_messages(history, limit=None, max_tokens=None):
            seen_budgets.append(max_tokens)
            return []

        async def _run_chat():
            response = await chat_module.chat(
                chat_module.ChatRequest(message="hello"),
                BackgroundTasks(),
            )
            chunks = []
            async for item in response.body_iterator:
                chunks.append(item)
            return chunks

        with patch.object(chat_module.S, "add_to_history", side_effect=lambda *_args, **_kwargs: None), patch.object(
            chat_module.S, "load_msg_history", side_effect=fake_load_history
        ), patch.object(
            chat_module.S, "save_msg_history", side_effect=fake_save_history
        ), patch.object(
            chat_module.S, "awareness_pull", return_value=[]
        ), patch.object(
            chat_module.S, "get_recent_messages", side_effect=fake_get_recent_messages
        ), patch.object(
            chat_module.S, "extract_session_context", return_value=[]
        ), patch.object(
            chat_module.S, "load_l4_persona", return_value={}
        ), patch.object(
            chat_module.S, "build_dialogue_context", return_value={}
        ), patch.object(
            chat_module.S, "search_relevant_rules", return_value=[]
        ), patch.object(
            chat_module.S, "debug_write", side_effect=lambda *_args, **_kwargs: None
        ), patch.object(
            chat_module.S, "detect_recall_intent", None
        ), patch(
            "core.runtime_state.state_loader.record_memory_stats", side_effect=lambda **_kwargs: None
        ), patch(
            "brain.get_current_model_name", return_value="deepseek-chat"
        ), patch(
            "decision.tool_runtime.runtime_control.create_tool_runtime_control",
            return_value={"cancel_requested": False},
        ), patch.object(
            chat_module, "_get_tool_call_unavailable_reason", return_value="disabled"
        ), patch.object(
            chat_module, "_get_cod_enabled", return_value=False
        ), patch.object(
            chat_module,
            "_detect_model_switch",
            return_value={"reply": "ok", "trace": "skip", "model_changed": False},
        ):
            asyncio.run(_run_chat())

        self.assertEqual(seen_budgets, [6000])


if __name__ == "__main__":
    unittest.main()
