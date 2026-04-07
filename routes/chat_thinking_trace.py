from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

from routes.chat_trace_semantics import (
    append_thinking_text,
    normalize_thinking_trace_text,
    prefer_reason_note_for_tool,
)


@dataclass
class ChatThinkingTraceState:
    user_message: str
    segment_index: int = 1
    trace_sent: bool = False
    trace_text: str = ""
    trace_emitted: str = ""
    last_emit_at: float = 0.0
    reason_kind: str = "decision"
    goal: str = ""
    decision_note: str = ""
    handoff_note: str = ""
    expected_output: str = ""
    next_user_need: str = ""
    default_detail: str = ""
    pending_followup_segment: bool = False

    def __post_init__(self) -> None:
        self.reset()

    @property
    def step_key(self) -> str:
        if self.segment_index <= 1:
            return "thinking:decision"
        return f"thinking:decision:{self.segment_index}"

    def _build_default_detail(self) -> str:
        msg_short = self.user_message[:20] + ("..." if len(self.user_message) > 20 else "")
        if self.segment_index <= 1:
            return (
                f"\u6211\u5148\u7406\u89e3\u4f60\u8fd9\u53e5\u300c{msg_short}\u300d\uff0c"
                "\u5224\u65ad\u662f\u76f4\u63a5\u56de\u7b54\u8fd8\u662f\u5148\u8c03\u7528\u5de5\u5177\u3002"
            )
        return "\u6211\u5148\u63a5\u4f4f\u4e0a\u4e00\u6b65\u7ed3\u679c\uff0c\u5224\u65ad\u662f\u7ee7\u7eed\u8c03\u7528\u5de5\u5177\u8fd8\u662f\u6574\u7406\u6210\u6700\u7ec8\u56de\u7b54\u3002"

    def _reset_segment_state(self) -> None:
        self.default_detail = self._build_default_detail()
        self.trace_sent = False
        self.trace_text = ""
        self.trace_emitted = ""
        self.last_emit_at = 0.0
        self.reason_kind = "decision"
        self.goal = ""
        self.decision_note = self.default_detail
        self.handoff_note = ""
        self.expected_output = ""
        self.next_user_need = ""

    def reset(self) -> None:
        self.segment_index = 1
        self.pending_followup_segment = False
        self._reset_segment_state()

    def queue_followup_segment(self) -> None:
        self.pending_followup_segment = True

    def activate_pending_segment(self) -> bool:
        if not self.pending_followup_segment:
            return False
        self.segment_index += 1
        self.pending_followup_segment = False
        self._reset_segment_state()
        return True

    def update_meta(
        self,
        *,
        reason_kind: str = "",
        goal: str = "",
        decision_note: str = "",
        handoff_note: str = "",
        expected_output: str = "",
        next_user_need: str = "",
    ) -> None:
        if str(reason_kind or "").strip():
            self.reason_kind = str(reason_kind).strip()
        if str(goal or "").strip():
            self.goal = str(goal).strip()
        if str(decision_note or "").strip():
            self.decision_note = str(decision_note).strip()
        if str(handoff_note or "").strip():
            self.handoff_note = str(handoff_note).strip()
        if str(expected_output or "").strip():
            self.expected_output = str(expected_output).strip()
        if str(next_user_need or "").strip():
            self.next_user_need = str(next_user_need).strip()

    def append_text(self, incoming: str) -> None:
        self.trace_text = append_thinking_text(self.trace_text, incoming)

    def apply_preferred_reason_note(
        self,
        *,
        tool_name: str = "",
        preview: str = "",
        reason_note: str = "",
        action_summary: str = "",
    ) -> None:
        self.trace_text = prefer_reason_note_for_tool(
            self.trace_text or self.trace_emitted or self.default_detail,
            tool_name=tool_name,
            preview=preview,
            reason_note=reason_note,
            action_summary=action_summary,
            default_think_detail=self.default_detail,
        )

    async def emit_default(self, trace_callback) -> dict | None:
        if self.trace_sent:
            return None
        event = await trace_callback(
            "\u6a21\u578b\u601d\u8003",
            self.default_detail,
            "running",
            step_key=self.step_key,
            phase="thinking",
            reason_kind=self.reason_kind,
            decision_note=self.decision_note,
            expected_output=self.expected_output,
            next_user_need=self.next_user_need,
            full_detail=self.default_detail,
        )
        self.trace_sent = True
        return event

    async def emit(
        self,
        trace_callback,
        *,
        force: bool = False,
        tool_trace_started: bool = False,
    ) -> dict | None:
        detail = normalize_thinking_trace_text(self.trace_text) or self.decision_note or self.default_detail
        if not detail or detail == self.trace_emitted:
            return None
        now = asyncio.get_running_loop().time()
        if not force:
            changed = detail[len(self.trace_emitted):] if detail.startswith(self.trace_emitted) else detail
            if len(changed) < 24 and not re.search(r"[。！？!?；;：:]\s*$", changed) and (now - self.last_emit_at) < 0.35:
                return None
        self.trace_emitted = detail
        self.last_emit_at = now
        event = await trace_callback(
            "\u6a21\u578b\u601d\u8003",
            detail,
            "running",
            step_key=self.step_key,
            phase="thinking",
            reason_kind=self.reason_kind,
            goal=self.goal,
            decision_note=self.decision_note,
            handoff_note=self.handoff_note,
            expected_output=self.expected_output,
            next_user_need=self.next_user_need,
            full_detail=detail,
        )
        self.trace_sent = True
        return event
