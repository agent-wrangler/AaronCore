import copy
import unittest
from unittest.mock import patch

import tools.agent.delivery_protocol as delivery_protocol_module


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


class DeliveryProtocolTests(unittest.TestCase):
    def setUp(self):
        self.data = _InMemoryTaskData()
        task_store = delivery_protocol_module._task_store
        self.patches = [
            patch.object(task_store, "load_task_projects", side_effect=self.data.load_task_projects),
            patch.object(task_store, "save_task_projects", side_effect=self.data.save_task_projects),
            patch.object(task_store, "load_tasks", side_effect=self.data.load_tasks),
            patch.object(task_store, "save_tasks", side_effect=self.data.save_tasks),
            patch.object(task_store, "load_task_relations", side_effect=self.data.load_task_relations),
            patch.object(task_store, "save_task_relations", side_effect=self.data.save_task_relations),
            patch.object(task_store, "load_content_projects", side_effect=self.data.load_content_projects),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()

    def test_build_delivery_plan_tracks_waiting_choice_step(self):
        plan = delivery_protocol_module.build_delivery_task_plan(
            "做个赛博风小游戏",
            completed_steps=["clarify_spec"],
            waiting_step="choose_approach",
            summary="等待选择模板",
        )

        statuses = {item.get("id"): item.get("status") for item in plan.get("items") or []}
        self.assertEqual(plan.get("current_item_id"), "choose_approach")
        self.assertEqual(statuses.get("clarify_spec"), "done")
        self.assertEqual(statuses.get("choose_approach"), "running")
        self.assertEqual(statuses.get("build_artifact"), "pending")

    def test_save_delivery_plan_persists_task_plan_snapshot(self):
        _task, saved_plan = delivery_protocol_module.save_delivery_task_plan(
            "继续做 AaronCore 开发交付协议",
            completed_steps=["clarify_spec", "choose_approach"],
            current_step="build_artifact",
            summary="正在把协议抽成通用 helper",
            source="delivery_protocol_test",
        )

        self.assertEqual(saved_plan.get("current_item_id"), "build_artifact")
        snapshot = delivery_protocol_module._task_store.get_active_task_plan_snapshot("继续做 AaronCore 开发交付协议")
        self.assertEqual(snapshot.get("goal"), "继续做 AaronCore 开发交付协议")
        statuses = {item.get("id"): item.get("status") for item in snapshot.get("items") or []}
        self.assertEqual(statuses.get("clarify_spec"), "done")
        self.assertEqual(statuses.get("choose_approach"), "done")
        self.assertEqual(statuses.get("build_artifact"), "running")


if __name__ == "__main__":
    unittest.main()
