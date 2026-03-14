# feedback_loop - 反馈记录、后台学习任务
# 从 agent_final.py 提取

from core.state_loader import PRIMARY_STATE_DIR

# ── 注入依赖 ──────────────────────────────────────────────
_debug_write = lambda stage, data: None
_load_autolearn_config = lambda: {}
_l8_auto_learn = None
_l8_feedback_relearn = None
_find_relevant_knowledge = lambda q, limit=3, touch=False: []
_should_trigger_auto_learn = lambda q, **kw: (False, "not_initialized")
_create_self_repair_report = None
_preview_self_repair_report = None


def init(*, debug_write=None, load_autolearn_config=None,
         l8_auto_learn=None, l8_feedback_relearn=None,
         find_relevant_knowledge=None, should_trigger_auto_learn=None,
         create_self_repair_report=None, preview_self_repair_report=None):
    global _debug_write, _load_autolearn_config
    global _l8_auto_learn, _l8_feedback_relearn
    global _find_relevant_knowledge, _should_trigger_auto_learn
    global _create_self_repair_report, _preview_self_repair_report
    if debug_write:
        _debug_write = debug_write
    if load_autolearn_config:
        _load_autolearn_config = load_autolearn_config
    if l8_auto_learn:
        _l8_auto_learn = l8_auto_learn
    if l8_feedback_relearn:
        _l8_feedback_relearn = l8_feedback_relearn
    if find_relevant_knowledge:
        _find_relevant_knowledge = find_relevant_knowledge
    if should_trigger_auto_learn:
        _should_trigger_auto_learn = should_trigger_auto_learn
    if create_self_repair_report:
        _create_self_repair_report = create_self_repair_report
    if preview_self_repair_report:
        _preview_self_repair_report = preview_self_repair_report


# ── 反馈记录 ──────────────────────────────────────────────

def l7_record_feedback(msg: str, history: list, background_tasks=None):
    negative_keywords = ["\u4e0d\u5bf9", "\u4e0d\u662f", "\u9519\u4e86", "\u4e0d\u597d\u7528", "\u4e0d\u559c\u6b22", "\u91cd\u6765", "\u5047", "\u9a97\u4eba", "\u6ca1\u542c\u61c2", "\u5b8c\u5168\u6ca1\u542c\u61c2"]
    if not any(word in msg for word in negative_keywords):
        return

    last_q = ""
    for item in reversed(history[:-1]):
        if item.get("role") == "user" and item.get("content") != msg:
            last_q = item.get("content", "")
            break

    if last_q:
        try:
            from core.feedback_classifier import record_feedback_rule

            rule_item = record_feedback_rule(msg, last_q)
            _debug_write("feedback_rule", rule_item)
        except Exception as exc:
            _debug_write("feedback_rule_error", {"error": str(exc)})


def l7_record_feedback_v2(msg: str, history: list, background_tasks=None):
    negative_keywords = ["\u4e0d\u5bf9", "\u4e0d\u662f", "\u9519\u4e86", "\u4e0d\u597d\u7528", "\u4e0d\u559c\u6b22", "\u91cd\u6765", "\u5047", "\u9a97\u4eba", "\u6ca1\u542c\u61c2", "\u5b8c\u5168\u6ca1\u542c\u61c2"]
    if not any(word in msg for word in negative_keywords):
        return None

    last_q = ""
    last_answer = ""
    for item in reversed(history[:-1]):
        role = item.get("role")
        content = item.get("content", "")
        if not last_answer and role in ("nova", "assistant") and content:
            last_answer = content
        if role == "user" and content != msg:
            last_q = content
            break

    if not last_q:
        return None

    try:
        from core.feedback_classifier import record_feedback_rule

        rule_item = record_feedback_rule(msg, last_q, last_answer)
        _debug_write("feedback_rule", rule_item)
        l8_config = _load_autolearn_config()
        if (
            l8_config.get("enabled", True)
            and l8_config.get("allow_knowledge_write", True)
            and l8_config.get("allow_feedback_relearn", True)
        ):
            if background_tasks is not None:
                background_tasks.add_task(run_l8_feedback_relearn_task, rule_item)
            else:
                run_l8_feedback_relearn_task(rule_item)
            _debug_write(
                "l8_feedback_relearn_scheduled",
                {
                    "rule_id": rule_item.get("id"),
                    "last_question": rule_item.get("last_question", ""),
                    "scene": rule_item.get("scene", ""),
                    "problem": rule_item.get("problem", ""),
                },
            )
        if l8_config.get("allow_self_repair_planning", True):
            if background_tasks is not None:
                background_tasks.add_task(run_self_repair_planning_task, rule_item)
            else:
                run_self_repair_planning_task(rule_item)
            _debug_write(
                "self_repair_planning_scheduled",
                {
                    "rule_id": rule_item.get("id"),
                    "fix": rule_item.get("fix", ""),
                    "problem": rule_item.get("problem", ""),
                },
            )
        return rule_item
    except Exception as exc:
        _debug_write("feedback_rule_error", {"error": str(exc)})
        return None


# ── L8 状态 ──────────────────────────────────────────────

def l8_touch():
    _debug_write(
        "l8_status",
        {
            "growth_exists": (PRIMARY_STATE_DIR / "growth.json").exists(),
            "evolution_exists": (PRIMARY_STATE_DIR / "evolution.json").exists(),
            "knowledge_base_exists": (PRIMARY_STATE_DIR / "knowledge_base.json").exists(),
        },
    )


# ── 后台学习任务 ──────────────────────────────────────────

def run_l8_autolearn_task(msg: str, response: str, route: dict, has_l8_hit: bool):
    try:
        result = _l8_auto_learn(msg, response, route_result=route if isinstance(route, dict) else None)
        debug_payload = {
            "message": msg,
            "has_l8_hit": has_l8_hit,
            "success": bool(result.get("success")),
            "reason": result.get("reason", ""),
        }
        entry = result.get("entry") if isinstance(result, dict) else None
        if isinstance(entry, dict):
            debug_payload["entry"] = {
                "name": entry.get("name"),
                "query": entry.get("query"),
            }
        if result.get("summary"):
            debug_payload["summary"] = str(result.get("summary"))[:160]
        _debug_write("l8_autolearn", debug_payload)
    except Exception as exc:
        _debug_write("l8_autolearn_error", {"message": msg, "error": str(exc)})


def run_l8_feedback_relearn_task(rule_item: dict):
    try:
        result = _l8_feedback_relearn(rule_item if isinstance(rule_item, dict) else {})
        debug_payload = {
            "rule_id": rule_item.get("id") if isinstance(rule_item, dict) else "",
            "last_question": rule_item.get("last_question") if isinstance(rule_item, dict) else "",
            "success": bool(result.get("success")),
            "reason": result.get("reason", ""),
            "used_web": bool(result.get("used_web")),
        }
        entry = result.get("entry") if isinstance(result, dict) else None
        if isinstance(entry, dict):
            debug_payload["entry"] = {
                "name": entry.get("name"),
                "query": entry.get("query"),
            }
        if result.get("summary"):
            debug_payload["summary"] = str(result.get("summary"))[:200]
        _debug_write("l8_feedback_relearn", debug_payload)
    except Exception as exc:
        _debug_write("l8_feedback_relearn_error", {"error": str(exc)})


def run_self_repair_planning_task(rule_item: dict):
    try:
        config = _load_autolearn_config()
        if not config.get("allow_self_repair_planning", True):
            return

        report = _create_self_repair_report(
            rule_item if isinstance(rule_item, dict) else {},
            config=config,
            run_validation=bool(config.get("allow_self_repair_test_run", True)),
        )
        _debug_write(
            "self_repair_report",
            {
                "report_id": report.get("id"),
                "feedback_rule_id": report.get("feedback_rule_id"),
                "status": report.get("status"),
                "candidate_files": [item.get("path") for item in report.get("candidate_files", [])],
                "suggested_tests": [item.get("path") for item in report.get("suggested_tests", [])],
                "validation_ran": bool((report.get("validation") or {}).get("ran")),
                "validation_passed": (report.get("validation") or {}).get("all_passed"),
            },
        )
        report = _preview_self_repair_report(
            report_id=str(report.get("id") or ""),
            config=config,
            auto_apply=bool(config.get("allow_self_repair_auto_apply", True)),
            run_validation=bool(config.get("allow_self_repair_test_run", True)),
        )
        _debug_write(
            "self_repair_follow_up",
            {
                "report_id": report.get("id"),
                "status": report.get("status"),
                "risk_level": ((report.get("patch_preview") or {}).get("risk_level")) or report.get("risk_level"),
                "auto_apply_ready": ((report.get("patch_preview") or {}).get("auto_apply_ready")),
                "apply_status": ((report.get("apply_result") or {}).get("status")),
            },
        )
    except Exception as exc:
        _debug_write("self_repair_report_error", {"error": str(exc)})


# ── 诊断 ─────────────────────────────────────────────────

def build_l8_diagnosis(query: str, route_mode: str = "chat", skill: str = "none", limit: int = 3) -> dict:
    route_result = {
        "mode": str(route_mode or "chat").strip() or "chat",
        "skill": str(skill or "none").strip() or "none",
    }
    config = _load_autolearn_config()
    knowledge_hits = _find_relevant_knowledge(query, limit=max(limit, 1), touch=False)
    should_run, reason = _should_trigger_auto_learn(
        query,
        route_result=route_result,
        has_relevant_knowledge=bool(knowledge_hits),
        config=config,
    )
    return {
        "query": str(query or ""),
        "route_result": route_result,
        "config": config,
        "should_trigger": should_run,
        "reason": reason,
        "knowledge_hits": knowledge_hits,
    }
