"""Meta inference helpers for L2 memory storage."""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from storage.persona_profile import normalize_assistant_name_candidate


MEMORY_TYPES = {
    "general",
    "correction",
    "knowledge",
    "preference",
    "goal",
    "project",
    "decision",
    "fact",
    "rule",
}

DAILY_TAG = "\u65e5\u5e38"
TECH_TAG = "\u6280\u672f"
STRUCTURED_TAG = "\u7ed3\u6784\u5316"
QA_TAG = "\u95ee\u7b54"
RECORD_TAG = "\u8bb0\u5f55"

EXPLICIT_CALL_ME_RE = re.compile(r"^(?:\u53eb\u6211|\u79f0\u547c\u6211)([^\s\uff0c,\u3002\u3001\uff01!\uff1f?]{1,8})$")
CALL_ME_BLOCKERS = (
    "\u770b\u770b",
    "\u67e5\u67e5",
    "\u8bd5\u8bd5",
    "\u60f3\u60f3",
    "\u95ee\u95ee",
    "\u4e00\u4e0b",
    "\u4e00\u773c",
    "\u6267\u884c",
    "\u5904\u7406",
    "\u5e2e\u6211",
)
PREFERENCE_EXPLICIT_PREFIXES = (
    "\u6211\u559c\u6b22",
    "\u6211\u4e0d\u559c\u6b22",
    "\u6211\u8ba8\u538c",
    "\u6211\u504f\u597d",
    "\u6211\u66f4\u559c\u6b22",
)
META_DISCUSSION_HINTS = (
    "agent",
    "llm",
    "\u67b6\u6784",
    "\u8bed\u4e49",
    "\u6279\u6b21",
    "\u56de\u704c",
    "\u8bbe\u8ba1",
    "\u6d41\u7a0b",
    "\u4e3b\u94fe",
    "\u8def\u7531",
    "\u8bb0\u5fc6",
    "\u5206\u53d1",
    "l1",
    "l2",
    "l3",
    "l4",
    "l5",
    "l6",
    "l7",
    "l8",
)
LOCAL_INTERACTION_DIRECTIVE_CUES = (
    "\u5fc5\u987b",
    "\u52a1\u5fc5",
    "\u4e0d\u8981",
    "\u522b",
    "\u8bf7\u5148",
    "\u5148",
)
LOCAL_INTERACTION_EXECUTION_CUES = (
    "\u8c03\u7528\u5de5\u5177",
    "\u6587\u672c\u91cc\u6a21\u62df",
    "\u5047\u88c5\u6267\u884c",
    "\u76f4\u63a5\u6267\u884c",
    "\u5148\u95ee\u6211",
    "\u5148\u786e\u8ba4",
    "\u95ee\u6211",
)
EXPLICIT_CONFIRM_EXECUTION_RE = re.compile(
    r"^(?:\u8bf7|\u4ee5\u540e\u8bf7|\u4e0b\u6b21\u8bf7|\u8bb0\u4f4f)?"
    r"[^\n\uff0c,\u3002\uff01!\uff1f?]{0,12}"
    r"(?:\u5148(?:\u95ee\u6211|\u786e\u8ba4)|\u95ee\u6211(?:\u540e)?|\u786e\u8ba4(?:\u540e)?)"
    r"[^\n\uff0c,\u3002\uff01!\uff1f?]{0,16}"
    r"(?:\u518d(?:\u6267\u884c|\u64cd\u4f5c|\u5904\u7406)|\u6267\u884c|\u64cd\u4f5c)$"
)
ASSISTANT_RENAME_PATTERNS = (
    re.compile(r"^你以后(?:就)?叫(.+)$"),
    re.compile(r"^以后你(?:就)?叫(.+)$"),
    re.compile(r"^你改名叫(.+)$"),
    re.compile(r"^以后叫你(.+)$"),
    re.compile(r"^以后就叫你(.+)$"),
)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def normalize_context_tag(tag: str) -> str:
    raw = re.sub(r"\s+", "", str(tag or "").strip())
    raw = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9_-]", "", raw)
    return raw[:12] or DAILY_TAG


def extract_json_object(raw: str) -> dict | None:
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


def normalize_profile_updates(payload: dict | None) -> dict:
    data = payload if isinstance(payload, dict) else {}
    normalized = {}
    assistant_name = normalize_assistant_name_candidate(data.get("assistant_name"), max_length=12)
    if assistant_name:
        normalized["assistant_name"] = assistant_name
    user_profile = data.get("user_profile") if isinstance(data.get("user_profile"), dict) else {}
    normalized_user_profile = {}
    for field in ("location", "city"):
        value = str(user_profile.get(field) or "").strip()
        if not value:
            continue
        value = re.sub(r"\s+", " ", value)
        if "\n" in value or len(value) > 80:
            continue
        normalized_user_profile[field] = value
    if normalized_user_profile.get("city") and not normalized_user_profile.get("location"):
        normalized_user_profile["location"] = normalized_user_profile["city"]
    if normalized_user_profile:
        normalized["user_profile"] = normalized_user_profile
    return normalized


def call_memory_meta_llm(prompt: str, *, llm_call, think, debug_write: Callable[[str, dict], None]) -> dict | None:
    raw = ""
    try:
        if llm_call:
            raw = str(llm_call(prompt) or "")
        elif think:
            result = think(prompt, "")
            raw = str(result.get("reply", "") if isinstance(result, dict) else result or "")
    except Exception as exc:
        debug_write("l2_meta_llm_err", {"err": str(exc)})
        return None
    payload = extract_json_object(raw)
    if payload is None and raw.strip():
        debug_write("l2_meta_llm_invalid", {"raw": raw[:160]})
    return payload


def call_yes_no_llm(prompt: str, *, llm_call, think, debug_write: Callable[[str, dict], None]) -> bool | None:
    raw = ""
    try:
        if llm_call:
            raw = str(llm_call(prompt) or "")
        elif think:
            result = think(prompt, "")
            raw = str(result.get("reply", "") if isinstance(result, dict) else result or "")
    except Exception as exc:
        debug_write("l2_yesno_llm_err", {"err": str(exc)})
        return None
    verdict = raw.strip().upper()
    if verdict.startswith("YES"):
        return True
    if verdict.startswith("NO"):
        return False
    if verdict:
        debug_write("l2_yesno_llm_invalid", {"raw": raw[:80]})
    return None


def contains_any(text: str, needles: tuple[str, ...]) -> bool:
    raw = str(text or "")
    return any(needle in raw for needle in needles)


def looks_like_meta_discussion(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return False
    hits = sum(1 for needle in META_DISCUSSION_HINTS if needle in lowered)
    if hits >= 2:
        return True
    return "\n" in str(text or "") and hits >= 1


def is_explicit_call_me_phrase(text: str) -> bool:
    compact = re.sub(r"\s+", "", str(text or "").strip())
    match = EXPLICIT_CALL_ME_RE.fullmatch(compact)
    if not match:
        return False
    target = match.group(1)
    return not contains_any(target, CALL_ME_BLOCKERS)


def extract_explicit_assistant_name(text: str) -> str:
    raw = str(text or "").strip()
    if not raw or "\n" in raw:
        return ""
    compact = re.sub(r"\s+", "", raw)
    for pattern in ASSISTANT_RENAME_PATTERNS:
        match = pattern.fullmatch(compact)
        if not match:
            continue
        candidate = normalize_assistant_name_candidate(match.group(1), max_length=12)
        if candidate and not contains_any(candidate, CALL_ME_BLOCKERS):
            return candidate
    return ""


def looks_like_explicit_interaction_shape(text: str) -> bool:
    compact = normalize_interaction_rule_text(text)
    if not compact or looks_like_meta_discussion(compact):
        return False
    if is_explicit_call_me_phrase(compact):
        return True
    if EXPLICIT_CONFIRM_EXECUTION_RE.fullmatch(compact):
        return True
    has_execution_cue = contains_any(compact, LOCAL_INTERACTION_EXECUTION_CUES)
    if not has_execution_cue:
        return False
    stripped = re.sub(r"^(?:\u4f60|\u8bf7\u4f60|\u4f60\u8981|\u4f60\u5f97)", "", compact).strip()
    return stripped.startswith(LOCAL_INTERACTION_DIRECTIVE_CUES)


def looks_like_explicit_preference_shape(text: str) -> bool:
    compact = normalize_preference_text(text)
    if not compact or looks_like_meta_discussion(compact):
        return False
    if is_explicit_call_me_phrase(compact):
        return True
    return compact.startswith(PREFERENCE_EXPLICIT_PREFIXES)


def normalize_interaction_rule_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())[:160]


def is_explicit_interaction_rule(
    text: str,
    *,
    llm_call,
    think,
    debug_write: Callable[[str, dict], None],
    normalize_signal_text: Callable[[str], str],
) -> bool:
    raw = str(text or "").strip()
    normalized = normalize_signal_text(raw)
    if not normalized or len(normalized) < 4:
        return False

    compact = normalize_interaction_rule_text(raw)
    if not compact or "\n" in raw or len(compact) > 80:
        return False
    if looks_like_explicit_interaction_shape(compact):
        return True

    if llm_call or think:
        verdict = call_yes_no_llm(
            "Decide whether the following user message should be stored into "
            "L4 interaction_rules. Answer YES only when it clearly constrains "
            "how the assistant should interact or execute in future turns. "
            "Answer NO for architecture discussion, design analysis, one-off "
            "explanations, reasoning notes, or general opinions. Reply with "
            "YES or NO only.\n"
            f"User message: {raw[:280]}",
            llm_call=llm_call,
            think=think,
            debug_write=debug_write,
        )
        if verdict is not None:
            return verdict
    return False


def normalize_preference_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())[:160]


def is_explicit_preference_statement(
    text: str,
    *,
    llm_call,
    think,
    debug_write: Callable[[str, dict], None],
    normalize_signal_text: Callable[[str], str],
) -> bool:
    raw = str(text or "").strip()
    normalized = normalize_preference_text(raw)
    if not normalized or len(normalize_signal_text(normalized)) < 4:
        return False

    if "\n" in raw or len(normalized) > 100:
        return False
    if looks_like_explicit_preference_shape(normalized):
        return True

    if llm_call or think:
        verdict = call_yes_no_llm(
            "Decide whether the following user message should be stored into "
            "L4 user_profile.preference. Answer YES only when it clearly "
            "expresses a stable user preference, aversion, naming preference, "
            "or interaction-style preference. Answer NO for architecture "
            "discussion, technical analysis, one-off task instructions, or "
            "general observations. Reply with YES or NO only.\n"
            f"User message: {raw[:280]}",
            llm_call=llm_call,
            think=think,
            debug_write=debug_write,
        )
        if verdict is not None:
            return verdict
    return False


def default_memory_type(
    text: str,
    ai_text: str = "",
    *,
    build_signal_profile: Callable[[str], set[str]],
    normalize_signal_text: Callable[[str], str],
) -> str:
    profile = build_signal_profile(text)
    normalized = normalize_signal_text(text)
    if not normalized:
        return "general"
    if "meta:question" in profile and len(normalized) >= 6 and len(normalize_signal_text(ai_text)) >= 20:
        return "knowledge"
    if "meta:structured" in profile and len(normalized) >= 12:
        return "project"
    return "general"


def default_knowledge_query(
    text: str,
    ai_text: str = "",
    *,
    build_signal_profile: Callable[[str], set[str]],
    normalize_signal_text: Callable[[str], str],
) -> bool:
    profile = build_signal_profile(text)
    normalized = normalize_signal_text(text)
    return bool(normalized and len(normalized) >= 6 and "meta:question" in profile and len(normalize_signal_text(ai_text)) >= 20)


def default_context_tag(
    text: str,
    ai_text: str = "",
    *,
    build_signal_profile: Callable[[str], set[str]],
    normalize_signal_text: Callable[[str], str],
) -> str:
    merged = "\n".join(part for part in (str(text or "").strip(), str(ai_text or "").strip()) if part).strip()
    normalized = normalize_signal_text(merged)
    if not normalized:
        return DAILY_TAG
    profile = build_signal_profile(merged)
    if re.search(r"[A-Za-z0-9]{2,}", merged):
        return TECH_TAG
    if "meta:structured" in profile and len(normalized) >= 12:
        return STRUCTURED_TAG
    if "meta:question" in profile:
        return QA_TAG
    if len(normalized) >= 16:
        return RECORD_TAG
    return DAILY_TAG


def score_importance_structural(
    text: str,
    ai_text: str = "",
    *,
    build_signal_profile: Callable[[str], set[str]],
    normalize_signal_text: Callable[[str], str],
) -> float:
    normalized = normalize_signal_text(text)
    if not normalized:
        return 0.0
    profile = build_signal_profile(text)
    length = len(normalized)
    if length <= 2:
        return 0.18
    if length <= 4 and "meta:question" not in profile and "meta:structured" not in profile:
        return 0.28

    score = 0.42
    if length >= 6:
        score += 0.06
    if length >= 12:
        score += 0.10
    if length >= 24:
        score += 0.08
    if "meta:question" in profile:
        score += 0.08
    if "meta:structured" in profile:
        score += 0.10
    if "meta:longform" in profile:
        score += 0.05
    if "meta:mixed_script" in profile or re.search(r"[A-Za-z0-9]{2,}", str(text or "")):
        score += 0.05
    if len(normalize_signal_text(ai_text)) >= 20:
        score += 0.04
    return clamp(score, 0.18, 0.88)


def infer_memory_meta(
    text: str,
    ai_text: str = "",
    *,
    llm_call,
    think,
    debug_write: Callable[[str, dict], None],
    build_signal_profile: Callable[[str], set[str]],
    normalize_signal_text: Callable[[str], str],
) -> dict:
    assistant_name = extract_explicit_assistant_name(text)
    default = {
        "importance": score_importance_structural(
            text,
            ai_text,
            build_signal_profile=build_signal_profile,
            normalize_signal_text=normalize_signal_text,
        ),
        "memory_type": default_memory_type(
            text,
            ai_text,
            build_signal_profile=build_signal_profile,
            normalize_signal_text=normalize_signal_text,
        ),
        "knowledge_query": default_knowledge_query(
            text,
            ai_text,
            build_signal_profile=build_signal_profile,
            normalize_signal_text=normalize_signal_text,
        ),
        "context_tag": default_context_tag(
            text,
            ai_text,
            build_signal_profile=build_signal_profile,
            normalize_signal_text=normalize_signal_text,
        ),
        "profile_updates": {},
    }
    if assistant_name:
        default["importance"] = max(float(default["importance"]), 0.92)
        default["memory_type"] = "preference"
        default["context_tag"] = RECORD_TAG
        default["profile_updates"] = {"assistant_name": assistant_name}
    if not (llm_call or think):
        return default

    prompt = (
        "You are NovaCore's memory metadata classifier. Infer fields from "
        "semantics and structure, not from keyword tables.\n"
        f"User message: {str(text or '')[:280]}\n"
        f"Assistant reply: {str(ai_text or '')[:320]}\n\n"
        "Return exactly one JSON object with the following fields:\n"
        f'{{"importance": 0.0, "memory_type": "general", "knowledge_query": false, "context_tag": "{DAILY_TAG}", "profile_updates": {{"assistant_name": "", "user_profile": {{"location": "", "city": ""}}}}}}\n'
        "Requirements:\n"
        "- importance must be between 0 and 1.\n"
        "- memory_type must be one of "
        "general/correction/knowledge/preference/goal/project/decision/fact/rule.\n"
        "- Only label as rule when the user clearly states a stable future "
        "interaction or execution constraint.\n"
        "- Only label as preference when the user clearly states a stable user "
        "preference, aversion, style preference, or naming preference.\n"
        "- Only label as fact when it is a stable user fact.\n"
        "- profile_updates.user_profile.location may be set only when the user "
        "explicitly reveals their own stable current location or base in this "
        "message. Do not infer it from requests, examples, travel plans, or "
        "casual mentions.\n"
        "- profile_updates.assistant_name may be set only when the user explicitly "
        "renames the assistant in this message.\n"
        "- profile_updates.user_profile.city may be set only when that explicit "
        "location is clearly a city. Leave it empty for regions, countries, "
        "neighborhoods, or ambiguous places.\n"
        "- Leave profile_updates as an empty object when there is no explicit "
        "stable profile update grounded in the user's own statement.\n"
        "- knowledge_query means this turn is a genuine knowledge Q&A worth "
        "condensing into L8, not small talk or meta-chat.\n"
        f"- context_tag should be a short 2-6 character topic tag; use {DAILY_TAG} when unsure.\n"
        "- Return JSON only."
    )
    payload = call_memory_meta_llm(prompt, llm_call=llm_call, think=think, debug_write=debug_write)
    if not payload:
        return default

    memory_type = str(payload.get("memory_type") or default["memory_type"]).strip()
    if memory_type not in MEMORY_TYPES:
        memory_type = default["memory_type"]
    context_tag = normalize_context_tag(str(payload.get("context_tag") or default["context_tag"]))

    try:
        importance = clamp(float(payload.get("importance", default["importance"])), 0.0, 1.0)
    except Exception:
        importance = float(default["importance"])

    knowledge_query = payload.get("knowledge_query", default["knowledge_query"])
    if isinstance(knowledge_query, str):
        knowledge_query = knowledge_query.strip().lower() in {"1", "true", "yes"}
    else:
        knowledge_query = bool(knowledge_query)

    normalized_profile_updates = normalize_profile_updates(payload.get("profile_updates"))
    if assistant_name:
        normalized_profile_updates["assistant_name"] = assistant_name
        importance = max(float(importance), 0.92)
        if memory_type == "general":
            memory_type = "preference"

    return {
        "importance": importance,
        "memory_type": memory_type,
        "knowledge_query": knowledge_query,
        "context_tag": context_tag,
        "profile_updates": normalized_profile_updates,
    }
