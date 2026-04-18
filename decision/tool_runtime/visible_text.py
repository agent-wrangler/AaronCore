"""Visible-reply text cleanup helpers for post-tool rendering."""

from decision import reply_hygiene as _reply_hygiene


_RESTART_TRANSITION_RE = (
    r"^(?:"
    r"(?:ok(?:ay)?[,\s]*)?(?:i\s+)?(?:understand|got it)"
    r"|(?:\u597d\u7684[,\uff0c]?\s*)?(?:\u6211)?(?:\u660e\u767d\u4e86|\u61c2\u4e86|\u7406\u89e3\u4e86)"
    r"|(?:\u554a[!！]?\s*)?(?:\u62b1\u6b49|\u4e0d\u597d\u610f\u601d|sorry)(?:\s*(?:\u62b1\u6b49|sorry))?"
    r"|(?:\u90a3\u6211|\u6211|\u8ba9\u6211)(?:\u518d)?\u91cd\u65b0(?:\u6574\u7406|\u8bf4(?:\u4e00\u904d)?|\u8bb2(?:\u4e00\u904d)?|\u603b\u7ed3)?"
    r"|(?:let me|i(?:'ll| will))\s+(?:restart|restate|rephrase|reorganize|summarize(?:\s+again)?|say\s+(?:that\s+)?again)"
    r")"
)
_GROUNDED_TAIL_RE = (
    r"^(?:"
    r"\u8fd9\u4e00\u6b65\u5df2\u7ecf\u5b8c\u6210"
    r"|(?:\u73b0\u5728|\u521a\u624d)?\u6211(?:\u73b0\u5728)?(?:\u770b\u5230|\u770b\u5230\u4e86|\u67e5\u5230|\u67e5\u5230\u4e86)"
    r"|\u6211\u521a\u770b\u4e86"
    r"|(?:\u6839\u636e|\u7ed3\u5408|\u6309|\u4ece)(?:\u521a\u624d|\u5de5\u5177\u7ed3\u679c)"
    r"|(?:now\s+i\s+(?:can\s+)?see|i\s+(?:can\s+)?see|i\s+found|based\s+on\s+(?:the\s+)?tool\s+result)"
    r")"
)
_STALE_PREFIX_RE = (
    r"(?:"
    r"\u9700\u8981\u6211"
    r"|need\s+me"
    r"|\u8fd9\u6837[^\n]{0,24}(?:\u6e05\u695a|\u660e\u767d|\u7b80\u6d01|\u591f)[^\n]{0,12}(?:\u5417|[?？])"
    r"|(?:clear\s+enough|make\s+sense)[^\n]{0,12}(?:[?？]|$)"
    r"|\*\*[^*\n]{0,16}(?:\u5efa\u8bae|\u95ee\u9898|advice|issue|problem)[^*\n]{0,16}\*\*"
    r")"
)


def _split_nonempty_paragraphs(text: str, *, re_mod) -> list[str]:
    return [part.strip() for part in re_mod.split(r"\n\s*\n", str(text or "")) if part.strip()]


def _has_restart_boundary(prefix_text: str, *, re_mod) -> bool:
    prefix = str(prefix_text or "").strip()
    if not prefix:
        return False
    return bool(
        re_mod.search(r"[\u3002\uff01\uff1f!?]\s*$", prefix)
        or "\n- " in prefix
        or "\n1." in prefix
        or "**" in prefix
        or len(prefix) > 220
    )


def _looks_like_restart_transition(text: str, *, re_mod) -> bool:
    return bool(re_mod.search(_RESTART_TRANSITION_RE, str(text or "").strip(), flags=re_mod.I))


def _looks_like_grounded_transition(text: str, *, re_mod) -> bool:
    return bool(re_mod.search(_GROUNDED_TAIL_RE, str(text or "").strip(), flags=re_mod.I))


def _prefix_looks_like_stale_scaffold(text: str, *, re_mod) -> bool:
    return bool(re_mod.search(_STALE_PREFIX_RE, str(text or ""), flags=re_mod.I))


def _iter_inline_transition_starts(text: str, *, re_mod):
    raw = str(text or "")
    for boundary in re_mod.finditer(r"[\u3002\uff01\uff1f!?]\s*", raw):
        tail_start = boundary.end()
        if tail_start <= 30:
            continue
        yield tail_start, raw[tail_start:].lstrip()


def prefer_post_think_answer_tail(text: str, *, re_mod) -> str:
    raw = str(text or "").strip()
    if not raw or "<think" not in raw.lower():
        return raw

    matches = list(re_mod.finditer(r"<think>.*?(?:</think>|$)", raw, flags=re_mod.S | re_mod.I))
    if not matches:
        return raw

    prefix = raw[: matches[0].start()].strip()
    suffix = raw[matches[-1].end() :].strip()
    if prefix and suffix:
        return suffix
    return raw


def strip_think_markup(text: str, *, re_mod) -> str:
    return re_mod.sub(r"<think>.*?(?:</think>|$)\s*", "", str(text or ""), flags=re_mod.S | re_mod.I).strip()


def strip_legacy_tool_markup(
    text: str,
    *,
    legacy_tool_block_re,
    legacy_minimax_tool_re,
    legacy_json_tool_re,
    re_mod,
) -> str:
    cleaned = str(text or "")
    if not cleaned:
        return ""
    cleaned = legacy_tool_block_re.sub("", cleaned)
    cleaned = legacy_minimax_tool_re.sub("", cleaned)
    cleaned = legacy_json_tool_re.sub("", cleaned)
    cleaned = re_mod.sub(r"<\s*function_calls\s*>.*?<\s*/\s*function_calls\s*>", "", cleaned, flags=re_mod.I | re_mod.S)
    cleaned = re_mod.sub(r"<\s*invoke\b[^>]*>.*?<\s*/\s*invoke\s*>", "", cleaned, flags=re_mod.I | re_mod.S)
    cleaned = cleaned.replace("DSML", "")
    return cleaned


def strip_mid_reply_restart(text: str, *, re_mod) -> tuple[str, list[str]]:
    raw = str(text or "").strip()
    if not raw or len(raw) < 80:
        return raw, []

    paragraphs = _split_nonempty_paragraphs(raw, re_mod=re_mod)
    for idx in range(1, len(paragraphs)):
        prefix_text = "\n\n".join(paragraphs[:idx]).strip()
        current = paragraphs[idx]
        if len(prefix_text) < 60:
            continue
        if not _looks_like_restart_transition(current, re_mod=re_mod):
            continue
        if not _has_restart_boundary(prefix_text, re_mod=re_mod):
            continue
        return prefix_text, [current[:40]]

    for tail_start, tail in _iter_inline_transition_starts(raw, re_mod=re_mod):
        if not _looks_like_restart_transition(tail, re_mod=re_mod):
            continue
        trimmed = raw[:tail_start].rstrip()
        if trimmed:
            return trimmed, [tail[:40]]

    return raw, []


def prefer_tool_grounded_tail(text: str, *, re_mod) -> str:
    raw = str(text or "").strip()
    if not raw or len(raw) < 80:
        return raw

    candidate = ""
    paragraphs = _split_nonempty_paragraphs(raw, re_mod=re_mod)
    for idx in range(1, len(paragraphs)):
        prefix = "\n\n".join(paragraphs[:idx]).strip()
        current = paragraphs[idx]
        if len(prefix) < 40:
            continue
        if not _looks_like_grounded_transition(current, re_mod=re_mod):
            continue
        if not _prefix_looks_like_stale_scaffold(prefix, re_mod=re_mod):
            continue
        candidate = "\n\n".join(paragraphs[idx:]).strip()

    for tail_start, tail in _iter_inline_transition_starts(raw, re_mod=re_mod):
        if not _looks_like_grounded_transition(tail, re_mod=re_mod):
            continue
        prefix = raw[:tail_start].strip()
        if not _prefix_looks_like_stale_scaffold(prefix, re_mod=re_mod):
            continue
        candidate = raw[tail_start:].strip()

    return candidate or raw


def clean_visible_reply_text(
    text: str,
    *,
    prefer_post_think_answer_tail,
    strip_think_markup,
    strip_legacy_tool_markup,
    prefer_tool_grounded_tail,
    strip_mid_reply_restart,
    re_mod,
) -> str:
    cleaned = prefer_post_think_answer_tail(text)
    cleaned = strip_think_markup(cleaned)
    cleaned = strip_legacy_tool_markup(cleaned)
    cleaned = prefer_tool_grounded_tail(cleaned)
    cleaned, _ = strip_mid_reply_restart(cleaned)
    cleaned = _reply_hygiene.strip_chat_emphasis_markdown(cleaned, re_mod=re_mod)
    cleaned = _reply_hygiene.flatten_simple_chat_list(cleaned, re_mod=re_mod)
    cleaned = re_mod.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
