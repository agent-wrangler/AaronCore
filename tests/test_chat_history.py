import unittest

from routes.chat_history import ChatHistoryTransaction


class ChatHistoryTransactionTests(unittest.TestCase):
    def test_append_pending_user_persists_history_and_tracks_entry(self):
        saved = []
        history = []
        tx = ChatHistoryTransaction(
            history,
            save_msg_history=lambda items: saved.append([dict(item) for item in items]),
        )

        entry = tx.append_pending_user("hello")

        self.assertEqual(entry["role"], "user")
        self.assertEqual(history[-1]["content"], "hello")
        self.assertEqual(tx.pending_user_entry, entry)
        self.assertEqual(saved[-1][-1]["content"], "hello")

    def test_append_pending_user_persists_attachments(self):
        saved = []
        history = []
        tx = ChatHistoryTransaction(
            history,
            save_msg_history=lambda items: saved.append([dict(item) for item in items]),
        )

        entry = tx.append_pending_user(
            "hello",
            attachments=[{"type": "image", "path": "20260417/test.png", "mime": "image/png"}],
        )

        self.assertEqual(entry["attachments"][0]["path"], "20260417/test.png")
        self.assertEqual(saved[-1][-1]["attachments"][0]["mime"], "image/png")

    def test_persist_assistant_entry_marks_transaction_saved(self):
        history = []
        saved = []
        remembered = []
        tx = ChatHistoryTransaction(
            history,
            save_msg_history=lambda items: saved.append([dict(item) for item in items]),
            add_to_history=lambda role, text: remembered.append((role, text)),
        )

        ok = tx.persist_assistant_entry("nova", "done")

        self.assertTrue(ok)
        self.assertTrue(tx.assistant_history_saved)
        self.assertEqual(history[-1]["role"], "nova")
        self.assertEqual(remembered, [("nova", "done")])

    def test_persist_assistant_entry_skips_transient_model_error_notice(self):
        history = []
        saved = []
        remembered = []
        tx = ChatHistoryTransaction(
            history,
            save_msg_history=lambda items: saved.append([dict(item) for item in items]),
            add_to_history=lambda role, text: remembered.append((role, text)),
        )

        ok = tx.persist_assistant_entry(
            "nova",
            "当前模型接口余额不足，暂时无法继续。请充值后重试，或先切换到其他模型。",
        )

        self.assertFalse(ok)
        self.assertFalse(tx.assistant_history_saved)
        self.assertEqual(history, [])
        self.assertEqual(saved, [])
        self.assertEqual(remembered, [])

    def test_rollback_pending_user_only_removes_orphan_user_turn(self):
        saved = []
        history = []
        tx = ChatHistoryTransaction(
            history,
            save_msg_history=lambda items: saved.append([dict(item) for item in items]),
        )
        tx.append_pending_user("hello")

        removed = tx.rollback_pending_user("fatal")

        self.assertTrue(removed)
        self.assertEqual(history, [])
        self.assertEqual(saved[-1], [])

    def test_rollback_cleans_up_pending_attachments(self):
        deleted = []
        history = []
        tx = ChatHistoryTransaction(
            history,
            save_msg_history=lambda _items: None,
            delete_attachments=lambda attachments: deleted.extend(list(attachments or [])),
        )
        tx.append_pending_user(
            "hello",
            attachments=[{"type": "image", "path": "20260417/test.png", "mime": "image/png"}],
        )

        removed = tx.rollback_pending_user("fatal")

        self.assertTrue(removed)
        self.assertEqual(deleted, [{"type": "image", "path": "20260417/test.png", "mime": "image/png"}])

    def test_rollback_skips_when_assistant_history_already_saved(self):
        history = []
        tx = ChatHistoryTransaction(
            history,
            save_msg_history=lambda _items: None,
        )
        tx.append_pending_user("hello")
        tx.persist_assistant_entry("nova", "done")

        removed = tx.rollback_pending_user("fatal")

        self.assertFalse(removed)
        self.assertEqual(len(history), 2)


if __name__ == "__main__":
    unittest.main()
