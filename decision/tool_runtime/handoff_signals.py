"""Post-LLM tool handoff and mixed-output compatibility signals."""

from decision.tool_runtime.parallel_runtime import get_tool_parallel_profile


def _prefers_explicit_tool_call(tool_name: str) -> bool:
    name = str(tool_name or "").strip()
    if not name:
        return False
    profile = get_tool_parallel_profile(name)
    effect_level = str(profile.get("effect_level") or "").strip().lower()
    operation_kind = str(profile.get("operation_kind") or "").strip().lower()
    if effect_level not in {"read_only", "external_lookup"}:
        return False
    return operation_kind in {"inspect", "query"}


def _allows_phrase_handoff_assist(tool_name: str) -> bool:
    name = str(tool_name or "").strip()
    if not name:
        return False
    if name == "ask_user":
        return True
    profile = get_tool_parallel_profile(name)
    operation_kind = str(profile.get("operation_kind") or "").strip().lower()
    effect_level = str(profile.get("effect_level") or "").strip().lower()
    if effect_level in {"local_write", "local_side_effect"}:
        return False
    return operation_kind in {"inspect", "query", "plan"}


def _split_visible_sentences(text: str, *, re_mod) -> list[str]:
    return [part.strip() for part in re_mod.split(r"[。！？?]\s*|\n+", str(text or "")) if part.strip()]


def _contains_any_token(text: str, tokens: tuple[str, ...]) -> bool:
    raw = str(text or "")
    return any(token in raw for token in tokens)


def _looks_like_answer_payload(
    text: str,
    *,
    clean_visible_reply_text,
    re_mod,
) -> bool:
    visible = clean_visible_reply_text(text)
    if not visible:
        return False
    if "```" in visible:
        return True

    lines = [line.strip(" -") for line in visible.replace("\r", "\n").splitlines() if line.strip()]
    if any(line.startswith("|") and line.endswith("|") for line in lines):
        return True
    if len(lines) > 6:
        return True

    sentence_count = len(_split_visible_sentences(visible, re_mod=re_mod))
    if sentence_count > 5:
        return True

    bullet_count = len([line for line in lines if re_mod.match(r"^(?:\d+\.|[-*•])\s+\S+", line)])
    if bullet_count >= 2:
        return True

    answer_like_patterns = (
        r"https?://",
        r"[A-Za-z]:\\",
        r"(?:SQLite|Flask|Electron|LocalStorage)\s+\+",
        r"\b(?:A|B|C)\b\s*\|",
        r"\b\d+\s*(?:%|h|hr|hrs|hour|hours|min|mins|minute|minutes|sec|secs|second|seconds|times?)\b",
        r"\b\d+\s*(?:to|-)\s*\d+\s*(?:degrees?|deg|°)\b",
        r"\d+\s*(?:到|-)\s*\d+\s*(?:度|°)",
    )
    return any(re_mod.search(pattern, visible, flags=re_mod.I) for pattern in answer_like_patterns)


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
    if _looks_like_answer_payload(
        visible,
        clean_visible_reply_text=clean_visible_reply_text,
        re_mod=re_mod,
    ):
        return False

    lines = [line.strip(" -") for line in visible.replace("\r", "\n").splitlines() if line.strip()]
    if len(lines) > 4:
        return False
    if any(re_mod.match(r"^\d+\.", line) for line in lines):
        return False
    if any(line.startswith("|") and line.endswith("|") for line in lines):
        return False

    sentence_count = len(_split_visible_sentences(visible, re_mod=re_mod))
    if sentence_count > 4:
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
    for part in _split_visible_sentences(visible, re_mod=re_mod):
        candidate = _normalize_segment(part)
        if candidate:
            sentence_candidates.append(candidate)
    later_candidates = sentence_candidates[1:] if len(sentence_candidates) > 1 else []

    strong_preamble_prefixes = (
        "我来",
        "我先",
        "我帮你",
        "让我",
        "先帮你",
        "先看",
        "先查",
        "稍等",
        "等我",
    )
    weak_preamble_prefixes = (
        "好",
        "行",
        "那我",
    )
    action_stems = (
        "看",
        "查",
        "梳理",
        "定位",
        "检索",
        "分析",
        "处理",
        "确认",
        "整理",
        "回忆",
        "执行",
        "创建",
        "写",
        "打开",
        "搜索",
        "检查",
        "记忆",
        "一步到位",
    )

    if any(normalized.startswith(prefix) for prefix in strong_preamble_prefixes):
        return True

    if any(
        any(candidate.startswith(prefix) for prefix in strong_preamble_prefixes)
        and _contains_any_token(candidate, action_stems)
        for candidate in later_candidates
    ):
        return True

    action_hit = _contains_any_token(normalized, action_stems)
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
            " look ",
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
        and _contains_any_token(candidate, action_stems)
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
    clean_visible_reply_text,
    re_mod,
) -> bool:
    tool_name = stream_tool_call_name(tool_calls_signal)
    visible = clean_visible_reply_text(visible_text)
    if not visible:
        return False
    if tool_name == "ask_user":
        return True
    if not _prefers_explicit_tool_call(tool_name):
        return False
    if len(visible) > 240:
        return False
    return not _looks_like_answer_payload(
        visible,
        clean_visible_reply_text=clean_visible_reply_text,
        re_mod=re_mod,
    )


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
        tool_profile = get_tool_parallel_profile(tool_name)
        is_preamble = looks_like_tool_preamble(visible_joined)
        is_structured_handoff = looks_like_structured_tool_handoff(visible_joined)
        is_trailing_handoff = looks_like_trailing_tool_handoff(visible_joined)
        phrase_handoff = is_preamble or is_structured_handoff or is_trailing_handoff
        keep_phrase_assist = phrase_handoff and _allows_phrase_handoff_assist(tool_name)
        keep_mixed = should_keep_stream_tool_call_with_visible_text(tool_calls_signal, visible_joined)
        if not (keep_mixed or keep_phrase_assist):
            debug_write(
                "tool_call_stream_mixed_output",
                {
                    "tool_name": tool_name,
                    "tool_profile": tool_profile,
                    "explicit_tool_call": True,
                    "phrase_handoff": phrase_handoff,
                    "phrase_assist": keep_phrase_assist,
                    "structure_kept": keep_mixed,
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
                    "tool_profile": tool_profile,
                    "explicit_tool_call": True,
                    "preamble_handoff": is_preamble,
                    "structured_handoff": is_structured_handoff,
                    "trailing_handoff": is_trailing_handoff,
                    "phrase_assist": keep_phrase_assist,
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
