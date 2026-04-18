"""Post-LLM tool handoff and mixed-output compatibility signals."""

from dataclasses import dataclass

from decision.tool_runtime.parallel_runtime import get_tool_parallel_profile


_HANDOFF_CHATTER_PREFIX_RE = (
    r"^(?:(?:\u4e3b\u4eba|ok(?:ay)?|sure|alright|"
    r"\u597d(?:\u7684|\u561e|\u5440|\u54e6|\u5427)?)[\s,\u3001\uff0c!！.。\-]*)+"
)
_CHINESE_HANDOFF_LEAD_RE = (
    r"^(?:(?:\u8fd9\u6b21|\u73b0\u5728|\u63a5\u4e0b\u6765)[\s,\u3001\uff0c]*)?"
    r"(?:\u8ba9\u6211(?:\u5148|\u7ee7\u7eed)?|"
    r"\u6211(?:\u5148|\u6765|\u53bb|\u7ee7\u7eed|\u8fd9\u5c31|\u9a6c\u4e0a|\u76f4\u63a5)|"
    r"\u5148|\u7a0d\u7b49|\u7b49\u6211)"
)
_CHINESE_HANDOFF_ACTION_RE = (
    r"(?:\u770b(?:\u770b)?|\u67e5(?:\u770b)?|\u68c0(?:\u67e5)?|\u641c(?:\u7d22)?|"
    r"\u8bfb(?:\u53d6)?|\u68b3\u7406|\u5206\u6790|\u5904\u7406|\u786e\u8ba4|\u5b9a\u4f4d|"
    r"\u56de\u5fc6|\u5199|\u6539|\u4fee|\u521b\u5efa|\u6253\u5f00|\u8fd0\u884c|"
    r"\u5b89\u88c5|\u63d0\u4ea4|\u63a8\u9001|\u8fc7\u4e00\u904d|\u641e\u5b9a)"
)
_ENGLISH_HANDOFF_LEAD_RE = (
    r"^(?:(?:ok(?:ay)?|sure|alright)[\s,!.]*)?"
    r"(?:(?:let\s+me|just\s+let\s+me|"
    r"i(?:'ll| will| am going to|'m going to| am wrapping|'m wrapping)|"
    r"first[, ]+i(?:'ll| will))(?:\s+go\s+)?)"
)
_ENGLISH_HANDOFF_ACTION_RE = (
    r"\b(?:check|inspect|look(?:\s+into)?|search|find|review|analy[sz]e|verify|"
    r"edit|modify|update|write|create|open|read|fix|run|plan|wrap(?:\s+this\s+up)?|"
    r"wrapping)\b"
)
_RESULT_EVIDENCE_PATTERNS = (
    r"https?://",
    r"[A-Za-z]:\\",
    r"/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)+",
    r"`[^`]+`",
    r"\b[A-Za-z0-9_.-]+\.(?:py|js|ts|tsx|jsx|json|md|txt|html|css|ya?ml|toml|ini|cfg|sh|ps1)\b",
    r"\b(?:sqlite|flask|electron|localstorage)\s+\+",
    r"\b(?:[A-C]|\d+)\b\s*\|",
    r"\b\d+\s*(?:%|h|hr|hrs|hour|hours|min|mins|minute|minutes|sec|secs|second|seconds|times?)\b",
    r"\b\d+\s*(?:to|-)\s*\d+\s*(?:degrees?|deg)\b",
)
_RESULT_GROUNDED_MARKER_RE = (
    r"(?:\u95ee\u9898|\u539f\u56e0|\u6839\u56e0)(?:\u5df2\u7ecf)?(?:\u5b9a\u4f4d\u5230|\u5b9a\u4f4d\u5728|\u627e\u5230|\u67e5\u5230|\u786e\u8ba4)"
    r"|(?:\u539f\u56e0\u662f|\u6839\u56e0\u662f|\u7ed3\u8bba\u662f)"
    r"|(?:\u5df2\u7ecf|\u5df2)(?:\u5b9a\u4f4d|\u627e\u5230|\u67e5\u5230|\u786e\u8ba4|\u770b\u5230|\u4fee\u597d)"
    r"|(?:\u5b9a\u4f4d\u5230|\u5b9a\u4f4d\u5728|\u627e\u5230|\u67e5\u5230)"
    r"|(?:\u6539\u6210|\u6539\u4e3a|\u4fee\u6210|\u4fee\u597d|\u4e0d\u4f1a\u518d|\u4e0d\u518d)"
    r"|(?:found|located|identified|updated|changed|fixed|no\s+longer)"
)
_WEATHER_RANGE_RE = (
    r"\b\d+\s*(?:to|-)\s*\d+\s*(?:degrees?|deg|°c|℃)\b"
    r"|\b\d+\s*(?:\u5230|-)\s*\d+\s*(?:\u5ea6|℃)\b"
)
_WEATHER_WORD_RE = (
    r"(?:\u6674|\u9634|\u591a\u4e91|\u9635\u96e8|\u5c0f\u96e8|\u4e2d\u96e8|\u5927\u96e8|"
    r"\u96f7\u9635\u96e8|\u5c0f\u96ea|\u4e2d\u96ea|\u5927\u96ea|\u9634\u8f6c|\u96e8\u8f6c|"
    r"weather|forecast|sunny|cloudy|overcast|rain|rainy|showers?|storm|thunderstorms?|snow|snowy|drizzle)"
)


@dataclass(frozen=True)
class _HandoffShape:
    visible: str
    analysis_visible: str
    raw_lines: list[str]
    analysis_lines: list[str]
    paragraphs: list[str]
    sentences: list[str]
    sentence_candidates: list[str]
    last_line: str
    last_line_candidate: str
    fallback_candidate: str
    line_count: int
    paragraph_count: int
    sentence_count: int
    plain_line_count: int
    numbered_count: int
    bullet_count: int
    has_code: bool
    has_table: bool
    char_count: int
    structured_summary_shape: bool


@dataclass(frozen=True)
class _TrailingHandoffSplit:
    body_text: str
    tail_text: str
    split_kind: str
    body_shape: _HandoffShape
    tail_shape: _HandoffShape


@dataclass(frozen=True)
class _PhraseIntent:
    candidate: str
    language: str
    has_action: bool
    short_followup: bool


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
    return [
        part.strip()
        for part in re_mod.split(r"[\u3002\uff01\uff1f!?]+\s*|\.\s+(?=[A-Z])|\n+", str(text or ""))
        if part.strip()
    ]


def _visible_lines(text: str) -> list[str]:
    return [line.strip() for line in str(text or "").replace("\r", "\n").splitlines() if line.strip()]


def _visible_paragraphs(text: str, *, re_mod) -> list[str]:
    return [part.strip() for part in re_mod.split(r"\n\s*\n", str(text or "")) if part.strip()]


def _normalize_segment(raw: str, *, re_mod) -> str:
    segment = re_mod.sub(r"^[\s#>*`\-\u2014\u2013\d\.\)\(]+", "", str(raw or "")).strip()
    segment = re_mod.sub(r"^[^A-Za-z0-9\u4e00-\u9fff]+", "", segment).strip()
    return segment


def _strip_chatter_prefix(raw: str, *, re_mod) -> str:
    segment = str(raw or "").strip()
    if not segment:
        return ""
    stripped = re_mod.sub(_HANDOFF_CHATTER_PREFIX_RE, "", segment, flags=re_mod.I).strip()
    return stripped or segment


def _strip_list_marker(raw: str, *, re_mod) -> str:
    return re_mod.sub(r"^(?:\d+\.\s+|[-*+\u2022]\s+)", "", str(raw or "")).strip()


def _is_numbered_line(line: str, *, re_mod) -> bool:
    return bool(re_mod.match(r"^\d+\.\s+\S+", str(line or "")))


def _is_bullet_line(line: str, *, re_mod) -> bool:
    return bool(re_mod.match(r"^(?:\d+\.|[-*+\u2022])\s+\S+", str(line or "")))


def _clean_handoff_candidate(raw: str, *, re_mod) -> str:
    candidate = _normalize_segment(raw, re_mod=re_mod) or str(raw or "").strip()
    candidate = _strip_chatter_prefix(candidate, re_mod=re_mod)
    candidate = _strip_list_marker(candidate, re_mod=re_mod)
    return candidate.strip()


def _extract_segment_handoff_intent(segment: str, *, re_mod) -> _PhraseIntent | None:
    text = _clean_handoff_candidate(segment, re_mod=re_mod)
    if not text or len(text) > 120:
        return None

    if re_mod.search(_ENGLISH_HANDOFF_LEAD_RE, text, flags=re_mod.I):
        if not re_mod.search(_ENGLISH_HANDOFF_ACTION_RE, text, flags=re_mod.I):
            return None
        return _PhraseIntent(
            candidate=text,
            language="en",
            has_action=True,
            short_followup=False,
        )

    if not re_mod.search(_CHINESE_HANDOFF_LEAD_RE, text, flags=re_mod.I):
        return None

    has_action = bool(re_mod.search(_CHINESE_HANDOFF_ACTION_RE, text, flags=re_mod.I))
    short_followup = not has_action and len(text) <= 16
    if not has_action and not short_followup:
        return None
    return _PhraseIntent(
        candidate=text,
        language="zh",
        has_action=has_action,
        short_followup=short_followup,
    )


def _extract_handoff_shape(text: str, *, clean_visible_reply_text, re_mod) -> _HandoffShape:
    visible = clean_visible_reply_text(text)
    analysis_visible = re_mod.sub(r"```.*?```", "\n", visible, flags=re_mod.S).strip()

    raw_lines = _visible_lines(visible)
    analysis_lines = _visible_lines(analysis_visible)
    paragraphs = _visible_paragraphs(analysis_visible, re_mod=re_mod)
    sentences = _split_visible_sentences(analysis_visible, re_mod=re_mod)

    sentence_candidates: list[str] = []
    for sentence in sentences:
        candidate = _clean_handoff_candidate(sentence, re_mod=re_mod)
        if candidate:
            sentence_candidates.append(candidate)

    numbered_lines = [line for line in analysis_lines if _is_numbered_line(line, re_mod=re_mod)]
    bullet_lines = [line for line in analysis_lines if _is_bullet_line(line, re_mod=re_mod)]
    table_lines = [line for line in raw_lines if line.startswith("|") and line.endswith("|")]
    plain_lines = [
        line
        for line in analysis_lines
        if not _is_bullet_line(line, re_mod=re_mod) and not (line.startswith("|") and line.endswith("|"))
    ]
    last_line = analysis_lines[-1] if analysis_lines else ""
    last_line_candidate = _clean_handoff_candidate(last_line, re_mod=re_mod)
    fallback_candidate = _clean_handoff_candidate(analysis_visible, re_mod=re_mod) if analysis_visible else ""

    structured_summary_shape = (
        3 <= len(analysis_lines) <= 5
        and 1 <= len(numbered_lines) <= 3
        and bool(last_line)
        and not _is_numbered_line(last_line, re_mod=re_mod)
        and len(visible) <= 260
    )

    return _HandoffShape(
        visible=visible,
        analysis_visible=analysis_visible,
        raw_lines=raw_lines,
        analysis_lines=analysis_lines,
        paragraphs=paragraphs,
        sentences=sentences,
        sentence_candidates=sentence_candidates,
        last_line=last_line,
        last_line_candidate=last_line_candidate,
        fallback_candidate=fallback_candidate,
        line_count=len(analysis_lines),
        paragraph_count=len(paragraphs),
        sentence_count=len(sentences),
        plain_line_count=len(plain_lines),
        numbered_count=len(numbered_lines),
        bullet_count=len(bullet_lines),
        has_code="```" in visible,
        has_table=bool(table_lines),
        char_count=len(visible),
        structured_summary_shape=structured_summary_shape,
    )


def _has_result_payload_shape(shape: _HandoffShape, *, re_mod) -> bool:
    if not shape.visible:
        return False

    if shape.has_code or shape.has_table:
        return True
    # Treat compact grounded answers as payload before the broader length heuristics kick in.
    # This keeps short weather/results replies from being mistaken for handoff chatter.
    if (
        re_mod.search(_WEATHER_RANGE_RE, shape.visible, flags=re_mod.I)
        and re_mod.search(_WEATHER_WORD_RE, shape.visible, flags=re_mod.I)
    ):
        return True
    if (
        (shape.paragraph_count >= 2 or shape.sentence_count >= 2)
        and re_mod.search(_RESULT_GROUNDED_MARKER_RE, shape.visible, flags=re_mod.I)
    ):
        return True
    if shape.line_count > 6:
        return True
    if shape.sentence_count > 5:
        return True

    if shape.bullet_count >= 2:
        if shape.structured_summary_shape and _extract_segment_handoff_intent(
            shape.last_line_candidate,
            re_mod=re_mod,
        ):
            return False
        return True

    if any(re_mod.search(pattern, shape.visible, flags=re_mod.I) for pattern in _RESULT_EVIDENCE_PATTERNS):
        return True

    if (
        shape.plain_line_count >= 3
        and shape.sentence_count >= 3
        and shape.char_count > 180
    ):
        return True

    return False


def _is_phrase_candidate_shape(shape: _HandoffShape, *, re_mod) -> bool:
    if not shape.visible:
        return False
    if shape.has_code or shape.has_table:
        return False
    if shape.line_count > 5:
        return False
    if shape.sentence_count > 5:
        return False
    return not _has_result_payload_shape(shape, re_mod=re_mod)


def _is_short_handoff_shape(shape: _HandoffShape, *, re_mod) -> bool:
    if not _is_phrase_candidate_shape(shape, re_mod=re_mod):
        return False
    if shape.line_count > 4:
        return False
    if shape.sentence_count > 4:
        return False
    return shape.numbered_count == 0


def _is_structured_handoff_shape(shape: _HandoffShape, *, re_mod) -> bool:
    if not _is_phrase_candidate_shape(shape, re_mod=re_mod):
        return False
    if not shape.structured_summary_shape:
        return False
    return bool(shape.last_line)


def _iter_shape_intent_segments(shape: _HandoffShape) -> list[str]:
    segments = list(shape.sentence_candidates)
    if segments:
        return segments
    if shape.fallback_candidate:
        return [shape.fallback_candidate]
    return []


def _extract_shape_handoff_intent(shape: _HandoffShape, *, re_mod) -> _PhraseIntent | None:
    if not _is_phrase_candidate_shape(shape, re_mod=re_mod):
        return None

    for candidate in _iter_shape_intent_segments(shape):
        intent = _extract_segment_handoff_intent(candidate, re_mod=re_mod)
        if intent is not None:
            return intent
    return None


def _tail_matches_handoff_shape(shape: _HandoffShape, *, re_mod) -> bool:
    if _is_structured_handoff_shape(shape, re_mod=re_mod):
        return _extract_segment_handoff_intent(shape.last_line, re_mod=re_mod) is not None
    if _is_short_handoff_shape(shape, re_mod=re_mod):
        return _extract_shape_handoff_intent(shape, re_mod=re_mod) is not None
    return False


def _body_supports_trailing_handoff(shape: _HandoffShape, *, re_mod) -> bool:
    if not shape.visible:
        return False
    if _is_short_handoff_shape(shape, re_mod=re_mod):
        return False
    if _is_structured_handoff_shape(shape, re_mod=re_mod):
        return False
    if _has_result_payload_shape(shape, re_mod=re_mod):
        return True
    return (
        shape.line_count >= 2
        or shape.paragraph_count >= 2
        or shape.char_count >= 72
    )


def _build_trailing_handoff_split(
    body_text: str,
    tail_text: str,
    *,
    split_kind: str,
    clean_visible_reply_text,
    re_mod,
) -> _TrailingHandoffSplit | None:
    body_clean = clean_visible_reply_text(body_text)
    tail_clean = clean_visible_reply_text(tail_text)
    if not body_clean or not tail_clean:
        return None

    body_shape = _extract_handoff_shape(
        body_clean,
        clean_visible_reply_text=clean_visible_reply_text,
        re_mod=re_mod,
    )
    tail_shape = _extract_handoff_shape(
        tail_clean,
        clean_visible_reply_text=clean_visible_reply_text,
        re_mod=re_mod,
    )
    if not _body_supports_trailing_handoff(body_shape, re_mod=re_mod):
        return None
    if not _tail_matches_handoff_shape(tail_shape, re_mod=re_mod):
        return None
    return _TrailingHandoffSplit(
        body_text=body_clean,
        tail_text=tail_clean,
        split_kind=split_kind,
        body_shape=body_shape,
        tail_shape=tail_shape,
    )


def _extract_trailing_handoff_split(
    text: str,
    *,
    clean_visible_reply_text,
    re_mod,
) -> _TrailingHandoffSplit | None:
    visible = clean_visible_reply_text(text)
    if not visible:
        return None

    whole_shape = _extract_handoff_shape(
        visible,
        clean_visible_reply_text=clean_visible_reply_text,
        re_mod=re_mod,
    )
    if _is_short_handoff_shape(whole_shape, re_mod=re_mod):
        return None
    if _is_structured_handoff_shape(whole_shape, re_mod=re_mod):
        return None

    paragraphs = _visible_paragraphs(visible, re_mod=re_mod)
    if len(paragraphs) >= 2:
        split = _build_trailing_handoff_split(
            "\n\n".join(paragraphs[:-1]).strip(),
            paragraphs[-1].strip(),
            split_kind="paragraph",
            clean_visible_reply_text=clean_visible_reply_text,
            re_mod=re_mod,
        )
        if split:
            return split

    lines = _visible_lines(visible)
    if len(lines) >= 2:
        split = _build_trailing_handoff_split(
            "\n".join(lines[:-1]).strip(),
            lines[-1].strip(),
            split_kind="last_line",
            clean_visible_reply_text=clean_visible_reply_text,
            re_mod=re_mod,
        )
        if split:
            return split

    if len(lines) >= 3:
        split = _build_trailing_handoff_split(
            "\n".join(lines[:-2]).strip(),
            "\n".join(lines[-2:]).strip(),
            split_kind="two_line_tail",
            clean_visible_reply_text=clean_visible_reply_text,
            re_mod=re_mod,
        )
        if split:
            return split

    return None


def _looks_like_answer_payload(
    text: str,
    *,
    clean_visible_reply_text,
    re_mod,
) -> bool:
    shape = _extract_handoff_shape(
        text,
        clean_visible_reply_text=clean_visible_reply_text,
        re_mod=re_mod,
    )
    return _has_result_payload_shape(shape, re_mod=re_mod)


def looks_like_tool_preamble(
    text: str,
    *,
    clean_visible_reply_text,
    re_mod,
) -> bool:
    shape = _extract_handoff_shape(
        text,
        clean_visible_reply_text=clean_visible_reply_text,
        re_mod=re_mod,
    )
    if not _is_short_handoff_shape(shape, re_mod=re_mod):
        return False
    return _extract_shape_handoff_intent(shape, re_mod=re_mod) is not None


def contains_tool_handoff_phrase(text: str, *, clean_visible_reply_text, re_mod) -> bool:
    shape = _extract_handoff_shape(
        text,
        clean_visible_reply_text=clean_visible_reply_text,
        re_mod=re_mod,
    )
    return _extract_shape_handoff_intent(shape, re_mod=re_mod) is not None


def looks_like_structured_tool_handoff(
    text: str,
    *,
    clean_visible_reply_text,
    re_mod,
) -> bool:
    shape = _extract_handoff_shape(
        text,
        clean_visible_reply_text=clean_visible_reply_text,
        re_mod=re_mod,
    )
    if not _is_structured_handoff_shape(shape, re_mod=re_mod):
        return False

    handoff_line = shape.last_line
    if not handoff_line:
        return False
    return _extract_segment_handoff_intent(handoff_line, re_mod=re_mod) is not None


def split_trailing_tool_handoff(
    text: str,
    *,
    clean_visible_reply_text,
    re_mod,
) -> tuple[str, str] | None:
    split = _extract_trailing_handoff_split(
        text,
        clean_visible_reply_text=clean_visible_reply_text,
        re_mod=re_mod,
    )
    if not split:
        return None
    return split.body_text, split.tail_text


def looks_like_trailing_tool_handoff(
    text: str,
    *,
    clean_visible_reply_text,
    re_mod,
) -> bool:
    split = _extract_trailing_handoff_split(
        text,
        clean_visible_reply_text=clean_visible_reply_text,
        re_mod=re_mod,
    )
    return split is not None


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
    clean_visible_reply_text,
    stream_tool_call_name,
    looks_like_tool_preamble,
    looks_like_structured_tool_handoff,
    looks_like_trailing_tool_handoff,
    should_keep_stream_tool_call_with_visible_text,
    resolve_tool_calls_from_result,
    debug_write,
    re_mod,
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
        keep_short_preface = (
            _prefers_explicit_tool_call(tool_name)
            and len(visible_joined) <= 120
            and not _looks_like_answer_payload(
                visible_joined,
                clean_visible_reply_text=clean_visible_reply_text,
                re_mod=re_mod,
            )
        )
        if not (keep_mixed or keep_phrase_assist or keep_short_preface):
            debug_write(
                "tool_call_stream_mixed_output",
                {
                    "tool_name": tool_name,
                    "tool_profile": tool_profile,
                    "explicit_tool_call": True,
                    "phrase_handoff": phrase_handoff,
                    "phrase_assist": keep_phrase_assist,
                    "structure_kept": keep_mixed,
                    "short_preface_kept": keep_short_preface,
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
                    "short_preface_preserved": keep_short_preface,
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
