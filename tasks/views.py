"""Task-plan projections and working-state views."""


_BLOCKED_RUNTIME_STATUSES = {"blocked", "waiting_user"}


def _snapshot_verification(snapshot: dict) -> dict:
    return snapshot.get("verification") if isinstance(snapshot.get("verification"), dict) else {}


def _verification_status(snapshot: dict) -> str:
    verification = _snapshot_verification(snapshot)
    status = str(verification.get("status") or "").strip().lower()
    if status:
        return status
    verified = verification.get("verified")
    if verified is True:
        return "verified"
    if verified is False:
        return "failed"
    return ""


def find_matching_task_plan_task(
    user_input: str = "",
    preferred_fs_target: str = "",
    *,
    all_task_plan_tasks,
    extract_task_fs_target,
    extract_explicit_query_paths,
    get_structured_fs_target_for_task_plan,
    task_matches_query_paths,
    normalize_query_path,
    has_task_fs_target,
    looks_like_task_plan_continuation,
    looks_like_direct_task_resume_command,
    query_clearly_refers_to_active_task,
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
    plan = latest.get("plan") if isinstance(latest.get("plan"), dict) else {}
    snapshot = plan.get("snapshot") if isinstance(plan.get("snapshot"), dict) else plan
    goal = str(
        (snapshot.get("goal") if isinstance(snapshot, dict) else "")
        or (latest.get("input") or {}).get("query")
        or latest.get("title")
        or ""
    ).strip()
    current_item_id = str((snapshot.get("current_item_id") if isinstance(snapshot, dict) else "") or "").strip()
    current_step = ""
    current_step_status = ""
    current_step_detail = ""
    items = snapshot.get("items") if isinstance(snapshot.get("items"), list) else []
    if current_item_id and items:
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("id") or "").strip() == current_item_id:
                current_step = str(item.get("title") or "").strip()
                current_step_status = str(item.get("status") or "").strip()
                current_step_detail = str(item.get("detail") or "").strip()
                if current_step:
                    break
    last_done = _last_done_plan_item(items, current_item_id=current_item_id)
    recent_progress = str(last_done.get("title") or "").strip()
    latest_event = {}
    events = latest.get("events") if isinstance(latest.get("events"), list) else []
    for event in reversed(events):
        if isinstance(event, dict):
            latest_event = event
            break
    latest_event_summary = str(latest_event.get("summary") or "").strip()
    phase = str((snapshot.get("phase") if isinstance(snapshot, dict) else "") or latest.get("stage") or "").strip()
    runtime_status = str((snapshot.get("runtime_status") if isinstance(snapshot, dict) else "") or "").strip()
    next_action = str((snapshot.get("next_action") if isinstance(snapshot, dict) else "") or "").strip()
    verification_status = _verification_status(snapshot if isinstance(snapshot, dict) else {})
    verification_detail = str(
        (_snapshot_verification(snapshot).get("detail") if isinstance(snapshot, dict) else "") or ""
    ).strip()
    blocker = ""
    task_fs_target = ""
    task_target = extract_task_fs_target(latest) if callable(extract_task_fs_target) else None
    if isinstance(task_target, dict):
        task_fs_target = str(task_target.get("path") or "").strip()
    if not task_fs_target and callable(get_structured_fs_target_for_task_plan):
        inferred_target = get_structured_fs_target_for_task_plan(snapshot)
        if isinstance(inferred_target, dict):
            task_fs_target = str(inferred_target.get("path") or "").strip()
    if phase == "blocked" or runtime_status in _BLOCKED_RUNTIME_STATUSES or str(latest.get("status") or "").strip() == "blocked" or current_step_status in {
        "blocked",
        "error",
        "failed",
        "waiting_user",
    }:
        blocker = current_step_detail or str(
            (snapshot.get("blocker") if isinstance(snapshot, dict) else "") or ""
        ).strip() or verification_detail or latest_event_summary or str(
            (snapshot.get("summary") if isinstance(snapshot, dict) else "") or ""
        ).strip()

    if query_clearly_refers_to_active_task(
        raw,
        last_ref=last_ref,
        goal=goal,
        current_step=current_step,
        current_step_status=current_step_status,
        recent_progress=recent_progress,
        blocker=blocker,
        fs_target=task_fs_target or prefer_by_fs_target,
        phase=phase,
        task_status=str(latest.get("status") or ""),
        latest_event_summary=latest_event_summary,
        runtime_status=runtime_status,
        next_action=next_action,
        verification_status=verification_status,
        verification_detail=verification_detail,
    ):
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
    runtime_status = str(snapshot.get("runtime_status") or "").strip().lower()
    next_action = str(snapshot.get("next_action") or "").strip().lower()
    verification = _snapshot_verification(snapshot)
    verification_status = _verification_status(snapshot)
    verification_detail = str(verification.get("detail") or "").strip()
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
    if phase == "blocked" or runtime_status in _BLOCKED_RUNTIME_STATUSES or str(task.get("status") or "").strip() == "blocked" or current_step_status in {
        "blocked",
        "error",
        "failed",
        "waiting_user",
    }:
        blocker = (
            str(current_item.get("detail") or "").strip()
            or str(snapshot.get("blocker") or "").strip()
            or verification_detail
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
        "runtime_status": runtime_status,
        "next_action": next_action,
        "verification_status": verification_status,
        "verification_detail": verification_detail,
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
    infer_task_query_mode,
) -> dict | None:
    task = find_matching_task_plan_task(user_input, preferred_fs_target=preferred_fs_target)
    state = task_to_working_state(task)
    if not isinstance(state, dict) or not state:
        return state
    query_mode = infer_task_query_mode(
        user_input,
        goal=str(state.get("goal") or "").strip(),
        current_step=str(state.get("current_step") or "").strip(),
        current_step_status=str(state.get("current_step_status") or "").strip(),
        recent_progress=str(state.get("recent_progress") or "").strip(),
        blocker=str(state.get("blocker") or "").strip(),
        fs_target=str(state.get("fs_target") or "").strip(),
        phase=str(state.get("phase") or "").strip(),
        task_status=str(state.get("task_status") or "").strip(),
        latest_event_summary=str(
            ((state.get("latest_event") if isinstance(state.get("latest_event"), dict) else {}) or {}).get("summary") or ""
        ).strip(),
        runtime_status=str(state.get("runtime_status") or "").strip(),
        next_action=str(state.get("next_action") or "").strip(),
        verification_status=str(state.get("verification_status") or "").strip(),
        verification_detail=str(state.get("verification_detail") or "").strip(),
    )
    updated = dict(state)
    updated["query_mode"] = query_mode
    return updated
