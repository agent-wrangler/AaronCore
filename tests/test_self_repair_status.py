import unittest
from unittest.mock import patch

import agent_final


class SelfRepairStatusTests(unittest.TestCase):
    def test_build_self_repair_status_includes_human_readable_summaries(self):
        config = {
            "enabled": True,
            "allow_web_search": True,
            "allow_knowledge_write": True,
            "allow_feedback_relearn": True,
            "allow_self_repair_planning": True,
            "allow_self_repair_test_run": True,
            "allow_self_repair_auto_apply": True,
            "self_repair_apply_mode": "confirm",
            "allow_skill_generation": False,
        }
        reports = [
            {
                "id": "repair_1",
                "status": "awaiting_confirmation",
                "patch_preview": {
                    "status": "preview_ready",
                    "risk_level": "medium",
                    "auto_apply_ready": False,
                    "confirmation_required": True,
                },
                "apply_result": {},
            }
        ]

        with patch("agent_final.load_autolearn_config", return_value=config), patch(
            "agent_final.load_self_repair_reports", return_value=reports
        ):
            status = agent_final.build_self_repair_status()

        self.assertIn("补学并写回知识库", status["learning_summary"])
        self.assertIn("只确认一次", status["repair_summary"])
        self.assertIn("只确认一次", status["autonomy_summary"])
        self.assertIn("只等一次确认", status["latest_status_summary"])


if __name__ == "__main__":
    unittest.main()
