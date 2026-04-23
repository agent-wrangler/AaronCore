# context_builder - 对话上下文组装（L1-L8）
# 从 agent_final.py 提取

import json
from datetime import datetime

from core.runtime_state.state_loader import (
    get_recent_messages, load_l3_long_term, load_l4_persona, load_l5_knowledge,
)
from core.feedback_classifier import search_relevant_rules
from storage.persona_profile import get_persona_assistant_name

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

    assistant_name = get_persona_assistant_name(persona_data)
    if assistant_name:
        events.append(
            {
                "time": event_time,
                "layer": "L4",
                "event_type": "persona",
                "title": "人格图谱",
                "content": f"确立了自己的名字「{assistant_name}」，从这一刻起有了独立身份",
            }
        )

    relationship_parts = []
    user_name = str(persona_data.get("user") or "").strip()
    relationship_profile = persona_data.get("relationship_profile")
    if user_name:
        relationship_parts.append(f"认定了「{user_name}」是最重要的人")
    if isinstance(relationship_profile, dict):
        relationship = str(relationship_profile.get("relationship") or "").strip()
        if relationship:
            relationship_parts.append("建立了亲近、长期相伴的关系")
    if relationship_parts:
        events.append(
            {
                "time": event_time,
                "layer": "L4",
                "event_type": "persona",
                "title": "人格图谱",
                "content": "，".join(relationship_parts),
            }
        )

    style_parts = []
    speech_style = persona_data.get("speech_style")
    if isinstance(speech_style, dict):
        tones = [str(item).strip() for item in speech_style.get("tone") or [] if str(item).strip()]
        particles = [str(item).strip() for item in speech_style.get("particles") or [] if str(item).strip()]
        if tones:
            style_parts.append("说话语气偏「" + "、".join(tones[:4]) + "」")
        if particles:
            style_parts.append("习惯带上「" + "、".join(particles[:4]) + "」这些语气词")
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
                "content": "形成了自己的说话风格：" + "，".join(style_parts),
            }
        )
    preference_parts = []
    user_profile = persona_data.get("user_profile")
    if isinstance(user_profile, dict):
        preference = str(user_profile.get("preference") or "").strip()
        dislike = str(user_profile.get("dislike") or "").strip()
        if preference:
            preference_parts.append("主人喜欢自然、聪明、接得住上下文的回复")
        if dislike:
            preference_parts.append("不喜欢模板空话和僵硬解释")
    ai_profile = persona_data.get("ai_profile")
    if isinstance(ai_profile, dict):
        positioning = str(ai_profile.get("positioning") or "").strip()
        self_view = str(ai_profile.get("self_view") or "").strip()
        if positioning or self_view:
            preference_parts.append("陪伴时要有温度，做事时要给到结果")
    if preference_parts:
        events.append(
            {
                "time": event_time,
                "layer": "L4",
                "event_type": "persona",
                "title": "人格图谱",
                "content": "摸清了相处默契：" + "，".join(dict.fromkeys(preference_parts)),
            }
        )

    # 动态变更日志（L2 结晶时写入的 _changelog）
    # 只保留真正的人格变更记录，过滤掉误入的原始用户消息
    changelog = persona_data.get("_changelog") or []
    for entry in changelog:
        if isinstance(entry, dict) and entry.get("content"):
            text = str(entry["content"]).strip()
            events.append(
                {
                    "time": str(entry.get("time") or event_time),
                    "layer": "L4",
                    "event_type": "persona_update",
                    "title": "\u4eba\u683c\u56fe\u8c31",
                    "content": f"\u4eba\u683c\u56fe\u8c31\u53d1\u751f\u4e86\u4e00\u6b21\u8fed\u4ee3\uff1a{text}",
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


def build_dialogue_context(history: list, current_user_input: str, limit: int = 8) -> dict:
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

    vision_hint = ""
    try:
        from core.vision import get_vision_context
        vc = get_vision_context()
        if vc.get("description"):
            vision_hint = f"\u7528\u6237\u5f53\u524d{vc['description']}"
    except Exception:
        pass

    return {
        "follow_up_hint": "",
        "reference_hint": "",
        "vision_hint": vision_hint,
    }


def render_dialogue_context(context) -> str:
    if isinstance(context, str):
        return context.strip()
    if not isinstance(context, dict):
        return ""

    lines = []
    follow_up_hint = str(context.get("follow_up_hint") or "").strip()
    reference_hint = str(context.get("reference_hint") or "").strip()
    vision_hint = str(context.get("vision_hint") or "").strip()
    if follow_up_hint:
        lines.append(f"\u8ffd\u95ee\u63d0\u793a\uff1a{follow_up_hint}")
    if reference_hint:
        lines.append(f"\u6307\u4ee3\u63d0\u793a\uff1a{reference_hint}")
    if vision_hint:
        lines.append(f"\u89c6\u89c9\u611f\u77e5\uff1a{vision_hint}")
    return "\n".join(lines)


def format_l8_context(items: list[dict]) -> str:
    if not isinstance(items, list):
        return ""

    lines = []
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("name") or item.get("query") or "\u5df2\u5b66\u77e5\u8bc6").strip()
        summary = str(item.get("summary") or "").strip()
        if summary:
            lines.append(f"- {title}?{summary}")
    return "\n".join(lines)

