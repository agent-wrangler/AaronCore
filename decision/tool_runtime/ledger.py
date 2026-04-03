from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


_TERMINAL_STATUSES = {"completed", "synthetic_failed"}


@dataclass
class ToolCallRecord:
    call_id: str
    tool_name: str
    tool_args: dict = field(default_factory=dict)
    preview: str = ""
    status: str = "pending"
    success: bool | None = None
    response: str = ""
    action_summary: str = ""
    run_meta: dict = field(default_factory=dict)
    synthetic: bool = False
    reason: str = ""
    order: int = 0

    @property
    def is_terminal(self) -> bool:
        return self.status in _TERMINAL_STATUSES


class ToolCallTurnLedger:
    def __init__(self) -> None:
        self._records: list[ToolCallRecord] = []
        self._by_id: dict[str, ToolCallRecord] = {}

    def register(
        self,
        tool_call: dict | None,
        *,
        tool_name: str,
        tool_args: dict | None = None,
        preview: str = "",
    ) -> ToolCallRecord:
        call_id = ""
        if isinstance(tool_call, dict):
            call_id = str(tool_call.get("id") or "").strip()
        if not call_id:
            call_id = f"{tool_name or 'tool_call'}_{len(self._records) + 1}"

        existing = self._by_id.get(call_id)
        if existing:
            if tool_name:
                existing.tool_name = tool_name
            if isinstance(tool_args, dict) and tool_args:
                existing.tool_args = dict(tool_args)
            if preview:
                existing.preview = preview
            return existing

        record = ToolCallRecord(
            call_id=call_id,
            tool_name=tool_name,
            tool_args=dict(tool_args or {}),
            preview=str(preview or "").strip(),
            order=len(self._records),
        )
        self._records.append(record)
        self._by_id[call_id] = record
        return record

    def has_records(self) -> bool:
        return bool(self._records)

    def has_unfinished(self) -> bool:
        return any(not record.is_terminal for record in self._records)

    def latest_terminal(self) -> ToolCallRecord | None:
        for record in reversed(self._records):
            if record.is_terminal:
                return record
        return None

    def latest_record(self) -> ToolCallRecord | None:
        if not self._records:
            return None
        return self._records[-1]

    def records(self) -> list[ToolCallRecord]:
        return list(self._records)

    def terminal_records(self) -> list[ToolCallRecord]:
        return [record for record in self._records if record.is_terminal]

    def get(self, call_id: str) -> ToolCallRecord | None:
        return self._by_id.get(str(call_id or "").strip())

    def mark_executing(self, call_id: str) -> ToolCallRecord | None:
        record = self.get(call_id)
        if record and not record.is_terminal:
            record.status = "executing"
        return record

    def mark_terminal(
        self,
        call_id: str,
        *,
        success: bool,
        response: str = "",
        action_summary: str = "",
        run_meta: dict | None = None,
        synthetic: bool = False,
        reason: str = "",
    ) -> ToolCallRecord | None:
        record = self.get(call_id)
        if not record:
            return None
        record.status = "synthetic_failed" if synthetic else "completed"
        record.success = bool(success)
        record.response = str(response or "").strip()
        record.action_summary = str(action_summary or "").strip()
        record.run_meta = dict(run_meta or {})
        record.synthetic = bool(synthetic)
        record.reason = str(reason or "").strip()
        return record

    def flush_unfinished(
        self,
        *,
        reason: str,
        response_factory: Callable[[ToolCallRecord], str] | None = None,
        action_summary_factory: Callable[[ToolCallRecord], str] | None = None,
        run_meta_factory: Callable[[ToolCallRecord], dict] | None = None,
    ) -> list[ToolCallRecord]:
        flushed: list[ToolCallRecord] = []
        for record in self._records:
            if record.is_terminal:
                continue
            response = response_factory(record) if callable(response_factory) else record.response
            action_summary = (
                action_summary_factory(record)
                if callable(action_summary_factory)
                else record.action_summary
            )
            run_meta = run_meta_factory(record) if callable(run_meta_factory) else record.run_meta
            terminal = self.mark_terminal(
                record.call_id,
                success=False,
                response=response,
                action_summary=action_summary,
                run_meta=run_meta,
                synthetic=True,
                reason=reason,
            )
            if terminal:
                flushed.append(terminal)
        return flushed
