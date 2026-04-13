import copy
import unittest
from unittest.mock import patch

import core.reply_formatter as reply_formatter_module
import core.session_context as session_context_module
import core.task_store as task_store_module
from routes.chat_run_helpers import apply_runtime_state_to_task_plan


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


class TaskReplayEvalTests(unittest.TestCase):
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

    def _save_open_plan(self, *, goal="继续整理桌面文件", fs_target="C:/Users/36459/Desktop"):
        _task, snapshot = task_store_module.save_task_plan_snapshot(
            goal,
            {
                "goal": goal,
                "summary": "正在整理桌面文件",
                "items": [
                    {"id": "inspect", "title": "检查桌面文件", "status": "done"},
                    {"id": "sort", "title": "整理分类结构", "status": "running"},
                ],
                "current_item_id": "sort",
                "phase": "sort",
            },
        )
        if fs_target:
            task_store_module.remember_fs_target_for_task_plan(
                snapshot,
                {"path": fs_target, "option": "inspect", "source": "tool_runtime"},
            )
        return snapshot

    def _save_waiting_user_plan(self):
        snapshot = self._save_open_plan(goal="继续处理抖音登录后的采集")
        updated = apply_runtime_state_to_task_plan(
            snapshot,
            meta={
                "runtime_state": {
                    "status": "waiting_user",
                    "next_action": "wait_for_user",
                    "blocker": "需要你先完成抖音登录",
                    "fs_target": {"path": "https://www.douyin.com", "kind": "url"},
                },
                "verification": {
                    "verified": False,
                    "detail": "需要你先完成抖音登录",
                },
            },
            tool_used="open_target",
            tool_response="Login required",
        )
        return updated

    def _save_verify_failed_plan(self):
        _task, snapshot = task_store_module.save_task_plan_snapshot(
            "继续修 AaronCore 连续性",
            {
                "goal": "继续修 AaronCore 连续性",
                "summary": "验证还没通过",
                "items": [
                    {"id": "inspect", "title": "检查连续性链路", "status": "done"},
                    {"id": "verify", "title": "验证修复结果", "status": "running"},
                ],
                "current_item_id": "verify",
                "phase": "verify",
                "runtime_status": "verify_failed",
                "next_action": "retry_or_close",
                "verification": {
                    "verified": False,
                    "detail": "continuity 还会被一句闲聊误续接",
                },
            },
        )
        return snapshot

    def _save_interrupted_plan(self):
        snapshot = self._save_open_plan(goal="Inspect desktop folders", fs_target="C:/Users/36459/Desktop")
        updated = apply_runtime_state_to_task_plan(
            snapshot,
            meta={
                "runtime_state": {
                    "status": "interrupted",
                    "next_action": "resume_or_close",
                    "blocker": "sense_environment interrupted before the folder check completed",
                    "fs_target": {"path": "C:/Users/36459/Desktop", "kind": "directory"},
                },
            },
            tool_used="sense_environment",
            tool_response="sense_environment interrupted",
        )
        return updated

    def _context(self, query: str) -> str:
        return reply_formatter_module._build_active_task_context({"user_input": query, "l5_success_paths": []})

    def test_replay_eval_unrelated_small_talk_does_not_resume_active_task(self):
        self._save_open_plan()
        query = "明天要不要打伞啊"

        resumed = task_store_module.get_active_task_plan_snapshot(query)
        working_state = task_store_module.get_active_task_working_state(query)
        session_context = session_context_module.extract_session_context([], query)
        context = self._context(query)

        self.assertIsNone(resumed)
        self.assertFalse(bool(working_state))
        self.assertFalse(bool(session_context.get("working_state")))
        self.assertEqual(context, "")

    def test_replay_eval_bare_continue_does_not_resume_waiting_user_task(self):
        self._save_waiting_user_plan()
        query = "继续"

        resumed = task_store_module.get_active_task_plan_snapshot(query)
        working_state = task_store_module.get_active_task_working_state(query)
        session_context = session_context_module.extract_session_context([], query)
        context = self._context(query)

        self.assertIsNone(resumed)
        self.assertFalse(bool(working_state))
        self.assertFalse(bool(session_context.get("working_state")))
        self.assertEqual(context, "")

    def test_replay_eval_topic_switch_does_not_resume_waiting_user_task(self):
        self._save_waiting_user_plan()
        query = "哈哈 这首歌还挺好听"

        resumed = task_store_module.get_active_task_plan_snapshot(query)
        working_state = task_store_module.get_active_task_working_state(query)
        session_context = session_context_module.extract_session_context([], query)
        context = self._context(query)

        self.assertIsNone(resumed)
        self.assertFalse(bool(working_state))
        self.assertFalse(bool(session_context.get("working_state")))
        self.assertEqual(context, "")

    def test_replay_eval_blocker_question_answers_waiting_user_state_first(self):
        self._save_waiting_user_plan()
        query = "需要我做什么"

        snapshot = task_store_module.get_active_task_plan_snapshot(query)
        working_state = task_store_module.get_active_task_working_state(query)
        session_context = session_context_module.extract_session_context([], query)
        context = self._context(query)

        self.assertIsInstance(snapshot, dict)
        self.assertEqual(working_state.get("query_mode"), "blocker")
        self.assertEqual(working_state.get("runtime_status"), "waiting_user")
        self.assertEqual(working_state.get("blocker"), "需要你先完成抖音登录")
        self.assertIn("explain the blocker or the missing user action first", session_context.get("user_state") or "")
        self.assertIn("Current user request: explain the blocker or missing user action first.", context)
        self.assertIn("This request is already answerable from the current task runtime state.", context)
        self.assertIn("Current blocker: 需要你先完成抖音登录", context)

    def test_replay_eval_verify_question_answers_verification_first(self):
        self._save_verify_failed_plan()
        query = "验证了吗"

        snapshot = task_store_module.get_active_task_plan_snapshot(query)
        working_state = task_store_module.get_active_task_working_state(query)
        session_context = session_context_module.extract_session_context([], query)
        context = self._context(query)

        self.assertIsInstance(snapshot, dict)
        self.assertEqual(working_state.get("query_mode"), "verify")
        self.assertEqual(working_state.get("verification_status"), "failed")
        self.assertEqual(working_state.get("verification_detail"), "continuity 还会被一句闲聊误续接")
        self.assertIn("answer the current task verification state first", session_context.get("user_state") or "")
        self.assertIn("Current user request: answer whether the latest task result is verified first.", context)
        self.assertIn("This request is already answerable from the current task runtime state.", context)
        self.assertIn("Latest verification status: failed", context)

    def test_replay_eval_interrupt_question_answers_interruption_first(self):
        self._save_interrupted_plan()
        query = "what interrupted it just now"

        snapshot = task_store_module.get_active_task_plan_snapshot(query)
        working_state = task_store_module.get_active_task_working_state(query)
        session_context = session_context_module.extract_session_context([], query)
        context = self._context(query)

        self.assertIsInstance(snapshot, dict)
        self.assertEqual(working_state.get("query_mode"), "interrupt")
        self.assertEqual(working_state.get("runtime_status"), "interrupted")
        self.assertEqual(working_state.get("next_action"), "resume_or_close")
        self.assertIn("explain the interruption state first", session_context.get("user_state") or "")
        self.assertIn("Current user request: explain why the last attempt was interrupted first.", context)
        self.assertIn("This request is already answerable from the current task runtime state.", context)
        self.assertIn("Latest runtime status: interrupted", context)

    def test_replay_eval_status_question_answers_progress_first(self):
        self._save_open_plan(goal="继续整理 AaronCore 项目")
        query = "现在到哪了"

        snapshot = task_store_module.get_active_task_plan_snapshot(query)
        working_state = task_store_module.get_active_task_working_state(query)
        session_context = session_context_module.extract_session_context([], query)
        context = self._context(query)

        self.assertIsInstance(snapshot, dict)
        self.assertEqual(working_state.get("query_mode"), "status")
        self.assertEqual(working_state.get("current_step"), "整理分类结构")
        self.assertIn("answer the current task status first", session_context.get("user_state") or "")
        self.assertIn("Current user request: answer with the current task status or progress first.", context)
        self.assertIn("This request is already answerable from the current task runtime state.", context)

    def test_replay_eval_locate_question_answers_target_first(self):
        self._save_open_plan(goal="继续完善 NovaNotes", fs_target="C:/Users/36459/NovaNotes/templates/index.html")
        query = "那个项目在哪"

        snapshot = task_store_module.get_active_task_plan_snapshot(query)
        working_state = task_store_module.get_active_task_working_state(query)
        session_context = session_context_module.extract_session_context([], query)
        context = self._context(query)

        self.assertIsInstance(snapshot, dict)
        self.assertEqual(working_state.get("query_mode"), "locate")
        self.assertEqual(
            str(working_state.get("fs_target") or "").replace("\\", "/"),
            "C:/Users/36459/NovaNotes/templates/index.html",
        )
        self.assertIn("answer the current task location first", session_context.get("user_state") or "")
        self.assertIn("Current user request: answer with the current task target or location first.", context)
        self.assertIn("This request is already answerable from the current task runtime state.", context)
        self.assertIn("Current task directory/file target: C:/Users/36459/NovaNotes/templates/index.html", context)

    def test_replay_eval_retry_request_with_known_target_keeps_execution_bias(self):
        self._save_open_plan(goal="看下桌面的文件夹有哪些", fs_target="C:/Users/36459/Desktop")
        query = "再试试看 能看到桌面的文件夹吗"

        snapshot = task_store_module.get_active_task_plan_snapshot(query)
        working_state = task_store_module.get_active_task_working_state(query)
        session_context = session_context_module.extract_session_context([], query)
        context = self._context(query)

        self.assertIsInstance(snapshot, dict)
        self.assertEqual(working_state.get("query_mode"), "")
        self.assertTrue(bool(working_state.get("fs_target")))
        self.assertIn("continue only if the current user input clearly refers to this task", session_context.get("user_state") or "")
        self.assertNotIn("Current user request:", context)

    def test_replay_eval_explicit_path_action_does_not_collapse_into_locate_mode(self):
        self._save_open_plan(goal="看下桌面的文件夹有哪些", fs_target="C:/Users/36459/Desktop")
        query = r"C:/Users/36459/Desktop/切格瓦拉 这个文件 你去看下"

        snapshot = task_store_module.get_active_task_plan_snapshot(query)
        working_state = task_store_module.get_active_task_working_state(query)
        session_context = session_context_module.extract_session_context([], query)
        context = self._context(query)

        self.assertIsInstance(snapshot, dict)
        self.assertEqual(working_state.get("query_mode"), "")
        self.assertIn("continue only if the current user input clearly refers to this task", session_context.get("user_state") or "")
        self.assertNotIn("Current user request: answer with the current task target or location first.", context)


class TaskReplayResumeAfterInterruptTests(unittest.TestCase):
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

    def _save_interrupted_plan(self):
        _task, snapshot = task_store_module.save_task_plan_snapshot(
            "Inspect desktop folders",
            {
                "goal": "Inspect desktop folders",
                "summary": "working",
                "items": [
                    {"id": "inspect", "title": "Inspect current target", "status": "done"},
                    {"id": "work", "title": "Continue current step", "status": "running"},
                ],
                "current_item_id": "work",
                "phase": "work",
            },
        )
        task_store_module.remember_fs_target_for_task_plan(
            snapshot,
            {"path": "C:/Users/36459/Desktop", "option": "inspect", "source": "tool_runtime"},
        )
        return apply_runtime_state_to_task_plan(
            snapshot,
            meta={
                "runtime_state": {
                    "status": "interrupted",
                    "next_action": "resume_or_close",
                    "blocker": "sense_environment interrupted before the folder check completed",
                    "fs_target": {"path": "C:/Users/36459/Desktop", "kind": "directory"},
                }
            },
            tool_used="sense_environment",
            tool_response="sense_environment interrupted",
        )

    def _context(self, query: str) -> str:
        return reply_formatter_module._build_active_task_context({"user_input": query, "l5_success_paths": []})

    def test_replay_eval_resume_after_interrupt_keeps_execution_bias(self):
        self._save_interrupted_plan()
        query = "continue the interrupted task"

        snapshot = task_store_module.get_active_task_plan_snapshot(query)
        working_state = task_store_module.get_active_task_working_state(query)
        session_context = session_context_module.extract_session_context([], query)
        context = self._context(query)

        self.assertIsInstance(snapshot, dict)
        self.assertEqual(working_state.get("query_mode"), "continue")
        self.assertEqual(working_state.get("runtime_status"), "interrupted")
        self.assertEqual(
            str(working_state.get("fs_target") or "").replace("\\", "/"),
            "C:/Users/36459/Desktop",
        )
        self.assertIn("resume the interrupted task", session_context.get("user_state") or "")
        self.assertIn("Latest runtime status: interrupted", context)
        self.assertNotIn("Current user request:", context)


class TaskReplayStateDrivenRecoveryTests(unittest.TestCase):
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

    def _save_waiting_user_plan(self):
        _task, snapshot = task_store_module.save_task_plan_snapshot(
            "继续处理抖音登录后的采集",
            {
                "goal": "继续处理抖音登录后的采集",
                "summary": "正在等待登录完成",
                "items": [
                    {"id": "inspect", "title": "检查登录状态", "status": "done"},
                    {"id": "login", "title": "等待用户登录", "status": "running"},
                ],
                "current_item_id": "login",
                "phase": "blocked",
            },
        )
        return apply_runtime_state_to_task_plan(
            snapshot,
            meta={
                "runtime_state": {
                    "status": "waiting_user",
                    "next_action": "wait_for_user",
                    "blocker": "需要你先完成抖音登录",
                    "fs_target": {"path": "https://www.douyin.com", "kind": "url"},
                },
                "verification": {
                    "verified": False,
                    "detail": "需要你先完成抖音登录",
                },
            },
            tool_used="open_target",
            tool_response="Login required",
        )

    def _save_verify_failed_plan(self):
        _task, snapshot = task_store_module.save_task_plan_snapshot(
            "继续修 AaronCore continuity",
            {
                "goal": "继续修 AaronCore continuity",
                "summary": "验证还没通过",
                "items": [
                    {"id": "inspect", "title": "检查 continuity 链路", "status": "done"},
                    {"id": "verify", "title": "验证修复结果", "status": "running"},
                ],
                "current_item_id": "verify",
                "phase": "verify",
                "runtime_status": "verify_failed",
                "next_action": "retry_or_close",
                "verification": {
                    "verified": False,
                    "detail": "continuity 还会被一句闲聊误续接",
                },
            },
        )
        return snapshot

    def _context(self, query: str) -> str:
        return reply_formatter_module._build_active_task_context({"user_input": query, "l5_success_paths": []})

    def test_waiting_user_completion_update_restores_continue_policy(self):
        self._save_waiting_user_plan()
        query = "我登录好了"

        snapshot = task_store_module.get_active_task_plan_snapshot(query)
        working_state = task_store_module.get_active_task_working_state(query)
        session_context = session_context_module.extract_session_context([], query)
        context = self._context(query)

        self.assertIsInstance(snapshot, dict)
        self.assertEqual(working_state.get("query_mode"), "continue")
        self.assertEqual(working_state.get("runtime_status"), "waiting_user")
        self.assertIn("user says the blocker step is complete", session_context.get("user_state") or "")
        self.assertIn("Turn execution policy: continue_execution_allowed", context)
        self.assertNotIn("Current user request: answer about the active task first.", context)

    def test_verify_failed_retry_request_restores_continue_policy(self):
        self._save_verify_failed_plan()
        query = "再试一下修这个"

        snapshot = task_store_module.get_active_task_plan_snapshot(query)
        working_state = task_store_module.get_active_task_working_state(query)
        session_context = session_context_module.extract_session_context([], query)
        context = self._context(query)

        self.assertIsInstance(snapshot, dict)
        self.assertEqual(working_state.get("query_mode"), "continue")
        self.assertEqual(working_state.get("runtime_status"), "verify_failed")
        self.assertIn("retry the latest failed step", session_context.get("user_state") or "")
        self.assertIn("Turn execution policy: continue_execution_allowed", context)
        self.assertNotIn("Current user request: answer about the active task first.", context)


if __name__ == "__main__":
    unittest.main()
