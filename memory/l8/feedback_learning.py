"""Feedback relearning helpers for L8."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime


DEFAULT_PROBLEM_HINTS = {
    "output_not_matching_intent": "上次回复方向跑偏了",
    "length_too_short": "上次给得太短，没有把内容展开",
    "wrong_skill_selected": "上次技能走错了，没贴住真正场景",
    "fallback_too_generic": "上次回答太空，像模板话",
    "generic_feedback": "上次没有真正接住用户想问的点",
}


DEFAULT_FIX_HINTS = {
    "humor_request_should_use_llm_generation": "遇到玩笑、段子、内容生成类请求，直接给出内容，不要答成说明文",
    "story_should_expand_when_user_requests_more": "用户要更长一点时，把内容继续展开，不要草草收住",
    "adjust_skill_routing_for_scene": "先重新判断场景和工具，不要急着走错技能",
    "ability_queries_should_answer_capabilities_directly": "能力类问题先直接说清能做什么，不要回模板空话",
    "keep_observing_and_refine": "结合上下文把问题接住，再把回答收得更贴近用户真正想要的点",
}


def build_feedback_learning_query(
    rule_item: dict,
    *,
    clean_text: Callable[[str, int | None], str],
) -> str:
    if not isinstance(rule_item, dict):
        return ""

    query = str(rule_item.get("last_question") or "").strip()
    if query:
        return clean_text(query, 120)

    return clean_text(rule_item.get("user_feedback") or "", 120)


def feedback_problem_text(problem: str, *, problem_hints: dict[str, str]) -> str:
    key = str(problem or "").strip()
    if not key:
        return "上次回复偏了一点"
    return problem_hints.get(key, key.replace("_", " "))


def feedback_fix_text(fix: str, *, fix_hints: dict[str, str]) -> str:
    key = str(fix or "").strip()
    if not key:
        return "先结合上下文把问题接住，再更贴近用户真正想要的结果"
    return fix_hints.get(key, key.replace("_", " "))


def build_feedback_relearn_preview(
    rule_item: dict,
    summary: str = "",
    *,
    used_web: bool = False,
    build_feedback_learning_query_fn: Callable[[dict], str],
    clean_text: Callable[[str, int | None], str],
    strip_think_content: Callable[[str], str],
) -> dict:
    query = build_feedback_learning_query_fn(rule_item)
    label = "纠偏补学" if used_web else "反馈记录"
    return {
        "id": f"l7_feedback_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        "source": "feedback_relearn",
        "type": "feedback_relearn",
        "query": query,
        "name": clean_text(f"{label}：{query}", 24) or label,
        "summary": strip_think_content(summary),
    }


def build_feedback_summary(
    rule_item: dict,
    *,
    web_summary: str = "",
    max_length: int = 360,
    clean_text: Callable[[str, int | None], str],
) -> str:
    question = clean_text(rule_item.get("last_question") or "", 72)
    feedback = clean_text(rule_item.get("user_feedback") or "", 60)
    last_answer = clean_text(rule_item.get("last_answer") or "", 120)

    parts = []
    if question and feedback:
        parts.append(f"用户问「{question}」")
        if last_answer:
            parts.append(f"Nova 回复了「{last_answer}」")
        parts.append(f"用户纠正说「{feedback}」")
        parts.append("下次遇到类似问题要按用户纠正的方向回答")
    elif question:
        parts.append(f"用户问过「{question}」，上次回答不够好")
    if web_summary:
        parts.append(f"补充信息：{clean_text(web_summary, 140)}")
    return clean_text("；".join(parts), max_length)


def auto_learn_from_feedback(
    rule_item: dict,
    *,
    load_autolearn_config: Callable[[], dict],
    build_feedback_learning_query_fn: Callable[[dict], str],
    build_feedback_summary_fn: Callable[..., str],
    build_feedback_relearn_preview: Callable[[dict, str], dict],
    sanitize_extra_fields: Callable[[dict | None], dict],
    should_trigger_auto_learn: Callable[..., tuple[bool, str]],
    search_web_results: Callable[..., list[dict]],
    build_summary: Callable[..., str],
    clean_text: Callable[[str, int | None], str],
) -> dict:
    config = load_autolearn_config()
    if not config.get("enabled", True):
        return {"success": False, "reason": "disabled"}
    if not config.get("allow_feedback_relearn", True):
        return {"success": False, "reason": "feedback_relearn_disabled"}
    if not isinstance(rule_item, dict):
        return {"success": False, "reason": "invalid_rule"}

    query = build_feedback_learning_query_fn(rule_item)
    if not query:
        return {"success": False, "reason": "missing_query"}

    max_length = int(config.get("max_summary_length", 360) or 360)
    extra_fields = {
        "type": "feedback_relearn",
        "name": clean_text(f"纠偏补学：{query}", 24) or "纠偏补学",
        "feedback_rule_id": rule_item.get("id"),
        "feedback_scene": rule_item.get("scene"),
        "feedback_problem": rule_item.get("problem"),
        "feedback_fix": rule_item.get("fix"),
        "feedback_source": rule_item.get("source") or "user_feedback",
        "from_feedback": True,
    }

    base_summary = build_feedback_summary_fn(rule_item, max_length=max_length)
    entry = build_feedback_relearn_preview(rule_item, base_summary, used_web=False)
    entry.update(sanitize_extra_fields(extra_fields))

    if not config.get("allow_web_search", True):
        return {
            "success": True,
            "type": "feedback_note",
            "reason": "note_only",
            "entry": entry,
            "summary": base_summary,
            "used_web": False,
        }

    should_search, reason = should_trigger_auto_learn(
        query,
        route_result=None,
        has_relevant_knowledge=False,
        config=config,
    )
    if not should_search:
        return {
            "success": True,
            "type": "feedback_note",
            "reason": reason,
            "entry": entry,
            "summary": base_summary,
            "used_web": False,
        }

    try:
        results = search_web_results(
            query,
            max_results=int(config.get("max_results", 5) or 5),
            timeout_sec=int(config.get("search_timeout_sec", 5) or 5),
        )
    except Exception as exc:
        return {
            "success": True,
            "type": "feedback_note",
            "reason": f"search_error:{exc}",
            "entry": entry,
            "summary": base_summary,
            "used_web": False,
        }

    if not results:
        return {
            "success": True,
            "type": "feedback_note",
            "reason": "no_results",
            "entry": entry,
            "summary": base_summary,
            "used_web": False,
        }

    web_summary = build_summary(query, results, max_length=max(max_length // 2, 180))
    combined_summary = build_feedback_summary_fn(rule_item, web_summary=web_summary, max_length=max_length)
    entry = build_feedback_relearn_preview(rule_item, combined_summary, used_web=True)
    entry.update(sanitize_extra_fields(extra_fields))
    return {
        "success": True,
        "type": "feedback_relearn",
        "reason": "relearned",
        "entry": entry,
        "summary": combined_summary,
        "used_web": True,
        "result_count": len(results),
    }
