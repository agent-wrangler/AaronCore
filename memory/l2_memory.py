"""
L2 持久记忆引擎 — 评分入库 + 检索召回 + 自动结晶 + 每20轮摘要
存储：state_data/l2_short_term.json（不设上限）
"""

import re
import time
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from memory.l2 import crystallization as _l2_crystallization
from memory.l2 import hygiene as _l2_hygiene
from memory.l2 import meta_inference as _l2_meta
from memory.l2 import retention as _l2_retention
from memory.l2 import retrieval as _l2_retrieval
from memory.l2 import signals as _l2_signals
from memory.l2 import storage as _l2_storage
from memory.l2 import summaries as _l2_summaries
from storage.json_store import load_json, write_json
from storage.paths import PRIMARY_STATE_DIR

# ── 文件路径 ──
L2_FILE = PRIMARY_STATE_DIR / "l2_short_term.json"
L2_CFG  = PRIMARY_STATE_DIR / "l2_config.json"
L3_FILE = PRIMARY_STATE_DIR / "long_term.json"
L4_FILE = PRIMARY_STATE_DIR / "persona.json"
L5_FILE = PRIMARY_STATE_DIR / "knowledge.json"
L7_FILE = PRIMARY_STATE_DIR / "feedback_rules.json"
L8_FILE = PRIMARY_STATE_DIR / "knowledge_base.json"

# ── 依赖注入 ──
_debug_write = lambda stage, data: None
_think = None
_llm_call = None  # 裸 LLM 调用（不带人格）

def init(*, debug_write=None, think=None, llm_call=None):
    global _debug_write, _think, _llm_call
    if debug_write: _debug_write = debug_write
    if think: _think = think
    if llm_call: _llm_call = llm_call

def _normalize_signal_text(text: str) -> str:
    return _l2_signals.normalize_signal_text(text)


def _clamp(value: float, low: float, high: float) -> float:
    return _l2_meta.clamp(value, low, high)


def _normalize_context_tag(tag: str) -> str:
    return _l2_meta.normalize_context_tag(tag)


def _extract_json_object(raw: str) -> dict | None:
    return _l2_meta.extract_json_object(raw)


def _call_memory_meta_llm(prompt: str) -> dict | None:
    return _l2_meta.call_memory_meta_llm(
        prompt,
        llm_call=_llm_call,
        think=_think,
        debug_write=_debug_write,
    )


def _call_yes_no_llm(prompt: str) -> bool | None:
    return _l2_meta.call_yes_no_llm(
        prompt,
        llm_call=_llm_call,
        think=_think,
        debug_write=_debug_write,
    )


def _normalize_interaction_rule_text(text: str) -> str:
    return _l2_meta.normalize_interaction_rule_text(text)


def _is_explicit_interaction_rule(text: str) -> bool:
    return _l2_meta.is_explicit_interaction_rule(
        text,
        llm_call=_llm_call,
        think=_think,
        debug_write=_debug_write,
        normalize_signal_text=_normalize_signal_text,
    )


def _normalize_preference_text(text: str) -> str:
    return _l2_meta.normalize_preference_text(text)


def _is_explicit_preference_statement(text: str) -> bool:
    return _l2_meta.is_explicit_preference_statement(
        text,
        llm_call=_llm_call,
        think=_think,
        debug_write=_debug_write,
        normalize_signal_text=_normalize_signal_text,
    )


def _default_memory_type(text: str, ai_text: str = "") -> str:
    return _l2_meta.default_memory_type(
        text,
        ai_text,
        build_signal_profile=build_signal_profile,
        normalize_signal_text=_normalize_signal_text,
    )


def _default_knowledge_query(text: str, ai_text: str = "") -> bool:
    return _l2_meta.default_knowledge_query(
        text,
        ai_text,
        build_signal_profile=build_signal_profile,
        normalize_signal_text=_normalize_signal_text,
    )


def _default_context_tag(text: str, ai_text: str = "") -> str:
    return _l2_meta.default_context_tag(
        text,
        ai_text,
        build_signal_profile=build_signal_profile,
        normalize_signal_text=_normalize_signal_text,
    )


def _score_importance_structural(text: str, ai_text: str = "") -> float:
    return _l2_meta.score_importance_structural(
        text,
        ai_text,
        build_signal_profile=build_signal_profile,
        normalize_signal_text=_normalize_signal_text,
    )


def _infer_memory_meta(text: str, ai_text: str = "") -> dict:
    return _l2_meta.infer_memory_meta(
        text,
        ai_text,
        llm_call=_llm_call,
        think=_think,
        debug_write=_debug_write,
        build_signal_profile=build_signal_profile,
        normalize_signal_text=_normalize_signal_text,
    )


def score_importance(text: str, ai_text: str = "") -> float:
    return float(_infer_memory_meta(text, ai_text).get("importance", 0.0))


def _detect_type(text: str, ai_text: str = "") -> str:
    return str(_infer_memory_meta(text, ai_text).get("memory_type") or "general")


def _profile_content_tokens(text: str) -> list[str]:
    return _l2_signals.profile_content_tokens(text)


def build_signal_profile(text: str) -> set[str]:
    return _l2_signals.build_signal_profile(text)


def _signal_overlap(query_profile: set[str], candidate_profile: set[str]) -> float:
    return _l2_signals.signal_overlap(query_profile, candidate_profile)


def _normalize_signature_anchor(text: str) -> str:
    return _l2_signals.normalize_signature_anchor(text)


def _is_low_signal_general_candidate(text: str) -> bool:
    return _l2_retrieval.is_low_signal_general_candidate(
        text,
        normalize_signal_text=_normalize_signal_text,
        looks_like_low_signal_general=_looks_like_low_signal_general,
    )


def _build_retrieval_signature(entry: dict) -> str:
    return _l2_signals.build_retrieval_signature(entry)


def _memory_type_retrieval_bonus(memory_type: str) -> float:
    return _l2_signals.memory_type_retrieval_bonus(memory_type)

# ── 文本相关度 ──
def _normalize_retrieval_text(text: str) -> str:
    return _l2_signals.normalize_retrieval_text(text)


def _token_overlap_score(query: str, stored: str) -> float:
    return _l2_signals.token_overlap_score(query, stored)


def _relevance(query: str, stored: str) -> float:
    return _l2_signals.relevance(query, stored)

def _freshness(created_at: str) -> float:
    return _l2_signals.freshness(created_at)

# ── 存储操作 ──
def _load():
    data = _l2_storage.load_entries(L2_FILE)
    cleaned, changed = _l2_hygiene.clean_memory_entries(
        data,
        normalize_signal_text=_normalize_signal_text,
    )
    if changed:
        _l2_storage.save_entries(L2_FILE, cleaned)
    return cleaned


def _save(data):
    _l2_storage.save_entries(L2_FILE, data)


def _cfg():
    return _l2_storage.load_config(L2_CFG)


def _save_cfg(config):
    _l2_storage.save_config(L2_CFG, config)

THRESHOLD = 0.35

def add_memory(user_input: str, ai_response: str):
    """每轮对话后调用，评分入库+结晶+摘要检查"""
    if not user_input or not user_input.strip():
        return None
    user_input = str(user_input or "").strip()
    ai_response = _l2_hygiene.sanitize_ai_response_for_memory(ai_response)
    if not ai_response:
        _debug_write("l2_skip_empty_reply", {"input": user_input[:80]})
        return None
    if _l2_hygiene.is_dirty_memory_turn(
        user_input,
        ai_response,
        normalize_signal_text=_normalize_signal_text,
    ):
        _debug_write("l2_skip_dirty", {"input": user_input[:80]})
        return None

    meta = _infer_memory_meta(user_input, ai_response)
    imp = float(meta.get("importance", 0.0) or 0.0)
    if imp < THRESHOLD:
        _debug_write("l2_skip", {"input": user_input[:50], "imp": imp})
        return None
    mtype = str(meta.get("memory_type") or "general")
    mid = f"l2_{int(time.time()*1000)}"
    entry = {
        "id": mid, "user_text": user_input, "ai_text": ai_response,
        "importance": imp, "memory_type": mtype,
        "context_tag": _normalize_context_tag(meta.get("context_tag") or "日常"),
        "knowledge_query": bool(meta.get("knowledge_query")),
        "created_at": datetime.now().isoformat(),
        "hit_count": 0, "crystallized": False,
    }
    store = _load()
    store.append(entry)
    _save(store)
    _debug_write("l2_add", {"id":mid,"imp":imp,"type":mtype})
    # 结晶 — 异步后台执行，不阻塞对话链路
    import threading
    threading.Thread(target=_try_crystallize, args=(entry,), daemon=True).start()
    # 摘要检查
    cfg = _cfg()
    cfg["total_rounds"] = cfg.get("total_rounds",0) + 1
    _save_cfg(cfg)
    _auto_summary(cfg, store)
    # 每50轮自动清理一次低价值记忆
    if cfg["total_rounds"] % 50 == 0:
        cleanup_stale_memories()
    return {"id": mid, "importance": imp, "type": mtype}

def search_relevant(query: str, limit: int = 8) -> list:
    """多信号相关度检索：不再只靠关键词和 freshness。"""
    return _l2_retrieval.search_relevant(
        query,
        limit=limit,
        load_entries=_load,
        save_entries=_save,
        build_signal_profile=build_signal_profile,
        normalize_signature_anchor=_normalize_signature_anchor,
        relevance=_relevance,
        signal_overlap=_signal_overlap,
        classify_retention_bucket=classify_retention_bucket,
        freshness=_freshness,
        memory_type_retrieval_bonus=_memory_type_retrieval_bonus,
        build_retrieval_signature=_build_retrieval_signature,
        is_low_signal_general_candidate=_is_low_signal_general_candidate,
    )

def _bump_hits(ids):
    _l2_retrieval.bump_hits(
        ids,
        load_entries=_load,
        save_entries=_save,
    )

def _is_real_knowledge_query(text: str, ai_text: str = "") -> bool:
    """二次验证：确认当前对话是否真的是可沉淀到 L8 的知识问答。"""
    return bool(_infer_memory_meta(text, ai_text).get("knowledge_query"))


def _try_crystallize(entry):
    return _l2_crystallization.try_crystallize(
        entry,
        is_real_knowledge_query=_is_real_knowledge_query,
        to_l7=_to_l7,
        to_l8=_to_l8,
        try_update_city=_try_update_city,
        mark_crystal=_mark_crystal,
        to_l3=_to_l3,
        to_l4=_to_l4,
    )
    imp = entry.get("importance",0)
    mtype = entry.get("memory_type","general")
    text = entry.get("user_text","")
    ai_text = entry.get("ai_text","")
    context_tag = entry.get("context_tag")
    knowledge_query = entry.get("knowledge_query")

    # L7: 纠正/不满 — 不要求高分，只要检测到就推
    if mtype == "correction":
        _to_l7(text, ai_text)

    # L8: 知识类 — 需要二次验证确实是知识问答，防止闲聊污染
    if mtype == "knowledge" and len(ai_text) > 20:
        if knowledge_query is None:
            knowledge_query = _is_real_knowledge_query(text, ai_text)
        if knowledge_query:
            _to_l8(text, ai_text)

    # 城市提取 — 不受分数限制，用户提到"我在X"就更新L4
    _try_update_city(text)

    # 以下需要高分才结晶
    if imp <= 0.7:
        return
    _mark_crystal(entry["id"])
    if mtype in ("event","milestone","general","decision"):
        _to_l3(text, mtype, ai_text=ai_text, context_tag=context_tag)
    if mtype in ("fact","preference","goal","rule"):
        _to_l4(text, mtype)

def _mark_crystal(mid):
    return _l2_crystallization.mark_crystal(
        mid,
        load_entries=_load,
        save_entries=_save,
    )
    try:
        store = _load()
        for m in store:
            if m.get("id")==mid:
                m["crystallized"]=True; break
        _save(store)
    except: pass

def _to_l3(text, mtype, *, ai_text="", context_tag=None):
    return _l2_crystallization.to_l3(
        text,
        mtype,
        ai_text=ai_text,
        context_tag=context_tag,
        load_json_fn=load_json,
        write_json_fn=write_json,
        l3_file=L3_FILE,
        normalize_context_tag=_normalize_context_tag,
        extract_context_tag=_extract_context_tag,
        debug_write=_debug_write,
        llm_call=_llm_call,
        think=_think,
        thread_factory=threading.Thread,
        refine_l3_entry_async=_refine_l3_entry_async,
    )
    """L2→L3 结晶：提炼高保真经历摘要，异步执行不阻塞主请求"""
    try:
        l3 = load_json(L3_FILE, [])
        # 去重：最近20条里有相似内容就跳过
        for it in l3[-20:]:
            if text in str(it.get("event") or it.get("summary", "")) or str(it.get("event") or it.get("summary", "")) in text:
                return
        tag = _normalize_context_tag(context_tag or _extract_context_tag(text, ai_text))
        # 先写入原文占位，保证不丢
        entry = {
            "event": text[:200],
            "raw_ref": text[:200],
            "context_tag": tag,
            "type": "event" if mtype in ("event", "general", "decision") else mtype,
            "source": "l2_crystallize",
            "created_at": datetime.now().isoformat(),
        }
        l3.append(entry)
        write_json(L3_FILE, l3)
        _debug_write("l2_crystal_l3", {"text": text[:50], "tag": tag})
        # 异步提炼：有 LLM 时后台升级 event 字段
        if ai_text and (_llm_call or _think):
            threading.Thread(
                target=_refine_l3_entry_async,
                args=(text, ai_text, entry["created_at"]),
                daemon=True,
            ).start()
    except Exception as e:
        _debug_write("l2_crystal_l3_err", {"err": str(e)})


def _extract_context_tag(text: str, ai_text: str = "") -> str:
    return _l2_crystallization.extract_context_tag(
        text,
        ai_text,
        infer_memory_meta=_infer_memory_meta,
    )
    return str(_infer_memory_meta(text, ai_text).get("context_tag") or "日常")


def _refine_l3_entry_async(user_text: str, ai_text: str, created_at: str):
    return _l2_crystallization.refine_l3_entry_async(
        user_text,
        ai_text,
        created_at,
        llm_call=_llm_call,
        think=_think,
        clean_summary=_clean_summary,
        load_json_fn=load_json,
        write_json_fn=write_json,
        l3_file=L3_FILE,
        debug_write=_debug_write,
    )
    """后台线程：用 LLM 提炼结晶摘要，回写到 L3 对应条目"""
    prompt = (
        f"\u7528\u6237\u8bf4\uff1a{user_text[:300]}\n"
        f"AI\u56de\u590d\uff1a{ai_text[:300]}\n\n"
        "\u7528\u4e00\u53e5\u8bdd\u6982\u62ec\u8fd9\u6bb5\u5bf9\u8bdd\u7684\u6838\u5fc3\u4e8b\u4ef6\u6216\u4fe1\u606f\uff0c"
        "\u4fdd\u7559\u5173\u952e\u7ec6\u8282\uff08\u4eba\u540d\u3001\u6570\u5b57\u3001\u5177\u4f53\u4e8b\u7269\uff09\u3002"
        "\u4e0d\u8981\u7528\u8868\u60c5\uff0c\u4e0d\u8981\u89d2\u8272\u626e\u6f14\uff0c\u63a7\u5236\u5728 80 \u5b57\u5185\u3002"
    )
    refined = None
    try:
        if _llm_call:
            txt = (_llm_call(prompt) or "").strip()
            if len(txt) > 5:
                refined = _clean_summary(txt)
        if not refined and _think:
            result = _think(prompt, "")
            txt = str(result.get("reply", "") if isinstance(result, dict) else result or "").strip()
            if len(txt) > 5:
                refined = _clean_summary(txt)
    except Exception:
        pass
    if not refined:
        return
    # 回写：找到对应条目，升级 event 字段
    try:
        l3 = load_json(L3_FILE, [])
        for entry in l3:
            if entry.get("created_at") == created_at and entry.get("source") == "l2_crystallize":
                entry["event"] = refined
                break
        write_json(L3_FILE, l3)
        _debug_write("l2_crystal_l3_refined", {"refined": refined[:50]})
    except Exception:
        pass

_KNOWN_CITIES = [
    "常州","北京","上海","苏州","南京","杭州","广州","深圳",
    "大理","成都","重庆","武汉","长沙","西安","天津","青岛",
    "厦门","昆明","贵阳","郑州","济南","合肥","福州","南昌",
    "哈尔滨","长春","沈阳","大连","无锡","宁波","温州","东莞",
    "佛山","珠海","三亚","拉萨","乌鲁木齐","呼和浩特","银川",
    "兰州","西宁","海口","南宁","石家庄","太原",
]

def _append_l4_changelog(persona: dict, content: str):
    return _l2_crystallization.append_l4_changelog(persona, content)
    """在 persona.json 里追加一条变更日志，供记忆页展示"""
    changelog = persona.setdefault("_changelog", [])
    changelog.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "content": content,
    })
    # 只保留最近 50 条
    if len(changelog) > 50:
        persona["_changelog"] = changelog[-50:]

def _try_update_city(text):
    return _l2_crystallization.try_update_city(
        text,
        load_json_fn=load_json,
        write_json_fn=write_json,
        l4_file=L4_FILE,
        append_l4_changelog=_append_l4_changelog,
        debug_write=_debug_write,
    )
    """独立的城市提取，不受重要性分数限制"""
    try:
        city_m = re.search(r'(?:\u6211\u5728|\u6211\u4f4f|\u5750\u6807|\u4eba\u5728|\u5b9a\u5c45)([^\s\uff0c,\u3002\u3001\uff01!\uff1f?\u7684\u4e86]+)', text)
        if not city_m:
            return
        candidate = city_m.group(1).strip()
        for city in _KNOWN_CITIES:
            if city in candidate:
                persona = load_json(L4_FILE, {})
                up = persona.setdefault("user_profile",{})
                old_city = str(up.get("city","")).strip()
                if old_city != city:
                    up["city"] = city
                    _append_l4_changelog(persona, f"\u7528\u6237\u66f4\u65b0\u4e86\u5730\u5740\uff1a{city}")
                    write_json(L4_FILE, persona)
                    _debug_write("l2_city_update", {"old": old_city, "new": city})
                return
    except Exception as e:
        _debug_write("l2_city_update_err", {"err": str(e)})

def _to_l4(text, mtype):
    return _l2_crystallization.to_l4(
        text,
        mtype,
        load_json_fn=load_json,
        write_json_fn=write_json,
        l4_file=L4_FILE,
        normalize_preference_text=_normalize_preference_text,
        is_explicit_preference_statement=_is_explicit_preference_statement,
        normalize_interaction_rule_text=_normalize_interaction_rule_text,
        is_explicit_interaction_rule=_is_explicit_interaction_rule,
        append_l4_changelog=_append_l4_changelog,
        debug_write=_debug_write,
    )
    try:
        persona = load_json(L4_FILE, {})
        updated = False
        if '\u6211\u53eb' in text:
            m = re.search(r'\u6211\u53eb([^\s\uff0c,\u3002\u3001\uff01!\uff1f?]+)', text)
            if m:
                up = persona.setdefault("user_profile",{})
                eid = str(up.get("identity",""))
                name = m.group(1)
                if name not in eid:
                    up["identity"] = (eid+"\uff0c"+f"\u53eb{name}").strip("\uff0c")
                    updated = True
        if mtype == "preference":
            pref_text = _normalize_preference_text(text)
            if _is_explicit_preference_statement(pref_text):
                up = persona.setdefault("user_profile",{})
                ep = str(up.get("preference",""))
                if pref_text not in ep:
                    up["preference"] = (ep+"\uff1b"+pref_text).strip("\uff1b")
                    updated = True
            else:
                _debug_write("l2_l4_preference_skip", {"text": text[:80], "reason": "not_explicit_preference"})
        if mtype == "rule":
            rule_text = _normalize_interaction_rule_text(text)
            if _is_explicit_interaction_rule(rule_text):
                rules = persona.setdefault("interaction_rules",[])
                existing = {_normalize_interaction_rule_text(r) for r in rules}
                if rule_text and rule_text not in existing:
                    rules.append(rule_text)
                    updated = True
            else:
                _debug_write("l2_l4_rule_skip", {"text": text[:80], "reason": "not_explicit_interaction_rule"})
        if updated:
            _changelog_labels = {
                "fact": "\u8bb0\u5f55\u4e86\u7528\u6237\u4fe1\u606f",
                "preference": "\u66f4\u65b0\u4e86\u7528\u6237\u504f\u597d",
                "rule": "\u65b0\u589e\u4e86\u4ea4\u4e92\u89c4\u5219",
                "goal": "\u8bb0\u5f55\u4e86\u7528\u6237\u76ee\u6807",
            }
            label = _changelog_labels.get(mtype, "\u66f4\u65b0\u4e86\u7528\u6237\u753b\u50cf")
            _append_l4_changelog(persona, f"{label}\uff1a{text[:50]}")
            write_json(L4_FILE, persona)
            _debug_write("l2_crystal_l4", {"text":text[:50]})
    except Exception as e:
        _debug_write("l2_crystal_l4_err", {"err":str(e)})

def _to_l7(text, ai_text):
    return _l2_crystallization.to_l7(
        text,
        ai_text,
        load_json_fn=load_json,
        write_json_fn=write_json,
        l7_file=L7_FILE,
        debug_write=_debug_write,
    )
    """L2→L7：检测到纠正/不满时，带上对话上下文推给L7，让反馈更精准"""
    try:
        l7 = load_json(L7_FILE, [])
        # 去重：同样的反馈不重复记
        for item in l7:
            if isinstance(item, dict) and text[:20] in str(item.get("user_feedback", "")):
                return
        l7.append({
            "id": f"l2_fb_{int(time.time()*1000)}",
            "source": "l2_context",
            "created_at": datetime.now().isoformat(),
            "enabled": True,
            "user_feedback": text,
            "last_answer": ai_text[:200] if ai_text else "",
            "l2_context": "L2检测到用户纠正/不满",
        })
        write_json(L7_FILE, l7)
        _debug_write("l2_crystal_l7", {"text": text[:50]})
    except Exception as e:
        _debug_write("l2_crystal_l7_err", {"err": str(e)})

def _condense_knowledge(user_text: str, ai_text: str) -> str:
    return _l2_crystallization.condense_knowledge(
        user_text,
        ai_text,
        llm_call=_llm_call,
        debug_write=_debug_write,
    )
    """用 LLM 从对话中凝结纯知识，同时过滤非知识内容。
    返回凝结后的知识摘要；如果不含可复用知识则返回空字符串。"""
    if not _llm_call or not ai_text:
        return ""
    try:
        prompt = (
            "\u4f60\u662f\u77e5\u8bc6\u51dd\u7ed3\u5668\u3002\u4ee5\u4e0b\u662f\u4e00\u6bb5\u5bf9\u8bdd\uff1a\n"
            f"\u7528\u6237\u95ee\uff1a\u300c{user_text[:200]}\u300d\n"
            f"AI\u56de\u590d\uff1a\u300c{ai_text[:500]}\u300d\n\n"
            "\u5224\u65ad\u8fd9\u6bb5\u5bf9\u8bdd\u91cc\u662f\u5426\u5305\u542b\u53ef\u72ec\u7acb\u590d\u7528\u7684\u4e8b\u5b9e/\u6982\u5ff5/\u539f\u7406\u3002\n"
            "\u4ee5\u4e0b\u60c5\u51b5\u4e0d\u662f\u77e5\u8bc6\uff1a\n"
            "- \u8ba8\u8bbaAI\u7cfb\u7edf\u672c\u8eab\uff08\u8bb0\u5fc6/\u8def\u7531/L2/L3\u7b49\uff09\n"
            "- \u7eaf\u60c5\u7eea\u4e92\u52a8/\u95f2\u804a/\u89d2\u8272\u626e\u6f14\n"
            "- \u7528\u6237\u5410\u69fd/\u62b1\u6028/\u8bc4\u4ef7AI\u8868\u73b0\n\n"
            "\u5982\u679c\u6709\u77e5\u8bc6\uff0c\u7528\u7b80\u6d01\u4e2d\u6587\u63d0\u53d62-3\u53e5\uff0c"
            "\u53bb\u6389\u8868\u60c5/\u8bed\u6c14\u8bcd/\u89d2\u8272\u626e\u6f14\u8bed\u53e5\uff0c\u53ea\u4fdd\u7559\u77e5\u8bc6\u672c\u8eab\u3002\n"
            "\u5982\u679c\u6ca1\u6709\u53ef\u590d\u7528\u77e5\u8bc6\uff0c\u53ea\u8fd4\u56de\u4e24\u4e2a\u5b57\uff1a\u65e0\u77e5\u8bc6"
        )
        result = _llm_call(prompt)
        if not result:
            return ""
        result = result.strip()
        # LLM 判断无知识
        if result in ("\u65e0\u77e5\u8bc6", "\u65e0", ""):
            _debug_write("l2_condense_skip", {"user": user_text[:40], "reason": "no_knowledge"})
            return ""
        if len(result) < 8:
            return ""
        _debug_write("l2_condense_ok", {"user": user_text[:40], "len": len(result)})
        return result[:360]
    except Exception as e:
        _debug_write("l2_condense_err", {"err": str(e)})
        return ""


def _to_l8(text, ai_text):
    from memory import l8_learning as l8_learn

    return _l2_crystallization.to_l8(
        text,
        ai_text,
        llm_call=_llm_call,
        condense_knowledge=_condense_knowledge,
        save_learned_knowledge=l8_learn.save_learned_knowledge,
        debug_write=_debug_write,
    )
    """L2→L8：知识类对话沉淀到知识库，Nova下次就记住了"""
    try:
        # LLM 凝结：从对话中提取纯知识，同时过滤非知识内容
        summary = _condense_knowledge(text, ai_text)
        if not summary:
            # LLM 判断无可复用知识，或 LLM 不可用时 fallback 存原文
            if not _llm_call:
                summary = ai_text[:500] if ai_text else ""
            else:
                _debug_write("l2_crystal_l8_filtered", {"text": text[:50]})
                return
        from memory import l8_learning as l8_learn

        entry = l8_learn.save_learned_knowledge(
            text,
            summary,
            [],
            source="l2_crystallize",
        )
        if isinstance(entry, dict) and entry.get("saved") is False:
            _debug_write("l2_crystal_l8_filtered", {"text": text[:50], "reason": entry.get("reason", "")})
            return
        _debug_write("l2_crystal_l8", {"text": text[:50]})
    except Exception as e:
        _debug_write("l2_crystal_l8_err", {"err": str(e)})

# ── 每20轮自动摘要 ──
SUMMARY_INTERVAL = 20

def _auto_summary(cfg, store):
    return _l2_summaries.auto_summary(
        cfg,
        store,
        summary_interval=SUMMARY_INTERVAL,
        l3_file=L3_FILE,
        save_config=_save_cfg,
        gen_summary=_gen_summary,
        debug_write=_debug_write,
    )
    total = cfg.get("total_rounds",0)
    last = cfg.get("last_summary_round",0)
    if total - last < SUMMARY_INTERVAL:
        return
    recent = store[-SUMMARY_INTERVAL:]
    if len(recent) < 10:
        return
    summary = _gen_summary(recent, last+1, total)
    if not summary:
        return
    try:
        l3 = load_json(L3_FILE, [])
        l3.append({
            "event": summary,
            "type": "event",
            "source": "l2_auto_summary",
            "metadata": {"start_round":last+1, "end_round":total},
            "created_at": datetime.now().isoformat(),
        })
        write_json(L3_FILE, l3)
    except: pass
    cfg["last_summary_round"] = total
    cfg["total_summaries"] = cfg.get("total_summaries",0) + 1
    _save_cfg(cfg)
    _debug_write("l2_summary", {"rounds":f"{last+1}-{total}"})

def _clean_summary(text: str) -> str:
    """清理摘要中的表情、角色扮演语句、过长内容。"""
    return _l2_summaries.clean_summary(text)
    import re
    t = str(text or "").strip()
    # 去除 emoji 和特殊符号
    t = re.sub(r'[\U0001f300-\U0001f9ff\u2728\u2705\u274c\u2764\u2b50\u26a1\u2600-\u26ff\u2700-\u27bf]', '', t)
    # 去除角色扮演动作描述（括号开头的）
    t = re.sub(r'[\uff08\(][^\uff09\)]{0,30}[\uff09\)]', '', t)
    # 去除 markdown 加粗
    t = re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
    t = t.strip()
    # 截断到 100 字
    if len(t) > 100:
        t = t[:100]
    return t


def _gen_summary(mems, start, end):
    # 优先用裸 LLM，fallback 到 think
    return _l2_summaries.gen_summary(
        mems,
        start,
        end,
        summary_interval=SUMMARY_INTERVAL,
        llm_call=_llm_call,
        think=_think,
        build_signal_profile=build_signal_profile,
        normalize_signal_text=_normalize_signal_text,
    )
    dialog = ""
    for m in mems[-SUMMARY_INTERVAL:]:
        dialog += f"\u7528\u6237: {m.get('user_text','')}\nAI: {m.get('ai_text','')[:100]}\n\n"
    prompt = (
        f"\u4ee5\u4e0b\u662f\u7b2c{start}\u8f6e\u5230\u7b2c{end}\u8f6e\u7684\u5bf9\u8bdd\u8bb0\u5f55\uff0c"
        "\u8bf7\u75281-2\u53e5\u8bdd\u63d0\u70bc\u7528\u6237\u7684\u884c\u4e3a\u548c\u5173\u6ce8\u70b9\uff08\u7528\u6237\u505a\u4e86\u4ec0\u4e48\u3001\u95ee\u4e86\u4ec0\u4e48\u3001\u8868\u8fbe\u4e86\u4ec0\u4e48\u504f\u597d\uff09\u3002\n"
        "\u8981\u6c42\uff1a\n"
        "1. \u53ea\u5173\u6ce8\u7528\u6237\u884c\u4e3a\uff0c\u4e0d\u8981\u590d\u8ff0AI\u7684\u56de\u590d\u5185\u5bb9\n"
        "2. \u4e0d\u8981\u7528\u8868\u60c5/\u8bed\u6c14\u8bcd/\u89d2\u8272\u626e\u6f14\u8bed\u53e5\n"
        "3. \u7528\u7b80\u6d01\u7684\u9648\u8ff0\u53e5\uff0c\u4e0d\u8981\u5217\u6e05\u5355\n"
        "4. \u63a7\u5236\u5728 50 \u5b57\u5185\n\n"
        + dialog[:2000]
    )
    if _llm_call:
        try:
            txt = (_llm_call(prompt) or "").strip()
            if len(txt) > 5:
                return _clean_summary(txt)
        except Exception:
            pass
    if _think:
        try:
            result = _think(prompt, "")
            if isinstance(result, dict):
                txt = str(result.get("reply","")).strip()
            else:
                txt = str(result or "").strip()
            if len(txt) > 5:
                return _clean_summary(txt)
        except Exception:
            pass
    # fallback: 用结构信号提炼摘要，不再依赖关键词名单
    kps = []
    for m in mems:
        ut = str(m.get("user_text", "") or "").strip()
        if not ut:
            continue
        profile = build_signal_profile(ut)
        normalized = _normalize_signal_text(ut)
        if float(m.get("importance", 0.0) or 0.0) >= 0.65:
            kps.append(ut[:40])
        elif len(normalized) >= 10 and (
            "meta:question" in profile
            or "meta:structured" in profile
            or "meta:mixed_script" in profile
        ):
            kps.append(ut[:40])
    if kps:
        return f"\u5bf9\u8bdd\u8981\u70b9\uff08\u7b2c{start}-{end}\u8f6e\uff09\uff1a" + "\uff1b".join(kps[:5])
    return f"\u7b2c{start}-{end}\u8f6e\u4e3a\u4e00\u822c\u6027\u4ea4\u6d41\u3002"

# ── 格式化（供prompt注入）──
def format_l2_context(memories: list) -> str:
    return _l2_summaries.format_l2_context(memories)
    if not memories:
        return ""
    lines = []
    for m in memories:
        ut = m.get("user_text","")[:80]
        at = m.get("ai_text","")[:60]
        imp = m.get("importance",0)
        marker = "\u2605" if imp >= 0.7 else "\u00b7"
        line = f"{marker} {ut}"
        if at:
            line += f" \u2192 {at}"
        lines.append(line)
    return "\n".join(lines)

# ── 统计 ──
def get_stats() -> dict:
    return _l2_storage.build_stats(_load(), _cfg())

def _entry_age_days(entry: dict, now: datetime | None = None) -> int:
    return _l2_retention.entry_age_days(entry, now=now)


def _looks_like_active_general_context(text: str) -> bool:
    return _l2_retention.looks_like_active_general_context(
        text,
        normalize_signal_text=_normalize_signal_text,
        build_signal_profile=build_signal_profile,
    )


def _looks_like_low_signal_general(text: str) -> bool:
    return _l2_retention.looks_like_low_signal_general(
        text,
        normalize_signal_text=_normalize_signal_text,
        build_signal_profile=build_signal_profile,
    )


def classify_retention_bucket(entry: dict, now: datetime | None = None) -> dict:
    """给 L2 条目分配保留层级：keep / compress / prune。"""
    return _l2_retention.classify_retention_bucket(
        entry,
        now=now,
        normalize_signal_text=_normalize_signal_text,
        build_signal_profile=build_signal_profile,
        looks_like_low_signal_general=_looks_like_low_signal_general,
    )
    now = now or datetime.now()
    user_text = str(entry.get("user_text") or "").strip()
    memory_type = str(entry.get("memory_type") or "general").strip().lower() or "general"
    importance = float(entry.get("importance", 0.5) or 0.5)
    hits = int(entry.get("hit_count", 0) or 0)
    crystallized = bool(entry.get("crystallized"))
    age_days = _entry_age_days(entry, now)

    tier = "compress"
    label = "压缩类"
    reason = "适合在 L2 保留轻量痕迹，不必长期保留完整原文"

    if memory_type in ("fact", "rule", "preference", "goal"):
        if crystallized:
            reason = "已分发到更高层，L2 保留轻量痕迹即可"
        else:
            tier = "keep"
            label = "永保类"
            reason = "结构化高价值信息，适合作为 L2 的核心兜底"
    elif memory_type in ("project", "decision"):
        if crystallized:
            reason = "项目或决策已被更高层接住，L2 只需保留轻量痕迹"
        elif age_days <= 30 or hits > 0 or importance >= 0.7:
            tier = "keep"
            label = "永保类"
            reason = "当前阶段仍可能持续推进，保留原始印象更稳"
        elif age_days >= 120 and hits == 0 and importance < 0.6:
            tier = "prune"
            label = "淘汰候选"
            reason = "项目或决策长期没有再被提及，继续保留价值较低"
    elif memory_type in ("knowledge", "correction", "skill_demand"):
        if crystallized:
            reason = "已完成分发或纠偏，L2 只需保留轻量痕迹"
        elif age_days >= 90 and hits == 0:
            tier = "prune"
            label = "淘汰候选"
            reason = "线索长期未复用，继续保留的收益较低"
        else:
            reason = "更适合作为短中期线索保留，而不是长期保留原始对话"
    else:
        active_general = _looks_like_active_general_context(user_text)
        if age_days <= 3 and active_general:
            tier = "keep"
            label = "永保类"
            reason = "最近几天仍在推进的任务型对话印象，保留原始上下文更稳"
        elif age_days <= 7 and hits >= 5 and active_general:
            tier = "keep"
            label = "永保类"
            reason = "高复用且带任务连续性信号，说明仍在承担短中期上下文"
        elif age_days <= 7 and crystallized and hits >= 3:
            tier = "keep"
            label = "永保类"
            reason = "近期一般印象已被反复命中并结晶，继续保留原始上下文更稳"
        elif age_days <= 7 and _looks_like_low_signal_general(user_text):
            reason = "近期但低信号的一般对话印象，更适合压成轻量痕迹"
        elif age_days <= 7:
            reason = "近期一般对话印象，先压成轻量痕迹观察是否继续承接"
        elif age_days >= 30 and importance < 0.5 and hits == 0:
            tier = "prune"
            label = "淘汰候选"
            reason = "陈旧且未复用的一般对话印象"
        elif age_days >= 90 and importance < 0.7 and hits <= 1:
            tier = "prune"
            label = "淘汰候选"
            reason = "长期没有承接价值的一般对话印象"
        else:
            reason = "一般对话印象更适合压成轻量痕迹，避免 L2 臃肿"

    return {
        "tier": tier,
        "label": label,
        "reason": reason,
        "memory_type": memory_type,
        "importance": importance,
        "hit_count": hits,
        "crystallized": crystallized,
        "age_days": age_days,
    }


def cleanup_stale_memories(now: datetime | None = None) -> dict:
    """定期清理低价值记忆，返回清理统计"""
    return _l2_retention.cleanup_stale_memories(
        load_entries=_load,
        save_entries=_save,
        classify_retention_bucket=classify_retention_bucket,
        debug_write=_debug_write,
        now=now,
    )
    store = _load()
    if not store:
        return {"before": 0, "after": 0, "removed": 0}

    now = now or datetime.now()
    kept = []
    removed = 0
    retention_counts = {"keep": 0, "compress": 0, "prune": 0}

    for m in store:
        retention = classify_retention_bucket(m, now=now)
        tier = retention["tier"]
        retention_counts[tier] = retention_counts.get(tier, 0) + 1
        if tier == "prune":
            removed += 1
            continue

        kept.append(m)

    if removed > 0:
        _save(kept)
        _debug_write("l2_cleanup", {
            "before": len(store), "after": len(kept), "removed": removed,
            "retention_counts": retention_counts,
        })

    return {
        "before": len(store),
        "after": len(kept),
        "removed": removed,
        "retention_counts": retention_counts,
    }


def prune_legacy_l2_demands_from_l5(make_backup: bool = True, reason: str = "manual_cleanup") -> dict:
    """清理旧版 L2→L5 遗留的 l2_demand 条目。"""
    return _l2_retention.prune_legacy_l2_demands_from_l5(
        L5_FILE,
        make_backup=make_backup,
        reason=reason,
        debug_write=_debug_write,
    )
    store = load_json(L5_FILE, [])
    if not isinstance(store, list):
        return {"success": False, "reason": "invalid_knowledge_store"}

    kept = []
    removed = []
    for item in store:
        if isinstance(item, dict) and str(item.get("source") or "").strip() == "l2_demand":
            removed.append(item)
            continue
        kept.append(item)

    backup_path = None
    if removed and make_backup and L5_FILE.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = L5_FILE.with_name(f"{L5_FILE.stem}.backup_{stamp}{L5_FILE.suffix}")
        backup_path.write_text(L5_FILE.read_text(encoding="utf-8"), encoding="utf-8")

    if removed:
        write_json(L5_FILE, kept)

    result = {
        "success": True,
        "reason": reason,
        "original_count": len(store),
        "kept_count": len(kept),
        "removed_count": len(removed),
        "backup_created": bool(backup_path),
        "backup_path": str(backup_path) if backup_path else "",
        "removed_triggers": [
            str(((item.get("trigger") or [""]) if isinstance(item, dict) else [""])[0] or "")[:80]
            for item in removed
        ],
    }
    _debug_write("l2_l5_legacy_prune", result)
    return result
