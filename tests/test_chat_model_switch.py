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
        self.assertIn("已配置的：", reply)
        self.assertIn("← 当前", reply)
        self.assertIn("还可以用：", reply)

    def test_is_placeholder_key_rejects_templates(self):
        self.assertTrue(is_placeholder_key("sk-xxx"))
        self.assertTrue(is_placeholder_key("请填写你的key"))
        self.assertFalse(is_placeholder_key("sk-live-1234567890abcdef"))

    def test_detect_model_switch_lists_provider_models_for_vague_request(self):
        fake_brain = types.SimpleNamespace(
            MODELS_CONFIG={
                "gpt-5.4": {
                    "base_url": "https://api.openai.com/v1",
                    "api_key": "sk-live-1234567890abcdef",
                    "model": "gpt-5.4",
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
            result = detect_model_switch("换成 openai")
        finally:
            if original is None:
                sys.modules.pop("brain", None)
            else:
                sys.modules["brain"] = original
        self.assertIsInstance(result, dict)
        self.assertIn("OPENAI", result["reply"])
        self.assertIn("列出 openai 可用模型", result["trace"])

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
            result = detect_model_switch("换成 gpt-5.4")
        finally:
            if original is None:
                sys.modules.pop("brain", None)
            else:
                sys.modules["brain"] = original
        self.assertTrue(result["model_changed"])
        self.assertIn("gpt-5.4", result["reply"].lower())


if __name__ == "__main__":
    unittest.main()
