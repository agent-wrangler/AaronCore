"""Dispatch helpers for post-LLM tool execution."""

from decision.tool_runtime.runtime_control import (
    ToolRuntimeInterrupted,
    build_interrupted_tool_result,
    raise_if_cancelled,
)


_NEGATIVE_OUTCOME_TOKENS = (
    "blocked",
    "failed",
    "missing",
    "invalid",
    "unresolved",
    "pending",
)
_NEGATIVE_STATE_TOKENS = (
    "blocked",
    "failed",
    "missing",
    "invalid",
    "unresolved",
    "not_found",
    "pending",
    "required",
    "unavailable",
)


def _coerce_meta_section(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _looks_like_legacy_operation_result(result: dict) -> bool:
    if not isinstance(result, dict):
        return False
    return any(isinstance(result.get(key), dict) for key in ("state", "drift", "action"))


def _infer_legacy_operation_success(result: dict) -> bool:
    state = _coerce_meta_section(result.get("state"))
    drift = _coerce_meta_section(result.get("drift"))
    action = _coerce_meta_section(result.get("action"))
    outcome = str(action.get("outcome") or "").strip().lower()
    observed_state = str(state.get("observed_state") or "").strip().lower()
    drift_reason = str(drift.get("reason") or "").strip()

    if outcome and any(token in outcome for token in _NEGATIVE_OUTCOME_TOKENS):
        return False
    if drift_reason:
        return False
    if observed_state and any(token in observed_state for token in _NEGATIVE_STATE_TOKENS):
        return False
    return bool(
        str(result.get("reply") or result.get("response") or "").strip()
        or outcome
        or observed_state
        or str(action.get("target") or "").strip()
        or str(action.get("action_kind") or "").strip()
    )


def _normalize_legacy_operation_result(result: dict) -> dict:
    normalized = dict(result)
    if normalized.get("meta") or "success" in normalized or not _looks_like_legacy_operation_result(normalized):
        return normalized

    state = _coerce_meta_section(normalized.get("state"))
    drift = _coerce_meta_section(normalized.get("drift"))
    action = _coerce_meta_section(normalized.get("action"))
    meta = {}
    if state:
        meta["state"] = state
    if drift:
        meta["drift"] = drift
    if action:
        meta["action"] = action

    if "repair_attempted" in normalized:
        meta["repair_attempted"] = bool(normalized.get("repair_attempted"))
    if "repair_succeeded" in normalized:
        meta["repair_succeeded"] = bool(normalized.get("repair_succeeded"))

    expected_state = str(state.get("expected_state") or "").strip()
    observed_state = str(state.get("observed_state") or "").strip()
    verification_mode = str(action.get("verification_mode") or "").strip()
    verification_detail = str(action.get("verification_detail") or "").strip()
    verification = {}
    if observed_state:
        verification["observed_state"] = observed_state
    if verification_mode:
        verification["verification_mode"] = verification_mode
    if verification_detail:
        verification["verification_detail"] = verification_detail

    drift_reason = str(drift.get("reason") or "").strip()
    if drift_reason:
        verification["verified"] = False
    elif expected_state and observed_state:
        verification["verified"] = expected_state == observed_state
    elif observed_state or verification_mode or verification_detail:
        verification["verified"] = None
    if verification:
        meta["verification"] = verification

    normalized["meta"] = meta
    normalized["response"] = str(normalized.get("reply") or normalized.get("response") or "").strip()
    normalized["success"] = _infer_legacy_operation_success(normalized)
    return normalized


def execute_tool_call_legacy(
    name: str,
    arguments: dict,
    context: dict | None = None,
    *,
    execute_ask_user,
    memory_tools,
    execute_memory_tool,
    apply_protocol_context,
    execute_skill,
    remember_protocol_target,
    debug_write,
) -> dict:
    if name == "ask_user":
        return execute_ask_user(arguments)
    if name in memory_tools:
        return execute_memory_tool(name, arguments)

    user_input = str(arguments.get("user_input") or "").strip()
    skill_route = {"skill": name}
    ctx = context if isinstance(context, dict) else {}
    for key, value in arguments.items():
        if key != "user_input" and value:
            ctx[key] = value
    ctx = apply_protocol_context(name, ctx, user_input, arguments)
    debug_write(
        "tool_call_execute",
        {
            "name": name,
            "user_input": user_input[:100],
            "extra_args": {key: value for key, value in arguments.items() if key != "user_input"},
        },
    )
    normalized_result = normalize_tool_adapter_result(
        execute_skill(skill_route, user_input, ctx),
        name=name,
    )
    remember_protocol_target(name, ctx, normalized_result)
    debug_write(
        "tool_call_result",
        {
            "name": name,
            "success": normalized_result.get("success"),
            "response_len": len(str(normalized_result.get("response") or "")),
        },
    )
    return normalized_result


def normalize_tool_adapter_result(result: object, *, name: str) -> dict:
    normalized = result.copy() if isinstance(result, dict) else {
        "success": False,
        "error": "执行结果格式异常：预期为 dict",
        "response": str(result),
    }
    normalized = _normalize_legacy_operation_result(normalized)
    if not isinstance(normalized.get("success"), bool):
        normalized["success"] = bool(normalized.get("success"))
    normalized.setdefault("skill", name)
    if normalized.get("success") is False and "error" not in normalized:
        normalized["error"] = normalized.get("response", "执行失败")
    if normalized.get("success") is True and "error" in normalized and not normalized.get("response"):
        normalized["response"] = str(normalized.get("error"))
        normalized.pop("error", None)
    if normalized.get("success") is True and "response" not in normalized:
        normalized["response"] = ""
    return normalized


def execute_tool_call(
    name: str,
    arguments: dict,
    context: dict | None = None,
    *,
    execute_tool_call_legacy,
    debug_write,
) -> dict:
    try:
        raise_if_cancelled(context, detail=f"{name} cancelled before execution")
        return normalize_tool_adapter_result(
            execute_tool_call_legacy(name, arguments, context),
            name=name,
        )
    except ToolRuntimeInterrupted as exc:
        debug_write(
            "tool_call_interrupted",
            {"name": name, "reason": exc.reason, "detail": exc.detail},
        )
        return normalize_tool_adapter_result(
            build_interrupted_tool_result(name, reason=exc.reason, detail=exc.detail),
            name=name,
        )
    except Exception as exc:
        error_message = f"执行异常: {type(exc).__name__}: {exc}"
        debug_write("tool_call_execute_error", {"name": name, "error": error_message})
        return {
            "success": False,
            "error": error_message,
            "response": error_message,
            "skill": name,
        }
