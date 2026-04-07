from __future__ import annotations


_STRING_META_FIELDS = (
    "step_key",
    "phase",
    "reason_kind",
    "goal",
    "decision_note",
    "handoff_note",
    "expected_output",
    "next_user_need",
    "tool_name",
    "parallel_group_id",
)
_INT_META_FIELDS = (
    "parallel_size",
    "parallel_index",
    "parallel_completed_count",
    "parallel_success_count",
    "parallel_failure_count",
)
_LIST_META_FIELDS = ("parallel_tools",)


def _is_thinking_label(value: str) -> bool:
    text = str(value or "").strip().lower()
    return text in {"thinking", "\u6a21\u578b\u601d\u8003"}


def _merge_normalized_steps(existing: dict, incoming: dict) -> dict:
    merged = dict(existing)
    for field in ("label", "detail", "status"):
        value = incoming.get(field)
        if str(value or "").strip():
            merged[field] = value
    for field in _STRING_META_FIELDS + _INT_META_FIELDS + _LIST_META_FIELDS:
        value = incoming.get(field)
        if value not in (None, "", [], 0):
            merged[field] = value
    return merged


def normalize_persisted_process_steps(steps: list | None) -> list[dict]:
    rows: list[dict] = []
    merge_index_by_key: dict[str, int] = {}

    for item in steps or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        detail = str(item.get("detail") or "").strip()
        status = str(item.get("status") or "").strip().lower()
        if status not in {"done", "error", "running"}:
            continue
        if status == "running" and not _is_thinking_label(label):
            continue
        if not label and not detail:
            continue

        row = {
            "label": label,
            "detail": detail,
            "status": "error" if status == "error" else "done",
        }
        for field in _STRING_META_FIELDS:
            value = str(item.get(field) or "").strip()
            if value:
                row[field] = value
        for field in _INT_META_FIELDS:
            try:
                value = int(item.get(field) or 0)
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                row[field] = value
        for field in _LIST_META_FIELDS:
            values = [
                str(entry or "").strip()
                for entry in (item.get(field) or [])
                if str(entry or "").strip()
            ]
            if values:
                row[field] = values

        merge_key = (
            str(row.get("step_key") or "").strip()
            or str(row.get("parallel_group_id") or "").strip()
            or ("thinking:decision" if _is_thinking_label(label) else "")
        )
        if merge_key and merge_key in merge_index_by_key:
            rows[merge_index_by_key[merge_key]] = _merge_normalized_steps(
                rows[merge_index_by_key[merge_key]],
                row,
            )
            continue

        if rows and rows[-1] == row:
            continue

        rows.append(row)
        if merge_key:
            merge_index_by_key[merge_key] = len(rows) - 1

    return rows


def trim_persisted_process_steps_for_stream_reset(
    steps: list | None,
    *,
    keep_prefix_count: int = 0,
) -> list[dict]:
    normalized = normalize_persisted_process_steps(steps)
    keep_count = max(0, int(keep_prefix_count))
    if keep_count <= 0:
        return []
    return normalized[: min(len(normalized), keep_count)]


def normalize_process_payload(process: dict | None) -> dict | None:
    if not isinstance(process, dict):
        return None
    normalized = dict(process)
    normalized_steps = normalize_persisted_process_steps(process.get("steps"))
    if normalized_steps:
        normalized["steps"] = normalized_steps
    else:
        normalized.pop("steps", None)
    return normalized or None
