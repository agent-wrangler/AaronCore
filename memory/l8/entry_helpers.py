"""Entry-level helpers for L8 knowledge records."""

from __future__ import annotations

import json
import re
from typing import Callable


THINK_RE = re.compile(r"(?is)<think>.*?(?:</think>|$)")


def entry_text(entry: dict) -> str:
    parts = [
        entry.get("query", ""),
        entry.get("summary", ""),
        entry.get("name", ""),
        entry.get("应用示例", ""),
        entry.get("二级场景", ""),
        entry.get("核心技能", ""),
    ]
    return " ".join(str(part or "") for part in parts).lower()


def entry_sort_key(entry: dict) -> tuple[int, str]:
    hit_count = int(entry.get("hit_count", 0) or 0)
    last_used = str(entry.get("last_used") or entry.get("最近使用时间") or entry.get("created_at") or "")
    return hit_count, last_used


def strip_json_fence(text: str) -> str:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def llm_rank_knowledge_candidates(
    query: str,
    candidates: list[tuple[int, dict]],
    *,
    llm_call,
    clean_text: Callable[[str, int | None], str],
    max_candidates: int = 18,
) -> list[tuple[int, int, dict]]:
    if not llm_call or not candidates:
        return []

    selected = sorted(candidates, key=lambda item: entry_sort_key(item[1]), reverse=True)[:max_candidates]
    if not selected:
        return []

    blocks = []
    index_by_id = {}
    entry_by_id = {}
    for fallback_id, (index, entry) in enumerate(selected, start=1):
        entry_id = str(entry.get("id") or f"l8_candidate_{fallback_id}").strip()
        index_by_id[entry_id] = index
        entry_by_id[entry_id] = entry
        blocks.append(
            "\n".join(
                [
                    f"ID: {entry_id}",
                    f"Query: {clean_text(entry.get('query') or entry.get('name') or '', 60)}",
                    f"Summary: {clean_text(entry.get('summary') or entry.get('应用示例') or '', 180)}",
                    f"Scene: {clean_text(entry.get('一级场景') or entry.get('二级场景') or '', 32)}",
                ]
            )
        )

    prompt = (
        f"User query: {clean_text(query, 120)}\n\n"
        "Below are learned knowledge candidates. Judge which entries are semantically useful for answering the user's current question.\n"
        "Do not rely on surface word overlap alone, and do not miss paraphrases that mean the same thing.\n"
        "Return JSON only. Each item must be {\"id\":\"entry_id\",\"score\":0-3}.\n"
        "Score meaning: 0=irrelevant, 1=weakly relevant, 2=clearly relevant, 3=directly relevant.\n"
        "Return only items with score >= 1, sorted from highest to lowest.\n\n"
        + "\n\n".join(blocks)
    )

    try:
        raw = str(llm_call(prompt, max_tokens=500) or "").strip()
    except TypeError:
        raw = str(llm_call(prompt) or "").strip()

    if not raw:
        return []

    raw = strip_json_fence(raw)
    match = re.search(r"\[[\s\S]*\]", raw)
    if match:
        raw = match.group(0)

    try:
        payload = json.loads(raw)
    except Exception:
        return []

    ranked = []
    seen_ids = set()
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, dict):
            continue
        entry_id = str(item.get("id") or "").strip()
        if not entry_id or entry_id in seen_ids or entry_id not in entry_by_id:
            continue
        try:
            score = int(item.get("score") or 0)
        except Exception:
            score = 0
        if score < 1:
            continue
        seen_ids.add(entry_id)
        ranked.append((score * 10, index_by_id[entry_id], entry_by_id[entry_id]))

    ranked.sort(key=lambda item: (item[0], entry_sort_key(item[2])), reverse=True)
    return ranked


def normalize_tool_skill_name(skill_name: str) -> str:
    name = str(skill_name or "").strip()
    if name.endswith("_query"):
        name = name[:-6]
    return name


def is_registered_skill_name(skill_name: str) -> bool:
    name = normalize_tool_skill_name(skill_name)
    if not name:
        return False
    try:
        from core.skills import get_all_skills

        return name in get_all_skills()
    except Exception:
        return False


def strip_think_content(text: str) -> str:
    cleaned = THINK_RE.sub(" ", str(text or ""))
    return re.sub(r"\s+", " ", cleaned).strip()


def sanitize_extra_fields(extra_fields: dict | None) -> dict:
    cleaned = {}
    for key, value in (extra_fields or {}).items():
        if isinstance(value, str):
            sanitized = strip_think_content(value).strip()
            if sanitized:
                cleaned[key] = sanitized[:400]
            continue
        cleaned[key] = value
    return cleaned


def looks_like_query_noise(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return True
    if len(raw) <= 3 and not re.search(r"[A-Za-z0-9]{3,}", raw) and not re.search(r"[\u4e00-\u9fff]{2,}", raw):
        return True
    if len(raw) <= 6 and not re.search(r"[A-Za-z0-9]{3,}", raw):
        return not bool(re.search(r"[\u4e00-\u9fff]{4,}", raw))
    return False


def looks_like_compact_search_query(text: str) -> bool:
    raw = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(raw) < 2 or len(raw) > 32:
        return False
    if re.search(r"[\r\n\t]", raw):
        return False
    if re.search(r"[。！？?!；;]", raw):
        return False
    return True


def entry_query(entry: dict) -> str:
    return str(entry.get("query") or "").strip()


def entry_summary(entry: dict) -> str:
    return str(entry.get("summary") or entry.get("应用示例") or "").strip()


def entry_type(entry: dict) -> str:
    return str(entry.get("type") or entry.get("source") or "").strip()


def entry_source(entry: dict) -> str:
    return str(entry.get("source") or "").strip()


def entry_has_reusable_knowledge(
    entry: dict,
    *,
    clean_text: Callable[[str, int | None], str],
) -> bool:
    if not isinstance(entry, dict):
        return False

    query = entry_query(entry)
    summary = entry_summary(entry)
    if not query or not summary:
        return False
    if THINK_RE.search(query) or THINK_RE.search(summary):
        return False
    if looks_like_query_noise(query):
        return False
    if len(clean_text(summary)) < 15:
        return False
    return True
