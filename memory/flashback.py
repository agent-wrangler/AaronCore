# 闪回引擎 — 对话中自动关联旧记忆
# 用户说话时扫描情绪/任务连续性线索 → 搜 L3+L2 → 命中则返回 hint
# hint 只注入 prompt，不改变 chat.py 主链顺序

import json
import re

from storage.paths import PRIMARY_STATE_DIR

_LOW_SIGNAL_TEXTS = {"好", "嗯", "行", "可以", "好的", "哈哈", "收到", "知道了"}
L2_FILE = PRIMARY_STATE_DIR / "l2_short_term.json"


def _is_low_signal_text(text: str) -> bool:
    text = str(text or "").strip()
    if not text:
        return True
    if text in _LOW_SIGNAL_TEXTS:
        return True
    return len(text) <= 2


def _load_l3() -> list:
    """直接读 L3 长期记忆。"""
    try:
        path = PRIMARY_STATE_DIR / "long_term.json"
        data = json.loads(path.read_text("utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _load_l2_recent(limit: int = 240) -> list:
    """直接读取最近一段 L2，用于闪回联想，而不是走显式检索。"""
    try:
        data = json.loads(L2_FILE.read_text("utf-8"))
        if not isinstance(data, list):
            return []
        return list(reversed(data[-limit:]))
    except Exception:
        return []


def _search_l2_backstop(query: str, limit: int = 4) -> list:
    """只给强任务连续性场景兜底，不把闪回退回成普通检索。"""
    try:
        from .l2_memory import search_relevant

        return search_relevant(query, limit=limit)
    except Exception:
        return []


def _bigram_echo(query_norm: str, cand_norm: str) -> float:
    if len(query_norm) < 2 or len(cand_norm) < 2:
        return 0.0
    grams = {query_norm[idx:idx + 2] for idx in range(len(query_norm) - 1)}
    if not grams:
        return 0.0
    hits = sum(1 for gram in grams if gram in cand_norm)
    return hits / max(len(grams), 1)


def _lexical_echo(user_input: str, candidate_text: str) -> float:
    try:
        from .l2_memory import _normalize_signal_text, _normalize_signature_anchor

        query_norm = _normalize_signal_text(user_input)
        cand_norm = _normalize_signal_text(candidate_text)
        query_anchor = _normalize_signature_anchor(user_input)
        cand_anchor = _normalize_signature_anchor(candidate_text)
    except Exception:
        query_norm = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", str(user_input or "").lower())
        cand_norm = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", str(candidate_text or "").lower())
        query_anchor = query_norm[:8]
        cand_anchor = cand_norm[:8]

    if not query_norm or not cand_norm:
        return 0.0
    if query_norm == cand_norm or (query_anchor and cand_anchor and query_anchor == cand_anchor):
        return 1.0
    if len(cand_anchor) >= 3 and (cand_anchor in query_anchor or query_anchor in cand_anchor):
        return 0.82
    if query_norm in cand_norm or cand_norm in query_norm:
        return 0.72
    if re.fullmatch(r"[\u4e00-\u9fff]{2,6}", query_norm) and query_norm[-1] in cand_norm:
        return 0.44
    return min(_bigram_echo(query_norm, cand_norm) * 0.68, 0.62)


def _resonance_score(query_profile: set[str], candidate_profile: set[str]) -> float:
    try:
        from .l2_memory import _signal_overlap

        return _signal_overlap(query_profile, candidate_profile)
    except Exception:
        if not query_profile or not candidate_profile:
            return 0.0
        shared = query_profile & candidate_profile
        if not shared:
            return 0.0
        return min(len(shared) / max(len(query_profile), 1), 1.0)


def _profile_content_tokens(profile: set[str]) -> set[str]:
    return {item for item in profile if str(item).startswith("tok:")}


def _has_strong_theme(query_profile: set[str]) -> bool:
    content = _profile_content_tokens(query_profile)
    if not content:
        return False
    longest = max(len(item.split(":", 1)[1]) for item in content if ":" in item)
    dense = sum(1 for item in content if len(item.split(":", 1)[1]) >= 3)
    return longest >= 4 or dense >= 3


def _should_use_backstop(user_input: str, query_profile: set[str], query_anchor: str) -> bool:
    raw = str(user_input or "").strip()
    anchor = str(query_anchor or "").strip()
    if len(anchor) >= 6:
        return True
    if "meta:question" in query_profile and len(anchor) >= 3:
        return True
    if re.search(r"[A-Za-z0-9]{6,}", raw):
        return True
    if len(anchor) >= 5 and len(raw) <= 24 and _has_strong_theme(query_profile):
        return True
    return False


def _score_l3_candidate(user_input: str, query_profile: set[str], mem: dict) -> float:
    event = str(mem.get("event") or mem.get("summary") or "").strip()
    if not event or _is_low_signal_text(event):
        return 0.0
    try:
        from .l2_memory import build_signal_profile, _freshness

        candidate_profile = build_signal_profile(event)
        freshness = _freshness(mem.get("created_at", ""))
    except Exception:
        candidate_profile = set()
        freshness = 0.5

    resonance = _resonance_score(query_profile, candidate_profile)
    lexical = _lexical_echo(user_input, event)
    if resonance <= 0 and lexical <= 0:
        return 0.0
    if _has_strong_theme(query_profile) and resonance < 0.28 and lexical < 0.42:
        return 0.0
    source_bonus = 0.08 if str(mem.get("source") or "").strip() == "l2_crystallize" else 0.03
    return resonance * 0.62 + lexical * 0.18 + freshness * 0.08 + source_bonus


def _score_l2_candidate(user_input: str, query_profile: set[str], mem: dict) -> float:
    user_text = str(mem.get("user_text") or "").strip()
    ai_text = str(mem.get("ai_text") or "").strip()
    text = f"{user_text} {ai_text}".strip()
    if _is_low_signal_text(user_text):
        return 0.0

    try:
        from .l2_memory import build_signal_profile, classify_retention_bucket, _freshness

        candidate_profile = build_signal_profile(text)
        retention = classify_retention_bucket(mem)
        freshness = _freshness(mem.get("created_at", ""))
    except Exception:
        candidate_profile = set()
        retention = {"tier": "compress"}
        freshness = 0.5

    if retention.get("tier") == "prune":
        return 0.0

    resonance = _resonance_score(query_profile, candidate_profile)
    lexical = _lexical_echo(user_input, text)
    if resonance <= 0 and lexical < 0.45:
        return 0.0
    if _has_strong_theme(query_profile) and resonance < 0.28 and lexical < 0.42:
        return 0.0

    memory_type = str(mem.get("memory_type") or "general").strip().lower() or "general"
    retention_bonus = 0.08 if retention.get("tier") == "keep" else 0.03
    type_bonus = 0.1 if memory_type in ("project", "decision", "rule", "fact", "preference", "goal") else 0.05
    exact_bonus = 0.12 if lexical >= 1.0 else 0.0

    return resonance * 0.5 + lexical * 0.18 + freshness * 0.12 + retention_bonus + type_bonus + exact_bonus


def detect_flashback(user_input: str) -> str | None:
    """
    扫描用户输入，搜索关联旧记忆，返回闪回 hint 或 None。

    返回的 hint 直接注入 system prompt，LLM 决定是否自然融入回复。
    """
    user_input = str(user_input or "").strip()
    if not user_input or len(user_input) < 4:
        return None
    try:
        from .l2_memory import build_signal_profile, _normalize_signature_anchor

        query_profile = build_signal_profile(user_input)
        query_anchor = _normalize_signature_anchor(user_input)
    except Exception:
        query_profile = set()
        query_anchor = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", user_input.lower())[:8]
    if not query_profile and not query_anchor:
        return None

    best = None
    best_score = 0.0
    best_source = ""

    for mem in _load_l3():
        if not isinstance(mem, dict):
            continue
        score = _score_l3_candidate(user_input, query_profile, mem)
        if score > best_score and score >= 0.30:
            best_score = score
            best = mem
            best_source = "l3"

    for mem in _load_l2_recent(limit=240):
        if not isinstance(mem, dict):
            continue
        score = _score_l2_candidate(user_input, query_profile, mem)
        if score > best_score and score >= 0.46:
            best_score = score
            best = mem
            best_source = "l2"

    if _should_use_backstop(user_input, query_profile, query_anchor):
        for mem in _search_l2_backstop(user_input, limit=4):
            if not isinstance(mem, dict):
                continue
            lexical = _lexical_echo(
                user_input,
                f"{str(mem.get('user_text') or '')} {str(mem.get('ai_text') or '')}".strip(),
            )
            if lexical < 0.55 and float(mem.get("relevance") or 0.0) < 0.6:
                continue
            score = _score_l2_candidate(user_input, query_profile, mem) + 0.06
            if score > best_score and score >= 0.54:
                best_score = score
                best = mem
                best_source = "l2"

    if not best:
        return None

    if best_source == "l3":
        event = str(best.get("event") or best.get("summary") or "").strip()
        date = str(best.get("created_at") or "")[:10]
        return (
            f"[联想] 你的记忆里闪过一段画面（{date}）：{event}\n"
            "如果跟当前对话有自然的关联，可以不经意地提到这段记忆，"
            "比如「你说的这个让我想起之前...」。"
            "不要生硬，不相关就完全忽略这条提示。"
        )

    user_text = str(best.get("user_text") or "").strip()[:80]
    date = str(best.get("created_at") or "")[:10]
    return (
        f"[联想] 你隐约记得之前的一段对话（{date}）：主人说过「{user_text}」\n"
        "如果跟现在聊的内容有自然关联，可以不经意地提到。"
        "不要生硬，不相关就完全忽略。"
    )
