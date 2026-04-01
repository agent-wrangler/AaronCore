import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.runtime_memory import l2_memory
from core import l8_learn


class L8LearnTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmpdir.name)
        self.knowledge_base_file = self.state_dir / "knowledge_base.json"
        self.config_file = self.state_dir / "autolearn_config.json"
        self._patcher = patch.multiple(
            l8_learn,
            STATE_DIR=self.state_dir,
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

    def test_should_trigger_auto_learn_allows_question_like_queries(self):
        allowed, reason = l8_learn.should_trigger_auto_learn("FastAPI 是什么？")

        self.assertTrue(allowed)
        self.assertEqual(reason, "eligible")

    def test_should_trigger_auto_learn_rejects_greetings(self):
        allowed, reason = l8_learn.should_trigger_auto_learn("hello")

        self.assertFalse(allowed)
        self.assertEqual(reason, "greeting")

    def test_should_trigger_auto_learn_rejects_skill_handled_queries(self):
        allowed, reason = l8_learn.should_trigger_auto_learn(
            "帮我查下上海天气怎么样",
            route_result={"mode": "skill", "skill": "weather"},
        )

        self.assertFalse(allowed)
        self.assertEqual(reason, "handled_by_skill")

    def test_should_trigger_auto_learn_rejects_non_question_like_queries(self):
        # "今天心情不错" 既不是问句也不是学习请求
        allowed, reason = l8_learn.should_trigger_auto_learn("今天心情不错")

        self.assertFalse(allowed)

    def test_save_and_find_relevant_knowledge_updates_hit_count_when_touched(self):
        l8_learn.save_learned_knowledge(
            "FastAPI 是什么？",
            "FastAPI：现代 Python Web 框架。",
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

    def test_auto_learn_writes_knowledge_entry_from_search_results(self):
        mock_results = [
            {
                "title": "FastAPI 是什么",
                "snippet": "FastAPI 是什么？FastAPI 是用于构建 API 的现代 Python Web 框架。",
                "url": "https://fastapi.tiangolo.com/",
            },
            {
                "title": "FastAPI 教程",
                "snippet": "FastAPI 是什么：一个提供类型提示驱动的开发体验的框架。",
                "url": "https://example.com/fastapi-tutorial",
            },
        ]

        def fake_llm(prompt):
            if "关键词" in prompt:
                return "FastAPI, Python, Web框架"
            if "提炼" in prompt or "查询词" in prompt:
                return "FastAPI 是什么"
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

    def test_auto_learn_skips_search_when_query_is_already_known(self):
        l8_learn.save_learned_knowledge(
            "FastAPI 是什么？",
            "FastAPI：现代 Python Web 框架。",
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
                        "summary": "FastAPI 是一个高性能 Python Web 框架。",
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
