import sys
import types
import unittest

from routes.chat_run_helpers import (
    apply_runtime_state_to_task_plan,
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
        self.assertIn("sense_environment", result["items"][1]["detail"])
        self.assertEqual(result["saved_source"], "task_plan_runtime")

    def test_apply_runtime_state_marks_waiting_user_and_remembers_target(self):
        fake_task_store = types.ModuleType("core.task_store")
        remembered = {}

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

        def _remember(plan, fs_target):
            remembered["plan"] = dict(plan)
            remembered["fs_target"] = dict(fs_target)
            return dict(fs_target)

        fake_task_store.normalize_task_plan_snapshot = _normalize
        fake_task_store.save_task_plan_snapshot = _save
        fake_task_store.remember_fs_target_for_task_plan = _remember
        original = sys.modules.get("core.task_store")
        sys.modules["core.task_store"] = fake_task_store

        try:
            result = apply_runtime_state_to_task_plan(
                {
                    "goal": "Open the target site",
                    "phase": "open",
                    "summary": "Opening the target site",
                    "current_item_id": "step-1",
                    "items": [
                        {"id": "step-1", "title": "Open target", "status": "running"},
                        {"id": "step-2", "title": "Verify page", "status": "pending"},
                    ],
                },
                meta={
                    "runtime_state": {
                        "status": "waiting_user",
                        "next_action": "wait_for_user",
                        "blocker": "Please finish login first",
                        "fs_target": {"path": "C:/repo", "kind": "directory"},
                    },
                    "verification": {
                        "verified": False,
                        "detail": "Please finish login first",
                    },
                    "process_meta": {
                        "attempt_kind": "retry",
                        "execution_lane": "verify",
                        "previous_tool": "sense_environment",
                        "parallel_tools": ["open_target", "read_file"],
                        "parallel_size": 2,
                    },
                },
                tool_used="open_target",
                tool_response="Login required",
            )
        finally:
            if original is None:
                sys.modules.pop("core.task_store", None)
            else:
                sys.modules["core.task_store"] = original

        self.assertEqual(result["phase"], "blocked")
        self.assertEqual(result["runtime_status"], "waiting_user")
        self.assertEqual(result["next_action"], "wait_for_user")
        self.assertEqual(result["blocker"], "Please finish login first")
        self.assertEqual(result["last_tool"], "open_target")
        self.assertEqual(result["last_result_summary"], "Login required")
        self.assertEqual(result["attempt_kind"], "retry")
        self.assertEqual(result["execution_lane"], "verify")
        self.assertEqual(result["previous_tool"], "sense_environment")
        self.assertEqual(result["parallel_tools"], ["open_target", "read_file"])
        self.assertEqual(result["parallel_size"], 2)
        self.assertEqual(result["items"][0]["status"], "waiting_user")
        self.assertEqual(result["items"][0]["detail"], "Please finish login first")
        self.assertEqual(result["verification"]["status"], "failed")
        self.assertEqual(result["saved_source"], "task_plan_runtime")
        self.assertEqual(remembered["fs_target"]["path"], "C:/repo")

    def test_apply_runtime_state_preserves_running_step_for_verified_result(self):
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
        fake_task_store.remember_fs_target_for_task_plan = lambda *_args, **_kwargs: None
        original = sys.modules.get("core.task_store")
        sys.modules["core.task_store"] = fake_task_store

        try:
            result = apply_runtime_state_to_task_plan(
                {
                    "goal": "Patch the target module",
                    "phase": "patch",
                    "summary": "Patching lower layers",
                    "current_item_id": "step-2",
                    "items": [
                        {"id": "step-1", "title": "Inspect flow", "status": "done"},
                        {"id": "step-2", "title": "Patch lower layers", "status": "running"},
                    ],
                },
                meta={
                    "runtime_state": {
                        "status": "verified",
                        "next_action": "continue",
                    },
                    "verification": {
                        "verified": True,
                        "detail": "Target module updated",
                    },
                },
                tool_used="write_file",
                tool_response="Updated target module",
            )
        finally:
            if original is None:
                sys.modules.pop("core.task_store", None)
            else:
                sys.modules["core.task_store"] = original

        self.assertEqual(result["phase"], "patch")
        self.assertEqual(result["runtime_status"], "verified")
        self.assertEqual(result["next_action"], "continue")
        self.assertEqual(result["last_tool"], "write_file")
        self.assertEqual(result["last_result_summary"], "Updated target module")
        self.assertEqual(result["items"][1]["status"], "running")
        self.assertEqual(result["verification"]["status"], "verified")


if __name__ == "__main__":
    unittest.main()
