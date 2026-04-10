"""Task continuity matching and referential follow-up helpers."""

from __future__ import annotations

import re
from pathlib import Path as _Path


def normalize_query_path(path: str) -> str:
    raw = str(path or "").strip().strip("`\"'[]{}()<>")
    return raw.rstrip("\\/")


def _path_parts(path: str) -> list[str]:
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


def _is_ancestor_path(parent_path: str, child_path: str) -> bool:
    parent_parts = _path_parts(parent_path)
    child_parts = _path_parts(child_path)
    if not parent_parts or not child_parts:
        return False
    if len(parent_parts) >= len(child_parts):
        return False
    return child_parts[: len(parent_parts)] == parent_parts


def extract_explicit_query_paths(query: str) -> list[str]:
    raw = str(query or "").strip()
    if not raw:
        return []

    patterns = (
        re.compile(r'"([A-Za-z]:\\[^"]+|[A-Za-z]:/[^"]+)"'),
        re.compile(r"([A-Za-z]:[\\/][^\s`<>\"\]]+)"),
    )
    paths: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in pattern.findall(raw):
            candidate = normalize_query_path(match)
            if not candidate:
                continue
            lowered = candidate.replace("/", "\\").lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            paths.append(candidate)
            if len(paths) >= 6:
                return paths
    return paths


def paths_overlap_for_resume(left_path: str, right_path: str) -> bool:
    left = normalize_query_path(left_path)
    right = normalize_query_path(right_path)
    if not left or not right:
        return False
    if left.replace("/", "\\").lower() == right.replace("/", "\\").lower():
        return True
    return _is_ancestor_path(left, right) or _is_ancestor_path(right, left)


def plan_goal_key(text: str) -> str:
    raw = str(text or "").strip().lower()
    raw = re.sub(r"[\W_]+", " ", raw, flags=re.UNICODE)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw[:120]


def goal_overlap(a: str, b: str) -> float:
    a_key = plan_goal_key(a)
    b_key = plan_goal_key(b)
    if not a_key or not b_key:
        return 0.0
    a_tokens = {token for token in a_key.split(" ") if token}
    b_tokens = {token for token in b_key.split(" ") if token}
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = a_tokens & b_tokens
    return len(overlap) / max(len(a_tokens), len(b_tokens), 1)


def task_plan_continuation_markers() -> tuple[str, ...]:
    return (
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


def looks_like_task_plan_continuation(query: str) -> bool:
    raw = str(query or "").strip().lower()
    if not raw:
        return False
    normalized = re.sub(r"\s+", " ", raw).strip()
    return any(normalized.startswith(marker) for marker in task_plan_continuation_markers())


def looks_like_short_referential_followup(query: str) -> bool:
    raw = str(query or "").strip().lower()
    if not raw or len(raw) > 24:
        return False
    referential_tokens = (
        "它",
        "这个",
        "那个",
        "之前那个",
        "刚才那个",
        "上次那个",
        "that",
        "it",
        "previous",
    )
    if not any(token in raw for token in referential_tokens):
        return False
    followup_markers = (
        "哪",
        "哪里",
        "在哪",
        "在哪儿",
        "怎么",
        "呢",
        "吗",
        "?",
        "？",
        "where",
        "how",
        "what",
    )
    return any(marker in raw for marker in followup_markers)


def looks_like_long_referential_followup(query: str) -> bool:
    raw = str(query or "").strip().lower()
    if not raw:
        return False
    referential_tokens = (
        "之前",
        "刚才",
        "上次",
        "那个",
        "这个",
        "它",
        "that",
        "it",
        "previous",
    )
    if not any(token in raw for token in referential_tokens):
        return False
    followup_markers = (
        "在哪",
        "哪里",
        "文件夹",
        "目录",
        "路径",
        "位置",
        "where",
        "folder",
        "directory",
        "path",
    )
    return any(marker in raw for marker in followup_markers)


def looks_like_direct_task_resume_command(query: str) -> bool:
    raw = str(query or "").strip().lower()
    if not raw:
        return False
    normalized = re.sub(r"\s+", " ", raw).strip()
    filler_tails = {
        "it",
        "this",
        "that",
        "this task",
        "that task",
        "this project",
        "that project",
        "the task",
        "the project",
        "the plan",
        "the step",
        "这个",
        "那个",
        "这个任务",
        "那个任务",
        "这个项目",
        "那个项目",
        "这个计划",
        "那个计划",
        "任务",
        "项目",
        "计划",
        "吧",
        "一下",
        "下",
        "来",
        "做",
        "弄",
        "搞",
        "处理",
    }
    reference_tokens = (
        "this",
        "that",
        "it",
        "task",
        "project",
        "plan",
        "step",
        "file",
        "folder",
        "path",
        "这个",
        "那个",
        "任务",
        "项目",
        "计划",
        "步骤",
        "文件",
        "目录",
        "路径",
    )
    for marker in task_plan_continuation_markers():
        if not normalized.startswith(marker):
            continue
        tail = normalized[len(marker) :].strip(" ,.;:!?，。！？")
        if not tail:
            return True
        if tail in filler_tails:
            return True
        if any(token in tail for token in reference_tokens):
            return True
    return False


def query_clearly_refers_to_active_task(
    query: str,
    *,
    last_ref: str = "",
    goal: str = "",
    current_step: str = "",
    task_status: str = "",
) -> bool:
    raw = str(query or "").strip()
    if not raw:
        return False

    refs = [
        str(goal or "").strip(),
        str(current_step or "").strip(),
        str(last_ref or "").strip(),
    ]
    refs = [item for item in refs if item]

    if looks_like_task_plan_continuation(raw):
        if looks_like_direct_task_resume_command(raw):
            return True
        return any(ref in raw or raw in ref or goal_overlap(raw, ref) >= 0.2 for ref in refs)

    if looks_like_short_referential_followup(raw):
        compact = re.sub(r"\s+", "", raw).strip()
        taskish_tokens = (
            "任务",
            "项目",
            "计划",
            "步骤",
            "文件",
            "文件夹",
            "目录",
            "路径",
            "task",
            "project",
            "plan",
            "step",
            "file",
            "folder",
            "directory",
            "path",
        )
        if len(compact) <= 12:
            return True
        if any(token in raw.lower() for token in taskish_tokens):
            return True
        return any(ref in raw or raw in ref or goal_overlap(raw, ref) >= 0.45 for ref in refs)

    if looks_like_long_referential_followup(raw):
        return True

    if any(ref in raw or raw in ref or goal_overlap(raw, ref) >= 0.45 for ref in refs):
        return True

    if str(task_status or "").strip() in {"blocked", "waiting"}:
        return False
    return False


def resolve_task_for_goal(kind: str, user_input: str, *, get_latest_active_task_by_kind):
    raw = str(user_input or "").strip()
    active = get_latest_active_task_by_kind(kind)
    if not active:
        return None
    if looks_like_task_plan_continuation(raw) or looks_like_direct_task_resume_command(raw):
        return active
    memory = active.get("memory") if isinstance(active.get("memory"), dict) else {}
    last_ref = str(memory.get("last_user_reference") or "").strip()
    if last_ref and last_ref[:10] and last_ref[:10] in raw:
        return active
    return None
