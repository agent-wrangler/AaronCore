import copy


def summarize_execution_text(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return ""
    text = text.replace("`", "").replace("\r", "\n")
    lines = [line.strip(" -") for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    summary = " / ".join(lines[:2]).strip()
    return summary[:140] + ("..." if len(summary) > 140 else "")


def build_run_event(
    *,
    success: bool,
    meta: dict | None = None,
    fallback_text: str = "",
    fallback_summary: str = "",
) -> dict:
    meta = meta if isinstance(meta, dict) else {}
    state = meta.get("state") if isinstance(meta.get("state"), dict) else {}
    drift = meta.get("drift") if isinstance(meta.get("drift"), dict) else {}
    action = meta.get("action") if isinstance(meta.get("action"), dict) else {}
    post = meta.get("post_condition") if isinstance(meta.get("post_condition"), dict) else {}
    verification = meta.get("verification") if isinstance(meta.get("verification"), dict) else {}

    summary = str(action.get("display_hint") or fallback_summary or "").strip()
    if not summary:
        parts = [
            str(action.get("action_kind") or "").strip(),
            str(action.get("target_kind") or "").strip(),
            str(action.get("outcome") or "").strip(),
            str(action.get("target") or "").strip(),
        ]
        summary = " / ".join([part for part in parts if part][:4]).strip()
    if not summary:
        summary = summarize_execution_text(fallback_text)

    expected_state = str(state.get("expected_state") or post.get("expected") or "").strip()
    observed_state = str(
        state.get("observed_state")
        or post.get("observed")
        or verification.get("observed_state")
        or ""
    ).strip()
    drift_reason = str(drift.get("reason") or post.get("drift") or "").strip()
    repair_hint = str(drift.get("repair_hint") or post.get("hint") or "").strip()

    verified = None
    if "verified" in verification:
        verified = bool(verification.get("verified"))
    elif "ok" in post:
        verified = bool(post.get("ok"))

    run_event = {
        "success": bool(success),
        "verified": verified,
        "summary": summary,
        "expected_state": expected_state,
        "observed_state": observed_state,
        "drift_reason": drift_reason,
        "repair_hint": repair_hint,
        "repair_succeeded": bool(meta.get("repair_succeeded", False)),
        "action_kind": str(action.get("action_kind") or "").strip(),
        "target_kind": str(action.get("target_kind") or "").strip(),
        "target": str(action.get("target") or "").strip(),
        "outcome": str(action.get("outcome") or "").strip(),
        "verification_mode": str(action.get("verification_mode") or "").strip(),
        "verification_detail": str(
            action.get("verification_detail")
            or verification.get("detail")
            or ""
        ).strip(),
    }
    return {key: value for key, value in run_event.items() if value not in ("", None)}


def extract_task_plan_from_meta(meta: dict | None) -> dict | None:
    meta = meta if isinstance(meta, dict) else {}
    task_plan = meta.get("task_plan") if isinstance(meta.get("task_plan"), dict) else {}
    items = task_plan.get("items") if isinstance(task_plan.get("items"), list) else []
    if not task_plan or not items:
        return None
    return task_plan


def record_tool_call_memory_stats(
    tool_used: str,
    run_meta: dict | None = None,
    tool_success: bool | None = None,
) -> None:
    tool_name = str(tool_used or "").strip()
    if tool_name not in {"recall_memory", "query_knowledge"}:
        return

    meta = run_meta if isinstance(run_meta, dict) else {}
    memory_stats = meta.get("memory_stats") if isinstance(meta.get("memory_stats"), dict) else {}
    if tool_success is False and not memory_stats:
        return

    payload = {"count_query": False}
    if tool_name == "recall_memory":
        payload["l2_searches"] = max(int(memory_stats.get("l2_searches", 1)), 0)
        payload["l2_hits"] = max(int(memory_stats.get("l2_hits", 0)), 0)
        payload["l3_queries"] = max(int(memory_stats.get("l3_queries", 1)), 0)
        payload["l3_hits"] = max(int(memory_stats.get("l3_hits", 0)), 0)
    else:
        payload["l8_searches"] = max(int(memory_stats.get("l8_searches", 1)), 0)
        payload["l8_hits"] = max(int(memory_stats.get("l8_hits", 0)), 0)

    try:
        from core.runtime_state.state_loader import record_memory_stats

        record_memory_stats(**payload)
    except Exception:
        pass


def is_task_plan_terminal(plan: dict | None) -> bool:
    plan = plan if isinstance(plan, dict) else {}
    items = plan.get("items") if isinstance(plan.get("items"), list) else []
    phase = str(plan.get("phase") or "").strip().lower()
    if phase in {"done", "failed", "blocked", "cancelled"}:
        return True
    if not items:
        return True
    return not any(
        str((item or {}).get("status") or "").strip() in {"pending", "running", "waiting_user"}
        for item in items
    )


def block_task_plan_after_failure(
    plan: dict | None,
    *,
    goal_hint: str = "",
    tool_used: str = "",
    action_summary: str = "",
    tool_response: str = "",
) -> dict | None:
    plan = copy.deepcopy(plan if isinstance(plan, dict) else {})
    items = plan.get("items") if isinstance(plan.get("items"), list) else []
    if not items or is_task_plan_terminal(plan):
        return plan or None

    summary = summarize_execution_text(tool_response) or summarize_execution_text(action_summary)
    if tool_used and summary:
        summary = f"{tool_used} 未完成：{summary}"
    elif tool_used:
        summary = f"{tool_used} 未完成"
    elif not summary:
        summary = "当前步骤执行失败"

    current_item_id = str(plan.get("current_item_id") or "").strip()
    target = None
    if current_item_id:
        target = next(
            (item for item in items if str((item or {}).get("id") or "").strip() == current_item_id),
            None,
        )
    if not target:
        target = next((item for item in items if str((item or {}).get("status") or "").strip() == "running"), None)
    if not target:
        target = next((item for item in items if str((item or {}).get("status") or "").strip() == "pending"), None)
    if not target and items:
        target = items[-1]

    if target:
        target["status"] = "blocked"
        if summary:
            target["detail"] = summary
        plan["current_item_id"] = str(target.get("id") or "").strip()

    plan["phase"] = "blocked"
    if summary:
        plan["summary"] = summary

    try:
        from core.task_store import normalize_task_plan_snapshot, save_task_plan_snapshot

        normalized = normalize_task_plan_snapshot(plan, goal=str(plan.get("goal") or goal_hint or "").strip())
        _, saved_plan = save_task_plan_snapshot(
            str(normalized.get("goal") or goal_hint or "").strip(),
            normalized,
            source="task_plan_runtime",
        )
        return saved_plan if isinstance(saved_plan, dict) else normalized
    except Exception:
        return plan
