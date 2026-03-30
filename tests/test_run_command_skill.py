import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.executor as executor_module
import core.reply_formatter as reply_formatter_module
import core.tool_adapter as tool_adapter_module
import core.skills.run_code as run_code_module
import core.skills.run_command as run_command_module


class RunCommandSkillTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmpdir.name).resolve()
        self.notes_dir = self.workspace / "notes_app"
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        (self.notes_dir / "notes_gui.py").write_text("print('hello')\n", encoding="utf-8")
        self.desktop_dir = self.workspace / "desktop"
        self.desktop_dir.mkdir(parents=True, exist_ok=True)
        self._workspace_patch = patch.object(run_command_module, "WORKSPACE_ROOT", self.workspace)
        self._workspace_patch.start()

    def tearDown(self):
        self._workspace_patch.stop()
        self._tmpdir.cleanup()

    def test_execute_repairs_common_pyinstaller_flags_and_verifies_artifact(self):
        command = (
            'pyinstaller --onefile --windowed --name NovaNotes '
            '--destpath "../desktop" -- noconfirm notes_gui.py'
        )

        def fake_run(argv, **kwargs):
            self.assertIn("--distpath", argv)
            self.assertIn("--noconfirm", argv)
            self.assertNotIn("--destpath", argv)
            artifact = self.desktop_dir / "NovaNotes.exe"
            artifact.write_text("binary placeholder", encoding="utf-8")

            class Result:
                returncode = 0
                stdout = "build ok"
                stderr = ""

            return Result()

        with patch("core.skills.run_command.subprocess.run", side_effect=fake_run):
            result = run_command_module.execute(
                "",
                {
                    "command": command,
                    "workdir": str(self.notes_dir),
                    "description": "build NovaNotes",
                },
            )

        self.assertEqual(result.get("drift", {}).get("reason"), "")
        self.assertTrue(result.get("verification", {}).get("verified"))
        self.assertIn("repaired --destpath to --distpath", result.get("verification", {}).get("detail", ""))
        self.assertIn(str(self.desktop_dir / "NovaNotes.exe"), result.get("verification", {}).get("detail", ""))

    def test_execute_blocks_dangerous_command(self):
        result = run_command_module.execute(
            "",
            {
                "command": 'powershell -Command "Remove-Item C:/tmp/test -Recurse -Force"',
                "workdir": str(self.workspace),
            },
        )

        self.assertEqual(result.get("drift", {}).get("reason"), "disallowed_command")
        self.assertFalse(result.get("verification", {}).get("verified"))


class RunCodeGuardTests(unittest.TestCase):
    def test_run_code_rejects_packaging_requests(self):
        result = run_code_module.execute("把 notes_gui.py 打包成 exe 放到桌面")

        self.assertEqual(result.get("drift", {}).get("reason"), "wrong_tool_selected")
        self.assertEqual(result.get("drift", {}).get("repair_hint"), "use_run_command")
        self.assertFalse(result.get("verification", {}).get("verified"))


class ToolingPromptTests(unittest.TestCase):
    def test_executor_preserves_verification_meta_for_dict_skill_results(self):
        fake_result = {
            "reply": "ok",
            "state": {"expected_state": "command_succeeded", "observed_state": "command_succeeded"},
            "drift": {"reason": "", "repair_hint": ""},
            "action": {"action_kind": "run_command", "target_kind": "process", "target": "pytest", "outcome": "verified"},
            "verification": {"verified": True, "observed_state": "command_succeeded", "detail": "exit_code=0"},
        }

        with patch("core.executor.get_skill", return_value={"execute": lambda _user, _ctx: fake_result}):
            result = executor_module.execute({"skill": "fake_skill"}, "run tests", {})

        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("meta", {}).get("verification", {}).get("detail"), "exit_code=0")

    def test_build_tool_call_system_prompt_mentions_run_command_guidance(self):
        prompt = reply_formatter_module._build_tool_call_system_prompt(
            {
                "l3": [],
                "l4": {},
                "l5": {},
                "l7": [],
                "l8": [],
                "l2_memories": [],
                "current_model": "test-model",
            }
        )

        self.assertIn("run_command", prompt)
        self.assertIn("Do not use run_code", prompt)

    def test_build_tools_list_cod_includes_run_command(self):
        with patch.object(
            tool_adapter_module,
            "_get_all_skills",
            return_value={
                "run_command": {
                    "execute": lambda *_args, **_kwargs: None,
                    "description": "Run a safe local workspace command.",
                    "parameters": {
                        "type": "object",
                        "properties": {"command": {"type": "string"}},
                        "required": ["command"],
                    },
                }
            },
        ):
            tools = tool_adapter_module.build_tools_list_cod()

        names = [item.get("function", {}).get("name") for item in tools if isinstance(item, dict)]
        self.assertIn("run_command", names)


if __name__ == "__main__":
    unittest.main()
