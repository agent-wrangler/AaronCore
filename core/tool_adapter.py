# tool_adapter - Register skills and convert them to OpenAI function-calling tools.
# Provides wrappers for tool_call execution paths.

import json
import time
import threading
import re as _re
from pathlib import Path as _Path

from core.executor import execute as _execute
from core.fs_protocol import (
    execute_edit_file_action as _execute_edit_file_protocol,
    execute_write_file_action as _execute_write_file_protocol,
    load_export_state as _load_export_state,
    normalize_user_special_path as _normalize_user_special_path,
)
from decision.tool_runtime import ask_user as _ask_user_runtime
from decision.tool_runtime import dispatcher as _dispatcher_runtime
from decision.tool_runtime import file_targets as _file_target_runtime
from decision.tool_runtime import inspection_tools as _inspection_tool_runtime
from decision.tool_runtime import memory_tools as _memory_tool_runtime
from decision.tool_runtime import protocol_context as _protocol_context_runtime
from decision.tool_runtime import self_fix as _self_fix_runtime
from decision.tool_runtime import tool_defs as _tool_defs
from decision.tool_runtime import web_tools as _web_tool_runtime

# ask_user state lock for interactive tool prompts.
_ask_user_lock = threading.Lock()
_ask_user_pending = None   # {"question": str, "options": [...], "id": str}
_ask_user_answer = None    # Cached user selection payload.
def ask_user_submit(question_id: str, answer: str) -> bool:
    return _ask_user_runtime.ask_user_submit(question_id, answer)

def get_ask_user_pending() -> dict | None:
    return _ask_user_runtime.get_ask_user_pending()

# Configuration directory for runtime resources.
_CONFIGS_DIR = _Path(__file__).resolve().parent.parent / "configs"

# Runtime adapter injection points.
_get_all_skills = lambda: {}
_get_exposed_skills = None
_debug_write = lambda stage, data: None
_l2_search_relevant = lambda q, **kw: []
_load_l3_long_term = lambda **kw: []
_find_relevant_knowledge = lambda q, **kw: []

def _summarize_tool_response_text(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return ""
    text = text.replace("`", "")
    text = text.replace("\r", "\n")
    lines = [line.strip(" -") for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    summary = " / ".join(lines[:2]).strip()
    return summary[:140] + ("..." if len(summary) > 140 else "")

def _resolve_user_file_target(file_path: str):
    return _file_target_runtime.resolve_user_file_target(
        file_path,
        normalize_user_special_path=_normalize_user_special_path,
        load_export_state=_load_export_state,
        project_root=_Path(__file__).resolve().parent.parent,
    )

def _is_allowed_user_target(target) -> bool:
    return _file_target_runtime.is_allowed_user_target(target)

def _is_system_protected_target(target) -> bool:
    return _file_target_runtime.is_system_protected_target(target)

def _is_aaroncore_protected_write_target(target) -> bool:
    return _file_target_runtime.is_aaroncore_protected_write_target(
        target,
        project_root=_Path(__file__).resolve().parent.parent,
    )

def _is_allowed_read_target(target) -> bool:
    return _file_target_runtime.is_allowed_read_target(target)

def _is_allowed_write_target(target) -> bool:
    return _file_target_runtime.is_allowed_write_target(
        target,
        project_root=_Path(__file__).resolve().parent.parent,
    )

def _apply_protocol_context(name: str, ctx: dict, user_input: str, tool_args: dict | None = None) -> dict:
    return _protocol_context_runtime.apply_protocol_context(
        name,
        ctx,
        user_input,
        tool_args,
        resolve_user_file_target=_resolve_user_file_target,
        is_allowed_user_target=_is_allowed_user_target,
    )

def _remember_protocol_target(name: str, ctx: dict, result: dict) -> None:
    _protocol_context_runtime.remember_protocol_target(
        name,
        ctx,
        result,
        resolve_user_file_target=_resolve_user_file_target,
        is_allowed_user_target=_is_allowed_user_target,
    )

def _normalize_exposure_scope_values(scope) -> set[str]:
    return _tool_defs.normalize_exposure_scope_values(scope)

def _skill_matches_exposure_scope(info: dict | None, scope) -> bool:
    return _tool_defs.skill_matches_exposure_scope(info, scope)

def _get_exposed_skill_map(scope) -> dict:
    return _tool_defs.get_exposed_skill_map(_get_all_skills, _get_exposed_skills, scope)

def _build_registered_skill_tool_defs(scope) -> list[dict]:
    return _tool_defs.build_registered_skill_tool_defs(_get_all_skills, _get_exposed_skills, scope)

def init(*, get_all_skills=None, get_exposed_skills=None, debug_write=None,
         l2_search_relevant=None, load_l3_long_term=None, find_relevant_knowledge=None):
    global _get_all_skills, _get_exposed_skills, _debug_write
    global _l2_search_relevant, _load_l3_long_term, _find_relevant_knowledge
    if get_all_skills:
        _get_all_skills = get_all_skills
    if get_exposed_skills:
        _get_exposed_skills = get_exposed_skills
    if debug_write:
        _debug_write = debug_write
    if l2_search_relevant:
        _l2_search_relevant = l2_search_relevant
    if load_l3_long_term:
        _load_l3_long_term = load_l3_long_term
    if find_relevant_knowledge:
        _find_relevant_knowledge = find_relevant_knowledge

def _build_file_protocol_tool_defs() -> list[dict]:
    return _tool_defs.build_file_protocol_tool_defs()

_MEMORY_TOOLS = _memory_tool_runtime.MEMORY_TOOL_NAMES

def _load_cod_tool_defs() -> list:
    return _tool_defs.load_cod_tool_defs()

_COD_TOOL_DEFS_DEFAULT = _tool_defs.COD_TOOL_DEFS_DEFAULT
_COD_TOOL_DEFS = _tool_defs.COD_TOOL_DEFS

def build_tools_list() -> list[dict]:
    """Build the default tool_call tool list from the exposed skill catalog."""
    return _tool_defs.build_tools_list(
        _get_all_skills,
        _get_exposed_skills,
        _ask_user_runtime.get_ask_user_tool_def,
    )

def build_tools_list_cod() -> list[dict]:
    """Build the CoD tool list from skills exposed to tool_call or tool_call_cod."""
    return _tool_defs.build_tools_list_cod(
        _get_all_skills,
        _get_exposed_skills,
        _ask_user_runtime.get_ask_user_tool_def,
    )

def _execute_tool_call_legacy(name: str, arguments: dict, context: dict = None) -> dict:
    return _dispatcher_runtime.execute_tool_call_legacy(
        name,
        arguments,
        context,
        execute_ask_user=lambda payload: _ask_user_runtime.execute_ask_user(payload, debug_write=_debug_write),
        memory_tools=_MEMORY_TOOLS,
        execute_memory_tool=_execute_memory_tool,
        apply_protocol_context=_apply_protocol_context,
        execute_skill=_execute,
        remember_protocol_target=_remember_protocol_target,
        debug_write=_debug_write,
    )

def _normalize_tool_adapter_result(result: object, *, name: str) -> dict:
    return _dispatcher_runtime.normalize_tool_adapter_result(result, name=name)

def execute_tool_call(name: str, arguments: dict, context: dict = None) -> dict:
    return _dispatcher_runtime.execute_tool_call(
        name,
        arguments,
        context,
        execute_tool_call_legacy=_execute_tool_call_legacy,
        debug_write=_debug_write,
    )

def _normalize_time_sensitive_search_query(query: str) -> str:
    return _web_tool_runtime.normalize_time_sensitive_search_query(query)

def _execute_web_search(query: str) -> dict:
    from memory.l8_learning import search_web_results

    return _web_tool_runtime.execute_web_search(
        query,
        debug_write=_debug_write,
        search_web_results=search_web_results,
    )

# self_fix helper for best-effort runtime recovery behavior.

# Safe write/read prefix guard for self-fix runtime behavior.
_SELF_FIX_ALLOWED = list(_self_fix_runtime.SAFE_FILE_PREFIXES)

def _execute_self_fix(arguments: dict) -> dict:
    from brain import LLM_CONFIG
    from brain import llm_call_stream

    return _self_fix_runtime.execute_self_fix(
        arguments,
        debug_write=_debug_write,
        llm_config=LLM_CONFIG,
        llm_call_stream=llm_call_stream,
        allowed_prefixes=_SELF_FIX_ALLOWED,
        project_root=_Path(__file__).resolve().parent.parent,
    )

def _execute_read_file(arguments: dict, context: dict | None = None) -> dict:
    return _inspection_tool_runtime.execute_read_file(
        arguments,
        allowed_prefixes=_SELF_FIX_ALLOWED,
        resolve_user_file_target=_resolve_user_file_target,
        is_allowed_user_target=_is_allowed_user_target,
        debug_write=_debug_write,
        context=context,
        project_root=_Path(__file__).resolve().parent.parent,
    )

def _execute_list_files_v3(arguments: dict, context: dict | None = None) -> dict:
    return _inspection_tool_runtime.execute_list_files_v3(
        arguments,
        resolve_user_file_target=_resolve_user_file_target,
        normalize_user_special_path=_normalize_user_special_path,
        is_allowed_user_target=_is_allowed_user_target,
        context=context,
        project_root=_Path(__file__).resolve().parent.parent,
    )

def _execute_discover_tools(arguments: dict) -> dict:
    return _inspection_tool_runtime.execute_discover_tools(
        arguments,
        debug_write=_debug_write,
        get_all_skills=_get_all_skills,
    )

def _execute_sense_environment(arguments: dict) -> dict:
    def _load_vision_context():
        from core.vision import get_vision_context

        return get_vision_context()

    return _inspection_tool_runtime.execute_sense_environment(
        arguments,
        debug_write=_debug_write,
        get_vision_context=_load_vision_context,
    )

def _execute_write_file(arguments: dict) -> dict:
    return _execute_write_file_protocol(arguments)

def _execute_write_file_v2(arguments: dict) -> dict:
    return _execute_write_file_protocol(arguments)

def _format_recall(l2_results, l3_events):
    return _memory_tool_runtime.format_recall(l2_results, l3_events)

def _format_knowledge(hits):
    return _memory_tool_runtime.format_knowledge(hits)

def _execute_memory_tool(name: str, arguments: dict, context: dict = None) -> dict:
    return _memory_tool_runtime.execute_memory_tool(
        name,
        arguments,
        context=context,
        debug_write=_debug_write,
        l2_search_relevant=_l2_search_relevant,
        load_l3_long_term=_load_l3_long_term,
        find_relevant_knowledge=_find_relevant_knowledge,
        execute_web_search=_execute_web_search,
        execute_self_fix=_execute_self_fix,
        execute_read_file=_execute_read_file,
        execute_list_files_v3=_execute_list_files_v3,
        execute_discover_tools=_execute_discover_tools,
        execute_sense_environment=_execute_sense_environment,
    )

# ask_user adapter tool hook.

def _execute_ask_user(arguments: dict) -> dict:
    return _ask_user_runtime.execute_ask_user(arguments, debug_write=_debug_write)

def get_ask_user_tool_def() -> dict:
    return _ask_user_runtime.get_ask_user_tool_def()




def _is_novacore_protected_write_target(target) -> bool:
    return _is_aaroncore_protected_write_target(target)
