"""Task continuity matching and referential follow-up helpers."""

from __future__ import annotations

import re
from pathlib import Path as _Path


_BLOCKED_TASK_STATUSES = {"blocked", "waiting", "waiting_user"}
_BLOCKED_STEP_STATUSES = {"blocked", "error", "failed", "waiting_user"}
_BLOCKED_RUNTIME_STATUSES = {"blocked", "waiting_user"}
_LOCATION_QUERY_MARKERS = (
    "where",
    "path",
    "folder",
    "directory",
    "location",
    "\u54ea",
    "\u54ea\u91cc",
    "\u5728\u54ea",
    "\u5728\u54ea\u91cc",
    "\u8def\u5f84",
    "\u76ee\u5f55",
    "\u4f4d\u7f6e",
)
_STATUS_QUERY_MARKERS = (
    "status",
    "progress",
    "state",
    "current step",
    "doing",
    "working on",
    "how far",
    "\u8fdb\u5c55",
    "\u72b6\u6001",
    "\u6b65\u9aa4",
    "\u9636\u6bb5",
    "\u505a\u5230\u54ea",
    "\u5230\u54ea\u4e86",
    "\u505a\u5230\u54ea\u4e86",
    "\u73b0\u5728\u5728\u5e72",
)
_VERIFY_QUERY_MARKERS = (
    "verify",
    "verified",
    "verification",
    "checked",
    "pass",
    "\u9a8c\u8bc1",
    "\u6838\u9a8c",
    "\u786e\u8ba4",
    "\u901a\u8fc7",
    "\u597d\u4e86\u6ca1",
)
_INTERRUPT_QUERY_MARKERS = (
    "interrupt",
    "interrupted",
    "stop",
    "stopped",
    "cancelled",
    "\u4e2d\u65ad",
    "\u505c\u4e86",
    "\u65ad\u4e86",
    "\u6253\u65ad",
    "\u505c\u5728",
    "\u65ad\u5728",
)
_BLOCKER_QUERY_MARKERS = (
    "blocked",
    "blocker",
    "blocking",
    "stuck",
    "waiting",
    "need from me",
    "\u5361\u4f4f",
    "\u5361\u5728",
    "\u963b\u585e",
    "\u963b\u585e\u70b9",
    "\u9700\u8981\u6211",
    "\u7b49\u6211",
)
_ACTION_REQUEST_MARKERS = (
    "look at",
    "check",
    "inspect",
    "open",
    "read",
    "retry",
    "try again",
    "\u770b\u4e0b",
    "\u770b\u770b",
    "\u770b\u4e00\u4e0b",
    "\u770b\u770b\u91cc",
    "\u8bd5\u8bd5",
    "\u8bd5\u770b\u770b",
    "\u518d\u8bd5\u8bd5",
    "\u518d\u8bd5\u8bd5\u770b",
    "\u6253\u5f00",
    "\u8bfb\u4e00\u4e0b",
    "\u68c0\u67e5",
    "\u53bb\u770b\u4e0b",
    "\u53bb\u770b\u770b",
)
_USER_COMPLETION_MARKERS = (
    "i'm done",
    "im done",
    "i am done",
    "i finished",
    "i've finished",
    "ive finished",
    "done now",
    "finished now",
    "i logged in",
    "i've logged in",
    "ive logged in",
    "logged in now",
    "\u6211\u597d\u4e86",
    "\u6211\u641e\u597d\u4e86",
    "\u6211\u5f04\u597d\u4e86",
    "\u6211\u5df2\u7ecf\u641e\u5b9a\u4e86",
    "\u6211\u5df2\u7ecf\u5b8c\u6210\u4e86",
    "\u6211\u767b\u5f55\u597d\u4e86",
    "\u6211\u767b\u9646\u597d\u4e86",
    "\u6211\u5df2\u7ecf\u767b\u5f55\u4e86",
    "\u6211\u5df2\u7ecf\u767b\u9646\u4e86",
    "\u5df2\u7ecf\u641e\u5b9a\u4e86",
    "\u5df2\u7ecf\u5b8c\u6210\u4e86",
    "\u767b\u5f55\u597d\u4e86",
    "\u767b\u9646\u597d\u4e86",
)
_USER_COMPLETION_NEGATIONS = (
    "not yet",
    "haven't",
    "havent",
    "didn't",
    "didnt",
    "\u8fd8\u6ca1",
    "\u6ca1\u6709",
    "\u6ca1",
    "\u672a",
    "\u4e0d\u884c",
)
_RETRY_RESUME_MARKERS = (
    "retry",
    "try again",
    "rerun",
    "run again",
    "resume",
    "continue fixing",
    "continue the fix",
    "\u518d\u8bd5",
    "\u518d\u8bd5\u4e00\u4e0b",
    "\u518d\u8bd5\u8bd5",
    "\u518d\u8bd5\u770b\u770b",
    "\u91cd\u8bd5",
    "\u91cd\u65b0\u8bd5",
    "\u518d\u8dd1\u4e00\u6b21",
    "\u518d\u4fee\u4e00\u4e0b",
    "\u7ee7\u7eed\u4fee",
)
_RETRY_RESUME_NEGATIONS = (
    "don't retry",
    "dont retry",
    "do not retry",
    "stop retrying",
    "\u5148\u522b",
    "\u4e0d\u8981\u518d\u8bd5",
    "\u4e0d\u7528\u518d\u8bd5",
    "\u522b\u518d\u8bd5",
)


def normalize_query_path(path: str) -> str:
    raw = str(path or "").strip().strip("`\"'[]{}()<>")
    return raw.rstrip("\\/")


def _normalize_query_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip()).lower()


def _contains_any_marker(text: str, markers: tuple[str, ...]) -> bool:
    lowered = _normalize_query_text(text)
    if not lowered:
        return False
    return any(marker in lowered for marker in markers)


def _looks_like_direct_action_request(text: str) -> bool:
    return _contains_any_marker(text, _ACTION_REQUEST_MARKERS)


def _contains_marker_without_negation(text: str, markers: tuple[str, ...], negations: tuple[str, ...]) -> bool:
    lowered = _normalize_query_text(text)
    if not lowered:
        return False
    if any(marker in lowered for marker in negations):
        return False
    return any(marker in lowered for marker in markers)


def looks_like_user_completion_update(query: str) -> bool:
    return _contains_marker_without_negation(query, _USER_COMPLETION_MARKERS, _USER_COMPLETION_NEGATIONS)


def looks_like_retry_resume_request(query: str) -> bool:
    return _contains_marker_without_negation(query, _RETRY_RESUME_MARKERS, _RETRY_RESUME_NEGATIONS)


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


def _fs_target_reference_tokens(path: str) -> list[str]:
    normalized = normalize_query_path(path)
    if not normalized:
        return []
    tokenized = normalized.replace("/", "\\")
    parts = [part.strip().lower() for part in tokenized.split("\\") if part.strip()]
    if not parts:
        return []
    filename = parts[-1]
    stem = filename.rsplit(".", 1)[0]
    tokens = [filename, stem]
    if len(parts) >= 2:
        tokens.append(parts[-2])
    return [token for token in tokens if token]


def _raw_mentions_fs_target(query: str, fs_target: str) -> bool:
    lowered = _normalize_query_text(query)
    if not lowered:
        return False
    return any(token in lowered for token in _fs_target_reference_tokens(fs_target))


def _has_cjk_reference_fragment(raw: str, refs: list[str], *, min_chars: int = 4) -> bool:
    lowered = _normalize_query_text(raw)
    if not lowered or not re.search(r"[\u4e00-\u9fff]", lowered):
        return False
    for ref in refs:
        normalized_ref = _normalize_query_text(ref)
        if not normalized_ref or not re.search(r"[\u4e00-\u9fff]", normalized_ref):
            continue
        shorter, longer = sorted((lowered, normalized_ref), key=len)
        if len(shorter) < min_chars:
            continue
        max_len = min(len(shorter), 12)
        for size in range(max_len, min_chars - 1, -1):
            for start in range(0, len(shorter) - size + 1):
                fragment = shorter[start : start + size].strip()
                if len(fragment) < min_chars:
                    continue
                if fragment in longer:
                    return True
    return False


def _has_strong_reference_match(raw: str, refs: list[str], *, fs_target: str = "") -> bool:
    lowered = _normalize_query_text(raw)
    if not lowered:
        return False
    if lowered in set(task_plan_continuation_markers()):
        return False
    if fs_target and _raw_mentions_fs_target(lowered, fs_target):
        return True
    for ref in refs:
        normalized_ref = _normalize_query_text(ref)
        if not normalized_ref:
            continue
        if normalized_ref in lowered or lowered in normalized_ref:
            return True
        if goal_overlap(lowered, normalized_ref) >= 0.45:
            return True
    if _has_cjk_reference_fragment(lowered, refs):
        return True
    return False


def task_plan_continuation_markers() -> tuple[str, ...]:
    return (
        "continue",
        "resume",
        "follow up",
        "next",
        "keep going",
        "carry on",
        "\u7ee7\u7eed",
        "\u63a5\u7740",
        "\u7136\u540e",
        "\u8fd9\u4e2a\u4efb\u52a1",
        "\u8fd9\u4e2a\u9879\u76ee",
        "\u63a5\u4e0b\u6765",
        "\u5f80\u4e0b",
    )


def looks_like_task_plan_continuation(query: str) -> bool:
    raw = _normalize_query_text(query)
    if not raw:
        return False
    return any(raw.startswith(marker) for marker in task_plan_continuation_markers())


def looks_like_short_referential_followup(query: str) -> bool:
    raw = _normalize_query_text(query)
    if not raw or len(raw) > 24:
        return False
    referential_tokens = (
        "\u5b83",
        "\u8fd9\u4e2a",
        "\u90a3\u4e2a",
        "\u4e4b\u524d\u90a3\u4e2a",
        "\u521a\u624d\u90a3\u4e2a",
        "\u4e0a\u6b21\u90a3\u4e2a",
        "that",
        "it",
        "previous",
    )
    if not any(token in raw for token in referential_tokens):
        return False
    followup_markers = (
        "\u54ea",
        "\u54ea\u91cc",
        "\u5728\u54ea",
        "\u5728\u54ea\u513f",
        "\u600e\u4e48",
        "\u5417",
        "?",
        "where",
        "how",
        "what",
    )
    return any(marker in raw for marker in followup_markers)


def looks_like_long_referential_followup(query: str) -> bool:
    raw = _normalize_query_text(query)
    if not raw:
        return False
    referential_tokens = (
        "\u4e4b\u524d",
        "\u521a\u624d",
        "\u4e0a\u6b21",
        "\u90a3\u4e2a",
        "\u8fd9\u4e2a",
        "\u5b83",
        "that",
        "it",
        "previous",
    )
    if not any(token in raw for token in referential_tokens):
        return False
    followup_markers = (
        "\u5728\u54ea",
        "\u54ea\u91cc",
        "\u6587\u4ef6",
        "\u76ee\u5f55",
        "\u8def\u5f84",
        "\u4f4d\u7f6e",
        "where",
        "folder",
        "directory",
        "path",
    )
    return any(marker in raw for marker in followup_markers)


def looks_like_direct_task_resume_command(query: str) -> bool:
    raw = _normalize_query_text(query)
    if not raw:
        return False
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
        "\u8fd9\u4e2a",
        "\u90a3\u4e2a",
        "\u8fd9\u4e2a\u4efb\u52a1",
        "\u90a3\u4e2a\u4efb\u52a1",
        "\u8fd9\u4e2a\u9879\u76ee",
        "\u90a3\u4e2a\u9879\u76ee",
        "\u8fd9\u4e2a\u8ba1\u5212",
        "\u90a3\u4e2a\u8ba1\u5212",
        "\u4efb\u52a1",
        "\u9879\u76ee",
        "\u8ba1\u5212",
        "\u641e",
        "\u4e00\u4e0b",
        "\u4e0b",
        "\u6765",
        "\u505a",
        "\u5f04",
        "\u5904\u7406",
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
        "\u8fd9\u4e2a",
        "\u90a3\u4e2a",
        "\u4efb\u52a1",
        "\u9879\u76ee",
        "\u8ba1\u5212",
        "\u6b65\u9aa4",
        "\u6587\u4ef6",
        "\u76ee\u5f55",
        "\u8def\u5f84",
    )
    for marker in task_plan_continuation_markers():
        if not raw.startswith(marker):
            continue
        tail = raw[len(marker) :].strip(" ,.;:!?")
        if not tail:
            return False
        if tail in filler_tails:
            return True
        if any(token in tail for token in reference_tokens):
            return True
    return False


def infer_task_query_mode(
    query: str,
    *,
    goal: str = "",
    current_step: str = "",
    current_step_status: str = "",
    recent_progress: str = "",
    blocker: str = "",
    fs_target: str = "",
    phase: str = "",
    task_status: str = "",
    last_ref: str = "",
    latest_event_summary: str = "",
    runtime_status: str = "",
    next_action: str = "",
    verification_status: str = "",
    verification_detail: str = "",
) -> str:
    raw = str(query or "").strip()
    if not raw:
        return ""

    has_location = _contains_any_marker(raw, _LOCATION_QUERY_MARKERS)
    has_status = _contains_any_marker(raw, _STATUS_QUERY_MARKERS)
    has_verify = _contains_any_marker(raw, _VERIFY_QUERY_MARKERS)
    has_interrupt = _contains_any_marker(raw, _INTERRUPT_QUERY_MARKERS)
    has_blocker = _contains_any_marker(raw, _BLOCKER_QUERY_MARKERS)
    interrupted_state = (
        str(runtime_status or "").strip() == "interrupted"
        or str(next_action or "").strip() == "resume_or_close"
    )
    waiting_user_state = (
        str(current_step_status or "").strip() == "waiting_user"
        or str(runtime_status or "").strip() == "waiting_user"
        or str(next_action or "").strip() == "wait_for_user"
    )
    retry_ready_state = (
        str(runtime_status or "").strip() == "verify_failed"
        or str(next_action or "").strip() == "retry_or_close"
        or str(verification_status or "").strip() == "failed"
    )
    blocked_state = (
        str(task_status or "").strip() in _BLOCKED_TASK_STATUSES
        or str(current_step_status or "").strip() in _BLOCKED_STEP_STATUSES
        or str(phase or "").strip() == "blocked"
        or str(runtime_status or "").strip() in _BLOCKED_RUNTIME_STATUSES
        or bool(str(blocker or "").strip())
    )
    refs = [
        str(goal or "").strip(),
        str(current_step or "").strip(),
        str(recent_progress or "").strip(),
        str(last_ref or "").strip(),
        str(latest_event_summary or "").strip(),
    ]
    refs = [ref for ref in refs if ref]

    if waiting_user_state and looks_like_user_completion_update(raw):
        return "continue"
    if retry_ready_state and looks_like_retry_resume_request(raw):
        return "continue"
    if looks_like_direct_task_resume_command(raw):
        return "continue"
    if has_verify:
        return "verify"
    if has_interrupt and interrupted_state:
        return "interrupt"
    if has_blocker and blocked_state:
        return "blocker"
    if has_status:
        return "status"
    if _looks_like_direct_action_request(raw):
        return ""
    if has_location and (fs_target or looks_like_long_referential_followup(raw) or looks_like_short_referential_followup(raw)):
        return "locate"
    if looks_like_task_plan_continuation(raw):
        return "continue"
    if looks_like_long_referential_followup(raw) or looks_like_short_referential_followup(raw):
        if has_location and fs_target:
            return "locate"
        if has_blocker and blocked_state:
            return "blocker"
        if has_interrupt and interrupted_state:
            return "interrupt"
        if has_status:
            return "status"
        if has_verify:
            return "verify"
        if _looks_like_direct_action_request(raw):
            return ""
        return "reference"
    if _raw_mentions_fs_target(raw, fs_target):
        return "locate"
    if _has_strong_reference_match(raw, refs, fs_target=fs_target):
        return "reference"
    return ""


def query_clearly_refers_to_active_task(
    query: str,
    *,
    last_ref: str = "",
    goal: str = "",
    current_step: str = "",
    current_step_status: str = "",
    recent_progress: str = "",
    blocker: str = "",
    fs_target: str = "",
    phase: str = "",
    task_status: str = "",
    latest_event_summary: str = "",
    runtime_status: str = "",
    next_action: str = "",
    verification_status: str = "",
    verification_detail: str = "",
) -> bool:
    raw = str(query or "").strip()
    if not raw:
        return False

    refs = [
        str(goal or "").strip(),
        str(current_step or "").strip(),
        str(recent_progress or "").strip(),
        str(last_ref or "").strip(),
        str(latest_event_summary or "").strip(),
    ]
    refs = [item for item in refs if item]
    query_mode = infer_task_query_mode(
        raw,
        goal=goal,
        current_step=current_step,
        current_step_status=current_step_status,
        recent_progress=recent_progress,
        blocker=blocker,
        fs_target=fs_target,
        phase=phase,
        task_status=task_status,
        last_ref=last_ref,
        latest_event_summary=latest_event_summary,
        runtime_status=runtime_status,
        next_action=next_action,
        verification_status=verification_status,
        verification_detail=verification_detail,
    )
    interrupted_state = (
        str(runtime_status or "").strip() == "interrupted"
        or str(next_action or "").strip() == "resume_or_close"
    )
    waiting_user_state = (
        str(current_step_status or "").strip() == "waiting_user"
        or str(runtime_status or "").strip() == "waiting_user"
        or str(next_action or "").strip() == "wait_for_user"
    )
    retry_ready_state = (
        str(runtime_status or "").strip() == "verify_failed"
        or str(next_action or "").strip() == "retry_or_close"
        or str(verification_status or "").strip() == "failed"
    )
    blocked_state = (
        str(task_status or "").strip() in _BLOCKED_TASK_STATUSES
        or str(current_step_status or "").strip() in _BLOCKED_STEP_STATUSES
        or str(phase or "").strip() == "blocked"
        or str(runtime_status or "").strip() in _BLOCKED_RUNTIME_STATUSES
    )
    strong_ref_match = _has_strong_reference_match(raw, refs, fs_target=fs_target)
    has_state_anchor = bool(goal or current_step or recent_progress or blocker or fs_target or phase or last_ref or latest_event_summary)

    if not has_state_anchor:
        return False

    if query_mode == "continue":
        if waiting_user_state and looks_like_user_completion_update(raw):
            return True
        if retry_ready_state and looks_like_retry_resume_request(raw):
            return True
        if blocked_state:
            return strong_ref_match and not looks_like_direct_task_resume_command(raw)
        if looks_like_direct_task_resume_command(raw):
            return True
        return strong_ref_match

    if query_mode == "locate":
        return bool(
            fs_target
            or strong_ref_match
            or (
                (looks_like_short_referential_followup(raw) or looks_like_long_referential_followup(raw))
                and bool(goal or current_step or last_ref or recent_progress)
            )
        )

    if query_mode == "status":
        return bool(
            current_step
            or recent_progress
            or phase
            or blocker
            or latest_event_summary
            or runtime_status
            or strong_ref_match
        )

    if query_mode == "verify":
        return bool(
            verification_status
            or verification_detail
            or phase
            or recent_progress
            or latest_event_summary
            or strong_ref_match
        )

    if query_mode == "interrupt":
        return bool(
            interrupted_state
            or runtime_status
            or next_action
            or latest_event_summary
            or recent_progress
            or strong_ref_match
        )

    if query_mode == "blocker":
        return bool(blocked_state or blocker or strong_ref_match)

    if query_mode == "reference":
        return strong_ref_match and bool(current_step or goal or last_ref or fs_target)

    if blocked_state and not strong_ref_match:
        return False
    return strong_ref_match and bool(current_step or goal or last_ref)


def resolve_task_for_goal(kind: str, user_input: str, *, get_latest_active_task_by_kind):
    raw = str(user_input or "").strip()
    active = get_latest_active_task_by_kind(kind)
    if not active:
        return None

    title = str(active.get("title") or (active.get("input") or {}).get("query") or "").strip()
    stage = str(active.get("stage") or "").strip()
    status = str(active.get("status") or "").strip()
    memory = active.get("memory") if isinstance(active.get("memory"), dict) else {}
    last_ref = str(memory.get("last_user_reference") or "").strip()
    refs = [ref for ref in [title, stage, last_ref] if ref]
    query_mode = infer_task_query_mode(
        raw,
        goal=title,
        current_step=stage,
        task_status=status,
        last_ref=last_ref,
    )
    strong_ref_match = _has_strong_reference_match(raw, refs)

    if query_mode == "continue":
        if status in _BLOCKED_TASK_STATUSES:
            return None
        if looks_like_direct_task_resume_command(raw) or strong_ref_match:
            return active
        return None
    if query_mode == "reference" and strong_ref_match:
        return active
    if not query_mode and strong_ref_match:
        return active
    return None
