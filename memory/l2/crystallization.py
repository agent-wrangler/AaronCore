"""Crystallization helpers for L2 memory."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import datetime


KNOWN_CITIES = [
    "常州",
    "北京",
    "上海",
    "苏州",
    "南京",
    "杭州",
    "广州",
    "深圳",
    "大理",
    "成都",
    "重庆",
    "武汉",
    "长沙",
    "西安",
    "天津",
    "青岛",
    "厦门",
    "昆明",
    "贵阳",
    "郑州",
    "济南",
    "合肥",
    "福州",
    "南昌",
    "哈尔滨",
    "长春",
    "沈阳",
    "大连",
    "无锡",
    "宁波",
    "温州",
    "东莞",
    "佛山",
    "珠海",
    "三亚",
    "拉萨",
    "乌鲁木齐",
    "呼和浩特",
    "银川",
    "兰州",
    "西宁",
    "海口",
    "南宁",
    "石家庄",
    "太原",
]


def try_crystallize(
    entry,
    *,
    is_real_knowledge_query: Callable[[str, str], bool],
    to_l7: Callable[[str, str], None],
    to_l8: Callable[[str, str], None],
    try_update_city: Callable[[str], None],
    mark_crystal: Callable[[str], None],
    to_l3: Callable[..., None],
    to_l4: Callable[[str, str], None],
) -> None:
    importance = entry.get("importance", 0)
    memory_type = entry.get("memory_type", "general")
    text = entry.get("user_text", "")
    ai_text = entry.get("ai_text", "")
    context_tag = entry.get("context_tag")
    knowledge_query = entry.get("knowledge_query")

    if memory_type == "correction":
        to_l7(text, ai_text)

    if memory_type == "knowledge" and len(ai_text) > 20:
        if knowledge_query is None:
            knowledge_query = is_real_knowledge_query(text, ai_text)
        if knowledge_query:
            to_l8(text, ai_text)

    try_update_city(text)

    if importance <= 0.7:
        return

    mark_crystal(entry["id"])
    if memory_type in ("event", "milestone", "general", "decision"):
        to_l3(text, memory_type, ai_text=ai_text, context_tag=context_tag)
    if memory_type in ("fact", "preference", "goal", "rule"):
        to_l4(text, memory_type)


def mark_crystal(
    memory_id,
    *,
    load_entries: Callable[[], list],
    save_entries: Callable[[list], None],
) -> None:
    try:
        store = load_entries()
        for item in store:
            if item.get("id") == memory_id:
                item["crystallized"] = True
                break
        save_entries(store)
    except Exception:
        return None


def extract_context_tag(
    text: str,
    ai_text: str = "",
    *,
    infer_memory_meta: Callable[[str, str], dict],
) -> str:
    return str(infer_memory_meta(text, ai_text).get("context_tag") or "日常")


def refine_l3_entry_async(
    user_text: str,
    ai_text: str,
    created_at: str,
    *,
    llm_call,
    think,
    clean_summary: Callable[[str], str],
    load_json_fn: Callable[[object, object], list],
    write_json_fn: Callable[[object, object], None],
    l3_file,
    debug_write: Callable[[str, dict], None],
) -> None:
    prompt = (
        f"用户说：{user_text[:300]}\n"
        f"AI回复：{ai_text[:300]}\n\n"
        "用一句话概括这段对话的核心事件或信息，"
        "保留关键细节（人名、数字、具体事物）。"
        "不要用表情，不要角色扮演，控制在 80 字内。"
    )
    refined = None
    try:
        if llm_call:
            text = (llm_call(prompt) or "").strip()
            if len(text) > 5:
                refined = clean_summary(text)
        if not refined and think:
            result = think(prompt, "")
            text = str(result.get("reply", "") if isinstance(result, dict) else result or "").strip()
            if len(text) > 5:
                refined = clean_summary(text)
    except Exception:
        pass

    if not refined:
        return

    try:
        l3 = load_json_fn(l3_file, [])
        for entry in l3:
            if entry.get("created_at") == created_at and entry.get("source") == "l2_crystallize":
                entry["event"] = refined
                break
        write_json_fn(l3_file, l3)
        debug_write("l2_crystal_l3_refined", {"refined": refined[:50]})
    except Exception:
        pass


def to_l3(
    text,
    memory_type,
    *,
    ai_text="",
    context_tag=None,
    load_json_fn: Callable[[object, object], list],
    write_json_fn: Callable[[object, object], None],
    l3_file,
    normalize_context_tag: Callable[[str], str],
    extract_context_tag: Callable[[str, str], str],
    debug_write: Callable[[str, dict], None],
    llm_call,
    think,
    thread_factory,
    refine_l3_entry_async: Callable[[str, str, str], None],
) -> None:
    try:
        l3 = load_json_fn(l3_file, [])
        for item in l3[-20:]:
            if text in str(item.get("event") or item.get("summary", "")) or str(item.get("event") or item.get("summary", "")) in text:
                return

        tag = normalize_context_tag(context_tag or extract_context_tag(text, ai_text))
        entry = {
            "event": text[:200],
            "raw_ref": text[:200],
            "context_tag": tag,
            "type": "event" if memory_type in ("event", "general", "decision") else memory_type,
            "source": "l2_crystallize",
            "created_at": datetime.now().isoformat(),
        }
        l3.append(entry)
        write_json_fn(l3_file, l3)
        debug_write("l2_crystal_l3", {"text": text[:50], "tag": tag})

        if ai_text and (llm_call or think):
            thread_factory(
                target=refine_l3_entry_async,
                args=(text, ai_text, entry["created_at"]),
                daemon=True,
            ).start()
    except Exception as exc:
        debug_write("l2_crystal_l3_err", {"err": str(exc)})


def append_l4_changelog(persona: dict, content: str) -> None:
    changelog = persona.setdefault("_changelog", [])
    changelog.append(
        {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "content": content,
        }
    )
    if len(changelog) > 50:
        persona["_changelog"] = changelog[-50:]


def try_update_city(
    text,
    *,
    load_json_fn: Callable[[object, object], dict],
    write_json_fn: Callable[[object, object], None],
    l4_file,
    append_l4_changelog: Callable[[dict, str], None],
    debug_write: Callable[[str, dict], None],
) -> None:
    try:
        match = re.search(
            r"(?:\u6211\u5728|\u6211\u4f4f|\u5750\u6807|\u4eba\u5728|\u5b9a\u5c45)([^\s\uff0c,\u3002\u3001\uff01!\uff1f?\u7684\u4e86]+)",
            text,
        )
        if not match:
            return
        candidate = match.group(1).strip()
        for city in KNOWN_CITIES:
            if city in candidate:
                persona = load_json_fn(l4_file, {})
                user_profile = persona.setdefault("user_profile", {})
                old_city = str(user_profile.get("city", "")).strip()
                if old_city != city:
                    user_profile["city"] = city
                    append_l4_changelog(persona, f"用户更新了地址：{city}")
                    write_json_fn(l4_file, persona)
                    debug_write("l2_city_update", {"old": old_city, "new": city})
                return
    except Exception as exc:
        debug_write("l2_city_update_err", {"err": str(exc)})


def to_l4(
    text,
    memory_type,
    *,
    load_json_fn: Callable[[object, object], dict],
    write_json_fn: Callable[[object, object], None],
    l4_file,
    normalize_preference_text: Callable[[str], str],
    is_explicit_preference_statement: Callable[[str], bool],
    normalize_interaction_rule_text: Callable[[str], str],
    is_explicit_interaction_rule: Callable[[str], bool],
    append_l4_changelog: Callable[[dict, str], None],
    debug_write: Callable[[str, dict], None],
) -> None:
    try:
        persona = load_json_fn(l4_file, {})
        updated = False
        if "\u6211\u53eb" in text:
            match = re.search(r"\u6211\u53eb([^\s\uff0c,\u3002\u3001\uff01!\uff1f?]+)", text)
            if match:
                user_profile = persona.setdefault("user_profile", {})
                existing_identity = str(user_profile.get("identity", ""))
                name = match.group(1)
                if name not in existing_identity:
                    user_profile["identity"] = (existing_identity + "\uff0c" + f"\u53eb{name}").strip("\uff0c")
                    updated = True
        if memory_type == "preference":
            preference_text = normalize_preference_text(text)
            if is_explicit_preference_statement(preference_text):
                user_profile = persona.setdefault("user_profile", {})
                existing_pref = str(user_profile.get("preference", ""))
                if preference_text not in existing_pref:
                    user_profile["preference"] = (existing_pref + "\uff1b" + preference_text).strip("\uff1b")
                    updated = True
            else:
                debug_write("l2_l4_preference_skip", {"text": text[:80], "reason": "not_explicit_preference"})
        if memory_type == "rule":
            rule_text = normalize_interaction_rule_text(text)
            if is_explicit_interaction_rule(rule_text):
                rules = persona.setdefault("interaction_rules", [])
                existing = {normalize_interaction_rule_text(item) for item in rules}
                if rule_text and rule_text not in existing:
                    rules.append(rule_text)
                    updated = True
            else:
                debug_write("l2_l4_rule_skip", {"text": text[:80], "reason": "not_explicit_interaction_rule"})
        if updated:
            changelog_labels = {
                "fact": "记录了用户信息",
                "preference": "更新了用户偏好",
                "rule": "新增了交互规则",
                "goal": "记录了用户目标",
            }
            label = changelog_labels.get(memory_type, "更新了用户画像")
            append_l4_changelog(persona, f"{label}：{text[:50]}")
            write_json_fn(l4_file, persona)
            debug_write("l2_crystal_l4", {"text": text[:50]})
    except Exception as exc:
        debug_write("l2_crystal_l4_err", {"err": str(exc)})


def to_l7(
    text,
    ai_text,
    *,
    load_json_fn: Callable[[object, object], list],
    write_json_fn: Callable[[object, object], None],
    l7_file,
    debug_write: Callable[[str, dict], None],
) -> None:
    try:
        l7 = load_json_fn(l7_file, [])
        for item in l7:
            if isinstance(item, dict) and text[:20] in str(item.get("user_feedback", "")):
                return
        l7.append(
            {
                "id": f"l2_fb_{int(time.time() * 1000)}",
                "source": "l2_context",
                "created_at": datetime.now().isoformat(),
                "enabled": True,
                "user_feedback": text,
                "last_answer": ai_text[:200] if ai_text else "",
                "l2_context": "L2检测到用户纠正/不满",
            }
        )
        write_json_fn(l7_file, l7)
        debug_write("l2_crystal_l7", {"text": text[:50]})
    except Exception as exc:
        debug_write("l2_crystal_l7_err", {"err": str(exc)})


def condense_knowledge(
    user_text: str,
    ai_text: str,
    *,
    llm_call,
    debug_write: Callable[[str, dict], None],
) -> str:
    if not llm_call or not ai_text:
        return ""
    try:
        prompt = (
            "你是知识凝结器。以下是一段对话：\n"
            f"用户问：「{user_text[:200]}」\n"
            f"AI回复：「{ai_text[:500]}」\n\n"
            "判断这段对话里是否包含可独立复用的事实/概念/原理。\n"
            "以下情况不是知识：\n"
            "- 讨论AI系统本身（记忆/路由/L2/L3等）\n"
            "- 纯情绪互动/闲聊/角色扮演\n"
            "- 用户吐槽/抱怨/评价AI表现\n\n"
            "如果有知识，用简洁中文提炼2-3句，"
            "去掉表情/语气词/角色扮演语句，只保留知识本身。\n"
            "如果没有可复用知识，只返回两个字：无知识"
        )
        result = llm_call(prompt)
        if not result:
            return ""
        result = result.strip()
        if result in ("无知识", "无", ""):
            debug_write("l2_condense_skip", {"user": user_text[:40], "reason": "no_knowledge"})
            return ""
        if len(result) < 8:
            return ""
        debug_write("l2_condense_ok", {"user": user_text[:40], "len": len(result)})
        return result[:360]
    except Exception as exc:
        debug_write("l2_condense_err", {"err": str(exc)})
        return ""


def to_l8(
    text,
    ai_text,
    *,
    llm_call,
    condense_knowledge: Callable[[str, str], str],
    save_learned_knowledge: Callable[..., object],
    debug_write: Callable[[str, dict], None],
) -> None:
    try:
        summary = condense_knowledge(text, ai_text)
        if not summary:
            if not llm_call:
                summary = ai_text[:500] if ai_text else ""
            else:
                debug_write("l2_crystal_l8_filtered", {"text": text[:50]})
                return

        entry = save_learned_knowledge(
            text,
            summary,
            [],
            source="l2_crystallize",
        )
        if isinstance(entry, dict) and entry.get("saved") is False:
            debug_write(
                "l2_crystal_l8_filtered",
                {"text": text[:50], "reason": entry.get("reason", "")},
            )
            return
        debug_write("l2_crystal_l8", {"text": text[:50]})
    except Exception as exc:
        debug_write("l2_crystal_l8_err", {"err": str(exc)})
