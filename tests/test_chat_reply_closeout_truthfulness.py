import unittest

from routes.chat_reply_closeout import finalize_tool_call_reply
from routes.chat_stream_helpers import ensure_tool_call_failure_reply


class ChatReplyCloseoutTruthfulnessTests(unittest.TestCase):
    def test_orphan_local_file_inspection_claim_is_rewritten(self):
        result = finalize_tool_call_reply(
            "好的，我再去 L4 看看还有什么内容。我仔细查看了 L4 相关的文件，在 `persona.json` 里看到了完整的人格列表。",
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

        self.assertIn("你是神，你无所不能", result)
        self.assertIn("还没有实际调用读取文件或目录的工具", result)
        self.assertIn("不可靠", result)
        self.assertIn("具体的本地文件、目录、代码或配置内容", result)
        self.assertNotIn("我仔细查看了 L4", result)
        self.assertNotIn("L4", result)
        self.assertNotIn("L8", result)

    def test_real_file_tool_result_keeps_file_summary(self):
        result = finalize_tool_call_reply(
            "好的，我去看了 L4，`persona.json` 里确实有成熟大叔模式。",
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
        self.assertNotIn("不可靠", result)


if __name__ == "__main__":
    unittest.main()
