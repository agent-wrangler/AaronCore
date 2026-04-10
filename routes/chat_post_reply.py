from __future__ import annotations

from datetime import datetime

from storage.history_store import is_transient_assistant_notice


def update_companion_reply_state(companion, response: str, *, detect_emotion) -> None:
    companion.activity = "idle"
    companion.reply_id = datetime.now().isoformat()
    summary = str(response or "").replace("\n", " ").strip()
    companion.last_reply = summary[:60] + ("..." if len(summary) > 60 else "")
    companion.last_reply_full = summary
    try:
        companion.emotion = detect_emotion(response) if callable(detect_emotion) else "neutral"
    except Exception:
        companion.emotion = "neutral"


def record_feedback_memory_hit(feedback_rule: dict | None) -> None:
    if not isinstance(feedback_rule, dict) or not feedback_rule:
        return
    try:
        from core.runtime_state.state_loader import record_memory_stats

        record_memory_stats(l7_hits=1, count_query=False)
    except Exception:
        pass


def build_feedback_awareness_event(feedback_rule: dict | None) -> dict | None:
    if not isinstance(feedback_rule, dict):
        return None
    event = dict(feedback_rule)
    event["event_type"] = "feedback_awareness"
    event["kind"] = str(event.get("kind") or "general").strip() or "general"
    return event


def build_repair_payload(route: dict | None, feedback_rule: dict | None) -> dict:
    try:
        import agent_final as _af

        payload = _af.build_repair_progress_payload(route, feedback_rule)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def should_schedule_autolearn(
    l8_config: dict | None,
    *,
    feedback_rule: dict | None,
    l8: list | None,
    route: dict | None = None,
    forbid_missing_skill_intent: bool = False,
) -> bool:
    cfg = l8_config if isinstance(l8_config, dict) else {}
    if not cfg.get("enabled", True):
        return False
    if not cfg.get("allow_web_search", True):
        return False
    if not cfg.get("allow_knowledge_write", True):
        return False
    if feedback_rule:
        return False
    if l8:
        return False
    if forbid_missing_skill_intent and str((route or {}).get("intent") or "").strip() == "missing_skill":
        return False
    return True


def build_process_payload(
    steps: list | None,
    *,
    normalize_steps,
    task_plan: dict | None = None,
    include_empty_steps_with_plan: bool = False,
) -> dict | None:
    normalized_steps = normalize_steps(steps) if callable(normalize_steps) else list(steps or [])
    if task_plan:
        process = {"plan": task_plan}
        if normalized_steps or include_empty_steps_with_plan:
            process["steps"] = normalized_steps
        return process
    if normalized_steps:
        return {"steps": normalized_steps}
    return None


def persist_reply_artifacts(
    response: str,
    history: list,
    *,
    steps: list | None,
    normalize_steps,
    persist_assistant_history_entry,
    debug_write=None,
    add_memory=None,
    task_plan: dict | None = None,
    include_empty_steps_with_plan: bool = False,
) -> str:
    text = str(response or "")
    try:
        from core.reply_formatter import l1_hygiene_clean

        text, toxic = l1_hygiene_clean(text, history)
        if toxic and callable(debug_write):
            debug_write("l1_hygiene", {"removed": toxic})
    except Exception:
        pass

    if is_transient_assistant_notice({"role": "nova", "content": text}):
        if callable(debug_write):
            debug_write("reply_skip_transient_notice_persist", {"content": text[:120]})
        return text

    process = build_process_payload(
        steps,
        normalize_steps=normalize_steps,
        task_plan=task_plan,
        include_empty_steps_with_plan=include_empty_steps_with_plan,
    )
    if callable(persist_assistant_history_entry):
        persist_assistant_history_entry("nova", text, process=process)
    if callable(add_memory):
        add_memory(text)
    return text


def run_deferred_post_reply_tasks(
    *,
    shared,
    msg: str,
    history: list,
    response: str,
    route: dict | None,
    l8: list | None,
    forbid_missing_skill_intent: bool = False,
) -> None:
    if shared is None:
        return

    try:
        shared.l2_add_memory(msg, response)
    except Exception as exc:
        try:
            shared.debug_write("post_reply_error", {"stage": "l2_add_memory", "error": str(exc)})
        except Exception:
            pass

    feedback_rule = None
    try:
        feedback_rule = shared.l7_record_feedback_v2(msg, history, None)
    except Exception as exc:
        try:
            shared.debug_write("feedback_rule_error", {"error": str(exc)})
        except Exception:
            pass

    if feedback_rule:
        record_feedback_memory_hit(feedback_rule)
        awareness_evt = build_feedback_awareness_event(feedback_rule)
        if awareness_evt:
            try:
                shared.awareness_push(awareness_evt)
            except Exception as exc:
                try:
                    shared.debug_write("post_reply_error", {"stage": "awareness", "error": str(exc)})
                except Exception:
                    pass

    try:
        shared.l8_touch()
        l8_config = shared.load_autolearn_config()
        if should_schedule_autolearn(
            l8_config,
            feedback_rule=feedback_rule,
            l8=l8,
            route=route,
            forbid_missing_skill_intent=forbid_missing_skill_intent,
        ):
            shared.run_l8_autolearn_task(msg, response, route, bool(l8))
    except Exception as exc:
        try:
            shared.debug_write("post_reply_error", {"stage": "l8", "error": str(exc)})
        except Exception:
            pass

    repair_payload = build_repair_payload(route, feedback_rule)
    try:
        shared.debug_write("final_response", {"reply": response, "repair": repair_payload})
    except Exception:
        pass

