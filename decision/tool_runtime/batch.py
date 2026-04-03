from __future__ import annotations

from dataclasses import dataclass, field

from decision.tool_runtime.events import (
    build_tool_call_done_event,
    build_tool_call_executing_event,
    synthesize_tool_failure_response,
)
from decision.tool_runtime.ledger import ToolCallRecord, ToolCallTurnLedger
from decision.tool_runtime.process_meta import (
    build_attempt_process_meta,
    build_done_process_meta,
)
from decision.tool_runtime.parallel_runtime import (
    ParallelCallSpec,
    ParallelToolExecutionError,
    execute_parallel_tool_calls,
    is_parallel_safe_tool,
)


@dataclass
class ToolCallBatchState:
    tool_used: str = ""
    run_meta: dict = field(default_factory=dict)
    tool_success: bool | None = None
    action_summary: str = ""
    tool_response: str = ""
    arg_failure: dict | None = None
    tool_args: dict = field(default_factory=dict)
    recent_attempts: list[dict] = field(default_factory=list)
    followup_tools: list[dict] = field(default_factory=list)


@dataclass
class ToolCallBatchOutcome:
    state: ToolCallBatchState
    tool_calls: list[dict] = field(default_factory=list)
    records: list[ToolCallRecord] = field(default_factory=list)
    tool_messages: list[dict] = field(default_factory=list)
    guidance_notes: list[str] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    requires_user_takeover: bool = False
    strict_retry_note: str = ""


def create_tool_call_batch_state(tools: list[dict] | None = None) -> ToolCallBatchState:
    return ToolCallBatchState(followup_tools=list(tools or []))


def _record_result_message(tool_call: dict, response: str) -> dict:
    return {
        "role": "tool",
        "tool_call_id": tool_call.get("id", "") if isinstance(tool_call, dict) else "",
        "content": str(response or ""),
    }


def _append_recent_attempt(
    state: ToolCallBatchState,
    *,
    tool_name: str,
    success: bool,
    summary: str,
    arg_failure: dict | None,
) -> None:
    state.recent_attempts.append(
        {
            "tool": tool_name,
            "success": bool(success),
            "summary": str(summary or "").strip(),
            "arg_failure": arg_failure,
        }
    )


def _append_shadow_recent_attempt(
    attempts: list[dict],
    *,
    tool_name: str,
    summary: str,
    arg_failure: dict | None,
) -> None:
    attempts.append(
        {
            "tool": tool_name,
            "success": False,
            "summary": str(summary or "").strip(),
            "arg_failure": arg_failure,
        }
    )


def _update_state_after_record(
    state: ToolCallBatchState,
    *,
    tools: list[dict],
    bundle: dict,
    record: ToolCallRecord,
    tool_args: dict,
    arg_failure: dict | None,
) -> None:
    from decision import reply_formatter as formatter

    state.tool_used = record.tool_name
    state.run_meta = record.run_meta if isinstance(record.run_meta, dict) else {}
    state.tool_success = record.success
    state.action_summary = record.action_summary or state.action_summary
    state.tool_response = record.response
    state.arg_failure = arg_failure
    state.tool_args = dict(tool_args or {})
    state.followup_tools = formatter._build_followup_tools_after_arg_failure(
        tools,
        state.arg_failure,
        state.tool_args,
        bundle,
        current_tool_name=record.tool_name,
    )


def append_tool_batch_to_messages(
    messages: list[dict],
    outcome: ToolCallBatchOutcome,
    *,
    reasoning_details=None,
) -> None:
    from decision import reply_formatter as formatter

    if outcome.tool_calls:
        messages.append(
            formatter._build_assistant_history_message(
                None,
                tool_calls=outcome.tool_calls,
                reasoning_details=reasoning_details,
            )
        )
    messages.extend(outcome.tool_messages)
    for note in outcome.guidance_notes:
        formatter._append_runtime_guidance(messages, note)


def _emit_batch_event(
    outcome: ToolCallBatchOutcome,
    event: dict,
    *,
    event_callback=None,
) -> None:
    outcome.events.append(event)
    if callable(event_callback):
        event_callback(event)


def _plan_prepared_call(
    formatter,
    state: ToolCallBatchState,
    shadow_recent_attempts: list[dict],
    *,
    tool_name: str,
    tool_args: dict,
) -> dict:
    missing_fields = formatter._missing_required_tool_fields(tool_name, tool_args)
    arg_failure = (
        formatter._tool_arg_failure_signature(tool_name, tool_args, missing_fields)
        if missing_fields
        else None
    )
    repeated_invalid_args = bool(
        arg_failure and formatter._has_same_arg_failure_recently(shadow_recent_attempts, arg_failure)
    )
    failure_summary = ""
    if arg_failure:
        failure_response = formatter._build_tool_arg_failure_feedback(tool_name, tool_args, missing_fields)
        failure_summary = formatter._summarize_tool_response_text(failure_response) or state.action_summary
        _append_shadow_recent_attempt(
            shadow_recent_attempts,
            tool_name=tool_name,
            summary=failure_summary,
            arg_failure=arg_failure,
        )
    return {
        "missing_fields": missing_fields,
        "arg_failure": arg_failure,
        "repeated_invalid_args": repeated_invalid_args,
        "failure_summary": failure_summary,
    }


def _handle_repeated_invalid_args(
    *,
    formatter,
    outcome: ToolCallBatchOutcome,
    ledger: ToolCallTurnLedger,
    state: ToolCallBatchState,
    tools: list[dict],
    bundle: dict,
    tool_call: dict,
    tool_name: str,
    tool_args: dict,
    record: ToolCallRecord,
    plan: dict,
    mode: str,
    round_index: int | None,
    batch_index: int,
    batch_size: int,
    event_callback=None,
) -> None:
    arg_failure = plan.get("arg_failure")
    missing_fields = list(plan.get("missing_fields") or [])
    formatter._debug_write(
        "tool_call_repeated_invalid_args",
        {
            "mode": mode,
            "tool": tool_name,
            "target": arg_failure.get("target", "") if isinstance(arg_failure, dict) else "",
            "missing_fields": list(arg_failure.get("missing_fields") or ()) if isinstance(arg_failure, dict) else [],
            "round": round_index or 0,
            "batch_index": batch_index,
            "batch_size": batch_size,
        },
    )
    failure_response = formatter._build_tool_arg_failure_feedback(tool_name, tool_args, missing_fields)
    failure_summary = str(plan.get("failure_summary") or "").strip() or formatter._summarize_tool_response_text(failure_response) or state.action_summary
    attempt_meta = build_attempt_process_meta(
        recent_attempts=state.recent_attempts,
        tool_name=tool_name,
        round_index=round_index,
        batch_index=batch_index,
        batch_size=batch_size,
    )
    terminal = ledger.mark_terminal(
        record.call_id,
        success=False,
        response=failure_response,
        action_summary=failure_summary,
        run_meta={},
        reason="repeated_invalid_args",
    ) or record
    outcome.records.append(terminal)
    outcome.tool_messages.append(_record_result_message(tool_call, failure_response))
    _emit_batch_event(
        outcome,
        build_tool_call_done_event(
            terminal,
            process_meta=build_done_process_meta(
                record=terminal,
                attempt_meta=attempt_meta,
                reason="repeated_invalid_args",
                arg_failure=arg_failure,
            ),
        ),
        event_callback=event_callback,
    )
    _append_recent_attempt(
        state,
        tool_name=tool_name,
        success=False,
        summary=failure_summary,
        arg_failure=arg_failure,
    )
    _update_state_after_record(
        state,
        tools=tools,
        bundle=bundle,
        record=terminal,
        tool_args=tool_args,
        arg_failure=arg_failure,
    )
    if formatter._is_write_file_content_arg_failure(arg_failure):
        outcome.strict_retry_note = formatter._build_strict_write_file_retry_note(tool_args, arg_failure)


def close_tool_call_batch_as_synthetic_failure(
    ledger: ToolCallTurnLedger,
    tool_calls: list[dict] | None,
    bundle: dict,
    *,
    reason: str,
    detail: str = "",
) -> list[ToolCallRecord]:
    from decision import reply_formatter as formatter

    closed: list[ToolCallRecord] = []
    for raw_tool_call in tool_calls or []:
        sanitized, tool_name, tool_args, preview = formatter._prepare_tool_call_runtime(raw_tool_call, bundle)
        record = ledger.register(
            sanitized,
            tool_name=tool_name,
            tool_args=tool_args,
            preview=preview,
        )
        if record.is_terminal:
            closed.append(record)
            continue
        response = synthesize_tool_failure_response(tool_name, reason, detail=detail)
        summary = formatter._summarize_tool_response_text(response)
        terminal = ledger.mark_terminal(
            record.call_id,
            success=False,
            response=response,
            action_summary=summary,
            run_meta={},
            synthetic=True,
            reason=reason,
        )
        if terminal:
            closed.append(terminal)
    return closed


def _apply_exec_result(
    *,
    formatter,
    outcome: ToolCallBatchOutcome,
    ledger: ToolCallTurnLedger,
    state: ToolCallBatchState,
    tools: list[dict],
    bundle: dict,
    prepared_calls: list[tuple[dict, str, dict, str, ToolCallRecord]],
    index: int,
    tool_call: dict,
    tool_name: str,
    tool_args: dict,
    record: ToolCallRecord,
    plan: dict,
    exec_result: dict,
    round_index: int | None = None,
    attempt_meta: dict | None = None,
    event_callback=None,
) -> bool:
    missing_fields = list(plan.get("missing_fields") or [])
    arg_failure = plan.get("arg_failure")
    success = bool(exec_result.get("success", False))
    response = exec_result.get("response", "") if success else f"执行失败: {exec_result.get('error', '')}"
    if arg_failure and not success:
        response = formatter._build_tool_arg_failure_feedback(tool_name, tool_args, missing_fields)
    action_summary = formatter._tool_action_summary(exec_result)
    if formatter._tool_has_unresolved_drift(exec_result):
        response = formatter._append_drift_note(response, exec_result)
    terminal = ledger.mark_terminal(
        record.call_id,
        success=success,
        response=response,
        action_summary=action_summary,
        run_meta=exec_result.get("meta") if isinstance(exec_result.get("meta"), dict) else {},
    ) or record
    outcome.records.append(terminal)
    outcome.tool_messages.append(_record_result_message(tool_call, response))
    requires_user_takeover = formatter._tool_requires_user_takeover(exec_result)
    done_process_meta = build_done_process_meta(
        record=terminal,
        attempt_meta=attempt_meta,
        reason=terminal.reason,
        requires_user_takeover=requires_user_takeover,
        arg_failure=arg_failure,
    )
    _emit_batch_event(
        outcome,
        build_tool_call_done_event(terminal, process_meta=done_process_meta),
        event_callback=event_callback,
    )

    if tool_name == "discover_tools" and success:
        from core.tool_adapter import build_tools_list

        discovered_tools = build_tools_list()
        existing_names = {tool.get("function", {}).get("name") for tool in tools}
        for discovered_tool in discovered_tools:
            if discovered_tool.get("function", {}).get("name") not in existing_names:
                tools.append(discovered_tool)
        formatter._debug_write("discover_tools_expanded", {"total_tools": len(tools)})

    retry_note = formatter._build_failed_tool_retry_note(tool_name, tool_args, exec_result)
    if retry_note and not arg_failure:
        outcome.guidance_notes.append(retry_note)
    if arg_failure:
        outcome.guidance_notes.append(
            formatter._build_tool_arg_failure_system_note(tool_name, tool_args, missing_fields)
        )

    _append_recent_attempt(
        state,
        tool_name=tool_name,
        success=success,
        summary=action_summary or formatter._summarize_tool_response_text(response),
        arg_failure=arg_failure,
    )
    _update_state_after_record(
        state,
        tools=tools,
        bundle=bundle,
        record=terminal,
        tool_args=tool_args,
        arg_failure=arg_failure,
    )

    if requires_user_takeover:
        outcome.requires_user_takeover = True
        remaining_calls = [item[0] for item in prepared_calls[index + 1 :]]
        blocked_records = close_tool_call_batch_as_synthetic_failure(
            ledger,
            remaining_calls,
            bundle,
            reason="blocked_by_user_takeover",
            detail=f"前序动作 {tool_name} 已经卡在需要用户接手的步骤上。",
        )
        outcome.records.extend(blocked_records)
        outcome.tool_messages.extend(
            [
                _record_result_message(record_tool_call, blocked_record.response)
                for record_tool_call, blocked_record in zip(remaining_calls, blocked_records)
            ]
        )
        for blocked_batch_index, (_record_tool_call, blocked_record) in enumerate(
            zip(remaining_calls, blocked_records),
            start=index + 2,
        ):
            blocked_attempt_meta = build_attempt_process_meta(
                recent_attempts=state.recent_attempts,
                tool_name=blocked_record.tool_name,
                round_index=round_index,
                batch_index=blocked_batch_index,
                batch_size=len(prepared_calls),
            )
            _emit_batch_event(
                outcome,
                build_tool_call_done_event(
                    blocked_record,
                    process_meta=build_done_process_meta(
                        record=blocked_record,
                        attempt_meta=blocked_attempt_meta,
                        reason="blocked_by_user_takeover",
                        requires_user_takeover=True,
                    ),
                ),
                event_callback=event_callback,
            )
        return True
    return False


def execute_tool_call_batch(
    tool_calls: list[dict] | None,
    *,
    bundle: dict,
    tools: list[dict],
    tool_executor,
    skill_context: dict,
    ledger: ToolCallTurnLedger,
    state: ToolCallBatchState,
    mode: str,
    round_index: int | None = None,
    event_callback=None,
) -> ToolCallBatchOutcome:
    from decision import reply_formatter as formatter

    outcome = ToolCallBatchOutcome(state=state)
    prepared_calls: list[tuple[dict, str, dict, str, ToolCallRecord]] = []

    for raw_tool_call in tool_calls or []:
        sanitized, tool_name, tool_args, preview = formatter._prepare_tool_call_runtime(raw_tool_call, bundle)
        record = ledger.register(
            sanitized,
            tool_name=tool_name,
            tool_args=tool_args,
            preview=preview,
        )
        prepared_calls.append((sanitized, tool_name, tool_args, preview, record))
        outcome.tool_calls.append(sanitized)

    shadow_recent_attempts = list(state.recent_attempts)
    call_plans = [
        _plan_prepared_call(
            formatter,
            state,
            shadow_recent_attempts,
            tool_name=tool_name,
            tool_args=tool_args,
        )
        for (_tool_call, tool_name, tool_args, _preview, _record) in prepared_calls
    ]

    index = 0
    while index < len(prepared_calls):
        tool_call, tool_name, tool_args, preview, record = prepared_calls[index]
        plan = call_plans[index]

        if plan.get("repeated_invalid_args"):
            _handle_repeated_invalid_args(
                formatter=formatter,
                outcome=outcome,
                ledger=ledger,
                state=state,
                tools=tools,
                bundle=bundle,
                tool_call=tool_call,
                tool_name=tool_name,
                tool_args=tool_args,
                record=record,
                plan=plan,
                mode=mode,
                round_index=round_index,
                batch_index=index + 1,
                batch_size=len(prepared_calls),
                event_callback=event_callback,
            )
            index += 1
            continue

        parallel_group: list[ParallelCallSpec] = []
        scan = index
        while scan < len(prepared_calls):
            next_tool_call, next_tool_name, next_tool_args, next_preview, next_record = prepared_calls[scan]
            next_plan = call_plans[scan]
            if next_plan.get("repeated_invalid_args") or not is_parallel_safe_tool(next_tool_name):
                break
            parallel_group.append(
                ParallelCallSpec(
                    index=scan,
                    tool_call=next_tool_call,
                    tool_name=next_tool_name,
                    tool_args=next_tool_args,
                    preview=next_preview,
                    record=next_record,
                )
            )
            scan += 1

        if len(parallel_group) > 1:
            formatter._debug_write(
                "tool_call_parallel_group",
                {
                    "mode": mode,
                    "round": round_index or 0,
                    "batch_start": index + 1,
                    "batch_size": len(prepared_calls),
                    "parallel_size": len(parallel_group),
                    "tools": [spec.tool_name for spec in parallel_group],
                },
            )
            parallel_tools = [spec.tool_name for spec in parallel_group]
            attempt_meta_by_call_id: dict[str, dict] = {}
            for parallel_pos, spec in enumerate(parallel_group, start=1):
                attempt_meta = build_attempt_process_meta(
                    recent_attempts=state.recent_attempts,
                    tool_name=spec.tool_name,
                    round_index=round_index,
                    batch_index=spec.index + 1,
                    batch_size=len(prepared_calls),
                    parallel_index=parallel_pos,
                    parallel_size=len(parallel_group),
                    parallel_tools=parallel_tools,
                )
                attempt_meta_by_call_id[spec.record.call_id] = attempt_meta
                ledger.mark_executing(spec.record.call_id)
                _emit_batch_event(
                    outcome,
                    build_tool_call_executing_event(spec.record, process_meta=attempt_meta),
                    event_callback=event_callback,
                )
                formatter._debug_write(
                    "tool_call_invoke",
                    {
                        "name": spec.tool_name,
                        "args": spec.tool_args,
                        "mode": mode,
                        "round": round_index or 0,
                        "batch_index": spec.index + 1,
                        "batch_size": len(prepared_calls),
                        "parallel": True,
                    },
                )
            try:
                parallel_result = execute_parallel_tool_calls(
                    parallel_group,
                    tool_executor=tool_executor,
                    skill_context=skill_context,
                )
                results_by_call_id = parallel_result.results_by_call_id
            except ParallelToolExecutionError as exc:
                results_by_call_id = dict(exc.results_by_call_id)
                for spec in parallel_group:
                    exec_result = results_by_call_id.get(spec.record.call_id)
                    if not isinstance(exec_result, dict):
                        continue
                    if _apply_exec_result(
                        formatter=formatter,
                        outcome=outcome,
                        ledger=ledger,
                        state=state,
                        tools=tools,
                        bundle=bundle,
                        prepared_calls=prepared_calls,
                        index=spec.index,
                        tool_call=spec.tool_call,
                        tool_name=spec.tool_name,
                        tool_args=spec.tool_args,
                        record=spec.record,
                        plan=call_plans[spec.index],
                        exec_result=exec_result,
                        round_index=round_index,
                        attempt_meta=attempt_meta_by_call_id.get(spec.record.call_id),
                        event_callback=event_callback,
                    ):
                        return outcome
                raise exc.original_exception

            for spec in parallel_group:
                exec_result = results_by_call_id.get(spec.record.call_id)
                if not isinstance(exec_result, dict):
                    continue
                if _apply_exec_result(
                    formatter=formatter,
                    outcome=outcome,
                    ledger=ledger,
                    state=state,
                    tools=tools,
                    bundle=bundle,
                    prepared_calls=prepared_calls,
                    index=spec.index,
                    tool_call=spec.tool_call,
                    tool_name=spec.tool_name,
                    tool_args=spec.tool_args,
                    record=spec.record,
                    plan=call_plans[spec.index],
                    exec_result=exec_result,
                    round_index=round_index,
                    attempt_meta=attempt_meta_by_call_id.get(spec.record.call_id),
                    event_callback=event_callback,
                ):
                    return outcome
            index = scan
            continue

        attempt_meta = build_attempt_process_meta(
            recent_attempts=state.recent_attempts,
            tool_name=tool_name,
            round_index=round_index,
            batch_index=index + 1,
            batch_size=len(prepared_calls),
        )
        ledger.mark_executing(record.call_id)
        _emit_batch_event(
            outcome,
            build_tool_call_executing_event(record, process_meta=attempt_meta),
            event_callback=event_callback,
        )
        formatter._debug_write(
            "tool_call_invoke",
            {
                "name": tool_name,
                "args": tool_args,
                "mode": mode,
                "round": round_index or 0,
                "batch_index": index + 1,
                "batch_size": len(prepared_calls),
            },
        )

        exec_result = tool_executor(tool_name, tool_args, skill_context)
        if _apply_exec_result(
            formatter=formatter,
            outcome=outcome,
            ledger=ledger,
            state=state,
            tools=tools,
            bundle=bundle,
            prepared_calls=prepared_calls,
            index=index,
            tool_call=tool_call,
            tool_name=tool_name,
            tool_args=tool_args,
            record=record,
            plan=plan,
            exec_result=exec_result,
            round_index=round_index,
            attempt_meta=attempt_meta,
            event_callback=event_callback,
        ):
            return outcome
        index += 1

    return outcome
