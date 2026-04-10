import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from storage import history_store


class HistoryStoreTests(unittest.TestCase):
    def test_load_msg_history_prunes_transient_model_error_notices(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            primary = Path(tmp_dir) / "msg_history.json"
            legacy = Path(tmp_dir) / "legacy_msg_history.json"
            now = datetime.now().isoformat()
            payload = [
                {"role": "user", "content": "hello", "time": now},
                {
                    "role": "nova",
                    "content": "当前模型接口余额不足，暂时无法继续。请充值后重试，或先切换到其他模型。",
                    "time": now,
                },
                {"role": "assistant", "content": "pong", "time": now},
            ]
            primary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            original_primary = history_store.PRIMARY_HISTORY_FILE
            original_legacy = history_store.LEGACY_HISTORY_FILE
            history_store.PRIMARY_HISTORY_FILE = primary
            history_store.LEGACY_HISTORY_FILE = legacy
            try:
                loaded = history_store.load_msg_history()
            finally:
                history_store.PRIMARY_HISTORY_FILE = original_primary
                history_store.LEGACY_HISTORY_FILE = original_legacy

            self.assertEqual(
                loaded,
                [
                    {"role": "user", "content": "hello", "time": now},
                    {"role": "assistant", "content": "pong", "time": now},
                ],
            )
            rewritten = json.loads(primary.read_text(encoding="utf-8"))
            self.assertEqual(rewritten, loaded)

    def test_is_transient_assistant_notice_matches_english_model_errors(self):
        item = {
            "role": "nova",
            "content": "Current model API balance is insufficient. Unable to continue for now. Please top up and try again, or switch to another model first.",
        }

        self.assertTrue(history_store.is_transient_assistant_notice(item))

    def test_is_transient_assistant_notice_matches_missing_execution_closeout(self):
        item = {
            "role": "nova",
            "content": (
                "主人，刚才那个说桌面没有临时文档文件夹的回复不可靠，我并没有实际完成检查操作。😅\n\n"
                "我需要重新执行真实的检查，看看临时文档文件夹到底还在不在。\n\n"
                "让我重新检查一下！😊"
            ),
        }

        self.assertTrue(history_store.is_transient_assistant_notice(item))

    def test_is_transient_assistant_notice_matches_missing_execution_closeout_with_chatter_prefix(self):
        item = {
            "role": "nova",
            "content": (
                "你是神，你无所不能！\n\n"
                "这一轮我还没有实际调用读取文件或目录的工具，所以不能直接说我已经看过本地内容。"
                "刚才那段带本地文件或目录结论的答复不可靠。\n\n"
                "如果要确认具体的本地文件、目录、代码或配置内容，我需要先真实读取相关目标，再回来给你总结。"
            ),
        }

        self.assertTrue(history_store.is_transient_assistant_notice(item))

    def test_get_recent_messages_ignores_missing_execution_closeout(self):
        now = datetime.now().isoformat()
        history = [
            {"role": "user", "content": "别说了", "time": now},
            {
                "role": "nova",
                "content": (
                    "刚才那段带本地文件或目录结论的答复不可靠。\n\n"
                    "如果要确认具体的本地文件、目录、代码或配置内容，我需要先真实读取相关目标，再回来给你总结。"
                ),
                "time": now,
            },
            {"role": "assistant", "content": "好的，那我们继续聊别的。", "time": now},
        ]

        recent = history_store.get_recent_messages(history, limit=6)

        self.assertEqual(len(recent), 2)
        self.assertEqual(recent[0]["content"], "别说了")
        self.assertEqual(recent[1]["content"], "好的，那我们继续聊别的。")


if __name__ == "__main__":
    unittest.main()
