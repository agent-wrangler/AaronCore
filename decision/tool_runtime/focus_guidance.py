"""Known file/directory focus guidance for post-LLM tool runtime."""


def is_write_file_content_arg_failure(signature: dict | None) -> bool:
    signature = signature if isinstance(signature, dict) else {}
    if str(signature.get("tool") or "").strip() != "write_file":
        return False
    missing_fields = {str(x).strip() for x in (signature.get("missing_fields") or []) if str(x).strip()}
    return "content" in missing_fields


def tool_definition_name(tool_def: dict | None) -> str:
    tool_def = tool_def if isinstance(tool_def, dict) else {}
    fn = tool_def.get("function") if isinstance(tool_def.get("function"), dict) else {}
    return str(fn.get("name") or tool_def.get("name") or "").strip()


def resolve_existing_file_target(tool_args: dict | None, *, resolve_protocol_user_file_target) -> str:
    tool_args = tool_args if isinstance(tool_args, dict) else {}
    raw_target = (
        str(tool_args.get("file_path") or tool_args.get("path") or "").strip()
        or str(tool_args.get("target") or tool_args.get("filename") or "").strip()
    )
    if not raw_target:
        return ""
    try:
        target = resolve_protocol_user_file_target(raw_target)
    except Exception:
        target = None
    if not target or not target.exists() or not target.is_file():
        return ""
    return str(target)


def resolve_known_fs_focus_target(
    bundle: dict | None = None,
    tool_args: dict | None = None,
    *,
    load_context_fs_target,
    load_task_plan_fs_target,
    extract_recent_file_paths,
    resolve_protocol_user_file_target,
) -> tuple[str, str]:
    candidates = []
    tool_args = tool_args if isinstance(tool_args, dict) else {}
    bundle = bundle if isinstance(bundle, dict) else {}

    raw_tool_target = (
        str(tool_args.get("file_path") or tool_args.get("path") or "").strip()
        or str(tool_args.get("target") or tool_args.get("filename") or "").strip()
    )
    if raw_tool_target:
        candidates.append(raw_tool_target)

    for candidate in (load_context_fs_target(bundle), load_task_plan_fs_target(bundle)):
        candidate = str(candidate or "").strip()
        if candidate:
            candidates.append(candidate)

    for candidate in extract_recent_file_paths(bundle):
        candidate = str(candidate or "").strip()
        if candidate:
            candidates.append(candidate)

    seen = set()
    for raw_target in candidates:
        lowered = raw_target.replace("/", "\\").lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        try:
            target = resolve_protocol_user_file_target(raw_target)
        except Exception:
            target = None
        if not target or not target.exists():
            continue
        if target.is_file():
            return str(target), "file"
        if target.is_dir():
            return str(target), "directory"
    return "", ""


def build_fs_focus_guidance(bundle: dict | None = None, tool_args: dict | None = None, *, resolve_known_fs_focus_target) -> str:
    target, target_kind = resolve_known_fs_focus_target(bundle, tool_args)
    if target_kind == "file":
        return "\n".join([
            f"Known coding target: {target}",
            "This already resolves to an existing file. Stay on this file first.",
            "Primary coding lane: read_file -> write_file -> run_command verification when needed.",
            "Prefer read_file for context, then use write_file for the actual change.",
            "Use write_file for both instruction-driven updates and intentional whole-file rewrites.",
            "These are priorities, not hard bans.",
            "Do not jump to folder_explore or desktop/app inspection unless this file path is wrong or adjacent context is truly required.",
        ])
    if target_kind == "directory":
        return "\n".join([
            f"Known task directory: {target}",
            "Stay inside this directory for the current coding task.",
            "Primary coding lane: list_files -> read_file -> write_file.",
            "Prefer list_files or read_file before broad folder_explore when the task directory is already known.",
        ])
    return ""


def reprioritize_tools_for_coding_focus(
    tools: list[dict] | None,
    *,
    target_kind: str = "",
    current_tool_name: str = "",
    tool_definition_name,
    debug_write,
) -> list[dict]:
    tool_list = list(tools or [])
    if target_kind not in {"file", "directory"}:
        return tool_list

    coding_anchor_tools = {
        "read_file",
        "list_files",
        "write_file",
        "run_command",
        "task_plan",
        "ask_user",
    }
    current_name = str(current_tool_name or "").strip()
    if current_name and current_name not in coding_anchor_tools:
        return tool_list

    priority = {
        "file": {
            "read_file": 0,
            "write_file": 1,
            "run_command": 2,
            "list_files": 3,
            "task_plan": 4,
            "ask_user": 5,
        },
        "directory": {
            "list_files": 0,
            "read_file": 1,
            "write_file": 2,
            "run_command": 3,
            "task_plan": 4,
            "ask_user": 5,
        },
    }.get(target_kind, {})

    ranked = sorted(
        enumerate(tool_list),
        key=lambda item: (priority.get(tool_definition_name(item[1]), 20), item[0]),
    )
    reprioritized = [item[1] for item in ranked]
    if reprioritized != tool_list:
        debug_write("coding_focus_tools_reprioritized", {
            "target_kind": target_kind,
            "current_tool": current_name,
            "front": [tool_definition_name(tool) for tool in reprioritized[:8]],
        })
    return reprioritized


def build_followup_tools_after_arg_failure(
    tools: list[dict] | None,
    arg_failure: dict | None,
    tool_args: dict | None,
    bundle: dict | None = None,
    current_tool_name: str = "",
    *,
    resolve_known_fs_focus_target,
    tool_definition_name,
    reprioritize_tools_for_coding_focus,
    is_write_file_content_arg_failure,
    resolve_existing_file_target,
    debug_write,
) -> list[dict]:
    tool_list = list(tools or [])
    focused_target, focused_kind = resolve_known_fs_focus_target(bundle, tool_args)
    if focused_kind in {"file", "directory"}:
        blocked_tools = {
            "folder_explore",
            "sense_environment",
            "screen_capture",
            "open_target",
            "app_target",
            "ui_interaction",
        }
        filtered = []
        removed = []
        for tool in tool_list:
            name = tool_definition_name(tool)
            if name in blocked_tools:
                removed.append(name)
                continue
            filtered.append(tool)
        if filtered and removed:
            debug_write("file_focus_followup_tools_filtered", {
                "target": focused_target,
                "removed": removed,
                "remaining_tools": len(filtered),
            })
            tool_list = filtered
        tool_list = reprioritize_tools_for_coding_focus(
            tool_list,
            target_kind=focused_kind,
            current_tool_name=current_tool_name or str((arg_failure or {}).get("tool") or ""),
        )

    if not is_write_file_content_arg_failure(arg_failure):
        return tool_list

    existing_target = resolve_existing_file_target(tool_args) or (focused_target if focused_kind == "file" else "")
    if existing_target:
        debug_write("write_file_followup_tools_kept", {
            "target": existing_target,
            "available_tools": len(tool_list),
        })
    return tool_list


def build_strict_write_file_retry_note(
    tool_args: dict | None,
    signature: dict | None = None,
    *,
    resolve_existing_file_target,
) -> str:
    tool_args = tool_args if isinstance(tool_args, dict) else {}
    signature = signature if isinstance(signature, dict) else {}
    target = (
        str(tool_args.get("file_path") or tool_args.get("path") or "").strip()
        or str(signature.get("target") or "").strip()
        or "unknown target"
    )
    existing_target = resolve_existing_file_target(tool_args)
    if existing_target:
        return (
            f"The write_file target is {target}, and that file already exists at {existing_target}. "
            "Do not send natural-language promises in the next turn. "
            "Your next assistant turn must do exactly one of these: "
            "(1) call write_file with the SAME file_path and either the COMPLETE final content string or a precise change_request/description; "
            "(2) if you still need surrounding project context, call read_file or list_files first. "
            "Do not repeat write_file with only file_path."
        )
    return (
        f"The write_file target is {target}. "
        "Do not send natural-language promises in the next turn. "
        "Your next assistant turn must do exactly one of these: "
        "(1) call write_file with the SAME file_path and either the COMPLETE final content string or a precise change_request/description; "
        "(2) if you still need surrounding project context, call list_files or read_file first. "
        "Do not repeat write_file with only file_path."
    )
