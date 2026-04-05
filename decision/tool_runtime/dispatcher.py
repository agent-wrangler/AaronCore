"""Dispatch helpers for post-LLM tool execution."""

from decision.tool_runtime.runtime_control import (
    ToolRuntimeInterrupted,
    build_interrupted_tool_result,
    raise_if_cancelled,
)


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
    result = execute_skill(skill_route, user_input, ctx)
    if isinstance(result, dict):
        result_success = result.get("success")
        result_response = result.get("response")
    else:
        result_success = None
        result_response = result
    remember_protocol_target(name, ctx, result)
    debug_write(
        "tool_call_result",
        {
            "name": name,
            "success": result_success,
            "response_len": len(str(result_response or "")),
        },
    )
    return result


def normalize_tool_adapter_result(result: object, *, name: str) -> dict:
    normalized = result.copy() if isinstance(result, dict) else {
        "success": False,
        "error": "执行结果格式异常：预期为 dict",
        "response": str(result),
    }
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
