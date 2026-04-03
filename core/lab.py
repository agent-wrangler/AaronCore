"""锻造炉：L7 候选工作台的数据聚合器。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state_data"
LAB_DIR = STATE_DIR / "lab"
LAB_DIR.mkdir(parents=True, exist_ok=True)

FORGE_QUEUE_FILE = LAB_DIR / "forge_queue.json"
EVOLUTION_FILE = STATE_DIR / "evolution.json"
REPORTS_FILE = STATE_DIR / "self_repair_reports.json"
RULES_FILE = STATE_DIR / "feedback_rules.json"

MAX_QUEUE_ITEMS = 60


def init(*, llm_call=None, debug_write=None):
    """Compatibility hook kept for existing bootstrap code."""
    return None


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return default


def _save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_time(value: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "T" in text:
        text = text.replace("T", " ")
    return text[:19]


def _load_queue() -> list[dict]:
    data = _load_json(FORGE_QUEUE_FILE, [])
    if not isinstance(data, list):
        return []
    rows = []
    for item in data:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "").strip()
        # 旧 forge_queue 里有一批历史实验残留，这一版先不继续往前带。
        if source and source not in {"manual_forge", "l7_forge", "failure_candidate", "rule_candidate"}:
            continue
        rows.append(item)
    rows.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return rows


def _save_queue(rows: list[dict]):
    rows = [item for item in rows if isinstance(item, dict)]
    rows.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    _save_json(FORGE_QUEUE_FILE, rows[:MAX_QUEUE_ITEMS])


def _build_failed_run_candidates(limit: int = 16) -> list[dict]:
    data = _load_json(EVOLUTION_FILE, {})
    runs = data.get("skill_runs", [])
    if not isinstance(runs, list):
        return []

    items = []
    for run in reversed(runs):
        if not isinstance(run, dict):
            continue
        drift_reason = str(run.get("drift_reason") or "").strip()
        verified = run.get("verified")
        success = bool(run.get("success"))
        needs_attention = (not success) or (verified is False) or bool(drift_reason)
        if not needs_attention:
            continue

        skill = str(run.get("skill") or "unknown").strip()
        summary = str(run.get("summary") or "").strip()
        observed = str(run.get("observed_state") or "").strip()
        expected = str(run.get("expected_state") or "").strip()
        repair_hint = str(run.get("repair_hint") or "").strip()
        outcome = str(run.get("outcome") or "").strip()
        title = skill or "unknown"
        detail_parts = []
        if summary:
            detail_parts.append(summary)
        if drift_reason:
            detail_parts.append(f"drift={drift_reason}")
        elif verified is False:
            detail_parts.append("verified=false")
        if observed:
            detail_parts.append(f"observed={observed}")
        if expected:
            detail_parts.append(f"expected={expected}")
        if outcome and outcome not in detail_parts:
            detail_parts.append(outcome)

        item_id = f"run_{_normalize_time(run.get('at')).replace(' ', '_').replace(':', '').replace('-', '')}_{skill}"
        items.append(
            {
                "id": item_id,
                "kind": "failed_run",
                "status": "needs_attention",
                "created_at": _normalize_time(run.get("at")),
                "updated_at": _normalize_time(run.get("at")),
                "title": title,
                "subtitle": " / ".join([part for part in detail_parts if part]) or "这次执行没有闭环",
                "goal": str(run.get("target") or "").strip(),
                "summary": summary,
                "meta": {
                    "skill": skill,
                    "verified": verified,
                    "success": success,
                    "drift_reason": drift_reason,
                    "repair_hint": repair_hint,
                    "observed_state": observed,
                    "expected_state": expected,
                    "action_kind": str(run.get("action_kind") or "").strip(),
                    "target_kind": str(run.get("target_kind") or "").strip(),
                    "verification_mode": str(run.get("verification_mode") or "").strip(),
                },
            }
        )
        if len(items) >= limit:
            break
    return items


def _build_self_repair_candidates(limit: int = 10) -> list[dict]:
    from core.self_repair import load_self_repair_reports

    rows = load_self_repair_reports(limit=limit)
    items = []
    for report in rows:
        if not isinstance(report, dict):
            continue
        status = str(report.get("status") or "").strip()
        scene = str(report.get("scene") or "").strip()
        problem = str(report.get("problem") or "").strip()
        title = str(report.get("label") or report.get("scene") or "L7提案").strip()
        summary = str(report.get("summary") or report.get("diagnosis") or "").strip()
        preview = report.get("patch_preview") or {}
        validation = report.get("validation") or {}
        preview_status = str(preview.get("status") or "").strip()
        issue_key = str(report.get("issue_key") or "").strip()

        # 锻造炉先只看更像“技术候选”的提案，旧时代那些过泛的通用提案先隐掉。
        if problem not in {"skill_failed", "chat_exception"}:
            continue
        if scene not in {"skill_failed", "chat_exception"}:
            continue
        if issue_key == "general_refine" and preview_status not in {"preview_ready"} and status not in {"awaiting_confirmation"}:
            continue

        parts = []
        if summary:
            parts.append(summary)
        if preview_status:
            parts.append(f"preview={preview_status}")
        if validation.get("ran"):
            parts.append("validation=ran")
        items.append(
            {
                "id": str(report.get("id") or ""),
                "kind": "self_repair_report",
                "status": status or "needs_attention",
                "created_at": _normalize_time(report.get("created_at")),
                "updated_at": _normalize_time(report.get("updated_at") or report.get("created_at")),
                "title": title,
                "subtitle": " / ".join([part for part in parts if part]) or "已生成一条自修复候选提案",
                "goal": str(report.get("last_question") or "").strip(),
                "summary": summary,
                "meta": {
                    "scene": str(report.get("scene") or "").strip(),
                    "problem": str(report.get("problem") or "").strip(),
                    "risk_level": str(report.get("risk_level") or "").strip(),
                    "auto_apply_ready": bool(report.get("auto_apply_ready")),
                    "preview_status": preview_status,
                    "preview_summary": str(preview.get("summary") or "").strip(),
                    "preview_error": str(preview.get("error") or "").strip(),
                    "preview_decision": str(preview.get("decision_reason") or "").strip(),
                },
            }
        )
        if len(items) >= limit:
            break
    return items


def _load_rules(limit: int = 8) -> list[dict]:
    data = _load_json(RULES_FILE, [])
    if not isinstance(data, list):
        return []
    rows = [item for item in data if isinstance(item, dict)]
    rows.sort(key=lambda item: str(item.get("created_at") or item.get("time") or ""), reverse=True)
    return rows[:limit]


def _build_rule_items(limit: int = 8) -> list[dict]:
    items = []
    for rule in _load_rules(limit=limit):
        feedback = str(rule.get("user_feedback") or "").strip()
        fix = str(rule.get("fix") or "").strip()
        category = str(rule.get("category") or "L7规则").strip()
        detail = feedback or fix or "一条已沉淀的 L7 规则"
        items.append(
            {
                "id": str(rule.get("id") or ""),
                "kind": "l7_rule",
                "status": "active" if rule.get("enabled", True) else "disabled",
                "created_at": _normalize_time(rule.get("created_at") or rule.get("time")),
                "updated_at": _normalize_time(rule.get("last_hit_at") or rule.get("created_at") or rule.get("time")),
                "title": category,
                "subtitle": detail[:140],
                "goal": str(rule.get("last_question") or "").strip(),
                "summary": fix[:180] if fix else detail[:180],
                "meta": {
                    "hit_count": int(rule.get("hit_count", 0) or 0),
                    "scene": str(rule.get("scene") or "").strip(),
                },
            }
        )
    return items


def get_status() -> dict:
    queue = _load_queue()
    failed_runs = _build_failed_run_candidates(limit=24)
    reports = _build_self_repair_candidates(limit=12)
    rules = _build_rule_items(limit=8)
    return {
        "state": "ready",
        "summary": {
            "queued": len(queue),
            "failed_runs": len(failed_runs),
            "repair_reports": len(reports),
            "active_rules": len(rules),
        },
        "queue": queue[:18],
        "failed_runs": failed_runs,
        "reports": reports,
        "rules": rules,
    }


def get_targets() -> list[dict]:
    return [
        {
            "key": "l7_forge",
            "label": "L7 锻造炉",
            "description": "最近失败轨迹、自修复提案、待锻造需求",
            "content_preview": "用于观察失败、提炼修正候选，不再跑旧实验变异。",
        }
    ]


def read_target(key: str) -> str:
    if str(key or "").strip() == "l7_forge":
        return "L7 锻造炉：观察失败轨迹、自修复提案、待锻造需求。"
    return f"[未找到目标: {key}]"


def get_experiments() -> list[dict]:
    status = get_status()
    rows = []
    rows.extend(status.get("queue", []))
    rows.extend(status.get("reports", []))
    rows.extend(status.get("failed_runs", []))
    rows.extend(status.get("rules", []))
    rows.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return rows


def get_experiment(exp_id: str) -> dict | None:
    wanted = str(exp_id or "").strip()
    if not wanted:
        return None
    for item in get_experiments():
        if str(item.get("id") or "").strip() == wanted:
            return item
    return None


def create_experiment(target_key: str = "", goal: str = "", rounds: int = 10, test_inputs: list[str] | None = None) -> dict:
    need = str(goal or "").strip()
    if not need:
        return {"ok": False, "error": "need_required"}

    now = datetime.now().isoformat()
    item = {
        "id": f"forge_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        "status": "queued",
        "need": need,
        "query": need,
        "source": "manual_forge",
        "created_at": now,
        "updated_at": now,
        "meta": {
            "target_key": str(target_key or "l7_forge"),
            "rounds": int(rounds or 0),
            "test_inputs": list(test_inputs or []),
        },
    }
    rows = _load_queue()
    rows = [existing for existing in rows if str(existing.get("query") or "").strip() != need]
    rows.append(item)
    _save_queue(rows)
    return item


def start_experiment(exp_id: str) -> dict:
    wanted = str(exp_id or "").strip()
    if not wanted:
        return {"ok": False, "error": "forge_id_required"}
    rows = _load_queue()
    updated = False
    now = datetime.now().isoformat()
    for item in rows:
        if str(item.get("id") or "").strip() == wanted:
            item["status"] = "reviewing"
            item["updated_at"] = now
            updated = True
            break
    if updated:
        _save_queue(rows)
        return {"ok": True}
    return {"ok": False, "error": "forge_item_not_found"}


def stop_experiment() -> dict:
    return {"ok": True, "detail": "L7 锻造炉当前没有后台实验循环可停止。"}


def apply_best_result(exp_id: str) -> dict:
    wanted = str(exp_id or "").strip()
    if not wanted:
        return {"ok": False, "error": "forge_id_required"}
    rows = _load_queue()
    updated = False
    now = datetime.now().isoformat()
    for item in rows:
        if str(item.get("id") or "").strip() == wanted:
            item["status"] = "promoted"
            item["updated_at"] = now
            updated = True
            break
    if updated:
        _save_queue(rows)
        return {"ok": True, "detail": "已标记为后续可提炼到 L7 的候选。"}
    return {"ok": False, "error": "forge_item_not_found"}
