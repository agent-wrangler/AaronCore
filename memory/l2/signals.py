"""Signal profiling and retrieval helpers for L2 memory."""

from __future__ import annotations

import re
from datetime import datetime


SIGNAL_FILLERS = "吗呢吧啊呀嘛啦喔哦"
SIGNATURE_EXCLUDED_TAGS = {"meta:question", "meta:structured", "meta:longform", "meta:mixed_script"}


def normalize_signal_text(text: str) -> str:
    text = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", str(text or "").lower())
    return text.strip()


def profile_content_tokens(text: str) -> list[str]:
    raw = str(text or "").strip()
    normalized = normalize_signal_text(raw)
    if not normalized:
        return []

    tokens = []
    for token in re.findall(r"[A-Za-z0-9]{2,12}", raw):
        tokens.append(f"tok:{token.lower()[:12]}")

    cjk = "".join(re.findall(r"[\u4e00-\u9fff]", raw))
    if cjk:
        if len(cjk) <= 8:
            tokens.append(f"tok:{cjk}")
        for ch in dict.fromkeys(cjk):
            tokens.append(f"char:{ch}")
        max_size = min(4, len(cjk))
        for size in range(max_size, 1, -1):
            for idx in range(0, len(cjk) - size + 1):
                tokens.append(f"tok:{cjk[idx:idx + size]}")

    if not tokens:
        tokens.append(f"tok:{normalized[:8]}")

    out = []
    seen = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
        if len(out) >= 32:
            break
    return out


def build_signal_profile(text: str) -> set[str]:
    raw = str(text or "").strip().lower()
    normalized = normalize_signal_text(raw)
    if not normalized:
        return set()

    profile = set(profile_content_tokens(raw))

    if any(sig in raw for sig in ("?", "？")):
        profile.add("meta:question")
    if any(sig in raw for sig in (":", "：", "\n")) or any(ch.isdigit() for ch in normalized):
        profile.add("meta:structured")
    if len(normalized) >= 12:
        profile.add("meta:longform")
    if re.search(r"[A-Za-z]", raw) and re.search(r"[\u4e00-\u9fff]", raw):
        profile.add("meta:mixed_script")
    return profile


def signal_overlap(query_profile: set[str], candidate_profile: set[str]) -> float:
    if not query_profile or not candidate_profile:
        return 0.0

    query_meta = {item for item in query_profile if item.startswith("meta:")}
    candidate_meta = {item for item in candidate_profile if item.startswith("meta:")}
    query_content = query_profile - query_meta
    candidate_content = candidate_profile - candidate_meta
    query_tokens = {item for item in query_content if item.startswith("tok:")}
    candidate_tokens = {item for item in candidate_content if item.startswith("tok:")}
    query_chars = {item for item in query_content if item.startswith("char:")}
    candidate_chars = {item for item in candidate_content if item.startswith("char:")}

    shared_content = query_tokens & candidate_tokens
    shared_chars = query_chars & candidate_chars
    shared_meta = query_meta & candidate_meta
    if not shared_content and not shared_chars and not shared_meta:
        return 0.0

    content_score = 0.0
    if shared_content:
        longest = max(len(item.split(":", 1)[1]) for item in shared_content if ":" in item)
        density = len(shared_content) / max(len(query_tokens), 1)
        content_score = max(density, min(0.12 * longest + 0.12, 0.72))

    char_score = 0.0
    if shared_chars:
        density = len(shared_chars) / max(len(query_chars), 1)
        char_score = min(0.12 + density * 0.24, 0.32)

    meta_score = 0.0
    if shared_meta:
        meta_score = 0.12 * (len(shared_meta) / max(len(query_meta), 1))

    return min(content_score + char_score + meta_score, 1.0)


def normalize_signature_anchor(text: str) -> str:
    normalized = normalize_signal_text(text)
    for filler in SIGNAL_FILLERS:
        normalized = normalized.replace(filler, "")
    return normalized[:8]


def build_retrieval_signature(entry: dict) -> str:
    memory_type = str(entry.get("memory_type") or "general").strip().lower() or "general"
    text = str(entry.get("user_text") or "").strip()
    anchor = normalize_signature_anchor(text)
    parts = []
    if anchor:
        parts.append(anchor)
    else:
        profile = sorted(
            tag for tag in build_signal_profile(text)
            if tag not in SIGNATURE_EXCLUDED_TAGS and tag.startswith("tok:")
        )
        if profile:
            parts.append(profile[0].split(":", 1)[1])
        elif text:
            parts.append(text[:8])
    return f"{memory_type}:{'|'.join(parts[:2])}"


def memory_type_retrieval_bonus(memory_type: str) -> float:
    memory_type = str(memory_type or "general").strip().lower() or "general"
    if memory_type in ("rule", "fact", "preference", "goal"):
        return 0.1
    if memory_type in ("project", "decision", "correction", "knowledge"):
        return 0.08
    return 0.04


def normalize_retrieval_text(text: str) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", str(text or "").lower())


def token_overlap_score(query: str, stored: str) -> float:
    ascii_query = {token.lower() for token in re.findall(r"[A-Za-z0-9]{2,}", str(query or ""))}
    ascii_stored = {token.lower() for token in re.findall(r"[A-Za-z0-9]{2,}", str(stored or ""))}
    cjk_query = {token for token in re.findall(r"[\u4e00-\u9fff]{2,8}", str(query or ""))}
    cjk_stored = {token for token in re.findall(r"[\u4e00-\u9fff]{2,8}", str(stored or ""))}

    scores = []
    if ascii_query:
        scores.append(len(ascii_query & ascii_stored) / max(len(ascii_query), 1))
    if cjk_query:
        scores.append(len(cjk_query & cjk_stored) / max(len(cjk_query), 1))
    return max(scores, default=0.0)


def relevance(query: str, stored: str) -> float:
    qc = normalize_retrieval_text(query)
    sc = normalize_retrieval_text(stored)
    if not qc or not sc:
        return 0.0

    if qc == sc:
        return 1.0

    direct = 0.88 if (qc in sc or sc in qc) else 0.0
    bigram = 0.0
    if len(qc) >= 2:
        grams = {qc[i:i + 2] for i in range(len(qc) - 1)}
        if grams:
            hits = sum(1 for gram in grams if gram in sc)
            bigram = hits / max(len(grams), 1)

    overlap = token_overlap_score(query, stored)
    return max(direct, bigram * 0.76, overlap * 0.72)


def freshness(created_at: str) -> float:
    try:
        days = (datetime.now() - datetime.fromisoformat(created_at)).total_seconds() / 86400
        return 1.0 / (1.0 + 0.1 * days)
    except Exception:
        return 0.5
