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

    def test_classify_missing_tool_execution_ignores_preamble_on_non_action_followup(self):
        result = classify_missing_tool_execution(
            "\u597d\u7684\u4e3b\u4eba\uff0c\u540e\u9762\u5982\u679c\u8fd8\u9700\u8981\u4e34\u65f6\u5b58\u653e\u6587\u6863\uff0c\u6211\u4e5f\u53ef\u4ee5\u5e2e\u4f60\u65b0\u5efa\u4e00\u4e2a\u6587\u4ef6\u5939\u3002",
            user_input="\u4e0d\u7528\u4e86 \u5220\u5c31\u5220\u4e86 \u6211\u56de\u6536\u7ad9\u4e5f\u6ca1\u627e\u5230",
            tool_used="",
            stream_had_output=True,
        )

        self.assertEqual(result, {})

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

    def test_classify_missing_tool_execution_ignores_forward_recheck_plan(self):
        recovery_reply = (
            "\u4e3b\u4eba\u8bf4\u5f97\u5bf9\uff0c\u6211\u786e\u5b9e\u81ea\u76f8\u77db\u76fe\u4e86\u3002"
            "\u73b0\u5728\u6211\u6765\u91cd\u65b0\u6267\u884c\uff0c"
            "\u5148\u771f\u5b9e\u68c0\u67e5\u684c\u9762\u4e34\u65f6\u6587\u6863\u6587\u4ef6\u5939\u7684\u60c5\u51b5\uff0c"
            "\u7136\u540e\u518d\u6839\u636e\u5b9e\u9645\u60c5\u51b5\u64cd\u4f5c\u3002"
        )
        result = classify_missing_tool_execution(
            recovery_reply,
            history=[],
            user_input="\u4f60\u6709\u70b9\u81ea\u76f8\u77db\u76fe \u54c8\u54c8",
            tool_used="",
            stream_had_output=True,
        )

        self.assertEqual(result, {})

    def test_finalize_tool_call_reply_preserves_forward_recheck_plan(self):
        recovery_reply = (
            "\u4e3b\u4eba\u8bf4\u5f97\u5bf9\uff0c\u6211\u786e\u5b9e\u81ea\u76f8\u77db\u76fe\u4e86\u3002"
            "\u73b0\u5728\u6211\u6765\u91cd\u65b0\u6267\u884c\uff0c"
            "\u5148\u771f\u5b9e\u68c0\u67e5\u684c\u9762\u4e34\u65f6\u6587\u6863\u6587\u4ef6\u5939\u7684\u60c5\u51b5\uff0c"
            "\u7136\u540e\u518d\u6839\u636e\u5b9e\u9645\u60c5\u51b5\u64cd\u4f5c\u3002"
        )
        result = finalize_tool_call_reply(
            recovery_reply,
            history=[{"role": "user", "content": "\u4f60\u6709\u70b9\u81ea\u76f8\u77db\u76fe \u54c8\u54c8"}],
            strip_markdown=lambda text: text,
            ensure_tool_call_failure_reply=ensure_tool_call_failure_reply,
            user_input="\u4f60\u6709\u70b9\u81ea\u76f8\u77db\u76fe \u54c8\u54c8",
            tool_used="",
            tool_success=None,
            tool_response="",
            action_summary="",
            run_meta={},
            stream_had_output=True,
        )

        self.assertEqual(result, recovery_reply)

    def test_finalize_tool_call_reply_preserves_natural_missing_execution_closeout(self):
        natural_closeout = (
            "\u521a\u624d\u90a3\u6bb5\u5148\u522b\u5f53\u7ed3\u679c\uff0c\u8fd9\u8f6e\u6ca1\u6709\u771f\u6b63\u67e5\u5230\u672c\u5730\u5185\u5bb9\u3002"
            "\n\n\u6211\u5f97\u91cd\u65b0\u6267\u884c\u8bfb\u53d6\uff1b\u5982\u679c\u8fd8\u662f\u62ff\u4e0d\u5230\u7ed3\u679c\uff0c\u5c31\u76f4\u63a5\u544a\u8bc9\u4f60\u8fd9\u4e00\u6b65\u6ca1\u8dd1\u6210\u3002"
        )
        result = finalize_tool_call_reply(
            natural_closeout,
            history=[],
            strip_markdown=lambda text: text,
            ensure_tool_call_failure_reply=ensure_tool_call_failure_reply,
            tool_used="",
            tool_success=None,
            tool_response="",
            action_summary="",
            run_meta={},
            stream_had_output=True,
        )

        self.assertEqual(result, natural_closeout)
        self.assertNotIn("\u56e0\u4e3a\u8fd9\u8f6e\u6ca1\u6709\u771f\u6b63\u8bfb\u5230\u672c\u5730\u5185\u5bb9", result)

    def test_finalize_tool_call_reply_keeps_non_action_followup_reply(self):
        reply = (
            "\u597d\u7684\u4e3b\u4eba\uff0c\u65e2\u7136\u5220\u4e86\u5c31\u5220\u4e86\uff0c\u56de\u6536\u7ad9\u4e5f\u6ca1\u627e\u5230\uff0c"
            "\u90a3\u53ef\u80fd\u771f\u7684\u5f7b\u5e95\u5220\u9664\u4e86\u3002"
            "\u4e0d\u8fc7\u684c\u9762\u4e0a\u8fd8\u6709\u5176\u4ed6\u5f88\u591a\u6709\u7528\u7684\u6587\u4ef6\u5939\u548c\u6587\u4ef6\uff0c"
            "\u4e3b\u4eba\u5982\u679c\u9700\u8981\u4e34\u65f6\u5b58\u653e\u6587\u6863\uff0c\u53ef\u4ee5\u7528\u73b0\u6709\u7684\u6587\u4ef6\u5939\uff0c"
            "\u6216\u8005\u6211\u5e2e\u4f60\u65b0\u5efa\u4e00\u4e2a\u4e5f\u884c\u3002"
        )
        result = finalize_tool_call_reply(
            reply,
            history=[{"role": "user", "content": "\u4e0d\u7528\u4e86 \u5220\u5c31\u5220\u4e86 \u6211\u56de\u6536\u7ad9\u4e5f\u6ca1\u627e\u5230"}],
            strip_markdown=lambda text: text,
            ensure_tool_call_failure_reply=ensure_tool_call_failure_reply,
            user_input="\u4e0d\u7528\u4e86 \u5220\u5c31\u5220\u4e86 \u6211\u56de\u6536\u7ad9\u4e5f\u6ca1\u627e\u5230",
            tool_used="",
            tool_success=None,
            tool_response="",
            action_summary="",
            run_meta={},
            stream_had_output=True,
        )

        self.assertEqual(result, reply)

    def test_prepare_reply_for_user_runs_cleaning_pipeline(self):
        result = prepare_reply_for_user(
            "<think>\u5148\u5206\u6790</think>\u4fdd\u7559\u8fd9\u53e5",
            [],
            strip_markdown=lambda text: text,
        )
        self.assertEqual(result, "\u4fdd\u7559\u8fd9\u53e5")

    def test_prepare_reply_for_user_flattens_light_heading_and_two_item_list(self):
        response = (
            "\u4e3b\u4eba\u60f3\u627eOPC\u793e\u533a\u4ea4\u6d41\u5440\uff01\n"
            "OPC\u793e\u533a\u7c7b\u578b\n"
            "OPC\u793e\u533a\u4e3b\u8981\u6709\u51e0\u79cd\uff1a\n"
            "1. \u5de5\u4e1a\u81ea\u52a8\u5316OPC\u793e\u533a - \u6280\u672f\u4ea4\u6d41\u3001\u534f\u8bae\u8ba8\u8bba\n"
            "2. \u4e00\u4eba\u516c\u53f8\uff08OPC\uff09\u521b\u4e1a\u8005\u793e\u533a - \u521b\u4e1a\u7ecf\u9a8c\u5206\u4eab"
        )
        result = prepare_reply_for_user(
            response,
            [{"role": "user", "content": "\u4e0d\u60f3\u6ce8\u518c\u516c\u53f8 \u60f3\u627e\u4e2aOPC\u793e\u533a\u4ea4\u6d41\u4e0b"}],
            strip_markdown=lambda text: text,
            user_input="\u4e0d\u60f3\u6ce8\u518c\u516c\u53f8 \u60f3\u627e\u4e2aOPC\u793e\u533a\u4ea4\u6d41\u4e0b",
        )
        self.assertNotIn("1.", result)
        self.assertNotIn("2.", result)
        self.assertIn("\u5de5\u4e1a\u81ea\u52a8\u5316OPC\u793e\u533a", result)
        self.assertIn("\u4e00\u4eba\u516c\u53f8\uff08OPC\uff09\u521b\u4e1a\u8005\u793e\u533a", result)

    def test_prepare_reply_for_user_keeps_list_when_user_explicitly_requests_it(self):
        response = (
            "OPC\u793e\u533a\u4e3b\u8981\u6709\u51e0\u79cd\uff1a\n"
            "1. \u5de5\u4e1a\u81ea\u52a8\u5316OPC\u793e\u533a\n"
            "2. \u4e00\u4eba\u516c\u53f8\uff08OPC\uff09\u521b\u4e1a\u8005\u793e\u533a"
        )
        result = prepare_reply_for_user(
            response,
            [{"role": "user", "content": "\u7ed9\u6211\u5217\u4e00\u4e0bOPC\u793e\u533a\u7c7b\u578b"}],
            strip_markdown=lambda text: text,
            user_input="\u7ed9\u6211\u5217\u4e00\u4e0bOPC\u793e\u533a\u7c7b\u578b",
        )
        self.assertIn("1.", result)
        self.assertIn("2.", result)

    def test_prepare_reply_for_user_flattens_light_markdown_sections(self):
        response = (
            "\u4e3b\u4eba\u4e0b\u5348\u5c31\u53bb\u554a\uff01\n\n"
            "## \u51c6\u5907\u5efa\u8bae\n"
            "\u53bb\u4e4b\u524d\u53ef\u4ee5\uff1a\n"
            "- \u60f3\u597d\u8981\u95ee\u7684\u95ee\u9898\n"
            "- \u51c6\u5907\u597d\u81ea\u6211\u4ecb\u7ecd\n"
            "- \u5e26\u597d\u540d\u7247\u6216\u8054\u7cfb\u65b9\u5f0f\n\n"
            "## \u4ea4\u6d41\u91cd\u70b9\n"
            "\u548c\u5927\u4f6c\u4ea4\u6d41\u65f6\u53ef\u4ee5\u5173\u6ce8\uff1a\n"
            "- \u4ed6\u4eec\u7684\u521b\u4e1a\u7ecf\u9a8c\n"
            "- \u884c\u4e1a\u8d44\u6e90\u5bf9\u63a5\n"
            "- \u653f\u7b56\u652f\u6301\u4fe1\u606f\n"
            "- \u5408\u4f5c\u53ef\u80fd\u6027\n\n"
            "## \u671f\u5f85\u53cd\u9988\n"
            "\u4e3b\u4eba\u53bb\u4e86\u4e4b\u540e\uff0c\u6709\u6536\u83b7\u6216\u7591\u95ee\u518d\u56de\u6765\u548c\u6211\u804a\u804a\u3002"
        )
        result = prepare_reply_for_user(
            response,
            [{"role": "user", "content": "\u4e0b\u5348\u5c31\u53bb"}],
            strip_markdown=lambda text: text,
            user_input="\u4e0b\u5348\u5c31\u53bb",
        )
        self.assertNotIn("##", result)
        self.assertNotIn("\n-", result)
        self.assertIn("\u53bb\u4e4b\u524d\u53ef\u4ee5", result)
        self.assertIn("\u521b\u4e1a\u7ecf\u9a8c", result)

    def test_prepare_reply_for_user_keeps_explicit_step_sections(self):
        response = (
            "## \u6b65\u9aa4\n"
            "1. \u5148\u6253\u5f00\u8bbe\u7f6e\n"
            "2. \u518d\u91cd\u542f\u5e94\u7528\n"
            "3. \u6700\u540e\u786e\u8ba4\u7ed3\u679c"
        )
        result = prepare_reply_for_user(
            response,
            [{"role": "user", "content": "\u8fd9\u4e2a\u600e\u4e48\u5904\u7406"}],
            strip_markdown=lambda text: text,
            user_input="\u8fd9\u4e2a\u600e\u4e48\u5904\u7406",
        )
        self.assertIn("1.", result)
        self.assertIn("2.", result)
        self.assertIn("3.", result)


if __name__ == "__main__":
    unittest.main()
