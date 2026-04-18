import unittest

import core.reply_formatter as reply_formatter_module


class ReplyHygieneTests(unittest.TestCase):
    def test_clean_visible_reply_text_trims_mid_reply_restart(self):
        reply = (
            "明白了！看来我刚才确实太啰嗦了，一个问题重复说。\n\n"
            "**核心问题**：文件夹结构混乱，文件散落各处。\n\n"
            "**建议方向**：按功能分类，一个文件夹一个职责。\n\n"
            "这样够简洁了吗？需要我进一步解释哪个部分？"
            "好的，我明白了。刚才确实有点过度反应了。\n\n"
            "让我重新整理一下思路，给你一个清晰简洁的建议：\n\n"
            "**当前问题**：文件夹结构混乱，文件散落各处，命名不一致。"
        )

        cleaned = reply_formatter_module._clean_visible_reply_text(reply)

        self.assertIn("这样够简洁了吗？", cleaned)
        self.assertNotIn("让我重新整理一下思路", cleaned)
        self.assertNotIn("**当前问题**", cleaned)

    def test_clean_visible_reply_text_keeps_valid_opening_acknowledgement(self):
        reply = "好的，我明白了。核心问题是根目录文件太散，需要先清理再分组。"

        cleaned = reply_formatter_module._clean_visible_reply_text(reply)

        self.assertEqual(cleaned, reply)

    def test_build_l1_messages_sanitizes_polluted_assistant_history(self):
        polluted = (
            "啊！抱歉抱歉，我太着急了。\n\n"
            "**问题总结**：根目录文件爆炸。\n\n"
            "这样清楚了吗？明白了，我重新整理一下：\n\n"
            "**文件夹结构问题分析**：这里又重复开讲了一遍。"
        )
        bundle = {
            "l1": [
                {"role": "assistant", "content": polluted},
                {"role": "user", "content": "那你直接说重点"},
            ],
            "user_input": "那你直接说重点",
        }

        messages = reply_formatter_module._build_l1_messages(bundle)

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "assistant")
        self.assertIn("问题总结：", messages[0]["content"])
        self.assertNotIn("**问题总结**", messages[0]["content"])
        self.assertNotIn("重新整理一下", messages[0]["content"])

    def test_clean_visible_reply_text_prefers_grounded_tool_tail(self):
        reply = (
            "好的，我明白了！刚才确实太啰嗦了。\n\n"
            "**核心建议**：\n"
            "1. 先清理\n"
            "2. 再分类\n\n"
            "这样整理后结构会清晰很多。需要我详细说明某个具体操作吗？"
            "现在我看到了你的桌面情况！确实很乱，各种文件混在一起。\n\n"
            "## 桌面整理方案\n"
            "先把 Nova 相关文件夹合并到一个目录下。"
        )

        cleaned = reply_formatter_module._clean_visible_reply_text(reply)

        self.assertTrue(cleaned.startswith("现在我看到了你的桌面情况"))
        self.assertNotIn("**核心建议**", cleaned)

    def test_clean_visible_reply_text_prefers_tool_closeout_tail(self):
        reply = (
            "好的，我明白了！刚才确实太啰嗦了。\n\n"
            "**核心建议**：先清理，再分类。\n\n"
            "这样整理后结构会清晰很多。需要我详细说明某个具体操作吗？"
            "这一步已经完成：\n\n"
            "Computer Use 技能支持：在QQ群发消息。"
        )

        cleaned = reply_formatter_module._clean_visible_reply_text(reply)

        self.assertTrue(cleaned.startswith("这一步已经完成"))
        self.assertNotIn("**核心建议**", cleaned)


    def test_clean_visible_reply_text_prefers_post_think_answer_tail(self):
        reply = (
            "My underlying model is MiniMax-M2.7, tailored for local assistant use.\n"
            "<think>The user is asking what model I am again.</think>\n"
            "I am the MiniMax-M2.7 local assistant."
        )

        cleaned = reply_formatter_module._clean_visible_reply_text(reply)

        self.assertEqual(cleaned, "I am the MiniMax-M2.7 local assistant.")

    def test_get_skill_display_name_repairs_known_mojibake_label(self):
        original_ready = reply_formatter_module._nova_core_ready
        original_get_all_skills = reply_formatter_module._get_all_skills
        try:
            reply_formatter_module._nova_core_ready = True
            reply_formatter_module._get_all_skills = lambda: {
                "weather": {"name": "澶╂皵鏌ヨ"},
            }
            self.assertEqual(reply_formatter_module.get_skill_display_name("weather"), "天气查询")
        finally:
            reply_formatter_module._nova_core_ready = original_ready
            reply_formatter_module._get_all_skills = original_get_all_skills

    def test_clean_visible_reply_text_strips_inline_bold_markers(self):
        reply = "Plain **important** note."

        cleaned = reply_formatter_module._clean_visible_reply_text(reply)

        self.assertEqual(cleaned, "Plain important note.")

    def test_clean_visible_reply_text_keeps_code_span_markers(self):
        reply = "Use `**/*.py` and **carefully**."

        cleaned = reply_formatter_module._clean_visible_reply_text(reply)

        self.assertEqual(cleaned, "Use `**/*.py` and carefully.")

    def test_clean_visible_reply_text_flattens_simple_chat_list(self):
        reply = "核心建议：\n1. 先清理\n2. 再分类"

        cleaned = reply_formatter_module._clean_visible_reply_text(reply)

        self.assertEqual(cleaned, "核心建议：先清理；再分类。")

    def test_clean_visible_reply_text_keeps_explicit_step_list(self):
        reply = "步骤如下：\n1. 先运行测试\n2. 再改配置\n3. 最后重启"

        cleaned = reply_formatter_module._clean_visible_reply_text(reply)

        self.assertEqual(cleaned, reply)

    def test_clean_visible_reply_text_keeps_code_list(self):
        reply = "- `npm test`\n- `npm run build`"

        cleaned = reply_formatter_module._clean_visible_reply_text(reply)

        self.assertEqual(cleaned, reply)

    def test_clean_visible_reply_text_trims_generic_restart_restatement(self):
        reply = (
            "\u524d\u9762\u90a3\u7248\u8bf4\u5f97\u592a\u7ed5\u4e86\uff0c\u4f60\u5148\u770b\u7ed3\u8bba\u3002\n\n"
            "**\u6838\u5fc3\u95ee\u9898**\uff1a\u6587\u4ef6\u5939\u7ed3\u6784\u8fd8\u5728\u6df7\u7740\u3002\n\n"
            "\u8fd9\u6837\u8bb2\u6e05\u695a\u4e86\u5417\uff1f\u9700\u8981\u6211\u518d\u62c6\u5f00\u4e00\u70b9\u5417\uff1f"
            "\u6211\u7406\u89e3\u4e86\uff0c\u8ba9\u6211\u518d\u91cd\u8ff0\u4e00\u904d\u3002\n\n"
            "\u73b0\u5728\u53ea\u7559\u4e0b\u4e24\u4ef6\u4e8b\uff1a\u5148\u6536\u76ee\u5f55\uff0c\u518d\u6536\u547d\u540d\u3002"
        )

        cleaned = reply_formatter_module._clean_visible_reply_text(reply)

        self.assertIn("\u8fd9\u6837\u8bb2\u6e05\u695a\u4e86\u5417", cleaned)
        self.assertNotIn("\u8ba9\u6211\u518d\u91cd\u8ff0\u4e00\u904d", cleaned)
        self.assertNotIn("\u73b0\u5728\u53ea\u7559\u4e0b\u4e24\u4ef6\u4e8b", cleaned)

    def test_clean_visible_reply_text_prefers_generic_tool_result_tail(self):
        reply = (
            "\u6211\u5148\u7ed9\u4f60\u4e00\u4e2a\u7c97\u7565\u5224\u65ad\u3002\n\n"
            "**\u5efa\u8bae\u65b9\u5411**\uff1a\u5148\u4e0d\u8981\u52a8\u592a\u591a\u6587\u4ef6\u3002\n\n"
            "\u9700\u8981\u6211\u628a\u4e0a\u9762\u90a3\u6bb5\u518d\u5c55\u5f00\u5417\uff1f"
            "\u6839\u636e\u5de5\u5177\u7ed3\u679c\uff0c\u73b0\u5728\u5df2\u7ecf\u5b9a\u4f4d\u5230 `tasks/continuity.py` \u8fd9\u6761\u94fe\u8def\u3002\n\n"
            "\u5148\u4ece\u8fd9\u4e2a\u6587\u4ef6\u5f80\u4e0b\u6536\u5373\u53ef\u3002"
        )

        cleaned = reply_formatter_module._clean_visible_reply_text(reply)

        self.assertTrue(cleaned.startswith("\u6839\u636e\u5de5\u5177\u7ed3\u679c"))
        self.assertIn("`tasks/continuity.py`", cleaned)
        self.assertNotIn("**\u5efa\u8bae\u65b9\u5411**", cleaned)


if __name__ == "__main__":
    unittest.main()
