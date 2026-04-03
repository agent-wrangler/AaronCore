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


def _parallel_text(process_meta: dict | None) -> str:
    meta = process_meta if isinstance(process_meta, dict) else {}
    parallel_size = int(meta.get("parallel_size") or 0)
    parallel_index = int(meta.get("parallel_index") or 0)
    if parallel_size <= 1:
        return ""
    if parallel_index > 0:
        return f"并行批次 {parallel_index}/{parallel_size}"
    return f"并行批次 {parallel_size} 个动作"


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
        _append_unique(parts, f"目标：{preview}")
    return " · ".join(parts) or f"正在{_clean_text(skill_display) or '执行技能'}..."


def build_tool_done_label(default_label: str, *, success: bool, process_meta: dict | None = None) -> str:
    if success:
        return default_label
    meta = process_meta if isinstance(process_meta, dict) else {}
    outcome_kind = _clean_text(meta.get("outcome_kind"))
    attempt_kind = _clean_text(meta.get("attempt_kind"))
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
    _append_unique(parts, base_name)

    attempt_kind = _clean_text(meta.get("attempt_kind"))
    outcome_kind = _clean_text(meta.get("outcome_kind"))
    reason = _clean_text(meta.get("reason"))
    summary = _clean_text(action_summary) or _summarize_text(response)

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
        _append_unique(parts, f"目标：{preview}")
    _append_unique(parts, summary)
    return " · ".join(parts)
