import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.executor as executor_module
import core.reply_formatter as reply_formatter_module
import core.tool_adapter as tool_adapter_module
import tools.agent.game_templates as game_templates_module
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

    def test_execute_adapts_simple_file_copy_commands(self):
        source = self.workspace / "a.txt"
        dest = self.workspace / "b.txt"
        source.write_text("hello", encoding="utf-8")

        result = run_command_module.execute(
            "",
            {
                "command": f'cp "{source}" "{dest}"',
                "workdir": str(self.workspace),
            },
        )

        self.assertEqual(result.get("drift", {}).get("reason"), "")
        self.assertTrue(result.get("verification", {}).get("verified"))
        self.assertTrue(dest.exists())
        self.assertEqual(dest.read_text(encoding="utf-8"), "hello")
        self.assertIn("delegated_from=run_command", result.get("verification", {}).get("detail", ""))

    def test_execute_allows_user_home_project_outside_workspace(self):
        with tempfile.TemporaryDirectory() as home_tmp:
            home_dir = Path(home_tmp).resolve()
            project_dir = home_dir / "NovaNotes"
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "app.py").write_text("print('ok')\n", encoding="utf-8")

            def fake_run(argv, **kwargs):
                self.assertEqual(kwargs.get("cwd"), str(project_dir))
                self.assertEqual(argv[1], str(project_dir / "app.py"))

                class Result:
                    returncode = 0
                    stdout = "ok"
                    stderr = ""

                return Result()

            with patch.object(run_command_module, "USER_HOME", home_dir), patch(
                "core.skills.run_command.subprocess.run",
                side_effect=fake_run,
            ):
                result = run_command_module.execute(
                    "",
                    {
                        "command": "python app.py",
                        "workdir": str(project_dir),
                    },
                )

        self.assertTrue(result.get("verification", {}).get("verified"))
        self.assertEqual(result.get("drift", {}).get("reason"), "")

    def test_execute_background_launch_treats_running_process_as_success(self):
        class FakeProcess:
            pid = 4242

            def poll(self):
                return None

        with patch("core.skills.run_command.subprocess.Popen", return_value=FakeProcess()), patch(
            "core.skills.run_command.time.sleep",
            lambda _seconds: None,
        ):
            result = run_command_module.execute(
                "",
                {
                    "command": "python app.py",
                    "workdir": str(self.notes_dir),
                    "description": "启动 NovaNotes Flask 应用",
                    "background": True,
                },
            )

        self.assertTrue(result.get("verification", {}).get("verified"))
        self.assertEqual(result.get("verification", {}).get("observed_state"), "process_running")
        self.assertIn("pid=4242", result.get("verification", {}).get("detail", ""))

    def test_execute_background_launch_reports_early_exit_output(self):
        class FakeProcess:
            pid = 4243
            returncode = 1

            def poll(self):
                return 1

            def communicate(self):
                return ("", "ModuleNotFoundError: No module named 'flask'")

        with patch("core.skills.run_command.subprocess.Popen", return_value=FakeProcess()), patch(
            "core.skills.run_command.time.sleep",
            lambda _seconds: None,
        ):
            result = run_command_module.execute(
                "",
                {
                    "command": "python app.py",
                    "workdir": str(self.notes_dir),
                    "description": "启动 NovaNotes Flask 应用",
                    "background": True,
                },
            )

        self.assertFalse(result.get("verification", {}).get("verified"))
        self.assertEqual(result.get("verification", {}).get("observed_state"), "process_exited_early")
        self.assertIn("ModuleNotFoundError", result.get("verification", {}).get("detail", ""))

    def test_execute_verify_lane_uses_fs_target_parent_as_default_workdir(self):
        target = self.notes_dir / "app.py"
        target.write_text("print('verify')\n", encoding="utf-8")

        def fake_run(argv, **kwargs):
            self.assertEqual(kwargs.get("cwd"), str(self.notes_dir))
            self.assertEqual(argv[1], str(target))

            class Result:
                returncode = 0
                stdout = "ok"
                stderr = ""

            return Result()

        with patch("core.skills.run_command.subprocess.run", side_effect=fake_run):
            result = run_command_module.execute(
                "",
                {
                    "command": "python app.py",
                    "fs_target": {"path": str(target), "option": "inspect"},
                    "execution_lane": "verify",
                    "current_step_task": {
                        "task_id": "task_step_verify",
                        "title": "Verify the patch",
                        "status": "in_progress",
                        "execution_lane": "verify",
                    },
                },
            )

        self.assertTrue(result.get("verification", {}).get("verified"))
        self.assertEqual(result.get("drift", {}).get("reason"), "")

    def test_execute_verify_lane_does_not_auto_background_launch(self):
        target = self.notes_dir / "app.py"
        target.write_text("print('verify')\n", encoding="utf-8")

        def fake_run(argv, **kwargs):
            self.assertEqual(kwargs.get("cwd"), str(self.notes_dir))
            self.assertEqual(argv[1], str(target))

            class Result:
                returncode = 0
                stdout = "ok"
                stderr = ""

            return Result()

        with patch("core.skills.run_command.subprocess.run", side_effect=fake_run) as run_mock, patch(
            "core.skills.run_command.subprocess.Popen",
            side_effect=AssertionError("verify lane should stay foreground unless background is explicit"),
        ):
            result = run_command_module.execute(
                "",
                {
                    "command": "python app.py",
                    "description": "launch local app for verification",
                    "fs_target": {"path": str(target), "option": "inspect"},
                    "execution_lane": "verify",
                    "current_step_task": {
                        "task_id": "task_step_verify",
                        "title": "Verify the patch",
                        "status": "in_progress",
                        "execution_lane": "verify",
                    },
                },
            )

        self.assertEqual(run_mock.call_count, 1)
        self.assertTrue(result.get("verification", {}).get("verified"))
        self.assertEqual(result.get("verification", {}).get("observed_state"), "command_succeeded")


class RunCodeGuardTests(unittest.TestCase):
    def test_run_code_rejects_packaging_requests(self):
        result = run_code_module.execute("鎶?notes_gui.py 鎵撳寘鎴?exe 鏀惧埌妗岄潰")

        self.assertEqual(result.get("drift", {}).get("reason"), "wrong_tool_selected")
        self.assertEqual(result.get("drift", {}).get("repair_hint"), "use_run_command")
        self.assertFalse(result.get("verification", {}).get("verified"))

    def test_run_code_builds_browser_game_for_generic_request(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir).resolve()
            with patch.object(run_code_module, "_resolve_output_dir", return_value=output_dir), patch.object(
                run_code_module.webbrowser,
                "open",
                return_value=True,
            ), patch.object(
                run_code_module,
                "execute_ask_user",
                return_value={"success": True, "response": "用户选择了：贪吃蛇"},
            ):
                result = run_code_module.execute("给我搞个小游戏玩玩")
            target = Path(result.get("action", {}).get("target", ""))
            self.assertTrue(result.get("verification", {}).get("verified"))
            self.assertEqual(result.get("verification", {}).get("observed_state"), "browser_opened")
            self.assertEqual(target.suffix, ".html")
            self.assertTrue(target.exists())
            content = target.read_text(encoding="utf-8")
            self.assertIn("snake", content)
            self.assertIn("重新开始", content)
            self.assertIn("<canvas", content)
            self.assertEqual((result.get("task_plan") or {}).get("phase"), "done")

    def test_run_code_prefers_requested_template_and_theme(self):
        spec = run_code_module._build_game_spec("做个赛博风贪吃蛇")

        self.assertEqual(spec.get("template"), "snake")
        self.assertEqual(spec.get("theme"), "neon")
        self.assertIn("贪吃蛇", spec.get("title", ""))

    def test_run_code_uses_external_template_registry(self):
        script = game_templates_module.get_template_script("snake")

        self.assertIn("function createGame", script)
        self.assertIn("长度 3", script)

    def test_run_code_skips_template_choice_for_explicit_request(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir).resolve()
            with patch.object(run_code_module, "_resolve_output_dir", return_value=output_dir), patch.object(
                run_code_module.webbrowser,
                "open",
                return_value=True,
            ), patch.object(
                run_code_module,
                "execute_ask_user",
                side_effect=AssertionError("explicit template should not trigger ask_user"),
            ):
                result = run_code_module.execute("做个贪吃蛇")

        self.assertTrue(result.get("verification", {}).get("verified"))
        self.assertEqual((result.get("task_plan") or {}).get("phase"), "done")

    def test_run_code_surfaces_waiting_plan_when_template_choice_times_out(self):
        with patch.object(
            run_code_module,
            "execute_ask_user",
            return_value={"success": False, "response": ""},
        ):
            result = run_code_module.execute("给我来个小游戏")

        plan = result.get("task_plan") or {}
        statuses = {item.get("id"): item.get("status") for item in plan.get("items") or []}
        self.assertFalse(result.get("verification", {}).get("verified"))
        self.assertEqual(plan.get("current_item_id"), "choose_approach")
        self.assertEqual(statuses.get("choose_approach"), "running")


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

    def test_build_tool_call_system_prompt_uses_prose_instruction_blocks(self):
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

        self.assertIn("回复要求（优先级最高，必须遵守）：\n你拥有完整的记忆系统", prompt)
        self.assertNotIn("回复要求（优先级最高，必须遵守）：\n1.", prompt)
        self.assertNotIn("\n- 工具使用的主判断", prompt)
        self.assertNotIn("列表/分点/编号", prompt)
        self.assertIn("普通聊天默认直接接话", prompt)

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
