def _short_text(value, limit: int = 120) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _build_topics(working_state: dict) -> list[str]:
    working_state = working_state if isinstance(working_state, dict) else {}
    goal = _short_text(working_state.get("goal"), 72)
    current_step = _short_text(working_state.get("current_step"), 48)
    topics = []
    if goal:
        topics.append(goal)
    if current_step and current_step != goal:
        topics.append(current_step)
    return topics[:2]


def extract_session_context(history: list, current_input: str = "") -> dict:
    """Build a lightweight session context from the active task substrate."""
    try:
        from core.task_store import get_active_task_working_state

        working_state = get_active_task_working_state(current_input) or {}
    except Exception:
        working_state = {}

    goal = _short_text((working_state or {}).get("goal"), 96)
    current_step = _short_text((working_state or {}).get("current_step"), 96)
    blocker = _short_text((working_state or {}).get("blocker"), 120)
    recent_progress = _short_text((working_state or {}).get("recent_progress"), 120)
    summary = _short_text((working_state or {}).get("summary"), 160)

    intent = ""
    user_state = ""
    session_state = ""
    continuation_hint = ""
    current_focus = current_step or goal
    resume_point = current_step or recent_progress or goal
    if working_state:
        if blocker:
            session_state = "open task context; last attempt blocked"
        elif current_step:
            session_state = "open task context; last step paused"
        else:
            session_state = "open task context available"
        continuation_hint = "continue only if the current user input clearly refers to this task"
        user_state = (
            f"{session_state}; {continuation_hint}"
            if session_state and continuation_hint
            else (session_state or continuation_hint)
        )

    return {
        "topics": _build_topics(working_state),
        "mood": "",
        "intents": [intent] if intent else [],
        "follow_up": {},
        "stage": str((working_state or {}).get("phase") or "").strip(),
        "attitude": "",
        "intent": intent,
        "user_state": user_state,
        "session_state": session_state,
        "continuation_hint": continuation_hint,
        "current_focus": current_focus,
        "resume_point": resume_point,
        "working_state": working_state,
        "working_summary": summary or recent_progress or blocker,
    }
