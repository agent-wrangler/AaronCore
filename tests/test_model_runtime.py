import copy
import unittest

from brain import model_runtime


class ModelRuntimeTests(unittest.TestCase):
    def test_set_default_model_requires_redacted_save_runtime(self):
        ok, new_default, new_cfg = model_runtime.set_default_model(
            "deepseek-chat",
            models_config={"deepseek-chat": {"model": "deepseek-chat"}},
            raw_config={"models": {"deepseek-chat": {"model": "deepseek-chat"}}, "default": "other"},
            config_path="unused.json",
            save_raw_config_fn=None,
        )

        self.assertFalse(ok)
        self.assertEqual(new_default, "")
        self.assertEqual(new_cfg, {})

    def test_set_default_model_persists_through_save_runtime(self):
        saved = {}
        raw_config = {"models": {"deepseek-chat": {"model": "deepseek-chat"}}, "default": "other"}

        def _save_raw_config(raw):
            saved.update(copy.deepcopy(raw))

        ok, new_default, new_cfg = model_runtime.set_default_model(
            "deepseek-chat",
            models_config={"deepseek-chat": {"model": "deepseek-chat"}},
            raw_config=raw_config,
            config_path="unused.json",
            save_raw_config_fn=_save_raw_config,
        )

        self.assertTrue(ok)
        self.assertEqual(new_default, "deepseek-chat")
        self.assertEqual(new_cfg["model"], "deepseek-chat")
        self.assertEqual(saved["default"], "deepseek-chat")


if __name__ == "__main__":
    unittest.main()
