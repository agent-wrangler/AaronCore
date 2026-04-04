import unittest
from datetime import datetime
from unittest.mock import patch

from memory import history_recall


class HistoryRecallTests(unittest.TestCase):
    def test_format_topic_list_uses_l2_snippets_not_keywords(self):
        user_msgs = [
            {"content": "我们今天讨论了 MCP 协议怎么接工具", "dt": datetime(2026, 3, 29, 10, 0, 0)},
        ]
        l2_entries = [
            {
                "user_text": "mcp protocol",
                "keywords": [],
            }
        ]

        result = history_recall._format_topic_list(user_msgs, l2_entries, "今天")

        self.assertIn("相关记忆", result)
        self.assertIn("mcp protocol", result)
        self.assertNotIn("核心话题", result)

    def test_fallback_extract_uses_l2_snippets_not_keyword_list(self):
        user_msgs = [
            {"content": "先修复 MCP 连接问题"},
            {"content": "然后再看工具调用"},
        ]
        l2_entries = [
            {
                "user_text": "mcp protocol",
                "keywords": [],
            }
        ]

        result = history_recall._fallback_extract(user_msgs, l2_entries, "今天")

        self.assertIn("相关记忆", result)
        self.assertIn("mcp protocol", result)
        self.assertIn("用户提到过", result)
        self.assertNotIn("核心话题", result)

    def test_detect_recall_intent_uses_llm_yes_no_instead_of_recall_words(self):
        with patch.object(history_recall, "_llm_call", return_value="YES"):
            result = history_recall.detect_recall_intent("今天我们之前都讨论了什么")

        self.assertIsNotNone(result)
        self.assertTrue(result["is_recall"])

    def test_detect_recall_intent_rejects_non_recall_time_queries(self):
        with patch.object(history_recall, "_llm_call", return_value="NO"):
            result = history_recall.detect_recall_intent("今天上海天气怎么样")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
