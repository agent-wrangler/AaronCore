import unittest

import core.reply_formatter as reply_formatter_module
from core.runtime_state import state_loader as state_loader_module


class RecentMessagesTests(unittest.TestCase):
    def test_get_recent_messages_returns_last_n_without_budget(self):
        history = [{"role": "user", "content": f"msg-{idx}"} for idx in range(6)]

        recent = state_loader_module.get_recent_messages(history, limit=4)

        self.assertEqual([item["content"] for item in recent], ["msg-2", "msg-3", "msg-4", "msg-5"])

    def test_get_recent_messages_respects_token_budget(self):
        history = [
            {"role": "user", "content": "你" * 120},
            {"role": "assistant", "content": "你" * 120},
            {"role": "user", "content": "你" * 120},
        ]

        recent = state_loader_module.get_recent_messages(history, limit=6, max_tokens=150)

        self.assertEqual(recent, [history[-1]])

    def test_get_recent_messages_keeps_latest_item_even_if_it_exceeds_budget(self):
        history = [
            {"role": "user", "content": "ok"},
            {"role": "assistant", "content": "你" * 300},
        ]

        recent = state_loader_module.get_recent_messages(history, limit=6, max_tokens=50)

        self.assertEqual(recent, [history[-1]])

    def test_get_recent_messages_can_use_budget_without_turn_cap(self):
        history = [{"role": "user" if idx % 2 == 0 else "assistant", "content": "a" * 40} for idx in range(12)]

        recent = state_loader_module.get_recent_messages(history, limit=None, max_tokens=60)

        self.assertLess(len(recent), len(history))
        self.assertEqual(recent[-1], history[-1])

    def test_get_recent_messages_with_budget_can_keep_more_than_six_messages(self):
        history = [{"role": "user" if idx % 2 == 0 else "assistant", "content": "a" * 40} for idx in range(12)]

        recent = state_loader_module.get_recent_messages(history, limit=None, max_tokens=400)

        self.assertEqual(len(recent), len(history))
        self.assertGreater(len(recent), 6)
        self.assertEqual(recent[0], history[0])
        self.assertEqual(recent[-1], history[-1])

    def test_build_l1_messages_uses_all_budget_trimmed_history_by_default(self):
        history = []
        for idx in range(25):
            history.append({"role": "user", "content": f"user-{idx}"})
            history.append({"role": "assistant", "content": f"assistant-{idx}"})

        messages = reply_formatter_module._build_l1_messages({"l1": history, "user_input": "new-input"})

        self.assertEqual(len(messages), 50)
        self.assertEqual(messages[0]["content"], "user-0")
        self.assertEqual(messages[-1]["content"], "assistant-24")


if __name__ == "__main__":
    unittest.main()
