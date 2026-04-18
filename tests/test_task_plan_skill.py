import copy
import unittest
from unittest.mock import patch

import core.executor as executor_module
import core.reply_formatter as reply_formatter_module
import core.session_context as session_context_module
import core.skills.task_plan as task_plan_module
import core.task_store as task_store_module


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

    def test_current_plan_step_child_carries_runtime_execution_metadata(self):
        task_store_module.save_task_plan_snapshot(
            "continue AaronCore coding lane",
            {
                "goal": "continue AaronCore coding lane",
                "summary": "Verification failed after a parallel inspection batch",
                "items": [
                    {"id": "inspect", "title": "Inspect the current chain", "status": "done"},
                    {"id": "verify", "title": "Verify the patch", "status": "running", "detail": "Tests are still failing"},
                ],
                "current_item_id": "verify",
                "phase": "verify",
                "runtime_status": "verify_failed",
                "next_action": "retry_or_close",
                "last_tool": "run_command",
                "last_action_summary": "Ran pytest for the modified module",
                "last_result_summary": "pytest still reports the output file missing",
                "attempt_kind": "retry",
                "execution_lane": "verify",
                "previous_tool": "write_file",
                "parallel_tools": ["read_file", "list_files"],
                "parallel_size": 2,
                "verification": {
                    "verified": False,
                    "detail": "Output file is still missing",
                },
            },
        )

        verify_step = next(
            task for task in self.data.tasks
            if task.get("kind") == "plan_step" and task.get("title") == "Verify the patch"
        )
        inspect_step = next(
            task for task in self.data.tasks
            if task.get("kind") == "plan_step" and task.get("title") == "Inspect the current chain"
        )

        self.assertEqual((verify_step.get("context") or {}).get("runtime_status"), "verify_failed")
        self.assertEqual((verify_step.get("context") or {}).get("blocker"), "Output file is still missing")
        self.assertEqual((verify_step.get("context") or {}).get("verification_status"), "failed")
        self.assertEqual((verify_step.get("context") or {}).get("verification_detail"), "Output file is still missing")
        self.assertEqual((verify_step.get("memory") or {}).get("last_tool"), "run_command")
        self.assertEqual((verify_step.get("memory") or {}).get("attempt_kind"), "retry")
        self.assertEqual((verify_step.get("memory") or {}).get("execution_lane"), "verify")
        self.assertEqual((verify_step.get("memory") or {}).get("previous_tool"), "write_file")
        self.assertEqual((verify_step.get("memory") or {}).get("parallel_tools"), ["read_file", "list_files"])
        self.assertEqual((verify_step.get("memory") or {}).get("parallel_size"), 2)
        self.assertTrue(bool((verify_step.get("domain") or {}).get("task_plan_item", {}).get("is_current")))
        self.assertFalse(bool((inspect_step.get("memory") or {}).get("last_tool")))
        self.assertFalse(bool((inspect_step.get("domain") or {}).get("task_plan_item", {}).get("is_current")))

        working_state = task_store_module.get_active_task_working_state("continue AaronCore coding lane")
        current_step_task = (working_state or {}).get("current_step_task") or {}
        self.assertEqual(current_step_task.get("task_id"), verify_step.get("id"))
        self.assertEqual(current_step_task.get("status"), "active")
        self.assertEqual(current_step_task.get("runtime_status"), "verify_failed")
        self.assertEqual(current_step_task.get("blocker"), "Output file is still missing")
        self.assertEqual(current_step_task.get("attempt_kind"), "retry")
        self.assertEqual(current_step_task.get("execution_lane"), "verify")
        self.assertEqual(current_step_task.get("parallel_tools"), ["read_file", "list_files"])

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

    def test_advance_prefers_explicit_transition_over_stale_items_payload(self):
        task_plan_module.execute(
            "",
            {
                "action": "create_or_update",
                "goal": "Diagnose execution stalls",
                "items": [
                    {"id": "1", "title": "Inspect config", "status": "running"},
                    {"id": "2", "title": "Analyze root cause", "status": "pending"},
                    {"id": "3", "title": "Propose fixes", "status": "pending"},
                ],
            },
        )

        result = task_plan_module.execute(
            "",
            {
                "action": "advance",
                "goal": "Diagnose execution stalls",
                "completed_item_id": "1",
                "next_item_id": "2",
                "summary": "Config inspected, now analyzing the root cause",
                # Simulate the model echoing a stale full plan payload while also
                # sending explicit transition signals.
                "items": [
                    {"id": "1", "title": "Inspect config", "status": "running"},
                    {"id": "2", "title": "Analyze root cause", "status": "pending"},
                    {"id": "3", "title": "Propose fixes", "status": "pending"},
                ],
            },
        )

        plan = result.get("task_plan") or {}
        statuses = {item.get("id"): item.get("status") for item in plan.get("items") or []}
        self.assertEqual(statuses.get("1"), "done")
        self.assertEqual(statuses.get("2"), "running")
        self.assertEqual(plan.get("current_item_id"), "2")
        self.assertEqual(plan.get("summary"), "Config inspected, now analyzing the root cause")

    def test_mark_done_with_explicit_next_item_stays_in_progress(self):
        task_plan_module.execute(
            "",
            {
                "action": "create_or_update",
                "goal": "Diagnose execution stalls",
                "items": [
                    {"id": "inspect", "title": "Inspect config", "status": "done"},
                    {"id": "verify", "title": "Verify the patch", "status": "running"},
                    {"id": "deliver", "title": "Deliver the result", "status": "pending"},
                ],
                "current_item_id": "verify",
            },
        )

        result = task_plan_module.execute(
            "",
            {
                "action": "mark_done",
                "goal": "Diagnose execution stalls",
                "completed_item_id": "verify",
                "next_item_id": "deliver",
                "summary": "Verification is complete, moving to the delivery step",
                "items": [
                    {"id": "inspect", "title": "Inspect config", "status": "done"},
                    {"id": "verify", "title": "Verify the patch", "status": "done"},
                    {"id": "deliver", "title": "Deliver the result", "status": "running"},
                ],
            },
        )

        plan = result.get("task_plan") or {}
        statuses = {item.get("id"): item.get("status") for item in plan.get("items") or []}
        self.assertEqual(statuses.get("inspect"), "done")
        self.assertEqual(statuses.get("verify"), "done")
        self.assertEqual(statuses.get("deliver"), "running")
        self.assertEqual(plan.get("current_item_id"), "deliver")
        self.assertNotEqual(plan.get("phase"), "done")

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

    def test_task_plan_working_state_tracks_progress_blocker_and_target(self):
        _task, snapshot = task_store_module.save_task_plan_snapshot(
            "continue NovaNotes",
            {
                "goal": "continue NovaNotes",
                "summary": "Blocked while patching the admin page target",
                "items": [
                    {"id": "inspect", "title": "Inspect current flow", "status": "done"},
                    {
                        "id": "patch",
                        "title": "Patch lower layers",
                        "status": "blocked",
                        "detail": "Need the final HTML target path",
                    },
                ],
                "current_item_id": "patch",
                "phase": "blocked",
            },
        )
        task_store_module.remember_fs_target_for_task_plan(
            snapshot,
            {"path": "C:/Users/36459/NovaNotes/templates/index.html", "option": "inspect", "source": "tool_runtime"},
        )

        working_state = task_store_module.get_active_task_working_state("continue NovaNotes")

        self.assertEqual(working_state.get("goal"), "continue NovaNotes")
        self.assertEqual(working_state.get("current_step"), "Patch lower layers")
        self.assertEqual(working_state.get("recent_progress"), "Inspect current flow")
        self.assertEqual(working_state.get("blocker"), "Need the final HTML target path")
        self.assertEqual(working_state.get("next_step"), "Patch lower layers")
        self.assertEqual(
            str(working_state.get("fs_target") or "").replace("\\", "/"),
            "C:/Users/36459/NovaNotes/templates/index.html",
        )

    def test_extract_session_context_exposes_active_working_state(self):
        task_store_module.save_task_plan_snapshot(
            "continue NovaNotes",
            {
                "goal": "continue NovaNotes",
                "summary": "Working on the admin page patch",
                "items": [
                    {"id": "inspect", "title": "Inspect current flow", "status": "done"},
                    {"id": "patch", "title": "Patch lower layers", "status": "running"},
                ],
                "current_item_id": "patch",
                "phase": "patch",
            },
        )

        session_context = session_context_module.extract_session_context([], "continue NovaNotes")

        self.assertEqual(session_context.get("intent"), "")
        self.assertIn("continue NovaNotes", session_context.get("topics") or [])
        self.assertIn("open task context", session_context.get("user_state") or "")
        self.assertIn("user explicitly asked to continue the current task", session_context.get("user_state") or "")
        self.assertIn("resume execution from the current step", session_context.get("user_state") or "")
        self.assertEqual(session_context.get("current_focus"), "Patch lower layers")
        self.assertEqual(session_context.get("resume_point"), "Patch lower layers")
        self.assertEqual((session_context.get("working_state") or {}).get("current_step"), "Patch lower layers")

    def test_mid_sentence_continue_phrase_does_not_resume_unrelated_task_plan(self):
        task_store_module.save_task_plan_snapshot(
            "Plan a complex refactor",
            {
                "goal": "Plan a complex refactor",
                "summary": "Working on the refactor",
                "items": [
                    {"id": "map_flow", "title": "Map the current flow", "status": "running"},
                    {"id": "patch_lower_layers", "title": "Patch lower layers", "status": "pending"},
                ],
                "current_item_id": "map_flow",
                "phase": "inspect",
            },
        )
        casual_query = (
            "\u6ca1\u4e8b \u6211\u5c31\u662f\u60f3\u8ba9\u4f60\u6d4b\u8bd5\u4e00\u4e0b"
            "\u81ea\u5df1\u7684\u80fd\u529b \u770b\u770b\u6211\u6709\u4ec0\u4e48\u5730\u65b9"
            "\u53ef\u4ee5\u7ee7\u7eed\u4f18\u5316\u7684"
        )

        resumed = task_store_module.get_active_task_plan_snapshot(casual_query)
        session_context = session_context_module.extract_session_context([], casual_query)
        prompt = reply_formatter_module._build_tool_call_user_prompt({"user_input": casual_query})

        self.assertIsNone(resumed)
        self.assertNotEqual(session_context.get("intent"), "task_continue")
        self.assertFalse(bool(session_context.get("working_state")))
        self.assertEqual(prompt, casual_query)
        self.assertNotIn("Current task goal in this turn", prompt)

    def test_generic_project_reference_does_not_resume_old_task_plan(self):
        task_store_module.save_task_plan_snapshot(
            "整理文件结构，解决“层级归属”与“物理目录归属”混淆的问题",
            {
                "goal": "整理文件结构，解决“层级归属”与“物理目录归属”混淆的问题",
                "summary": "正在推进：分析当前文件结构问题",
                "items": [
                    {"id": "1", "title": "分析当前文件结构问题", "status": "done"},
                    {"id": "2", "title": "检查记忆系统文件", "status": "done"},
                    {"id": "3", "title": "检查技能系统文件", "status": "done"},
                    {"id": "4", "title": "整理和修复", "status": "done"},
                    {"id": "5", "title": "验证修复结果", "status": "running"},
                ],
                "current_item_id": "5",
                "phase": "verify",
            },
        )

        query = "就是我们这个项目啊"
        resumed = task_store_module.get_active_task_plan_snapshot(query)
        session_context = session_context_module.extract_session_context([], query)
        prompt = reply_formatter_module._build_tool_call_user_prompt({"user_input": query})

        self.assertIsNone(resumed)
        self.assertFalse(bool(session_context.get("working_state")))
        self.assertEqual(prompt, query)
        self.assertNotIn("Current task goal in this turn", prompt)

    def test_explicit_release_message_does_not_resume_active_task_plan(self):
        task_store_module.save_task_plan_snapshot(
            "整理桌面文件，清理临时文件，创建分类文件夹",
            {
                "goal": "整理桌面文件，清理临时文件，创建分类文件夹",
                "summary": "刚处理完临时文件夹的误删问题",
                "items": [
                    {"id": "inspect", "title": "检查桌面临时文件夹", "status": "done"},
                    {"id": "review", "title": "确认用户后续需求", "status": "running"},
                ],
                "current_item_id": "review",
                "phase": "active",
            },
        )

        query = "不用了 删就删了 我回收站也没找到"
        resumed = task_store_module.get_active_task_plan_snapshot(query)
        session_context = session_context_module.extract_session_context([], query)
        prompt = reply_formatter_module._build_tool_call_user_prompt({"user_input": query})

        self.assertIsNone(resumed)
        self.assertFalse(bool(session_context.get("working_state")))
        self.assertEqual(prompt, query)
        self.assertNotIn("Current task goal in this turn", prompt)

    def test_generic_agent_duration_question_does_not_resume_old_desktop_task(self):
        task_store_module.save_task_plan_snapshot(
            "整理桌面文件，清理临时文件，创建分类文件夹",
            {
                "goal": "整理桌面文件，清理临时文件，创建分类文件夹",
                "summary": "刚处理完临时文件夹的误删问题",
                "items": [
                    {"id": "inspect", "title": "检查桌面临时文件夹", "status": "done"},
                    {"id": "review", "title": "确认用户后续需求", "status": "running"},
                ],
                "current_item_id": "review",
                "phase": "active",
            },
        )

        query = "我又来了 现在你知道这个agent做了多久了吗"
        resumed = task_store_module.get_active_task_plan_snapshot(query)
        session_context = session_context_module.extract_session_context([], query)
        prompt = reply_formatter_module._build_tool_call_user_prompt({"user_input": query})

        self.assertIsNone(resumed)
        self.assertFalse(bool(session_context.get("working_state")))
        self.assertEqual(prompt, query)
        self.assertNotIn("Current task goal in this turn", prompt)

    def test_build_active_task_context_ignores_stale_working_state_after_release(self):
        context = reply_formatter_module._build_active_task_context(
            {
                "user_input": "别说了 我都没让你操作啊",
                "l2": {
                    "working_state": {
                        "goal": "整理桌面文件，清理临时文件，创建分类文件夹",
                        "summary": "刚处理完临时文件夹的误删问题",
                        "current_step": "确认用户后续需求",
                        "recent_progress": "检查桌面临时文件夹",
                        "task_status": "active",
                    }
                },
                "l5_success_paths": [],
            }
        )

        self.assertEqual(context, "")

    def test_build_active_task_context_ignores_stale_bundle_task_plan_when_query_unrelated(self):
        context = reply_formatter_module._build_active_task_context(
            {
                "user_input": "我又来了 现在你知道这个agent做了多久了吗",
                "task_plan": {
                    "goal": "整理桌面文件，清理临时文件，创建分类文件夹",
                    "summary": "刚处理完临时文件夹的误删问题",
                    "items": [
                        {"id": "inspect", "title": "检查桌面临时文件夹", "status": "done"},
                        {"id": "review", "title": "确认用户后续需求", "status": "running"},
                    ],
                    "current_item_id": "review",
                    "phase": "active",
                },
                "l5_success_paths": [],
            }
        )

        self.assertEqual(context, "")

    def test_build_active_task_context_uses_working_state_without_bundle_task_plan(self):
        _task, snapshot = task_store_module.save_task_plan_snapshot(
            "continue NovaNotes",
            {
                "goal": "continue NovaNotes",
                "summary": "Blocked while patching the admin page target",
                "items": [
                    {"id": "inspect", "title": "Inspect current flow", "status": "done"},
                    {
                        "id": "patch",
                        "title": "Patch lower layers",
                        "status": "blocked",
                        "detail": "Need the final HTML target path",
                    },
                ],
                "current_item_id": "patch",
                "phase": "blocked",
            },
        )
        task_store_module.remember_fs_target_for_task_plan(
            snapshot,
            {"path": "C:/Users/36459/NovaNotes/templates/index.html", "option": "inspect", "source": "tool_runtime"},
        )
        session_context = session_context_module.extract_session_context([], "continue NovaNotes")

        context = reply_formatter_module._build_active_task_context(
            {
                "user_input": "continue NovaNotes",
                "l2": session_context,
                "l5_success_paths": [],
            }
        )

        self.assertIn("Current step: Patch lower layers", context)
        self.assertIn("Recent progress: Inspect current flow", context)
        self.assertIn("Current blocker: Need the final HTML target path", context)
        self.assertIn("Current task directory/file target: C:/Users/36459/NovaNotes/templates/index.html", context)

    def test_location_followup_keeps_task_context_without_auto_continue_bias(self):
        _task, snapshot = task_store_module.save_task_plan_snapshot(
            "continue NovaNotes",
            {
                "goal": "continue NovaNotes",
                "summary": "Working on the admin page patch",
                "items": [
                    {"id": "inspect", "title": "Inspect current flow", "status": "done"},
                    {"id": "patch", "title": "Patch lower layers", "status": "running"},
                ],
                "current_item_id": "patch",
                "phase": "patch",
            },
        )
        task_store_module.remember_fs_target_for_task_plan(
            snapshot,
            {"path": "C:/Users/36459/NovaNotes/templates/index.html", "option": "inspect", "source": "tool_runtime"},
        )

        query = "that file path?"
        working_state = task_store_module.get_active_task_working_state(query)
        session_context = session_context_module.extract_session_context([], query)
        context = reply_formatter_module._build_active_task_context({"user_input": query, "l5_success_paths": []})

        self.assertEqual((working_state or {}).get("query_mode"), "locate")
        self.assertEqual(((session_context.get("working_state") or {}).get("query_mode")), "locate")
        self.assertIn("answer the current task location first", session_context.get("user_state") or "")
        self.assertIn(
            "Current user request: answer with the current task target or location first.",
            context,
        )
        self.assertIn("Current task directory/file target", context)

    def test_runtime_verification_fields_flow_into_working_state_and_context(self):
        task_store_module.save_task_plan_snapshot(
            "continue NovaNotes",
            {
                "goal": "continue NovaNotes",
                "summary": "Verification is still pending",
                "items": [
                    {"id": "inspect", "title": "Inspect current flow", "status": "done"},
                    {"id": "verify", "title": "Verify the patch", "status": "running"},
                ],
                "current_item_id": "verify",
                "phase": "verify",
                "runtime_status": "verify_failed",
                "next_action": "retry_or_close",
                "last_tool": "run_command",
                "last_action_summary": "Ran the verification command",
                "last_result_summary": "pytest still reports the output file missing",
                "attempt_kind": "retry",
                "execution_lane": "verify",
                "previous_tool": "write_file",
                "parallel_tools": ["read_file", "list_files"],
                "parallel_size": 2,
                "verification": {
                    "verified": False,
                    "detail": "Output file is still missing",
                },
            },
        )

        working_state = task_store_module.get_active_task_working_state("验证了吗")
        session_context = session_context_module.extract_session_context([], "验证了吗")
        context = reply_formatter_module._build_active_task_context({"user_input": "验证了吗", "l5_success_paths": []})

        self.assertEqual(working_state.get("query_mode"), "verify")
        self.assertEqual(working_state.get("runtime_status"), "verify_failed")
        self.assertEqual(working_state.get("blocker"), "Output file is still missing")
        self.assertEqual(working_state.get("verification_status"), "failed")
        self.assertEqual(working_state.get("verification_detail"), "Output file is still missing")
        self.assertEqual(working_state.get("last_tool"), "run_command")
        self.assertEqual(working_state.get("last_action_summary"), "Ran the verification command")
        self.assertEqual(working_state.get("last_result_summary"), "pytest still reports the output file missing")
        self.assertEqual(working_state.get("attempt_kind"), "retry")
        self.assertEqual(working_state.get("execution_lane"), "verify")
        self.assertEqual(working_state.get("previous_tool"), "write_file")
        self.assertEqual(working_state.get("parallel_tools"), ["read_file", "list_files"])
        self.assertEqual(working_state.get("parallel_size"), 2)
        self.assertEqual((working_state.get("current_step_task") or {}).get("status"), "active")
        self.assertEqual((working_state.get("current_step_task") or {}).get("runtime_status"), "verify_failed")
        self.assertEqual((working_state.get("current_step_task") or {}).get("blocker"), "Output file is still missing")
        self.assertEqual((working_state.get("current_step_task") or {}).get("last_tool"), "run_command")
        self.assertEqual((working_state.get("current_step_task") or {}).get("execution_lane"), "verify")
        self.assertIn("answer the current task verification state first", session_context.get("user_state") or "")
        self.assertIn("Latest tool used: run_command", context)
        self.assertIn("Latest action summary: Ran the verification command", context)
        self.assertIn("Latest result summary: pytest still reports the output file missing", context)
        self.assertIn("Current execution lane: verify", context)
        self.assertIn("Latest attempt kind: retry", context)
        self.assertIn("Previous tool before latest step: write_file", context)
        self.assertIn("Latest parallel tool batch: read_file, list_files", context)
        self.assertIn("Current plan-step task status: active", context)
        self.assertIn("Current plan-step runtime status: verify_failed", context)
        self.assertIn("Current blocker: Output file is still missing", context)
        self.assertIn("Latest verification status: failed", context)
        self.assertNotIn("Latest verification detail: Output file is still missing", context)

    def test_task_plan_can_remember_and_retrieve_fs_target(self):
        _task, snapshot = task_store_module.save_task_plan_snapshot(
            "continue NovaNotes",
            {
                "goal": "continue NovaNotes",
                "summary": "continue NovaNotes",
                "items": [{"id": "inspect", "title": "Inspect project", "status": "running"}],
                "current_item_id": "inspect",
                "phase": "inspect",
            },
        )

        remembered = task_store_module.remember_fs_target_for_task_plan(
            snapshot,
            {"path": "C:/Users/36459/NovaNotes", "option": "inspect", "source": "tool_runtime"},
        )
        loaded = task_store_module.get_structured_fs_target_for_task_plan(snapshot)

        self.assertEqual(str(remembered.get("path") or "").replace("\\", "/"), "C:/Users/36459/NovaNotes")
        self.assertEqual(str(loaded.get("path") or "").replace("\\", "/"), "C:/Users/36459/NovaNotes")

    def test_task_plan_does_not_downgrade_project_target_to_desktop_root(self):
        _task, snapshot = task_store_module.save_task_plan_snapshot(
            "continue NovaNotes work",
            {
                "goal": "continue NovaNotes work",
                "summary": "continue NovaNotes work",
                "items": [{"id": "inspect", "title": "Inspect project", "status": "running"}],
                "current_item_id": "inspect",
                "phase": "inspect",
            },
        )

        task_store_module.remember_fs_target_for_task_plan(
            snapshot,
            {"path": "C:/Users/36459/NovaNotes", "option": "inspect", "source": "tool_runtime"},
        )
        remembered = task_store_module.remember_fs_target_for_task_plan(
            snapshot,
            {"path": "C:/Users/36459/Desktop", "option": "open", "source": "tool_runtime"},
        )
        loaded = task_store_module.get_structured_fs_target_for_task_plan(snapshot)

        self.assertEqual(str(remembered.get("path") or "").replace("\\", "/"), "C:/Users/36459/NovaNotes")
        self.assertEqual(str(loaded.get("path") or "").replace("\\", "/"), "C:/Users/36459/NovaNotes")

    def test_short_referential_followup_can_resume_latest_task_plan(self):
        _task, _snapshot = task_store_module.save_task_plan_snapshot(
            "continue NovaNotes",
            {
                "goal": "continue NovaNotes",
                "summary": "continue NovaNotes",
                "items": [{"id": "inspect", "title": "Inspect project", "status": "running"}],
                "current_item_id": "inspect",
                "phase": "inspect",
            },
        )

        resumed = task_store_module.get_active_task_plan_snapshot("它在哪?")

        self.assertIsInstance(resumed, dict)
        self.assertTrue(bool(resumed.get("task_id")))

    def test_long_referential_followup_can_resume_latest_task_plan(self):
        _task, _snapshot = task_store_module.save_task_plan_snapshot(
            "continue NovaNotes",
            {
                "goal": "continue NovaNotes",
                "summary": "continue NovaNotes",
                "items": [{"id": "inspect", "title": "Inspect project", "status": "running"}],
                "current_item_id": "inspect",
                "phase": "inspect",
            },
        )

        resumed = task_store_module.get_active_task_plan_snapshot("之前做的那个记录笔记的文件夹在哪?")

        self.assertIsInstance(resumed, dict)
        self.assertTrue(bool(resumed.get("task_id")))

    def test_explicit_file_path_can_resume_task_plan_from_parent_directory_target(self):
        _task, snapshot = task_store_module.save_task_plan_snapshot(
            "continue NovaNotes",
            {
                "goal": "continue NovaNotes",
                "summary": "continue NovaNotes",
                "items": [{"id": "inspect", "title": "Inspect project", "status": "running"}],
                "current_item_id": "inspect",
                "phase": "inspect",
            },
        )
        task_store_module.remember_fs_target_for_task_plan(
            snapshot,
            {"path": "C:/Users/36459/NovaNotes", "option": "inspect", "source": "tool_runtime"},
        )

        resumed = task_store_module.get_active_task_plan_snapshot(
            "write_file · 目标：c:/Users/36459/NovaNotes/templates/index.html 总是失败"
        )

        self.assertIsInstance(resumed, dict)
        self.assertTrue(bool(resumed.get("task_id")))
        self.assertEqual(resumed.get("goal"), "continue NovaNotes")

    def test_explicit_file_path_prefers_matching_task_plan_over_newer_unrelated_task(self):
        _older_task, older_snapshot = task_store_module.save_task_plan_snapshot(
            "continue NovaNotes",
            {
                "goal": "continue NovaNotes",
                "summary": "continue NovaNotes",
                "items": [{"id": "inspect", "title": "Inspect project", "status": "running"}],
                "current_item_id": "inspect",
                "phase": "inspect",
            },
        )
        task_store_module.remember_fs_target_for_task_plan(
            older_snapshot,
            {"path": "C:/Users/36459/NovaNotes", "option": "inspect", "source": "tool_runtime"},
        )

        _newer_task, newer_snapshot = task_store_module.save_task_plan_snapshot(
            "OtherProject build pipeline",
            {
                "goal": "OtherProject build pipeline",
                "summary": "OtherProject build pipeline",
                "items": [{"id": "inspect", "title": "Inspect other project", "status": "running"}],
                "current_item_id": "inspect",
                "phase": "inspect",
            },
        )
        task_store_module.remember_fs_target_for_task_plan(
            newer_snapshot,
            {"path": "D:/Sandbox/OtherProject", "option": "inspect", "source": "tool_runtime"},
        )

        resumed = task_store_module.get_active_task_plan_snapshot(
            "还是 c:/Users/36459/NovaNotes/templates/index.html 这个文件"
        )

        self.assertIsInstance(resumed, dict)
        self.assertEqual(resumed.get("goal"), "continue NovaNotes")
        self.assertNotEqual(resumed.get("goal"), "OtherProject build pipeline")

    def test_referential_followup_prefers_matching_task_plan_when_preferred_fs_target_is_known(self):
        _older_task, older_snapshot = task_store_module.save_task_plan_snapshot(
            "continue NovaNotes",
            {
                "goal": "continue NovaNotes",
                "summary": "continue NovaNotes",
                "items": [{"id": "inspect", "title": "Inspect project", "status": "running"}],
                "current_item_id": "inspect",
                "phase": "inspect",
            },
        )
        task_store_module.remember_fs_target_for_task_plan(
            older_snapshot,
            {"path": "C:/Users/36459/NovaNotes/templates/index.html", "option": "inspect", "source": "tool_runtime"},
        )

        task_store_module.save_task_plan_snapshot(
            "找回丢失物品",
            {
                "goal": "找回丢失物品",
                "summary": "通过系统化回溯与排查，定位并取回丢失物品",
                "items": [{"id": "trace_back", "title": "回溯活动路径", "status": "running"}],
                "current_item_id": "trace_back",
                "phase": "immediate_search",
            },
        )

        resumed = task_store_module.get_active_task_plan_snapshot(
            "怎么又丢了",
            preferred_fs_target="C:/Users/36459/NovaNotes/templates/index.html",
        )

        self.assertIsInstance(resumed, dict)
        self.assertEqual(resumed.get("goal"), "continue NovaNotes")

    def test_shared_task_plan_project_does_not_borrow_fs_target_from_other_task(self):
        _older_task, older_snapshot = task_store_module.save_task_plan_snapshot(
            "continue NovaNotes",
            {
                "goal": "continue NovaNotes",
                "summary": "continue NovaNotes",
                "items": [{"id": "inspect", "title": "Inspect project", "status": "running"}],
                "current_item_id": "inspect",
                "phase": "inspect",
            },
        )
        task_store_module.remember_fs_target_for_task_plan(
            older_snapshot,
            {"path": "C:/Users/36459/NovaNotes/templates/index.html", "option": "inspect", "source": "tool_runtime"},
        )

        _newer_task, newer_snapshot = task_store_module.save_task_plan_snapshot(
            "找回丢失物品",
            {
                "goal": "找回丢失物品",
                "summary": "通过系统化回溯与排查，定位并取回丢失物品",
                "items": [{"id": "trace_back", "title": "回溯活动路径", "status": "running"}],
                "current_item_id": "trace_back",
                "phase": "immediate_search",
            },
        )

        loaded = task_store_module.get_structured_fs_target_for_task_plan(newer_snapshot)

        self.assertIsNone(loaded)


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
