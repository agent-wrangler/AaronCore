import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from memory import l2_memory


class L2MemoryTests(unittest.TestCase):
    def test_detect_type_no_longer_uses_skill_demand(self):
        detected = l2_memory._detect_type("可以帮我配置模型吗")

        self.assertNotEqual(detected, "skill_demand")

    def test_classify_retention_bucket_distinguishes_keep_compress_and_prune(self):
        now = datetime(2026, 3, 30, 12, 0, 0)

        keep_entry = {
            "memory_type": "rule",
            "importance": 0.92,
            "hit_count": 0,
            "crystallized": False,
            "created_at": "2026-03-10T10:00:00",
        }
        compress_entry = {
            "memory_type": "fact",
            "importance": 0.88,
            "hit_count": 0,
            "crystallized": True,
            "created_at": "2026-03-12T10:00:00",
        }
        prune_entry = {
            "memory_type": "general",
            "importance": 0.4,
            "hit_count": 0,
            "crystallized": False,
            "created_at": "2025-12-01T10:00:00",
        }

        keep = l2_memory.classify_retention_bucket(keep_entry, now=now)
        compress = l2_memory.classify_retention_bucket(compress_entry, now=now)
        prune = l2_memory.classify_retention_bucket(prune_entry, now=now)

        self.assertEqual(keep["tier"], "keep")
        self.assertEqual(keep["label"], "永保类")
        self.assertEqual(compress["tier"], "compress")
        self.assertEqual(compress["label"], "压缩类")
        self.assertEqual(prune["tier"], "prune")
        self.assertEqual(prune["label"], "淘汰候选")

    def test_classify_retention_bucket_keeps_only_active_or_highly_reused_general_context(self):
        now = datetime(2026, 3, 30, 12, 0, 0)

        lightly_reused_general = {
            "memory_type": "general",
            "user_text": "修好了？",
            "importance": 0.5,
            "hit_count": 1,
            "crystallized": False,
            "created_at": "2026-03-25T10:00:00",
        }
        active_general = {
            "memory_type": "general",
            "user_text": "还是没成功。是哪里的设置问题",
            "importance": 0.5,
            "hit_count": 0,
            "crystallized": False,
            "created_at": "2026-03-29T10:00:00",
        }
        low_signal_general = {
            "memory_type": "general",
            "user_text": "越来越聪明了",
            "importance": 0.5,
            "hit_count": 0,
            "crystallized": False,
            "created_at": "2026-03-29T10:00:00",
        }
        high_reuse_general = {
            "memory_type": "general",
            "user_text": "时间线：1. 你在跑的 Nova 还是旧代码 2. self_fix 卡住了",
            "importance": 0.5,
            "hit_count": 6,
            "crystallized": False,
            "created_at": "2026-03-24T10:00:00",
        }

        lightly_reused = l2_memory.classify_retention_bucket(lightly_reused_general, now=now)
        active = l2_memory.classify_retention_bucket(active_general, now=now)
        low_signal = l2_memory.classify_retention_bucket(low_signal_general, now=now)
        high_reuse = l2_memory.classify_retention_bucket(high_reuse_general, now=now)

        self.assertEqual(lightly_reused["tier"], "compress")
        self.assertEqual(active["tier"], "keep")
        self.assertEqual(low_signal["tier"], "compress")
        self.assertEqual(high_reuse["tier"], "keep")

    def test_classify_retention_bucket_keeps_recent_crystallized_general_context_when_reused(self):
        now = datetime(2026, 3, 30, 12, 0, 0)

        crystallized_general = {
            "memory_type": "general",
            "user_text": "停止监听",
            "importance": 0.85,
            "hit_count": 3,
            "crystallized": True,
            "created_at": "2026-03-29T10:20:00",
        }

        result = l2_memory.classify_retention_bucket(crystallized_general, now=now)

        self.assertEqual(result["tier"], "keep")

    def test_cleanup_stale_memories_only_removes_prune_candidates(self):
        now = datetime(2026, 3, 30, 12, 0, 0)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            l2_file = tmp / "l2_short_term.json"
            l2_file.write_text(
                json.dumps(
                    [
                        {
                            "id": "keep_rule",
                            "user_text": "你必须调用工具",
                            "importance": 0.9,
                            "memory_type": "rule",
                            "created_at": "2026-03-05T10:00:00",
                            "hit_count": 0,
                            "crystallized": False,
                        },
                        {
                            "id": "compress_fact",
                            "user_text": "我在常州",
                            "importance": 0.88,
                            "memory_type": "fact",
                            "created_at": "2026-03-06T10:00:00",
                            "hit_count": 0,
                            "crystallized": True,
                        },
                        {
                            "id": "prune_general",
                            "user_text": "今天天气",
                            "importance": 0.4,
                            "memory_type": "general",
                            "created_at": "2025-12-01T10:00:00",
                            "hit_count": 0,
                            "crystallized": False,
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(l2_memory, "L2_FILE", l2_file):
                result = l2_memory.cleanup_stale_memories(now=now)

            kept = json.loads(l2_file.read_text(encoding="utf-8"))
            kept_ids = {item["id"] for item in kept}

            self.assertEqual(result["removed"], 1)
            self.assertEqual(result["retention_counts"]["keep"], 1)
            self.assertEqual(result["retention_counts"]["compress"], 1)
            self.assertEqual(result["retention_counts"]["prune"], 1)
            self.assertEqual(kept_ids, {"keep_rule", "compress_fact"})

    def test_search_relevant_requires_positive_relevance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            l2_file = tmp / "l2_short_term.json"
            l2_file.write_text(
                json.dumps(
                    [
                        {
                            "id": "weather_1",
                            "user_text": "今天天气",
                            "ai_text": "我来查一下。",
                            "importance": 0.4,
                            "memory_type": "general",
                            "keywords": ["天气"],
                            "created_at": "2026-03-29T10:00:00",
                            "hit_count": 0,
                            "crystallized": False,
                        },
                        {
                            "id": "browser_1",
                            "user_text": "打开百度",
                            "ai_text": "我来打开百度。",
                            "importance": 0.4,
                            "memory_type": "general",
                            "keywords": ["百度"],
                            "created_at": "2026-03-29T10:05:00",
                            "hit_count": 0,
                            "crystallized": False,
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(l2_memory, "L2_FILE", l2_file):
                nonsense = l2_memory.search_relevant("zzzzzzzzzz", limit=8)
                matched = l2_memory.search_relevant("今天天气", limit=8)

            self.assertEqual(nonsense, [])
            self.assertEqual(len(matched), 1)
            self.assertEqual(matched[0]["id"], "weather_1")

    def test_search_relevant_skips_low_signal_general_and_reduces_same_topic_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            l2_file = tmp / "l2_short_term.json"
            l2_file.write_text(
                json.dumps(
                    [
                        {
                            "id": "repair_exact",
                            "user_text": "修好了？",
                            "ai_text": "我再检查一下修复状态。",
                            "importance": 0.5,
                            "memory_type": "general",
                            "keywords": ["修好了"],
                            "created_at": "2026-03-29T10:00:00",
                            "hit_count": 3,
                            "crystallized": False,
                        },
                        {
                            "id": "repair_variant",
                            "user_text": "修好了吗",
                            "ai_text": "继续确认这次修复有没有真的完成。",
                            "importance": 0.5,
                            "memory_type": "general",
                            "keywords": ["修好"],
                            "created_at": "2026-03-29T09:55:00",
                            "hit_count": 2,
                            "crystallized": False,
                        },
                        {
                            "id": "low_signal",
                            "user_text": "好",
                            "ai_text": "收到。",
                            "importance": 0.5,
                            "memory_type": "general",
                            "keywords": ["好"],
                            "created_at": "2026-03-29T10:05:00",
                            "hit_count": 8,
                            "crystallized": False,
                        },
                        {
                            "id": "other_topic",
                            "user_text": "打开百度",
                            "ai_text": "我来打开百度。",
                            "importance": 0.5,
                            "memory_type": "general",
                            "keywords": ["百度"],
                            "created_at": "2026-03-29T10:06:00",
                            "hit_count": 0,
                            "crystallized": False,
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(l2_memory, "L2_FILE", l2_file):
                matched = l2_memory.search_relevant("修好了？", limit=5)

            ids = [item["id"] for item in matched]
            self.assertIn("repair_exact", ids)
            self.assertNotIn("low_signal", ids)
            self.assertEqual(len([item_id for item_id in ids if item_id.startswith("repair_")]), 1)

    def test_prune_legacy_l2_demands_from_l5_backs_up_and_removes_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            knowledge_file = tmp / "knowledge.json"
            knowledge_file.write_text(
                json.dumps(
                    [
                        {
                            "name": "open_target",
                            "source": "l6_success_path",
                            "summary": "先定位窗口，再打开目标目录",
                        },
                        {
                            "source": "l2_demand",
                            "trigger": ["可以帮我配置模型吗"],
                            "demand_count": 1,
                            "status": "unmet",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(l2_memory, "L5_FILE", knowledge_file):
                result = l2_memory.prune_legacy_l2_demands_from_l5(reason="test_cleanup")

            stored = json.loads(knowledge_file.read_text(encoding="utf-8"))
            backups = list(tmp.glob("knowledge.backup_*.json"))

            self.assertTrue(result["success"])
            self.assertEqual(result["reason"], "test_cleanup")
            self.assertEqual(result["removed_count"], 1)
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0]["source"], "l6_success_path")
            self.assertEqual(len(backups), 1)


if __name__ == "__main__":
    unittest.main()
