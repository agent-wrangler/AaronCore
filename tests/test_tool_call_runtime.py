import json
import re
import unittest
from unittest.mock import patch

from core.fs_protocol import build_operation_result
from core.decision_runtime.tool_runtime.events import build_tool_turn_done_event
from core.decision_runtime.tool_runtime.ledger import ToolCallRecord, ToolCallTurnLedger
from decision.tool_runtime import dispatcher as dispatcher_module
from decision.tool_runtime import result_resolution as result_resolution_module
from decision.tool_runtime import signal_recovery as signal_recovery_module
from decision.tool_runtime.events import build_tool_call_done_event, build_tool_call_executing_event
from decision.tool_runtime.process_meta import build_attempt_process_meta, build_done_process_meta


class ToolCallRuntimeTests(unittest.TestCase):
    def test_text_compat_tool_inference_is_initial_only(self):
        compat_tool_call = {
            "id": "call_open_1",
            "type": "function",
            "function": {"name": "open_target", "arguments": '{"target":"https://www.baidu.com"}'},
        }
        bundle = {"user_input": "打开百度", "context_data": {}}

        initial = result_resolution_module.resolve_tool_calls_from_result(
            {"content": "我先帮你打开网页。"},
            bundle,
            mode="stream_initial",
            parse_legacy_tool_call_text=lambda *_args, **_kwargs: None,
            force_app_tool_call_from_reply=lambda *_args, **_kwargs: None,
            infer_action_tool_call_from_reply=lambda *_args, **_kwargs: compat_tool_call,
            infer_directory_resolution_tool_call=lambda *_args, **_kwargs: None,
            debug_write=lambda *_args, **_kwargs: None,
        )
        followup = result_resolution_module.resolve_tool_calls_from_result(
            {"content": "我继续帮你打开网页。"},
            bundle,
            mode="stream_round_1",
            parse_legacy_tool_call_text=lambda *_args, **_kwargs: compat_tool_call,
            force_app_tool_call_from_reply=lambda *_args, **_kwargs: compat_tool_call,
            infer_action_tool_call_from_reply=lambda *_args, **_kwargs: compat_tool_call,
            infer_directory_resolution_tool_call=lambda *_args, **_kwargs: None,
            debug_write=lambda *_args, **_kwargs: None,
        )

        self.assertEqual(initial, [compat_tool_call])
        self.assertIsNone(followup)

    def test_infer_action_tool_call_prefers_open_target_for_known_web_search(self):
        with patch("core.target_protocol._llm_resolve_target", return_value=None):
            tool_call = signal_recovery_module.infer_action_tool_call_from_reply(
                "我来帮你打开百度搜索。",
                "打开百度 搜索agent",
                {},
                re_mod=re,
                json_module=json,
            )

        self.assertIsNotNone(tool_call)
        self.assertEqual(tool_call["function"]["name"], "open_target")
        args = json.loads(tool_call["function"]["arguments"])
        self.assertEqual(args.get("path"), "https://www.baidu.com")
        self.assertEqual(args.get("user_input"), "打开百度 搜索agent")

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

    def test_build_attempt_process_meta_infers_execution_lane_from_current_step_task(self):
        attempt_meta = build_attempt_process_meta(
            recent_attempts=[],
            tool_name="run_command",
            round_index=1,
            batch_index=1,
            batch_size=1,
            working_state={
                "current_step": "Verify the patch",
                "execution_lane": "verify",
                "current_step_task": {
                    "task_id": "task_step_verify",
                    "title": "Verify the patch",
                    "status": "active",
                },
            },
        )

        self.assertEqual(attempt_meta.get("execution_lane"), "verify")
        self.assertEqual(attempt_meta.get("current_step_task_id"), "task_step_verify")
        self.assertEqual(attempt_meta.get("current_step_task_title"), "Verify the patch")
        self.assertEqual(attempt_meta.get("current_step_task_status"), "active")

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

        interrupted_record = ToolCallRecord(
            call_id="call_interrupt_1",
            tool_name="sense_environment",
            status="synthetic_failed",
            success=False,
            synthetic=True,
            reason="user_interrupted",
            response="interrupted",
        )
        interrupted_meta = build_done_process_meta(
            record=interrupted_record,
            attempt_meta={"attempt_kind": "retry"},
            reason="user_interrupted",
        )
        self.assertEqual(interrupted_meta["outcome_kind"], "interrupted")
        self.assertEqual(interrupted_meta["next_hint_kind"], "resume_or_close")

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

    def test_build_done_process_meta_marks_success_that_needs_user_takeover(self):
        record = ToolCallRecord(
            call_id="call_login_1",
            tool_name="open_target",
            status="completed",
            success=True,
            response="opened login page",
            action_summary="已打开登录页",
        )

        meta = build_done_process_meta(
            record=record,
            attempt_meta={"attempt_kind": "initial"},
            requires_user_takeover=True,
        )

        self.assertEqual(meta["outcome_kind"], "success")
        self.assertEqual(meta["next_hint_kind"], "wait_for_user")

    def test_build_done_process_meta_marks_verification_failures_from_runtime_state(self):
        record = ToolCallRecord(
            call_id="call_verify_1",
            tool_name="write_file",
            status="completed",
            success=True,
            response="write_file completed but verification failed",
            action_summary="updated target file",
            run_meta={
                "action": {
                    "action_kind": "write_file",
                    "target_kind": "file",
                    "target": "C:/repo/result.txt",
                    "outcome": "edited",
                    "verification_mode": "artifact_exists",
                    "verification_detail": "Expected output file is still missing",
                },
                "verification": {
                    "verified": False,
                    "detail": "Expected output file is still missing",
                    "verification_mode": "artifact_exists",
                },
            },
        )

        meta = build_done_process_meta(
            record=record,
            attempt_meta={"attempt_kind": "retry"},
        )

        self.assertEqual(meta["outcome_kind"], "verify_failed")
        self.assertEqual(meta["next_hint_kind"], "retry_or_close")
        self.assertEqual((meta.get("runtime_state") or {}).get("status"), "verify_failed")

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
        self.assertEqual(event.get("status"), "runtime_failed")
        self.assertEqual(event.get("next_action"), "retry_or_close")

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
        self.assertEqual((event.get("tool_results") or [])[0].get("status"), "done")
        self.assertEqual((event.get("tool_results") or [])[1].get("next_action"), "continue")

    def test_build_tool_turn_done_event_includes_verification_payload(self):
        record = ToolCallRecord(
            call_id="call_verify_1",
            tool_name="write_file",
            status="completed",
            success=True,
            response="write_file completed but verification failed",
            action_summary="updated target file",
            run_meta={
                "action": {
                    "action_kind": "write_file",
                    "target_kind": "file",
                    "target": "C:/repo/result.txt",
                    "outcome": "edited",
                    "verification_mode": "artifact_exists",
                    "verification_detail": "Expected output file is still missing",
                },
                "verification": {
                    "verified": False,
                    "detail": "Expected output file is still missing",
                    "verification_mode": "artifact_exists",
                },
            },
        )

        event = build_tool_turn_done_event(record, {"prompt_tokens": 2}, records=[record])

        self.assertEqual(event.get("status"), "verify_failed")
        self.assertEqual(event.get("next_action"), "retry_or_close")
        self.assertEqual((event.get("verification") or {}).get("detail"), "Expected output file is still missing")
        result_row = (event.get("tool_results") or [])[0]
        self.assertEqual(result_row.get("status"), "verify_failed")
        self.assertEqual(result_row.get("next_action"), "retry_or_close")
        self.assertEqual((result_row.get("verification") or {}).get("status"), "failed")

    def test_normalize_tool_adapter_result_adds_runtime_state_for_user_takeover(self):
        result = dispatcher_module.normalize_tool_adapter_result(
            build_operation_result(
                "Current page needs login first.",
                expected_state="auth_cleared",
                observed_state="auth_required",
                drift_reason="auth_required",
                repair_hint="user_login_required",
                action_kind="open_url",
                target_kind="url",
                target="https://www.douyin.com",
                outcome="blocked",
                verification_mode="browser_search_submit",
                verification_detail="Douyin login prompt",
            ),
            name="open_target",
        )

        self.assertEqual(result.get("status"), "waiting_user")
        self.assertEqual(result.get("next_action"), "wait_for_user")
        self.assertFalse(result.get("verified"))
        self.assertEqual(result.get("blocker"), "Douyin login prompt")
        self.assertEqual((result.get("meta", {}).get("runtime_state") or {}).get("status"), "waiting_user")
        self.assertFalse(isinstance(result.get("fs_target"), dict))

    def test_normalize_legacy_operation_result_preserves_takeover_signals(self):
        result = dispatcher_module.normalize_tool_adapter_result(
            build_operation_result(
                "当前网页需要先完成登录或验证，暂时不能继续自动搜索：`AI`",
                expected_state="auth_cleared",
                observed_state="auth_required",
                drift_reason="auth_required",
                repair_hint="user_login_required",
                action_kind="open_url",
                target_kind="url",
                target="https://www.douyin.com",
                outcome="blocked",
                verification_mode="browser_search_submit",
                verification_detail="Douyin login prompt",
            ),
            name="open_target",
        )

        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("meta", {}).get("drift", {}).get("reason"), "auth_required")
        self.assertEqual(result.get("meta", {}).get("action", {}).get("outcome"), "blocked")
        self.assertFalse(result.get("meta", {}).get("verification", {}).get("verified"))
        self.assertTrue(signal_recovery_module.tool_requires_user_takeover(result))

    def test_normalize_legacy_operation_result_marks_verified_success(self):
        result = dispatcher_module.normalize_tool_adapter_result(
            build_operation_result(
                "已打开网页：`https://www.douyin.com`",
                expected_state="url_opened",
                observed_state="url_opened",
                action_kind="open_url",
                target_kind="url",
                target="https://www.douyin.com",
                outcome="opened",
                verification_mode="window_changed",
                verification_detail="Window count changed",
            ),
            name="open_target",
        )

        self.assertTrue(result.get("success"))
        self.assertTrue(result.get("meta", {}).get("verification", {}).get("verified"))
        self.assertEqual(result.get("meta", {}).get("action", {}).get("target_kind"), "url")

    def test_normalize_tool_adapter_result_adds_fs_target_for_file_like_results(self):
        result = dispatcher_module.normalize_tool_adapter_result(
            build_operation_result(
                "Listed the target directory.",
                expected_state="directory_listed",
                observed_state="directory_listed",
                action_kind="list_directory",
                target_kind="directory",
                target="C:/repo/src",
                outcome="resolved",
                verification_mode="directory_listed",
                verification_detail="dirs=3 files=12",
            ),
            name="folder_explore",
        )

        self.assertEqual(result.get("status"), "verified")
        self.assertEqual(result.get("next_action"), "continue")
        self.assertTrue(result.get("verified"))
        self.assertEqual((result.get("fs_target") or {}).get("path"), "C:/repo/src")
        self.assertEqual((result.get("fs_target") or {}).get("kind"), "directory")

    def test_normalize_tool_adapter_result_marks_verify_failed_as_retry_or_close(self):
        result = dispatcher_module.normalize_tool_adapter_result(
            build_operation_result(
                "Saved the file, but the expected artifact is still missing.",
                expected_state="artifact_created",
                observed_state="artifact_absent",
                action_kind="write_file",
                target_kind="file",
                target="C:/repo/result.txt",
                outcome="edited",
                verification_mode="artifact_exists",
                verification_detail="Expected output file is still missing",
            ),
            name="write_file",
        )

        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("status"), "verify_failed")
        self.assertEqual(result.get("next_action"), "retry_or_close")
        self.assertFalse(result.get("verified"))
        self.assertEqual((result.get("verification") or {}).get("verification_mode"), "artifact_exists")


if __name__ == "__main__":
    unittest.main()
