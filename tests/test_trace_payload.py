import unittest
from unittest.mock import patch

from agent_final import build_repair_progress_payload


class RepairPayloadTests(unittest.TestCase):
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
