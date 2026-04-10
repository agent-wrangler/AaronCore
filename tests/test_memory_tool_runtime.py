import unittest

from decision.tool_runtime.memory_tools import execute_memory_tool, format_recall


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
                "path": "C:/Users/36459/NovaCore",
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
        self.assertIn("C:/Users/36459/NovaCore", effective_query)
        self.assertEqual(seen.get("l2_kwargs"), {"limit": 5})
        self.assertEqual(seen.get("l3_kwargs"), {"limit": 5, "query": effective_query})
        self.assertIn("AaronCore milestone", recall["response"])


if __name__ == "__main__":
    unittest.main()
