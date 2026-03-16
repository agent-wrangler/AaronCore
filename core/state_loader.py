# state_loader - 状态加载、历史记录、文档索引、路径常量
# 从 agent_final.py 提取，消除单文件过长问题

from datetime import datetime, timedelta
from pathlib import Path

from core.json_store import load_json, write_json, load_json_store

# ── 路径常量 ──────────────────────────────────────────────
ENGINE_DIR = Path(__file__).resolve().parent.parent
CORE_DIR = ENGINE_DIR / "core"
PRIMARY_STATE_DIR = ENGINE_DIR / "memory_db"
LEGACY_STATE_DIR = ENGINE_DIR / "memory"
LOGS_DIR = ENGINE_DIR / "logs"
HTML_FILE = ENGINE_DIR / "output.html"
RESTORED_OUTPUT_JS_FILE = ENGINE_DIR / ".tmp_settings_check.js"
LLM_CONFIG_FILE = ENGINE_DIR / "brain" / "llm_config.json"

PRIMARY_HISTORY_FILE = PRIMARY_STATE_DIR / "msg_history.json"
LEGACY_HISTORY_FILE = LEGACY_STATE_DIR / "msg_history.json"
PRIMARY_STATS_FILE = PRIMARY_STATE_DIR / "stats.json"
LEGACY_STATS_FILE = LEGACY_STATE_DIR / "stats.json"
LEGACY_L3_SKILL_ARCHIVE_FILE = PRIMARY_STATE_DIR / "long_term_legacy_skill_logs.json"
DOCS_DIR = ENGINE_DIR / "docs"

# ── 注入依赖（由 agent_final 调用 init() 设置） ──────────
_debug_write = lambda stage, data: None
_get_all_skills = lambda: {}
_nova_core_ready = False


def init(*, debug_write=None, get_all_skills=None, nova_core_ready=False):
    global _debug_write, _get_all_skills, _nova_core_ready
    if debug_write:
        _debug_write = debug_write
    if get_all_skills:
        _get_all_skills = get_all_skills
    _nova_core_ready = nova_core_ready


# ── Legacy 清理 ───────────────────────────────────────────
_LONG_TERM_CLEANUP_DONE = False


def event_text(item: dict) -> str:
    if not isinstance(item, dict):
        return ""
    return str(item.get("summary") or item.get("content") or "").strip()


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


def ensure_long_term_clean():
    global _LONG_TERM_CLEANUP_DONE
    if _LONG_TERM_CLEANUP_DONE:
        return

    l3_file = PRIMARY_STATE_DIR / "long_term.json"
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
        archived_at = datetime.now().isoformat()
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


# ── 配置加载 ──────────────────────────────────────────────

def load_current_model() -> str:
    llm_conf = load_json(LLM_CONFIG_FILE, {})
    if isinstance(llm_conf, dict):
        return llm_conf.get("model", "unknown")
    return "unknown"


# ── 文档索引 ──────────────────────────────────────────────

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


# ── 消息历史 ──────────────────────────────────────────────

def load_msg_history():
    history = load_json_store(PRIMARY_HISTORY_FILE, LEGACY_HISTORY_FILE, [])
    if not isinstance(history, list):
        return []

    now = datetime.now()
    cutoff = now - timedelta(days=7)
    cleaned = []
    for item in history:
        try:
            item_time = datetime.fromisoformat(item.get("time", "2020-01-01"))
            if item_time > cutoff:
                cleaned.append(item)
        except Exception:
            cleaned.append(item)

    if len(cleaned) != len(history):
        write_json(PRIMARY_HISTORY_FILE, cleaned)
    return cleaned


def save_msg_history(history):
    write_json(PRIMARY_HISTORY_FILE, history)


def get_recent_messages(history, limit=6):
    return history[-limit:]


# ── 层级数据加载 ─────────────────────────────────────────

def load_l3_long_term(limit=8):
    ensure_long_term_clean()
    items = load_json(PRIMARY_STATE_DIR / "long_term.json", [])
    # L3 只存经历：发生过的事件、里程碑、重要时刻。
    # 用户事实/偏好/交互规则 → L4 persona.json
    # 知识内容 → L8 knowledge_base.json
    # 这里用白名单，只有经历类 type 才会被加载到 prompt 里。
    ALLOWED_TYPES = {"event", "milestone", "general"}
    out = []
    for item in items[-limit:]:
        if is_legacy_l3_skill_log(item):
            continue
        item_type = str(item.get("type") or "").strip()
        if item_type and item_type not in ALLOWED_TYPES:
            continue
        summary = event_text(item)
        if summary:
            out.append(summary)
    return out


def load_l4_persona():
    local_persona = load_json(PRIMARY_STATE_DIR / "persona.json", {})

    # interaction_rules 已经直接存在 persona.json 里了，
    # 不再从 long_term.json 交叉抽取 style 规则，避免 L3/L4 职责混淆。
    interaction_rules = local_persona.get("interaction_rules") or []

    return {
        "local_persona": local_persona,
        "style_rules": interaction_rules[-8:] if isinstance(interaction_rules, list) else [],
    }


def load_l5_knowledge():
    knowledge = load_json(PRIMARY_STATE_DIR / "knowledge.json", [])
    knowledge_base = load_json(PRIMARY_STATE_DIR / "knowledge_base.json", [])
    skills = _get_all_skills() if _nova_core_ready else {}
    return {
        "knowledge": knowledge[-10:],
        "knowledge_base": knowledge_base[-10:],
        "skills": {k: {"name": v.get("name", k), "keywords": v.get("keywords", [])} for k, v in skills.items()},
    }


# ── 统计 ─────────────────────────────────────────────────

def load_stats_data():
    stats = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "total_requests": 0,
        "cache_write_tokens": 0,
        "cache_read_tokens": 0,
        "model": load_current_model(),
        "last_used": "",
        "by_scene": {},
    }
    saved = load_json_store(PRIMARY_STATS_FILE, LEGACY_STATS_FILE, {})
    if isinstance(saved, dict):
        stats.update(saved)
    stats["model"] = load_current_model()
    # 兼容旧格式：补 by_scene
    if "by_scene" not in stats:
        stats["by_scene"] = {}
    return stats


def record_stats(input_tokens: int = 0, output_tokens: int = 0, scene: str = "chat",
                 cache_write: int = 0, cache_read: int = 0):
    """记录真实 token 消耗，按场景分类，含缓存统计"""
    inp = max(int(input_tokens), 0)
    out = max(int(output_tokens), 0)
    cw = max(int(cache_write), 0)
    cr = max(int(cache_read), 0)
    total = inp + out
    stats = load_stats_data()
    stats["input_tokens"] = stats.get("input_tokens", 0) + inp
    stats["output_tokens"] = stats.get("output_tokens", 0) + out
    stats["total_tokens"] = stats.get("total_tokens", 0) + total
    stats["total_requests"] = stats.get("total_requests", 0) + 1
    stats["cache_write_tokens"] = stats.get("cache_write_tokens", 0) + cw
    stats["cache_read_tokens"] = stats.get("cache_read_tokens", 0) + cr
    stats["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    # 按场景累计
    by_scene = stats.setdefault("by_scene", {})
    sc = by_scene.setdefault(scene, {"requests": 0, "tokens": 0})
    sc["requests"] = sc.get("requests", 0) + 1
    sc["tokens"] = sc.get("tokens", 0) + total
    write_json(PRIMARY_STATS_FILE, stats)
    return stats


def record_memory_stats(l2_searches: int = 0, l2_hits: int = 0,
                        l8_searches: int = 0, l8_hits: int = 0,
                        l1_count: int = 0, l3_count: int = 0,
                        l4_available: bool = False, l5_count: int = 0):
    """记录本地记忆指标（全量层可用性 + 检索层命中率）"""
    stats = load_stats_data()
    mem = stats.get("memory")
    if not isinstance(mem, dict):
        mem = {
            "l2_searches": 0, "l2_hits": 0,
            "l8_searches": 0, "l8_hits": 0,
            "total_queries": 0,
            "full_layer_available": 0,
            "l1_count": 0, "l3_count": 0, "l4_available": 0, "l5_count": 0,
        }
    mem["l2_searches"] = mem.get("l2_searches", 0) + max(int(l2_searches), 0)
    mem["l2_hits"] = mem.get("l2_hits", 0) + max(int(l2_hits), 0)
    mem["l8_searches"] = mem.get("l8_searches", 0) + max(int(l8_searches), 0)
    mem["l8_hits"] = mem.get("l8_hits", 0) + max(int(l8_hits), 0)
    mem["total_queries"] = mem.get("total_queries", 0) + 1
    # 全量层可用性：L1/L3/L4/L5 有数据的层数（满分 4）
    layers_up = (1 if l1_count > 0 else 0) + (1 if l3_count > 0 else 0) + \
                (1 if l4_available else 0) + (1 if l5_count > 0 else 0)
    mem["full_layer_available"] = mem.get("full_layer_available", 0) + layers_up
    # 最新一次的数据量快照
    mem["l1_count"] = l1_count
    mem["l3_count"] = l3_count
    mem["l4_available"] = 1 if l4_available else 0
    mem["l5_count"] = l5_count
    stats["memory"] = mem
    write_json(PRIMARY_STATS_FILE, stats)


def reset_stats():
    """清零所有统计"""
    stats = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "total_requests": 0,
        "cache_write_tokens": 0,
        "cache_read_tokens": 0,
        "model": load_current_model(),
        "last_used": "",
        "by_scene": {},
        "memory": {
            "l2_searches": 0, "l2_hits": 0,
            "l8_searches": 0, "l8_hits": 0,
            "total_queries": 0, "full_layer_available": 0,
            "l1_count": 0, "l3_count": 0, "l4_available": 0, "l5_count": 0,
        },
    }
    write_json(PRIMARY_STATS_FILE, stats)
    return stats
