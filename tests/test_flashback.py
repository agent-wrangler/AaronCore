import unittest
from unittest.mock import patch

import memory.flashback as flashback


class FlashbackTests(unittest.TestCase):
    def test_detect_flashback_uses_recent_l2_for_status_follow_up(self):
        query = "修好了？"
        l2_items = [
            {
                "user_text": "修好了？",
                "ai_text": "我再检查一下当前修复结果。",
                "created_at": "2026-03-29T10:00:00",
                "memory_type": "general",
                "importance": 0.5,
                "hit_count": 6,
                "crystallized": False,
                "relevance": 1.0,
                "final_score": 0.95,
            }
        ]

        with patch.object(flashback, "_load_l3", return_value=[]), patch.object(flashback, "_load_l2_recent", return_value=l2_items):
            hint = flashback.detect_flashback(query)

        self.assertIsNotNone(hint)
        self.assertIn("修好了？", hint)

    def test_detect_flashback_prefers_task_continuity_l2_match(self):
        query = "还是没成功。是哪里的设置问题"
        l2_items = [
            {
                "user_text": "还是没成功。是哪里的设置问题",
                "ai_text": "我们继续排查设置问题。",
                "created_at": "2026-03-29T10:00:00",
                "memory_type": "general",
                "importance": 0.5,
                "hit_count": 0,
                "crystallized": False,
                "relevance": 1.0,
                "final_score": 0.88,
            },
            {
                "user_text": "今天天气",
                "ai_text": "我来查一下天气。",
                "created_at": "2026-03-29T09:00:00",
                "memory_type": "general",
                "importance": 0.4,
                "hit_count": 0,
                "crystallized": False,
                "relevance": 0.1,
                "final_score": 0.2,
            },
        ]

        with patch.object(flashback, "_load_l3", return_value=[]), patch.object(flashback, "_load_l2_recent", return_value=l2_items):
            hint = flashback.detect_flashback(query)

        self.assertIsNotNone(hint)
        self.assertIn("设置问题", hint)

    def test_detect_flashback_can_use_search_backstop_for_strong_repair_followups(self):
        query = "修好了？"
        backstop_items = [
            {
                "user_text": "修好了？",
                "ai_text": "我再检查一下当前修复结果。",
                "created_at": "2026-03-22T10:00:00",
                "memory_type": "general",
                "importance": 0.5,
                "hit_count": 2,
                "crystallized": False,
                "relevance": 1.0,
                "final_score": 0.95,
            }
        ]

        with patch.object(flashback, "_load_l3", return_value=[]), patch.object(
            flashback, "_load_l2_recent", return_value=[]
        ), patch.object(flashback, "_search_l2_backstop", return_value=backstop_items):
            hint = flashback.detect_flashback(query)

        self.assertIsNotNone(hint)
        self.assertIn("修好了？", hint)

    def test_detect_flashback_can_use_l3_when_emotion_matches(self):
        query = "今天好累"
        l3_items = [
            {
                "event": "之前你也说过连续开发很累，想先放松一下。",
                "created_at": "2026-03-20T10:00:00",
                "source": "l2_crystallize",
            }
        ]

        with patch.object(flashback, "_load_l3", return_value=l3_items), patch.object(flashback, "_load_l2_recent", return_value=[]):
            hint = flashback.detect_flashback(query)

        self.assertIsNotNone(hint)
        self.assertIn("连续开发很累", hint)

    def test_detect_flashback_skips_low_signal_l2_candidates(self):
        query = "今天好累"
        l2_items = [
            {
                "user_text": "好",
                "ai_text": "",
                "created_at": "2026-03-29T10:00:00",
                "memory_type": "general",
                "importance": 0.4,
                "hit_count": 2,
                "crystallized": False,
                "relevance": 0.8,
                "final_score": 0.8,
            }
        ]
        l3_items = [
            {
                "event": "之前你也说过连续开发很累，想先放松一下。",
                "created_at": "2026-03-20T10:00:00",
                "source": "l2_crystallize",
            }
        ]

        with patch.object(flashback, "_load_l3", return_value=l3_items), patch.object(flashback, "_load_l2_recent", return_value=l2_items):
            hint = flashback.detect_flashback(query)

        self.assertIsNotNone(hint)
        self.assertIn("连续开发很累", hint)

    def test_detect_flashback_skips_plain_non_cue_queries(self):
        with patch.object(flashback, "_load_l3", return_value=[]), patch.object(flashback, "_load_l2_recent", return_value=[]):
            hint = flashback.detect_flashback("今天天气")

        self.assertIsNone(hint)


if __name__ == "__main__":
    unittest.main()
