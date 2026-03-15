# context_builder - 对话上下文组装（L1-L8）
# 从 agent_final.py 提取

import json
from datetime import datetime

from core.state_loader import (
    get_recent_messages, load_l3_long_term, load_l4_persona, load_l5_knowledge,
)

# ── 注入依赖 ──────────────────────────────────────────────
_find_relevant_knowledge = lambda msg, limit=3, touch=True: []
_extract_session_context = lambda history, current_input="": {"topics": [], "mood": "平稳", "intents": [], "follow_up": {}}


def init(*, find_relevant_knowledge=None, extract_session_context=None):
    global _find_relevant_knowledge, _extract_session_context
    if find_relevant_knowledge:
        _find_relevant_knowledge = find_relevant_knowledge
    if extract_session_context:
        _extract_session_context = extract_session_context


# ── 事件值格式化 ──────────────────────────────────────────

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


# ── 人格事件构建 ──────────────────────────────────────────

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

    # 动态变更日志（L2 结晶时写入的 _changelog）
    changelog = persona_data.get("_changelog") or []
    for entry in changelog:
        if isinstance(entry, dict) and entry.get("content"):
            events.append(
                {
                    "time": str(entry.get("time") or event_time),
                    "layer": "L4",
                    "event_type": "persona_update",
                    "title": "\u4eba\u683c\u56fe\u8c31",
                    "content": str(entry["content"]),
                }
            )

    return events


# ── 时间与对话工具 ────────────────────────────────────────

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


# ── 上下文总装 ────────────────────────────────────────────

def build_context_bundle(msg: str, history: list) -> dict:
    return {
        "l1": get_recent_messages(history, 6),
        "l2": _extract_session_context(history, msg),
        "l3": load_l3_long_term(),
        "l4": load_l4_persona(),
        "l5": load_l5_knowledge(),
        "l8": _find_relevant_knowledge(msg, limit=3, touch=True),
        "dialogue_context": build_dialogue_context(history, msg),
        "user_input": msg,
    }
