from storage.content_store import load_content_projects
from tasks import continuity as _continuity
from tasks import fs_targets as _fs_targets
from tasks import maintenance as _maintenance
from tasks import plan_runtime as _plan_runtime
from tasks import substrate as _substrate
from tasks import task_plans as _task_plans
from storage.task_files import (
    load_task_projects,
    save_task_projects,
    load_tasks,
    save_tasks,
    load_task_relations,
    save_task_relations,
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
    return _substrate.now_iso()


def _make_id(prefix: str, seq: int) -> str:
    return _substrate.make_id(prefix, seq)


def _ensure_list(value):
    return _substrate.ensure_list(value)


def _normalize_project(obj: dict) -> dict:
    return _substrate.normalize_project(
        obj,
        allowed_project_kinds=ALLOWED_PROJECT_KINDS,
        now_iso=_now_iso,
    )


def _normalize_task(obj: dict) -> dict:
    return _substrate.normalize_task(
        obj,
        allowed_task_kinds=ALLOWED_TASK_KINDS,
        allowed_task_status=ALLOWED_TASK_STATUS,
        ensure_list=_ensure_list,
        now_iso=_now_iso,
    )


def _normalize_relation(obj: dict) -> dict:
    return _substrate.normalize_relation(
        obj,
        allowed_relation_types=ALLOWED_RELATION_TYPES,
        now_iso=_now_iso,
    )


def load_all_task_data():
    return _substrate.load_all_task_data(
        load_task_projects=load_task_projects,
        load_tasks=load_tasks,
        load_task_relations=load_task_relations,
        normalize_project=_normalize_project,
        normalize_task=_normalize_task,
        normalize_relation=_normalize_relation,
    )


def save_all_task_data(projects, tasks, relations):
    return _substrate.save_all_task_data(
        projects,
        tasks,
        relations,
        save_task_projects=save_task_projects,
        save_tasks=save_tasks,
        save_task_relations=save_task_relations,
        normalize_project=_normalize_project,
        normalize_task=_normalize_task,
        normalize_relation=_normalize_relation,
    )


def create_project(kind: str, title: str, **extra):
    return _substrate.create_project(
        kind,
        title,
        load_task_projects=load_task_projects,
        save_task_projects=save_task_projects,
        normalize_project=_normalize_project,
        make_id=_make_id,
        **extra,
    )


def create_task(kind: str, title: str, **extra):
    return _substrate.create_task(
        kind,
        title,
        load_tasks=load_tasks,
        save_tasks=save_tasks,
        normalize_task=_normalize_task,
        make_id=_make_id,
        **extra,
    )


def update_project(project_id: str, patch: dict):
    return _substrate.update_project(
        project_id,
        patch,
        load_task_projects=load_task_projects,
        save_task_projects=save_task_projects,
        normalize_project=_normalize_project,
        now_iso=_now_iso,
    )


def update_task(task_id: str, patch: dict):
    return _substrate.update_task(
        task_id,
        patch,
        load_tasks=load_tasks,
        save_tasks=save_tasks,
        normalize_task=_normalize_task,
        now_iso=_now_iso,
    )


def append_task_event(task_id: str, event_type: str, summary: str, **extra):
    return _substrate.append_task_event(
        task_id,
        event_type,
        summary,
        load_tasks=load_tasks,
        save_tasks=save_tasks,
        normalize_task=_normalize_task,
        ensure_list=_ensure_list,
        now_iso=_now_iso,
        **extra,
    )


def create_relation(from_id: str, to_id: str, rel_type: str, **meta):
    return _substrate.create_relation(
        from_id,
        to_id,
        rel_type,
        load_task_relations=load_task_relations,
        save_task_relations=save_task_relations,
        normalize_relation=_normalize_relation,
        make_id=_make_id,
        **meta,
    )


def get_project(project_id: str):
    return _substrate.get_project(
        project_id,
        load_task_projects=load_task_projects,
        normalize_project=_normalize_project,
    )


def get_task(task_id: str):
    return _substrate.get_task(
        task_id,
        load_tasks=load_tasks,
        normalize_task=_normalize_task,
    )


def get_project_tasks(project_id: str):
    return _substrate.get_project_tasks(
        project_id,
        load_tasks=load_tasks,
        normalize_task=_normalize_task,
    )


def get_tasks_by_kind(kind: str):
    return _substrate.get_tasks_by_kind(
        kind,
        load_tasks=load_tasks,
        normalize_task=_normalize_task,
    )


def get_latest_active_task_by_kind(kind: str):
    return _substrate.get_latest_active_task_by_kind(
        kind,
        get_tasks_by_kind=get_tasks_by_kind,
    )


def _extract_task_fs_target(task: dict | None) -> dict | None:
    return _fs_targets.extract_task_fs_target(task, normalize_task=_normalize_task)


def _normalize_fs_target_for_store(target: dict | None) -> dict | None:
    return _fs_targets.normalize_fs_target_for_store(target)


def _fs_target_parts(path: str) -> list[str]:
    return _fs_targets.fs_target_parts(path)


def _is_generic_user_shell_dir(path: str) -> bool:
    return _fs_targets.is_generic_user_shell_dir(path)


def _path_exists_for_target(path: str) -> bool:
    return _fs_targets.path_exists_for_target(path)


def _is_target_ancestor_path(parent_path: str, child_path: str) -> bool:
    return _fs_targets.is_target_ancestor_path(parent_path, child_path)


def _fs_target_specificity_score(target: dict | None) -> int:
    return _fs_targets.fs_target_specificity_score(
        target,
        normalize_fs_target_for_store=_normalize_fs_target_for_store,
    )


def _should_replace_fs_target(current_target: dict | None, new_target: dict | None) -> bool:
    return _fs_targets.should_replace_fs_target(
        current_target,
        new_target,
        normalize_fs_target_for_store=_normalize_fs_target_for_store,
    )


def _normalize_query_path(path: str) -> str:
    return _continuity.normalize_query_path(path)


def _extract_explicit_query_paths(query: str) -> list[str]:
    return _continuity.extract_explicit_query_paths(query)


def _paths_overlap_for_resume(left_path: str, right_path: str) -> bool:
    return _continuity.paths_overlap_for_resume(left_path, right_path)


def _task_matches_query_paths(task: dict | None, query_paths: list[str]) -> bool:
    return _fs_targets.task_matches_query_paths(
        task,
        query_paths,
        extract_task_fs_target=_extract_task_fs_target,
        paths_overlap_for_resume=_paths_overlap_for_resume,
    )


def _has_task_fs_target(task: dict | None) -> bool:
    return _fs_targets.has_task_fs_target(
        task,
        extract_task_fs_target=_extract_task_fs_target,
    )


def _merge_task_fs_target(task: dict, fs_target: dict) -> dict:
    return _fs_targets.merge_task_fs_target(
        task,
        fs_target,
        normalize_task=_normalize_task,
        normalize_fs_target_for_store=_normalize_fs_target_for_store,
    )


def _is_file_workflow_like_task(task: dict | None) -> bool:
    return _fs_targets.is_file_workflow_like_task(task, normalize_task=_normalize_task)


def get_latest_structured_fs_target() -> dict | None:
    return _fs_targets.get_latest_structured_fs_target(
        load_tasks=load_tasks,
        normalize_task=_normalize_task,
        extract_task_fs_target=_extract_task_fs_target,
        is_file_workflow_like_task=_is_file_workflow_like_task,
    )


def get_structured_fs_target_for_task_plan(task_plan: dict | None) -> dict | None:
    return _fs_targets.get_structured_fs_target_for_task_plan(
        task_plan,
        plan_project_title=PLAN_PROJECT_TITLE,
        get_task=get_task,
        get_project=get_project,
        get_active_task_for_project=get_active_task_for_project,
        get_project_tasks=get_project_tasks,
        extract_task_fs_target=_extract_task_fs_target,
        normalize_fs_target_for_store=_normalize_fs_target_for_store,
    )


def remember_fs_target_for_task_plan(task_plan: dict | None, fs_target: dict | None) -> dict | None:
    return _fs_targets.remember_fs_target_for_task_plan(
        task_plan,
        fs_target,
        get_task=get_task,
        update_task=update_task,
        get_project=get_project,
        update_project=update_project,
        extract_task_fs_target=_extract_task_fs_target,
        normalize_fs_target_for_store=_normalize_fs_target_for_store,
        should_replace_fs_target=_should_replace_fs_target,
        merge_task_fs_target=_merge_task_fs_target,
    )


def resolve_task_for_goal(kind: str, user_input: str):
    return _continuity.resolve_task_for_goal(
        kind,
        user_input,
        get_latest_active_task_by_kind=get_latest_active_task_by_kind,
    )


def get_child_tasks(parent_task_id: str):
    return _substrate.get_child_tasks(
        parent_task_id,
        load_tasks=load_tasks,
        normalize_task=_normalize_task,
    )


def get_task_relations_for(task_id: str):
    return _substrate.get_task_relations_for(
        task_id,
        load_task_relations=load_task_relations,
        normalize_relation=_normalize_relation,
    )


def get_active_task_for_project(project_id: str):
    return _substrate.get_active_task_for_project(
        project_id,
        get_project_tasks=get_project_tasks,
    )


def _is_task_plan_task(task: dict) -> bool:
    return _task_plans.is_task_plan_task(task)


def _slugify_plan_item(text: str, fallback: str) -> str:
    return _plan_runtime._slugify_plan_item(text, fallback)


def _default_plan_items(goal: str) -> list[dict]:
    return _plan_runtime._default_plan_items(goal)


def _normalize_plan_item_status(status: str, fallback: str = "pending") -> str:
    return _plan_runtime.normalize_plan_item_status(status, plan_item_status=PLAN_ITEM_STATUS, fallback=fallback)


def _normalize_plan_items(items, goal: str = "") -> list[dict]:
    return _plan_runtime._normalize_plan_items(items, goal=goal, plan_item_status=PLAN_ITEM_STATUS)


def normalize_task_plan_snapshot(plan: dict | None, *, goal: str = "") -> dict:
    return _plan_runtime.normalize_task_plan_snapshot(
        plan,
        goal=goal,
        plan_item_status=PLAN_ITEM_STATUS,
        now_iso=_now_iso,
    )


def _task_status_from_plan(plan: dict) -> str:
    return _plan_runtime.task_status_from_plan(plan)


def _task_stage_from_plan(plan: dict) -> str:
    return _plan_runtime.task_stage_from_plan(plan)


def _plan_goal_key(text: str) -> str:
    return _continuity.plan_goal_key(text)

def _looks_like_task_plan_continuation(query: str) -> bool:
    return _continuity.looks_like_task_plan_continuation(query)

def _looks_like_short_referential_followup(query: str) -> bool:
    return _continuity.looks_like_short_referential_followup(query)

def _looks_like_long_referential_followup(query: str) -> bool:
    return _continuity.looks_like_long_referential_followup(query)

def _looks_like_direct_task_resume_command(query: str) -> bool:
    return _continuity.looks_like_direct_task_resume_command(query)

def _goal_overlap(a: str, b: str) -> float:
    return _continuity.goal_overlap(a, b)

def _get_or_create_task_plan_project():
    return _task_plans.get_or_create_task_plan_project(
        load_task_projects=load_task_projects,
        normalize_project=_normalize_project,
        create_project=create_project,
        plan_project_title=PLAN_PROJECT_TITLE,
    )


def _all_task_plan_tasks() -> list[dict]:
    return _task_plans.all_task_plan_tasks(
        load_tasks=load_tasks,
        normalize_task=_normalize_task,
        is_task_plan_task=_is_task_plan_task,
    )


def _find_matching_task_plan_task(user_input: str = "", preferred_fs_target: str = ""):
    return _task_plans.find_matching_task_plan_task(
        user_input,
        preferred_fs_target,
        all_task_plan_tasks=_all_task_plan_tasks,
        extract_explicit_query_paths=_extract_explicit_query_paths,
        task_matches_query_paths=_task_matches_query_paths,
        normalize_query_path=_normalize_query_path,
        has_task_fs_target=_has_task_fs_target,
        looks_like_task_plan_continuation=_looks_like_task_plan_continuation,
        looks_like_direct_task_resume_command=_looks_like_direct_task_resume_command,
        goal_overlap=_goal_overlap,
        looks_like_short_referential_followup=_looks_like_short_referential_followup,
        looks_like_long_referential_followup=_looks_like_long_referential_followup,
    )


def task_to_plan_snapshot(task: dict | None) -> dict | None:
    return _task_plans.task_to_plan_snapshot(
        task,
        normalize_task=_normalize_task,
        is_task_plan_task=_is_task_plan_task,
        normalize_task_plan_snapshot=normalize_task_plan_snapshot,
    )


def get_active_task_plan_snapshot(user_input: str = "", preferred_fs_target: str = "") -> dict | None:
    return _task_plans.get_active_task_plan_snapshot(
        user_input,
        preferred_fs_target,
        find_matching_task_plan_task=_find_matching_task_plan_task,
        task_to_plan_snapshot=task_to_plan_snapshot,
    )


def task_to_working_state(task: dict | None) -> dict | None:
    return _task_plans.task_to_working_state(
        task,
        normalize_task=_normalize_task,
        task_to_plan_snapshot=task_to_plan_snapshot,
        extract_task_fs_target=_extract_task_fs_target,
        get_structured_fs_target_for_task_plan=get_structured_fs_target_for_task_plan,
    )


def get_active_task_working_state(user_input: str = "", preferred_fs_target: str = "") -> dict | None:
    return _task_plans.get_active_task_working_state(
        user_input,
        preferred_fs_target,
        find_matching_task_plan_task=_find_matching_task_plan_task,
        task_to_working_state=task_to_working_state,
    )


def _task_plan_item_to_status(item_status: str) -> str:
    return _task_plans.task_plan_item_to_status(
        item_status,
        normalize_plan_item_status=_normalize_plan_item_status,
    )


def _sync_task_plan_children(parent_task: dict, plan: dict):
    return _task_plans.sync_task_plan_children(
        parent_task,
        plan,
        get_child_tasks=get_child_tasks,
        load_task_relations=load_task_relations,
        update_task=update_task,
        create_task=create_task,
        create_relation=create_relation,
        task_plan_item_to_status=_task_plan_item_to_status,
    )


def save_task_plan_snapshot(user_input: str, snapshot: dict, *, source: str = "task_plan"):
    return _task_plans.save_task_plan_snapshot(
        user_input,
        snapshot,
        normalize_task_plan_snapshot=normalize_task_plan_snapshot,
        get_or_create_task_plan_project=_get_or_create_task_plan_project,
        find_matching_task_plan_task=_find_matching_task_plan_task,
        task_status_from_plan=_task_status_from_plan,
        task_stage_from_plan=_task_stage_from_plan,
        plan_goal_key=_plan_goal_key,
        now_iso=_now_iso,
        update_task=update_task,
        create_task=create_task,
        append_task_event=append_task_event,
        update_project=update_project,
        sync_task_plan_children=_sync_task_plan_children,
        get_task=get_task,
        task_to_plan_snapshot=task_to_plan_snapshot,
        source=source,
    )


def validate_task_substrate():
    return _maintenance.validate_task_substrate(load_all_task_data=load_all_task_data)


def ensure_content_project_migrated():
    return _maintenance.ensure_content_project_migrated(
        load_task_projects=load_task_projects,
        load_tasks=load_tasks,
        load_content_projects=load_content_projects,
        make_id=_make_id,
        normalize_project=_normalize_project,
        normalize_task=_normalize_task,
        ensure_list=_ensure_list,
        now_iso=_now_iso,
        save_task_projects=save_task_projects,
        save_tasks=save_tasks,
    )
