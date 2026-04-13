from __future__ import annotations

import argparse
import copy
import json
import sys
from collections.abc import Iterable as IterableABC
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
FIXTURE_CASES_FILE = ROOT_DIR / "tests" / "fixtures" / "live_llm_replay_cases.json"
FIXTURE_SUITES_FILE = ROOT_DIR / "tests" / "fixtures" / "live_llm_eval_suites.json"
BACKGROUND_DIALOGUE_ONLY_GUIDANCE = (
    "The dialogue context in this turn is background only. "
    "The current user prompt does not include the explicit task continuity block, "
    "so previous dialogue does not grant permission to resume a task or call tools. "
    "Ask a brief clarification instead of executing tools."
)
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import brain
import core.reply_formatter as reply_formatter_module
import core.task_store as task_store_module
import core.tool_adapter as tool_adapter_module
from core.skills import get_all_skills, get_exposed_skills
from routes.chat_run_helpers import apply_runtime_state_to_task_plan


@dataclass(frozen=True)
class ReplayCase:
    case_id: str
    description: str
    query: str
    seed_kind: str
    goal: str = ""
    fs_target: str = ""
    expect_active_context: bool = False
    expected_query_mode: str = ""
    expect_tool_call: bool | None = None
    expected_reply_any: tuple[str, ...] = ()
    expected_tool_any: tuple[str, ...] = ()
    dialogue_context: str = ""
    preset_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvalSuite:
    suite_id: str
    description: str
    preset_ids: tuple[str, ...] = ()
    case_ids: tuple[str, ...] = ()
    strict_by_default: bool = True


@dataclass
class _InMemoryTaskData:
    projects: list[dict]
    tasks: list[dict]
    relations: list[dict]

    def __init__(self):
        self.projects = []
        self.tasks = []
        self.relations = []

    def load_task_projects(self):
        return copy.deepcopy(self.projects)

    def save_task_projects(self, data):
        self.projects = copy.deepcopy(data)

    def load_tasks(self):
        return copy.deepcopy(self.tasks)

    def save_tasks(self, data):
        self.tasks = copy.deepcopy(data)

    def load_task_relations(self):
        return copy.deepcopy(self.relations)

    def save_task_relations(self, data):
        self.relations = copy.deepcopy(data)

    def load_content_projects(self):
        return []


class _ReplayRuntime:
    def __init__(self):
        self.data = _InMemoryTaskData()
        self.patches = [
            patch.object(task_store_module, "load_task_projects", side_effect=self.data.load_task_projects),
            patch.object(task_store_module, "save_task_projects", side_effect=self.data.save_task_projects),
            patch.object(task_store_module, "load_tasks", side_effect=self.data.load_tasks),
            patch.object(task_store_module, "save_tasks", side_effect=self.data.save_tasks),
            patch.object(task_store_module, "load_task_relations", side_effect=self.data.load_task_relations),
            patch.object(task_store_module, "save_task_relations", side_effect=self.data.save_task_relations),
            patch.object(task_store_module, "load_content_projects", side_effect=self.data.load_content_projects),
        ]

    def __enter__(self):
        for item in self.patches:
            item.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        for item in reversed(self.patches):
            item.stop()
        return False

    def save_open_plan(self, *, goal: str, fs_target: str = "") -> dict:
        _task, snapshot = task_store_module.save_task_plan_snapshot(
            goal,
            {
                "goal": goal,
                "summary": "正在推进当前任务",
                "items": [
                    {"id": "inspect", "title": "检查当前目标", "status": "done"},
                    {"id": "work", "title": "继续处理当前步骤", "status": "running"},
                ],
                "current_item_id": "work",
                "phase": "work",
            },
        )
        if fs_target:
            task_store_module.remember_fs_target_for_task_plan(
                snapshot,
                {"path": fs_target, "option": "inspect", "source": "tool_runtime"},
            )
        return snapshot

    def save_waiting_user_plan(self) -> dict:
        snapshot = self.save_open_plan(goal="继续处理抖音登录后的采集")
        return apply_runtime_state_to_task_plan(
            snapshot,
            meta={
                "runtime_state": {
                    "status": "waiting_user",
                    "next_action": "wait_for_user",
                    "blocker": "需要你先完成抖音登录",
                    "fs_target": {"path": "https://www.douyin.com", "kind": "url"},
                },
                "verification": {
                    "verified": False,
                    "detail": "需要你先完成抖音登录",
                },
            },
            tool_used="open_target",
            tool_response="Login required",
        )

    def save_verify_failed_plan(self) -> dict:
        _task, snapshot = task_store_module.save_task_plan_snapshot(
            "继续修 AaronCore continuity",
            {
                "goal": "继续修 AaronCore continuity",
                "summary": "验证还没通过",
                "items": [
                    {"id": "inspect", "title": "检查 continuity 链路", "status": "done"},
                    {"id": "verify", "title": "验证修复结果", "status": "running"},
                ],
                "current_item_id": "verify",
                "phase": "verify",
                "runtime_status": "verify_failed",
                "next_action": "retry_or_close",
                "verification": {
                    "verified": False,
                    "detail": "continuity 还会被一句闲聊误续接",
                },
            },
        )
        return snapshot

    def save_interrupted_plan(self, *, goal: str, fs_target: str = "") -> dict:
        snapshot = self.save_open_plan(goal=goal, fs_target=fs_target)
        return apply_runtime_state_to_task_plan(
            snapshot,
            meta={
                "runtime_state": {
                    "status": "interrupted",
                    "next_action": "resume_or_close",
                    "blocker": "sense_environment interrupted before the folder check completed",
                    "fs_target": {"path": fs_target or "C:/Users/36459/Desktop", "kind": "directory"},
                },
            },
            tool_used="sense_environment",
            tool_response="sense_environment interrupted",
        )


_REPLAY_CASES = (
    ReplayCase(
        case_id="unrelated_small_talk",
        description="闲聊不能误续接活跃任务",
        query="明天要不要打伞啊",
        seed_kind="open_plan",
        goal="继续整理桌面文件",
        fs_target="C:/Users/36459/Desktop",
        expect_active_context=False,
        expected_query_mode="",
        expect_tool_call=None,
    ),
    ReplayCase(
        case_id="bare_continue_waiting_user",
        description="waiting_user 不能被 bare continue 误续接",
        query="继续",
        seed_kind="waiting_user",
        expect_active_context=False,
        expected_query_mode="",
        expect_tool_call=False,
    ),
    ReplayCase(
        case_id="topic_switch_waiting_user",
        description="User topic switch should detach even if a waiting_user task is still hanging",
        query="哈哈 这首歌还挺好听",
        seed_kind="waiting_user",
        expect_active_context=False,
        expected_query_mode="",
        expect_tool_call=False,
    ),
    ReplayCase(
        case_id="blocker_question",
        description="阻塞问句要先答 blocker",
        query="需要我做什么",
        seed_kind="waiting_user",
        expect_active_context=True,
        expected_query_mode="blocker",
        expect_tool_call=False,
        expected_reply_any=("登录", "抖音", "login"),
    ),
    ReplayCase(
        case_id="verify_question",
        description="验证问句要先答 verify 状态",
        query="验证了吗",
        seed_kind="verify_failed",
        expect_active_context=True,
        expected_query_mode="verify",
        expect_tool_call=False,
        expected_reply_any=("验证", "没通过", "未通过", "失败", "failed"),
    ),
    ReplayCase(
        case_id="status_question",
        description="进度问句要先答当前状态",
        query="现在到哪了",
        seed_kind="open_plan",
        goal="继续整理 AaronCore 项目",
        fs_target="C:/Users/36459/AaronCore",
        expect_active_context=True,
        expected_query_mode="status",
        expect_tool_call=False,
        expected_reply_any=("整理", "进度", "步骤", "当前"),
    ),
    ReplayCase(
        case_id="locate_question",
        description="定位问句要先答 fs_target",
        query="那个项目在哪",
        seed_kind="open_plan",
        goal="继续完善 NovaNotes",
        fs_target="C:/Users/36459/NovaNotes/templates/index.html",
        expect_active_context=True,
        expected_query_mode="locate",
        expect_tool_call=False,
        expected_reply_any=("NovaNotes", "index.html", "路径", "位置"),
    ),
    ReplayCase(
        case_id="interrupt_question",
        description="Interrupted run should be explained before any new tool call",
        query="what interrupted it just now",
        seed_kind="interrupted",
        goal="Inspect desktop folders",
        fs_target="C:/Users/36459/Desktop",
        expect_active_context=True,
        expected_query_mode="interrupt",
        expect_tool_call=False,
        expected_reply_any=("中断", "interrupted", "interrupt"),
    ),
    ReplayCase(
        case_id="resume_after_interrupt",
        description="Explicit resume after interruption should keep execution bias",
        query="continue the interrupted task",
        seed_kind="interrupted",
        goal="Inspect desktop folders",
        fs_target="C:/Users/36459/Desktop",
        expect_active_context=True,
        expected_query_mode="continue",
        expect_tool_call=True,
        expected_tool_any=("folder_explore",),
    ),
    ReplayCase(
        case_id="retry_request_with_known_target",
        description="重试动作请求要保留执行倾向",
        query="再试试看 能看到桌面的文件夹吗",
        seed_kind="open_plan",
        goal="看下桌面的文件夹有哪些",
        fs_target="C:/Users/36459/Desktop",
        expect_active_context=True,
        expected_query_mode="",
        expect_tool_call=True,
        expected_tool_any=("folder_explore",),
    ),
    ReplayCase(
        case_id="explicit_path_action",
        description="显式路径动作请求不能塌成 locate",
        query=r"C:/Users/36459/Desktop/切格瓦拉 这个文件 你去看下",
        seed_kind="open_plan",
        goal="看下桌面的文件夹有哪些",
        fs_target="C:/Users/36459/Desktop",
        expect_active_context=True,
        expected_query_mode="",
        expect_tool_call=True,
    ),
)


_REPLAY_PRESETS = {
    "runtime_guardrails": (
        "unrelated_small_talk",
        "bare_continue_waiting_user",
        "topic_switch_waiting_user",
        "blocker_question",
        "verify_question",
        "status_question",
        "locate_question",
        "interrupt_question",
        "resume_after_interrupt",
        "retry_request_with_known_target",
        "explicit_path_action",
    ),
    "recorded_runtime_guardrails": (),
    "full_runtime_guardrails": (
        "unrelated_small_talk",
        "bare_continue_waiting_user",
        "topic_switch_waiting_user",
        "blocker_question",
        "verify_question",
        "status_question",
        "locate_question",
        "interrupt_question",
        "resume_after_interrupt",
        "retry_request_with_known_target",
        "explicit_path_action",
    ),
}


_EVAL_SUITES = (
    EvalSuite(
        suite_id="runtime_guardrails",
        description="Built-in runtime guardrails dry-run/live replay evals.",
        preset_ids=("runtime_guardrails",),
    ),
    EvalSuite(
        suite_id="recorded_runtime_guardrails",
        description="Recorded regression traces layered on top of runtime guardrails.",
        preset_ids=("recorded_runtime_guardrails",),
    ),
    EvalSuite(
        suite_id="full_runtime_guardrails",
        description="Full runtime guardrails, including built-in and recorded regression cases.",
        preset_ids=("full_runtime_guardrails",),
    ),
)


def _coerce_str_tuple(value) -> tuple[str, ...]:
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, IterableABC):
        items = []
        for item in value:
            text = str(item or "").strip()
            if text:
                items.append(text)
        return tuple(items)
    return ()


def _coerce_bool_or_none(value) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise ValueError(f"Unsupported boolean-like value: {value!r}")


def _coerce_bool(value, *, default: bool = False) -> bool:
    if value is None or value == "":
        return bool(default)
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise ValueError(f"Unsupported boolean-like value: {value!r}")


def _replay_case_from_dict(raw: dict) -> ReplayCase:
    case_id = str(raw.get("case_id") or "").strip()
    query = str(raw.get("query") or "").strip()
    seed_kind = str(raw.get("seed_kind") or "").strip()
    if not case_id or not query or not seed_kind:
        raise ValueError(f"Replay fixture must define case_id/query/seed_kind: {raw!r}")
    return ReplayCase(
        case_id=case_id,
        description=str(raw.get("description") or case_id).strip(),
        query=query,
        seed_kind=seed_kind,
        goal=str(raw.get("goal") or "").strip(),
        fs_target=str(raw.get("fs_target") or "").strip(),
        expect_active_context=bool(raw.get("expect_active_context")),
        expected_query_mode=str(raw.get("expected_query_mode") or "").strip(),
        expect_tool_call=_coerce_bool_or_none(raw.get("expect_tool_call")),
        expected_reply_any=_coerce_str_tuple(raw.get("expected_reply_any")),
        expected_tool_any=_coerce_str_tuple(raw.get("expected_tool_any")),
        dialogue_context=str(raw.get("dialogue_context") or "").strip(),
        preset_ids=_coerce_str_tuple(raw.get("preset_ids")),
    )


def _eval_suite_from_dict(raw: dict) -> EvalSuite:
    suite_id = str(raw.get("suite_id") or "").strip()
    if not suite_id:
        raise ValueError(f"Eval suite must define suite_id: {raw!r}")
    return EvalSuite(
        suite_id=suite_id,
        description=str(raw.get("description") or suite_id).strip(),
        preset_ids=_coerce_str_tuple(raw.get("preset_ids")),
        case_ids=_coerce_str_tuple(raw.get("case_ids")),
        strict_by_default=_coerce_bool(raw.get("strict_by_default"), default=True),
    )


@lru_cache(maxsize=1)
def _load_external_replay_cases() -> tuple[ReplayCase, ...]:
    if not FIXTURE_CASES_FILE.exists():
        return ()
    payload = json.loads(FIXTURE_CASES_FILE.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Replay fixture file must contain a list: {FIXTURE_CASES_FILE}")

    builtin_ids = {item.case_id for item in _REPLAY_CASES}
    external_cases: list[ReplayCase] = []
    seen_ids = set(builtin_ids)
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError(f"Replay fixture entries must be objects: {item!r}")
        case = _replay_case_from_dict(item)
        if case.case_id in seen_ids:
            raise ValueError(f"Duplicate replay case id: {case.case_id}")
        seen_ids.add(case.case_id)
        external_cases.append(case)
    return tuple(external_cases)


@lru_cache(maxsize=1)
def _load_external_eval_suites() -> tuple[EvalSuite, ...]:
    if not FIXTURE_SUITES_FILE.exists():
        return ()
    payload = json.loads(FIXTURE_SUITES_FILE.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Eval suite fixture file must contain a list: {FIXTURE_SUITES_FILE}")

    builtin_ids = {item.suite_id for item in _EVAL_SUITES}
    external_suites: list[EvalSuite] = []
    seen_ids = set(builtin_ids)
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError(f"Eval suite entries must be objects: {item!r}")
        suite = _eval_suite_from_dict(item)
        if suite.suite_id in seen_ids:
            raise ValueError(f"Duplicate eval suite id: {suite.suite_id}")
        seen_ids.add(suite.suite_id)
        external_suites.append(suite)
    return tuple(external_suites)


def get_replay_cases() -> list[ReplayCase]:
    return [*list(_REPLAY_CASES), *list(_load_external_replay_cases())]


def get_replay_case(case_id: str) -> ReplayCase:
    for item in get_replay_cases():
        if item.case_id == case_id:
            return item
    raise KeyError(case_id)


def get_replay_presets() -> dict[str, tuple[str, ...]]:
    merged: dict[str, list[str]] = {
        name: list(case_ids)
        for name, case_ids in _REPLAY_PRESETS.items()
    }
    for case in _load_external_replay_cases():
        for preset_id in case.preset_ids:
            merged.setdefault(preset_id, []).append(case.case_id)
    return {
        name: tuple(dict.fromkeys(case_ids))
        for name, case_ids in merged.items()
    }


def get_eval_suites() -> list[EvalSuite]:
    return [*list(_EVAL_SUITES), *list(_load_external_eval_suites())]


def get_eval_suite(suite_id: str) -> EvalSuite:
    wanted = str(suite_id or "").strip()
    for item in get_eval_suites():
        if item.suite_id == wanted:
            return item
    raise KeyError(suite_id)


def suite_defaults_to_strict(suite_ids: Iterable[str] | None = None) -> bool:
    for suite_name in [str(item or "").strip() for item in suite_ids or () if str(item or "").strip()]:
        if get_eval_suite(suite_name).strict_by_default:
            return True
    return False


def select_replay_cases(
    case_ids: Iterable[str] | None = None,
    preset_ids: Iterable[str] | None = None,
    suite_ids: Iterable[str] | None = None,
) -> list[ReplayCase]:
    all_cases = get_replay_cases()
    presets = get_replay_presets()
    wanted = {str(item or "").strip() for item in case_ids or () if str(item or "").strip()}
    preset_names = [str(item or "").strip() for item in preset_ids or () if str(item or "").strip()]
    for preset_name in preset_names:
        preset_cases = presets.get(preset_name)
        if not preset_cases:
            raise KeyError(f"Unknown replay preset: {preset_name}")
        wanted.update(preset_cases)
    for suite_name in [str(item or "").strip() for item in suite_ids or () if str(item or "").strip()]:
        suite = get_eval_suite(suite_name)
        wanted.update(suite.case_ids)
        for preset_name in suite.preset_ids:
            preset_cases = presets.get(preset_name)
            if not preset_cases:
                raise KeyError(f"Unknown replay preset referenced by suite {suite_name}: {preset_name}")
            wanted.update(preset_cases)
    if not wanted:
        return all_cases
    return [item for item in all_cases if item.case_id in wanted]


def _seed_case(runtime: _ReplayRuntime, case: ReplayCase) -> None:
    if case.seed_kind == "open_plan":
        runtime.save_open_plan(goal=case.goal, fs_target=case.fs_target)
        return
    if case.seed_kind == "waiting_user":
        runtime.save_waiting_user_plan()
        return
    if case.seed_kind == "verify_failed":
        runtime.save_verify_failed_plan()
        return
    if case.seed_kind == "interrupted":
        runtime.save_interrupted_plan(goal=case.goal, fs_target=case.fs_target)
        return
    raise ValueError(f"Unknown seed_kind: {case.seed_kind}")


def _build_bundle(query: str, *, model_name: str, cod_mode: bool, dialogue_context: str = "") -> dict:
    return {
        "user_input": query,
        "current_model": model_name,
        "dialogue_context": str(dialogue_context or ""),
        "search_context": "",
        "recall_context": "",
        "flashback_hint": "",
        "l1": [],
        "l2": {},
        "l2_memories": [],
        "l3": {},
        "l4": {},
        "l5": {},
        "l5_success_paths": [],
        "l7": [],
        "l8": [],
        "cod_mode": cod_mode,
    }


def _preview_text(text: str, *, limit: int = 220) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _extract_tool_call_names(tool_calls) -> list[str]:
    names: list[str] = []
    for item in tool_calls or []:
        if not isinstance(item, dict):
            continue
        function_block = item.get("function") if isinstance(item.get("function"), dict) else {}
        name = str(function_block.get("name") or item.get("name") or "").strip()
        if name:
            names.append(name)
    return names


def _normalize_match_text(text: str) -> str:
    return " ".join(str(text or "").replace("\\", "/").lower().split())


def _match_reply_markers(reply_text: str, markers: Iterable[str]) -> list[str]:
    normalized_reply = _normalize_match_text(reply_text)
    matched: list[str] = []
    for marker in markers or ():
        raw = str(marker or "").strip()
        if not raw:
            continue
        if _normalize_match_text(raw) in normalized_reply:
            matched.append(raw)
    return matched


def _match_expected_names(observed: Iterable[str], expected: Iterable[str]) -> list[str]:
    observed_map = {
        _normalize_match_text(item): str(item or "").strip()
        for item in observed or ()
        if str(item or "").strip()
    }
    matched: list[str] = []
    for item in expected or ():
        raw = str(item or "").strip()
        if not raw:
            continue
        normalized = _normalize_match_text(raw)
        if normalized in observed_map:
            matched.append(observed_map[normalized])
    return matched


def _score_reply_content(case: ReplayCase, reply_text: str) -> dict:
    markers = tuple(str(item or "").strip() for item in case.expected_reply_any if str(item or "").strip())
    if not markers:
        return {
            "reply_anchor_ok": None,
            "matched_reply_markers": [],
        }
    matched = _match_reply_markers(reply_text, markers)
    return {
        "reply_anchor_ok": bool(matched),
        "matched_reply_markers": matched,
    }


def _score_tool_names(case: ReplayCase, tool_names: Iterable[str]) -> dict:
    expected = tuple(str(item or "").strip() for item in case.expected_tool_any if str(item or "").strip())
    if not expected:
        return {
            "tool_name_ok": None,
            "matched_tool_names": [],
        }
    matched = _match_expected_names(tool_names, expected)
    return {
        "tool_name_ok": bool(matched),
        "matched_tool_names": matched,
    }


def _score_case(
    case: ReplayCase,
    *,
    active_context_used: bool,
    query_mode: str,
    has_tool_call: bool | None,
    resolved_tool_names: Iterable[str] = (),
    reply_text: str = "",
    check_reply_content: bool = True,
    check_tool_names: bool = True,
) -> dict:
    checks = {
        "active_context_ok": active_context_used == case.expect_active_context,
        "query_mode_ok": str(query_mode or "") == str(case.expected_query_mode or ""),
    }
    if case.expect_tool_call is None or has_tool_call is None:
        checks["tool_decision_ok"] = None
    else:
        checks["tool_decision_ok"] = bool(has_tool_call) == bool(case.expect_tool_call)
    if check_tool_names:
        checks.update(_score_tool_names(case, resolved_tool_names))
    else:
        checks.update(
            {
                "tool_name_ok": None,
                "matched_tool_names": [],
            }
        )
    if check_reply_content:
        checks.update(_score_reply_content(case, reply_text))
    else:
        checks.update(
            {
                "reply_anchor_ok": None,
                "matched_reply_markers": [],
            }
        )
    values = [value for value in checks.values() if isinstance(value, bool)]
    checks["pass"] = all(values) if values else True
    return checks


def _resolve_model_cfg(model_id: str = "") -> tuple[dict, str]:
    wanted = str(model_id or "").strip()
    if not wanted:
        return dict(brain.LLM_CONFIG), brain.get_current_model_name()
    cfg = brain.MODELS_CONFIG.get(wanted)
    if not isinstance(cfg, dict):
        raise ValueError(f"Unknown model: {wanted}")
    return dict(cfg), wanted


def _build_messages(bundle: dict) -> tuple[str, str, list[dict]]:
    system_prompt = (
        reply_formatter_module._build_cod_system_prompt(bundle)
        if bundle.get("cod_mode")
        else reply_formatter_module._build_tool_call_system_prompt(bundle)
    )
    user_prompt = reply_formatter_module._build_tool_call_user_prompt(bundle)
    dialogue_context = reply_formatter_module.render_dialogue_context(bundle.get("dialogue_context", ""))
    messages = [{"role": "system", "content": system_prompt}]
    if dialogue_context:
        messages.append({"role": "system", "content": f"对话增量提示：\n{dialogue_context}"})
    if dialogue_context and "任务连续性提示" not in user_prompt:
        messages.append({"role": "system", "content": BACKGROUND_DIALOGUE_ONLY_GUIDANCE})
    messages.append({"role": "user", "content": user_prompt})
    return system_prompt, user_prompt, messages


def run_replay_case(
    case: ReplayCase,
    *,
    model_id: str = "",
    cod_mode: bool = False,
    dry_run: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    timeout: int = 30,
    show_prompts: bool = False,
) -> dict:
    tool_adapter_module.init(get_all_skills=get_all_skills, get_exposed_skills=get_exposed_skills)
    cfg, resolved_model_id = _resolve_model_cfg(model_id)
    tools = tool_adapter_module.build_tools_list_cod() if cod_mode else tool_adapter_module.build_tools_list()

    with _ReplayRuntime() as runtime:
        _seed_case(runtime, case)

        bundle = _build_bundle(
            case.query,
            model_name=resolved_model_id,
            cod_mode=cod_mode,
            dialogue_context=case.dialogue_context,
        )
        active_task_context = reply_formatter_module._build_active_task_context(bundle)
        working_state = task_store_module.get_active_task_working_state(case.query) or {}
        resumed_snapshot = task_store_module.get_active_task_plan_snapshot(case.query)
        system_prompt, user_prompt, messages = _build_messages(bundle)

        report = {
            "case": asdict(case),
            "model": resolved_model_id,
            "cod_mode": bool(cod_mode),
            "tool_count": len(tools),
            "prompt": {
                "active_context_used": bool(active_task_context),
                "active_context_preview": _preview_text(active_task_context, limit=180),
                "dialogue_context_used": bool(bundle.get("dialogue_context")),
                "dialogue_context_preview": _preview_text(str(bundle.get("dialogue_context") or ""), limit=180),
                "user_prompt_preview": _preview_text(user_prompt, limit=220),
                "system_prompt_preview": _preview_text(system_prompt, limit=220),
                "query_mode": str(working_state.get("query_mode") or ""),
                "runtime_status": str(working_state.get("runtime_status") or ""),
                "current_step": str(working_state.get("current_step") or ""),
                "fs_target": str(working_state.get("fs_target") or ""),
                "resumed_task": bool(resumed_snapshot),
            },
            "llm": {
                "executed": False,
                "reply_preview": "",
                "raw_tool_calls": [],
                "resolved_tool_calls": [],
                "error": "",
            },
        }

        if show_prompts:
            report["prompt"]["user_prompt"] = user_prompt
            report["prompt"]["system_prompt"] = system_prompt

        if dry_run:
            report["checks"] = _score_case(
                case,
                active_context_used=bool(active_task_context),
                query_mode=str(working_state.get("query_mode") or ""),
                has_tool_call=None,
                resolved_tool_names=(),
                reply_text="",
                check_reply_content=False,
                check_tool_names=False,
            )
            return report

        result = brain.llm_call(
            cfg,
            messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        reply_text = str(result.get("content", "") or "")
        raw_tool_calls = result.get("tool_calls") if isinstance(result.get("tool_calls"), list) else []
        resolved_tool_calls = reply_formatter_module._resolve_tool_calls_from_result(
            result,
            bundle,
            mode="live_replay",
        ) or []
        resolved_tool_names = _extract_tool_call_names(resolved_tool_calls)
        report["llm"] = {
            "executed": True,
            "reply_preview": _preview_text(reply_text, limit=280),
            "raw_tool_calls": _extract_tool_call_names(raw_tool_calls),
            "resolved_tool_calls": resolved_tool_names,
            "usage": result.get("usage", {}),
            "error": str(result.get("error") or ""),
        }
        report["checks"] = _score_case(
            case,
            active_context_used=bool(active_task_context),
            query_mode=str(working_state.get("query_mode") or ""),
            has_tool_call=bool(resolved_tool_names),
            resolved_tool_names=resolved_tool_names,
            reply_text=reply_text,
            check_reply_content=True,
            check_tool_names=True,
        )
        return report


def run_replay_suite(
    *,
    case_ids: Iterable[str] | None = None,
    preset_ids: Iterable[str] | None = None,
    suite_ids: Iterable[str] | None = None,
    model_id: str = "",
    cod_mode: bool = False,
    dry_run: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    timeout: int = 30,
    show_prompts: bool = False,
) -> dict:
    selected_suite_ids = [str(item or "").strip() for item in suite_ids or () if str(item or "").strip()]
    cases = select_replay_cases(case_ids=case_ids, preset_ids=preset_ids, suite_ids=selected_suite_ids)
    results = [
        run_replay_case(
            item,
            model_id=model_id,
            cod_mode=cod_mode,
            dry_run=dry_run,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            show_prompts=show_prompts,
        )
        for item in cases
    ]
    passed = sum(1 for item in results if item.get("checks", {}).get("pass"))
    return {
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "dry_run": bool(dry_run),
            "model": model_id or brain.get_current_model_name(),
            "cod_mode": bool(cod_mode),
            "suite_ids": selected_suite_ids,
            "preset_ids": [str(item or "").strip() for item in preset_ids or () if str(item or "").strip()],
            "case_ids": [item.case_id for item in cases],
        },
        "results": results,
    }


def run_eval_suite(
    suite_ids: Iterable[str] | None = None,
    *,
    case_ids: Iterable[str] | None = None,
    preset_ids: Iterable[str] | None = None,
    model_id: str = "",
    cod_mode: bool = False,
    dry_run: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    timeout: int = 30,
    show_prompts: bool = False,
) -> dict:
    suite_names = [str(item or "").strip() for item in suite_ids or () if str(item or "").strip()]
    suite_meta = []
    for suite_name in suite_names:
        suite = get_eval_suite(suite_name)
        suite_meta.append(
            {
                "suite_id": suite.suite_id,
                "description": suite.description,
                "preset_ids": list(suite.preset_ids),
                "case_ids": list(suite.case_ids),
                "strict_by_default": bool(suite.strict_by_default),
            }
        )
    payload = run_replay_suite(
        case_ids=case_ids,
        preset_ids=preset_ids,
        suite_ids=suite_names,
        model_id=model_id,
        cod_mode=cod_mode,
        dry_run=dry_run,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        show_prompts=show_prompts,
    )
    payload.setdefault("summary", {})
    payload["summary"]["suite_strict_default"] = suite_defaults_to_strict(suite_names)
    payload["eval_suites"] = suite_meta
    return payload


def _parse_case_ids(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _parse_preset_ids(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _parse_suite_ids(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _emit_json(payload: object) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        safe = text.encode(encoding, errors="backslashreplace").decode(encoding, errors="strict")
        sys.stdout.write(f"{safe}\n")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run thin live replay evals against the current tool-call prompt and runtime state.",
    )
    parser.add_argument(
        "--case",
        dest="case_ids",
        default="",
        help="Comma-separated replay case ids. Omit to run all cases.",
    )
    parser.add_argument(
        "--list-cases",
        action="store_true",
        help="List available replay case ids and exit.",
    )
    parser.add_argument(
        "--preset",
        dest="preset_ids",
        default="",
        help="Comma-separated replay preset names.",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List available replay preset names and exit.",
    )
    parser.add_argument(
        "--suite",
        dest="suite_ids",
        default="",
        help="Comma-separated eval suite ids.",
    )
    parser.add_argument(
        "--list-suites",
        action="store_true",
        help="List available eval suite ids and exit.",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Optional model id from brain/llm_config.json.",
    )
    parser.add_argument(
        "--cod-mode",
        action="store_true",
        help="Use CoD tool schema and CoD system prompt.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build state and prompts only, without calling the live model.",
    )
    parser.add_argument(
        "--show-prompts",
        action="store_true",
        help="Include full system/user prompts in the JSON output.",
    )
    parser.add_argument("--temperature", type=float, default=0.7, help="LLM temperature.")
    parser.add_argument("--max-tokens", type=int, default=2000, help="LLM max_tokens.")
    parser.add_argument("--timeout", type=int, default=30, help="LLM timeout in seconds.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 when any checked case fails.",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="Disable strict-by-default behavior for selected eval suites.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    suite_ids = _parse_suite_ids(args.suite_ids)

    if args.list_cases:
        payload = [
            {
                "case_id": item.case_id,
                "description": item.description,
                "query": item.query,
            }
            for item in get_replay_cases()
        ]
        _emit_json(payload)
        return 0

    if args.list_presets:
        payload = [
            {
                "preset": name,
                "cases": list(case_ids),
            }
            for name, case_ids in get_replay_presets().items()
        ]
        _emit_json(payload)
        return 0

    if args.list_suites:
        payload = [
            {
                "suite_id": item.suite_id,
                "description": item.description,
                "preset_ids": list(item.preset_ids),
                "case_ids": list(item.case_ids),
                "strict_by_default": bool(item.strict_by_default),
            }
            for item in get_eval_suites()
        ]
        _emit_json(payload)
        return 0

    suite = run_eval_suite(
        suite_ids=suite_ids,
        case_ids=_parse_case_ids(args.case_ids),
        preset_ids=_parse_preset_ids(args.preset_ids),
        model_id=args.model,
        cod_mode=args.cod_mode,
        dry_run=args.dry_run,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
        show_prompts=args.show_prompts,
    )
    _emit_json(suite)
    failed = int(suite.get("summary", {}).get("failed", 0))
    strict_mode = bool(args.strict or (not args.no_strict and suite_defaults_to_strict(suite_ids)))
    if strict_mode and failed > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
