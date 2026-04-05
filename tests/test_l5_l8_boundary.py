import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from storage import state_loader


class L5L8BoundaryTests(unittest.TestCase):
    def test_load_l5_knowledge_no_longer_mixes_l8_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            knowledge_file = tmp / "knowledge.json"
            knowledge_base_file = tmp / "knowledge_base.json"
            knowledge_file.write_text(
                json.dumps([{"name": "weather", "核心技能": "weather"}], ensure_ascii=False),
                encoding="utf-8",
            )
            knowledge_base_file.write_text(
                json.dumps([{"query": "FastAPI 是什么？", "summary": "FastAPI 是一个 Python Web 框架。"}], ensure_ascii=False),
                encoding="utf-8",
            )

            with patch.object(state_loader, "KNOWLEDGE_FILE", knowledge_file), patch.object(
                state_loader, "KNOWLEDGE_BASE_FILE", knowledge_base_file
            ), patch.object(state_loader, "_nova_core_ready", False):
                loaded = state_loader.load_l5_knowledge()

        self.assertIn("knowledge", loaded)
        self.assertIn("skills", loaded)
        self.assertNotIn("knowledge_base", loaded)
        self.assertEqual(len(loaded["knowledge"]), 1)


if __name__ == "__main__":
    unittest.main()
