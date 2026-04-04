import unittest

from brain import think_helpers


class ThinkHelpersTests(unittest.TestCase):
    def test_detect_mode_with_skill_result_no_longer_uses_keyword_hybrid_promotion(self):
        prompt = "技能结果：已经找到资料\n\n陪我说说"
        self.assertEqual(think_helpers._detect_mode(prompt), "skill")

    def test_detect_emotion_is_retired_to_neutral(self):
        self.assertEqual(think_helpers._detect_emotion("whatever"), "neutral")
        self.assertEqual(think_helpers._detect_emotion(""), "neutral")


if __name__ == "__main__":
    unittest.main()
