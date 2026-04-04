"""Task-plan orchestration over views, runtime helpers, and continuity."""

from __future__ import annotations

from tasks import plan_runtime as _plan_runtime
from tasks import views as _views


def is_task_plan_task(task: dict) -> bool:
    task = task if isinstance(task, dict) else {}
    domain = task.get("domain") if isinstance(task.get("domain"), dict) else {}
    task_plan = domain.get("task_plan") if isinstance(domain.get("task_plan"), dict) else {}
    return bool(task_plan.get("enabled"))


def all_task_plan_tasks(*, load_tasks, normalize_task, is_task_plan_task) -> list[dict]:
    tasks = [normalize_task(x) for x in load_tasks() if isinstance(x, dict)]
    return [task for task in tasks if is_task_plan_task(task)]


def get_or_create_task_plan_project(*, load_task_projects, normalize_project, create_project, plan_project_title):
    return _plan_runtime.get_or_create_task_plan_project(
        load_task_projects=load_task_projects,
        normalize_project=normalize_project,
        create_project=create_project,
        plan_project_title=plan_project_title,
    )


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
    return _views.find_matching_task_plan_task(
        user_input,
        preferred_fs_target,
        all_task_plan_tasks=all_task_plan_tasks,
        extract_explicit_query_paths=extract_explicit_query_paths,
        task_matches_query_paths=task_matches_query_paths,
        normalize_query_path=normalize_query_path,
        has_task_fs_target=has_task_fs_target,
        looks_like_task_plan_continuation=looks_like_task_plan_continuation,
        looks_like_direct_task_resume_command=looks_like_direct_task_resume_command,
        goal_overlap=goal_overlap,
        looks_like_short_referential_followup=looks_like_short_referential_followup,
        looks_like_long_referential_followup=looks_like_long_referential_followup,
    )


def task_to_plan_snapshot(task: dict | None, *, normalize_task, is_task_plan_task, normalize_task_plan_snapshot) -> dict | None:
    return _views.task_to_plan_snapshot(
        task,
        normalize_task=normalize_task,
        is_task_plan_task=is_task_plan_task,
        normalize_task_plan_snapshot=normalize_task_plan_snapshot,
    )


def get_active_task_plan_snapshot(
    user_input: str = "",
    preferred_fs_target: str = "",
    *,
    find_matching_task_plan_task,
    task_to_plan_snapshot,
) -> dict | None:
    return _views.get_active_task_plan_snapshot(
        user_input,
        preferred_fs_target,
        find_matching_task_plan_task=find_matching_task_plan_task,
        task_to_plan_snapshot=task_to_plan_snapshot,
    )


def task_to_working_state(
    task: dict | None,
    *,
    normalize_task,
    task_to_plan_snapshot,
    extract_task_fs_target,
    get_structured_fs_target_for_task_plan,
) -> dict | None:
    return _views.task_to_working_state(
        task,
        normalize_task=normalize_task,
        task_to_plan_snapshot=task_to_plan_snapshot,
        extract_task_fs_target=extract_task_fs_target,
        get_structured_fs_target_for_task_plan=get_structured_fs_target_for_task_plan,
    )


def get_active_task_working_state(
    user_input: str = "",
    preferred_fs_target: str = "",
    *,
    find_matching_task_plan_task,
    task_to_working_state,
) -> dict | None:
    return _views.get_active_task_working_state(
        user_input,
        preferred_fs_target,
        find_matching_task_plan_task=find_matching_task_plan_task,
        task_to_working_state=task_to_working_state,
    )


def task_plan_item_to_status(item_status: str, *, normalize_plan_item_status) -> str:
    return _plan_runtime.task_plan_item_to_status(
        item_status,
        normalize_plan_item_status=normalize_plan_item_status,
    )


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
    return _plan_runtime.sync_task_plan_children(
        parent_task,
        plan,
        get_child_tasks=get_child_tasks,
        load_task_relations=load_task_relations,
        update_task=update_task,
        create_task=create_task,
        create_relation=create_relation,
        task_plan_item_to_status=task_plan_item_to_status,
    )


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
    return _plan_runtime.save_task_plan_snapshot(
        user_input,
        snapshot,
        normalize_task_plan_snapshot=normalize_task_plan_snapshot,
        get_or_create_task_plan_project=get_or_create_task_plan_project,
        find_matching_task_plan_task=find_matching_task_plan_task,
        task_status_from_plan=task_status_from_plan,
        task_stage_from_plan=task_stage_from_plan,
        plan_goal_key=plan_goal_key,
        now_iso=now_iso,
        update_task=update_task,
        create_task=create_task,
        append_task_event=append_task_event,
        update_project=update_project,
        sync_task_plan_children=sync_task_plan_children,
        get_task=get_task,
        task_to_plan_snapshot=task_to_plan_snapshot,
        source=source,
    )
