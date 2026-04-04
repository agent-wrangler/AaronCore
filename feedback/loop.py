# feedback_loop - 鍙嶉璁板綍銆佸悗鍙板涔犱换鍔?
# 浠?agent_final.py 鎻愬彇

from datetime import datetime
from pathlib import Path

from core.runtime_state.state_loader import PRIMARY_STATE_DIR

# 鈹€鈹€ 娉ㄥ叆渚濊禆 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
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


# 鈹€鈹€ 鍙嶉璁板綍 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€



def l7_record_feedback(msg: str, history: list, background_tasks=None):
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

    if last_q:
        try:
            from core.feedback_classifier import record_feedback_rule

            rule_item = record_feedback_rule(msg, last_q, last_answer)
            if rule_item:
                _debug_write("feedback_rule", rule_item)
        except Exception as exc:
            _debug_write("feedback_rule_error", {"error": str(exc)})


# 鈹€鈹€ self-repair锛氱郴缁熸晠闅?+ 鐢ㄦ埛鍙嶉涓殑浠ｇ爜绾ч棶棰?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# 浠ｇ爜绾ч棶棰橈紙璺敱璋冨害绛夛級闇€瑕佺湡姝ｆ敼浠ｇ爜鎵嶈兘淇紝浠呴潬 prompt 鎻愮ず涓嶅
_SELF_REPAIR_CATEGORIES = {"璺敱璋冨害", "绯荤粺鏁呴殰", "鎰忓浘鐞嗚В"}


def trigger_self_repair_from_error(
    error_type: str,
    error_detail: dict,
    background_tasks=None,
):
    """浠庣郴缁熸晠闅滀簨浠惰Е鍙?self-repair銆?

    error_type: skill_failed | skill_missing | core_route_error | chat_exception
    error_detail: 鍖呭惈 skill, error, input 绛変笂涓嬫枃淇℃伅
    """
    l8_config = _load_autolearn_config()
    if not l8_config.get("allow_self_repair_planning", True):
        return None

    # 鏋勯€犱竴涓被浼?feedback_rule 鐨勭粨鏋勭粰 self-repair 娴佺▼澶嶇敤
    rule_item = {
        "id": f"sys_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        "source": "system_error",
        "created_at": datetime.now().isoformat(),
        "enabled": True,
        "scene": error_type,
        "problem": error_type,
        "type": "system_error",
        "category": "绯荤粺鏁呴殰",
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
    """鏁堟灉杩借釜锛氬鏋滄湁鏃ц鍒欐渶杩戝懡涓繃浣嗙敤鎴蜂粛涓嶆弧鎰忥紝鍗囩骇澶勭悊寮哄害銆?
    L1(prompt) fail>=2 鈫?琛ョ敓鎴?L2 绾︽潫 + 浜や簰椋庢牸绫诲啓鍥?L4
    L2(绾︽潫) fail>=2 鈫?瑙﹀彂 L3 self-repair
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
        # 鍙湅鏈€杩?24 灏忔椂鍐呭懡涓繃鐨勮鍒?
        last_hit = rule.get("last_hit_at", "")
        if not last_hit or last_hit < cutoff:
            continue
        # 妫€鏌ユ棫瑙勫垯鐨?last_question 鍜屾柊鍙嶉鐨?last_question 鏄惁鐩镐技
        old_q = str(rule.get("last_question", ""))
        if not old_q or len(old_q) < 2:
            continue
        if old_q[:4] not in last_q and last_q[:4] not in old_q:
            continue

        # 鍛戒腑浜嗭細杩欐潯鏃ц鍒欐病鑳介樆姝㈤棶棰樺啀娆″彂鐢?
        rule["fail_count"] = (rule.get("fail_count") or 0) + 1
        dirty = True
        fail_count = rule["fail_count"]

        _debug_write("l7_rule_failed", {
            "rule_id": rule.get("id"), "fail_count": fail_count,
            "has_constraint": bool(rule.get("constraint")),
        })

        # L1 鈫?L2 鍗囩骇锛歱rompt 鎻愰啋澶辫触 2 娆★紝琛ョ敓鎴愯矾鐢辩害鏉?
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

            # 鎵€鏈夌被鍒弽棣?鈫?淇妗堟満鍒讹紙L7鈫扡4/L5锛?
            if not rule.get("l4_amended"):
                _l7_apply_amendment(rule)

        # L2 鈫?L3 鍗囩骇锛氳矾鐢辩害鏉熶篃澶辫触 2 娆★紝瑙﹀彂 self-repair
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
    """Apply stable feedback amendments to L4 profile rules only."""
    category = rule.get("category", "")
    fix = str(rule.get("fix", "")).strip()
    feedback = str(rule.get("user_feedback", "")).strip()
    amendment = fix if fix and fix != "keep_observing_and_refine" else feedback
    if not amendment or len(amendment) < 4:
        return

    # Keep L7 amendments constrained to explicit L4 interaction rules.
    _amend_l4_rules(rule, amendment, category)



def _amend_l4_rules(rule: dict, amendment: str, category: str):
    """鍐欏叆 L4 interaction_rules锛屾寜 category 鍔犲墠缂€鏍囨敞鏉ユ簮"""
    from core.runtime_state.json_store import load_json, write_json

    # 鎸夌被鍒姞璇箟鍓嶇紑锛岃 LLM 鐞嗚В杩欐潯瑙勫垯鐨勭敤閫?
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
        # 鍘婚噸
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




def l7_record_feedback_v2(msg: str, history: list, background_tasks=None):
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
        if not rule_item:
            return None
        _debug_write("feedback_rule", rule_item)

        # 鈹€鈹€ 鏁堟灉杩借釜锛氭鏌ユ槸鍚︽湁宸插懡涓絾浠嶅け璐ョ殑鏃ц鍒?鈫?鍗囩骇澶勭悊 鈹€鈹€
        try:
            _check_and_escalate_failed_rules(last_q, rule_item, background_tasks)
        except Exception as esc_err:
            _debug_write("l7_escalate_error", {"error": str(esc_err)})

        # L7 鍙嶉鍒嗘祦锛?
        # - 鍐呭鐢熸垚/浜や簰椋庢牸/鎰忓浘鐞嗚В 鈫?鐣欏湪 L7锛岄€氳繃 prompt 鎻愮ず褰卞搷涓嬫鍥炲
        # - 璺敱璋冨害/绯荤粺鏁呴殰 鈫?鍚屾椂瑙﹀彂 self-repair锛岄渶瑕佺湡姝ｆ敼浠ｇ爜
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


# 鈹€鈹€ L8 鐘舵€?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def l8_touch():
    _debug_write(
        "l8_status",
        {
            "growth_exists": (PRIMARY_STATE_DIR / "growth.json").exists(),
            "evolution_exists": (PRIMARY_STATE_DIR / "evolution.json").exists(),
            "knowledge_base_exists": (PRIMARY_STATE_DIR / "knowledge_base.json").exists(),
        },
    )


# 鈹€鈹€ 鍚庡彴瀛︿範浠诲姟 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

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

        # 鈹€鈹€ 鎰熺煡灞傦細鎺ㄩ€佸涔犱簨浠?鈹€鈹€
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

        # 鈹€鈹€ 鎰熺煡灞傦細鎺ㄩ€佸弽棣堥噸瀛︿簨浠?鈹€鈹€
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

        # preview + 鍙兘 auto_apply锛屽け璐ユ椂鏈夐檺閲嶈瘯
        for attempt in range(1 + MAX_REPAIR_RETRIES):
            report = _preview_self_repair_report(
                report_id=str(report.get("id") or ""),
                config=config,
                auto_apply=bool(config.get("allow_self_repair_auto_apply", True)),
                run_validation=bool(config.get("allow_self_repair_test_run", True)),
            )
            status = str(report.get("status") or "")
            apply_status = str((report.get("apply_result") or {}).get("status") or "")
            # 鎴愬姛鎴栫瓑寰呭鏍?鈫?涓嶉渶瑕侀噸璇?
            if status in ("applied", "applied_without_validation", "awaiting_confirmation", "proposal_ready"):
                break
            # 鍙噸璇曠殑澶辫触锛氳娉曢敊璇€乸atch 鍖归厤澶辫触銆乸atch 鐢熸垚澶辫触
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


# 鈹€鈹€ 璇婃柇 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

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
