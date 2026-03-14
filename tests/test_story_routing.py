import unittest

from agent_final import detect_story_follow_up_route


class StoryRoutingTests(unittest.TestCase):
    def test_detect_story_follow_up_route_uses_recent_story_title(self):
        bundle = {
            "user_input": "然后呢",
            "l2": [
                {"role": "user", "content": "讲个故事"},
                {"role": "nova", "content": "《月灯森林的最后一把钥匙》\n\n小狐狸阿雾在月灯森林里……"},
            ],
        }

        route = detect_story_follow_up_route(bundle)

        self.assertIsNotNone(route)
        self.assertEqual(route["mode"], "skill")
        self.assertEqual(route["skill"], "story")
        self.assertEqual(route["source"], "context")

    def test_detect_story_follow_up_route_ignores_non_story_context(self):
        bundle = {
            "user_input": "然后呢",
            "l2": [
                {"role": "user", "content": "查一下天气"},
                {"role": "nova", "content": "上海今天 18°C，多云。"},
            ],
        }

        route = detect_story_follow_up_route(bundle)

        self.assertIsNone(route)


if __name__ == "__main__":
    unittest.main()
