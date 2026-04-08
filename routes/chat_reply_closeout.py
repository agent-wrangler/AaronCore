from __future__ import annotations

import re

from core.reply_formatter import (
    _clean_visible_reply_text,
    _finalize_tool_reply,
    _looks_like_tool_preamble,
    _summarize_tool_response_text,
    l1_hygiene_clean,
)

_LIST_REQUEST_HINT_RE = re.compile(
    r"(?:\u5217\u4e00\u4e0b|\u6e05\u5355|\u5217\u8868|\u8981\u70b9|\u5206\u70b9|\u6b65\u9aa4|step|\u5bf9\u6bd4|\u4f18\u7f3a\u70b9|\u603b\u7ed3|\u6c47\u603b)",
    re.I,
)
_BULLET_LINE_RE = re.compile(r"^\s*(?:[-*•]|[0-9]{1,2}[.)\u3001])\s+")

_LOCAL_FILE_EVIDENCE_RE = re.compile(
    r"(?:`[^`\n]+\.(?:py|json|md|txt|ya?ml|toml|js|ts|jsx|tsx|css|html)`|"
    r"[A-Za-z]:\\\\[^\n]+|"
    r"\b[a-z0-9_\-]+\.(?:py|json|md|txt|ya?ml|toml|js|ts|jsx|tsx|css|html)\b|"
    r"\bL[1-9]\b|"
    r"\u6587\u4ef6|\u76ee\u5f55|\u9879\u76ee)",
    re.I,
)
_LOCAL_INSPECTION_LEAD_RE = re.compile(
    r"(?:let me|i(?:'m| am)? going to|i(?:'ve| have)?|just)\s+(?:check|inspect|look|read|search|find)|"
    r"(?:\u8ba9\u6211|\u6211\u5148|\u6211\u521a\u521a|\u6211\u5df2\u7ecf)?(?:\u53bb|\u5148\u53bb)?(?:\u770b\u770b|\u67e5\u770b|\u627e\u627e|\u641c\u7d22|\u8bfb\u53d6|\u5b9a\u4f4d)",
    re.I,
)
_LOCAL_INSPECTION_FINDING_RE = re.compile(
    r"(?:in\s+`[^`\n]+`\s+I\s+(?:found|saw)|"
    r"in\s+[A-Za-z]:\\\\[^\n]{0,120}\s+I\s+(?:found|saw)|"
    r"(?:\u5728|\u6211\u5728).+?(?:\u6587\u4ef6|\u76ee\u5f55|\u9879\u76ee).+?(?:\u770b\u5230|\u53d1\u73b0))",
    re.I,
)
_ACTION_REQUEST_HINT_RE = re.compile(
    r"(?:\u5e2e\u6211|\u7ed9\u6211|\u66ff\u6211|\u8bf7|\u9ebb\u70e6|\u53bb|\u6253\u5f00|\u67e5\u770b|\u8bfb\u53d6|\u68c0\u67e5|\u641c\u7d22|\u67e5\u627e|\u5217\u51fa|\u4fee\u6539|\u66f4\u65b0|\u5220\u9664|\u91cd\u542f|\u5173\u95ed|\u542f\u52a8|\u65b0\u5efa|\u521b\u5efa|\u8fd0\u884c|\u6267\u884c|\u5b89\u88c5|\u63d0\u4ea4|\u63a8\u9001|\u6062\u590d|\u56de\u9000|\u56de\u6eda|\u5bfc\u51fa|\u79fb\u52a8|\u590d\u5236|\u4fdd\u5b58|\u6574\u7406|\u751f\u6210|\u7ed1\u5b9a|read|open|check|inspect|search|list|modify|update|delete|restart|run|execute|install|commit|push|restore|rollback|export|move|copy|save)",
    re.I,
)
_COMPLETION_CLAIM_RE = re.compile(
    r"(?:^|[\s\uff0c,\u3002\uff1b;])(?:i(?:'ve| have)?|i|already|just|\u6211(?:\u5df2(?:\u7ecf)?)?|\u5df2\u7ecf|\u5df2|\u521a\u521a|\u521a\u624d)?(?:\u5e2e\u4f60|\u66ff\u4f60|\u4e3a\u4f60|\u628a)?"
    r"(?:\u5b8c\u6210(?:\u4e86)?|\u5904\u7406(?:\u597d\u4e86|\u5b8c\u4e86)?|\u6539(?:\u597d\u4e86|\u5b8c\u4e86)?|\u4fee(?:\u597d\u4e86|\u590d\u4e86)?|\u66f4\u65b0(?:\u597d\u4e86|\u5b8c\u4e86)?|\u5220\u9664(?:\u4e86)?|\u91cd\u542f(?:\u597d\u4e86)?|\u6253\u5f00(?:\u4e86)?|\u5173\u95ed(?:\u4e86)?|\u5207\u6362(?:\u597d\u4e86)?|\u8fd0\u884c(?:\u4e86)?|\u6267\u884c(?:\u4e86)?|\u521b\u5efa(?:\u597d\u4e86|\u5b8c\u6210)?|\u65b0\u5efa(?:\u597d\u4e86|\u5b8c\u6210)?|\u5b89\u88c5(?:\u597d\u4e86)?|\u63d0\u4ea4(?:\u4e86)?|\u63a8\u9001(?:\u4e86)?|\u6062\u590d(?:\u4e86)?|\u56de\u9000(?:\u4e86)?|\u56de\u6eda(?:\u4e86)?|\u4fdd\u5b58(?:\u4e86)?|\u5bfc\u51fa(?:\u4e86)?|\u6574\u7406(?:\u597d\u4e86)?|\u751f\u6210(?:\u597d\u4e86)?|\u7ed1\u5b9a(?:\u597d\u4e86)?|done|completed|updated|restarted|fixed|created|deleted|saved)",
    re.I,
)


def _get_last_user_message(history: list) -> str:
    for item in reversed(history or []):
        if isinstance(item, dict) and item.get("role") == "user":
            return str(item.get("content") or "")
    return ""


def _maybe_de_listify_for_chat(text: str, *, history: list) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return cleaned

    last_user = _get_last_user_message(history)
    if last_user and _LIST_REQUEST_HINT_RE.search(last_user):
        return cleaned

    lines = cleaned.splitlines()
    bullet_idxs = [i for i, line in enumerate(lines) if _BULLET_LINE_RE.match(line)]
    if len(bullet_idxs) < 3:
        return cleaned

    non_empty = [ln for ln in lines if ln.strip()]
    bullet_like = [ln for ln in non_empty if _BULLET_LINE_RE.match(ln)]
    if not non_empty or (len(bullet_like) / max(1, len(non_empty))) < 0.55:
        return cleaned

    items: list[str] = []
    for ln in non_empty:
        ln2 = _BULLET_LINE_RE.sub("", ln).strip()
        if ln2:
            items.append(ln2)
    if len(items) < 2:
        return cleaned

    merged = "；".join(items)
    if len(merged) <= 220:
        return merged
    if len(merged) <= 520:
        return "；\n".join(items)
    return "\n".join(items)


def clean_reply_for_user(response: str, *, strip_markdown) -> str:
    text = str(response or "")
    try:
        text = _clean_visible_reply_text(text)
    except Exception:
        try:
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I).strip()
        except Exception:
            text = str(response or "")
    if callable(strip_markdown):
        text = strip_markdown(text)
    return text


def apply_pre_reply_hygiene(
    response: str,
    history: list,
    *,
    debug_write=None,
) -> str:
    text = str(response or "")
    try:
        text, pre_cleaned = l1_hygiene_clean(text, history)
        if pre_cleaned and callable(debug_write):
            debug_write("l1_hygiene_pre_reply", {"removed": pre_cleaned})
    except Exception:
        pass
    return text


def prepare_reply_for_user(
    response: str,
    history: list,
    *,
    strip_markdown,
    debug_write=None,
) -> str:
    text = clean_reply_for_user(response, strip_markdown=strip_markdown)
    text = _maybe_de_listify_for_chat(text, history=history)
    return apply_pre_reply_hygiene(text, history, debug_write=debug_write)


def _build_unverified_local_inspection_reply() -> str:
    return (
        "这一轮我还没有实际调用读取文件或目录的工具，所以不能直接说我已经看过本地内容。"
        "\n\n刚才那段带本地文件或目录结论的答复不可靠。"
        "\n\n如果要确认具体的本地文件、目录、代码或配置内容，我需要先真实读取相关目标，再回来给你总结。"
    )


def _build_unverified_action_completion_reply() -> str:
    return (
        "这一轮我还没有实际执行任何工具，所以刚才那句“已完成/已处理”不可靠。"
        "\n\n如果这件事需要我动文件、执行命令、读取本地内容或操作应用，我必须先真实发起对应工具调用，才能把结果算作完成。"
    )


def classify_missing_tool_execution(
    text: str,
    *,
    user_input: str = "",
    tool_used: str = "",
    stream_had_output: bool = False,
) -> dict:
    cleaned = str(text or "").strip()
    if tool_used or not stream_had_output or not cleaned:
        return {}
    lead = cleaned[:260]
    has_evidence = bool(_LOCAL_FILE_EVIDENCE_RE.search(cleaned))
    has_claim = bool(_LOCAL_INSPECTION_LEAD_RE.search(lead) or _LOCAL_INSPECTION_FINDING_RE.search(cleaned))
    if has_evidence and has_claim:
        return {
            "reason": "local_inspection_without_tool",
            "summary": "claimed local inspection without a real read/list tool result",
        }
    if user_input and _ACTION_REQUEST_HINT_RE.search(str(user_input or "")) and _COMPLETION_CLAIM_RE.search(cleaned):
        return {
            "reason": "completion_without_tool",
            "summary": _summarize_tool_response_text(cleaned) or "claimed completion without a real tool result",
        }
    if _looks_like_tool_preamble(cleaned):
        return {
            "reason": "preamble_without_tool",
            "summary": _summarize_tool_response_text(cleaned),
        }
    return {}


def _rewrite_unverified_missing_execution_reply(
    text: str,
    *,
    user_input: str = "",
    tool_used: str = "",
    stream_had_output: bool = False,
) -> str:
    cleaned = str(text or "").strip()
    gap = classify_missing_tool_execution(
        cleaned,
        user_input=user_input,
        tool_used=tool_used,
        stream_had_output=stream_had_output,
    )
    if not gap:
        return cleaned
    if gap.get("reason") == "local_inspection_without_tool":
        return _build_unverified_local_inspection_reply()
    if gap.get("reason") == "completion_without_tool":
        return _build_unverified_action_completion_reply()
    return cleaned


def finalize_tool_call_reply(
    response: str,
    *,
    history: list,
    strip_markdown,
    ensure_tool_call_failure_reply,
    user_input: str = "",
    tool_used: str = "",
    tool_success: bool | None = None,
    tool_response: str = "",
    action_summary: str = "",
    run_meta: dict | None = None,
    stream_had_output: bool = False,
    debug_write=None,
) -> str:
    text = clean_reply_for_user(response, strip_markdown=strip_markdown)
    text = _maybe_de_listify_for_chat(text, history=history)
    missing_tool_gap = classify_missing_tool_execution(
        text,
        user_input=user_input,
        tool_used=tool_used,
        stream_had_output=stream_had_output,
    )
    if tool_used:
        text = _finalize_tool_reply(
            text,
            success=bool(tool_success) if tool_success is not None else True,
            action_summary=action_summary,
            tool_response=tool_response,
            run_meta=run_meta,
        )
    text = ensure_tool_call_failure_reply(
        text,
        tool_used=tool_used,
        tool_success=tool_success,
        tool_response=tool_response,
        action_summary=action_summary,
        run_meta=run_meta,
    )
    if missing_tool_gap.get("reason") == "local_inspection_without_tool":
        text = _build_unverified_local_inspection_reply()
    elif missing_tool_gap.get("reason") == "completion_without_tool":
        text = _build_unverified_action_completion_reply()
    elif not tool_used and stream_had_output and _looks_like_tool_preamble(text):
        text = ensure_tool_call_failure_reply(
            text,
            tool_used="tool_call",
            tool_success=False,
            tool_response=tool_response or text,
            action_summary=action_summary or _summarize_tool_response_text(text),
            run_meta=run_meta,
        )
    text = _rewrite_unverified_missing_execution_reply(
        text,
        user_input=user_input,
        tool_used=tool_used,
        stream_had_output=stream_had_output,
    )
    return apply_pre_reply_hygiene(text, history, debug_write=debug_write)
