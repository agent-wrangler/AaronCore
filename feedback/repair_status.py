"""Self-repair status summaries and UI payload helpers."""


def build_learning_summary(config: dict) -> str:
    if not bool(config.get("enabled", True)):
        return "自动学习已关闭，反馈只会停留在当前会话里。"
    if bool(config.get("allow_feedback_relearn", True)):
        if bool(config.get("allow_web_search", True)) and bool(config.get("allow_knowledge_write", True)):
            return "会先记住负反馈，必要时补学并写回知识库。"
        if bool(config.get("allow_knowledge_write", True)):
            return "会先记住负反馈，并把纠偏结论写回知识库。"
        return "会先记住负反馈，但暂时不会长期写回知识库。"
    return "现在不会把负反馈沉淀成纠偏记录。"


def build_repair_summary(config: dict) -> str:
    planning_enabled = bool(config.get("allow_self_repair_planning", True))
    test_run_enabled = bool(config.get("allow_self_repair_test_run", True))
    auto_apply_enabled = bool(config.get("allow_self_repair_auto_apply", True))
    apply_mode = str(config.get("self_repair_apply_mode") or "confirm").strip() or "confirm"

    if not planning_enabled:
        return "目前只做学习纠偏，不会主动整理修复方案。"
    if not test_run_enabled:
        return "会先整理修法，但动手前还不会自动自查。"
    if not auto_apply_enabled:
        return "会先整理修法并自查，真正动手前先停下来给你看。"
    if apply_mode == "suggest":
        return "低风险会继续，中高风险先给你看方案。"
    return "低风险会继续，中高风险只确认一次。"


def build_latest_status_summary(latest: dict, latest_preview: dict, latest_apply: dict) -> str:
    apply_status = str((latest_apply or {}).get("status") or "").strip()
    if apply_status:
        if apply_status in {"applied", "applied_without_validation"} and bool(latest_apply.get("auto_applied")):
            return "最近一次反馈已经在后台自动落成修改。"
        if apply_status == "applied":
            return "最近一次反馈已经真正动手修改并通过了自查。"
        if apply_status == "applied_without_validation":
            return "最近一次反馈已经动手修改，但还没有跑自查。"
        if apply_status.startswith("rolled_back"):
            return "最近一次尝试已经自动回滚，没有把坏补丁留在源码里。"
        return "最近一次反馈已经走到动手阶段，但结果还需要进一步确认。"

    preview_status = str((latest_preview or {}).get("status") or "").strip()
    if preview_status == "preview_ready":
        if bool(latest_preview.get("auto_apply_ready")):
            return "最近一次反馈已经整理成低风险补丁，会继续在后台往下处理。"
        if bool(latest_preview.get("confirmation_required", True)):
            return "最近一次反馈已经整理出改法，只等一次确认。"
        return "最近一次反馈已经整理出改法，这次不用额外确认。"

    latest_status = str((latest or {}).get("status") or "").strip()
    if latest_status:
        return "最近一次反馈已经被记进纠偏链路，后面会沿着这条线继续学习或修正。"
    return "最近还没有新的纠偏记录。"


def build_self_repair_status(
    *,
    load_autolearn_config,
    load_self_repair_reports,
) -> dict:
    l8_config = load_autolearn_config()
    all_reports = load_self_repair_reports()
    latest = all_reports[0] if all_reports else {}
    latest_preview = latest.get("patch_preview") or {}
    latest_apply = latest.get("apply_result") or {}
    planning_enabled = bool(l8_config.get("allow_self_repair_planning", True))
    test_run_enabled = bool(l8_config.get("allow_self_repair_test_run", True))
    auto_apply_enabled = bool(l8_config.get("allow_self_repair_auto_apply", True))
    apply_mode = str(l8_config.get("self_repair_apply_mode") or "confirm").strip() or "confirm"
    learning_summary = build_learning_summary(l8_config)
    repair_summary = build_repair_summary(l8_config)

    return {
        "stage": "controlled_patch_loop" if planning_enabled else "feedback_learning_only",
        "feedback_learning": bool(l8_config.get("allow_feedback_relearn", True)),
        "web_learning": bool(l8_config.get("allow_web_search", True)),
        "knowledge_write": bool(l8_config.get("allow_knowledge_write", True)),
        "planning_enabled": planning_enabled,
        "test_run_enabled": test_run_enabled,
        "auto_apply_enabled": auto_apply_enabled,
        "skill_generation": bool(l8_config.get("allow_skill_generation", False)),
        "apply_mode": apply_mode,
        "report_count": len(all_reports),
        "latest_report_id": str(latest.get("id") or ""),
        "latest_report_status": str(latest.get("status") or ""),
        "latest_summary": str(latest.get("summary") or ""),
        "latest_apply_status": str(latest_apply.get("status") or ""),
        "latest_risk_level": str(latest_preview.get("risk_level") or latest.get("risk_level") or ""),
        "latest_auto_apply_ready": bool(latest_preview.get("auto_apply_ready")),
        "latest_confirmation_required": bool(latest_preview.get("confirmation_required", True)),
        "learning_summary": learning_summary,
        "repair_summary": repair_summary,
        "autonomy_summary": f"{learning_summary} {repair_summary}",
        "latest_status_summary": build_latest_status_summary(latest, latest_preview, latest_apply),
        "can_patch_source_code": True,
        "can_plan_repairs": planning_enabled,
        "can_run_source_tests": test_run_enabled,
        "can_auto_apply_fixes": planning_enabled and test_run_enabled and auto_apply_enabled,
    }


def build_repair_progress_payload(
    route: dict | None = None,
    feedback_rule: dict | None = None,
    *,
    build_self_repair_status,
) -> dict:
    route = route if isinstance(route, dict) else {}
    feedback_rule = feedback_rule if isinstance(feedback_rule, dict) else {}
    intent = str(route.get("intent") or "").strip()
    feedback_type = str(feedback_rule.get("type") or "").strip()

    if not feedback_type and intent not in {"meta_bug_report", "answer_correction"}:
        return {"show": False}

    status = build_self_repair_status()
    can_plan = bool(status.get("can_plan_repairs"))
    headline = "已记录反馈"
    detail = "我先把这次反馈记下来了。"
    item = "当前事项：先把这次问题记进修复链路。"
    if intent == "answer_correction":
        headline = "已收到纠偏"
        detail = "我先把这次答偏和错路由记下来了。"
        item = "当前事项：回看上一轮答复和被误触发的能力。"
    if can_plan:
        detail += " 接下来会继续看修复提案、验证结果和是否需要回滚。"
    else:
        detail += " 现在还没打开自动修复规划，所以会先停在记录这一步。"

    return {
        "show": True,
        "watch": can_plan,
        "label": "修复进度",
        "stage": "logged",
        "headline": headline,
        "detail": detail,
        "item": item,
        "progress": 22,
        "poll_ms": 1600,
        "max_polls": 10,
    }
