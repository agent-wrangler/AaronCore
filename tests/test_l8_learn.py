import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory import l2_memory
from core import l8_learn


class L8LearnTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmpdir.name)
        self.knowledge_file = self.state_dir / "knowledge.json"
        self.knowledge_base_file = self.state_dir / "knowledge_base.json"
        self.config_file = self.state_dir / "autolearn_config.json"
        self._patcher = patch.multiple(
            l8_learn,
            STATE_DIR=self.state_dir,
            KNOWLEDGE_FILE=self.knowledge_file,
            KNOWLEDGE_BASE_FILE=self.knowledge_base_file,
            CONFIG_FILE=self.config_file,
        )
        self._patcher.start()
        l8_learn.save_autolearn_config(dict(l8_learn.DEFAULT_CONFIG))

    def tearDown(self):
        self._patcher.stop()
        self._tmpdir.cleanup()

    def _read_knowledge_base(self):
        if not self.knowledge_base_file.exists():
            return []
        return json.loads(self.knowledge_base_file.read_text(encoding="utf-8"))

    def _read_l5_knowledge(self):
        if not self.knowledge_file.exists():
            return []
        return json.loads(self.knowledge_file.read_text(encoding="utf-8"))

    def test_should_trigger_auto_learn_allows_question_like_queries(self):
        allowed, reason = l8_learn.should_trigger_auto_learn("FastAPI 是什么？")

        self.assertTrue(allowed)
        self.assertEqual(reason, "eligible")

    def test_should_trigger_auto_learn_no_longer_keyword_blocks_greetings(self):
        allowed, reason = l8_learn.should_trigger_auto_learn("hello")

        self.assertTrue(allowed)
        self.assertEqual(reason, "eligible")

    def test_should_trigger_auto_learn_rejects_skill_handled_queries(self):
        allowed, reason = l8_learn.should_trigger_auto_learn(
            "帮我查下上海天气怎么样",
            route_result={"mode": "skill", "skill": "weather"},
        )

        self.assertFalse(allowed)
        self.assertEqual(reason, "handled_by_skill")

    def test_should_trigger_auto_learn_no_longer_uses_question_keyword_gate(self):
        allowed, reason = l8_learn.should_trigger_auto_learn("今天心情不错")

        self.assertTrue(allowed)
        self.assertEqual(reason, "eligible")

    def test_auto_learn_uses_llm_to_reject_non_knowledge_input(self):
        with patch.object(l8_learn, "_llm_call", return_value="NO"), \
             patch.object(l8_learn, "search_web_results") as mock_search:
            result = l8_learn.auto_learn("hello")

        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "not_knowledge_query")
        mock_search.assert_not_called()

    def test_is_explicit_learning_request_uses_llm_yes_no(self):
        with patch.object(l8_learn, "_llm_call", return_value="YES"):
            self.assertTrue(l8_learn.is_explicit_learning_request("你去查一下量子计算"))

        with patch.object(l8_learn, "_llm_call", return_value="NO"):
            self.assertFalse(l8_learn.is_explicit_learning_request("量子计算是什么"))

    def test_save_and_find_relevant_knowledge_updates_hit_count_when_touched(self):
        l8_learn.save_learned_knowledge(
            "FastAPI 是什么？",
            "FastAPI 是一个现代 Python Web 框架。",
            [
                {
                    "title": "FastAPI 官方文档",
                    "snippet": "FastAPI 是一个高性能的 Python Web 框架。",
                    "url": "https://fastapi.tiangolo.com/",
                }
            ],
        )

        hits = l8_learn.find_relevant_knowledge("FastAPI 是什么？", touch=True)
        stored = self._read_knowledge_base()

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["query"], "FastAPI 是什么？")
        self.assertEqual(stored[0]["hit_count"], 1)
        self.assertIn("last_used", stored[0])

    def test_find_relevant_knowledge_no_longer_requires_entry_keywords(self):
        self.knowledge_base_file.write_text(
            json.dumps(
                [
                    {
                        "id": "l8_1",
                        "source": "bing_rss",
                        "type": "knowledge",
                        "query": "mcp protocol",
                        "summary": "mcp protocol connects models with tools and external context.",
                        "keywords": [],
                        "trigger": [],
                        "created_at": "2026-03-29T10:00:00",
                        "last_used": "2026-03-29T10:00:00",
                        "hit_count": 0,
                        "一级场景": "自主学习",
                        "二级场景": "自动学习-mcp",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        hits = l8_learn.find_relevant_knowledge("mcp protocol", touch=False)

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["query"], "mcp protocol")

    def test_find_relevant_knowledge_uses_llm_semantic_ranking_for_non_exact_matches(self):
        self.knowledge_base_file.write_text(
            json.dumps(
                [
                    {
                        "id": "l8_semantic",
                        "source": "bing_rss",
                        "type": "knowledge",
                        "query": "model context protocol overview",
                        "summary": "Model Context Protocol lets models use tools and external context through a standard interface.",
                        "created_at": "2026-03-29T10:00:00",
                        "last_used": "2026-03-29T10:00:00",
                        "hit_count": 0,
                        "一级场景": "自主学习",
                        "二级场景": "自动学习-mcp",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with patch.object(l8_learn, "_llm_call", return_value='[{"id":"l8_semantic","score":2}]'):
            hits = l8_learn.find_relevant_knowledge("什么是 MCP", touch=False)

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["query"], "model context protocol overview")

    def test_auto_learn_writes_knowledge_entry_from_search_results(self):
        mock_results = [
            {
                "title": "FastAPI 是什么",
                "snippet": "FastAPI 是用于构建 API 的现代 Python Web 框架。",
                "url": "https://fastapi.tiangolo.com/",
            },
            {
                "title": "FastAPI 教程",
                "snippet": "FastAPI 提供类型提示驱动的开发体验。",
                "url": "https://example.com/fastapi-tutorial",
            },
        ]

        def fake_llm(prompt, *args, **kwargs):
            max_tokens = kwargs.get("max_tokens")
            if max_tokens == 5:
                return "YES"
            if max_tokens == 16:
                return "OK"
            if max_tokens == 20:
                return "FastAPI"
            if "3-5" in prompt:
                return "FastAPI, Python, Web"
            return "FastAPI 是一个现代 Python Web 框架，支持类型提示驱动的开发。"

        with patch.object(l8_learn, "search_web_results", return_value=mock_results), \
             patch.object(l8_learn, "_llm_call", fake_llm):
            result = l8_learn.auto_learn("FastAPI 是什么？")

        stored = self._read_knowledge_base()

        self.assertTrue(result["success"])
        self.assertEqual(result["type"], "knowledge")
        self.assertEqual(result["result_count"], 2)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["query"], "FastAPI 是什么？")
        self.assertIn("FastAPI", stored[0]["summary"])

    def test_auto_learn_accepts_semantically_relevant_results_without_keyword_overlap(self):
        mock_results = [
            {
                "title": "Model Context Protocol overview",
                "snippet": "MCP is an open protocol for connecting models with tools and external context.",
                "url": "https://example.com/mcp",
            }
        ]

        def fake_llm(prompt, *args, **kwargs):
            max_tokens = kwargs.get("max_tokens")
            if max_tokens == 5:
                return "YES"
            if max_tokens == 16:
                return "OK"
            if max_tokens == 20:
                return "MCP"
            if "3-5" in prompt:
                return "MCP, protocol"
            return "MCP 是一种连接模型与工具和外部上下文的协议。"

        with patch.object(l8_learn, "search_web_results", return_value=mock_results), \
             patch.object(l8_learn, "_llm_call", fake_llm):
            result = l8_learn.auto_learn("什么是MCP")

        stored = self._read_knowledge_base()

        self.assertTrue(result["success"])
        self.assertEqual(result["result_count"], 1)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["query"], "什么是MCP")

    def test_auto_learn_uses_llm_to_reject_irrelevant_search_results(self):
        mock_results = [
            {
                "title": "Newton biography",
                "snippet": "A short introduction to Isaac Newton and classical mechanics.",
                "url": "https://example.com/newton",
            }
        ]

        def fake_llm(prompt, *args, **kwargs):
            max_tokens = kwargs.get("max_tokens")
            if max_tokens == 5:
                return "NO"
            if max_tokens == 20:
                return "量子计算"
            return "OK"

        with patch.object(l8_learn, "search_web_results", return_value=mock_results), \
             patch.object(l8_learn, "_llm_call", fake_llm):
            result = l8_learn.auto_learn("帮我查一下量子计算")

        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "search_results_irrelevant")

    def test_auto_learn_skips_search_when_query_is_already_known(self):
        l8_learn.save_learned_knowledge(
            "FastAPI 是什么？",
            "FastAPI 是一个现代 Python Web 框架。",
            [
                {
                    "title": "FastAPI 官方文档",
                    "snippet": "FastAPI 是一个高性能的 Python Web 框架。",
                    "url": "https://fastapi.tiangolo.com/",
                }
            ],
        )

        with patch.object(l8_learn, "search_web_results") as mock_search:
            result = l8_learn.auto_learn("FastAPI 是什么？")

        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "already_known")
        mock_search.assert_not_called()

    def test_should_surface_knowledge_entry_rejects_dirty_l8_items(self):
        dirty_entry = {
            "source": "l2_crystallize",
            "type": "knowledge",
            "query": "我都不知道你说的是什么意思",
            "summary": "<think>这段对话没有可复用知识</think>",
        }

        self.assertFalse(l8_learn.should_surface_knowledge_entry(dirty_entry))
        self.assertFalse(l8_learn.should_show_l8_timeline_entry(dirty_entry))

    def test_prune_l8_garbage_entries_backs_up_and_removes_dirty_items(self):
        self.knowledge_base_file.write_text(
            json.dumps(
                [
                    {
                        "source": "bing_rss",
                        "type": "knowledge",
                        "query": "FastAPI 是什么？",
                        "summary": "FastAPI 是一个高性能 Python Web 框架，适合构建 API。",
                    },
                    {
                        "source": "l2_crystallize",
                        "type": "knowledge",
                        "query": "我都不知道你说的是什么意思",
                        "summary": "<think>这段对话没有可复用知识</think>",
                    },
                    {
                        "source": "feedback_relearn",
                        "type": "feedback_relearn",
                        "query": "好神奇",
                        "summary": "上次回复偏了，需要纠偏。",
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = l8_learn.prune_l8_garbage_entries()
        stored = self._read_knowledge_base()
        backups = list(self.state_dir.glob("knowledge_base.backup_*.json"))

        self.assertTrue(result["success"])
        self.assertEqual(result["removed_count"], 2)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["query"], "FastAPI 是什么？")
        self.assertEqual(len(backups), 1)

    def test_save_learned_knowledge_sanitizes_extra_fields(self):
        entry = l8_learn.save_learned_knowledge(
            "FastAPI 是什么？",
            "<think>internal</think>FastAPI 是一个高性能 Python Web 框架。",
            [],
            extra_fields={"feedback_fix": "<think>internal</think>下次先直接回答定义"},
        )

        stored = self._read_knowledge_base()

        self.assertEqual(entry["summary"], "FastAPI 是一个高性能 Python Web 框架。")
        self.assertEqual(stored[0]["feedback_fix"], "下次先直接回答定义")

    def test_save_learned_knowledge_no_longer_persists_keywords_fields(self):
        entry = l8_learn.save_learned_knowledge(
            "FastAPI 是什么？",
            "FastAPI 是一个现代 Python Web 框架。",
            [],
        )

        stored = self._read_knowledge_base()

        self.assertNotIn("keywords", entry)
        self.assertNotIn("trigger", entry)
        self.assertNotIn("keywords", stored[0])
        self.assertNotIn("trigger", stored[0])

    def test_save_learned_knowledge_defaults_primary_scene_for_reusable_knowledge(self):
        entry = l8_learn.save_learned_knowledge(
            "MCP 是什么？",
            "MCP 是一种让模型与工具和外部上下文连接的协议。",
            [],
        )

        self.assertEqual(entry["layer"], "L8")
        self.assertEqual(entry["一级场景"], "自主学习")
        self.assertEqual(entry["二级场景"], "自动学习-MCP 是什么？")

    def test_save_learned_knowledge_routes_tool_scene_into_l5(self):
        entry = l8_learn.save_learned_knowledge(
            "上海天气",
            "这是一次天气技能返回后的知识记录，包含可复用信息。",
            [],
            route_result={"mode": "skill", "skill": "weather"},
        )

        stored_l8 = self._read_knowledge_base()
        stored_l5 = self._read_l5_knowledge()

        self.assertEqual(entry["layer"], "L5")
        self.assertEqual(stored_l8, [])
        self.assertEqual(len(stored_l5), 1)
        self.assertEqual(stored_l5[0]["核心技能"], "weather")

    def test_save_learned_knowledge_routes_method_query_into_existing_l5_hint(self):
        self.knowledge_file.write_text(
            json.dumps(
                [
                    {
                        "name": "weather",
                        "一级场景": "工具应用",
                        "二级场景": "天气查询",
                        "核心技能": "weather",
                        "trigger": ["天气", "气温"],
                        "应用示例": "查询城市天气",
                        "使用次数": 2,
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        entry = l8_learn.save_learned_knowledge(
            "天气怎么查",
            "这是一个关于天气查询方式的方法总结。",
            [],
        )

        stored_l8 = self._read_knowledge_base()
        stored_l5 = self._read_l5_knowledge()

        self.assertEqual(entry["layer"], "L5")
        self.assertEqual(stored_l8, [])
        self.assertEqual(len(stored_l5), 1)
        self.assertIn("天气怎么查", stored_l5[0]["trigger"])
        self.assertEqual(stored_l5[0]["使用次数"], 3)

    def test_should_surface_knowledge_entry_rejects_tool_application_items(self):
        entry = {
            "source": "bing_rss",
            "type": "knowledge",
            "query": "上海天气",
            "summary": "这是一次天气技能返回后的方法型记录。",
            "一级场景": "工具应用",
            "核心技能": "weather",
        }

        self.assertFalse(l8_learn.should_surface_knowledge_entry(entry))
        self.assertFalse(l8_learn.should_show_l8_timeline_entry(entry))

    def test_save_learned_knowledge_uses_llm_quality_gate_for_self_referential_entries(self):
        def fake_llm(prompt, *args, **kwargs):
            if kwargs.get("max_tokens") == 16:
                return "self_referential"
            return "OK"

        with patch.object(l8_learn, "_llm_call", fake_llm):
            result = l8_learn.save_learned_knowledge(
                "我们的记忆系统怎么工作",
                "这条摘要主要在解释系统内部运行和记忆层的工作方式，不是外部可复用知识。",
                [],
            )

        self.assertFalse(result["saved"])
        self.assertEqual(result["reason"], "self_referential")
        self.assertEqual(self._read_knowledge_base(), [])

    def test_feedback_relearn_does_not_persist_into_l8_knowledge_base(self):
        with patch.object(
            l8_learn,
            "search_web_results",
            return_value=[
                {
                    "title": "FastAPI 是什么？",
                    "snippet": "FastAPI 是一个高性能 Python Web 框架。",
                    "url": "https://fastapi.tiangolo.com/",
                }
            ],
        ):
            result = l8_learn.auto_learn_from_feedback(
                {
                    "id": "fb_1",
                    "last_question": "FastAPI 是什么？",
                    "user_feedback": "上次回复偏了",
                    "last_answer": "我回答得不准",
                    "scene": "general",
                    "problem": "generic_feedback",
                    "fix": "keep_observing_and_refine",
                }
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["entry"]["type"], "feedback_relearn")
        self.assertEqual(self._read_knowledge_base(), [])

    def test_l2_to_l8_uses_unified_l8_writer(self):
        with patch.object(l2_memory, "_condense_knowledge", return_value="FastAPI 是一个现代 Python Web 框架。"), \
             patch("core.l8_learn.save_learned_knowledge", return_value={"saved": True}) as mock_save:
            l2_memory._to_l8("FastAPI 是什么？", "FastAPI 是一个现代 Python Web 框架。")

        mock_save.assert_called_once_with(
            "FastAPI 是什么？",
            "FastAPI 是一个现代 Python Web 框架。",
            [],
            source="l2_crystallize",
        )


if __name__ == "__main__":
    unittest.main()
