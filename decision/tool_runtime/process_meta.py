from __future__ import annotations


_RUNTIME_FAILURE_REASONS = {
    "stream_signal_dropped",
    "tool_executor_exception",
    "tool_call_runtime_exception",
    "user_interrupted",
}


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _clean_summary(value: object, *, limit: int = 160) -> str:
    text = _clean_text(value).replace("\r", "\n")
    if not text:
        return ""
    lines = [line.strip(" -") for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    summary = " / ".join(lines[:2]).strip()
    if len(summary) > limit:
        return summary[: limit - 3].rstrip() + "..."
    return summary


def build_attempt_process_meta(
    *,
    recent_attempts: list[dict] | None,
    tool_name: str,
    round_index: int | None,
    batch_index: int,
    batch_size: int,
    parallel_index: int = 0,
    parallel_size: int = 0,
    parallel_group_id: str = "",
    parallel_tools: list[str] | None = None,
) -> dict:
    attempts = [item for item in (recent_attempts or []) if isinstance(item, dict)]
    previous = attempts[-1] if attempts else {}
    previous_tool = _clean_text(previous.get("tool"))
    previous_summary = _clean_summary(previous.get("summary"))
    previous_success = previous.get("success")

    attempt_kind = "initial"
    if previous_tool:
        if previous_success is False and previous_tool != tool_name:
            attempt_kind = "fallback"
        elif previous_success is False:
            attempt_kind = "retry"
        elif previous_tool == tool_name:
            attempt_kind = "followup"
        else:
            attempt_kind = "next_step"

    return {
        "attempt_kind": attempt_kind,
        "attempt_index": len(attempts) + 1,
        "round_index": int(round_index or 0) + 1,
        "batch_index": int(batch_index or 0),
        "batch_size": int(batch_size or 0),
        "parallel_index": int(parallel_index or 0),
        "parallel_size": int(parallel_size or 0),
        "parallel_group_id": _clean_text(parallel_group_id),
        "parallel_tools": [str(name or "").strip() for name in (parallel_tools or []) if str(name or "").strip()],
        "previous_tool": previous_tool,
        "previous_success": previous_success,
        "previous_summary": previous_summary,
    }


def build_done_process_meta(
    *,
    record,
    attempt_meta: dict | None = None,
    reason: str = "",
    requires_user_takeover: bool = False,
    arg_failure: dict | None = None,
) -> dict:
    meta = dict(attempt_meta or {})
    resolved_reason = _clean_text(reason or getattr(record, "reason", ""))
    success = getattr(record, "success", None)
    synthetic = bool(getattr(record, "synthetic", False))

    if success:
        outcome_kind = "success"
        next_hint_kind = "continue"
    elif requires_user_takeover or resolved_reason == "blocked_by_user_takeover":
        outcome_kind = "blocked"
        next_hint_kind = "wait_for_user"
    elif arg_failure or resolved_reason == "repeated_invalid_args":
        outcome_kind = "arg_failure"
        next_hint_kind = "repair_args"
    elif synthetic or resolved_reason in _RUNTIME_FAILURE_REASONS:
        outcome_kind = "runtime_failure"
        next_hint_kind = "retry_or_close"
    else:
        outcome_kind = "failed"
        next_hint_kind = "try_alternate_path"

    meta.update(
        {
            "outcome_kind": outcome_kind,
            "next_hint_kind": next_hint_kind,
            "reason": resolved_reason,
            "success": success,
            "synthetic": synthetic,
            "action_summary": _clean_summary(getattr(record, "action_summary", "")),
            "response_summary": _clean_summary(getattr(record, "response", "")),
        }
    )
    return meta
