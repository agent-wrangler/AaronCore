import unittest

from tools import live_llm_replay as live_replay_module


class LiveReplayHarnessTests(unittest.TestCase):
    def test_dry_run_blocker_case_keeps_blocker_query_mode(self):
        case = live_replay_module.get_replay_case("blocker_question")

        report = live_replay_module.run_replay_case(case, dry_run=True)

        self.assertTrue(report["prompt"]["active_context_used"])
        self.assertEqual(report["prompt"]["query_mode"], "blocker")
        self.assertTrue(report["checks"]["active_context_ok"])
        self.assertTrue(report["checks"]["query_mode_ok"])
        self.assertTrue(report["checks"]["pass"])

    def test_dry_run_unrelated_small_talk_stays_detached(self):
        case = live_replay_module.get_replay_case("unrelated_small_talk")

        report = live_replay_module.run_replay_case(case, dry_run=True)

        self.assertFalse(report["prompt"]["active_context_used"])
        self.assertFalse(report["prompt"]["resumed_task"])
        self.assertEqual(report["prompt"]["query_mode"], "")
        self.assertTrue(report["checks"]["pass"])

    def test_dry_run_interrupt_case_keeps_interrupt_query_mode(self):
        case = live_replay_module.get_replay_case("interrupt_question")

        report = live_replay_module.run_replay_case(case, dry_run=True)

        self.assertTrue(report["prompt"]["active_context_used"])
        self.assertEqual(report["prompt"]["query_mode"], "interrupt")
        self.assertTrue(report["checks"]["active_context_ok"])
        self.assertTrue(report["checks"]["query_mode_ok"])
        self.assertTrue(report["checks"]["pass"])

    def test_dry_run_resume_after_interrupt_keeps_continue_query_mode(self):
        case = live_replay_module.get_replay_case("resume_after_interrupt")

        report = live_replay_module.run_replay_case(case, dry_run=True)

        self.assertTrue(report["prompt"]["active_context_used"])
        self.assertEqual(report["prompt"]["query_mode"], "continue")
        self.assertTrue(report["checks"]["active_context_ok"])
        self.assertTrue(report["checks"]["query_mode_ok"])
        self.assertTrue(report["checks"]["pass"])

    def test_dry_run_topic_switch_waiting_user_stays_detached(self):
        case = live_replay_module.get_replay_case("topic_switch_waiting_user")

        report = live_replay_module.run_replay_case(case, dry_run=True)

        self.assertFalse(report["prompt"]["active_context_used"])
        self.assertFalse(report["prompt"]["resumed_task"])
        self.assertEqual(report["prompt"]["query_mode"], "")
        self.assertTrue(report["checks"]["pass"])

    def test_reply_content_score_matches_any_expected_marker(self):
        case = live_replay_module.ReplayCase(
            case_id="demo",
            description="demo",
            query="demo",
            seed_kind="open_plan",
            expected_reply_any=("login",),
        )

        checks = live_replay_module._score_reply_content(case, "Please finish login first, then I can continue.")

        self.assertTrue(checks["reply_anchor_ok"])
        self.assertIn("login", checks["matched_reply_markers"])

    def test_tool_name_score_matches_expected_tool(self):
        case = live_replay_module.ReplayCase(
            case_id="tool-demo",
            description="tool demo",
            query="demo",
            seed_kind="open_plan",
            expected_tool_any=("folder_explore",),
        )

        checks = live_replay_module._score_tool_names(case, ["folder_explore"])

        self.assertTrue(checks["tool_name_ok"])
        self.assertIn("folder_explore", checks["matched_tool_names"])

    def test_runtime_guardrails_preset_includes_resume_and_retry_cases(self):
        cases = live_replay_module.select_replay_cases(preset_ids=["runtime_guardrails"])
        case_ids = {item.case_id for item in cases}

        self.assertIn("resume_after_interrupt", case_ids)
        self.assertIn("retry_request_with_known_target", case_ids)


if __name__ == "__main__":
    unittest.main()
