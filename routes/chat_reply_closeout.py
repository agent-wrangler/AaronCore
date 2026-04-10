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
_BULLET_LINE_RE = re.compile(r"^\s*(?:[-*•]\s+|[0-9]{1,2}[.)\u3001]\s+)")
_HEADING_PREFIX_RE = re.compile(r"^\s*#{1,3}\s*")
_SENTENCE_END_RE = re.compile(r"[。！？!?]$")
_LIGHT_STRUCTURE_LABEL_RE = re.compile(
    r"(?:\u7c7b\u578b|\u51e0\u79cd|\u65b9\u5411|\u573a\u666f|\u9002\u5408|\u793e\u533a|\u65b9\u6848|\u5efa\u8bae|\u9009\u62e9)$"
)
_CHAT_BLOCK_SPLIT_RE = re.compile(r"\n\s*\n+")
_EXPLICIT_STRUCTURE_LABEL_RE = re.compile(
    r"(?:\u6b65\u9aa4|\u6e05\u5355|\u5217\u8868|\u5bf9\u6bd4|\u5982\u4e0b|\u5206\u4e3a|\u5206\u6210|\u5305\u62ec|\u8ba1\u5212)$"
)

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
_LOCAL_INSPECTION_RESULT_RE = re.compile(
    r"(?:\u770b\u5230|\u770b\u89c1|\u53d1\u73b0|\u786e\u8ba4|\u7ee7\u7eed\u5728|\u8fd8\u5728|\u4e0d\u5728|\u5df2\u4e0d\u5728|"
    r"\u627e\u5230|\u6ca1\u627e\u5230|\u5b58\u5728|\u4e0d\u5b58\u5728|\u88ab\u5220\u9664|\u5220\u6389\u4e86|\u5220\u9664\u4e86|"
    r"\u91cc\u9762\u6709|\u5305\u542b|\u6709.+?\u6587\u4ef6|"
    r"\bfound\b|\bsaw\b|\bconfirmed\b|\bexists?\b|\bdeleted\b|\bmissing\b|\bnot found\b)",
    re.I,
)
_LOCAL_INSPECTION_PLAN_RE = re.compile(
    r"(?:\u73b0\u5728|\u8fd9\u6b21|\u5148|\u5148\u53bb|\u91cd\u65b0|\u91cd\u65b0\u6267\u884c|\u63a5\u4e0b\u6765|\u8ba9\u6211|\u6211\u6765|"
    r"let me|i(?:'m| am)? going to|i will|next)\s*.*?(?:\u67e5\u770b|\u68c0\u67e5|\u8bfb\u53d6|\u641c\u7d22|\u67e5\u627e|\u770b\u770b|check|inspect|read|search|find)",
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
_LOCAL_FILE_TOOL_NAMES = {
    "file_copy",
    "file_delete",
    "file_move",
    "folder_explore",
    "read_file",
    "list_files",
    "write_file",
}


def _get_last_user_message(history: list) -> str:
    for item in reversed(history or []):
        if isinstance(item, dict) and item.get("role") == "user":
            return str(item.get("content") or "")
    return ""


def _resolve_user_input(history: list, user_input: str = "") -> str:
    return str(user_input or _get_last_user_message(history) or "")


def _latest_assistant_tool_results(history: list | None) -> list[dict]:
    for item in reversed(history or []):
        if not isinstance(item, dict):
            continue
        if str(item.get("role") or "").strip().lower() not in {"assistant", "nova"}:
            continue
        process = item.get("process") if isinstance(item.get("process"), dict) else {}
        tool_results = process.get("tool_results") if isinstance(process.get("tool_results"), list) else []
        normalized = [row for row in tool_results if isinstance(row, dict) and str(row.get("name") or "").strip()]
        if normalized:
            return normalized
    return []


def _has_recent_local_tool_success(history: list | None, *, user_input: str = "") -> bool:
    requested = str(user_input or "").strip()
    if requested and (_ACTION_REQUEST_HINT_RE.search(requested) or _LOCAL_INSPECTION_LEAD_RE.search(requested)):
        return False
    for item in _latest_assistant_tool_results(history):
        if str(item.get("name") or "").strip() not in _LOCAL_FILE_TOOL_NAMES:
            continue
        if item.get("success") is True:
            return True
    return False


def _strip_list_marker(line: str) -> str:
    return _BULLET_LINE_RE.sub("", str(line or "")).strip().rstrip("；;。.!?！？")


def _ensure_sentence(text: str) -> str:
    sentence = str(text or "").strip()
    if not sentence:
        return ""
    if not _SENTENCE_END_RE.search(sentence):
        sentence += "。"
    return sentence


def _looks_like_light_heading(line: str) -> bool:
    text = _HEADING_PREFIX_RE.sub("", str(line or "")).strip()
    if not text or len(text) > 18:
        return False
    if any(token in text for token in ("http://", "https://", "`", "|")):
        return False
    if any(punc in text for punc in "，,；;。.!?！？"):
        return text.endswith(("：", ":"))
    return bool(_LIGHT_STRUCTURE_LABEL_RE.search(text))


def _heading_text(line: str) -> str:
    return _HEADING_PREFIX_RE.sub("", str(line or "")).strip()


def _looks_like_markdown_heading(line: str) -> bool:
    text = str(line or "").strip()
    if not text or not _HEADING_PREFIX_RE.match(text):
        return False
    label = _heading_text(text)
    return bool(label) and len(label) <= 20


def _looks_like_explicit_structure_label(text: str) -> bool:
    label = _heading_text(str(text or "")).strip().rstrip("：: ")
    if not label:
        return False
    return bool(_EXPLICIT_STRUCTURE_LABEL_RE.search(label))


def _flatten_chat_block(
    lines: list[str],
    *,
    heading: str = "",
) -> str:
    normalized = [str(line or "").strip() for line in (lines or []) if str(line or "").strip()]
    if not normalized:
        return ""

    bullet_idxs = [index for index, line in enumerate(normalized) if _BULLET_LINE_RE.match(line)]
    if bullet_idxs:
        first_list_index = bullet_idxs[0]
        prefix_lines = normalized[:first_list_index]
        list_lines = normalized[first_list_index:]
        if len(prefix_lines) > 2 or any(not _BULLET_LINE_RE.match(line) for line in list_lines):
            return ""

        items: list[str] = []
        for line in list_lines:
            item = _strip_list_marker(line)
            if (
                not item
                or len(item) > 64
                or item.endswith(("：", ":"))
                or any(token in item for token in ("```", "`", "http://", "https://", "|"))
            ):
                return ""
            items.append(item)

        if len(items) < 2 or len(items) > 4:
            return ""

        context_sentences: list[str] = []
        lead_label = ""
        if heading:
            heading_label = _heading_text(heading).rstrip("：: ")
            if heading_label and not _looks_like_explicit_structure_label(heading_label):
                lead_label = heading_label

        for line in prefix_lines:
            text = _heading_text(line)
            if not text:
                continue
            if _looks_like_explicit_structure_label(text):
                return ""
            if text.endswith(("：", ":")) or _looks_like_light_heading(text):
                lead_label = text.rstrip("：: ")
            else:
                context_sentences.append(_ensure_sentence(text))

        list_sentence = "；".join(items) + "。"
        if lead_label:
            list_sentence = f"{lead_label}：{list_sentence}"
        return f"{''.join(context_sentences)}{list_sentence}".strip()

    if len(normalized) == 1 and heading:
        heading_label = _heading_text(heading).rstrip("：: ")
        if heading_label and not _looks_like_explicit_structure_label(heading_label):
            body = normalized[0].rstrip("；。!?！？")
            return f"{heading_label}：{body}。"

    return ""


def _flatten_light_chat_sections(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned or any(token in cleaned for token in ("```", "http://", "https://", "|")):
        return cleaned

    blocks = [block for block in _CHAT_BLOCK_SPLIT_RE.split(cleaned) if block and block.strip()]
    if len(blocks) < 2 or len(blocks) > 8:
        return cleaned

    changed = False
    rebuilt: list[str] = []
    pending_heading = ""

    for raw_block in blocks:
        lines = [line.strip() for line in str(raw_block or "").splitlines() if line.strip()]
        if not lines:
            continue

        if len(lines) == 1 and _looks_like_markdown_heading(lines[0]):
            if pending_heading:
                rebuilt.append(_heading_text(pending_heading))
            pending_heading = lines[0]
            changed = True
            continue

        block_heading = ""
        block_lines = lines
        if _looks_like_markdown_heading(lines[0]):
            block_heading = lines[0]
            block_lines = lines[1:]
            changed = True

        heading_for_block = pending_heading or block_heading
        pending_heading = ""

        flattened = _flatten_chat_block(block_lines, heading=heading_for_block)
        if flattened:
            rebuilt.append(flattened)
            changed = True
            continue

        if heading_for_block:
            heading_label = _heading_text(heading_for_block)
            if heading_label and not _looks_like_explicit_structure_label(heading_label):
                if block_lines:
                    rebuilt.append(f"{heading_label}：{' '.join(block_lines)}")
                    changed = True
                    continue
                rebuilt.append(heading_label)
                changed = True
                continue

        rebuilt.append("\n".join(lines))

    if pending_heading:
        rebuilt.append(_heading_text(pending_heading))

    merged = "\n\n".join(part.strip() for part in rebuilt if str(part or "").strip()).strip()
    if not merged or not changed or len(merged) > 560:
        return cleaned
    return merged


def _flatten_light_chat_structure(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned or any(token in cleaned for token in ("```", "http://", "https://", "|")):
        return cleaned

    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if len(lines) < 3 or len(lines) > 9:
        return cleaned

    bullet_idxs = [index for index, line in enumerate(lines) if _BULLET_LINE_RE.match(line)]
    if len(bullet_idxs) < 2 or len(bullet_idxs) > 4:
        return cleaned

    first_list_index = bullet_idxs[0]
    prefix_lines = lines[:first_list_index]
    list_lines = lines[first_list_index:]
    if len(prefix_lines) > 3 or any(not _BULLET_LINE_RE.match(line) for line in list_lines):
        return cleaned

    intro_parts: list[str] = []
    label_parts: list[str] = []
    for line in prefix_lines:
        normalized = _HEADING_PREFIX_RE.sub("", line).strip()
        if not normalized:
            continue
        if len(normalized) > 32:
            intro_parts.append(_ensure_sentence(normalized))
        elif normalized.endswith(("：", ":")) or _looks_like_light_heading(normalized):
            label_parts.append(normalized.rstrip("：: "))
        else:
            intro_parts.append(_ensure_sentence(normalized))

    items: list[str] = []
    for line in list_lines:
        item = _strip_list_marker(line)
        if not item or len(item) > 48 or item.endswith(("：", ":")):
            return cleaned
        items.append(item)

    if len(items) < 2:
        return cleaned

    body = "；".join(items) + "。"
    if label_parts:
        body = f"{label_parts[-1]}：{body}"
    merged = f"{''.join(intro_parts)}{body}".strip()
    return merged if merged and len(merged) <= 260 else cleaned


def _maybe_de_listify_for_chat(text: str, *, history: list, user_input: str = "") -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return cleaned

    last_user = str(user_input or _get_last_user_message(history) or "")
    if last_user and _LIST_REQUEST_HINT_RE.search(last_user):
        return cleaned

    non_empty_lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if non_empty_lines:
        first_label = _heading_text(non_empty_lines[0]).strip().rstrip("：: ")
        explicit_bullets = sum(1 for line in non_empty_lines[1:] if _BULLET_LINE_RE.match(line))
        if first_label and _looks_like_explicit_structure_label(first_label) and explicit_bullets >= 2:
            return cleaned

    flattened = _flatten_light_chat_structure(cleaned)
    if flattened != cleaned:
        return flattened

    flattened = _flatten_light_chat_sections(cleaned)
    if flattened != cleaned:
        return flattened

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
        ln2 = _strip_list_marker(ln)
        if ln2:
            items.append(ln2)
    if len(items) < 2:
        return cleaned

    merged = "；".join(items)
    if len(merged) <= 220:
        return merged + "。"
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


def _clean_reply_preserving_requested_structure(
    response: str,
    *,
    strip_markdown,
) -> str:
    text = re.sub(r"<think>.*?</think>", "", str(response or ""), flags=re.S | re.I).strip()
    if callable(strip_markdown):
        text = strip_markdown(text)
    return text


def apply_pre_reply_hygiene(
    response: str,
    history: list,
    *,
    preserve_structure: bool = False,
    debug_write=None,
) -> str:
    text = str(response or "")
    if preserve_structure:
        return text
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
    user_input: str = "",
    debug_write=None,
) -> str:
    requested_format = _resolve_user_input(history, user_input)
    if requested_format and _LIST_REQUEST_HINT_RE.search(requested_format):
        text = _clean_reply_preserving_requested_structure(
            response,
            strip_markdown=strip_markdown,
        )
        return apply_pre_reply_hygiene(
            text,
            history,
            preserve_structure=True,
            debug_write=debug_write,
        )
    else:
        text = clean_reply_for_user(response, strip_markdown=strip_markdown)
        text = _maybe_de_listify_for_chat(text, history=history, user_input=requested_format)
    return apply_pre_reply_hygiene(text, history, debug_write=debug_write)


def classify_missing_tool_execution(
    text: str,
    *,
    history: list | None = None,
    user_input: str = "",
    tool_used: str = "",
    stream_had_output: bool = False,
) -> dict:
    cleaned = str(text or "").strip()
    if tool_used or not stream_had_output or not cleaned:
        return {}
    requested_text = str(user_input or "").strip()
    requested_is_action = bool(_ACTION_REQUEST_HINT_RE.search(requested_text)) if requested_text else False
    lead = cleaned[:260]
    has_evidence = bool(_LOCAL_FILE_EVIDENCE_RE.search(cleaned))
    has_lead = bool(_LOCAL_INSPECTION_LEAD_RE.search(lead))
    has_finding = bool(_LOCAL_INSPECTION_FINDING_RE.search(cleaned))
    has_result = bool(_LOCAL_INSPECTION_RESULT_RE.search(cleaned))
    has_completion_claim = bool(_COMPLETION_CLAIM_RE.search(cleaned))
    looks_like_plan = bool(_LOCAL_INSPECTION_PLAN_RE.search(cleaned))
    has_claim = bool(has_finding or (has_lead and (has_result or has_completion_claim)))
    if has_evidence and looks_like_plan and not has_claim:
        return {}
    if has_evidence and has_claim:
        if _has_recent_local_tool_success(history, user_input=user_input):
            return {}
        return {
            "reason": "local_inspection_without_tool",
            "summary": "claimed local inspection without a real read/list tool result",
        }
    if requested_is_action and has_completion_claim:
        return {
            "reason": "completion_without_tool",
            "summary": _summarize_tool_response_text(cleaned) or "claimed completion without a real tool result",
        }
    if _looks_like_tool_preamble(cleaned):
        if requested_text and not requested_is_action:
            return {}
        return {
            "reason": "preamble_without_tool",
            "summary": _summarize_tool_response_text(cleaned),
        }
    return {}


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
    requested_format = _resolve_user_input(history, user_input)
    if requested_format and _LIST_REQUEST_HINT_RE.search(requested_format):
        text = _clean_reply_preserving_requested_structure(
            response,
            strip_markdown=strip_markdown,
        )
    else:
        text = clean_reply_for_user(response, strip_markdown=strip_markdown)
        text = _maybe_de_listify_for_chat(text, history=history, user_input=requested_format)
    missing_tool_gap = classify_missing_tool_execution(
        text,
        history=history,
        user_input=requested_format,
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
    if not tool_used and stream_had_output and missing_tool_gap.get("reason") == "preamble_without_tool":
        text = ensure_tool_call_failure_reply(
            text,
            tool_used="tool_call",
            tool_success=False,
            tool_response=tool_response or text,
            action_summary=action_summary or _summarize_tool_response_text(text),
            run_meta=run_meta,
        )
    return apply_pre_reply_hygiene(
        text,
        history,
        preserve_structure=bool(requested_format and _LIST_REQUEST_HINT_RE.search(requested_format)),
        debug_write=debug_write,
    )
