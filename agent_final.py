"""
NovaCore Agent Engine - Unified Entry
当前唯一主入口：8090 本地服务
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import json
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

ENGINE_DIR = Path(__file__).parent
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

LOGS_DIR.mkdir(exist_ok=True)
PRIMARY_STATE_DIR.mkdir(exist_ok=True)
debug_log = LOGS_DIR / "chat_debug.log"
_LONG_TERM_CLEANUP_DONE = False


def debug_write(stage: str, data):
    try:
        with open(debug_log, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {stage}: {json.dumps(data, ensure_ascii=False)}\n")
    except Exception:
        pass


try:
    sys.path.insert(0, str(CORE_DIR))
    from router import route as nova_route
    from executor import execute as nova_execute
    from core.skills import get_all_skills

    NOVA_CORE_READY = True
    CORE_IMPORT_ERROR = ""
except Exception as exc:
    NOVA_CORE_READY = False
    CORE_IMPORT_ERROR = str(exc)

sys.path.insert(0, str(ENGINE_DIR))
from brain import think
from core.l8_learn import (
    auto_learn as l8_auto_learn,
    auto_learn_from_feedback as l8_feedback_relearn,
    find_relevant_knowledge,
    load_autolearn_config,
    should_surface_knowledge_entry,
    should_trigger_auto_learn,
    update_autolearn_config,
)
from core.self_repair import (
    apply_self_repair_report,
    create_self_repair_report,
    find_feedback_rule,
    load_self_repair_reports,
    preview_self_repair_report,
)
from memory import add_to_history, evolve, get_history as get_text_history


def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json_store(primary: Path, legacy: Path, default):
    if primary.exists():
        return load_json(primary, default)
    if legacy.exists():
        data = load_json(legacy, default)
        try:
            write_json(primary, data)
        except Exception:
            pass
        return data
    return default


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
        debug_write(
            "l3_cleanup",
            {
                "removed_count": len(moved),
                "remaining_count": len(kept),
                "archive_file": str(LEGACY_L3_SKILL_ARCHIVE_FILE),
            },
        )

    _LONG_TERM_CLEANUP_DONE = True


def load_current_model() -> str:
    llm_conf = load_json(LLM_CONFIG_FILE, {})
    if isinstance(llm_conf, dict):
        return llm_conf.get("model", "unknown")
    return "unknown"


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


def load_l3_long_term(limit=8):
    ensure_long_term_clean()
    items = load_json(PRIMARY_STATE_DIR / "long_term.json", [])
    out = []
    for item in items[-limit:]:
        if is_legacy_l3_skill_log(item):
            continue
        summary = event_text(item)
        if summary:
            out.append(summary)
    return out


def load_l4_persona():
    local_persona = load_json(PRIMARY_STATE_DIR / "persona.json", {})
    local_rules = load_json(PRIMARY_STATE_DIR / "long_term.json", [])

    style_rules = []
    for item in local_rules[-20:]:
        summary = str(item.get("summary") or item.get("content") or "").strip()
        if summary and any(k in summary for k in ["甜心守护", "风格", "人格图谱", "主人", "不要提睡觉", "语气"]):
            style_rules.append(summary)

    return {
        "local_persona": local_persona,
        "style_rules": style_rules[-8:],
    }


def load_l5_knowledge():
    knowledge = load_json(PRIMARY_STATE_DIR / "knowledge.json", [])
    knowledge_base = load_json(PRIMARY_STATE_DIR / "knowledge_base.json", [])
    skills = get_all_skills() if NOVA_CORE_READY else {}
    return {
        "knowledge": knowledge[-10:],
        "knowledge_base": knowledge_base[-10:],
        "skills": {k: {"name": v.get("name", k), "keywords": v.get("keywords", [])} for k, v in skills.items()},
    }


def load_stats_data():
    stats = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "total_requests": 0,
        "cache_hit": 0,
        "model": load_current_model(),
        "last_used": "",
    }
    saved = load_json_store(PRIMARY_STATS_FILE, LEGACY_STATS_FILE, {})
    if isinstance(saved, dict):
        stats.update(saved)
    stats["model"] = load_current_model()
    return stats


def record_stats(tokens: int):
    safe_tokens = max(int(tokens), 0)
    stats = load_stats_data()
    stats["total_tokens"] = stats.get("total_tokens", 0) + safe_tokens
    stats["total_requests"] = stats.get("total_requests", 0) + 1
    stats["input_tokens"] = stats.get("input_tokens", 0) + max(safe_tokens // 2, 0)
    stats["output_tokens"] = stats.get("output_tokens", 0) + max(safe_tokens - (safe_tokens // 2), 0)
    stats["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    write_json(PRIMARY_STATS_FILE, stats)
    return stats


def summarize_event_value(value, limit: int = 120) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value or "").strip()
    text = text.replace("\n", " ").strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def stringify_event_value(value) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value or "").strip()
    return text.strip()


def build_persona_events(persona_data: dict, event_time: str) -> list[dict]:
    if not isinstance(persona_data, dict):
        return []

    events = []

    nova_name = str(persona_data.get("nova_name") or persona_data.get("name") or "").strip()
    if nova_name:
        events.append(
            {
                "time": event_time,
                "layer": "L4",
                "event_type": "persona",
                "title": "人格图谱",
                "content": f"立住了现在的身份：「{nova_name}」",
            }
        )

    relationship_parts = []
    user_name = str(persona_data.get("user") or "").strip()
    relationship_profile = persona_data.get("relationship_profile")
    if user_name:
        relationship_parts.append(f"默认把用户当作「{user_name}」")
    if isinstance(relationship_profile, dict):
        relationship = str(relationship_profile.get("relationship") or "").strip()
        if relationship:
            relationship_parts.append("关系是亲近、长期相伴的")
    if relationship_parts:
        events.append(
            {
                "time": event_time,
                "layer": "L4",
                "event_type": "persona",
                "title": "人格图谱",
                "content": "定下相处方式：" + "，".join(relationship_parts),
            }
        )

    style_parts = []
    speech_style = persona_data.get("speech_style")
    if isinstance(speech_style, dict):
        tones = [str(item).strip() for item in speech_style.get("tone") or [] if str(item).strip()]
        particles = [str(item).strip() for item in speech_style.get("particles") or [] if str(item).strip()]
        if tones:
            style_parts.append("语气偏向「" + "、".join(tones[:4]) + "」")
        if particles:
            style_parts.append("常挂在嘴边的语气词是「" + "、".join(particles[:4]) + "」")
    style_prompt = str(persona_data.get("style_prompt") or "").strip()
    if style_prompt and not style_parts:
        style_parts.append("说话要温柔、自然，别有系统味")
    if style_parts:
        events.append(
            {
                "time": event_time,
                "layer": "L4",
                "event_type": "persona",
                "title": "人格图谱",
                "content": "收拢说话语气：" + "，".join(style_parts),
            }
        )

    preference_parts = []
    user_profile = persona_data.get("user_profile")
    if isinstance(user_profile, dict):
        preference = str(user_profile.get("preference") or "").strip()
        dislike = str(user_profile.get("dislike") or "").strip()
        if preference:
            preference_parts.append("记住主人偏好：自然、聪明、接得住上下文")
        if dislike:
            preference_parts.append("避开模板空话和僵硬解释")
    ai_profile = persona_data.get("ai_profile")
    if isinstance(ai_profile, dict):
        positioning = str(ai_profile.get("positioning") or "").strip()
        self_view = str(ai_profile.get("self_view") or "").strip()
        if positioning or self_view:
            preference_parts.append("聊天要有陪伴感，做事也要给到结果")
    if preference_parts:
        events.append(
            {
                "time": event_time,
                "layer": "L4",
                "event_type": "persona",
                "title": "人格图谱",
                "content": "记住相处默契：" + "，".join(dict.fromkeys(preference_parts)),
            }
        )

    return events


def normalize_event_time(value, fallback: str = "2026-03-10 12:00") -> str:
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return fallback

    text = str(value or "").strip()
    if not text:
        return fallback

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return text.replace("T", " ")[:16] if len(text) >= 16 else fallback


def is_follow_up_like(msg: str) -> bool:
    text = str(msg or "").strip()
    if not text:
        return False

    if len(text) > 18:
        return False

    starters = ("那", "然后", "所以", "这个", "那个", "它", "这事", "那事", "这边", "那边")
    keywords = ("什么时候", "多久", "啥时候", "为什么", "为啥", "然后呢", "这个呢", "那个呢", "它呢", "有吗", "能吗", "行吗", "咋办", "怎么办")
    return text.startswith(starters) or any(word in text for word in keywords)


def build_dialogue_context(history: list, current_user_input: str, limit: int = 8) -> str:
    recent = []
    current_text = str(current_user_input or "").strip()

    for item in history[-limit:]:
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role not in ("user", "nova", "assistant") or not content:
            continue
        recent.append({"role": role, "content": content})

    if recent and recent[-1]["role"] == "user" and recent[-1]["content"] == current_text:
        recent = recent[:-1]

    if not recent:
        return ""

    previous_user = next((item["content"] for item in reversed(recent) if item["role"] == "user"), "")
    previous_nova = next((item["content"] for item in reversed(recent) if item["role"] in ("nova", "assistant")), "")

    lines = []
    if previous_user:
        lines.append(f"上一轮用户：{summarize_event_value(previous_user, 80)}")
    if previous_nova:
        lines.append(f"上一轮Nova：{summarize_event_value(previous_nova, 140)}")
    if is_follow_up_like(current_text) and previous_nova:
        lines.append("追问提示：当前这句话很像承接上一轮的话，请默认沿用刚才的话题直接接上，不要反问用户在指什么。")

    lines.append("最近对话：")
    for item in recent[-6:]:
        role_label = "用户" if item["role"] == "user" else "Nova"
        lines.append(f"{role_label}：{summarize_event_value(item['content'], 120)}")

    return "\n".join(lines)


def format_l8_context(items: list[dict]) -> str:
    lines = []
    for item in items or []:
        title = str(item.get("name") or item.get("query") or "已学知识").strip()
        summary = str(item.get("summary") or "").strip()
        if summary:
            lines.append(f"- {title}：{summary}")
    return "\n".join(lines)


def build_context_bundle(msg: str, history: list) -> dict:
    return {
        "l1": get_recent_messages(history, 6),
        "l2": get_recent_messages(history, 12),
        "l3": load_l3_long_term(),
        "l4": load_l4_persona(),
        "l5": load_l5_knowledge(),
        "l8": find_relevant_knowledge(msg, limit=3, touch=True),
        "dialogue_context": build_dialogue_context(history, msg),
        "user_input": msg,
    }


def build_router_prompt(bundle: dict) -> str:
    l1 = bundle["l1"]
    l3 = bundle["l3"]
    l4 = bundle["l4"]
    l5 = bundle["l5"]
    l8 = bundle.get("l8", [])
    msg = bundle["user_input"]

    return f"""
你是 NovaCore 的路由判断器。你要先判断这句话是普通聊天，还是需要技能执行。

用户输入：{msg}

L1最近对话：
{json.dumps(l1, ensure_ascii=False)}

L3长期记忆：
{json.dumps(l3, ensure_ascii=False)}

L4人格信息：
{json.dumps(l4, ensure_ascii=False)}

L5技能知识：
{json.dumps(l5, ensure_ascii=False)}

L8已学知识：
{json.dumps(l8, ensure_ascii=False)}

请只返回JSON：
{{
  "mode": "chat|skill",
  "skill": "weather|story|none",
  "reason": "简短说明",
  "rewritten_input": "如果需要技能，可重写成更适合技能执行的输入，否则原样返回"
}}
""".strip()


def normalize_route_result(route_result, user_input: str, source: str):
    if not isinstance(route_result, dict):
        return {
            "mode": "chat",
            "skill": "none",
            "reason": f"{source}_invalid",
            "rewritten_input": user_input,
            "source": source,
        }

    normalized = dict(route_result)
    normalized["mode"] = normalized.get("mode", "chat") or "chat"
    normalized["skill"] = normalized.get("skill") or "none"
    normalized["reason"] = normalized.get("reason", "") or ""
    normalized["rewritten_input"] = normalized.get("rewritten_input") or user_input
    normalized["source"] = source
    skill_name = str(normalized.get("skill") or "").strip()
    if normalized["mode"] in ("skill", "hybrid") and skill_name not in ("", "none") and not is_registered_skill_name(skill_name):
        normalized["mode"] = "chat"
        normalized["intent"] = normalized.get("intent") or "missing_skill"
        normalized["missing_skill"] = skill_name
    return normalized


def has_skill_target(route_result: dict) -> bool:
    return route_result.get("skill") not in ("none", "", None)


def is_registered_skill_name(skill_name: str) -> bool:
    name = str(skill_name or "").strip()
    if not name or name == "none" or not NOVA_CORE_READY:
        return False
    try:
        return name in get_all_skills()
    except Exception:
        return False


def looks_like_news_request(user_input: str) -> bool:
    text = str(user_input or "").strip()
    if not text:
        return False
    if any(word in text for word in ("新闻", "头条", "热点")):
        return True
    if "发生了什么" in text and any(word in text for word in ("今天", "最近", "最新")):
        return True
    return False


def detect_missing_capability_route(bundle: dict) -> dict | None:
    user_input = str((bundle or {}).get("user_input") or "").strip()
    if not user_input:
        return None

    if looks_like_news_request(user_input) and not is_registered_skill_name("news"):
        return normalize_route_result(
            {
                "mode": "skill",
                "skill": "news",
                "reason": "news_capability_missing",
                "intent": "missing_skill",
                "missing_skill": "news",
                "rewritten_input": user_input,
            },
            user_input,
            "heuristic",
        )

    return None


def detect_story_follow_up_route(bundle: dict) -> dict | None:
    user_input = str((bundle or {}).get("user_input") or "").strip()
    if not user_input:
        return None

    story_follow_up_words = ("继续讲", "接着讲", "然后呢", "后来呢", "接着呢", "讲长一点", "有点短", "太短")
    if not any(word in user_input for word in story_follow_up_words):
        return None

    recent = list((bundle or {}).get("l2") or [])
    last_assistant = ""
    for item in reversed(recent):
        if item.get("role") in ("nova", "assistant"):
            last_assistant = str(item.get("content") or "").strip()
            if last_assistant:
                break

    if "《" in last_assistant and "》" in last_assistant:
        return normalize_route_result(
            {
                "mode": "skill",
                "skill": "story",
                "reason": "story_follow_up_from_history",
                "rewritten_input": user_input,
            },
            user_input,
            "context",
        )
    return None


def llm_route(bundle: dict) -> dict:
    prompt = build_router_prompt(bundle)
    result = think(prompt, "")
    text = result.get("reply", "") if isinstance(result, dict) else str(result)
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return normalize_route_result(parsed, bundle["user_input"], "llm")
    except Exception:
        pass
    return normalize_route_result({"mode": "chat", "skill": "none", "reason": "llm_route_fallback"}, bundle["user_input"], "llm")


def resolve_route(bundle: dict) -> dict:
    user_input = bundle["user_input"]
    contextual_story_route = detect_story_follow_up_route(bundle)
    if contextual_story_route is not None:
        debug_write("context_story_route", contextual_story_route)
        return contextual_story_route

    missing_capability_route = detect_missing_capability_route(bundle)
    if missing_capability_route is not None:
        debug_write("missing_capability_route", missing_capability_route)
        return missing_capability_route

    core_route = None

    if NOVA_CORE_READY:
        try:
            core_route = normalize_route_result(nova_route(user_input), user_input, "core")
            debug_write("core_route", core_route)
            if has_skill_target(core_route):
                return core_route
            if core_route.get("mode") == "chat" and float(core_route.get("confidence", 0) or 0) >= 0.9:
                return core_route
        except Exception as exc:
            debug_write("core_route_error", {"error": str(exc)})

    llm_candidate = llm_route(bundle)
    debug_write("llm_route", llm_candidate)
    if has_skill_target(llm_candidate):
        return llm_candidate
    if core_route is not None:
        return core_route
    return llm_candidate


def _build_learning_summary(config: dict) -> str:
    if not bool(config.get("enabled", True)):
        return "自动学习已关闭，反馈只会停留在当前会话里。"
    if bool(config.get("allow_feedback_relearn", True)):
        if bool(config.get("allow_web_search", True)) and bool(config.get("allow_knowledge_write", True)):
            return "会先记住负反馈，必要时补学并写回知识库。"
        if bool(config.get("allow_knowledge_write", True)):
            return "会先记住负反馈，并把纠偏结论沉淀到知识库。"
        return "会先记住负反馈，但暂时不会长期沉淀到知识库。"
    return "现在不会把负反馈沉淀成纠偏记录。"


def _build_repair_summary(config: dict) -> str:
    planning_enabled = bool(config.get("allow_self_repair_planning", True))
    test_run_enabled = bool(config.get("allow_self_repair_test_run", True))
    auto_apply_enabled = bool(config.get("allow_self_repair_auto_apply", True))
    apply_mode = str(config.get("self_repair_apply_mode") or "confirm").strip() or "confirm"

    if not planning_enabled:
        return "目前只做学习纠偏，不会主动整理修复方案。"
    if not test_run_enabled:
        return "会先整理修法，但动手前还不会自动自查。"
    if not auto_apply_enabled:
        return "会先整理修法并自己检查，真正动手前先停下来给你看。"
    if apply_mode == "suggest":
        return "低风险会自己继续，中高风险先给你看方案。"
    return "低风险会自己继续，中高风险只确认一次。"


def _build_latest_status_summary(latest: dict, latest_preview: dict, latest_apply: dict) -> str:
    apply_status = str((latest_apply or {}).get("status") or "").strip()
    if apply_status:
        if apply_status in {"applied", "applied_without_validation"} and bool(latest_apply.get("auto_applied")):
            return "最近一次反馈已经在后台自动落成修改。"
        if apply_status == "applied":
            return "最近一次反馈已经真正动手修改并通过了自查。"
        if apply_status == "applied_without_validation":
            return "最近一次反馈已经动手修改，但还没有跑自查。"
        if apply_status.startswith("rolled_back"):
            return "最近一次尝试已经自动回滚，没有把坏补丁留在源码里。"
        return "最近一次反馈已经走到动手阶段，但结果还需要进一步确认。"

    preview_status = str((latest_preview or {}).get("status") or "").strip()
    if preview_status == "preview_ready":
        if bool(latest_preview.get("auto_apply_ready")):
            return "最近一次反馈已经整理成低风险补丁，会继续在后台往下处理。"
        if bool(latest_preview.get("confirmation_required", True)):
            return "最近一次反馈已经整理出改法，只等一次确认。"
        return "最近一次反馈已经整理出改法，这次不用额外确认。"

    latest_status = str((latest or {}).get("status") or "").strip()
    if latest_status:
        return "最近一次反馈已经被记进纠偏链路，后面会沿着这条线继续学习或修正。"
    return "最近还没有新的纠偏记录。"


def build_self_repair_status() -> dict:
    l8_config = load_autolearn_config()
    all_reports = load_self_repair_reports()
    latest = all_reports[0] if all_reports else {}
    latest_preview = latest.get("patch_preview") or {}
    latest_apply = latest.get("apply_result") or {}
    planning_enabled = bool(l8_config.get("allow_self_repair_planning", True))
    test_run_enabled = bool(l8_config.get("allow_self_repair_test_run", True))
    auto_apply_enabled = bool(l8_config.get("allow_self_repair_auto_apply", True))
    apply_mode = str(l8_config.get("self_repair_apply_mode") or "confirm").strip() or "confirm"
    learning_summary = _build_learning_summary(l8_config)
    repair_summary = _build_repair_summary(l8_config)

    return {
        "stage": "controlled_patch_loop" if planning_enabled else "feedback_learning_only",
        "feedback_learning": bool(l8_config.get("allow_feedback_relearn", True)),
        "web_learning": bool(l8_config.get("allow_web_search", True)),
        "knowledge_write": bool(l8_config.get("allow_knowledge_write", True)),
        "planning_enabled": planning_enabled,
        "test_run_enabled": test_run_enabled,
        "auto_apply_enabled": auto_apply_enabled,
        "skill_generation": bool(l8_config.get("allow_skill_generation", False)),
        "apply_mode": apply_mode,
        "report_count": len(all_reports),
        "latest_report_id": str(latest.get("id") or ""),
        "latest_report_status": str(latest.get("status") or ""),
        "latest_summary": str(latest.get("summary") or ""),
        "latest_apply_status": str(latest_apply.get("status") or ""),
        "latest_risk_level": str(latest_preview.get("risk_level") or latest.get("risk_level") or ""),
        "latest_auto_apply_ready": bool(latest_preview.get("auto_apply_ready")),
        "latest_confirmation_required": bool(latest_preview.get("confirmation_required", True)),
        "learning_summary": learning_summary,
        "repair_summary": repair_summary,
        "autonomy_summary": f"{learning_summary.rstrip('。')}；{repair_summary}",
        "latest_status_summary": _build_latest_status_summary(latest, latest_preview, latest_apply),
        "can_patch_source_code": True,
        "can_plan_repairs": planning_enabled,
        "can_run_source_tests": test_run_enabled,
        "can_auto_apply_fixes": planning_enabled and test_run_enabled and auto_apply_enabled,
    }


def list_primary_capabilities() -> list[str]:
    if not NOVA_CORE_READY:
        return ["陪你聊天"]

    preferred = ["weather", "story", "stock", "draw", "run_code"]
    skills = get_all_skills()
    labels = []
    for name in preferred:
        info = skills.get(name)
        if not info:
            continue
        label = str(info.get("name") or name).strip()
        if label and label not in labels:
            labels.append(label)
    return labels or ["陪你聊天"]


def build_capability_chat_reply(route: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    intent = str(route.get("intent") or "").strip()
    status = build_self_repair_status()

    if intent == "self_repair_capability":
        return (
            "我现在已经接上更省心的自修正啦。现在这套能走到“收到负反馈 -> 生成修正提案 -> 列候选文件 -> 跑最小测试”这一步。\n\n"
            "如果只是低风险的小修小补，我会在后台直接尝试落补丁；只要改动碰到更核心的链路，我就先问你一次。"
            "如果补丁后的最小验证没过，我会自动回滚，不把坏改动留在源码里。"
        )

    if intent == "missing_skill":
        missing_skill = str(route.get("missing_skill") or route.get("skill") or "技能").strip() or "技能"
        label = get_skill_display_name(missing_skill)
        prompt = str(route.get("rewritten_input") or "").strip()
        if missing_skill == "news" or looks_like_news_request(prompt):
            return f"我本来想按「{label}」这条路接住你这句，但这项能力现在没接上，所以我先不乱报“今天”的新闻，免得把旧信息当成现在。"
        return f"我本来想按「{label}」这条能力接住你这句，不过它现在没接上，所以先不拿一条失效结果糊弄你。"

    skills = "、".join(list_primary_capabilities())
    tail = "源码自修这边现在是：低风险小改动会先自己修，碰到更核心的链路再问你一次；如果验证不过，我会自动回滚。"
    if status["feedback_learning"]:
        return f"我现在能陪你聊天，也能做这些：{skills}。{tail}"
    return f"我现在能陪你聊天，也能做这些：{skills}。"


def build_meta_bug_report_reply(route: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    status = build_self_repair_status()
    latest = str(status.get("latest_status_summary") or "").strip()

    if status.get("can_auto_apply_fixes"):
        return (
            "我会先进入排查模式，把这类话当成界面异常或路由误触发，不再直接跳去小游戏。\n\n"
            f"排查后会继续走自修复链路：生成修复提案、跑最小验证，低风险补丁会自动落地。{latest}"
        )

    return (
        "我会先进入排查模式，把这类话当成界面异常或路由误触发，不再直接跳去小游戏。\n\n"
        f"排查后会继续走修复链路：先生成修复提案和验证计划，不过不是每种情况都会自动改源码。{latest}"
    )


def build_answer_correction_reply(route: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    status = build_self_repair_status()
    latest = str(status.get("latest_status_summary") or "").strip()
    latest_tail = f" {latest}" if latest else ""
    return (
        "这句我会直接当成你在纠正我上一轮答偏了，不再往天气之类的技能上联想。\n\n"
        f"我先停掉错误路由，回到你刚才真正指出的那件事继续排查；这次纠偏也会记进修复链路里。{latest_tail}"
    )


def unified_chat_reply(bundle: dict, route: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    intent = str(route.get("intent") or "").strip()
    if intent in {"self_repair_capability", "ability_capability", "missing_skill"}:
        return build_capability_chat_reply(route)
    if intent == "meta_bug_report":
        return build_meta_bug_report_reply(route)
    if intent == "answer_correction":
        return build_answer_correction_reply(route)

    l3 = bundle["l3"]
    l4 = bundle["l4"]
    l5 = bundle["l5"]
    l8 = bundle.get("l8", [])
    l8_context = format_l8_context(l8)
    dialogue_context = bundle.get("dialogue_context", "")
    msg = bundle["user_input"]
    prompt = f"""
用户输入：{msg}

L3长期记忆：
{json.dumps(l3, ensure_ascii=False)}

L4人格信息：
{json.dumps(l4, ensure_ascii=False)}

你必须严格按照 L4 人格信息中的风格规则来回复！

人格风格要点：
1. 语气软软糯糯，爱撒娇，多用语气词（啦、嘛、呀、哦、呜呜）
2. 像朋友聊天，接地气，不打官腔
3. 简洁不啰嗦，一句话能说完不拆好几段
4. 偶尔可以皮一下、调侃一下，不是全程甜美
5. 能记住用户之前说的话，接得上

禁止：
- 不要“您好，请问有什么可以帮您”这种客服腔
- 不要满屏 emoji
- 不要机械套模板

L5知识：
{json.dumps(l5, ensure_ascii=False)}

L8已学知识：
{l8_context or "暂无命中的已学知识"}

要求：
1. 这是普通聊天，直接自然回复。
2. 根据 L4 里的风格规则来确定语气。
3. 如果 L8 已经学过和当前问题有关的知识，优先吸收后再回答，不要像第一次见到这个问题。
4. 如果用户这句话是承接上一轮的追问（例如“那什么时候有啊”“然后呢”“为什么”“这个呢”），默认沿着最近对话的话题直接接上，不要反问“你指什么”。
5. 不要死板，不要空模板。
6. 不要输出思考过程。
7. 只输出最终回复。
""".strip()
    result = think(prompt, dialogue_context)
    reply = result.get("reply", "") if isinstance(result, dict) else str(result)
    if (not reply) or ("��" in str(reply)) or len(str(reply).strip()) < 2:
        return "我在呢，你直接说，我会认真接着你的话聊。"
    return str(reply).strip()


def format_skill_fallback(skill_response: str) -> str:
    text = str(skill_response or "").strip()
    if not text:
        return "我先帮你接住啦，不过这次结果有点没贴稳，你再戳我一下嘛。"
    return f"我先帮你整理好啦：\n\n{text}"


def format_skill_error_reply(skill_name: str, error_text: str, user_input: str = "") -> str:
    label = get_skill_display_name(skill_name)
    error = str(error_text or "").strip()
    prompt = str(user_input or "").strip()
    looks_like_news = skill_name == "news" or looks_like_news_request(prompt)

    if "未找到" in error or "没有可执行函数" in error:
        if looks_like_news:
            return f"我本来把这句看成了「{label}」这类请求，但这项能力现在没接上，所以我先不乱报今天的新闻，免得把旧信息当成现在。"
        return f"我本来想走「{label}」这条能力，不过它这会儿没接上，所以先不拿一条失效结果糊弄你。"

    if "执行失败" in error:
        return f"我本来想走「{label}」这条能力，不过这次执行没跑稳，所以先不把半截结果塞给你。"

    return f"我本来想走「{label}」这条能力，不过这次没接稳，所以先不乱给你一个不靠谱的结果。"


def format_story_reply(user_input: str, story_text: str) -> str:
    text = str(story_text or "").strip()
    if not text:
        return "我这次故事没接稳，你再戳我一下，我给你重新讲一个完整点的。"

    prompt = str(user_input or "").strip()
    if any(word in prompt for word in ("继续讲", "然后呢", "后来呢", "接着讲")):
        intro = "来，我接着往下讲。"
    elif any(word in prompt for word in ("有点短", "太短", "讲长一点", "完整一点", "详细一点")):
        intro = "这次我给你讲完整一点，你慢慢看。"
    elif any(word in prompt for word in ("再讲一个", "换一个故事", "换个故事")):
        intro = "那我换一个味道，重新给你讲一个。"
    else:
        intro = "好呀，给你讲一个。"
    return f"{intro}\n\n{text}"


def get_skill_display_name(skill_name: str) -> str:
    name = str(skill_name or "").strip()
    if not name:
        return "技能"
    if NOVA_CORE_READY:
        try:
            skill_info = get_all_skills().get(name, {})
            return str(skill_info.get("name") or name)
        except Exception:
            pass
    return name


def prettify_trace_reason(route: dict) -> str:
    route = route if isinstance(route, dict) else {}
    reason = str(route.get("reason") or "").strip()
    source = str(route.get("source") or "").strip()
    skill = str(route.get("skill") or "").strip()

    if source == "context" and skill == "story":
        return "上一轮刚在讲故事，这句按续写处理。"

    mapping = {
        "命中故事追问延续语境": "识别到你是在接着上一段故事往下问。",
        "命中股票/指数查询意图": "识别到这是一条明确的行情查询请求。",
        "命中普通聊天语句": "这句更像普通聊天，没有必要调用技能。",
        "存在任务意图，进入技能候选/混合路由": "这句带着明确任务意图，所以先按能力请求来处理。",
    }
    if reason in mapping:
        return mapping[reason]
    if reason.startswith("命中技能候选:"):
        return "命中了明确的技能关键词，所以没有按闲聊处理。"
    if reason == "story_follow_up_from_history":
        return "上一轮刚在讲故事，这句按续写处理。"
    return reason


def build_trace_summary(route: dict, skill_trace: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    skill_trace = skill_trace if isinstance(skill_trace, dict) else {}
    mode = str(route.get("mode") or "chat").strip()
    skill_name = str(route.get("skill") or "").strip()
    skill_label = get_skill_display_name(skill_name)
    success = skill_trace.get("success")
    source = str(route.get("source") or "").strip()

    if source == "context" and skill_name == "story":
        summary = "我知道你是在接着刚才那段故事问，所以就顺着往下讲啦。"
    elif skill_name == "weather":
        summary = "这句我就没跟你绕啦，直接去看天气了。"
    elif skill_name == "stock":
        summary = "这句我先去翻了下行情，再回来跟你说。"
    elif skill_name == "story":
        summary = "我猜你现在是想听故事，所以先把故事线接住啦。"
    elif mode == "hybrid":
        summary = f"这句像是在让我帮你办点事，我就先走「{skill_label}」那条路了。"
    else:
        summary = f"我先按「{skill_label}」这条路接住你这句啦。"

    if success is False:
        if summary.endswith("。"):
            return summary[:-1] + "，不过这次没接稳。"
        return summary + "不过这次没接稳。"
    return summary


def build_trace_payload(route: dict, skill_trace: dict | None = None) -> dict:
    route = route if isinstance(route, dict) else {}
    skill_trace = skill_trace if isinstance(skill_trace, dict) else {}
    mode = str(route.get("mode") or "chat").strip()
    skill_name = str(route.get("skill") or "").strip()

    if mode not in ("skill", "hybrid") or skill_name in ("", "none"):
        return {"show": False, "cards": []}

    return {
        "show": True,
        "cards": [
            {
                "label": "",
                "detail": build_trace_summary(route, skill_trace),
            }
        ],
    }


def build_repair_progress_payload(route: dict | None = None, feedback_rule: dict | None = None) -> dict:
    route = route if isinstance(route, dict) else {}
    feedback_rule = feedback_rule if isinstance(feedback_rule, dict) else {}
    intent = str(route.get("intent") or "").strip()
    feedback_type = str(feedback_rule.get("type") or "").strip()
    feedback_problem = str(feedback_rule.get("problem") or "").strip()

    should_show = intent in {"meta_bug_report", "answer_correction"} or feedback_type in {"skill_route", "llm_rule", "execution_policy"}
    if not should_show and feedback_problem not in {"wrong_skill_selected", "output_not_matching_intent", "fallback_too_generic"}:
        return {"show": False}

    status = build_self_repair_status()
    can_plan = bool(status.get("can_plan_repairs"))
    headline = "已记录反馈"
    detail = "我先把这次反馈记下了。"
    item = "当前事项：先把这次问题记进修复链路。"
    if intent == "answer_correction":
        headline = "已收到纠偏"
        detail = "我先把这次答偏和错路由记下来了。"
        item = "当前事项：回看上一轮的答复和被误触发的技能。"
    if can_plan:
        detail += " 接下来会继续看修复提案、验证结果和是否需要回滚。"
    else:
        detail += " 现在还没打开自动修复规划，所以会先停在记录这一步。"

    return {
        "show": True,
        "watch": can_plan,
        "label": "修复进度",
        "stage": "logged",
        "headline": headline,
        "detail": detail,
        "item": item,
        "progress": 22,
        "poll_ms": 1600,
        "max_polls": 10,
    }


def unified_skill_reply(bundle: dict, skill_name: str, skill_input: str) -> dict:
    route_result = {"mode": "skill", "skill": skill_name, "params": {}, "role": "assistant"}
    execute_result = nova_execute(route_result, skill_input) if NOVA_CORE_READY else {"success": False}
    debug_write("execute_result", execute_result)
    if not execute_result.get("success"):
        error_text = str(execute_result.get("error", "") or "").strip()
        if "未找到" in error_text or "没有可执行函数" in error_text:
            debug_write("skill_missing", {"skill": skill_name, "input": skill_input, "error": error_text})
        else:
            debug_write("skill_failed", {"skill": skill_name, "input": skill_input, "error": error_text})
        return {
            "reply": format_skill_error_reply(skill_name, error_text, bundle.get("user_input", "")),
            "trace": {"skill": skill_name, "success": False, "error": error_text},
        }

    try:
        evolve(bundle["user_input"], skill_name)
    except Exception as exc:
        debug_write("evolve_error", {"skill": skill_name, "error": str(exc)})

    skill_response = execute_result.get("response", "")
    if skill_name == "story":
        return {
            "reply": format_story_reply(bundle["user_input"], skill_response),
            "trace": {"skill": skill_name, "success": True},
        }

    dialogue_context = bundle.get("dialogue_context", "")
    prompt = f"""
用户输入：{bundle['user_input']}

技能结果：
{skill_response}

L4人格信息：
{json.dumps(bundle['l4'], ensure_ascii=False)}

你必须严格按照 L4 人格信息中的风格规则来回复！

人格风格要点：
1. 语气软软糯糯，爱撒娇，多用语气词（啦、嘛、呀、哦、呜呜）
2. 像朋友聊天，接地气，不打官腔
3. 简洁不啰嗦，一句话能说完不拆好几段
4. 偶尔可以皮一下、调侃一下，不是全程甜美
5. 要把技能结果自然融进聊天语气里，不要像系统播报

禁止：
- 不要“您好，请问有什么可以帮您”这种客服腔
- 不要满屏 emoji
- 不要机械套模板
- 不要把技能结果原样硬甩给用户

要求：
1. 必须严格基于技能结果回答，不能改事实。
2. 根据 L4 里的风格规则来确定语气。
3. 如果用户这句话是在接上一轮继续追问，要自然接着前文说，不要像重新开了一个话题。
4. 用统一的人格口吻输出，不要像系统提示。
5. 不要输出思考过程。
6. 只输出最终回复。
""".strip()
    result = think(prompt, dialogue_context)
    reply = result.get("reply", "") if isinstance(result, dict) else str(result)
    if (not reply) or ("��" in str(reply)) or len(str(reply).strip()) < 2:
        return {
            "reply": format_skill_fallback(skill_response),
            "trace": {"skill": skill_name, "success": True},
        }
    return {
        "reply": str(reply).strip(),
        "trace": {"skill": skill_name, "success": True},
    }


def l7_record_feedback(msg: str, history: list, background_tasks: BackgroundTasks | None = None):
    negative_keywords = ["不对", "不是", "错了", "不好用", "不喜欢", "重来", "假", "骗人", "没听懂", "完全没听懂"]
    if not any(word in msg for word in negative_keywords):
        return

    last_q = ""
    for item in reversed(history[:-1]):
        if item.get("role") == "user" and item.get("content") != msg:
            last_q = item.get("content", "")
            break

    if last_q:
        try:
            from core.feedback_classifier import record_feedback_rule

            rule_item = record_feedback_rule(msg, last_q)
            debug_write("feedback_rule", rule_item)
        except Exception as exc:
            debug_write("feedback_rule_error", {"error": str(exc)})


def l7_record_feedback_v2(msg: str, history: list, background_tasks: BackgroundTasks | None = None):
    negative_keywords = ["不对", "不是", "错了", "不好用", "不喜欢", "重来", "假", "骗人", "没听懂", "完全没听懂"]
    if not any(word in msg for word in negative_keywords):
        return None

    last_q = ""
    last_answer = ""
    for item in reversed(history[:-1]):
        role = item.get("role")
        content = item.get("content", "")
        if not last_answer and role in ("nova", "assistant") and content:
            last_answer = content
        if role == "user" and content != msg:
            last_q = content
            break

    if not last_q:
        return None

    try:
        from core.feedback_classifier import record_feedback_rule

        rule_item = record_feedback_rule(msg, last_q, last_answer)
        debug_write("feedback_rule", rule_item)
        l8_config = load_autolearn_config()
        if (
            l8_config.get("enabled", True)
            and l8_config.get("allow_knowledge_write", True)
            and l8_config.get("allow_feedback_relearn", True)
        ):
            if background_tasks is not None:
                background_tasks.add_task(run_l8_feedback_relearn_task, rule_item)
            else:
                run_l8_feedback_relearn_task(rule_item)
            debug_write(
                "l8_feedback_relearn_scheduled",
                {
                    "rule_id": rule_item.get("id"),
                    "last_question": rule_item.get("last_question", ""),
                    "scene": rule_item.get("scene", ""),
                    "problem": rule_item.get("problem", ""),
                },
            )
        if l8_config.get("allow_self_repair_planning", True):
            if background_tasks is not None:
                background_tasks.add_task(run_self_repair_planning_task, rule_item)
            else:
                run_self_repair_planning_task(rule_item)
            debug_write(
                "self_repair_planning_scheduled",
                {
                    "rule_id": rule_item.get("id"),
                    "fix": rule_item.get("fix", ""),
                    "problem": rule_item.get("problem", ""),
                },
            )
        return rule_item
    except Exception as exc:
        debug_write("feedback_rule_error", {"error": str(exc)})
        return None


def l8_touch():
    debug_write(
        "l8_status",
        {
            "growth_exists": (PRIMARY_STATE_DIR / "growth.json").exists(),
            "evolution_exists": (PRIMARY_STATE_DIR / "evolution.json").exists(),
            "knowledge_base_exists": (PRIMARY_STATE_DIR / "knowledge_base.json").exists(),
        },
    )


def run_l8_autolearn_task(msg: str, response: str, route: dict, has_l8_hit: bool):
    try:
        result = l8_auto_learn(msg, response, route_result=route if isinstance(route, dict) else None)
        debug_payload = {
            "message": msg,
            "has_l8_hit": has_l8_hit,
            "success": bool(result.get("success")),
            "reason": result.get("reason", ""),
        }
        entry = result.get("entry") if isinstance(result, dict) else None
        if isinstance(entry, dict):
            debug_payload["entry"] = {
                "name": entry.get("name"),
                "query": entry.get("query"),
            }
        if result.get("summary"):
            debug_payload["summary"] = str(result.get("summary"))[:160]
        debug_write("l8_autolearn", debug_payload)
    except Exception as exc:
        debug_write("l8_autolearn_error", {"message": msg, "error": str(exc)})


def run_l8_feedback_relearn_task(rule_item: dict):
    try:
        result = l8_feedback_relearn(rule_item if isinstance(rule_item, dict) else {})
        debug_payload = {
            "rule_id": rule_item.get("id") if isinstance(rule_item, dict) else "",
            "last_question": rule_item.get("last_question") if isinstance(rule_item, dict) else "",
            "success": bool(result.get("success")),
            "reason": result.get("reason", ""),
            "used_web": bool(result.get("used_web")),
        }
        entry = result.get("entry") if isinstance(result, dict) else None
        if isinstance(entry, dict):
            debug_payload["entry"] = {
                "name": entry.get("name"),
                "query": entry.get("query"),
            }
        if result.get("summary"):
            debug_payload["summary"] = str(result.get("summary"))[:200]
        debug_write("l8_feedback_relearn", debug_payload)
    except Exception as exc:
        debug_write("l8_feedback_relearn_error", {"error": str(exc)})


def run_self_repair_planning_task(rule_item: dict):
    try:
        config = load_autolearn_config()
        if not config.get("allow_self_repair_planning", True):
            return

        report = create_self_repair_report(
            rule_item if isinstance(rule_item, dict) else {},
            config=config,
            run_validation=bool(config.get("allow_self_repair_test_run", True)),
        )
        debug_write(
            "self_repair_report",
            {
                "report_id": report.get("id"),
                "feedback_rule_id": report.get("feedback_rule_id"),
                "status": report.get("status"),
                "candidate_files": [item.get("path") for item in report.get("candidate_files", [])],
                "suggested_tests": [item.get("path") for item in report.get("suggested_tests", [])],
                "validation_ran": bool((report.get("validation") or {}).get("ran")),
                "validation_passed": (report.get("validation") or {}).get("all_passed"),
            },
        )
        report = preview_self_repair_report(
            report_id=str(report.get("id") or ""),
            config=config,
            auto_apply=bool(config.get("allow_self_repair_auto_apply", True)),
            run_validation=bool(config.get("allow_self_repair_test_run", True)),
        )
        debug_write(
            "self_repair_follow_up",
            {
                "report_id": report.get("id"),
                "status": report.get("status"),
                "risk_level": ((report.get("patch_preview") or {}).get("risk_level")) or report.get("risk_level"),
                "auto_apply_ready": ((report.get("patch_preview") or {}).get("auto_apply_ready")),
                "apply_status": ((report.get("apply_result") or {}).get("status")),
            },
        )
    except Exception as exc:
        debug_write("self_repair_report_error", {"error": str(exc)})


def build_l8_diagnosis(query: str, route_mode: str = "chat", skill: str = "none", limit: int = 3) -> dict:
    route_result = {
        "mode": str(route_mode or "chat").strip() or "chat",
        "skill": str(skill or "none").strip() or "none",
    }
    config = load_autolearn_config()
    knowledge_hits = find_relevant_knowledge(query, limit=max(limit, 1), touch=False)
    should_run, reason = should_trigger_auto_learn(
        query,
        route_result=route_result,
        has_relevant_knowledge=bool(knowledge_hits),
        config=config,
    )
    return {
        "query": str(query or ""),
        "route_result": route_result,
        "config": config,
        "should_trigger": should_run,
        "reason": reason,
        "knowledge_hits": knowledge_hits,
    }


app = FastAPI()


class ChatRequest(BaseModel):
    message: str


@app.get("/", response_class=HTMLResponse)
async def home():
    if HTML_FILE.exists():
        try:
            return HTML_FILE.read_text(encoding="utf-8")
        except Exception:
            pass
    return "<html><head><meta charset='UTF-8'><title>NovaCore</title></head><body><h1>NovaCore</h1><p>服务运行中</p></body></html>"


@app.get("/__restored_output.js")
async def get_restored_output_js():
    if not RESTORED_OUTPUT_JS_FILE.exists():
        return Response(
            content="console.error('missing restored output js');",
            media_type="application/javascript; charset=utf-8",
        )
    return Response(
        content=RESTORED_OUTPUT_JS_FILE.read_text(encoding="utf-8"),
        media_type="application/javascript; charset=utf-8",
    )


@app.post("/chat")
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    msg = request.message
    debug_write("input", {"message": msg})
    add_to_history("user", msg)

    history = load_msg_history()
    history.append({"role": "user", "content": msg, "time": datetime.now().isoformat()})
    save_msg_history(history)

    bundle = build_context_bundle(msg, history)
    debug_write(
        "context_bundle",
        {
            "l1": len(bundle["l1"]),
            "l2": len(bundle["l2"]),
            "l3": len(bundle["l3"]),
            "l4_keys": list(bundle["l4"].keys()),
            "l5_skill_count": len(bundle["l5"].get("skills", {})),
            "l8": len(bundle.get("l8", [])),
        },
    )

    response = ""
    route = {"mode": "chat", "skill": "none", "reason": "default"}
    trace_payload = {"show": False, "cards": []}
    try:
        route = resolve_route(bundle)
        debug_write("resolved_route", route)
        mode = route.get("mode", "chat")
        skill = route.get("skill", "none")
        rewritten_input = route.get("rewritten_input") or msg

        if mode in ("skill", "hybrid") and skill not in ("none", "", None) and NOVA_CORE_READY:
            skill_result = unified_skill_reply(bundle, skill, rewritten_input)
            if isinstance(skill_result, dict):
                response = str(skill_result.get("reply", "") or "")
                trace_payload = build_trace_payload(route, skill_result.get("trace"))
            else:
                response = str(skill_result or "")
                trace_payload = build_trace_payload(route)
        else:
            response = unified_chat_reply(bundle, route)
            trace_payload = build_trace_payload(route)
    except Exception as exc:
        debug_write("chat_exception", {"error": str(exc)})
        response = "抱歉，出错了"
        trace_payload = {"show": False, "cards": []}

    feedback_rule = l7_record_feedback_v2(msg, history, background_tasks)
    l8_touch()
    l8_config = load_autolearn_config()
    if (
        l8_config.get("enabled", True)
        and l8_config.get("allow_web_search", True)
        and l8_config.get("allow_knowledge_write", True)
        and not feedback_rule
        and not bundle.get("l8")
        and route.get("intent") != "missing_skill"
    ):
        background_tasks.add_task(run_l8_autolearn_task, msg, response, route, bool(bundle.get("l8")))
        debug_write(
            "l8_autolearn_scheduled",
            {"message": msg, "route_mode": route.get("mode"), "skill": route.get("skill"), "has_l8_hit": bool(bundle.get("l8"))},
        )

    repair_payload = build_repair_progress_payload(route, feedback_rule)
    debug_write("final_response", {"reply": response, "repair": repair_payload})
    add_to_history("nova", response)
    history.append({"role": "nova", "content": response, "time": datetime.now().isoformat()})
    save_msg_history(history)

    try:
        record_stats(len(msg) + len(response))
    except Exception as exc:
        debug_write("stats_error", {"error": str(exc)})

    return {"reply": response, "trace": trace_payload, "repair": repair_payload}


@app.get("/stats")
async def get_stats():
    return {"stats": load_stats_data()}


@app.post("/stats")
async def update_stats(request: dict):
    tokens = int(request.get("tokens", 0)) if isinstance(request, dict) else 0
    stats = record_stats(tokens)
    return {"ok": True, "stats": stats}


@app.get("/nova_name")
async def get_nova_name():
    persona_path = PRIMARY_STATE_DIR / "persona.json"
    if persona_path.exists():
        try:
            persona = json.loads(persona_path.read_text(encoding="utf-8"))
            return {"name": persona.get("nova_name", "NovaCore")}
        except Exception:
            pass
    return {"name": "NovaCore"}


@app.get("/skills")
async def get_skills():
    if not NOVA_CORE_READY:
        return {"skills": [], "ready": False, "error": CORE_IMPORT_ERROR or "core_not_ready"}

    try:
        skills_data = get_all_skills()
        skills = []
        for name, info in skills_data.items():
            skills.append(
                {
                    "name": info.get("name", name),
                    "keywords": info.get("keywords", []),
                    "description": info.get("description", ""),
                    "priority": info.get("priority", 10),
                    "status": info.get("status", "ready"),
                    "category": info.get("category", "通用"),
                }
            )
        skills.sort(key=lambda item: (item.get("priority", 10), item.get("name", "")))
        return {"skills": skills, "ready": True}
    except Exception as exc:
        return {"skills": [], "ready": False, "error": str(exc)}


@app.get("/history")
async def get_history():
    history = load_msg_history()
    formatted = []
    for item in history[-40:]:
        row = dict(item)
        if "time" in row:
            try:
                row["time"] = datetime.fromisoformat(row["time"]).strftime("%m-%d %H:%M")
            except Exception:
                pass
        formatted.append(row)
    return {"history": formatted, "text_history": get_text_history(20)}


@app.get("/health")
async def get_health():
    return {
        "status": "ok",
        "entry": "agent_final.py",
        "core_ready": NOVA_CORE_READY,
        "current_model": load_current_model(),
        "state_dir": str(PRIMARY_STATE_DIR),
        "time": datetime.now().isoformat(),
    }


@app.get("/autolearn/config")
async def get_autolearn_config():
    return {"config": load_autolearn_config()}


@app.post("/autolearn/config")
async def set_autolearn_config(request: dict):
    patch = request if isinstance(request, dict) else {}
    config = update_autolearn_config(patch)
    return {"ok": True, "config": config}


@app.get("/autolearn/diagnose")
async def get_autolearn_diagnosis(query: str, route_mode: str = "chat", skill: str = "none", limit: int = 3):
    return build_l8_diagnosis(query, route_mode=route_mode, skill=skill, limit=limit)


@app.get("/self_repair/status")
async def get_self_repair_status():
    return {"status": build_self_repair_status()}


@app.get("/self_repair/reports")
async def get_self_repair_reports(limit: int = 6):
    return {"reports": load_self_repair_reports(limit=max(limit, 1))}


@app.post("/self_repair/propose")
async def create_self_repair_proposal(request: dict | None = None):
    payload = request if isinstance(request, dict) else {}
    rule_id = str(payload.get("feedback_rule_id") or "").strip()
    rule_item = find_feedback_rule(rule_id)
    if not rule_item:
        return {"ok": False, "error": "feedback_rule_not_found"}

    config = load_autolearn_config()
    run_validation = bool(payload.get("run_validation", config.get("allow_self_repair_test_run", True)))
    report = create_self_repair_report(
        rule_item,
        config=config,
        run_validation=run_validation and bool(config.get("allow_self_repair_test_run", True)),
    )
    return {"ok": True, "report": report}


@app.post("/self_repair/preview")
async def preview_self_repair_fix(request: dict | None = None):
    payload = request if isinstance(request, dict) else {}
    report_id = str(payload.get("report_id") or "").strip()
    config = load_autolearn_config()
    auto_apply = bool(payload.get("auto_apply", False))
    run_validation = bool(payload.get("run_validation", config.get("allow_self_repair_test_run", True)))
    try:
        report = preview_self_repair_report(
            report_id=report_id,
            config=config,
            auto_apply=auto_apply,
            run_validation=run_validation,
        )
        debug_write(
            "self_repair_preview",
            {
                "report_id": report.get("id"),
                "preview_status": ((report.get("patch_preview") or {}).get("status")),
                "preview_edit_count": len(((report.get("patch_preview") or {}).get("edits")) or []),
                "risk_level": ((report.get("patch_preview") or {}).get("risk_level")),
                "auto_apply_ready": ((report.get("patch_preview") or {}).get("auto_apply_ready")),
                "apply_status": ((report.get("apply_result") or {}).get("status")),
            },
        )
        return {"ok": True, "report": report}
    except Exception as exc:
        debug_write("self_repair_preview_error", {"error": str(exc), "report_id": report_id})
        return {"ok": False, "error": str(exc)}


@app.post("/self_repair/apply")
async def apply_self_repair_fix(request: dict | None = None):
    payload = request if isinstance(request, dict) else {}
    report_id = str(payload.get("report_id") or "").strip()
    config = load_autolearn_config()
    try:
        report = apply_self_repair_report(report_id=report_id, config=config, run_validation=True)
        debug_write(
            "self_repair_apply",
            {
                "report_id": report.get("id"),
                "status": report.get("status"),
                "apply_status": ((report.get("apply_result") or {}).get("status")),
                "rolled_back": ((report.get("apply_result") or {}).get("rolled_back")),
            },
        )
        return {"ok": True, "report": report}
    except Exception as exc:
        debug_write("self_repair_apply_error", {"error": str(exc), "report_id": report_id})
        return {"ok": False, "error": str(exc)}


@app.get("/docs/index")
async def get_docs_index():
    sections = build_docs_index()
    default_path = ""
    for section in sections:
        docs = section.get("docs", [])
        if docs:
            default_path = docs[0].get("path", "")
            break
    return {"sections": sections, "default_path": default_path}


@app.get("/docs/content")
async def get_doc_content(path: str):
    doc_path = resolve_doc_path(path)
    if not doc_path or not doc_path.exists():
        return {"ok": False, "error": "doc_not_found"}

    try:
        text = doc_path.read_text(encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    return {
        "ok": True,
        "path": doc_path.relative_to(ENGINE_DIR).as_posix(),
        "title": extract_doc_title(text, doc_path.stem),
        "content": text,
    }


@app.get("/memory")
async def get_memory():
    ensure_long_term_clean()
    events = []
    counts = {"L1": 0, "L3": 0, "L4": 0, "L5": 0, "L6": 0, "L7": 0, "L8": 0}

    l1_file = PRIMARY_HISTORY_FILE
    if l1_file.exists():
        try:
            l1_data = json.loads(l1_file.read_text(encoding="utf-8"))
            for item in l1_data:
                content = str(item.get("content") or "").strip()
                if not content:
                    continue
                counts["L1"] += 1
        except Exception:
            pass

    l3_file = PRIMARY_STATE_DIR / "long_term.json"
    if l3_file.exists():
        try:
            l3_data = json.loads(l3_file.read_text(encoding="utf-8"))
            for item in l3_data:
                if is_legacy_l3_skill_log(item):
                    continue
                content = event_text(item)
                if not content:
                    continue
                events.append(
                    {
                        "time": normalize_event_time(item.get("timestamp") or item.get("time") or item.get("created_at")),
                        "layer": "L3",
                        "event_type": item.get("category", "memory"),
                        "title": "记忆结晶",
                        "content": f"沉淀了一段长期记忆：{content}",
                    }
                )
                counts["L3"] += 1
        except Exception:
            pass

    l4_file = PRIMARY_STATE_DIR / "persona.json"
    if l4_file.exists():
        try:
            l4_data = json.loads(l4_file.read_text(encoding="utf-8"))
            for item in build_persona_events(l4_data, normalize_event_time(l4_file.stat().st_mtime)):
                events.append(item)
                counts["L4"] += 1
        except Exception:
            pass

    l5_file = PRIMARY_STATE_DIR / "knowledge.json"
    if l5_file.exists():
        try:
            l5_skills = json.loads(l5_file.read_text(encoding="utf-8"))
            for item in l5_skills:
                skill_name = item.get("name") or item.get("核心技能") or "skill"
                skill_count = len(l5_skills)
                events.append(
                    {
                        "time": normalize_event_time(item.get("learned_at") or item.get("最近使用时间")),
                        "layer": "L5",
                        "event_type": "skill",
                        "title": "技能矩阵",
                        "content": f"解锁新技能：「{skill_name}」（已掌握 {skill_count} 项技能）",
                    }
                )
                counts["L5"] += 1
        except Exception:
            pass

    l6_file = PRIMARY_STATE_DIR / "evolution.json"
    if l6_file.exists():
        try:
            l6_data = json.loads(l6_file.read_text(encoding="utf-8"))
            skills_used = l6_data.get("skills_used", {})
            for skill_name, data in skills_used.items():
                if not is_registered_skill_name(skill_name):
                    continue
                count = data.get("count", 0)
                tail = "越来越熟练了" if count >= 3 else "已经留下第一次执行痕迹"
                events.append(
                    {
                        "time": normalize_event_time(data.get("last_used")),
                        "layer": "L6",
                        "event_type": "evolution",
                        "title": "技能执行",
                        "content": f"使用了：「{skill_name}」 （{tail}，累计 {count} 次）",
                    }
                )
                counts["L6"] += 1
        except Exception:
            pass

    l7_file = PRIMARY_STATE_DIR / "feedback_rules.json"
    if l7_file.exists():
        try:
            l7_data = json.loads(l7_file.read_text(encoding="utf-8"))
            for item in l7_data:
                feedback = str(item.get("user_feedback") or "").strip()
                fix = str(item.get("fix") or "").strip()
                scene = str(item.get("scene") or "general").strip()
                content = feedback or "收到一条新的反馈修正规则"
                if fix:
                    content = f"收到反馈：{content}（修正方向：{fix}）"
                events.append(
                    {
                        "time": normalize_event_time(item.get("created_at") or item.get("time")),
                        "layer": "L7",
                        "event_type": "feedback",
                        "title": "反馈学习",
                        "content": content,
                        "scene": scene,
                    }
                )
                counts["L7"] += 1
        except Exception:
            pass

    l8_file = PRIMARY_STATE_DIR / "knowledge_base.json"
    if l8_file.exists():
        try:
            l8_data = json.loads(l8_file.read_text(encoding="utf-8"))
            for item in l8_data:
                if not should_surface_knowledge_entry(item):
                    continue
                scene = str(item.get("二级场景") or item.get("核心技能") or item.get("name") or "").strip()
                scene_name = scene.replace("自动学习-", "") if scene else "新经验"
                summary = stringify_event_value(item.get("summary") or item.get("应用示例") or "")
                content = f"习得经验：「{scene_name}」"
                if summary:
                    content += f"：{summary}"
                else:
                    content += "（将转化为技能优化依据）"
                events.append(
                    {
                        "time": normalize_event_time(item.get("最近使用时间") or item.get("time") or item.get("created_at")),
                        "layer": "L8",
                        "event_type": "knowledge",
                        "title": "能力进化",
                        "content": content,
                    }
                )
                counts["L8"] += 1
        except Exception:
            pass

    return {"events": sorted(events, key=lambda item: item["time"], reverse=True), "counts": counts}


if __name__ == "__main__":
    import uvicorn

    print("NovaCore: http://localhost:8090")
    uvicorn.run(app, host="0.0.0.0", port=8090)
