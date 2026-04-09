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


if __name__ == "__main__":
    unittest.main()
