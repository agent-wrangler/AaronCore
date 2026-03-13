"""
NovaCore Agent Engine - Unified Entry
当前唯一主入口：8090 本地服务
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import json
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

ENGINE_DIR = Path(__file__).parent
CORE_DIR = ENGINE_DIR / "core"
PRIMARY_STATE_DIR = ENGINE_DIR / "memory_db"
LEGACY_STATE_DIR = ENGINE_DIR / "memory"
LOGS_DIR = ENGINE_DIR / "logs"
HTML_FILE = ENGINE_DIR / "output.html"
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
    update_autolearn_config,
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
    return normalized


def has_skill_target(route_result: dict) -> bool:
    return route_result.get("skill") not in ("none", "", None)


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


def unified_chat_reply(bundle: dict) -> str:
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


def unified_skill_reply(bundle: dict, skill_name: str, skill_input: str) -> str:
    route_result = {"mode": "skill", "skill": skill_name, "params": {}, "role": "assistant"}
    execute_result = nova_execute(route_result, skill_input) if NOVA_CORE_READY else {"success": False}
    debug_write("execute_result", execute_result)
    if not execute_result.get("success"):
        return execute_result.get("error", "技能执行失败")

    try:
        evolve(bundle["user_input"], skill_name)
    except Exception as exc:
        debug_write("evolve_error", {"skill": skill_name, "error": str(exc)})

    skill_response = execute_result.get("response", "")
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
        return format_skill_fallback(skill_response)
    return str(reply).strip()


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
    try:
        route = resolve_route(bundle)
        debug_write("resolved_route", route)
        mode = route.get("mode", "chat")
        skill = route.get("skill", "none")
        rewritten_input = route.get("rewritten_input") or msg

        if mode in ("skill", "hybrid") and skill not in ("none", "", None) and NOVA_CORE_READY:
            response = unified_skill_reply(bundle, skill, rewritten_input)
        else:
            response = unified_chat_reply(bundle)
    except Exception as exc:
        debug_write("chat_exception", {"error": str(exc)})
        response = "抱歉，出错了"

    feedback_rule = l7_record_feedback_v2(msg, history, background_tasks)
    l8_touch()
    l8_config = load_autolearn_config()
    if (
        l8_config.get("enabled", True)
        and l8_config.get("allow_web_search", True)
        and l8_config.get("allow_knowledge_write", True)
        and not feedback_rule
        and not bundle.get("l8")
    ):
        background_tasks.add_task(run_l8_autolearn_task, msg, response, route, bool(bundle.get("l8")))
        debug_write(
            "l8_autolearn_scheduled",
            {"message": msg, "route_mode": route.get("mode"), "skill": route.get("skill"), "has_l8_hit": bool(bundle.get("l8"))},
        )

    debug_write("final_response", {"reply": response})
    add_to_history("nova", response)
    history.append({"role": "nova", "content": response, "time": datetime.now().isoformat()})
    save_msg_history(history)

    try:
        record_stats(len(msg) + len(response))
    except Exception as exc:
        debug_write("stats_error", {"error": str(exc)})

    return {"reply": response}


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
                        "content": f"沉淀了一段长期记忆：{content[:120]}",
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
                scene = str(item.get("二级场景") or item.get("核心技能") or item.get("name") or "").strip()
                scene_name = scene.replace("自动学习-", "") if scene else "新经验"
                summary = summarize_event_value(item.get("summary") or item.get("应用示例") or "", 120)
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
