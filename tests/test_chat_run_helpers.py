import sys
import types
import unittest

from routes.chat_run_helpers import (
    block_task_plan_after_failure,
    build_run_event,
    extract_task_plan_from_meta,
    is_task_plan_terminal,
    summarize_execution_text,
)


class ChatRunHelpersTests(unittest.TestCase):
    def test_summarize_execution_text_joins_first_two_lines(self):
        summary = summarize_execution_text(" - first line\nsecond line\nthird line")
        self.assertEqual(summary, "first line / second line")

    def test_build_run_event_prefers_action_display_hint(self):
        event = build_run_event(
            success=True,
            meta={
                "action": {
                    "display_hint": "Open target tab",
                    "action_kind": "open",
                },
                "verification": {"verified": True},
            },
            fallback_text="unused",
        )
        self.assertEqual(event["summary"], "Open target tab")
        self.assertTrue(event["verified"])
        self.assertEqual(event["action_kind"], "open")

    def test_extract_task_plan_from_meta_requires_items(self):
        self.assertIsNone(extract_task_plan_from_meta({"task_plan": {"goal": "x"}}))
        plan = {"goal": "x", "items": [{"id": "1", "status": "pending"}]}
        self.assertIs(extract_task_plan_from_meta({"task_plan": plan}), plan)

    def test_is_task_plan_terminal_tracks_pending_and_running(self):
        self.assertTrue(is_task_plan_terminal({"phase": "done", "items": [{"status": "pending"}]}))
        self.assertFalse(is_task_plan_terminal({"items": [{"status": "running"}]}))
        self.assertTrue(is_task_plan_terminal({"items": [{"status": "done"}]}))

    def test_block_task_plan_after_failure_marks_current_item_blocked(self):
        fake_task_store = types.ModuleType("core.task_store")

        def _normalize(plan, goal=""):
            out = dict(plan)
            if goal:
                out["goal"] = goal
            return out

        def _save(goal, plan, source=""):
            saved = dict(plan)
            saved["saved_goal"] = goal
            saved["saved_source"] = source
            return "task-plan-id", saved

        fake_task_store.normalize_task_plan_snapshot = _normalize
        fake_task_store.save_task_plan_snapshot = _save
        original = sys.modules.get("core.task_store")
        sys.modules["core.task_store"] = fake_task_store

        try:
            result = block_task_plan_after_failure(
                {
                    "goal": "Find target window",
                    "phase": "running",
                    "current_item_id": "step-2",
                    "items": [
                        {"id": "step-1", "status": "done"},
                        {"id": "step-2", "status": "running"},
                    ],
                },
                tool_used="sense_environment",
                tool_response="window not found",
            )
        finally:
            if original is None:
                sys.modules.pop("core.task_store", None)
            else:
                sys.modules["core.task_store"] = original

        self.assertIsInstance(result, dict)
        self.assertEqual(result["phase"], "blocked")
        self.assertEqual(result["current_item_id"], "step-2")
        self.assertEqual(result["items"][1]["status"], "blocked")
        self.assertIn("sense_environment 未完成", result["items"][1]["detail"])
        self.assertEqual(result["saved_source"], "task_plan_runtime")


if __name__ == "__main__":
    unittest.main()
