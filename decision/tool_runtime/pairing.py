from __future__ import annotations

from .events import synthesize_tool_failure_response
from .ledger import ToolCallRecord


def _tool_name_from_call(tool_call: dict | None) -> str:
    if not isinstance(tool_call, dict):
        return ""
    fn = tool_call.get("function")
    if not isinstance(fn, dict):
        return ""
    return str(fn.get("name") or "").strip()


def _unique_ordered_records(records: list[ToolCallRecord] | None) -> list[ToolCallRecord]:
    ordered: list[ToolCallRecord] = []
    seen: set[str] = set()
    for record in sorted(
        (item for item in (records or []) if isinstance(item, ToolCallRecord)),
        key=lambda item: (int(getattr(item, "order", 0) or 0), str(getattr(item, "call_id", "") or "")),
    ):
        call_id = str(getattr(record, "call_id", "") or "").strip()
        if not call_id or call_id in seen:
            continue
        ordered.append(record)
        seen.add(call_id)
    return ordered


def _copy_tool_message(message: dict, *, tool_call_id: str) -> dict:
    copied = dict(message)
    copied["role"] = "tool"
    copied["tool_call_id"] = str(tool_call_id or "").strip()
    return copied


def _pop_preferred_message(message_list: list[dict]) -> dict | None:
    if not message_list:
        return None
    best_index = 0
    best_score = (-1, -1)
    for index, message in enumerate(message_list):
        text = str(message.get("content") or "")
        score = (1 if text.strip() else 0, len(text))
        if score > best_score:
            best_index = index
            best_score = score
    return message_list.pop(best_index)


def _build_missing_tool_message(
    *,
    tool_call_id: str,
    tool_name: str,
    record: ToolCallRecord | None,
) -> dict:
    if isinstance(record, ToolCallRecord):
        content = str(record.response or "").strip()
        if not content:
            content = synthesize_tool_failure_response(
                record.tool_name or tool_name,
                record.reason or "tool_call_runtime_exception",
            )
    else:
        content = synthesize_tool_failure_response(
            tool_name,
            "tool_call_runtime_exception",
            detail="tool_result missing during tool history repair",
        )
    return {
        "role": "tool",
        "tool_call_id": str(tool_call_id or "").strip(),
        "content": content,
    }


def _fallback_tool_call_id(tool_name: str, position: int, used_ids: set[str]) -> str:
    stem = str(tool_name or "tool_call").strip() or "tool_call"
    candidate = f"{stem}_{max(1, int(position or 0))}"
    suffix = 2
    while candidate in used_ids:
        candidate = f"{stem}_{max(1, int(position or 0))}_{suffix}"
        suffix += 1
    return candidate


def repair_tool_batch_for_context(
    tool_calls: list[dict] | None,
    tool_messages: list[dict] | None,
    *,
    records: list[ToolCallRecord] | None = None,
) -> tuple[list[dict], list[dict], dict]:
    ordered_records = _unique_ordered_records(records)
    record_by_slot = {
        max(0, int(getattr(record, "order", 0) or 0)): record
        for record in ordered_records
    }

    keyed_messages: dict[str, list[dict]] = {}
    blank_id_messages: list[dict] = []
    non_tool_messages: list[dict] = []
    valid_tool_messages = 0
    for raw_message in tool_messages or []:
        if not isinstance(raw_message, dict):
            continue
        if raw_message.get("role") != "tool":
            non_tool_messages.append(dict(raw_message))
            continue
        valid_tool_messages += 1
        call_id = str(raw_message.get("tool_call_id") or "").strip()
        copied = dict(raw_message)
        if call_id:
            keyed_messages.setdefault(call_id, []).append(copied)
        else:
            blank_id_messages.append(copied)

    repaired_tool_calls: list[dict] = []
    repaired_tool_messages: list[dict] = []
    slot_descriptors: list[dict] = []
    used_ids: set[str] = set()
    rewritten_tool_call_ids = 0
    dropped_tool_calls = 0

    for index, raw_tool_call in enumerate(tool_calls or []):
        if not isinstance(raw_tool_call, dict):
            continue
        tool_call = dict(raw_tool_call)
        raw_call_id = str(tool_call.get("id") or "").strip()
        tool_name = _tool_name_from_call(tool_call)
        slot_record = record_by_slot.get(index)

        resolved_call_id = ""
        if raw_call_id and raw_call_id not in used_ids:
            resolved_call_id = raw_call_id
        elif slot_record:
            candidate = str(slot_record.call_id or "").strip()
            if candidate and candidate not in used_ids:
                resolved_call_id = candidate
        elif not raw_call_id:
            resolved_call_id = _fallback_tool_call_id(tool_name, index + 1, used_ids)

        if not resolved_call_id:
            dropped_tool_calls += 1
            continue

        if raw_call_id != resolved_call_id:
            rewritten_tool_call_ids += 1
        tool_call["id"] = resolved_call_id
        repaired_tool_calls.append(tool_call)
        slot_descriptors.append(
            {
                "raw_call_id": raw_call_id,
                "resolved_call_id": resolved_call_id,
                "tool_name": tool_name,
                "record": slot_record,
            }
        )
        used_ids.add(resolved_call_id)

    rewritten_tool_result_ids = 0
    synthesized_tool_results = 0
    for slot in slot_descriptors:
        resolved_call_id = slot["resolved_call_id"]
        raw_call_id = slot["raw_call_id"]
        tool_name = slot["tool_name"]
        record = slot["record"]

        message = _pop_preferred_message(keyed_messages.get(resolved_call_id, []))
        if message is None and raw_call_id and raw_call_id != resolved_call_id:
            message = _pop_preferred_message(keyed_messages.get(raw_call_id, []))
        if message is None and not raw_call_id and blank_id_messages:
            message = blank_id_messages.pop(0)

        if message is None:
            repaired_tool_messages.append(
                _build_missing_tool_message(
                    tool_call_id=resolved_call_id,
                    tool_name=tool_name,
                    record=record,
                )
            )
            synthesized_tool_results += 1
            continue

        if str(message.get("tool_call_id") or "").strip() != resolved_call_id:
            rewritten_tool_result_ids += 1
        repaired_tool_messages.append(_copy_tool_message(message, tool_call_id=resolved_call_id))

    orphan_tool_results = len(blank_id_messages)
    duplicate_tool_results = 0
    for bucket in keyed_messages.values():
        if bucket:
            orphan_tool_results += len(bucket)
            duplicate_tool_results += len(bucket)

    repaired_tool_messages.extend(non_tool_messages)
    repair_meta = {
        "rewritten_tool_call_ids": rewritten_tool_call_ids,
        "rewritten_tool_result_ids": rewritten_tool_result_ids,
        "synthesized_tool_results": synthesized_tool_results,
        "dropped_tool_calls": dropped_tool_calls,
        "dropped_tool_results": orphan_tool_results,
        "duplicate_tool_results": duplicate_tool_results,
        "repair_applied": any(
            (
                rewritten_tool_call_ids,
                rewritten_tool_result_ids,
                synthesized_tool_results,
                dropped_tool_calls,
                orphan_tool_results,
            )
        ),
        "original_tool_call_count": len([item for item in tool_calls or [] if isinstance(item, dict)]),
        "repaired_tool_call_count": len(repaired_tool_calls),
        "original_tool_result_count": valid_tool_messages,
        "repaired_tool_result_count": len([item for item in repaired_tool_messages if item.get("role") == "tool"]),
    }
    return repaired_tool_calls, repaired_tool_messages, repair_meta
