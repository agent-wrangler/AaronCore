"""
NovaCore Agent Engine - Unified Entry
当前唯一主入口：8090 本地服务
"""
import asyncio
import sys
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

import json
import requests
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from core.state_loader import (
    ENGINE_DIR, CORE_DIR, PRIMARY_STATE_DIR, LEGACY_STATE_DIR, LOGS_DIR,
    HTML_FILE, RESTORED_OUTPUT_JS_FILE, LLM_CONFIG_FILE,
    PRIMARY_HISTORY_FILE, LEGACY_HISTORY_FILE,
    PRIMARY_STATS_FILE, LEGACY_STATS_FILE,
    LEGACY_L3_SKILL_ARCHIVE_FILE, DOCS_DIR,
    event_text, is_legacy_l3_skill_log, ensure_long_term_clean,
    load_current_model,
    extract_doc_title, extract_doc_summary, build_docs_index, resolve_doc_path,
    load_msg_history, save_msg_history, get_recent_messages,
    load_l3_long_term, load_l4_persona, load_l5_knowledge,
    load_stats_data, record_stats, reset_stats,
)
from core.state_loader import init as _state_loader_init

LOGS_DIR.mkdir(exist_ok=True)
PRIMARY_STATE_DIR.mkdir(exist_ok=True)
debug_log = LOGS_DIR / "chat_debug.log"


def debug_write(stage: str, data):
    try:
        with open(debug_log, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {stage}: {json.dumps(data, ensure_ascii=False)}\n")
    except Exception:
        pass


# ── 轻感知状态层：内存事件队列 ──────────────────────────────
_awareness_lock = threading.Lock()
_awareness_events: list = []


def awareness_push(event: dict):
    """L7/L8 处理完成后调用，将事件暂存到队列供前端拉取。"""
    event.setdefault("ts", datetime.now().isoformat())
    event.setdefault("date", date.today().isoformat())
    with _awareness_lock:
        _awareness_events.append(event)
    debug_write("awareness_push", {"type": event.get("type"), "summary": event.get("summary", "")})


def awareness_pull(since_ts: str = None) -> list:
    """取出待推送事件。只返回今日事件，已取出则移除。"""
    today = date.today().isoformat()
    with _awareness_lock:
        result = [e for e in _awareness_events
                  if e.get("date") == today and (not since_ts or e["ts"] > since_ts)]
        for e in result:
            if e in _awareness_events:
                _awareness_events.remove(e)
        _awareness_events[:] = [e for e in _awareness_events if e.get("date") == today]
        return result


try:
    sys.path.insert(0, str(CORE_DIR))
    from router import route as nova_route
    from executor import execute as nova_execute
    from core.skills import get_all_skills

    NOVA_CORE_READY = True
    CORE_IMPORT_ERROR = ""
except Exception as exc:
    NOVA_CORE_READY = False
    CORE_IMPORT_ERROR = str(exc)

sys.path.insert(0, str(ENGINE_DIR))
from brain import think
from core.l8_learn import (
    auto_learn as l8_auto_learn,
    auto_learn_from_feedback as l8_feedback_relearn,
    find_relevant_knowledge,
    init as _l8_learn_init,
    load_autolearn_config,
    should_surface_knowledge_entry,
    should_trigger_auto_learn,
    update_autolearn_config,
    is_explicit_learning_request,
    explicit_search_and_learn,
)
from core.self_repair import (
    apply_self_repair_report,
    create_self_repair_report,
    find_feedback_rule,
    load_self_repair_reports,
    preview_self_repair_report,
)
from memory import add_to_history, evolve, get_history as get_text_history
from core.session_context import extract_session_context
from core.l2_memory import (
    add_memory as l2_add_memory,
    search_relevant as l2_search_relevant,
    format_l2_context,
)
from core.l2_memory import init as _l2_memory_init


def _raw_llm_call(prompt: str) -> str:
    """裸 LLM 调用：不带人格，纯意图分类用"""
    from brain import LLM_CONFIG
    try:
        resp = requests.post(
            f"{LLM_CONFIG['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_CONFIG['api_key']}", "Content-Type": "application/json"},
            json={"model": LLM_CONFIG["model"], "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.1, "max_tokens": 100},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            usage = data.get("usage", {})
            if usage:
                try:
                    record_stats(
                        input_tokens=usage.get("prompt_tokens", 0),
                        output_tokens=usage.get("completion_tokens", 0),
                        scene="route",
                        cache_write=usage.get("prompt_cache_miss_tokens", 0),
                        cache_read=usage.get("prompt_cache_hit_tokens", 0),
                    )
                except Exception:
                    pass
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception:
        pass
    return ""


def _knowledge_llm_call(prompt: str) -> str:
    """知识凝结专用 LLM 调用：允许更长输出"""
    from brain import LLM_CONFIG
    try:
        resp = requests.post(
            f"{LLM_CONFIG['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_CONFIG['api_key']}", "Content-Type": "application/json"},
            json={"model": LLM_CONFIG["model"], "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.2, "max_tokens": 300},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            usage = data.get("usage", {})
            if usage:
                try:
                    record_stats(
                        input_tokens=usage.get("prompt_tokens", 0),
                        output_tokens=usage.get("completion_tokens", 0),
                        scene="learn",
                        cache_write=usage.get("prompt_cache_miss_tokens", 0),
                        cache_read=usage.get("prompt_cache_hit_tokens", 0),
                    )
                except Exception:
                    pass
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception:
        pass
    return ""


_state_loader_init(
    debug_write=debug_write,
    get_all_skills=get_all_skills if NOVA_CORE_READY else None,
    nova_core_ready=NOVA_CORE_READY,
)

_l2_memory_init(
    debug_write=debug_write,
    think=think,
    llm_call=_raw_llm_call,
)

_l8_learn_init(
    llm_call=_knowledge_llm_call,
    debug_write=debug_write,
)

from core.feedback_classifier import init as _feedback_classifier_init, search_relevant_rules
_feedback_classifier_init(
    llm_call=_raw_llm_call,
    debug_write=debug_write,
)

from core.json_store import load_json, write_json, load_json_store
from core.context_builder import (
    summarize_event_value, stringify_event_value,
    build_persona_events, normalize_event_time,
    is_follow_up_like, build_dialogue_context,
    format_l8_context, build_context_bundle,
)
from core.context_builder import init as _context_builder_init
_context_builder_init(
    find_relevant_knowledge=find_relevant_knowledge,
    extract_session_context=extract_session_context,
)

from core.route_resolver import (
    build_router_prompt, normalize_route_result, has_skill_target,
    is_registered_skill_name, looks_like_news_request,
    detect_missing_capability_route, detect_story_follow_up_route,
    llm_route, resolve_route,
)
from core.route_resolver import init as _route_resolver_init


_route_resolver_init(
    nova_route=nova_route if NOVA_CORE_READY else None,
    debug_write=debug_write,
    think=think,
    get_all_skills=get_all_skills if NOVA_CORE_READY else None,
    nova_core_ready=NOVA_CORE_READY,
    search_l2=l2_search_relevant,
    llm_call=_raw_llm_call,
)

from core.reply_formatter import (
    list_primary_capabilities, get_skill_display_name,
    build_meta_bug_report_reply, build_answer_correction_reply,
    unified_chat_reply,
    format_skill_fallback, format_skill_error_reply, format_story_reply,
    prettify_trace_reason, build_trace_summary,
    _build_learning_summary, _build_repair_summary, _build_latest_status_summary,
)
from core.reply_formatter import init as _reply_formatter_init
_reply_formatter_init(
    think=think,
    debug_write=debug_write,
    nova_core_ready=NOVA_CORE_READY,
    get_all_skills=get_all_skills if NOVA_CORE_READY else None,
    nova_execute=nova_execute if NOVA_CORE_READY else None,
    evolve=evolve,
    load_autolearn_config=load_autolearn_config,
    load_self_repair_reports=load_self_repair_reports,
    find_feedback_rule=find_feedback_rule,
)


def build_self_repair_status() -> dict:
    """Wrapper that uses module-level names so tests can patch them."""
    l8_config = load_autolearn_config()
    all_reports = load_self_repair_reports()
    latest = all_reports[0] if all_reports else {}
    latest_preview = latest.get("patch_preview") or {}
    latest_apply = latest.get("apply_result") or {}
    planning_enabled = bool(l8_config.get("allow_self_repair_planning", True))
    test_run_enabled = bool(l8_config.get("allow_self_repair_test_run", True))
    auto_apply_enabled = bool(l8_config.get("allow_self_repair_auto_apply", True))
    apply_mode = str(l8_config.get("self_repair_apply_mode") or "confirm").strip() or "confirm"
    learning_summary = _build_learning_summary(l8_config)
    repair_summary = _build_repair_summary(l8_config)

    _stripped = learning_summary.rstrip("\u3002")
    return {
        "stage": "controlled_patch_loop" if planning_enabled else "feedback_learning_only",
        "feedback_learning": bool(l8_config.get("allow_feedback_relearn", True)),
        "web_learning": bool(l8_config.get("allow_web_search", True)),
        "knowledge_write": bool(l8_config.get("allow_knowledge_write", True)),
        "planning_enabled": planning_enabled,
        "test_run_enabled": test_run_enabled,
        "auto_apply_enabled": auto_apply_enabled,
        "skill_generation": bool(l8_config.get("allow_skill_generation", False)),
        "apply_mode": apply_mode,
        "report_count": len(all_reports),
        "latest_report_id": str(latest.get("id") or ""),
        "latest_report_status": str(latest.get("status") or ""),
        "latest_summary": str(latest.get("summary") or ""),
        "latest_apply_status": str(latest_apply.get("status") or ""),
        "latest_risk_level": str(latest_preview.get("risk_level") or latest.get("risk_level") or ""),
        "latest_auto_apply_ready": bool(latest_preview.get("auto_apply_ready")),
        "latest_confirmation_required": bool(latest_preview.get("confirmation_required", True)),
        "learning_summary": learning_summary,
        "repair_summary": repair_summary,
        "autonomy_summary": f"{_stripped}\uff1b{repair_summary}",
        "latest_status_summary": _build_latest_status_summary(latest, latest_preview, latest_apply),
        "can_patch_source_code": True,
        "can_plan_repairs": planning_enabled,
        "can_run_source_tests": test_run_enabled,
        "can_auto_apply_fixes": planning_enabled and test_run_enabled and auto_apply_enabled,
    }


def build_capability_chat_reply(route: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    intent = str(route.get("intent") or "").strip()
    status = build_self_repair_status()

    if intent == "self_repair_capability":
        return (
            "\u6211\u73b0\u5728\u5df2\u7ecf\u63a5\u4e0a\u66f4\u7701\u5fc3\u7684\u81ea\u4fee\u6b63\u5566\u3002\u73b0\u5728\u8fd9\u5957\u80fd\u8d70\u5230\u201c\u6536\u5230\u8d1f\u53cd\u9988 -> \u751f\u6210\u4fee\u6b63\u63d0\u6848 -> \u5217\u5019\u9009\u6587\u4ef6 -> \u8dd1\u6700\u5c0f\u6d4b\u8bd5\u201d\u8fd9\u4e00\u6b65\u3002\n\n"
            "\u5982\u679c\u53ea\u662f\u4f4e\u98ce\u9669\u7684\u5c0f\u4fee\u5c0f\u8865\uff0c\u6211\u4f1a\u5728\u540e\u53f0\u76f4\u63a5\u5c1d\u8bd5\u843d\u8865\u4e01\uff1b\u53ea\u8981\u6539\u52a8\u78b0\u5230\u66f4\u6838\u5fc3\u7684\u94fe\u8def\uff0c\u6211\u5c31\u5148\u95ee\u4f60\u4e00\u6b21\u3002"
            "\u5982\u679c\u8865\u4e01\u540e\u7684\u6700\u5c0f\u9a8c\u8bc1\u6ca1\u8fc7\uff0c\u6211\u4f1a\u81ea\u52a8\u56de\u6eda\uff0c\u4e0d\u628a\u574f\u6539\u52a8\u7559\u5728\u6e90\u7801\u91cc\u3002"
        )

    if intent == "missing_skill":
        missing_skill = str(route.get("missing_skill") or route.get("skill") or "\u6280\u80fd").strip() or "\u6280\u80fd"
        label = get_skill_display_name(missing_skill)
        prompt = str(route.get("rewritten_input") or "").strip()
        if missing_skill == "news" or looks_like_news_request(prompt):
            return f"\u6211\u672c\u6765\u60f3\u6309\u300c{label}\u300d\u8fd9\u6761\u8def\u63a5\u4f4f\u4f60\u8fd9\u53e5\uff0c\u4f46\u8fd9\u9879\u80fd\u529b\u73b0\u5728\u6ca1\u63a5\u4e0a\uff0c\u6240\u4ee5\u6211\u5148\u4e0d\u4e71\u62a5\u201c\u4eca\u5929\u201d\u7684\u65b0\u95fb\uff0c\u514d\u5f97\u628a\u65e7\u4fe1\u606f\u5f53\u6210\u73b0\u5728\u3002"
        return f"\u6211\u672c\u6765\u60f3\u6309\u300c{label}\u300d\u8fd9\u6761\u80fd\u529b\u63a5\u4f4f\u4f60\u8fd9\u53e5\uff0c\u4e0d\u8fc7\u5b83\u73b0\u5728\u6ca1\u63a5\u4e0a\uff0c\u6240\u4ee5\u5148\u4e0d\u62ff\u4e00\u6761\u5931\u6548\u7ed3\u679c\u7cca\u5f04\u4f60\u3002"

    skills = "\u3001".join(list_primary_capabilities())
    tail = "\u6e90\u7801\u81ea\u4fee\u8fd9\u8fb9\u73b0\u5728\u662f\uff1a\u4f4e\u98ce\u9669\u5c0f\u6539\u52a8\u4f1a\u5148\u81ea\u5df1\u4fee\uff0c\u78b0\u5230\u66f4\u6838\u5fc3\u7684\u94fe\u8def\u518d\u95ee\u4f60\u4e00\u6b21\uff1b\u5982\u679c\u9a8c\u8bc1\u4e0d\u8fc7\uff0c\u6211\u4f1a\u81ea\u52a8\u56de\u6eda\u3002"
    if status["feedback_learning"]:
        return f"\u6211\u73b0\u5728\u80fd\u966a\u4f60\u804a\u5929\uff0c\u4e5f\u80fd\u505a\u8fd9\u4e9b\uff1a{skills}\u3002{tail}"
    return f"\u6211\u73b0\u5728\u80fd\u966a\u4f60\u804a\u5929\uff0c\u4e5f\u80fd\u505a\u8fd9\u4e9b\uff1a{skills}\u3002"


def build_repair_progress_payload(route: dict | None = None, feedback_rule: dict | None = None) -> dict:
    route = route if isinstance(route, dict) else {}
    feedback_rule = feedback_rule if isinstance(feedback_rule, dict) else {}
    intent = str(route.get("intent") or "").strip()
    feedback_type = str(feedback_rule.get("type") or "").strip()
    feedback_problem = str(feedback_rule.get("problem") or "").strip()

    should_show = intent in {"meta_bug_report", "answer_correction"} or feedback_type in {"skill_route", "llm_rule", "execution_policy"}
    if not should_show and feedback_problem not in {"wrong_skill_selected", "output_not_matching_intent", "fallback_too_generic"}:
        return {"show": False}

    status = build_self_repair_status()
    can_plan = bool(status.get("can_plan_repairs"))
    headline = "\u5df2\u8bb0\u5f55\u53cd\u9988"
    detail = "\u6211\u5148\u628a\u8fd9\u6b21\u53cd\u9988\u8bb0\u4e0b\u4e86\u3002"
    item = "\u5f53\u524d\u4e8b\u9879\uff1a\u5148\u628a\u8fd9\u6b21\u95ee\u9898\u8bb0\u8fdb\u4fee\u590d\u94fe\u8def\u3002"
    if intent == "answer_correction":
        headline = "\u5df2\u6536\u5230\u7ea0\u504f"
        detail = "\u6211\u5148\u628a\u8fd9\u6b21\u7b54\u504f\u548c\u9519\u8def\u7531\u8bb0\u4e0b\u6765\u4e86\u3002"
        item = "\u5f53\u524d\u4e8b\u9879\uff1a\u56de\u770b\u4e0a\u4e00\u8f6e\u7684\u7b54\u590d\u548c\u88ab\u8bef\u89e6\u53d1\u7684\u6280\u80fd\u3002"
    if can_plan:
        detail += " \u63a5\u4e0b\u6765\u4f1a\u7ee7\u7eed\u770b\u4fee\u590d\u63d0\u6848\u3001\u9a8c\u8bc1\u7ed3\u679c\u548c\u662f\u5426\u9700\u8981\u56de\u6eda\u3002"
    else:
        detail += " \u73b0\u5728\u8fd8\u6ca1\u6253\u5f00\u81ea\u52a8\u4fee\u590d\u89c4\u5212\uff0c\u6240\u4ee5\u4f1a\u5148\u505c\u5728\u8bb0\u5f55\u8fd9\u4e00\u6b65\u3002"

    return {
        "show": True,
        "watch": can_plan,
        "label": "\u4fee\u590d\u8fdb\u5ea6",
        "stage": "logged",
        "headline": headline,
        "detail": detail,
        "item": item,
        "progress": 22,
        "poll_ms": 1600,
        "max_polls": 10,
    }


def unified_skill_reply(bundle: dict, skill_name: str, skill_input: str) -> dict:
    route_result = {"mode": "skill", "skill": skill_name, "params": {}, "role": "assistant"}
    # 把 L4 用户上下文传给 executor，技能可按需读取（如天气读城市）
    skill_context = {}
    l4 = bundle.get("l4") or {}
    if isinstance(l4, dict):
        up = l4.get("user_profile") or {}
        if isinstance(up, dict):
            skill_context["user_city"] = str(up.get("city") or "").strip()
            skill_context["user_identity"] = str(up.get("identity") or "").strip()
    execute_result = nova_execute(route_result, skill_input, skill_context) if NOVA_CORE_READY else {"success": False}
    debug_write("execute_result", execute_result)
    if not execute_result.get("success"):
        error_text = str(execute_result.get("error", "") or "").strip()
        if "\u672a\u627e\u5230" in error_text or "\u6ca1\u6709\u53ef\u6267\u884c\u51fd\u6570" in error_text:
            debug_write("skill_missing", {"skill": skill_name, "input": skill_input, "error": error_text})
            trigger_self_repair_from_error("skill_missing", {"skill": skill_name, "input": skill_input, "error": error_text})
        else:
            debug_write("skill_failed", {"skill": skill_name, "input": skill_input, "error": error_text})
            # timeout / 网络错误等临时性故障不触发修复提案
            if "timeout" not in error_text.lower() and "connection" not in error_text.lower():
                trigger_self_repair_from_error("skill_failed", {"skill": skill_name, "input": skill_input, "error": error_text})
        return {
            "reply": format_skill_error_reply(skill_name, error_text, bundle.get("user_input", "")),
            "trace": {"skill": skill_name, "success": False, "error": error_text},
        }

    try:
        evolve(bundle["user_input"], skill_name)
    except Exception as exc:
        debug_write("evolve_error", {"skill": skill_name, "error": str(exc)})

    skill_response = execute_result.get("response", "")
    if skill_name == "story":
        return {
            "reply": format_story_reply(bundle["user_input"], skill_response),
            "trace": {"skill": skill_name, "success": True},
        }

    # 文章技能：article.py 已处理文件保存和摘要，直接透传
    if skill_name == "article":
        return {
            "reply": skill_response,
            "trace": {"skill": skill_name, "success": True},
        }

    # 新闻类技能：新闻 → LLM排版 → 人格润色，三步分离
    if skill_name == "news":
        dialogue_context = bundle.get("dialogue_context", "")
        # Step 1: 干净的 LLM 调用做排版（不走 think，避免人格指令干扰）
        format_prompt = (
            f"下面是刚从 Google News 抓到的新闻（已翻译成中文）：\n{skill_response}\n\n"
            "请把这些新闻整理成一份结构清晰的新闻简报：\n"
            "1. 按话题分板块（国际局势、科技、财经、社会等），板块标题用你喜欢的样式\n"
            "2. 每条新闻单独一行，保留来源，不要压缩或合并\n"
            "3. 不要加开场白和结尾点评，只输出分好板块的新闻列表\n"
            "直接输出结果。"
        )
        from brain import LLM_CONFIG
        formatted = ""
        try:
            llm_resp = requests.post(
                f"{LLM_CONFIG['base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_CONFIG['api_key']}", "Content-Type": "application/json"},
                json={"model": LLM_CONFIG["model"], "messages": [{"role": "user", "content": format_prompt}], "max_tokens": 2000},
                timeout=25,
            )
            if llm_resp.status_code == 200:
                formatted = llm_resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception:
            pass
        if not formatted or len(formatted) < 20:
            formatted = skill_response

        # Step 2: 直接做人格润色 LLM 调用（不走 think，避免 12s 超时）
        l4 = bundle.get("l4") or {}
        persona_data = l4.get("local_persona") or {}
        style = str(persona_data.get("style_prompt", "")).strip() or "\u6e29\u67d4\u3001\u81ea\u7136\u3001\u6709\u70b9\u4eb2\u8fd1\u611f"
        nova_name = str(persona_data.get("nova_name", "Nova")).strip()
        user_name = str(persona_data.get("user", "\u4e3b\u4eba")).strip()

        polish_prompt = (
            f"\u4f60\u662f {nova_name}\uff0c\u6b63\u5728\u7ed9 {user_name} \u62a5\u65b0\u95fb\u3002\n"
            f"\u4f60\u7684\u98ce\u683c\uff1a{style}\n\n"
            f"\u4e0b\u9762\u662f\u6574\u7406\u597d\u7684\u65b0\u95fb\u5217\u8868\uff1a\n{formatted}\n\n"
            "\u8981\u6c42\uff1a\n"
            "1. \u5728\u65b0\u95fb\u5217\u8868\u524d\u52a0\u4e00\u53e5\u4f60\u98ce\u683c\u7684\u5f00\u573a\u767d\n"
            "2. \u5728\u65b0\u95fb\u5217\u8868\u540e\u52a0\u4e00\u4e24\u53e5\u4f60\u7684\u70b9\u8bc4\n"
            "3. \u65b0\u95fb\u5217\u8868\u672c\u8eab\u539f\u6837\u4fdd\u7559\uff0c\u4e0d\u8981\u6539\u52a8\u3001\u538b\u7f29\u6216\u5408\u5e76\n"
            "4. \u53ea\u8f93\u51fa\u6700\u7ec8\u7ed3\u679c"
        )
        reply = ""
        try:
            polish_resp = requests.post(
                f"{LLM_CONFIG['base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_CONFIG['api_key']}", "Content-Type": "application/json"},
                json={"model": LLM_CONFIG["model"], "messages": [{"role": "user", "content": polish_prompt}], "temperature": 0.7, "max_tokens": 2500},
                timeout=30,
            )
            if polish_resp.status_code == 200:
                reply = polish_resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception:
            pass
        if not reply or len(reply.strip()) < 20 or "\ufffd" in reply:
            reply = f"\u62ff\u597d\u5566\uff0c\u4eca\u5929\u7684\u65b0\u95fb\u6211\u5e2e\u4f60\u6293\u56de\u6765\u4e86\uff5e\n\n{formatted}"
        return {
            "reply": reply.strip(),
            "trace": {"skill": skill_name, "success": True},
        }

    dialogue_context = bundle.get("dialogue_context", "")
    prompt = f"""
\u7528\u6237\u8f93\u5165\uff1a{bundle['user_input']}

\u6280\u80fd\u7ed3\u679c\uff1a
{skill_response}

L4\u4eba\u683c\u4fe1\u606f\uff1a
{json.dumps(bundle['l4'], ensure_ascii=False)}

\u4f60\u5fc5\u987b\u4e25\u683c\u6309\u7167 L4 \u4eba\u683c\u4fe1\u606f\u4e2d\u7684\u98ce\u683c\u89c4\u5219\u6765\u56de\u590d\uff01

\u4eba\u683c\u98ce\u683c\u8981\u70b9\uff1a
1. \u8bed\u6c14\u8f6f\u8f6f\u7cef\u7cef\uff0c\u7231\u6492\u5a07\uff0c\u591a\u7528\u8bed\u6c14\u8bcd\uff08\u5566\u3001\u561b\u3001\u5440\u3001\u54e6\u3001\u545c\u545c\uff09
2. \u50cf\u670b\u53cb\u804a\u5929\uff0c\u63a5\u5730\u6c14\uff0c\u4e0d\u6253\u5b98\u8154
3. \u7b80\u6d01\u4e0d\u5570\u55e6\uff0c\u4e00\u53e5\u8bdd\u80fd\u8bf4\u5b8c\u4e0d\u62c6\u597d\u51e0\u6bb5
4. \u5076\u5c14\u53ef\u4ee5\u76ae\u4e00\u4e0b\u3001\u8c03\u4f83\u4e00\u4e0b\uff0c\u4e0d\u662f\u5168\u7a0b\u751c\u7f8e
5. \u8981\u628a\u6280\u80fd\u7ed3\u679c\u81ea\u7136\u878d\u8fdb\u804a\u5929\u8bed\u6c14\u91cc\uff0c\u4e0d\u8981\u50cf\u7cfb\u7edf\u64ad\u62a5

\u7981\u6b62\uff1a
- \u4e0d\u8981\u201c\u60a8\u597d\uff0c\u8bf7\u95ee\u6709\u4ec0\u4e48\u53ef\u4ee5\u5e2e\u60a8\u201d\u8fd9\u79cd\u5ba2\u670d\u8154
- \u4e0d\u8981\u6ee1\u5c4f emoji
- \u4e0d\u8981\u673a\u68b0\u5957\u6a21\u677f
- \u4e0d\u8981\u628a\u6280\u80fd\u7ed3\u679c\u539f\u6837\u786c\u7529\u7ed9\u7528\u6237

\u8981\u6c42\uff1a
1. \u5fc5\u987b\u4e25\u683c\u57fa\u4e8e\u6280\u80fd\u7ed3\u679c\u56de\u7b54\uff0c\u4e0d\u80fd\u6539\u4e8b\u5b9e\u3002
2. \u6839\u636e L4 \u91cc\u7684\u98ce\u683c\u89c4\u5219\u6765\u786e\u5b9a\u8bed\u6c14\u3002
3. \u5982\u679c\u7528\u6237\u8fd9\u53e5\u8bdd\u662f\u5728\u63a5\u4e0a\u4e00\u8f6e\u7ee7\u7eed\u8ffd\u95ee\uff0c\u8981\u81ea\u7136\u63a5\u7740\u524d\u6587\u8bf4\uff0c\u4e0d\u8981\u50cf\u91cd\u65b0\u5f00\u4e86\u4e00\u4e2a\u8bdd\u9898\u3002
4. \u7528\u7edf\u4e00\u7684\u4eba\u683c\u53e3\u543b\u8f93\u51fa\uff0c\u4e0d\u8981\u50cf\u7cfb\u7edf\u63d0\u793a\u3002
5. \u4e0d\u8981\u8f93\u51fa\u601d\u8003\u8fc7\u7a0b\u3002
6. \u53ea\u8f93\u51fa\u6700\u7ec8\u56de\u590d\u3002
""".strip()
    result = think(prompt, dialogue_context)
    reply = result.get("reply", "") if isinstance(result, dict) else str(result)
    if (not reply) or ("\ufffd" in str(reply)) or len(str(reply).strip()) < 2:
        return {
            "reply": format_skill_fallback(skill_response),
            "trace": {"skill": skill_name, "success": True},
        }
    return {
        "reply": str(reply).strip(),
        "trace": {"skill": skill_name, "success": True},
    }


from core.feedback_loop import (
    l7_record_feedback, l7_record_feedback_v2,
    l8_touch, run_l8_autolearn_task, run_l8_feedback_relearn_task,
    run_self_repair_planning_task, build_l8_diagnosis,
    trigger_self_repair_from_error,
)
from core.feedback_loop import init as _feedback_loop_init
_feedback_loop_init(
    debug_write=debug_write,
    load_autolearn_config=load_autolearn_config,
    l8_auto_learn=l8_auto_learn,
    l8_feedback_relearn=l8_feedback_relearn,
    find_relevant_knowledge=find_relevant_knowledge,
    should_trigger_auto_learn=should_trigger_auto_learn,
    create_self_repair_report=create_self_repair_report,
    preview_self_repair_report=preview_self_repair_report,
    awareness_push=awareness_push,
)


app = FastAPI()

# 挂载静态文件目录（CSS/JS 模块化拆分后的资源）
from fastapi.staticfiles import StaticFiles as _StaticFiles
_static_dir = ENGINE_DIR / "static"
if _static_dir.is_dir():
    app.mount("/static", _StaticFiles(directory=str(_static_dir)), name="static")


class ChatRequest(BaseModel):
    message: str


# ── Companion 伴侣窗口状态 ──
_companion_activity = "idle"  # idle / thinking / replying / skill
_companion_last_reply = ""    # 最近一次回复摘要
_companion_reply_id = ""      # 回复 ID（用于前端去重）
_companion_model = "Hiyori"   # 当前模型名

COMPANION_HTML_FILE = ENGINE_DIR / "companion.html"
LIVE2D_DIR = ENGINE_DIR / "static" / "live2d"

# 可用模型列表（扫描目录）
def _scan_live2d_models():
    models = {}
    if LIVE2D_DIR.is_dir():
        for d in sorted(LIVE2D_DIR.iterdir()):
            if d.is_dir() and not d.name.startswith("_"):
                m3 = d / f"{d.name}.model3.json"
                if m3.exists():
                    models[d.name] = f"/static/live2d/{d.name}/{d.name}.model3.json"
    return models

_available_models = _scan_live2d_models()


@app.get("/companion", response_class=HTMLResponse)
async def companion_page():
    """伴侣窗口 HTML 页面"""
    if COMPANION_HTML_FILE.exists():
        try:
            html = COMPANION_HTML_FILE.read_text(encoding="utf-8")
            # 内联 companion CSS
            css_file = ENGINE_DIR / "static" / "css" / "companion.css"
            if css_file.exists():
                css = css_file.read_text(encoding="utf-8")
                html = html.replace(
                    '<link rel="stylesheet" href="/static/css/companion.css">',
                    f"<style>{css}</style>",
                )
            return html
        except Exception:
            pass
    return "<html><body style='background:transparent'>companion not found</body></html>"


@app.get("/companion/state")
async def companion_state():
    """伴侣窗口轮询端点：返回当前 mood/activity/最近回复"""
    persona = load_l4_persona()
    ps = persona.get("persona_state", {}) if isinstance(persona, dict) else {}
    return {
        "mood": ps.get("mood", "\u6e29\u67d4"),
        "energy": ps.get("energy", "\u7a33\u5b9a"),
        "active_mode": persona.get("active_mode", "sweet") if isinstance(persona, dict) else "sweet",
        "activity": _companion_activity,
        "last_reply_id": _companion_reply_id,
        "last_reply_summary": _companion_last_reply,
        "model": _companion_model,
        "ts": datetime.now().isoformat(),
    }


@app.get("/companion/models")
async def companion_models():
    """返回可用模型列表"""
    return {"models": _available_models, "current": _companion_model}


@app.post("/companion/model/{name}")
async def companion_switch_model(name: str):
    """切换伴侣模型"""
    global _companion_model
    if name in _available_models:
        _companion_model = name
        return {"ok": True, "model": name, "path": _available_models[name]}
    return {"ok": False, "error": f"model '{name}' not found"}


@app.get("/", response_class=HTMLResponse)
async def home():
    if HTML_FILE.exists():
        try:
            html = HTML_FILE.read_text(encoding="utf-8")
            # 内联 CSS/JS，避免代理拦截静态资源导致样式丢失
            static_dir = ENGINE_DIR / "static"
            css_file = static_dir / "css" / "main.css"
            if css_file.exists():
                css = css_file.read_text(encoding="utf-8")
                html = html.replace(
                    '<link rel="stylesheet" href="/static/css/main.css">',
                    f"<style>{css}</style>",
                )
            js_dir = static_dir / "js"
            js_order = ["utils.js", "awareness.js", "chat.js", "memory.js", "settings.js", "docs.js", "app.js"]
            for js_name in js_order:
                js_file = js_dir / js_name
                if js_file.exists():
                    js = js_file.read_text(encoding="utf-8")
                    html = html.replace(
                        f'<script src="/static/js/{js_name}"></script>',
                        f"<script>{js}</script>",
                    )
            return html
        except Exception:
            pass
    return "<html><head><meta charset='UTF-8'><title>NovaCore</title></head><body><h1>NovaCore</h1><p>\u670d\u52a1\u8fd0\u884c\u4e2d</p></body></html>"


@app.get("/__restored_output.js")
async def get_restored_output_js():
    if not RESTORED_OUTPUT_JS_FILE.exists():
        return Response(
            content="console.error('missing restored output js');",
            media_type="application/javascript; charset=utf-8",
        )
    return Response(
        content=RESTORED_OUTPUT_JS_FILE.read_text(encoding="utf-8"),
        media_type="application/javascript; charset=utf-8",
    )


@app.post("/chat")
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    msg = request.message
    debug_write("input", {"message": msg})
    add_to_history("user", msg)

    history = load_msg_history()
    history.append({"role": "user", "content": msg, "time": datetime.now().isoformat()})
    save_msg_history(history)

    async def event_stream():
        global _companion_activity, _companion_last_reply, _companion_reply_id
        _companion_activity = "thinking"

        async def _trace(label, detail):
            await asyncio.sleep(0.3)
            return {"event": "trace", "data": json.dumps({"label": label, "detail": detail}, ensure_ascii=False)}

        # ── Step 0: 推送上次积攒的感知事件（L8 后台完成的） ──
        pending_awareness = awareness_pull()
        for evt in pending_awareness:
            yield {"event": "awareness", "data": json.dumps(evt, ensure_ascii=False)}

        # ── Step 1: 读取记忆 ──
        l1 = get_recent_messages(history, 6)
        l2 = extract_session_context(history, msg)
        l2_memories = l2_search_relevant(msg)
        user_turns = len([m for m in l1 if isinstance(m, dict) and m.get("role") == "user"])
        mem_detail = f"\u56de\u987e\u4e86\u6700\u8fd1 {user_turns} \u8f6e\u5bf9\u8bdd" if user_turns else "\u8fd9\u662f\u7b2c\u4e00\u53e5\u5bf9\u8bdd"
        if l2.get("topics") and l2["topics"] != ["\u95f2\u804a"]:
            mem_detail += f"\uff0c\u8bdd\u9898\u6d89\u53ca{'、'.join(l2['topics'])}"
        if l2_memories:
            mem_detail += f"\uff0c\u5524\u9192 {len(l2_memories)} \u6761\u6301\u4e45\u8bb0\u5fc6"
        yield await _trace("\u8bfb\u53d6\u8bb0\u5fc6", mem_detail)

        # ── Step 2: 加载人格和知识 ──
        l3 = load_l3_long_term()
        l4 = load_l4_persona()
        l5 = load_l5_knowledge()
        persona_name = ""
        if isinstance(l4, dict):
            lp = l4.get("local_persona") or l4
            persona_name = str(lp.get("nova_name") or lp.get("name") or "")
        skill_count = len(l5.get("skills", {})) if isinstance(l5, dict) else 0
        persona_detail = f"\u4eba\u683c\u8c31\u56fe\u300c{persona_name}\u300d\u5df2\u5524\u9192" if persona_name else "\u4eba\u683c\u8c31\u56fe\u5df2\u5524\u9192"
        yield await _trace("\u52a0\u8f7d\u4eba\u683c", persona_detail)

        # ── Step 3: 检索知识库 ──
        l8 = find_relevant_knowledge(msg, limit=3, touch=True)
        if l8:
            topics = [str(h.get("query") or h.get("name") or "") for h in l8[:2] if isinstance(h, dict)]
            topics = [t for t in topics if t]
            if topics:
                yield await _trace("\u68c0\u7d22\u77e5\u8bc6", "\u5339\u914d\u77e5\u8bc6\u5e93\uff1a" + "\u3001".join(topics))

        # ── 记忆检索统计 ──
        try:
            from core.state_loader import record_memory_stats
            record_memory_stats(
                l2_searches=1, l2_hits=1 if l2_memories else 0,
                l8_searches=1, l8_hits=1 if l8 else 0,
                l1_count=len(l1),
                l3_count=len(l3),
                l4_available=bool(l4 and isinstance(l4, dict) and len(l4) > 0),
                l5_count=skill_count,
            )
        except Exception:
            pass

        # ── Step 4: 理解意图 ──
        dialogue_context = build_dialogue_context(history, msg)
        bundle = {
            "l1": l1, "l2": l2, "l2_memories": l2_memories,
            "l3": l3, "l4": l4, "l5": l5,
            "l7": search_relevant_rules(msg, limit=3),
            "l8": l8,
            "dialogue_context": dialogue_context, "user_input": msg,
        }
        debug_write("context_bundle", {
            "l1": len(l1), "l2": len(l2), "l2_memories": len(l2_memories),
            "l3": len(l3),
            "l4_keys": list(l4.keys()) if isinstance(l4, dict) else [],
            "l5_skill_count": skill_count, "l8": len(l8 or []),
        })

        response = ""
        route = {"mode": "chat", "skill": "none", "reason": "default"}
        try:
            # ── Step 3.5: 检测人格模式切换 ──
            from brain import _detect_mode_switch
            mode_switch_reply = _detect_mode_switch(msg)
            if mode_switch_reply:
                response = mode_switch_reply
                yield await _trace("\u4eba\u683c\u5207\u6362", "\u5df2\u5207\u6362\u4eba\u683c\u6a21\u5f0f")
                yield {"event": "reply", "data": json.dumps({"reply": response}, ensure_ascii=False)}
                _companion_activity = "idle"
                add_to_history("assistant", response)
                history.append({"role": "assistant", "content": response, "time": datetime.now().isoformat()})
                save_msg_history(history)
                return

            route = resolve_route(bundle)
            debug_write("resolved_route", route)
            mode = route.get("mode", "chat")
            skill = route.get("skill", "none")
            rewritten_input = route.get("rewritten_input") or msg

            reason_text = prettify_trace_reason(route)
            if reason_text:
                yield await _trace("\u7406\u89e3\u610f\u56fe", reason_text)

            if mode in ("skill", "hybrid") and skill not in ("none", "", None) and NOVA_CORE_READY:
                # ── Step 5: 调用技能 ──
                _companion_activity = "skill"
                skill_display = get_skill_display_name(skill)
                yield await _trace("\u8c03\u7528\u6280\u80fd", f"\u6b63\u5728\u8c03\u7528\u300c{skill_display}\u300d\u6280\u80fd\u2026")

                skill_result = unified_skill_reply(bundle, skill, rewritten_input)
                if isinstance(skill_result, dict):
                    response = str(skill_result.get("reply", "") or "")
                else:
                    response = str(skill_result or "")
            else:
                # ── Step 5: 生成回复 ──
                _companion_activity = "replying"
                # 检测用户是否主动要求学习/搜索
                if is_explicit_learning_request(msg):
                    yield await _trace("\u8054\u7f51\u641c\u7d22", "\u6b63\u5728\u5206\u6790\u641c\u7d22\u4e3b\u9898\u2026")

                    # 用裸 LLM 从用户原话+上下文中提取真正要搜的主题
                    _extract_prompt = (
                        "\u7528\u6237\u8bf4\u4e86\u4e0b\u9762\u8fd9\u53e5\u8bdd\uff0c\u8bf7\u4ece\u4e2d\u63d0\u53d6\u51fa\u4ed6\u771f\u6b63\u60f3\u641c\u7d22/\u5b66\u4e60\u7684\u4e3b\u9898\u5173\u952e\u8bcd\u3002"
                        "\u5982\u679c\u7528\u6237\u6ca1\u6709\u6307\u5b9a\u5177\u4f53\u4e3b\u9898\uff08\u6bd4\u5982\u53ea\u8bf4\u201c\u53bb\u5b66\u70b9\u4e1c\u897f\u201d\uff09\uff0c"
                        "\u5c31\u6839\u636e\u4e4b\u524d\u7684\u5bf9\u8bdd\u4e0a\u4e0b\u6587\uff0c\u9009\u4e00\u4e2a\u7528\u6237\u53ef\u80fd\u611f\u5174\u8da3\u7684\u4e3b\u9898\u3002"
                        "\u53ea\u8f93\u51fa\u641c\u7d22\u5173\u952e\u8bcd\uff0c\u4e0d\u8981\u89e3\u91ca\uff0c\u4e0d\u8981\u52a0\u5f15\u53f7\uff0c\u4e0d\u8d85\u8fc715\u4e2a\u5b57\u3002\n\n"
                        f"\u7528\u6237\u539f\u8bdd\uff1a{msg}\n"
                        f"\u6700\u8fd1\u5bf9\u8bdd\u4e0a\u4e0b\u6587\uff1a{bundle.get('dialogue_context', '')[:300]}"
                    )
                    _raw_topic = _raw_llm_call(_extract_prompt)
                    search_topic = str(_raw_topic or "").strip()[:15]
                    search_topic = search_topic.strip('"\'\u201c\u201d\u300c\u300d\u3010\u3011')
                    if len(search_topic) < 2 or len(search_topic) > 40:
                        search_topic = msg
                    # 如果 LLM 没能精简搜索词（跟原文一样），做停用词清理
                    if search_topic == msg:
                        import re as _re
                        _stop = ["\u5e2e\u6211","\u7ed9\u6211","\u80fd\u4e0d\u80fd","\u53ef\u4ee5","\u597d\u770b\u7684","\u6700\u65b0\u7684","\u4e00\u4e0b","\u51e0\u672c","\u4e00\u4e9b","\u4f60","\u5417","\u5440","\u5462","\u4e86","\u7684","\u70b9"]
                        _cleaned = msg
                        for sw in _stop:
                            _cleaned = _cleaned.replace(sw, "")
                        _cleaned = _re.sub(r'\s+', ' ', _cleaned).strip()
                        if len(_cleaned) >= 2:
                            search_topic = _cleaned
                    debug_write("extract_search_topic", {"input": msg, "topic": search_topic})

                    yield await _trace("\u8054\u7f51\u641c\u7d22", "\u641c\u7d22\u4e3b\u9898\uff1a" + search_topic)
                    search_result = explicit_search_and_learn(search_topic)
                    debug_write("explicit_search", {
                        "topic": search_topic,
                        "success": search_result.get("success"),
                        "reason": search_result.get("reason", ""),
                        "result_count": search_result.get("result_count", 0),
                    })
                    if search_result.get("success"):
                        # 把搜索结果注入 bundle，让 LLM 基于真实数据生成回复
                        search_context = "\u3010\u5b9e\u65f6\u641c\u7d22\u7ed3\u679c\u3011\n"
                        for i, r in enumerate(search_result.get("results", [])[:5], 1):
                            search_context += f"{i}. {r.get('title', '')}\n   {r.get('snippet', '')}\n"
                        bundle["search_context"] = search_context
                        bundle["search_summary"] = search_result.get("summary", "")
                        yield await _trace("\u6574\u7406\u7ed3\u679c", "搜到 " + str(search_result.get("result_count", 0)) + " \u6761\u7ed3\u679c\uff0c\u6b63\u5728\u6574\u7406\u2026")
                    else:
                        debug_write("explicit_search_failed", {"reason": search_result.get("reason", "")})
                        yield await _trace("\u7ec4\u7ec7\u56de\u590d", "\u641c\u7d22\u672a\u627e\u5230\u7ed3\u679c\uff0c\u7ed3\u5408\u5df2\u6709\u77e5\u8bc6\u56de\u590d\u2026")
                else:
                    yield await _trace("\u7ec4\u7ec7\u56de\u590d", f"\u300c{persona_name or 'Nova'}\u300d\u6b63\u5728\u8ba4\u771f\u601d\u8003\u5e76\u56de\u590d\u4f60\u2026")
                response = unified_chat_reply(bundle, route)
        except Exception as exc:
            debug_write("chat_exception", {"error": str(exc)})
            trigger_self_repair_from_error("chat_exception", {"message": msg, "error": str(exc)}, background_tasks)
            response = "\u62b1\u6b49\uff0c\u51fa\u9519\u4e86"

        # ── 最终回复 ──
        await asyncio.sleep(0.05)
        yield {"event": "reply", "data": json.dumps({"reply": response}, ensure_ascii=False)}
        _companion_activity = "idle"

        # 更新伴侣窗口的回复摘要（截取前 30 字）
        _companion_reply_id = datetime.now().isoformat()
        summary = str(response or "").replace("\n", " ").strip()
        _companion_last_reply = summary[:60] + ("..." if len(summary) > 60 else "")

        # ── 后台任务 ──
        feedback_rule = l7_record_feedback_v2(msg, history, background_tasks)
        if feedback_rule:
            awareness_evt = {
                "type": "l7_feedback",
                "summary": "记录反馈规则: " + feedback_rule.get("category", "未分类"),
                "detail": {
                    "id": feedback_rule.get("id"),
                    "scene": feedback_rule.get("scene", ""),
                    "problem": feedback_rule.get("problem", ""),
                    "category": feedback_rule.get("category", ""),
                    "fix": feedback_rule.get("fix", ""),
                },
            }
            awareness_push(awareness_evt)
            yield {"event": "awareness", "data": json.dumps(awareness_evt, ensure_ascii=False)}
        l8_touch()
        l8_config = load_autolearn_config()
        if (
            l8_config.get("enabled", True)
            and l8_config.get("allow_web_search", True)
            and l8_config.get("allow_knowledge_write", True)
            and not feedback_rule
            and not (l8 or [])
            and route.get("intent") != "missing_skill"
        ):
            background_tasks.add_task(run_l8_autolearn_task, msg, response, route, bool(l8))

        repair_payload = build_repair_progress_payload(route, feedback_rule)
        if repair_payload.get("show"):
            yield {"event": "repair", "data": json.dumps(repair_payload, ensure_ascii=False)}

        debug_write("final_response", {"reply": response, "repair": repair_payload})
        add_to_history("nova", response)
        history.append({"role": "nova", "content": response, "time": datetime.now().isoformat()})
        save_msg_history(history)

        # L2 持久记忆入库
        try:
            l2_add_memory(msg, response)
        except Exception as exc:
            debug_write("l2_add_error", {"error": str(exc)})

    return EventSourceResponse(event_stream())


@app.get("/skills/news/headlines")
async def get_news_headlines():
    """欢迎页今日热点，取 Google News top 6 条标题"""
    try:
        from core.skills.news import _parse_rss, GOOGLE_NEWS_FEEDS
        url = GOOGLE_NEWS_FEEDS.get("top", list(GOOGLE_NEWS_FEEDS.values())[0])
        items, _ = _parse_rss(url, limit=6)
        headlines = [item.get("title", "") for item in items if item.get("title")]
        return {"headlines": headlines}
    except Exception as e:
        return {"headlines": [], "error": str(e)}


@app.get("/stats")
async def get_stats():
    return {"stats": load_stats_data()}


@app.get("/awareness/pending")
async def get_awareness_pending(since: str = None):
    """前端短期轮询端点：获取待推送的 L7/L8 感知事件。"""
    return {"events": awareness_pull(since_ts=since), "server_ts": datetime.now().isoformat()}


@app.post("/stats")
async def update_stats(request: dict):
    if isinstance(request, dict) and request.get("reset"):
        stats = reset_stats()
        return {"ok": True, "stats": stats}
    inp = int(request.get("input_tokens", 0)) if isinstance(request, dict) else 0
    out = int(request.get("output_tokens", 0)) if isinstance(request, dict) else 0
    scene = str(request.get("scene", "chat")) if isinstance(request, dict) else "chat"
    stats = record_stats(input_tokens=inp, output_tokens=out, scene=scene)
    return {"ok": True, "stats": stats}


@app.get("/nova_name")
async def get_nova_name():
    persona_path = PRIMARY_STATE_DIR / "persona.json"
    if persona_path.exists():
        try:
            persona = json.loads(persona_path.read_text(encoding="utf-8"))
            return {"name": persona.get("nova_name", "NovaCore")}
        except Exception:
            pass
    return {"name": "NovaCore"}


@app.get("/skills")
async def get_skills():
    if not NOVA_CORE_READY:
        return {"skills": [], "ready": False, "error": CORE_IMPORT_ERROR or "core_not_ready"}

    try:
        skills_data = get_all_skills()
        skills = []
        for name, info in skills_data.items():
            skills.append(
                {
                    "name": info.get("name", name),
                    "keywords": info.get("keywords", []),
                    "description": info.get("description", ""),
                    "priority": info.get("priority", 10),
                    "status": info.get("status", "ready"),
                    "category": info.get("category", "通用"),
                }
            )
        skills.sort(key=lambda item: (item.get("priority", 10), item.get("name", "")))
        return {"skills": skills, "ready": True}
    except Exception as exc:
        return {"skills": [], "ready": False, "error": str(exc)}


@app.get("/history")
async def get_history():
    history = load_msg_history()
    formatted = []
    for item in history[-40:]:
        row = dict(item)
        if "time" in row:
            try:
                row["time"] = datetime.fromisoformat(row["time"]).strftime("%m-%d %H:%M")
            except Exception:
                pass
        formatted.append(row)
    return {"history": formatted, "text_history": get_text_history(20)}


@app.get("/health")
async def get_health():
    return {
        "status": "ok",
        "entry": "agent_final.py",
        "core_ready": NOVA_CORE_READY,
        "current_model": load_current_model(),
        "state_dir": str(PRIMARY_STATE_DIR),
        "time": datetime.now().isoformat(),
    }


@app.get("/autolearn/config")
async def get_autolearn_config():
    return {"config": load_autolearn_config()}


@app.post("/autolearn/config")
async def set_autolearn_config(request: dict):
    patch = request if isinstance(request, dict) else {}
    config = update_autolearn_config(patch)
    return {"ok": True, "config": config}


@app.get("/autolearn/diagnose")
async def get_autolearn_diagnosis(query: str, route_mode: str = "chat", skill: str = "none", limit: int = 3):
    return build_l8_diagnosis(query, route_mode=route_mode, skill=skill, limit=limit)


@app.get("/qq/monitor")
async def get_qq_monitor_status():
    try:
        from core.skills.computer_use import qq_monitor_status
        return qq_monitor_status()
    except Exception:
        return {"active": False, "group": None}


@app.get("/l7/stats")
async def get_l7_stats():
    from core.feedback_classifier import _load_rules as _l7_load_rules
    rules = _l7_load_rules()
    total = len(rules)
    with_constraint = sum(1 for r in rules if r.get("constraint"))
    categories = {}
    for r in rules:
        cat = r.get("category", "\u672a\u5206\u7c7b")
        categories[cat] = categories.get(cat, 0) + 1
    latest = None
    if rules:
        rules_sorted = sorted(rules, key=lambda x: x.get("created_at", ""), reverse=True)
        if rules_sorted:
            lt = rules_sorted[0]
            latest = {
                "fix": str(lt.get("fix", ""))[:60],
                "category": lt.get("category", ""),
                "created_at": lt.get("created_at", ""),
            }
    l8_data = load_json(PRIMARY_STATE_DIR / "knowledge_base.json", [])
    l8_count = len([e for e in l8_data if isinstance(e, dict) and e.get("type") != "feedback_relearn"])
    repair_reports = []
    try:
        from core.self_repair import load_self_repair_reports
        repair_reports = load_self_repair_reports()
    except Exception:
        pass
    return {
        "l7_rule_count": total,
        "l7_constraint_count": with_constraint,
        "l7_categories": categories,
        "l7_latest": latest,
        "l8_knowledge_count": l8_count,
        "repair_report_count": len(repair_reports),
    }


@app.get("/self_repair/status")
async def get_self_repair_status():
    return {"status": build_self_repair_status()}


@app.get("/self_repair/reports")
async def get_self_repair_reports(limit: int = 6):
    return {"reports": load_self_repair_reports(limit=max(limit, 1))}


@app.post("/self_repair/propose")
async def create_self_repair_proposal(request: dict | None = None):
    payload = request if isinstance(request, dict) else {}
    rule_id = str(payload.get("feedback_rule_id") or "").strip()
    rule_item = find_feedback_rule(rule_id)
    if not rule_item:
        return {"ok": False, "error": "feedback_rule_not_found"}

    config = load_autolearn_config()
    run_validation = bool(payload.get("run_validation", config.get("allow_self_repair_test_run", True)))
    report = create_self_repair_report(
        rule_item,
        config=config,
        run_validation=run_validation and bool(config.get("allow_self_repair_test_run", True)),
    )
    return {"ok": True, "report": report}


@app.post("/self_repair/preview")
async def preview_self_repair_fix(request: dict | None = None):
    payload = request if isinstance(request, dict) else {}
    report_id = str(payload.get("report_id") or "").strip()
    config = load_autolearn_config()
    auto_apply = bool(payload.get("auto_apply", False))
    run_validation = bool(payload.get("run_validation", config.get("allow_self_repair_test_run", True)))
    try:
        report = preview_self_repair_report(
            report_id=report_id,
            config=config,
            auto_apply=auto_apply,
            run_validation=run_validation,
        )
        debug_write(
            "self_repair_preview",
            {
                "report_id": report.get("id"),
                "preview_status": ((report.get("patch_preview") or {}).get("status")),
                "preview_edit_count": len(((report.get("patch_preview") or {}).get("edits")) or []),
                "risk_level": ((report.get("patch_preview") or {}).get("risk_level")),
                "auto_apply_ready": ((report.get("patch_preview") or {}).get("auto_apply_ready")),
                "apply_status": ((report.get("apply_result") or {}).get("status")),
            },
        )
        return {"ok": True, "report": report}
    except Exception as exc:
        debug_write("self_repair_preview_error", {"error": str(exc), "report_id": report_id})
        return {"ok": False, "error": str(exc)}


@app.post("/self_repair/apply")
async def apply_self_repair_fix(request: dict | None = None):
    payload = request if isinstance(request, dict) else {}
    report_id = str(payload.get("report_id") or "").strip()
    config = load_autolearn_config()
    try:
        report = apply_self_repair_report(report_id=report_id, config=config, run_validation=True)
        debug_write(
            "self_repair_apply",
            {
                "report_id": report.get("id"),
                "status": report.get("status"),
                "apply_status": ((report.get("apply_result") or {}).get("status")),
                "rolled_back": ((report.get("apply_result") or {}).get("rolled_back")),
            },
        )
        return {"ok": True, "report": report}
    except Exception as exc:
        debug_write("self_repair_apply_error", {"error": str(exc), "report_id": report_id})
        return {"ok": False, "error": str(exc)}


@app.get("/docs/index")
async def get_docs_index():
    sections = build_docs_index()
    default_path = ""
    for section in sections:
        docs = section.get("docs", [])
        if docs:
            default_path = docs[0].get("path", "")
            break
    return {"sections": sections, "default_path": default_path}


@app.get("/docs/content")
async def get_doc_content(path: str):
    doc_path = resolve_doc_path(path)
    if not doc_path or not doc_path.exists():
        return {"ok": False, "error": "doc_not_found"}

    try:
        text = doc_path.read_text(encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    return {
        "ok": True,
        "path": doc_path.relative_to(ENGINE_DIR).as_posix(),
        "title": extract_doc_title(text, doc_path.stem),
        "content": text,
    }


@app.get("/memory")
async def get_memory():
    ensure_long_term_clean()
    events = []
    counts = {"L1": 0, "L3": 0, "L4": 0, "L5": 0, "L6": 0, "L7": 0, "L8": 0}

    l1_file = PRIMARY_HISTORY_FILE
    if l1_file.exists():
        try:
            l1_data = json.loads(l1_file.read_text(encoding="utf-8"))
            for item in l1_data:
                content = str(item.get("content") or "").strip()
                if not content:
                    continue
                counts["L1"] += 1
        except Exception:
            pass

    l3_file = PRIMARY_STATE_DIR / "long_term.json"
    if l3_file.exists():
        try:
            l3_data = json.loads(l3_file.read_text(encoding="utf-8"))
            for item in l3_data:
                if is_legacy_l3_skill_log(item):
                    continue
                content = event_text(item)
                if not content:
                    continue
                events.append(
                    {
                        "time": normalize_event_time(item.get("timestamp") or item.get("time") or item.get("created_at")),
                        "layer": "L3",
                        "event_type": item.get("category", "memory"),
                        "title": "记忆结晶",
                        "content": f"沉淀了一段长期记忆：{content}",
                    }
                )
                counts["L3"] += 1
        except Exception:
            pass

    l4_file = PRIMARY_STATE_DIR / "persona.json"
    if l4_file.exists():
        try:
            l4_data = json.loads(l4_file.read_text(encoding="utf-8"))
            # L4 人格事件用固定初始化时间，避免 persona.json 被更新时事件冒顶
            l4_init_time = normalize_event_time(l4_data.get("created_at") or "2026-03-10 00:00")
            for item in build_persona_events(l4_data, l4_init_time):
                events.append(item)
                counts["L4"] += 1
        except Exception:
            pass

    l5_file = PRIMARY_STATE_DIR / "knowledge.json"
    if l5_file.exists():
        try:
            l5_skills = json.loads(l5_file.read_text(encoding="utf-8"))
            for item in l5_skills:
                skill_name = item.get("name") or item.get("核心技能") or "skill"
                skill_count = len(l5_skills)
                events.append(
                    {
                        "time": normalize_event_time(item.get("learned_at") or item.get("最近使用时间")),
                        "layer": "L5",
                        "event_type": "skill",
                        "title": "技能矩阵",
                        "content": f"解锁新技能：「{skill_name}」（已掌握 {skill_count} 项技能）",
                    }
                )
                counts["L5"] += 1
        except Exception:
            pass

    l6_file = PRIMARY_STATE_DIR / "evolution.json"
    if l6_file.exists():
        try:
            l6_data = json.loads(l6_file.read_text(encoding="utf-8"))
            skills_used = l6_data.get("skills_used", {})
            for skill_name, data in skills_used.items():
                if not is_registered_skill_name(skill_name):
                    continue
                count = data.get("count", 0)
                tail = "越来越熟练了" if count >= 3 else "已经留下第一次执行痕迹"
                events.append(
                    {
                        "time": normalize_event_time(data.get("last_used")),
                        "layer": "L6",
                        "event_type": "evolution",
                        "title": "技能执行",
                        "content": f"使用了：「{skill_name}」 （{tail}，累计 {count} 次）",
                    }
                )
                counts["L6"] += 1
        except Exception:
            pass

    l7_file = PRIMARY_STATE_DIR / "feedback_rules.json"
    if l7_file.exists():
        try:
            l7_data = json.loads(l7_file.read_text(encoding="utf-8"))
            for item in l7_data:
                feedback = str(item.get("user_feedback") or "").strip()
                fix = str(item.get("fix") or "").strip()
                category = str(item.get("category") or "").strip()
                scene = str(item.get("scene") or "general").strip()
                content = feedback or "收到一条新的反馈修正规则"
                if fix:
                    content = f"收到反馈：{content}（修正方向：{fix}）"
                title = category or "反馈学习"
                events.append(
                    {
                        "time": normalize_event_time(item.get("created_at") or item.get("time")),
                        "layer": "L7",
                        "event_type": "feedback",
                        "title": title,
                        "content": content,
                        "scene": scene,
                    }
                )
                counts["L7"] += 1
        except Exception:
            pass

    l8_file = PRIMARY_STATE_DIR / "knowledge_base.json"
    if l8_file.exists():
        try:
            l8_data = json.loads(l8_file.read_text(encoding="utf-8"))
            for item in l8_data:
                if not should_surface_knowledge_entry(item):
                    continue
                scene = str(item.get("二级场景") or item.get("核心技能") or item.get("name") or "").strip()
                scene_name = scene.replace("自动学习-", "") if scene else "新经验"
                summary = stringify_event_value(item.get("summary") or item.get("应用示例") or "")
                content = f"习得经验：「{scene_name}」"
                if summary:
                    content += f"：{summary}"
                else:
                    content += "（将转化为技能优化依据）"
                events.append(
                    {
                        "time": normalize_event_time(item.get("最近使用时间") or item.get("time") or item.get("created_at")),
                        "layer": "L8",
                        "event_type": "knowledge",
                        "title": "能力进化",
                        "content": content,
                    }
                )
                counts["L8"] += 1
        except Exception:
            pass

    return {"events": sorted(events, key=lambda item: item["time"], reverse=True), "counts": counts}


if __name__ == "__main__":
    import uvicorn

    print("NovaCore: http://localhost:8090")
    uvicorn.run(app, host="0.0.0.0", port=8090)
