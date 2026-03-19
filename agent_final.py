"""
NovaCore 主入口 — 仅负责 app 初始化和路由挂载。
所有 API 路由请放到 routes/ 目录下对应模块。
"""
import sys
import requests

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response

from core.state_loader import (
    ENGINE_DIR, CORE_DIR, PRIMARY_STATE_DIR, LOGS_DIR,
    HTML_FILE, RESTORED_OUTPUT_JS_FILE,
    load_current_model,
    load_msg_history, save_msg_history, get_recent_messages,
    load_l3_long_term, load_l4_persona, load_l5_knowledge,
    load_stats_data, record_stats, reset_stats,
    event_text, is_legacy_l3_skill_log, ensure_long_term_clean,
    extract_doc_title, build_docs_index, resolve_doc_path,
    PRIMARY_HISTORY_FILE,
)
from core.state_loader import init as _state_loader_init
from core.context_builder import (
    normalize_event_time, build_persona_events, stringify_event_value,
    build_dialogue_context,
)
from core.context_builder import init as _context_builder_init

# ── shared 状态初始化 ──
from core import shared as S

LOGS_DIR.mkdir(exist_ok=True)
PRIMARY_STATE_DIR.mkdir(exist_ok=True)
S.debug_log = LOGS_DIR / "chat_debug.log"
S.ENGINE_DIR = ENGINE_DIR
S.PRIMARY_STATE_DIR = PRIMARY_STATE_DIR
S.PRIMARY_HISTORY_FILE = PRIMARY_HISTORY_FILE
S.HTML_FILE = HTML_FILE
S.RESTORED_OUTPUT_JS_FILE = RESTORED_OUTPUT_JS_FILE

# ── 便捷别名（保持向后兼容，测试 patch agent_final.debug_write 等） ──
debug_write = S.debug_write
awareness_push = S.awareness_push
awareness_pull = S.awareness_pull

# ── Core 模块导入 ──
try:
    sys.path.insert(0, str(CORE_DIR))
    from router import route as nova_route
    from executor import execute as nova_execute
    from core.skills import get_all_skills
    NOVA_CORE_READY = True
    CORE_IMPORT_ERROR = ""
except Exception as exc:
    nova_route = nova_execute = get_all_skills = None
    NOVA_CORE_READY = False
    CORE_IMPORT_ERROR = str(exc)

sys.path.insert(0, str(ENGINE_DIR))
from brain import think
from core.l8_learn import (
    auto_learn as l8_auto_learn,
    auto_learn_from_feedback as l8_feedback_relearn,
    find_relevant_knowledge, init as _l8_learn_init,
    load_autolearn_config, should_surface_knowledge_entry,
    should_trigger_auto_learn, update_autolearn_config,
    is_explicit_learning_request, explicit_search_and_learn,
)
from core.self_repair import (
    apply_self_repair_report, create_self_repair_report,
    find_feedback_rule, load_self_repair_reports, preview_self_repair_report,
)
from memory import add_to_history, evolve, get_history as get_text_history
from core.session_context import extract_session_context
from core.l2_memory import (
    add_memory as l2_add_memory, search_relevant as l2_search_relevant,
)
from core.l2_memory import init as _l2_memory_init
from core.json_store import load_json
from core.route_resolver import (
    is_registered_skill_name, looks_like_news_request, resolve_route,
    normalize_route_result, detect_story_follow_up_route, llm_route,
)
from core.route_resolver import init as _route_resolver_init
from core.reply_formatter import (
    list_primary_capabilities, get_skill_display_name,
    unified_chat_reply, format_skill_fallback, format_skill_error_reply,
    format_story_reply, prettify_trace_reason,
    _build_learning_summary, _build_repair_summary,
    _build_latest_status_summary,
)
from core.reply_formatter import init as _reply_formatter_init
from core.feedback_classifier import init as _feedback_classifier_init, search_relevant_rules


# ── LLM 调用函数 ──
def _raw_llm_call(prompt: str) -> str:
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
        return ""


def _knowledge_llm_call(prompt: str) -> str:
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


# ── 依赖注入：初始化各 core 模块 ──
_state_loader_init(
    debug_write=debug_write,
    get_all_skills=get_all_skills if NOVA_CORE_READY else None,
    nova_core_ready=NOVA_CORE_READY,
)
_l2_memory_init(debug_write=debug_write, think=think, llm_call=_raw_llm_call)
_l8_learn_init(llm_call=_knowledge_llm_call, debug_write=debug_write)
_feedback_classifier_init(llm_call=_raw_llm_call, debug_write=debug_write)
_context_builder_init(
    find_relevant_knowledge=find_relevant_knowledge,
    extract_session_context=extract_session_context,
)
_route_resolver_init(
    nova_route=nova_route if NOVA_CORE_READY else None,
    debug_write=debug_write, think=think,
    get_all_skills=get_all_skills if NOVA_CORE_READY else None,
    nova_core_ready=NOVA_CORE_READY,
    search_l2=l2_search_relevant, llm_call=_raw_llm_call,
)
_reply_formatter_init(
    think=think, debug_write=debug_write,
    nova_core_ready=NOVA_CORE_READY,
    get_all_skills=get_all_skills if NOVA_CORE_READY else None,
    nova_execute=nova_execute if NOVA_CORE_READY else None,
    evolve=evolve,
    load_autolearn_config=load_autolearn_config,
    load_self_repair_reports=load_self_repair_reports,
    find_feedback_rule=find_feedback_rule,
)

from core.feedback_loop import (
    l7_record_feedback_v2, l8_touch, run_l8_autolearn_task,
    trigger_self_repair_from_error, build_l8_diagnosis,
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

# ── 填充 shared 状态供路由模块使用 ──
S.NOVA_CORE_READY = NOVA_CORE_READY
S.CORE_IMPORT_ERROR = CORE_IMPORT_ERROR
for _name, _val in {
    "nova_route": nova_route, "nova_execute": nova_execute, "get_all_skills": get_all_skills,
    "think": think, "evolve": evolve, "raw_llm_call": _raw_llm_call,
    "l2_add_memory": l2_add_memory, "l2_search_relevant": l2_search_relevant,
    "find_relevant_knowledge": find_relevant_knowledge,
    "load_autolearn_config": load_autolearn_config,
    "should_surface_knowledge_entry": should_surface_knowledge_entry,
    "should_trigger_auto_learn": should_trigger_auto_learn,
    "update_autolearn_config": update_autolearn_config,
    "is_explicit_learning_request": is_explicit_learning_request,
    "explicit_search_and_learn": explicit_search_and_learn,
    "load_self_repair_reports": load_self_repair_reports,
    "find_feedback_rule": find_feedback_rule,
    "create_self_repair_report": create_self_repair_report,
    "preview_self_repair_report": preview_self_repair_report,
    "apply_self_repair_report": apply_self_repair_report,
    "l7_record_feedback_v2": l7_record_feedback_v2, "l8_touch": l8_touch,
    "run_l8_autolearn_task": run_l8_autolearn_task,
    "trigger_self_repair_from_error": trigger_self_repair_from_error,
    "build_l8_diagnosis": build_l8_diagnosis, "search_relevant_rules": search_relevant_rules,
    "load_current_model": load_current_model,
    "list_primary_capabilities": list_primary_capabilities,
    "get_skill_display_name": get_skill_display_name,
    "unified_chat_reply": unified_chat_reply,
    "format_skill_fallback": format_skill_fallback,
    "format_skill_error_reply": format_skill_error_reply,
    "format_story_reply": format_story_reply,
    "prettify_trace_reason": prettify_trace_reason,
    "_build_learning_summary": _build_learning_summary,
    "_build_repair_summary": _build_repair_summary,
    "_build_latest_status_summary": _build_latest_status_summary,
    "build_dialogue_context": build_dialogue_context,
    "extract_session_context": extract_session_context,
    "resolve_route": resolve_route,
    "looks_like_news_request": looks_like_news_request,
    "is_registered_skill_name": is_registered_skill_name,
    "load_msg_history": load_msg_history, "save_msg_history": save_msg_history,
    "get_recent_messages": get_recent_messages,
    "load_l3_long_term": load_l3_long_term, "load_l4_persona": load_l4_persona,
    "load_l5_knowledge": load_l5_knowledge,
    "load_stats_data": load_stats_data, "record_stats": record_stats, "reset_stats": reset_stats,
    "ensure_long_term_clean": ensure_long_term_clean,
    "event_text": event_text, "is_legacy_l3_skill_log": is_legacy_l3_skill_log,
    "normalize_event_time": normalize_event_time,
    "build_persona_events": build_persona_events,
    "stringify_event_value": stringify_event_value,
    "build_docs_index": build_docs_index, "resolve_doc_path": resolve_doc_path,
    "extract_doc_title": extract_doc_title,
    "add_to_history": add_to_history, "get_text_history": get_text_history,
    "load_json": load_json,
}.items():
    setattr(S, _name, _val)

# ── 测试兼容：保留 agent_final 上的函数名供 tests patch ──
# 这些函数必须定义在 agent_final.py 中，因为测试通过 patch("agent_final.xxx") 来 mock 依赖。
# 路由模块通过 lazy import 调用它们。

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
        "show": True, "watch": can_plan, "label": "\u4fee\u590d\u8fdb\u5ea6",
        "stage": "logged", "headline": headline, "detail": detail, "item": item,
        "progress": 22, "poll_ms": 1600, "max_polls": 10,
    }

# ── FastAPI app + 路由挂载 ──
app = FastAPI()

# 启动时清理残留的监听状态（重启后旧的监听进程已死）
try:
    import json as _json
    _monitor_state = ENGINE_DIR / "memory_db" / "qq_monitor_state.json"
    if _monitor_state.exists():
        _json.dump({"active": False, "groups": [], "group": None},
                   open(_monitor_state, "w", encoding="utf-8"), ensure_ascii=False)
except Exception:
    pass

from fastapi.staticfiles import StaticFiles as _StaticFiles
_static_dir = ENGINE_DIR / "static"
if _static_dir.is_dir():
    app.mount("/static", _StaticFiles(directory=str(_static_dir)), name="static")

from routes.health import router as _health_router
from routes.models import router as _models_router
from routes.companion import router as _companion_router
from routes.companion import init as _companion_init
from routes.data import router as _data_router
from routes.settings import router as _settings_router
from routes.chat import router as _chat_router
from routes.chat import unified_skill_reply  # re-export for test compatibility

_companion_init(engine_dir=ENGINE_DIR)

app.include_router(_health_router)
app.include_router(_models_router)
app.include_router(_companion_router)
app.include_router(_data_router)
app.include_router(_settings_router)
app.include_router(_chat_router)


@app.get("/", response_class=HTMLResponse)
async def home():
    if HTML_FILE.exists():
        try:
            html = HTML_FILE.read_text(encoding="utf-8")
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


if __name__ == "__main__":
    import uvicorn
    print("NovaCore: http://localhost:8090")
    uvicorn.run(app, host="0.0.0.0", port=8090)
