"""Task-substrate validation and migration helpers."""

from __future__ import annotations


def validate_task_substrate(*, load_all_task_data) -> dict:
    projects, tasks, relations = load_all_task_data()
    project_ids = {p.get("id") for p in projects if p.get("id")}
    task_ids = {t.get("id") for t in tasks if t.get("id")}
    issues: list[dict] = []
    for task in tasks:
        if not task.get("id") or not task.get("title"):
            issues.append({"type": "task_invalid", "id": task.get("id")})
        if task.get("project_id") and task.get("project_id") not in project_ids:
            issues.append({"type": "task_missing_project", "id": task.get("id"), "project_id": task.get("project_id")})
    for relation in relations:
        if relation.get("from_id") not in task_ids and relation.get("from_id") not in project_ids:
            issues.append({"type": "relation_missing_from", "id": relation.get("id")})
        if relation.get("to_id") not in task_ids and relation.get("to_id") not in project_ids:
            issues.append({"type": "relation_missing_to", "id": relation.get("id")})
    return {"ok": len(issues) == 0, "issues": issues}


def ensure_content_project_migrated(
    *,
    load_task_projects,
    load_tasks,
    load_content_projects,
    make_id,
    normalize_project,
    normalize_task,
    ensure_list,
    now_iso,
    save_task_projects,
    save_tasks,
):
    projects = load_task_projects()
    tasks = load_tasks()
    if any(isinstance(project, dict) and project.get("kind") == "content" for project in projects) or any(
        isinstance(task, dict) and task.get("kind") == "content" for task in tasks
    ):
        return
    legacy_projects = load_content_projects()
    if not isinstance(legacy_projects, list):
        return
    task_seq = len(tasks)
    for legacy in legacy_projects:
        if not isinstance(legacy, dict):
            continue
        project_id = make_id("proj", len(projects) + 1)
        project = normalize_project(
            {
                "id": project_id,
                "kind": "content",
                "title": legacy.get("name") or "content project",
                "status": legacy.get("status") or "active",
                "created_at": legacy.get("created_at") or now_iso(),
                "updated_at": legacy.get("updated_at") or now_iso(),
                "current_task_id": None,
                "settings": legacy.get("settings") or {},
                "goal": {"summary": "????????????"},
                "memory": {},
            }
        )
        projects.append(project)
        for legacy_task in ensure_list(legacy.get("tasks")):
            task_seq += 1
            task = normalize_task(
                {
                    "id": make_id("task", task_seq),
                    "project_id": project_id,
                    "kind": "content",
                    "title": ((legacy_task.get("selected_topic") or {}).get("title") or "content task").strip(),
                    "status": legacy_task.get("status") or "draft_ready",
                    "stage": legacy_task.get("stage") or "draft",
                    "created_at": legacy_task.get("created_at") or now_iso(),
                    "updated_at": legacy_task.get("updated_at") or now_iso(),
                    "artifacts": {
                        "materials": legacy_task.get("materials") or [],
                        "selected_topic": legacy_task.get("selected_topic") or {},
                        "angle": legacy_task.get("angle") or {},
                        "outline": legacy_task.get("outline") or {},
                        "draft": legacy_task.get("draft") or {},
                    },
                    "result": {"summary": legacy_task.get("result_summary") or ""},
                    "domain": {
                        "content": {
                            "source_mode": (legacy.get("settings") or {}).get("source_mode", "news"),
                            "topic_key": ((legacy_task.get("selected_topic") or {}).get("normalized_key") or ""),
                            "draft_version": ((legacy_task.get("draft") or {}).get("version") or 1),
                        }
                    },
                    "memory": {"last_active_at": legacy_task.get("updated_at") or now_iso()},
                }
            )
            tasks.append(task)
            project["current_task_id"] = task["id"]
            project["updated_at"] = task.get("updated_at") or project["updated_at"]
    save_task_projects(projects)
    save_tasks(tasks)
