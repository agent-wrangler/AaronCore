import unittest

from core.feedback_classifier import classify_feedback


class FeedbackClassifierTests(unittest.TestCase):
    def test_meta_bug_report_is_classified_as_routing_issue(self):
        result = classify_feedback("检查下这个路径 只要对话里出现代码就会出现个小游戏到窗口。感觉有问题")

        self.assertEqual(result["type"], "skill_route")
        self.assertEqual(result["scene"], "routing")
        self.assertEqual(result["problem"], "wrong_skill_selected")

    def test_weather_misroute_feedback_is_classified_as_routing_issue(self):
        result = classify_feedback("不是 我没说天气 你发天气之前")

        self.assertEqual(result["type"], "skill_route")
        self.assertEqual(result["scene"], "routing")
        self.assertEqual(result["problem"], "wrong_skill_selected")


if __name__ == "__main__":
    unittest.main()
