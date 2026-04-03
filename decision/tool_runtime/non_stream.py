from __future__ import annotations

from decision.tool_runtime.batch import (
    append_tool_batch_to_messages,
    create_tool_call_batch_state,
    execute_tool_call_batch,
)
from decision.tool_runtime.events import synthesize_tool_failure_response
from decision.tool_runtime.ledger import ToolCallTurnLedger


def _build_non_stream_result(reply: str, terminal_record, usage: dict, ledger: ToolCallTurnLedger) -> dict:
    terminal_records = ledger.terminal_records()
    return {
        "reply": reply,
        "tool_used": terminal_record.tool_name if terminal_record else None,
        "usage": usage,
        "action_summary": terminal_record.action_summary if terminal_record else "",
        "run_meta": terminal_record.run_meta if terminal_record else {},
        "success": terminal_record.success if terminal_record else None,
        "tool_response": terminal_record.response if terminal_record else "",
        "call_id": terminal_record.call_id if terminal_record else "",
        "synthetic": bool(terminal_record.synthetic) if terminal_record else False,
        "reason": terminal_record.reason if terminal_record else "",
        "tools_used": [record.tool_name for record in terminal_records if record.tool_name],
        "action_count": len(terminal_records),
        "batch_mode": len(terminal_records) > 1,
        "tool_results": [
            {
                "call_id": record.call_id,
                "name": record.tool_name,
                "success": record.success,
                "synthetic": bool(record.synthetic),
                "reason": record.reason,
            }
            for record in terminal_records
        ],
    }


def run_non_stream_tool_call_turn(bundle: dict, tools: list[dict], tool_executor) -> dict:
    from brain import LLM_CONFIG
    from decision import reply_formatter as formatter

    if not formatter._llm_call:
        return {
            "reply": formatter.unified_chat_reply(bundle),
            "tool_used": None,
            "usage": {},
            "success": None,
            "tool_response": "",
            "call_id": "",
            "synthetic": False,
            "reason": "",
            "tools_used": [],
            "action_count": 0,
            "batch_mode": False,
            "tool_results": [],
        }

    cfg = LLM_CONFIG
    usage = {}
    ledger = ToolCallTurnLedger()
    batch_state = create_tool_call_batch_state(tools)

    try:
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
        messages.append({"role": "user", "content": user_prompt})

        formatter._debug_write("tool_call_request", {"tools_count": len(tools), "msg_len": len(user_prompt)})

        result = formatter._llm_call(cfg, messages, tools=tools, temperature=0.7, max_tokens=2000, timeout=30)
        usage = result.get("usage", {})
        formatter._record_tool_call_usage_stats(cfg, usage)

        tool_calls = formatter._resolve_tool_calls_from_result(result, bundle, mode="non_stream_initial")
        if not tool_calls:
            reply = result.get("content", "")
            formatter._debug_write("tool_call_direct_reply", {"reply_len": len(reply)})
            return {
                "reply": reply,
                "tool_used": None,
                "usage": usage,
                "success": None,
                "tool_response": "",
                "call_id": "",
                "synthetic": False,
                "reason": "",
                "tools_used": [],
                "action_count": 0,
                "batch_mode": False,
                "tool_results": [],
            }

        skill_context = formatter._build_tool_exec_context(bundle)
        batch_outcome = execute_tool_call_batch(
            tool_calls,
            bundle=bundle,
            tools=tools,
            tool_executor=tool_executor,
            skill_context=skill_context,
            ledger=ledger,
            state=batch_state,
            mode="non_stream_initial",
            round_index=0,
        )
        append_tool_batch_to_messages(
            messages,
            batch_outcome,
            reasoning_details=result.get("reasoning_details"),
        )
        if batch_outcome.strict_retry_note:
            formatter._append_runtime_guidance(messages, batch_outcome.strict_retry_note)

        current_record = batch_outcome.records[-1] if batch_outcome.records else ledger.latest_terminal()
        current_result = {"content": ""}

        if batch_outcome.requires_user_takeover:
            final_messages = list(messages)
            formatter._append_runtime_guidance(
                final_messages,
                "The task is blocked by login, verification, captcha, or another user-only step. Do not call more tools. Explain clearly that the user needs to complete that step first, then you can continue.",
            )
            current_result = formatter._llm_call(cfg, final_messages, temperature=0.7, max_tokens=2000, timeout=25)
            formatter._merge_tool_call_usage_totals(usage, current_result.get("usage", {}))
            formatter._record_tool_call_usage_stats(cfg, current_result.get("usage", {}))
            terminal_record = ledger.latest_terminal() or current_record
            reply = formatter._finalize_tool_reply(
                current_result.get("content", ""),
                success=bool(batch_state.tool_success) if batch_state.tool_success is not None else False,
                action_summary=batch_state.action_summary,
                tool_response=batch_state.tool_response,
                run_meta=batch_state.run_meta,
            )
            if not str(reply or "").strip():
                reply = formatter._build_tool_closeout_reply(
                    success=bool(batch_state.tool_success) if batch_state.tool_success is not None else False,
                    action_summary=batch_state.action_summary,
                    tool_response=batch_state.tool_response,
                    run_meta=batch_state.run_meta,
                )
            return _build_non_stream_result(reply, terminal_record, usage, ledger)

        current_result = formatter._llm_call(cfg, messages, temperature=0.7, max_tokens=2000, timeout=25)
        formatter._merge_tool_call_usage_totals(usage, current_result.get("usage", {}))
        formatter._record_tool_call_usage_stats(cfg, current_result.get("usage", {}))

        for round_idx in range(3):
            followup_tool_calls = formatter._resolve_tool_calls_from_result(
                current_result,
                bundle,
                mode=f"non_stream_followup_{round_idx + 1}",
            )
            if not followup_tool_calls:
                break

            batch_outcome = execute_tool_call_batch(
                followup_tool_calls,
                bundle=bundle,
                tools=tools,
                tool_executor=tool_executor,
                skill_context=skill_context,
                ledger=ledger,
                state=batch_state,
                mode="non_stream",
                round_index=round_idx + 1,
            )
            append_tool_batch_to_messages(
                messages,
                batch_outcome,
                reasoning_details=current_result.get("reasoning_details"),
            )
            if batch_outcome.strict_retry_note:
                formatter._append_runtime_guidance(messages, batch_outcome.strict_retry_note)

            current_record = batch_outcome.records[-1] if batch_outcome.records else ledger.latest_terminal()
            if batch_outcome.requires_user_takeover:
                final_messages = list(messages)
                formatter._append_runtime_guidance(
                    final_messages,
                    "The task is blocked by login, verification, captcha, or another user-only step. Do not call more tools. Explain clearly that the user needs to complete that step first, then you can continue.",
                )
                current_result = formatter._llm_call(cfg, final_messages, temperature=0.7, max_tokens=2000, timeout=25)
                formatter._merge_tool_call_usage_totals(usage, current_result.get("usage", {}))
                formatter._record_tool_call_usage_stats(cfg, current_result.get("usage", {}))
                break

            current_result = formatter._llm_call(cfg, messages, temperature=0.7, max_tokens=2000, timeout=25)
            formatter._merge_tool_call_usage_totals(usage, current_result.get("usage", {}))
            formatter._record_tool_call_usage_stats(cfg, current_result.get("usage", {}))

        terminal_record = ledger.latest_terminal() or current_record
        reply = formatter._finalize_tool_reply(
            current_result.get("content", ""),
            success=bool(batch_state.tool_success) if batch_state.tool_success is not None else False,
            action_summary=batch_state.action_summary,
            tool_response=batch_state.tool_response,
            run_meta=batch_state.run_meta,
        )
        if not str(reply or "").strip():
            reply = formatter._build_tool_closeout_reply(
                success=bool(batch_state.tool_success) if batch_state.tool_success is not None else False,
                action_summary=batch_state.action_summary,
                tool_response=batch_state.tool_response,
                run_meta=batch_state.run_meta,
            )
            formatter._debug_write(
                "tool_call_final_reply_fallback",
                {"tool": terminal_record.tool_name if terminal_record else "", "fallback_len": len(reply)},
            )
        formatter._debug_write(
            "tool_call_final_reply",
            {"tool": terminal_record.tool_name if terminal_record else "", "reply_len": len(reply)},
        )
        return _build_non_stream_result(reply, terminal_record, usage, ledger)
    except Exception as exc:
        detail = f"工具链中断：{type(exc).__name__}: {exc}"
        terminal_record = None
        if ledger.has_unfinished():
            flushed = ledger.flush_unfinished(
                reason="tool_call_runtime_exception",
                response_factory=lambda record: synthesize_tool_failure_response(
                    record.tool_name,
                    "tool_call_runtime_exception",
                    detail=detail,
                ),
                action_summary_factory=lambda record: formatter._summarize_tool_response_text(
                    synthesize_tool_failure_response(
                        record.tool_name,
                        "tool_call_runtime_exception",
                        detail=detail,
                    )
                ),
                run_meta_factory=lambda _record: {},
            )
            if flushed:
                terminal_record = flushed[-1]
        if not terminal_record:
            terminal_record = ledger.latest_terminal()
        if terminal_record:
            reply = formatter._build_tool_closeout_reply(
                success=bool(terminal_record.success),
                action_summary=terminal_record.action_summary,
                tool_response=terminal_record.response or detail,
                run_meta=terminal_record.run_meta,
            )
            formatter._debug_write(
                "tool_call_final_reply_fallback",
                {"tool": terminal_record.tool_name, "fallback_len": len(reply)},
            )
            return _build_non_stream_result(reply, terminal_record, usage, ledger)
        raise
