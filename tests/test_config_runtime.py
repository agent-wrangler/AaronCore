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


if __name__ == "__main__":
    unittest.main()
