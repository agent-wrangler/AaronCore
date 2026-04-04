"""
共享状态容器 — agent_final.py 启动时赋值，路由模块通过 import 访问。
避免路由模块直接 import agent_final 导致循环依赖。
"""
from datetime import datetime, date
import threading

# ── debug ──
debug_log = None  # Path, set by agent_final


def debug_write(stage: str, data):
    import json
    try:
        with open(debug_log, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {stage}: {json.dumps(data, ensure_ascii=False)}\n")
    except Exception:
        pass


# ── 轻感知状态层：内存事件队列 ──
_awareness_lock = threading.Lock()
_awareness_events: list = []


def awareness_push(event: dict):
    event.setdefault("ts", datetime.now().isoformat())
    event.setdefault("date", date.today().isoformat())
    with _awareness_lock:
        _awareness_events.append(event)
    debug_write("awareness_push", {"type": event.get("type"), "summary": event.get("summary", "")})


def awareness_pull(since_ts: str = None) -> list:
    today = date.today().isoformat()
    with _awareness_lock:
        result = [e for e in _awareness_events
                  if e.get("date") == today and (not since_ts or e["ts"] > since_ts)]
        for e in result:
            if e in _awareness_events:
                _awareness_events.remove(e)
        _awareness_events[:] = [e for e in _awareness_events if e.get("date") == today]
        return result


# ── core 模块引用（agent_final.py 启动时赋值） ──
NOVA_CORE_READY = False
CORE_IMPORT_ERROR = ""

# 函数引用
nova_execute = None
get_all_skills = None
think = None
evolve = None

# LLM 调用
raw_llm_call = None
knowledge_llm_call = None

# L2
l2_add_memory = None
l2_search_relevant = None

# history recall
detect_recall_intent = None
recall_by_time = None

# L8
l8_auto_learn = None
find_relevant_knowledge = None
load_autolearn_config = None
should_surface_knowledge_entry = None
should_trigger_auto_learn = None
update_autolearn_config = None
is_explicit_learning_request = None
explicit_search_and_learn = None

# self_repair
load_self_repair_reports = None
find_feedback_rule = None
create_self_repair_report = None
preview_self_repair_report = None
apply_self_repair_report = None

# feedback_loop
l7_record_feedback_v2 = None
l8_touch = None
run_l8_autolearn_task = None
run_l8_feedback_relearn_task = None
trigger_self_repair_from_error = None
build_l8_diagnosis = None
search_relevant_rules = None

# state_loader
load_current_model = None

# reply_formatter
list_primary_capabilities = None
get_skill_display_name = None
unified_chat_reply = None
unified_chat_reply_stream = None
unified_reply_with_tools = None
unified_reply_with_tools_stream = None
format_skill_fallback = None
format_skill_error_reply = None
format_story_reply = None
prettify_trace_reason = None
_build_learning_summary = None
_build_repair_summary = None
_build_latest_status_summary = None

# context_builder
build_dialogue_context = None
render_dialogue_context = None
extract_session_context = None

# route_resolver
resolve_route = None
resolve_route_fast = None
is_registered_skill_name = None

# state_loader functions
load_msg_history = None
save_msg_history = None
get_recent_messages = None
load_l3_long_term = None
load_l4_persona = None
load_l5_knowledge = None
load_stats_data = None
record_stats = None
reset_stats = None
ensure_long_term_clean = None
event_text = None
is_legacy_l3_skill_log = None
normalize_event_time = None
build_persona_events = None
stringify_event_value = None
summarize_event_value = None
build_docs_index = None
resolve_doc_path = None
extract_doc_title = None
should_surface_knowledge_entry_fn = None

# memory module
add_to_history = None
get_text_history = None

# paths (set by agent_final)
ENGINE_DIR = None
PRIMARY_STATE_DIR = None
PRIMARY_HISTORY_FILE = None
LEGACY_HISTORY_FILE = None
HTML_FILE = None
RESTORED_OUTPUT_JS_FILE = None

# load_json
load_json = None

# skill store
get_skill_catalog_summary = None
get_exposed_skills = None
get_tool_view = None
get_surfacing_view = None
get_user_view = None
get_user_visible_skills = None
get_all_skills_for_ui = None
set_skill_enabled = None
