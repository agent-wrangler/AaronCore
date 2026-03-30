import copy
import unittest
from unittest.mock import patch

import core.executor as executor_module
import core.reply_formatter as reply_formatter_module
import core.task_store as task_store_module
import core.skills.task_plan as task_plan_module


class _InMemoryTaskData:
    def __init__(self):
        self.projects = []
        self.tasks = []
        self.relations = []

    def load_task_projects(self):
        return copy.deepcopy(self.projects)

    def save_task_projects(self, data):
        self.projects = copy.deepcopy(data)

    def load_tasks(self):
        return copy.deepcopy(self.tasks)

    def save_tasks(self, data):
        self.tasks = copy.deepcopy(data)

    def load_task_relations(self):
        return copy.deepcopy(self.relations)

    def save_task_relations(self, data):
        self.relations = copy.deepcopy(data)

    def load_content_projects(self):
        return []


class TaskPlanSkillTests(unittest.TestCase):
    def setUp(self):
        self.data = _InMemoryTaskData()
        self.patches = [
            patch.object(task_store_module, "load_task_projects", side_effect=self.data.load_task_projects),
            patch.object(task_store_module, "save_task_projects", side_effect=self.data.save_task_projects),
            patch.object(task_store_module, "load_tasks", side_effect=self.data.load_tasks),
            patch.object(task_store_module, "save_tasks", side_effect=self.data.save_tasks),
            patch.object(task_store_module, "load_task_relations", side_effect=self.data.load_task_relations),
            patch.object(task_store_module, "save_task_relations", side_effect=self.data.save_task_relations),
            patch.object(task_store_module, "load_content_projects", side_effect=self.data.load_content_projects),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()

    def test_create_or_update_plan_persists_snapshot_and_children(self):
        result = task_plan_module.execute(
            "",
            {
                "action": "create_or_update",
                "goal": "Implement planning layer without touching route order",
                "items": [
                    {"id": "inspect_flow", "title": "Inspect the current chain", "status": "running"},
                    {"id": "build_tool", "title": "Build the planner tool", "status": "pending"},
                    {"id": "wire_ui", "title": "Wire the plan into UI", "status": "pending"},
                ],
            },
        )

        self.assertTrue(result.get("verification", {}).get("verified"))
        plan = result.get("task_plan") or {}
        self.assertEqual(plan.get("current_item_id"), "inspect_flow")
        self.assertEqual(plan.get("items", [])[0].get("status"), "running")

        snapshot = task_store_module.get_active_task_plan_snapshot("continue this task")
        self.assertEqual(snapshot.get("goal"), "Implement planning layer without touching route order")
        self.assertEqual(len(snapshot.get("items") or []), 3)

        plan_step_titles = [task.get("title") for task in self.data.tasks if task.get("kind") == "plan_step"]
        self.assertIn("Inspect the current chain", plan_step_titles)
        self.assertIn("Build the planner tool", plan_step_titles)

    def test_advance_marks_current_item_done_and_next_item_running(self):
        task_plan_module.execute(
            "",
            {
                "action": "create_or_update",
                "goal": "Add a resilient planning layer",
                "items": [
                    {"id": "inspect", "title": "Inspect the current chain", "status": "running"},
                    {"id": "implement", "title": "Implement the planner", "status": "pending"},
                ],
            },
        )

        result = task_plan_module.execute(
            "",
            {
                "action": "advance",
                "goal": "Add a resilient planning layer",
                "completed_item_id": "inspect",
            },
        )

        plan = result.get("task_plan") or {}
        statuses = {item.get("id"): item.get("status") for item in plan.get("items") or []}
        self.assertEqual(statuses.get("inspect"), "done")
        self.assertEqual(statuses.get("implement"), "running")
        self.assertEqual(plan.get("current_item_id"), "implement")

    def test_build_active_task_context_uses_stored_plan_when_bundle_has_none(self):
        task_plan_module.execute(
            "",
            {
                "action": "create_or_update",
                "goal": "Plan a complex refactor",
                "items": [
                    {"id": "map_flow", "title": "Map the current flow", "status": "running"},
                    {"id": "patch_lower_layers", "title": "Patch lower layers", "status": "pending"},
                ],
            },
        )

        context = reply_formatter_module._build_active_task_context(
            {
                "user_input": "continue this refactor",
                "l5_success_paths": [],
            }
        )

        self.assertIn("Current task goal in this turn: Plan a complex refactor", context)
        self.assertIn("Current plan checklist:", context)
        self.assertIn("[running] Map the current flow", context)


class TaskPlanMetaTests(unittest.TestCase):
    def test_executor_preserves_task_plan_meta(self):
        fake_result = {
            "reply": "ok",
            "state": {"expected_state": "task_plan_saved", "observed_state": "task_plan_saved"},
            "drift": {"reason": "", "repair_hint": ""},
            "action": {"action_kind": "task_plan", "target_kind": "task", "target": "plan", "outcome": "saved"},
            "verification": {"verified": True, "detail": "phase=inspect"},
            "task_plan": {
                "goal": "Track a complex task",
                "phase": "inspect",
                "summary": "Working on inspect",
                "current_item_id": "inspect",
                "items": [{"id": "inspect", "title": "Inspect", "status": "running"}],
            },
        }

        with patch("core.executor.get_skill", return_value={"execute": lambda _user, _ctx: fake_result}):
            result = executor_module.execute({"skill": "fake_skill"}, "track task", {})

        self.assertEqual(result.get("meta", {}).get("task_plan", {}).get("goal"), "Track a complex task")

    def test_tool_call_prompt_mentions_task_plan_guidance(self):
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

        self.assertIn("task_plan", prompt)
        self.assertIn("3-6 item plan", prompt)


if __name__ == "__main__":
    unittest.main()
