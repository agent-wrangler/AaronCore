from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from capability_registry import get_skill


_SAFE_PARALLEL_EFFECT_LEVELS = {"read_only", "external_lookup"}
_SAFE_PARALLEL_PROTOCOL_SUBFAMILIES = {"filesystem_read", "live_data_query"}
_MAX_PARALLEL_BATCH_WORKERS = 4
_FALLBACK_TOOL_PROFILES = {
    "folder_explore": {
        "effect_level": "read_only",
        "operation_kind": "inspect",
        "protocol_subfamily": "filesystem_read",
        "capability_kind": "protocol_tool",
    },
    "read_file": {
        "effect_level": "read_only",
        "operation_kind": "inspect",
        "protocol_subfamily": "filesystem_read",
        "capability_kind": "memory_tool",
    },
    "list_files": {
        "effect_level": "read_only",
        "operation_kind": "inspect",
        "protocol_subfamily": "filesystem_read",
        "capability_kind": "memory_tool",
    },
    "search_text": {
        "effect_level": "read_only",
        "operation_kind": "inspect",
        "protocol_subfamily": "filesystem_read",
        "capability_kind": "protocol_tool",
    },
    "recall_memory": {
        "effect_level": "read_only",
        "operation_kind": "query",
        "protocol_subfamily": "memory_recall",
        "capability_kind": "memory_tool",
    },
    "query_knowledge": {
        "effect_level": "read_only",
        "operation_kind": "query",
        "protocol_subfamily": "memory_recall",
        "capability_kind": "memory_tool",
    },
    "web_search": {
        "effect_level": "external_lookup",
        "operation_kind": "query",
        "protocol_subfamily": "live_data_query",
        "capability_kind": "memory_tool",
    },
}


@dataclass(frozen=True)
class ParallelCallSpec:
    index: int
    tool_call: dict
    tool_name: str
    tool_args: dict
    preview: str
    record: object


@dataclass(frozen=True)
class ParallelExecutionResult:
    completion_order: list[str]
    results_by_call_id: dict[str, dict]


class ParallelToolExecutionError(RuntimeError):
    def __init__(
        self,
        *,
        call_id: str,
        tool_name: str,
        original_exception: Exception,
        completion_order: list[str],
        results_by_call_id: dict[str, dict],
    ) -> None:
        super().__init__(f"{tool_name or 'tool_call'} failed in parallel batch: {type(original_exception).__name__}: {original_exception}")
        self.call_id = str(call_id or "").strip()
        self.tool_name = str(tool_name or "").strip()
        self.original_exception = original_exception
        self.completion_order = list(completion_order or [])
        self.results_by_call_id = dict(results_by_call_id or {})


def get_tool_parallel_profile(tool_name: str) -> dict:
    name = str(tool_name or "").strip()
    if not name:
        return {}
    skill = get_skill(name)
    if isinstance(skill, dict):
        return {
            "effect_level": str(skill.get("effect_level") or "").strip().lower(),
            "operation_kind": str(skill.get("operation_kind") or "").strip().lower(),
            "protocol_subfamily": str(skill.get("protocol_subfamily") or "").strip().lower(),
            "capability_kind": str(skill.get("capability_kind") or "").strip().lower(),
        }
    return dict(_FALLBACK_TOOL_PROFILES.get(name, {}))


def is_parallel_safe_tool(tool_name: str) -> bool:
    profile = get_tool_parallel_profile(tool_name)
    effect_level = str(profile.get("effect_level") or "").strip().lower()
    protocol_subfamily = str(profile.get("protocol_subfamily") or "").strip().lower()
    capability_kind = str(profile.get("capability_kind") or "").strip().lower()
    if effect_level not in _SAFE_PARALLEL_EFFECT_LEVELS:
        return False
    if protocol_subfamily in _SAFE_PARALLEL_PROTOCOL_SUBFAMILIES:
        return True
    return capability_kind == "memory_tool"


def execute_parallel_tool_calls(
    prepared_calls: list[ParallelCallSpec],
    *,
    tool_executor,
    skill_context: dict,
) -> ParallelExecutionResult:
    if not prepared_calls:
        return ParallelExecutionResult(completion_order=[], results_by_call_id={})

    completion_order: list[str] = []
    results_by_call_id: dict[str, dict] = {}
    first_error: tuple[str, str, Exception] | None = None

    with ThreadPoolExecutor(max_workers=min(len(prepared_calls), _MAX_PARALLEL_BATCH_WORKERS)) as pool:
        future_map = {
            pool.submit(tool_executor, spec.tool_name, spec.tool_args, skill_context): spec
            for spec in prepared_calls
        }
        for future in as_completed(future_map):
            spec = future_map[future]
            call_id = str(getattr(spec.record, "call_id", "") or "").strip()
            try:
                result = future.result()
            except Exception as exc:  # pragma: no cover - production executor normalizes to dict
                if first_error is None:
                    first_error = (call_id, spec.tool_name, exc)
                continue
            completion_order.append(call_id)
            results_by_call_id[call_id] = result

    if first_error:
        call_id, tool_name, exc = first_error
        raise ParallelToolExecutionError(
            call_id=call_id,
            tool_name=tool_name,
            original_exception=exc,
            completion_order=completion_order,
            results_by_call_id=results_by_call_id,
        )

    return ParallelExecutionResult(
        completion_order=completion_order,
        results_by_call_id=results_by_call_id,
    )
