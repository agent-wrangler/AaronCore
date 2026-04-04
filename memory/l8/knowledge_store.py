"""Knowledge entry storage/query helpers for L8."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

_SCENE_PREFIX_MAP = {
    "\u5de5\u5177\u5e94\u7528": "\u6280\u80fd\u5b66\u4e60",
    "\u5185\u5bb9\u521b\u4f5c": "\u521b\u4f5c\u7ea0\u504f",
    "\u7cfb\u7edf\u80fd\u529b": "\u8def\u7531\u4fee\u6b63",
    "\u7cfb\u7edf\u529f\u80fd": "\u80fd\u529b\u8865\u5145",
    "\u4eba\u7269\u89d2\u8272": "\u4eba\u8bbe\u8c03\u6574",
    "\u81ea\u4e3b\u5b66\u4e60": "\u81ea\u52a8\u5b66\u4e60",
}


def classify_l8_entry_kind(entry: dict) -> str:
    entry_type = str(entry.get("type") or entry.get("source") or "").strip()
    source = str(entry.get("source") or "").strip()
    if entry_type == "feedback_relearn" or source == "feedback_relearn":
        return "feedback_relearn"
    if source == "l2_crystallize":
        return "dialogue_crystal"
    return "self_learned"


def should_surface_knowledge_entry(
    entry: dict,
    *,
    entry_has_reusable_knowledge: Callable[[dict], bool],
    is_registered_skill_name: Callable[[str], bool],
) -> bool:
    if not isinstance(entry, dict):
        return False
    if not entry_has_reusable_knowledge(entry):
        return False

    primary_scene = str(entry.get("\u4e00\u7ea7\u573a\u666f") or "").strip()
    core_skill = str(entry.get("\u6838\u5fc3\u6280\u80fd") or entry.get("name") or "").strip()
    if (
        primary_scene == "\u5de5\u5177\u5e94\u7528"
        and core_skill
        and not is_registered_skill_name(core_skill)
    ):
        return False

    entry_type = str(entry.get("type") or entry.get("source") or "").strip()
    if entry_type == "feedback_relearn":
        return False
    return True


def should_show_l8_timeline_entry(
    entry: dict,
    *,
    entry_has_reusable_knowledge: Callable[[dict], bool],
    classify_entry_kind: Callable[[dict], str],
) -> bool:
    if not entry_has_reusable_knowledge(entry):
        return False
    if classify_entry_kind(entry) == "feedback_relearn":
        return False
    return True


def prune_l8_garbage_entries(
    *,
    make_backup: bool = True,
    reason: str = "manual_cleanup",
    file_lock,
    load_json,
    write_json,
    knowledge_base_file: Path,
    should_surface_knowledge_entry_fn: Callable[[dict], bool],
    debug_write: Callable[[str, dict], None],
) -> dict:
    with file_lock:
        data = load_json(knowledge_base_file, [])
        if not isinstance(data, list):
            data = []

        original_count = len(data)
        kept = []
        removed = []
        for item in data:
            if isinstance(item, dict) and should_surface_knowledge_entry_fn(item):
                kept.append(item)
            else:
                removed.append(item)

        backup_path = ""
        if make_backup and knowledge_base_file.exists():
            backup_name = (
                f"{knowledge_base_file.stem}.backup_"
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                f"{knowledge_base_file.suffix}"
            )
            backup_file = knowledge_base_file.with_name(backup_name)
            shutil.copy2(knowledge_base_file, backup_file)
            backup_path = str(backup_file)

        write_json(knowledge_base_file, kept[-500:])

    removed_queries = []
    for item in removed[:10]:
        if isinstance(item, dict):
            removed_queries.append(str(item.get("query") or item.get("name") or "")[:80])

    result = {
        "success": True,
        "reason": reason,
        "backup_created": bool(backup_path),
        "backup_path": backup_path,
        "original_count": original_count,
        "kept_count": len(kept[-500:]),
        "removed_count": len(removed),
        "removed_queries": removed_queries,
    }
    debug_write("l8_prune", result)
    return result


def find_relevant_knowledge(
    query: str,
    *,
    limit: int = 3,
    min_score: int = 12,
    touch: bool = False,
    load_json,
    write_json,
    knowledge_base_file: Path,
    file_lock,
    normalize_query: Callable[[str], str],
    should_surface_knowledge_entry_fn: Callable[[dict], bool],
    llm_rank_knowledge_candidates: Callable[[str, list[tuple[int, dict]]], list[tuple[int, int, dict]]],
    entry_sort_key: Callable[[dict], tuple[int, str]],
    clean_text: Callable[[str, int | None], str],
) -> list[dict]:
    entries = load_json(knowledge_base_file, [])
    if not isinstance(entries, list):
        return []

    normalized_query = normalize_query(query)
    if not normalized_query:
        return []

    direct_matches = []
    semantic_candidates = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        if not should_surface_knowledge_entry_fn(entry):
            continue
        entry_query = normalize_query(entry.get("query", ""))
        if entry_query and entry_query == normalized_query:
            direct_matches.append((100, index, entry))
            continue
        semantic_candidates.append((index, entry))

    scored = list(direct_matches)
    for score, index, entry in llm_rank_knowledge_candidates(query, semantic_candidates):
        if score >= min_score:
            scored.append((score, index, entry))

    scored.sort(key=lambda item: (item[0], entry_sort_key(item[2])), reverse=True)

    if touch and scored:
        for _, index, entry in scored[:limit]:
            entry["hit_count"] = int(entry.get("hit_count", 0) or 0) + 1
            entry["last_used"] = datetime.now().isoformat()
            entries[index] = entry
        with file_lock:
            write_json(knowledge_base_file, entries[-500:])

    results = []
    for _, _, entry in scored[:limit]:
        summary = clean_text(entry.get("summary") or entry.get("\u5e94\u7528\u793a\u4f8b") or "", 160)
        if not summary:
            continue
        results.append(
            {
                "name": entry.get("name")
                or entry.get("\u4e8c\u7ea7\u573a\u666f")
                or entry.get("query")
                or "\u5df2\u5b66\u77e5\u8bc6",
                "query": entry.get("query") or "",
                "summary": summary,
                "created_at": entry.get("created_at")
                or entry.get("\u6700\u8fd1\u4f7f\u7528\u65f6\u95f4")
                or "",
            }
        )
    return results


def save_learned_knowledge(
    query: str,
    summary: str,
    results: list[dict],
    *,
    source: str = "bing_rss",
    extra_fields: dict | None = None,
    feedback_scene: str = "",
    route_result: dict | None = None,
    strip_think_content: Callable[[str], str],
    check_entry_quality: Callable[[str, str], str],
    clean_text: Callable[[str, int | None], str],
    normalize_query: Callable[[str], str],
    sanitize_extra_fields: Callable[[dict | None], dict],
    infer_primary_scene: Callable[..., str],
    load_json,
    write_json,
    knowledge_base_file: Path,
    file_lock,
) -> dict:
    summary = strip_think_content(summary)
    reject_reason = check_entry_quality(query, summary)
    if reject_reason:
        print(f"[L8] Rejected: {reject_reason} | query={query[:40]}")
        return {"saved": False, "reason": reject_reason}

    now = datetime.now()
    normalized_query = normalize_query(query)
    extra = sanitize_extra_fields(extra_fields)
    primary_scene = infer_primary_scene(query, feedback_scene=feedback_scene, route_result=route_result)
    scene_prefix = _SCENE_PREFIX_MAP.get(primary_scene, "\u81ea\u52a8\u5b66\u4e60")

    with file_lock:
        data = load_json(knowledge_base_file, [])
        if not isinstance(data, list):
            data = []

        existing = None
        for item in data:
            if normalize_query(item.get("query", "")) == normalized_query:
                existing = item
                break

        if existing is None:
            existing = {
                "id": f"l8_{now.strftime('%Y%m%d_%H%M%S_%f')}",
                "source": source,
                "type": "knowledge",
                "query": query,
                "name": clean_text(query, 24) or "\u5df2\u5b66\u77e5\u8bc6",
                "summary": summary,
                "results": results[:3],
                "created_at": now.isoformat(),
                "last_used": now.isoformat(),
                "hit_count": 0,
                "\u4e00\u7ea7\u573a\u666f": primary_scene,
                "\u4e8c\u7ea7\u573a\u666f": f"{scene_prefix}-{clean_text(query, 12)}",
                "\u6838\u5fc3\u6280\u80fd": clean_text(query, 18) or "\u65b0\u77e5\u8bc6",
                "\u5e94\u7528\u793a\u4f8b": summary,
                "\u6700\u8fd1\u4f7f\u7528\u65f6\u95f4": now.strftime("%Y-%m-%d %H:%M:%S"),
                "\u89e6\u53d1\u5668\u51fd\u6570": "l8_web_search",
            }
            existing.update(extra)
            data.append(existing)
        else:
            existing["source"] = source or existing.get("source", "bing_rss")
            existing["summary"] = summary or existing.get("summary", "")
            existing["results"] = results[:3] or existing.get("results", [])
            existing["last_used"] = now.isoformat()
            existing.update(extra)
            existing["\u6700\u8fd1\u4f7f\u7528\u65f6\u95f4"] = now.strftime("%Y-%m-%d %H:%M:%S")
            existing["\u5e94\u7528\u793a\u4f8b"] = summary or existing.get("\u5e94\u7528\u793a\u4f8b", "")

        existing.pop("keywords", None)
        existing.pop("trigger", None)
        write_json(knowledge_base_file, data[-500:])
        return existing
