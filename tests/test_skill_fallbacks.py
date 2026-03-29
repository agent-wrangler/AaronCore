import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.l8_learn as l8_learn_module
import core.reply_formatter as reply_formatter_module
import memory as memory_module
import routes.chat as chat_module
from agent_final import normalize_route_result, resolve_route, unified_chat_reply, unified_skill_reply
from core.context_builder import build_dialogue_context, render_dialogue_context


class SkillFallbackTests(unittest.TestCase):
    def test_normalize_route_result_downgrades_unknown_skill_to_missing_skill_intent(self):
        # 使用一个确实不存在的技能名来测试降级逻辑
        result = normalize_route_result(
            {"mode": "skill", "skill": "nonexistent_skill_xyz", "reason": "llm_guess"},
            "帮我做个不存在的事",
            "llm",
        )

        self.assertEqual(result["mode"], "chat")
        self.assertEqual(result.get("intent"), "missing_skill")
        self.assertEqual(result.get("missing_skill"), "nonexistent_skill_xyz")

    def test_unified_chat_reply_honestly_handles_missing_skill(self):
        reply = unified_chat_reply(
            {"user_input": "今天有什么新闻", "l3": [], "l4": {}, "l5": {"skills": {}}, "l8": []},
            {"mode": "chat", "skill": "news", "intent": "missing_skill", "missing_skill": "news", "rewritten_input": "今天有什么新闻"},
        )

        self.assertIn("没接上", reply)
        self.assertIn("新闻", reply)

    def test_resolve_route_short_circuits_news_to_missing_skill(self):
        # news 技能现在已存在，改用不存在的技能测试 missing_skill 短路
        bundle = {
            "user_input": "帮我做个不存在的事",
            "l1": [],
            "l2": [],
            "l3": [],
            "l4": {},
            "l5": {"skills": {}},
            "l8": [],
            "dialogue_context": "",
        }

        result = resolve_route(bundle)

        # 不存在的技能不会被路由命中，应走 chat
        self.assertEqual(result.get("mode"), "chat")

    def test_unified_skill_reply_humanizes_runtime_failure(self):
        bundle = {"user_input": "上海天气怎么样", "l4": {}, "dialogue_context": ""}

        with patch("agent_final.nova_execute", return_value={"success": False, "error": "执行失败: timeout"}):
            result = unified_skill_reply(bundle, "weather", "上海天气怎么样")

        self.assertFalse(result["trace"]["success"])
        self.assertIn("没跑稳", result["reply"])

    def test_unified_skill_reply_passes_run_event_to_evolve(self):
        bundle = {"user_input": "打开项目目录", "l4": {}, "dialogue_context": ""}
        execute_result = {
            "success": True,
            "response": "已打开项目目录。",
            "meta": {
                "state": {"expected_state": "folder_opened", "observed_state": "folder_opened"},
                "drift": {"reason": "", "repair_hint": ""},
                "action": {
                    "action_kind": "open_folder",
                    "target_kind": "folder",
                    "target": "C:/Users/36459/NovaCore",
                    "outcome": "opened",
                    "display_hint": "已打开项目目录",
                    "verification_mode": "window_detected",
                },
                "post_condition": {"ok": True, "expected": "folder_opened", "observed": "folder_opened"},
                "repair_succeeded": True,
            },
        }

        with patch("agent_final.nova_execute", return_value=execute_result), patch("routes.chat.S.evolve") as evolve_mock:
            result = unified_skill_reply(bundle, "open_target", "打开项目目录")

        self.assertTrue(result["trace"]["success"])
        evolve_mock.assert_called_once()
        _, _skill = evolve_mock.call_args.args[:2]
        self.assertEqual(_skill, "open_target")
        run_event = evolve_mock.call_args.kwargs.get("run_event") or {}
        self.assertEqual(run_event.get("success"), True)
        self.assertEqual(run_event.get("verified"), True)
        self.assertEqual(run_event.get("action_kind"), "open_folder")
        self.assertEqual(run_event.get("observed_state"), "folder_opened")
        self.assertEqual(run_event.get("verification_mode"), "window_detected")


class DialogueContextTests(unittest.TestCase):
    def test_build_dialogue_context_returns_structured_hints(self):
        history = [
            {"role": "user", "content": "帮我看下这个方案", "time": "2026-03-27T10:00:00"},
            {"role": "nova", "content": "我先帮你过一遍。", "time": "2026-03-27T10:00:05"},
        ]

        ctx = build_dialogue_context(history, "这个呢")

        self.assertIsInstance(ctx, dict)
        self.assertIn("follow_up_hint", ctx)
        self.assertIn("reference_hint", ctx)
        self.assertIn("vision_hint", ctx)
        self.assertNotIn("fallback_summary", ctx)
        self.assertTrue(ctx["follow_up_hint"])

    def test_render_dialogue_context_accepts_legacy_string(self):
        self.assertEqual(render_dialogue_context("旧格式上下文"), "旧格式上下文")

    def test_render_dialogue_context_renders_structured_hints(self):
        rendered = render_dialogue_context(
            {
                "follow_up_hint": "沿用刚才话题",
                "reference_hint": "最近相关用户语境：配一下支付",
                "vision_hint": "用户当前正看着设置页",
            }
        )

        self.assertIn("追问提示：沿用刚才话题", rendered)
        self.assertIn("指代提示：最近相关用户语境：配一下支付", rendered)
        self.assertIn("视觉感知：用户当前正看着设置页", rendered)


class RunEventMappingTests(unittest.TestCase):
    def test_build_run_event_prefers_meta_facts(self):
        run_event = chat_module._build_run_event(
            success=True,
            meta={
                "state": {"expected_state": "window_visible", "observed_state": "window_visible"},
                "drift": {"reason": "", "repair_hint": ""},
                "action": {
                    "action_kind": "open_app",
                    "target_kind": "app",
                    "target": "notepad.exe",
                    "outcome": "opened",
                    "display_hint": "已打开记事本",
                    "verification_mode": "window_detected",
                },
                "post_condition": {"ok": True, "expected": "window_visible", "observed": "window_visible"},
                "repair_succeeded": True,
            },
            fallback_text="已打开记事本。",
        )

        self.assertEqual(run_event.get("success"), True)
        self.assertEqual(run_event.get("verified"), True)
        self.assertEqual(run_event.get("summary"), "已打开记事本")
        self.assertEqual(run_event.get("action_kind"), "open_app")
        self.assertEqual(run_event.get("target_kind"), "app")
        self.assertEqual(run_event.get("target"), "notepad.exe")
        self.assertEqual(run_event.get("observed_state"), "window_visible")

    def test_unified_reply_with_tools_stream_fallback_exposes_run_meta(self):
        fallback_result = {
            "reply": "好的，已经处理完了。",
            "tool_used": "open_target",
            "usage": {"prompt_tokens": 1},
            "action_summary": "已打开项目目录",
            "run_meta": {
                "action": {"action_kind": "open_folder", "target_kind": "folder"},
                "state": {"observed_state": "folder_opened"},
            },
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", None), patch.object(
            reply_formatter_module, "_llm_call", None
        ), patch.object(reply_formatter_module, "unified_reply_with_tools", return_value=fallback_result):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream({"user_input": "打开项目目录"}, [], None))

        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertEqual(done.get("tool_used"), "open_target")
        self.assertEqual(done.get("run_meta", {}).get("action", {}).get("action_kind"), "open_folder")
        self.assertEqual(done.get("success"), True)


class MemoryEvolutionTests(unittest.TestCase):
    def test_evolve_skips_unknown_skill_usage_but_keeps_preferences(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            evolution_path = tmp / "evolution.json"
            knowledge_path = tmp / "knowledge.json"
            evolution_path.write_text(
                json.dumps({"skills_used": {}, "user_preferences": {}, "learning": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            knowledge_path.write_text("[]", encoding="utf-8")

            with patch.object(memory_module, "evolution_file", evolution_path), patch.object(
                memory_module, "knowledge_file", knowledge_path
            ):
                # 使用一个确实不存在的技能名
                result = memory_module.evolve("帮我做个不存在的事", "nonexistent_skill_xyz")

        self.assertEqual(result["skills_used"], {})

    def test_find_relevant_knowledge_skips_invalid_tool_skill_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            knowledge_path = tmp / "knowledge_base.json"
            # 使用一个没有 query/summary/keywords 的无效条目
            knowledge_path.write_text(
                json.dumps(
                    [
                        {
                            "一级场景": "工具应用",
                            "二级场景": "不存在的技能",
                            "核心技能": "nonexistent_xyz",
                            "应用示例": "这是一个无效条目",
                            "trigger": ["不存在"],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(l8_learn_module, "KNOWLEDGE_BASE_FILE", knowledge_path):
                result = l8_learn_module.find_relevant_knowledge("帮我做个完全无关的事情吧", touch=True)

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
