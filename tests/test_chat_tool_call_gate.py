import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

import routes.chat_tool_call_gate as gate_module
from routes.chat_tool_call_gate import (
    build_tool_call_unavailable_reply,
    get_cod_enabled,
    get_tool_call_enabled,
    get_tool_call_unavailable_reason,
    is_anthropic_model,
)


class ChatToolCallGateTests(unittest.TestCase):
    def test_config_flags_are_loaded_from_runtime_state_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "tool_call.json"
            config_path.write_text(json.dumps({"enabled": False, "cod_enabled": True}), encoding="utf-8")
            fake_loader = types.ModuleType("core.runtime_state.state_loader")
            fake_loader.TOOL_CALL_CONFIG_FILE = config_path
            original = sys.modules.get("core.runtime_state.state_loader")
            sys.modules["core.runtime_state.state_loader"] = fake_loader
            try:
                self.assertFalse(get_tool_call_enabled())
                self.assertTrue(get_cod_enabled())
            finally:
                if original is None:
                    sys.modules.pop("core.runtime_state.state_loader", None)
                else:
                    sys.modules["core.runtime_state.state_loader"] = original

    def test_is_anthropic_model_detects_current_base_url(self):
        original = sys.modules.get("brain")
        sys.modules["brain"] = types.SimpleNamespace(LLM_CONFIG={"base_url": "https://x.example.com/anthropic/v1"})
        try:
            self.assertTrue(is_anthropic_model())
        finally:
            if original is None:
                sys.modules.pop("brain", None)
            else:
                sys.modules["brain"] = original

    def test_get_tool_call_unavailable_reason_prioritizes_disabled(self):
        original_enabled = gate_module.get_tool_call_enabled
        original_anthropic = gate_module.is_anthropic_model
        original_ready = gate_module.S.NOVA_CORE_READY
        gate_module.get_tool_call_enabled = lambda: False
        gate_module.is_anthropic_model = lambda: False
        gate_module.S.NOVA_CORE_READY = True
        try:
            self.assertEqual("disabled", get_tool_call_unavailable_reason())
        finally:
            gate_module.get_tool_call_enabled = original_enabled
            gate_module.is_anthropic_model = original_anthropic
            gate_module.S.NOVA_CORE_READY = original_ready

    def test_build_tool_call_unavailable_reply_contains_reason_text(self):
        reply = build_tool_call_unavailable_reply("unsupported_model")
        self.assertIn("tool_call", reply)
        self.assertIn("主链", reply)


if __name__ == "__main__":
    unittest.main()
