from __future__ import annotations

import core.task_store as _task_store

DELIVERY_STEP_ORDER = (
    "clarify_spec",
    "choose_approach",
    "build_artifact",
    "verify_delivery",
)

DEFAULT_STEP_TITLES = {
    "clarify_spec": "明确目标和约束",
    "choose_approach": "选定骨架和实现路径",
    "build_artifact": "生成或修改交付物",
    "verify_delivery": "验证并交付结果",
}


def _normalize_goal(goal: str) -> str:
    return str(goal or "").strip()


def _normalize_step_titles(titles: dict | None = None) -> dict:
    custom = titles if isinstance(titles, dict) else {}
    normalized = dict(DEFAULT_STEP_TITLES)
    for step_id in DELIVERY_STEP_ORDER:
        title = str(custom.get(step_id) or "").strip()
        if title:
            normalized[step_id] = title
    return normalized


def _normalize_step_set(values) -> set[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple, set)):
        return set()
    return {
        str(item or "").strip()
        for item in values
        if str(item or "").strip() in DELIVERY_STEP_ORDER
    }


def _normalize_step_details(step_details: dict | None = None) -> dict:
    raw = step_details if isinstance(step_details, dict) else {}
    normalized = {}
    for step_id in DELIVERY_STEP_ORDER:
        detail = str(raw.get(step_id) or "").strip()
        if detail:
            normalized[step_id] = detail
    return normalized


def build_delivery_task_plan(
    goal: str,
    *,
    titles: dict | None = None,
    summary: str = "",
    current_step: str = "",
    completed_steps=None,
    waiting_step: str = "",
    blocked_step: str = "",
    step_details: dict | None = None,
    phase: str = "",
) -> dict:
    plan_goal = _normalize_goal(goal)
    step_titles = _normalize_step_titles(titles)
    done_steps = _normalize_step_set(completed_steps)
    details = _normalize_step_details(step_details)
    current = str(current_step or "").strip()
    waiting = str(waiting_step or "").strip()
    blocked = str(blocked_step or "").strip()
    explicit_phase = str(phase or "").strip()

    items = []
    for step_id in DELIVERY_STEP_ORDER:
        status = "done" if step_id in done_steps else "pending"
        # The shared task-plan normalizer always expects a running item.
        # For user-choice pauses, keep the current step running and surface
        # the wait in summary/detail instead of inventing a parallel state model.
        if waiting and step_id == waiting and step_id not in done_steps:
            status = "running"
        elif blocked and step_id == blocked and step_id not in done_steps:
            status = "blocked"
        elif current and step_id == current and step_id not in done_steps and not waiting and not blocked:
            status = "running"
        items.append(
            {
                "id": step_id,
                "title": step_titles[step_id],
                "status": status,
                "kind": "phase",
                "detail": details.get(step_id, ""),
            }
        )

    if explicit_phase == "done":
        for item in items:
            item["status"] = "done"
    elif not waiting and not blocked and not any(item.get("status") == "running" for item in items):
        for item in items:
            if item.get("status") == "pending":
                item["status"] = "running"
                current = str(item.get("id") or "").strip()
                break

    current_item_id = ""
    if explicit_phase == "done":
        current_item_id = str(items[-1].get("id") or "").strip() if items else ""
    elif waiting:
        current_item_id = waiting
    elif blocked:
        current_item_id = blocked
    elif current and current in DELIVERY_STEP_ORDER:
        current_item_id = current
    else:
        for item in items:
            if str(item.get("status") or "").strip() == "running":
                current_item_id = str(item.get("id") or "").strip()
                break

    plan_phase = explicit_phase
    if not plan_phase:
        if blocked:
            plan_phase = "blocked"
        elif waiting:
            plan_phase = waiting
        elif items and all(str(item.get("status") or "").strip() == "done" for item in items):
            plan_phase = "done"
        elif current_item_id:
            plan_phase = current_item_id

    return _task_store.normalize_task_plan_snapshot(
        {
            "goal": plan_goal,
            "summary": str(summary or "").strip(),
            "phase": plan_phase,
            "items": items,
            "current_item_id": current_item_id,
        },
        goal=plan_goal,
    )


def save_delivery_task_plan(
    goal: str,
    *,
    source: str = "delivery_protocol",
    **kwargs,
) -> tuple[dict | None, dict]:
    plan = build_delivery_task_plan(goal, **kwargs)
    try:
        task, saved_plan = _task_store.save_task_plan_snapshot(goal, plan, source=source)
        return task, saved_plan if isinstance(saved_plan, dict) else plan
    except Exception:
        return None, plan
