from __future__ import annotations

from core import shared as S


def ensure_tool_call_failure_reply(
    response: str,
    *,
    tool_used: str = "",
    tool_success: bool | None = None,
    tool_response: str = "",
    action_summary: str = "",
    run_meta: dict | None = None,
) -> str:
    text = str(response or "")
    if not tool_used or tool_success is not False:
        return text
    try:
        from core.reply_formatter import _build_tool_closeout_reply, _clean_visible_reply_text, _looks_like_tool_preamble

        cleaned = _clean_visible_reply_text(text)
        if cleaned and not _looks_like_tool_preamble(cleaned):
            return text
        fallback = _build_tool_closeout_reply(
            success=False,
            action_summary=action_summary,
            tool_response=str(tool_response or text).strip(),
            run_meta=run_meta if isinstance(run_meta, dict) else {},
        )
        if fallback:
            return fallback
    except Exception:
        pass
    fallback_text = str(tool_response or text).strip()
    if fallback_text:
        return S.format_skill_fallback(fallback_text)
    return text


def drop_incomplete_tool_handoff_prefix(chunks: list[str]) -> str:
    if not chunks:
        return ""
    try:
        from core.reply_formatter import _clean_visible_reply_text, _looks_like_incomplete_tool_handoff

        joined = "".join(str(chunk or "") for chunk in chunks).strip()
        cleaned = _clean_visible_reply_text(joined)
        if cleaned and _looks_like_incomplete_tool_handoff(cleaned):
            chunks.clear()
            return cleaned
    except Exception:
        return ""
    return ""


_THINK_OPEN_TAG = "<think>"
_THINK_CLOSE_TAG = "</think>"


def consume_think_filtered_stream_text(
    carry: str,
    chunk: str,
    *,
    in_think: bool = False,
    end_of_stream: bool = False,
) -> tuple[list[str], str, bool, bool]:
    carry = f"{carry}{str(chunk or '')}"
    visible_parts: list[str] = []
    saw_think = False
    open_keep = max(0, len(_THINK_OPEN_TAG) - 1)
    close_keep = max(0, len(_THINK_CLOSE_TAG) - 1)

    while carry:
        lowered = carry.lower()
        if in_think:
            close_idx = lowered.find(_THINK_CLOSE_TAG)
            if close_idx < 0:
                if end_of_stream:
                    return visible_parts, "", True, saw_think
                if close_keep and len(carry) > close_keep:
                    carry = carry[-close_keep:]
                break
            carry = carry[close_idx + len(_THINK_CLOSE_TAG):]
            in_think = False
            continue

        open_idx = lowered.find(_THINK_OPEN_TAG)
        if open_idx >= 0:
            prefix = carry[:open_idx]
            if prefix:
                visible_parts.append(prefix)
            carry = carry[open_idx + len(_THINK_OPEN_TAG):]
            in_think = True
            saw_think = True
            continue

        if end_of_stream:
            visible_parts.append(carry)
            return visible_parts, "", in_think, saw_think

        if len(carry) <= open_keep:
            break
        visible_parts.append(carry[:-open_keep])
        carry = carry[-open_keep:]
        break

    return visible_parts, carry, in_think, saw_think


def reset_stream_visible_state(stream_chunks: list[str], carry: str) -> tuple[str, str, bool]:
    dropped_text = f"{''.join(stream_chunks)}{str(carry or '')}".strip()
    if stream_chunks:
        stream_chunks.clear()
    return dropped_text, "", False
