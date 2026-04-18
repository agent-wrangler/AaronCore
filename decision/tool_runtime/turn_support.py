"""Turn-local helpers for tool-call runtime bookkeeping."""


def build_tool_exec_context(
    bundle: dict,
    *,
    load_task_plan_fs_target,
    load_context_fs_target,
    resolve_active_task_plan,
) -> dict:
    skill_context = {}
    l2_session = bundle.get("l2") if isinstance(bundle.get("l2"), dict) else {}
    working_state = l2_session.get("working_state") if isinstance(l2_session.get("working_state"), dict) else {}
    if working_state:
        skill_context["working_state"] = dict(working_state)
        current_step_task = working_state.get("current_step_task") if isinstance(working_state.get("current_step_task"), dict) else {}
        if current_step_task:
            skill_context["current_step_task"] = dict(current_step_task)
        execution_lane = str(
            (current_step_task.get("execution_lane") if current_step_task else "")
            or working_state.get("execution_lane")
            or ""
        ).strip()
        if execution_lane:
            skill_context["execution_lane"] = execution_lane
    l4 = bundle.get("l4") or {}
    if isinstance(l4, dict):
        up = l4.get("user_profile") or {}
        if isinstance(up, dict):
            user_location = str(up.get("location") or up.get("city") or "").strip()
            if user_location:
                skill_context["user_location"] = user_location
            user_city = str(up.get("city") or "").strip()
            if user_city:
                skill_context["user_city"] = user_city
            user_identity = str(up.get("identity") or "").strip()
            if user_identity:
                skill_context["user_identity"] = user_identity
    l1 = bundle.get("l1") or []
    if l1:
        skill_context["recent_history"] = [
            {"role": item.get("role", ""), "content": str(item.get("content") or "")[:300]}
            for item in l1[-8:]
            if isinstance(item, dict)
        ]
    context_data = bundle.get("context_data") if isinstance(bundle.get("context_data"), dict) else {}
    merged_context_data = dict(context_data) if context_data else {}
    task_plan_fs_target = load_task_plan_fs_target(bundle)
    context_fs_target = load_context_fs_target(bundle)
    task_fs_target = task_plan_fs_target or context_fs_target
    task_fs_source = "task_plan" if task_plan_fs_target else "context_data"
    if task_fs_target:
        skill_context["fs_target"] = {
            "path": task_fs_target,
            "option": "inspect",
            "source": task_fs_source,
        }
        if "fs_target" not in merged_context_data:
            merged_context_data["fs_target"] = {
                "path": task_fs_target,
                "option": "inspect",
                "source": task_fs_source,
            }
    if merged_context_data:
        skill_context["context_data"] = merged_context_data
    task_plan = resolve_active_task_plan(bundle)
    if task_plan:
        skill_context["task_plan"] = task_plan
    runtime_control = bundle.get("tool_runtime_control")
    if runtime_control is not None:
        skill_context["tool_runtime_control"] = runtime_control
    return skill_context


def tool_preview(name: str, arguments: dict) -> str:
    if not isinstance(arguments, dict):
        return ""

    candidates_by_tool = {
        "open_target": ("path", "url", "target"),
        "read_file": ("file_path", "path"),
        "list_files": ("path", "file_path"),
        "apply_unified_diff": ("file_path", "path", "target", "filename"),
        "search_replace": ("file_path", "path", "target", "filename"),
        "edit_file": ("file_path", "path", "target", "filename"),
        "write_file": ("file_path", "path", "target", "filename"),
        "save_export": ("filename", "destination"),
        "web_search": ("query", "intent"),
        "weather": ("city",),
        "news": ("topic",),
        "sense_environment": ("detail_level",),
        "ui_interaction": ("action", "target"),
        "app_target": ("target", "app", "path"),
        "ask_user": ("question",),
    }
    keys = candidates_by_tool.get(name, ())
    for key in keys:
        value = str(arguments.get(key) or "").strip()
        if value:
            return value[:120]
    return ""


def prepare_tool_call_runtime(
    tc: dict,
    bundle: dict,
    *,
    repair_tool_args_from_context,
    coerce_tool_args,
    sanitize_tool_call_payload,
    tool_preview,
) -> tuple[dict, str, dict, str]:
    fn = tc.get("function", {}) if isinstance(tc.get("function"), dict) else {}
    tool_name = str(fn.get("name") or "").strip()
    tool_args = repair_tool_args_from_context(
        tool_name,
        coerce_tool_args(fn.get("arguments", "{}"), bundle.get("user_input", "")),
        bundle,
    )
    sanitized = sanitize_tool_call_payload(tc, tool_args)
    preview = tool_preview(tool_name, tool_args)
    return sanitized, tool_name, tool_args, preview


def close_tool_call_as_synthetic_failure(
    ledger,
    tc: dict,
    bundle: dict,
    *,
    reason: str,
    detail: str = "",
    prepare_tool_call_runtime,
    synthesize_tool_failure_response,
    summarize_tool_response_text,
):
    sanitized, tool_name, tool_args, preview = prepare_tool_call_runtime(tc, bundle)
    record = ledger.register(
        sanitized,
        tool_name=tool_name,
        tool_args=tool_args,
        preview=preview,
    )
    response = synthesize_tool_failure_response(tool_name, reason, detail=detail)
    summary = summarize_tool_response_text(response)
    return ledger.mark_terminal(
        record.call_id,
        success=False,
        response=response,
        action_summary=summary,
        run_meta={},
        synthetic=True,
        reason=reason,
    )


def tool_action_summary(exec_result: dict, *, summarize_action_meta, re_mod) -> str:
    if not isinstance(exec_result, dict):
        return ""
    meta = exec_result.get("meta") if isinstance(exec_result.get("meta"), dict) else {}
    summary = summarize_action_meta(meta.get("action"))
    if summary:
        return summary
    response = str(exec_result.get("response") or "").strip()
    if not response:
        return ""
    response = re_mod.sub(r"\[drift:[^\]]+\]", "", response).strip().replace("`", "")
    lines = [line.strip(" -") for line in response.splitlines() if line.strip()]
    if not lines:
        return ""
    summary = " / ".join(lines[:2]).strip()
    return summary[:160] + ("..." if len(summary) > 160 else "")
