import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.skills import story


class StorySkillTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.history_path = Path(self._tmpdir.name) / "msg_history.json"
        self.state_path = Path(self._tmpdir.name) / "story_state.json"
        self._patcher = patch.multiple(
            story,
            HISTORY_PATH=self.history_path,
            STORY_STATE_PATH=self.state_path,
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmpdir.cleanup()

    def _read_state(self):
        if not self.state_path.exists():
            return {}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def test_story_returns_multi_paragraph_content_and_saves_state(self):
        with patch("core.skills.story.random.choice", side_effect=lambda seq: seq[0]):
            result = story.execute("讲个故事")

        state = self._read_state()

        self.assertIn("《月灯森林的最后一把钥匙》", result)
        self.assertGreaterEqual(result.count("\n\n"), 5)
        self.assertGreater(len(result), 300)
        self.assertEqual(state["theme_id"], "forest_fox")
        self.assertEqual(state["title"], "月灯森林的最后一把钥匙")
        self.assertEqual(state["chapter"], 1)

    def test_story_follow_up_continues_same_title_and_increments_chapter(self):
        self.state_path.write_text(
            json.dumps(
                {
                    "theme_id": "forest_fox",
                    "title": "月灯森林的最后一把钥匙",
                    "chapter": 1,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        result = story.execute("继续讲")
        state = self._read_state()

        self.assertIn("《月灯森林的最后一把钥匙·第二章》", result)
        self.assertIn("上一章", result)
        self.assertIn("小狐狸阿雾", result)
        self.assertEqual(state["theme_id"], "forest_fox")
        self.assertEqual(state["title"], "月灯森林的最后一把钥匙")
        self.assertEqual(state["chapter"], 2)

    def test_story_can_restore_previous_title_from_history_when_state_is_missing(self):
        self.history_path.write_text(
            json.dumps(
                [
                    {"role": "user", "content": "给我讲个狐狸的故事"},
                    {"role": "nova", "content": "《月灯森林的最后一把钥匙》\n\n小狐狸阿雾在月灯森林里……"},
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        result = story.execute("然后呢")
        state = self._read_state()

        self.assertIn("《月灯森林的最后一把钥匙·第二章》", result)
        self.assertEqual(state["theme_id"], "forest_fox")
        self.assertEqual(state["chapter"], 2)


if __name__ == "__main__":
    unittest.main()
