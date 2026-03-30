from datetime import datetime
import re

from core.state_loader import (
    load_task_projects,
    save_task_projects,
    load_tasks,
    save_tasks,
    load_task_relations,
    save_task_relations,
    load_content_projects,
)

ALLOWED_PROJECT_KINDS = {"content", "development", "experiment", "repair", "file_workflow", "generic"}
ALLOWED_TASK_KINDS = {"content", "plan_step", "experiment", "repair", "development", "file_workflow", "generic"}
ALLOWED_TASK_STATUS = {
    "created", "planned", "active", "blocked", "waiting", "draft_ready",
    "completed", "failed", "cancelled", "archived"
}
ALLOWED_RELATION_TYPES = {"belongs_to_project", "parent_of", "depends_on", "references", "derived_from"}
PLAN_PROJECT_TITLE = "Default task planning pipeline"
PLAN_ITEM_STATUS = {"pending", "running", "done", "blocked", "error", "failed", "waiting_user", "cancelled"}
PLAN_TERMINAL_STATUS = {"done", "blocked", "error", "failed", "waiting_user", "cancelled"}


def _now_iso():
    return datetime.now().isoformat()


def _make_id(prefix: str, seq: int) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d')}_{seq:03d}"


def _ensure_list(value):
    return value if isinstance(value, list) else []


def _normalize_project(obj: dict) -> dict:
    data = obj if isinstance(obj, dict) else {}
    kind = str(data.get("kind") or "generic")
    if kind not in ALLOWED_PROJECT_KINDS:
        kind = "generic"
    return {
        "id": str(data.get("id") or ""),
        "kind": kind,
        "title": str(data.get("title") or data.get("name") or "").strip(),
        "status": str(data.get("status") or "active"),
        "description": str(data.get("description") or ""),
        "owner": str(data.get("owner") or "nova"),
        "created_at": str(data.get("created_at") or _now_iso()),
        "updated_at": str(data.get("updated_at") or _now_iso()),
        "current_task_id": data.get("current_task_id"),
        "goal": data.get("goal") if isinstance(data.get("goal"), dict) else {},
        "settings": data.get("settings") if isinstance(data.get("settings"), dict) else {},
        "memory": data.get("memory") if isinstance(data.get("memory"), dict) else {},
    }


def _normalize_task(obj: dict) -> dict:
    data = obj if isinstance(obj, dict) else {}
    kind = str(data.get("kind") or "generic")
    if kind not in ALLOWED_TASK_KINDS:
        kind = "generic"
    status = str(data.get("status") or "created")
    if status not in ALLOWED_TASK_STATUS:
        status = "created"
    return {
        "id": str(data.get("id") or ""),
        "project_id": data.get("project_id"),
        "parent_task_id": data.get("parent_task_id"),
        "kind": kind,
        "title": str(data.get("title") or "").strip(),
        "status": status,
        "stage": str(data.get("stage") or "").strip(),
        "priority": str(data.get("priority") or "normal"),
        "created_at": str(data.get("created_at") or _now_iso()),
        "updated_at": str(data.get("updated_at") or _now_iso()),
        "started_at": data.get("started_at"),
        "completed_at": data.get("completed_at"),
        "intent": data.get("intent") if isinstance(data.get("intent"), dict) else {},
        "input": data.get("input") if isinstance(data.get("input"), dict) else {},
        "context": data.get("context") if isinstance(data.get("context"), dict) else {},
        "plan": data.get("plan") if isinstance(data.get("plan"), dict) else {},
        "artifacts": data.get("artifacts") if isinstance(data.get("artifacts"), dict) else {},
        "result": data.get("result") if isinstance(data.get("result"), dict) else {},
        "memory": data.get("memory") if isinstance(data.get("memory"), dict) else {},
        "domain": data.get("domain") if isinstance(data.get("domain"), dict) else {},
        "events": _ensure_list(data.get("events")),
    }


def _normalize_relation(obj: dict) -> dict:
    data = obj if isinstance(obj, dict) else {}
    rel_type = str(data.get("type") or "references")
    if rel_type not in ALLOWED_RELATION_TYPES:
        rel_type = "references"
    return {
        "id": str(data.get("id") or ""),
        "from_id": str(data.get("from_id") or ""),
        "to_id": str(data.get("to_id") or ""),
        "type": rel_type,
        "created_at": str(data.get("created_at") or _now_iso()),
        "meta": data.get("meta") if isinstance(data.get("meta"), dict) else {},
    }


def load_all_task_data():
    projects = [_normalize_project(x) for x in load_task_projects() if isinstance(x, dict)]
    tasks = [_normalize_task(x) for x in load_tasks() if isinstance(x, dict)]
    relations = [_normalize_relation(x) for x in load_task_relations() if isinstance(x, dict)]
    return projects, tasks, relations


def save_all_task_data(projects, tasks, relations):
    save_task_projects([_normalize_project(x) for x in (projects or [])])
    save_tasks([_normalize_task(x) for x in (tasks or [])])
    save_task_relations([_normalize_relation(x) for x in (relations or [])])


def create_project(kind: str, title: str, **extra):
    projects = load_task_projects()
    project = _normalize_project({
        "id": _make_id("proj", len(projects) + 1),
        "kind": kind,
        "title": title,
        "status": extra.get("status") or "active",
        "description": extra.get("description") or "",
        "owner": extra.get("owner") or "nova",
        "goal": extra.get("goal") or {},
        "settings": extra.get("settings") or {},
        "memory": extra.get("memory") or {},
    })
    projects.append(project)
    save_task_projects(projects)
    return project


def create_task(kind: str, title: str, **extra):
    tasks = load_tasks()
    task = _normalize_task({
        "id": _make_id("task", len(tasks) + 1),
        "kind": kind,
        "title": title,
        "project_id": extra.get("project_id"),
        "parent_task_id": extra.get("parent_task_id"),
        "status": extra.get("status") or "created",
        "stage": extra.get("stage") or "",
        "priority": extra.get("priority") or "normal",
        "started_at": extra.get("started_at"),
        "completed_at": extra.get("completed_at"),
        "intent": extra.get("intent") or {},
        "input": extra.get("input") or {},
        "context": extra.get("context") or {},
        "plan": extra.get("plan") or {},
        "artifacts": extra.get("artifacts") or {},
        "result": extra.get("result") or {},
        "memory": extra.get("memory") or {},
        "domain": extra.get("domain") or {},
        "events": extra.get("events") or [],
    })
    tasks.append(task)
    save_tasks(tasks)
    return task


def update_project(project_id: str, patch: dict):
    projects = load_task_projects()
    updated = None
    for idx, item in enumerate(projects):
        if isinstance(item, dict) and item.get("id") == project_id:
            merged = dict(item)
            merged.update(patch or {})
            merged["updated_at"] = _now_iso()
            projects[idx] = _normalize_project(merged)
            updated = projects[idx]
            break
    if updated is not None:
        save_task_projects(projects)
    return updated


def update_task(task_id: str, patch: dict):
    tasks = load_tasks()
    updated = None
    for idx, item in enumerate(tasks):
        if isinstance(item, dict) and item.get("id") == task_id:
            merged = dict(item)
            merged.update(patch or {})
            merged["updated_at"] = _now_iso()
            tasks[idx] = _normalize_task(merged)
            updated = tasks[idx]
            break
    if updated is not None:
        save_tasks(tasks)
    return updated


def append_task_event(task_id: str, event_type: str, summary: str, **extra):
    tasks = load_tasks()
    updated = None
    for idx, item in enumerate(tasks):
        if isinstance(item, dict) and item.get("id") == task_id:
            merged = dict(item)
            events = _ensure_list(merged.get("events"))
            row = {"type": event_type, "at": _now_iso(), "summary": summary}
            row.update(extra or {})
            events.append(row)
            merged["events"] = events
            merged["updated_at"] = _now_iso()
            tasks[idx] = _normalize_task(merged)
            updated = tasks[idx]
            break
    if updated is not None:
        save_tasks(tasks)
    return updated


def create_relation(from_id: str, to_id: str, rel_type: str, **meta):
    relations = load_task_relations()
    relation = _normalize_relation({
        "id": _make_id("rel", len(relations) + 1),
        "from_id": from_id,
        "to_id": to_id,
        "type": rel_type,
        "meta": meta or {},
    })
    relations.append(relation)
    save_task_relations(relations)
    return relation


def get_project(project_id: str):
    for item in load_task_projects():
        if isinstance(item, dict) and item.get("id") == project_id:
            return _normalize_project(item)
    return None


def get_task(task_id: str):
    for item in load_tasks():
        if isinstance(item, dict) and item.get("id") == task_id:
            return _normalize_task(item)
    return None


def get_project_tasks(project_id: str):
    return [_normalize_task(x) for x in load_tasks() if isinstance(x, dict) and x.get("project_id") == project_id]


def get_tasks_by_kind(kind: str):
    return [_normalize_task(x) for x in load_tasks() if isinstance(x, dict) and x.get("kind") == kind]


def get_latest_active_task_by_kind(kind: str):
    tasks = get_tasks_by_kind(kind)
    non_terminal = [t for t in tasks if t.get("status") not in {"completed", "failed", "cancelled", "archived"}]
    if not non_terminal:
        return tasks[-1] if tasks else None
    non_terminal.sort(key=lambda x: str(x.get("updated_at") or ""))
    return non_terminal[-1]


def resolve_task_for_goal(kind: str, user_input: str):
    raw = str(user_input or "").strip()
    active = get_latest_active_task_by_kind(kind)
    if not active:
        return None
    if any(w in raw for w in ("继续", "接着", "然后", "这个项目", "这个任务", "换个题", "换题", "初稿", "处理", "修复", "开始")):
        return active
    mem = active.get("memory") or {}
    last_ref = str(mem.get("last_user_reference") or "").strip()
    if last_ref and last_ref[:10] and last_ref[:10] in raw:
        return active
    return None


def get_child_tasks(parent_task_id: str):
    return [_normalize_task(x) for x in load_tasks() if isinstance(x, dict) and x.get("parent_task_id") == parent_task_id]


def get_task_relations_for(task_id: str):
    rels = load_task_relations()
    return [_normalize_relation(x) for x in rels if isinstance(x, dict) and (x.get("from_id") == task_id or x.get("to_id") == task_id)]


def get_active_task_for_project(project_id: str):
    tasks = get_project_tasks(project_id)
    non_terminal = [t for t in tasks if t.get("status") not in {"completed", "failed", "cancelled", "archived"}]
    if not non_terminal:
        return tasks[-1] if tasks else None
    non_terminal.sort(key=lambda x: str(x.get("updated_at") or ""))
    return non_terminal[-1]


def _is_task_plan_task(task: dict) -> bool:
    task = task if isinstance(task, dict) else {}
    domain = task.get("domain") if isinstance(task.get("domain"), dict) else {}
    task_plan = domain.get("task_plan") if isinstance(domain.get("task_plan"), dict) else {}
    return bool(task_plan.get("enabled"))


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


def _normalize_plan_item_status(status: str, fallback: str = "pending") -> str:
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
    return normalized if normalized in PLAN_ITEM_STATUS else fallback


def _normalize_plan_items(items, goal: str = "") -> list[dict]:
    rows = []
    raw_items = items if isinstance(items, list) and items else _default_plan_items(goal)
    seen_ids = set()
    running_seen = False
    for idx, item in enumerate(raw_items):
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("label") or "").strip()
            detail = str(item.get("detail") or item.get("summary") or "").strip()
            status = _normalize_plan_item_status(item.get("status"), "pending")
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


def normalize_task_plan_snapshot(plan: dict | None, *, goal: str = "") -> dict:
    data = plan if isinstance(plan, dict) else {}
    plan_goal = str(data.get("goal") or goal or "").strip()
    items = _normalize_plan_items(data.get("items") or data.get("steps"), plan_goal)
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

    return {
        "goal": plan_goal,
        "mode": "multi_step",
        "phase": phase,
        "summary": summary,
        "items": items,
        "current_item_id": current_item_id,
        "updated_at": str(data.get("updated_at") or _now_iso()),
    }


def _task_status_from_plan(plan: dict) -> str:
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


def _task_stage_from_plan(plan: dict) -> str:
    phase = str(plan.get("phase") or "").strip()
    if phase:
        return phase[:80]
    current_item_id = str(plan.get("current_item_id") or "").strip()
    return current_item_id[:80]


def _plan_goal_key(text: str) -> str:
    raw = str(text or "").strip().lower()
    raw = re.sub(r"[\W_]+", " ", raw, flags=re.UNICODE)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw[:120]


def _looks_like_task_plan_continuation(query: str) -> bool:
    raw = str(query or "").strip().lower()
    if not raw:
        return False
    markers = (
        "continue",
        "resume",
        "follow up",
        "next",
        "keep going",
        "carry on",
        "继续",
        "接着",
        "然后",
        "这个任务",
        "这个项目",
        "接下来",
        "往下",
    )
    return any(marker in raw for marker in markers)


def _goal_overlap(a: str, b: str) -> float:
    a_key = _plan_goal_key(a)
    b_key = _plan_goal_key(b)
    if not a_key or not b_key:
        return 0.0
    a_tokens = {token for token in a_key.split(" ") if token}
    b_tokens = {token for token in b_key.split(" ") if token}
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = a_tokens & b_tokens
    return len(overlap) / max(len(a_tokens), len(b_tokens), 1)


def _get_or_create_task_plan_project():
    projects = load_task_projects()
    for item in projects:
        if isinstance(item, dict) and item.get("kind") == "generic" and item.get("title") == PLAN_PROJECT_TITLE:
            return _normalize_project(item)
    return create_project(
        "generic",
        PLAN_PROJECT_TITLE,
        status="active",
        goal={"summary": "持续推进多步任务计划"},
        memory={"tags": ["task_plan"]},
    )


def _all_task_plan_tasks() -> list[dict]:
    tasks = [_normalize_task(x) for x in load_tasks() if isinstance(x, dict)]
    return [task for task in tasks if _is_task_plan_task(task)]


def _find_matching_task_plan_task(user_input: str = ""):
    tasks = _all_task_plan_tasks()
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
    if _looks_like_task_plan_continuation(raw):
        return latest
    last_ref = str((latest.get("memory") or {}).get("last_user_reference") or (latest.get("input") or {}).get("query") or latest.get("title") or "").strip()
    if last_ref and (last_ref in raw or raw in last_ref or _goal_overlap(raw, last_ref) >= 0.45):
        return latest
    return None


def task_to_plan_snapshot(task: dict | None) -> dict | None:
    task = _normalize_task(task) if isinstance(task, dict) else {}
    if not task or not _is_task_plan_task(task):
        return None
    plan = task.get("plan") if isinstance(task.get("plan"), dict) else {}
    snapshot = plan.get("snapshot") if isinstance(plan.get("snapshot"), dict) else plan
    goal = str((snapshot.get("goal") if isinstance(snapshot, dict) else "") or (task.get("input") or {}).get("query") or task.get("title") or "").strip()
    normalized = normalize_task_plan_snapshot(snapshot if isinstance(snapshot, dict) else {}, goal=goal)
    normalized["task_id"] = str(task.get("id") or "").strip()
    normalized["project_id"] = str(task.get("project_id") or "").strip()
    return normalized


def get_active_task_plan_snapshot(user_input: str = "") -> dict | None:
    task = _find_matching_task_plan_task(user_input)
    return task_to_plan_snapshot(task)


def _task_plan_item_to_status(item_status: str) -> str:
    status = _normalize_plan_item_status(item_status, "pending")
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


def _sync_task_plan_children(parent_task: dict, plan: dict):
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
            "status": _task_plan_item_to_status(item.get("status")),
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


def save_task_plan_snapshot(user_input: str, snapshot: dict, *, source: str = "task_plan"):
    normalized = normalize_task_plan_snapshot(snapshot, goal=user_input)
    project = _get_or_create_task_plan_project()
    task = _find_matching_task_plan_task(user_input)
    goal = str(normalized.get("goal") or user_input or "task plan").strip()
    patch = {
        "title": goal[:80] or "task plan",
        "status": _task_status_from_plan(normalized),
        "stage": _task_stage_from_plan(normalized),
        "intent": {"source": source, "summary": goal},
        "input": {"query": goal},
        "plan": {"snapshot": normalized},
        "result": {"summary": str(normalized.get("summary") or "").strip()},
        "memory": {
            "last_user_reference": str(user_input or goal).strip(),
            "resume_tokens": ["继续", "接着", "然后", "continue", "resume"],
            "last_active_at": _now_iso(),
        },
        "domain": {"task_plan": {"enabled": True, "source": source, "goal_key": _plan_goal_key(goal)}},
    }
    if task:
        if patch["status"] == "completed" and not task.get("completed_at"):
            patch["completed_at"] = _now_iso()
        task = update_task(task.get("id"), patch) or task
    else:
        started_at = _now_iso() if patch["status"] in {"active", "blocked"} else None
        completed_at = _now_iso() if patch["status"] == "completed" else None
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
    _sync_task_plan_children(task, normalized)
    latest = get_task(task.get("id")) or task
    latest_snapshot = task_to_plan_snapshot(latest) or normalized
    return latest, latest_snapshot


def validate_task_substrate():
    projects, tasks, relations = load_all_task_data()
    project_ids = {p.get("id") for p in projects if p.get("id")}
    task_ids = {t.get("id") for t in tasks if t.get("id")}
    issues = []
    for t in tasks:
        if not t.get("id") or not t.get("title"):
            issues.append({"type": "task_invalid", "id": t.get("id")})
        if t.get("project_id") and t.get("project_id") not in project_ids:
            issues.append({"type": "task_missing_project", "id": t.get("id"), "project_id": t.get("project_id")})
    for r in relations:
        if r.get("from_id") not in task_ids and r.get("from_id") not in project_ids:
            issues.append({"type": "relation_missing_from", "id": r.get("id")})
        if r.get("to_id") not in task_ids and r.get("to_id") not in project_ids:
            issues.append({"type": "relation_missing_to", "id": r.get("id")})
    return {"ok": len(issues) == 0, "issues": issues}


def ensure_content_project_migrated():
    projects = load_task_projects()
    tasks = load_tasks()
    if any(isinstance(p, dict) and p.get("kind") == "content" for p in projects) or any(isinstance(t, dict) and t.get("kind") == "content" for t in tasks):
        return
    legacy_projects = load_content_projects()
    if not isinstance(legacy_projects, list):
        return
    task_seq = len(tasks)
    for legacy in legacy_projects:
        if not isinstance(legacy, dict):
            continue
        project_id = _make_id("proj", len(projects) + 1)
        project = _normalize_project({
            "id": project_id,
            "kind": "content",
            "title": legacy.get("name") or "content project",
            "status": legacy.get("status") or "active",
            "created_at": legacy.get("created_at") or _now_iso(),
            "updated_at": legacy.get("updated_at") or _now_iso(),
            "current_task_id": None,
            "settings": legacy.get("settings") or {},
            "goal": {"summary": "持续推进内容任务"},
            "memory": {},
        })
        projects.append(project)
        for lt in _ensure_list(legacy.get("tasks")):
            task_seq += 1
            task = _normalize_task({
                "id": _make_id("task", task_seq),
                "project_id": project_id,
                "kind": "content",
                "title": ((lt.get("selected_topic") or {}).get("title") or "content task").strip(),
                "status": lt.get("status") or "draft_ready",
                "stage": lt.get("stage") or "draft",
                "created_at": lt.get("created_at") or _now_iso(),
                "updated_at": lt.get("updated_at") or _now_iso(),
                "artifacts": {
                    "materials": lt.get("materials") or [],
                    "selected_topic": lt.get("selected_topic") or {},
                    "angle": lt.get("angle") or {},
                    "outline": lt.get("outline") or {},
                    "draft": lt.get("draft") or {},
                },
                "result": {"summary": lt.get("result_summary") or ""},
                "domain": {
                    "content": {
                        "source_mode": (legacy.get("settings") or {}).get("source_mode", "news"),
                        "topic_key": ((lt.get("selected_topic") or {}).get("normalized_key") or ""),
                        "draft_version": ((lt.get("draft") or {}).get("version") or 1),
                    }
                },
                "memory": {"last_active_at": lt.get("updated_at") or _now_iso()},
            })
            tasks.append(task)
            project["current_task_id"] = task["id"]
            project["updated_at"] = task.get("updated_at") or project["updated_at"]
    save_task_projects(projects)
    save_tasks(tasks)
