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
    looks_like_structured_tool_handoff,
    looks_like_trailing_tool_handoff,
    build_tool_closeout_reply,
    re_mod,
) -> str:
    cleaned = clean_visible_reply_text(raw_reply)
    if cleaned and looks_like_structured_tool_handoff(cleaned):
        return build_tool_closeout_reply(
            success=success,
            action_summary=action_summary,
            tool_response=tool_response,
            run_meta=run_meta,
        )
    cleaned = strip_trailing_tool_handoff(
        cleaned,
        clean_visible_reply_text=clean_visible_reply_text,
        looks_like_tool_preamble=looks_like_tool_preamble,
        looks_like_structured_tool_handoff=looks_like_structured_tool_handoff,
        looks_like_trailing_tool_handoff=looks_like_trailing_tool_handoff,
        re_mod=re_mod,
    )
    if cleaned and not (
        looks_like_tool_preamble(cleaned) or looks_like_structured_tool_handoff(cleaned)
    ):
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
    looks_like_structured_tool_handoff,
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
    joined = clean_visible_reply_text("\n\n".join(visible))
    if joined and (
        looks_like_tool_preamble(joined) or looks_like_structured_tool_handoff(joined)
    ):
        return True
    return all(
        looks_like_tool_preamble(text) or looks_like_structured_tool_handoff(text)
        for text in visible
    )


def strip_trailing_tool_handoff(
    text: str,
    *,
    clean_visible_reply_text,
    looks_like_tool_preamble,
    looks_like_structured_tool_handoff,
    looks_like_trailing_tool_handoff,
    re_mod,
) -> str:
    cleaned = clean_visible_reply_text(text)
    if not cleaned or not looks_like_trailing_tool_handoff(cleaned):
        return cleaned

    paragraphs = [part.strip() for part in re_mod.split(r"\n\s*\n", cleaned) if part.strip()]
    lines = [line.strip() for line in cleaned.replace("\r", "\n").splitlines() if line.strip()]
    candidates: list[tuple[str, str]] = []

    if len(paragraphs) >= 2:
        candidates.append(("\n\n".join(paragraphs[:-1]).strip(), paragraphs[-1].strip()))
    if len(lines) >= 2:
        candidates.append(("\n".join(lines[:-1]).strip(), lines[-1].strip()))
    if len(lines) >= 3:
        candidates.append(("\n".join(lines[:-2]).strip(), "\n".join(lines[-2:]).strip()))

    for remaining, tail in candidates:
        if not remaining or not tail:
            continue
        if not (
            looks_like_tool_preamble(tail)
            or looks_like_structured_tool_handoff(tail)
        ):
            continue
        stripped = clean_visible_reply_text(remaining)
        if not stripped:
            continue
        if looks_like_tool_preamble(stripped) or looks_like_structured_tool_handoff(stripped):
            continue
        return stripped

    return cleaned
