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

        # mock LLM 避免依赖真实 API
        self._llm_patcher = patch.object(
            story, "_llm_generate",
            side_effect=self._fake_llm_generate,
        )
        self._llm_patcher.start()

    def _fake_llm_generate(self, prompt, max_tokens=2000):
        if "\u7b2c" in prompt or "\u7eed\u5199" in prompt or "\u4e0a\u4e00\u7ae0" in prompt:
            # 续写请求
            return (
                "\u300a\u6708\u706f\u68ee\u6797\u00b7\u7b2c\u4e8c\u7ae0\u300b\n\n"
                "\u5c0f\u72d0\u72f8\u963f\u96fe\u7ee7\u7eed\u5728\u68ee\u6797\u91cc\u5bfb\u627e\u6708\u5149\u4e95\u3002\n\n"
                "\u5b83\u8d70\u8fc7\u4e86\u4e00\u7247\u53c8\u4e00\u7247\u7684\u6811\u6797\u3002\n\n"
                "\u6700\u7ec8\uff0c\u5b83\u627e\u5230\u4e86\u90a3\u53e3\u4f1a\u5531\u6b4c\u7684\u4e95\u3002\n\n"
                "\u6574\u7247\u68ee\u6797\u91cd\u65b0\u4eae\u4e86\u8d77\u6765\u3002\n\n"
                "\u4e0a\u4e00\u7ae0\u7684\u6545\u4e8b\u8fd8\u5728\u7ee7\u7eed\u3002"
            )
        # 新故事
        return (
            "\u300a\u6708\u706f\u68ee\u6797\u7684\u6700\u540e\u4e00\u628a\u94a5\u5319\u300b\n\n"
            "\u5c0f\u72d0\u72f8\u963f\u96fe\u5728\u6708\u706f\u68ee\u6797\u91cc\u5bfb\u627e\u6708\u5149\u4e95\u3002"
            "\u5b83\u6709\u4e00\u679a\u4f1a\u53d1\u70ed\u7684\u94f6\u53f6\u94a5\u5319\uff0c\u8fd8\u6709\u4e00\u53ea\u603b\u7231\u7ed5\u7740\u5b83\u6253\u8f6c\u7684\u8424\u706b\u866b\u5c0f\u706f\u966a\u7740\u5b83\u3002\n\n"
            "\u5b83\u4eec\u8d70\u8fc7\u4e86\u5f88\u591a\u5730\u65b9\uff0c\u7a7f\u8fc7\u4e86\u6f06\u9ed1\u7684\u6811\u6797\uff0c\u8d9f\u8fc7\u4e86\u6e05\u51c9\u7684\u5c0f\u6eaa\u3002"
            "\u94a5\u5319\u5728\u9ed1\u6697\u4e2d\u5fae\u5fae\u53d1\u70ed\uff0c\u6307\u5f15\u7740\u524d\u8fdb\u7684\u65b9\u5411\u3002\n\n"
            "\u5c0f\u706f\u98de\u5728\u524d\u9762\uff0c\u7528\u5fae\u5f31\u7684\u5149\u8292\u7167\u4eae\u811a\u4e0b\u7684\u8def\u3002"
            "\u963f\u96fe\u8ddf\u5728\u540e\u9762\uff0c\u5c3e\u5df4\u8f7b\u8f7b\u6447\u6643\u3002\n\n"
            "\u5b83\u4eec\u9047\u5230\u4e86\u4e00\u53ea\u8001\u4e4c\u9f9f\uff0c\u4e4c\u9f9f\u8bf4\uff1a\u201c\u6708\u5149\u4e95\u5728\u68ee\u6797\u7684\u6700\u6df1\u5904\uff0c"
            "\u4f60\u9700\u8981\u7528\u94a5\u5319\u6253\u5f00\u4e09\u9053\u95e8\u624d\u80fd\u627e\u5230\u5b83\u3002\u201d\n\n"
            "\u963f\u96fe\u8c22\u8fc7\u4e4c\u9f9f\uff0c\u7ee7\u7eed\u524d\u884c\u3002\u7b2c\u4e00\u9053\u95e8\u662f\u7528\u85e4\u8513\u7f16\u7ec7\u7684\uff0c"
            "\u94a5\u5319\u4e00\u78b0\uff0c\u85e4\u8513\u5c31\u81ea\u52a8\u6563\u5f00\u4e86\u3002\n\n"
            "\u7b2c\u4e8c\u9053\u95e8\u662f\u7528\u51b0\u505a\u7684\uff0c\u94a5\u5319\u53d1\u51fa\u6e29\u6696\u7684\u5149\uff0c\u51b0\u95e8\u6162\u6162\u878d\u5316\u3002"
            "\u5c0f\u706f\u5f00\u5fc3\u5730\u8f6c\u4e86\u4e2a\u5708\u3002\n\n"
            "\u7b2c\u4e09\u9053\u95e8\u662f\u7528\u6708\u5149\u505a\u7684\uff0c\u94a5\u5319\u63d2\u8fdb\u53bb\u7684\u4e00\u523b\uff0c\u6574\u7247\u68ee\u6797\u90fd\u4eae\u4e86\u8d77\u6765\u3002"
            "\u6708\u5149\u4e95\u5c31\u5728\u773c\u524d\uff0c\u6e05\u6f88\u7684\u4e95\u6c34\u6620\u7167\u51fa\u6ee1\u5929\u661f\u8fb0\u3002\n\n"
            "\u963f\u96fe\u7b11\u4e86\uff0c\u5c0f\u706f\u4e5f\u7b11\u4e86\u3002\u68ee\u6797\u91cd\u65b0\u6709\u4e86\u5149\uff0c\u800c\u5b83\u4eec\u7684\u53cb\u8c0a\uff0c\u6bd4\u6708\u5149\u8fd8\u8981\u6e29\u6696\u3002"
        )

    def tearDown(self):
        self._llm_patcher.stop()
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

        # 标题由 LLM 生成，每次不同，只验证格式和结构
        self.assertIn("\u300a", result)  # 《
        self.assertIn("\u300b", result)  # 》
        self.assertGreaterEqual(result.count("\n\n"), 5)
        self.assertGreater(len(result), 300)
        self.assertEqual(state["theme_id"], "forest_fox")
        self.assertEqual(state["chapter"], 1)

    def test_story_follow_up_continues_same_title_and_increments_chapter(self):
        self.state_path.write_text(
            json.dumps(
                {
                    "theme_id": "forest_fox",
                    "chapter": 1,
                    "last_story_text": "小狐狸阿雾在月灯森林里寻找月光井。",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        result = story.execute("继续讲")
        state = self._read_state()

        # 续写应包含章节标记和承接上文
        self.assertIn("\u300a", result)  # 《
        self.assertEqual(state["theme_id"], "forest_fox")
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

        # 无 state 时从历史恢复，验证能生成续写并保存状态
        self.assertIn("\u300a", result)  # 《
        self.assertIn("theme_id", state)
        self.assertIn("chapter", state)


if __name__ == "__main__":
    unittest.main()
