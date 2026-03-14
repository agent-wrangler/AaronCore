import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.l8_learn as l8_learn_module
import memory as memory_module
from agent_final import normalize_route_result, resolve_route, unified_chat_reply, unified_skill_reply


class SkillFallbackTests(unittest.TestCase):
    def test_normalize_route_result_downgrades_unknown_skill_to_missing_skill_intent(self):
        result = normalize_route_result(
            {"mode": "skill", "skill": "news", "reason": "llm_guess"},
            "今天有什么新闻",
            "llm",
        )

        self.assertEqual(result["mode"], "chat")
        self.assertEqual(result.get("intent"), "missing_skill")
        self.assertEqual(result.get("missing_skill"), "news")

    def test_unified_chat_reply_honestly_handles_missing_skill(self):
        reply = unified_chat_reply(
            {"user_input": "今天有什么新闻", "l3": [], "l4": {}, "l5": {"skills": {}}, "l8": []},
            {"mode": "chat", "skill": "news", "intent": "missing_skill", "missing_skill": "news", "rewritten_input": "今天有什么新闻"},
        )

        self.assertIn("没接上", reply)
        self.assertIn("新闻", reply)

    def test_resolve_route_short_circuits_news_to_missing_skill(self):
        bundle = {
            "user_input": "今天有什么新闻",
            "l1": [],
            "l2": [],
            "l3": [],
            "l4": {},
            "l5": {"skills": {}},
            "l8": [],
            "dialogue_context": "",
        }

        with patch("agent_final.nova_route", side_effect=AssertionError("core route should not run")), patch(
            "agent_final.llm_route", side_effect=AssertionError("llm route should not run")
        ):
            result = resolve_route(bundle)

        self.assertEqual(result.get("intent"), "missing_skill")
        self.assertEqual(result.get("missing_skill"), "news")

    def test_unified_skill_reply_humanizes_runtime_failure(self):
        bundle = {"user_input": "上海天气怎么样", "l4": {}, "dialogue_context": ""}

        with patch("agent_final.nova_execute", return_value={"success": False, "error": "执行失败: timeout"}):
            result = unified_skill_reply(bundle, "weather", "上海天气怎么样")

        self.assertFalse(result["trace"]["success"])
        self.assertIn("没跑稳", result["reply"])


class MemoryEvolutionTests(unittest.TestCase):
    def test_evolve_skips_unknown_skill_usage_but_keeps_preferences(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            evolution_path = tmp / "evolution.json"
            knowledge_path = tmp / "knowledge.json"
            evolution_path.write_text(
                json.dumps({"skills_used": {}, "user_preferences": {}, "learning": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            knowledge_path.write_text("[]", encoding="utf-8")

            with patch.object(memory_module, "evolution_file", evolution_path), patch.object(
                memory_module, "knowledge_file", knowledge_path
            ):
                result = memory_module.evolve("今天有什么新闻", "news")

        self.assertEqual(result["skills_used"], {})
        self.assertEqual(result["user_preferences"], {})

    def test_find_relevant_knowledge_skips_invalid_tool_skill_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            knowledge_path = tmp / "knowledge_base.json"
            knowledge_path.write_text(
                json.dumps(
                    [
                        {
                            "一级场景": "工具应用",
                            "二级场景": "新闻查询",
                            "核心技能": "news_query",
                            "应用示例": "查询全球热点新闻",
                            "trigger": ["新闻", "热点"],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(l8_learn_module, "KNOWLEDGE_BASE_FILE", knowledge_path):
                result = l8_learn_module.find_relevant_knowledge("今天有什么新闻", touch=True)

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
