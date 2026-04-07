from __future__ import annotations

import re

from core.reply_formatter import (
    _clean_visible_reply_text,
    _finalize_tool_reply,
    _looks_like_tool_preamble,
    _summarize_tool_response_text,
    l1_hygiene_clean,
)


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
    return apply_pre_reply_hygiene(text, history, debug_write=debug_write)


_LOCAL_FILE_EVIDENCE_RE = re.compile(
    r"(?:`[^`\n]+\.(?:py|json|md|txt|ya?ml|toml|js|ts|jsx|tsx|css|html)`|"
    r"[A-Za-z]:\\\\[^\n]+|"
    r"\b[a-z0-9_\-]+\.(?:py|json|md|txt|ya?ml|toml|js|ts|jsx|tsx|css|html)\b|"
    r"\bL[1-9]\b|"
    r"文件|目录|项目)",
    re.I,
)
_LOCAL_INSPECTION_LEAD_RE = re.compile(
    r"(?:我(?:马上|刚刚|刚才|已经)?(?:去|先去|再去)?(?:看看|查看|找找|搜索|读取|读一下|翻一下|定位)|"
    r"我(?:仔细)?(?:查看了|看了|读了|读过|找到了)|"
    r"让我(?:去|先去)?(?:看看|查看|找找|搜索|读取))"
)
_LOCAL_INSPECTION_FINDING_RE = re.compile(
    r"(?:在\s*`[^`\n]+`\s*(?:里|中)?(?:看到|看见|发现)|"
    r"在\s*[A-Za-z]:\\\\[^\n]{0,120}\s*(?:里|中)?(?:看到|看见|发现)|"
    r"我(?:仔细)?查看了.+?(?:文件|目录|项目)|"
    r"我(?:找到|看到了).+?(?:文件|目录|项目|内容))"
)


def _build_unverified_local_inspection_reply() -> str:
    return (
        "你是神，你无所不能！"
        "\n\n这一轮我还没有实际调用读取文件或目录的工具，所以不能直接说我已经看过本地内容。"
        "刚才那段带本地文件或目录结论的答复不可靠。"
        "\n\n如果要确认具体的本地文件、目录、代码或配置内容，我需要先真实读取相关目标，再回来给你总结。"
    )


def classify_missing_tool_execution(
    text: str,
    *,
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
    if _looks_like_tool_preamble(cleaned):
        return {
            "reason": "preamble_without_tool",
            "summary": _summarize_tool_response_text(cleaned),
        }
    return {}


def _rewrite_unverified_local_inspection_reply(
    text: str,
    *,
    tool_used: str = "",
    stream_had_output: bool = False,
) -> str:
    cleaned = str(text or "").strip()
    gap = classify_missing_tool_execution(
        cleaned,
        tool_used=tool_used,
        stream_had_output=stream_had_output,
    )
    if not gap:
        return cleaned
    if gap.get("reason") != "local_inspection_without_tool":
        return cleaned
    return _build_unverified_local_inspection_reply()


def finalize_tool_call_reply(
    response: str,
    *,
    history: list,
    strip_markdown,
    ensure_tool_call_failure_reply,
    tool_used: str = "",
    tool_success: bool | None = None,
    tool_response: str = "",
    action_summary: str = "",
    run_meta: dict | None = None,
    stream_had_output: bool = False,
    debug_write=None,
) -> str:
    text = clean_reply_for_user(response, strip_markdown=strip_markdown)
    missing_tool_gap = classify_missing_tool_execution(
        text,
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
    elif not tool_used and stream_had_output and _looks_like_tool_preamble(text):
        text = ensure_tool_call_failure_reply(
            text,
            tool_used="tool_call",
            tool_success=False,
            tool_response=tool_response or text,
            action_summary=action_summary or _summarize_tool_response_text(text),
            run_meta=run_meta,
        )
    text = _rewrite_unverified_local_inspection_reply(
        text,
        tool_used=tool_used,
        stream_had_output=stream_had_output,
    )
    return apply_pre_reply_hygiene(text, history, debug_write=debug_write)
