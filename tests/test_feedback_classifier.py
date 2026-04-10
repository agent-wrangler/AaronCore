import json
import re
import tempfile
import unittest
from pathlib import Path

import core.feedback_classifier as feedback_classifier
import core.feedback_loop as feedback_loop


class FeedbackClassifierTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.rules_file = Path(self.tmpdir.name) / "feedback_rules.json"
        self.original_rules_file = feedback_classifier.RULES_FILE
        self.original_llm_call = feedback_classifier._llm_call
        self.original_debug_write = feedback_classifier._debug_write
        feedback_classifier.RULES_FILE = self.rules_file
        feedback_classifier.init(llm_call=self._fake_llm, debug_write=lambda *_: None)

    def tearDown(self):
        feedback_classifier.RULES_FILE = self.original_rules_file
        feedback_classifier._llm_call = self.original_llm_call
        feedback_classifier._debug_write = self.original_debug_write
        self.tmpdir.cleanup()

    @staticmethod
    def _fake_llm(prompt: str) -> str:
        text = str(prompt)
        if "反馈分类器" in text and "当前用户输入" in text:
            current_input_match = re.search(r"当前用户输入:\s*(.+)", text)
            current_input = current_input_match.group(1).strip() if current_input_match else text

            if "小游戏到窗口" in current_input:
                return json.dumps(
                    {
                        "is_feedback": True,
                        "category": "路由调度",
                        "type": "skill_route",
                        "scene": "routing",
                        "problem": "wrong_skill_selected",
                        "fix": "adjust_skill_routing_for_scene",
                        "level": "short_term",
                    },
                    ensure_ascii=False,
                )
            if "没说天气" in current_input:
                return json.dumps(
                    {
                        "is_feedback": True,
                        "category": "路由调度",
                        "type": "skill_route",
                        "scene": "routing",
                        "problem": "wrong_skill_selected",
                        "fix": "adjust_skill_routing_for_scene",
                        "level": "short_term",
                    },
                    ensure_ascii=False,
                )
            if "太空了" in current_input or "别回空话" in current_input:
                return json.dumps(
                    {
                        "is_feedback": True,
                        "category": "交互风格",
                        "type": "execution_policy",
                        "scene": "chat",
                        "problem": "fallback_too_generic",
                        "fix": "ability_queries_should_answer_capabilities_directly",
                        "level": "short_term",
                    },
                    ensure_ascii=False,
                )
            if "今天天气怎么样" in current_input:
                return json.dumps({"is_feedback": False}, ensure_ascii=False)
            return json.dumps(
                {
                    "is_feedback": True,
                    "category": "意图理解",
                    "type": "user_pref",
                    "scene": "general",
                    "problem": "generic_feedback",
                    "fix": "keep_observing_and_refine",
                    "level": "session",
                },
                ensure_ascii=False,
            )

        if "你是经验凝结器" in text:
            return "当用户指出走错流程时，不要误触发技能，应该按纠正后的方向处理"

        return ""

    def test_meta_bug_report_is_classified_as_routing_issue(self):
        result = feedback_classifier.classify_feedback(
            "检查下这个路径 只要对话里出现代码就会出现个小游戏到窗口。感觉有问题"
        )

        self.assertEqual(result["type"], "skill_route")
        self.assertEqual(result["scene"], "routing")
        self.assertEqual(result["problem"], "wrong_skill_selected")

    def test_weather_misroute_feedback_is_classified_as_routing_issue(self):
        result = feedback_classifier.classify_feedback("不是 我没说天气 你发天气之前")

        self.assertEqual(result["type"], "skill_route")
        self.assertEqual(result["scene"], "routing")
        self.assertEqual(result["problem"], "wrong_skill_selected")

    def test_record_feedback_rule_skips_new_requests(self):
        result = feedback_classifier.record_feedback_rule(
            "今天天气怎么样",
            "你还会什么",
            "我会很多",
        )

        self.assertIsNone(result)
        self.assertFalse(self.rules_file.exists())

    def test_record_feedback_rule_skips_system_explanation_requests(self):
        result = feedback_classifier.record_feedback_rule(
            "是系统内置的当前时间戳在哪 什么时候加的 我怎么不知道",
            "这次怎么直接就知道了",
            "因为当前环境里带了系统时间",
        )

        self.assertIsNone(result)
        self.assertFalse(self.rules_file.exists())

    def test_search_relevant_rules_relies_on_text_overlap(self):
        item = feedback_classifier.record_feedback_rule(
            "检查下这个路径 只要对话里出现代码就会出现个小游戏到窗口。感觉有问题",
            "帮我看看为什么一提代码就会乱触发",
            "我帮你打开了一个小游戏窗口",
        )

        matches = feedback_classifier.search_relevant_rules("为什么一出现代码就弹小游戏窗口", limit=1)
        stored_rules = feedback_classifier._load_rules()

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["id"], item["id"])
        self.assertGreaterEqual(stored_rules[0]["hit_count"], 1)

    def test_record_feedback_rule_merges_duplicate_rules(self):
        first = feedback_classifier.record_feedback_rule(
            "不是 我没说天气 你发天气之前",
            "帮我看下今天温度",
            "常州今天 18 到 26 度",
        )
        second = feedback_classifier.record_feedback_rule(
            "不是 我没说天气 你发天气之前",
            "帮我看下今天温度",
            "常州今天 18 到 26 度",
        )
        stored_rules = feedback_classifier._load_rules()

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(stored_rules), 1)
        self.assertEqual(stored_rules[0]["feedback_count"], 2)

    def test_feedback_loop_v2_no_longer_depends_on_negative_keywords(self):
        history = [
            {"role": "user", "content": "帮我写段代码"},
            {"role": "assistant", "content": "我给你打开了一个小游戏窗口"},
            {"role": "user", "content": "检查下这个路径 只要对话里出现代码就会出现个小游戏到窗口。感觉有问题"},
        ]

        item = feedback_loop.l7_record_feedback_v2(history[-1]["content"], history)

        self.assertIsNotNone(item)
        self.assertEqual(item["scene"], "routing")
        self.assertEqual(item["problem"], "wrong_skill_selected")

    def test_feedback_loop_v2_skips_followup_feedback_threads(self):
        first_history = [
            {"role": "user", "content": "还记得你自己说你喜欢的游戏吗"},
            {"role": "assistant", "content": "我喜欢塔防和解谜"},
            {"role": "user", "content": "不是这些 之前我们的玩的"},
        ]
        first = feedback_loop.l7_record_feedback_v2(first_history[-1]["content"], first_history)
        self.assertIsNotNone(first)

        followup_history = first_history + [
            {"role": "assistant", "content": "那我再想想是不是别的游戏"},
            {"role": "user", "content": "带脑筋两个字的"},
        ]
        second = feedback_loop.l7_record_feedback_v2(followup_history[-1]["content"], followup_history)
        stored_rules = feedback_classifier._load_rules()

        self.assertIsNone(second)
        self.assertEqual(len(stored_rules), 1)

    def test_format_l7_context_rewrites_list_feedback_into_positive_preference(self):
        formatted = feedback_classifier.format_l7_context(
            [
                {
                    "category": "交互风格",
                    "fix": "当用户指出格式问题时，不要继续使用列表回复，应该改用自然句式直接回应内容。",
                    "user_feedback": "你怎么又用列表啊",
                }
            ]
        )

        self.assertIn("普通聊天默认写成自然、连贯的短正文。", formatted)
        self.assertNotIn("列表回复", formatted)

    def test_format_l7_context_rewrites_list_feedback_without_fix(self):
        formatted = feedback_classifier.format_l7_context(
            [
                {
                    "category": "交互风格",
                    "last_question": "正常聊天好吧",
                    "user_feedback": "你怎么又开始用列表了",
                }
            ]
        )

        self.assertEqual(formatted, "交互风格：普通聊天默认写成自然、连贯的短正文。")

    def test_normalize_rules_data_rewrites_list_style_fixes(self):
        rules = [
            {
                "fix": "当用户指出格式问题时，不要继续使用列表回复，应该改用自然句式直接回应内容。",
                "user_feedback": "你怎么又用列表啊",
                "last_question": "对啊 为什么还是用列表",
                "category": "交互风格",
                "type": "user_pref",
                "scene": "general",
            },
            {
                "fix": "当用户抱怨界面卡顿时，不要机械罗列原因和解决方法，应该直接提供最可能的核心解决方案。",
                "user_feedback": "能不能不要又用列表解释了",
                "last_question": "就是感觉好卡 不知道为什么",
                "category": "交互风格",
                "type": "user_pref",
                "scene": "general",
            },
            {
                "fix": "先核实工具结果再下结论。",
                "user_feedback": "你都没搜就说搜了",
                "last_question": "能不能先查一下",
                "category": "路由调度",
                "type": "skill_route",
                "scene": "routing",
            },
            {
                "fix": "当用户询问操作结果时，不要罗列技术排查步骤，应直接说明当前界面状态并提供后续操作选项。",
                "user_feedback": "又没成功啊 你说话可以根据目前的界面说吗 一直很短 感觉看着不舒服",
                "last_question": "修好了吗",
                "category": "意图理解",
                "type": "user_pref",
                "scene": "general",
            },
        ]

        changed = feedback_classifier.normalize_rules_data(rules)

        self.assertEqual(changed, 2)
        self.assertEqual(rules[0]["fix"], "普通聊天默认写成自然、连贯的短正文。")
        self.assertEqual(rules[1]["fix"], "用户抱怨界面卡顿时，先直接给最可能的核心解决方案。")
        self.assertEqual(rules[2]["fix"], "先核实工具结果再下结论。")
        self.assertEqual(
            rules[3]["fix"],
            "当用户询问操作结果时，不要罗列技术排查步骤，应直接说明当前界面状态并提供后续操作选项。",
        )

    def test_record_feedback_rule_compacts_verbose_fix_into_short_action(self):
        item = feedback_classifier.record_feedback_rule(
            "检查下这个路径 只要对话里出现代码就会出现个小游戏到窗口。感觉有问题",
            "帮我看看为什么一提代码就会乱触发",
            "我帮你打开了一个小游戏窗口",
        )

        self.assertIsNotNone(item)
        self.assertEqual(item["fix"], "按纠正后的方向处理。")
        self.assertNotIn("当用户指出", item["fix"])


if __name__ == "__main__":
    unittest.main()
