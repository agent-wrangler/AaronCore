from pathlib import Path
import re

from storage import content_store as _content_store
from storage import history_store as _history_store
from storage import stats_store as _stats_store
from storage import task_files as _task_files
from storage.json_store import load_json, write_json
from storage.model_config import load_current_model as _default_load_current_model
from storage.paths import (
    AUTOLEARN_CONFIG_FILE,
    CONTENT_STORE_DIR,
    CONTENT_PROJECTS_FILE,
    CONTENT_TOPIC_REGISTRY_FILE,
    CORE_DIR,
    CU_DEBUG_LOG_FILE,
    DEFAULT_L1_RECENT_TOKEN_BUDGET,
    DOCS_DIR,
    ENGINE_DIR,
    FEEDBACK_RULES_FILE,
    FILE_EXPORT_STATE_FILE,
    GROWTH_FILE,
    HTML_FILE,
    KNOWLEDGE_BASE_FILE,
    KNOWLEDGE_FILE,
    LAB_DIR,
    LEGACY_HISTORY_FILE,
    LEGACY_L3_SKILL_ARCHIVE_FILE,
    LEGACY_STATE_DIR,
    LEGACY_STATS_FILE,
    LLM_CONFIG_FILE,
    LOGS_DIR,
    LONG_TERM_FILE,
    MCP_REGISTRY_CACHE_FILE,
    MCP_SERVERS_FILE,
    MEMORY_STORE_DIR,
    PERSONA_FILE,
    PRIMARY_HISTORY_FILE,
    PRIMARY_STATE_DIR,
    PRIMARY_STATS_FILE,
    QQ_MONITOR_DEBUG_LOG_FILE,
    QQ_MONITOR_STATE_FILE,
    QUERY_CACHE_FILE,
    RESTORED_OUTPUT_JS_FILE,
    RUNTIME_STORE_DIR,
    SELF_REPAIR_REPORTS_FILE,
    SKILL_STORE_FILE,
    STATE_DATA_DIR,
    TASK_PROJECTS_FILE,
    TASK_RELATIONS_FILE,
    TASKS_FILE,
    TASK_STORE_DIR,
    TOOL_CALL_CONFIG_FILE,
)


_debug_write = lambda stage, data: None
_get_all_skills = lambda: {}
_nova_core_ready = False

# Keep this as a module variable so tests can monkeypatch it on the compatibility facade.
load_current_model = _default_load_current_model


def init(*, debug_write=None, get_all_skills=None, nova_core_ready=False):
    global _debug_write, _get_all_skills, _nova_core_ready
    if debug_write:
        _debug_write = debug_write
    if get_all_skills:
        _get_all_skills = get_all_skills
    _nova_core_ready = nova_core_ready


def event_text(item: dict) -> str:
    if not isinstance(item, dict):
        return ""
    text = str(item.get("event") or item.get("summary") or item.get("content") or "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    if not text:
        return ""
    if any(marker in text for marker in ("根据对话上下文", "作为AI助手", "系统提示中可能有时间信息", "让我们检查")):
        return ""
    return text


def is_legacy_l3_skill_log(item: dict) -> bool:
    text = event_text(item)
    if not text:
        return False
    return "场景使用" in text and "技能" in text and ("执行成功" in text or "执行失败" in text)


def _legacy_l3_log_key(item: dict) -> str:
    if not isinstance(item, dict):
        return ""
    time_key = str(item.get("time") or item.get("timestamp") or item.get("created_at") or "").strip()
    return f"{time_key}|{event_text(item)}"


_LONG_TERM_CLEANUP_DONE = False


def ensure_long_term_clean():
    global _LONG_TERM_CLEANUP_DONE
    if _LONG_TERM_CLEANUP_DONE:
        return

    l3_file = LONG_TERM_FILE
    data = load_json(l3_file, [])
    if not isinstance(data, list):
        _LONG_TERM_CLEANUP_DONE = True
        return

    kept = []
    moved = []
    for item in data:
        if isinstance(item, dict) and is_legacy_l3_skill_log(item):
            moved.append(item)
        else:
            kept.append(item)

    if moved:
        archived = load_json(LEGACY_L3_SKILL_ARCHIVE_FILE, [])
        if not isinstance(archived, list):
            archived = []

        known = {_legacy_l3_log_key(item) for item in archived if isinstance(item, dict)}
        archived_at = __import__("datetime").datetime.now().isoformat()
        for item in moved:
            key = _legacy_l3_log_key(item)
            if key in known:
                continue
            row = dict(item)
            row["archived_at"] = archived_at
            row["archived_reason"] = "legacy_l3_skill_execution_conflict"
            archived.append(row)
            known.add(key)

        write_json(LEGACY_L3_SKILL_ARCHIVE_FILE, archived)
        write_json(l3_file, kept)
        _debug_write(
            "l3_cleanup",
            {
                "removed_count": len(moved),
                "remaining_count": len(kept),
                "archive_file": str(LEGACY_L3_SKILL_ARCHIVE_FILE),
            },
        )

    _LONG_TERM_CLEANUP_DONE = True


def extract_doc_title(text: str, fallback: str) -> str:
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
    return fallback


def extract_doc_summary(text: str, fallback: str = "") -> str:
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return stripped[:120]
    return fallback


def build_docs_index() -> list[dict]:
    sections_config = [
        ("快速开始", [ENGINE_DIR / "README.md", DOCS_DIR / "README.md"]),
        ("总览", sorted((DOCS_DIR / "00-总览-overview").glob("*.md")) if (DOCS_DIR / "00-总览-overview").exists() else []),
        ("架构", sorted((DOCS_DIR / "10-架构-architecture").glob("*.md")) if (DOCS_DIR / "10-架构-architecture").exists() else []),
        ("前端", sorted((DOCS_DIR / "20-前端与界面-frontend").glob("*.md")) if (DOCS_DIR / "20-前端与界面-frontend").exists() else []),
        ("计划", sorted((DOCS_DIR / "30-计划与路线-plans").glob("*.md")) if (DOCS_DIR / "30-计划与路线-plans").exists() else []),
    ]

    sections = []
    for section_name, paths in sections_config:
        docs = []
        for path in paths:
            if not isinstance(path, Path) or not path.exists() or path.suffix.lower() != ".md":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            rel_path = path.relative_to(ENGINE_DIR).as_posix()
            docs.append(
                {
                    "path": rel_path,
                    "title": extract_doc_title(text, path.stem),
                    "summary": extract_doc_summary(text, path.stem),
                }
            )
        if docs:
            sections.append({"section": section_name, "docs": docs})
    return sections


def resolve_doc_path(path_value: str) -> Path | None:
    target = str(path_value or "").strip().replace("\\", "/")
    if not target or ".." in target:
        return None

    allowed = {}
    for section in build_docs_index():
        for item in section.get("docs", []):
            allowed[item.get("path", "")] = ENGINE_DIR / item.get("path", "")

    return allowed.get(target)


def _sync_history_store():
    _history_store.PRIMARY_HISTORY_FILE = PRIMARY_HISTORY_FILE
    _history_store.LEGACY_HISTORY_FILE = LEGACY_HISTORY_FILE


def _sync_content_store():
    _content_store.CONTENT_PROJECTS_FILE = CONTENT_PROJECTS_FILE
    _content_store.CONTENT_TOPIC_REGISTRY_FILE = CONTENT_TOPIC_REGISTRY_FILE


def _sync_task_files():
    _task_files.TASK_PROJECTS_FILE = TASK_PROJECTS_FILE
    _task_files.TASKS_FILE = TASKS_FILE
    _task_files.TASK_RELATIONS_FILE = TASK_RELATIONS_FILE


def _sync_stats_store():
    _stats_store.PRIMARY_STATS_FILE = PRIMARY_STATS_FILE
    _stats_store.LEGACY_STATS_FILE = LEGACY_STATS_FILE
    _stats_store.load_current_model = load_current_model


def load_msg_history():
    _sync_history_store()
    return _history_store.load_msg_history()


def save_msg_history(history):
    _sync_history_store()
    return _history_store.save_msg_history(history)


def get_recent_messages(history, limit=6, max_tokens=None):
    return _history_store.get_recent_messages(history, limit=limit, max_tokens=max_tokens)


def load_content_projects():
    _sync_content_store()
    return _content_store.load_content_projects()


def save_content_projects(projects):
    _sync_content_store()
    return _content_store.save_content_projects(projects)


def load_content_topic_registry():
    _sync_content_store()
    return _content_store.load_content_topic_registry()


def save_content_topic_registry(registry):
    _sync_content_store()
    return _content_store.save_content_topic_registry(registry)


def load_task_projects():
    _sync_task_files()
    return _task_files.load_task_projects()


def save_task_projects(projects):
    _sync_task_files()
    return _task_files.save_task_projects(projects)


def load_tasks():
    _sync_task_files()
    return _task_files.load_tasks()


def save_tasks(tasks):
    _sync_task_files()
    return _task_files.save_tasks(tasks)


def load_task_relations():
    _sync_task_files()
    return _task_files.load_task_relations()


def save_task_relations(relations):
    _sync_task_files()
    return _task_files.save_task_relations(relations)


def load_l3_long_term(limit=8):
    ensure_long_term_clean()
    items = load_json(LONG_TERM_FILE, [])
    allowed_types = {"event", "milestone", "general"}
    out = []
    for item in items[-limit:]:
        if is_legacy_l3_skill_log(item):
            continue
        item_type = str(item.get("type") or "").strip()
        if item_type and item_type not in allowed_types:
            continue
        summary = event_text(item)
        if summary:
            out.append(summary)
    return out


def load_l4_persona():
    local_persona = load_json(PERSONA_FILE, {})
    interaction_rules = local_persona.get("interaction_rules") or []
    payload = dict(local_persona) if isinstance(local_persona, dict) else {}
    payload["local_persona"] = local_persona if isinstance(local_persona, dict) else {}
    payload["style_rules"] = interaction_rules[-8:] if isinstance(interaction_rules, list) else []
    return payload


def load_l5_knowledge():
    knowledge = load_json(KNOWLEDGE_FILE, [])
    knowledge_base = load_json(KNOWLEDGE_BASE_FILE, [])
    skills = _get_all_skills() if _nova_core_ready else {}
    return {
        "knowledge": knowledge[-10:],
        "knowledge_base": knowledge_base[-10:],
        "skills": {k: {"name": v.get("name", k), "keywords": v.get("keywords", [])} for k, v in skills.items()},
    }


def load_stats_data():
    _sync_stats_store()
    return _stats_store.load_stats_data()


def migrate_stats_data(stats: dict) -> tuple[dict, bool]:
    return _stats_store.migrate_stats_data(stats)


def record_stats(input_tokens: int = 0, output_tokens: int = 0, scene: str = "chat",
                 cache_write: int = 0, cache_read: int = 0, model: str = ""):
    _sync_stats_store()
    return _stats_store.record_stats(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        scene=scene,
        cache_write=cache_write,
        cache_read=cache_read,
        model=model,
    )


MODEL_PRICES = _stats_store.MODEL_PRICES


def get_model_price(model_name: str) -> dict:
    return _stats_store.get_model_price(model_name)


def record_memory_stats(l2_searches: int = 0, l2_hits: int = 0,
                        l8_searches: int = 0, l8_hits: int = 0,
                        l3_queries: int = 0, l3_hits: int = 0,
                        l4_queries: int = 0, l4_hits: int = 0,
                        l5_queries: int = 0, l5_hits: int = 0,
                        l6_hits: int = 0, l7_hits: int = 0,
                        l1_count: int = 0, l3_count: int = 0,
                        l4_available: bool = False, l5_count: int = 0,
                        cod_used=None, count_query: bool = True):
    _sync_stats_store()
    return _stats_store.record_memory_stats(
        l2_searches=l2_searches,
        l2_hits=l2_hits,
        l8_searches=l8_searches,
        l8_hits=l8_hits,
        l3_queries=l3_queries,
        l3_hits=l3_hits,
        l4_queries=l4_queries,
        l4_hits=l4_hits,
        l5_queries=l5_queries,
        l5_hits=l5_hits,
        l6_hits=l6_hits,
        l7_hits=l7_hits,
        l1_count=l1_count,
        l3_count=l3_count,
        l4_available=l4_available,
        l5_count=l5_count,
        cod_used=cod_used,
        count_query=count_query,
    )


def reset_stats():
    _sync_stats_store()
    return _stats_store.reset_stats()
