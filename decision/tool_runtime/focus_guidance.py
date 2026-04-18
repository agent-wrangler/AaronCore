"""Known file/directory focus guidance for post-LLM tool runtime."""


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _clean_lower_text(value: object) -> str:
    return _clean_text(value).lower()


def _coerce_dict(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _priority_map(*names: str) -> dict[str, int]:
    return {
        str(name).strip(): index
        for index, name in enumerate(names)
        if str(name).strip()
    }


def _bundle_working_state(bundle: dict | None) -> dict:
    bundle = bundle if isinstance(bundle, dict) else {}
    l2_session = bundle.get("l2") if isinstance(bundle.get("l2"), dict) else {}
    return l2_session.get("working_state") if isinstance(l2_session.get("working_state"), dict) else {}


def _resolve_execution_lane(bundle: dict | None, tool_run_meta: dict | None = None) -> str:
    working_state = _bundle_working_state(bundle)
    current_step_task = _coerce_dict(working_state.get("current_step_task"))
    explicit_lane = _clean_lower_text(
        current_step_task.get("execution_lane") or working_state.get("execution_lane")
    )
    if explicit_lane:
        return explicit_lane

    run_meta = _coerce_dict(tool_run_meta)
    process_meta = _coerce_dict(run_meta.get("process_meta"))
    return _clean_lower_text(process_meta.get("execution_lane"))


def _lane_coding_priority(*, target_kind: str = "", execution_lane: str = "") -> dict[str, int]:
    lane = _clean_lower_text(execution_lane)
    if target_kind not in {"file", "directory"} or not lane:
        return {}

    if lane == "inspect":
        if target_kind == "file":
            return _priority_map(
                "read_file",
                "list_files",
                "task_plan",
                "ask_user",
                "run_command",
                "write_file",
            )
        return _priority_map(
            "list_files",
            "read_file",
            "task_plan",
            "ask_user",
            "run_command",
            "write_file",
        )

    if lane == "implement":
        if target_kind == "file":
            return _priority_map(
                "write_file",
                "read_file",
                "run_command",
                "list_files",
                "task_plan",
                "ask_user",
            )
        return _priority_map(
            "read_file",
            "list_files",
            "write_file",
            "run_command",
            "task_plan",
            "ask_user",
        )

    if lane == "verify":
        return _priority_map(
            "run_command",
            "read_file",
            "list_files",
            "write_file",
            "task_plan",
            "ask_user",
        )

    return {}


def _dynamic_coding_priority(
    *,
    target_kind: str = "",
    effective_tool_name: str = "",
    runtime_status: str = "",
    verification_status: str = "",
    execution_lane: str = "",
) -> dict[str, int]:
    if target_kind not in {"file", "directory"}:
        return {}

    tool_name = _clean_text(effective_tool_name)
    if not tool_name:
        return {}

    status = _clean_lower_text(runtime_status)
    verification = _clean_lower_text(verification_status)
    lane = _clean_lower_text(execution_lane)
    failure_statuses = {"arg_failed", "blocked", "failed", "runtime_failed", "verify_failed"}
    failed_verification_statuses = {"failed", "verify_failed"}
    has_failure = status in failure_statuses or verification in failed_verification_statuses

    if lane == "inspect":
        return _lane_coding_priority(target_kind=target_kind, execution_lane=lane)

    if lane == "verify":
        if has_failure:
            return _priority_map(
                "read_file",
                "write_file",
                "run_command",
                "list_files",
                "task_plan",
                "ask_user",
            )
        return _lane_coding_priority(target_kind=target_kind, execution_lane=lane)

    if tool_name == "list_files" and not has_failure:
        return _priority_map(
            "read_file",
            "write_file",
            "run_command",
            "list_files",
            "task_plan",
            "ask_user",
        )

    if tool_name == "read_file" and not has_failure:
        return _priority_map(
            "write_file",
            "run_command",
            "read_file",
            "list_files",
            "task_plan",
            "ask_user",
        )

    if tool_name == "write_file":
        if status == "arg_failed":
            return _priority_map(
                "write_file",
                "read_file",
                "run_command",
                "list_files",
                "task_plan",
                "ask_user",
            )
        if has_failure:
            return _priority_map(
                "read_file",
                "write_file",
                "run_command",
                "list_files",
                "task_plan",
                "ask_user",
            )
        return _priority_map(
            "run_command",
            "read_file",
            "write_file",
            "list_files",
            "task_plan",
            "ask_user",
        )

    if tool_name == "run_command" and has_failure:
        return _priority_map(
            "read_file",
            "write_file",
            "run_command",
            "list_files",
            "task_plan",
            "ask_user",
        )

    return {}


def _resolve_followup_runtime_hints(
    bundle: dict | None,
    tool_run_meta: dict | None,
    *,
    current_tool_name: str = "",
    arg_failure: dict | None = None,
) -> tuple[str, str, str]:
    bundle = bundle if isinstance(bundle, dict) else {}
    working_state = _bundle_working_state(bundle)
    run_meta = _coerce_dict(tool_run_meta)
    runtime_state = _coerce_dict(run_meta.get("runtime_state"))
    verification = _coerce_dict(run_meta.get("verification"))

    last_tool_name = _clean_text(current_tool_name) or _clean_text(working_state.get("last_tool"))
    runtime_status = _clean_lower_text(runtime_state.get("status") or working_state.get("runtime_status"))
    verification_status = _clean_lower_text(verification.get("status") or working_state.get("verification_status"))

    if not verification_status:
        if runtime_status == "verified":
            verification_status = "verified"
        elif runtime_status == "verify_failed":
            verification_status = "failed"

    if arg_failure and not runtime_status:
        runtime_status = "arg_failed"

    return last_tool_name, runtime_status, verification_status


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
    execution_lane = _resolve_execution_lane(bundle)
    if target_kind == "file":
        lines = []
        if execution_lane == "inspect":
            lines.extend([
                "Current coding lane: inspect",
                "Treat this step like an inspection subtask: stay read-first, gather concrete context, and avoid speculative edits.",
            ])
        elif execution_lane == "implement":
            lines.extend([
                "Current coding lane: implement",
                "Treat this step like an implementation subtask: stay change-focused and prefer write_file after you have enough file context.",
            ])
        elif execution_lane == "verify":
            lines.extend([
                "Current coding lane: verify",
                "Treat this step like a verification subtask: prefer run_command or read_file to confirm behavior before making another edit.",
            ])
        lines.extend([
            f"Known coding target: {target}",
            "This already resolves to an existing file. Stay on this file first.",
            "Primary coding lane: read_file -> write_file -> run_command verification when needed.",
            "Prefer read_file for context, then use write_file for the actual change.",
            "Use write_file for both instruction-driven updates and intentional whole-file rewrites.",
            "These are priorities, not hard bans.",
            "Do not jump to folder_explore or desktop/app inspection unless this file path is wrong or adjacent context is truly required.",
        ])
        return "\n".join(lines)
    if target_kind == "directory":
        lines = []
        if execution_lane == "inspect":
            lines.extend([
                "Current coding lane: inspect",
                "Treat this step like an inspection subtask: stay inside the directory, map the relevant files, and avoid edits until the target is grounded.",
            ])
        elif execution_lane == "implement":
            lines.extend([
                "Current coding lane: implement",
                "Treat this step like an implementation subtask: narrow to the relevant files quickly, then move into write_file.",
            ])
        elif execution_lane == "verify":
            lines.extend([
                "Current coding lane: verify",
                "Treat this step like a verification subtask: prefer run_command plus focused reads over broad exploration.",
            ])
        lines.extend([
            f"Known task directory: {target}",
            "Stay inside this directory for the current coding task.",
            "Primary coding lane: list_files -> read_file -> write_file.",
            "Prefer list_files or read_file before broad folder_explore when the task directory is already known.",
        ])
        return "\n".join(lines)
    return ""


def reprioritize_tools_for_coding_focus(
    tools: list[dict] | None,
    *,
    target_kind: str = "",
    current_tool_name: str = "",
    last_tool_name: str = "",
    runtime_status: str = "",
    verification_status: str = "",
    execution_lane: str = "",
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
    current_name = _clean_text(current_tool_name)
    if current_name and current_name not in coding_anchor_tools:
        return tool_list
    effective_last_tool = _clean_text(last_tool_name)
    effective_tool_name = current_name or (
        effective_last_tool if effective_last_tool in coding_anchor_tools else ""
    )

    default_priority = {
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
    lane_priority = _lane_coding_priority(target_kind=target_kind, execution_lane=execution_lane)
    priority = lane_priority or default_priority
    dynamic_priority = _dynamic_coding_priority(
        target_kind=target_kind,
        effective_tool_name=effective_tool_name,
        runtime_status=runtime_status,
        verification_status=verification_status,
        execution_lane=execution_lane,
    )

    ranked = sorted(
        enumerate(tool_list),
        key=lambda item: (
            dynamic_priority.get(
                tool_definition_name(item[1]),
                priority.get(
                    tool_definition_name(item[1]),
                    default_priority.get(tool_definition_name(item[1]), 20),
                ),
            ),
            priority.get(
                tool_definition_name(item[1]),
                default_priority.get(tool_definition_name(item[1]), 20),
            ),
            item[0],
        ),
    )
    reprioritized = [item[1] for item in ranked]
    if reprioritized != tool_list:
        debug_write("coding_focus_tools_reprioritized", {
            "target_kind": target_kind,
            "current_tool": current_name,
            "last_tool": effective_last_tool,
            "runtime_status": runtime_status,
            "verification_status": verification_status,
            "execution_lane": _clean_lower_text(execution_lane),
            "front": [tool_definition_name(tool) for tool in reprioritized[:8]],
        })
    return reprioritized


def build_followup_tools_after_arg_failure(
    tools: list[dict] | None,
    arg_failure: dict | None,
    tool_args: dict | None,
    bundle: dict | None = None,
    current_tool_name: str = "",
    tool_run_meta: dict | None = None,
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
    execution_lane = _resolve_execution_lane(bundle, tool_run_meta)
    last_tool_name, runtime_status, verification_status = _resolve_followup_runtime_hints(
        bundle,
        tool_run_meta,
        current_tool_name=current_tool_name or str((arg_failure or {}).get("tool") or ""),
        arg_failure=arg_failure,
    )
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
            last_tool_name=last_tool_name,
            runtime_status=runtime_status,
            verification_status=verification_status,
            execution_lane=execution_lane,
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
