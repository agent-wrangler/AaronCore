# reply_formatter - 回复格式化、trace 构建、统一回复生成
# 从 agent_final.py 提取

import json
import re as _re
from pathlib import Path as _Path

from context import chat_context as _chat_context
from context.builder import format_l8_context, render_dialogue_context
from decision import capability_replies as _capability_replies
from decision import reply_hygiene as _reply_hygiene
from decision import reply_prompts as _reply_prompts
from decision import reasoning_trace as _reasoning_trace
from decision.tool_runtime import closeout_helpers as _closeout_helpers
from decision.tool_runtime import directory_resolution as _directory_resolution
from decision.tool_runtime import focus_guidance as _focus_guidance
from decision.tool_runtime import handoff_signals as _handoff_signals
from decision.tool_runtime import result_resolution as _result_resolution
from decision.tool_runtime import runtime_guidance as _runtime_guidance
from decision.tool_runtime import signal_recovery as _signal_recovery
from decision.tool_runtime import tool_args as _tool_args
from decision.tool_runtime import turn_support as _turn_support
from decision.tool_runtime import usage_stats as _usage_stats
from decision.tool_runtime import visible_text as _visible_text
from decision.tool_runtime.events import (
    synthesize_tool_failure_response,
)
from decision.tool_runtime.ledger import ToolCallRecord, ToolCallTurnLedger
from core.feedback_classifier import format_l7_context
from feedback import repair_status as _repair_status
from core.fs_protocol import (
    build_protocol_arg_failure_feedback as _protocol_arg_failure_feedback,
    build_protocol_arg_failure_system_note as _protocol_arg_failure_system_note,
    build_protocol_retry_note as _protocol_retry_note,
    has_same_protocol_arg_failure_recently as _protocol_has_same_arg_failure_recently,
    missing_required_protocol_fields as _protocol_missing_required_fields,
    protocol_arg_failure_signature as _protocol_arg_failure_signature,
    resolve_user_file_target as _resolve_protocol_user_file_target,
    summarize_action_meta,
)

# ── 配置文件化：从 configs/ 读取 prompt 配置 ──
_CONFIGS_DIR = _Path(__file__).resolve().parents[1] / "configs"
_prompt_error_count = 0  # 连续报错计数

def _load_prompt_config() -> dict:
    """加载 prompt 配置（连续 3 次报错自动回滚到 .bak）"""
    global _prompt_error_count
    p = _CONFIGS_DIR / "prompts.json"
    bak = _CONFIGS_DIR / "prompts.json.bak"
    try:
        cfg = json.loads(p.read_text("utf-8"))
        _prompt_error_count = 0
        return cfg
    except Exception:
        _prompt_error_count += 1
        if _prompt_error_count >= 3 and bak.exists():
            try:
                import shutil
                shutil.copy2(bak, p)
                _prompt_error_count = 0
                return json.loads(p.read_text("utf-8"))
            except Exception:
                pass
        return {}

# ── 注入依赖 ──────────────────────────────────────────────
_think = None
_think_stream = None
_llm_call = None        # 裸 llm_call（brain.llm_call），用于 tool_call 模式
_llm_call_stream = None  # 裸 llm_call_stream（brain.llm_call_stream），用于 tool_call 流式

_debug_write = lambda stage, data: None




def _extract_json_object_text(raw: str) -> str:
    return _tool_args.extract_json_object_text(raw)


def _salvage_string_field(raw: str, key: str) -> str:
    return _tool_args.salvage_string_field(raw, key)


def _coerce_tool_args(raw_args, user_input: str = "") -> dict:
    return _tool_args.coerce_tool_args(raw_args, user_input=user_input)


def _sanitize_tool_call_payload(tc: dict, tool_args: dict) -> dict:
    return _tool_args.sanitize_tool_call_payload(tc, tool_args)


def _extract_recent_file_paths(bundle: dict) -> list[str]:
    return _directory_resolution.extract_recent_file_paths(bundle)


def _extract_explicit_local_path(text: str) -> str:
    return _directory_resolution.extract_explicit_local_path(text)


def _infer_recent_directory_target(bundle: dict) -> str:
    return _directory_resolution.infer_recent_directory_target(bundle)


def _load_latest_structured_fs_target() -> str:
    return _chat_context.load_latest_structured_fs_target()


def _load_task_plan_fs_target(bundle: dict) -> str:
    return _chat_context.load_task_plan_fs_target(bundle)


def _load_context_fs_target(bundle: dict) -> str:
    return _chat_context.load_context_fs_target(bundle)


def _looks_like_directory_resolution_request(user_input: str, *, has_structured_target: bool) -> bool:
    return _directory_resolution.looks_like_directory_resolution_request(
        user_input,
        has_structured_target=has_structured_target,
    )

def _reply_already_contains_location(reply_text: str) -> bool:
    return _directory_resolution.reply_already_contains_location(
        reply_text,
        clean_visible_reply_text=_clean_visible_reply_text,
    )

def _pick_directory_resolution_target(bundle: dict, *, allow_global_fallback: bool = True) -> str:
    return _directory_resolution.pick_directory_resolution_target(
        bundle,
        load_task_plan_fs_target=_load_task_plan_fs_target,
        load_context_fs_target=_load_context_fs_target,
        load_latest_structured_fs_target=_load_latest_structured_fs_target,
        allow_global_fallback=allow_global_fallback,
    )

def _infer_directory_resolution_tool_call(bundle: dict, reply_text: str = "") -> dict | None:
    return _directory_resolution.infer_directory_resolution_tool_call(
        bundle,
        reply_text=reply_text,
        clean_visible_reply_text=_clean_visible_reply_text,
        load_task_plan_fs_target=_load_task_plan_fs_target,
        load_context_fs_target=_load_context_fs_target,
        load_latest_structured_fs_target=_load_latest_structured_fs_target,
    )

def _repair_tool_args_from_context(tool_name: str, tool_args: dict, bundle: dict) -> dict:
    return _directory_resolution.repair_tool_args_from_context(
        tool_name,
        tool_args,
        bundle,
        load_task_plan_fs_target=_load_task_plan_fs_target,
        load_context_fs_target=_load_context_fs_target,
        load_latest_structured_fs_target=_load_latest_structured_fs_target,
    )

def _build_tool_exec_context(bundle: dict) -> dict:
    return _turn_support.build_tool_exec_context(
        bundle,
        load_task_plan_fs_target=_load_task_plan_fs_target,
        load_context_fs_target=_load_context_fs_target,
        resolve_active_task_plan=_resolve_active_task_plan,
    )


def _missing_required_tool_fields(tool_name: str, tool_args: dict) -> list[str]:
    return _protocol_missing_required_fields(tool_name, tool_args)


def _tool_arg_failure_signature(tool_name: str, tool_args: dict, missing_fields: list[str]) -> dict:
    return _protocol_arg_failure_signature(tool_name, tool_args, missing_fields)


def _has_same_arg_failure_recently(recent_attempts: list[dict], signature: dict) -> bool:
    return _protocol_has_same_arg_failure_recently(recent_attempts, signature)


def _build_tool_arg_failure_feedback(tool_name: str, tool_args: dict, missing_fields: list[str]) -> str:
    return _runtime_guidance.build_tool_arg_failure_feedback(
        tool_name,
        tool_args,
        missing_fields,
        protocol_arg_failure_feedback=_protocol_arg_failure_feedback,
    )


def _build_tool_arg_failure_system_note(tool_name: str, tool_args: dict, missing_fields: list[str]) -> str:
    return _runtime_guidance.build_tool_arg_failure_system_note(
        tool_name,
        tool_args,
        missing_fields,
        protocol_arg_failure_system_note=_protocol_arg_failure_system_note,
    )


def _build_failed_tool_retry_note(tool_name: str, tool_args: dict, exec_result: dict) -> str:
    return _runtime_guidance.build_failed_tool_retry_note(
        tool_name,
        tool_args,
        exec_result,
        protocol_retry_note=_protocol_retry_note,
    )


def _append_runtime_guidance(messages: list[dict], content: str) -> None:
    _runtime_guidance.append_runtime_guidance(messages, content)


def _is_write_file_content_arg_failure(signature: dict | None) -> bool:
    return _focus_guidance.is_write_file_content_arg_failure(signature)


def _build_strict_write_file_retry_note(tool_args: dict | None, signature: dict | None = None) -> str:
    return _focus_guidance.build_strict_write_file_retry_note(
        tool_args,
        signature,
        resolve_existing_file_target=_resolve_existing_file_target,
    )


def _tool_definition_name(tool_def: dict | None) -> str:
    return _focus_guidance.tool_definition_name(tool_def)


def _resolve_existing_file_target(tool_args: dict | None) -> str:
    return _focus_guidance.resolve_existing_file_target(
        tool_args,
        resolve_protocol_user_file_target=_resolve_protocol_user_file_target,
    )


def _resolve_known_fs_focus_target(bundle: dict | None = None, tool_args: dict | None = None) -> tuple[str, str]:
    return _focus_guidance.resolve_known_fs_focus_target(
        bundle,
        tool_args,
        load_context_fs_target=_load_context_fs_target,
        load_task_plan_fs_target=_load_task_plan_fs_target,
        extract_recent_file_paths=_directory_resolution.extract_recent_file_paths,
        resolve_protocol_user_file_target=_resolve_protocol_user_file_target,
    )


def _build_fs_focus_guidance(bundle: dict | None = None, tool_args: dict | None = None) -> str:
    return _focus_guidance.build_fs_focus_guidance(
        bundle,
        tool_args,
        resolve_known_fs_focus_target=_resolve_known_fs_focus_target,
    )


def _reprioritize_tools_for_coding_focus(
    tools: list[dict] | None,
    *,
    target_kind: str = "",
    current_tool_name: str = "",
) -> list[dict]:
    return _focus_guidance.reprioritize_tools_for_coding_focus(
        tools,
        target_kind=target_kind,
        current_tool_name=current_tool_name,
        tool_definition_name=_tool_definition_name,
        debug_write=_debug_write,
    )


def _build_followup_tools_after_arg_failure(
    tools: list[dict] | None,
    arg_failure: dict | None,
    tool_args: dict | None,
    bundle: dict | None = None,
    current_tool_name: str = "",
) -> list[dict]:
    return _focus_guidance.build_followup_tools_after_arg_failure(
        tools,
        arg_failure,
        tool_args,
        bundle,
        current_tool_name,
        resolve_known_fs_focus_target=_resolve_known_fs_focus_target,
        tool_definition_name=_tool_definition_name,
        reprioritize_tools_for_coding_focus=_reprioritize_tools_for_coding_focus,
        is_write_file_content_arg_failure=_is_write_file_content_arg_failure,
        resolve_existing_file_target=_resolve_existing_file_target,
        debug_write=_debug_write,
    )

def _tool_preview(name: str, arguments: dict) -> str:
    return _turn_support.tool_preview(name, arguments)


def _prepare_tool_call_runtime(tc: dict, bundle: dict) -> tuple[dict, str, dict, str]:
    return _turn_support.prepare_tool_call_runtime(
        tc,
        bundle,
        repair_tool_args_from_context=_repair_tool_args_from_context,
        coerce_tool_args=_coerce_tool_args,
        sanitize_tool_call_payload=_sanitize_tool_call_payload,
        tool_preview=_tool_preview,
    )


def _close_tool_call_as_synthetic_failure(
    ledger: ToolCallTurnLedger,
    tc: dict,
    bundle: dict,
    *,
    reason: str,
    detail: str = "",
) -> ToolCallRecord:
    return _turn_support.close_tool_call_as_synthetic_failure(
        ledger,
        tc,
        bundle,
        reason=reason,
        detail=detail,
        prepare_tool_call_runtime=_prepare_tool_call_runtime,
        synthesize_tool_failure_response=synthesize_tool_failure_response,
        summarize_tool_response_text=_summarize_tool_response_text,
    )


def _tool_action_summary(exec_result: dict) -> str:
    return _turn_support.tool_action_summary(
        exec_result,
        summarize_action_meta=summarize_action_meta,
        re_mod=_re,
    )


def _build_visible_tools_context(tools: list[dict]) -> str:
    return _runtime_guidance.build_visible_tools_context(
        tools,
        tool_definition_name=_tool_definition_name,
    )


def _contains_legacy_tool_markup(text: str) -> bool:
    return _signal_recovery.contains_legacy_tool_markup(
        text,
        legacy_tool_markup_re=_tool_args.LEGACY_TOOL_MARKUP_RE,
    )


def _parse_legacy_tool_call_text(text: str, user_input: str = "") -> dict | None:
    return _signal_recovery.parse_legacy_tool_call_text(
        text,
        user_input,
        legacy_tool_block_re=_tool_args.LEGACY_TOOL_BLOCK_RE,
        legacy_minimax_tool_re=_tool_args.LEGACY_MINIMAX_TOOL_RE,
        legacy_json_tool_re=_tool_args.LEGACY_JSON_TOOL_RE,
        re_mod=_re,
        json_module=json,
    )


def _infer_action_tool_call_from_reply(reply_text: str, user_input: str = "", context: dict | None = None) -> dict | None:
    return _signal_recovery.infer_action_tool_call_from_reply(
        reply_text,
        user_input,
        context,
        re_mod=_re,
        json_module=json,
    )


def _force_app_tool_call_from_reply(reply_text: str, user_input: str = "") -> dict | None:
    return _signal_recovery.force_app_tool_call_from_reply(
        reply_text,
        user_input,
        json_module=json,
    )


def _tool_has_unresolved_drift(exec_result: dict) -> bool:
    return _signal_recovery.tool_has_unresolved_drift(exec_result)


def _append_drift_note(tool_response: str, exec_result: dict) -> str:
    return _signal_recovery.append_drift_note(tool_response, exec_result)


def _tool_requires_user_takeover(exec_result: dict) -> bool:
    return _signal_recovery.tool_requires_user_takeover(exec_result)


def _build_l1_messages(bundle: dict, limit: int | None = None) -> list[dict]:
    return _chat_context.build_l1_messages(
        bundle,
        clean_visible_reply_text=_clean_visible_reply_text,
        limit=limit,
    )

def _build_recent_dialogue_text(bundle: dict, limit: int | None = None) -> str:
    return _chat_context.build_recent_dialogue_text(
        bundle,
        clean_visible_reply_text=_clean_visible_reply_text,
        limit=limit,
    )

def _resolve_active_task_plan(bundle: dict) -> dict:
    return _chat_context.resolve_active_task_plan(bundle)


def _resolve_active_working_state(bundle: dict) -> dict:
    return _chat_context.resolve_active_working_state(
        bundle,
        load_task_plan_fs_target=_load_task_plan_fs_target,
        load_context_fs_target=_load_context_fs_target,
    )


def _build_active_task_context(bundle: dict, recent_attempts: list[dict] | None = None) -> str:
    return _chat_context.build_active_task_context(
        bundle,
        recent_attempts=recent_attempts,
        load_task_plan_fs_target=_load_task_plan_fs_target,
        load_context_fs_target=_load_context_fs_target,
        build_fs_focus_guidance=_build_fs_focus_guidance,
    )

def _build_style_hints_from_l4(l4: dict, *, is_skill: bool = False) -> str:
    return _reply_prompts.build_style_hints_from_l4(l4, is_skill=is_skill)
_debug_write = lambda stage, data: None
_nova_core_ready = False
_get_all_skills = lambda: {}
_nova_execute = lambda route_result, skill_input: {"success": False}
_evolve = lambda user_input, skill_name: None
_load_autolearn_config = lambda: {}
_load_self_repair_reports = lambda: []
_find_feedback_rule = lambda msg, history: None


def init(*, think=None, think_stream=None, debug_write=None, nova_core_ready=False,
         get_all_skills=None, nova_execute=None, evolve=None,
         load_autolearn_config=None, load_self_repair_reports=None,
         find_feedback_rule=None, llm_call=None, llm_call_stream=None):
    global _think, _think_stream, _debug_write, _nova_core_ready, _get_all_skills
    global _nova_execute, _evolve, _load_autolearn_config
    global _load_self_repair_reports, _find_feedback_rule
    global _llm_call, _llm_call_stream
    if think:
        _think = think
    if think_stream:
        _think_stream = think_stream
    if debug_write:
        _debug_write = debug_write
    _nova_core_ready = nova_core_ready
    if get_all_skills:
        _get_all_skills = get_all_skills
    if nova_execute:
        _nova_execute = nova_execute
    if evolve:
        _evolve = evolve
    if load_autolearn_config:
        _load_autolearn_config = load_autolearn_config
    if load_self_repair_reports:
        _load_self_repair_reports = load_self_repair_reports
    if find_feedback_rule:
        _find_feedback_rule = find_feedback_rule
    if llm_call:
        _llm_call = llm_call
    if llm_call_stream:
        _llm_call_stream = llm_call_stream


# ── 学习/修复状态摘要 ────────────────────────────────────
def _build_learning_summary(config: dict) -> str:
    return _repair_status.build_learning_summary(config)


def _build_repair_summary(config: dict) -> str:
    return _repair_status.build_repair_summary(config)


def _build_latest_status_summary(latest: dict, latest_preview: dict, latest_apply: dict) -> str:
    return _repair_status.build_latest_status_summary(latest, latest_preview, latest_apply)


def build_self_repair_status() -> dict:
    return _repair_status.build_self_repair_status(
        load_autolearn_config=_load_autolearn_config,
        load_self_repair_reports=_load_self_repair_reports,
    )

# PLACEHOLDER_CAPABILITIES

def list_primary_capabilities() -> list[str]:
    return _capability_replies.list_primary_capabilities(
        nova_core_ready=_nova_core_ready,
        get_all_skills=_get_all_skills,
    )
def get_skill_display_name(skill_name: str) -> str:
    return _capability_replies.get_skill_display_name(
        skill_name,
        nova_core_ready=_nova_core_ready,
        get_all_skills=_get_all_skills,
    )

def build_capability_chat_reply(route: dict | None = None) -> str:
    return _capability_replies.build_capability_chat_reply(
        route,
        nova_core_ready=_nova_core_ready,
        get_all_skills=_get_all_skills,
        build_self_repair_status=build_self_repair_status,
    )

def build_meta_bug_report_reply(route: dict | None = None) -> str:
    return _capability_replies.build_meta_bug_report_reply(
        route,
        build_self_repair_status=build_self_repair_status,
    )

def build_answer_correction_reply(route: dict | None = None) -> str:
    return _capability_replies.build_answer_correction_reply(
        route,
        build_self_repair_status=build_self_repair_status,
    )
def _build_light_chat_prompt(bundle: dict) -> str:
    return _reply_prompts.build_light_chat_prompt(
        bundle,
        build_recent_dialogue_text=_build_recent_dialogue_text,
    )


def unified_chat_reply(bundle: dict, route: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    intent = str(route.get("intent") or "").strip()
    if intent in {"self_repair_capability", "ability_capability", "missing_skill"}:
        return build_capability_chat_reply(route)
    if intent == "meta_bug_report":
        return build_meta_bug_report_reply(route)
    if intent == "answer_correction":
        return build_answer_correction_reply(route)

    prompt = _build_light_chat_prompt(bundle)
    # 普通聊天轻链路已经携带 L1 最近对话，这里不再重复注入 dialogue_context。
    result = _think(prompt, "", image=bundle.get("image"), images=bundle.get("images"))
    reply = result.get("reply", "") if isinstance(result, dict) else str(result)
    if (not reply) or ("\ufffd" in str(reply)) or len(str(reply).strip()) < 2:
        return "\u6211\u5728\u5440\uff0c\u4f60\u76f4\u63a5\u8bf4\uff0c\u6211\u4f1a\u8ba4\u771f\u63a5\u7740\u4f60\u7684\u8bdd\u804a\u3002"
    return str(reply).strip()


def unified_chat_reply_stream(bundle: dict, route: dict | None = None):
    """普通聊天轻量流式实现。"""
    route = route if isinstance(route, dict) else {}
    intent = str(route.get("intent") or "").strip()
    if intent in {"self_repair_capability", "ability_capability", "missing_skill"}:
        yield build_capability_chat_reply(route)
        return
    if intent == "meta_bug_report":
        yield build_meta_bug_report_reply(route)
        return
    if intent == "answer_correction":
        yield build_answer_correction_reply(route)
        return

    if not _think_stream:
        yield unified_chat_reply(bundle, route)
        return

    prompt = _build_light_chat_prompt(bundle)
    # 普通聊天轻链路已经携带 L1 最近对话，这里不再重复注入 dialogue_context。
    for chunk in _think_stream(prompt, "", image=bundle.get("image"), images=bundle.get("images")):
        if isinstance(chunk, dict):
            if chunk.get("_done"):
                break
            yield chunk
        else:
            yield chunk


def _build_cod_system_prompt(bundle: dict) -> str:
    return _reply_prompts.build_cod_system_prompt(
        bundle,
        build_fs_focus_guidance=_build_fs_focus_guidance,
    )


def _build_tool_call_system_prompt(bundle: dict) -> str:
    return _reply_prompts.build_tool_call_system_prompt(
        bundle,
        build_fs_focus_guidance=_build_fs_focus_guidance,
    )


def _build_tool_call_user_prompt(bundle: dict) -> str:
    return _reply_prompts.build_tool_call_user_prompt(
        bundle,
        build_active_task_context=_build_active_task_context,
    )


def _normalize_reasoning_details(reasoning_details) -> list[dict]:
    return _reasoning_trace.normalize_reasoning_details(reasoning_details)


def _reasoning_details_from_chunks(chunks: list[str]) -> list[dict]:
    return _reasoning_trace.reasoning_details_from_chunks(chunks)


def _build_assistant_history_message(
    content,
    *,
    tool_calls: list[dict] | None = None,
    reasoning_details=None,
) -> dict:
    return _reasoning_trace.build_assistant_history_message(
        content,
        tool_calls=tool_calls,
        reasoning_details=reasoning_details,
        normalize_reasoning_details=_normalize_reasoning_details,
    )


def _resolve_tool_calls_from_result(result: dict, bundle: dict, *, mode: str = "non_stream") -> list[dict] | None:
    return _result_resolution.resolve_tool_calls_from_result(
        result,
        bundle,
        mode=mode,
        parse_legacy_tool_call_text=_parse_legacy_tool_call_text,
        force_app_tool_call_from_reply=_force_app_tool_call_from_reply,
        infer_action_tool_call_from_reply=_infer_action_tool_call_from_reply,
        infer_directory_resolution_tool_call=_infer_directory_resolution_tool_call,
        debug_write=_debug_write,
    )


def unified_reply_with_tools(bundle: dict, tools: list[dict], tool_executor) -> dict:
    """??tool_call ?????LLM ?????????????    ??? {"reply": str, "tool_used": str|None, "usage": dict}"""
    from decision.tool_runtime.non_stream import run_non_stream_tool_call_turn

    return run_non_stream_tool_call_turn(bundle, tools, tool_executor)


def _prefer_post_think_answer_tail(text: str) -> str:
    return _visible_text.prefer_post_think_answer_tail(text, re_mod=_re)


def _strip_think_markup(text: str) -> str:
    return _visible_text.strip_think_markup(text, re_mod=_re)


def _strip_legacy_tool_markup(text: str) -> str:
    return _visible_text.strip_legacy_tool_markup(
        text,
        legacy_tool_block_re=_tool_args.LEGACY_TOOL_BLOCK_RE,
        legacy_minimax_tool_re=_tool_args.LEGACY_MINIMAX_TOOL_RE,
        legacy_json_tool_re=_tool_args.LEGACY_JSON_TOOL_RE,
        re_mod=_re,
    )


def _strip_mid_reply_restart(text: str) -> tuple[str, list[str]]:
    return _visible_text.strip_mid_reply_restart(text, re_mod=_re)

def _prefer_tool_grounded_tail(text: str) -> str:
    return _visible_text.prefer_tool_grounded_tail(text, re_mod=_re)

def _clean_visible_reply_text(text: str) -> str:
    return _visible_text.clean_visible_reply_text(
        text,
        prefer_post_think_answer_tail=_prefer_post_think_answer_tail,
        strip_think_markup=_strip_think_markup,
        strip_legacy_tool_markup=_strip_legacy_tool_markup,
        prefer_tool_grounded_tail=_prefer_tool_grounded_tail,
        strip_mid_reply_restart=_strip_mid_reply_restart,
        re_mod=_re,
    )


def _build_tool_closeout_reply(
    *,
    success: bool,
    action_summary: str = "",
    tool_response: str = "",
    run_meta: dict | None = None,
) -> str:
    return _closeout_helpers.build_tool_closeout_reply(
        success=success,
        action_summary=action_summary,
        tool_response=tool_response,
        run_meta=run_meta,
        summarize_action_meta=summarize_action_meta,
        summarize_tool_response_text=_summarize_tool_response_text,
        fallback_tool_reply=_fallback_tool_reply,
    )

def _finalize_tool_reply(
    raw_reply: str,
    *,
    success: bool,
    action_summary: str = "",
    tool_response: str = "",
    run_meta: dict | None = None,
) -> str:
    return _closeout_helpers.finalize_tool_reply(
        raw_reply,
        success=success,
        action_summary=action_summary,
        tool_response=tool_response,
        run_meta=run_meta,
        clean_visible_reply_text=_clean_visible_reply_text,
        looks_like_tool_preamble=_looks_like_tool_preamble,
        build_tool_closeout_reply=_build_tool_closeout_reply,
    )

def _looks_like_tool_preamble(text: str) -> bool:
    return _handoff_signals.looks_like_tool_preamble(
        text,
        clean_visible_reply_text=_clean_visible_reply_text,
        contains_tool_handoff_phrase=_contains_tool_handoff_phrase,
        re_mod=_re,
    )

def _contains_tool_handoff_phrase(text: str) -> bool:
    return _handoff_signals.contains_tool_handoff_phrase(
        text,
        clean_visible_reply_text=_clean_visible_reply_text,
        re_mod=_re,
    )

def _looks_like_structured_tool_handoff(text: str) -> bool:
    return _handoff_signals.looks_like_structured_tool_handoff(
        text,
        clean_visible_reply_text=_clean_visible_reply_text,
        contains_tool_handoff_phrase=_contains_tool_handoff_phrase,
        re_mod=_re,
    )

def _looks_like_trailing_tool_handoff(text: str) -> bool:
    return _handoff_signals.looks_like_trailing_tool_handoff(
        text,
        clean_visible_reply_text=_clean_visible_reply_text,
        looks_like_tool_preamble=_looks_like_tool_preamble,
        looks_like_structured_tool_handoff=_looks_like_structured_tool_handoff,
        re_mod=_re,
    )

def _stream_tool_call_name(tool_calls_signal: list[dict] | None) -> str:
    return _handoff_signals.stream_tool_call_name(tool_calls_signal)


def _should_keep_stream_tool_call_with_visible_text(tool_calls_signal: list[dict] | None, visible_text: str) -> bool:
    return _handoff_signals.should_keep_stream_tool_call_with_visible_text(
        tool_calls_signal,
        visible_text,
        stream_tool_call_name=_stream_tool_call_name,
    )


def _resolve_stream_tool_calls_signal(
    tool_calls_signal: list[dict] | None,
    collected_tokens: list,
    bundle: dict,
    *,
    mode: str,
) -> tuple[list[dict] | None, str, str]:
    return _handoff_signals.resolve_stream_tool_calls_signal(
        tool_calls_signal,
        collected_tokens,
        bundle,
        mode=mode,
        strip_think_markup=_strip_think_markup,
        stream_tool_call_name=_stream_tool_call_name,
        looks_like_tool_preamble=_looks_like_tool_preamble,
        looks_like_structured_tool_handoff=_looks_like_structured_tool_handoff,
        looks_like_trailing_tool_handoff=_looks_like_trailing_tool_handoff,
        should_keep_stream_tool_call_with_visible_text=_should_keep_stream_tool_call_with_visible_text,
        resolve_tool_calls_from_result=_resolve_tool_calls_from_result,
        debug_write=_debug_write,
    )


def _record_tool_call_usage_stats(cfg: dict, usage: dict | None) -> None:
    _usage_stats.record_tool_call_usage_stats(cfg, usage)


def _merge_tool_call_usage_totals(usage: dict, delta: dict | None) -> None:
    _usage_stats.merge_tool_call_usage_totals(usage, delta)


def unified_reply_with_tools_stream(bundle: dict, tools: list[dict], tool_executor):
    """??tool_call ??????????    yield: str (token) | dict (???)
    ??????:
      {"_tool_call": {"name": str, "executing": True}}
      {"_tool_call": {"name": str, "done": True, "success": bool}}
      {"_done": True, "usage": dict, "tool_used": str|None}
    """
    from decision.tool_runtime.stream import run_stream_tool_call_turn

    yield from run_stream_tool_call_turn(bundle, tools, tool_executor)
    return


def _summarize_tool_response_text(text: str) -> str:
    return _closeout_helpers.summarize_tool_response_text(text)


def _fallback_tool_reply(tool_response: str) -> str:
    return _closeout_helpers.fallback_tool_reply(tool_response, format_skill_fallback=format_skill_fallback)


def _has_only_preamble_text(chunks: list, *, current_tool_success: bool) -> bool:
    return _closeout_helpers.has_only_preamble_text(
        chunks,
        clean_visible_reply_text=_clean_visible_reply_text,
        looks_like_tool_preamble=_looks_like_tool_preamble,
    )


def format_skill_fallback(skill_response: str) -> str:  # override legacy fallback wording
    return _closeout_helpers.format_skill_fallback_text(skill_response)


def format_skill_error_reply(skill_name: str, error_text: str, user_input: str = "") -> str:
    return _capability_replies.format_skill_error_reply(
        skill_name,
        error_text,
        user_input,
        get_skill_display_name=get_skill_display_name,
    )

def format_story_reply(user_input: str, story_text: str) -> str:
    return _capability_replies.format_story_reply(user_input, story_text)


def prettify_trace_reason(route: dict) -> str:
    return _capability_replies.prettify_trace_reason(route)


def build_repair_progress_payload(route: dict | None = None, feedback_rule: dict | None = None) -> dict:
    return _repair_status.build_repair_progress_payload(
        route,
        feedback_rule,
        build_self_repair_status=build_self_repair_status,
    )


def l1_hygiene_clean(response: str, history: list, window: int = 8, min_repeat: int = 3) -> str:
    return _reply_hygiene.l1_hygiene_clean(
        response,
        history,
        window=window,
        min_repeat=min_repeat,
        prefer_tool_grounded_tail=_prefer_tool_grounded_tail,
        strip_mid_reply_restart=_strip_mid_reply_restart,
        re_mod=_re,
    )
