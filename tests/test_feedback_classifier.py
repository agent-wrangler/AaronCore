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
        if "你是 NovaCore 的反馈分类器" in text:
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


if __name__ == "__main__":
    unittest.main()
