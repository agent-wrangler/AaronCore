"""Task-substrate normalization, persistence, and query helpers."""

from __future__ import annotations

from datetime import datetime


def now_iso() -> str:
    return datetime.now().isoformat()


def make_id(prefix: str, seq: int) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d')}_{seq:03d}"


def ensure_list(value):
    return value if isinstance(value, list) else []


def normalize_project(obj: dict, *, allowed_project_kinds, now_iso) -> dict:
    data = obj if isinstance(obj, dict) else {}
    kind = str(data.get("kind") or "generic")
    if kind not in allowed_project_kinds:
        kind = "generic"
    return {
        "id": str(data.get("id") or ""),
        "kind": kind,
        "title": str(data.get("title") or data.get("name") or "").strip(),
        "status": str(data.get("status") or "active"),
        "description": str(data.get("description") or ""),
        "owner": str(data.get("owner") or "nova"),
        "created_at": str(data.get("created_at") or now_iso()),
        "updated_at": str(data.get("updated_at") or now_iso()),
        "current_task_id": data.get("current_task_id"),
        "goal": data.get("goal") if isinstance(data.get("goal"), dict) else {},
        "settings": data.get("settings") if isinstance(data.get("settings"), dict) else {},
        "memory": data.get("memory") if isinstance(data.get("memory"), dict) else {},
    }


def normalize_task(obj: dict, *, allowed_task_kinds, allowed_task_status, ensure_list, now_iso) -> dict:
    data = obj if isinstance(obj, dict) else {}
    kind = str(data.get("kind") or "generic")
    if kind not in allowed_task_kinds:
        kind = "generic"
    status = str(data.get("status") or "created")
    if status not in allowed_task_status:
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
        "created_at": str(data.get("created_at") or now_iso()),
        "updated_at": str(data.get("updated_at") or now_iso()),
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
        "events": ensure_list(data.get("events")),
    }


def normalize_relation(obj: dict, *, allowed_relation_types, now_iso) -> dict:
    data = obj if isinstance(obj, dict) else {}
    rel_type = str(data.get("type") or "references")
    if rel_type not in allowed_relation_types:
        rel_type = "references"
    return {
        "id": str(data.get("id") or ""),
        "from_id": str(data.get("from_id") or ""),
        "to_id": str(data.get("to_id") or ""),
        "type": rel_type,
        "created_at": str(data.get("created_at") or now_iso()),
        "meta": data.get("meta") if isinstance(data.get("meta"), dict) else {},
    }


def load_all_task_data(*, load_task_projects, load_tasks, load_task_relations, normalize_project, normalize_task, normalize_relation):
    projects = [normalize_project(x) for x in load_task_projects() if isinstance(x, dict)]
    tasks = [normalize_task(x) for x in load_tasks() if isinstance(x, dict)]
    relations = [normalize_relation(x) for x in load_task_relations() if isinstance(x, dict)]
    return projects, tasks, relations


def save_all_task_data(projects, tasks, relations, *, save_task_projects, save_tasks, save_task_relations, normalize_project, normalize_task, normalize_relation):
    save_task_projects([normalize_project(x) for x in (projects or [])])
    save_tasks([normalize_task(x) for x in (tasks or [])])
    save_task_relations([normalize_relation(x) for x in (relations or [])])


def create_project(kind: str, title: str, *, load_task_projects, save_task_projects, normalize_project, make_id, **extra):
    projects = load_task_projects()
    project = normalize_project(
        {
            "id": make_id("proj", len(projects) + 1),
            "kind": kind,
            "title": title,
            "status": extra.get("status") or "active",
            "description": extra.get("description") or "",
            "owner": extra.get("owner") or "nova",
            "goal": extra.get("goal") or {},
            "settings": extra.get("settings") or {},
            "memory": extra.get("memory") or {},
        }
    )
    projects.append(project)
    save_task_projects(projects)
    return project


def create_task(kind: str, title: str, *, load_tasks, save_tasks, normalize_task, make_id, **extra):
    tasks = load_tasks()
    task = normalize_task(
        {
            "id": make_id("task", len(tasks) + 1),
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
        }
    )
    tasks.append(task)
    save_tasks(tasks)
    return task


def update_project(project_id: str, patch: dict, *, load_task_projects, save_task_projects, normalize_project, now_iso):
    projects = load_task_projects()
    updated = None
    for idx, item in enumerate(projects):
        if isinstance(item, dict) and item.get("id") == project_id:
            merged = dict(item)
            merged.update(patch or {})
            merged["updated_at"] = now_iso()
            projects[idx] = normalize_project(merged)
            updated = projects[idx]
            break
    if updated is not None:
        save_task_projects(projects)
    return updated


def update_task(task_id: str, patch: dict, *, load_tasks, save_tasks, normalize_task, now_iso):
    tasks = load_tasks()
    updated = None
    for idx, item in enumerate(tasks):
        if isinstance(item, dict) and item.get("id") == task_id:
            merged = dict(item)
            merged.update(patch or {})
            merged["updated_at"] = now_iso()
            tasks[idx] = normalize_task(merged)
            updated = tasks[idx]
            break
    if updated is not None:
        save_tasks(tasks)
    return updated


def append_task_event(task_id: str, event_type: str, summary: str, *, load_tasks, save_tasks, normalize_task, ensure_list, now_iso, **extra):
    tasks = load_tasks()
    updated = None
    for idx, item in enumerate(tasks):
        if isinstance(item, dict) and item.get("id") == task_id:
            merged = dict(item)
            events = ensure_list(merged.get("events"))
            row = {"type": event_type, "at": now_iso(), "summary": summary}
            row.update(extra or {})
            events.append(row)
            merged["events"] = events
            merged["updated_at"] = now_iso()
            tasks[idx] = normalize_task(merged)
            updated = tasks[idx]
            break
    if updated is not None:
        save_tasks(tasks)
    return updated


def create_relation(from_id: str, to_id: str, rel_type: str, *, load_task_relations, save_task_relations, normalize_relation, make_id, **meta):
    relations = load_task_relations()
    relation = normalize_relation(
        {
            "id": make_id("rel", len(relations) + 1),
            "from_id": from_id,
            "to_id": to_id,
            "type": rel_type,
            "meta": meta or {},
        }
    )
    relations.append(relation)
    save_task_relations(relations)
    return relation


def get_project(project_id: str, *, load_task_projects, normalize_project):
    for item in load_task_projects():
        if isinstance(item, dict) and item.get("id") == project_id:
            return normalize_project(item)
    return None


def get_task(task_id: str, *, load_tasks, normalize_task):
    for item in load_tasks():
        if isinstance(item, dict) and item.get("id") == task_id:
            return normalize_task(item)
    return None


def get_project_tasks(project_id: str, *, load_tasks, normalize_task):
    return [normalize_task(x) for x in load_tasks() if isinstance(x, dict) and x.get("project_id") == project_id]


def get_tasks_by_kind(kind: str, *, load_tasks, normalize_task):
    return [normalize_task(x) for x in load_tasks() if isinstance(x, dict) and x.get("kind") == kind]


def get_latest_active_task_by_kind(kind: str, *, get_tasks_by_kind):
    tasks = get_tasks_by_kind(kind)
    non_terminal = [t for t in tasks if t.get("status") not in {"completed", "failed", "cancelled", "archived"}]
    if not non_terminal:
        return tasks[-1] if tasks else None
    non_terminal.sort(key=lambda x: str(x.get("updated_at") or ""))
    return non_terminal[-1]


def get_child_tasks(parent_task_id: str, *, load_tasks, normalize_task):
    return [normalize_task(x) for x in load_tasks() if isinstance(x, dict) and x.get("parent_task_id") == parent_task_id]


def get_task_relations_for(task_id: str, *, load_task_relations, normalize_relation):
    relations = load_task_relations()
    return [normalize_relation(x) for x in relations if isinstance(x, dict) and (x.get("from_id") == task_id or x.get("to_id") == task_id)]


def get_active_task_for_project(project_id: str, *, get_project_tasks):
    tasks = get_project_tasks(project_id)
    non_terminal = [t for t in tasks if t.get("status") not in {"completed", "failed", "cancelled", "archived"}]
    if not non_terminal:
        return tasks[-1] if tasks else None
    non_terminal.sort(key=lambda x: str(x.get("updated_at") or ""))
    return non_terminal[-1]
