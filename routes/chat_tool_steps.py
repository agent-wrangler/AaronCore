from __future__ import annotations


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _summarize_text(value: object, *, limit: int = 140) -> str:
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


def _append_unique(parts: list[str], value: object) -> None:
    text = _clean_text(value)
    if not text or text in parts:
        return
    parts.append(text)


def _parallel_group_enabled(process_meta: dict | None) -> bool:
    meta = process_meta if isinstance(process_meta, dict) else {}
    return bool(_clean_text(meta.get("parallel_group_id"))) and int(meta.get("parallel_size") or 0) > 1


def _parallel_tool_names(process_meta: dict | None, *, fallback_tool: str = "") -> list[str]:
    meta = process_meta if isinstance(process_meta, dict) else {}
    names = [
        _clean_text(name)
        for name in (meta.get("parallel_tools") or [])
        if _clean_text(name)
    ]
    if not names and fallback_tool:
        names = [_clean_text(fallback_tool)]
    deduped: list[str] = []
    seen: set[str] = set()
    for name in names:
        lowered = name.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(name)
    return deduped


def _parallel_tool_names_text(process_meta: dict | None, *, fallback_tool: str = "") -> str:
    names = _parallel_tool_names(process_meta, fallback_tool=fallback_tool)
    if not names:
        return ""
    if len(names) <= 4:
        return ", ".join(names)
    return ", ".join(names[:4]) + f" (+{len(names) - 4} more)"


def _parallel_text(process_meta: dict | None) -> str:
    meta = process_meta if isinstance(process_meta, dict) else {}
    parallel_size = int(meta.get("parallel_size") or 0)
    parallel_index = int(meta.get("parallel_index") or 0)
    if parallel_size <= 1:
        return ""
    if parallel_index > 0:
        return f"parallel batch {parallel_index}/{parallel_size}"
    return f"parallel batch {parallel_size} actions"


def _tool_done_presentation_kind(success: bool, process_meta: dict | None) -> str:
    meta = process_meta if isinstance(process_meta, dict) else {}
    outcome_kind = _clean_text(meta.get("outcome_kind"))
    next_hint_kind = _clean_text(meta.get("next_hint_kind"))
    if next_hint_kind == "wait_for_user":
        return "wait_for_user"
    if outcome_kind in {
        "arg_failure",
        "blocked",
        "failed",
        "interrupted",
        "runtime_failure",
        "verify_failed",
    }:
        return outcome_kind
    if not success:
        return "failed"
    return ""


def build_tool_execution_trace_label(default_label: str, *, process_meta: dict | None = None) -> str:
    if _parallel_group_enabled(process_meta):
        return "PARALLEL CALL"
    return _clean_text(default_label) or "调用工具"


def build_tool_execution_trace_detail(
    *,
    tool_name: str,
    preview: str,
    skill_display: str,
    process_meta: dict | None = None,
) -> str:
    meta = process_meta if isinstance(process_meta, dict) else {}
    parts: list[str] = []
    base_name = _clean_text(tool_name) or _clean_text(skill_display)
    if _parallel_group_enabled(meta):
        parallel_size = int(meta.get("parallel_size") or 0)
        names_text = _parallel_tool_names_text(meta, fallback_tool=base_name)
        if names_text:
            return f"这一批同时起跑 {parallel_size} 个工具: {names_text}"
        return f"这一批同时起跑 {parallel_size} 个工具"
    _append_unique(parts, base_name)

    attempt_kind = _clean_text(meta.get("attempt_kind"))
    previous_tool = _clean_text(meta.get("previous_tool"))
    if attempt_kind == "fallback" and previous_tool:
        _append_unique(parts, f"上一步 {previous_tool} 没走通，切到这条路径")
    elif attempt_kind == "retry":
        _append_unique(parts, "根据上一轮结果继续重试")
    elif attempt_kind == "followup":
        _append_unique(parts, "沿着上一条结果继续推进")

    _append_unique(parts, _parallel_text(meta))
    if preview:
        _append_unique(parts, f"目标: {preview}")
    return " · ".join(parts) or f"正在{_clean_text(skill_display) or '执行工具'}..."


def build_tool_done_label(default_label: str, *, success: bool, process_meta: dict | None = None) -> str:
    meta = process_meta if isinstance(process_meta, dict) else {}
    if _parallel_group_enabled(meta):
        parallel_size = int(meta.get("parallel_size") or 0)
        completed = int(meta.get("parallel_completed_count") or 0)
        failure_count = int(meta.get("parallel_failure_count") or 0)
        if completed < parallel_size:
            return "PARALLEL RUN"
        if failure_count > 0 or not success:
            return "PARALLEL RESULT"
        return "PARALLEL DONE"

    outcome_kind = _tool_done_presentation_kind(success, meta)
    attempt_kind = _clean_text(meta.get("attempt_kind"))
    if outcome_kind == "wait_for_user":
        return "等待接手"
    if outcome_kind == "verify_failed":
        return "核验失败"
    if outcome_kind == "interrupted":
        return "已中断"
    if success and not outcome_kind:
        return default_label
    if outcome_kind == "blocked":
        return "等待接手"
    if outcome_kind == "arg_failure":
        return "参数待补"
    if outcome_kind == "runtime_failure":
        return "技能中断"
    if attempt_kind == "fallback":
        return "备用路径失败"
    if attempt_kind == "retry":
        return "重试失败"
    return default_label


def build_tool_done_trace_detail(
    *,
    tool_name: str,
    preview: str,
    success: bool,
    action_summary: str,
    response: str,
    process_meta: dict | None = None,
) -> str:
    meta = process_meta if isinstance(process_meta, dict) else {}
    parts: list[str] = []
    base_name = _clean_text(tool_name)
    if _parallel_group_enabled(meta):
        parallel_size = int(meta.get("parallel_size") or 0)
        completed = max(0, int(meta.get("parallel_completed_count") or 0))
        success_count = max(0, int(meta.get("parallel_success_count") or 0))
        failure_count = max(0, int(meta.get("parallel_failure_count") or 0))
        if completed <= 0:
            completed = 1
        pending_count = max(0, parallel_size - completed)
        names_text = _parallel_tool_names_text(meta, fallback_tool=base_name)
        if completed < parallel_size:
            parts.append(f"{parallel_size} 个工具同时在跑，已收回 {completed}/{parallel_size}")
            if success_count > 0:
                parts.append(f"成功 {success_count} 个")
            if failure_count > 0:
                parts.append(f"失败 {failure_count} 个")
            if pending_count > 0:
                parts.append(f"还在跑 {pending_count} 个")
        else:
            parts.append(f"{parallel_size} 个工具已经收口")
            if success_count > 0:
                parts.append(f"成功 {success_count} 个")
            if failure_count > 0:
                parts.append(f"失败 {failure_count} 个")
            elif success_count == parallel_size:
                parts.append("都已完成")
        if names_text:
            parts.append(f"这一批: {names_text}")
        return " · ".join(parts)

    _append_unique(parts, base_name)

    attempt_kind = _clean_text(meta.get("attempt_kind"))
    outcome_kind = _tool_done_presentation_kind(success, meta)
    reason = _clean_text(meta.get("reason"))
    next_hint_kind = _clean_text(meta.get("next_hint_kind"))
    summary = _clean_text(action_summary) or _summarize_text(response)

    if outcome_kind == "wait_for_user":
        _append_unique(parts, "需要用户接手")
        if next_hint_kind == "wait_for_user":
            _append_unique(parts, "先等你完成当前步骤再继续")
        _append_unique(parts, _parallel_text(meta))
        _append_unique(parts, summary)
        return " · ".join(parts)

    if outcome_kind == "verify_failed":
        _append_unique(parts, "已执行但核验没有通过")
        _append_unique(parts, _parallel_text(meta))
        if preview and not summary:
            _append_unique(parts, f"目标: {preview}")
        _append_unique(parts, summary)
        return " · ".join(parts)

    if success:
        if attempt_kind == "fallback":
            _append_unique(parts, "切换路径后完成")
        elif attempt_kind == "retry":
            _append_unique(parts, "重试后完成")
        elif attempt_kind == "followup":
            _append_unique(parts, "继续推进完成")
        _append_unique(parts, _parallel_text(meta))
        _append_unique(parts, summary)
        return " · ".join(parts)

    if outcome_kind == "blocked":
        _append_unique(parts, "需要用户接手")
    elif outcome_kind == "interrupted":
        _append_unique(parts, "这一步被中断了")
    elif outcome_kind == "arg_failure":
        _append_unique(parts, "参数还不完整")
    elif outcome_kind == "runtime_failure":
        if reason == "stream_signal_dropped":
            _append_unique(parts, "这一轮中断了，没拿到完整结果")
        elif reason == "tool_executor_exception":
            _append_unique(parts, "执行时抛异常了")
        else:
            _append_unique(parts, "执行链中断了")
    elif attempt_kind == "fallback":
        _append_unique(parts, "切换后的这条路径也没走通")
    elif attempt_kind == "retry":
        _append_unique(parts, "这次重试还是没走通")

    _append_unique(parts, _parallel_text(meta))
    if preview and not summary:
        _append_unique(parts, f"目标: {preview}")
    _append_unique(parts, summary)
    return " · ".join(parts)
