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

    def test_pick_vision_model_config_prefers_capable_model(self):
        picked = model_runtime.pick_vision_model_config(
            {"model": "deepseek-chat", "vision": False},
            {
                "deepseek-chat": {"model": "deepseek-chat", "vision": False},
                "gpt-4o": {"model": "gpt-4o", "vision": True},
            },
        )

        self.assertEqual(picked, {"model": "gpt-4o", "vision": True})

    def test_vision_llm_call_skips_when_no_vision_model_exists(self):
        calls = []

        def _fake_openai_call(*args, **kwargs):
            calls.append((args, kwargs))
            return {"content": "should-not-run", "usage": {}}

        result = model_runtime.vision_llm_call(
            "describe",
            images=["abc123"],
            llm_config={"model": "deepseek-chat", "vision": False},
            models_config={"deepseek-chat": {"model": "deepseek-chat", "vision": False}},
            llm_call_openai_fn=_fake_openai_call,
        )

        self.assertEqual(result, "")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
