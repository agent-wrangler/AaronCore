from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field


_TOOL_STEP_LABELS = {
    "调用技能",
    "技能完成",
    "技能失败",
    "联网搜索",
    "搜索完成",
    "搜索失败",
    "检索记忆",
    "检索失败",
    "记忆就绪",
}


def _clean_text(value: object) -> str:
    return str(value or "").strip()


@dataclass
class ChatTraceState:
    collected_steps: list[dict] = field(default_factory=list)
    last_progress_label: str = ""
    last_progress_detail: str = ""
    last_progress_step_key: str = ""
    last_progress_status: str = ""
    last_progress_at: float = 0.0
    last_wait_event_at: float = 0.0
    step_key_counts: dict[str, int] = field(default_factory=dict)
    active_tool_step_key: str = ""
    active_tool_name: str = ""

    def __post_init__(self) -> None:
        self.last_progress_at = asyncio.get_running_loop().time()

    def _slugify_step_part(self, value: str, fallback: str = "step") -> str:
        text = re.sub(r"[^a-z0-9]+", "_", _clean_text(value).lower()).strip("_")
        return text or fallback

    def _next_step_key(self, prefix: str, hint: str) -> str:
        base = f"{self._slugify_step_part(prefix, 'step')}:{self._slugify_step_part(hint, 'step')}"
        count = self.step_key_counts.get(base, 0) + 1
        self.step_key_counts[base] = count
        return base if count == 1 else f"{base}:{count}"

    def _build_parallel_tool_step_key(
        self,
        *,
        parallel_group_id: str,
        parallel_index: int = 0,
        tool_name: str = "",
        label: str = "",
    ) -> str:
        base = _clean_text(parallel_group_id) or "parallel:group"
        index_part = ""
        if int(parallel_index or 0) > 0:
            index_part = f":{int(parallel_index)}"
        hint = self._slugify_step_part(tool_name or label or "tool", "tool")
        return f"{base}{index_part}:{hint}"

    def _looks_like_tool_label(self, label: str) -> bool:
        return _clean_text(label) in _TOOL_STEP_LABELS

    def _infer_step_phase(self, label: str, *, explicit_phase: str = "", tool_name: str = "") -> str:
        phase = _clean_text(explicit_phase).lower()
        if phase:
            return phase
        text = _clean_text(label)
        if text in {"模型思考", "thinking"}:
            return "thinking"
        if text in {"等待", "waiting"}:
            return "waiting"
        if tool_name or self._looks_like_tool_label(text):
            return "tool"
        return "info"

    def build_step_payload(
        self,
        *,
        label: str,
        detail: str,
        status: str = "running",
        step_key: str = "",
        phase: str = "",
        full_detail: str = "",
        reason_kind: str = "",
        goal: str = "",
        decision_note: str = "",
        handoff_note: str = "",
        expected_output: str = "",
        next_user_need: str = "",
        tool_name: str = "",
        parallel_group_id: str = "",
        parallel_index: int = 0,
        parallel_size: int = 0,
        parallel_completed_count: int = 0,
        parallel_success_count: int = 0,
        parallel_failure_count: int = 0,
        parallel_tools: list[str] | None = None,
    ) -> dict:
        clean_label = _clean_text(label)
        clean_detail = _clean_text(detail)
        clean_status = _clean_text(status).lower() or "running"
        clean_phase = self._infer_step_phase(clean_label, explicit_phase=phase, tool_name=tool_name)
        clean_tool_name = _clean_text(tool_name)
        clean_step_key = _clean_text(step_key)
        clean_full_detail = _clean_text(full_detail) or clean_detail
        clean_decision_note = _clean_text(decision_note)
        clean_handoff_note = _clean_text(handoff_note)
        clean_goal = _clean_text(goal)
        clean_expected_output = _clean_text(expected_output)
        clean_next_user_need = _clean_text(next_user_need)
        clean_reason_kind = _clean_text(reason_kind)
        clean_parallel_group_id = _clean_text(parallel_group_id)
        try:
            clean_parallel_index = max(0, int(parallel_index or 0))
        except (TypeError, ValueError):
            clean_parallel_index = 0
        try:
            clean_parallel_size = max(0, int(parallel_size or 0))
        except (TypeError, ValueError):
            clean_parallel_size = 0
        try:
            clean_parallel_completed_count = max(0, int(parallel_completed_count or 0))
        except (TypeError, ValueError):
            clean_parallel_completed_count = 0
        try:
            clean_parallel_success_count = max(0, int(parallel_success_count or 0))
        except (TypeError, ValueError):
            clean_parallel_success_count = 0
        try:
            clean_parallel_failure_count = max(0, int(parallel_failure_count or 0))
        except (TypeError, ValueError):
            clean_parallel_failure_count = 0
        clean_parallel_tools = [
            _clean_text(name)
            for name in (parallel_tools or [])
            if _clean_text(name)
        ]
        if not clean_step_key:
            if clean_phase == "thinking":
                clean_step_key = "thinking:decision"
            elif clean_phase == "waiting":
                clean_step_key = self.last_progress_step_key or "thinking:decision"
            elif clean_phase == "tool":
                if clean_parallel_group_id and clean_parallel_size > 1:
                    clean_step_key = self._build_parallel_tool_step_key(
                        parallel_group_id=clean_parallel_group_id,
                        parallel_index=clean_parallel_index,
                        tool_name=clean_tool_name,
                        label=clean_label,
                    )
                elif clean_status == "running" or not self.active_tool_step_key:
                    clean_step_key = self._next_step_key("tool", clean_tool_name or clean_label or "tool")
                else:
                    clean_step_key = self.active_tool_step_key
            else:
                clean_step_key = self._next_step_key(clean_phase or "info", clean_label or "step")
        payload = {
            "label": clean_label,
            "detail": clean_detail,
            "status": "error" if clean_status == "error" else ("running" if clean_status == "running" else "done"),
            "step_key": clean_step_key,
            "phase": clean_phase,
            "full_detail": clean_full_detail,
        }
        optional_fields = {
            "reason_kind": clean_reason_kind,
            "goal": clean_goal,
            "decision_note": clean_decision_note,
            "handoff_note": clean_handoff_note,
            "expected_output": clean_expected_output,
            "next_user_need": clean_next_user_need,
            "tool_name": clean_tool_name,
            "parallel_group_id": clean_parallel_group_id,
        }
        for field_name, value in optional_fields.items():
            if value:
                payload[field_name] = value
        if clean_parallel_index > 0:
            payload["parallel_index"] = clean_parallel_index
        if clean_parallel_size > 0:
            payload["parallel_size"] = clean_parallel_size
        if clean_parallel_completed_count > 0:
            payload["parallel_completed_count"] = clean_parallel_completed_count
        if clean_parallel_success_count > 0:
            payload["parallel_success_count"] = clean_parallel_success_count
        if clean_parallel_failure_count > 0:
            payload["parallel_failure_count"] = clean_parallel_failure_count
        if clean_parallel_tools:
            payload["parallel_tools"] = clean_parallel_tools
        return payload

    async def trace(
        self,
        label,
        detail,
        status="running",
        *,
        step_key: str = "",
        phase: str = "",
        full_detail: str = "",
        reason_kind: str = "",
        goal: str = "",
        decision_note: str = "",
        handoff_note: str = "",
        expected_output: str = "",
        next_user_need: str = "",
        tool_name: str = "",
        parallel_group_id: str = "",
        parallel_index: int = 0,
        parallel_size: int = 0,
        parallel_completed_count: int = 0,
        parallel_success_count: int = 0,
        parallel_failure_count: int = 0,
        parallel_tools: list[str] | None = None,
    ) -> dict:
        payload = self.build_step_payload(
            label=label,
            detail=detail,
            status=status,
            step_key=step_key,
            phase=phase,
            full_detail=full_detail,
            reason_kind=reason_kind,
            goal=goal,
            decision_note=decision_note,
            handoff_note=handoff_note,
            expected_output=expected_output,
            next_user_need=next_user_need,
            tool_name=tool_name,
            parallel_group_id=parallel_group_id,
            parallel_index=parallel_index,
            parallel_size=parallel_size,
            parallel_completed_count=parallel_completed_count,
            parallel_success_count=parallel_success_count,
            parallel_failure_count=parallel_failure_count,
            parallel_tools=parallel_tools,
        )
        self.collected_steps.append(dict(payload))
        self.last_progress_status = payload.get("status", "")
        if self.last_progress_status == "running":
            self.last_progress_label = payload.get("label", "")
            self.last_progress_detail = payload.get("detail", "")
            self.last_progress_step_key = payload.get("step_key", "")
        else:
            self.last_progress_label = ""
            self.last_progress_detail = ""
            self.last_progress_step_key = ""
        self.last_progress_at = asyncio.get_running_loop().time()
        self.last_wait_event_at = 0.0
        if payload.get("phase") == "tool":
            self.active_tool_name = payload.get("tool_name") or self.active_tool_name
            self.active_tool_step_key = payload.get("step_key") or self.active_tool_step_key
            if payload.get("status") != "running":
                self.active_tool_name = ""
                self.active_tool_step_key = ""
        return {"event": "trace", "data": json.dumps(payload, ensure_ascii=False)}

    async def agent_step(
        self,
        phase,
        detail="",
        label="",
        waited_seconds=0,
        *,
        step_key: str = "",
        reason_kind: str = "",
        goal: str = "",
        decision_note: str = "",
        handoff_note: str = "",
        expected_output: str = "",
        next_user_need: str = "",
        tool_name: str = "",
    ) -> dict:
        self.last_wait_event_at = asyncio.get_running_loop().time()
        payload = self.build_step_payload(
            label=label,
            detail=detail,
            status="running",
            step_key=step_key or (
                self.last_progress_step_key
                if (_clean_text(phase).lower() == "waiting" and self.last_progress_status == "running")
                else ""
            ),
            phase=phase,
            full_detail=detail,
            reason_kind=reason_kind,
            goal=goal,
            decision_note=decision_note,
            handoff_note=handoff_note,
            expected_output=expected_output,
            next_user_need=next_user_need,
            tool_name=tool_name,
        )
        payload["phase"] = _clean_text(phase).lower() or payload.get("phase", "")
        if waited_seconds:
            payload["waited_seconds"] = int(waited_seconds)
        return {"event": "agent_step", "data": json.dumps(payload, ensure_ascii=False)}

    def build_waiting_step(self, waited_seconds: float, *, tool_active: bool = False, streamed: bool = False) -> tuple[str, str]:
        waited = max(1, int(waited_seconds))
        if tool_active:
            label = self.last_progress_label or "调用技能"
            base_detail = self.last_progress_detail or "正在等待工具执行结果"
        else:
            label = "模型思考"
            base_detail = self.last_progress_detail or (
                "正在等待模型继续输出" if streamed else "正在继续分析下一步动作"
            )
        return label, f"{base_detail} {waited}s"

    def note_activity(self) -> None:
        self.last_progress_at = asyncio.get_running_loop().time()
        self.last_wait_event_at = 0.0

    def reset_progress_tracking(self) -> None:
        self.last_progress_label = ""
        self.last_progress_detail = ""
        self.last_progress_step_key = ""
        self.last_progress_status = ""
        self.step_key_counts = {}
        self.active_tool_step_key = ""
        self.active_tool_name = ""

    def replace_collected_steps(self, steps: list[dict] | None) -> None:
        self.collected_steps = list(steps or [])
