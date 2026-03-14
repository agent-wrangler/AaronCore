import unittest
from unittest.mock import patch

from agent_final import resolve_route, unified_chat_reply
from core.router import route


class CapabilityRoutingTests(unittest.TestCase):
    def test_router_treats_meta_bug_report_as_chat(self):
        result = route("检查下这个路径 只要对话里出现代码就会出现个小游戏到窗口。感觉有问题")

        self.assertEqual(result["mode"], "chat")
        self.assertIsNone(result["skill"])
        self.assertEqual(result.get("intent"), "meta_bug_report")
        self.assertGreaterEqual(float(result.get("confidence", 0)), 0.95)

    def test_router_treats_game_misfire_complaint_as_chat(self):
        result = route("怎么又给搞了个小游戏 这有点尴尬啊，像是流程错了吧")

        self.assertEqual(result["mode"], "chat")
        self.assertIsNone(result["skill"])
        self.assertEqual(result.get("intent"), "meta_bug_report")

    def test_router_treats_answer_correction_as_chat(self):
        result = route("不是 我刚才说的不是这个 你发天气之前")

        self.assertEqual(result["mode"], "chat")
        self.assertIsNone(result["skill"])
        self.assertEqual(result.get("intent"), "answer_correction")
        self.assertGreaterEqual(float(result.get("confidence", 0)), 0.95)

    def test_router_treats_look_at_my_question_correction_as_chat(self):
        result = route("你又犯傻了 看我问的什么是啊")

        self.assertEqual(result["mode"], "chat")
        self.assertIsNone(result["skill"])
        self.assertEqual(result.get("intent"), "answer_correction")

    def test_router_treats_self_repair_question_as_chat(self):
        result = route("你自己什么时候会修改自己的代码就好了，发现自己错了会自己修正吗")

        self.assertEqual(result["mode"], "chat")
        self.assertIsNone(result["skill"])
        self.assertEqual(result.get("intent"), "self_repair_capability")
        self.assertGreaterEqual(float(result.get("confidence", 0)), 0.95)

    def test_router_treats_ability_query_as_chat(self):
        result = route("你现在能做什么")

        self.assertEqual(result["mode"], "chat")
        self.assertIsNone(result["skill"])
        self.assertEqual(result.get("intent"), "ability_capability")

    def test_router_still_routes_explicit_game_request_to_run_code(self):
        result = route("写个游戏")

        self.assertEqual(result["mode"], "skill")
        self.assertEqual(result["skill"], "run_code")

    def test_resolve_route_keeps_high_confidence_capability_chat(self):
        bundle = {"user_input": "你自己什么时候会修改自己的代码", "l2": []}
        core_result = {
            "mode": "chat",
            "skill": None,
            "confidence": 0.97,
            "reason": "命中自修正能力提问",
            "intent": "self_repair_capability",
        }

        with patch("agent_final.nova_route", return_value=core_result), patch(
            "agent_final.llm_route",
            return_value={"mode": "skill", "skill": "run_code", "reason": "llm_override"},
        ):
            result = resolve_route(bundle)

        self.assertEqual(result["mode"], "chat")
        self.assertEqual(result.get("intent"), "self_repair_capability")

    def test_unified_chat_reply_answers_self_repair_capability_directly(self):
        reply = unified_chat_reply(
            {"user_input": "你能不能自己修自己的代码", "l3": [], "l4": {}, "l5": {"skills": {}}, "l8": []},
            {"mode": "chat", "skill": "none", "intent": "self_repair_capability"},
        )

        self.assertIn("尝试落补丁", reply)
        self.assertIn("修正提案", reply)
        self.assertIn("自动回滚", reply)


    def test_unified_chat_reply_answers_meta_bug_report_directly(self):
        reply = unified_chat_reply(
            {"user_input": "检查下这个路径 只要对话里出现代码就会出现个小游戏到窗口。感觉有问题", "l3": [], "l4": {}, "l5": {"skills": {}}, "l8": []},
            {"mode": "chat", "skill": "none", "intent": "meta_bug_report"},
        )

        self.assertIn("排查模式", reply)
        self.assertIn("修复提案", reply)

    def test_unified_chat_reply_answers_answer_correction_directly(self):
        reply = unified_chat_reply(
            {"user_input": "不是 我刚才说的不是这个 你发天气之前", "l3": [], "l4": {}, "l5": {"skills": {}}, "l8": []},
            {"mode": "chat", "skill": "none", "intent": "answer_correction"},
        )

        self.assertIn("纠正我上一轮答偏", reply)
        self.assertIn("天气", reply)


if __name__ == "__main__":
    unittest.main()
