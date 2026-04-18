"""Chat- and task-context assembly helpers for reply construction."""

from __future__ import annotations

from collections.abc import Callable

from core import task_store as _task_store
from storage.history_store import is_transient_assistant_notice


def build_l1_messages(
    bundle: dict,
    *,
    clean_visible_reply_text: Callable[[str], str] | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Convert recent L1 dialogue into alternating user/assistant messages."""
    l1 = bundle.get("l1") or []
    if not l1:
        return []

    recent = l1 if limit is None else l1[-(int(limit) * 2) :]
    messages: list[dict] = []
    for item in recent:
        if not isinstance(item, dict):
            continue
        if is_transient_assistant_notice(item):
            continue
        role = item.get("role", "")
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            api_role = "user"
        elif role in ("nova", "assistant"):
            api_role = "assistant"
        else:
            continue
        if api_role == "assistant" and clean_visible_reply_text:
            content = clean_visible_reply_text(content)
            if not content:
                continue
        if len(content) > 800:
            content = content[:800] + "…"
        if messages and messages[-1]["role"] == api_role:
            messages[-1]["content"] += "\n" + content
        else:
            messages.append({"role": api_role, "content": content})

    current_input = str(bundle.get("user_input") or "").strip()
    if current_input and messages and messages[-1]["role"] == "user":
        last_content = messages[-1]["content"].strip()
        if last_content == current_input or current_input in last_content:
            messages = messages[:-1]

    return messages


def build_recent_dialogue_text(
    bundle: dict,
    *,
    clean_visible_reply_text: Callable[[str], str] | None = None,
    limit: int | None = None,
) -> str:
    """Render recent dialogue into a compact prompt-ready text block."""
    messages = build_l1_messages(
        bundle,
        clean_visible_reply_text=clean_visible_reply_text,
        limit=limit,
    )
    if not messages:
        return ""

    lines: list[str] = []
    visible_messages = messages if limit is None else messages[-limit:]
    for item in visible_messages:
        role = "用户" if item.get("role") == "user" else "Nova"
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        if len(content) > 180:
            content = content[:180] + "…"
        lines.append(f"{role}：{content}")
    return "\n".join(lines)


def resolve_active_task_plan(bundle: dict) -> dict:
    query = str(bundle.get("user_input") or "").strip()
    if not query:
        return bundle.get("task_plan") if isinstance(bundle.get("task_plan"), dict) else {}
    try:
        inferred = _task_store.get_active_task_plan_snapshot(query)
    except Exception:
        inferred = None
    if isinstance(inferred, dict) and inferred:
        bundle["task_plan"] = inferred
        return inferred
    bundle.pop("task_plan", None)
    return {}


def load_latest_structured_fs_target() -> str:
    try:
        target = _task_store.get_latest_structured_fs_target()
    except Exception:
        target = None
    if not isinstance(target, dict):
        return ""
    return str(target.get("path") or "").strip()


def load_task_plan_fs_target(bundle: dict) -> str:
    task_plan = resolve_active_task_plan(bundle)
    if not task_plan:
        return ""
    try:
        target = _task_store.get_structured_fs_target_for_task_plan(task_plan)
    except Exception:
        target = None
    if not isinstance(target, dict):
        return ""
    return str(target.get("path") or "").strip()


def load_context_fs_target(bundle: dict) -> str:
    context_data = bundle.get("context_data") if isinstance(bundle.get("context_data"), dict) else {}
    fs_target = context_data.get("fs_target") if isinstance(context_data.get("fs_target"), dict) else {}
    return str(fs_target.get("path") or "").strip()


def resolve_active_working_state(
    bundle: dict,
    *,
    load_task_plan_fs_target: Callable[[dict], str] | None = None,
    load_context_fs_target: Callable[[dict], str] | None = None,
) -> dict:
    query = str(bundle.get("user_input") or "").strip()
    l2_session = bundle.get("l2") if isinstance(bundle.get("l2"), dict) else {}
    working_state = l2_session.get("working_state") if isinstance(l2_session.get("working_state"), dict) else {}
    if not query:
        return working_state

    preferred_fs_target = ""
    if load_task_plan_fs_target:
        try:
            preferred_fs_target = str(load_task_plan_fs_target(bundle) or "").strip()
        except Exception:
            preferred_fs_target = ""
    if not preferred_fs_target and load_context_fs_target:
        try:
            preferred_fs_target = str(load_context_fs_target(bundle) or "").strip()
        except Exception:
            preferred_fs_target = ""

    try:
        inferred = _task_store.get_active_task_working_state(
            query,
            preferred_fs_target=preferred_fs_target,
        )
    except Exception:
        inferred = None
    if isinstance(inferred, dict) and inferred:
        if isinstance(l2_session, dict):
            updated_l2 = dict(l2_session)
            updated_l2["working_state"] = inferred
            bundle["l2"] = updated_l2
        return inferred
    if working_state and isinstance(l2_session, dict):
        updated_l2 = dict(l2_session)
        updated_l2.pop("working_state", None)
        bundle["l2"] = updated_l2
    return {}


def build_session_context_text(l2_session: dict) -> str:
    if not isinstance(l2_session, dict):
        return ""

    parts: list[str] = []
    topics = [str(topic).strip() for topic in (l2_session.get("topics") or []) if str(topic).strip()]
    if topics and topics != ["闲聊"]:
        parts.append(f"当前话题：{'、'.join(topics[:4])}")

    mood = str(l2_session.get("mood") or "").strip()
    if mood:
        parts.append(f"用户情绪：{mood}")

    intent = str(l2_session.get("intent") or "").strip()
    if intent and intent != "闲聊":
        parts.append(f"会话意图：{intent}")

    user_state = str(l2_session.get("user_state") or "").strip()
    if user_state:
        parts.append(f"用户状态：{user_state}")

    working_state = l2_session.get("working_state") if isinstance(l2_session.get("working_state"), dict) else {}
    if working_state:
        goal = str(working_state.get("goal") or "").strip()
        current_step = str(working_state.get("current_step") or "").strip()
        current_step_task = working_state.get("current_step_task") if isinstance(working_state.get("current_step_task"), dict) else {}
        working_summary = str(l2_session.get("working_summary") or working_state.get("summary") or "").strip()
        recent_progress = str(working_state.get("recent_progress") or "").strip()
        blocker = str(working_state.get("blocker") or "").strip()
        next_step = str(working_state.get("next_step") or "").strip()
        fs_target = str(working_state.get("fs_target") or "").strip()
        last_tool = str(working_state.get("last_tool") or "").strip()
        last_action_summary = str(working_state.get("last_action_summary") or "").strip()
        last_result_summary = str(working_state.get("last_result_summary") or "").strip()
        execution_lane = str(working_state.get("execution_lane") or "").strip()
        attempt_kind = str(working_state.get("attempt_kind") or "").strip()
        previous_tool = str(working_state.get("previous_tool") or "").strip()
        parallel_tools = [
            str(name or "").strip()
            for name in (working_state.get("parallel_tools") or [])
            if str(name or "").strip()
        ]
        try:
            parallel_size = int(working_state.get("parallel_size") or 0)
        except Exception:
            parallel_size = 0
        if parallel_size <= 0:
            parallel_size = len(parallel_tools)
        if goal:
            parts.append(f"当前工作目标：{goal}")
        if current_step:
            parts.append(f"当前步骤：{current_step}")
        if working_summary and working_summary not in {goal, current_step}:
            parts.append(f"工作摘要：{working_summary}")
        if recent_progress and recent_progress != current_step:
            parts.append(f"最近进展：{recent_progress}")
        if last_tool:
            parts.append(f"最近工具：{last_tool}")
        if last_action_summary and last_action_summary not in {working_summary, recent_progress, current_step}:
            parts.append(f"最近操作：{last_action_summary}")
        if last_result_summary and last_result_summary not in {last_action_summary, working_summary, blocker}:
            parts.append(f"最近结果：{last_result_summary}")
        if execution_lane:
            parts.append(f"当前执行车道：{execution_lane}")
        if attempt_kind:
            parts.append(f"最近尝试类型：{attempt_kind}")
        if previous_tool and previous_tool != last_tool:
            parts.append(f"上一个工具：{previous_tool}")
        if parallel_tools and parallel_size > 1:
            parts.append(f"最近并行工具：{', '.join(parallel_tools[:4])}")
        if str(current_step_task.get("status") or "").strip():
            parts.append(f"当前步骤子任务状态：{str(current_step_task.get('status') or '').strip()}")
        if str(current_step_task.get("runtime_status") or "").strip():
            parts.append(f"当前步骤执行态：{str(current_step_task.get('runtime_status') or '').strip()}")
        if blocker:
            parts.append(f"当前阻塞：{blocker}")
        if next_step and next_step != current_step:
            parts.append(f"默认下一步：{next_step}")
        if fs_target:
            parts.append(f"当前目标路径：{fs_target}")

    return "\n".join(parts)


def build_active_task_context(
    bundle: dict,
    *,
    recent_attempts: list[dict] | None = None,
    load_task_plan_fs_target: Callable[[dict], str] | None = None,
    load_context_fs_target: Callable[[dict], str] | None = None,
    build_fs_focus_guidance: Callable[[dict | None, dict | None], str] | None = None,
) -> str:
    task_plan = resolve_active_task_plan(bundle)
    working_state = resolve_active_working_state(
        bundle,
        load_task_plan_fs_target=load_task_plan_fs_target,
        load_context_fs_target=load_context_fs_target,
    )
    if not task_plan and not working_state:
        return ""

    goal = str(
        (working_state.get("goal") if working_state else "")
        or task_plan.get("goal")
        or bundle.get("user_input")
        or ""
    ).strip()
    if not goal:
        return ""

    lines = [f"Current task goal in this turn: {goal}"]
    items = task_plan.get("items") if isinstance(task_plan.get("items"), list) else []

    phase = str((working_state.get("phase") if working_state else "") or task_plan.get("phase") or "").strip()
    summary = str((working_state.get("summary") if working_state else "") or task_plan.get("summary") or "").strip()
    query_mode = str((working_state.get("query_mode") if working_state else "") or "").strip()
    current_item_id = str(
        (working_state.get("current_item_id") if working_state else "")
        or task_plan.get("current_item_id")
        or ""
    ).strip()
    current_step = str((working_state.get("current_step") if working_state else "") or "").strip()
    recent_progress = str((working_state.get("recent_progress") if working_state else "") or "").strip()
    blocker = str((working_state.get("blocker") if working_state else "") or "").strip()
    next_step = str((working_state.get("next_step") if working_state else "") or "").strip()
    runtime_status = str((working_state.get("runtime_status") if working_state else "") or "").strip()
    verification_status = str((working_state.get("verification_status") if working_state else "") or "").strip()
    verification_detail = str((working_state.get("verification_detail") if working_state else "") or "").strip()
    last_tool = str((working_state.get("last_tool") if working_state else "") or "").strip()
    last_action_summary = str((working_state.get("last_action_summary") if working_state else "") or "").strip()
    last_result_summary = str((working_state.get("last_result_summary") if working_state else "") or "").strip()
    current_step_task = (working_state.get("current_step_task") if working_state and isinstance(working_state.get("current_step_task"), dict) else {})
    execution_lane = str((working_state.get("execution_lane") if working_state else "") or "").strip()
    attempt_kind = str((working_state.get("attempt_kind") if working_state else "") or "").strip()
    previous_tool = str((working_state.get("previous_tool") if working_state else "") or "").strip()
    parallel_tools = [
        str(name or "").strip()
        for name in ((working_state.get("parallel_tools") if working_state else []) or [])
        if str(name or "").strip()
    ]
    try:
        parallel_size = int((working_state.get("parallel_size") if working_state else 0) or 0)
    except Exception:
        parallel_size = 0
    if parallel_size <= 0:
        parallel_size = len(parallel_tools)

    if task_plan and items:
        current_item = next(
            (
                item
                for item in items
                if isinstance(item, dict) and str(item.get("id") or "").strip() == current_item_id
            ),
            {},
        )
        current_status = str(current_item.get("status") or "").strip()
        if not current_step:
            current_step = str(current_item.get("title") or "").strip()
        if not recent_progress:
            done_item = next(
                (
                    item
                    for item in reversed(items)
                    if isinstance(item, dict)
                    and str(item.get("status") or "").strip() == "done"
                    and str(item.get("id") or "").strip() != current_item_id
                ),
                {},
            )
            recent_progress = str(done_item.get("title") or "").strip()
        if not blocker and (phase == "blocked" or current_status in {"blocked", "error", "failed", "waiting_user"}):
            blocker = str(current_item.get("detail") or task_plan.get("summary") or "").strip()
        if not next_step:
            next_step = current_step
            if not next_step:
                pending_item = next(
                    (
                        item
                        for item in items
                        if isinstance(item, dict)
                        and str(item.get("status") or "").strip() in {"running", "pending", "waiting_user"}
                    ),
                    {},
                )
                next_step = str(pending_item.get("title") or "").strip()

    if phase:
        lines.append(f"Current phase: {phase}")
    turn_execution_policy = ""
    if query_mode == "locate":
        lines.append("Current user request: answer with the current task target or location first. Do not continue execution automatically.")
        turn_execution_policy = "explain_only"
    elif query_mode == "status":
        lines.append("Current user request: answer with the current task status or progress first. Do not continue execution automatically.")
        turn_execution_policy = "explain_only"
    elif query_mode == "verify":
        lines.append("Current user request: answer whether the latest task result is verified first. Do not continue execution automatically.")
        turn_execution_policy = "explain_only"
    elif query_mode == "interrupt":
        lines.append("Current user request: explain why the last attempt was interrupted first. Do not continue execution automatically.")
        turn_execution_policy = "explain_only"
    elif query_mode == "blocker":
        lines.append("Current user request: explain the blocker or missing user action first. Do not continue execution automatically.")
        turn_execution_policy = "explain_only"
    elif query_mode == "continue":
        turn_execution_policy = "continue_execution_allowed"
    elif query_mode:
        lines.append("Current user request: answer about the active task first. Do not continue execution automatically.")
        turn_execution_policy = "explain_only"
    if turn_execution_policy:
        lines.append(f"Turn execution policy: {turn_execution_policy}")
    if turn_execution_policy == "explain_only":
        lines.append(
            "This request is already answerable from the current task runtime state. "
            "Answer from that state first, and do not call inspection, search, capture, or execution tools "
            "unless the user explicitly asks for a new check."
        )
        lines.append(
            "This turn is explanation-only. End after answering the current question. "
            "Do not continue the task or call tools in this same turn."
        )
    if summary:
        lines.append(f"Working summary: {summary}")
    if current_step:
        lines.append(f"Current step: {current_step}")
    elif current_item_id:
        lines.append(f"Current plan item: {current_item_id}")
    if recent_progress and recent_progress != current_step:
        lines.append(f"Recent progress: {recent_progress}")
    if last_tool:
        lines.append(f"Latest tool used: {last_tool}")
    if last_action_summary and last_action_summary not in {summary, current_step, recent_progress}:
        lines.append(f"Latest action summary: {last_action_summary}")
    if last_result_summary and last_result_summary not in {summary, blocker, last_action_summary}:
        lines.append(f"Latest result summary: {last_result_summary}")
    if execution_lane:
        lines.append(f"Current execution lane: {execution_lane}")
    if attempt_kind:
        lines.append(f"Latest attempt kind: {attempt_kind}")
    if previous_tool and previous_tool != last_tool:
        lines.append(f"Previous tool before latest step: {previous_tool}")
    if parallel_tools and parallel_size > 1:
        lines.append(f"Latest parallel tool batch: {', '.join(parallel_tools[:4])}")
    if str(current_step_task.get("status") or "").strip():
        lines.append(f"Current plan-step task status: {str(current_step_task.get('status') or '').strip()}")
    if str(current_step_task.get("runtime_status") or "").strip():
        lines.append(f"Current plan-step runtime status: {str(current_step_task.get('runtime_status') or '').strip()}")
    if blocker:
        lines.append(f"Current blocker: {blocker}")
    if runtime_status == "interrupted":
        lines.append("Latest runtime status: interrupted")
    if verification_status:
        lines.append(f"Latest verification status: {verification_status}")
    if verification_detail and verification_detail not in {summary, blocker}:
        lines.append(f"Latest verification detail: {verification_detail}")
    if next_step and next_step != current_step:
        lines.append(f"Default next step: {next_step}")

    task_fs_target = ""
    if load_task_plan_fs_target:
        try:
            task_fs_target = str(load_task_plan_fs_target(bundle) or "").strip()
        except Exception:
            task_fs_target = ""
    if not task_fs_target:
        task_fs_target = str((working_state.get("fs_target") if working_state else "") or "").strip()
    if task_fs_target:
        lines.append(f"Current task directory/file target: {task_fs_target}")
        if build_fs_focus_guidance:
            try:
                focus_guidance = str(
                    build_fs_focus_guidance(bundle, {"file_path": task_fs_target}) or ""
                ).strip()
            except Exception:
                focus_guidance = ""
            if focus_guidance:
                lines.append("Execution focus:")
                lines.extend(f"- {line}" for line in focus_guidance.splitlines() if line.strip())

    if items:
        lines.append("Current plan checklist:")
        for item in items[:6]:
            if not isinstance(item, dict):
                continue
            item_title = str(item.get("title") or "").strip()
            item_status = str(item.get("status") or "pending").strip()
            if item_title:
                lines.append(f"- [{item_status}] {item_title}")

    success_paths = bundle.get("l5_success_paths") if isinstance(bundle.get("l5_success_paths"), list) else []
    if success_paths:
        lines.append("Reusable successful approaches for similar tasks:")
        for item in success_paths[:2]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            summary = str(item.get("summary") or "").strip()
            if name and summary:
                lines.append(f"- {name}: {summary}")
            elif name:
                lines.append(f"- {name}")

    attempts = recent_attempts or []
    if attempts:
        lines.append("Recent attempts in this turn:")
        for item in attempts[-4:]:
            tool_name = str(item.get("tool") or "").strip()
            status = "success" if item.get("success") else "failed"
            summary = str(item.get("summary") or "").strip()
            if tool_name and summary:
                lines.append(f"- {tool_name}: {status} | {summary}")
            elif tool_name:
                lines.append(f"- {tool_name}: {status}")

    lines.append("Keep advancing the same user goal unless a tool result clearly changes it.")
    lines.append("Do not restart the search from scratch after every tool call.")
    lines.append("Use the latest tool result to choose the next closest action.")
    return "\n".join(lines)
