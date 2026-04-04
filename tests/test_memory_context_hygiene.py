import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory import l2_memory
from storage import state_loader


class MemoryContextHygieneTests(unittest.TestCase):
    def test_add_memory_skips_corrupted_turn(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            l2_file = tmp / "l2_short_term.json"
            cfg_file = tmp / "l2_config.json"
            l2_file.write_text("[]", encoding="utf-8")
            cfg_file.write_text(
                json.dumps({"total_rounds": 0, "last_summary_round": 0, "total_summaries": 0}),
                encoding="utf-8",
            )

            with patch.object(l2_memory, "L2_FILE", l2_file), patch.object(l2_memory, "L2_CFG", cfg_file):
                result = l2_memory.add_memory(
                    "??????????,?????:ok",
                    "这样整理后结构会清晰很多。Computer Use 技能支持：在QQ群发消息。",
                )

            self.assertIsNone(result)
            self.assertEqual(json.loads(l2_file.read_text(encoding="utf-8")), [])

    def test_add_memory_strips_think_block_before_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            l2_file = tmp / "l2_short_term.json"
            cfg_file = tmp / "l2_config.json"
            l2_file.write_text("[]", encoding="utf-8")
            cfg_file.write_text(
                json.dumps({"total_rounds": 0, "last_summary_round": 0, "total_summaries": 0}),
                encoding="utf-8",
            )

            meta = {
                "importance": 0.82,
                "memory_type": "general",
                "knowledge_query": False,
                "context_tag": "日常",
            }

            with patch.object(l2_memory, "L2_FILE", l2_file), patch.object(
                l2_memory, "L2_CFG", cfg_file
            ), patch.object(l2_memory, "_infer_memory_meta", return_value=meta), patch.object(
                l2_memory.threading, "Thread"
            ) as thread_mock, patch.object(
                l2_memory, "_auto_summary"
            ):
                thread_mock.return_value.start.return_value = None
                result = l2_memory.add_memory(
                    "查查今天新闻热点",
                    "<think>先判断该不该调用工具</think>\n好嘛主人～我去给你抓今天的新闻热点。",
                )

            stored = json.loads(l2_file.read_text(encoding="utf-8"))
            self.assertIsNotNone(result)
            self.assertEqual(len(stored), 1)
            self.assertNotIn("<think>", stored[0]["ai_text"])
            self.assertIn("今天的新闻热点", stored[0]["ai_text"])

    def test_load_l3_long_term_skips_internal_think_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            long_term_file = tmp / "long_term.json"
            long_term_file.write_text(
                json.dumps(
                    [
                        {
                            "event": "<think>根据对话上下文，作为AI助手，我来总结</think>",
                            "type": "event",
                            "source": "l2_auto_summary",
                        },
                        {
                            "event": "用户强调了 memory=代码，state_data=数据总仓 这个边界。",
                            "type": "event",
                            "source": "l2_auto_summary",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(state_loader, "LONG_TERM_FILE", long_term_file), patch.object(
                state_loader, "_LONG_TERM_CLEANUP_DONE", False
            ):
                loaded = state_loader.load_l3_long_term(limit=8)

        self.assertEqual(loaded, ["用户强调了 memory=代码，state_data=数据总仓 这个边界。"])


if __name__ == "__main__":
    unittest.main()
