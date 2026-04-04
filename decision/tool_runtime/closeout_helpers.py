"""Tool-call closeout text helpers."""


def format_skill_fallback_text(skill_response: str) -> str:
    text = str(skill_response or "").strip()
    if not text:
        return "这一步没接稳，不过失败点我已经接住了。"
    failure_markers = ("执行失败", "缺少 ", "安全限制", "未找到", "卡住", "blocked", "failed")
    if any(marker in text for marker in failure_markers):
        return f"这一步没接稳：\n\n{text}"
    return f"我先把当前结果接住：\n\n{text}"


def summarize_tool_response_text(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return ""
    text = text.replace("`", "")
    text = text.replace("\r", "\n")
    lines = [line.strip(" -") for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    summary = " / ".join(lines[:2]).strip()
    return summary[:140] + ("..." if len(summary) > 140 else "")


def fallback_tool_reply(tool_response: str, *, format_skill_fallback) -> str:
    text = str(tool_response or "").strip()
    if not text:
        return ""
    if callable(format_skill_fallback):
        return format_skill_fallback(text)
    return format_skill_fallback_text(text)


def build_tool_closeout_reply(
    *,
    success: bool,
    action_summary: str = "",
    tool_response: str = "",
    run_meta: dict | None = None,
    summarize_action_meta,
    summarize_tool_response_text,
    fallback_tool_reply,
) -> str:
    if not success:
        return fallback_tool_reply(tool_response)

    summary = str(action_summary or "").strip()
    if not summary and isinstance(run_meta, dict):
        action = run_meta.get("action") if isinstance(run_meta.get("action"), dict) else {}
        summary = summarize_action_meta(action)
    if not summary:
        summary = summarize_tool_response_text(tool_response)

    verification = run_meta.get("verification") if isinstance(run_meta, dict) and isinstance(run_meta.get("verification"), dict) else {}
    verification_detail = ""
    verification_state = "__missing__"
    if verification:
        verification_state = verification.get("verified", "__missing__")
        verification_detail = str(
            verification.get("verification_detail")
            or verification.get("detail")
            or ""
        ).strip()
    if not verification_detail and isinstance(run_meta, dict):
        action = run_meta.get("action") if isinstance(run_meta.get("action"), dict) else {}
        verification_detail = str(action.get("verification_detail") or "").strip()

    if verification_state is True:
        if summary and verification_detail and verification_detail not in summary and len(verification_detail) <= 160:
            return f"这一步已经完成，并已通过核验：\n\n{summary}\n\n核验：{verification_detail}"
        if summary:
            return f"这一步已经完成，并已通过核验：\n\n{summary}"
        return ""

    if verification_state is None:
        if summary and verification_detail and verification_detail not in summary and len(verification_detail) <= 160:
            return f"这一步已经完成，但当前还没有可靠核验：\n\n{summary}\n\n说明：{verification_detail}"
        if summary:
            return f"这一步已经完成，但当前还没有可靠核验：\n\n{summary}"
        return ""

    if summary and verification_detail and verification_detail not in summary and len(verification_detail) <= 160:
        return f"这一步已经完成：\n\n{summary}\n\n核验：{verification_detail}"
    if summary:
        return f"这一步已经完成：\n\n{summary}"
    return ""


def finalize_tool_reply(
    raw_reply: str,
    *,
    success: bool,
    action_summary: str = "",
    tool_response: str = "",
    run_meta: dict | None = None,
    clean_visible_reply_text,
    looks_like_tool_preamble,
    build_tool_closeout_reply,
) -> str:
    cleaned = clean_visible_reply_text(raw_reply)
    if cleaned and not looks_like_tool_preamble(cleaned):
        return cleaned
    return build_tool_closeout_reply(
        success=success,
        action_summary=action_summary,
        tool_response=tool_response,
        run_meta=run_meta,
    )


def has_only_preamble_text(
    chunks: list,
    *,
    clean_visible_reply_text,
    looks_like_tool_preamble,
) -> bool:
    visible = []
    for chunk in chunks or []:
        if not isinstance(chunk, str):
            continue
        cleaned = clean_visible_reply_text(chunk)
        if cleaned:
            visible.append(cleaned)
    if not visible:
        return True
    return all(looks_like_tool_preamble(text) for text in visible)
