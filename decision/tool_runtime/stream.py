from __future__ import annotations

from decision.tool_runtime.batch import (
    append_tool_batch_to_messages,
    close_tool_call_batch_as_synthetic_failure,
    create_tool_call_batch_state,
    execute_tool_call_batch,
)
from decision.tool_runtime.events import (
    build_tool_call_done_event,
    build_tool_turn_done_event,
    synthesize_tool_failure_response,
)
from decision.tool_runtime.ledger import ToolCallRecord, ToolCallTurnLedger
from decision.tool_runtime.process_meta import build_done_process_meta
from decision.tool_runtime.turn_limits import (
    build_max_turns_closeout_reply,
    build_turn_limit_meta,
    resolve_max_turns,
)


def _result_to_terminal_record(result: dict) -> ToolCallRecord | None:
    tool_name = str(result.get("tool_used") or "").strip()
    if not tool_name:
        return None
    success = result.get("success")
    if success is None:
        success = not bool(result.get("synthetic"))
    return ToolCallRecord(
        call_id=str(result.get("call_id") or f"{tool_name}_1").strip(),
        tool_name=tool_name,
        status="synthetic_failed" if result.get("synthetic") else "completed",
        success=success,
        response=str(result.get("tool_response") or "").strip(),
        action_summary=str(result.get("action_summary") or "").strip(),
        run_meta=result.get("run_meta") if isinstance(result.get("run_meta"), dict) else {},
        synthetic=bool(result.get("synthetic")),
        reason=str(result.get("reason") or "").strip(),
    )


def _result_to_terminal_records(result: dict) -> list[ToolCallRecord]:
    records: list[ToolCallRecord] = []
    for item in result.get("tool_results") or []:
        if not isinstance(item, dict):
            continue
        tool_name = str(item.get("name") or "").strip()
        if not tool_name:
            continue
        records.append(
            ToolCallRecord(
                call_id=str(item.get("call_id") or f"{tool_name}_{len(records) + 1}").strip(),
                tool_name=tool_name,
                status="synthetic_failed" if item.get("synthetic") else "completed",
                success=item.get("success"),
                synthetic=bool(item.get("synthetic")),
                reason=str(item.get("reason") or "").strip(),
            )
        )
    if records:
        return records
    terminal_record = _result_to_terminal_record(result)
    return [terminal_record] if terminal_record else []


def _maybe_build_closeout_reply(formatter, record: ToolCallRecord | None, visible_chunks: list) -> str:
    if not record:
        return ""
    if not formatter._has_only_preamble_text(
        visible_chunks,
        current_tool_success=bool(record.success) if record.success is not None else False,
    ):
        return ""
    return formatter._build_tool_closeout_reply(
        success=bool(record.success),
        action_summary=record.action_summary,
        tool_response=record.response,
        run_meta=record.run_meta,
    )


def run_stream_tool_call_turn(bundle: dict, tools: list[dict], tool_executor):
    from brain import LLM_CONFIG
    from decision import reply_formatter as formatter

    max_turns = resolve_max_turns(bundle)
    turn_limit_reached = False
    turn_reason = ""

    if not formatter._llm_call_stream:
        formatter._debug_write(
            "tool_call_stream_unavailable",
            {"reason": "missing_llm_call_stream"},
        )
        yield "当前前端聊天只保留流式工具链，但当前模型没有可用的流式调用能力。请检查流式 LLM 配置后再试一次。"
        yield build_tool_turn_done_event(
            None,
            {},
            records=[],
            turn_meta=build_turn_limit_meta(
                turns_used=0,
                max_turns=max_turns,
                turn_limit_reached=False,
                turn_reason="",
            ),
        )
        return

    cfg = LLM_CONFIG
    usage = {}
    ledger = ToolCallTurnLedger()
    latest_observed_tool_calls = None
    latest_visible_chunks: list = []
    buffered_batch_events: list[dict] = []
    failure_reason = "tool_call_runtime_exception"
    current_record = None
    batch_state = create_tool_call_batch_state(tools)
    turns_used = 1

    try:
        def _turn_done(record):
            return build_tool_turn_done_event(
                record,
                usage,
                records=ledger.terminal_records(),
                turn_meta=build_turn_limit_meta(
                    turns_used=turns_used,
                    max_turns=max_turns,
                    turn_limit_reached=turn_limit_reached,
                    turn_reason=turn_reason,
                ),
            )

        system_prompt = (
            formatter._build_cod_system_prompt(bundle)
            if bundle.get("cod_mode")
            else formatter._build_tool_call_system_prompt(bundle)
        )
        user_prompt = formatter._build_tool_call_user_prompt(bundle)
        dialogue_context = formatter.render_dialogue_context(bundle.get("dialogue_context", ""))

        messages = [
            {"role": "system", "content": system_prompt},
        ]
        if dialogue_context:
            messages.append({"role": "system", "content": f"对话增量提示：\n{dialogue_context}"})
        l1_messages = formatter._build_l1_messages(bundle, limit=None)
        if l1_messages:
            messages.extend(l1_messages)
        messages.append({"role": "user", "content": user_prompt})

        formatter._debug_write(
            "tool_call_stream_messages",
            {
                "msg_count": len(messages),
                "messages_summary": [
                    {"role": message["role"], "content": (message.get("content") or "")[:120]}
                    for message in messages
                ],
                "l1_count": len(l1_messages),
                "user_prompt_preview": user_prompt[:100],
            },
        )
        formatter._debug_write("tool_call_stream_request", {"tools_count": len(tools)})

        collected_tokens = []
        tool_calls_signal = None
        initial_reasoning_chunks = []

        for chunk in formatter._llm_call_stream(
            cfg,
            messages,
            tools=tools,
            temperature=0.7,
            max_tokens=2000,
            timeout=30,
        ):
            if isinstance(chunk, dict):
                if chunk.get("_tool_calls"):
                    tool_calls_signal = chunk["_tool_calls"]
                    if (
                        latest_observed_tool_calls is None
                        and isinstance(tool_calls_signal, list)
                        and tool_calls_signal
                    ):
                        latest_observed_tool_calls = [
                            dict(item) for item in tool_calls_signal if isinstance(item, dict)
                        ]
                elif chunk.get("_usage"):
                    usage = chunk["_usage"]
                elif chunk.get("_thinking"):
                    yield chunk
                elif "_thinking_content" in chunk:
                    thinking_text = str(chunk.get("_thinking_content") or "")
                    if thinking_text:
                        initial_reasoning_chunks.append(thinking_text)
                    yield chunk
            else:
                collected_tokens.append(chunk)
                latest_visible_chunks = list(collected_tokens)
                yield chunk

        tool_calls_signal, _joined, visible_joined = formatter._resolve_stream_tool_calls_signal(
            tool_calls_signal,
            collected_tokens,
            bundle,
            mode="stream_initial",
        )
        formatter._record_tool_call_usage_stats(cfg, usage)

        if not tool_calls_signal:
            if latest_observed_tool_calls:
                closed_records = close_tool_call_batch_as_synthetic_failure(
                    ledger,
                    latest_observed_tool_calls,
                    bundle,
                    reason="stream_signal_dropped",
                    detail=visible_joined[:200],
                )
                for closed_record in closed_records:
                    yield build_tool_call_done_event(
                        closed_record,
                        process_meta=build_done_process_meta(
                            record=closed_record,
                            reason="stream_signal_dropped",
                        ),
                    )
                current_record = closed_records[-1] if closed_records else None
                fallback = _maybe_build_closeout_reply(formatter, current_record, collected_tokens)
                if fallback:
                    yield fallback
                yield _turn_done(current_record)
                return
            yield _turn_done(None)
            return

        skill_context = formatter._build_tool_exec_context(bundle)
        failure_reason = "tool_executor_exception"
        buffered_batch_events = []
        batch_outcome = execute_tool_call_batch(
            tool_calls_signal,
            bundle=bundle,
            tools=tools,
            tool_executor=tool_executor,
            skill_context=skill_context,
            ledger=ledger,
            state=batch_state,
            mode="stream_initial",
            round_index=0,
            event_callback=buffered_batch_events.append,
        )
        failure_reason = "tool_call_runtime_exception"
        for event in batch_outcome.events:
            yield event
        buffered_batch_events = []
        append_tool_batch_to_messages(
            messages,
            batch_outcome,
            reasoning_details=formatter._reasoning_details_from_chunks(initial_reasoning_chunks),
        )

        recent_attempts = list(batch_state.recent_attempts)
        write_file_arg_retry_budget = 1
        current_record = batch_outcome.records[-1] if batch_outcome.records else ledger.latest_terminal()
        current_run_meta = batch_state.run_meta
        current_tool_success = batch_state.tool_success
        current_action_summary = batch_state.action_summary
        current_tool_response = batch_state.tool_response
        current_arg_failure = batch_state.arg_failure
        current_tool_args = dict(batch_state.tool_args)
        followup_tools = list(batch_state.followup_tools or tools)
        requires_user_takeover = batch_outcome.requires_user_takeover

        if requires_user_takeover:
            final_messages = list(messages)
            formatter._append_runtime_guidance(
                final_messages,
                "The task is blocked by login, verification, captcha, or another user-only step. Do not call more tools. Explain clearly that the user needs to complete that step first, then you can continue.",
            )
            usage_blocked = {}
            emitted = False
            latest_visible_chunks = []
            for chunk in formatter._llm_call_stream(
                cfg,
                final_messages,
                temperature=0.7,
                max_tokens=800,
                timeout=25,
            ):
                if isinstance(chunk, dict):
                    if chunk.get("_usage"):
                        usage_blocked = chunk["_usage"]
                else:
                    emitted = True
                    latest_visible_chunks.append(chunk)
                    yield chunk
            formatter._record_tool_call_usage_stats(cfg, usage_blocked)
            formatter._merge_tool_call_usage_totals(usage, usage_blocked)
            if not emitted:
                fallback = formatter._fallback_tool_reply(current_tool_response)
                if fallback:
                    latest_visible_chunks = [fallback]
                    yield fallback
            yield _turn_done(ledger.latest_terminal() or current_record)
            return

        round_index = 1
        while True:
            if round_index >= max_turns:
                turn_limit_reached = True
                turn_reason = "max_turns_reached"
                formatter._debug_write(
                    "tool_call_max_turns_reached",
                    {"max_turns": max_turns, "turns_used": turns_used},
                )
                closeout = build_max_turns_closeout_reply(
                    formatter,
                    max_turns=max_turns,
                    turns_used=turns_used,
                    success=current_tool_success,
                    action_summary=current_action_summary,
                    tool_response=current_tool_response,
                    run_meta=current_run_meta,
                )
                latest_visible_chunks = [closeout]
                yield closeout
                yield _turn_done(ledger.latest_terminal() or current_record)
                return

            usage_n = {}
            collected_n = []
            tool_calls_n = None
            observed_round_tool_calls = None
            round_reasoning_chunks = []
            turns_used += 1

            for chunk in formatter._llm_call_stream(
                cfg,
                messages,
                tools=followup_tools,
                temperature=0.7,
                max_tokens=2000,
                timeout=30,
            ):
                if isinstance(chunk, dict):
                    if chunk.get("_tool_calls"):
                        tool_calls_n = chunk["_tool_calls"]
                        if (
                            observed_round_tool_calls is None
                            and isinstance(tool_calls_n, list)
                            and tool_calls_n
                        ):
                            observed_round_tool_calls = [
                                dict(item) for item in tool_calls_n if isinstance(item, dict)
                            ]
                            latest_observed_tool_calls = list(observed_round_tool_calls)
                    elif chunk.get("_usage"):
                        usage_n = chunk["_usage"]
                    elif chunk.get("_thinking"):
                        yield chunk
                    elif "_thinking_content" in chunk:
                        thinking_text = str(chunk.get("_thinking_content") or "")
                        if thinking_text:
                            round_reasoning_chunks.append(thinking_text)
                        yield chunk
                else:
                    collected_n.append(chunk)

            latest_visible_chunks = list(collected_n)
            formatter._record_tool_call_usage_stats(cfg, usage_n)
            formatter._merge_tool_call_usage_totals(usage, usage_n)

            tool_calls_n, joined_n, visible_n = formatter._resolve_stream_tool_calls_signal(
                tool_calls_n,
                collected_n,
                bundle,
                mode=f"stream_round_{round_index}",
            )
            if not tool_calls_n:
                if observed_round_tool_calls:
                    closed_records = close_tool_call_batch_as_synthetic_failure(
                        ledger,
                        observed_round_tool_calls,
                        bundle,
                        reason="stream_signal_dropped",
                        detail=visible_n[:200],
                    )
                    for closed_record in closed_records:
                        yield build_tool_call_done_event(
                            closed_record,
                            process_meta=build_done_process_meta(
                                record=closed_record,
                                reason="stream_signal_dropped",
                            ),
                        )
                    current_record = closed_records[-1] if closed_records else ledger.latest_terminal()
                    fallback = _maybe_build_closeout_reply(formatter, current_record, collected_n)
                    if fallback:
                        yield fallback
                    yield _turn_done(current_record)
                    return

                if (
                    write_file_arg_retry_budget > 0
                    and formatter._is_write_file_content_arg_failure(current_arg_failure)
                    and visible_n
                    and formatter._looks_like_tool_preamble(visible_n)
                ):
                    messages.append(
                        formatter._build_assistant_history_message(
                            joined_n,
                            reasoning_details=formatter._reasoning_details_from_chunks(round_reasoning_chunks),
                        )
                    )
                    formatter._append_runtime_guidance(
                        messages,
                        formatter._build_strict_write_file_retry_note(current_tool_args, current_arg_failure),
                    )
                    write_file_arg_retry_budget -= 1
                    round_index += 1
                    continue

                final_reply = formatter._finalize_tool_reply(
                    joined_n,
                    success=current_tool_success,
                    action_summary=current_action_summary,
                    tool_response=current_tool_response,
                    run_meta=current_run_meta,
                )
                if final_reply:
                    latest_visible_chunks = [final_reply]
                    yield final_reply
                else:
                    fallback = formatter._build_tool_closeout_reply(
                        success=current_tool_success,
                        action_summary=current_action_summary,
                        tool_response=current_tool_response,
                        run_meta=current_run_meta,
                    )
                    if fallback:
                        latest_visible_chunks = [fallback]
                        yield fallback
                yield _turn_done(ledger.latest_terminal() or current_record)
                return

            failure_reason = "tool_executor_exception"
            buffered_batch_events = []
            batch_outcome = execute_tool_call_batch(
                tool_calls_n,
                bundle=bundle,
                tools=tools,
                tool_executor=tool_executor,
                skill_context=skill_context,
                ledger=ledger,
                state=batch_state,
                mode="stream",
                round_index=round_index,
                event_callback=buffered_batch_events.append,
            )
            failure_reason = "tool_call_runtime_exception"
            for event in batch_outcome.events:
                yield event
            buffered_batch_events = []
            append_tool_batch_to_messages(
                messages,
                batch_outcome,
                reasoning_details=formatter._reasoning_details_from_chunks(round_reasoning_chunks),
            )
            current_record = batch_outcome.records[-1] if batch_outcome.records else ledger.latest_terminal()
            current_run_meta = batch_state.run_meta
            current_tool_success = batch_state.tool_success
            current_action_summary = batch_state.action_summary
            current_tool_response = batch_state.tool_response
            current_arg_failure = batch_state.arg_failure
            current_tool_args = dict(batch_state.tool_args)
            followup_tools = list(batch_state.followup_tools or tools)
            recent_attempts = list(batch_state.recent_attempts)

            if batch_outcome.requires_user_takeover:
                final_messages = list(messages)
                formatter._append_runtime_guidance(
                    final_messages,
                    "The task is blocked by login, verification, captcha, or another user-only step. Do not call more tools. Explain clearly that the user needs to complete that step first, then you can continue.",
                )
                usage_blocked = {}
                emitted = False
                latest_visible_chunks = []
                for chunk in formatter._llm_call_stream(
                    cfg,
                    final_messages,
                    temperature=0.7,
                    max_tokens=800,
                    timeout=25,
                ):
                    if isinstance(chunk, dict):
                        if chunk.get("_usage"):
                            usage_blocked = chunk["_usage"]
                    else:
                        emitted = True
                        latest_visible_chunks.append(chunk)
                        yield chunk
                formatter._record_tool_call_usage_stats(cfg, usage_blocked)
                formatter._merge_tool_call_usage_totals(usage, usage_blocked)
                if not emitted:
                    fallback = formatter._fallback_tool_reply(current_tool_response)
                    if fallback:
                        latest_visible_chunks = [fallback]
                        yield fallback
                yield _turn_done(ledger.latest_terminal() or current_record)
                return

            if batch_outcome.strict_retry_note and write_file_arg_retry_budget > 0:
                formatter._append_runtime_guidance(messages, batch_outcome.strict_retry_note)
                write_file_arg_retry_budget -= 1
                round_index += 1
                continue

            if current_record and current_record.reason == "repeated_invalid_args":
                final_reply = formatter._build_tool_closeout_reply(
                    success=False,
                    action_summary=current_action_summary,
                    tool_response=current_tool_response,
                    run_meta=current_run_meta,
                )
                if final_reply:
                    latest_visible_chunks = [final_reply]
                    yield final_reply
                yield _turn_done(current_record)
                return

            round_index += 1

        formatter._debug_write("tool_call_multi_round", {"rounds": round_index})
        fallback = _maybe_build_closeout_reply(formatter, ledger.latest_terminal() or current_record, latest_visible_chunks)
        if fallback:
            latest_visible_chunks = [fallback]
            yield fallback
        yield _turn_done(ledger.latest_terminal() or current_record)
    except Exception as exc:
        detail = f"工具链中断：{type(exc).__name__}: {exc}"
        for event in buffered_batch_events:
            yield event
        buffered_batch_events = []
        flushed_records = []
        if not ledger.has_records() and latest_observed_tool_calls:
            flushed_records = close_tool_call_batch_as_synthetic_failure(
                ledger,
                latest_observed_tool_calls,
                bundle,
                reason=failure_reason,
                detail=detail,
            )
        elif ledger.has_unfinished():
            flushed_records = ledger.flush_unfinished(
                reason=failure_reason,
                response_factory=lambda record: synthesize_tool_failure_response(
                    record.tool_name,
                    failure_reason,
                    detail=detail,
                ),
                action_summary_factory=lambda record: formatter._summarize_tool_response_text(
                    synthesize_tool_failure_response(
                        record.tool_name,
                        failure_reason,
                        detail=detail,
                    )
                ),
                run_meta_factory=lambda _record: {},
            )

        for record in flushed_records:
            yield build_tool_call_done_event(
                record,
                process_meta=build_done_process_meta(
                    record=record,
                    reason=failure_reason,
                ),
            )

        terminal_record = flushed_records[-1] if flushed_records else ledger.latest_terminal()
        if terminal_record:
            fallback = _maybe_build_closeout_reply(formatter, terminal_record, latest_visible_chunks)
            if fallback:
                yield fallback
            yield build_tool_turn_done_event(
                terminal_record,
                usage,
                records=ledger.terminal_records(),
                turn_meta=build_turn_limit_meta(
                    turns_used=turns_used,
                    max_turns=max_turns,
                    turn_limit_reached=turn_limit_reached,
                    turn_reason=turn_reason,
                ),
            )
            return
        raise
