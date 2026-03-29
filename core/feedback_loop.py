# feedback_loop - 反馈记录、后台学习任务
# 从 agent_final.py 提取

from datetime import datetime
from pathlib import Path

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
_awareness_push = lambda event: None


def init(*, debug_write=None, load_autolearn_config=None,
         l8_auto_learn=None, l8_feedback_relearn=None,
         find_relevant_knowledge=None, should_trigger_auto_learn=None,
         create_self_repair_report=None, preview_self_repair_report=None,
         awareness_push=None):
    global _debug_write, _load_autolearn_config
    global _l8_auto_learn, _l8_feedback_relearn
    global _find_relevant_knowledge, _should_trigger_auto_learn
    global _create_self_repair_report, _preview_self_repair_report
    global _awareness_push
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
    if awareness_push:
        _awareness_push = awareness_push


# ── 反馈记录 ──────────────────────────────────────────────

_NEGATIVE_WORDS = [
    "\u4e0d\u5bf9", "\u9519\u4e86", "\u4e0d\u597d\u7528", "\u7406\u89e3\u9519\u4e86",
    "\u4e0d\u662f\u8fd9\u6837", "\u7b54\u504f\u4e86", "\u4f60\u6ca1\u542c\u61c2",
    "\u53c8\u6765\u4e86", "\u70e6\u6b7b\u4e86", "\u600e\u4e48\u53c8", "\u8001\u662f", "\u4e00\u76f4",
]


def _is_negative_feedback(msg: str) -> bool:
    """检测负反馈/纠偏信号。"""
    return any(w in msg for w in _NEGATIVE_WORDS)


def l7_record_feedback(msg: str, history: list, background_tasks=None):
    if not _is_negative_feedback(msg):
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


# ── self-repair：系统故障 + 用户反馈中的代码级问题 ────────
# 代码级问题（路由调度等）需要真正改代码才能修，仅靠 prompt 提示不够
_SELF_REPAIR_CATEGORIES = {"路由调度", "系统故障", "意图理解"}


def trigger_self_repair_from_error(
    error_type: str,
    error_detail: dict,
    background_tasks=None,
):
    """从系统故障事件触发 self-repair。

    error_type: skill_failed | skill_missing | core_route_error | chat_exception
    error_detail: 包含 skill, error, input 等上下文信息
    """
    l8_config = _load_autolearn_config()
    if not l8_config.get("allow_self_repair_planning", True):
        return None

    # 构造一个类似 feedback_rule 的结构给 self-repair 流程复用
    rule_item = {
        "id": f"sys_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        "source": "system_error",
        "created_at": datetime.now().isoformat(),
        "enabled": True,
        "scene": error_type,
        "problem": error_type,
        "type": "system_error",
        "category": "系统故障",
        "fix": "investigate_and_fix_code",
        "level": "session",
        "user_feedback": "",
        "last_question": str(error_detail.get("input") or error_detail.get("message") or "").strip(),
        "last_answer": str(error_detail.get("error") or "").strip(),
        "error_type": error_type,
        "error_detail": error_detail,
    }

    _debug_write("self_repair_from_system_error", {
        "error_type": error_type,
        "skill": error_detail.get("skill", ""),
        "error": str(error_detail.get("error", ""))[:200],
    })

    if background_tasks is not None:
        background_tasks.add_task(run_self_repair_planning_task, rule_item)
    else:
        run_self_repair_planning_task(rule_item)

    return rule_item


def _check_and_escalate_failed_rules(last_q: str, new_rule: dict, background_tasks=None):
    """效果追踪：如果有旧规则最近命中过但用户仍不满意，升级处理强度。
    L1(prompt) fail>=2 → 补生成 L2 约束 + 交互风格类写回 L4
    L2(约束) fail>=2 → 触发 L3 self-repair
    """
    from core.feedback_classifier import _load_rules, _save_rules, _extract_routing_constraint
    from datetime import datetime, timedelta

    rules = _load_rules()
    now = datetime.now()
    cutoff = (now - timedelta(hours=24)).isoformat()
    dirty = False

    for rule in rules:
        if not isinstance(rule, dict) or not rule.get("enabled", True):
            continue
        # 只看最近 24 小时内命中过的规则
        last_hit = rule.get("last_hit_at", "")
        if not last_hit or last_hit < cutoff:
            continue
        # 检查旧规则的 last_question 和新反馈的 last_question 是否相似
        old_q = str(rule.get("last_question", ""))
        if not old_q or len(old_q) < 2:
            continue
        if old_q[:4] not in last_q and last_q[:4] not in old_q:
            continue

        # 命中了：这条旧规则没能阻止问题再次发生
        rule["fail_count"] = (rule.get("fail_count") or 0) + 1
        dirty = True
        fail_count = rule["fail_count"]

        _debug_write("l7_rule_failed", {
            "rule_id": rule.get("id"), "fail_count": fail_count,
            "has_constraint": bool(rule.get("constraint")),
        })

        # L1 → L2 升级：prompt 提醒失败 2 次，补生成路由约束
        if fail_count >= 2 and not rule.get("constraint"):
            constraint = _extract_routing_constraint(
                rule.get("user_feedback", ""),
                rule.get("last_question", ""),
                rule.get("last_answer", ""),
                rule,
            )
            if constraint:
                rule["constraint"] = constraint
                _debug_write("l7_escalate_l1_to_l2", {"rule_id": rule.get("id")})

            # 所有类别反馈 → 修正案机制（L7→L4/L5）
            if not rule.get("l4_amended"):
                _l7_apply_amendment(rule)

        # L2 → L3 升级：路由约束也失败 2 次，触发 self-repair
        elif fail_count >= 4 and rule.get("constraint"):
            l8_config = _load_autolearn_config()
            conf = float((rule.get("constraint") or {}).get("confidence", 0) or 0)
            if conf >= 0.8 and l8_config.get("allow_self_repair_planning", True):
                _debug_write("l7_escalate_l2_to_l3", {"rule_id": rule.get("id")})
                if background_tasks is not None:
                    background_tasks.add_task(run_self_repair_planning_task, rule)
                else:
                    run_self_repair_planning_task(rule)

    if dirty:
        _save_rules(rules)


def _l7_apply_amendment(rule: dict):
    """L7 修正案：按反馈类别分发到 L4/L5，实现全闭环进化。
    - 交互风格 → L4 interaction_rules（性格调节）
    - 内容生成 → L4 interaction_rules（输出偏好）
    - 路由调度 → L4 interaction_rules + L5 anti_keywords（路由修正）
    - 意图理解 → L4 interaction_rules（认知偏置修正）
    """
    category = rule.get("category", "")
    fix = str(rule.get("fix", "")).strip()
    feedback = str(rule.get("user_feedback", "")).strip()
    amendment = fix if fix and fix != "keep_observing_and_refine" else feedback
    if not amendment or len(amendment) < 4:
        return

    # 所有类别都写入 L4 interaction_rules（LLM 能看到）
    _amend_l4_rules(rule, amendment, category)

    # 路由调度类额外写入 L5 anti_keywords（规则路由也能拦截）
    # Legacy anti_keywords writeback has been retired.


def _amend_l4_rules(rule: dict, amendment: str, category: str):
    """写入 L4 interaction_rules，按 category 加前缀标注来源"""
    from core.json_store import load_json, write_json

    # 按类别加语义前缀，让 LLM 理解这条规则的用途
    _PREFIX = {
        "\u4ea4\u4e92\u98ce\u683c": "\u98ce\u683c",
        "\u5185\u5bb9\u751f\u6210": "\u5185\u5bb9",
        "\u8def\u7531\u8c03\u5ea6": "\u8def\u7531",
        "\u610f\u56fe\u7406\u89e3": "\u7406\u89e3",
    }
    prefix = _PREFIX.get(category, "")
    tagged = f"[{prefix}] {amendment}" if prefix else amendment

    l4_file = PRIMARY_STATE_DIR / "persona.json"
    try:
        persona = load_json(l4_file, {})
        rules_list = persona.setdefault("interaction_rules", [])
        # 去重
        for existing in rules_list:
            if amendment[:15] in str(existing) or str(existing)[:15] in amendment:
                _debug_write("l7_amendment_skip", {"reason": "duplicate", "text": amendment[:40]})
                return
        rules_list.append(tagged)
        # changelog
        changelog = persona.setdefault("_changelog", [])
        changelog.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "content": f"\u4fee\u6b63\u6848\uff08L7\u2192L4\uff09\uff1a{tagged[:50]}",
        })
        if len(changelog) > 50:
            persona["_changelog"] = changelog[-50:]
        write_json(l4_file, persona)
        rule["l4_amended"] = True
        _debug_write("l7_amend_l4_ok", {"category": category, "text": amendment[:50]})
    except Exception as e:
        _debug_write("l7_amend_l4_err", {"err": str(e)})


def _amend_l5_anti_keywords(rule: dict):
    _debug_write("l7_amend_l5_retired", {
        "reason": "legacy_keyword_routing_retired",
        "rule_id": str(rule.get("id", "")),
        "category": str(rule.get("category", "")),
    })
    return
    """路由调度类反馈 → 提取误触技能，写入 skill JSON anti_keywords + 运行时注册表"""
    import json

    # 从 constraint 中提取被误触的技能名
    constraint = rule.get("constraint") or {}
    skill_name = constraint.get("skill", "")
    if not skill_name:
        _debug_write("l7_amend_l5_skip", {"reason": "no_skill_name"})
        return

    last_q = str(rule.get("last_question", ""))
    if len(last_q) < 2:
        return
    neg_kw = last_q[:10]

    # 1. 写入 skill JSON 文件（持久化）
    skill_json = Path(__file__).resolve().parent / "skills" / f"{skill_name}.json"
    try:
        if skill_json.exists():
            meta = json.loads(skill_json.read_text(encoding="utf-8"))
            anti_list = meta.setdefault("anti_keywords", [])
            if neg_kw not in anti_list:
                anti_list.append(neg_kw)
                skill_json.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                _debug_write("l7_amend_l5_json", {"skill": skill_name, "anti_kw": neg_kw})
    except Exception as e:
        _debug_write("l7_amend_l5_json_err", {"err": str(e)})

    # 2. 更新运行时 _skill_registry（立即生效，不用重启）
    try:
        from core.skills import get_skill
        info = get_skill(skill_name)
        if info:
            anti_list = info.setdefault("anti_keywords", [])
            if neg_kw not in anti_list:
                anti_list.append(neg_kw)
                _debug_write("l7_amend_l5_runtime", {"skill": skill_name, "anti_kw": neg_kw})
    except Exception as e:
        _debug_write("l7_amend_l5_runtime_err", {"err": str(e)})


def l7_record_feedback_v2(msg: str, history: list, background_tasks=None):
    if not _is_negative_feedback(msg):
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
        from core.feedback_classifier import record_feedback_rule, _load_rules, _save_rules

        rule_item = record_feedback_rule(msg, last_q, last_answer)
        _debug_write("feedback_rule", rule_item)

        # ── 效果追踪：检查是否有已命中但仍失败的旧规则 → 升级处理 ──
        try:
            _check_and_escalate_failed_rules(last_q, rule_item, background_tasks)
        except Exception as esc_err:
            _debug_write("l7_escalate_error", {"error": str(esc_err)})

        # L7 反馈分流：
        # - 内容生成/交互风格/意图理解 → 留在 L7，通过 prompt 提示影响下次回复
        # - 路由调度/系统故障 → 同时触发 self-repair，需要真正改代码
        category = rule_item.get("category", "")
        confidence = float((rule_item.get("constraint") or {}).get("confidence", 0) or 0)
        if category in _SELF_REPAIR_CATEGORIES and confidence >= 0.8:
            l8_config = _load_autolearn_config()
            if l8_config.get("allow_self_repair_planning", True):
                _debug_write("l7_to_self_repair", {
                    "rule_id": rule_item.get("id"),
                    "category": category,
                    "scene": rule_item.get("scene", ""),
                    "problem": rule_item.get("problem", ""),
                })
                if background_tasks is not None:
                    background_tasks.add_task(run_self_repair_planning_task, rule_item)
                else:
                    run_self_repair_planning_task(rule_item)

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

        # ── 感知层：推送学习事件 ──
        if result.get("success") and isinstance(entry, dict):
            _awareness_push({
                "type": "l8_learn",
                "summary": "学到新知识: " + entry.get("name", "未命名"),
                "detail": {
                    "entry_name": entry.get("name", ""),
                    "query": entry.get("query", ""),
                    "summary": str(result.get("summary", ""))[:120],
                },
            })
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

        # ── 感知层：推送反馈重学事件 ──
        if result.get("success") and isinstance(entry, dict):
            _awareness_push({
                "type": "l8_relearn",
                "summary": "反馈重学: " + entry.get("name", "未命名"),
                "detail": {
                    "entry_name": entry.get("name", ""),
                    "reason": result.get("reason", ""),
                    "used_web": bool(result.get("used_web")),
                },
            })
    except Exception as exc:
        _debug_write("l8_feedback_relearn_error", {"error": str(exc)})


def run_self_repair_planning_task(rule_item: dict):
    MAX_REPAIR_RETRIES = 1
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

        # preview + 可能 auto_apply，失败时有限重试
        for attempt in range(1 + MAX_REPAIR_RETRIES):
            report = _preview_self_repair_report(
                report_id=str(report.get("id") or ""),
                config=config,
                auto_apply=bool(config.get("allow_self_repair_auto_apply", True)),
                run_validation=bool(config.get("allow_self_repair_test_run", True)),
            )
            status = str(report.get("status") or "")
            apply_status = str((report.get("apply_result") or {}).get("status") or "")
            # 成功或等待审核 → 不需要重试
            if status in ("applied", "applied_without_validation", "awaiting_confirmation", "proposal_ready"):
                break
            # 可重试的失败：语法错误、patch 匹配失败、patch 生成失败
            retryable = apply_status in ("syntax_error_before_write", "edit_validation_failed", "patch_plan_failed")
            preview_failed = str((report.get("patch_preview") or {}).get("status") or "") == "preview_failed"
            if (retryable or preview_failed) and attempt < MAX_REPAIR_RETRIES:
                _debug_write("self_repair_retry", {
                    "report_id": report.get("id"), "attempt": attempt + 1,
                    "reason": apply_status or "preview_failed",
                })
                continue
            break

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
