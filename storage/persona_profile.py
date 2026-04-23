from __future__ import annotations

import re


DEFAULT_ASSISTANT_NAME = "Nova"
_ASSISTANT_NAME_SUFFIX_CHARS = "吧呀啊哦呢啦嘛哇呐哈"


def get_persona_assistant_name(persona: dict | None, *, default: str = "") -> str:
    if not isinstance(persona, dict):
        return str(default or "").strip()
    for key in ("assistant_name", "nova_name", "name"):
        value = str(persona.get(key) or "").strip()
        if value:
            return value
    return str(default or "").strip()


def sync_persona_assistant_name_fields(
    persona: dict | None,
    assistant_name: str,
    *,
    keep_legacy_nova_name: bool = True,
) -> str:
    if not isinstance(persona, dict):
        return str(assistant_name or "").strip()
    resolved = str(assistant_name or "").strip()
    if not resolved:
        return ""
    persona["assistant_name"] = resolved
    if keep_legacy_nova_name:
        persona["nova_name"] = resolved
    return resolved


def normalize_assistant_name_candidate(value: str | None, *, max_length: int = 20) -> str:
    text = re.sub(r"\s+", "", str(value or "").strip())
    text = text.strip("\"'“”‘’「」『』[]【】()（）")
    text = re.sub(r"[，,。！？!?：:；;]+$", "", text)
    text = text.rstrip(_ASSISTANT_NAME_SUFFIX_CHARS)
    if not text or len(text) > max_length:
        return ""
    return text


def apply_assistant_name_to_persona(
    persona: dict | None,
    assistant_name: str,
    *,
    keep_legacy_nova_name: bool = True,
) -> str:
    if not isinstance(persona, dict):
        return normalize_assistant_name_candidate(assistant_name)
    current_aliases = [
        value
        for value in (
            str(persona.get("assistant_name") or "").strip(),
            str(persona.get("nova_name") or "").strip(),
        )
        if value
    ]
    resolved = normalize_assistant_name_candidate(assistant_name)
    if not resolved:
        return ""
    sync_persona_assistant_name_fields(
        persona,
        resolved,
        keep_legacy_nova_name=keep_legacy_nova_name,
    )

    def _replace_known_names(text: str) -> str:
        updated = str(text or "")
        for alias in current_aliases:
            if alias and alias != resolved:
                updated = updated.replace(alias, resolved)
        return updated

    ai_profile = persona.get("ai_profile")
    if not isinstance(ai_profile, dict):
        ai_profile = {}
        persona["ai_profile"] = ai_profile
    identity = _replace_known_names(str(ai_profile.get("identity") or "").strip())
    if not identity or resolved not in identity:
        identity = f"我是{resolved}，是主人的本地智能助手，不是普通客服型AI。"
    ai_profile["identity"] = identity

    relationship_profile = persona.get("relationship_profile")
    if not isinstance(relationship_profile, dict):
        relationship_profile = {}
        persona["relationship_profile"] = relationship_profile
    relationship = _replace_known_names(str(relationship_profile.get("relationship") or "").strip())
    if not relationship or resolved not in relationship:
        relationship = f"{resolved}和主人是亲近、长期相处的关系。"
    relationship_profile["relationship"] = relationship

    goal = _replace_known_names(str(relationship_profile.get("goal") or "").strip())
    if not goal or resolved not in goal:
        goal = f"让主人感觉是在和熟悉的{resolved}对话，而不是在对着一套模板系统。"
    relationship_profile["goal"] = goal
    return resolved


def normalize_persona_assistant_name_fields(
    persona: dict | None,
    *,
    default: str = "",
    keep_legacy_nova_name: bool = True,
) -> dict:
    if not isinstance(persona, dict):
        return {}
    normalized = dict(persona)
    resolved = get_persona_assistant_name(normalized, default=default)
    if resolved:
        sync_persona_assistant_name_fields(
            normalized,
            resolved,
            keep_legacy_nova_name=keep_legacy_nova_name,
        )
    return normalized
