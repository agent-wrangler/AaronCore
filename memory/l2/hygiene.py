"""Hygiene helpers for L2/L3 memory text."""

from __future__ import annotations

import re


THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
MINIMAX_TOOL_RE = re.compile(r"<minimax:tool_call>.*?</minimax:tool_call>", re.IGNORECASE | re.DOTALL)
INVOKE_RE = re.compile(r"<invoke\b[^>]*>.*?</invoke>", re.IGNORECASE | re.DOTALL)

INTERNAL_REASONING_MARKERS = (
    "根据对话上下文",
    "作为AI助手",
    "系统提示中可能有时间信息",
    "让我们检查",
    "用户要求我",
    "这是一个很随意的开场",
)

TOOL_RECEIPT_PREFIXES = (
    "已打开网页：",
    "已截取窗口：",
    "屏幕分辨率：",
    "鼠标位置：",
    "当前活动窗口：",
    "已打开窗口数：",
    "执行失败:",
    "执行异常:",
)


def sanitize_ai_response_for_memory(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = THINK_BLOCK_RE.sub("", cleaned)
    cleaned = MINIMAX_TOOL_RE.sub("", cleaned)
    cleaned = INVOKE_RE.sub("", cleaned)
    cleaned = re.sub(r"</?think[^>]*>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def sanitize_summary_text(text: str) -> str:
    cleaned = sanitize_ai_response_for_memory(text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def looks_questionmark_garbled(text: str) -> bool:
    raw = str(text or "").strip()
    if len(raw) < 6:
        return False
    question_like = raw.count("?") + raw.count("？")
    return question_like >= 6 and question_like >= max(6, len(raw) // 2)


def looks_internal_reasoning(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    if "Traceback (most recent call last):" in raw or "UnicodeEncodeError" in raw:
        return True
    return any(marker in raw for marker in INTERNAL_REASONING_MARKERS)


def looks_tool_receipt(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    if raw.startswith(TOOL_RECEIPT_PREFIXES):
        return True
    return "Computer Use 技能支持" in raw


def is_dirty_memory_turn(user_text: str, ai_text: str, *, normalize_signal_text) -> bool:
    user_raw = str(user_text or "").strip()
    ai_clean = sanitize_ai_response_for_memory(ai_text)
    user_norm = normalize_signal_text(user_raw)

    if not user_raw:
        return True
    if not ai_clean:
        return False
    if looks_questionmark_garbled(user_raw):
        return True
    if looks_internal_reasoning(ai_clean):
        return True
    if looks_tool_receipt(ai_clean) and len(user_norm) < 16:
        return True
    return False


def clean_memory_entry(item: dict, *, normalize_signal_text) -> tuple[dict | None, bool]:
    if not isinstance(item, dict):
        return None, True

    original_user = str(item.get("user_text") or "")
    original_ai = str(item.get("ai_text") or "")
    cleaned_user = original_user.strip()
    cleaned_ai = sanitize_ai_response_for_memory(original_ai)

    if not cleaned_user:
        return None, True
    if not cleaned_ai:
        if looks_questionmark_garbled(cleaned_user):
            return None, True
        if cleaned_user == original_user:
            return item, False
        row = dict(item)
        row["user_text"] = cleaned_user
        return row, True

    if is_dirty_memory_turn(cleaned_user, cleaned_ai, normalize_signal_text=normalize_signal_text):
        return None, True

    changed = cleaned_user != original_user or cleaned_ai != original_ai
    if not changed:
        return item, False

    row = dict(item)
    row["user_text"] = cleaned_user
    row["ai_text"] = cleaned_ai
    return row, True


def clean_memory_entries(entries: list, *, normalize_signal_text) -> tuple[list, bool]:
    cleaned = []
    changed = False
    for item in entries or []:
        row, row_changed = clean_memory_entry(item, normalize_signal_text=normalize_signal_text)
        if row is None:
            changed = True
            continue
        cleaned.append(row)
        changed = changed or row_changed
    return cleaned, changed
