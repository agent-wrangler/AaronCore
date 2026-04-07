import unittest

from routes.chat_reply_closeout import (
    classify_missing_tool_execution,
    clean_reply_for_user,
    finalize_tool_call_reply,
    prepare_reply_for_user,
)
from routes.chat_stream_helpers import ensure_tool_call_failure_reply


class ChatReplyCloseoutTests(unittest.TestCase):
    def test_clean_reply_for_user_removes_think_markup(self):
        cleaned = clean_reply_for_user(
            "<think>\u5148\u5206\u6790</think>\u6700\u7ec8\u7b54\u6848",
            strip_markdown=lambda text: text,
        )
        self.assertEqual(cleaned, "\u6700\u7ec8\u7b54\u6848")

    def test_finalize_tool_call_reply_replaces_tool_preamble_with_closeout(self):
        result = finalize_tool_call_reply(
            "\u6211\u5148\u53bb\u770b\u770b\u5f53\u524d\u73af\u5883\u3002",
            history=[],
            strip_markdown=lambda text: text,
            ensure_tool_call_failure_reply=ensure_tool_call_failure_reply,
            tool_used="sense_environment",
            tool_success=True,
            tool_response="\u73af\u5883\u5df2\u8bfb\u53d6\u5b8c\u6210",
            action_summary="\u5df2\u8bfb\u53d6\u5f53\u524d\u73af\u5883",
            run_meta={},
            stream_had_output=True,
        )
        self.assertIn("\u5df2\u8bfb\u53d6\u5f53\u524d\u73af\u5883", result)
        self.assertNotEqual(result.strip(), "\u6211\u5148\u53bb\u770b\u770b\u5f53\u524d\u73af\u5883\u3002")

    def test_finalize_tool_call_reply_converts_orphan_preamble_to_failure_closeout(self):
        orphan_preamble = "\u597d\u7684\uff0c\u6211\u8fd9\u5c31\u53bbQQ\u7fa4\u91cc\u770b\u770b\u3002"
        result = finalize_tool_call_reply(
            orphan_preamble,
            history=[],
            strip_markdown=lambda text: text,
            ensure_tool_call_failure_reply=ensure_tool_call_failure_reply,
            tool_used="",
            tool_success=None,
            tool_response="\u8fd9\u4e00\u8f6e\u4e2d\u65ad\u4e86\uff0c\u6ca1\u62ff\u5230\u5b8c\u6574\u7ed3\u679c",
            action_summary="",
            run_meta={},
            stream_had_output=True,
        )
        self.assertIn("\u8fd9\u4e00\u8f6e\u4e2d\u65ad\u4e86", result)
        self.assertNotEqual(result.strip(), orphan_preamble)

    def test_classify_missing_tool_execution_marks_orphan_preamble(self):
        result = classify_missing_tool_execution(
            "\u597d\u7684\uff0c\u6211\u8fd9\u5c31\u53bbQQ\u7fa4\u91cc\u770b\u770b\u3002",
            tool_used="",
            stream_had_output=True,
        )

        self.assertEqual(result.get("reason"), "preamble_without_tool")
        self.assertTrue(result.get("summary"))

    def test_classify_missing_tool_execution_marks_local_inspection_claim(self):
        local_claim = (
            "\u597d\u7684\uff0c\u6211\u518d\u53bb L4 \u770b\u770b\u8fd8\u6709\u4ec0\u4e48\u5185\u5bb9\u3002"
            "\u6211\u4ed4\u7ec6\u67e5\u770b\u4e86 L4 \u76f8\u5173\u7684\u6587\u4ef6\uff0c"
            "\u5728 `persona.json` \u91cc\u770b\u5230\u4e86\u5b8c\u6574\u7684\u4eba\u683c\u5217\u8868\u3002"
        )
        result = classify_missing_tool_execution(
            local_claim,
            tool_used="",
            stream_had_output=True,
        )

        self.assertEqual(result.get("reason"), "local_inspection_without_tool")
        self.assertIn("read/list tool result", result.get("summary", ""))

    def test_prepare_reply_for_user_runs_cleaning_pipeline(self):
        result = prepare_reply_for_user(
            "<think>\u5148\u5206\u6790</think>\u4fdd\u7559\u8fd9\u53e5",
            [],
            strip_markdown=lambda text: text,
        )
        self.assertEqual(result, "\u4fdd\u7559\u8fd9\u53e5")


if __name__ == "__main__":
    unittest.main()
