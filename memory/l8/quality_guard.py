"""Quality gating helpers for L8 knowledge entries."""

from __future__ import annotations

from collections.abc import Callable

_ENTRY_QUALITY_REJECT_LABELS = {
    "query_is_complaint",
    "self_referential",
    "summary_is_dialogue_analysis",
    "summary_is_llm_chatter",
    "summary_no_new_info",
}


def llm_entry_quality_label(
    query: str,
    summary: str,
    *,
    llm_call,
    clean_text: Callable[[str, int | None], str],
) -> str:
    if not llm_call:
        return ""
    q = clean_text(query, 120)
    s = clean_text(summary, 220)
    if not q or not s:
        return ""
    prompt = (
        "Review this L8 knowledge candidate.\n"
        f"query: {q}\n"
        f"summary: {s}\n\n"
        "Return exactly one label:\n"
        "- query_is_complaint when the query is only a complaint, blame, or venting.\n"
        "- self_referential when the entry is mainly about the system itself or internal meta discussion.\n"
        "- summary_is_dialogue_analysis when it mainly analyzes the conversation instead of storing reusable knowledge.\n"
        "- summary_is_llm_chatter when it is mostly chain-of-thought, filler, or process chatter.\n"
        "- summary_no_new_info when it adds almost no new information beyond the query.\n"
        "- OK when it is reusable knowledge.\n"
        "Return the label only."
    )
    try:
        result = str(llm_call(prompt, max_tokens=16) or "").strip()
    except Exception:
        return ""
    if result in _ENTRY_QUALITY_REJECT_LABELS or result == "OK":
        return result
    return ""


def check_entry_quality(
    query: str,
    summary: str,
    *,
    strip_think_content: Callable[[str], str],
    looks_like_query_noise: Callable[[str], bool],
    llm_entry_quality_label_fn: Callable[[str, str], str],
) -> str:
    q = str(query or "").strip()
    s = strip_think_content(summary)

    if "<think>" in q.lower() or "<think>" in s.lower():
        return "contains_think_tag"
    if len(q) < 3:
        return "query_too_short"
    if len(q) > 80:
        return "query_too_long_likely_raw_msg"
    if len(s) < 15:
        return "summary_too_short"
    if looks_like_query_noise(q):
        return "query_is_noise"
    if s.replace(q, "").strip() == "" or len(s) < len(q) + 10:
        return "summary_no_new_info"

    llm_label = llm_entry_quality_label_fn(q, s)
    if llm_label and llm_label != "OK":
        return llm_label
    return ""
