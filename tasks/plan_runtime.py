"""Task-plan runtime normalization and persistence support."""

from datetime import datetime
from pathlib import Path
import re


def _slugify_plan_item(text: str, fallback: str) -> str:
    raw = str(text or "").strip().lower()
    raw = re.sub(r"[^a-z0-9]+", "_", raw)
    raw = raw.strip("_")
    return raw[:48] or fallback


def _default_plan_items(goal: str) -> list[dict]:
    raw = str(goal or "").strip()
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", raw))
    if has_cjk:
        titles = [
            "梳理目标和约束",
            "收集当前上下文",
            "执行主要工作",
            "验证结果",
            "整理最终交付",
        ]
    else:
        titles = [
            "Clarify the goal and constraints",
            "Gather the current context",
            "Execute the main work",
            "Verify the result",
            "Deliver the outcome",
        ]
    items = []
    for idx, title in enumerate(titles):
        items.append(
            {
                "id": _slugify_plan_item(title, f"step_{idx + 1}"),
                "title": title,
                "status": "running" if idx == 0 else "pending",
                "kind": "phase",
                "detail": "",
            }
        )
    return items


def normalize_plan_item_status(status: str, *, plan_item_status: set[str], fallback: str = "pending") -> str:
    raw = str(status or "").strip().lower()
    aliases = {
        "planned": "pending",
        "queued": "pending",
        "todo": "pending",
        "active": "running",
        "in_progress": "running",
        "in-progress": "running",
        "working": "running",
        "completed": "done",
        "complete": "done",
        "success": "done",
        "waiting": "waiting_user",
    }
    normalized = aliases.get(raw, raw or fallback)
    return normalized if normalized in plan_item_status else fallback


def _normalize_plan_items(items, *, goal: str, plan_item_status: set[str]) -> list[dict]:
    rows = []
    raw_items = items if isinstance(items, list) and items else _default_plan_items(goal)
    seen_ids = set()
    running_seen = False
    for idx, item in enumerate(raw_items):
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("label") or "").strip()
            detail = str(item.get("detail") or item.get("summary") or "").strip()
            status = normalize_plan_item_status(item.get("status"), plan_item_status=plan_item_status, fallback="pending")
            kind = str(item.get("kind") or "phase").strip() or "phase"
            item_id = str(item.get("id") or "").strip()
        else:
            title = str(item or "").strip()
            detail = ""
            status = "pending"
            kind = "phase"
            item_id = ""
        if not title:
            continue
        if not item_id:
            item_id = _slugify_plan_item(title, f"step_{idx + 1}")
        if item_id in seen_ids:
            item_id = f"{item_id}_{idx + 1}"
        seen_ids.add(item_id)
        if status == "running":
            if running_seen:
                status = "pending"
            else:
                running_seen = True
        rows.append(
            {
                "id": item_id,
                "title": title,
                "status": status,
                "kind": kind,
                "detail": detail,
            }
        )
    if not rows:
        rows = _default_plan_items(goal)
    if not any(item.get("status") == "running" for item in rows):
        if any(item.get("status") == "pending" for item in rows):
            for item in rows:
                if item.get("status") == "pending":
                    item["status"] = "running"
                    break
    return rows


def _normalize_verification_payload(data: dict | None) -> dict:
    payload = data if isinstance(data, dict) else {}
    verified = payload.get("verified")
    status = str(payload.get("status") or "").strip().lower()
    detail = str(payload.get("detail") or payload.get("verification_detail") or "").strip()
    observed_state = str(payload.get("observed_state") or "").strip()
    verification_mode = str(payload.get("verification_mode") or "").strip()

    if not status:
        if verified is True:
            status = "verified"
        elif verified is False:
            status = "failed"

    normalized = {}
    if verified in {True, False}:
        normalized["verified"] = bool(verified)
    if status:
        normalized["status"] = status
    if detail:
        normalized["detail"] = detail
    if observed_state:
        normalized["observed_state"] = observed_state
    if verification_mode:
        normalized["verification_mode"] = verification_mode
    return normalized


def normalize_task_plan_snapshot(
    plan: dict | None,
    *,
    goal: str = "",
    plan_item_status: set[str],
    now_iso,
) -> dict:
    data = plan if isinstance(plan, dict) else {}
    plan_goal = str(data.get("goal") or goal or "").strip()
    items = _normalize_plan_items(data.get("items") or data.get("steps"), goal=plan_goal, plan_item_status=plan_item_status)
    explicit_current = str(data.get("current_item_id") or "").strip()
    current_item_id = ""
    if explicit_current and any(item.get("id") == explicit_current for item in items):
        current_item_id = explicit_current
    if not current_item_id:
        for item in items:
            if item.get("status") == "running":
                current_item_id = str(item.get("id") or "").strip()
                break
    if not current_item_id:
        for item in items:
            if item.get("status") == "pending":
                current_item_id = str(item.get("id") or "").strip()
                break
    if not current_item_id and items:
        current_item_id = str(items[-1].get("id") or "").strip()

    phase = str(data.get("phase") or "").strip()
    current_item = next((item for item in items if str(item.get("id") or "") == current_item_id), {})
    if not phase:
        if items and all(item.get("status") == "done" for item in items):
            phase = "done"
        elif not any(item.get("status") in {"pending", "running"} for item in items) and any(
            item.get("status") in {"blocked", "error", "failed", "waiting_user"} for item in items
        ):
            phase = "blocked"
        else:
            phase = str(current_item.get("id") or "planning").strip()

    summary = str(data.get("summary") or "").strip()
    if not summary:
        current_title = str(current_item.get("title") or "").strip()
        if phase == "done":
            summary = "任务计划已完成" if re.search(r"[\u4e00-\u9fff]", plan_goal) else "The plan is complete."
        elif phase == "blocked":
            blocked_detail = str(current_item.get("detail") or "").strip()
            summary = blocked_detail or (
                f"当前卡在：{current_title}" if re.search(r"[\u4e00-\u9fff]", plan_goal) else f"Blocked on: {current_title}"
            )
        elif current_title:
            summary = (
                f"正在推进：{current_title}" if re.search(r"[\u4e00-\u9fff]", plan_goal) else f"Working on: {current_title}"
            )
        else:
            summary = "正在推进任务" if re.search(r"[\u4e00-\u9fff]", plan_goal) else "Working through the task."

    normalized = {
        "goal": plan_goal,
        "mode": "multi_step",
        "phase": phase,
        "summary": summary,
        "items": items,
        "current_item_id": current_item_id,
        "updated_at": str(data.get("updated_at") or now_iso()),
    }
    runtime_status = str(data.get("runtime_status") or "").strip().lower()
    next_action = str(data.get("next_action") or "").strip().lower()
    blocker = str(data.get("blocker") or "").strip()
    verification = _normalize_verification_payload(data.get("verification"))
    if runtime_status:
        normalized["runtime_status"] = runtime_status
    if next_action:
        normalized["next_action"] = next_action
    if blocker:
        normalized["blocker"] = blocker
    if verification:
        normalized["verification"] = verification
    return normalized


def task_status_from_plan(plan: dict) -> str:
    items = plan.get("items") if isinstance(plan.get("items"), list) else []
    phase = str(plan.get("phase") or "").strip()
    if phase == "done" or (items and all(item.get("status") == "done" for item in items)):
        return "completed"
    if phase == "cancelled" or any(item.get("status") == "cancelled" for item in items):
        return "cancelled"
    if phase == "blocked" or any(item.get("status") in {"blocked", "error", "failed", "waiting_user"} for item in items):
        return "blocked"
    if any(item.get("status") == "running" for item in items):
        return "active"
    return "planned"


def task_stage_from_plan(plan: dict) -> str:
    phase = str(plan.get("phase") or "").strip()
    if phase:
        return phase[:80]
    current_item_id = str(plan.get("current_item_id") or "").strip()
    return current_item_id[:80]


def get_or_create_task_plan_project(
    *,
    load_task_projects,
    normalize_project,
    create_project,
    plan_project_title: str,
):
    projects = load_task_projects()
    for item in projects:
        if isinstance(item, dict) and item.get("kind") == "generic" and item.get("title") == plan_project_title:
            return normalize_project(item)
    return create_project(
        "generic",
        plan_project_title,
        status="active",
        goal={"summary": "持续推进多步任务计划"},
        memory={"tags": ["task_plan"]},
    )


def task_plan_item_to_status(item_status: str, *, normalize_plan_item_status) -> str:
    status = normalize_plan_item_status(item_status, fallback="pending")
    mapping = {
        "pending": "planned",
        "running": "active",
        "done": "completed",
        "blocked": "blocked",
        "error": "failed",
        "failed": "failed",
        "waiting_user": "waiting",
        "cancelled": "cancelled",
    }
    return mapping.get(status, "planned")


def sync_task_plan_children(
    parent_task: dict,
    plan: dict,
    *,
    get_child_tasks,
    load_task_relations,
    update_task,
    create_task,
    create_relation,
    task_plan_item_to_status,
):
    parent_id = str(parent_task.get("id") or "").strip()
    if not parent_id:
        return
    existing_children = [task for task in get_child_tasks(parent_id) if task.get("kind") == "plan_step"]
    by_item_id = {}
    for child in existing_children:
        memory = child.get("memory") if isinstance(child.get("memory"), dict) else {}
        plan_item_id = str(memory.get("plan_item_id") or "").strip()
        if plan_item_id:
            by_item_id[plan_item_id] = child
    relation_keys = {
        (rel.get("from_id"), rel.get("to_id"), rel.get("type"))
        for rel in load_task_relations()
        if isinstance(rel, dict)
    }
    for index, item in enumerate(plan.get("items") or [], 1):
        item_id = str(item.get("id") or "").strip()
        child = by_item_id.get(item_id)
        patch = {
            "title": str(item.get("title") or "").strip(),
            "status": task_plan_item_to_status(item.get("status")),
            "stage": str(item.get("status") or "").strip(),
            "context": {"detail": str(item.get("detail") or "").strip()},
            "memory": {"plan_item_id": item_id},
            "domain": {"task_plan_item": {"item_id": item_id, "kind": str(item.get("kind") or "phase").strip() or "phase"}},
        }
        if child:
            update_task(child.get("id"), patch)
        else:
            child = create_task(
                "plan_step",
                patch["title"],
                project_id=parent_task.get("project_id"),
                parent_task_id=parent_id,
                status=patch["status"],
                stage=patch["stage"],
                context=patch["context"],
                memory=patch["memory"],
                domain=patch["domain"],
                events=[],
            )
        rel_key = (parent_id, child.get("id"), "parent_of")
        if rel_key not in relation_keys:
            create_relation(parent_id, child.get("id"), "parent_of", index=index, plan_item_id=item_id)
            relation_keys.add(rel_key)


def save_task_plan_snapshot(
    user_input: str,
    snapshot: dict,
    *,
    normalize_task_plan_snapshot,
    get_or_create_task_plan_project,
    find_matching_task_plan_task,
    task_status_from_plan,
    task_stage_from_plan,
    plan_goal_key,
    now_iso,
    update_task,
    create_task,
    append_task_event,
    update_project,
    sync_task_plan_children,
    get_task,
    task_to_plan_snapshot,
    source: str = "task_plan",
):
    normalized = normalize_task_plan_snapshot(snapshot, goal=user_input)
    project = get_or_create_task_plan_project()
    task = find_matching_task_plan_task(user_input)
    goal = str(normalized.get("goal") or user_input or "task plan").strip()
    patch = {
        "title": goal[:80] or "task plan",
        "status": task_status_from_plan(normalized),
        "stage": task_stage_from_plan(normalized),
        "intent": {"source": source, "summary": goal},
        "input": {"query": goal},
        "plan": {"snapshot": normalized},
        "result": {"summary": str(normalized.get("summary") or "").strip()},
        "memory": {
            "last_user_reference": str(user_input or goal).strip(),
            "resume_tokens": ["继续", "接着", "然后", "continue", "resume"],
            "last_active_at": now_iso(),
        },
        "domain": {"task_plan": {"enabled": True, "source": source, "goal_key": plan_goal_key(goal)}},
    }
    if task:
        if patch["status"] == "completed" and not task.get("completed_at"):
            patch["completed_at"] = now_iso()
        task = update_task(task.get("id"), patch) or task
    else:
        started_at = now_iso() if patch["status"] in {"active", "blocked"} else None
        completed_at = now_iso() if patch["status"] == "completed" else None
        task = create_task(
            "generic",
            patch["title"],
            project_id=project.get("id"),
            status=patch["status"],
            stage=patch["stage"],
            started_at=started_at,
            completed_at=completed_at,
            intent=patch["intent"],
            input=patch["input"],
            plan=patch["plan"],
            result=patch["result"],
            memory=patch["memory"],
            domain=patch["domain"],
            events=[],
        )
        append_task_event(task.get("id"), "created", "Task plan created")
    append_task_event(
        task.get("id"),
        "plan_updated",
        str(normalized.get("summary") or goal)[:160],
        phase=str(normalized.get("phase") or "").strip(),
        current_item_id=str(normalized.get("current_item_id") or "").strip(),
    )
    update_project(project.get("id"), {"current_task_id": task.get("id")})
    sync_task_plan_children(task, normalized)
    latest = get_task(task.get("id")) or task
    latest_snapshot = task_to_plan_snapshot(latest) or normalized
    return latest, latest_snapshot
