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

# ── 依赖注入 ──
_llm_call = None  # 裸 LLM 调用（不带人格），由 agent_final.py 注入
_debug_write = lambda stage, data: None

def init(*, llm_call=None, debug_write=None):
    global _llm_call, _debug_write
    if llm_call: _llm_call = llm_call
    if debug_write: _debug_write = debug_write

DEFAULT_CONFIG = {
    "enabled": True,
    "allow_web_search": True,
    "allow_knowledge_write": True,
    "allow_feedback_relearn": True,
    "allow_self_repair_planning": True,
    "allow_self_repair_test_run": True,
    "allow_self_repair_auto_apply": True,
    "allow_skill_generation": False,
    "mode": "shadow",
    "self_repair_apply_mode": "confirm",
    "self_repair_test_timeout_sec": 45,
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
    "什么是",
    "是什么",
    "为啥",
    "为什么",
    "怎么办",
    "怎么用",
    "怎么做",
    "怎么回事",
    "如何",
    "怎样",
    "区别",
    "什么原理",
    "原理是",
    "什么意思",
    "意思是什么",
    "教程",
    "步骤",
    "办法",
    "哪里",
    "哪个",
    "谁是",
    "是谁",
    "是否",
]

# 用户主动要求 Nova 去学习/搜索的祈使句关键词
LEARNING_HINTS = [
    "去学", "去查", "去搜", "去找", "去研究", "去了解",
    "学一下", "查一下", "搜一下", "找一下", "了解一下",
    "帮我查", "帮我搜", "帮我找", "帮我学",
    "学几本", "查几本", "找几本", "推荐几本",
    "学点", "查点", "搜点", "找点",
    "去看看", "去搜搜", "去查查", "去找找", "去学学",
    "学完", "查完", "搜完",
    "你去学", "你去查", "你去搜",
    "自己去学", "自己去查", "自己学",
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

# ── 一级场景推断 ──────────────────────────────────────────────
# 原始设计的板块：工具应用 / 自主学习 / 内容创作 / 系统能力 / 人物角色 / 系统功能
# feedback scene → 一级场景 映射
_FEEDBACK_SCENE_TO_PRIMARY = {
    "joke": "内容创作",
    "story": "内容创作",
    "routing": "系统能力",
    "chat": "系统功能",
    "general": "",  # 需要进一步推断
}

# 关键词 → 一级场景 的简单规则
_SCENE_KEYWORD_RULES: list[tuple[list[str], str]] = [
    # 工具应用：涉及已注册技能的
    (["天气", "weather", "股票", "stock", "画", "draw", "代码", "run_code"], "工具应用"),
    # 内容创作：创作类
    (["故事", "笑话", "段子", "文案", "脚本", "小说", "诗", "歌词", "创作"], "内容创作"),
    # 人物角色：人设相关
    (["人设", "角色", "性格", "人格", "甜心", "守护"], "人物角色"),
    # 系统能力：路由、技能调度
    (["路由", "技能", "调用", "触发", "弹窗", "误触发"], "系统能力"),
    # 系统功能：能力、设置
    (["设置", "配置", "功能", "能力", "你会什么"], "系统功能"),
]


def _infer_primary_scene(
    query: str = "",
    feedback_scene: str = "",
    route_result: dict | None = None,
) -> str:
    """根据上下文推断知识条目应归入哪个一级场景。"""
    # 1. 如果有 feedback scene 且能直接映射，优先用
    if feedback_scene:
        mapped = _FEEDBACK_SCENE_TO_PRIMARY.get(feedback_scene, "")
        if mapped:
            return mapped

    # 2. 如果 route 指向了某个技能，归入工具应用
    if route_result and isinstance(route_result, dict):
        mode = route_result.get("mode", "")
        skill = route_result.get("skill", "")
        if mode in ("skill", "hybrid") and skill and skill != "none":
            return "工具应用"

    # 3. 关键词匹配
    text = str(query or "").lower()
    for keywords, scene in _SCENE_KEYWORD_RULES:
        if any(kw in text for kw in keywords):
            return scene

    # 4. 默认：自主学习（纯知识类问答）
    return "自主学习"


from core.json_store import load_json as _load_json, write_json as _write_json


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
        # Self-heal legacy config files that are missing newer keys so the
        # frontend can always detect the current preset consistently.
        if (not CONFIG_FILE.exists()) or (not isinstance(stored, dict)) or stored != config:
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
    cleaned_query = re.sub(r"[？?，。!！、：:（）()\[\]【】""\"'’‘]", " ", cleaned_query)
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


def _normalize_tool_skill_name(skill_name: str) -> str:
    name = str(skill_name or "").strip()
    if name.endswith("_query"):
        name = name[:-6]
    return name


def _is_registered_skill_name(skill_name: str) -> bool:
    name = _normalize_tool_skill_name(skill_name)
    if not name:
        return False
    try:
        from core.skills import get_all_skills

        return name in get_all_skills()
    except Exception:
        return False


def should_surface_knowledge_entry(entry: dict) -> bool:
    if not isinstance(entry, dict):
        return False

    primary_scene = str(entry.get("一级场景") or "").strip()
    core_skill = str(entry.get("核心技能") or entry.get("name") or "").strip()

    # 老的"工具应用"补学里混入过并不存在的伪技能，这类条目不该继续影响聊天或记忆页。
    if primary_scene == "工具应用" and core_skill and not _is_registered_skill_name(core_skill):
        return False

    # feedback_relearn 条目质量普遍较低：query 是用户的口语抱怨（如"太短了点"
    # "怎么还是这个纳瓦尔宝典"），keywords 是无意义碎片。这类条目不应出现在
    # 知识检索结果里，它们的价值仅在于记录 feedback_rule，不应作为"已学知识"影响后续对话。
    entry_type = str(entry.get("type") or entry.get("source") or "").strip()
    if entry_type == "feedback_relearn":
        return False

    return True


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

    score = 0

    # 完全匹配原始 query — 最高分
    if normalized_query == _normalize_query(entry.get("query", "")):
        score += 24

    # 关键词匹配 — 只在 keywords/trigger 里匹配（精确），不在 summary 里模糊搜
    entry_keywords = set()
    for k in (entry.get("keywords") or []):
        entry_keywords.add(str(k).lower().strip())
    for k in (entry.get("trigger") or []):
        entry_keywords.add(str(k).lower().strip())

    query_keywords = extract_keywords(query)
    for keyword in query_keywords:
        nk = keyword.lower().strip()
        if len(nk) < 2:
            continue
        if nk in entry_keywords:
            score += 6  # 精确命中 entry 的关键词

    return score


def find_relevant_knowledge(query: str, limit: int = 3, min_score: int = 6, touch: bool = False) -> list[dict]:
    entries = _load_json(KNOWLEDGE_BASE_FILE, [])
    if not isinstance(entries, list):
        return []

    scored = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        if not should_surface_knowledge_entry(entry):
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


def search_web_results(query: str, max_results: int = 5, timeout_sec: int = 5, skip_filter: bool = False) -> list[dict]:
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

        # skip_filter: 跳过严格过滤，直接返回原始结果（交给 LLM 判断相关性）
        if skip_filter and raw_results:
            return raw_results[:max_results]

        filtered = _filter_results_by_query(query, raw_results)
        if filtered:
            return filtered[:max_results]
        if raw_results and not fallback:
            fallback = raw_results[:max_results]

    # 即使过滤没命中，也返回原始结果作为 fallback（总比空结果好）
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


def is_explicit_learning_request(text: str) -> bool:
    """判断用户是否主动要求 Nova 去学习/搜索。"""
    return any(hint in text for hint in LEARNING_HINTS)


def explicit_search_and_learn(search_query: str) -> dict:
    """用户主动要求学习时调用：立即搜索 → 存入知识库 → 返回搜索结果供回复使用。

    Args:
        search_query: 已提取的搜索主题（由调用方通过 LLM 从用户原始输入中提取）。

    Returns:
        {"success": True, "results": [...], "summary": "...", "entry": {...}}
        or {"success": False, "reason": "..."}
    """
    config = load_autolearn_config()
    if not config.get("allow_web_search", True):
        return {"success": False, "reason": "web_search_disabled"}

    query = str(search_query or "").strip()
    if len(query) < 2:
        return {"success": False, "reason": "empty_query"}

    try:
        results = search_web_results(
            query,
            max_results=int(config.get("max_results", 5) or 5),
            timeout_sec=int(config.get("search_timeout_sec", 5) or 5),
            skip_filter=True,  # 用户主动搜索，交给 LLM 判断相关性
        )
    except Exception as exc:
        return {"success": False, "reason": "search_error: " + str(exc)}

    if not results:
        return {"success": False, "reason": "no_results"}

    summary = _build_summary(query, results, max_length=int(config.get("max_summary_length", 360) or 360))
    if not summary:
        return {"success": False, "reason": "empty_summary"}

    # 存入知识库
    entry = None
    if config.get("allow_knowledge_write", True):
        entry = save_learned_knowledge(query, summary, results)

    return {
        "success": True,
        "query": query,
        "results": results,
        "summary": summary,
        "entry": entry,
        "result_count": len(results),
    }


def _build_summary(query: str, results: list[dict], max_length: int = 360) -> str:
    if not results:
        return ""

    # 先拼原始素材
    snippets = []
    for item in results[:3]:
        title = _clean_text(item.get("title"), 48)
        snippet = _clean_text(item.get("snippet"), 88)
        if title and snippet:
            snippets.append(f"{title}：{snippet}")
        elif title:
            snippets.append(title)
    raw_material = "\n".join(snippets)

    # 尝试用 LLM 凝结成高质量知识摘要
    if _llm_call and raw_material:
        try:
            prompt = (
                f"\u4f60\u662f\u77e5\u8bc6\u51dd\u7ed3\u5668\u3002\u7528\u6237\u95ee\u4e86\uff1a\u300c{query}\u300d\n"
                f"\u4ee5\u4e0b\u662f\u641c\u7d22\u7ed3\u679c\uff1a\n{raw_material}\n\n"
                f"\u8bf7\u7528\u7b80\u6d01\u7684\u4e2d\u6587\u603b\u7ed3\u6838\u5fc3\u7b54\u6848\uff0c\u8981\u6c42\uff1a\n"
                f"1. \u53ea\u4fdd\u7559\u6700\u6709\u4ef7\u503c\u7684\u4fe1\u606f\uff0c\u53bb\u6389\u5e7f\u544a\u3001\u65e0\u5173\u5185\u5bb9\u3001\u975e\u4e2d\u6587\u5185\u5bb9\n"
                f"2. \u63a7\u5236\u5728 2-3 \u53e5\u8bdd\u5185\n"
                f"3. \u76f4\u63a5\u8f93\u51fa\u6458\u8981\uff0c\u4e0d\u8981\u52a0\u524d\u7f00"
            )
            condensed = _llm_call(prompt)
            if condensed and len(condensed) > 10:
                _debug_write("l8_condense_ok", {"query": query[:30], "len": len(condensed)})
                return _clean_text(condensed, max_length)
        except Exception as e:
            _debug_write("l8_condense_err", {"err": str(e)})

    # fallback：原始拼接
    summary = "\uff1b".join(snippets)
    return _clean_text(summary, max_length)


def save_learned_knowledge(
    query: str,
    summary: str,
    results: list[dict],
    source: str = "bing_rss",
    extra_fields: dict | None = None,
    feedback_scene: str = "",
    route_result: dict | None = None,
) -> dict:
    now = datetime.now()
    normalized_query = _normalize_query(query)
    keywords = extract_keywords(query)
    # LLM 提取更精准的关键词（补充到规则提取结果中）
    if _llm_call and summary:
        try:
            kw_prompt = (
                f"\u4ece\u4ee5\u4e0b\u77e5\u8bc6\u6458\u8981\u4e2d\u63d0\u53d6 3-5 \u4e2a\u6700\u91cd\u8981\u7684\u4e2d\u6587\u5173\u952e\u8bcd\uff0c\u7528\u4e8e\u540e\u7eed\u68c0\u7d22\u3002\n"
                f"\u95ee\u9898\uff1a{query}\n\u6458\u8981\uff1a{summary[:200]}\n"
                f"\u76f4\u63a5\u8f93\u51fa\u5173\u952e\u8bcd\uff0c\u7528\u9017\u53f7\u5206\u9694\uff0c\u4e0d\u8981\u52a0\u5176\u4ed6\u5185\u5bb9"
            )
            kw_result = _llm_call(kw_prompt)
            if kw_result:
                seen = set(k.lower() for k in keywords)
                for kw in re.split(r'[,\uff0c\u3001\s]+', kw_result.strip()):
                    kw = kw.strip()
                    if kw and len(kw) <= 18 and kw.lower() not in seen:
                        keywords.append(kw)
                        seen.add(kw.lower())
                keywords = keywords[:10]
        except Exception:
            pass
    extra = dict(extra_fields or {})
    primary_scene = _infer_primary_scene(query, feedback_scene=feedback_scene, route_result=route_result)

    # 二级场景：根据一级场景给更有意义的前缀
    _scene_prefix_map = {
        "工具应用": "技能学习",
        "内容创作": "创作纠偏",
        "系统能力": "路由修正",
        "系统功能": "能力补充",
        "人物角色": "人设调整",
        "自主学习": "自动学习",
    }
    scene_prefix = _scene_prefix_map.get(primary_scene, "自动学习")

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
                "一级场景": primary_scene,
                "二级场景": f"{scene_prefix}-{_clean_text(query, 12)}",
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
    """Build a fact-based summary from feedback, not a reflection template."""
    question = _clean_text(rule_item.get("last_question") or "", 72)
    feedback = _clean_text(rule_item.get("user_feedback") or "", 60)
    last_answer = _clean_text(rule_item.get("last_answer") or "", 120)

    parts = []
    # Extract the factual correction from the conversation
    if question and feedback:
        parts.append(f"\u7528\u6237\u95ee\u300c{question}\u300d")
        if last_answer:
            parts.append(f"Nova\u56de\u590d\u4e86\u300c{last_answer}\u300d")
        parts.append(f"\u7528\u6237\u7ea0\u6b63\u8bf4\u300c{feedback}\u300d")
        parts.append("\u4e0b\u6b21\u9047\u5230\u7c7b\u4f3c\u95ee\u9898\u8981\u6309\u7528\u6237\u7ea0\u6b63\u7684\u65b9\u5411\u56de\u7b54")
    elif question:
        parts.append(f"\u7528\u6237\u95ee\u8fc7\u300c{question}\u300d\uff0c\u4e0a\u6b21\u56de\u7b54\u4e0d\u591f\u597d")
    if web_summary:
        parts.append(f"\u8865\u5145\u4fe1\u606f\uff1a{_clean_text(web_summary, 140)}")
    return _clean_text("\uff1b".join(parts), max_length)


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
    feedback_scene = str(rule_item.get("scene") or "")
    entry = save_learned_knowledge(
        query,
        base_summary,
        [],
        source="feedback_relearn",
        extra_fields=extra_fields,
        feedback_scene=feedback_scene,
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
        feedback_scene=feedback_scene,
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

    # 排除闲聊/感叹/评价类短句
    _casual = ['有意思','没意思','不错','还行','厉害','好玩','无聊',
               '哈哈','嘿嘿','呵呵','嗯嗯','好的','知道了','明白',
               '懂了','可以','牛','真的吗','是吗','对吧']
    if any(c in text for c in _casual):
        return False, "casual_chat"

    is_question_like = any(hint in lowered or hint in text for hint in QUESTION_HINTS)
    is_learning_request = any(hint in text for hint in LEARNING_HINTS)
    if not is_question_like and not is_learning_request:
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

    entry = save_learned_knowledge(user_input, summary, results, route_result=route_result)
    return {
        "success": True,
        "type": "knowledge",
        "entry": entry,
        "summary": summary,
        "result_count": len(results),
    }
