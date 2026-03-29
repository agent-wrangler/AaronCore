import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import l2_memory


class L2MemoryTests(unittest.TestCase):
    def test_detect_type_no_longer_uses_skill_demand(self):
        detected = l2_memory._detect_type("可以帮我配置模型吗")

        self.assertNotEqual(detected, "skill_demand")

    def test_prune_legacy_l2_demands_from_l5_backs_up_and_removes_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            knowledge_file = tmp / "knowledge.json"
            knowledge_file.write_text(
                json.dumps(
                    [
                        {
                            "name": "open_target",
                            "source": "l6_success_path",
                            "summary": "先定位窗口，再打开目标目录",
                        },
                        {
                            "source": "l2_demand",
                            "trigger": ["可以帮我配置模型吗"],
                            "demand_count": 1,
                            "status": "unmet",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(l2_memory, "L5_FILE", knowledge_file):
                result = l2_memory.prune_legacy_l2_demands_from_l5(reason="test_cleanup")

            stored = json.loads(knowledge_file.read_text(encoding="utf-8"))
            backups = list(tmp.glob("knowledge.backup_*.json"))

            self.assertTrue(result["success"])
            self.assertEqual(result["reason"], "test_cleanup")
            self.assertEqual(result["removed_count"], 1)
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0]["source"], "l6_success_path")
            self.assertEqual(len(backups), 1)


if __name__ == "__main__":
    unittest.main()
