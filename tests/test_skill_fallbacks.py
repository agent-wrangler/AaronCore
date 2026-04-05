import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.l8_learn as l8_learn_module
import core.reply_formatter as reply_formatter_module
import core.tool_adapter as tool_adapter_module
import core.executor as executor_module
import core.fs_protocol as fs_protocol_module
import core.target_protocol as target_protocol_module
import memory as memory_module
import routes.chat as chat_module
from agent_final import normalize_route_result, resolve_route, unified_chat_reply
from core.context_builder import build_dialogue_context, render_dialogue_context


class SkillFallbackTests(unittest.TestCase):
    def test_normalize_persisted_process_steps_keeps_running_steps_as_done(self):
        steps = chat_module._normalize_persisted_process_steps(
            [
                {"label": "模型思考", "detail": "我先理解你的问题", "status": "running"},
                {"label": "调用技能", "detail": "folder_explore", "status": "done"},
            ]
        )

        self.assertEqual(
            steps,
            [
                {"label": "模型思考", "detail": "我先理解你的问题", "status": "done"},
                {"label": "调用技能", "detail": "folder_explore", "status": "done"},
            ],
        )

    def test_trim_collected_steps_for_stream_reset_keeps_only_stable_prefix(self):
        steps = [
            {"label": "记忆加载", "detail": "上下文载入完成", "status": "done", "phase": "info"},
            {"label": "模型思考", "detail": "我先看一下", "status": "done", "phase": "thinking"},
            {"label": "调用技能", "detail": "folder_explore", "status": "done", "phase": "tool"},
        ]

        trimmed = chat_module._trim_collected_steps_for_stream_reset(steps, keep_prefix_count=1)

        self.assertEqual(
            trimmed,
            [
                {"label": "记忆加载", "detail": "上下文载入完成", "status": "done", "phase": "info"},
            ],
        )

    def test_block_task_plan_after_failure_marks_current_item_blocked(self):
        plan = {
            "goal": "改进 NovaNotes 前端",
            "phase": "1",
            "summary": "改进 NovaNotes 前端",
            "items": [
                {"id": "1", "title": "重写 index.html", "status": "running", "detail": ""},
                {"id": "2", "title": "测试 Flask", "status": "pending", "detail": ""},
            ],
            "current_item_id": "1",
        }

        with patch("core.task_store.save_task_plan_snapshot", return_value=({}, None)):
            blocked = chat_module._block_task_plan_after_failure(
                plan,
                goal_hint="改进 NovaNotes 前端",
                tool_used="write_file",
                action_summary="目标：C:/Users/36459/NovaNotes/templates/index.html",
                tool_response="执行失败: 缺少 content。",
            )

        self.assertEqual(blocked.get("phase"), "blocked")
        self.assertEqual(blocked.get("current_item_id"), "1")
        self.assertEqual((blocked.get("items") or [])[0].get("status"), "blocked")
        self.assertIn("write_file", (blocked.get("summary") or ""))
        self.assertIn("缺少 content", ((blocked.get("items") or [])[0].get("detail") or ""))

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

    def test_unified_chat_reply_no_longer_uses_news_keywords_without_missing_skill_signal(self):
        reply = unified_chat_reply(
            {"user_input": "今天有什么新闻", "l3": [], "l4": {}, "l5": {"skills": {}}, "l8": []},
            {"mode": "chat", "skill": "nonexistent_skill_xyz", "intent": "missing_skill", "missing_skill": "nonexistent_skill_xyz", "rewritten_input": "今天有什么新闻"},
        )

        self.assertIn("没接上", reply)
        self.assertNotIn("不乱报", reply)

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


class StreamThinkFilterTests(unittest.TestCase):
    def test_consume_think_filtered_stream_text_suppresses_mid_reply_think_blocks(self):
        chunks = [
            "Draft answer. <th",
            "ink>The user is asking again.",
            "</thi",
            "nk>Final answer.",
        ]

        visible_parts = []
        carry = ""
        in_think = False

        for chunk in chunks:
            emitted, carry, in_think, _saw_think = chat_module._consume_think_filtered_stream_text(
                carry,
                chunk,
                in_think=in_think,
            )
            visible_parts.extend(emitted)

        emitted, carry, in_think, _saw_think = chat_module._consume_think_filtered_stream_text(
            carry,
            "",
            in_think=in_think,
            end_of_stream=True,
        )
        visible_parts.extend(emitted)

        self.assertEqual("".join(visible_parts), "Draft answer. Final answer.")
        self.assertEqual(carry, "")
        self.assertFalse(in_think)

    def test_reset_stream_visible_state_discards_buffered_tail_before_retry(self):
        stream_chunks = []
        carry = ""
        in_think = False

        emitted, carry, in_think, _saw_think = chat_module._consume_think_filtered_stream_text(
            carry,
            "I will update the file directly now.",
            in_think=in_think,
        )
        stream_chunks.extend(emitted)

        dropped_text, carry, in_think = chat_module._reset_stream_visible_state(stream_chunks, carry)

        self.assertEqual(dropped_text, "I will update the file directly now.")
        self.assertEqual(stream_chunks, [])
        self.assertEqual(carry, "")
        self.assertFalse(in_think)

        visible_parts = []
        emitted, carry, in_think, _saw_think = chat_module._consume_think_filtered_stream_text(
            carry,
            "File updated.",
            in_think=in_think,
        )
        visible_parts.extend(emitted)
        emitted, carry, in_think, _saw_think = chat_module._consume_think_filtered_stream_text(
            carry,
            "",
            in_think=in_think,
            end_of_stream=True,
        )
        visible_parts.extend(emitted)

        self.assertEqual("".join(visible_parts), "File updated.")


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
        self.assertEqual(ctx["follow_up_hint"], "")
        self.assertEqual(ctx["reference_hint"], "")

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
    def test_normalize_persisted_process_steps_merges_parallel_group_updates(self):
        steps = [
            {
                "label": "并行调用",
                "detail": "这一批同时起跑 2 个工具：folder_explore、search_text",
                "status": "done",
                "step_key": "parallel:1:1:call_parallel_fast",
                "phase": "tool",
                "parallel_group_id": "parallel:1:1:call_parallel_fast",
                "parallel_size": 2,
                "parallel_tools": ["folder_explore", "search_text"],
            },
            {
                "label": "并行执行中",
                "detail": "2 个工具同时在跑，已收回 1/2",
                "status": "running",
                "step_key": "parallel:1:1:call_parallel_fast",
                "phase": "tool",
                "parallel_group_id": "parallel:1:1:call_parallel_fast",
                "parallel_size": 2,
                "parallel_completed_count": 1,
                "parallel_success_count": 1,
                "parallel_tools": ["folder_explore", "search_text"],
            },
            {
                "label": "并行完成",
                "detail": "2 个工具已经收口",
                "status": "done",
                "step_key": "parallel:1:1:call_parallel_fast",
                "phase": "tool",
                "parallel_group_id": "parallel:1:1:call_parallel_fast",
                "parallel_size": 2,
                "parallel_completed_count": 2,
                "parallel_success_count": 2,
                "parallel_tools": ["folder_explore", "search_text"],
            },
        ]

        normalized = chat_module._normalize_persisted_process_steps(steps)

        self.assertEqual(
            normalized,
            [
                {
                    "label": "并行完成",
                    "detail": "2 个工具已经收口",
                    "status": "done",
                    "step_key": "parallel:1:1:call_parallel_fast",
                    "phase": "tool",
                    "parallel_group_id": "parallel:1:1:call_parallel_fast",
                    "parallel_size": 2,
                    "parallel_completed_count": 2,
                    "parallel_success_count": 2,
                    "parallel_tools": ["folder_explore", "search_text"],
                }
            ],
        )

    def test_tool_preamble_detector_distinguishes_lead_in_from_answer_payload(self):
        self.assertTrue(reply_formatter_module._looks_like_tool_preamble("我先梳理一下技术方案 👇"))
        self.assertTrue(reply_formatter_module._looks_like_tool_preamble("好嘞！这个需求很明确～\n我先梳理一下技术方案 👇"))
        self.assertTrue(reply_formatter_module._looks_like_tool_preamble("让我看看记忆库～"))
        self.assertTrue(
            reply_formatter_module._looks_like_tool_preamble(
                "啊！这个发现很重要。让我帮你检查一下当前的环境状态，看看有没有隐藏的进程在运行。"
            )
        )
        self.assertTrue(
            reply_formatter_module._looks_like_tool_preamble(
                "主人，我理解这种\"时好时坏\"的情况最让人头疼。让我帮你深入分析一下："
            )
        )
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
        self.assertFalse(reply_formatter_module._looks_like_tool_preamble("好的，有需要随时叫我哦～"))
        self.assertTrue(
            reply_formatter_module._looks_like_trailing_tool_handoff(
                "主人，你说到点子上了！这确实是个很关键的问题。\n\n"
                "我理解你的感受：\n"
                "- 日常聊天还能接住\n"
                "- 一到任务就容易断片\n\n"
                "好消息是我现在有完整的记忆系统了。\n\n"
                "让我先回忆一下我们最近的开发任务："
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
        self.assertIn("self_fix and discover_tools are not available in the current tool list", prompt)
        self.assertIn("缺少必要参数", prompt)

    def test_tool_call_system_prompt_focuses_existing_task_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "templates" / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("<html><body>old</body></html>", encoding="utf-8")

            prompt = reply_formatter_module._build_tool_call_system_prompt(
                {
                    "l3": [],
                    "l4": {},
                    "l5": {},
                    "l7": [],
                    "l8": [],
                    "l2_memories": [],
                    "current_model": "test-model",
                    "context_data": {"fs_target": {"path": str(target), "option": "inspect"}},
                }
            )

        self.assertIn("Focused task guidance", prompt)
        self.assertIn(str(target), prompt)
        self.assertIn("prefer read_file / write_file over folder_explore", prompt)
        self.assertIn("Primary coding lane", prompt)

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

    def test_unified_reply_with_tools_stream_reports_stream_only_unavailable_reply(self):
        with patch.object(reply_formatter_module, "_llm_call_stream", None), patch.object(
            reply_formatter_module,
            "unified_reply_with_tools",
            side_effect=AssertionError("frontend chat should not fall back to non-stream"),
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream({"user_input": "鎵撳紑椤圭洰鐩綍"}, [], None))

        self.assertTrue(any(isinstance(chunk, str) and "只保留流式工具链" in chunk for chunk in chunks))
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertIsNone(done.get("tool_used"))
        self.assertEqual(done.get("action_count"), 0)
        self.assertEqual(done.get("success"), None)
        return

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

    def test_unified_reply_with_tools_stream_keeps_multisentence_handoff_before_environment_tool(self):
        executed = []

        def fake_stream(_cfg, messages, **_kwargs):
            has_tool_result = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
            if not has_tool_result:
                yield "啊！这个发现很重要。让我帮你检查一下当前的环境状态，看看有没有隐藏的进程在运行。"
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_env_1",
                            "type": "function",
                            "function": {
                                "name": "sense_environment",
                                "arguments": json.dumps({"detail_level": "basic"}, ensure_ascii=False),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 3}}
                return

            yield "这一步已经完成：\n\n已拿到当前环境状态。"
            yield {"_usage": {"prompt_tokens": 7, "completion_tokens": 2}}

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {
                "success": True,
                "response": "Environment inspected",
                "meta": {
                    "action": {
                        "action_kind": "inspect_environment",
                        "target_kind": "desktop_environment",
                        "display_hint": "已拿到当前环境状态",
                        "verification_detail": "environment snapshot captured",
                    }
                },
            }

        bundle = {
            "user_input": "说是之前还有个隐秘的东西在跑",
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

        self.assertEqual(executed[0][0], "sense_environment")
        self.assertEqual(executed[0][1].get("detail_level"), "basic")
        self.assertTrue(any(isinstance(chunk, str) and "让我帮你检查一下当前的环境状态" in chunk for chunk in chunks))
        self.assertTrue(any(isinstance(chunk, dict) and chunk.get("_tool_call", {}).get("executing") for chunk in chunks))
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertEqual(done.get("tool_used"), "sense_environment")
        self.assertEqual(done.get("success"), True)

    def test_unified_reply_with_tools_stream_closes_dropped_stream_tool_signal_as_failure(self):
        executed = []

        def fake_stream(_cfg, messages, **_kwargs):
            has_tool_result = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
            if not has_tool_result:
                yield "结论先说：这更像是缓存残留，不是当前窗口本身的问题。"
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_env_drop_1",
                            "type": "function",
                            "function": {
                                "name": "sense_environment",
                                "arguments": json.dumps({"detail_level": "basic"}, ensure_ascii=False),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 6, "completion_tokens": 4}}
                return

            yield "unexpected followup"

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {"success": True, "response": "should not run"}

        bundle = {
            "user_input": "检查一下是不是还有别的东西在后台跑",
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

        self.assertEqual(executed, [])
        synthetic_done = next(
            chunk
            for chunk in chunks
            if isinstance(chunk, dict)
            and chunk.get("_tool_call", {}).get("done")
        )
        self.assertTrue(synthetic_done.get("_tool_call", {}).get("synthetic"))
        self.assertEqual(synthetic_done.get("_tool_call", {}).get("reason"), "stream_signal_dropped")
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertEqual(done.get("tool_used"), "sense_environment")
        self.assertEqual(done.get("success"), False)
        self.assertEqual(done.get("synthetic"), True)
        self.assertEqual(done.get("reason"), "stream_signal_dropped")

    def test_unified_reply_with_tools_stream_closes_tool_executor_exception_as_terminal_failure(self):
        def fake_stream(_cfg, messages, **_kwargs):
            has_tool_result = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
            if not has_tool_result:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_env_boom_1",
                            "type": "function",
                            "function": {
                                "name": "sense_environment",
                                "arguments": json.dumps({"detail_level": "basic"}, ensure_ascii=False),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 4, "completion_tokens": 2}}
                return

            yield "unexpected followup"

        def fake_tool_executor(_name, _args, _context):
            raise RuntimeError("boom")

        bundle = {
            "user_input": "看看当前环境状态",
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

        self.assertTrue(
            any(
                isinstance(chunk, dict)
                and chunk.get("_tool_call", {}).get("executing")
                and chunk.get("_tool_call", {}).get("name") == "sense_environment"
                for chunk in chunks
            )
        )
        synthetic_done = next(
            chunk
            for chunk in chunks
            if isinstance(chunk, dict)
            and chunk.get("_tool_call", {}).get("done")
        )
        self.assertTrue(synthetic_done.get("_tool_call", {}).get("synthetic"))
        self.assertEqual(synthetic_done.get("_tool_call", {}).get("reason"), "tool_executor_exception")
        self.assertIn("boom", synthetic_done.get("_tool_call", {}).get("response", ""))
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertEqual(done.get("tool_used"), "sense_environment")
        self.assertEqual(done.get("success"), False)
        self.assertEqual(done.get("synthetic"), True)
        self.assertEqual(done.get("reason"), "tool_executor_exception")
        self.assertIn("boom", done.get("tool_response", ""))

    def test_unified_reply_with_tools_stream_closes_user_interrupted_without_followup_round(self):
        stream_call_count = {"value": 0}

        def fake_stream(_cfg, messages, **_kwargs):
            stream_call_count["value"] += 1
            has_tool_result = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
            if not has_tool_result:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_interrupt_1",
                            "type": "function",
                            "function": {
                                "name": "sense_environment",
                                "arguments": json.dumps({"detail_level": "basic"}, ensure_ascii=False),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 4, "completion_tokens": 2}}
                return

            raise AssertionError("stream should not request a followup round after user_interrupted")

        def fake_tool_executor(_name, _args, _context):
            return {
                "success": False,
                "response": "sense_environment interrupted",
                "error": "sense_environment interrupted",
                "reason": "user_interrupted",
                "synthetic": True,
                "meta": {},
            }

        bundle = {
            "user_input": "看下当前环境",
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

        self.assertEqual(stream_call_count["value"], 1)
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertEqual(done.get("tool_used"), "sense_environment")
        self.assertEqual(done.get("success"), False)
        self.assertEqual(done.get("reason"), "user_interrupted")

    def test_unified_reply_with_tools_non_stream_closes_user_interrupted_without_followup_round(self):
        call_count = {"value": 0}

        def fake_llm_call(_cfg, _messages, **_kwargs):
            call_count["value"] += 1
            if call_count["value"] == 1:
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_interrupt_non_stream_1",
                            "type": "function",
                            "function": {
                                "name": "sense_environment",
                                "arguments": json.dumps({"detail_level": "basic"}, ensure_ascii=False),
                            },
                        }
                    ],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 2},
                }
            raise AssertionError("non-stream should not request a followup round after user_interrupted")

        def fake_tool_executor(_name, _args, _context):
            return {
                "success": False,
                "response": "sense_environment interrupted",
                "error": "sense_environment interrupted",
                "reason": "user_interrupted",
                "synthetic": True,
                "meta": {},
            }

        bundle = {
            "user_input": "看下当前环境",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call", side_effect=fake_llm_call), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"):
            result = reply_formatter_module.unified_reply_with_tools(bundle, [], fake_tool_executor)

        self.assertEqual(call_count["value"], 1)
        self.assertEqual(result.get("tool_used"), "sense_environment")
        self.assertEqual(result.get("success"), False)
        self.assertEqual(result.get("reason"), "user_interrupted")

    def test_unified_reply_with_tools_stream_keeps_visible_intro_before_ask_user(self):
        executed = []

        def fake_stream(_cfg, messages, **_kwargs):
            has_tool_result = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
            if not has_tool_result:
                yield "Let's play a tiny game. Pick one:"
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_ask_1",
                            "type": "function",
                            "function": {
                                "name": "ask_user",
                                "arguments": json.dumps(
                                    {"question": "Which game?", "options": ["Trivia", "Would you rather"]},
                                    ensure_ascii=False,
                                ),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 3}}
                return

            yield "Nice, let's start with trivia."
            yield {"_usage": {"prompt_tokens": 4, "completion_tokens": 6}}

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {
                "success": True,
                "response": "User selected: Trivia",
            }

        bundle = {
            "user_input": "I have nothing in mind",
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

        self.assertEqual(executed[0][0], "ask_user")
        self.assertEqual(executed[0][1].get("question"), "Which game?")
        self.assertEqual(executed[0][1].get("options"), ["Trivia", "Would you rather"])
        self.assertTrue(any(isinstance(chunk, str) and "Pick one" in chunk for chunk in chunks))
        self.assertTrue(
            any(
                isinstance(chunk, dict)
                and chunk.get("_tool_call", {}).get("executing")
                and chunk.get("_tool_call", {}).get("name") == "ask_user"
                for chunk in chunks
            )
        )
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertEqual(done.get("tool_used"), "ask_user")
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

    def test_write_file_arg_failure_system_note_keeps_retry_on_write_file_lane(self):
        note = reply_formatter_module._build_tool_arg_failure_system_note(
            "write_file",
            {"file_path": "notes_app/templates/index.html"},
            ["content"],
        )

        self.assertIn("immediately call write_file again", note)
        self.assertIn("change_request or description", note)
        self.assertIn("inspect with list_files or read_file first", note)
        self.assertIn("Only stop calling tools", note)

    def test_strict_write_file_retry_note_forbids_empty_promises(self):
        note = reply_formatter_module._build_strict_write_file_retry_note(
            {"file_path": "notes_app/templates/index.html"},
            {"tool": "write_file", "target": "notes_app/templates/index.html", "missing_fields": ["content"]},
        )

        self.assertIn("Do not send natural-language promises", note)
        self.assertIn("call write_file with the SAME file_path", note)
        self.assertIn("precise change_request/description", note)
        self.assertIn("call list_files or read_file first", note)
        self.assertIn("Do not repeat write_file with only file_path", note)

    def test_execute_edit_file_action_updates_existing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "index.html"
            target.write_text("<html><body>old</body></html>", encoding="utf-8")

            def fake_stream(_cfg, _messages, **_kwargs):
                yield "<html><body>new</body></html>"

            with patch("brain.llm_call_stream", side_effect=fake_stream):
                result = fs_protocol_module.execute_edit_file_action(
                    {
                        "file_path": str(target),
                        "change_request": "把 old 改成 new",
                    }
                )

            self.assertTrue(result.get("success"))
            self.assertEqual(target.read_text(encoding="utf-8"), "<html><body>new</body></html>")
            meta = result.get("meta") or {}
            action = meta.get("action") or {}
            self.assertEqual(action.get("action_kind"), "edit_file")
            self.assertEqual(action.get("outcome"), "edited")

    def test_execute_search_replace_action_replaces_single_match(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "index.html"
            target.write_text("<html><body>old</body></html>", encoding="utf-8")

            result = fs_protocol_module.execute_search_replace_action(
                {
                    "file_path": str(target),
                    "old_text": "old",
                    "new_text": "new",
                }
            )

            self.assertTrue(result.get("success"))
            self.assertEqual(target.read_text(encoding="utf-8"), "<html><body>new</body></html>")
            meta = result.get("meta") or {}
            action = meta.get("action") or {}
            self.assertEqual(action.get("action_kind"), "search_replace")
            self.assertEqual(action.get("outcome"), "edited")

    def test_execute_search_replace_action_blocks_ambiguous_single_replace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "sample.txt"
            target.write_text("foo\nfoo\n", encoding="utf-8")

            result = fs_protocol_module.execute_search_replace_action(
                {
                    "file_path": str(target),
                    "old_text": "foo",
                    "new_text": "bar",
                }
            )

            self.assertFalse(result.get("success"))
            meta = result.get("meta") or {}
            drift = meta.get("drift") or {}
            self.assertEqual(drift.get("reason"), "search_text_ambiguous")
            self.assertIn("match_count=2", (meta.get("action") or {}).get("verification_detail", ""))

    def test_execute_search_replace_action_allows_empty_new_text_for_delete(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "sample.txt"
            target.write_text("alpha beta", encoding="utf-8")

            result = fs_protocol_module.execute_search_replace_action(
                {
                    "file_path": str(target),
                    "old_text": " beta",
                    "new_text": "",
                }
            )

            self.assertTrue(result.get("success"))
            self.assertEqual(target.read_text(encoding="utf-8"), "alpha")

    def test_execute_apply_unified_diff_action_updates_existing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "index.html"
            target.write_text("<html>\n<body>old</body>\n</html>\n", encoding="utf-8")
            patch_text = (
                "--- a/index.html\n"
                "+++ b/index.html\n"
                "@@ -1,3 +1,3 @@\n"
                " <html>\n"
                "-<body>old</body>\n"
                "+<body>new</body>\n"
                " </html>\n"
            )

            result = fs_protocol_module.execute_apply_unified_diff_action(
                {
                    "file_path": str(target),
                    "patch": patch_text,
                }
            )

            self.assertTrue(result.get("success"))
            self.assertEqual(target.read_text(encoding="utf-8"), "<html>\n<body>new</body>\n</html>\n")
            meta = result.get("meta") or {}
            action = meta.get("action") or {}
            self.assertEqual(action.get("action_kind"), "apply_unified_diff")
            self.assertEqual(action.get("outcome"), "edited")

    def test_execute_apply_unified_diff_action_blocks_mismatched_patch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "index.html"
            target.write_text("<html>\n<body>old</body>\n</html>\n", encoding="utf-8")
            patch_text = (
                "--- a/index.html\n"
                "+++ b/index.html\n"
                "@@ -1,3 +1,3 @@\n"
                " <html>\n"
                "-<body>missing</body>\n"
                "+<body>new</body>\n"
                " </html>\n"
            )

            result = fs_protocol_module.execute_apply_unified_diff_action(
                {
                    "file_path": str(target),
                    "patch": patch_text,
                }
            )

            self.assertFalse(result.get("success"))
            meta = result.get("meta") or {}
            drift = meta.get("drift") or {}
            self.assertEqual(drift.get("reason"), "patch_apply_failed")

    def test_execute_write_file_action_verifies_python_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "app.py"

            result = fs_protocol_module.execute_write_file_action(
                {
                    "file_path": str(target),
                    "content": "print('ok')\n",
                }
            )

            self.assertTrue(result.get("success"))
            meta = result.get("meta") or {}
            verification = meta.get("verification") or {}
            action = meta.get("action") or {}
            self.assertIs(verification.get("verified"), True)
            self.assertEqual(verification.get("verification_mode"), "python_compile")
            self.assertEqual(action.get("verification_mode"), "python_compile")

    def test_execute_write_file_action_generates_new_file_from_change_request(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "app.py"

            def fake_stream(_cfg, _messages, **_kwargs):
                yield "print('ok')\n"

            with patch("brain.llm_call_stream", side_effect=fake_stream):
                result = fs_protocol_module.execute_write_file_action(
                    {
                        "file_path": str(target),
                        "change_request": "Create a tiny Python script that prints ok.",
                    }
                )

            self.assertTrue(result.get("success"))
            self.assertEqual(target.read_text(encoding="utf-8").strip(), "print('ok')")
            meta = result.get("meta") or {}
            action = meta.get("action") or {}
            verification = meta.get("verification") or {}
            self.assertEqual(action.get("action_kind"), "write_file")
            self.assertEqual(verification.get("verification_mode"), "python_compile")

    def test_execute_write_file_action_rewrites_existing_file_from_change_request(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "index.html"
            target.write_text("<html><body>old</body></html>", encoding="utf-8")

            def fake_stream(_cfg, _messages, **_kwargs):
                yield "<html><body>new</body></html>"

            with patch("brain.llm_call_stream", side_effect=fake_stream):
                result = fs_protocol_module.execute_write_file_action(
                    {
                        "file_path": str(target),
                        "change_request": "Replace old with new.",
                    }
                )

            self.assertTrue(result.get("success"))
            self.assertEqual(target.read_text(encoding="utf-8"), "<html><body>new</body></html>")
            meta = result.get("meta") or {}
            action = meta.get("action") or {}
            self.assertEqual(action.get("action_kind"), "write_file")

    def test_execute_write_file_action_fails_on_invalid_python(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "app.py"

            result = fs_protocol_module.execute_write_file_action(
                {
                    "file_path": str(target),
                    "content": "print(\n",
                }
            )

            self.assertFalse(result.get("success"))
            meta = result.get("meta") or {}
            action = meta.get("action") or {}
            self.assertEqual(action.get("verification_mode"), "python_compile")
            self.assertIn("SyntaxError", action.get("verification_detail", ""))

    def test_execute_search_replace_action_verifies_json_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "data.json"
            target.write_text('{"count": 1}\n', encoding="utf-8")

            result = fs_protocol_module.execute_search_replace_action(
                {
                    "file_path": str(target),
                    "old_text": "1",
                    "new_text": "2",
                }
            )

            self.assertTrue(result.get("success"))
            meta = result.get("meta") or {}
            verification = meta.get("verification") or {}
            self.assertIs(verification.get("verified"), True)
            self.assertEqual(verification.get("verification_mode"), "json_parse")

    def test_execute_search_replace_action_fails_on_invalid_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "data.json"
            target.write_text('{"count": 1}\n', encoding="utf-8")

            result = fs_protocol_module.execute_search_replace_action(
                {
                    "file_path": str(target),
                    "old_text": "1",
                    "new_text": "",
                }
            )

            self.assertFalse(result.get("success"))
            meta = result.get("meta") or {}
            action = meta.get("action") or {}
            self.assertEqual(action.get("verification_mode"), "json_parse")
            self.assertIn("JSONDecodeError", action.get("verification_detail", ""))

    def test_execute_edit_file_action_fails_on_invalid_jinja(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "template.jinja"
            target.write_text("Hello {{ name }}\n", encoding="utf-8")

            def fake_stream(_cfg, _messages, **_kwargs):
                yield "{% if user %}\nHello {{ name }} and welcome to NovaCore.\n"

            with patch("brain.llm_call_stream", side_effect=fake_stream):
                result = fs_protocol_module.execute_edit_file_action(
                    {
                        "file_path": str(target),
                        "change_request": "改成带条件判断的模板",
                    }
                )

            self.assertFalse(result.get("success"))
            meta = result.get("meta") or {}
            action = meta.get("action") or {}
            self.assertEqual(action.get("verification_mode"), "jinja_parse")
            self.assertIn("TemplateSyntaxError", action.get("verification_detail", ""))

    def test_execute_apply_unified_diff_action_verifies_javascript_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "app.js"
            target.write_text("const value = 1;\nconsole.log(value);\n", encoding="utf-8")
            patch_text = (
                "--- a/app.js\n"
                "+++ b/app.js\n"
                "@@ -1,2 +1,2 @@\n"
                "-const value = 1;\n"
                "+const value = 2;\n"
                " console.log(value);\n"
            )

            result = fs_protocol_module.execute_apply_unified_diff_action(
                {
                    "file_path": str(target),
                    "patch": patch_text,
                }
            )

            self.assertTrue(result.get("success"))
            meta = result.get("meta") or {}
            verification = meta.get("verification") or {}
            self.assertIs(verification.get("verified"), True)
            self.assertEqual(verification.get("verification_mode"), "node_check")

    def test_execute_apply_unified_diff_action_fails_on_invalid_javascript(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "app.js"
            target.write_text("const value = 1;\nconsole.log(value);\n", encoding="utf-8")
            patch_text = (
                "--- a/app.js\n"
                "+++ b/app.js\n"
                "@@ -1,2 +1,2 @@\n"
                "-const value = 1;\n"
                "+const value = ;\n"
                " console.log(value);\n"
            )

            result = fs_protocol_module.execute_apply_unified_diff_action(
                {
                    "file_path": str(target),
                    "patch": patch_text,
                }
            )

            self.assertFalse(result.get("success"))
            meta = result.get("meta") or {}
            action = meta.get("action") or {}
            self.assertEqual(action.get("verification_mode"), "node_check")
            self.assertIn("SyntaxError", action.get("verification_detail", ""))

    def test_execute_write_file_action_marks_css_as_unverified(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "main.css"

            result = fs_protocol_module.execute_write_file_action(
                {
                    "file_path": str(target),
                    "content": "body { color: red; }\n",
                }
            )

            self.assertTrue(result.get("success"))
            meta = result.get("meta") or {}
            verification = meta.get("verification") or {}
            self.assertIn("verified", verification)
            self.assertIsNone(verification.get("verified"))
            self.assertEqual(verification.get("verification_mode"), "unverified_no_parser")

    def test_execute_write_file_action_fails_on_invalid_markdown_front_matter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "README.md"

            result = fs_protocol_module.execute_write_file_action(
                {
                    "file_path": str(target),
                    "content": "---\ntitle: [oops\n---\nbody\n",
                }
            )

            self.assertFalse(result.get("success"))
            meta = result.get("meta") or {}
            action = meta.get("action") or {}
            self.assertEqual(action.get("verification_mode"), "markdown_front_matter")
            self.assertIn("ParserError", action.get("verification_detail", ""))

    def test_execute_write_file_action_does_not_run_semantic_verifier_when_persistence_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "app.py"

            with patch.object(
                fs_protocol_module,
                "verify_post_condition",
                return_value={
                    "ok": False,
                    "expected": "file_written",
                    "observed": "file_missing_after_write",
                    "drift": "write_not_persisted",
                    "hint": "retry_or_check_write_target",
                },
            ), patch.object(fs_protocol_module, "verify_file_change", side_effect=AssertionError("semantic verifier should not run")):
                result = fs_protocol_module.execute_write_file_action(
                    {
                        "file_path": str(target),
                        "content": "print('ok')\n",
                    }
                )

            self.assertFalse(result.get("success"))
            meta = result.get("meta") or {}
            action = meta.get("action") or {}
            self.assertEqual(action.get("verification_mode"), "path_exists")

    def test_build_tool_closeout_reply_distinguishes_verified_success(self):
        reply = reply_formatter_module._build_tool_closeout_reply(
            success=True,
            action_summary="已写入文件：app.py",
            tool_response="",
            run_meta={
                "verification": {
                    "verified": True,
                    "verification_mode": "python_compile",
                    "verification_detail": "Python source compiled successfully.",
                }
            },
        )

        self.assertIn("已通过核验", reply)
        self.assertIn("Python source compiled successfully.", reply)

    def test_build_tool_closeout_reply_distinguishes_unverified_success(self):
        reply = reply_formatter_module._build_tool_closeout_reply(
            success=True,
            action_summary="已写入文件：main.css",
            tool_response="",
            run_meta={
                "verification": {
                    "verified": None,
                    "verification_mode": "unverified_no_parser",
                    "verification_detail": "CSS was written successfully, but no reliable local CSS parser is configured.",
                }
            },
        )

        self.assertIn("还没有可靠核验", reply)
        self.assertIn("CSS was written successfully", reply)

    def test_unified_reply_with_tools_stream_allows_one_more_write_file_repair_attempt(self):
        executed = []
        call_count = {"value": 0}

        def fake_stream(_cfg, messages, **_kwargs):
            call_count["value"] += 1
            idx = call_count["value"]
            if idx == 1:
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
            if idx == 2:
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
                return
            if idx == 3:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_write_3",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": json.dumps(
                                    {
                                        "file_path": "notes_app/templates/index.html",
                                        "content": "<html><body>ok</body></html>",
                                    },
                                    ensure_ascii=False,
                                ),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 8, "completion_tokens": 4}}
                return

            yield "已经写好了。"
            yield {"_usage": {"prompt_tokens": 4, "completion_tokens": 3}}

        def fake_tool_executor(name, args, _context):
            executed.append((name, dict(args)))
            if not str(args.get("content") or "").strip():
                return {"success": False, "error": "缺少 content"}
            return {
                "success": True,
                "response": "已写入 index.html",
                "meta": {"action": {"display_hint": "已写入 index.html"}},
            }

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

        self.assertEqual(len(executed), 2)
        self.assertEqual(executed[0][1].get("file_path"), "notes_app/templates/index.html")
        self.assertFalse(bool(executed[0][1].get("content")))
        self.assertEqual(executed[1][1].get("file_path"), "notes_app/templates/index.html")
        self.assertEqual(executed[1][1].get("content"), "<html><body>ok</body></html>")
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertEqual(done.get("tool_used"), "write_file")
        self.assertEqual(done.get("success"), True)

    def test_followup_tools_keep_write_file_after_missing_content_for_existing_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "templates" / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("<html><body>old</body></html>", encoding="utf-8")

            tools = [
                {"type": "function", "function": {"name": "write_file"}},
                {"type": "function", "function": {"name": "read_file"}},
                {"type": "function", "function": {"name": "folder_explore"}},
                {"type": "function", "function": {"name": "screen_capture"}},
            ]

            filtered = reply_formatter_module._build_followup_tools_after_arg_failure(
                tools,
                {"tool": "write_file", "missing_fields": ["content"], "target": str(target)},
                {"file_path": str(target)},
            )

        filtered_names = [tool.get("function", {}).get("name") for tool in filtered]
        self.assertIn("write_file", filtered_names)
        self.assertIn("read_file", filtered_names)

    def test_followup_tools_keep_write_file_for_new_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "templates" / "index.html"
            tools = [
                {"type": "function", "function": {"name": "write_file"}},
                {"type": "function", "function": {"name": "read_file"}},
            ]

            filtered = reply_formatter_module._build_followup_tools_after_arg_failure(
                tools,
                {"tool": "write_file", "missing_fields": ["content"], "target": str(target)},
                {"file_path": str(target)},
            )

        filtered_names = [tool.get("function", {}).get("name") for tool in filtered]
        self.assertIn("write_file", filtered_names)

    def test_followup_tools_drop_environment_tools_for_existing_file_focus(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "templates" / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("<html><body>old</body></html>", encoding="utf-8")

            tools = [
                {"type": "function", "function": {"name": "read_file"}},
                {"type": "function", "function": {"name": "write_file"}},
                {"type": "function", "function": {"name": "folder_explore"}},
                {"type": "function", "function": {"name": "screen_capture"}},
                {"type": "function", "function": {"name": "app_target"}},
            ]

            filtered = reply_formatter_module._build_followup_tools_after_arg_failure(
                tools,
                None,
                {"file_path": str(target)},
            )

        filtered_names = [tool.get("function", {}).get("name") for tool in filtered]
        self.assertIn("read_file", filtered_names)
        self.assertIn("write_file", filtered_names)
        self.assertNotIn("folder_explore", filtered_names)
        self.assertNotIn("screen_capture", filtered_names)
        self.assertNotIn("app_target", filtered_names)

    def test_followup_tools_reprioritize_primary_coding_lane_without_hard_ban(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "templates" / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("<html><body>old</body></html>", encoding="utf-8")

            tools = [
                {"type": "function", "function": {"name": "task_plan"}},
                {"type": "function", "function": {"name": "web_search"}},
                {"type": "function", "function": {"name": "write_file"}},
                {"type": "function", "function": {"name": "run_command"}},
                {"type": "function", "function": {"name": "read_file"}},
                {"type": "function", "function": {"name": "folder_explore"}},
            ]

            filtered = reply_formatter_module._build_followup_tools_after_arg_failure(
                tools,
                None,
                {"file_path": str(target)},
                current_tool_name="read_file",
            )

        filtered_names = [tool.get("function", {}).get("name") for tool in filtered]
        self.assertEqual(
            filtered_names[:4],
            ["read_file", "write_file", "run_command", "task_plan"],
        )
        self.assertIn("web_search", filtered_names)
        self.assertNotIn("folder_explore", filtered_names)

    def test_file_protocol_tool_defs_expose_open_instruction_aliases(self):
        defs = tool_adapter_module._build_file_protocol_tool_defs()
        names = [tool.get("function", {}).get("name") for tool in defs]

        self.assertEqual(names, ["write_file"])

        write_props = defs[0]["function"]["parameters"]["properties"]
        self.assertIn("instructions", write_props)
        self.assertIn("problem", write_props)

    def test_build_tools_list_cod_hides_removed_protocol_and_runtime_tools(self):
        with patch.object(
            tool_adapter_module,
            "_get_all_skills",
            return_value={"development_flow": {"execute": (lambda *_a, **_k: None), "description": "dev", "parameters": {"type": "object", "properties": {"user_input": {"type": "string"}}, "required": ["user_input"]}}},
        ):
            tools = tool_adapter_module.build_tools_list_cod()

        names = [tool.get("function", {}).get("name") for tool in tools]
        self.assertIn("read_file", names)
        self.assertIn("write_file", names)
        self.assertNotIn("edit_file", names)
        self.assertNotIn("search_replace", names)
        self.assertNotIn("apply_unified_diff", names)
        self.assertNotIn("self_fix", names)
        self.assertIn("sense_environment", names)
        self.assertNotIn("discover_tools", names)

    def test_unified_reply_with_tools_stream_keeps_write_file_available_for_existing_file_retry(self):
        executed = []
        tool_sets = []
        call_count = {"value": 0}

        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "templates" / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("<html><body>old</body></html>", encoding="utf-8")

            tools = [
                {"type": "function", "function": {"name": "write_file"}},
                {"type": "function", "function": {"name": "read_file"}},
            ]

            def fake_stream(_cfg, messages, tools=None, **_kwargs):
                call_count["value"] += 1
                tool_sets.append([tool.get("function", {}).get("name") for tool in (tools or [])])
                idx = call_count["value"]
                if idx == 1:
                    yield {
                        "_tool_calls": [
                            {
                                "id": "call_write_1",
                                "type": "function",
                                "function": {
                                    "name": "write_file",
                                    "arguments": json.dumps(
                                        {"file_path": str(target)},
                                        ensure_ascii=False,
                                    ),
                                },
                            }
                        ]
                    }
                    yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 3}}
                    return
                if idx == 2:
                    self.assertIn("write_file", tool_sets[-1])
                    self.assertNotIn("folder_explore", tool_sets[-1])
                    self.assertNotIn("sense_environment", tool_sets[-1])
                    yield {
                        "_tool_calls": [
                            {
                                "id": "call_write_2",
                                "type": "function",
                                "function": {
                                    "name": "write_file",
                                    "arguments": json.dumps(
                                        {
                                            "file_path": str(target),
                                            "change_request": "Add a class to the body tag.",
                                        },
                                        ensure_ascii=False,
                                    ),
                                },
                            }
                        ]
                    }
                    yield {"_usage": {"prompt_tokens": 7, "completion_tokens": 2}}
                    return

                yield "已经改好了。"
                yield {"_usage": {"prompt_tokens": 4, "completion_tokens": 3}}

            def fake_tool_executor(name, args, _context):
                executed.append((name, dict(args)))
                if name == "write_file" and not args.get("change_request"):
                    return {"success": False, "error": "缺少 content"}
                return {
                    "success": True,
                    "response": "已写入 index.html",
                    "meta": {"action": {"display_hint": "已写入 index.html"}},
                }

            bundle = {
                "user_input": "改好了吗",
                "l1": [],
                "l4": {},
                "dialogue_context": "",
            }

            with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
                reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
            ), patch.object(
                reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
            ):
                chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, tools, fake_tool_executor))

        self.assertEqual([name for name, _args in executed], ["write_file", "write_file"])
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertEqual(done.get("tool_used"), "write_file")
        self.assertEqual(done.get("success"), True)

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
        meta = result.get("meta") or {}
        action = meta.get("action") or {}
        self.assertEqual(action.get("action_kind"), "resolve_directory")
        self.assertEqual(action.get("target_kind"), "directory")
        self.assertEqual(action.get("verification_mode"), "directory_listed")
        self.assertIn("dirs=", action.get("verification_detail", ""))

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

    def test_execute_tool_call_remembers_failed_write_file_target_as_file(self):
        remembered = {}
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "templates" / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("<html><body>old</body></html>", encoding="utf-8")
            context = {
                "fs_target": {"path": str(target.parent), "option": "inspect", "source": "memory"},
                "context_data": {"fs_target": {"path": str(target.parent), "option": "inspect", "source": "memory"}},
                "task_plan": {"task_id": "task_demo", "project_id": "proj_demo", "goal": "继续修改 index.html", "items": []},
            }

            fake_result = {
                "success": False,
                "error": "执行失败: 缺少 content。",
                "meta": {
                    "action": {
                        "action_kind": "write_file",
                        "target_kind": "file",
                        "target": str(target),
                        "outcome": "blocked",
                        "verification_mode": "argument_check",
                        "verification_detail": "missing_fields=content",
                    }
                },
            }

            with patch.object(tool_adapter_module, "_execute", return_value=fake_result), patch(
                "core.task_store.remember_fs_target_for_task_plan",
                side_effect=lambda task_plan, fs_target: remembered.setdefault("target", dict(fs_target)),
            ):
                result = tool_adapter_module.execute_tool_call(
                    "write_file",
                    {"file_path": str(target)},
                    context,
                )

        self.assertFalse(result.get("success"))
        self.assertEqual((context.get("fs_target") or {}).get("path"), str(target))
        self.assertEqual(((context.get("context_data") or {}).get("fs_target") or {}).get("path"), str(target))
        self.assertEqual((remembered.get("target") or {}).get("path"), str(target))

    def test_execute_tool_call_routes_search_replace_into_protocol_base(self):
        result = tool_adapter_module.execute_tool_call(
            "search_replace",
            {"file_path": "notes_app/templates/__missing_search_replace__.html", "old_text": "<body>", "new_text": "<body class='x'>"},
            {},
        )

        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("skill"), "search_replace")
        meta = result.get("meta") or {}
        action = meta.get("action") or {}
        self.assertEqual(action.get("action_kind"), "search_replace")
        self.assertEqual(action.get("target_kind"), "file")
        self.assertEqual(action.get("verification_mode"), "path_exists")

    def test_execute_tool_call_routes_apply_unified_diff_into_protocol_base(self):
        result = tool_adapter_module.execute_tool_call(
            "apply_unified_diff",
            {"file_path": "notes_app/templates/__missing_patch__.html", "patch": "@@ -1 +1 @@\n-old\n+new\n"},
            {},
        )

        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("skill"), "apply_unified_diff")
        meta = result.get("meta") or {}
        action = meta.get("action") or {}
        self.assertEqual(action.get("action_kind"), "apply_unified_diff")
        self.assertEqual(action.get("target_kind"), "file")
        self.assertEqual(action.get("verification_mode"), "path_exists")

    def test_execute_tool_call_catches_executor_exception_as_tool_failure(self):
        with patch.object(tool_adapter_module, "_execute", side_effect=RuntimeError("boom")):
            result = tool_adapter_module.execute_tool_call(
                "write_file",
                {"file_path": "notes_app/templates/index.html", "content": "hello"},
                {},
            )

        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("skill"), "write_file")
        self.assertIn("boom", result.get("error", ""))
        self.assertIn("执行异常", result.get("error", ""))
        self.assertIn("执行异常", result.get("response", ""))

    def test_execute_tool_call_normalizes_non_dict_executor_result(self):
        with patch.object(tool_adapter_module, "_execute", return_value="not-a-dict-result"):
            result = tool_adapter_module.execute_tool_call(
                "write_file",
                {"file_path": "notes_app/templates/index.html", "content": "hello"},
                {},
            )

        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("skill"), "write_file")
        self.assertIn("not-a-dict-result", result.get("response", ""))
        self.assertIn("结果格式异常", result.get("error", ""))

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

    def test_repair_tool_args_prefers_explicit_user_input_path_over_stale_folder_target(self):
        with patch.object(reply_formatter_module, "_load_task_plan_fs_target", return_value="C:/Users/36459/Desktop"), patch.object(
            reply_formatter_module, "_load_context_fs_target", return_value="C:/Users/36459/Desktop"
        ), patch.object(reply_formatter_module, "_infer_recent_directory_target", return_value="C:/Users/36459/Desktop"), patch.object(
            reply_formatter_module, "_load_latest_structured_fs_target", return_value="C:/Users/36459/Desktop"
        ):
            repaired = reply_formatter_module._repair_tool_args_from_context(
                "folder_explore",
                {"path": "C:/Users/36459/Desktop"},
                {
                    "user_input": r"C:\Users\36459\NovaNotes\ 项目结构",
                    "l1": [],
                    "context_data": {"fs_target": {"path": "C:/Users/36459/Desktop", "option": "inspect"}},
                },
            )

        self.assertEqual(str(repaired.get("path") or "").replace("\\", "/"), "C:/Users/36459/NovaNotes")

    def test_repair_tool_args_prefers_context_fs_target_before_global_fallback(self):
        with patch.object(reply_formatter_module, "_load_task_plan_fs_target", return_value=""), patch.object(
            reply_formatter_module, "_load_context_fs_target", return_value="C:/Users/36459/NovaNotes"
        ), patch.object(reply_formatter_module, "_infer_recent_directory_target", return_value=""), patch.object(
            reply_formatter_module, "_load_latest_structured_fs_target", return_value="C:/Users/36459/Desktop"
        ):
            repaired = reply_formatter_module._repair_tool_args_from_context(
                "folder_explore",
                {},
                {
                    "user_input": "继续看看这个项目结构",
                    "l1": [],
                    "context_data": {"fs_target": {"path": "C:/Users/36459/NovaNotes", "option": "inspect"}},
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

    def test_execute_tool_call_explicit_path_overrides_stale_folder_target(self):
        seen = []

        def fake_execute(skill_route, user_input, context):
            seen.append({"skill": skill_route.get("skill"), "user_input": user_input, "context": dict(context)})
            return {"success": True, "skill": skill_route.get("skill"), "response": "ok", "meta": {}}

        shared_context = {
            "path": "C:/Users/36459/Desktop",
            "fs_target": {"path": "C:/Users/36459/Desktop", "option": "inspect", "source": "memory"},
            "context_data": {"fs_target": {"path": "C:/Users/36459/Desktop", "option": "inspect", "source": "memory"}},
        }

        with patch.object(tool_adapter_module, "_execute", side_effect=fake_execute):
            tool_adapter_module.execute_tool_call(
                "folder_explore",
                {"user_input": "看这个目录", "path": "E:/文字红包"},
                shared_context,
            )

        self.assertEqual(len(seen), 1)
        self.assertEqual(
            str((seen[0]["context"].get("fs_target") or {}).get("path") or "").replace("\\", "/"),
            "E:/文字红包",
        )
        self.assertEqual(str(seen[0]["context"].get("path") or "").replace("\\", "/"), "E:/文字红包")

    def test_execute_tool_call_explicit_user_input_path_overrides_stale_folder_target(self):
        seen = []

        def fake_execute(skill_route, user_input, context):
            seen.append({"skill": skill_route.get("skill"), "user_input": user_input, "context": dict(context)})
            return {"success": True, "skill": skill_route.get("skill"), "response": "ok", "meta": {}}

        shared_context = {
            "path": "C:/Users/36459/Desktop",
            "fs_target": {"path": "C:/Users/36459/Desktop", "option": "inspect", "source": "memory"},
            "context_data": {"fs_target": {"path": "C:/Users/36459/Desktop", "option": "inspect", "source": "memory"}},
        }

        with patch.object(tool_adapter_module, "_execute", side_effect=fake_execute), patch(
            "core.context_pull.pull_context_data",
            return_value={
                "fs_target": {"path": "E:/文字红包", "option": "inspect", "source": "context_pull"},
                "fs_action": {"action": "inspect", "target": {"path": "E:/文字红包"}},
            },
        ):
            tool_adapter_module.execute_tool_call(
                "folder_explore",
                {"user_input": "看看 E:/文字红包"},
                shared_context,
            )

        self.assertEqual(len(seen), 1)
        self.assertEqual(
            str((seen[0]["context"].get("fs_target") or {}).get("path") or "").replace("\\", "/"),
            "E:/文字红包",
        )
        self.assertEqual(str(seen[0]["context"].get("path") or "").replace("\\", "/"), "E:/文字红包")
    def test_execute_tool_call_generic_request_does_not_reuse_stale_desktop_target(self):
        seen = []

        def fake_execute(skill_route, user_input, context):
            seen.append({"skill": skill_route.get("skill"), "user_input": user_input, "context": dict(context)})
            return {"success": True, "skill": skill_route.get("skill"), "response": "ok", "meta": {}}

        shared_context = {
            "path": "C:/Users/36459/Desktop",
            "fs_target": {"path": "C:/Users/36459/Desktop", "option": "inspect", "source": "memory"},
            "context_data": {"fs_target": {"path": "C:/Users/36459/Desktop", "option": "inspect", "source": "memory"}},
        }

        with patch.object(tool_adapter_module, "_execute", side_effect=fake_execute):
            tool_adapter_module.execute_tool_call(
                "folder_explore",
                {"user_input": "find selfie files"},
                shared_context,
            )

        self.assertEqual(len(seen), 1)
        self.assertFalse((seen[0]["context"].get("fs_target") or {}).get("path"))
        self.assertEqual(str(seen[0]["context"].get("path") or "").replace("\\", "/"), "")
        self.assertFalse((((seen[0]["context"].get("context_data") or {}).get("fs_target") or {}).get("path")))


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


class TaskPlanFsTargetBridgeTests(unittest.TestCase):
    def test_repair_tool_args_prefers_task_plan_fs_target_for_folder_explore(self):
        with patch(
            "core.task_store.get_structured_fs_target_for_task_plan",
            return_value={"path": "C:/Users/36459/NovaNotes", "option": "inspect", "source": "task_plan"},
        ):
            repaired = reply_formatter_module._repair_tool_args_from_context(
                "folder_explore",
                {},
                {
                    "user_input": "看看之前那个开发者笔记项目",
                    "task_plan": {"task_id": "task_demo", "project_id": "proj_demo"},
                    "l1": [],
                },
            )

        self.assertEqual(str(repaired.get("path") or "").replace("\\", "/"), "C:/Users/36459/NovaNotes")

    def test_directory_resolution_followup_infers_folder_explore_from_task_target(self):
        with patch(
            "core.task_store.get_structured_fs_target_for_task_plan",
            return_value={"path": "C:/Users/36459/NovaNotes", "option": "inspect", "source": "task_plan"},
        ):
            tool_calls = reply_formatter_module._resolve_tool_calls_from_result(
                {"content": "我先回忆一下路径。"},
                {
                    "user_input": "之前那个开发者笔记项目在哪个文件夹",
                    "task_plan": {"task_id": "task_demo", "project_id": "proj_demo"},
                    "l1": [],
                    "context_data": {},
                },
                mode="test_directory_resolution",
            )

        self.assertIsInstance(tool_calls, list)
        self.assertEqual(tool_calls[0]["function"]["name"], "folder_explore")
        args = json.loads(tool_calls[0]["function"]["arguments"])
        self.assertEqual(str(args.get("path") or "").replace("\\", "/"), "C:/Users/36459/NovaNotes")

    def test_directory_resolution_followup_allows_generic_pronoun_when_target_is_structured(self):
        with patch(
            "core.task_store.get_structured_fs_target_for_task_plan",
            return_value={"path": "C:/Users/36459/NovaNotes", "option": "inspect", "source": "task_plan"},
        ):
            tool_calls = reply_formatter_module._resolve_tool_calls_from_result(
                {"content": "我先想一下。"},
                {
                    "user_input": "它在哪",
                    "task_plan": {"task_id": "task_demo", "project_id": "proj_demo"},
                    "l1": [],
                    "context_data": {},
                },
                mode="test_directory_resolution_generic",
            )

        self.assertIsInstance(tool_calls, list)
        self.assertEqual(tool_calls[0]["function"]["name"], "folder_explore")

    def test_directory_resolution_does_not_trigger_from_keywords_without_structured_target(self):
        with patch.object(reply_formatter_module, "_resolve_active_task_plan", return_value=None), patch.object(
            reply_formatter_module, "_load_task_plan_fs_target", return_value=""
        ), patch.object(reply_formatter_module, "_load_context_fs_target", return_value=""), patch.object(
            reply_formatter_module, "_load_latest_structured_fs_target", return_value=""
        ):
            tool_calls = reply_formatter_module._resolve_tool_calls_from_result(
                {"content": "我先回忆一下路径。"},
                {
                    "user_input": "那个项目在哪个文件夹",
                    "l1": [],
                    "context_data": {},
                },
                mode="test_directory_resolution_without_target",
            )

        self.assertIsNone(tool_calls)

    def test_active_task_context_exposes_current_task_directory(self):
        with patch(
            "core.task_store.get_structured_fs_target_for_task_plan",
            return_value={"path": "C:/Users/36459/NovaNotes", "option": "inspect", "source": "task_plan"},
        ):
            context_text = reply_formatter_module._build_active_task_context(
                {
                    "user_input": "那个项目在哪",
                    "task_plan": {
                        "task_id": "task_demo",
                        "project_id": "proj_demo",
                        "goal": "继续完善 NovaNotes",
                        "items": [],
                    },
                }
            )

        self.assertIn("Current task directory/file target: C:/Users/36459/NovaNotes", context_text)

    def test_active_task_context_focuses_existing_task_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "templates" / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("<html><body>old</body></html>", encoding="utf-8")

            with patch(
                "core.task_store.get_structured_fs_target_for_task_plan",
                return_value={"path": str(target), "option": "inspect", "source": "task_plan"},
            ):
                context_text = reply_formatter_module._build_active_task_context(
                    {
                        "user_input": "继续改那个后台页面",
                        "task_plan": {
                            "task_id": "task_demo",
                            "project_id": "proj_demo",
                            "goal": "继续完善 NovaNotes 后台页面",
                            "items": [],
                        },
                    }
                )

        self.assertIn("Execution focus:", context_text)
        self.assertIn("Known coding target:", context_text)
        self.assertIn("Stay on this file first.", context_text)


class InitialToolHandoffRetryRegressionTests(unittest.TestCase):
    def test_stream_does_not_retry_text_only_handoff_without_structured_tool_signal(self):
        executed = []
        call_count = {"value": 0}

        def fake_stream(_cfg, messages, **_kwargs):
            call_count["value"] += 1
            yield "I will update the file directly now."
            yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 4}}

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {
                "success": True,
                "response": "Updated index.html",
                "meta": {
                    "action": {
                        "action_kind": "write_file",
                        "target_kind": "file",
                    }
                },
            }

        bundle = {
            "user_input": "Fix the admin page",
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

        self.assertEqual(call_count["value"], 1)
        self.assertEqual(len(executed), 0)
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertIsNone(done.get("tool_used"))
        self.assertIn("I will update the file directly now.", "".join(str(chunk) for chunk in chunks if isinstance(chunk, str)))

    def test_non_stream_does_not_retry_text_only_handoff_without_structured_tool_signal(self):
        executed = []
        call_count = {"value": 0}

        def fake_llm_call(_cfg, messages, tools=None, **_kwargs):
            call_count["value"] += 1
            return {
                "content": "I will update the file directly now.",
                "usage": {"prompt_tokens": 5, "completion_tokens": 4},
            }

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {
                "success": True,
                "response": "Updated index.html",
                "meta": {
                    "action": {
                        "action_kind": "write_file",
                        "target_kind": "file",
                    }
                },
            }

        bundle = {
            "user_input": "Fix the admin page",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call", side_effect=fake_llm_call), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"):
            result = reply_formatter_module.unified_reply_with_tools(bundle, [], fake_tool_executor)

        self.assertEqual(call_count["value"], 1)
        self.assertEqual(len(executed), 0)
        self.assertIsNone(result.get("tool_used"))
        self.assertIn("I will update the file directly now.", result.get("reply", ""))
        self.assertTrue(str(result.get("reply") or "").strip())


class StructuredToolHandoffRegressionTests(unittest.TestCase):
    def test_structured_tool_handoff_detector_allows_numbered_issue_summary(self):
        self.assertTrue(
            reply_formatter_module._looks_like_structured_tool_handoff(
                "明白！两个核心问题：\n1. 保存了也看不到\n2. 分类逻辑不对\n让我先完整看看项目结构和代码，搞清楚问题在哪："
            )
        )
        self.assertFalse(
            reply_formatter_module._looks_like_structured_tool_handoff(
                "明白！两个核心问题：\n1. 保存了也看不到\n2. 分类逻辑不对\n结论就是要重做分类逻辑。"
            )
        )

    def test_unified_reply_with_tools_stream_keeps_structured_handoff_before_tool_call(self):
        executed = []

        def fake_stream(_cfg, messages, **_kwargs):
            has_tool_result = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
            if not has_tool_result:
                yield "明白！两个核心问题：\n1. 保存了也看不到\n2. 分类逻辑不对\n让我先完整看看项目结构和代码，搞清楚问题在哪："
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_folder_1",
                            "type": "function",
                            "function": {
                                "name": "folder_explore",
                                "arguments": json.dumps({"query": "检查项目结构"}, ensure_ascii=False),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 3}}
                return

            yield "我已经先把项目结构看完了。"
            yield {"_usage": {"prompt_tokens": 7, "completion_tokens": 5}}

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {
                "success": True,
                "response": "已查看项目结构。",
                "meta": {
                    "action": {
                        "action_kind": "resolve_directory",
                        "target_kind": "directory",
                        "display_hint": "已查看项目结构",
                    }
                },
            }

        bundle = {
            "user_input": "看下项目结构",
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

        self.assertEqual(executed[0][0], "folder_explore")
        self.assertEqual(executed[0][1].get("query"), "检查项目结构")
        self.assertTrue(any(isinstance(chunk, str) and "两个核心问题" in chunk for chunk in chunks))
        self.assertTrue(any(isinstance(chunk, dict) and chunk.get("_tool_call", {}).get("executing") for chunk in chunks))
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertEqual(done.get("tool_used"), "folder_explore")
        self.assertEqual(done.get("success"), True)

    def test_unified_reply_with_tools_stream_keeps_long_trailing_handoff_before_recall_tool(self):
        executed = []

        def fake_stream(_cfg, messages, **_kwargs):
            has_tool_result = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
            if not has_tool_result:
                yield (
                    "主人，你说到点子上了！这确实是个很关键的问题。\n\n"
                    "我理解你的感受：\n"
                    "- 日常聊天还能接住\n"
                    "- 一到任务就容易断片\n\n"
                    "好消息是我现在有完整的记忆系统了。\n\n"
                    "让我先回忆一下我们最近的开发任务："
                )
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_recall_1",
                            "type": "function",
                            "function": {
                                "name": "recall_memory",
                                "arguments": json.dumps(
                                    {"query": "NovaNotes 开发项目 任务进度 最近遇到的问题"},
                                    ensure_ascii=False,
                                ),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 3}}
                return

            yield "我已经回忆完最近的开发任务了。"
            yield {"_usage": {"prompt_tokens": 7, "completion_tokens": 5}}

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {
                "success": True,
                "response": "已找到 NovaNotes 相关任务记忆",
                "meta": {
                    "action": {
                        "action_kind": "recall_memory",
                        "target_kind": "memory",
                        "display_hint": "已回忆开发任务",
                    }
                },
            }

        bundle = {
            "user_input": "而且说着说着就断了 感觉还是这个问题",
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

        self.assertEqual(executed[0][0], "recall_memory")
        self.assertEqual(executed[0][1].get("query"), "NovaNotes 开发项目 任务进度 最近遇到的问题")
        self.assertTrue(any(isinstance(chunk, dict) and chunk.get("_tool_call", {}).get("executing") for chunk in chunks))
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertEqual(done.get("tool_used"), "recall_memory")
        self.assertEqual(done.get("success"), True)

    def test_unified_reply_with_tools_stream_keeps_trailing_handoff_after_code_block(self):
        executed = []

        def fake_stream(_cfg, messages, **_kwargs):
            has_tool_result = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
            if not has_tool_result:
                yield (
                    "主人说得对，我刚才的表达确实不够清晰。让我重新解释一下：\n\n"
                    "### 1. 检查当前配置\n"
                    "我们应该查看代码里关于记忆 token 的设置。\n\n"
                    "### 2. 具体要查什么\n"
                    "```python\n"
                    "max_tokens = 4096\n"
                    "context_window = 8192\n"
                    "memory_limit = 4096\n"
                    "```\n\n"
                    "## 📝 让我实际查看一下"
                )
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_read_cfg_1",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": json.dumps(
                                    {"file_path": "C:/Users/36459/NovaCore/agent_final.py"},
                                    ensure_ascii=False,
                                ),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 3}}
                return

            yield "我已经查看过相关配置位置。"
            yield {"_usage": {"prompt_tokens": 7, "completion_tokens": 5}}

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {
                "success": True,
                "response": "已查看 agent_final.py",
                "meta": {
                    "action": {
                        "action_kind": "read_file",
                        "target_kind": "file",
                        "display_hint": "已查看 agent_final.py",
                    }
                },
            }

        bundle = {
            "user_input": "看看我们的记忆 token 设置情况是什么意思",
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

        self.assertEqual(executed[0][0], "read_file")
        self.assertEqual(executed[0][1].get("file_path"), "C:/Users/36459/NovaCore/agent_final.py")
        self.assertTrue(any(isinstance(chunk, dict) and chunk.get("_tool_call", {}).get("executing") for chunk in chunks))
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertEqual(done.get("tool_used"), "read_file")
        self.assertEqual(done.get("success"), True)

    def test_finalize_tool_reply_strips_trailing_handoff_after_grounded_answer(self):
        reply = reply_formatter_module._finalize_tool_reply(
            "问题已经定位到 `settings.js` 的旧监听器覆盖。\n\n"
            "把初始化顺序改成先注册 store，再挂 click handler，就能避免重复触发。\n\n"
            "让我继续把剩下的交互链路也过一遍。",
            success=True,
            action_summary="已定位旧监听器覆盖问题",
            tool_response="已定位旧监听器覆盖问题",
            run_meta={"action": {"display_hint": "已定位旧监听器覆盖问题"}},
        )

        self.assertIn("问题已经定位到 `settings.js` 的旧监听器覆盖", reply)
        self.assertIn("先注册 store", reply)
        self.assertNotIn("让我继续把剩下的交互链路也过一遍", reply)

    def test_finalize_tool_reply_replaces_structured_handoff_only_reply_with_closeout(self):
        reply = reply_formatter_module._finalize_tool_reply(
            "1. 先确认目录\n2. 再比对配置\n让我继续检查剩余文件。",
            success=True,
            action_summary="已完成目录和配置检查",
            tool_response="目录和配置已检查",
            run_meta={"action": {"display_hint": "已完成目录和配置检查"}},
        )

        self.assertIn("这一步已经完成", reply)
        self.assertIn("已完成目录和配置检查", reply)
        self.assertNotIn("让我继续检查剩余文件", reply)

    def test_stream_success_reply_strips_trailing_handoff_tail(self):
        def fake_stream(_cfg, messages, **_kwargs):
            has_tool_result = any(isinstance(m, dict) and m.get("role") == "tool" for m in messages)
            if not has_tool_result:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_fix_trace_1",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": json.dumps(
                                    {"file_path": "notes_app/settings.js"},
                                    ensure_ascii=False,
                                ),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 3}}
                return

            yield (
                "问题已经定位到按钮重复绑定。\n\n"
                "把旧的全局 click handler 改成局部委托，就不会再重复触发。\n\n"
                "让我继续把剩下的文件也看一遍。"
            )
            yield {"_usage": {"prompt_tokens": 7, "completion_tokens": 2}}

        def fake_tool_executor(_name, _args, _context):
            return {
                "success": True,
                "response": "Found duplicated click handlers.",
                "meta": {
                    "action": {
                        "action_kind": "read_file",
                        "target_kind": "file",
                        "target": "notes_app/settings.js",
                        "outcome": "inspected",
                        "display_hint": "已定位按钮重复绑定",
                    }
                },
            }

        bundle = {
            "user_input": "看下为什么按钮会重复触发",
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

        visible_text = "".join(chunk for chunk in chunks if isinstance(chunk, str))
        self.assertIn("问题已经定位到按钮重复绑定", visible_text)
        self.assertIn("局部委托", visible_text)
        self.assertNotIn("让我继续把剩下的文件也看一遍", visible_text)
        self.assertEqual(chunks[-1].get("success"), True)


    def test_unified_reply_with_tools_stream_forwards_stream_reset_signal(self):
        def fake_stream(_cfg, _messages, **_kwargs):
            yield "half reply"
            yield {"_stream_reset": {"reason": "stream_exception_fallback"}}
            yield "final reply"
            yield {"_usage": {"prompt_tokens": 3, "completion_tokens": 2}}

        bundle = {
            "user_input": "continue",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], lambda *_args: {}))

        reset_index = next(
            i for i, chunk in enumerate(chunks) if isinstance(chunk, dict) and chunk.get("_stream_reset")
        )

        self.assertEqual(chunks[0], "half reply")
        self.assertEqual(chunks[reset_index].get("_stream_reset", {}).get("reason"), "stream_exception_fallback")
        self.assertEqual(chunks[reset_index + 1], "final reply")
        self.assertEqual(chunks[-1].get("_done"), True)


class TargetProtocolPathResolutionTests(unittest.TestCase):
    def test_resolve_target_reference_prefers_explicit_local_path_inside_sentence(self):
        resolved = target_protocol_module.resolve_target_reference(r"C:\Users\36459\NovaNotes\ 项目结构", {})

        self.assertEqual(resolved.get("target_type"), "path")
        self.assertEqual(str(resolved.get("value") or "").replace("\\", "/"), "C:/Users/36459/NovaNotes")
        self.assertEqual(resolved.get("source"), "direct_path")

    def test_resolve_local_app_reference_does_not_treat_directory_path_as_app(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            resolved = target_protocol_module.resolve_local_app_reference(f"{temp_dir} 项目结构", {})

        self.assertEqual(resolved.get("target_type"), "unknown")
        self.assertEqual(resolved.get("source"), "explicit_path_non_app")


if __name__ == "__main__":
    unittest.main()
