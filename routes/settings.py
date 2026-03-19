"""设置相关路由：autolearn、self_repair、L7 stats"""
import json
from fastapi import APIRouter
from core import shared as S

router = APIRouter()


@router.get("/autolearn/config")
async def get_autolearn_config():
    return {"config": S.load_autolearn_config()}


@router.post("/autolearn/config")
async def set_autolearn_config(request: dict):
    patch = request if isinstance(request, dict) else {}
    config = S.update_autolearn_config(patch)
    return {"ok": True, "config": config}


@router.get("/autolearn/diagnose")
async def get_autolearn_diagnosis(query: str, route_mode: str = "chat", skill: str = "none", limit: int = 3):
    return S.build_l8_diagnosis(query, route_mode=route_mode, skill=skill, limit=limit)


@router.get("/l7/stats")
async def get_l7_stats():
    from core.feedback_classifier import _load_rules as _l7_load_rules
    rules = _l7_load_rules()
    total = len(rules)
    with_constraint = sum(1 for r in rules if r.get("constraint"))
    categories = {}
    for r in rules:
        cat = r.get("category", "\u672a\u5206\u7c7b")
        categories[cat] = categories.get(cat, 0) + 1
    latest = None
    if rules:
        rules_sorted = sorted(rules, key=lambda x: x.get("created_at", ""), reverse=True)
        if rules_sorted:
            lt = rules_sorted[0]
            latest = {
                "fix": str(lt.get("fix", ""))[:60],
                "category": lt.get("category", ""),
                "created_at": lt.get("created_at", ""),
            }
    l8_data = S.load_json(S.PRIMARY_STATE_DIR / "knowledge_base.json", [])
    l8_count = len([e for e in l8_data if isinstance(e, dict) and e.get("type") != "feedback_relearn"])
    repair_reports = []
    try:
        repair_reports = S.load_self_repair_reports()
    except Exception:
        pass
    return {
        "l7_rule_count": total,
        "l7_constraint_count": with_constraint,
        "l7_categories": categories,
        "l7_latest": latest,
        "l8_knowledge_count": l8_count,
        "repair_report_count": len(repair_reports),
    }


@router.get("/self_repair/status")
async def get_self_repair_status():
    import agent_final as _af
    return {"status": _af.build_self_repair_status()}


@router.get("/self_repair/reports")
async def get_self_repair_reports(limit: int = 6):
    return {"reports": S.load_self_repair_reports(limit=max(limit, 1))}


@router.post("/self_repair/propose")
async def create_self_repair_proposal(request: dict | None = None):
    payload = request if isinstance(request, dict) else {}
    rule_id = str(payload.get("feedback_rule_id") or "").strip()
    rule_item = S.find_feedback_rule(rule_id)
    if not rule_item:
        return {"ok": False, "error": "feedback_rule_not_found"}
    config = S.load_autolearn_config()
    run_validation = bool(payload.get("run_validation", config.get("allow_self_repair_test_run", True)))
    report = S.create_self_repair_report(
        rule_item,
        config=config,
        run_validation=run_validation and bool(config.get("allow_self_repair_test_run", True)),
    )
    return {"ok": True, "report": report}


@router.post("/self_repair/preview")
async def preview_self_repair_fix(request: dict | None = None):
    payload = request if isinstance(request, dict) else {}
    report_id = str(payload.get("report_id") or "").strip()
    config = S.load_autolearn_config()
    auto_apply = bool(payload.get("auto_apply", False))
    run_validation = bool(payload.get("run_validation", config.get("allow_self_repair_test_run", True)))
    try:
        report = S.preview_self_repair_report(
            report_id=report_id,
            config=config,
            auto_apply=auto_apply,
            run_validation=run_validation,
        )
        S.debug_write(
            "self_repair_preview",
            {
                "report_id": report.get("id"),
                "preview_status": ((report.get("patch_preview") or {}).get("status")),
                "preview_edit_count": len(((report.get("patch_preview") or {}).get("edits")) or []),
                "risk_level": ((report.get("patch_preview") or {}).get("risk_level")),
                "auto_apply_ready": ((report.get("patch_preview") or {}).get("auto_apply_ready")),
                "apply_status": ((report.get("apply_result") or {}).get("status")),
            },
        )
        return {"ok": True, "report": report}
    except Exception as exc:
        S.debug_write("self_repair_preview_error", {"error": str(exc), "report_id": report_id})
        return {"ok": False, "error": str(exc)}


@router.post("/self_repair/apply")
async def apply_self_repair_fix(request: dict | None = None):
    payload = request if isinstance(request, dict) else {}
    report_id = str(payload.get("report_id") or "").strip()
    config = S.load_autolearn_config()
    try:
        report = S.apply_self_repair_report(report_id=report_id, config=config, run_validation=True)
        S.debug_write(
            "self_repair_apply",
            {
                "report_id": report.get("id"),
                "status": report.get("status"),
                "apply_status": ((report.get("apply_result") or {}).get("status")),
                "rolled_back": ((report.get("apply_result") or {}).get("rolled_back")),
            },
        )
        return {"ok": True, "report": report}
    except Exception as exc:
        S.debug_write("self_repair_apply_error", {"error": str(exc), "report_id": report_id})
        return {"ok": False, "error": str(exc)}
