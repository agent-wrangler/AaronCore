import sys
import tempfile
import types
import unittest
from pathlib import Path

from routes.chat_model_switch import (
    build_model_list_reply,
    detect_model_switch,
    is_placeholder_key,
    match_provider,
)


class ChatModelSwitchTests(unittest.TestCase):
    def test_match_provider_finds_provider_and_donor(self):
        provider_key, donor_cfg = match_provider(
            "openai",
            {
                "gpt-5.4": {
                    "base_url": "https://api.openai.com/v1",
                    "model": "gpt-5.4",
                }
            },
        )
        self.assertEqual(provider_key, "openai")
        self.assertEqual(donor_cfg["model"], "gpt-5.4")

    def test_match_provider_prefers_explicit_provider_key(self):
        provider_key, donor_cfg = match_provider(
            "openai",
            {
                "workspace-gpt": {
                    "base_url": "https://gateway.example.internal/v1",
                    "model": "gpt-5.4",
                    "provider_key": "openai",
                }
            },
        )
        self.assertEqual(provider_key, "openai")
        self.assertEqual(donor_cfg["model"], "gpt-5.4")

    def test_match_provider_prefers_gateway_host_over_anthropic_path(self):
        provider_key, donor_cfg = match_provider(
            "minimax",
            {
                "gateway-claude": {
                    "base_url": "https://api.minimaxi.com/anthropic/v1",
                    "model": "claude-sonnet-4-6",
                    "provider_key": "claude",
                }
            },
        )
        self.assertEqual(provider_key, "minimax")
        self.assertEqual(donor_cfg["model"], "claude-sonnet-4-6")

    def test_build_model_list_reply_marks_current_and_suggestions(self):
        reply = build_model_list_reply(
            "openai",
            "openai",
            {"base_url": "https://api.openai.com/v1"},
            {
                "gpt-5.4": {"base_url": "https://api.openai.com/v1", "model": "gpt-5.4"},
            },
            "gpt-5.4",
        )
        self.assertIn("OPENAI", reply)
        self.assertIn("gpt-5.4", reply)
        self.assertIn("gpt-4o", reply)
        self.assertIn("[current]", reply)

    def test_detect_model_switch_matches_display_name(self):
        state = {"current": "deepseek-chat"}

        def _set_default(mid):
            state["current"] = mid
            fake_brain._current_default = mid
            return True

        fake_brain = types.SimpleNamespace(
            MODELS_CONFIG={
                "deepseek-chat": {
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key": "sk-live-abcdef1234567890",
                    "model": "deepseek-chat",
                    "display_name": "deepseek-main",
                },
                "gpt-5.4": {
                    "base_url": "https://api.openai.com/v1",
                    "api_key": "sk-live-1234567890abcdef",
                    "model": "gpt-5.4",
                },
            },
            _current_default="gpt-5.4",
            _raw_config={"models": {}},
            config_path=str(Path(tempfile.gettempdir()) / "unused-model-config.json"),
            set_default_model=_set_default,
            get_current_model_name=lambda: "deepseek-main",
        )
        original = sys.modules.get("brain")
        sys.modules["brain"] = fake_brain
        try:
            result = detect_model_switch("switch deepseek-main")
        finally:
            if original is None:
                sys.modules.pop("brain", None)
            else:
                sys.modules["brain"] = original
        self.assertTrue(result["model_changed"])
        self.assertIn("deepseek-main", result["reply"])

    def test_is_placeholder_key_rejects_templates(self):
        self.assertTrue(is_placeholder_key("sk-xxx"))
        self.assertTrue(is_placeholder_key("your-api-key"))
        self.assertFalse(is_placeholder_key("sk-live-1234567890abcdef"))

    def test_detect_model_switch_lists_provider_models_for_vague_request(self):
        fake_brain = types.SimpleNamespace(
            MODELS_CONFIG={
                "gpt-5.4": {
                    "base_url": "https://gateway.example.internal/v1",
                    "api_key": "sk-live-1234567890abcdef",
                    "model": "gpt-5.4",
                    "provider_key": "openai",
                }
            },
            _current_default="gpt-5.4",
            _raw_config={"models": {}},
            config_path=str(Path(tempfile.gettempdir()) / "unused-model-config.json"),
            set_default_model=lambda _mid: True,
            get_current_model_name=lambda: "gpt-5.4",
        )
        original = sys.modules.get("brain")
        sys.modules["brain"] = fake_brain
        try:
            result = detect_model_switch("switch openai")
        finally:
            if original is None:
                sys.modules.pop("brain", None)
            else:
                sys.modules["brain"] = original
        self.assertIsInstance(result, dict)
        self.assertIn("OPENAI", result["reply"])
        self.assertIn("list models", result["trace"])

    def test_detect_model_switch_switches_exact_model_id(self):
        state = {"current": "deepseek-chat"}

        def _set_default(mid):
            state["current"] = mid
            fake_brain._current_default = mid
            return True

        fake_brain = types.SimpleNamespace(
            MODELS_CONFIG={
                "gpt-5.4": {
                    "base_url": "https://api.openai.com/v1",
                    "api_key": "sk-live-1234567890abcdef",
                    "model": "gpt-5.4",
                },
                "deepseek-chat": {
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key": "sk-live-abcdef1234567890",
                    "model": "deepseek-chat",
                },
            },
            _current_default="deepseek-chat",
            _raw_config={"models": {}},
            config_path=str(Path(tempfile.gettempdir()) / "unused-model-config.json"),
            set_default_model=_set_default,
            get_current_model_name=lambda: state["current"],
        )
        original = sys.modules.get("brain")
        sys.modules["brain"] = fake_brain
        try:
            result = detect_model_switch("switch gpt-5.4")
        finally:
            if original is None:
                sys.modules.pop("brain", None)
            else:
                sys.modules["brain"] = original
        self.assertTrue(result["model_changed"])
        self.assertIn("gpt-5.4", result["reply"].lower())

    def test_check_model_ready_accepts_codex_cli_login(self):
        state = {"current": "deepseek-chat"}

        def _set_default(mid):
            state["current"] = mid
            fake_brain._current_default = mid
            return True

        fake_brain = types.SimpleNamespace(
            MODELS_CONFIG={
                "gpt-5.4": {
                    "base_url": "codex://local",
                    "transport": "codex_cli",
                    "auth_mode": "codex_cli",
                    "model": "gpt-5.4",
                },
                "deepseek-chat": {
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key": "sk-live-abcdef1234567890",
                    "model": "deepseek-chat",
                },
            },
            _current_default="deepseek-chat",
            _raw_config={"models": {}},
            config_path=str(Path(tempfile.gettempdir()) / "unused-model-config.json"),
            set_default_model=_set_default,
            get_current_model_name=lambda: state["current"],
            validate_codex_cli_login=lambda timeout=8: (True, ""),
        )
        original = sys.modules.get("brain")
        sys.modules["brain"] = fake_brain
        try:
            result = detect_model_switch("switch gpt-5.4")
        finally:
            if original is None:
                sys.modules.pop("brain", None)
            else:
                sys.modules["brain"] = original
        self.assertTrue(result["model_changed"])
        self.assertIn("gpt-5.4", result["reply"].lower())


if __name__ == "__main__":
    unittest.main()
