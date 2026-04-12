import unittest
from pathlib import Path
from unittest.mock import patch

import core.skills.development_flow as development_flow_module

TEST_REPO_ROOT = Path(__file__).resolve().parents[1].as_posix()


def _fake_task(task_id: str, title: str, **extra):
    data = {"id": task_id, "title": title}
    data.update(extra)
    return data


class DevelopmentFlowDisambiguationTests(unittest.TestCase):
    def test_execute_reuses_matched_open_task_plan_instead_of_creating_new_task(self):
        latest_plan = {
            "task_id": "task_plan_1",
            "goal": "继续修 AaronCore 的连续性问题",
            "items": [{"id": "inspect", "title": "检查连续性链路", "status": "running"}],
        }
        working_state = {
            "goal": "继续修 AaronCore 的连续性问题",
            "current_step": "检查连续性链路",
        }

        with patch.object(
            development_flow_module,
            "get_active_task_plan_snapshot",
            side_effect=[latest_plan, latest_plan],
        ), patch.object(
            development_flow_module,
            "get_structured_fs_target_for_task_plan",
            return_value={"path": f"{TEST_REPO_ROOT}/app.py", "option": "inspect", "source": "task_plan"},
        ), patch.object(
            development_flow_module,
            "get_active_task_working_state",
            return_value=working_state,
        ), patch.object(
            development_flow_module,
            "get_latest_active_task_by_kind",
            return_value={},
        ), patch.object(
            development_flow_module,
            "resolve_task_for_goal",
            return_value={},
        ), patch.object(
            development_flow_module,
            "create_task",
            side_effect=AssertionError("matched open task should not create a new development task"),
        ):
            result = development_flow_module.execute("继续修 AaronCore 的连续性问题")

        self.assertTrue(result.get("verification", {}).get("verified"))
        self.assertEqual(result.get("verification", {}).get("observed_state"), "existing_task_selected")
        self.assertEqual((result.get("task_plan") or {}).get("goal"), "继续修 AaronCore 的连续性问题")

    def test_execute_asks_user_when_open_task_exists_but_new_request_is_ambiguous(self):
        latest_plan = {
            "task_id": "task_plan_1",
            "goal": "继续修 AaronCore 的连续性问题",
            "items": [{"id": "inspect", "title": "检查连续性链路", "status": "running"}],
        }
        working_state = {
            "goal": "继续修 AaronCore 的连续性问题",
            "current_step": "检查连续性链路",
        }

        with patch.object(
            development_flow_module,
            "get_active_task_plan_snapshot",
            side_effect=[latest_plan, {}],
        ), patch.object(
            development_flow_module,
            "get_structured_fs_target_for_task_plan",
            return_value={"path": f"{TEST_REPO_ROOT}/app.py", "option": "inspect", "source": "task_plan"},
        ), patch.object(
            development_flow_module,
            "get_active_task_working_state",
            return_value=working_state,
        ), patch.object(
            development_flow_module,
            "get_latest_active_task_by_kind",
            return_value={},
        ), patch.object(
            development_flow_module,
            "resolve_task_for_goal",
            return_value={},
        ), patch.object(
            development_flow_module,
            "execute_ask_user",
            return_value={"success": True, "response": "用户选择了：继续上一个开发任务"},
        ), patch.object(
            development_flow_module,
            "create_task",
            side_effect=AssertionError("continuing the open task should not create a new development task"),
        ):
            result = development_flow_module.execute("做个本地记事本")

        self.assertTrue(result.get("verification", {}).get("verified"))
        self.assertEqual(result.get("verification", {}).get("observed_state"), "existing_task_selected")
        self.assertIn("继续上一个开发任务", result.get("action", {}).get("display_hint", ""))

    def test_execute_can_start_new_task_after_user_chooses_new_task(self):
        latest_plan = {
            "task_id": "task_plan_1",
            "goal": "继续修 AaronCore 的连续性问题",
            "items": [{"id": "inspect", "title": "检查连续性链路", "status": "running"}],
        }
        working_state = {
            "goal": "继续修 AaronCore 的连续性问题",
            "current_step": "检查连续性链路",
        }
        created_tasks = []

        def fake_create_task(kind, title, **extra):
            task = _fake_task(f"task_{len(created_tasks) + 1}", title, kind=kind, **extra)
            created_tasks.append(task)
            return task

        with patch.object(
            development_flow_module,
            "get_active_task_plan_snapshot",
            side_effect=[latest_plan, {}],
        ), patch.object(
            development_flow_module,
            "get_structured_fs_target_for_task_plan",
            return_value={"path": f"{TEST_REPO_ROOT}/app.py", "option": "inspect", "source": "task_plan"},
        ), patch.object(
            development_flow_module,
            "get_active_task_working_state",
            return_value=working_state,
        ), patch.object(
            development_flow_module,
            "get_latest_active_task_by_kind",
            return_value={},
        ), patch.object(
            development_flow_module,
            "resolve_task_for_goal",
            return_value={},
        ), patch.object(
            development_flow_module,
            "execute_ask_user",
            return_value={"success": True, "response": "用户选择了：按新开发任务处理"},
        ), patch.object(
            development_flow_module,
            "_get_or_create_project",
            return_value={"id": "proj_1"},
        ), patch.object(
            development_flow_module,
            "_llm_plan",
            return_value={"understanding": "这是一个新开发任务。", "next_steps": ["定位相关文件", "开始实现"]},
        ), patch.object(
            development_flow_module,
            "create_task",
            side_effect=fake_create_task,
        ), patch.object(
            development_flow_module,
            "create_relation",
            return_value={},
        ), patch.object(
            development_flow_module,
            "append_task_event",
            return_value={},
        ), patch.object(
            development_flow_module,
            "update_project",
            return_value={},
        ), patch.object(
            development_flow_module,
            "update_task",
            return_value={},
        ):
            result = development_flow_module.execute("做个本地记事本")

        self.assertIsInstance(result, str)
        self.assertIn("这个开发任务我先接住了", result)
        self.assertGreaterEqual(len(created_tasks), 3)
        self.assertEqual(created_tasks[0].get("kind"), "development")


if __name__ == "__main__":
    unittest.main()
