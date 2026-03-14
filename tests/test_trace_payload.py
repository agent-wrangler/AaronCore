import unittest
from unittest.mock import patch

from agent_final import build_repair_progress_payload, build_trace_payload


class TracePayloadTests(unittest.TestCase):
    def test_plain_chat_shows_trace_cards(self):
        trace = build_trace_payload({"mode": "chat", "skill": "none", "reason": "命中普通聊天语句"})

        self.assertTrue(trace["show"])
        self.assertEqual(len(trace["cards"]), 2)
        self.assertEqual(trace["cards"][0]["label"], "理解")
        self.assertIn("普通聊天", trace["cards"][0]["detail"])
        self.assertEqual(trace["cards"][1]["label"], "路径")

    def test_story_context_route_returns_soft_summary(self):
        trace = build_trace_payload(
            {"mode": "skill", "skill": "story", "source": "context", "reason": "story_follow_up_from_history"},
            {"skill": "story", "success": True},
        )

        self.assertTrue(trace["show"])
        self.assertEqual(len(trace["cards"]), 2)
        self.assertEqual(trace["cards"][0]["label"], "理解")
        self.assertIn("接着刚才那段故事", trace["cards"][1]["detail"])

    def test_weather_skill_route_returns_trace_cards(self):
        trace = build_trace_payload(
            {"mode": "skill", "skill": "weather", "reason": "命中技能候选: 上海"},
            {"skill": "weather", "success": True},
        )

        self.assertTrue(trace["show"])
        self.assertEqual(len(trace["cards"]), 2)
        self.assertIn("直接去看天气", trace["cards"][1]["detail"])

    def test_meta_bug_report_returns_repair_progress_payload(self):
        with patch("agent_final.build_self_repair_status", return_value={"can_plan_repairs": True}):
            payload = build_repair_progress_payload({"intent": "meta_bug_report"}, {"type": "skill_route"})

        self.assertTrue(payload["show"])
        self.assertTrue(payload["watch"])
        self.assertEqual(payload["label"], "修复进度")
        self.assertEqual(payload["headline"], "已记录反馈")

    def test_answer_correction_returns_repair_progress_payload(self):
        with patch("agent_final.build_self_repair_status", return_value={"can_plan_repairs": True}):
            payload = build_repair_progress_payload({"intent": "answer_correction"}, None)

        self.assertTrue(payload["show"])
        self.assertTrue(payload["watch"])
        self.assertEqual(payload["headline"], "已收到纠偏")
        self.assertIn("上一轮", payload["item"])

    def test_plain_chat_feedback_hides_repair_progress_payload(self):
        payload = build_repair_progress_payload({"mode": "chat"}, None)

        self.assertFalse(payload["show"])


if __name__ == "__main__":
    unittest.main()
