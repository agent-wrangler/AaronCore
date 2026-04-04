"""Post-LLM tool-call result resolution helpers."""


def resolve_tool_calls_from_result(
    result: dict,
    bundle: dict,
    *,
    mode: str = "non_stream",
    parse_legacy_tool_call_text,
    force_app_tool_call_from_reply,
    infer_action_tool_call_from_reply,
    infer_directory_resolution_tool_call,
    debug_write,
) -> list[dict] | None:
    if not isinstance(result, dict):
        return None

    tool_calls = result.get("tool_calls")
    if tool_calls:
        return tool_calls

    content = result.get("content", "")
    legacy_tc = parse_legacy_tool_call_text(content, bundle.get("user_input", ""))
    if legacy_tc:
        debug_write("legacy_tool_call_compat", {"mode": mode, "name": legacy_tc.get("function", {}).get("name", "")})
        return [legacy_tc]

    forced_app_tc = force_app_tool_call_from_reply(
        content,
        bundle.get("user_input", ""),
    )
    if forced_app_tc:
        debug_write("forced_app_tool_call", {"mode": mode})
        return [forced_app_tc]

    inferred_tc = infer_action_tool_call_from_reply(
        content,
        bundle.get("user_input", ""),
        bundle.get("context_data"),
    )
    if inferred_tc:
        debug_write(
            "inferred_action_tool_call",
            {"mode": mode, "name": inferred_tc.get("function", {}).get("name", "")},
        )
        return [inferred_tc]

    directory_tc = infer_directory_resolution_tool_call(bundle, content)
    if directory_tc:
        debug_write("inferred_directory_resolution_tool_call", {"mode": mode})
        return [directory_tc]

    return None
