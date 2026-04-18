from __future__ import annotations


_RUNTIME_FAILURE_REASONS = {
    "stream_signal_dropped",
    "tool_executor_exception",
    "tool_call_runtime_exception",
    "user_interrupted",
}
_USER_TAKEOVER_REASONS = {
    "auth_required",
    "login_required",
    "verification_required",
    "captcha_required",
}
_USER_TAKEOVER_HINTS = {
    "user_login_required",
    "user_verification_required",
}
_ARG_FAILURE_OUTCOMES = {
    "invalid",
    "missing_target",
}
_FS_TARGET_KINDS = {
    "artifact",
    "directory",
    "file",
    "folder",
    "path",
}
_RUNTIME_STATUS_PROCESS_META = {
    "arg_failed": ("arg_failure", "repair_args"),
    "blocked": ("blocked", "retry_or_close"),
    "done": ("success", "continue"),
    "failed": ("failed", "try_alternate_path"),
    "interrupted": ("interrupted", "resume_or_close"),
    "runtime_failed": ("runtime_failure", "retry_or_close"),
    "verify_failed": ("verify_failed", "retry_or_close"),
    "verified": ("success", "continue"),
}


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _clean_lower_text(value: object) -> str:
    return _clean_text(value).lower()


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


def _coerce_dict(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _text_contains_any(text: object, tokens: tuple[str, ...]) -> bool:
    lowered = _clean_lower_text(text)
    if not lowered:
        return False
    return any(token in lowered for token in tokens)


def _infer_execution_lane(tool_name: str, working_state: dict | None) -> str:
    working_state = _coerce_dict(working_state)
    current_step_task = _coerce_dict(working_state.get("current_step_task"))
    explicit_lane = _clean_lower_text(
        current_step_task.get("execution_lane") or working_state.get("execution_lane")
    )
    if explicit_lane:
        return explicit_lane

    step_text = " ".join(
        part
        for part in [
            _clean_text(current_step_task.get("title")),
            _clean_text(current_step_task.get("detail")),
            _clean_text(working_state.get("current_step")),
            _clean_text(working_state.get("summary")),
            _clean_text(working_state.get("phase")),
        ]
        if part
    )
    verify_tokens = (
        "verify", "verification", "validate", "test", "pytest", "assert",
        "验", "验证", "核验", "测试", "回归", "检查结果",
    )
    inspect_tokens = (
        "inspect", "investigate", "analy", "analysis", "debug", "diagnos", "trace",
        "map", "gather", "context", "review", "read", "search", "look up",
        "看", "查", "排查", "分析", "定位", "搜集", "上下文", "读取",
    )
    implement_tokens = (
        "implement", "patch", "edit", "modify", "write", "refactor", "fix", "build", "code", "apply",
        "改", "修", "实现", "补丁", "编写", "重构",
    )
    if _text_contains_any(step_text, verify_tokens):
        return "verify"
    if _text_contains_any(step_text, inspect_tokens):
        return "inspect"
    if _text_contains_any(step_text, implement_tokens):
        return "implement"

    clean_tool_name = _clean_lower_text(tool_name)
    if clean_tool_name in {
        "discover_tools",
        "folder_explore",
        "list_files",
        "query_knowledge",
        "read_file",
        "recall_memory",
        "search_text",
        "sense_environment",
        "web_search",
    }:
        return "inspect"
    if clean_tool_name in {
        "apply_unified_diff",
        "edit_file",
        "save_export",
        "search_replace",
        "write_file",
    }:
        return "implement"
    if clean_tool_name == "run_command":
        verification_status = _clean_lower_text(working_state.get("verification_status"))
        runtime_status = _clean_lower_text(working_state.get("runtime_status"))
        if verification_status or runtime_status in {"verify_failed", "verified"}:
            return "verify"
        return "execute"
    if clean_tool_name in {"app_target", "open_target", "ui_interaction"}:
        return "interact"
    return ""


def _verification_payload(meta: dict | None, runtime_state: dict | None = None) -> dict:
    meta = _coerce_dict(meta)
    runtime_state = _coerce_dict(runtime_state)
    verification = _coerce_dict(meta.get("verification"))
    payload = {}

    verified = verification.get("verified", runtime_state.get("verified"))
    if verified in {True, False}:
        payload["verified"] = bool(verified)

    status = _clean_text(verification.get("status")).lower()
    if not status:
        if verified is True:
            status = "verified"
        elif verified is False:
            status = "failed"
    if status:
        payload["status"] = status

    detail = _clean_text(
        verification.get("detail")
        or verification.get("verification_detail")
        or runtime_state.get("blocker")
    )
    if detail:
        payload["detail"] = detail

    observed_state = _clean_text(verification.get("observed_state"))
    if observed_state:
        payload["observed_state"] = observed_state

    verification_mode = _clean_text(verification.get("verification_mode"))
    if verification_mode:
        payload["verification_mode"] = verification_mode

    return payload


def _resolve_process_outcome_from_runtime_state(
    runtime_state: dict | None,
    *,
    success: bool | None,
) -> tuple[str, str] | None:
    runtime_state = _coerce_dict(runtime_state)
    status = _clean_text(runtime_state.get("status")).lower()
    if not status:
        return None

    next_action = _clean_text(runtime_state.get("next_action")).lower()
    if status == "waiting_user":
        return ("success" if success is True else "blocked", next_action or "wait_for_user")

    mapped = _RUNTIME_STATUS_PROCESS_META.get(status)
    if not mapped:
        return None
    outcome_kind, default_next = mapped
    return outcome_kind, next_action or default_next


def build_tool_runtime_state(
    *,
    meta: dict | None,
    success: bool | None,
    reason: str = "",
    synthetic: bool = False,
    response: str = "",
) -> dict:
    meta = _coerce_dict(meta)
    existing = _coerce_dict(meta.get("runtime_state"))
    state = _coerce_dict(meta.get("state"))
    drift = _coerce_dict(meta.get("drift"))
    action = _coerce_dict(meta.get("action"))
    post_condition = _coerce_dict(meta.get("post_condition"))
    verification = _coerce_dict(meta.get("verification"))

    drift_reason = _clean_text(drift.get("reason") or post_condition.get("drift")).lower()
    repair_hint = _clean_text(drift.get("repair_hint") or post_condition.get("hint")).lower()
    action_outcome = _clean_text(action.get("outcome")).lower()
    verification_mode = _clean_text(
        verification.get("verification_mode") or action.get("verification_mode")
    ).lower()
    verification_detail = _clean_text(
        verification.get("verification_detail")
        or verification.get("detail")
        or action.get("verification_detail")
    )
    observed_state = _clean_text(
        verification.get("observed_state")
        or state.get("observed_state")
        or post_condition.get("observed")
    )
    verified = verification.get("verified", existing.get("verified"))
    if verified not in {True, False, None}:
        verified = None

    resolved_reason = _clean_text(reason).lower()
    user_takeover = (
        drift_reason in _USER_TAKEOVER_REASONS
        or repair_hint in _USER_TAKEOVER_HINTS
    )
    blocked_outcome = action_outcome == "blocked" or resolved_reason == "blocked_by_user_takeover"
    arg_failed = verification_mode == "argument_check" or action_outcome in _ARG_FAILURE_OUTCOMES

    if resolved_reason == "user_interrupted":
        status = "interrupted"
        next_action = "resume_or_close"
    elif user_takeover:
        status = "waiting_user"
        next_action = "wait_for_user"
    elif blocked_outcome:
        status = "blocked"
        next_action = "retry_or_close"
    elif success is True:
        if verified is True:
            status = "verified"
            next_action = "continue"
        elif verified is False:
            status = "verify_failed"
            next_action = "retry_or_close"
        else:
            status = "done"
            next_action = "continue"
    elif arg_failed or resolved_reason == "repeated_invalid_args":
        status = "arg_failed"
        next_action = "repair_args"
    elif synthetic or resolved_reason in _RUNTIME_FAILURE_REASONS:
        status = "runtime_failed"
        next_action = "retry_or_close"
    elif verified is False:
        status = "verify_failed"
        next_action = "retry_or_close"
    else:
        status = "failed"
        next_action = "try_alternate_path"

    blocker = _clean_summary(
        verification_detail
        or observed_state
        or drift_reason
        or resolved_reason
        or response,
        limit=240,
    )

    target_kind = _clean_text(action.get("target_kind") or existing.get("target_kind")).lower()
    target = _clean_text(action.get("target") or existing.get("target"))
    fs_target = _coerce_dict(existing.get("fs_target"))
    if not fs_target and target and target_kind in _FS_TARGET_KINDS:
        fs_target = {
            "path": target,
            "kind": target_kind,
        }

    runtime_state = {
        "status": status,
        "next_action": next_action,
        "verified": verified,
        "reason": resolved_reason or drift_reason,
        "outcome": action_outcome,
        "target_kind": target_kind,
        "target": target,
    }
    if blocker and status in {
        "arg_failed",
        "blocked",
        "failed",
        "interrupted",
        "runtime_failed",
        "verify_failed",
        "waiting_user",
    }:
        runtime_state["blocker"] = blocker
    if fs_target:
        runtime_state["fs_target"] = fs_target
    return runtime_state


def extract_record_runtime_state(record) -> dict:
    if not record:
        return {}
    return build_tool_runtime_state(
        meta=getattr(record, "run_meta", {}),
        success=getattr(record, "success", None),
        reason=getattr(record, "reason", ""),
        synthetic=bool(getattr(record, "synthetic", False)),
        response=str(getattr(record, "response", "") or ""),
    )


def build_runtime_payload(record) -> dict:
    runtime_state = extract_record_runtime_state(record)
    if not runtime_state:
        return {}
    run_meta = _coerce_dict(getattr(record, "run_meta", {}))
    payload = {
        "runtime_state": runtime_state,
        "status": runtime_state.get("status"),
        "next_action": runtime_state.get("next_action"),
        "verified": runtime_state.get("verified"),
    }
    blocker = str(runtime_state.get("blocker") or "").strip()
    if blocker:
        payload["blocker"] = blocker
    fs_target = runtime_state.get("fs_target")
    if isinstance(fs_target, dict) and fs_target:
        payload["fs_target"] = dict(fs_target)
    verification = _verification_payload(run_meta, runtime_state)
    if verification:
        payload["verification"] = verification
    return payload


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
    working_state: dict | None = None,
) -> dict:
    attempts = [item for item in (recent_attempts or []) if isinstance(item, dict)]
    previous = attempts[-1] if attempts else {}
    previous_tool = _clean_text(previous.get("tool"))
    previous_summary = _clean_summary(previous.get("summary"))
    previous_success = previous.get("success")
    current_step_task = _coerce_dict(_coerce_dict(working_state).get("current_step_task"))
    execution_lane = _infer_execution_lane(tool_name, working_state)
    current_step_task_id = _clean_text(current_step_task.get("task_id"))
    current_step_task_title = _clean_text(current_step_task.get("title"))
    current_step_task_status = _clean_text(current_step_task.get("status"))

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

    meta = {
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
    if execution_lane:
        meta["execution_lane"] = execution_lane
    if current_step_task_id:
        meta["current_step_task_id"] = current_step_task_id
    if current_step_task_title:
        meta["current_step_task_title"] = current_step_task_title
    if current_step_task_status:
        meta["current_step_task_status"] = current_step_task_status
    return meta


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
    runtime_state = extract_record_runtime_state(record)

    runtime_outcome = _resolve_process_outcome_from_runtime_state(runtime_state, success=success)
    if requires_user_takeover or resolved_reason == "blocked_by_user_takeover":
        outcome_kind = "success" if success else "blocked"
        next_hint_kind = "wait_for_user"
    elif runtime_outcome:
        outcome_kind, next_hint_kind = runtime_outcome
    elif success:
        outcome_kind = "success"
        next_hint_kind = "continue"
    elif resolved_reason == "user_interrupted":
        outcome_kind = "interrupted"
        next_hint_kind = "resume_or_close"
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
    if runtime_state:
        meta["runtime_state"] = runtime_state
    return meta
