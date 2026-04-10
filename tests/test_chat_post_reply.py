import sys
import types
import unittest

from routes.chat_post_reply import (
    build_feedback_awareness_event,
    build_repair_payload,
    build_process_payload,
    persist_reply_artifacts,
    record_feedback_memory_hit,
    should_schedule_autolearn,
    update_companion_reply_state,
)


class _Companion:
    activity = "thinking"
    reply_id = ""
    last_reply = ""
    last_reply_full = ""
    emotion = "neutral"


class ChatPostReplyTests(unittest.TestCase):
    def test_update_companion_reply_state(self):
        companion = _Companion()
        update_companion_reply_state(
            companion,
            "这是\n一条回复",
            detect_emotion=lambda text: "happy",
        )
        self.assertEqual(companion.activity, "idle")
        self.assertEqual(companion.last_reply_full, "这是 一条回复")
        self.assertEqual(companion.emotion, "happy")
        self.assertTrue(companion.reply_id)

    def test_build_feedback_awareness_event(self):
        event = build_feedback_awareness_event({
            "id": "fb-1",
            "scene": "chat",
            "problem": "too vague",
            "category": "format",
            "fix": "be direct",
        })
        self.assertEqual(event["type"], "l7_feedback")
        self.assertEqual(event["detail"]["id"], "fb-1")
        self.assertIn("format", event["summary"])

    def test_should_schedule_autolearn(self):
        config = {
            "enabled": True,
            "allow_web_search": True,
            "allow_knowledge_write": True,
        }
        self.assertTrue(should_schedule_autolearn(config, feedback_rule=None, l8=[]))
        self.assertFalse(should_schedule_autolearn(config, feedback_rule={"id": "x"}, l8=[]))
        self.assertFalse(
            should_schedule_autolearn(
                config,
                feedback_rule=None,
                l8=[],
                route={"intent": "missing_skill"},
                forbid_missing_skill_intent=True,
            )
        )

    def test_build_process_payload(self):
        payload = build_process_payload(
            [{"step_key": "a"}],
            normalize_steps=lambda steps: [{"step_key": item["step_key"], "ok": True} for item in steps],
            task_plan={"goal": "finish"},
            include_empty_steps_with_plan=True,
        )
        self.assertEqual(payload["plan"]["goal"], "finish")
        self.assertEqual(payload["steps"][0]["step_key"], "a")

    def test_persist_reply_artifacts_runs_clean_and_memory(self):
        saved = {}
        remembered = []
        result = persist_reply_artifacts(
            "最终答案",
            [],
            steps=[{"step_key": "a"}],
            normalize_steps=lambda steps: steps,
            persist_assistant_history_entry=lambda role, text, process=None: saved.update(
                {"role": role, "text": text, "process": process}
            ),
            debug_write=lambda *_args, **_kwargs: None,
            add_memory=lambda text: remembered.append(text),
            task_plan={"goal": "finish"},
            include_empty_steps_with_plan=True,
        )
        self.assertEqual(result, "最终答案")
        self.assertEqual(saved["role"], "nova")
        self.assertEqual(saved["text"], "最终答案")
        self.assertEqual(saved["process"]["plan"]["goal"], "finish")
        self.assertEqual(remembered, ["最终答案"])

    def test_persist_reply_artifacts_skips_transient_model_error_notice(self):
        saved = []
        remembered = []
        text = "当前模型接口余额不足，暂时无法继续。请充值后重试，或先切换到其他模型。"
        result = persist_reply_artifacts(
            text,
            [],
            steps=[{"step_key": "a"}],
            normalize_steps=lambda steps: steps,
            persist_assistant_history_entry=lambda role, reply, process=None: saved.append(
                {"role": role, "text": reply, "process": process}
            ),
            debug_write=lambda *_args, **_kwargs: None,
            add_memory=lambda reply: remembered.append(reply),
            task_plan={"goal": "finish"},
            include_empty_steps_with_plan=True,
        )
        self.assertEqual(result, text)
        self.assertEqual(saved, [])
        self.assertEqual(remembered, [])

    def test_persist_reply_artifacts_skips_missing_execution_closeout_notice(self):
        saved = []
        remembered = []
        text = (
            "主人，刚才那个说桌面没有临时文档文件夹的回复不可靠，我并没有实际完成检查操作。😅\n\n"
            "我需要重新执行真实的检查，看看临时文档文件夹到底还在不在。\n\n"
            "让我重新检查一下！😊"
        )
        result = persist_reply_artifacts(
            text,
            [],
            steps=[{"step_key": "a"}],
            normalize_steps=lambda steps: steps,
            persist_assistant_history_entry=lambda role, reply, process=None: saved.append(
                {"role": role, "text": reply, "process": process}
            ),
            debug_write=lambda *_args, **_kwargs: None,
            add_memory=lambda reply: remembered.append(reply),
            task_plan={"goal": "finish"},
            include_empty_steps_with_plan=True,
        )
        self.assertEqual(result, text)
        self.assertEqual(saved, [])
        self.assertEqual(remembered, [])

    def test_build_repair_payload_uses_agent_final(self):
        original = sys.modules.get("agent_final")
        sys.modules["agent_final"] = types.SimpleNamespace(
            build_repair_progress_payload=lambda route, feedback_rule: {"show": True, "route": route}
        )
        try:
            payload = build_repair_payload({"mode": "chat"}, {"id": "fb"})
        finally:
            if original is None:
                sys.modules.pop("agent_final", None)
            else:
                sys.modules["agent_final"] = original
        self.assertTrue(payload["show"])
        self.assertEqual(payload["route"]["mode"], "chat")

    def test_record_feedback_memory_hit_accepts_empty_input(self):
        record_feedback_memory_hit(None)


if __name__ == "__main__":
    unittest.main()
