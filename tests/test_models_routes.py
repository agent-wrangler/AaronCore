import asyncio
import sys
import tempfile
import types
import unittest
from pathlib import Path

from routes.models import (
    list_models,
    save_model_config,
    switch_model,
    test_model_config as probe_model_config,
)


class ModelRoutesTests(unittest.TestCase):
    def _install_fake_brain(self, models_config, *, current="deepseek-chat", llm_result=None):
        temp_path = str(Path(tempfile.gettempdir()) / "aaroncore-test-model-config.json")
        state = {"current": current}

        def _llm_call(_cfg, _messages, **_kwargs):
            return dict(llm_result or {"content": "pong"})

        def _set_default(mid):
            state["current"] = mid
            fake_brain._current_default = mid
            return True

        fake_brain = types.SimpleNamespace(
            MODELS_CONFIG=models_config,
            _current_default=current,
            _raw_config={"models": dict(models_config), "default": current},
            config_path=temp_path,
            llm_call=_llm_call,
            set_default_model=_set_default,
            validate_codex_cli_login=lambda timeout=8: (True, "ok"),
        )
        original = sys.modules.get("brain")
        sys.modules["brain"] = fake_brain
        return original

    def _restore_brain(self, original):
        if original is None:
            sys.modules.pop("brain", None)
        else:
            sys.modules["brain"] = original

    def test_list_models_hides_codex_and_incomplete_entries(self):
        original = self._install_fake_brain(
            {
                "deepseek-chat": {
                    "model": "deepseek-chat",
                    "transport": "openai_api",
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key": "sk-live-123",
                    "vision": False,
                },
                "gpt-5.4": {
                    "model": "gpt-5.4",
                    "transport": "codex_cli",
                    "base_url": "codex://local",
                },
                "broken-model": {
                    "model": "broken-model",
                    "transport": "openai_api",
                    "base_url": "https://api.example.com/v1",
                    "api_key": "",
                },
            }
        )
        try:
            result = asyncio.run(list_models())
        finally:
            self._restore_brain(original)
        self.assertIn("deepseek-chat", result["models"])
        self.assertIn("deepseek-reasoner", result["models"])
        self.assertNotIn("gpt-5.4", result["models"])
        self.assertNotIn("broken-model", result["models"])

    def test_test_model_config_supports_inline_api_probe(self):
        original = self._install_fake_brain({}, llm_result={"content": "pong"})
        try:
            result = asyncio.run(
                probe_model_config(
                    {
                        "id": "deepseek-chat",
                        "config": {
                            "model": "deepseek-chat",
                            "transport": "openai_api",
                            "base_url": "https://api.deepseek.com/v1",
                            "api_key": "sk-live-123",
                        },
                    }
                )
            )
        finally:
            self._restore_brain(original)
        self.assertTrue(result["ok"])
        self.assertEqual(result["detail"], "Connection OK")

    def test_save_model_config_rejects_non_api_transport(self):
        original = self._install_fake_brain({})
        try:
            result = asyncio.run(
                save_model_config(
                    {
                        "id": "gpt-5.4",
                        "config": {
                            "model": "gpt-5.4",
                            "transport": "codex_cli",
                            "base_url": "codex://local",
                        },
                    }
                )
            )
        finally:
            self._restore_brain(original)
        self.assertFalse(result["ok"])
        self.assertIn("API-backed", result["error"])

    def test_switch_model_auto_derives_catalog_model_from_provider_connection(self):
        original = self._install_fake_brain(
            {
                "deepseek-chat": {
                    "model": "deepseek-chat",
                    "transport": "openai_api",
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key": "sk-live-123",
                    "vision": False,
                }
            },
            current="deepseek-chat",
        )
        try:
            result = asyncio.run(switch_model("deepseek-reasoner"))
            fake_brain = sys.modules["brain"]
        finally:
            self._restore_brain(original)
        self.assertTrue(result["ok"])
        self.assertTrue(result["derived"])
        self.assertIn("deepseek-reasoner", fake_brain.MODELS_CONFIG)
        self.assertEqual(
            fake_brain.MODELS_CONFIG["deepseek-reasoner"]["base_url"],
            "https://api.deepseek.com/v1",
        )

    def test_switch_model_does_not_probe_remote_api_before_switching(self):
        original = self._install_fake_brain(
            {
                "minimax-chat": {
                    "model": "MiniMax-M2.7",
                    "transport": "openai_api",
                    "base_url": "https://api.minimax.chat/v1",
                    "api_key": "sk-live-123",
                    "vision": False,
                }
            },
            current="deepseek-chat",
            llm_result={
                "error": (
                    '{"type":"error","error":{"type":"insufficient_balance_error",'
                    '"message":"insufficient balance","http_code":"429"}}'
                )
            },
        )
        try:
            result = asyncio.run(switch_model("minimax-chat"))
            fake_brain = sys.modules["brain"]
        finally:
            self._restore_brain(original)
        self.assertTrue(result["ok"])
        self.assertEqual(result["current"], "minimax-chat")
        self.assertEqual(fake_brain._current_default, "minimax-chat")

    def test_test_model_config_can_probe_derived_catalog_model_by_id(self):
        original = self._install_fake_brain(
            {
                "deepseek-chat": {
                    "model": "deepseek-chat",
                    "transport": "openai_api",
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key": "sk-live-123",
                    "vision": False,
                }
            }
        )
        try:
            result = asyncio.run(probe_model_config({"id": "deepseek-reasoner"}))
        finally:
            self._restore_brain(original)
        self.assertTrue(result["ok"])
        self.assertEqual(result["detail"], "Connection OK")


if __name__ == "__main__":
    unittest.main()
