import asyncio
import copy
import sys
import tempfile
import types
import unittest
from pathlib import Path

from routes.models import (
    get_models_catalog,
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

        def _save_raw_config(raw):
            fake_brain._raw_config = copy.deepcopy(raw)

        fake_brain = types.SimpleNamespace(
            MODELS_CONFIG=models_config,
            _current_default=current,
            _raw_config={"models": dict(models_config), "default": current},
            config_path=temp_path,
            llm_call=_llm_call,
            save_raw_config=_save_raw_config,
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

    def test_models_catalog_exposes_official_provider_base_urls(self):
        original = self._install_fake_brain({})
        try:
            result = asyncio.run(get_models_catalog())
        finally:
            self._restore_brain(original)
        self.assertEqual(result["catalog"]["openai"]["base_url"], "https://api.openai.com/v1")
        self.assertEqual(result["catalog"]["claude"]["base_url"], "https://api.anthropic.com/v1")
        self.assertEqual(
            result["catalog"]["qwen"]["base_url"],
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        claude_models = [entry["id"] for entry in result["catalog"]["claude"]["models"]]
        self.assertIn("claude-opus-4-6", claude_models)
        self.assertIn("claude-sonnet-4-6", claude_models)

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
        self.assertEqual(
            fake_brain.MODELS_CONFIG["deepseek-reasoner"]["provider_key"],
            "deepseek",
        )
        self.assertEqual(
            fake_brain.MODELS_CONFIG["deepseek-reasoner"]["api_mode"],
            "chat_completions",
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

    def test_list_models_prefers_gateway_base_url_over_model_name_for_provider_grouping(self):
        original = self._install_fake_brain(
            {
                "gateway-claude": {
                    "model": "claude-sonnet-4-6",
                    "transport": "openai_api",
                    "base_url": "https://api.minimaxi.com/anthropic/v1",
                    "api_key": "sk-live-123",
                    "provider_key": "claude",
                    "provider": "anthropic",
                }
            }
        )
        try:
            result = asyncio.run(list_models())
        finally:
            self._restore_brain(original)
        self.assertEqual(result["models"]["gateway-claude"]["provider_key"], "minimax")

    def test_save_model_config_preserves_display_name_but_keeps_actual_model_name(self):
        original = self._install_fake_brain({})
        try:
            result = asyncio.run(
                save_model_config(
                    {
                        "id": "deepseek-main",
                        "config": {
                            "model": "deepseek-chat",
                            "display_name": "主脑对话",
                            "transport": "openai_api",
                            "base_url": "https://api.deepseek.com/v1",
                            "api_key": "sk-live-123",
                        },
                    }
                )
            )
            fake_brain = sys.modules["brain"]
        finally:
            self._restore_brain(original)
        self.assertTrue(result["ok"])
        self.assertEqual(fake_brain.MODELS_CONFIG["deepseek-main"]["model"], "deepseek-chat")
        self.assertEqual(fake_brain.MODELS_CONFIG["deepseek-main"]["display_name"], "主脑对话")

    def test_save_model_config_requires_redacted_save_runtime(self):
        original = self._install_fake_brain({})
        try:
            fake_brain = sys.modules["brain"]
            delattr(fake_brain, "save_raw_config")
            result = asyncio.run(
                save_model_config(
                    {
                        "id": "deepseek-main",
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
        self.assertFalse(result["ok"])
        self.assertIn("save_raw_config", result["error"])
        self.assertNotIn("deepseek-main", fake_brain.MODELS_CONFIG)


if __name__ == "__main__":
    unittest.main()
