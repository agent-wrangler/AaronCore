"""Post-LLM tool handoff and mixed-output compatibility signals."""


def looks_like_tool_preamble(
    text: str,
    *,
    clean_visible_reply_text,
    contains_tool_handoff_phrase,
    re_mod,
) -> bool:
    visible = clean_visible_reply_text(text)
    if not visible or "```" in visible:
        return False

    lines = [line.strip(" -") for line in visible.replace("\r", "\n").splitlines() if line.strip()]
    if len(lines) > 4:
        return False
    if any(re_mod.match(r"^\d+\.", line) for line in lines):
        return False
    if any(line.startswith("|") and line.endswith("|") for line in lines):
        return False

    sentence_count = len([part for part in re_mod.split(r"[。！？?]\s*|\n+", visible) if part.strip()])
    if sentence_count > 4:
        return False

    answer_like_patterns = (
        r"\b\d+\s*(?:%|小时|分钟|秒|次)\b",
        r"https?://",
        r"[A-Za-z]:\\",
        r"(?:SQLite|Flask|Electron|LocalStorage)\s+\+",
        r"\b(?:A|B|C)\b\s*\|",
    )
    if any(re_mod.search(pattern, visible, flags=re_mod.I) for pattern in answer_like_patterns):
        return False

    return contains_tool_handoff_phrase(visible)


def contains_tool_handoff_phrase(text: str, *, clean_visible_reply_text, re_mod) -> bool:
    visible = clean_visible_reply_text(text)
    if not visible:
        return False

    def _normalize_segment(raw: str) -> str:
        segment = re_mod.sub(r"^[\s#>*`\-\u2014\u2013\d\.\)\(]+", "", str(raw or "")).strip()
        segment = re_mod.sub(r"^[^A-Za-z0-9\u4e00-\u9fff]+", "", segment).strip()
        return segment

    normalized = _normalize_segment(visible) or visible
    lowered = normalized.lower()
    sentence_candidates = []
    for part in re_mod.split(r"[。！？?]\s*|\n+", visible):
        candidate = _normalize_segment(part)
        if candidate:
            sentence_candidates.append(candidate)
    later_candidates = sentence_candidates[1:] if len(sentence_candidates) > 1 else []

    strong_preamble_prefixes = (
        "我来",
        "我先",
        "我帮你",
        "让我",
        "我看看",
        "我查",
        "我去",
        "先帮你",
        "先看",
        "先查",
        "稍等",
        "等我",
        "好我来",
        "好的我来",
        "那我来",
        "那我先",
    )
    weak_preamble_prefixes = (
        "好",
        "好吧",
        "行",
        "那我",
    )
    preamble_actions = (
        "看一下",
        "看下",
        "看看",
        "查一下",
        "查下",
        "梳理一下",
        "梳理下",
        "定位一下",
        "定位下",
        "检索一下",
        "检索下",
        "分析一下",
        "分析下",
        "处理一下",
        "处理下",
        "确认一下",
        "确认下",
        "整理一下",
        "整理下",
        "过一遍",
        "回忆一下",
        "看看记忆",
        "开始执行",
        "直接上代码",
        "一步到位",
        "先创建",
        "然后我",
        "逐个文件",
    )

    if any(normalized.startswith(prefix) for prefix in strong_preamble_prefixes):
        return True

    if any(
        any(candidate.startswith(prefix) for prefix in strong_preamble_prefixes)
        and any(action in candidate for action in preamble_actions)
        for candidate in later_candidates
    ):
        return True

    action_hit = any(action in normalized for action in preamble_actions)
    if not action_hit:
        english_prefixes = (
            "i will ",
            "i'll ",
            "let me ",
            "first, i will ",
            "first, i'll ",
            "i am going to ",
            "i'm going to ",
            "i am wrapping ",
            "i'm wrapping ",
        )
        english_actions = (
            " update ",
            " write ",
            " create ",
            " check ",
            " inspect ",
            " look at ",
            " search ",
            " review ",
            " analyze ",
            " verify ",
            " edit ",
            " modify ",
            " open ",
            " wrap ",
            " wrapping ",
        )
        if any(
            any(candidate.lower().startswith(prefix) for prefix in english_prefixes)
            and any(action in f" {candidate.lower()} " for action in english_actions)
            for candidate in later_candidates
        ):
            return True
        if not any(lowered.startswith(prefix) for prefix in english_prefixes):
            return False
        return any(action in f" {lowered} " for action in english_actions)

    if any(normalized.startswith(prefix) for prefix in weak_preamble_prefixes) or normalized.startswith("先"):
        return True

    return any(
        (
            any(candidate.startswith(prefix) for prefix in weak_preamble_prefixes)
            or candidate.startswith("先")
        )
        and any(action in candidate for action in preamble_actions)
        for candidate in later_candidates
    )


def looks_like_structured_tool_handoff(
    text: str,
    *,
    clean_visible_reply_text,
    contains_tool_handoff_phrase,
    re_mod,
) -> bool:
    visible = clean_visible_reply_text(text)
    if not visible or "```" in visible:
        return False

    lines = [line.strip(" -") for line in visible.replace("\r", "\n").splitlines() if line.strip()]
    if len(lines) < 3 or len(lines) > 5:
        return False
    if any(line.startswith("|") and line.endswith("|") for line in lines):
        return False

    numbered_lines = [line for line in lines if re_mod.match(r"^\d+\.\s+\S+", line)]
    if not numbered_lines or len(numbered_lines) > 3:
        return False

    handoff_line = lines[-1]
    if re_mod.match(r"^\d+\.", handoff_line):
        return False
    if len(visible) > 220:
        return False

    return contains_tool_handoff_phrase(handoff_line)


def looks_like_trailing_tool_handoff(
    text: str,
    *,
    clean_visible_reply_text,
    looks_like_tool_preamble,
    looks_like_structured_tool_handoff,
    re_mod,
) -> bool:
    visible = clean_visible_reply_text(text)
    if not visible:
        return False

    trailing_visible = re_mod.sub(r"```.*?```", "\n", visible, flags=re_mod.S).strip()
    if not trailing_visible:
        return False

    lines = [line.strip(" -") for line in trailing_visible.replace("\r", "\n").splitlines() if line.strip()]
    paragraphs = [part.strip() for part in re_mod.split(r"\n\s*\n", trailing_visible) if part.strip()]

    candidates = []
    if paragraphs:
        candidates.append(paragraphs[-1])
    if len(lines) >= 2:
        candidates.append("\n".join(lines[-2:]))
    if lines:
        candidates.append(lines[-1])

    seen = set()
    for candidate in candidates:
        candidate = str(candidate or "").strip()
        if not candidate or candidate == trailing_visible or candidate in seen:
            continue
        seen.add(candidate)
        if looks_like_tool_preamble(candidate) or looks_like_structured_tool_handoff(candidate):
            return True
    return False


def stream_tool_call_name(tool_calls_signal: list[dict] | None) -> str:
    if not tool_calls_signal:
        return ""
    first = tool_calls_signal[0] if isinstance(tool_calls_signal[0], dict) else {}
    fn = first.get("function") if isinstance(first.get("function"), dict) else {}
    return str(fn.get("name") or "").strip()


def should_keep_stream_tool_call_with_visible_text(
    tool_calls_signal: list[dict] | None,
    visible_text: str,
    *,
    stream_tool_call_name,
) -> bool:
    tool_name = stream_tool_call_name(tool_calls_signal)
    return tool_name == "ask_user" and bool(str(visible_text or "").strip())


def resolve_stream_tool_calls_signal(
    tool_calls_signal: list[dict] | None,
    collected_tokens: list,
    bundle: dict,
    *,
    mode: str,
    strip_think_markup,
    stream_tool_call_name,
    looks_like_tool_preamble,
    looks_like_structured_tool_handoff,
    looks_like_trailing_tool_handoff,
    should_keep_stream_tool_call_with_visible_text,
    resolve_tool_calls_from_result,
    debug_write,
) -> tuple[list[dict] | None, str, str]:
    joined = "".join(str(token) for token in (collected_tokens or [])).strip()
    visible_joined = strip_think_markup(joined).strip()

    if tool_calls_signal and visible_joined:
        tool_name = stream_tool_call_name(tool_calls_signal)
        is_preamble = looks_like_tool_preamble(visible_joined)
        is_structured_handoff = looks_like_structured_tool_handoff(visible_joined)
        is_trailing_handoff = looks_like_trailing_tool_handoff(visible_joined)
        keep_mixed = should_keep_stream_tool_call_with_visible_text(tool_calls_signal, visible_joined)
        if not (is_preamble or is_structured_handoff or is_trailing_handoff or keep_mixed):
            debug_write(
                "tool_call_stream_mixed_output",
                {
                    "tool_name": tool_name,
                    "text_len": len(visible_joined),
                    "text_preview": visible_joined[:80],
                },
            )
            tool_calls_signal = None
        else:
            debug_write(
                "tool_call_stream_preamble_kept",
                {
                    "tool_name": tool_name,
                    "structured_handoff": is_structured_handoff,
                    "trailing_handoff": is_trailing_handoff,
                    "mixed_preserved": keep_mixed,
                    "text_len": len(visible_joined),
                    "text_preview": visible_joined[:80],
                },
            )

    if not tool_calls_signal:
        tool_calls_signal = resolve_tool_calls_from_result(
            {"content": joined},
            bundle,
            mode=mode,
        )

    return tool_calls_signal, joined, visible_joined
