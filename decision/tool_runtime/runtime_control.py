from __future__ import annotations

import threading
import time


class ToolRuntimeInterrupted(RuntimeError):
    def __init__(self, *, reason: str = "user_interrupted", detail: str = "") -> None:
        self.reason = str(reason or "user_interrupted").strip() or "user_interrupted"
        self.detail = str(detail or "").strip()
        super().__init__(self.detail or self.reason)


class ToolRuntimeControl:
    def __init__(self) -> None:
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()
        self._reason = ""
        self._detail = ""

    def cancel(self, *, reason: str = "user_interrupted", detail: str = "") -> None:
        normalized_reason = str(reason or "user_interrupted").strip() or "user_interrupted"
        normalized_detail = str(detail or "").strip()
        with self._lock:
            if not self._reason:
                self._reason = normalized_reason
            if normalized_detail and not self._detail:
                self._detail = normalized_detail
            self._cancel_event.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def detail(self) -> str:
        return self._detail


def create_tool_runtime_control() -> ToolRuntimeControl:
    return ToolRuntimeControl()


def get_tool_runtime_control(*sources) -> ToolRuntimeControl | None:
    for source in sources:
        if isinstance(source, ToolRuntimeControl):
            return source
        if isinstance(source, dict):
            control = source.get("tool_runtime_control")
            if isinstance(control, ToolRuntimeControl):
                return control
    return None


def request_tool_runtime_cancel(
    *sources,
    reason: str = "user_interrupted",
    detail: str = "",
) -> bool:
    control = get_tool_runtime_control(*sources)
    if not control:
        return False
    control.cancel(reason=reason, detail=detail)
    return True


def tool_runtime_cancelled(*sources) -> bool:
    control = get_tool_runtime_control(*sources)
    return bool(control and control.cancelled)


def tool_runtime_cancel_reason(*sources) -> str:
    control = get_tool_runtime_control(*sources)
    return str(control.reason if control else "").strip()


def tool_runtime_cancel_detail(*sources) -> str:
    control = get_tool_runtime_control(*sources)
    return str(control.detail if control else "").strip()


def raise_if_cancelled(*sources, detail: str = "") -> None:
    control = get_tool_runtime_control(*sources)
    if not control or not control.cancelled:
        return
    resolved_detail = str(detail or control.detail or "").strip()
    raise ToolRuntimeInterrupted(
        reason=control.reason or "user_interrupted",
        detail=resolved_detail,
    )


def cooperative_sleep(
    seconds: float,
    *sources,
    detail: str = "",
    poll_interval: float = 0.1,
) -> None:
    duration = max(0.0, float(seconds or 0.0))
    if duration <= 0:
        raise_if_cancelled(*sources, detail=detail)
        return

    deadline = time.monotonic() + duration
    while True:
        raise_if_cancelled(*sources, detail=detail)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(max(0.01, float(poll_interval or 0.1)), remaining))
    raise_if_cancelled(*sources, detail=detail)


def build_interrupted_tool_result(
    tool_name: str,
    *,
    reason: str = "user_interrupted",
    detail: str = "",
) -> dict:
    from decision.tool_runtime.events import synthesize_tool_failure_response

    normalized_reason = str(reason or "user_interrupted").strip() or "user_interrupted"
    response = synthesize_tool_failure_response(tool_name, normalized_reason, detail=detail)
    return {
        "success": False,
        "error": response,
        "response": response,
        "skill": tool_name,
        "reason": normalized_reason,
        "synthetic": True,
        "meta": {},
    }
