# L8 自动学习 - 安全版：后台搜索、知识沉淀、主链回流
import threading
from pathlib import Path

from memory.l8 import config_store as _l8_config_store
from memory.l8 import entry_helpers as _l8_entry_helpers
from memory.l8 import feedback_learning as _l8_feedback_learning
from memory.l8 import scene_rules as _l8_scene_rules
from memory.l8 import text_utils as _l8_text_utils
from memory.l8 import auto_learning as _l8_auto_learning
from memory.l8 import knowledge_store as _l8_knowledge_store
from memory.l8 import quality_guard as _l8_quality_guard
from memory.l8 import web_search as _l8_web_search
from core.runtime_state.json_store import load_json as _load_json, write_json as _write_json
from storage.paths import AUTOLEARN_CONFIG_FILE, KNOWLEDGE_BASE_FILE, KNOWLEDGE_FILE, RUNTIME_STORE_DIR


ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = RUNTIME_STORE_DIR
CONFIG_FILE = AUTOLEARN_CONFIG_FILE
_FILE_LOCK = threading.Lock()

# ── 依赖注入 ──
_llm_call = None  # 裸 LLM 调用（不带人格），由 agent_final.py 注入
_debug_write = lambda stage, data: None

def init(*, llm_call=None, debug_write=None):
    global _llm_call, _debug_write
    if llm_call: _llm_call = llm_call
    if debug_write: _debug_write = debug_write

DEFAULT_CONFIG = _l8_config_store.DEFAULT_CONFIG

def _infer_primary_scene(
    query: str = "",
    feedback_scene: str = "",
    route_result: dict | None = None,
) -> str:
    return _l8_scene_rules.infer_primary_scene(
        query,
        feedback_scene=feedback_scene,
        route_result=route_result,
    )

def _normalize_query(text: str) -> str:
    return _l8_text_utils.normalize_query(text)


def _clean_text(text: str, limit: int | None = None) -> str:
    return _l8_text_utils.clean_text(text, limit)


def load_autolearn_config() -> dict:
    return _l8_config_store.load_autolearn_config(
        config_file=CONFIG_FILE,
        default_config=DEFAULT_CONFIG,
        load_json=_load_json,
        write_json=_write_json,
        file_lock=_FILE_LOCK,
    )


def save_autolearn_config(config: dict) -> dict:
    return _l8_config_store.save_autolearn_config(
        config,
        config_file=CONFIG_FILE,
        default_config=DEFAULT_CONFIG,
        write_json=_write_json,
        file_lock=_FILE_LOCK,
    )


def update_autolearn_config(patch: dict) -> dict:
    return _l8_config_store.update_autolearn_config(
        patch,
        load_autolearn_config_fn=load_autolearn_config,
        save_autolearn_config_fn=save_autolearn_config,
    )


def _entry_text(entry: dict) -> str:
    return _l8_entry_helpers.entry_text(entry)


def _entry_sort_key(entry: dict) -> tuple[int, str]:
    return _l8_entry_helpers.entry_sort_key(entry)


def _strip_json_fence(text: str) -> str:
    return _l8_entry_helpers.strip_json_fence(text)


def _llm_rank_knowledge_candidates(query: str, candidates: list[tuple[int, dict]], max_candidates: int = 18) -> list[tuple[int, int, dict]]:
    return _l8_entry_helpers.llm_rank_knowledge_candidates(
        query,
        candidates,
        llm_call=_llm_call,
        clean_text=_clean_text,
        max_candidates=max_candidates,
    )


def _normalize_tool_skill_name(skill_name: str) -> str:
    return _l8_entry_helpers.normalize_tool_skill_name(skill_name)


def _is_registered_skill_name(skill_name: str) -> bool:
    return _l8_entry_helpers.is_registered_skill_name(skill_name)


_THINK_RE = _l8_entry_helpers.THINK_RE
def _strip_think_content(text: str) -> str:
    return _l8_entry_helpers.strip_think_content(text)


def _sanitize_extra_fields(extra_fields: dict | None) -> dict:
    return _l8_entry_helpers.sanitize_extra_fields(extra_fields)


def _looks_like_query_noise(text: str) -> bool:
    return _l8_entry_helpers.looks_like_query_noise(text)


def _looks_like_compact_search_query(text: str) -> bool:
    return _l8_entry_helpers.looks_like_compact_search_query(text)


def _llm_entry_quality_label(query: str, summary: str) -> str:
    return _l8_quality_guard.llm_entry_quality_label(
        query,
        summary,
        llm_call=_llm_call,
        clean_text=_clean_text,
    )


def _results_match_learning_query(user_input: str, search_query: str, results: list[dict]) -> bool:
    return _l8_auto_learning.results_match_learning_query(
        user_input,
        search_query,
        results,
        llm_call=_llm_call,
        format_search_results_fn=_format_search_results,
        clean_text=_clean_text,
    )


def _entry_query(entry: dict) -> str:
    return _l8_entry_helpers.entry_query(entry)


def _entry_summary(entry: dict) -> str:
    return _l8_entry_helpers.entry_summary(entry)


def _entry_type(entry: dict) -> str:
    return _l8_entry_helpers.entry_type(entry)


def _entry_source(entry: dict) -> str:
    return _l8_entry_helpers.entry_source(entry)


def _entry_has_reusable_knowledge(entry: dict) -> bool:
    return _l8_entry_helpers.entry_has_reusable_knowledge(
        entry,
        clean_text=_clean_text,
    )


def classify_l8_entry_kind(entry: dict) -> str:
    return _l8_knowledge_store.classify_l8_entry_kind(entry)


def build_feedback_relearn_preview(rule_item: dict, summary: str = "", *, used_web: bool = False) -> dict:
    return _l8_feedback_learning.build_feedback_relearn_preview(
        rule_item,
        summary,
        used_web=used_web,
        build_feedback_learning_query_fn=build_feedback_learning_query,
        clean_text=_clean_text,
        strip_think_content=_strip_think_content,
    )


def prune_l8_garbage_entries(*, make_backup: bool = True, reason: str = "manual_cleanup") -> dict:
    return _l8_knowledge_store.prune_l8_garbage_entries(
        make_backup=make_backup,
        reason=reason,
        file_lock=_FILE_LOCK,
        load_json=_load_json,
        write_json=_write_json,
        knowledge_base_file=KNOWLEDGE_BASE_FILE,
        should_surface_knowledge_entry_fn=should_surface_knowledge_entry,
        debug_write=_debug_write,
    )


def should_surface_knowledge_entry(entry: dict) -> bool:
    return _l8_knowledge_store.should_surface_knowledge_entry(
        entry,
        entry_has_reusable_knowledge=_entry_has_reusable_knowledge,
        is_registered_skill_name=_is_registered_skill_name,
    )


def should_show_l8_timeline_entry(entry: dict) -> bool:
    return _l8_knowledge_store.should_show_l8_timeline_entry(
        entry,
        entry_has_reusable_knowledge=_entry_has_reusable_knowledge,
        classify_entry_kind=classify_l8_entry_kind,
    )


def find_relevant_knowledge(query: str, limit: int = 3, min_score: int = 12, touch: bool = False) -> list[dict]:
    return _l8_knowledge_store.find_relevant_knowledge(
        query,
        limit=limit,
        min_score=min_score,
        touch=touch,
        load_json=_load_json,
        write_json=_write_json,
        knowledge_base_file=KNOWLEDGE_BASE_FILE,
        file_lock=_FILE_LOCK,
        normalize_query=_normalize_query,
        should_surface_knowledge_entry_fn=should_surface_knowledge_entry,
        llm_rank_knowledge_candidates=_llm_rank_knowledge_candidates,
        entry_sort_key=_entry_sort_key,
        clean_text=_clean_text,
    )


def _format_search_results(results: list[dict]) -> str:
    return _l8_web_search.format_search_results(results, clean_text=_clean_text)


def search_web_results(query: str, max_results: int = 5, timeout_sec: int = 8, skip_filter: bool = False) -> list[dict]:
    return _l8_web_search.search_web_results(
        query,
        load_autolearn_config=load_autolearn_config,
        max_results=max_results,
        timeout_sec=timeout_sec,
        skip_filter=skip_filter,
        search_tavily_fn=_search_tavily,
        search_brave_fn=_search_brave,
    )


def _search_tavily(query: str, api_key: str, max_results: int = 5, timeout_sec: int = 8) -> list[dict]:
    return _l8_web_search.search_tavily(
        query,
        api_key,
        max_results=max_results,
        timeout_sec=timeout_sec,
        clean_text=_clean_text,
    )


def _search_brave(query: str, api_key: str, max_results: int = 5, timeout_sec: int = 8) -> list[dict]:
    return _l8_web_search.search_brave(
        query,
        api_key,
        max_results=max_results,
        timeout_sec=timeout_sec,
        clean_text=_clean_text,
    )


def search_web(query: str):
    return _l8_web_search.search_web(
        query,
        load_autolearn_config=load_autolearn_config,
        search_web_results_fn=search_web_results,
        format_search_results_fn=_format_search_results,
    )


def is_explicit_learning_request(text: str) -> bool:
    return _l8_auto_learning.is_explicit_learning_request(text, llm_call=_llm_call)


def explicit_search_and_learn(search_query: str) -> dict:
    return _l8_auto_learning.explicit_search_and_learn(
        search_query,
        load_autolearn_config=load_autolearn_config,
        search_web_results_fn=search_web_results,
        build_summary_fn=_build_summary,
        save_learned_knowledge_fn=save_learned_knowledge,
    )


def _build_summary(query: str, results: list[dict], max_length: int = 360) -> str:
    return _l8_web_search.build_summary(
        query,
        results,
        max_length=max_length,
        llm_call=_llm_call,
        clean_text=_clean_text,
        debug_write=_debug_write,
    )


def _check_entry_quality(query: str, summary: str) -> str:
    return _l8_quality_guard.check_entry_quality(
        query,
        summary,
        strip_think_content=_strip_think_content,
        looks_like_query_noise=_looks_like_query_noise,
        llm_entry_quality_label_fn=_llm_entry_quality_label,
    )


def save_learned_knowledge(
    query: str,
    summary: str,
    results: list[dict],
    source: str = "bing_rss",
    extra_fields: dict | None = None,
    feedback_scene: str = "",
    route_result: dict | None = None,
) -> dict:
    return _l8_knowledge_store.save_learned_knowledge(
        query,
        summary,
        results,
        source=source,
        extra_fields=extra_fields,
        feedback_scene=feedback_scene,
        route_result=route_result,
        strip_think_content=_strip_think_content,
        check_entry_quality=_check_entry_quality,
        clean_text=_clean_text,
        normalize_query=_normalize_query,
        sanitize_extra_fields=_sanitize_extra_fields,
        infer_primary_scene=_infer_primary_scene,
        load_json=_load_json,
        write_json=_write_json,
        knowledge_base_file=KNOWLEDGE_BASE_FILE,
        knowledge_file=KNOWLEDGE_FILE,
        file_lock=_FILE_LOCK,
    )


def build_feedback_learning_query(rule_item: dict) -> str:
    return _l8_feedback_learning.build_feedback_learning_query(
        rule_item,
        clean_text=_clean_text,
    )


def _feedback_problem_text(problem: str) -> str:
    return _l8_feedback_learning.feedback_problem_text(
        problem,
        problem_hints=_l8_feedback_learning.DEFAULT_PROBLEM_HINTS,
    )


def _feedback_fix_text(fix: str) -> str:
    return _l8_feedback_learning.feedback_fix_text(
        fix,
        fix_hints=_l8_feedback_learning.DEFAULT_FIX_HINTS,
    )


def _build_feedback_summary(rule_item: dict, web_summary: str = "", max_length: int = 360) -> str:
    return _l8_feedback_learning.build_feedback_summary(
        rule_item,
        web_summary=web_summary,
        max_length=max_length,
        clean_text=_clean_text,
    )


def auto_learn_from_feedback(rule_item: dict) -> dict:
    return _l8_feedback_learning.auto_learn_from_feedback(
        rule_item,
        load_autolearn_config=load_autolearn_config,
        build_feedback_learning_query_fn=build_feedback_learning_query,
        build_feedback_summary_fn=_build_feedback_summary,
        build_feedback_relearn_preview=build_feedback_relearn_preview,
        sanitize_extra_fields=_sanitize_extra_fields,
        should_trigger_auto_learn=should_trigger_auto_learn,
        search_web_results=search_web_results,
        build_summary=_build_summary,
        clean_text=_clean_text,
    )


def should_trigger_auto_learn(user_input: str, route_result: dict | None = None, has_relevant_knowledge: bool = False, config: dict | None = None) -> tuple[bool, str]:
    return _l8_auto_learning.should_trigger_auto_learn(
        user_input,
        route_result=route_result,
        has_relevant_knowledge=has_relevant_knowledge,
        config=config,
        load_autolearn_config=load_autolearn_config,
    )


def _extract_search_query(user_input: str) -> str | None:
    return _l8_auto_learning.extract_search_query(
        user_input,
        llm_call=_llm_call,
        looks_like_compact_search_query=_looks_like_compact_search_query,
    )


def auto_learn(user_input: str, ai_response: str = "", route_result: dict | None = None) -> dict:
    return _l8_auto_learning.auto_learn(
        user_input,
        route_result=route_result,
        load_autolearn_config=load_autolearn_config,
        find_relevant_knowledge_fn=find_relevant_knowledge,
        should_trigger_auto_learn_fn=should_trigger_auto_learn,
        extract_search_query_fn=_extract_search_query,
        search_web_results_fn=search_web_results,
        results_match_learning_query_fn=_results_match_learning_query,
        build_summary_fn=_build_summary,
        save_learned_knowledge_fn=save_learned_knowledge,
        debug_write=_debug_write,
    )
