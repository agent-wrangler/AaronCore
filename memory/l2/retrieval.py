"""Retrieval helpers for L2 memory."""

from __future__ import annotations

from collections.abc import Callable


def is_low_signal_general_candidate(
    text: str,
    *,
    normalize_signal_text: Callable[[str], str],
    looks_like_low_signal_general: Callable[[str], bool],
) -> bool:
    text = str(text or "").strip()
    normalized = normalize_signal_text(text)
    if not normalized:
        return True
    if len(normalized) <= 2:
        return True
    return looks_like_low_signal_general(text)


def bump_hits(
    ids,
    *,
    load_entries: Callable[[], list],
    save_entries: Callable[[list], None],
) -> None:
    try:
        store = load_entries()
        changed = False
        for item in store:
            if item.get("id") in ids:
                item["hit_count"] = item.get("hit_count", 0) + 1
                changed = True
        if changed:
            save_entries(store)
    except Exception:
        return None


def search_relevant(
    query: str,
    *,
    limit: int = 8,
    load_entries: Callable[[], list],
    save_entries: Callable[[list], None],
    build_signal_profile: Callable[[str], set[str]],
    normalize_signature_anchor: Callable[[str], str],
    relevance: Callable[[str, str], float],
    signal_overlap: Callable[[set[str], set[str]], float],
    classify_retention_bucket: Callable[[dict], dict],
    freshness: Callable[[str], float],
    memory_type_retrieval_bonus: Callable[[str], float],
    build_retrieval_signature: Callable[[dict], str],
    is_low_signal_general_candidate: Callable[[str], bool],
) -> list:
    if not query or not query.strip():
        return []

    store = load_entries()
    if not store:
        return []

    query_profile = build_signal_profile(query)
    query_anchor = normalize_signature_anchor(query)
    scored = []
    for item in store:
        user_text = str(item.get("user_text", ""))
        ai_text = str(item.get("ai_text", ""))
        candidate_text = f"{user_text} {ai_text}".strip()
        rel = relevance(query, user_text)
        signal_score = signal_overlap(query_profile, build_signal_profile(candidate_text))
        anchor = normalize_signature_anchor(user_text)
        direct_score = 0.0
        if query_anchor and anchor:
            if query_anchor == anchor:
                direct_score = 1.0
            elif len(anchor) >= 3 and (anchor in query_anchor or query_anchor in anchor):
                direct_score = 0.82

        if rel <= 0 and signal_score <= 0 and direct_score <= 0:
            continue

        memory_type = str(item.get("memory_type") or "general").strip().lower() or "general"
        if (
            memory_type == "general"
            and is_low_signal_general_candidate(user_text)
            and direct_score < 1.0
            and signal_score < 0.7
        ):
            continue

        retention = classify_retention_bucket(item)
        if retention.get("tier") == "prune":
            continue

        frs = freshness(item.get("created_at", ""))
        hit_bonus = min(int(item.get("hit_count", 0) or 0) / 8.0, 1.0)
        retention_bonus = 0.08 if retention.get("tier") == "keep" else 0.04
        type_bonus = memory_type_retrieval_bonus(memory_type)
        final_score = (
            rel * 0.38
            + signal_score * 0.24
            + direct_score * 0.16
            + frs * 0.10
            + hit_bonus * 0.06
            + type_bonus * 0.04
            + retention_bonus * 0.02
        )
        if final_score > 0.15:
            scored.append(
                {
                    **item,
                    "relevance": round(rel, 3),
                    "signal_score": round(signal_score, 3),
                    "freshness": round(frs, 3),
                    "direct_score": round(direct_score, 3),
                    "final_score": round(final_score, 3),
                }
            )

    scored.sort(
        key=lambda item: (
            item["final_score"],
            item.get("signal_score", 0),
            item.get("direct_score", 0),
            item.get("relevance", 0),
            item.get("freshness", 0),
        ),
        reverse=True,
    )

    result = []
    seen_signatures = set()
    for item in scored:
        signature = build_retrieval_signature(item)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        result.append(item)
        if len(result) >= limit:
            break

    if result:
        bump_hits(
            [item["id"] for item in result],
            load_entries=load_entries,
            save_entries=save_entries,
        )
    return result
