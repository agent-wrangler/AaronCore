"""
L2 持久记忆引擎 — 评分入库 + 检索召回 + 自动结晶 + 每20轮摘要
存储：state_data/l2_short_term.json（不设上限）
"""

import time
import threading
from datetime import datetime
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
        "profile_updates": meta.get("profile_updates") if isinstance(meta.get("profile_updates"), dict) else {},
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
        mark_crystal=_mark_crystal,
        to_l3=_to_l3,
        to_l4=_to_l4,
    )

def _mark_crystal(mid):
    return _l2_crystallization.mark_crystal(
        mid,
        load_entries=_load,
        save_entries=_save,
    )

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


def _extract_context_tag(text: str, ai_text: str = "") -> str:
    return _l2_crystallization.extract_context_tag(
        text,
        ai_text,
        infer_memory_meta=_infer_memory_meta,
    )


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

def _append_l4_changelog(persona: dict, content: str):
    return _l2_crystallization.append_l4_changelog(persona, content)

def _to_l4(text, mtype, *, profile_updates=None):
    return _l2_crystallization.to_l4(
        text,
        mtype,
        profile_updates=profile_updates,
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

def _to_l7(text, ai_text):
    return _l2_crystallization.to_l7(
        text,
        ai_text,
        load_json_fn=load_json,
        write_json_fn=write_json,
        l7_file=L7_FILE,
        debug_write=_debug_write,
    )

def _condense_knowledge(user_text: str, ai_text: str) -> str:
    return _l2_crystallization.condense_knowledge(
        user_text,
        ai_text,
        llm_call=_llm_call,
        debug_write=_debug_write,
    )


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

def _clean_summary(text: str) -> str:
    """清理摘要中的表情、角色扮演语句、过长内容。"""
    return _l2_summaries.clean_summary(text)


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

# ── 格式化（供prompt注入）──
def format_l2_context(memories: list) -> str:
    return _l2_summaries.format_l2_context(memories)

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


def cleanup_stale_memories(now: datetime | None = None) -> dict:
    """定期清理低价值记忆，返回清理统计"""
    return _l2_retention.cleanup_stale_memories(
        load_entries=_load,
        save_entries=_save,
        classify_retention_bucket=classify_retention_bucket,
        debug_write=_debug_write,
        now=now,
    )


def prune_legacy_l2_demands_from_l5(make_backup: bool = True, reason: str = "manual_cleanup") -> dict:
    """清理旧版 L2→L5 遗留的 l2_demand 条目。"""
    return _l2_retention.prune_legacy_l2_demands_from_l5(
        L5_FILE,
        make_backup=make_backup,
        reason=reason,
        debug_write=_debug_write,
    )
