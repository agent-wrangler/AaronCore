import tempfile
import unittest
from pathlib import Path

from decision.tool_runtime import inspection_tools as inspection_tools_module
from decision.tool_runtime.memory_tools import execute_memory_tool, format_recall

TEST_REPO_ROOT = Path(__file__).resolve().parents[1].as_posix()


class MemoryToolRuntimeTests(unittest.TestCase):
    def test_format_recall_accepts_current_l2_and_l3_shapes(self):
        l2_results = [
            {
                "user_text": "\u6211\u4eec\u524d\u9762\u804a\u8fc7 state_data \u600e\u4e48\u5206",
                "ai_text": "\u540e\u6765\u6536\u6210\u4e86 state_data \u4e0b\u56db\u4e2a store",
            }
        ]
        l3_events = [
            "\u7528\u6237\u628a memory=\u4ee3\u7801\uff0cstate_data=\u6570\u636e\u603b\u4ed3 \u8fd9\u4e2a\u8fb9\u754c\u5b9a\u4e0b\u6765\u4e86\u3002"
        ]

        result = format_recall(l2_results, l3_events)

        self.assertIn("\u6211\u4eec\u524d\u9762\u804a\u8fc7 state_data \u600e\u4e48\u5206", result)
        self.assertIn("state_data \u4e0b\u56db\u4e2a store", result)
        self.assertIn("memory=\u4ee3\u7801", result)

    def test_format_recall_skips_non_dict_l2_entries_without_crashing(self):
        result = format_recall(["bad-entry"], ["\u4e00\u6761\u957f\u671f\u8bb0\u5fc6"])

        self.assertIn("\u4e00\u6761\u957f\u671f\u8bb0\u5fc6", result)

    def test_execute_memory_tool_returns_runtime_meta_for_recall_and_knowledge(self):
        seen = {}

        def fake_load_l3_long_term(**kwargs):
            seen.update(kwargs)
            return ["l3"]

        recall = execute_memory_tool(
            "recall_memory",
            {"query": "state_data"},
            debug_write=lambda *_args, **_kwargs: None,
            l2_search_relevant=lambda *_args, **_kwargs: [{"user_text": "q", "ai_text": "a"}],
            load_l3_long_term=fake_load_l3_long_term,
            find_relevant_knowledge=lambda *_args, **_kwargs: [],
            execute_web_search=lambda *_args, **_kwargs: {},
            execute_self_fix=lambda *_args, **_kwargs: {},
            execute_read_file=lambda *_args, **_kwargs: {},
            execute_list_files_v3=lambda *_args, **_kwargs: {},
            execute_discover_tools=lambda *_args, **_kwargs: {},
            execute_sense_environment=lambda *_args, **_kwargs: {},
        )
        knowledge = execute_memory_tool(
            "query_knowledge",
            {"topic": "stats"},
            debug_write=lambda *_args, **_kwargs: None,
            l2_search_relevant=lambda *_args, **_kwargs: [],
            load_l3_long_term=lambda **_kwargs: [],
            find_relevant_knowledge=lambda *_args, **_kwargs: [{"name": "stats", "summary": "ok"}],
            execute_web_search=lambda *_args, **_kwargs: {},
            execute_self_fix=lambda *_args, **_kwargs: {},
            execute_read_file=lambda *_args, **_kwargs: {},
            execute_list_files_v3=lambda *_args, **_kwargs: {},
            execute_discover_tools=lambda *_args, **_kwargs: {},
            execute_sense_environment=lambda *_args, **_kwargs: {},
        )

        self.assertEqual(
            recall["meta"]["memory_stats"],
            {"l2_searches": 1, "l2_hits": 1, "l3_queries": 1, "l3_hits": 1},
        )
        self.assertEqual(seen, {"limit": 5, "query": "state_data"})
        self.assertEqual(
            knowledge["meta"]["memory_stats"],
            {"l8_searches": 1, "l8_hits": 1},
        )

    def test_execute_memory_tool_prefers_long_term_timeline_for_duration_queries(self):
        recall = execute_memory_tool(
            "recall_memory",
            {"query": "我们这个agent做了多久 项目开始时间 开发时长"},
            debug_write=lambda *_args, **_kwargs: None,
            l2_search_relevant=lambda *_args, **_kwargs: [
                {"user_text": "你觉得agent到什么程度就算好了", "ai_text": "成熟度评估维度如下"}
            ],
            load_l3_long_term=lambda **_kwargs: ["用户明确说 novacore 是最近搞出来的 agent 框架。"],
            find_relevant_knowledge=lambda *_args, **_kwargs: [],
            execute_web_search=lambda *_args, **_kwargs: {},
            execute_self_fix=lambda *_args, **_kwargs: {},
            execute_read_file=lambda *_args, **_kwargs: {},
            execute_list_files_v3=lambda *_args, **_kwargs: {},
            execute_discover_tools=lambda *_args, **_kwargs: {},
            execute_sense_environment=lambda *_args, **_kwargs: {},
        )

        self.assertTrue(recall["response"].startswith("[长期记忆]"))
        self.assertNotIn("成熟度评估维度如下", recall["response"])
        self.assertIn("最近搞出来的 agent 框架", recall["response"])


    def test_execute_memory_tool_scopes_recall_with_runtime_project_context(self):
        seen = {}

        def fake_l2_search(query, **kwargs):
            seen["l2_query"] = query
            seen["l2_kwargs"] = kwargs
            return []

        def fake_load_l3_long_term(**kwargs):
            seen["l3_kwargs"] = kwargs
            return ["AaronCore milestone"]

        context = {
            "working_state": {
                "goal": "Continue AaronCore development",
                "summary": "Current agent project",
                "recent_progress": "Memory recall is being tuned",
                "project_id": "aaroncore",
            },
            "task_plan": {
                "goal": "Improve current AaronCore agent memory recall",
                "summary": "Make recall_memory prefer the active project scope",
            },
            "fs_target": {
                "path": TEST_REPO_ROOT,
                "option": "inspect",
            },
        }

        recall = execute_memory_tool(
            "recall_memory",
            {"query": "how long have we been building this agent"},
            context=context,
            debug_write=lambda *_args, **_kwargs: None,
            l2_search_relevant=fake_l2_search,
            load_l3_long_term=fake_load_l3_long_term,
            find_relevant_knowledge=lambda *_args, **_kwargs: [],
            execute_web_search=lambda *_args, **_kwargs: {},
            execute_self_fix=lambda *_args, **_kwargs: {},
            execute_read_file=lambda *_args, **_kwargs: {},
            execute_list_files_v3=lambda *_args, **_kwargs: {},
            execute_discover_tools=lambda *_args, **_kwargs: {},
            execute_sense_environment=lambda *_args, **_kwargs: {},
        )

        effective_query = seen.get("l2_query") or ""
        self.assertIn("how long have we been building this agent", effective_query)
        self.assertIn("Current project scope:", effective_query)
        self.assertIn("AaronCore", effective_query)
        self.assertIn(TEST_REPO_ROOT, effective_query)
        self.assertEqual(seen.get("l2_kwargs"), {"limit": 5})
        self.assertEqual(seen.get("l3_kwargs"), {"limit": 5, "query": effective_query})
        self.assertIn("AaronCore milestone", recall["response"])

    def test_execute_memory_tool_forwards_context_to_read_and_list_tools(self):
        seen = {}
        context = {
            "execution_lane": "verify",
            "current_step_task": {"task_id": "task_step_verify", "execution_lane": "verify"},
            "fs_target": {"path": TEST_REPO_ROOT, "option": "inspect"},
        }

        def fake_read(arguments, **kwargs):
            seen["read_arguments"] = arguments
            seen["read_context"] = kwargs.get("context")
            return {"success": True, "response": "read ok"}

        def fake_list(arguments, **kwargs):
            seen["list_arguments"] = arguments
            seen["list_context"] = kwargs.get("context")
            return {"success": True, "response": "list ok"}

        read_result = execute_memory_tool(
            "read_file",
            {},
            context=context,
            debug_write=lambda *_args, **_kwargs: None,
            l2_search_relevant=lambda *_args, **_kwargs: [],
            load_l3_long_term=lambda **_kwargs: [],
            find_relevant_knowledge=lambda *_args, **_kwargs: [],
            execute_web_search=lambda *_args, **_kwargs: {},
            execute_self_fix=lambda *_args, **_kwargs: {},
            execute_read_file=fake_read,
            execute_list_files_v3=fake_list,
            execute_discover_tools=lambda *_args, **_kwargs: {},
            execute_sense_environment=lambda *_args, **_kwargs: {},
        )
        list_result = execute_memory_tool(
            "list_files",
            {},
            context=context,
            debug_write=lambda *_args, **_kwargs: None,
            l2_search_relevant=lambda *_args, **_kwargs: [],
            load_l3_long_term=lambda **_kwargs: [],
            find_relevant_knowledge=lambda *_args, **_kwargs: [],
            execute_web_search=lambda *_args, **_kwargs: {},
            execute_self_fix=lambda *_args, **_kwargs: {},
            execute_read_file=fake_read,
            execute_list_files_v3=fake_list,
            execute_discover_tools=lambda *_args, **_kwargs: {},
            execute_sense_environment=lambda *_args, **_kwargs: {},
        )

        self.assertEqual(read_result["response"], "read ok")
        self.assertEqual(list_result["response"], "list ok")
        self.assertEqual(seen.get("read_arguments"), {})
        self.assertEqual(seen.get("list_arguments"), {})
        self.assertIs(seen.get("read_context"), context)
        self.assertIs(seen.get("list_context"), context)

    def test_read_file_uses_current_step_fs_target_when_file_path_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "pkg" / "main.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("print('ok')\n", encoding="utf-8")

            result = inspection_tools_module.execute_read_file(
                {},
                allowed_prefixes=[str(root)],
                resolve_user_file_target=lambda raw: Path(raw).resolve(),
                is_allowed_user_target=lambda _path: True,
                debug_write=lambda *_args, **_kwargs: None,
                context={
                    "execution_lane": "verify",
                    "current_step_task": {"task_id": "task_step_verify", "execution_lane": "verify"},
                    "fs_target": {"path": str(target), "option": "inspect"},
                },
                project_root=root,
            )

        self.assertTrue(result["success"])
        self.assertIn("main.py", result["response"])
        self.assertIn("print('ok')", result["response"])

    def test_list_files_uses_current_step_file_parent_when_directory_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "pkg" / "main.py"
            sibling = root / "pkg" / "utils.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("print('ok')\n", encoding="utf-8")
            sibling.write_text("print('util')\n", encoding="utf-8")

            result = inspection_tools_module.execute_list_files_v3(
                {},
                resolve_user_file_target=lambda raw: Path(raw).resolve(),
                normalize_user_special_path=lambda raw: raw,
                is_allowed_user_target=lambda _path: True,
                context={
                    "execution_lane": "verify",
                    "current_step_task": {"task_id": "task_step_verify", "execution_lane": "verify"},
                    "fs_target": {"path": str(target), "option": "inspect"},
                },
                project_root=root,
            )

        self.assertTrue(result["success"])
        self.assertIn("main.py", result["response"])
        self.assertIn("utils.py", result["response"])
        self.assertIn(str(target.parent).replace("\\", "/"), result["response"])


if __name__ == "__main__":
    unittest.main()
