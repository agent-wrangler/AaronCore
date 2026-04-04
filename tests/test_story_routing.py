import unittest

from agent_final import resolve_route


class StoryRoutingTests(unittest.TestCase):
    def test_resolve_route_keeps_story_follow_up_as_chat(self):
        bundle = {
            "user_input": "然后呢",
            "l2": [
                {"role": "user", "content": "讲个故事"},
                {"role": "nova", "content": "《月灯森林的最后一把钥匙》\n\n小狐狸阿雾在月灯森林里……"},
            ],
        }

        route = resolve_route(bundle)

        self.assertEqual(route["mode"], "chat")
        self.assertEqual(route["skill"], "none")

    def test_resolve_route_stays_chat_for_non_story_context(self):
        bundle = {
            "user_input": "然后呢",
            "l2": [
                {"role": "user", "content": "查一下天气"},
                {"role": "nova", "content": "上海今天 18°C，多云。"},
            ],
        }

        route = resolve_route(bundle)

        self.assertEqual(route["mode"], "chat")
        self.assertEqual(route["skill"], "none")


if __name__ == "__main__":
    unittest.main()
