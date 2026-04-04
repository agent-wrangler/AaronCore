"""Structured fs-target extraction and persistence helpers."""

from __future__ import annotations

from pathlib import Path as _Path


def extract_task_fs_target(task: dict | None, *, normalize_task) -> dict | None:
    task = normalize_task(task) if isinstance(task, dict) else {}
    if not task:
        return None

    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    memory = task.get("memory") if isinstance(task.get("memory"), dict) else {}
    candidates = [
        context.get("fs_target") if isinstance(context.get("fs_target"), dict) else {},
        memory.get("last_fs_target") if isinstance(memory.get("last_fs_target"), dict) else {},
    ]
    for candidate in candidates:
        path = str(candidate.get("path") or "").strip()
        if not path:
            continue
        normalized = dict(candidate)
        normalized["path"] = path
        normalized["option"] = str(normalized.get("option") or "inspect").strip() or "inspect"
        return normalized
    return None


def normalize_fs_target_for_store(target: dict | None) -> dict | None:
    target = target if isinstance(target, dict) else {}
    path = str(target.get("path") or "").strip()
    if not path:
        return None
    normalized = dict(target)
    normalized["path"] = path
    normalized["option"] = str(normalized.get("option") or "inspect").strip() or "inspect"
    normalized["source"] = str(normalized.get("source") or "task_store").strip() or "task_store"
    return normalized


def fs_target_parts(path: str) -> list[str]:
    raw = str(path or "").strip()
    if not raw:
        return []
    try:
        parts = list(_Path(raw.replace("/", "\\")).parts)
    except Exception:
        return []
    cleaned: list[str] = []
    for part in parts:
        token = str(part or "").strip()
        if not token:
            continue
        lowered = token.rstrip("\\/").lower()
        if lowered:
            cleaned.append(lowered)
    return cleaned


def is_generic_user_shell_dir(path: str) -> bool:
    parts = fs_target_parts(path)
    if not parts:
        return False
    return parts[-1] in {"desktop", "documents", "downloads"}


def path_exists_for_target(path: str) -> bool:
    raw = str(path or "").strip()
    if not raw:
        return False
    try:
        return _Path(raw).exists()
    except Exception:
        return False


def is_target_ancestor_path(parent_path: str, child_path: str) -> bool:
    parent_parts = fs_target_parts(parent_path)
    child_parts = fs_target_parts(child_path)
    if not parent_parts or not child_parts:
        return False
    if len(parent_parts) >= len(child_parts):
        return False
    return child_parts[: len(parent_parts)] == parent_parts


def fs_target_specificity_score(target: dict | None, *, normalize_fs_target_for_store) -> int:
    normalized = normalize_fs_target_for_store(target)
    if not normalized:
        return -10_000
    path = str(normalized.get("path") or "").strip()
    parts = fs_target_parts(path)
    score = len(parts) * 10
    if path_exists_for_target(path):
        score += 20
    if is_generic_user_shell_dir(path):
        score -= 80
    if _Path(path).anchor and len(parts) <= 2:
        score -= 40
    if str(normalized.get("source") or "").strip() == "tool_runtime":
        score -= 5
    return score


def should_replace_fs_target(current_target: dict | None, new_target: dict | None, *, normalize_fs_target_for_store) -> bool:
    current = normalize_fs_target_for_store(current_target)
    new = normalize_fs_target_for_store(new_target)
    if not new:
        return False
    if not current:
        return True

    current_path = str(current.get("path") or "").strip()
    new_path = str(new.get("path") or "").strip()
    if not current_path:
        return True
    if current_path.lower() == new_path.lower():
        return True

    current_exists = path_exists_for_target(current_path)
    new_exists = path_exists_for_target(new_path)
    if current_exists and not new_exists:
        return False
    if is_generic_user_shell_dir(new_path) and not is_generic_user_shell_dir(current_path):
        return False
    if is_target_ancestor_path(new_path, current_path):
        return False

    return fs_target_specificity_score(new, normalize_fs_target_for_store=normalize_fs_target_for_store) >= (
        fs_target_specificity_score(current, normalize_fs_target_for_store=normalize_fs_target_for_store)
    )


def task_matches_query_paths(
    task: dict | None,
    query_paths: list[str],
    *,
    extract_task_fs_target,
    paths_overlap_for_resume,
) -> bool:
    task_target = extract_task_fs_target(task)
    target_path = str((task_target or {}).get("path") or "").strip()
    if not target_path:
        return False
    return any(paths_overlap_for_resume(target_path, query_path) for query_path in (query_paths or []))


def has_task_fs_target(task: dict | None, *, extract_task_fs_target) -> bool:
    return bool(extract_task_fs_target(task))


def merge_task_fs_target(task: dict, fs_target: dict, *, normalize_task, normalize_fs_target_for_store) -> dict:
    task = normalize_task(task)
    normalized_target = normalize_fs_target_for_store(fs_target)
    if not normalized_target:
        return task
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    memory = task.get("memory") if isinstance(task.get("memory"), dict) else {}
    context = dict(context)
    memory = dict(memory)
    context["fs_target"] = dict(normalized_target)
    memory["last_fs_target"] = dict(normalized_target)
    return {"context": context, "memory": memory}


def is_file_workflow_like_task(task: dict | None, *, normalize_task) -> bool:
    task = normalize_task(task) if isinstance(task, dict) else {}
    if not task:
        return False
    if str(task.get("kind") or "").strip() == "file_workflow":
        return True
    domain = task.get("domain") if isinstance(task.get("domain"), dict) else {}
    intake = domain.get("intake") if isinstance(domain.get("intake"), dict) else {}
    return str(intake.get("detected_kind") or "").strip() == "file_workflow"


def get_latest_structured_fs_target(
    *,
    load_tasks,
    normalize_task,
    extract_task_fs_target,
    is_file_workflow_like_task,
) -> dict | None:
    tasks = [normalize_task(x) for x in load_tasks() if isinstance(x, dict)]
    if not tasks:
        return None

    def _pick(bucket: list[dict]) -> dict | None:
        if not bucket:
            return None
        non_terminal = [t for t in bucket if t.get("status") not in {"completed", "failed", "cancelled", "archived"}]
        search_pool = non_terminal or bucket
        search_pool.sort(key=lambda x: str(x.get("updated_at") or x.get("created_at") or ""))
        for task in reversed(search_pool):
            target = extract_task_fs_target(task)
            if target:
                return target
        return None

    preferred = [task for task in tasks if is_file_workflow_like_task(task) and extract_task_fs_target(task)]
    fallback = [task for task in tasks if extract_task_fs_target(task)]
    return _pick(preferred) or _pick(fallback)


def get_structured_fs_target_for_task_plan(
    task_plan: dict | None,
    *,
    plan_project_title: str,
    get_task,
    get_project,
    get_active_task_for_project,
    get_project_tasks,
    extract_task_fs_target,
    normalize_fs_target_for_store,
) -> dict | None:
    task_plan = task_plan if isinstance(task_plan, dict) else {}
    task_id = str(task_plan.get("task_id") or "").strip()
    project_id = str(task_plan.get("project_id") or "").strip()

    if task_id:
        task = get_task(task_id)
        target = extract_task_fs_target(task)
        if target:
            return target

    if project_id:
        project = get_project(project_id)
        if isinstance(project, dict) and project.get("kind") == "generic" and project.get("title") == plan_project_title:
            return None

    if project_id:
        project = get_project(project_id)
        if isinstance(project, dict):
            project_memory = project.get("memory") if isinstance(project.get("memory"), dict) else {}
            target = normalize_fs_target_for_store(project_memory.get("last_fs_target"))
            if target:
                return target

        active_task = get_active_task_for_project(project_id)
        target = extract_task_fs_target(active_task)
        if target:
            return target

        project_tasks = get_project_tasks(project_id)
        project_tasks.sort(key=lambda x: str(x.get("updated_at") or x.get("created_at") or ""))
        for task in reversed(project_tasks):
            target = extract_task_fs_target(task)
            if target:
                return target
    return None


def remember_fs_target_for_task_plan(
    task_plan: dict | None,
    fs_target: dict | None,
    *,
    get_task,
    update_task,
    get_project,
    update_project,
    extract_task_fs_target,
    normalize_fs_target_for_store,
    should_replace_fs_target,
    merge_task_fs_target,
) -> dict | None:
    task_plan = task_plan if isinstance(task_plan, dict) else {}
    normalized_target = normalize_fs_target_for_store(fs_target)
    if not normalized_target:
        return None

    task_id = str(task_plan.get("task_id") or "").strip()
    project_id = str(task_plan.get("project_id") or "").strip()
    remembered = None

    if task_id:
        task = get_task(task_id)
        if task:
            current_target = extract_task_fs_target(task)
            if should_replace_fs_target(current_target, normalized_target):
                patch = merge_task_fs_target(task, normalized_target)
                remembered = update_task(task_id, patch) or task
            else:
                remembered = task

    if project_id:
        project = get_project(project_id)
        if project:
            project_memory = project.get("memory") if isinstance(project.get("memory"), dict) else {}
            current_project_target = normalize_fs_target_for_store(project_memory.get("last_fs_target"))
            if should_replace_fs_target(current_project_target, normalized_target):
                project_memory = dict(project_memory)
                project_memory["last_fs_target"] = dict(normalized_target)
                update_project(project_id, {"memory": project_memory})

    remembered_target = extract_task_fs_target(remembered) if isinstance(remembered, dict) else None
    return remembered_target or normalized_target
