"""Task-plan projections and working-state views."""


def find_matching_task_plan_task(
    user_input: str = "",
    preferred_fs_target: str = "",
    *,
    all_task_plan_tasks,
    extract_explicit_query_paths,
    task_matches_query_paths,
    normalize_query_path,
    has_task_fs_target,
    looks_like_task_plan_continuation,
    looks_like_direct_task_resume_command,
    goal_overlap,
    looks_like_short_referential_followup,
    looks_like_long_referential_followup,
):
    tasks = list(all_task_plan_tasks() or [])
    if not tasks:
        return None

    non_terminal = [task for task in tasks if task.get("status") not in {"completed", "failed", "cancelled", "archived"}]
    if not non_terminal:
        non_terminal = tasks
    non_terminal.sort(key=lambda x: str(x.get("updated_at") or ""))
    latest = non_terminal[-1]

    raw = str(user_input or "").strip()
    if not raw:
        return latest

    query_paths = extract_explicit_query_paths(raw)
    if query_paths:
        for task in reversed(non_terminal):
            if task_matches_query_paths(task, query_paths):
                return task
        return None

    prefer_by_fs_target = normalize_query_path(preferred_fs_target)
    if prefer_by_fs_target:
        matching_tasks = [task for task in reversed(non_terminal) if task_matches_query_paths(task, [prefer_by_fs_target])]
        if matching_tasks:
            return matching_tasks[0]
        if any(has_task_fs_target(task) for task in non_terminal):
            return None

    last_ref = str(
        (latest.get("memory") or {}).get("last_user_reference")
        or (latest.get("input") or {}).get("query")
        or latest.get("title")
        or ""
    ).strip()
    if looks_like_task_plan_continuation(raw):
        if looks_like_direct_task_resume_command(raw):
            return latest
        if last_ref and (last_ref in raw or raw in last_ref or goal_overlap(raw, last_ref) >= 0.2):
            return latest
        return None

    if looks_like_short_referential_followup(raw) or looks_like_long_referential_followup(raw):
        return latest
    if last_ref and (last_ref in raw or raw in last_ref or goal_overlap(raw, last_ref) >= 0.45):
        return latest
    return None


def task_to_plan_snapshot(
    task: dict | None,
    *,
    normalize_task,
    is_task_plan_task,
    normalize_task_plan_snapshot,
) -> dict | None:
    task = normalize_task(task) if isinstance(task, dict) else {}
    if not task or not is_task_plan_task(task):
        return None

    plan = task.get("plan") if isinstance(task.get("plan"), dict) else {}
    snapshot = plan.get("snapshot") if isinstance(plan.get("snapshot"), dict) else plan
    goal = str(
        (snapshot.get("goal") if isinstance(snapshot, dict) else "")
        or (task.get("input") or {}).get("query")
        or task.get("title")
        or ""
    ).strip()
    normalized = normalize_task_plan_snapshot(snapshot if isinstance(snapshot, dict) else {}, goal=goal)
    normalized["task_id"] = str(task.get("id") or "").strip()
    normalized["project_id"] = str(task.get("project_id") or "").strip()
    return normalized


def get_active_task_plan_snapshot(
    user_input: str = "",
    preferred_fs_target: str = "",
    *,
    find_matching_task_plan_task,
    task_to_plan_snapshot,
) -> dict | None:
    task = find_matching_task_plan_task(user_input, preferred_fs_target=preferred_fs_target)
    return task_to_plan_snapshot(task)


def _find_plan_item(items: list[dict], item_id: str) -> dict:
    target = str(item_id or "").strip()
    if not target:
        return {}
    for item in items:
        if isinstance(item, dict) and str(item.get("id") or "").strip() == target:
            return item
    return {}


def _last_done_plan_item(items: list[dict], current_item_id: str = "") -> dict:
    current = str(current_item_id or "").strip()
    for item in reversed(items or []):
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "").strip() != "done":
            continue
        if current and str(item.get("id") or "").strip() == current:
            continue
        return item
    return {}


def task_to_working_state(
    task: dict | None,
    *,
    normalize_task,
    task_to_plan_snapshot,
    extract_task_fs_target,
    get_structured_fs_target_for_task_plan,
) -> dict | None:
    task = normalize_task(task) if isinstance(task, dict) else {}
    if not task:
        return None

    snapshot = task_to_plan_snapshot(task)
    if not snapshot:
        return None

    items = snapshot.get("items") if isinstance(snapshot.get("items"), list) else []
    goal = str(snapshot.get("goal") or (task.get("input") or {}).get("query") or task.get("title") or "").strip()
    phase = str(snapshot.get("phase") or task.get("stage") or "").strip()
    summary = str(snapshot.get("summary") or (task.get("result") or {}).get("summary") or "").strip()
    current_item_id = str(snapshot.get("current_item_id") or "").strip()
    current_item = _find_plan_item(items, current_item_id)
    current_step = str(current_item.get("title") or "").strip()
    current_step_status = str(current_item.get("status") or "").strip()

    last_done = _last_done_plan_item(items, current_item_id=current_item_id)
    last_completed_step = str(last_done.get("title") or "").strip()

    latest_event = {}
    events = task.get("events") if isinstance(task.get("events"), list) else []
    for event in reversed(events):
        if isinstance(event, dict):
            latest_event = event
            break
    latest_event_summary = str(latest_event.get("summary") or "").strip()

    fs_target = extract_task_fs_target(task) or get_structured_fs_target_for_task_plan(snapshot)
    fs_path = str((fs_target or {}).get("path") or "").strip()

    blocker = ""
    if phase == "blocked" or str(task.get("status") or "").strip() == "blocked" or current_step_status in {
        "blocked",
        "error",
        "failed",
        "waiting_user",
    }:
        blocker = (
            str(current_item.get("detail") or "").strip()
            or latest_event_summary
            or summary
            or current_step
        )

    recent_progress = ""
    if last_completed_step:
        recent_progress = last_completed_step
    elif latest_event_summary and str(latest_event.get("type") or "").strip() != "created":
        recent_progress = latest_event_summary

    next_step = ""
    if phase == "done":
        next_step = "Summarize completion and confirm final verification."
    elif current_step:
        next_step = current_step
    else:
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "").strip() in {"running", "pending", "waiting_user"}:
                next_step = str(item.get("title") or "").strip()
                if next_step:
                    break

    return {
        "task_id": str(task.get("id") or "").strip(),
        "project_id": str(task.get("project_id") or "").strip(),
        "goal": goal,
        "summary": summary,
        "phase": phase,
        "task_status": str(task.get("status") or "").strip(),
        "current_item_id": current_item_id,
        "current_step": current_step,
        "current_step_status": current_step_status,
        "last_completed_step": last_completed_step,
        "recent_progress": recent_progress,
        "blocker": blocker,
        "next_step": next_step,
        "fs_target": fs_path,
        "updated_at": str(task.get("updated_at") or snapshot.get("updated_at") or "").strip(),
        "latest_event": {
            "type": str(latest_event.get("type") or "").strip(),
            "summary": latest_event_summary,
            "at": str(latest_event.get("at") or "").strip(),
        },
    }


def get_active_task_working_state(
    user_input: str = "",
    preferred_fs_target: str = "",
    *,
    find_matching_task_plan_task,
    task_to_working_state,
) -> dict | None:
    task = find_matching_task_plan_task(user_input, preferred_fs_target=preferred_fs_target)
    return task_to_working_state(task)
