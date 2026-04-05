import json
import re
from datetime import datetime

from storage.paths import FEEDBACK_RULES_FILE as _FEEDBACK_RULES_FILE

RULES_FILE = _FEEDBACK_RULES_FILE

_llm_call = None
_debug_write = lambda stage, data: None

_PROBLEM_TO_CATEGORY = {
    ("joke", "output_not_matching_intent"): "内容生成",
    ("story", "length_too_short"): "内容生成",
    ("routing", "wrong_skill_selected"): "路由调度",
    ("general", "output_not_matching_intent"): "意图理解",
    ("chat", "fallback_too_generic"): "交互风格",
}
_ALLOWED_CATEGORIES = {"内容生成", "路由调度", "意图理解", "交互风格"}
_ALLOWED_TYPES = {"llm_rule", "skill_route", "execution_policy", "user_pref"}
_ALLOWED_SCENES = {"joke", "story", "routing", "general", "chat"}
_ALLOWED_PROBLEMS = {
    "output_not_matching_intent",
    "length_too_short",
    "wrong_skill_selected",
    "fallback_too_generic",
    "generic_feedback",
}
_ALLOWED_LEVELS = {"session", "short_term", "long_term"}


def init(*, llm_call=None, debug_write=None):
    global _llm_call, _debug_write
    if llm_call:
        _llm_call = llm_call
    if debug_write:
        _debug_write = debug_write


def _infer_category(scene: str, problem: str) -> str:
    category = _PROBLEM_TO_CATEGORY.get((scene, problem))
    if category:
        return category
    if scene in {"joke", "story"}:
        return "内容生成"
    if scene == "routing":
        return "路由调度"
    if scene == "chat":
        return "交互风格"
    return "意图理解"


def _load_rules():
    if RULES_FILE.exists():
        try:
            return json.loads(RULES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_rules(rules):
    RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    RULES_FILE.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        from core.rule_runtime import invalidate_constraint_cache

        invalidate_constraint_cache()
    except ImportError:
        pass


def _extract_json_object(raw: str) -> dict | None:
    text = str(raw or "").strip()
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_enum(value, allowed: set[str], fallback: str) -> str:
    text = str(value or "").strip()
    return text if text in allowed else fallback


def _coerce_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"true", "yes", "1"}:
        return True
    if text in {"false", "no", "0"}:
        return False
    return default


def _default_feedback_fix(scene: str, problem: str, user_feedback: str, last_answer: str) -> str:
    if scene == "routing" or problem == "wrong_skill_selected":
        return "adjust_skill_routing_for_scene"
    if scene == "story" and problem == "length_too_short":
        return "story_should_expand_when_user_requests_more"
    if scene == "chat" or problem == "fallback_too_generic":
        return "ability_queries_should_answer_capabilities_directly"
    if problem == "output_not_matching_intent":
        return "keep_observing_and_refine"
    if last_answer and user_feedback:
        short_answer = last_answer[:60].replace("\n", " ")
        short_feedback = user_feedback[:60].replace("\n", " ")
        return f"上次回复「{short_answer}」，用户说「{short_feedback}」，下次要按用户纠正的方向调整"
    return "keep_observing_and_refine"


def _default_feedback_rule(
    user_feedback: str,
    last_question: str = "",
    last_answer: str = "",
    *,
    is_feedback: bool = False,
) -> dict:
    scene = "general"
    problem = "generic_feedback"
    return {
        "is_feedback": bool(is_feedback),
        "category": _infer_category(scene, problem),
        "type": "user_pref",
        "scene": scene,
        "problem": problem,
        "fix": _default_feedback_fix(scene, problem, user_feedback, last_answer),
        "level": "session",
    }


def _normalize_feedback_result(
    result: dict | None,
    user_feedback: str,
    last_question: str = "",
    last_answer: str = "",
) -> dict:
    default = _default_feedback_rule(user_feedback, last_question, last_answer, is_feedback=False)
    if not isinstance(result, dict):
        return default

    scene = _normalize_enum(result.get("scene"), _ALLOWED_SCENES, default["scene"])
    problem = _normalize_enum(result.get("problem"), _ALLOWED_PROBLEMS, default["problem"])
    category = _normalize_enum(result.get("category"), _ALLOWED_CATEGORIES, _infer_category(scene, problem))
    rule_type = _normalize_enum(
        result.get("type"),
        _ALLOWED_TYPES,
        "skill_route" if scene == "routing" else default["type"],
    )
    level = _normalize_enum(result.get("level"), _ALLOWED_LEVELS, default["level"])
    fix = str(result.get("fix") or "").strip()[:180] or _default_feedback_fix(
        scene, problem, user_feedback, last_answer
    )
    has_specific = any(
        [
            scene != default["scene"],
            problem != default["problem"],
            rule_type != default["type"],
            category != default["category"],
        ]
    )

    return {
        "is_feedback": _coerce_bool(result.get("is_feedback"), default=has_specific),
        "category": category,
        "type": rule_type,
        "scene": scene,
        "problem": problem,
        "fix": fix,
        "level": level,
    }


def _classify_feedback_with_llm(user_feedback: str, last_question: str = "", last_answer: str = "") -> dict | None:
    if not _llm_call:
        return None
    prompt = (
        "你是 NovaCore 的反馈分类器。根据上一轮用户问题、上一轮助手回复、以及用户这轮输入，"
        "判断用户这轮话是不是在纠正或投诉上一轮系统行为。\n"
        "只返回一个 JSON 对象，不要解释。\n"
        'JSON 格式: {"is_feedback": true, "category": "...", "type": "...", "scene": "...", '
        '"problem": "...", "fix": "...", "level": "..."}\n'
        "允许的 category: 内容生成, 路由调度, 意图理解, 交互风格\n"
        "允许的 type: llm_rule, skill_route, execution_policy, user_pref\n"
        "允许的 scene: joke, story, routing, general, chat\n"
        "允许的 problem: output_not_matching_intent, length_too_short, wrong_skill_selected, fallback_too_generic, generic_feedback\n"
        "允许的 level: session, short_term, long_term\n"
        "判断标准:\n"
        "- routing: 用户在指出走错技能、误触发工具、错误打开窗口、执行流程走偏。\n"
        "- story + length_too_short: 用户是在要求故事/内容更长。\n"
        "- joke/general + output_not_matching_intent: 用户指出回答跑偏、答非所问、没有理解意图。\n"
        "- chat + fallback_too_generic: 用户指出回答太空泛、太模板、能力回答不直接。\n"
        "- generic_feedback: 确实是纠偏，但不属于上面几类。\n"
        "- 如果这轮输入其实是一个新问题、新请求或普通闲聊，不是在纠正上一轮，则返回 {\"is_feedback\": false}。\n"
        "- fix 用一句简短、可执行的英文 snake_case 或中文规则描述；拿不准可写 keep_observing_and_refine。\n"
        f"上一轮用户问题: {last_question[:120]}\n"
        f"上一轮助手回复: {last_answer[:180]}\n"
        f"当前用户输入: {user_feedback[:120]}"
    )
    try:
        raw = str(_llm_call(prompt) or "")
    except Exception as exc:
        _debug_write("l7_classify_llm_err", {"err": str(exc)})
        return None
    payload = _extract_json_object(raw)
    if payload is None and raw.strip():
        _debug_write("l7_classify_llm_invalid", {"raw": raw[:160]})
    return payload


def inspect_feedback(user_feedback: str, last_question: str = "", last_answer: str = "") -> dict:
    result = _classify_feedback_with_llm(user_feedback, last_question, last_answer)
    normalized = _normalize_feedback_result(result, user_feedback, last_question, last_answer)
    _debug_write(
        "l7_classify_result",
        {
            "is_feedback": normalized.get("is_feedback"),
            "scene": normalized.get("scene"),
            "problem": normalized.get("problem"),
            "source": "llm" if result else "fallback",
        },
    )
    return normalized


def classify_feedback(user_feedback: str, last_question: str = "", last_answer: str = "") -> dict:
    result = inspect_feedback(user_feedback, last_question, last_answer)
    return {key: value for key, value in result.items() if key != "is_feedback"}


def _condense_fix(user_feedback: str, last_question: str, last_answer: str, raw_fix: str) -> str:
    if not _llm_call:
        return raw_fix
    if not last_question and not user_feedback:
        return raw_fix
    try:
        prompt = (
            "你是经验凝结器。以下是一次对话纠偏：\n"
            f"用户上一次问：「{last_question[:100]}」\n"
            f"AI 回复：「{last_answer[:150]}」\n"
            f"用户纠正说：「{user_feedback[:100]}」\n\n"
            "请用一句话总结这次纠偏的核心教训，格式："
            "「当用户问XX时，不要YY，应该ZZ」\n"
            "要求：\n"
            "1. 只输出一句话，不超过50字\n"
            "2. 具体可执行，不要笼统的“注意用户感受”\n"
            "3. 去掉表情、语气词和角色扮演"
        )
        result = _llm_call(prompt)
        if result and len(str(result).strip()) >= 6:
            condensed = str(result).strip()[:100]
            _debug_write("l7_condense_ok", {"q": last_question[:30], "fix": condensed})
            return condensed
    except Exception as exc:
        _debug_write("l7_condense_err", {"err": str(exc)})
    return raw_fix


def _extract_routing_constraint(
    user_feedback: str, last_question: str, last_answer: str, classified: dict
) -> dict | None:
    _debug_write(
        "l7_constraint_retired",
        {
            "reason": "legacy_keyword_constraint_retired",
            "category": str(classified.get("category", "")),
        },
    )
    return None


_SYSTEM_EXPLANATION_HINTS = (
    "时间戳",
    "系统内置",
    "机制",
    "原理",
    "路径",
    "怎么知道",
    "直接就知道",
    "为什么知道",
    "哪来的",
    "什么时候加",
    "在哪",
    "哪里",
)
_CORRECTION_HINTS = (
    "不对",
    "不是",
    "错",
    "跑偏",
    "答非所问",
    "误触发",
    "乱触发",
    "太空",
    "空话",
    "没理解",
    "没听懂",
    "总是",
    "每次",
    "重复",
    "中断",
    "刷屏",
    "太短",
    "不用",
    "不要",
    "太蠢",
    "弱智",
    "莫名其妙",
    "不对劲",
)
_RECENT_RULE_SCAN_LIMIT = 80


def _looks_like_system_explanation_request(user_feedback: str) -> bool:
    raw = str(user_feedback or "").strip()
    if len(raw) < 4:
        return False
    compact = _normalize_match_text(raw)
    if not compact:
        return False
    has_question_form = any(token in raw for token in ("?", "？", "怎么", "为什么", "如何", "在哪", "哪里", "什么时候"))
    if not has_question_form:
        return False
    if any(_normalize_match_text(token) in compact for token in _CORRECTION_HINTS):
        return False
    return any(_normalize_match_text(token) in compact for token in _SYSTEM_EXPLANATION_HINTS)


def _find_followup_feedback_thread(rules: list[dict], last_question: str) -> dict | None:
    question = str(last_question or "").strip()
    if len(_normalize_match_text(question)) < 4:
        return None
    for rule in reversed(rules[-_RECENT_RULE_SCAN_LIMIT:]):
        if not isinstance(rule, dict) or not rule.get("enabled", True):
            continue
        previous_feedback = str(rule.get("user_feedback", "")).strip()
        if not previous_feedback:
            continue
        if _text_similarity(question, previous_feedback) >= 0.92:
            return rule
    return None


def _find_duplicate_rule(rules: list[dict], candidate: dict) -> dict | None:
    candidate_feedback = str(candidate.get("user_feedback", "")).strip()
    candidate_question = str(candidate.get("last_question", "")).strip()
    candidate_fix = str(candidate.get("fix", "")).strip()
    for rule in reversed(rules[-_RECENT_RULE_SCAN_LIMIT:]):
        if not isinstance(rule, dict) or not rule.get("enabled", True):
            continue
        if str(rule.get("scene", "")) != str(candidate.get("scene", "")):
            continue
        if str(rule.get("problem", "")) != str(candidate.get("problem", "")):
            continue
        if str(rule.get("type", "")) != str(candidate.get("type", "")):
            continue
        feedback_score = _text_similarity(candidate_feedback, str(rule.get("user_feedback", "")))
        question_score = _text_similarity(candidate_question, str(rule.get("last_question", "")))
        fix_score = _text_similarity(candidate_fix, str(rule.get("fix", "")))
        if feedback_score >= 0.92 and (question_score >= 0.55 or fix_score >= 0.75):
            return rule
        if feedback_score >= 0.82 and question_score >= 0.82:
            return rule
    return None


def _merge_feedback_rule(existing: dict, candidate: dict, *, now_iso: str) -> dict:
    existing_count = int(existing.get("feedback_count") or 1)
    existing["feedback_count"] = max(existing_count, 1) + 1
    existing["last_feedback_at"] = now_iso
    existing["updated_at"] = now_iso

    existing_fix = str(existing.get("fix", "")).strip()
    candidate_fix = str(candidate.get("fix", "")).strip()
    if candidate_fix and candidate_fix != "keep_observing_and_refine" and existing_fix in {"", "keep_observing_and_refine"}:
        for key in ("category", "type", "scene", "problem", "fix", "level"):
            if key in candidate:
                existing[key] = candidate[key]

    if candidate.get("constraint") and not existing.get("constraint"):
        existing["constraint"] = candidate["constraint"]

    return existing


def record_feedback_rule(user_feedback: str, last_question: str = "", last_answer: str = "") -> dict | None:
    if _looks_like_system_explanation_request(user_feedback):
        _debug_write(
            "l7_feedback_skip",
            {"feedback": str(user_feedback or "")[:80], "reason": "system_explanation_request"},
        )
        return None

    inspected = inspect_feedback(user_feedback, last_question, last_answer)
    if not inspected.get("is_feedback", False):
        _debug_write("l7_feedback_skip", {"feedback": str(user_feedback or "")[:80], "reason": "not_feedback"})
        return None

    rule = {key: value for key, value in inspected.items() if key != "is_feedback"}
    raw_fix = rule.get("fix", "")
    if raw_fix and raw_fix != "keep_observing_and_refine":
        rule["fix"] = _condense_fix(user_feedback, last_question, last_answer, raw_fix)

    constraint = _extract_routing_constraint(user_feedback, last_question, last_answer, rule)
    rules = _load_rules()
    followup_rule = _find_followup_feedback_thread(rules, last_question)
    if followup_rule:
        _debug_write(
            "l7_feedback_skip",
            {
                "feedback": str(user_feedback or "")[:80],
                "reason": "followup_feedback_thread",
                "parent_rule_id": followup_rule.get("id"),
            },
        )
        return None

    now_iso = datetime.now().isoformat()
    item = {
        "id": f"rule_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        "source": "user_feedback",
        "created_at": now_iso,
        "enabled": True,
        "user_feedback": user_feedback,
        "last_question": last_question,
        "last_answer": last_answer,
        "feedback_count": 1,
        "last_feedback_at": now_iso,
        "hit_count": 0,
        "fail_count": 0,
        "last_hit_at": None,
        **rule,
    }
    if constraint:
        item["constraint"] = constraint

    duplicate_rule = _find_duplicate_rule(rules, item)
    if duplicate_rule:
        merged = _merge_feedback_rule(duplicate_rule, item, now_iso=now_iso)
        _save_rules(rules[-200:])
        _debug_write(
            "l7_feedback_merge",
            {
                "rule_id": merged.get("id"),
                "feedback_count": merged.get("feedback_count"),
                "reason": "duplicate_rule",
            },
        )
        return merged

    rules.append(item)
    _save_rules(rules[-200:])
    return item


def _normalize_match_text(text: str) -> str:
    compact = re.sub(r"\s+", "", str(text or "").lower())
    compact = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", compact)
    return compact


def _char_bigrams(text: str) -> set[str]:
    if len(text) < 2:
        return set()
    return {text[idx : idx + 2] for idx in range(len(text) - 1)}


def _text_similarity(left: str, right: str) -> float:
    lhs = _normalize_match_text(left)
    rhs = _normalize_match_text(right)
    if not lhs or not rhs:
        return 0.0

    score = 0.0
    if min(len(lhs), len(rhs)) >= 4 and (lhs in rhs or rhs in lhs):
        score += 0.45

    lhs_chars = set(lhs)
    rhs_chars = set(rhs)
    if lhs_chars and rhs_chars:
        score += (len(lhs_chars & rhs_chars) / max(min(len(lhs_chars), len(rhs_chars)), 1)) * 0.2

    lhs_bigrams = _char_bigrams(lhs)
    rhs_bigrams = _char_bigrams(rhs)
    if lhs_bigrams and rhs_bigrams:
        overlap = len(lhs_bigrams & rhs_bigrams) / max(min(len(lhs_bigrams), len(rhs_bigrams)), 1)
        score += overlap * 0.45

    return min(score, 1.0)


def search_relevant_rules(user_input: str, limit: int = 3) -> list[dict]:
    text = str(user_input or "").strip()
    if not text or len(text) < 2:
        return []
    rules = _load_rules()
    if not rules:
        return []

    scored = []
    for rule in rules:
        if not isinstance(rule, dict) or not rule.get("enabled", True):
            continue
        last_question = str(rule.get("last_question", ""))
        fix = str(rule.get("fix", ""))
        feedback = str(rule.get("user_feedback", ""))
        if not last_question and not fix and not feedback:
            continue

        score = 0.0
        score += _text_similarity(text, last_question) * 0.55
        score += _text_similarity(text, feedback) * 0.35
        score += _text_similarity(text, fix) * 0.25

        reference = "\n".join(part for part in (last_question, feedback, fix) if part).strip()
        normalized_text = _normalize_match_text(text)
        normalized_reference = _normalize_match_text(reference)
        if normalized_text and normalized_reference and min(len(normalized_text), len(normalized_reference)) >= 6:
            if normalized_text in normalized_reference or normalized_reference in normalized_text:
                score += 0.2

        if score > 0.2:
            scored.append((score, rule))

    scored.sort(key=lambda item: item[0], reverse=True)
    matched = [item[1] for item in scored[:limit]]

    if matched:
        try:
            all_rules = _load_rules()
            matched_ids = {rule.get("id") for rule in matched if rule.get("id")}
            dirty = False
            updated_rows = {}
            for rule in all_rules:
                if rule.get("id") in matched_ids:
                    rule["hit_count"] = (rule.get("hit_count") or 0) + 1
                    rule["last_hit_at"] = datetime.now().isoformat()
                    updated_rows[rule.get("id")] = {
                        "hit_count": rule["hit_count"],
                        "last_hit_at": rule["last_hit_at"],
                    }
                    dirty = True
            if dirty:
                _save_rules(all_rules)
            for item in matched:
                row = updated_rows.get(item.get("id"))
                if row:
                    item["hit_count"] = row["hit_count"]
                    item["last_hit_at"] = row["last_hit_at"]
        except Exception:
            pass

    return matched


def format_l7_context(rules: list[dict]) -> str:
    if not rules:
        return ""
    lines = []
    for rule in rules:
        fix = str(rule.get("fix", "")).strip()
        category = rule.get("category", "")
        last_question = str(rule.get("last_question", ""))[:40]
        feedback = str(rule.get("user_feedback", ""))[:40]
        if fix and fix != "keep_observing_and_refine":
            lines.append(f"· [{category}] {fix}")
        elif last_question and feedback:
            lines.append(f"· 用户问「{last_question}」时说过「{feedback}」，注意避免同样的问题")
    return "\n".join(lines)
