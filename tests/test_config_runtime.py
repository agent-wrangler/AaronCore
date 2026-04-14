import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brain import config_runtime


class ConfigRuntimeTests(unittest.TestCase):
    def test_save_raw_config_splits_api_keys_into_local_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            public_path = Path(tmpdir) / "llm_config.json"
            local_path = Path(tmpdir) / "llm_config.local.json"
            merged_config = {
                "models": {
                    "deepseek-chat": {
                        "api_key": "sk-live-123456",
                        "base_url": "https://api.deepseek.com/v1",
                        "model": "deepseek-chat",
                        "display_name": "DeepSeek 主聊",
                        "transport": "openai_api",
                        "vision": False,
                    }
                },
                "default": "deepseek-chat",
            }

            with patch.object(config_runtime, "LLM_CONFIG_FILE", public_path), patch.object(
                config_runtime, "LLM_LOCAL_CONFIG_FILE", local_path
            ):
                config_runtime.save_raw_config(merged_config)

                public_data = json.loads(public_path.read_text(encoding="utf-8"))
                local_data = json.loads(local_path.read_text(encoding="utf-8"))

            self.assertEqual(public_data["models"]["deepseek-chat"]["api_key"], "")
            self.assertEqual(
                local_data["models"]["deepseek-chat"]["api_key"],
                "sk-live-123456",
            )
            self.assertEqual(public_data["models"]["deepseek-chat"]["provider_key"], "deepseek")
            self.assertEqual(public_data["models"]["deepseek-chat"]["provider"], "openai")
            self.assertEqual(public_data["models"]["deepseek-chat"]["api_mode"], "chat_completions")
            self.assertEqual(public_data["models"]["deepseek-chat"]["auth_mode"], "api_key")
            self.assertEqual(public_data["models"]["deepseek-chat"]["display_name"], "DeepSeek 主聊")

    def test_load_raw_config_merges_local_api_keys_back(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            public_path = Path(tmpdir) / "llm_config.json"
            local_path = Path(tmpdir) / "llm_config.local.json"
            public_path.write_text(
                json.dumps(
                    {
                        "models": {
                            "deepseek-chat": {
                                "api_key": "",
                                "base_url": "https://api.deepseek.com/v1",
                                "model": "deepseek-chat",
                                "transport": "openai_api",
                                "vision": False,
                            }
                        },
                        "default": "deepseek-chat",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            local_path.write_text(
                json.dumps(
                    {"models": {"deepseek-chat": {"api_key": "sk-live-abcdef"}}},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            with patch.object(config_runtime, "LLM_CONFIG_FILE", public_path), patch.object(
                config_runtime, "LLM_LOCAL_CONFIG_FILE", local_path
            ):
                merged = config_runtime._load_raw_config()

            self.assertEqual(
                merged["models"]["deepseek-chat"]["api_key"],
                "sk-live-abcdef",
            )

    def test_normalize_raw_config_marks_anthropic_message_mode(self):
        normalized = config_runtime._normalize_raw_config(
            {
                "models": {
                    "claude-sonnet": {
                        "api_key": "sk-live-abcdef",
                        "base_url": "https://api.anthropic.com/v1",
                        "model": "claude-sonnet-4-20250514",
                    }
                },
                "default": "claude-sonnet",
            }
        )

        cfg = normalized["models"]["claude-sonnet"]
        self.assertEqual(cfg["provider_key"], "claude")
        self.assertEqual(cfg["provider"], "anthropic")
        self.assertEqual(cfg["api_mode"], "anthropic_messages")
        self.assertEqual(cfg["auth_mode"], "api_key")

    def test_normalize_raw_config_prefers_gateway_base_url_for_provider_key(self):
        normalized = config_runtime._normalize_raw_config(
            {
                "models": {
                    "gateway-claude": {
                        "api_key": "sk-live-abcdef",
                        "base_url": "https://api.minimaxi.com/anthropic/v1",
                        "model": "claude-sonnet-4-6",
                        "provider_key": "claude",
                        "provider": "anthropic",
                    }
                },
                "default": "gateway-claude",
            }
        )

        cfg = normalized["models"]["gateway-claude"]
        self.assertEqual(cfg["provider_key"], "minimax")
        self.assertEqual(cfg["provider"], "minimax")
        self.assertEqual(cfg["api_mode"], "chat_completions")


if __name__ == "__main__":
    unittest.main()
