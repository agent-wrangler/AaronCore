"""Runtime guidance helpers for post-LLM tool execution."""


def build_tool_arg_failure_feedback(
    tool_name: str,
    tool_args: dict,
    missing_fields: list[str],
    *,
    protocol_arg_failure_feedback,
) -> str:
    return protocol_arg_failure_feedback(tool_name, tool_args, missing_fields)


def build_tool_arg_failure_system_note(
    tool_name: str,
    tool_args: dict,
    missing_fields: list[str],
    *,
    protocol_arg_failure_system_note,
) -> str:
    return protocol_arg_failure_system_note(tool_name, tool_args, missing_fields)


def build_failed_tool_retry_note(
    tool_name: str,
    tool_args: dict,
    exec_result: dict,
    *,
    protocol_retry_note,
) -> str:
    return protocol_retry_note(tool_name, tool_args, exec_result)


def append_runtime_guidance(messages: list[dict], content: str) -> None:
    text = str(content or "").strip()
    if not text:
        return
    messages.append({
        "role": "user",
        "content": f"[INTERNAL RUNTIME GUIDANCE - NOT FROM THE USER]\n{text}",
    })


def build_visible_tools_context(tools: list[dict], *, tool_definition_name) -> str:
    visible = []
    for item in tools or []:
        if not isinstance(item, dict):
            continue
        fn = item.get("function") if isinstance(item.get("function"), dict) else {}
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        desc = str(fn.get("description") or "").strip()
        params = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
        props = params.get("properties") if isinstance(params.get("properties"), dict) else {}
        param_names = [str(k).strip() for k in props.keys() if str(k).strip()]
        if name in {n for n, _, _ in visible}:
            continue
        visible.append((name, desc, param_names))

    if not visible:
        return ""

    lines = [
        f"Visible tools in this turn: {len(visible)}.",
        "When reasoning about capabilities, rely on this visible tool list instead of prior conversation memory.",
        "Do not claim a tool is unavailable unless it is absent from the visible tool list below.",
        "If the user asks for a real action in the environment, you must execute the relevant tool before claiming success.",
        "Do not say an app, file, folder, page, click, input, save, move, or delete action is done unless the tool result confirms it.",
        "Use screen_capture only for visual inspection or verification. Do not use it as a substitute for open_target, app_target, or ui_interaction.",
    ]
    for name, desc, param_names in visible:
        entry = f"- {name}"
        if param_names:
            entry += f"({', '.join(param_names[:6])})"
        if desc:
            entry += f": {desc}"
        lines.append(entry)
    return "\n".join(lines)
