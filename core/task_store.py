from datetime import datetime

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
