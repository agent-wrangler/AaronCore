"""核心对话路由：/chat SSE 流式"""
import asyncio
import json
import requests
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from core import shared as S
from core.markdown_render import render_markdown_html
from core.process_history import (
    normalize_persisted_process_steps as _normalize_process_history_steps,
    normalize_process_payload as _normalize_process_payload,
    trim_persisted_process_steps_for_stream_reset as _trim_process_history_steps_for_reset,
)
from core.runtime_state.state_loader import (
    DEFAULT_L1_RECENT_TOKEN_BUDGET as _L1_RECENT_TOKEN_BUDGET,
)
from routes.chat_tool_steps import (
    build_tool_done_label,
    build_tool_done_trace_detail,
    build_tool_execution_trace_label,
    build_tool_execution_trace_detail,
)
from routes.chat_history import (
    ChatHistoryTransaction,
    rollback_pending_user_history_turn as _rollback_pending_user_history_turn,
)
from routes.chat_stream_helpers import (
    consume_think_filtered_stream_text as _consume_think_filtered_stream_text,
    drop_incomplete_tool_handoff_prefix as _drop_incomplete_tool_handoff_prefix,
    ensure_tool_call_failure_reply as _ensure_tool_call_failure_reply,
    reset_stream_visible_state as _reset_stream_visible_state,
)
from routes.chat_reply_closeout import (
    classify_missing_tool_execution as _classify_missing_tool_execution,
    finalize_tool_call_reply as _finalize_tool_call_reply_for_user,
    prepare_reply_for_user as _prepare_reply_for_user,
)
from routes.chat_run_helpers import (
    block_task_plan_after_failure as _block_task_plan_after_failure,
    build_run_event as _build_run_event,
    extract_task_plan_from_meta as _extract_task_plan_from_meta,
    record_tool_call_memory_stats as _record_tool_call_memory_stats,
)
from routes.chat_tool_call_gate import (
    build_tool_call_unavailable_reply as _build_tool_call_unavailable_reply,
    get_cod_enabled as _get_cod_enabled,
    get_tool_call_enabled as _get_tool_call_enabled,
    get_tool_call_unavailable_reason as _get_tool_call_unavailable_reason,
    is_anthropic_model as _is_anthropic_model,
)
from routes.chat_model_switch import detect_model_switch as _detect_model_switch
from routes.chat_post_reply import (
    build_feedback_awareness_event as _build_feedback_awareness_event,
    build_repair_payload as _build_repair_payload,
    persist_reply_artifacts as _persist_reply_artifacts,
    record_feedback_memory_hit as _record_feedback_memory_hit,
    should_schedule_autolearn as _should_schedule_autolearn,
    update_companion_reply_state as _update_companion_reply_state,
)
from routes.chat_trace_semantics import (
    build_direct_reply_reason_note as _build_direct_reply_reason_note,
    build_expected_output as _build_expected_output,
    build_next_user_need as _build_next_user_need,
    build_tool_reason_note as _build_tool_reason_note,
)
from routes.chat_thinking_trace import ChatThinkingTraceState
from routes.chat_trace_state import ChatTraceState
from routes.chat_stream_markdown import MarkdownIncrementalStream
try:
    from routes import companion as _comp
except Exception:
    class _CompanionState:
        activity = "idle"
        reply_id = ""
        last_reply = ""
        last_reply_full = ""
        emotion = "neutral"

    _comp = _CompanionState()


def _normalize_persisted_process_steps(steps: list | None) -> list[dict]:
    return _normalize_process_history_steps(steps)


def _trim_collected_steps_for_stream_reset(steps: list | None, *, keep_prefix_count: int = 0) -> list[dict]:
    return _trim_process_history_steps_for_reset(
        steps,
        keep_prefix_count=keep_prefix_count,
    )

def _strip_markdown(text: str) -> str:
    """保留 Markdown 格式（已改为允许自由使用 Markdown）"""
    return text


def _build_reply_payload(reply: str, **extra) -> dict:
    payload = {
        "reply": str(reply or ""),
        "reply_html": render_markdown_html(reply),
    }
    for key, value in (extra or {}).items():
        if value is not None:
            payload[key] = value
    return payload


router = APIRouter()


def _get_pending_awareness_events() -> list[dict]:
    pull_fn = getattr(S, "awareness_pull", None)
    if callable(pull_fn):
        try:
            return pull_fn()
        except Exception as exc:
            if callable(getattr(S, "debug_write", None)):
                S.debug_write("awareness_pull_error", {"error": str(exc)})
            return []
    if callable(getattr(S, "debug_write", None)):
        S.debug_write("awareness_pull_missing", {"available": sorted([name for name in dir(S) if "awareness" in name])})
    return []


class ChatRequest(BaseModel):
    message: str
    image: str | None = None
    images: list[str] | None = None


class ChatAnswerRequest(BaseModel):
    question_id: str
    answer: str


@router.post("/chat")
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    msg = request.message
    user_image = request.image
    user_images = request.images or ([user_image] if user_image else [])
    S.debug_write("input", {"message": msg, "has_image": bool(user_images)})
    S.add_to_history("user", msg)

    # 通知视觉模块：用户活跃
    try:
        from core.vision import touch_user_activity
        touch_user_activity()
    except Exception:
        pass

    history = S.load_msg_history()
    # 当前消息先不 append 到 history，避免 L1 和 user prompt 重复
    # （会在回复完成后再存入）
    _history_for_context = list(history)  # 不含当前消息的副本

    async def event_stream():
      try:
        _comp.activity = "thinking"
        bundle = {}

        # 收集步骤，用于持久化到 msg_history
        _trace_state = ChatTraceState()
        _stream_attempt_step_keep_count = 0

        _trace = _trace_state.trace
        _agent_step = _trace_state.agent_step
        _build_waiting_step = _trace_state.build_waiting_step

        def _summarize_tool_response_text(text: str) -> str:
            text = str(text or "").strip()
            if not text:
                return ""
            text = text.replace("`", "").replace("\r", "\n")
            lines = [line.strip(" -") for line in text.splitlines() if line.strip()]
            if not lines:
                return ""
            summary = " / ".join(lines[:2]).strip()
            return summary[:140] + ("..." if len(summary) > 140 else "")

        _history_tx = ChatHistoryTransaction(
            history,
            save_msg_history=S.save_msg_history,
            add_to_history=S.add_to_history,
            debug_write=S.debug_write,
        )

        pending_awareness = _get_pending_awareness_events()
        for evt in pending_awareness:
            yield {"event": "awareness", "data": json.dumps(evt, ensure_ascii=False)}

        _pre_context_started_at = asyncio.get_running_loop().time()
        yield await _trace(
            "记忆加载",
            "正在读取最近对话、记忆和人格状态…",
            "running",
            step_key="info:memory_load",
            phase="info",
            full_detail="正在读取最近对话、记忆和人格状态…",
        )

        # 先把当前用户消息存入持久历史（但不影响 _history_for_context，避免 L1 重复）
        _history_tx.append_pending_user(msg)

        # ── CoD / tool_call 开关提前判断 ──
        _tool_call_unavailable_reason = _get_tool_call_unavailable_reason()
        _use_tool_call = _tool_call_unavailable_reason is None
        _use_cod = _use_tool_call and _get_cod_enabled()

        # Step 1: 记忆加载
        # L1 recent dialogue should be budget-driven instead of stopping at the
        # helper's default six-message cap. Keep the existing token budget and
        # let the history store trim by budget from the newest messages.
        l1 = S.get_recent_messages(
            _history_for_context,
            limit=None,
            max_tokens=_L1_RECENT_TOKEN_BUDGET,
        )
        l2 = S.extract_session_context(_history_for_context, msg)
        _use_light_chat_bundle = not _use_tool_call
        l2_memories = [] if (_use_cod or _use_light_chat_bundle) else S.l2_search_relevant(msg)

        # Step 1.5: 时间回忆检测
        recall_result = None
        if S.detect_recall_intent:
            recall_intent = S.detect_recall_intent(msg)
            if recall_intent:
                recall_result = S.recall_by_time(
                    recall_intent["start_dt"], recall_intent["end_dt"],
                    recall_intent["time_label"], history,
                )
                if recall_result:
                    yield await _trace("\u56de\u5fc6\u5bf9\u8bdd", f"\u6b63\u5728\u56de\u5fc6{recall_intent['time_label']}\u7684\u5bf9\u8bdd\u8bb0\u5f55\u2026", "running")

        # Step 2: 上下文接入（CoD 模式跳过 L3/L5）
        l3 = [] if (_use_cod or _use_light_chat_bundle) else S.load_l3_long_term()
        l4 = S.load_l4_persona()
        if isinstance(l4, dict):
            _lp = l4.get("local_persona") or {}
            if isinstance(_lp, dict):
                _up = _lp.get("user_profile")
                if isinstance(_up, dict) and not isinstance(l4.get("user_profile"), dict):
                    l4 = {**l4, "user_profile": dict(_up)}
        l5 = {} if (_use_cod or _use_light_chat_bundle) else S.load_l5_knowledge()
        persona_name = ""
        if isinstance(l4, dict):
            lp = l4.get("local_persona") or l4
            persona_name = str(lp.get("nova_name") or lp.get("name") or "")
        skill_count = len(l5.get("skills", {})) if isinstance(l5, dict) else 0

        # Step 3: 检索知识（CoD 模式跳过，由 LLM 按需调用 query_knowledge）
        if _use_cod or _use_light_chat_bundle:
            l8 = []
        else:
            l8 = S.find_relevant_knowledge(msg, limit=3, touch=True)

        try:
            from core.runtime_state.state_loader import record_memory_stats
            _cod_this = None if _use_tool_call else False
            _l4_ok = bool(l4 and isinstance(l4, dict) and len(l4) > 0)
            record_memory_stats(
                l2_searches=0 if (_use_cod or _use_light_chat_bundle) else 1, l2_hits=1 if l2_memories else 0,
                l8_searches=0 if (_use_cod or _use_light_chat_bundle) else 1, l8_hits=1 if l8 else 0,
                l3_queries=0 if (_use_cod or _use_light_chat_bundle) else 1, l3_hits=0 if (_use_cod or _use_light_chat_bundle) else (1 if l3 else 0),
                l4_queries=1, l4_hits=1 if _l4_ok else 0,
                l5_queries=0 if (_use_cod or _use_light_chat_bundle) else 1, l5_hits=0 if (_use_cod or _use_light_chat_bundle) else (1 if skill_count > 0 else 0),
                l1_count=len(l1), l3_count=len(l3),
                l4_available=_l4_ok, l5_count=skill_count,
                cod_used=_cod_this,
            )
        except Exception:
            pass

        user_turns = len([m for m in l1 if isinstance(m, dict) and m.get("role") == "user"])
        mem_parts = []
        # 上下文对话（L1）
        if user_turns:
            mem_parts.append("\u4e0a\u4e0b\u6587\u8f7d\u5165\u5b8c\u6210")
        else:
            mem_parts.append("\u9996\u8f6e\u5bf9\u8bdd")
        # 记忆模块（L2 会话理解 + L7 反馈规则）
        mem_parts.append("\u8bb0\u5fc6\u6a21\u5757\u6fc0\u6d3b")
        # 人格图谱（L4）
        mem_parts.append("\u4eba\u683c\u56fe\u8c31\u5bf9\u9f50")
        if l2_memories:
            mem_parts.append(f"\u5524\u9192{len(l2_memories)}\u6761\u6301\u4e45\u8bb0\u5fc6")
        if recall_result:
            mem_parts.append("\u65f6\u95f4\u56de\u5fc6\u5df2\u63a5\u5165")
        S.debug_write(
            "pre_context_timing",
            {
                "elapsed_ms": round((asyncio.get_running_loop().time() - _pre_context_started_at) * 1000, 2),
                "use_cod": _use_cod,
                "tool_call": _use_tool_call,
                "l2_memories": len(l2_memories or []),
                "l3": len(l3 or []),
                "l8": len(l8 or []),
            },
        )
        yield await _trace(
            "\u8bb0\u5fc6\u52a0\u8f7d",
            " / ".join(mem_parts),
            "done",
            step_key="info:memory_load",
            phase="info",
            full_detail=" / ".join(mem_parts),
        )

        # Step 4: 模型思考
        dialogue_context = S.build_dialogue_context(_history_for_context, msg)
        from brain import get_current_model_name
        from decision.tool_runtime.runtime_control import create_tool_runtime_control
        bundle = {
            "l1": l1, "l2": l2, "l2_memories": l2_memories,
            "l3": l3, "l4": l4, "l5": l5,
            "l7": S.search_relevant_rules(msg, limit=3),
            "l8": l8,
            "dialogue_context": dialogue_context, "user_input": msg,
            "image": user_images[0] if user_images else None,
            "images": user_images,
            "current_model": get_current_model_name(),
            "tool_runtime_control": create_tool_runtime_control(),
        }
        if _use_cod:
            bundle["cod_mode"] = True
        if recall_result:
            bundle["recall_context"] = recall_result

        # 闪回检测：旧记忆联想（潜意识层）
        try:
            from memory.flashback import detect_flashback
            _fb_hint = detect_flashback(msg)
            if _fb_hint:
                bundle["flashback_hint"] = _fb_hint
        except Exception:
            pass

        S.debug_write("context_bundle", {
            "l1": len(l1), "l2": len(l2), "l2_memories": len(l2_memories),
            "l3": len(l3),
            "l4_keys": list(l4.keys()) if isinstance(l4, dict) else [],
            "l5_skill_count": skill_count, "l8": len(l8 or []),
        })

        response = ""
        route = {"mode": "chat", "skill": "none", "reason": "default"}
        try:
            # 模型切换检测
            _model_switch = _detect_model_switch(msg)
            if _model_switch:
                yield await _trace("\u5207\u6362\u6a21\u578b", _model_switch.get("trace", "\u6b63\u5728\u5207\u6362\u6a21\u578b\u2026"), "done")
                response = _model_switch["reply"]
                yield {"event": "reply", "data": json.dumps(_build_reply_payload(response), ensure_ascii=False)}
                if _model_switch.get("model_changed"):
                    from brain import get_current_model_name, _current_default
                    yield {"event": "model_changed", "data": json.dumps({"model": _current_default, "model_name": get_current_model_name()}, ensure_ascii=False)}
                _comp.activity = "idle"
                _history_tx.persist_assistant_entry("assistant", response)
                return

            if _tool_call_unavailable_reason:
                response = _build_tool_call_unavailable_reply(_tool_call_unavailable_reason)
                S.debug_write(
                    "tool_call_unavailable",
                    {
                        "reason": _tool_call_unavailable_reason,
                        "tool_call_enabled": _get_tool_call_enabled(),
                        "anthropic_model": _is_anthropic_model(),
                        "core_ready": S.NOVA_CORE_READY,
                    },
                )
                yield await _trace(
                    "\u4e3b\u94fe\u4e8b\u6545",
                    "tool_call \u4e3b\u94fe\u4e0d\u53ef\u7528\uff0c\u5df2\u663e\u5f0f\u62a5\u9519\uff0c\u4e0d\u518d\u56de\u9000\u5230\u65e7 skill \u94fe\u3002",
                    "error",
                )
                yield {"event": "reply", "data": json.dumps(_build_reply_payload(response), ensure_ascii=False)}
                _comp.activity = "idle"
                _history_tx.persist_assistant_entry("nova", response)
                return

            # ── tool_call 模式分支 ──
            if _use_tool_call:
                from core.tool_adapter import (
                    build_tools_list,
                    build_tools_list_cod,
                    execute_tool_call,
                    get_ask_user_pending,
                )
                from core.reply_formatter import unified_reply_with_tools_stream

                # tool_call 模式：一次 LLM 调用搞定路由+回复，不走规则路由
                # CoD 模式下 bundle 已在上方构建时跳过 L2记忆/L3/L5/L8
                S.debug_write("tool_call_mode", {"enabled": True, "cod": _use_cod})

                # 联网搜索前置（和旧路径逻辑一致）
                if S.is_explicit_learning_request and S.is_explicit_learning_request(msg):
                    yield await _trace("\u8054\u7f51\u641c\u7d22", "\u6b63\u5728\u5206\u6790\u641c\u7d22\u4e3b\u9898\u2026", "running")
                    _extract_prompt = (
                        "\u7528\u6237\u8bf4\u4e86\u4e0b\u9762\u8fd9\u53e5\u8bdd\uff0c\u8bf7\u4ece\u4e2d\u63d0\u53d6\u51fa\u4ed6\u771f\u6b63\u60f3\u641c\u7d22/\u5b66\u4e60\u7684\u4e3b\u9898\u5173\u952e\u8bcd\u3002"
                        "\u5982\u679c\u7528\u6237\u6ca1\u6709\u6307\u5b9a\u5177\u4f53\u4e3b\u9898\uff08\u6bd4\u5982\u53ea\u8bf4\u201c\u53bb\u5b66\u70b9\u4e1c\u897f\u201d\uff09\uff0c"
                        "\u5c31\u6839\u636e\u4e4b\u524d\u7684\u5bf9\u8bdd\u4e0a\u4e0b\u6587\uff0c\u9009\u4e00\u4e2a\u7528\u6237\u53ef\u80fd\u611f\u5174\u8da3\u7684\u4e3b\u9898\u3002"
                        "\u53ea\u8f93\u51fa\u641c\u7d22\u5173\u952e\u8bcd\uff0c\u4e0d\u8981\u89e3\u91ca\uff0c\u4e0d\u8981\u52a0\u5f15\u53f7\uff0c\u4e0d\u8d85\u8fc715\u4e2a\u5b57\u3002\n\n"
                        f"\u7528\u6237\u539f\u8bdd\uff1a{msg}\n"
                        f"\u6700\u8fd1\u5bf9\u8bdd\u4e0a\u4e0b\u6587\uff1a{bundle.get('dialogue_context', '')[:300]}"
                    )
                    _raw_topic = S.raw_llm_call(_extract_prompt)
                    _search_topic = str(_raw_topic or "").strip()[:15]
                    _search_topic = _search_topic.strip('"\'\u201c\u201d\u300c\u300d\u3010\u3011')
                    if len(_search_topic) < 2 or len(_search_topic) > 40:
                        _search_topic = msg
                    S.debug_write("tool_call_search_topic", {"input": msg, "topic": _search_topic})
                    yield await _trace("\u8054\u7f51\u641c\u7d22", "\u641c\u7d22\u4e3b\u9898\uff1a" + _search_topic, "running")
                    _search_result = S.explicit_search_and_learn(_search_topic)
                    S.debug_write("tool_call_explicit_search", {
                        "topic": _search_topic, "success": _search_result.get("success"),
                        "reason": _search_result.get("reason", ""), "result_count": _search_result.get("result_count", 0),
                    })
                    if _search_result.get("success"):
                        _search_ctx = "\u3010\u5b9e\u65f6\u641c\u7d22\u7ed3\u679c\u3011\n"
                        for _si, _sr in enumerate(_search_result.get("results", [])[:5], 1):
                            _search_ctx += f"{_si}. {_sr.get('title', '')}\n   {_sr.get('snippet', '')}\n"
                        bundle["search_context"] = _search_ctx
                        bundle["search_summary"] = _search_result.get("summary", "")
                        yield await _trace("\u6574\u7406\u7ed3\u679c", "\u641c\u5230 " + str(_search_result.get("result_count", 0)) + " \u6761\u7ed3\u679c\uff0c\u6b63\u5728\u6574\u7406\u2026", "done")
                    else:
                        yield await _trace("\u7ec4\u7ec7\u56de\u590d", "\u641c\u7d22\u672a\u627e\u5230\u7ed3\u679c\uff0c\u7ed3\u5408\u5df2\u6709\u77e5\u8bc6\u56de\u590d\u2026", "running")

                tools = build_tools_list_cod() if _use_cod else build_tools_list()
                _comp.activity = "replying"
                _stream_chunks = []
                _markdown_stream = MarkdownIncrementalStream()
                _tool_used = None
                _tool_success = None
                _tool_run_meta = {}
                _task_plan = None
                _tool_action_summary = ""
                _tool_response_text = ""
                _think_carry = ""
                _inside_think_block = False
                _tool_trace_started = False
                _tool_inflight_name = ""
                _dropped_stream_prefix = ""
                _thinking_trace = ChatThinkingTraceState(msg)
                _stream_attempt_step_keep_count = len(_trace_state.collected_steps)
                # 立即发出思考卡片，不等 LLM 首 token
                yield await _thinking_trace.emit_default(_trace)
                async def _emit_default_thinking_trace():
                    event = await _thinking_trace.emit_default(_trace)
                    if event:
                        yield event

                def _update_thinking_meta(
                    *,
                    reason_kind: str = "",
                    goal: str = "",
                    decision_note: str = "",
                    handoff_note: str = "",
                    expected_output: str = "",
                    next_user_need: str = "",
                ) -> None:
                    _thinking_trace.update_meta(
                        reason_kind=reason_kind,
                        goal=goal,
                        decision_note=decision_note,
                        handoff_note=handoff_note,
                        expected_output=expected_output,
                        next_user_need=next_user_need,
                    )

                async def _emit_thinking_trace(force: bool = False):
                    event = await _thinking_trace.emit(_trace, force=force, tool_trace_started=_tool_trace_started)
                    if event:
                        yield event

                async def _ensure_followup_thinking_segment(*, emit_default: bool = False):
                    rotated = _thinking_trace.activate_pending_segment()
                    if emit_default and (rotated or not _thinking_trace.trace_sent):
                        event = await _thinking_trace.emit_default(_trace)
                        if event:
                            yield event

                try:
                    import queue, threading
                    _q = queue.Queue()
                    _last_ask_user_id = ""
                    def _tc_stream_worker():
                        try:
                            for _token in unified_reply_with_tools_stream(bundle, tools, execute_tool_call):
                                _q.put(_token)
                        except Exception as _e:
                            _q.put(("__error__", _e))
                        finally:
                            _q.put(None)
                    _t = threading.Thread(target=_tc_stream_worker, daemon=True)
                    _t.start()

                    while True:
                        try:
                            _item = _q.get(timeout=0.05)
                        except queue.Empty:
                            try:
                                _pending_question = get_ask_user_pending()
                            except Exception:
                                _pending_question = None
                            if isinstance(_pending_question, dict):
                                _pending_id = str(_pending_question.get("id") or "").strip()
                                if _pending_id and _pending_id != _last_ask_user_id:
                                    _last_ask_user_id = _pending_id
                                    yield {
                                        "event": "ask_user",
                                        "data": json.dumps(_pending_question, ensure_ascii=False),
                                    }
                            async for _evt in _emit_thinking_trace():
                                yield _evt
                            _now = asyncio.get_running_loop().time()
                            _idle_for = _now - _trace_state.last_progress_at
                            if _idle_for >= 1.2 and (_now - _trace_state.last_wait_event_at) >= 1.0:
                                _wait_label, _wait_detail = _build_waiting_step(
                                    _idle_for,
                                    tool_active=bool(_tool_trace_started and not _tool_used),
                                    streamed=bool(_stream_chunks),
                                )
                                yield await _agent_step("waiting", _wait_detail, _wait_label, int(_idle_for))
                            await asyncio.sleep(0.02)
                            continue
                        _trace_state.note_activity()
                        if _item is None:
                            break
                        if isinstance(_item, tuple) and len(_item) == 2 and _item[0] == "__error__":
                            raise _item[1]
                        if isinstance(_item, dict):
                            if _item.get("_stream_reset"):
                                _reset_info = _item.get("_stream_reset") or {}
                                _dropped_text, _think_carry, _inside_think_block = _reset_stream_visible_state(
                                    _stream_chunks,
                                    _think_carry,
                                )
                                _trace_state.replace_collected_steps(_trim_collected_steps_for_stream_reset(
                                    _trace_state.collected_steps,
                                    keep_prefix_count=_stream_attempt_step_keep_count,
                                ))
                                _trace_state.reset_progress_tracking()
                                _thinking_trace.reset()
                                _tool_trace_started = False
                                _tool_inflight_name = ""
                                _markdown_stream.reset()
                                yield {
                                    "event": "stream_reset",
                                    "data": json.dumps(
                                        {"reason": str(_reset_info.get("reason") or "stream_reset")},
                                        ensure_ascii=False,
                                    ),
                                }
                                _reset_text = str(_reset_info.get("text") or "").strip()
                                _dropped_stream_prefix = _dropped_text or _reset_text or _dropped_stream_prefix
                                if _dropped_stream_prefix:
                                    S.debug_write("tool_call_stream_prefix_dropped", {
                                        "reason": str(_reset_info.get("reason") or "stream_reset"),
                                        "text_len": len(_dropped_stream_prefix),
                                        "text_preview": _dropped_stream_prefix[:120],
                                    })
                                continue
                            if _item.get("_tool_call"):
                                tc_info = _item["_tool_call"]
                                tc_name = tc_info.get("name", "")
                                tc_preview = str(tc_info.get("preview") or "").strip()
                                tc_process_meta = tc_info.get("process_meta") if isinstance(tc_info.get("process_meta"), dict) else {}
                                _parallel_group_id = str(tc_process_meta.get("parallel_group_id") or "").strip()
                                try:
                                    _parallel_index = max(0, int(tc_process_meta.get("parallel_index") or 0))
                                except (TypeError, ValueError):
                                    _parallel_index = 0
                                try:
                                    _parallel_size = max(0, int(tc_process_meta.get("parallel_size") or 0))
                                except (TypeError, ValueError):
                                    _parallel_size = 0
                                try:
                                    _parallel_completed_count = max(0, int(tc_process_meta.get("parallel_completed_count") or 0))
                                except (TypeError, ValueError):
                                    _parallel_completed_count = 0
                                try:
                                    _parallel_success_count = max(0, int(tc_process_meta.get("parallel_success_count") or 0))
                                except (TypeError, ValueError):
                                    _parallel_success_count = 0
                                try:
                                    _parallel_failure_count = max(0, int(tc_process_meta.get("parallel_failure_count") or 0))
                                except (TypeError, ValueError):
                                    _parallel_failure_count = 0
                                _parallel_tools = [
                                    str(name or "").strip()
                                    for name in (tc_process_meta.get("parallel_tools") or [])
                                    if str(name or "").strip()
                                ]
                                _MEMORY_TOOL_NAMES = {"recall_memory": "\u56de\u5fc6\u8bb0\u5fc6", "query_knowledge": "\u67e5\u8be2\u77e5\u8bc6"}
                                _tool_skill_display = _MEMORY_TOOL_NAMES.get(tc_name) or S.get_skill_display_name(tc_name)
                                if tc_name == "web_search":
                                    _tool_skill_display = "\u8054\u7f51\u641c\u7d22"
                                _tool_expected_output = _build_expected_output(
                                    phase="tool",
                                    tool_name=tc_name,
                                    preview=tc_preview,
                                    display_name=_tool_skill_display,
                                )
                                _tool_next_user_need = _build_next_user_need(
                                    user_message=msg,
                                    tool_name=tc_name,
                                    preview=tc_preview,
                                    expected_output=_tool_expected_output,
                                )
                                _tool_handoff_note = (
                                    f"\u5148\u4ea4\u7ed9\u300c{_tool_skill_display}\u300d\u628a\u8fd9\u4e00\u6b65\u9700\u8981\u7684\u4f9d\u636e\u62ff\u5230"
                                    if _tool_skill_display
                                    else "\u5148\u62ff\u5230\u8fd9\u4e00\u6b65\u9700\u8981\u7684\u5173\u952e\u4f9d\u636e"
                                )
                                if tc_info.get("executing"):
                                    _tool_inflight_name = tc_name
                                    async for _evt in _emit_thinking_trace(force=True):
                                        yield _evt
                                    _thinking_trace.queue_followup_segment()
                                    _tool_trace_started = True
                                    if not _dropped_stream_prefix:
                                        _dropped_stream_prefix = _drop_incomplete_tool_handoff_prefix(_stream_chunks)
                                        if _dropped_stream_prefix:
                                            _markdown_stream.reset()
                                            yield {
                                                "event": "stream_reset",
                                                "data": json.dumps(
                                                    {"reason": "tool_handoff_prefix_dropped"},
                                                    ensure_ascii=False,
                                                ),
                                            }
                                            S.debug_write("tool_call_stream_prefix_dropped", {
                                                "tool_name": tc_name,
                                                "text_len": len(_dropped_stream_prefix),
                                                "text_preview": _dropped_stream_prefix[:120],
                                            })
                                    _comp.activity = "skill"
                                    skill_display = _tool_skill_display
                                    _is_mem_tool = tc_name in _MEMORY_TOOL_NAMES
                                    if tc_name == "web_search":
                                        _trace_label = "\u8054\u7f51\u641c\u7d22"
                                        skill_display = "\u8054\u7f51\u641c\u7d22"
                                    elif _is_mem_tool:
                                        _trace_label = "\u68c0\u7d22\u8bb0\u5fc6"
                                    else:
                                        _trace_label = "\u8c03\u7528\u6280\u80fd"
                                    _trace_label = build_tool_execution_trace_label(
                                        _trace_label,
                                        process_meta=tc_process_meta,
                                    )
                                    _reason_note = _build_tool_reason_note(tc_name, tc_preview, skill_display)
                                    if _reason_note:
                                        _update_thinking_meta(
                                            reason_kind="tool_decision",
                                            goal=tc_preview or skill_display,
                                            decision_note=_reason_note,
                                            handoff_note=_tool_handoff_note,
                                            expected_output=_tool_expected_output,
                                            next_user_need=_tool_next_user_need,
                                        )
                                        _thinking_trace.apply_preferred_reason_note(
                                            tool_name=tc_name,
                                            preview=tc_preview,
                                            reason_note=_reason_note,
                                            action_summary=_tool_action_summary,
                                        )
                                        async for _evt in _emit_thinking_trace(force=True):
                                            yield _evt
                                    elif not _thinking_trace.trace_sent:
                                        async for _evt in _emit_default_thinking_trace():
                                            yield _evt
                                    _trace_detail = build_tool_execution_trace_detail(
                                        tool_name=tc_name,
                                        preview=tc_preview,
                                        skill_display=skill_display,
                                        process_meta=tc_process_meta,
                                    )
                                    yield await _trace(
                                        _trace_label,
                                        _trace_detail,
                                        "running",
                                        phase="tool",
                                        tool_name=tc_name,
                                        goal=tc_preview,
                                        handoff_note=_tool_handoff_note,
                                        expected_output=_tool_expected_output,
                                        next_user_need=_tool_next_user_need,
                                        reason_kind="tool_execution",
                                        full_detail=_trace_detail,
                                        parallel_group_id=_parallel_group_id,
                                        parallel_index=_parallel_index,
                                        parallel_size=_parallel_size,
                                        parallel_tools=_parallel_tools,
                                    )
                                elif tc_info.get("done"):
                                    if tc_info.get("synthetic") and not _dropped_stream_prefix and _stream_chunks:
                                        _dropped_stream_prefix = _drop_incomplete_tool_handoff_prefix(_stream_chunks)
                                        if _dropped_stream_prefix:
                                            yield {
                                                "event": "stream_reset",
                                                "data": json.dumps(
                                                    {"reason": "tool_handoff_prefix_dropped"},
                                                    ensure_ascii=False,
                                                ),
                                            }
                                            S.debug_write("tool_call_stream_prefix_dropped", {
                                                "tool_name": tc_name,
                                                "text_len": len(_dropped_stream_prefix),
                                                "text_preview": _dropped_stream_prefix[:120],
                                                "synthetic": True,
                                            })
                                    _tool_inflight_name = ""
                                    _tool_used = tc_name
                                    _tool_success = bool(tc_info.get("success"))
                                    _tool_run_meta = tc_info.get("run_meta") if isinstance(tc_info.get("run_meta"), dict) else {}
                                    _plan_update = _extract_task_plan_from_meta(_tool_run_meta)
                                    if _plan_update:
                                        _task_plan = _plan_update
                                        yield {"event": "plan", "data": json.dumps(_plan_update, ensure_ascii=False)}
                                    _tool_action_summary = str(tc_info.get("action_summary") or "").strip()
                                    _tool_response_text = str(tc_info.get("response") or "").strip()
                                    _comp.activity = "replying"
                                    _MEMORY_TOOL_NAMES2 = {"recall_memory": "\u56de\u5fc6\u8bb0\u5fc6", "query_knowledge": "\u67e5\u8be2\u77e5\u8bc6"}
                                    _dn = _MEMORY_TOOL_NAMES2.get(tc_name) or ("联网搜索" if tc_name == "web_search" else S.get_skill_display_name(tc_name))
                                    _is_mem2 = tc_name in _MEMORY_TOOL_NAMES2
                                    _parallel_group_active = bool(
                                        _parallel_group_id and _parallel_size > 1 and _parallel_completed_count < _parallel_size
                                    )
                                    _parallel_group_failed = bool(
                                        _parallel_group_id
                                        and _parallel_size > 1
                                        and _parallel_completed_count >= _parallel_size
                                        and _parallel_failure_count > 0
                                    )
                                    if tc_info.get("success"):
                                        if tc_name == "web_search":
                                            _done_label = "\u641c\u7d22\u5b8c\u6210"
                                        elif _is_mem2:
                                            _done_label = "\u8bb0\u5fc6\u5c31\u7eea"
                                        else:
                                            _done_label = "\u6280\u80fd\u5b8c\u6210"
                                        _done_label = build_tool_done_label(
                                            _done_label,
                                            success=True,
                                            process_meta=tc_process_meta,
                                        )
                                        _done_detail = build_tool_done_trace_detail(
                                            tool_name=tc_name,
                                            preview=tc_preview,
                                            success=True,
                                            action_summary=str(tc_info.get("action_summary") or "").strip(),
                                            response=tc_info.get("response", ""),
                                            process_meta=tc_process_meta,
                                        ) or f"{_dn}\u5b8c\u6210"
                                        yield await _trace(
                                            _done_label,
                                            _done_detail,
                                            "running" if _parallel_group_active else ("error" if _parallel_group_failed else "done"),
                                            step_key="" if (_parallel_group_id and _parallel_size > 1) else _trace_state.active_tool_step_key,
                                            phase="tool",
                                            tool_name=tc_name,
                                            goal=tc_preview,
                                            expected_output=_tool_expected_output,
                                            next_user_need=_tool_next_user_need,
                                            reason_kind="tool_result",
                                            full_detail=_done_detail,
                                            parallel_group_id=_parallel_group_id,
                                            parallel_index=_parallel_index,
                                            parallel_size=_parallel_size,
                                            parallel_completed_count=_parallel_completed_count,
                                            parallel_success_count=_parallel_success_count,
                                            parallel_failure_count=_parallel_failure_count,
                                            parallel_tools=_parallel_tools,
                                        )
                                    else:
                                        if tc_name == "web_search":
                                            _fail_label = "\u641c\u7d22\u5931\u8d25"
                                        elif _is_mem2:
                                            _fail_label = "\u68c0\u7d22\u5931\u8d25"
                                        else:
                                            _fail_label = "\u6280\u80fd\u5931\u8d25"
                                        _fail_label = build_tool_done_label(
                                            _fail_label,
                                            success=False,
                                            process_meta=tc_process_meta,
                                        )
                                        _fail_detail = build_tool_done_trace_detail(
                                            tool_name=tc_name,
                                            preview=tc_preview,
                                            success=False,
                                            action_summary=str(tc_info.get("action_summary") or "").strip(),
                                            response=tc_info.get("response", ""),
                                            process_meta=tc_process_meta,
                                        ) or f"{_dn}\u5931\u8d25"
                                        yield await _trace(
                                            _fail_label,
                                            _fail_detail,
                                            "running" if _parallel_group_active else "error",
                                            step_key="" if (_parallel_group_id and _parallel_size > 1) else _trace_state.active_tool_step_key,
                                            phase="tool",
                                            tool_name=tc_name,
                                            goal=tc_preview,
                                            expected_output=_tool_expected_output,
                                            next_user_need=_tool_next_user_need,
                                            reason_kind="tool_result",
                                            full_detail=_fail_detail,
                                            parallel_group_id=_parallel_group_id,
                                            parallel_index=_parallel_index,
                                            parallel_size=_parallel_size,
                                            parallel_completed_count=_parallel_completed_count,
                                            parallel_success_count=_parallel_success_count,
                                            parallel_failure_count=_parallel_failure_count,
                                            parallel_tools=_parallel_tools,
                                        )
                            elif _item.get("_done"):
                                async for _evt in _emit_thinking_trace(force=True):
                                    yield _evt
                                _tool_used = _item.get("tool_used")
                                _tool_inflight_name = ""
                                if "run_meta" in _item and isinstance(_item.get("run_meta"), dict):
                                    _tool_run_meta = _item.get("run_meta") or {}
                                    _plan_update = _extract_task_plan_from_meta(_tool_run_meta)
                                    if _plan_update:
                                        _task_plan = _plan_update
                                        yield {"event": "plan", "data": json.dumps(_plan_update, ensure_ascii=False)}
                                if "success" in _item:
                                    _tool_success = bool(_item.get("success"))
                                if "tool_response" in _item:
                                    _tool_response_text = str(_item.get("tool_response") or _tool_response_text or "").strip()
                                _tool_action_summary = str(_item.get("action_summary") or _tool_action_summary or "").strip()
                                break
                            elif _item.get("_thinking"):
                                async for _evt in _ensure_followup_thinking_segment(emit_default=True):
                                    yield _evt
                            elif "_thinking_content" in _item:
                                _thinking_trace.activate_pending_segment()
                                _thinking_trace.append_text(str(_item.get("_thinking_content") or ""))
                                async for _evt in _emit_thinking_trace():
                                    yield _evt
                            continue
                        # 文本 token — 过滤 <think> 标签
                        _visible_parts, _think_carry, _inside_think_block, _saw_think = _consume_think_filtered_stream_text(
                            _think_carry,
                            _item,
                            in_think=_inside_think_block,
                        )
                        if _saw_think:
                            async for _evt in _ensure_followup_thinking_segment(emit_default=True):
                                yield _evt
                        for _visible in _visible_parts:
                            if not _visible:
                                continue
                            _stream_chunks.append(_visible)
                            _stream_payload = _markdown_stream.feed(_visible)
                            if _stream_payload:
                                yield {"event": "stream", "data": json.dumps(_stream_payload, ensure_ascii=False)}
                                # 超过 7 字符没出现 <think>，直接输出
                            if False:
                                if _think_buf.strip():
                                    _stream_chunks.append(_think_buf)
                                    yield {"event": "stream", "data": json.dumps({"token": _think_buf}, ensure_ascii=False)}
                            # else: 继续缓冲，等更多 token 到达再判断
                        if False:
                            _stream_chunks.append(_item)
                            yield {"event": "stream", "data": json.dumps({"token": _item}, ensure_ascii=False)}

                    _tail_parts, _think_carry, _inside_think_block, _tail_saw_think = _consume_think_filtered_stream_text(
                        _think_carry,
                        "",
                        in_think=_inside_think_block,
                        end_of_stream=True,
                    )
                    if _tail_saw_think:
                        async for _evt in _ensure_followup_thinking_segment(emit_default=True):
                            yield _evt
                    for _tail in _tail_parts:
                        if not _tail:
                            continue
                        _stream_chunks.append(_tail)
                        _stream_payload = _markdown_stream.feed(_tail)
                        if _stream_payload:
                            yield {"event": "stream", "data": json.dumps(_stream_payload, ensure_ascii=False)}
                    _final_stream_payload = _markdown_stream.flush()
                    if _final_stream_payload:
                        yield {"event": "stream", "data": json.dumps(_final_stream_payload, ensure_ascii=False)}
                    async for _evt in _emit_thinking_trace(force=True):
                        yield _evt
                    response = "".join(_stream_chunks)
                    if not _tool_used and not str(_thinking_trace.trace_text or "").strip():
                        _update_thinking_meta(
                            decision_note=_build_direct_reply_reason_note(has_context=bool(history)),
                            expected_output="",
                            next_user_need="",
                        )
                        async for _evt in _emit_thinking_trace(force=True):
                            yield _evt
                    S.debug_write("tool_call_stream_done", {
                        "chunks": len(_stream_chunks),
                        "len": len(response),
                        "tool_used": _tool_used,
                        "dropped_prefix_len": len(_dropped_stream_prefix),
                    })
                except Exception as _tce:
                    failure_message = f"\u5de5\u5177\u6267\u884c\u5f02\u5e38\uff1a{type(_tce).__name__}: {_tce}"
                    S.debug_write("tool_call_error", {
                        "error": failure_message,
                        "tool_inflight": _tool_inflight_name,
                        "tool_used": _tool_used,
                    })
                    if _tool_inflight_name:
                        _tool_used = _tool_inflight_name
                        _tool_success = False
                        _tool_response_text = failure_message if not _tool_response_text else f"{_tool_response_text}\n\n{failure_message}"
                        if not _tool_action_summary:
                            _tool_action_summary = _summarize_tool_response_text(_tool_response_text)
                        response = _tool_response_text
                        if _tool_action_summary:
                            yield await _trace(
                                "\u6280\u80fd\u5931\u8d25",
                                " \u00b7 ".join([p for p in [_tool_used, _tool_action_summary] if p]),
                                "error",
                            )
                    if not _stream_chunks and not _tool_inflight_name:
                        response = failure_message
                    if False and not _stream_chunks and not _tool_inflight_name:
                        # fallback 到非流式 tool_call
                        # legacy frontend non-stream fallback removed; keep branch unreachable for localized compatibility cleanup
                        tc_result = {}
                        response = tc_result.get("reply", "")
                        _tool_used = tc_result.get("tool_used")
                        _tool_run_meta = tc_result.get("run_meta") if isinstance(tc_result.get("run_meta"), dict) else {}
                        _plan_update = _extract_task_plan_from_meta(_tool_run_meta)
                        if _plan_update:
                            _task_plan = _plan_update
                            yield {"event": "plan", "data": json.dumps(_plan_update, ensure_ascii=False)}
                        _tool_success = tc_result.get("success") if _tool_used else None
                        _tool_response_text = str(tc_result.get("tool_response") or "").strip()
                        _action_summary = str(tc_result.get("action_summary") or "").strip()
                        _tool_action_summary = _action_summary or _tool_action_summary
                        if _tool_used and _action_summary:
                            yield await _trace(
                                "技能完成" if _tool_success else "技能失败",
                                " · ".join([p for p in [_tool_used, _action_summary] if p]),
                                "done" if _tool_success else "error",
                            )
                    elif _stream_chunks or _tool_inflight_name:
                        response = "".join(_stream_chunks)

                # 记录技能使用统计
                _direct_tool_gap = _classify_missing_tool_execution(
                    response,
                    tool_used=_tool_used or "",
                    stream_had_output=bool(_stream_chunks),
                )
                if _direct_tool_gap:
                    S.debug_write(
                        "tool_call_direct_gap",
                        {
                            "reason": _direct_tool_gap.get("reason"),
                            "summary": _direct_tool_gap.get("summary", ""),
                            "response_preview": response[:120],
                        },
                    )
                if _tool_used:
                    try:
                        run_event = _build_run_event(
                            success=bool(_tool_success) if _tool_success is not None else True,
                            meta=_tool_run_meta,
                            fallback_text=response,
                            fallback_summary=_tool_action_summary,
                        )
                        S.evolve(msg, _tool_used, run_event=run_event)
                    except Exception:
                        pass
                    route = {"mode": "skill", "skill": _tool_used, "reason": "tool_call", "source": "tool_call"}
                else:
                    route = {
                        "mode": "chat",
                        "skill": "none",
                        "reason": "tool_call_direct_unfulfilled" if _direct_tool_gap else "tool_call_direct",
                        "source": "tool_call",
                    }

                # ── CoD 闪念/溯源 + L6 埋点（tool_call 路径）──────────────
                try:
                    from core.runtime_state.state_loader import record_memory_stats
                    _RECALL_TOOLS = {"recall_memory", "query_knowledge"}
                    _tc_cod_used = bool(_tool_used and _tool_used in _RECALL_TOOLS)
                    # L6：tool_call 调的是真实技能（非记忆工具）= 技能执行
                    _l6_hit = 1 if (_tool_used and _tool_used not in _RECALL_TOOLS) else 0
                    record_memory_stats(
                        l6_hits=_l6_hit,
                        cod_used=_tc_cod_used,
                        count_query=False,
                    )
                except Exception:
                    pass
                _record_tool_call_memory_stats(_tool_used, _tool_run_meta, _tool_success)

                # 跳到最终回复处理（不走下面的正常路径）
                response = _finalize_tool_call_reply_for_user(
                    response,
                    history=history,
                    strip_markdown=_strip_markdown,
                    ensure_tool_call_failure_reply=_ensure_tool_call_failure_reply,
                    tool_used=_tool_used or "",
                    tool_success=_tool_success,
                    tool_response=_tool_response_text,
                    action_summary=_tool_action_summary,
                    run_meta=_tool_run_meta,
                    stream_had_output=bool(_stream_chunks),
                    debug_write=S.debug_write,
                )
                if _task_plan and (_tool_success is False or _direct_tool_gap):
                    _blocked_plan = _block_task_plan_after_failure(
                        _task_plan,
                        goal_hint=msg,
                        tool_used=_tool_used or ("tool_call" if _direct_tool_gap else ""),
                        action_summary=_tool_action_summary or str(_direct_tool_gap.get("summary") or "").strip(),
                        tool_response=_tool_response_text or response,
                    )
                    if _blocked_plan and _blocked_plan != _task_plan:
                        _task_plan = _blocked_plan
                        yield {"event": "plan", "data": json.dumps(_blocked_plan, ensure_ascii=False)}
                S.debug_write("pre_reply_yield", {"response_len": len(response), "response_preview": response[:100]})
                await asyncio.sleep(0.05)
                yield await _agent_step("complete")
                yield {"event": "reply", "data": json.dumps(_build_reply_payload(response), ensure_ascii=False)}

                try:
                    from brain import _detect_emotion
                except Exception:
                    _detect_emotion = None
                _update_companion_reply_state(_comp, response, detect_emotion=_detect_emotion)

                # 后台任务
                feedback_rule = None
                try:
                    feedback_rule = S.l7_record_feedback_v2(msg, history, background_tasks)
                except Exception:
                    pass
                # ── L7 埋点 ──
                if feedback_rule:
                    _record_feedback_memory_hit(feedback_rule)
                    awareness_evt = _build_feedback_awareness_event(feedback_rule)
                    if awareness_evt:
                        S.awareness_push(awareness_evt)
                        yield {"event": "awareness", "data": json.dumps(awareness_evt, ensure_ascii=False)}
                try:
                    S.l8_touch()
                    l8_config = S.load_autolearn_config()
                    if _should_schedule_autolearn(
                        l8_config,
                        feedback_rule=feedback_rule,
                        l8=l8,
                    ):
                        background_tasks.add_task(S.run_l8_autolearn_task, msg, response, route, bool(l8))
                except Exception:
                    pass

                repair_payload = _build_repair_payload(route, feedback_rule)
                if repair_payload.get("show"):
                    yield {"event": "repair", "data": json.dumps(repair_payload, ensure_ascii=False)}

                S.debug_write("final_response", {"reply": response, "repair": repair_payload})
                try:
                    # L1 卫生检查：防止自我强化的毒教材
                    response = _persist_reply_artifacts(
                        response,
                        history,
                        steps=_trace_state.collected_steps,
                        normalize_steps=_normalize_persisted_process_steps,
                        persist_assistant_history_entry=_history_tx.persist_assistant_entry,
                        debug_write=S.debug_write,
                        add_memory=lambda text: S.l2_add_memory(msg, text),
                        task_plan=_task_plan,
                        include_empty_steps_with_plan=True,
                    )
                except Exception:
                    pass
                return

        except Exception as exc:
            S.debug_write("chat_exception", {"error": str(exc)})
            S.trigger_self_repair_from_error("chat_exception", {"message": msg, "error": str(exc)}, background_tasks)
            response = "\u62b1\u6b49\uff0c\u51fa\u9519\u4e86"

        # 最终回复（清理 think 标签 + markdown + 预回复卫生）
        response = _prepare_reply_for_user(
            response,
            history,
            strip_markdown=_strip_markdown,
            debug_write=S.debug_write,
        )
        S.debug_write("pre_reply_yield", {"response_len": len(response), "response_preview": response[:100]})
        await asyncio.sleep(0.05)
        yield await _agent_step("complete")
        yield {"event": "reply", "data": json.dumps(_build_reply_payload(response), ensure_ascii=False)}
        S.debug_write("post_reply_yield", {"ok": True})

        try:
            from brain import _detect_emotion
        except Exception:
            _detect_emotion = None
        _update_companion_reply_state(_comp, response, detect_emotion=_detect_emotion)

        # 后台任务
        feedback_rule = None
        try:
            feedback_rule = S.l7_record_feedback_v2(msg, history, background_tasks)
        except Exception:
            pass
        # ── L7 埋点 ──
        if feedback_rule:
            _record_feedback_memory_hit(feedback_rule)
        if feedback_rule:
            awareness_evt = _build_feedback_awareness_event(feedback_rule)
            S.awareness_push(awareness_evt)
            yield {"event": "awareness", "data": json.dumps(awareness_evt, ensure_ascii=False)}
        try:
            S.l8_touch()
            l8_config = S.load_autolearn_config()
            if _should_schedule_autolearn(
                l8_config,
                feedback_rule=feedback_rule,
                l8=l8,
                route=route,
                forbid_missing_skill_intent=True,
            ):
                background_tasks.add_task(S.run_l8_autolearn_task, msg, response, route, bool(l8))
        except Exception as _post_exc:
            S.debug_write("post_reply_error", {"stage": "l8", "error": str(_post_exc)})

        repair_payload = _build_repair_payload(route, feedback_rule)
        if repair_payload.get("show"):
            yield {"event": "repair", "data": json.dumps(repair_payload, ensure_ascii=False)}

        S.debug_write("final_response", {"reply": response, "repair": repair_payload})
        try:
            # L1 卫生检查：防止自我强化的毒教材
            response = _persist_reply_artifacts(
                response,
                history,
                steps=_trace_state.collected_steps,
                normalize_steps=_normalize_persisted_process_steps,
                persist_assistant_history_entry=_history_tx.persist_assistant_entry,
                debug_write=S.debug_write,
                add_memory=lambda text: S.l2_add_memory(msg, text),
            )
        except Exception as _post_exc:
            S.debug_write("post_reply_error", {"stage": "save", "error": str(_post_exc)})

      except Exception as _fatal:
        S.debug_write("event_stream_fatal", {"error": str(_fatal), "type": type(_fatal).__name__})
        import traceback
        S.debug_write("event_stream_traceback", {"tb": traceback.format_exc()})
        _history_tx.rollback_pending_user("event_stream_fatal")
        yield {"event": "reply", "data": json.dumps(_build_reply_payload(f"\u5185\u90e8\u9519\u8bef\uff1a{_fatal}"), ensure_ascii=False)}
      except BaseException as _base:
        try:
            from decision.tool_runtime.runtime_control import request_tool_runtime_cancel

            request_tool_runtime_cancel(
                bundle if isinstance(bundle, dict) else None,
                reason="user_interrupted",
                detail=f"{type(_base).__name__}: {_base}",
            )
        except Exception:
            pass
        S.debug_write("event_stream_cancelled", {"error": str(_base), "type": type(_base).__name__})
        _history_tx.rollback_pending_user("event_stream_cancelled")
        raise

    return EventSourceResponse(event_stream(), ping=2)


@router.post("/chat/answer")
async def chat_answer(request: ChatAnswerRequest):
    from core.tool_adapter import ask_user_submit

    accepted = ask_user_submit(request.question_id, request.answer)
    S.debug_write("chat_answer_submit", {
        "question_id": request.question_id,
        "accepted": bool(accepted),
    })
    return {"ok": bool(accepted)}
