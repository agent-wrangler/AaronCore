"""Knowledge entry storage/query helpers for L8."""

from __future__ import annotations

import re
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
_TOOL_APPLICATION_SCENE = "\u5de5\u5177\u5e94\u7528"
_METHOD_QUERY_MARKERS = (
    "\u600e\u4e48\u67e5",
    "\u5982\u4f55\u67e5",
    "\u600e\u4e48\u7528",
    "\u5982\u4f55\u7528",
    "\u600e\u4e48\u8c03\u7528",
    "\u5982\u4f55\u8c03\u7528",
    "\u600e\u4e48\u64cd\u4f5c",
    "\u5982\u4f55\u64cd\u4f5c",
    "\u600e\u4e48\u95ee",
    "\u5982\u4f55\u95ee",
)


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip().lower()


def looks_like_method_query(query: str) -> bool:
    raw = _compact_text(query)
    if not raw:
        return False
    return any(marker in raw for marker in _METHOD_QUERY_MARKERS)


def _normalized_l5_key(value: object, *, normalize_query: Callable[[str], str]) -> str:
    return normalize_query(str(value or ""))


def _iter_l5_entry_keys(entry: dict) -> list[str]:
    values: list[str] = []
    for key in ("\u6838\u5fc3\u6280\u80fd", "name", "\u4e8c\u7ea7\u573a\u666f", "\u4e00\u7ea7\u573a\u666f"):
        value = str(entry.get(key) or "").strip()
        if value:
            values.append(value)
    triggers = entry.get("trigger")
    if isinstance(triggers, list):
        values.extend(str(item or "").strip() for item in triggers if str(item or "").strip())
    return values


def _match_l5_hint_entry(
    query: str,
    *,
    l5_entries: list[dict],
    route_result: dict | None,
    normalize_query: Callable[[str], str],
) -> dict | None:
    normalized_query = normalize_query(query)
    if not normalized_query:
        return None

    route_skill = ""
    if isinstance(route_result, dict):
        route_skill = str(route_result.get("skill") or "").strip()
    if route_skill:
        normalized_skill = normalize_query(route_skill)
        for item in l5_entries:
            if not isinstance(item, dict):
                continue
            item_skill = normalize_query(str(item.get("\u6838\u5fc3\u6280\u80fd") or item.get("name") or ""))
            if item_skill and item_skill == normalized_skill:
                return item

    if not looks_like_method_query(query):
        return None

    for item in l5_entries:
        if not isinstance(item, dict):
            continue
        for key in _iter_l5_entry_keys(item):
            normalized_key = _normalized_l5_key(key, normalize_query=normalize_query)
            if len(normalized_key) < 2:
                continue
            if normalized_key in normalized_query or normalized_query in normalized_key:
                return item
    return None


def _touch_l5_method_hint(
    query: str,
    summary: str,
    *,
    matched_entry: dict | None,
    route_result: dict | None,
    load_json,
    write_json,
    knowledge_file: Path,
    file_lock,
    clean_text: Callable[[str, int | None], str],
    normalize_query: Callable[[str], str],
) -> dict:
    now = datetime.now()
    with file_lock:
        data = load_json(knowledge_file, [])
        if not isinstance(data, list):
            data = []

        target = None
        if matched_entry is not None:
            matched_name = normalize_query(str(matched_entry.get("name") or ""))
            matched_skill = normalize_query(str(matched_entry.get("\u6838\u5fc3\u6280\u80fd") or ""))
            for item in data:
                if not isinstance(item, dict):
                    continue
                item_name = normalize_query(str(item.get("name") or ""))
                item_skill = normalize_query(str(item.get("\u6838\u5fc3\u6280\u80fd") or ""))
                if (matched_name and item_name == matched_name) or (matched_skill and item_skill == matched_skill):
                    target = item
                    break
        elif isinstance(route_result, dict):
            route_skill = str(route_result.get("skill") or "").strip()
            normalized_skill = normalize_query(route_skill)
            if normalized_skill:
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    item_skill = normalize_query(str(item.get("\u6838\u5fc3\u6280\u80fd") or item.get("name") or ""))
                    if item_skill and item_skill == normalized_skill:
                        target = item
                        break

        if target is None:
            route_skill = ""
            if isinstance(route_result, dict):
                route_skill = str(route_result.get("skill") or "").strip()
            display_name = clean_text(route_skill or query, 24) or "\u80fd\u529b\u7ebf\u7d22"
            target = {
                "source": "l5_method_hint",
                "name": display_name,
                "\u4e00\u7ea7\u573a\u666f": _TOOL_APPLICATION_SCENE,
                "\u4e8c\u7ea7\u573a\u666f": clean_text(query, 16) or "\u65b9\u6cd5\u7ecf\u9a8c",
                "\u6838\u5fc3\u6280\u80fd": route_skill or display_name,
                "trigger": [],
                "\u5e94\u7528\u793a\u4f8b": clean_text(query, 160) or clean_text(summary, 160),
                "\u4f7f\u7528\u6b21\u6570": 0,
                "learned_at": now.isoformat(),
            }
            data.append(target)

        triggers = target.get("trigger")
        if not isinstance(triggers, list):
            triggers = []
        query_trigger = clean_text(query, 24)
        existing_trigger_keys = {_normalized_l5_key(item, normalize_query=normalize_query) for item in triggers}
        normalized_trigger = _normalized_l5_key(query_trigger, normalize_query=normalize_query)
        if query_trigger and normalized_trigger and normalized_trigger not in existing_trigger_keys:
            triggers.append(query_trigger)
        target["trigger"] = triggers[-12:]

        if not str(target.get("\u5e94\u7528\u793a\u4f8b") or "").strip():
            target["\u5e94\u7528\u793a\u4f8b"] = clean_text(query, 160) or clean_text(summary, 160)

        target["\u6700\u8fd1\u4f7f\u7528\u65f6\u95f4"] = now.strftime("%Y-%m-%d %H:%M:%S")
        target["\u4f7f\u7528\u6b21\u6570"] = int(target.get("\u4f7f\u7528\u6b21\u6570", 0) or 0) + 1
        write_json(knowledge_file, data[-500:])

    target["saved"] = True
    target["layer"] = "L5"
    return target


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
    if primary_scene == _TOOL_APPLICATION_SCENE:
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
    if str(entry.get("\u4e00\u7ea7\u573a\u666f") or "").strip() == _TOOL_APPLICATION_SCENE:
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
    knowledge_file: Path,
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
    l5_entries = load_json(knowledge_file, [])
    if not isinstance(l5_entries, list):
        l5_entries = []
    matched_l5_entry = _match_l5_hint_entry(
        query,
        l5_entries=l5_entries,
        route_result=route_result,
        normalize_query=normalize_query,
    )
    if primary_scene == _TOOL_APPLICATION_SCENE or matched_l5_entry is not None:
        return _touch_l5_method_hint(
            query,
            summary,
            matched_entry=matched_l5_entry,
            route_result=route_result,
            load_json=load_json,
            write_json=write_json,
            knowledge_file=knowledge_file,
            file_lock=file_lock,
            clean_text=clean_text,
            normalize_query=normalize_query,
        )
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
        existing["saved"] = True
        existing["layer"] = "L8"
        return existing
