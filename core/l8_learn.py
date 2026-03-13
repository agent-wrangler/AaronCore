# L8 自动学习 - 安全版：后台搜索、知识沉淀、主链回流
import json
import re
import threading
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests


ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "memory_db"
KNOWLEDGE_BASE_FILE = STATE_DIR / "knowledge_base.json"
CONFIG_FILE = STATE_DIR / "autolearn_config.json"
_FILE_LOCK = threading.Lock()

DEFAULT_CONFIG = {
    "enabled": True,
    "allow_web_search": True,
    "allow_knowledge_write": True,
    "allow_feedback_relearn": True,
    "allow_skill_generation": False,
    "mode": "shadow",
    "min_query_length": 4,
    "search_timeout_sec": 5,
    "max_results": 5,
    "max_summary_length": 360,
}

GREETING_WORDS = [
    "hi",
    "hello",
    "hey",
    "嗨",
    "你好",
    "哈喽",
    "在吗",
    "早",
    "早安",
    "晚安",
    "谢谢",
    "好的",
    "好吧",
    "哈哈",
    "嘿嘿",
    "嗯",
    "哦",
    "啊",
]

QUESTION_HINTS = [
    "?",
    "？",
    "什么",
    "为啥",
    "为什么",
    "怎么",
    "如何",
    "怎样",
    "区别",
    "原理",
    "意思",
    "教程",
    "步骤",
    "办法",
    "能不能",
    "可不可以",
    "哪里",
    "哪个",
    "谁是",
    "是否",
]

GENERIC_QUESTION_PHRASES = [
    "什么是",
    "什么",
    "为什么",
    "为啥",
    "怎么做",
    "怎么",
    "如何",
    "怎样",
    "区别",
    "原理",
    "意思",
    "教程",
    "步骤",
    "办法",
    "能不能",
    "可不可以",
    "是否",
    "请问",
]

COMMON_KEYWORDS = [
    "mcp",
    "fastapi",
    "python",
    "javascript",
    "api",
    "模型",
    "提示词",
    "联网",
    "股票",
    "天气",
    "图像",
    "自动化",
    "教程",
    "原理",
]


FEEDBACK_PROBLEM_HINTS = {
    "output_not_matching_intent": "上次回复方向跑偏了",
    "length_too_short": "上次给得太短，没有把内容展开",
    "wrong_skill_selected": "上次技能走错了，没贴住真正场景",
    "fallback_too_generic": "上次回答太空，像模板话",
    "generic_feedback": "上次没有真正接住用户想问的点",
}

FEEDBACK_FIX_HINTS = {
    "humor_request_should_use_llm_generation": "遇到玩笑、段子、内容生成类请求，直接给出内容，不要答成说明文",
    "story_should_expand_when_user_requests_more": "用户要更长一点时，把内容继续展开，不要草草收住",
    "adjust_skill_routing_for_scene": "先重新判断场景和工具，不要急着走错技能",
    "ability_queries_should_answer_capabilities_directly": "能力类问题先直接说清能做什么，不要回模板空话",
    "keep_observing_and_refine": "结合上下文把问题接住，再把回答收得更贴近用户真正想要的点",
}


def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_query(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _clean_text(text: str, limit: int | None = None) -> str:
    cleaned = re.sub(r"<[^>]+>", "", str(text or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if limit and len(cleaned) > limit:
        return cleaned[: max(limit - 1, 1)] + "…"
    return cleaned


def load_autolearn_config() -> dict:
    with _FILE_LOCK:
        stored = _load_json(CONFIG_FILE, {})
        config = dict(DEFAULT_CONFIG)
        if isinstance(stored, dict):
            for key, value in stored.items():
                if key in config:
                    config[key] = value
        if not CONFIG_FILE.exists():
            _write_json(CONFIG_FILE, config)
        return config


def save_autolearn_config(config: dict) -> dict:
    merged = dict(DEFAULT_CONFIG)
    if isinstance(config, dict):
        for key, value in config.items():
            if key in merged:
                merged[key] = value
    with _FILE_LOCK:
        _write_json(CONFIG_FILE, merged)
    return merged


def update_autolearn_config(patch: dict) -> dict:
    current = load_autolearn_config()
    if isinstance(patch, dict):
        for key, value in patch.items():
            if key in current:
                current[key] = value
    return save_autolearn_config(current)


def extract_keywords(text: str) -> list[str]:
    raw = str(text or "").strip()
    lowered = raw.lower()
    keywords = []
    cleaned_query = raw

    for phrase in GENERIC_QUESTION_PHRASES:
        cleaned_query = re.sub(re.escape(phrase), " ", cleaned_query, flags=re.I)
    cleaned_query = re.sub(r"[？?，。!！、：:（）()\[\]【】“”\"'’‘]", " ", cleaned_query)
    cleaned_query = re.sub(r"\s+", " ", cleaned_query).strip()

    for word in COMMON_KEYWORDS:
        if word in lowered or word in cleaned_query.lower():
            keywords.append(word)

    for token in re.findall(r"[A-Za-z][A-Za-z0-9_\-]{1,}", cleaned_query):
        keywords.append(token.lower())

    for phrase in re.findall(r"[\u4e00-\u9fff]{2,8}", cleaned_query):
        if phrase not in GREETING_WORDS and phrase not in GENERIC_QUESTION_PHRASES:
            keywords.append(phrase)

    if cleaned_query:
        keywords.append(_clean_text(cleaned_query[:12]))

    out = []
    seen = set()
    for item in keywords:
        token = _clean_text(item, 18)
        if token and token not in seen:
            out.append(token)
            seen.add(token)
    return out[:8]


def _entry_text(entry: dict) -> str:
    parts = [
        entry.get("query", ""),
        entry.get("summary", ""),
        entry.get("name", ""),
        entry.get("应用示例", ""),
        entry.get("二级场景", ""),
        entry.get("核心技能", ""),
        " ".join(entry.get("keywords") or entry.get("trigger") or []),
    ]
    return " ".join(str(part or "") for part in parts).lower()


def _entry_has_topic_overlap(query: str, entry: dict) -> bool:
    keywords = extract_keywords(query)
    if not keywords:
        return True

    summary_text = " ".join(
        [
            str(entry.get("summary") or ""),
            str(entry.get("应用示例") or ""),
            " ".join(
                f"{item.get('title', '')} {item.get('snippet', '')}"
                for item in (entry.get("results") or [])
                if isinstance(item, dict)
            ),
        ]
    ).lower()

    ascii_keywords = [item.lower() for item in keywords if re.search(r"[A-Za-z]", item)]
    chinese_keywords = [item for item in keywords if re.search(r"[\u4e00-\u9fff]", item)]

    if ascii_keywords:
        return any(keyword in summary_text for keyword in ascii_keywords)
    if chinese_keywords:
        return any(keyword in summary_text for keyword in chinese_keywords)
    return True


def _score_entry(query: str, entry: dict) -> int:
    normalized_query = _normalize_query(query)
    if not normalized_query:
        return 0

    text = _entry_text(entry)
    score = 0

    if normalized_query == _normalize_query(entry.get("query", "")):
        score += 24
    if normalized_query and normalized_query in text:
        score += 12

    for keyword in extract_keywords(query):
        normalized_keyword = keyword.lower()
        if normalized_keyword and normalized_keyword in text:
            score += 4

    return score


def find_relevant_knowledge(query: str, limit: int = 3, min_score: int = 4, touch: bool = False) -> list[dict]:
    entries = _load_json(KNOWLEDGE_BASE_FILE, [])
    if not isinstance(entries, list):
        return []

    scored = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        if not _entry_has_topic_overlap(query, entry):
            continue
        score = _score_entry(query, entry)
        if score >= min_score:
            scored.append((score, index, entry))

    scored.sort(
        key=lambda item: (
            item[0],
            str(item[2].get("last_used") or item[2].get("最近使用时间") or item[2].get("created_at") or ""),
        ),
        reverse=True,
    )

    if touch and scored:
        for _, index, entry in scored[:limit]:
            entry["hit_count"] = int(entry.get("hit_count", 0) or 0) + 1
            entry["last_used"] = datetime.now().isoformat()
            entries[index] = entry
        with _FILE_LOCK:
            _write_json(KNOWLEDGE_BASE_FILE, entries[-500:])

    results = []
    for _, _, entry in scored[:limit]:
        summary = _clean_text(entry.get("summary") or entry.get("应用示例") or "", 160)
        if not summary:
            continue
        results.append(
            {
                "name": entry.get("name") or entry.get("二级场景") or entry.get("query") or "已学知识",
                "query": entry.get("query") or "",
                "summary": summary,
                "keywords": entry.get("keywords") or entry.get("trigger") or [],
                "created_at": entry.get("created_at") or entry.get("最近使用时间") or "",
            }
        )
    return results


def _format_search_results(results: list[dict]) -> str:
    lines = []
    for item in results:
        title = _clean_text(item.get("title"), 80)
        snippet = _clean_text(item.get("snippet"), 120)
        if title:
            lines.append(f"• {title}")
        if snippet:
            lines.append(f"  {snippet}")
    return "\n".join(lines[:10])


def _build_search_queries(query: str) -> list[str]:
    raw = _clean_text(query, 80)
    queries = [raw]
    keywords = extract_keywords(query)
    if raw and re.search(r"[A-Za-z]", raw) and " " in raw:
        queries.insert(0, f"\"{raw}\"")

    if keywords:
        condensed = " ".join(keywords[:4])
        if condensed and condensed.lower() != raw.lower():
            queries.append(condensed)

        for keyword in keywords:
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9_\-]{1,10}", keyword):
                queries.append(f"{keyword} protocol")
                queries.append(f"{keyword} 技术")
                break

    out = []
    seen = set()
    for item in queries:
        normalized = _normalize_query(item)
        if normalized and normalized not in seen:
            out.append(item)
            seen.add(normalized)
    return out[:4]


def _filter_results_by_query(query: str, results: list[dict]) -> list[dict]:
    if not results:
        return []

    keywords = extract_keywords(query)
    ascii_keywords = [item.lower() for item in keywords if re.search(r"[A-Za-z]", item)]
    chinese_keywords = [item for item in keywords if re.search(r"[\u4e00-\u9fff]", item)]
    normalized_query = _normalize_query(query)
    condensed_ascii = " ".join(ascii_keywords[:4]).strip()

    def overlap_score(item: dict) -> int:
        haystack = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
        score = 0
        ascii_hits = set()
        chinese_hits = set()
        if normalized_query and normalized_query in haystack:
            score += 18
        if condensed_ascii and condensed_ascii in haystack:
            score += 10
        for keyword in ascii_keywords:
            if keyword in haystack:
                score += 6
                ascii_hits.add(keyword)
        for keyword in chinese_keywords:
            if keyword in haystack:
                score += 4
                chinese_hits.add(keyword)
        return score, len(ascii_hits), len(chinese_hits), haystack

    filtered = []
    for item in results:
        score, ascii_hit_count, chinese_hit_count, haystack = overlap_score(item)
        enough_overlap = score > 0 or (not ascii_keywords and not chinese_keywords)
        if ascii_keywords:
            if len(ascii_keywords) >= 2:
                enough_overlap = ascii_hit_count >= 2 or (normalized_query and normalized_query in haystack) or (condensed_ascii and condensed_ascii in haystack)
            else:
                enough_overlap = ascii_hit_count >= 1
        elif chinese_keywords:
            enough_overlap = chinese_hit_count >= 1

        if enough_overlap:
            new_item = dict(item)
            new_item["_score"] = score
            filtered.append(new_item)

    filtered.sort(key=lambda item: item.get("_score", 0), reverse=True)
    if filtered:
        return [{k: v for k, v in item.items() if k != "_score"} for item in filtered[:5]]
    return []


def search_web_results(query: str, max_results: int = 5, timeout_sec: int = 5) -> list[dict]:
    candidates = _build_search_queries(query)
    fallback = []
    has_focus_keywords = bool(extract_keywords(query))

    for candidate in candidates:
        url = f"https://www.bing.com/search?format=rss&q={quote(candidate)}"
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=max(timeout_sec, 3),
        )
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        raw_results = []
        for item in root.findall(".//item"):
            title = item.findtext("title", default="")
            description = item.findtext("description", default="")
            link = item.findtext("link", default="")
            cleaned_title = _clean_text(title, 90)
            cleaned_desc = _clean_text(description, 180)
            if cleaned_title:
                raw_results.append(
                    {
                        "title": cleaned_title,
                        "snippet": cleaned_desc,
                        "link": link.strip(),
                    }
                )
            if len(raw_results) >= max_results:
                break

        filtered = _filter_results_by_query(query, raw_results)
        if filtered:
            return filtered[:max_results]
        if raw_results and not fallback:
            fallback = raw_results[:max_results]

    if has_focus_keywords:
        return []
    return fallback[:max_results]


def search_web(query: str):
    try:
        config = load_autolearn_config()
        results = search_web_results(query, max_results=int(config.get("max_results", 5)), timeout_sec=int(config.get("search_timeout_sec", 5)))
        if not results:
            return None
        return _format_search_results(results)
    except Exception:
        return None


def _build_summary(query: str, results: list[dict], max_length: int = 360) -> str:
    if not results:
        return ""

    snippets = []
    for item in results[:3]:
        title = _clean_text(item.get("title"), 48)
        snippet = _clean_text(item.get("snippet"), 88)
        if title and snippet:
            snippets.append(f"{title}：{snippet}")
        elif title:
            snippets.append(title)
    summary = "；".join(snippets)
    return _clean_text(summary, max_length)


def save_learned_knowledge(
    query: str,
    summary: str,
    results: list[dict],
    source: str = "bing_rss",
    extra_fields: dict | None = None,
) -> dict:
    now = datetime.now()
    normalized_query = _normalize_query(query)
    keywords = extract_keywords(query)
    extra = dict(extra_fields or {})

    with _FILE_LOCK:
        data = _load_json(KNOWLEDGE_BASE_FILE, [])
        if not isinstance(data, list):
            data = []

        existing = None
        for item in data:
            if _normalize_query(item.get("query", "")) == normalized_query:
                existing = item
                break

        if existing is None:
            existing = {
                "id": f"l8_{now.strftime('%Y%m%d_%H%M%S_%f')}",
                "source": source,
                "type": "knowledge",
                "query": query,
                "name": _clean_text(query, 24) or "已学知识",
                "summary": summary,
                "keywords": keywords,
                "results": results[:3],
                "created_at": now.isoformat(),
                "last_used": now.isoformat(),
                "hit_count": 0,
                "一级场景": "自主学习",
                "二级场景": f"自动学习-{_clean_text(query, 12)}",
                "核心技能": _clean_text(query, 18) or "新知识",
                "应用示例": summary,
                "最近使用时间": now.strftime("%Y-%m-%d %H:%M:%S"),
                "触发器函数": "l8_web_search",
                "trigger": keywords,
            }
            existing.update(extra)
            data.append(existing)
        else:
            existing["source"] = source or existing.get("source", "bing_rss")
            existing["summary"] = summary or existing.get("summary", "")
            existing["results"] = results[:3] or existing.get("results", [])
            existing["keywords"] = keywords or existing.get("keywords", [])
            existing["last_used"] = now.isoformat()
            existing.update(extra)
            existing["最近使用时间"] = now.strftime("%Y-%m-%d %H:%M:%S")
            existing["应用示例"] = summary or existing.get("应用示例", "")

        _write_json(KNOWLEDGE_BASE_FILE, data[-500:])
        return existing


def build_feedback_learning_query(rule_item: dict) -> str:
    if not isinstance(rule_item, dict):
        return ""

    query = str(rule_item.get("last_question") or "").strip()
    if query:
        return _clean_text(query, 120)

    return _clean_text(rule_item.get("user_feedback") or "", 120)


def _feedback_problem_text(problem: str) -> str:
    key = str(problem or "").strip()
    if not key:
        return "上次回复偏了一点"
    return FEEDBACK_PROBLEM_HINTS.get(key, key.replace("_", " "))


def _feedback_fix_text(fix: str) -> str:
    key = str(fix or "").strip()
    if not key:
        return "先结合上下文把问题接住，再更贴近用户真正想要的结果"
    return FEEDBACK_FIX_HINTS.get(key, key.replace("_", " "))


def _build_feedback_summary(rule_item: dict, web_summary: str = "", max_length: int = 360) -> str:
    question = _clean_text(rule_item.get("last_question") or "", 72)
    feedback = _clean_text(rule_item.get("user_feedback") or "", 60)
    problem_text = _feedback_problem_text(rule_item.get("problem"))
    fix_text = _feedback_fix_text(rule_item.get("fix"))

    parts = []
    if question:
        parts.append(f"这类问题之前问过「{question}」")
    parts.append(problem_text)
    if feedback:
        parts.append(f"用户后来明确说了「{feedback}」")
    parts.append(f"下次优先按这个方向收回答：{fix_text}")
    if web_summary:
        parts.append(f"这次补学到的关键信息：{_clean_text(web_summary, 140)}")
    return _clean_text("；".join(parts), max_length)


def auto_learn_from_feedback(rule_item: dict) -> dict:
    config = load_autolearn_config()
    if not config.get("enabled", True):
        return {"success": False, "reason": "disabled"}
    if not config.get("allow_feedback_relearn", True):
        return {"success": False, "reason": "feedback_relearn_disabled"}
    if not config.get("allow_knowledge_write", True):
        return {"success": False, "reason": "knowledge_write_blocked"}
    if not isinstance(rule_item, dict):
        return {"success": False, "reason": "invalid_rule"}

    query = build_feedback_learning_query(rule_item)
    if not query:
        return {"success": False, "reason": "missing_query"}

    max_length = int(config.get("max_summary_length", 360) or 360)
    extra_fields = {
        "type": "feedback_relearn",
        "name": _clean_text(f"纠偏补学：{query}", 24) or "纠偏补学",
        "feedback_rule_id": rule_item.get("id"),
        "feedback_scene": rule_item.get("scene"),
        "feedback_problem": rule_item.get("problem"),
        "feedback_fix": rule_item.get("fix"),
        "feedback_source": rule_item.get("source") or "user_feedback",
        "from_feedback": True,
    }

    base_summary = _build_feedback_summary(rule_item, max_length=max_length)
    entry = save_learned_knowledge(
        query,
        base_summary,
        [],
        source="feedback_relearn",
        extra_fields=extra_fields,
    )

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

    web_summary = _build_summary(query, results, max_length=max(max_length // 2, 180))
    combined_summary = _build_feedback_summary(rule_item, web_summary=web_summary, max_length=max_length)
    entry = save_learned_knowledge(
        query,
        combined_summary,
        results,
        source="feedback_relearn",
        extra_fields=extra_fields,
    )
    return {
        "success": True,
        "type": "feedback_relearn",
        "reason": "relearned",
        "entry": entry,
        "summary": combined_summary,
        "used_web": True,
        "result_count": len(results),
    }


def should_trigger_auto_learn(user_input: str, route_result: dict | None = None, has_relevant_knowledge: bool = False, config: dict | None = None) -> tuple[bool, str]:
    cfg = config or load_autolearn_config()
    text = str(user_input or "").strip()
    lowered = text.lower()

    if not cfg.get("enabled", True):
        return False, "disabled"
    if not cfg.get("allow_web_search", True) or not cfg.get("allow_knowledge_write", True):
        return False, "permission_blocked"
    if has_relevant_knowledge:
        return False, "already_known"
    if len(text) < int(cfg.get("min_query_length", 4) or 4):
        return False, "too_short"
    if text.lower() in GREETING_WORDS:
        return False, "greeting"
    if any(text == word or text.startswith(word + "呀") or text.startswith(word + "啊") for word in GREETING_WORDS):
        return False, "greeting"

    if route_result and route_result.get("mode") in ("skill", "hybrid") and route_result.get("skill") not in ("none", "", None):
        return False, "handled_by_skill"

    is_question_like = any(hint in lowered or hint in text for hint in QUESTION_HINTS)
    if not is_question_like:
        return False, "not_question_like"

    return True, "eligible"


def auto_learn(user_input: str, ai_response: str = "", route_result: dict | None = None) -> dict:
    config = load_autolearn_config()
    related = find_relevant_knowledge(user_input, limit=1, min_score=6)
    should_run, reason = should_trigger_auto_learn(
        user_input,
        route_result=route_result,
        has_relevant_knowledge=bool(related),
        config=config,
    )
    if not should_run:
        return {"success": False, "reason": reason}

    try:
        results = search_web_results(
            user_input,
            max_results=int(config.get("max_results", 5) or 5),
            timeout_sec=int(config.get("search_timeout_sec", 5) or 5),
        )
    except Exception as exc:
        return {"success": False, "reason": f"search_error:{exc}"}

    if not results:
        return {"success": False, "reason": "no_results"}

    summary = _build_summary(user_input, results, max_length=int(config.get("max_summary_length", 360) or 360))
    if not summary:
        return {"success": False, "reason": "empty_summary"}

    entry = save_learned_knowledge(user_input, summary, results)
    return {
        "success": True,
        "type": "knowledge",
        "entry": entry,
        "summary": summary,
        "result_count": len(results),
    }
