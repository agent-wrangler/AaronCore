"""Visible-reply text cleanup helpers for post-tool rendering."""

from decision import reply_hygiene as _reply_hygiene


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

    restart_prefixes = (
        "好的，我明白了",
        "明白了，我",
        "明白了！",
        "抱歉抱歉",
        "啊！抱歉抱歉",
        "让我重新整理一下",
        "我重新整理一下",
        "让我重新说一遍",
        "我重新总结一下",
        "那我重新",
        "我再重新",
    )

    paragraphs = [part.strip() for part in re_mod.split(r"\n\s*\n", raw) if part.strip()]
    for idx in range(1, len(paragraphs)):
        prefix_text = "\n\n".join(paragraphs[:idx]).strip()
        current = paragraphs[idx]
        if len(prefix_text) < 60:
            continue
        if not any(current.startswith(prefix) for prefix in restart_prefixes):
            continue
        if not (
            re_mod.search(r"[。！？!?]\s*$", prefix_text)
            or "\n- " in prefix_text
            or "\n1." in prefix_text
            or "**" in prefix_text
            or len(prefix_text) > 220
        ):
            continue
        return prefix_text, [current[:40]]

    inline_restart_re = (
        r"([。！？!?])\s*"
        r"(好的，我明白了|明白了，我|明白了！|抱歉抱歉|啊！抱歉抱歉|"
        r"让我重新整理一下|我重新整理一下|让我重新说一遍|我重新总结一下|那我重新|我再重新)"
    )
    for inline_match in re_mod.finditer(inline_restart_re, raw):
        if inline_match.start(2) <= 30:
            continue
        trimmed = raw[: inline_match.start(2)].rstrip()
        if trimmed:
            return trimmed, [inline_match.group(2)]

    return raw, []


def prefer_tool_grounded_tail(text: str, *, re_mod) -> str:
    raw = str(text or "").strip()
    if not raw or len(raw) < 80:
        return raw

    grounded_prefixes = (
        "这一步已经完成",
        "现在我看到了",
        "我现在看到了",
        "现在我看到",
        "我现在看到",
        "我查到了",
        "根据刚才",
        "从刚才看到",
        "从工具结果看",
        "结合刚才查到的",
        "按刚才查到的",
        "我刚看了",
    )
    stale_prefix_markers = (
        "这样清楚了吗",
        "需要我详细说明",
        "需要我进一步展开",
        "需要我详细解释",
        "**核心建议**",
        "**建议方向**",
        "**当前问题**",
        "**核心问题**",
    )

    candidate = ""
    paragraphs = [part.strip() for part in re_mod.split(r"\n\s*\n", raw) if part.strip()]
    for idx in range(1, len(paragraphs)):
        prefix = "\n\n".join(paragraphs[:idx]).strip()
        current = paragraphs[idx]
        if len(prefix) < 40:
            continue
        if not any(current.startswith(marker) for marker in grounded_prefixes):
            continue
        if "需要我" not in prefix and not any(marker in prefix for marker in stale_prefix_markers):
            continue
        candidate = "\n\n".join(paragraphs[idx:]).strip()

    inline_grounded_re = (
        r"([。！？!?])\s*"
        r"(这一步已经完成|现在我看到了|我现在看到了|现在我看到|我现在看到|我查到了|根据刚才|"
        r"从刚才看到|从工具结果看|结合刚才查到的|按刚才查到的|我刚看了)"
    )
    for inline_match in re_mod.finditer(inline_grounded_re, raw):
        if inline_match.start(2) <= 30:
            continue
        prefix = raw[: inline_match.start(2)].strip()
        if "需要我" not in prefix and not any(marker in prefix for marker in stale_prefix_markers):
            continue
        candidate = raw[inline_match.start(2) :].strip()

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
    cleaned = re_mod.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
