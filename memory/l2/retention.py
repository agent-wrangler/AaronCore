"""Retention and cleanup helpers for L2 memory."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from storage.json_store import load_json, write_json


def entry_age_days(entry: dict, now: datetime | None = None) -> int:
    now = now or datetime.now()
    try:
        return max(0, (now - datetime.fromisoformat(str(entry.get("created_at") or ""))).days)
    except Exception:
        return 999


def looks_like_active_general_context(
    text: str,
    *,
    normalize_signal_text: Callable[[str], str],
    build_signal_profile: Callable[[str], set[str]],
) -> bool:
    text = str(text or "").strip()
    if not text:
        return False
    normalized = normalize_signal_text(text)
    profile = build_signal_profile(text)
    if len(normalized) <= 4:
        return False
    if "meta:structured" in profile or "meta:mixed_script" in profile:
        return True
    if "meta:question" in profile and len(normalized) >= 6:
        return True
    content_tokens = [
        item
        for item in profile
        if str(item).startswith("tok:") and len(item.split(":", 1)[1]) >= 3
    ]
    if len(normalized) >= 10 and len(content_tokens) >= 3:
        return True
    return False


def looks_like_low_signal_general(
    text: str,
    *,
    normalize_signal_text: Callable[[str], str],
    build_signal_profile: Callable[[str], set[str]],
) -> bool:
    text = str(text or "").strip()
    if not text:
        return True
    normalized = normalize_signal_text(text)
    if len(normalized) <= 4:
        return True
    profile = build_signal_profile(text)
    if (
        "meta:question" in profile
        or "meta:structured" in profile
        or "meta:mixed_script" in profile
    ):
        return False
    return len(normalized) <= 6


def classify_retention_bucket(
    entry: dict,
    *,
    now: datetime | None = None,
    normalize_signal_text: Callable[[str], str],
    build_signal_profile: Callable[[str], set[str]],
    looks_like_low_signal_general: Callable[[str], bool],
) -> dict:
    now = now or datetime.now()
    user_text = str(entry.get("user_text") or "").strip()
    memory_type = str(entry.get("memory_type") or "general").strip().lower() or "general"
    importance = float(entry.get("importance", 0.5) or 0.5)
    hits = int(entry.get("hit_count", 0) or 0)
    crystallized = bool(entry.get("crystallized"))
    age_days = entry_age_days(entry, now)

    tier = "compress"
    label = "压缩类"
    reason = "适合在 L2 保留轻量痕迹，不必长期保留完整原文"

    if memory_type in ("fact", "rule", "preference", "goal"):
        if crystallized:
            reason = "已分发到更高层，L2 保留轻量痕迹即可"
        else:
            tier = "keep"
            label = "永保类"
            reason = "结构化高价值信息，适合作为 L2 的核心记忆"
    elif memory_type in ("project", "decision"):
        if crystallized:
            reason = "项目或决策已被更高层接住，L2 只需保留轻量痕迹"
        elif age_days <= 30 or hits > 0 or importance >= 0.7:
            tier = "keep"
            label = "永保类"
            reason = "当前阶段仍可能持续推进，保留原始印象更稳"
        elif age_days >= 120 and hits == 0 and importance < 0.6:
            tier = "prune"
            label = "淘汰候选"
            reason = "项目或决策长期没有再被提及，继续保留价值较低"
    elif memory_type in ("knowledge", "correction", "skill_demand"):
        if crystallized:
            reason = "已完成分发或纠偏，L2 只需保留轻量痕迹"
        elif age_days >= 90 and hits == 0:
            tier = "prune"
            label = "淘汰候选"
            reason = "线索长期未复用，继续保留的收益较低"
        else:
            reason = "更适合作为短中期线索保留，而不是长期保留原始对话"
    else:
        active_general = looks_like_active_general_context(
            user_text,
            normalize_signal_text=normalize_signal_text,
            build_signal_profile=build_signal_profile,
        )
        if age_days <= 3 and active_general:
            tier = "keep"
            label = "永保类"
            reason = "最近几天仍在推进的任务型对话印象，保留原始上下文更稳"
        elif age_days <= 7 and hits >= 5 and active_general:
            tier = "keep"
            label = "永保类"
            reason = "高复用且带任务连续性信号，说明仍在承担短中期上下文"
        elif age_days <= 7 and crystallized and hits >= 3:
            tier = "keep"
            label = "永保类"
            reason = "近期一般印象已被反复命中并结晶，继续保留原始上下文更稳"
        elif age_days <= 7 and looks_like_low_signal_general(user_text):
            reason = "近期但低信号的一般对话印象，更适合压成轻量痕迹"
        elif age_days <= 7:
            reason = "近期一般对话印象，先压成轻量痕迹观察是否继续承接"
        elif age_days >= 30 and importance < 0.5 and hits == 0:
            tier = "prune"
            label = "淘汰候选"
            reason = "陈旧且未复用的一般对话印象"
        elif age_days >= 90 and importance < 0.7 and hits <= 1:
            tier = "prune"
            label = "淘汰候选"
            reason = "长期没有承接价值的一般对话印象"
        else:
            reason = "一般对话印象更适合压成轻量痕迹，避免 L2 臃肿"

    return {
        "tier": tier,
        "label": label,
        "reason": reason,
        "memory_type": memory_type,
        "importance": importance,
        "hit_count": hits,
        "crystallized": crystallized,
        "age_days": age_days,
    }


def cleanup_stale_memories(
    *,
    load_entries: Callable[[], list],
    save_entries: Callable[[list], None],
    classify_retention_bucket: Callable[..., dict],
    debug_write: Callable[[str, dict], None],
    now: datetime | None = None,
) -> dict:
    store = load_entries()
    if not store:
        return {"before": 0, "after": 0, "removed": 0}

    now = now or datetime.now()
    kept = []
    removed = 0
    retention_counts = {"keep": 0, "compress": 0, "prune": 0}

    for item in store:
        retention = classify_retention_bucket(item, now=now)
        tier = retention["tier"]
        retention_counts[tier] = retention_counts.get(tier, 0) + 1
        if tier == "prune":
            removed += 1
            continue
        kept.append(item)

    if removed > 0:
        save_entries(kept)
        debug_write(
            "l2_cleanup",
            {
                "before": len(store),
                "after": len(kept),
                "removed": removed,
                "retention_counts": retention_counts,
            },
        )

    return {
        "before": len(store),
        "after": len(kept),
        "removed": removed,
        "retention_counts": retention_counts,
    }


def prune_legacy_l2_demands_from_l5(
    l5_file: Path,
    *,
    make_backup: bool = True,
    reason: str = "manual_cleanup",
    debug_write: Callable[[str, dict], None],
) -> dict:
    store = load_json(l5_file, [])
    if not isinstance(store, list):
        return {"success": False, "reason": "invalid_knowledge_store"}

    kept = []
    removed = []
    for item in store:
        if isinstance(item, dict) and str(item.get("source") or "").strip() == "l2_demand":
            removed.append(item)
            continue
        kept.append(item)

    backup_path = None
    if removed and make_backup and l5_file.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = l5_file.with_name(f"{l5_file.stem}.backup_{stamp}{l5_file.suffix}")
        backup_path.write_text(l5_file.read_text(encoding="utf-8"), encoding="utf-8")

    if removed:
        write_json(l5_file, kept)

    result = {
        "success": True,
        "reason": reason,
        "original_count": len(store),
        "kept_count": len(kept),
        "removed_count": len(removed),
        "backup_created": bool(backup_path),
        "backup_path": str(backup_path) if backup_path else "",
        "removed_triggers": [
            str(((item.get("trigger") or [""]) if isinstance(item, dict) else [""])[0] or "")[:80]
            for item in removed
        ],
    }
    debug_write("l2_l5_legacy_prune", result)
    return result
