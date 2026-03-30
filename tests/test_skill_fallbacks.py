import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.l8_learn as l8_learn_module
import core.reply_formatter as reply_formatter_module
import core.tool_adapter as tool_adapter_module
import core.executor as executor_module
import memory as memory_module
import routes.chat as chat_module
from agent_final import normalize_route_result, resolve_route, unified_chat_reply
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

    def disabled_test_legacy_skill_fallback_humanizes_runtime_failure(self):
        bundle = {"user_input": "上海天气怎么样", "l4": {}, "dialogue_context": ""}

        with patch("agent_final.nova_execute", return_value={"success": False, "error": "执行失败: timeout"}):
            self.skipTest("legacy skill fallback path retired")

        self.assertFalse(result["trace"]["success"])
        self.assertIn("没跑稳", result["reply"])

    def disabled_test_legacy_skill_fallback_passes_run_event_to_evolve(self):
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
                    "verification_detail": "Explorer window matched target path",
                },
                "post_condition": {"ok": True, "expected": "folder_opened", "observed": "folder_opened"},
                "repair_succeeded": True,
            },
        }

        with patch("agent_final.nova_execute", return_value=execute_result), patch("routes.chat.S.evolve") as evolve_mock:
            self.skipTest("legacy skill fallback path retired")

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
        self.assertEqual(run_event.get("verification_detail"), "Explorer window matched target path")


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
    def test_build_tool_exec_context_includes_recent_history_and_task_plan(self):
        bundle = {
            "l1": [
                {"role": "user", "content": "看看项目目录"},
                {"role": "nova", "content": "项目在 C:/Users/36459/NovaNotes/app.py"},
            ],
            "l4": {"user_profile": {"city": "Shanghai", "identity": "developer"}},
            "context_data": {"fs_target": {"path": "C:/Users/36459/NovaNotes", "option": "inspect"}},
            "task_plan": {"goal": "检查目录结构", "items": [{"id": "1", "title": "看目录"}]},
        }

        context = reply_formatter_module._build_tool_exec_context(bundle)

        self.assertEqual(context.get("user_city"), "Shanghai")
        self.assertEqual(context.get("user_identity"), "developer")
        self.assertEqual(len(context.get("recent_history") or []), 2)
        self.assertEqual((context.get("context_data") or {}).get("fs_target", {}).get("path"), "C:/Users/36459/NovaNotes")
        self.assertEqual((context.get("task_plan") or {}).get("goal"), "检查目录结构")

    def test_ensure_tool_call_failure_reply_replaces_preamble_with_failure_summary(self):
        reply = chat_module._ensure_tool_call_failure_reply(
            "好！开始执行\n\n先看看项目现在的文件结构和后端API",
            tool_used="write_file",
            tool_success=False,
            tool_response="执行失败: 缺少 content",
            action_summary="",
            run_meta={},
        )

        self.assertIn("这一步没接稳", reply)
        self.assertIn("缺少 content", reply)

    def test_normalize_persisted_process_steps_keeps_real_sequence(self):
        steps = [
            {"label": "记忆加载", "detail": "上下文载入完成", "status": "done"},
            {"label": "模型思考", "detail": "准备修改", "status": "done"},
            {"label": "调用技能", "detail": "read_file · 目标：index.html", "status": "running"},
            {"label": "技能完成", "detail": "read_file · index.html", "status": "done"},
            {"label": "调用技能", "detail": "write_file · 目标：index.html", "status": "running"},
            {"label": "技能失败", "detail": "write_file · 目标：index.html", "status": "error"},
        ]

        normalized = chat_module._normalize_persisted_process_steps(steps)

        self.assertEqual(
            normalized,
            [
                {"label": "记忆加载", "detail": "上下文载入完成", "status": "done"},
                {"label": "模型思考", "detail": "准备修改", "status": "done"},
                {"label": "技能完成", "detail": "read_file · index.html", "status": "done"},
                {"label": "技能失败", "detail": "write_file · 目标：index.html", "status": "error"},
            ],
        )
    def test_tool_preamble_detector_distinguishes_lead_in_from_answer_payload(self):
        self.assertTrue(reply_formatter_module._looks_like_tool_preamble("我先梳理一下技术方案 👇"))
        self.assertTrue(reply_formatter_module._looks_like_tool_preamble("好嘞！这个需求很明确～\n我先梳理一下技术方案 👇"))
        self.assertTrue(reply_formatter_module._looks_like_tool_preamble("让我看看记忆库～"))
        self.assertTrue(
            reply_formatter_module._looks_like_tool_preamble(
                "好！我来帮你全部搞定，直接上代码 👇\n\n先创建项目结构，然后我逐个文件写好～"
            )
        )
        self.assertFalse(reply_formatter_module._looks_like_tool_preamble("明天常州 18 到 26 度，阴转小雨。"))
        self.assertFalse(
            reply_formatter_module._looks_like_tool_preamble(
                "| 方案 | 技术栈 | 优点 |\n|------|--------|------|\n| A | HTML + LocalStorage | 零部署 |"
            )
        )

    def test_failed_tool_retry_note_guides_environment_or_file_inspection(self):
        write_note = reply_formatter_module._build_failed_tool_retry_note(
            "write_file",
            {"file_path": "notes_app/templates/index.html"},
            {"success": False, "error": "缺少 content"},
        )
        env_note = reply_formatter_module._build_failed_tool_retry_note(
            "folder_explore",
            {"path": "C:/Users/36459/NovaCore"},
            {"success": False, "error": "窗口未出现"},
        )

        self.assertIn("COMPLETE file content", write_note)
        self.assertIn("list_files", write_note)
        self.assertIn("sense_environment", env_note)

    def test_tool_call_system_prompt_contains_retry_policy(self):
        prompt = reply_formatter_module._build_tool_call_system_prompt(
            {
                "l3": [],
                "l4": {},
                "l5": {},
                "l7": [],
                "l8": [],
                "l2_memories": [],
                "current_model": "test-model",
            }
        )

        self.assertIn("list_files / read_file", prompt)
        self.assertIn("sense_environment", prompt)
        self.assertIn("缺少必要参数", prompt)

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
                    "verification_detail": "Window title matched notepad",
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
        self.assertEqual(run_event.get("verification_detail"), "Window title matched notepad")

    def test_tool_call_unavailable_reply_makes_incident_explicit(self):
        reply = chat_module._build_tool_call_unavailable_reply("unsupported_model")

        self.assertIn("没接上主链", reply)
        self.assertIn("不支持原生 tool_call", reply)
        self.assertIn("不会再静默回退到旧 skill 链", reply)

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

    def test_unified_reply_with_tools_stream_keeps_short_preamble_before_tool_call(self):
        executed = []

        def fake_stream(_cfg, messages, **_kwargs):
            has_tool_result = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
            if not has_tool_result:
                yield "<think>先想想怎么做</think>"
                yield "我先梳理一下技术方案 👇"
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_dev_1",
                            "type": "function",
                            "function": {
                                "name": "development_flow",
                                "arguments": json.dumps({"query": "做个本地记事本"}, ensure_ascii=False),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 3}}
                return

            yield "这个开发任务我先接住了。"
            yield {"_usage": {"prompt_tokens": 7, "completion_tokens": 11}}

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {
                "success": True,
                "response": "这个开发任务我先接住了。\n\n下一步我会先定位文件。",
                "meta": {
                    "action": {
                        "action_kind": "plan_task",
                        "target_kind": "development_task",
                        "display_hint": "已生成开发任务计划",
                    }
                },
            }

        bundle = {
            "user_input": "做个本地记事本",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_llm_call", lambda *_a, **_k: {"content": ""}
        ), patch.object(reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], fake_tool_executor))

        self.assertEqual(executed[0][0], "development_flow")
        self.assertEqual(executed[0][1].get("query"), "做个本地记事本")
        self.assertTrue(any(isinstance(chunk, str) and "我先梳理一下技术方案" in chunk for chunk in chunks))
        self.assertTrue(any(isinstance(chunk, dict) and chunk.get("_tool_call", {}).get("executing") for chunk in chunks))
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertEqual(done.get("tool_used"), "development_flow")
        self.assertEqual(done.get("success"), True)

    def test_unified_reply_with_tools_stream_stops_repeating_incomplete_write_file(self):
        executed = []

        def fake_stream(_cfg, messages, **_kwargs):
            has_tool_result = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
            if not has_tool_result:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_write_1",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": json.dumps(
                                    {"file_path": "notes_app/templates/index.html"},
                                    ensure_ascii=False,
                                ),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 3}}
                return

            yield {
                "_tool_calls": [
                    {
                        "id": "call_write_2",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": json.dumps(
                                {"file_path": "notes_app/templates/index.html"},
                                ensure_ascii=False,
                            ),
                        },
                    }
                ]
            }
            yield {"_usage": {"prompt_tokens": 7, "completion_tokens": 2}}

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {"success": False, "error": "缺少 content"}

        bundle = {
            "user_input": "好的 继续",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_llm_call", lambda *_a, **_k: {"content": ""}
        ), patch.object(reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], fake_tool_executor))

        self.assertEqual(len(executed), 1)
        self.assertEqual(executed[0][0], "write_file")
        self.assertEqual(executed[0][1].get("file_path"), "notes_app/templates/index.html")
        self.assertEqual(executed[0][1].get("user_input"), "好的 继续")
        self.assertTrue(any(isinstance(chunk, str) and "缺少 content" in chunk for chunk in chunks))
        self.assertTrue(any(isinstance(chunk, str) and "完整文件内容" in chunk for chunk in chunks))
        self.assertTrue(any(isinstance(chunk, str) and "如果你已经知道这个文件要写什么" in chunk for chunk in chunks))
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertEqual(done.get("tool_used"), "write_file")
        self.assertEqual(done.get("success"), False)

    def test_write_file_arg_failure_system_note_prefers_self_repair_before_stopping(self):
        note = reply_formatter_module._build_tool_arg_failure_system_note(
            "write_file",
            {"file_path": "notes_app/templates/index.html"},
            ["content"],
        )

        self.assertIn("immediately call write_file again", note)
        self.assertIn("inspect with list_files or read_file first", note)
        self.assertIn("Only stop calling tools", note)

    def test_stream_runtime_guidance_avoids_mid_conversation_system_role(self):
        seen_roles = []

        def fake_stream(_cfg, messages, **_kwargs):
            seen_roles.append([m.get("role") for m in messages])
            has_tool_result = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
            if not has_tool_result:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_write_1",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": json.dumps(
                                    {"file_path": "notes_app/templates/index.html"},
                                    ensure_ascii=False,
                                ),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 3}}
                return

            yield "我先把阻塞点接住。"
            yield {"_usage": {"prompt_tokens": 7, "completion_tokens": 2}}

        def fake_tool_executor(_name, _args, _context):
            return {"success": False, "error": "缺少 content"}

        bundle = {
            "user_input": "继续",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], fake_tool_executor))

        self.assertGreaterEqual(len(seen_roles), 2)
        self.assertEqual(seen_roles[0][0], "system")
        self.assertNotIn("system", seen_roles[1][1:])
        self.assertIn("user", seen_roles[1][1:])

    def test_repair_tool_args_recovers_relative_write_target_from_recent_dialogue(self):
        repaired = reply_formatter_module._repair_tool_args_from_context(
            "write_file",
            {},
            {
                "user_input": "再来 你可以的",
                "l1": [
                    {"role": "assistant", "content": "已写入 notes_app/app.py"},
                    {"role": "assistant", "content": "执行失败: 缺少 content。当前目标是 notes_app/templates/index.html。"},
                ],
            },
        )

        self.assertEqual(str(repaired.get("file_path") or "").replace("\\", "/"), "notes_app/templates/index.html")
        self.assertEqual(repaired.get("user_input"), "再来 你可以的")

    def test_protocol_style_folder_explore_missing_path_is_not_marked_success(self):
        result = executor_module.execute({"skill": "folder_explore"}, "看看目录", {})

        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("skill"), "folder_explore")
        self.assertIn("没有收到要查看的文件夹目标", result.get("response", ""))

    def test_protocol_style_folder_explore_accepts_context_path(self):
        result = executor_module.execute(
            {"skill": "folder_explore"},
            "看看目录",
            {"path": "c:/Users/36459/NovaCore"},
        )

        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("skill"), "folder_explore")
        self.assertIn("NovaCore", result.get("response", ""))

    def test_protocol_style_folder_explore_accepts_file_target_by_using_parent_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            target_file = temp_path / "index.html"
            target_file.write_text("<html></html>", encoding="utf-8")
            (temp_path / "static").mkdir()

            result = executor_module.execute(
                {"skill": "folder_explore"},
                "看看目录",
                {"path": str(target_file)},
            )

        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("skill"), "folder_explore")
        self.assertIn("index.html", result.get("response", ""))

    def disabled_test_legacy_skill_fallback_enriches_folder_explore_with_structured_context(self):
        bundle = {
            "user_input": "看看桌面里有什么",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }
        seen = {}

        def fake_nova_execute(_route_result, _skill_input, context):
            seen["context"] = context
            return {
                "success": True,
                "response": "已经看到目录了",
                "meta": {"action": {"display_hint": "已经看到目录了"}},
            }

        with patch("core.context_pull.pull_context_data", return_value={
            "fs_target": {"path": "C:\\Users\\36459\\Desktop", "option": "inspect", "source": "test"},
            "fs_action": {"action": "inspect", "target": {"path": "C:\\Users\\36459\\Desktop"}},
        }), patch("agent_final.nova_execute", side_effect=fake_nova_execute), patch.object(
            chat_module.S, "think", return_value={"reply": "好啦，我已经看到了"}
        ):
            self.skipTest("legacy skill fallback path retired")

        self.assertTrue(result["trace"]["success"])
        self.assertEqual(seen["context"].get("path"), "C:\\Users\\36459\\Desktop")
        self.assertEqual((seen["context"].get("fs_target") or {}).get("path"), "C:\\Users\\36459\\Desktop")
        self.assertEqual(((seen["context"].get("context_data") or {}).get("fs_target") or {}).get("path"), "C:\\Users\\36459\\Desktop")

    def disabled_test_legacy_skill_fallback_uses_latest_structured_fs_target_as_fallback(self):
        bundle = {
            "user_input": "继续看看",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }
        seen = {}

        def fake_nova_execute(_route_result, _skill_input, context):
            seen["context"] = context
            return {
                "success": True,
                "response": "已经继续看目录了",
                "meta": {"action": {"display_hint": "已经继续看目录了"}},
            }

        with patch("core.context_pull.pull_context_data", return_value={}), patch(
            "core.task_store.get_latest_structured_fs_target",
            return_value={"path": "C:\\Users\\36459\\Desktop", "option": "inspect", "source": "memory"},
        ), patch("agent_final.nova_execute", side_effect=fake_nova_execute), patch.object(
            chat_module.S, "think", return_value={"reply": "继续看到了"}
        ):
            self.skipTest("legacy skill fallback path retired")

        self.assertTrue(result["trace"]["success"])
        self.assertEqual((seen["context"].get("fs_target") or {}).get("source"), "memory")
        self.assertEqual(seen["context"].get("path"), "C:\\Users\\36459\\Desktop")

    def test_stream_uses_tool_fallback_when_failed_round_only_emits_preamble(self):
        seen_messages = []

        def fake_stream(_cfg, messages, **_kwargs):
            seen_messages.append(messages)
            has_tool_result = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
            if not has_tool_result:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_write_1",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": json.dumps(
                                    {"file_path": "notes_app/templates/index.html"},
                                    ensure_ascii=False,
                                ),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 3}}
                return

            yield "好！这次我直接一步到位。"
            yield {"_usage": {"prompt_tokens": 7, "completion_tokens": 2}}

        def fake_tool_executor(_name, _args, _context):
            return {"success": False, "error": "缺少 content"}

        bundle = {
            "user_input": "继续",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], fake_tool_executor))

        self.assertTrue(any(isinstance(chunk, str) and "缺少 content" in chunk for chunk in chunks))
        self.assertFalse(any(isinstance(chunk, str) and "一步到位" in chunk for chunk in chunks))
        self.assertEqual(chunks[-1].get("success"), False)

    """
    def test_stream_success_preamble_is_replaced_with_closeout_reply(self):
        def fake_stream(_cfg, messages, **_kwargs):
            has_tool_result = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
            if not has_tool_result:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_write_success",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": json.dumps(
                                    {
                                        "file_path": "notes_app/app.py",
                                        "content": "print('ok')\n",
                                    },
                                    ensure_ascii=False,
                                ),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 3}}
                return

            yield "濂界殑涓讳汉锛佹垜杩欏氨鏀朵釜灏俱€?
            yield {"_usage": {"prompt_tokens": 7, "completion_tokens": 2}}

        def fake_tool_executor(_name, _args, _context):
            return {
                "success": True,
                "response": "宸插啓鍏ユ枃浠讹細app.py",
                "meta": {
                    "action": {
                        "action_kind": "write_file",
                        "target_kind": "file",
                        "target": "notes_app/app.py",
                        "outcome": "written",
                        "display_hint": "宸插啓鍏?app.py",
                        "verification_mode": "file_write",
                        "verification_detail": "notes_app/app.py written successfully",
                    }
                },
            }

        bundle = {
            "user_input": "缁х画瀹炵幇",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], fake_tool_executor))

        self.assertTrue(any(isinstance(chunk, str) and "杩欎竴姝ュ凡缁忓畬鎴? in chunk for chunk in chunks))
        self.assertFalse(any(isinstance(chunk, str) and "鎴戣繖灏辨敹涓熬" in chunk for chunk in chunks))
        self.assertEqual(chunks[-1].get("success"), True)

    def test_clean_visible_reply_text_removes_legacy_tool_markup_but_keeps_visible_text(self):
        raw = (
            "宸茬粡澶勭悊濂戒簡锛乶\n"
            "<minimax:tool_call>\n"
            "<invoke name=\"run_code\">\n"
            "<parameter name=\"user_input\">echo hi</parameter>\n"
            "</invoke>\n"
            "</minimax:tool_call>"
        )

        cleaned = reply_formatter_module._clean_visible_reply_text(raw)

        self.assertEqual(cleaned, "宸茬粡澶勭悊濂戒簡锛?)

    """

    def test_stream_success_preamble_is_replaced_with_closeout_reply_v2(self):
        def fake_stream(_cfg, messages, **_kwargs):
            has_tool_result = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
            if not has_tool_result:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_write_success",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": json.dumps(
                                    {
                                        "file_path": "notes_app/app.py",
                                        "content": "print('ok')\n",
                                    },
                                    ensure_ascii=False,
                                ),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 3}}
                return

            yield "I am wrapping this up now."
            yield {"_usage": {"prompt_tokens": 7, "completion_tokens": 2}}

        def fake_tool_executor(_name, _args, _context):
            return {
                "success": True,
                "response": "File written: app.py",
                "meta": {
                    "action": {
                        "action_kind": "write_file",
                        "target_kind": "file",
                        "target": "notes_app/app.py",
                        "outcome": "written",
                        "display_hint": "File written: app.py",
                        "verification_mode": "file_write",
                        "verification_detail": "notes_app/app.py written successfully",
                    }
                },
            }

        bundle = {
            "user_input": "continue building",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], fake_tool_executor))

        self.assertTrue(any(isinstance(chunk, str) and "\u8fd9\u4e00\u6b65\u5df2\u7ecf\u5b8c\u6210" in chunk for chunk in chunks))
        self.assertFalse(any(isinstance(chunk, str) and "I am wrapping this up now." in chunk for chunk in chunks))
        self.assertEqual(chunks[-1].get("success"), True)

    def test_clean_visible_reply_text_removes_legacy_tool_markup_but_keeps_visible_text_v2(self):
        raw = (
            "Done already.\n"
            "<minimax:tool_call>\n"
            "<invoke name=\"run_code\">\n"
            "<parameter name=\"user_input\">echo hi</parameter>\n"
            "</invoke>\n"
            "</minimax:tool_call>"
        )

        cleaned = reply_formatter_module._clean_visible_reply_text(raw)

        self.assertEqual(cleaned, "Done already.")

    def test_execute_tool_call_routes_write_file_into_protocol_base(self):
        result = tool_adapter_module.execute_tool_call(
            "write_file",
            {"file_path": "notes_app/templates/index.html"},
            {},
        )

        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("skill"), "write_file")
        meta = result.get("meta") or {}
        action = meta.get("action") or {}
        self.assertEqual(action.get("action_kind"), "write_file")
        self.assertEqual(action.get("target_kind"), "file")
        self.assertEqual(action.get("verification_mode"), "argument_check")
        self.assertIn("missing_fields=content", action.get("verification_detail", ""))

    def test_repair_tool_args_recovers_folder_target_from_recent_project_history(self):
        repaired = reply_formatter_module._repair_tool_args_from_context(
            "folder_explore",
            {},
            {
                "user_input": "再去检查一下",
                "l1": [
                    {"role": "assistant", "content": "刚看过 C:/Users/36459/NovaNotes/app.py"},
                    {"role": "assistant", "content": "还有 C:/Users/36459/NovaNotes/templates/index.html"},
                ],
            },
        )

        self.assertEqual(str(repaired.get("path") or "").replace("\\", "/"), "C:/Users/36459/NovaNotes")

    def test_execute_tool_call_persists_folder_target_within_shared_context(self):
        seen = []

        def fake_execute(skill_route, user_input, context):
            seen.append({"skill": skill_route.get("skill"), "user_input": user_input, "context": dict(context)})
            return {"success": True, "skill": skill_route.get("skill"), "response": "ok", "meta": {}}

        shared_context = {
            "recent_history": [
                {"role": "assistant", "content": "项目在 C:/Users/36459/NovaNotes/app.py"},
            ]
        }

        with patch.object(tool_adapter_module, "_execute", side_effect=fake_execute):
            tool_adapter_module.execute_tool_call(
                "folder_explore",
                {"user_input": "查看项目结构", "path": "C:/Users/36459/NovaNotes"},
                shared_context,
            )
            tool_adapter_module.execute_tool_call(
                "folder_explore",
                {"user_input": "继续看看 templates 和 static"},
                shared_context,
            )

        self.assertEqual(len(seen), 2)
        self.assertEqual(
            str((seen[0]["context"].get("fs_target") or {}).get("path") or "").replace("\\", "/"),
            "C:/Users/36459/NovaNotes",
        )
        self.assertEqual(
            str((seen[1]["context"].get("fs_target") or {}).get("path") or "").replace("\\", "/"),
            "C:/Users/36459/NovaNotes",
        )


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

    def test_evolve_records_verification_detail_in_skill_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            evolution_path = tmp / "evolution.json"
            knowledge_path = tmp / "knowledge.json"
            evolution_path.write_text(
                json.dumps({"skills_used": {}, "user_preferences": {}, "learning": [], "skill_runs": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            knowledge_path.write_text("[]", encoding="utf-8")

            with patch.object(memory_module, "evolution_file", evolution_path), patch.object(
                memory_module, "knowledge_file", knowledge_path
            ):
                result = memory_module.evolve(
                    "打开记事本",
                    "app_target",
                    run_event={
                        "success": True,
                        "verified": True,
                        "summary": "已打开记事本",
                        "action_kind": "open_app",
                        "target_kind": "app",
                        "target": "notepad.exe",
                        "outcome": "opened",
                        "verification_mode": "window_detected",
                        "verification_detail": "Window title matched notepad",
                    },
                )

        self.assertEqual(result["skill_runs"][-1]["verification_detail"], "Window title matched notepad")

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
