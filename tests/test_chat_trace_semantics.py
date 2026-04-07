import unittest

from routes.chat_trace_semantics import (
    build_direct_reply_reason_note,
    build_expected_output,
    build_next_user_need,
    build_tool_reason_note,
    prefer_reason_note_for_tool,
)


class ChatTraceSemanticsTests(unittest.TestCase):
    def test_build_expected_output_and_next_user_need_cover_thinking_and_weather(self):
        thinking_expected = build_expected_output(phase="thinking")
        self.assertIn("\u5de5\u5177", thinking_expected)

        expected = build_expected_output(phase="tool", tool_name="weather", preview="\u4e0a\u6d77")
        self.assertIn("\u5929\u6c14", expected)
        self.assertEqual(
            build_next_user_need(
                user_message="\u4eca\u5929\u51fa\u95e8\u8981\u5e26\u4f1e\u5417",
                tool_name="weather",
                preview="\u4e0a\u6d77\u5929\u6c14",
                expected_output=expected,
            ),
            "\u4eca\u5929\u72b6\u6001\u3001\u51fa\u95e8\u5b89\u6392\u6216\u8981\u4e0d\u8981\u5e26\u4f1e",
        )

    def test_build_direct_reply_reason_note_distinguishes_context_presence(self):
        with_context = build_direct_reply_reason_note(has_context=True)
        without_context = build_direct_reply_reason_note(has_context=False)

        self.assertTrue(with_context)
        self.assertTrue(without_context)
        self.assertNotEqual(with_context, without_context)
        self.assertIn("直接回应", with_context)
        self.assertIn("直接回应", without_context)
        self.assertNotIn("杩", with_context)
        self.assertNotIn("杩", without_context)

    def test_build_tool_reason_note_prefers_preview_and_display_name(self):
        note = build_tool_reason_note("search_text", "router.py TODO", "Search Text")
        self.assertIn("Search Text", note)
        self.assertIn("router.py TODO", note)
        self.assertIn("继续回答", note)

    def test_prefer_reason_note_for_tool_replaces_toolish_or_default_text(self):
        reason = "\u6211\u5148\u6838\u5b9e\u8fd9\u4e00\u6b65\u9700\u8981\u7684\u4fe1\u606f\uff0c\u518d\u7ee7\u7eed\u56de\u7b54\u3002"
        self.assertEqual(
            prefer_reason_note_for_tool(
                "search_text / found 3 matches",
                tool_name="search_text",
                preview="TODO",
                reason_note=reason,
                action_summary="found 3 matches",
                default_think_detail="\u5148\u60f3\u4e00\u4e0b",
            ),
            reason,
        )
        self.assertEqual(
            prefer_reason_note_for_tool(
                "\u5148\u60f3\u4e00\u4e0b",
                tool_name="search_text",
                preview="TODO",
                reason_note=reason,
                default_think_detail="\u5148\u60f3\u4e00\u4e0b",
            ),
            reason,
        )
        kept_text = (
            "I will first review the task order, then decide whether any tools are needed, "
            "and only after that give the final answer."
        )
        kept = prefer_reason_note_for_tool(
            kept_text,
            tool_name="search_text",
            preview="TODO",
            reason_note=reason,
            action_summary="found 3 matches",
            default_think_detail="\u5148\u60f3\u4e00\u4e0b",
        )
        self.assertEqual(kept, kept_text)


if __name__ == "__main__":
    unittest.main()
