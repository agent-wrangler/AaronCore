import json
import re

from core.fs_protocol import build_operation_result
from tasks.store import (
    get_active_task_plan_snapshot,
    normalize_task_plan_snapshot,
    save_task_plan_snapshot,
)


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", str(text or "")))


def _strip_code_fence(text: str) -> str:
    raw = str(text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _clone_plan(plan: dict | None) -> dict:
    if not isinstance(plan, dict):
        return {}
    try:
        return json.loads(json.dumps(plan, ensure_ascii=False))
    except Exception:
        return dict(plan)


def _auto_plan_from_goal(goal: str) -> dict:
    raw_goal = str(goal or "").strip()
    if not raw_goal:
        return normalize_task_plan_snapshot({}, goal="")

    try:
        from core.skills.article import _llm_call
    except Exception:
        _llm_call = None

    if callable(_llm_call):
        prompt = (
            "你是任务规划助手。请把下面这个复杂任务整理成一个很短的执行计划。"
            "返回严格 JSON，格式为 "
            '{"goal":"...","summary":"...","items":[{"id":"...","title":"...","kind":"phase"}]}. '
            "要求：3 到 6 个高信号阶段；不要写微步骤；id 用短英文下划线；summary 一句话。\n\n"
            f"任务：{raw_goal}"
        )
        raw = _strip_code_fence(_llm_call(prompt, max_tokens=500, temperature=0.2) or "")
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return normalize_task_plan_snapshot(data, goal=raw_goal)
        except Exception:
            pass

    return normalize_task_plan_snapshot({}, goal=raw_goal)


def _find_item(plan: dict, item_id: str) -> dict | None:
    raw_id = str(item_id or "").strip()
    if not raw_id:
        return None
    for item in plan.get("items") or []:
        if str(item.get("id") or "").strip() == raw_id:
            return item
    return None


def _should_treat_mark_done_as_advance(goal: str, ctx: dict) -> bool:
    next_item_id = str(ctx.get("next_item_id") or "").strip()
    if next_item_id:
        return True

    raw_items = ctx.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        return False

    normalized = normalize_task_plan_snapshot(
        {
            "goal": goal,
            "items": raw_items,
            "current_item_id": str(ctx.get("current_item_id") or "").strip(),
        },
        goal=goal,
    )
    items = normalized.get("items") if isinstance(normalized.get("items"), list) else []
    unfinished_ids = [
        str(item.get("id") or "").strip()
        for item in items
        if str(item.get("status") or "").strip() in {"pending", "running", "blocked", "error", "failed", "waiting_user"}
        and str(item.get("id") or "").strip()
    ]
    if not unfinished_ids:
        return False

    completed_item_id = str(ctx.get("completed_item_id") or "").strip()
    if completed_item_id:
        return any(item_id != completed_item_id for item_id in unfinished_ids)
    return len(unfinished_ids) > 1


def _current_or_first_pending(plan: dict) -> dict | None:
    current = _find_item(plan, plan.get("current_item_id"))
    if current:
        return current
    for item in plan.get("items") or []:
        if item.get("status") == "running":
            return item
    for item in plan.get("items") or []:
        if item.get("status") == "pending":
            return item
    return (plan.get("items") or [None])[0]


def _apply_create_or_update(goal: str, existing: dict, ctx: dict) -> dict:
    items = ctx.get("items")
    phase = str(ctx.get("phase") or "").strip()
    summary = str(ctx.get("summary") or "").strip()
    current_item_id = str(ctx.get("current_item_id") or "").strip()
    if items or not existing:
        base = {
            "goal": goal,
            "phase": phase,
            "summary": summary,
            "items": items or [],
            "current_item_id": current_item_id,
        }
        if items:
            return normalize_task_plan_snapshot(base, goal=goal)
        generated = _auto_plan_from_goal(goal)
        if phase:
            generated["phase"] = phase
        if summary:
            generated["summary"] = summary
        if current_item_id:
            generated["current_item_id"] = current_item_id
        return normalize_task_plan_snapshot(generated, goal=goal)

    plan = _clone_plan(existing)
    if phase:
        plan["phase"] = phase
    if summary:
        plan["summary"] = summary
    if current_item_id:
        plan["current_item_id"] = current_item_id
    return normalize_task_plan_snapshot(plan, goal=goal)


def _apply_advance(goal: str, existing: dict, ctx: dict) -> dict:
    plan = _clone_plan(existing or _auto_plan_from_goal(goal))
    completed_item_id = str(ctx.get("completed_item_id") or "").strip()
    next_item_id = str(ctx.get("next_item_id") or "").strip()
    completed_item = _find_item(plan, completed_item_id) or _current_or_first_pending(plan)
    if completed_item:
        completed_item["status"] = "done"
    next_item = _find_item(plan, next_item_id)
    if not next_item:
        for item in plan.get("items") or []:
            if item.get("status") == "pending":
                next_item = item
                break
    if next_item and next_item is not completed_item:
        next_item["status"] = "running"
        plan["current_item_id"] = str(next_item.get("id") or "").strip()
    elif completed_item:
        plan["current_item_id"] = str(completed_item.get("id") or "").strip()
    if str(ctx.get("summary") or "").strip():
        plan["summary"] = str(ctx.get("summary") or "").strip()
    return normalize_task_plan_snapshot(plan, goal=goal)


def _apply_blocked(goal: str, existing: dict, ctx: dict) -> dict:
    plan = _clone_plan(existing or _auto_plan_from_goal(goal))
    item = _find_item(plan, ctx.get("current_item_id")) or _current_or_first_pending(plan)
    reason = str(ctx.get("blocked_reason") or ctx.get("summary") or "").strip()
    if item:
        item["status"] = "blocked"
        if reason:
            item["detail"] = reason
        plan["current_item_id"] = str(item.get("id") or "").strip()
    plan["phase"] = "blocked"
    if reason:
        plan["summary"] = reason
    return normalize_task_plan_snapshot(plan, goal=goal)


def _apply_done(goal: str, existing: dict, ctx: dict) -> dict:
    plan = _clone_plan(existing or _auto_plan_from_goal(goal))
    for item in plan.get("items") or []:
        if item.get("status") in {"pending", "running", "blocked", "waiting_user"}:
            item["status"] = "done"
    plan["phase"] = "done"
    if str(ctx.get("summary") or "").strip():
        plan["summary"] = str(ctx.get("summary") or "").strip()
    return normalize_task_plan_snapshot(plan, goal=goal)


def _apply_resume(goal: str, existing: dict, ctx: dict) -> dict:
    plan = _clone_plan(existing or _auto_plan_from_goal(goal))
    target = _find_item(plan, ctx.get("next_item_id")) or _find_item(plan, ctx.get("current_item_id"))
    if not target:
        for item in plan.get("items") or []:
            if item.get("status") in {"blocked", "waiting_user", "pending"}:
                target = item
                break
    for item in plan.get("items") or []:
        if item.get("status") == "running":
            item["status"] = "pending"
    if target:
        target["status"] = "running"
        plan["current_item_id"] = str(target.get("id") or "").strip()
    if str(ctx.get("summary") or "").strip():
        plan["summary"] = str(ctx.get("summary") or "").strip()
    return normalize_task_plan_snapshot(plan, goal=goal)


def _apply_cancel(goal: str, existing: dict, ctx: dict) -> dict:
    plan = _clone_plan(existing or _auto_plan_from_goal(goal))
    for item in plan.get("items") or []:
        if item.get("status") in {"pending", "running"}:
            item["status"] = "cancelled"
    plan["phase"] = "cancelled"
    if str(ctx.get("summary") or "").strip():
        plan["summary"] = str(ctx.get("summary") or "").strip()
    return normalize_task_plan_snapshot(plan, goal=goal)


def _build_reply(action: str, plan: dict) -> str:
    goal = str(plan.get("goal") or "").strip()
    summary = str(plan.get("summary") or "").strip()
    current = _current_or_first_pending(plan) or {}
    current_title = str(current.get("title") or "").strip()
    items = plan.get("items") or []
    has_cjk = _contains_cjk(goal or summary or current_title)
    if has_cjk:
        lead = {
            "get_current": "我把当前任务规划提出来了。",
            "create_or_update": "我已经把这轮任务规划接住并更新了。",
            "advance": "我把任务推进到下一步了。",
            "mark_blocked": "我已经把当前阻塞点记进任务计划里了。",
            "mark_done": "我把这轮任务标记完成了。",
            "resume": "我已经把任务计划恢复推进了。",
            "cancel": "我已经把这轮任务计划收住了。",
        }.get(action, "我已经把任务计划更新好了。")
        lines = [lead]
        if summary:
            lines.append(f"当前摘要：{summary}")
        if current_title and str(plan.get("phase") or "") not in {"done", "cancelled"}:
            lines.append(f"当前事项：{current_title}")
        if items:
            lines.append(f"任务清单：{len(items)} 项")
        return "\n".join(lines)
    lead = {
        "get_current": "I surfaced the current task plan.",
        "create_or_update": "I created or updated the task plan.",
        "advance": "I advanced the task plan.",
        "mark_blocked": "I recorded the blocker in the task plan.",
        "mark_done": "I marked the task plan complete.",
        "resume": "I resumed the task plan.",
        "cancel": "I closed out the task plan.",
    }.get(action, "I updated the task plan.")
    lines = [lead]
    if summary:
        lines.append(f"Summary: {summary}")
    if current_title and str(plan.get("phase") or "") not in {"done", "cancelled"}:
        lines.append(f"Current item: {current_title}")
    if items:
        lines.append(f"Items: {len(items)}")
    return "\n".join(lines)


def _success_result(reply: str, action: str, plan: dict) -> dict:
    goal = str(plan.get("goal") or "").strip()
    current_item = _current_or_first_pending(plan) or {}
    current_title = str(current_item.get("title") or "").strip()
    verification_detail = " / ".join(
        [
            f"phase={str(plan.get('phase') or '').strip()}",
            f"current_item={str(plan.get('current_item_id') or '').strip()}",
            f"items={len(plan.get('items') or [])}",
        ]
    )
    result = build_operation_result(
        reply,
        expected_state="task_plan_saved",
        observed_state="task_plan_saved",
        drift_reason="",
        repair_hint="",
        action_kind="task_plan",
        target_kind="task",
        target=goal or "current_task",
        outcome="saved",
        display_hint=str(plan.get("summary") or reply).strip(),
        verification_mode="task_store_snapshot",
        verification_detail=verification_detail,
    )
    result["verification"] = {
        "verified": True,
        "observed_state": "task_plan_saved",
        "detail": verification_detail,
    }
    result["task_plan"] = plan
    result["action"]["plan_action"] = action
    if current_title:
        result["action"]["current_item"] = current_title
    return result


def _failure_result(reply: str, reason: str, hint: str = "") -> dict:
    result = build_operation_result(
        reply,
        expected_state="task_plan_saved",
        observed_state="task_plan_missing",
        drift_reason=reason,
        repair_hint=hint,
        action_kind="task_plan",
        target_kind="task",
        target="current_task",
        outcome="missing",
        display_hint=reply,
        verification_mode="task_store_snapshot",
        verification_detail=reason,
    )
    result["verification"] = {
        "verified": False,
        "observed_state": "task_plan_missing",
        "detail": reason,
    }
    return result


def _extract_preferred_fs_target(ctx: dict) -> str:
    ctx = ctx if isinstance(ctx, dict) else {}
    fs_target = ctx.get("fs_target") if isinstance(ctx.get("fs_target"), dict) else {}
    path = str(fs_target.get("path") or "").strip()
    if path:
        return path
    context_data = ctx.get("context_data") if isinstance(ctx.get("context_data"), dict) else {}
    inherited = context_data.get("fs_target") if isinstance(context_data.get("fs_target"), dict) else {}
    return str(inherited.get("path") or "").strip()


def execute(query, context=None):
    ctx = context if isinstance(context, dict) else {}
    action = str(ctx.get("action") or "create_or_update").strip().lower() or "create_or_update"
    if action == "mark_blocked":
        normalized_action = "mark_blocked"
    elif action == "mark_done":
        normalized_action = "mark_done"
    else:
        aliases = {
            "create": "create_or_update",
            "update": "create_or_update",
            "create_or_update": "create_or_update",
            "advance": "advance",
            "resume": "resume",
            "get": "get_current",
            "get_current": "get_current",
            "current": "get_current",
            "done": "mark_done",
            "complete": "mark_done",
            "blocked": "mark_blocked",
            "cancel": "cancel",
        }
        normalized_action = aliases.get(action, "create_or_update")

    goal = str(ctx.get("goal") or query or "").strip()
    preferred_fs_target = _extract_preferred_fs_target(ctx) if normalized_action == "resume" else ""
    existing = get_active_task_plan_snapshot(
        goal or query or "",
        preferred_fs_target=preferred_fs_target,
    ) or {}

    if normalized_action == "get_current":
        if not existing:
            reply = "当前还没有活动任务计划。" if _contains_cjk(goal or query) else "There is no active task plan yet."
            return _failure_result(reply, "no_active_task_plan", "create_or_update")
        return _success_result(_build_reply(normalized_action, existing), normalized_action, existing)

    if not goal and not existing:
        reply = "还缺少这轮任务目标，没法建立任务计划。" if _contains_cjk(query) else "I need the task goal before I can create a plan."
        return _failure_result(reply, "missing_task_goal", "provide_goal")

    effective_goal = goal or str(existing.get("goal") or "").strip()
    if normalized_action == "mark_done" and _should_treat_mark_done_as_advance(effective_goal, ctx):
        normalized_action = "advance"

    if normalized_action == "create_or_update":
        plan = _apply_create_or_update(effective_goal, existing, ctx)
    elif normalized_action == "advance":
        plan = _apply_advance(effective_goal, existing, ctx)
    elif normalized_action == "mark_blocked":
        plan = _apply_blocked(effective_goal, existing, ctx)
    elif normalized_action == "mark_done":
        plan = _apply_done(effective_goal, existing, ctx)
    elif normalized_action == "resume":
        plan = _apply_resume(effective_goal, existing, ctx)
    elif normalized_action == "cancel":
        plan = _apply_cancel(effective_goal, existing, ctx)
    else:
        plan = _apply_create_or_update(effective_goal, existing, ctx)

    _task, saved_plan = save_task_plan_snapshot(effective_goal, plan, source="task_plan")
    reply = _build_reply(normalized_action, saved_plan)
    return _success_result(reply, normalized_action, saved_plan)
