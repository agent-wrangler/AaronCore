from __future__ import annotations

from .ledger import ToolCallRecord
from .process_meta import build_runtime_payload, extract_record_runtime_state


def synthesize_tool_failure_response(
    tool_name: str,
    reason: str,
    *,
    detail: str = "",
) -> str:
    label = str(tool_name or "tool_call").strip() or "tool_call"
    templates = {
        "stream_signal_dropped": f"{label} 没有完成：模型已经发出了工具请求，但这一轮没有得到匹配的完成结果。",
        "tool_executor_exception": f"{label} 没有完成：工具执行阶段发生异常，中途断在运行时。",
        "tool_call_runtime_exception": f"{label} 没有完成：tool_call 运行时在收尾前中断。",
        "user_interrupted": f"{label} 没有完成：当前工具调用被中断。",
        "blocked_by_user_takeover": f"{label} 没有完成：同轮前序动作已经卡在需要用户接手的步骤上，这个动作被终止。",
    }
    base = templates.get(reason, f"{label} 没有完成：这一轮工具调用没有形成完整闭环。")
    extra = str(detail or "").strip()
    if extra:
        return f"{base}\n\n{extra}"
    return base


def build_tool_call_executing_event(record: ToolCallRecord, *, process_meta: dict | None = None) -> dict:
    return {
        "_tool_call": {
            "id": record.call_id,
            "name": record.tool_name,
            "executing": True,
            "preview": record.preview,
            "process_meta": dict(process_meta or {}),
        }
    }


def build_tool_call_done_event(record: ToolCallRecord, *, process_meta: dict | None = None) -> dict:
    payload = {
        "id": record.call_id,
        "name": record.tool_name,
        "done": True,
        "success": bool(record.success),
        "response": str(record.response or "")[:200],
        "preview": record.preview,
        "action_summary": record.action_summary,
        "run_meta": record.run_meta if isinstance(record.run_meta, dict) else {},
        "synthetic": bool(record.synthetic),
        "reason": record.reason,
        "process_meta": dict(process_meta or {}),
    }
    payload.update(build_runtime_payload(record))
    return {"_tool_call": payload}


def build_tool_turn_done_event(
    record: ToolCallRecord | None,
    usage: dict | None,
    *,
    records: list[ToolCallRecord] | None = None,
    turn_meta: dict | None = None,
) -> dict:
    batch_records = [item for item in (records or ([record] if record else [])) if isinstance(item, ToolCallRecord)]
    runtime_state = extract_record_runtime_state(record) if record else {}
    event = {
        "_done": True,
        "usage": usage or {},
        "tool_used": record.tool_name if record else None,
        "action_summary": record.action_summary if record else "",
        "run_meta": record.run_meta if record and isinstance(record.run_meta, dict) else {},
        "success": record.success if record else None,
        "tool_response": record.response if record else "",
        "call_id": record.call_id if record else "",
        "synthetic": bool(record.synthetic) if record else False,
        "reason": record.reason if record else "",
        "tools_used": [item.tool_name for item in batch_records if item.tool_name],
        "action_count": len(batch_records),
        "batch_mode": len(batch_records) > 1,
        "tool_results": [
            {
                "call_id": item.call_id,
                "name": item.tool_name,
                "success": item.success,
                "synthetic": bool(item.synthetic),
                "reason": item.reason,
                **build_runtime_payload(item),
            }
            for item in batch_records
        ],
    }
    if runtime_state:
        event.update(build_runtime_payload(record))
    if isinstance(turn_meta, dict):
        event.update(turn_meta)
    return event
