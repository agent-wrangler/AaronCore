import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brain import local_learning


class LocalLearningTests(unittest.TestCase):
    def test_auto_learn_no_longer_intercepts_mode_switch_requests(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persona_file = Path(tmpdir) / "persona.json"
            persona_file.write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")

            local_learning.configure(str(persona_file), lambda persona, new_name: None)

            with patch("memory.evolve") as mock_evolve:
                result = local_learning.auto_learn("切换甜心模式")

        self.assertEqual(result, "")
        mock_evolve.assert_called_once_with("切换甜心模式", "")


if __name__ == "__main__":
    unittest.main()
