import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "memory_db"
REPORTS_FILE = STATE_DIR / "self_repair_reports.json"
FEEDBACK_RULES_FILE = STATE_DIR / "feedback_rules.json"
MAX_REPORTS = 80
DEFAULT_TEST_TIMEOUT_SEC = 45
DEFAULT_PATCH_TIMEOUT_SEC = 40
MAX_PATCH_FILE_CONTEXT_CHARS = 12000
MAX_PATCH_TOTAL_CONTEXT_CHARS = 24000
MAX_PATCH_FILE_COUNT = 4
MAX_PATCH_EDIT_COUNT = 6
AUTO_APPLY_MAX_FILE_COUNT = 2
AUTO_APPLY_MAX_EDIT_COUNT = 3


from core.runtime_state.json_store import load_json as _load_json, write_json as _write_json


def load_self_repair_reports(limit: int | None = None) -> list[dict]:
    data = _load_json(REPORTS_FILE, [])
    if not isinstance(data, list):
        data = []
    rows = [item for item in data if isinstance(item, dict)]
    rows.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    if limit is not None:
        return rows[: max(int(limit), 0)]
    return rows


def save_self_repair_report(report: dict) -> dict:
    data = load_self_repair_reports()
    kept = [item for item in data if str(item.get("id") or "") != str(report.get("id") or "")]
    kept.append(report)
    kept.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    _write_json(REPORTS_FILE, kept[:MAX_REPORTS])
    return report


def load_feedback_rules(limit: int | None = None) -> list[dict]:
    data = _load_json(FEEDBACK_RULES_FILE, [])
    if not isinstance(data, list):
        data = []
    rows = [item for item in data if isinstance(item, dict)]
    rows.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    if limit is not None:
        return rows[: max(int(limit), 0)]
    return rows


def find_feedback_rule(rule_id: str = "") -> dict | None:
    wanted = str(rule_id or "").strip()
    rules = load_feedback_rules()
    if not rules:
        return None
    if not wanted:
        return rules[0]
    for item in rules:
        if str(item.get("id") or "").strip() == wanted:
            return item
    return None


def get_self_repair_report(report_id: str = "") -> dict | None:
    wanted = str(report_id or "").strip()
    reports = load_self_repair_reports()
    if not reports:
        return None
    if not wanted:
        return reports[0]
    for item in reports:
        if str(item.get("id") or "").strip() == wanted:
            return item
    return None


def _contains_any(text: str, words: list[str] | tuple[str, ...]) -> bool:
    haystack = str(text or "")
    return any(word in haystack for word in words)


def _dedupe_items(items: list[dict]) -> list[dict]:
    out = []
    seen = set()
    for item in items:
        path = str((item or {}).get("path") or "").strip()
        if not path or path in seen:
            continue
        out.append({"path": path, "reason": str(item.get("reason") or "").strip()})
        seen.add(path)
    return out


def _route_candidate_files(text: str) -> list[dict]:
    candidates = [
        {"path": "core/router.py", "reason": "第一层技能/聊天分流在这里，最容易把问题提前送错路。"},
        {"path": "agent_final.py", "reason": "主链会在这里合并 core 路由和后续补救逻辑。"},
    ]

    if _contains_any(text, ("代码", "编程", "游戏", "run_code")):
        candidates.append({"path": "core/skills/run_code.json", "reason": "如果编程技能关键词太宽，会误吸“能力提问/元提问”。"})
    if _contains_any(text, ("天气", "温度", "多少度", "乌鲁木齐", "新疆")):
        candidates.append({"path": "core/skills/weather.py", "reason": "天气技能的地点提取和追问继承都在这里。"})
    if _contains_any(text, ("故事", "太短", "讲长一点", "继续讲")):
        candidates.append({"path": "core/skills/story.py", "reason": "故事长度和续写内容在这里生成。"})

    return _dedupe_items(candidates)


def _route_candidate_tests(text: str) -> list[dict]:
    tests = [{"path": "tests/test_capability_routing.py", "reason": "先确认路由不会再把能力提问误判成技能。"}]
    if _contains_any(text, ("天气", "温度", "多少度", "乌鲁木齐", "新疆")):
        tests.append({"path": "tests/test_weather_skill.py", "reason": "检查天气技能的城市识别和追问继承没有回归。"})
    if _contains_any(text, ("故事", "太短", "讲长一点", "继续讲")):
        tests.append({"path": "tests/test_story_skill.py", "reason": "检查故事技能长度和续写状态。"})
        tests.append({"path": "tests/test_story_routing.py", "reason": "检查故事追问仍能走对上下文路由。"})
    return _dedupe_items(tests)


def _generic_chat_files() -> list[dict]:
    return _dedupe_items(
        [
            {"path": "agent_final.py", "reason": "普通聊天的统一回复包装和主链回路都在这里。"},
            {"path": "brain/__init__.py", "reason": "本地人格兜底和能力回答模板还在这里兜底。"},
        ]
    )


def _generic_chat_tests() -> list[dict]:
    return _dedupe_items(
        [
            {"path": "tests/test_capability_routing.py", "reason": "先确认能力提问和普通聊天还在对的链路上。"},
            {"path": "tests/test_trace_payload.py", "reason": "检查思路气泡 payload 没被带坏。"},
        ]
    )


def _story_length_files() -> list[dict]:
    return _dedupe_items(
        [
            {"path": "core/skills/story.py", "reason": "故事正文长度、章节衔接和持久化状态都在这里。"},
            {"path": "agent_final.py", "reason": "故事技能的包装文案和续写引导也会影响用户体感。"},
        ]
    )


def _story_length_tests() -> list[dict]:
    return _dedupe_items(
        [
            {"path": "tests/test_story_skill.py", "reason": "先卡住故事长度、标题和续写状态。"},
            {"path": "tests/test_story_routing.py", "reason": "确保“然后呢”仍会顺着故事继续。"},
        ]
    )


def _ability_files() -> list[dict]:
    return _dedupe_items(
        [
            {"path": "agent_final.py", "reason": "能力说明和自修正状态直答现在在这里输出。"},
            {"path": "core/router.py", "reason": "要先保证“能力提问”不会误走技能分支。"},
            {"path": "brain/__init__.py", "reason": "如果远端模型回坏，兜底人格层也要能把能力说清楚。"},
        ]
    )


def _ability_tests() -> list[dict]:
    return _dedupe_items(
        [
            {"path": "tests/test_capability_routing.py", "reason": "能力提问、自修正提问和 run_code 真请求都在这里回归。"},
            {"path": "tests/test_trace_payload.py", "reason": "检查纯聊天不会被错误挂上技能 trace。"},
        ]
    )


def _build_issue_profile(rule_item: dict) -> dict:
    rule_item = rule_item if isinstance(rule_item, dict) else {}
    scene = str(rule_item.get("scene") or "").strip()
    problem = str(rule_item.get("problem") or "").strip()
    fix = str(rule_item.get("fix") or "").strip()
    feedback = str(rule_item.get("user_feedback") or "").strip()
    last_question = str(rule_item.get("last_question") or "").strip()
    last_answer = str(rule_item.get("last_answer") or "").strip()
    text = "\n".join([last_question, last_answer, feedback]).strip()

    if problem == "wrong_skill_selected" or fix == "adjust_skill_routing_for_scene":
        return {
            "issue_key": "routing_mismatch",
            "label": "技能走错路",
            "diagnosis": "这次更像是路由层先把问题送进了不该去的技能分支，优先排查上游分流，而不是只在最终回复层打补丁。",
            "candidate_files": _route_candidate_files(text),
            "suggested_tests": _route_candidate_tests(text),
        }

    if problem == "length_too_short" or fix == "story_should_expand_when_user_requests_more" or scene == "story":
        return {
            "issue_key": "story_length",
            "label": "内容展开不够",
            "diagnosis": "这次问题在内容生成和续写包装层，先看故事正文长度，再看故事技能返回给主链时有没有被截短。",
            "candidate_files": _story_length_files(),
            "suggested_tests": _story_length_tests(),
        }

    if problem == "fallback_too_generic" or fix == "ability_queries_should_answer_capabilities_directly":
        return {
            "issue_key": "capability_answering",
            "label": "能力说明太空",
            "diagnosis": "这次不是能力没有，而是回答没有把“现在会到哪一步、还差哪一步”说清楚，优先排查能力直答链路。",
            "candidate_files": _ability_files(),
            "suggested_tests": _ability_tests(),
        }

    return {
        "issue_key": "general_refine",
        "label": "通用纠偏",
        "diagnosis": "这次反馈比较泛，先从主回复层和上游路由层做最小排查，再决定要不要扩到技能内部。",
        "candidate_files": _generic_chat_files(),
        "suggested_tests": _generic_chat_tests(),
    }


def _build_patch_prompt(report: dict) -> str:
    report = report if isinstance(report, dict) else {}
    file_paths = [item.get("path", "") for item in report.get("candidate_files") or [] if item.get("path")]
    test_paths = [item.get("path", "") for item in report.get("suggested_tests") or [] if item.get("path")]
    return (
        f"反馈问题：{report.get('label', '待分析')}\n"
        f"问题摘要：{report.get('summary', '')}\n"
        f"诊断：{report.get('diagnosis', '')}\n"
        f"优先候选文件：{', '.join(file_paths) or '无'}\n"
        f"最小验证：{', '.join(test_paths) or '无'}\n"
        "修正原则：先改更上游的分流或包装层，再改技能内部；先通过最小回归，再决定是否继续扩改。"
    ).strip()


def _pending_report_status(report: dict) -> str:
    return "awaiting_confirmation" if str((report or {}).get("apply_mode") or "confirm").strip() == "confirm" else "proposal_ready"


def _is_safe_auto_apply_path(path_str: str) -> bool:
    rel = str(path_str or "").strip().replace("\\", "/")
    if not rel.startswith("core/skills/"):
        return False
    if rel.endswith("/__init__.py") or rel.endswith("__init__.py"):
        return False
    return rel.endswith(".py") or rel.endswith(".json")


def _validation_all_passed(report: dict) -> bool:
    validation = (report or {}).get("validation") or {}
    return bool(validation.get("ran")) and bool(validation.get("all_passed"))


def _build_auto_apply_decision(report: dict, patch_plan: dict) -> dict:
    report = report if isinstance(report, dict) else {}
    patch_plan = patch_plan if isinstance(patch_plan, dict) else {}
    edits = [item for item in (patch_plan.get("edits") or []) if isinstance(item, dict)]

    unique_paths = []
    seen = set()
    for item in edits:
        rel_path = str(item.get("path") or "").strip().replace("\\", "/")
        if rel_path and rel_path not in seen:
            unique_paths.append(rel_path)
            seen.add(rel_path)

    allowed_paths = {
        str(path or "").strip().replace("\\", "/")
        for path in patch_plan.get("allowed_paths") or []
        if str(path or "").strip()
    }
    validation_ok = _validation_all_passed(report)
    small_change = bool(edits) and len(edits) <= AUTO_APPLY_MAX_EDIT_COUNT and len(unique_paths) <= AUTO_APPLY_MAX_FILE_COUNT
    safe_paths = bool(unique_paths) and all(_is_safe_auto_apply_path(path) for path in unique_paths)
    paths_allowed = bool(unique_paths) and all(path in allowed_paths for path in unique_paths)

    reason = "confirmation_needed"
    if not patch_plan.get("ok"):
        risk_level = "high"
        reason = str(patch_plan.get("error") or "patch_plan_failed")
    elif not validation_ok:
        risk_level = "high"
        reason = "validation_not_green"
    elif safe_paths and small_change and paths_allowed:
        risk_level = "low"
        reason = "safe_small_skill_patch"
    else:
        risk_level = "medium"
        reason = "touches_wider_surface"

    auto_apply_ready = risk_level == "low"
    return {
        "risk_level": risk_level,
        "reason": reason,
        "edit_count": len(edits),
        "file_count": len(unique_paths),
        "paths": unique_paths,
        "validation_ok": validation_ok,
        "auto_apply_ready": auto_apply_ready,
        "confirmation_required": not auto_apply_ready,
    }


def _update_report_decision(report: dict, preview: dict):
    preview = preview if isinstance(preview, dict) else {}
    report["risk_level"] = str(preview.get("risk_level") or "")
    report["auto_apply_ready"] = bool(preview.get("auto_apply_ready"))
    report["requires_confirmation"] = bool(preview.get("confirmation_required", True))


def _resolve_repo_path(path_str: str) -> Path | None:
    rel = str(path_str or "").strip().replace("\\", "/")
    if not rel:
        return None
    root = ROOT.resolve()
    try:
        resolved = (root / rel).resolve()
        resolved.relative_to(root)
        return resolved
    except Exception:
        return None


def _load_llm_config() -> dict:
    config_path = ROOT / "brain" / "llm_config.json"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                # 新格式：models + default
                if "models" in data:
                    default = data.get("default", "")
                    models = data["models"]
                    return models.get(default) or next(iter(models.values()), {})
                # 旧格式：顶层 api_key/model/base_url
                return data
        except Exception:
            pass
    return {"api_key": "", "model": "", "base_url": ""}


def _trim_preview(text: str, limit: int = 160) -> str:
    raw = str(text or "").strip()
    if len(raw) <= limit:
        return raw
    return raw[: max(limit - 1, 1)] + "…"


def _collect_patch_contexts(report: dict) -> tuple[list[dict], list[str]]:
    contexts = []
    allowed_paths = []
    total_chars = 0
    for item in (report.get("candidate_files") or [])[:MAX_PATCH_FILE_COUNT]:
        rel_path = str((item or {}).get("path") or "").strip().replace("\\", "/")
        abs_path = _resolve_repo_path(rel_path)
        if not rel_path or not abs_path or not abs_path.exists() or not abs_path.is_file():
            continue
        try:
            content = abs_path.read_text(encoding="utf-8")
        except Exception:
            continue
        truncated = False
        if len(content) > MAX_PATCH_FILE_CONTEXT_CHARS:
            half = MAX_PATCH_FILE_CONTEXT_CHARS // 2
            content = (
                content[:half]
                + "\n\n# ... middle omitted for safety ...\n\n"
                + content[-half:]
            )
            truncated = True
        if contexts and total_chars + len(content) > MAX_PATCH_TOTAL_CONTEXT_CHARS:
            break
        total_chars += len(content)
        contexts.append(
            {
                "path": rel_path,
                "reason": str((item or {}).get("reason") or "").strip(),
                "content": content,
                "truncated": truncated,
            }
        )
        allowed_paths.append(rel_path)
    return contexts, allowed_paths


def _build_patch_generation_prompt(report: dict, contexts: list[dict]) -> str:
    blocks = []
    for item in contexts:
        blocks.append(
            "\n".join(
                [
                    f"文件路径：{item['path']}",
                    f"为什么可能要改：{item['reason'] or '未说明'}",
                    f"内容是否截断：{'是' if item.get('truncated') else '否'}",
                    "文件内容开始：",
                    "```",
                    item["content"],
                    "```",
                ]
            )
        )
    return (
        "你是一个极其保守的代码修复器。现在要根据一份自修正提案，输出最小可执行编辑计划。\n\n"
        f"{_build_patch_prompt(report)}\n\n"
        "请只返回 JSON，不要加解释、不要加 Markdown。\n"
        "JSON 格式必须是：\n"
        "{\n"
        '  "summary": "一句话说明这次准备怎么修",\n'
        '  "edits": [\n'
        "    {\n"
        '      "path": "相对路径",\n'
        '      "old": "要被替换的原始连续文本，必须从给出的文件内容里原样复制",\n'
        '      "new": "替换后的连续文本",\n'
        '      "reason": "这条编辑的目的"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "硬性规则：\n"
        "1. 只允许改下面给出的候选文件。\n"
        "2. 不要创建新文件，不要删除文件。\n"
        "3. 每个 old 必须是连续原文，后端会精确匹配；匹配不到就会拒绝。\n"
        "4. 改动尽量小，优先改上游分流或包装层。\n"
        "5. 总编辑数不要超过 6 条；如果拿不准，返回 edits: []。\n\n"
        "候选文件内容：\n\n"
        + "\n\n".join(blocks)
    ).strip()


def _extract_json_payload(text: str) -> dict:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def generate_self_repair_patch_plan(report: dict, config: dict | None = None) -> dict:
    report = report if isinstance(report, dict) else {}
    config = config if isinstance(config, dict) else {}
    contexts, allowed_paths = _collect_patch_contexts(report)
    if not contexts:
        return {"ok": False, "error": "no_patch_context", "summary": "", "edits": [], "allowed_paths": []}

    llm_config = _load_llm_config()
    api_key = str(llm_config.get("api_key") or "").strip()
    model = str(llm_config.get("model") or "").strip()
    base_url = str(llm_config.get("base_url") or "").rstrip("/")
    if not api_key or not model or not base_url:
        return {"ok": False, "error": "llm_config_missing", "summary": "", "edits": [], "allowed_paths": allowed_paths}

    prompt = _build_patch_generation_prompt(report, contexts)
    timeout_sec = max(int(config.get("self_repair_patch_timeout_sec") or DEFAULT_PATCH_TIMEOUT_SEC), 10)
    try:
        from brain import llm_call
        result = llm_call(llm_config, [{"role": "user", "content": prompt}],
                          temperature=0.1, max_tokens=4000, timeout=timeout_sec)
        if result.get("error"):
            return {
                "ok": False,
                "error": f"llm_error: {result['error']}",
                "summary": "",
                "edits": [],
                "allowed_paths": allowed_paths,
            }
        raw_text = result.get("content", "").strip()
        parsed = _extract_json_payload(raw_text)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "summary": "", "edits": [], "allowed_paths": allowed_paths}

    edits = []
    for item in (parsed.get("edits") or [])[:MAX_PATCH_EDIT_COUNT]:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip().replace("\\", "/")
        old = str(item.get("old") or "")
        new = str(item.get("new") or "")
        reason = str(item.get("reason") or "").strip()
        if not path or not old or old == new:
            continue
        if path not in allowed_paths:
            continue
        edits.append({"path": path, "old": old, "new": new, "reason": reason})

    return {
        "ok": bool(edits),
        "error": "" if edits else "empty_patch_plan",
        "summary": str(parsed.get("summary") or "").strip(),
        "edits": edits,
        "allowed_paths": allowed_paths,
    }


def _prepare_updated_files(edits: list[dict], allowed_paths: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    allowed = {str(path or "").strip().replace("\\", "/") for path in allowed_paths or [] if path}
    originals = {}
    updated = {}
    for item in edits or []:
        rel_path = str((item or {}).get("path") or "").strip().replace("\\", "/")
        old = str((item or {}).get("old") or "")
        new = str((item or {}).get("new") or "")
        if rel_path not in allowed:
            raise ValueError(f"edit_path_not_allowed:{rel_path}")
        abs_path = _resolve_repo_path(rel_path)
        if not abs_path or not abs_path.exists() or not abs_path.is_file():
            raise ValueError(f"edit_path_missing:{rel_path}")
        if rel_path not in originals:
            originals[rel_path] = abs_path.read_text(encoding="utf-8")
            updated[rel_path] = originals[rel_path]
        current_text = updated[rel_path]
        hit_count = current_text.count(old)
        if hit_count != 1:
            raise ValueError(f"edit_old_snippet_match_count_{hit_count}:{rel_path}")
        updated[rel_path] = current_text.replace(old, new, 1)
    return originals, updated


def _create_backup_snapshot(report_id: str, originals: dict[str, str]) -> dict:
    attempt_id = f"apply_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    backup_root = STATE_DIR / "self_repair_backups" / str(report_id or "unknown") / attempt_id
    for rel_path, content in originals.items():
        backup_path = backup_root / rel_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(content, encoding="utf-8")
    return {"attempt_id": attempt_id, "backup_root": str(backup_root)}


def _restore_backup_snapshot(backup_info: dict, rel_paths: list[str]):
    backup_root = Path(str((backup_info or {}).get("backup_root") or ""))
    for rel_path in rel_paths or []:
        source = backup_root / rel_path
        target = _resolve_repo_path(rel_path)
        if not source.exists() or not target:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _write_updated_files(updated: dict[str, str]):
    for rel_path, content in (updated or {}).items():
        target = _resolve_repo_path(rel_path)
        if not target:
            raise ValueError(f"write_path_invalid:{rel_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _preview_edit(item: dict) -> dict:
    return {
        "path": str((item or {}).get("path") or "").strip(),
        "reason": str((item or {}).get("reason") or "").strip(),
        "old_preview": _trim_preview(str((item or {}).get("old") or ""), 140),
        "new_preview": _trim_preview(str((item or {}).get("new") or ""), 140),
    }


def _build_patch_preview_result(report: dict, patch_plan: dict) -> dict:
    report = report if isinstance(report, dict) else {}
    patch_plan = patch_plan if isinstance(patch_plan, dict) else {}
    ok = bool(patch_plan.get("ok"))
    decision = _build_auto_apply_decision(report, patch_plan)
    return {
        "previewed_at": datetime.now().isoformat(),
        "status": "preview_ready" if ok else "preview_failed",
        "summary": str(patch_plan.get("summary") or "").strip(),
        "error": "" if ok else str(patch_plan.get("error") or "empty_patch_plan"),
        "edits": [_preview_edit(item) for item in patch_plan.get("edits") or []],
        "risk_level": decision["risk_level"],
        "auto_apply_ready": bool(decision["auto_apply_ready"]),
        "confirmation_required": bool(decision["confirmation_required"]),
        "decision_reason": str(decision["reason"] or ""),
        "edit_count": int(decision["edit_count"]),
        "file_count": int(decision["file_count"]),
    }


def _build_report_summary(rule_item: dict, profile: dict) -> str:
    feedback = str((rule_item or {}).get("user_feedback") or "").strip()
    question = str((rule_item or {}).get("last_question") or "").strip()
    label = str((profile or {}).get("label") or "通用纠偏").strip()
    if question and feedback:
        return f"{label}：用户刚才问「{question[:40]}」，随后反馈「{feedback[:36]}」，这轮值得先做一次最小纠偏提案。"
    if feedback:
        return f"{label}：用户反馈「{feedback[:40]}」，先按最小修正路径给出候选文件和验证计划。"
    if question:
        return f"{label}：围绕「{question[:40]}」这类问法，先给出一轮受控修正提案。"
    return f"{label}：先给出一轮最小修正提案。"


def build_self_repair_report(rule_item: dict, config: dict | None = None) -> dict:
    rule_item = rule_item if isinstance(rule_item, dict) else {}
    config = config if isinstance(config, dict) else {}
    now = datetime.now().isoformat()
    profile = _build_issue_profile(rule_item)
    apply_mode = str(config.get("self_repair_apply_mode") or "confirm").strip() or "confirm"
    status = "awaiting_confirmation" if apply_mode == "confirm" else "proposal_ready"
    report = {
        "id": f"repair_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        "created_at": now,
        "updated_at": now,
        "source": "feedback_rule",
        "feedback_rule_id": str(rule_item.get("id") or "").strip(),
        "scene": str(rule_item.get("scene") or "").strip(),
        "problem": str(rule_item.get("problem") or "").strip(),
        "fix": str(rule_item.get("fix") or "").strip(),
        "type": str(rule_item.get("type") or "").strip(),
        "label": profile["label"],
        "issue_key": profile["issue_key"],
        "summary": _build_report_summary(rule_item, profile),
        "diagnosis": profile["diagnosis"],
        "user_feedback": str(rule_item.get("user_feedback") or "").strip(),
        "last_question": str(rule_item.get("last_question") or "").strip(),
        "last_answer_excerpt": str(rule_item.get("last_answer") or "").strip()[:220],
        "candidate_files": profile["candidate_files"],
        "suggested_tests": profile["suggested_tests"],
        "proposed_actions": [
            "先复现这次反馈对应的最短问法，确保问题能稳定复现。",
            "优先检查候选文件里更上游的分流或包装层，避免只在最后一层回复上打补丁。",
            "改完先跑建议测试，确认没有把已有链路带坏，再决定要不要继续扩改。",
        ],
        "apply_mode": apply_mode,
        "requires_confirmation": True,
        "risk_level": "",
        "auto_apply_ready": False,
        "status": status,
        "validation": {
            "ran": False,
            "all_passed": None,
            "test_runs": [],
            "duration_ms": 0,
        },
    }
    report["patch_prompt"] = _build_patch_prompt(report)
    return report


def _summarize_process_output(stdout: str, stderr: str) -> str:
    lines = [line.strip() for line in f"{stdout}\n{stderr}".splitlines() if line.strip()]
    if not lines:
        return ""
    tail = lines[-4:]
    return " | ".join(tail)


def run_targeted_tests(test_paths: list[str], timeout_sec: int = DEFAULT_TEST_TIMEOUT_SEC) -> dict:
    runs = []
    started = time.time()
    patterns = []
    seen = set()
    for item in test_paths or []:
        name = Path(str(item or "")).name
        if not name or name in seen:
            continue
        patterns.append(name)
        seen.add(name)

    for pattern in patterns:
        cmd = [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            pattern,
            "-v",
        ]
        run_started = time.time()
        try:
            result = subprocess.run(
                cmd,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=max(int(timeout_sec), 10),
            )
            ok = result.returncode == 0
            runs.append(
                {
                    "pattern": pattern,
                    "command": " ".join(cmd),
                    "ok": ok,
                    "exit_code": result.returncode,
                    "duration_ms": int((time.time() - run_started) * 1000),
                    "summary": _summarize_process_output(result.stdout, result.stderr),
                }
            )
        except Exception as exc:
            runs.append(
                {
                    "pattern": pattern,
                    "command": " ".join(cmd),
                    "ok": False,
                    "exit_code": -1,
                    "duration_ms": int((time.time() - run_started) * 1000),
                    "summary": str(exc),
                }
            )

    return {
        "ran": bool(runs),
        "all_passed": bool(runs) and all(item.get("ok") for item in runs),
        "test_runs": runs,
        "duration_ms": int((time.time() - started) * 1000),
    }


def create_self_repair_report(rule_item: dict, config: dict | None = None, run_validation: bool = False) -> dict:
    config = config if isinstance(config, dict) else {}
    rule_item = rule_item if isinstance(rule_item, dict) else {}

    existing = None
    feedback_rule_id = str(rule_item.get("id") or "").strip()
    if feedback_rule_id:
        for item in load_self_repair_reports():
            if str(item.get("feedback_rule_id") or "").strip() == feedback_rule_id:
                existing = item
                break

    report = build_self_repair_report(rule_item, config=config)
    if existing:
        report["id"] = str(existing.get("id") or report["id"])
        report["created_at"] = str(existing.get("created_at") or report["created_at"])

    if run_validation:
        timeout_sec = int(config.get("self_repair_test_timeout_sec") or DEFAULT_TEST_TIMEOUT_SEC)
        test_paths = [item.get("path", "") for item in report.get("suggested_tests") or [] if item.get("path")]
        validation = run_targeted_tests(test_paths, timeout_sec=timeout_sec)
        report["validation"] = validation
        if validation.get("all_passed"):
            report["status"] = "awaiting_confirmation" if report.get("apply_mode") == "confirm" else "proposal_ready"
        else:
            report["status"] = "needs_attention"
    report["updated_at"] = datetime.now().isoformat()
    return save_self_repair_report(report)


def preview_self_repair_report(
    report_id: str = "",
    config: dict | None = None,
    auto_apply: bool = False,
    run_validation: bool = True,
) -> dict:
    config = config if isinstance(config, dict) else {}
    report = get_self_repair_report(report_id)
    if not report:
        raise ValueError("self_repair_report_not_found")

    patch_plan = generate_self_repair_patch_plan(report, config=config)
    report["patch_preview"] = _build_patch_preview_result(report, patch_plan)
    _update_report_decision(report, report["patch_preview"])
    if not patch_plan.get("ok"):
        report["status"] = "needs_attention"
    report["updated_at"] = datetime.now().isoformat()
    report = save_self_repair_report(report)

    if auto_apply and bool((report.get("patch_preview") or {}).get("auto_apply_ready")):
        return apply_self_repair_report(
            report_id=str(report.get("id") or report_id),
            config=config,
            run_validation=run_validation,
            auto_mode=True,
            patch_plan=patch_plan,
        )
    return report


def apply_self_repair_report(
    report_id: str = "",
    config: dict | None = None,
    run_validation: bool = True,
    auto_mode: bool = False,
    patch_plan: dict | None = None,
) -> dict:
    config = config if isinstance(config, dict) else {}
    report = get_self_repair_report(report_id)
    if not report:
        raise ValueError("self_repair_report_not_found")

    apply_result = {
        "attempted_at": datetime.now().isoformat(),
        "status": "",
        "rolled_back": False,
        "generator_summary": "",
        "edits": [],
        "auto_applied": bool(auto_mode),
        "validation": {"ran": False, "all_passed": None, "test_runs": [], "duration_ms": 0},
    }

    if str(report.get("status") or "").strip() == "applied":
        apply_result["status"] = "already_applied"
        report["apply_result"] = apply_result
        report["updated_at"] = datetime.now().isoformat()
        return save_self_repair_report(report)

    existing_validation = report.get("validation") or {}
    if existing_validation.get("ran") and existing_validation.get("all_passed") is False:
        apply_result["status"] = "blocked_by_existing_validation"
        report["apply_result"] = apply_result
        report["updated_at"] = datetime.now().isoformat()
        return save_self_repair_report(report)

    patch_plan = patch_plan if isinstance(patch_plan, dict) else generate_self_repair_patch_plan(report, config=config)
    report["patch_preview"] = _build_patch_preview_result(report, patch_plan)
    _update_report_decision(report, report["patch_preview"])
    apply_result["generator_summary"] = str(patch_plan.get("summary") or "").strip()
    apply_result["edits"] = [_preview_edit(item) for item in patch_plan.get("edits") or []]

    if auto_mode and not bool((report.get("patch_preview") or {}).get("auto_apply_ready")):
        apply_result["status"] = "auto_apply_not_allowed"
        apply_result["error"] = "auto_apply_not_allowed"
        report["apply_result"] = apply_result
        report["status"] = _pending_report_status(report) if patch_plan.get("ok") else "needs_attention"
        report["updated_at"] = datetime.now().isoformat()
        return save_self_repair_report(report)

    if not patch_plan.get("ok"):
        apply_result["status"] = "patch_plan_failed"
        apply_result["error"] = str(patch_plan.get("error") or "empty_patch_plan")
        report["apply_result"] = apply_result
        report["status"] = _pending_report_status(report)
        report["updated_at"] = datetime.now().isoformat()
        return save_self_repair_report(report)

    try:
        originals, updated = _prepare_updated_files(patch_plan.get("edits") or [], patch_plan.get("allowed_paths") or [])
    except Exception as exc:
        apply_result["status"] = "edit_validation_failed"
        apply_result["error"] = str(exc)
        report["apply_result"] = apply_result
        report["status"] = _pending_report_status(report)
        report["updated_at"] = datetime.now().isoformat()
        return save_self_repair_report(report)

    backup_info = _create_backup_snapshot(str(report.get("id") or ""), originals)
    apply_result["backup_root"] = str(backup_info.get("backup_root") or "")

    # 语法预检：写入前验证文件内容合法性（可扩展）
    import ast as _ast
    for rel_path, content in updated.items():
        syntax_err = None
        if rel_path.endswith(".py"):
            try:
                _ast.parse(content, filename=rel_path)
            except SyntaxError as e:
                syntax_err = f"{rel_path}:{e.lineno}: {e.msg}"
        elif rel_path.endswith(".json"):
            try:
                json.loads(content)
            except (json.JSONDecodeError, ValueError) as e:
                syntax_err = f"{rel_path}: invalid JSON: {e}"
        # 扩展点：未来加 .js/.html 等语言的验证放这里
        if syntax_err:
            apply_result["status"] = "syntax_error_before_write"
            apply_result["error"] = syntax_err
            report["apply_result"] = apply_result
            report["status"] = "needs_attention"
            report["updated_at"] = datetime.now().isoformat()
            return save_self_repair_report(report)

    try:
        _write_updated_files(updated)
        validation = {"ran": False, "all_passed": None, "test_runs": [], "duration_ms": 0}
        if run_validation:
            timeout_sec = int(config.get("self_repair_test_timeout_sec") or DEFAULT_TEST_TIMEOUT_SEC)
            test_paths = [item.get("path", "") for item in report.get("suggested_tests") or [] if item.get("path")]
            validation = run_targeted_tests(test_paths, timeout_sec=timeout_sec)
        apply_result["validation"] = validation

        if run_validation and not validation.get("ran"):
            _restore_backup_snapshot(backup_info, list(originals.keys()))
            apply_result["status"] = "rolled_back_without_validation"
            apply_result["rolled_back"] = True
            report["status"] = "needs_attention"
        elif run_validation and not validation.get("all_passed"):
            _restore_backup_snapshot(backup_info, list(originals.keys()))
            apply_result["status"] = "rolled_back_after_failed_validation"
            apply_result["rolled_back"] = True
            report["status"] = "rolled_back_after_failed_validation"
        else:
            apply_result["status"] = "applied_without_validation" if not run_validation else "applied"
            report["status"] = "applied_without_validation" if not run_validation else "applied"
    except Exception as exc:
        _restore_backup_snapshot(backup_info, list(originals.keys()))
        apply_result["status"] = "rolled_back_after_apply_error"
        apply_result["rolled_back"] = True
        apply_result["error"] = str(exc)
        report["status"] = "needs_attention"

    report["apply_result"] = apply_result
    report["updated_at"] = datetime.now().isoformat()
    return save_self_repair_report(report)
