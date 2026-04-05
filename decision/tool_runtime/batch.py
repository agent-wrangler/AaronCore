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
from decision.tool_runtime.runtime_control import (
    build_interrupted_tool_result,
    tool_runtime_cancel_detail,
    tool_runtime_cancel_reason,
    tool_runtime_cancelled,
)

_DEFAULT_TOOL_RESULT_CONTEXT_MAX_CHARS = 2400
_DEFAULT_TOOL_BATCH_CONTEXT_BUDGET_CHARS = 7200
_MIN_TOOL_RESULT_CONTEXT_NOTE_CHARS = 120


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
    current_record: ToolCallRecord | None = None


def create_tool_call_batch_state(tools: list[dict] | None = None) -> ToolCallBatchState:
    return ToolCallBatchState(followup_tools=list(tools or []))


def _record_result_message(tool_call: dict, response: str) -> dict:
    return {
        "role": "tool",
        "tool_call_id": tool_call.get("id", "") if isinstance(tool_call, dict) else "",
        "content": str(response or ""),
    }


def _resolve_context_char_budget(
    bundle: dict | None,
    *,
    keys: tuple[str, ...],
    default: int,
) -> int:
    raw_candidates: list[object] = []
    if isinstance(bundle, dict):
        for key in keys:
            raw_candidates.append(bundle.get(key))
        runtime_options = bundle.get("runtime_options")
        if isinstance(runtime_options, dict):
            for key in keys:
                raw_candidates.append(runtime_options.get(key))
        tool_runtime = bundle.get("tool_runtime")
        if isinstance(tool_runtime, dict):
            for key in keys:
                raw_candidates.append(tool_runtime.get(key))

    for raw_value in raw_candidates:
        try:
            parsed = int(raw_value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return default


def _compact_tool_message_content(
    formatter,
    content: str,
    *,
    action_summary: str = "",
    max_chars: int,
) -> str:
    text = str(content or "").strip()
    if not text:
        return ""

    limit = max(1, int(max_chars))
    if len(text) <= limit:
        return text

    summary = str(action_summary or "").strip() or formatter._summarize_tool_response_text(text)
    prefix = "[tool result truncated for context]"
    if summary:
        prefix = f"{prefix}\nsummary: {summary}"

    if len(prefix) >= limit:
        return prefix[:limit].rstrip()

    remaining = limit - len(prefix) - 2
    if remaining <= 0:
        return prefix[:limit].rstrip()

    if remaining <= 32:
        excerpt = text[:remaining].rstrip()
        return f"{prefix}\n\n{excerpt}".strip()[:limit]

    tail_budget = min(max(remaining // 4, 16), 160)
    head_budget = max(remaining - tail_budget - 5, 24)
    if head_budget + tail_budget + 5 > remaining:
        tail_budget = max(16, remaining - head_budget - 5)
    head = text[:head_budget].rstrip()
    tail = text[-tail_budget:].lstrip() if tail_budget > 0 else ""
    clipped = f"{prefix}\n\n{head}"
    if tail:
        clipped = f"{clipped}\n...\n{tail}"
    return clipped[:limit].rstrip()


def _budget_tool_messages_for_context(
    formatter,
    tool_messages: list[dict],
    *,
    records: list[ToolCallRecord],
    bundle: dict | None = None,
) -> list[dict]:
    if not tool_messages:
        return []

    per_tool_limit = _resolve_context_char_budget(
        bundle,
        keys=("tool_result_max_chars", "toolResultMaxChars"),
        default=_DEFAULT_TOOL_RESULT_CONTEXT_MAX_CHARS,
    )
    batch_budget = _resolve_context_char_budget(
        bundle,
        keys=("tool_batch_result_budget_chars", "toolBatchResultBudgetChars"),
        default=_DEFAULT_TOOL_BATCH_CONTEXT_BUDGET_CHARS,
    )
    remaining_budget = max(1, int(batch_budget))
    record_by_call_id = {
        str(record.call_id or "").strip(): record
        for record in records or []
        if isinstance(record, ToolCallRecord)
    }

    budgeted: list[dict] = []
    for message in tool_messages:
        if not isinstance(message, dict) or message.get("role") != "tool":
            budgeted.append(dict(message) if isinstance(message, dict) else message)
            continue

        call_id = str(message.get("tool_call_id") or "").strip()
        record = record_by_call_id.get(call_id)
        effective_limit = (
            min(per_tool_limit, remaining_budget)
            if remaining_budget > 0
            else _MIN_TOOL_RESULT_CONTEXT_NOTE_CHARS
        )
        compacted = _compact_tool_message_content(
            formatter,
            str(message.get("content") or ""),
            action_summary=getattr(record, "action_summary", ""),
            max_chars=effective_limit,
        )
        budgeted.append(
            {
                **message,
                "content": compacted,
            }
        )
        remaining_budget = max(0, remaining_budget - len(compacted))

    return budgeted


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


def _sanitize_parallel_group_fragment(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "group"
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text)
    cleaned = cleaned.strip("_")
    return cleaned[:48] or "group"


def _build_parallel_group_id(
    *,
    round_index: int | None,
    batch_start_index: int,
    parallel_group: list[ParallelCallSpec],
) -> str:
    round_part = max(1, int(round_index or 0) + 1)
    batch_part = max(1, int(batch_start_index or 0) + 1)
    first_call_id = ""
    if parallel_group:
        first_call_id = str(getattr(parallel_group[0].record, "call_id", "") or "").strip()
    return f"parallel:{round_part}:{batch_part}:{_sanitize_parallel_group_fragment(first_call_id)}"


def _build_parallel_progress_meta(
    attempt_meta: dict | None,
    *,
    completed_count: int,
    success_count: int,
    failure_count: int,
) -> dict:
    meta = dict(attempt_meta or {})
    if int(meta.get("parallel_size") or 0) <= 1:
        return meta
    meta.update(
        {
            "parallel_completed_count": max(0, int(completed_count or 0)),
            "parallel_success_count": max(0, int(success_count or 0)),
            "parallel_failure_count": max(0, int(failure_count or 0)),
        }
    )
    return meta


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
    bundle: dict | None = None,
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
    messages.extend(
        _budget_tool_messages_for_context(
            formatter,
            outcome.tool_messages,
            records=outcome.records,
            bundle=bundle,
        )
    )
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
    outcome.current_record = terminal
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


def _close_remaining_prepared_calls(
    *,
    outcome: ToolCallBatchOutcome,
    ledger: ToolCallTurnLedger,
    state: ToolCallBatchState,
    tools: list[dict],
    bundle: dict,
    prepared_calls: list[tuple[dict, str, dict, str, ToolCallRecord]],
    start_index: int,
    reason: str,
    detail: str = "",
    round_index: int | None = None,
    event_callback=None,
) -> list[ToolCallRecord]:
    remaining = prepared_calls[start_index:]
    if not remaining:
        return []

    closed_records = close_tool_call_batch_as_synthetic_failure(
        ledger,
        [item[0] for item in remaining],
        bundle,
        reason=reason,
        detail=detail,
    )
    outcome.records.extend(closed_records)
    outcome.tool_messages.extend(
        [
            _record_result_message(tool_call, blocked_record.response)
            for (tool_call, _tool_name, _tool_args, _preview, _record), blocked_record in zip(remaining, closed_records)
        ]
    )
    for relative_index, (prepared, blocked_record) in enumerate(zip(remaining, closed_records), start=start_index + 1):
        _tool_call, _tool_name, _tool_args, _preview, _record = prepared
        blocked_attempt_meta = build_attempt_process_meta(
            recent_attempts=state.recent_attempts,
            tool_name=blocked_record.tool_name,
            round_index=round_index,
            batch_index=relative_index,
            batch_size=len(prepared_calls),
        )
        _emit_batch_event(
            outcome,
            build_tool_call_done_event(
                blocked_record,
                process_meta=build_done_process_meta(
                    record=blocked_record,
                    attempt_meta=blocked_attempt_meta,
                    reason=reason,
                ),
            ),
            event_callback=event_callback,
        )
    if not outcome.current_record and closed_records:
        first_tool_args = remaining[0][2]
        outcome.current_record = closed_records[0]
        _update_state_after_record(
            state,
            tools=tools,
            bundle=bundle,
            record=closed_records[0],
            tool_args=first_tool_args,
            arg_failure=None,
        )
    return closed_records


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
        synthetic=bool(exec_result.get("synthetic", False)),
        reason=str(exec_result.get("reason") or "").strip(),
    ) or record
    outcome.current_record = terminal
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


def _ordered_parallel_specs(
    parallel_group: list[ParallelCallSpec],
    completion_order: list[str] | None,
) -> list[ParallelCallSpec]:
    if not parallel_group:
        return []

    by_call_id = {
        str(getattr(spec.record, "call_id", "") or "").strip(): spec
        for spec in parallel_group
    }
    ordered: list[ParallelCallSpec] = []
    seen: set[str] = set()

    for call_id in completion_order or []:
        normalized = str(call_id or "").strip()
        spec = by_call_id.get(normalized)
        if spec is None or normalized in seen:
            continue
        ordered.append(spec)
        seen.add(normalized)

    for spec in parallel_group:
        normalized = str(getattr(spec.record, "call_id", "") or "").strip()
        if normalized in seen:
            continue
        ordered.append(spec)

    return ordered


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

    if tool_runtime_cancelled(skill_context, bundle):
        _close_remaining_prepared_calls(
            outcome=outcome,
            ledger=ledger,
            state=state,
            tools=tools,
            bundle=bundle,
            prepared_calls=prepared_calls,
            start_index=0,
            reason=tool_runtime_cancel_reason(skill_context, bundle) or "user_interrupted",
            detail=tool_runtime_cancel_detail(skill_context, bundle),
            round_index=round_index,
            event_callback=event_callback,
        )
        return outcome

    index = 0
    while index < len(prepared_calls):
        tool_call, tool_name, tool_args, preview, record = prepared_calls[index]
        plan = call_plans[index]

        if tool_runtime_cancelled(skill_context, bundle):
            _close_remaining_prepared_calls(
                outcome=outcome,
                ledger=ledger,
                state=state,
                tools=tools,
                bundle=bundle,
                prepared_calls=prepared_calls,
                start_index=index,
                reason=tool_runtime_cancel_reason(skill_context, bundle) or "user_interrupted",
                detail=tool_runtime_cancel_detail(skill_context, bundle),
                round_index=round_index,
                event_callback=event_callback,
            )
            return outcome

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
            if tool_runtime_cancelled(skill_context, bundle):
                _close_remaining_prepared_calls(
                    outcome=outcome,
                    ledger=ledger,
                    state=state,
                    tools=tools,
                    bundle=bundle,
                    prepared_calls=prepared_calls,
                    start_index=index,
                    reason=tool_runtime_cancel_reason(skill_context, bundle) or "user_interrupted",
                    detail=tool_runtime_cancel_detail(skill_context, bundle),
                    round_index=round_index,
                    event_callback=event_callback,
                )
                return outcome
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
            parallel_group_id = _build_parallel_group_id(
                round_index=round_index,
                batch_start_index=index,
                parallel_group=parallel_group,
            )
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
                    parallel_group_id=parallel_group_id,
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
                interrupted_record = None
            except ParallelToolExecutionError as exc:
                results_by_call_id = dict(exc.results_by_call_id)
                interrupted_record = None
                ordered_specs = _ordered_parallel_specs(parallel_group, exc.completion_order)
                completed_count = 0
                success_count = 0
                failure_count = 0
                for spec in ordered_specs:
                    exec_result = results_by_call_id.get(spec.record.call_id)
                    if not isinstance(exec_result, dict):
                        continue
                    completed_count += 1
                    if bool(exec_result.get("success", False)):
                        success_count += 1
                    else:
                        failure_count += 1
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
                        attempt_meta=_build_parallel_progress_meta(
                            attempt_meta_by_call_id.get(spec.record.call_id),
                            completed_count=completed_count,
                            success_count=success_count,
                            failure_count=failure_count,
                        ),
                        event_callback=event_callback,
                    ):
                        return outcome
                    terminal = ledger.get(spec.record.call_id)
                    if terminal and terminal.reason == "user_interrupted" and interrupted_record is None:
                        interrupted_record = terminal
                if interrupted_record:
                    outcome.current_record = interrupted_record
                    _close_remaining_prepared_calls(
                        outcome=outcome,
                        ledger=ledger,
                        state=state,
                        tools=tools,
                        bundle=bundle,
                        prepared_calls=prepared_calls,
                        start_index=scan,
                        reason="user_interrupted",
                        detail=tool_runtime_cancel_detail(skill_context, bundle),
                        round_index=round_index,
                        event_callback=event_callback,
                    )
                    return outcome
                raise exc.original_exception

            interrupted_record = None
            ordered_specs = _ordered_parallel_specs(parallel_group, parallel_result.completion_order)
            completed_count = 0
            success_count = 0
            failure_count = 0
            for spec in ordered_specs:
                exec_result = results_by_call_id.get(spec.record.call_id)
                if not isinstance(exec_result, dict):
                    continue
                completed_count += 1
                if bool(exec_result.get("success", False)):
                    success_count += 1
                else:
                    failure_count += 1
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
                    attempt_meta=_build_parallel_progress_meta(
                        attempt_meta_by_call_id.get(spec.record.call_id),
                        completed_count=completed_count,
                        success_count=success_count,
                        failure_count=failure_count,
                    ),
                    event_callback=event_callback,
                ):
                    return outcome
                terminal = ledger.get(spec.record.call_id)
                if terminal and terminal.reason == "user_interrupted" and interrupted_record is None:
                    interrupted_record = terminal
            if interrupted_record:
                outcome.current_record = interrupted_record
                _close_remaining_prepared_calls(
                    outcome=outcome,
                    ledger=ledger,
                    state=state,
                    tools=tools,
                    bundle=bundle,
                    prepared_calls=prepared_calls,
                    start_index=scan,
                    reason="user_interrupted",
                    detail=tool_runtime_cancel_detail(skill_context, bundle),
                    round_index=round_index,
                    event_callback=event_callback,
                )
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

        if tool_runtime_cancelled(skill_context, bundle):
            exec_result = build_interrupted_tool_result(
                tool_name,
                reason=tool_runtime_cancel_reason(skill_context, bundle) or "user_interrupted",
                detail=tool_runtime_cancel_detail(skill_context, bundle),
            )
        else:
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
        terminal = ledger.get(record.call_id)
        if terminal and terminal.reason == "user_interrupted":
            outcome.current_record = terminal
            _close_remaining_prepared_calls(
                outcome=outcome,
                ledger=ledger,
                state=state,
                tools=tools,
                bundle=bundle,
                prepared_calls=prepared_calls,
                start_index=index + 1,
                reason="user_interrupted",
                detail=tool_runtime_cancel_detail(skill_context, bundle),
                round_index=round_index,
                event_callback=event_callback,
            )
            return outcome
        index += 1

    return outcome
