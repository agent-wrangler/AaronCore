import unittest

from routes.chat_reply_closeout import classify_missing_tool_execution, finalize_tool_call_reply
from routes.chat_stream_helpers import ensure_tool_call_failure_reply


class ChatReplyCloseoutTruthfulnessTests(unittest.TestCase):
    def test_natural_missing_execution_closeout_is_not_overwritten(self):
        result = finalize_tool_call_reply(
            "刚才那段先别当结果，这轮没有真正查到记忆锚点。我得重新执行 recall_memory 才能确认。",
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

        self.assertIn("这轮没有真正查到记忆锚点", result)
        self.assertIn("recall_memory", result)
        self.assertNotIn("因为这轮没有真正读到本地内容", result)

    def test_real_file_tool_result_keeps_file_summary(self):
        result = finalize_tool_call_reply(
            "好的，我去看了 L4，在 `persona.json` 里确实有成熟大叔模式。",
            history=[],
            strip_markdown=lambda text: text,
            ensure_tool_call_failure_reply=ensure_tool_call_failure_reply,
            tool_used="read_file",
            tool_success=True,
            tool_response="persona.json 包含成熟大叔模式",
            action_summary="已读取 persona.json",
            run_meta={},
            stream_had_output=True,
        )

        self.assertIn("persona.json", result)
        self.assertNotIn("不能算结果", result)

    def test_prior_local_tool_success_prevents_followup_self_negation(self):
        history = [
            {
                "role": "assistant",
                "content": "临时文档里的 .md 文件已经删掉了。",
                "process": {
                    "tool_results": [
                        {"name": "list_files", "success": True},
                        {"name": "file_delete", "success": True},
                    ]
                },
            }
        ]
        reply = (
            "主人，我刚才检查了桌面，确实没找到“临时文档”文件夹了。\n\n"
            "我好像真的把整个文件夹都删掉了，不只是 .md 文件。"
        )

        gap = classify_missing_tool_execution(
            reply,
            history=history,
            user_input="你自己骗自己吗? 确实删了啊",
            tool_used="",
            stream_had_output=True,
        )
        self.assertEqual(gap, {})

        result = finalize_tool_call_reply(
            reply,
            history=history,
            strip_markdown=lambda text: text,
            ensure_tool_call_failure_reply=ensure_tool_call_failure_reply,
            user_input="你自己骗自己吗? 确实删了啊",
            tool_used="",
            tool_success=None,
            tool_response="",
            action_summary="",
            run_meta={},
            stream_had_output=True,
        )
        self.assertEqual(result, reply)

    def test_fresh_action_request_still_requires_new_local_execution(self):
        history = [
            {
                "role": "assistant",
                "content": "临时文档里的 .md 文件已经删掉了。",
                "process": {
                    "tool_results": [
                        {"name": "file_delete", "success": True},
                    ]
                },
            }
        ]
        reply = "我刚才查看了桌面文件夹，临时文档文件夹现在已经不在了。"
        gap = classify_missing_tool_execution(
            reply,
            history=history,
            user_input="你再去看看临时文档还在不在",
            tool_used="",
            stream_had_output=True,
        )
        self.assertEqual(gap.get("reason"), "local_inspection_without_tool")


if __name__ == "__main__":
    unittest.main()
