import unittest

from tools import live_llm_replay as live_replay_module


class LiveReplayFixtureTests(unittest.TestCase):
    def test_recorded_fixture_case_is_loaded(self):
        case = live_replay_module.get_replay_case("recorded_retry_desktop_after_partial_check")

        self.assertEqual(case.query, "再试试看 能看到桌面的文件夹吗")
        self.assertEqual(case.expected_tool_any, ("folder_explore",))
        self.assertTrue(bool(case.dialogue_context))

    def test_recorded_runtime_preset_includes_fixture_cases(self):
        presets = live_replay_module.get_replay_presets()

        self.assertIn("recorded_continue_after_login_blocker", presets["recorded_runtime_guardrails"])
        self.assertIn("recorded_waiting_user_completion_resume", presets["recorded_runtime_guardrails"])
        self.assertIn("recorded_verify_failed_retry_resume", presets["recorded_runtime_guardrails"])
        self.assertIn("recorded_retry_desktop_after_partial_check", presets["full_runtime_guardrails"])
        self.assertIn("recorded_interrupt_reason_first", presets["full_runtime_guardrails"])

    def test_external_eval_suite_is_loaded(self):
        suite = live_replay_module.get_eval_suite("recorded_runtime_regressions")

        self.assertEqual(suite.preset_ids, ("recorded_runtime_guardrails",))
        self.assertTrue(suite.strict_by_default)
        self.assertTrue(live_replay_module.suite_defaults_to_strict(["recorded_runtime_regressions"]))

    def test_run_eval_suite_uses_external_suite_selection(self):
        report = live_replay_module.run_eval_suite(["recorded_runtime_regressions"], dry_run=True)

        self.assertEqual(report["summary"]["suite_ids"], ["recorded_runtime_regressions"])
        self.assertTrue(report["summary"]["suite_strict_default"])
        self.assertEqual(report["summary"]["failed"], 0)
        case_ids = {item["case"]["case_id"] for item in report["results"]}
        self.assertIn("recorded_continue_after_login_blocker", case_ids)
        self.assertIn("recorded_retry_desktop_after_partial_check", case_ids)
        self.assertIn("recorded_waiting_user_completion_resume", case_ids)
        self.assertIn("recorded_verify_failed_retry_resume", case_ids)

    def test_dry_run_recorded_continue_case_keeps_detached_and_uses_dialogue_context(self):
        case = live_replay_module.get_replay_case("recorded_continue_after_login_blocker")

        report = live_replay_module.run_replay_case(case, dry_run=True)

        self.assertFalse(report["prompt"]["active_context_used"])
        self.assertTrue(report["prompt"]["dialogue_context_used"])
        self.assertEqual(report["prompt"]["query_mode"], "")
        self.assertTrue(report["checks"]["pass"])

    def test_dry_run_recorded_retry_case_keeps_execution_bias(self):
        case = live_replay_module.get_replay_case("recorded_retry_desktop_after_partial_check")

        report = live_replay_module.run_replay_case(case, dry_run=True)

        self.assertTrue(report["prompt"]["active_context_used"])
        self.assertTrue(report["prompt"]["dialogue_context_used"])
        self.assertEqual(report["prompt"]["query_mode"], "")
        self.assertTrue(report["checks"]["pass"])

    def test_dry_run_waiting_user_completion_case_restores_continue_mode(self):
        case = live_replay_module.get_replay_case("recorded_waiting_user_completion_resume")

        report = live_replay_module.run_replay_case(case, dry_run=True)

        self.assertTrue(report["prompt"]["active_context_used"])
        self.assertTrue(report["prompt"]["dialogue_context_used"])
        self.assertEqual(report["prompt"]["query_mode"], "continue")
        self.assertTrue(report["checks"]["pass"])

    def test_dry_run_verify_failed_retry_case_restores_continue_mode(self):
        case = live_replay_module.get_replay_case("recorded_verify_failed_retry_resume")

        report = live_replay_module.run_replay_case(case, dry_run=True)

        self.assertTrue(report["prompt"]["active_context_used"])
        self.assertTrue(report["prompt"]["dialogue_context_used"])
        self.assertEqual(report["prompt"]["query_mode"], "continue")
        self.assertTrue(report["checks"]["pass"])

    def test_dry_run_interrupt_prompt_marks_explain_only_policy(self):
        case = live_replay_module.get_replay_case("interrupt_question")

        report = live_replay_module.run_replay_case(case, dry_run=True, show_prompts=True)

        self.assertIn("Turn execution policy: explain_only", report["prompt"]["user_prompt"])
        self.assertIn("This turn is explanation-only.", report["prompt"]["user_prompt"])

    def test_system_prompt_requires_explicit_continuity_block_before_auto_resume(self):
        case = live_replay_module.get_replay_case("recorded_continue_after_login_blocker")

        report = live_replay_module.run_replay_case(case, dry_run=True, show_prompts=True)

        self.assertIn(
            "Only auto-continue or resume a previous task when the current user prompt includes the explicit task continuity block.",
            report["prompt"]["system_prompt"],
        )

    def test_dialogue_background_guidance_is_injected_without_continuity_block(self):
        case = live_replay_module.get_replay_case("recorded_continue_after_login_blocker")

        bundle = live_replay_module._build_bundle(
            case.query,
            model_name="deepseek-chat",
            cod_mode=False,
            dialogue_context=case.dialogue_context,
        )
        _system_prompt, _user_prompt, messages = live_replay_module._build_messages(bundle)

        self.assertTrue(
            any(
                live_replay_module.BACKGROUND_DIALOGUE_ONLY_GUIDANCE in str(item.get("content") or "")
                for item in messages
            )
        )


if __name__ == "__main__":
    unittest.main()
