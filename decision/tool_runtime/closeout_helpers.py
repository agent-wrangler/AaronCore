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


def build_missing_execution_closeout_reply(*, reason: str = "", summary: str = "") -> str:
    reason_key = str(reason or "").strip()
    base_reply = {
        "local_inspection_without_tool": "这一步先停在这里，还没有拿到新的读取或检查结果。",
        "completion_without_tool": "这一步先停在这里，还没有拿到新的执行结果。",
        "preamble_without_tool": "这一步先停在这里，还没有拿到新的实际结果。",
    }.get(reason_key, "这一步先停在这里，还没有拿到新的实际结果。")

    summary_text = str(summary or "").strip()
    if not summary_text:
        return base_reply

    lowered = summary_text.lower()
    if any(
        marker in lowered
        for marker in (
            "claimed local inspection",
            "claimed completion",
            "without a real",
            "tool result",
            "local_inspection_without_tool",
            "completion_without_tool",
            "preamble_without_tool",
        )
    ):
        return base_reply

    if summary_text in base_reply:
        return base_reply
    return _build_closeout_text(base_reply, summary=summary_text)


def _extract_process_meta(run_meta: dict | None) -> dict:
    if not isinstance(run_meta, dict):
        return {}
    process_meta = run_meta.get("process_meta")
    return dict(process_meta) if isinstance(process_meta, dict) else {}


def _build_closeout_text(
    prefix: str,
    *,
    summary: str = "",
    detail: str = "",
    detail_label: str = "",
    allow_long_detail: bool = False,
) -> str:
    prefix_text = str(prefix or "").strip()
    summary_text = str(summary or "").strip()
    detail_text = str(detail or "").strip()
    label_text = str(detail_label or "").strip()
    detail_can_append = bool(detail_text) and (
        allow_long_detail or len(detail_text) <= 160
    )

    if summary_text and detail_can_append and detail_text not in summary_text:
        if label_text:
            return f"{prefix_text}\n\n{summary_text}\n\n{label_text}：{detail_text}"
        return f"{prefix_text}\n\n{summary_text}\n\n{detail_text}"
    if summary_text:
        return f"{prefix_text}\n\n{summary_text}"
    if detail_text:
        if label_text:
            return f"{prefix_text}\n\n{label_text}：{detail_text}"
        return f"{prefix_text}\n\n{detail_text}"
    return prefix_text


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
    summary = str(action_summary or "").strip()
    if not summary and isinstance(run_meta, dict):
        action = run_meta.get("action") if isinstance(run_meta.get("action"), dict) else {}
        summary = summarize_action_meta(action)
    if not summary:
        summary = summarize_tool_response_text(tool_response)

    process_meta = _extract_process_meta(run_meta)
    outcome_kind = str(process_meta.get("outcome_kind") or "").strip()
    next_hint_kind = str(process_meta.get("next_hint_kind") or "").strip()

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

    if next_hint_kind == "wait_for_user" or outcome_kind == "blocked":
        return _build_closeout_text(
            "这一步先停在需要你接手的位置了。你先完成登录、验证、验证码或其他只能由你完成的步骤，然后我再继续。",
            summary=summary,
            detail=tool_response,
            detail_label="当前情况",
        )

    if outcome_kind == "interrupted":
        return _build_closeout_text(
            "这一步刚才被中断了，我先停在这里。你如果要继续，我可以从当前状态接着往下走。",
            summary=summary,
            detail=tool_response,
            detail_label="中断前状态",
        )

    if not success:
        if outcome_kind == "arg_failure":
            return _build_closeout_text(
                "这一步没接稳，参数还不完整。",
                summary=summary,
                detail=tool_response,
                detail_label="缺口",
                allow_long_detail=True,
            )
        if outcome_kind == "runtime_failure":
            return _build_closeout_text(
                "这一步在执行里断掉了，还没有形成完整闭环。",
                summary=summary,
                detail=tool_response,
                detail_label="中断原因",
            )
        if outcome_kind == "failed":
            return _build_closeout_text(
                "这一步没接稳。",
                summary=summary,
                detail=tool_response,
                detail_label="失败原因",
            )
        return fallback_tool_reply(tool_response)

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

    if verification_state is False:
        if summary and verification_detail and verification_detail not in summary and len(verification_detail) <= 160:
            return f"这一步已经执行，但核验没有通过：\n\n{summary}\n\n核验失败：{verification_detail}"
        if summary:
            return f"这一步已经执行，但核验没有通过：\n\n{summary}"
        if verification_detail:
            return f"这一步已经执行，但核验没有通过：\n\n核验失败：{verification_detail}"
        return "这一步已经执行，但核验没有通过。"

    if summary and verification_detail and verification_detail not in summary and len(verification_detail) <= 160:
        return f"这一步已经完成：\n\n{summary}\n\n核验：{verification_detail}"
    if summary:
        return f"这一步已经完成：\n\n{summary}"
    return ""


def should_retry_tool_continuation_reply(
    text: str,
    *,
    run_meta: dict | None = None,
    clean_visible_reply_text,
    looks_like_tool_preamble,
    looks_like_structured_tool_handoff,
) -> bool:
    process_meta = _extract_process_meta(run_meta)
    if str(process_meta.get("next_hint_kind") or "").strip() != "continue":
        return False

    visible = clean_visible_reply_text(text)
    if not visible:
        return True
    return bool(
        looks_like_tool_preamble(visible)
        or looks_like_structured_tool_handoff(visible)
    )


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
    split_trailing_tool_handoff,
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
        split_trailing_tool_handoff=split_trailing_tool_handoff,
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
    split_trailing_tool_handoff,
    re_mod,
) -> str:
    cleaned = clean_visible_reply_text(text)
    if not cleaned or not looks_like_trailing_tool_handoff(cleaned):
        return cleaned

    split = split_trailing_tool_handoff(cleaned) if callable(split_trailing_tool_handoff) else None
    if split:
        stripped, _tail = split
        if stripped and not (
            looks_like_tool_preamble(stripped) or looks_like_structured_tool_handoff(stripped)
        ):
            return clean_visible_reply_text(stripped)

    return cleaned
