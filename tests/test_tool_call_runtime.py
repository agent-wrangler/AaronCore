import unittest

from core.decision_runtime.tool_runtime.events import build_tool_turn_done_event
from core.decision_runtime.tool_runtime.ledger import ToolCallRecord, ToolCallTurnLedger
from decision.tool_runtime.events import build_tool_call_done_event, build_tool_call_executing_event
from decision.tool_runtime.process_meta import build_attempt_process_meta, build_done_process_meta


class ToolCallRuntimeTests(unittest.TestCase):
    def test_tool_call_events_carry_process_meta_for_fallback_retry(self):
        attempt_meta = build_attempt_process_meta(
            recent_attempts=[{"tool": "run_command", "success": False, "summary": "命令被拦截：不允许命令链或重定向"}],
            tool_name="search_text",
            round_index=1,
            batch_index=1,
            batch_size=1,
        )
        record = ToolCallRecord(
            call_id="call_search_1",
            tool_name="search_text",
            status="completed",
            success=True,
            response="search_text ok",
            action_summary="找到 12 条结果",
        )
        done_meta = build_done_process_meta(record=record, attempt_meta=attempt_meta)

        executing_event = build_tool_call_executing_event(record, process_meta=attempt_meta)
        done_event = build_tool_call_done_event(record, process_meta=done_meta)

        self.assertEqual(executing_event["_tool_call"]["process_meta"]["attempt_kind"], "fallback")
        self.assertEqual(executing_event["_tool_call"]["process_meta"]["previous_tool"], "run_command")
        self.assertEqual(done_event["_tool_call"]["process_meta"]["outcome_kind"], "success")
        self.assertEqual(done_event["_tool_call"]["process_meta"]["next_hint_kind"], "continue")

    def test_build_done_process_meta_marks_runtime_failures_and_blocked_paths(self):
        blocked_record = ToolCallRecord(
            call_id="call_blocked_1",
            tool_name="open_target",
            status="synthetic_failed",
            success=False,
            synthetic=True,
            reason="blocked_by_user_takeover",
        )
        blocked_meta = build_done_process_meta(
            record=blocked_record,
            attempt_meta={},
            reason="blocked_by_user_takeover",
            requires_user_takeover=True,
        )
        self.assertEqual(blocked_meta["outcome_kind"], "blocked")
        self.assertEqual(blocked_meta["next_hint_kind"], "wait_for_user")

        runtime_record = ToolCallRecord(
            call_id="call_env_1",
            tool_name="sense_environment",
            status="synthetic_failed",
            success=False,
            synthetic=True,
            reason="tool_executor_exception",
            response="boom",
        )
        runtime_meta = build_done_process_meta(
            record=runtime_record,
            attempt_meta={"attempt_kind": "retry"},
            reason="tool_executor_exception",
        )
        self.assertEqual(runtime_meta["outcome_kind"], "runtime_failure")
        self.assertEqual(runtime_meta["next_hint_kind"], "retry_or_close")

    def test_flush_unfinished_marks_pending_and_executing_calls_as_synthetic_failures(self):
        ledger = ToolCallTurnLedger()
        first = ledger.register(
            {"id": "call_1"},
            tool_name="sense_environment",
            tool_args={"detail_level": "basic"},
            preview="inspect environment",
        )
        second = ledger.register(
            {"id": "call_2"},
            tool_name="folder_explore",
            tool_args={"query": "repo"},
            preview="inspect repo",
        )
        ledger.mark_executing(second.call_id)

        flushed = ledger.flush_unfinished(
            reason="tool_call_runtime_exception",
            response_factory=lambda record: f"{record.tool_name} failed",
            action_summary_factory=lambda record: f"{record.tool_name} summary",
            run_meta_factory=lambda record: {"tool": record.tool_name},
        )

        self.assertEqual([record.call_id for record in flushed], [first.call_id, second.call_id])
        self.assertTrue(all(record.synthetic for record in flushed))
        self.assertTrue(all(record.is_terminal for record in flushed))
        self.assertTrue(all(record.success is False for record in flushed))
        self.assertEqual(flushed[0].response, "sense_environment failed")
        self.assertEqual(flushed[1].action_summary, "folder_explore summary")
        self.assertEqual(flushed[1].run_meta.get("tool"), "folder_explore")

    def test_build_tool_turn_done_event_exposes_terminal_metadata(self):
        record = ToolCallRecord(
            call_id="call_env_1",
            tool_name="sense_environment",
            status="synthetic_failed",
            success=False,
            response="sense_environment 没有完成",
            action_summary="environment failed",
            run_meta={"action": {"action_kind": "inspect_environment"}},
            synthetic=True,
            reason="stream_signal_dropped",
        )

        event = build_tool_turn_done_event(record, {"prompt_tokens": 3, "completion_tokens": 1})

        self.assertEqual(event.get("_done"), True)
        self.assertEqual(event.get("tool_used"), "sense_environment")
        self.assertEqual(event.get("success"), False)
        self.assertEqual(event.get("tool_response"), "sense_environment 没有完成")
        self.assertEqual(event.get("call_id"), "call_env_1")
        self.assertEqual(event.get("reason"), "stream_signal_dropped")
        self.assertTrue(event.get("synthetic"))
        self.assertEqual(event.get("run_meta", {}).get("action", {}).get("action_kind"), "inspect_environment")

    def test_build_tool_turn_done_event_exposes_batch_metadata(self):
        first = ToolCallRecord(
            call_id="call_1",
            tool_name="folder_explore",
            status="completed",
            success=True,
        )
        second = ToolCallRecord(
            call_id="call_2",
            tool_name="search_text",
            status="completed",
            success=True,
        )

        event = build_tool_turn_done_event(second, {"prompt_tokens": 2}, records=[first, second])

        self.assertEqual(event.get("tools_used"), ["folder_explore", "search_text"])
        self.assertEqual(event.get("action_count"), 2)
        self.assertTrue(event.get("batch_mode"))
        self.assertEqual(len(event.get("tool_results") or []), 2)


if __name__ == "__main__":
    unittest.main()
