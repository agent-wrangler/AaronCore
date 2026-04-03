"""核心对话路由：/chat SSE 流式"""
import asyncio
import copy
import json
import requests
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import re as _re
from core import shared as S
from core.markdown_render import render_markdown_html
from core.runtime_state.state_loader import (
    DEFAULT_L1_RECENT_TOKEN_BUDGET as _L1_RECENT_TOKEN_BUDGET,
)
from routes.chat_tool_steps import (
    build_tool_done_label,
    build_tool_done_trace_detail,
    build_tool_execution_trace_detail,
)
try:
    from routes import companion as _comp
except Exception:
    class _CompanionState:
        activity = "idle"
        reply_id = ""
        last_reply = ""
        last_reply_full = ""
        emotion = "neutral"

    _comp = _CompanionState()


def _summarize_execution_text(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return ""
    text = text.replace("`", "").replace("\r", "\n")
    lines = [line.strip(" -") for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    summary = " / ".join(lines[:2]).strip()
    return summary[:140] + ("..." if len(summary) > 140 else "")


def _build_run_event(*, success: bool, meta: dict | None = None, fallback_text: str = "", fallback_summary: str = "") -> dict:
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
        summary = _summarize_execution_text(fallback_text)

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
    return {k: v for k, v in run_event.items() if v not in ("", None)}


def _extract_task_plan_from_meta(meta: dict | None) -> dict | None:
    meta = meta if isinstance(meta, dict) else {}
    task_plan = meta.get("task_plan") if isinstance(meta.get("task_plan"), dict) else {}
    items = task_plan.get("items") if isinstance(task_plan.get("items"), list) else []
    if not task_plan or not items:
        return None
    return task_plan


def _is_task_plan_terminal(plan: dict | None) -> bool:
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


def _block_task_plan_after_failure(
    plan: dict | None,
    *,
    goal_hint: str = "",
    tool_used: str = "",
    action_summary: str = "",
    tool_response: str = "",
) -> dict | None:
    plan = copy.deepcopy(plan if isinstance(plan, dict) else {})
    items = plan.get("items") if isinstance(plan.get("items"), list) else []
    if not items or _is_task_plan_terminal(plan):
        return plan or None

    summary = _summarize_execution_text(tool_response) or _summarize_execution_text(action_summary)
    if tool_used and summary:
        summary = f"{tool_used} 未完成：{summary}"
    elif tool_used:
        summary = f"{tool_used} 未完成"
    elif not summary:
        summary = "当前步骤执行失败"

    current_item_id = str(plan.get("current_item_id") or "").strip()
    target = None
    if current_item_id:
        target = next((item for item in items if str((item or {}).get("id") or "").strip() == current_item_id), None)
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


def _normalize_persisted_process_steps(steps: list | None) -> list[dict]:
    meta_fields = (
        "step_key",
        "phase",
        "reason_kind",
        "goal",
        "decision_note",
        "handoff_note",
        "expected_output",
        "next_user_need",
        "tool_name",
    )

    def _is_thinking_label(value: str) -> bool:
        text = str(value or "").strip().lower()
        return text in {"thinking", "\u6a21\u578b\u601d\u8003"}

    rows = []
    for item in steps or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        detail = str(item.get("detail") or "").strip()
        status = str(item.get("status") or "").strip().lower()
        if status not in {"done", "error", "running"}:
            continue
        if status == "running" and not _is_thinking_label(label):
            continue
        if not label and not detail:
            continue
        row = {
            "label": label,
            "detail": detail,
            "status": "error" if status == "error" else "done",
        }
        for field in meta_fields:
            value = str(item.get(field) or "").strip()
            if value:
                row[field] = value
        if rows and _is_thinking_label(label) and _is_thinking_label(rows[-1].get("label")):
            rows[-1]["detail"] = detail or rows[-1].get("detail", "")
            rows[-1]["status"] = row["status"]
            for field in meta_fields:
                if row.get(field):
                    rows[-1][field] = row[field]
            continue
        if rows and rows[-1] == row:
            continue
        rows.append(row)
    return rows


def _ensure_tool_call_failure_reply(
    response: str,
    *,
    tool_used: str = "",
    tool_success: bool | None = None,
    tool_response: str = "",
    action_summary: str = "",
    run_meta: dict | None = None,
) -> str:
    text = str(response or "")
    if not tool_used or tool_success is not False:
        return text
    try:
        from core.reply_formatter import _build_tool_closeout_reply, _clean_visible_reply_text, _looks_like_tool_preamble

        cleaned = _clean_visible_reply_text(text)
        if cleaned and not _looks_like_tool_preamble(cleaned):
            return text
        fallback = _build_tool_closeout_reply(
            success=False,
            action_summary=action_summary,
            tool_response=str(tool_response or text).strip(),
            run_meta=run_meta if isinstance(run_meta, dict) else {},
        )
        if fallback:
            return fallback
    except Exception:
        pass
    fallback_text = str(tool_response or text).strip()
    if fallback_text:
        return S.format_skill_fallback(fallback_text)
    return text


def _drop_incomplete_tool_handoff_prefix(chunks: list[str]) -> str:
    if not chunks:
        return ""
    try:
        from core.reply_formatter import _clean_visible_reply_text, _looks_like_incomplete_tool_handoff

        joined = "".join(str(chunk or "") for chunk in chunks).strip()
        cleaned = _clean_visible_reply_text(joined)
        if cleaned and _looks_like_incomplete_tool_handoff(cleaned):
            chunks.clear()
            return cleaned
    except Exception:
        return ""
    return ""


_THINK_OPEN_TAG = "<think>"
_THINK_CLOSE_TAG = "</think>"


def _consume_think_filtered_stream_text(
    carry: str,
    chunk: str,
    *,
    in_think: bool = False,
    end_of_stream: bool = False,
) -> tuple[list[str], str, bool, bool]:
    carry = f"{carry}{str(chunk or '')}"
    visible_parts: list[str] = []
    saw_think = False
    open_keep = max(0, len(_THINK_OPEN_TAG) - 1)
    close_keep = max(0, len(_THINK_CLOSE_TAG) - 1)

    while carry:
        lowered = carry.lower()
        if in_think:
            close_idx = lowered.find(_THINK_CLOSE_TAG)
            if close_idx < 0:
                if end_of_stream:
                    return visible_parts, "", True, saw_think
                if close_keep and len(carry) > close_keep:
                    carry = carry[-close_keep:]
                break
            carry = carry[close_idx + len(_THINK_CLOSE_TAG):]
            in_think = False
            continue

        open_idx = lowered.find(_THINK_OPEN_TAG)
        if open_idx >= 0:
            prefix = carry[:open_idx]
            if prefix:
                visible_parts.append(prefix)
            carry = carry[open_idx + len(_THINK_OPEN_TAG):]
            in_think = True
            saw_think = True
            continue

        if end_of_stream:
            visible_parts.append(carry)
            return visible_parts, "", in_think, saw_think

        if len(carry) <= open_keep:
            break
        visible_parts.append(carry[:-open_keep])
        carry = carry[-open_keep:]
        break

    return visible_parts, carry, in_think, saw_think


def _reset_stream_visible_state(stream_chunks: list[str], carry: str) -> tuple[str, str, bool]:
    dropped_text = f"{''.join(stream_chunks)}{str(carry or '')}".strip()
    if stream_chunks:
        stream_chunks.clear()
    return dropped_text, "", False


def _get_tool_call_enabled() -> bool:
    """tool_call 总开关，由配置控制。"""
    try:
        from core.runtime_state.state_loader import PRIMARY_STATE_DIR
        cfg = json.loads((PRIMARY_STATE_DIR / "tool_call_config.json").read_text("utf-8"))
        return bool(cfg.get("enabled", True))
    except Exception:
        return True


def _get_cod_enabled() -> bool:
    """CoD (Context-on-Demand) \u6a21\u5f0f\u5f00\u5173"""
    try:
        from core.runtime_state.state_loader import PRIMARY_STATE_DIR
        cfg = json.loads((PRIMARY_STATE_DIR / "tool_call_config.json").read_text("utf-8"))
        return bool(cfg.get("cod_enabled", False))
    except Exception:
        return False


def _is_anthropic_model() -> bool:
    """当前模型是否走 Anthropic 协议（不支持 tool_call）"""
    try:
        from brain import LLM_CONFIG
        base_url = str(LLM_CONFIG.get("base_url", "")).lower()
        if "minimaxi.com" in base_url:
            return False
        return "/anthropic" in base_url
    except Exception:
        return False


def _get_tool_call_unavailable_reason() -> str | None:
    """tool_call 不可用时返回事故原因；可用时返回 None。"""
    if not _get_tool_call_enabled():
        return "disabled"
    if _is_anthropic_model():
        return "unsupported_model"
    if not S.NOVA_CORE_READY:
        return "core_not_ready"
    return None


def _build_tool_call_unavailable_reply(reason: str) -> str:
    details = {
        "disabled": "tool_call 开关当前被关闭。按照现在的架构，这属于主链事故，不会再静默回退到旧 skill 链。",
        "unsupported_model": "当前模型走的是不支持原生 tool_call 的协议。按照现在的架构，这属于主链事故，不会再静默回退到旧 skill 链。",
        "core_not_ready": "NOVA Core 当前未就绪。按照现在的架构，这属于主链事故，不会再静默回退到旧 skill 链。",
    }
    detail = details.get(reason, "tool_call 主链当前不可用，而且系统不会再回退到旧链。")
    return (
        "这一步没接上主链。\n"
        f"{detail}\n"
        "请先恢复 tool_call 主链，再继续当前任务。"
    )


# ── 模型切换检测 ──────────────────────────────────────────
_MODEL_SWITCH_RE = _re.compile(
    r'(?:换成?|切换?到?|改[成用]|用)\s*'
    r'([a-zA-Z0-9][\w\-\.]*(?:[\-\.]\w+)*)',
    _re.IGNORECASE,
)

# 常见厂商 → 可用模型列表（用于用户只说厂商名时推荐）
_PROVIDER_CATALOG = {
    "deepseek": {
        "aliases": ["deepseek", "ds"],
        "url_hint": "deepseek",
        "models": [
            ("deepseek-chat", "V3 \u65e5\u5e38\u5bf9\u8bdd\uff0c\u5feb\u4e14\u4fbf\u5b9c"),
            ("deepseek-reasoner", "R1 \u6df1\u5ea6\u63a8\u7406\uff0c\u6162\u4f46\u667a\u5546\u9ad8"),
        ],
    },
    "openai": {
        "aliases": ["openai", "gpt", "chatgpt"],
        "url_hint": "openai",
        "models": [
            ("gpt-4o", "\u591a\u6a21\u6001\u65d7\u8230\uff0c\u652f\u6301\u56fe\u7247"),
            ("gpt-4o-mini", "\u8f7b\u91cf\u5feb\u901f\uff0c\u6027\u4ef7\u6bd4\u9ad8"),
            ("gpt-4.1", "\u6700\u65b0\u4e3b\u529b\u6a21\u578b"),
            ("gpt-4.1-mini", "\u8f7b\u91cf\u7248 4.1"),
            ("gpt-4.1-nano", "\u6781\u901f\u7248\uff0c\u6700\u4fbf\u5b9c"),
        ],
    },
    "claude": {
        "aliases": ["claude", "anthropic"],
        "url_hint": "anthropic",
        "models": [
            ("claude-sonnet-4-20250514", "Sonnet 4 \u5747\u8861\u578b"),
            ("claude-3-5-haiku-20241022", "Haiku 3.5 \u6781\u901f"),
        ],
    },
    "qwen": {
        "aliases": ["qwen", "\u901a\u4e49\u5343\u95ee", "\u5343\u95ee"],
        "url_hint": "dashscope",
        "models": [
            ("qwen-plus", "\u4e3b\u529b\u6a21\u578b\uff0c\u6027\u4ef7\u6bd4\u9ad8"),
            ("qwen-turbo", "\u6781\u901f\u7248\uff0c\u6700\u4fbf\u5b9c"),
            ("qwen-max", "\u65d7\u8230\u7248\uff0c\u6700\u5f3a"),
        ],
    },
    "minimax": {
        "aliases": ["minimax", "mm", "hailuo", "\u6d77\u87ba"],
        "url_hint": "minimax",
        "models": [
            ("MiniMax-M2.7", "M2.7 \u6700\u65b0\u4e3b\u529b"),
            ("MiniMax-M2.7-highspeed", "M2.7 \u6781\u901f\u7248"),
            ("MiniMax-M2.5", "M2.5 \u5747\u8861\u578b"),
            ("MiniMax-M2.5-highspeed", "M2.5 \u6781\u901f\u7248"),
            ("MiniMax-M2.1", "M2.1 \u7ecf\u5178\u7248"),
            ("MiniMax-M2.1-highspeed", "M2.1 \u6781\u901f\u7248"),
            ("MiniMax-M2", "M2 \u57fa\u7840\u7248"),
        ],
    },
    "doubao": {
        "aliases": ["doubao", "\u8c46\u5305"],
        "url_hint": "volcengine",
        "models": [
            ("doubao-1.5-pro-32k", "1.5 Pro \u4e3b\u529b"),
            ("doubao-1.5-lite-32k", "1.5 Lite \u8f7b\u91cf"),
        ],
    },
    "glm": {
        "aliases": ["glm", "zhipu", "\u667a\u8c31", "chatglm"],
        "url_hint": "zhipuai",
        "models": [
            ("glm-4-plus", "GLM-4 Plus \u65d7\u8230"),
            ("glm-4-flash", "GLM-4 Flash \u514d\u8d39"),
        ],
    },
}

def _match_provider(target: str, models_config: dict) -> tuple[str | None, dict | None]:
    """从 target 匹配厂商，返回 (provider_key, donor_cfg)"""
    target_l = target.lower()
    target_prefix = target_l.split("-")[0].lower()
    # 先查 catalog aliases（精确匹配或 target 前缀匹配）
    for pkey, pinfo in _PROVIDER_CATALOG.items():
        if target_l in pinfo["aliases"] or target_prefix in pinfo["aliases"]:
            # 找已配置的同厂商模型作为 donor
            for mid, cfg in models_config.items():
                base_url = str(cfg.get("base_url", "")).lower()
                mid_l = mid.lower()
                if pinfo["url_hint"] in base_url or pkey in mid_l:
                    return pkey, cfg
            return pkey, None
    # fallback: 用 target 的前缀在已有模型里找
    for mid, cfg in models_config.items():
        mid_l = mid.split("-")[0].lower()
        model_l = str(cfg.get("model", "")).split("-")[0].lower()
        base_url = str(cfg.get("base_url", "")).lower()
        if target_prefix == mid_l or target_prefix == model_l or target_l in base_url:
            # 反查 catalog
            for pkey, pinfo in _PROVIDER_CATALOG.items():
                if pinfo["url_hint"] in base_url or pkey in mid_l:
                    return pkey, cfg
            return None, cfg
    return None, None

def _is_vague_provider_name(target: str) -> bool:
    """判断 target 是否只是一个厂商名（没有具体模型后缀）"""
    if "-" in target or "." in target:
        return False
    target_l = target.lower()
    for pinfo in _PROVIDER_CATALOG.values():
        if target_l in pinfo["aliases"]:
            return True
    return False

def _build_model_list_reply(target: str, provider_key: str | None, donor_cfg: dict | None, models_config: dict, current_default: str) -> str:
    """构建模型推荐列表回复"""
    lines = []
    # 已配置的同厂商模型
    existing = []
    for mid, cfg in models_config.items():
        mid_l = mid.lower()
        model_name = str(cfg.get("model", mid))
        if provider_key:
            pinfo = _PROVIDER_CATALOG.get(provider_key, {})
            url_hint = pinfo.get("url_hint", provider_key)
            base_url = str(cfg.get("base_url", "")).lower()
            if provider_key in mid_l or url_hint in base_url:
                tag = " \u2190 \u5f53\u524d" if mid == current_default else ""
                existing.append(f"  {model_name}{tag}")
        else:
            if target.lower() in mid_l:
                tag = " \u2190 \u5f53\u524d" if mid == current_default else ""
                existing.append(f"  {model_name}{tag}")

    if existing:
        lines.append("\u5df2\u914d\u7f6e\u7684\uff1a")
        lines.extend(existing)

    # catalog 里的推荐
    if provider_key and provider_key in _PROVIDER_CATALOG:
        catalog_models = _PROVIDER_CATALOG[provider_key]["models"]
        existing_names = {str(cfg.get("model", mid)).lower() for mid, cfg in models_config.items()}
        suggestions = []
        for model_id, desc in catalog_models:
            if model_id.lower() not in existing_names:
                suggestions.append(f"  {model_id}\uff08{desc}\uff09")
        if suggestions:
            if existing:
                lines.append("")
            lines.append("\u8fd8\u53ef\u4ee5\u7528\uff1a" if donor_cfg else "\u5e38\u89c1\u6a21\u578b\uff1a")
            lines.extend(suggestions)

    if not lines:
        return ""

    header = f"{target.upper()} \u6709\u8fd9\u4e9b\u6a21\u578b\uff1a\n"
    footer = "\n\n\u76f4\u63a5\u8bf4\u201c\u6362\u6210 xxx\u201d\u5c31\u884c\uff0c"
    if donor_cfg:
        footer += "\u540c\u5382\u5546\u7684\u6211\u4f1a\u81ea\u52a8\u590d\u7528 API \u914d\u7f6e\u3002"
    else:
        footer += "\u4e0d\u8fc7\u8fd9\u4e2a\u5382\u5546\u8fd8\u6ca1\u914d\u7f6e API\uff0c\u9700\u8981\u5148\u5728\u8bbe\u7f6e\u91cc\u6dfb\u52a0\u4e00\u4e2a\u3002"
    return header + "\n".join(lines) + footer

def _is_placeholder_key(api_key: str) -> bool:
    """检查 API key 是否是占位符"""
    if not api_key:
        return True
    key = str(api_key).strip()
    if len(key) < 10:
        return True
    if "xxx" in key.lower() or "sk-xxx" in key.lower():
        return True
    # 包含中文字符 → 占位符
    if any('\u4e00' <= c <= '\u9fff' for c in key):
        return True
    if key.startswith(("\u4f60\u7684", "\u586b\u5199", "\u8bf7\u586b")):
        return True
    return False


def _check_model_ready(mid: str, cfg: dict) -> str | None:
    """检查模型配置是否可用，返回错误信息或 None"""
    api_key = str(cfg.get("api_key", "")).strip()
    base_url = str(cfg.get("base_url", "")).strip()
    if not base_url:
        return f"{mid} \u8fd8\u6ca1\u914d\u7f6e base_url\uff0c\u53bb\u8bbe\u7f6e\u9875\u586b\u4e00\u4e0b\u518d\u5207\u3002"
    if _is_placeholder_key(api_key):
        return f"{mid} \u7684 API key \u8fd8\u6ca1\u586b\uff0c\u53bb\u8bbe\u7f6e\u9875\u586b\u4e00\u4e0b\u518d\u5207\u3002"
    return None


def _detect_model_switch(text: str) -> dict | None:
    """检测用户是否想通过对话切换模型，返回 {reply, trace} 或 None"""
    text = str(text or "").strip()
    if len(text) > 60 or len(text) < 3:
        return None
    m = _MODEL_SWITCH_RE.search(text)
    if not m:
        return None
    target = m.group(1).strip()
    target_l = target.lower()
    # 排除常见误触（用户说"用xxx做/写/画"不是切模型）
    after = text[m.end():].strip()
    if after and after[0] in "\u505a\u5199\u753b\u641c\u67e5\u627e\u5e2e\u6765\u804a\u8bf4\u8bb2\u770b":
        return None

    import brain
    models = brain.MODELS_CONFIG

    # 1) 精确匹配已有模型 ID
    if target_l in {k.lower() for k in models}:
        mid = next(k for k in models if k.lower() == target_l)
        if mid == brain._current_default:
            return {"reply": f"\u5df2\u7ecf\u5728\u7528 {models[mid].get('model', mid)} \u4e86\u5440\uff5e",
                    "trace": f"\u5f53\u524d\u5df2\u662f {mid}"}
        err = _check_model_ready(mid, models[mid])
        if err:
            return {"reply": err, "trace": f"{mid} \u914d\u7f6e\u4e0d\u5b8c\u6574"}
        ok = brain.set_default_model(mid)
        if ok:
            name = brain.get_current_model_name()
            return {"reply": f"\u597d\u7684\uff0c\u5df2\u7ecf\u5207\u5230 {name} \u4e86\uff0c\u63a5\u4e0b\u6765\u7528\u8fd9\u4e2a\u6a21\u578b\u8ddf\u4f60\u804a\u3002",
                    "trace": f"\u5df2\u5207\u6362\u5230 {name}", "model_changed": True}
        return {"reply": "\u5207\u6362\u5931\u8d25\u4e86\uff0c\u4f60\u518d\u8bd5\u4e00\u6b21\u3002", "trace": "\u5207\u6362\u5931\u8d25"}

    # 2) 模糊匹配已有模型（model name 或 ID 包含 target，且 target 不是纯厂商名）
    #    注意：只匹配 target 是已有名称的子串（用户说了更短的名字）的情况。
    #    如果 target 比已有名称更长/更具体（如 M2.5 vs M2.7），应跳过让 step3 自动创建。
    if not _is_vague_provider_name(target_l):
        for mid, cfg in models.items():
            model_name = str(cfg.get("model", mid)).lower()
            if target_l in mid.lower() or target_l in model_name or target_l == model_name:
                if mid == brain._current_default:
                    return {"reply": f"\u5df2\u7ecf\u5728\u7528 {cfg.get('model', mid)} \u4e86\u5440\uff5e",
                            "trace": f"\u5f53\u524d\u5df2\u662f {mid}"}
                err = _check_model_ready(mid, cfg)
                if err:
                    return {"reply": err, "trace": f"{mid} \u914d\u7f6e\u4e0d\u5b8c\u6574"}
                ok = brain.set_default_model(mid)
                if ok:
                    name = brain.get_current_model_name()
                    return {"reply": f"\u597d\u7684\uff0c\u5df2\u7ecf\u5207\u5230 {name} \u4e86\uff0c\u63a5\u4e0b\u6765\u7528\u8fd9\u4e2a\u6a21\u578b\u8ddf\u4f60\u804a\u3002",
                            "trace": f"\u5df2\u5207\u6362\u5230 {name}", "model_changed": True}

    # 3) 厂商名匹配 → 列出可选模型
    provider_key, donor_cfg = _match_provider(target_l, models)
    if provider_key or donor_cfg:
        # 如果是模糊厂商名，列出可选模型让用户挑
        if _is_vague_provider_name(target_l):
            reply = _build_model_list_reply(target, provider_key, donor_cfg, models, brain._current_default)
            if reply:
                return {"reply": reply, "trace": f"\u5217\u51fa {target} \u53ef\u7528\u6a21\u578b"}
        # 如果是具体模型名（带横杠）且有 donor，自动创建
        elif donor_cfg and "-" in target:
            err = _check_model_ready("donor", donor_cfg)
            if err:
                return {"reply": f"\u540c\u5382\u5546\u7684 API \u914d\u7f6e\u4e0d\u5b8c\u6574\uff0c\u53bb\u8bbe\u7f6e\u9875\u586b\u597d key \u518d\u5207\u3002",
                        "trace": "\u540c\u5382\u5546\u914d\u7f6e\u4e0d\u5b8c\u6574"}
            new_cfg = {
                "api_key": donor_cfg["api_key"],
                "base_url": donor_cfg["base_url"],
                "model": target,
                "vision": donor_cfg.get("vision", False),
            }
            brain.MODELS_CONFIG[target] = new_cfg
            brain._raw_config["models"] = brain.MODELS_CONFIG
            try:
                json.dump(brain._raw_config, open(brain.config_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            except Exception:
                pass
            ok = brain.set_default_model(target)
            if ok:
                return {"reply": f"\u597d\u7684\uff0c\u5df2\u81ea\u52a8\u6dfb\u52a0\u5e76\u5207\u6362\u5230 {target}\uff0c\u590d\u7528\u4e86\u540c\u5382\u5546\u7684 API \u914d\u7f6e\u3002",
                        "trace": f"\u81ea\u52a8\u521b\u5efa + \u5207\u6362\u5230 {target}", "model_changed": True}

    # 4) 完全未知 → 不拦截，交给正常对话
    return None


def _strip_markdown(text: str) -> str:
    """保留 Markdown 格式（已改为允许自由使用 Markdown）"""
    return text


def _build_reply_payload(reply: str, **extra) -> dict:
    payload = {
        "reply": str(reply or ""),
        "reply_html": render_markdown_html(reply),
    }
    for key, value in (extra or {}).items():
        if value is not None:
            payload[key] = value
    return payload


router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    image: str | None = None
    images: list[str] | None = None


class ChatAnswerRequest(BaseModel):
    question_id: str
    answer: str


@router.post("/chat")
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    msg = request.message
    user_image = request.image
    user_images = request.images or ([user_image] if user_image else [])
    S.debug_write("input", {"message": msg, "has_image": bool(user_images)})
    S.add_to_history("user", msg)

    # 通知视觉模块：用户活跃
    try:
        from core.vision import touch_user_activity
        touch_user_activity()
    except Exception:
        pass

    history = S.load_msg_history()
    # 当前消息先不 append 到 history，避免 L1 和 user prompt 重复
    # （会在回复完成后再存入）
    _history_for_context = list(history)  # 不含当前消息的副本

    async def event_stream():
      try:
        _comp.activity = "thinking"

        # 先把当前用户消息存入持久历史（但不影响 _history_for_context，避免 L1 重复）
        history.append({"role": "user", "content": msg, "time": datetime.now().isoformat()})
        S.save_msg_history(history)

        # 收集步骤，用于持久化到 msg_history
        _collected_steps = []
        _last_progress_label = ""
        _last_progress_detail = ""
        _last_progress_step_key = ""
        _last_progress_status = ""
        _last_progress_at = asyncio.get_running_loop().time()
        _last_wait_event_at = 0.0
        _step_key_counts: dict[str, int] = {}
        _active_tool_step_key = ""
        _active_tool_name = ""

        def _clean_step_text(value: object) -> str:
            return str(value or "").strip()

        def _slugify_step_part(value: str, fallback: str = "step") -> str:
            text = _re.sub(r"[^a-z0-9]+", "_", _clean_step_text(value).lower()).strip("_")
            return text or fallback

        def _next_step_key(prefix: str, hint: str) -> str:
            base = f"{_slugify_step_part(prefix, 'step')}:{_slugify_step_part(hint, 'step')}"
            count = _step_key_counts.get(base, 0) + 1
            _step_key_counts[base] = count
            return base if count == 1 else f"{base}:{count}"

        def _looks_like_tool_label(label: str) -> bool:
            text = _clean_step_text(label)
            return text in {"调用技能", "技能完成", "技能失败", "联网搜索", "搜索完成", "搜索失败", "检索记忆", "检索失败", "记忆就绪"}

        def _infer_step_phase(label: str, *, explicit_phase: str = "", tool_name: str = "") -> str:
            phase = _clean_step_text(explicit_phase).lower()
            if phase:
                return phase
            text = _clean_step_text(label)
            if text in {"模型思考", "thinking"}:
                return "thinking"
            if text in {"等待", "waiting"}:
                return "waiting"
            if tool_name or _looks_like_tool_label(text):
                return "tool"
            return "info"

        def _build_expected_output(*, phase: str, tool_name: str = "", preview: str = "", display_name: str = "") -> str:
            phase = _clean_step_text(phase).lower()
            preview = _clean_step_text(preview)
            display_name = _clean_step_text(display_name or tool_name)
            if phase == "thinking":
                return "判断是直接回答还是先调用工具"
            if phase != "tool":
                return ""
            if tool_name == "weather":
                return "最新天气和一个可直接用的简洁结论"
            if preview:
                return f"围绕「{preview}」拿到可靠结果"
            if display_name:
                return f"拿到 {display_name} 的关键结果"
            return "拿到这一步需要的关键信息"

        def _build_next_user_need(*, tool_name: str = "", preview: str = "", expected_output: str = "") -> str:
            preview = _clean_step_text(preview)
            expected_output = _clean_step_text(expected_output)
            if tool_name == "weather" or "天气" in preview:
                return "今天状态、出门安排或要不要带伞"
            if tool_name == "web_search":
                return "最新结论、怎么做，或要不要继续展开"
            if tool_name in {"recall_memory", "query_knowledge"}:
                return "把上下文接回当前问题后的明确结论"
            if any(token in msg for token in ("今天", "新的一天", "早安", "早上")):
                return "今天最值得先关注的实时信息"
            if expected_output:
                return expected_output
            return "一个能直接接住当前话题的结论"

        def _build_step_payload(
            *,
            label: str,
            detail: str,
            status: str = "running",
            step_key: str = "",
            phase: str = "",
            full_detail: str = "",
            reason_kind: str = "",
            goal: str = "",
            decision_note: str = "",
            handoff_note: str = "",
            expected_output: str = "",
            next_user_need: str = "",
            tool_name: str = "",
        ) -> dict:
            clean_label = _clean_step_text(label)
            clean_detail = _clean_step_text(detail)
            clean_status = _clean_step_text(status).lower() or "running"
            clean_phase = _infer_step_phase(clean_label, explicit_phase=phase, tool_name=tool_name)
            clean_tool_name = _clean_step_text(tool_name)
            clean_step_key = _clean_step_text(step_key)
            clean_full_detail = _clean_step_text(full_detail) or clean_detail
            clean_decision_note = _clean_step_text(decision_note)
            clean_handoff_note = _clean_step_text(handoff_note)
            clean_goal = _clean_step_text(goal)
            clean_expected_output = _clean_step_text(expected_output)
            clean_next_user_need = _clean_step_text(next_user_need)
            clean_reason_kind = _clean_step_text(reason_kind)
            if not clean_step_key:
                if clean_phase == "thinking":
                    clean_step_key = "thinking:decision"
                elif clean_phase == "waiting":
                    clean_step_key = _last_progress_step_key or "thinking:decision"
                elif clean_phase == "tool":
                    if clean_status == "running" or not _active_tool_step_key:
                        clean_step_key = _next_step_key("tool", clean_tool_name or clean_label or "tool")
                    else:
                        clean_step_key = _active_tool_step_key
                else:
                    clean_step_key = _next_step_key(clean_phase or "info", clean_label or "step")
            payload = {
                "label": clean_label,
                "detail": clean_detail,
                "status": "error" if clean_status == "error" else ("running" if clean_status == "running" else "done"),
                "step_key": clean_step_key,
                "phase": clean_phase,
                "full_detail": clean_full_detail,
            }
            optional_fields = {
                "reason_kind": clean_reason_kind,
                "goal": clean_goal,
                "decision_note": clean_decision_note,
                "handoff_note": clean_handoff_note,
                "expected_output": clean_expected_output,
                "next_user_need": clean_next_user_need,
                "tool_name": clean_tool_name,
            }
            for field, value in optional_fields.items():
                if value:
                    payload[field] = value
            return payload

        async def _trace(
            label,
            detail,
            status="running",
            *,
            step_key: str = "",
            phase: str = "",
            full_detail: str = "",
            reason_kind: str = "",
            goal: str = "",
            decision_note: str = "",
            handoff_note: str = "",
            expected_output: str = "",
            next_user_need: str = "",
            tool_name: str = "",
        ):
            nonlocal _last_progress_label, _last_progress_detail, _last_progress_step_key, _last_progress_status, _last_progress_at, _last_wait_event_at, _active_tool_step_key, _active_tool_name
            payload = _build_step_payload(
                label=label,
                detail=detail,
                status=status,
                step_key=step_key,
                phase=phase,
                full_detail=full_detail,
                reason_kind=reason_kind,
                goal=goal,
                decision_note=decision_note,
                handoff_note=handoff_note,
                expected_output=expected_output,
                next_user_need=next_user_need,
                tool_name=tool_name,
            )
            _collected_steps.append(dict(payload))
            _last_progress_status = payload.get("status", "")
            if _last_progress_status == "running":
                _last_progress_label = payload.get("label", "")
                _last_progress_detail = payload.get("detail", "")
                _last_progress_step_key = payload.get("step_key", "")
            else:
                _last_progress_label = ""
                _last_progress_detail = ""
                _last_progress_step_key = ""
            _last_progress_at = asyncio.get_running_loop().time()
            _last_wait_event_at = 0.0
            if payload.get("phase") == "tool":
                _active_tool_name = payload.get("tool_name") or _active_tool_name
                _active_tool_step_key = payload.get("step_key") or _active_tool_step_key
                if payload.get("status") != "running":
                    _active_tool_name = ""
                    _active_tool_step_key = ""
            return {"event": "trace", "data": json.dumps(payload, ensure_ascii=False)}

        async def _agent_step(
            phase,
            detail="",
            label="",
            waited_seconds=0,
            *,
            step_key: str = "",
            reason_kind: str = "",
            goal: str = "",
            decision_note: str = "",
            handoff_note: str = "",
            expected_output: str = "",
            next_user_need: str = "",
            tool_name: str = "",
        ):
            nonlocal _last_wait_event_at
            _last_wait_event_at = asyncio.get_running_loop().time()
            payload = _build_step_payload(
                label=label,
                detail=detail,
                status="running",
                step_key=step_key or (_last_progress_step_key if (_clean_step_text(phase).lower() == "waiting" and _last_progress_status == "running") else ""),
                phase=phase,
                full_detail=detail,
                reason_kind=reason_kind,
                goal=goal,
                decision_note=decision_note,
                handoff_note=handoff_note,
                expected_output=expected_output,
                next_user_need=next_user_need,
                tool_name=tool_name,
            )
            payload["phase"] = _clean_step_text(phase).lower() or payload.get("phase", "")
            if waited_seconds:
                payload["waited_seconds"] = int(waited_seconds)
            return {"event": "agent_step", "data": json.dumps(payload, ensure_ascii=False)}

        def _build_waiting_step(waited_seconds: float, *, tool_active: bool = False, streamed: bool = False) -> tuple[str, str]:
            waited = max(1, int(waited_seconds))
            if tool_active:
                label = _last_progress_label or "\u8c03\u7528\u6280\u80fd"
                base_detail = str(_last_progress_detail or "").strip() or "\u6b63\u5728\u7b49\u5f85\u5de5\u5177\u6267\u884c\u7ed3\u679c"
            else:
                label = "\u6a21\u578b\u601d\u8003"
                base_detail = str(_last_progress_detail or "").strip()
                if not base_detail:
                    base_detail = (
                        "\u6b63\u5728\u7b49\u5f85\u6a21\u578b\u7ee7\u7eed\u8f93\u51fa"
                        if streamed
                        else "\u6b63\u5728\u7ee7\u7eed\u5206\u6790\u4e0b\u4e00\u6b65\u52a8\u4f5c"
                    )
            wait_note = f"{waited}s"
            return label, f"{base_detail} {wait_note}"

        def _summarize_tool_response_text(text: str) -> str:
            text = str(text or "").strip()
            if not text:
                return ""
            text = text.replace("`", "").replace("\r", "\n")
            lines = [line.strip(" -") for line in text.splitlines() if line.strip()]
            if not lines:
                return ""
            summary = " / ".join(lines[:2]).strip()
            return summary[:140] + ("..." if len(summary) > 140 else "")

        def _build_tool_reason_note(tool_name: str, preview: str, display_name: str) -> str:
            tool_name = str(tool_name or "").strip()
            preview = str(preview or "").strip()
            display_name = str(display_name or tool_name or "").strip()
            if tool_name == "weather" and preview:
                if "天气" not in preview:
                    preview = f"{preview}今天天气"
                return f"这是实时信息，直接凭记忆不稳。我先核实「{preview}」的最新天气，再根据结果给你一个简洁结论。"
            if preview:
                return f"我先把这一步需要核实的信息查清楚，再继续回答。当前先调用「{display_name}」确认「{preview}」。"
            if display_name:
                return f"我先调用「{display_name}」把关键事实拿到，再继续整理最终答复。"
            return ""

        pending_awareness = S.awareness_pull()
        for evt in pending_awareness:
            yield {"event": "awareness", "data": json.dumps(evt, ensure_ascii=False)}

        # ── CoD / tool_call 开关提前判断 ──
        _tool_call_unavailable_reason = _get_tool_call_unavailable_reason()
        _use_tool_call = _tool_call_unavailable_reason is None
        _use_cod = _use_tool_call and _get_cod_enabled()

        # Step 1: 记忆加载
        l1 = S.get_recent_messages(_history_for_context, max_tokens=_L1_RECENT_TOKEN_BUDGET)
        l2 = S.extract_session_context(_history_for_context, msg)
        _use_light_chat_bundle = not _use_tool_call
        l2_memories = [] if (_use_cod or _use_light_chat_bundle) else S.l2_search_relevant(msg)

        # Step 1.5: 时间回忆检测
        recall_result = None
        if S.detect_recall_intent:
            recall_intent = S.detect_recall_intent(msg)
            if recall_intent:
                recall_result = S.recall_by_time(
                    recall_intent["start_dt"], recall_intent["end_dt"],
                    recall_intent["time_label"], history,
                )
                if recall_result:
                    yield await _trace("\u56de\u5fc6\u5bf9\u8bdd", f"\u6b63\u5728\u56de\u5fc6{recall_intent['time_label']}\u7684\u5bf9\u8bdd\u8bb0\u5f55\u2026", "running")

        # Step 2: 上下文接入（CoD 模式跳过 L3/L5）
        l3 = [] if (_use_cod or _use_light_chat_bundle) else S.load_l3_long_term()
        l4 = S.load_l4_persona()
        if isinstance(l4, dict):
            _lp = l4.get("local_persona") or {}
            if isinstance(_lp, dict):
                _up = _lp.get("user_profile")
                if isinstance(_up, dict) and not isinstance(l4.get("user_profile"), dict):
                    l4 = {**l4, "user_profile": dict(_up)}
        l5 = {} if (_use_cod or _use_light_chat_bundle) else S.load_l5_knowledge()
        persona_name = ""
        if isinstance(l4, dict):
            lp = l4.get("local_persona") or l4
            persona_name = str(lp.get("nova_name") or lp.get("name") or "")
        skill_count = len(l5.get("skills", {})) if isinstance(l5, dict) else 0

        # Step 3: 检索知识（CoD 模式跳过，由 LLM 按需调用 query_knowledge）
        if _use_cod or _use_light_chat_bundle:
            l8 = []
        else:
            l8 = S.find_relevant_knowledge(msg, limit=3, touch=True)

        try:
            from core.runtime_state.state_loader import record_memory_stats
            _cod_this = None if _use_tool_call else False
            _l4_ok = bool(l4 and isinstance(l4, dict) and len(l4) > 0)
            record_memory_stats(
                l2_searches=0 if (_use_cod or _use_light_chat_bundle) else 1, l2_hits=1 if l2_memories else 0,
                l8_searches=0 if (_use_cod or _use_light_chat_bundle) else 1, l8_hits=1 if l8 else 0,
                l3_queries=0 if (_use_cod or _use_light_chat_bundle) else 1, l3_hits=0 if (_use_cod or _use_light_chat_bundle) else (1 if l3 else 0),
                l4_queries=1, l4_hits=1 if _l4_ok else 0,
                l5_queries=0 if (_use_cod or _use_light_chat_bundle) else 1, l5_hits=0 if (_use_cod or _use_light_chat_bundle) else (1 if skill_count > 0 else 0),
                l1_count=len(l1), l3_count=len(l3),
                l4_available=_l4_ok, l5_count=skill_count,
                cod_used=_cod_this,
            )
        except Exception:
            pass

        user_turns = len([m for m in l1 if isinstance(m, dict) and m.get("role") == "user"])
        mem_parts = []
        # 上下文对话（L1）
        if user_turns:
            mem_parts.append("\u4e0a\u4e0b\u6587\u8f7d\u5165\u5b8c\u6210")
        else:
            mem_parts.append("\u9996\u8f6e\u5bf9\u8bdd")
        # 记忆模块（L2 会话理解 + L7 反馈规则）
        mem_parts.append("\u8bb0\u5fc6\u6a21\u5757\u6fc0\u6d3b")
        # 人格图谱（L4）
        mem_parts.append("\u4eba\u683c\u56fe\u8c31\u5bf9\u9f50")
        if l2_memories:
            mem_parts.append(f"\u5524\u9192{len(l2_memories)}\u6761\u6301\u4e45\u8bb0\u5fc6")
        if recall_result:
            mem_parts.append("\u65f6\u95f4\u56de\u5fc6\u5df2\u63a5\u5165")
        yield await _trace("\u8bb0\u5fc6\u52a0\u8f7d", " / ".join(mem_parts), "done")

        # Step 4: 模型思考
        dialogue_context = S.build_dialogue_context(_history_for_context, msg)
        from brain import get_current_model_name
        bundle = {
            "l1": l1, "l2": l2, "l2_memories": l2_memories,
            "l3": l3, "l4": l4, "l5": l5,
            "l7": S.search_relevant_rules(msg, limit=3),
            "l8": l8,
            "dialogue_context": dialogue_context, "user_input": msg,
            "image": user_images[0] if user_images else None,
            "images": user_images,
            "current_model": get_current_model_name(),
        }
        if _use_cod:
            bundle["cod_mode"] = True
        if recall_result:
            bundle["recall_context"] = recall_result

        # 闪回检测：旧记忆联想（潜意识层）
        try:
            from memory.flashback import detect_flashback
            _fb_hint = detect_flashback(msg)
            if _fb_hint:
                bundle["flashback_hint"] = _fb_hint
        except Exception:
            pass

        S.debug_write("context_bundle", {
            "l1": len(l1), "l2": len(l2), "l2_memories": len(l2_memories),
            "l3": len(l3),
            "l4_keys": list(l4.keys()) if isinstance(l4, dict) else [],
            "l5_skill_count": skill_count, "l8": len(l8 or []),
        })

        response = ""
        route = {"mode": "chat", "skill": "none", "reason": "default"}
        try:
            from brain import _detect_mode_switch
            mode_switch_reply = _detect_mode_switch(msg)
            if mode_switch_reply:
                response = mode_switch_reply
                yield await _trace("\u4eba\u683c\u5207\u6362", "\u5df2\u5207\u6362\u4eba\u683c\u6a21\u5f0f", "done")
                yield {"event": "reply", "data": json.dumps(_build_reply_payload(response), ensure_ascii=False)}
                _comp.activity = "idle"
                S.add_to_history("assistant", response)
                history.append({"role": "assistant", "content": response, "time": datetime.now().isoformat()})
                S.save_msg_history(history)
                return

            # 模型切换检测
            _model_switch = _detect_model_switch(msg)
            if _model_switch:
                yield await _trace("\u5207\u6362\u6a21\u578b", _model_switch.get("trace", "\u6b63\u5728\u5207\u6362\u6a21\u578b\u2026"), "done")
                response = _model_switch["reply"]
                yield {"event": "reply", "data": json.dumps(_build_reply_payload(response), ensure_ascii=False)}
                if _model_switch.get("model_changed"):
                    from brain import get_current_model_name, _current_default
                    yield {"event": "model_changed", "data": json.dumps({"model": _current_default, "model_name": get_current_model_name()}, ensure_ascii=False)}
                _comp.activity = "idle"
                S.add_to_history("assistant", response)
                history.append({"role": "assistant", "content": response, "time": datetime.now().isoformat()})
                S.save_msg_history(history)
                return

            if _tool_call_unavailable_reason:
                response = _build_tool_call_unavailable_reply(_tool_call_unavailable_reason)
                S.debug_write(
                    "tool_call_unavailable",
                    {
                        "reason": _tool_call_unavailable_reason,
                        "tool_call_enabled": _get_tool_call_enabled(),
                        "anthropic_model": _is_anthropic_model(),
                        "core_ready": S.NOVA_CORE_READY,
                    },
                )
                yield await _trace(
                    "\u4e3b\u94fe\u4e8b\u6545",
                    "tool_call \u4e3b\u94fe\u4e0d\u53ef\u7528\uff0c\u5df2\u663e\u5f0f\u62a5\u9519\uff0c\u4e0d\u518d\u56de\u9000\u5230\u65e7 skill \u94fe\u3002",
                    "error",
                )
                yield {"event": "reply", "data": json.dumps(_build_reply_payload(response), ensure_ascii=False)}
                _comp.activity = "idle"
                S.add_to_history("nova", response)
                history.append({"role": "nova", "content": response, "time": datetime.now().isoformat()})
                S.save_msg_history(history)
                return

            # ── tool_call 模式分支 ──
            if _use_tool_call:
                from core.tool_adapter import (
                    build_tools_list,
                    build_tools_list_cod,
                    execute_tool_call,
                    get_ask_user_pending,
                )
                from core.reply_formatter import unified_reply_with_tools_stream

                # tool_call 模式：一次 LLM 调用搞定路由+回复，不走规则路由
                # CoD 模式下 bundle 已在上方构建时跳过 L2记忆/L3/L5/L8
                S.debug_write("tool_call_mode", {"enabled": True, "cod": _use_cod})

                # 联网搜索前置（和旧路径逻辑一致）
                if S.is_explicit_learning_request and S.is_explicit_learning_request(msg):
                    yield await _trace("\u8054\u7f51\u641c\u7d22", "\u6b63\u5728\u5206\u6790\u641c\u7d22\u4e3b\u9898\u2026", "running")
                    _extract_prompt = (
                        "\u7528\u6237\u8bf4\u4e86\u4e0b\u9762\u8fd9\u53e5\u8bdd\uff0c\u8bf7\u4ece\u4e2d\u63d0\u53d6\u51fa\u4ed6\u771f\u6b63\u60f3\u641c\u7d22/\u5b66\u4e60\u7684\u4e3b\u9898\u5173\u952e\u8bcd\u3002"
                        "\u5982\u679c\u7528\u6237\u6ca1\u6709\u6307\u5b9a\u5177\u4f53\u4e3b\u9898\uff08\u6bd4\u5982\u53ea\u8bf4\u201c\u53bb\u5b66\u70b9\u4e1c\u897f\u201d\uff09\uff0c"
                        "\u5c31\u6839\u636e\u4e4b\u524d\u7684\u5bf9\u8bdd\u4e0a\u4e0b\u6587\uff0c\u9009\u4e00\u4e2a\u7528\u6237\u53ef\u80fd\u611f\u5174\u8da3\u7684\u4e3b\u9898\u3002"
                        "\u53ea\u8f93\u51fa\u641c\u7d22\u5173\u952e\u8bcd\uff0c\u4e0d\u8981\u89e3\u91ca\uff0c\u4e0d\u8981\u52a0\u5f15\u53f7\uff0c\u4e0d\u8d85\u8fc715\u4e2a\u5b57\u3002\n\n"
                        f"\u7528\u6237\u539f\u8bdd\uff1a{msg}\n"
                        f"\u6700\u8fd1\u5bf9\u8bdd\u4e0a\u4e0b\u6587\uff1a{bundle.get('dialogue_context', '')[:300]}"
                    )
                    _raw_topic = S.raw_llm_call(_extract_prompt)
                    _search_topic = str(_raw_topic or "").strip()[:15]
                    _search_topic = _search_topic.strip('"\'\u201c\u201d\u300c\u300d\u3010\u3011')
                    if len(_search_topic) < 2 or len(_search_topic) > 40:
                        _search_topic = msg
                    if _search_topic == msg:
                        _stop = ["\u5e2e\u6211","\u7ed9\u6211","\u80fd\u4e0d\u80fd","\u53ef\u4ee5","\u597d\u770b\u7684","\u6700\u65b0\u7684","\u4e00\u4e0b","\u51e0\u672c","\u4e00\u4e9b","\u4f60","\u5417","\u5440","\u5462","\u4e86","\u7684","\u70b9"]
                        _cleaned = msg
                        for sw in _stop:
                            _cleaned = _cleaned.replace(sw, "")
                        _cleaned = _re.sub(r'\s+', ' ', _cleaned).strip()
                        if len(_cleaned) >= 2:
                            _search_topic = _cleaned
                    S.debug_write("tool_call_search_topic", {"input": msg, "topic": _search_topic})
                    yield await _trace("\u8054\u7f51\u641c\u7d22", "\u641c\u7d22\u4e3b\u9898\uff1a" + _search_topic, "running")
                    _search_result = S.explicit_search_and_learn(_search_topic)
                    S.debug_write("tool_call_explicit_search", {
                        "topic": _search_topic, "success": _search_result.get("success"),
                        "reason": _search_result.get("reason", ""), "result_count": _search_result.get("result_count", 0),
                    })
                    if _search_result.get("success"):
                        _search_ctx = "\u3010\u5b9e\u65f6\u641c\u7d22\u7ed3\u679c\u3011\n"
                        for _si, _sr in enumerate(_search_result.get("results", [])[:5], 1):
                            _search_ctx += f"{_si}. {_sr.get('title', '')}\n   {_sr.get('snippet', '')}\n"
                        bundle["search_context"] = _search_ctx
                        bundle["search_summary"] = _search_result.get("summary", "")
                        yield await _trace("\u6574\u7406\u7ed3\u679c", "\u641c\u5230 " + str(_search_result.get("result_count", 0)) + " \u6761\u7ed3\u679c\uff0c\u6b63\u5728\u6574\u7406\u2026", "done")
                    else:
                        yield await _trace("\u7ec4\u7ec7\u56de\u590d", "\u641c\u7d22\u672a\u627e\u5230\u7ed3\u679c\uff0c\u7ed3\u5408\u5df2\u6709\u77e5\u8bc6\u56de\u590d\u2026", "running")

                tools = build_tools_list_cod() if _use_cod else build_tools_list()
                _comp.activity = "replying"
                _stream_chunks = []
                _tool_used = None
                _tool_success = None
                _tool_run_meta = {}
                _task_plan = None
                _tool_action_summary = ""
                _tool_response_text = ""
                _trace_thinking_sent = False
                _thinking_trace_text = ""
                _thinking_trace_emitted = ""
                _last_thinking_emit_at = 0.0
                _think_carry = ""
                _inside_think_block = False
                _tool_trace_started = False
                _tool_inflight_name = ""
                _dropped_stream_prefix = ""
                _msg_short = msg[:20] + ("\u2026" if len(msg) > 20 else "")
                _default_think_detail = f"\u6211\u5148\u7406\u89e3\u4f60\u8fd9\u53e5\u300c{_msg_short}\u300d\uff0c\u5224\u65ad\u662f\u76f4\u63a5\u56de\u7b54\u8fd8\u662f\u5148\u8c03\u7528\u5de5\u5177\u3002"
                _thinking_step_key = "thinking:decision"
                _thinking_reason_kind = "decision"
                _thinking_goal = ""
                _thinking_decision_note = _default_think_detail
                _thinking_handoff_note = ""
                _thinking_expected_output = _build_expected_output(phase="thinking")
                _thinking_next_user_need = _build_next_user_need(expected_output=_thinking_expected_output)
                # 立即发出思考卡片，不等 LLM 首 token
                yield await _trace(
                    "\u6a21\u578b\u601d\u8003",
                    _default_think_detail,
                    "running",
                    step_key=_thinking_step_key,
                    phase="thinking",
                    reason_kind=_thinking_reason_kind,
                    decision_note=_thinking_decision_note,
                    expected_output=_thinking_expected_output,
                    next_user_need=_thinking_next_user_need,
                    full_detail=_default_think_detail,
                )
                _trace_thinking_sent = True
                async def _emit_default_thinking_trace():
                    nonlocal _trace_thinking_sent
                    if not _trace_thinking_sent:
                        yield await _trace(
                            "\u6a21\u578b\u601d\u8003",
                            _default_think_detail,
                            "running",
                            step_key=_thinking_step_key,
                            phase="thinking",
                            reason_kind=_thinking_reason_kind,
                            decision_note=_thinking_decision_note,
                            expected_output=_thinking_expected_output,
                            next_user_need=_thinking_next_user_need,
                            full_detail=_default_think_detail,
                        )
                        _trace_thinking_sent = True

                def _append_thinking_text(existing: str, incoming: str) -> str:
                    current = str(existing or "")
                    piece = str(incoming or "")
                    if not piece:
                        return current
                    if not current:
                        return piece
                    if current.endswith(piece):
                        return current
                    return current + piece

                def _normalize_thinking_trace_text(text: str) -> str:
                    cleaned = str(text or "").replace("\r", " ").replace("\n", " ")
                    cleaned = _re.sub(r"\s+", " ", cleaned).strip()
                    return cleaned

                def _update_thinking_meta(
                    *,
                    reason_kind: str = "",
                    goal: str = "",
                    decision_note: str = "",
                    handoff_note: str = "",
                    expected_output: str = "",
                    next_user_need: str = "",
                ) -> None:
                    nonlocal _thinking_reason_kind, _thinking_goal, _thinking_decision_note, _thinking_handoff_note, _thinking_expected_output, _thinking_next_user_need
                    if _clean_step_text(reason_kind):
                        _thinking_reason_kind = _clean_step_text(reason_kind)
                    if _clean_step_text(goal):
                        _thinking_goal = _clean_step_text(goal)
                    if _clean_step_text(decision_note):
                        _thinking_decision_note = _clean_step_text(decision_note)
                    if _clean_step_text(handoff_note):
                        _thinking_handoff_note = _clean_step_text(handoff_note)
                    if _clean_step_text(expected_output):
                        _thinking_expected_output = _clean_step_text(expected_output)
                    if _clean_step_text(next_user_need):
                        _thinking_next_user_need = _clean_step_text(next_user_need)

                def _looks_like_toolish_thinking_text(
                    text: str,
                    *,
                    tool_name: str = "",
                    preview: str = "",
                    action_summary: str = "",
                ) -> bool:
                    visible = _normalize_thinking_trace_text(text)
                    if not visible:
                        return False
                    lower = visible.lower()
                    tool_lower = str(tool_name or "").strip().lower()
                    preview_text = str(preview or "").strip()
                    action_text = str(action_summary or "").strip()
                    if visible.startswith("{") or visible.startswith("["):
                        return True
                    if any(token in visible for token in ("📍", "°C", "http://", "https://")):
                        return True
                    if tool_lower and (
                        lower.startswith(tool_lower)
                        or f"{tool_lower} ·" in lower
                        or f"{tool_lower}:" in lower
                    ):
                        return True
                    if action_text and action_text in visible:
                        return True
                    if preview_text and preview_text in visible and len(visible) <= max(len(preview_text) + 40, 180):
                        return True
                    if _re.match(r"^[a-z0-9_]+\s*[·•:/：-]\s*", lower) and len(visible) <= 180:
                        return True
                    if visible.count(" / ") >= 1 and len(visible) <= 160:
                        return True
                    return False

                def _prefer_reason_note_for_tool(
                    current_text: str,
                    *,
                    tool_name: str = "",
                    preview: str = "",
                    reason_note: str = "",
                    action_summary: str = "",
                ) -> str:
                    reason = _normalize_thinking_trace_text(reason_note)
                    current = _normalize_thinking_trace_text(current_text)
                    if not reason:
                        return current
                    if not current or current == _default_think_detail:
                        return reason
                    if _looks_like_toolish_thinking_text(
                        current,
                        tool_name=tool_name,
                        preview=preview,
                        action_summary=action_summary,
                    ):
                        return reason
                    if len(current) < 42:
                        return reason
                    return current

                async def _emit_thinking_trace(force: bool = False):
                    nonlocal _thinking_trace_emitted, _last_thinking_emit_at, _trace_thinking_sent
                    if _tool_trace_started:
                        return
                    detail = _normalize_thinking_trace_text(_thinking_trace_text) or _thinking_decision_note or _default_think_detail
                    if not detail or detail == _thinking_trace_emitted:
                        return
                    now = asyncio.get_running_loop().time()
                    if not force:
                        changed = detail[len(_thinking_trace_emitted):] if detail.startswith(_thinking_trace_emitted) else detail
                        if len(changed) < 24 and not _re.search(r"[。！？!?；;：:]\s*$", changed) and (now - _last_thinking_emit_at) < 0.35:
                            return
                    _thinking_trace_emitted = detail
                    _last_thinking_emit_at = now
                    yield await _trace(
                        "\u6a21\u578b\u601d\u8003",
                        detail,
                        "running",
                        step_key=_thinking_step_key,
                        phase="thinking",
                        reason_kind=_thinking_reason_kind,
                        goal=_thinking_goal,
                        decision_note=_thinking_decision_note,
                        handoff_note=_thinking_handoff_note,
                        expected_output=_thinking_expected_output,
                        next_user_need=_thinking_next_user_need,
                        full_detail=detail,
                    )
                    _trace_thinking_sent = True

                try:
                    import queue, threading
                    _q = queue.Queue()
                    _last_ask_user_id = ""
                    def _tc_stream_worker():
                        try:
                            for _token in unified_reply_with_tools_stream(bundle, tools, execute_tool_call):
                                _q.put(_token)
                        except Exception as _e:
                            _q.put(("__error__", _e))
                        finally:
                            _q.put(None)
                    _t = threading.Thread(target=_tc_stream_worker, daemon=True)
                    _t.start()

                    while True:
                        try:
                            _item = _q.get(timeout=0.05)
                        except queue.Empty:
                            try:
                                _pending_question = get_ask_user_pending()
                            except Exception:
                                _pending_question = None
                            if isinstance(_pending_question, dict):
                                _pending_id = str(_pending_question.get("id") or "").strip()
                                if _pending_id and _pending_id != _last_ask_user_id:
                                    _last_ask_user_id = _pending_id
                                    yield {
                                        "event": "ask_user",
                                        "data": json.dumps(_pending_question, ensure_ascii=False),
                                    }
                            async for _evt in _emit_thinking_trace():
                                yield _evt
                            _now = asyncio.get_running_loop().time()
                            _idle_for = _now - _last_progress_at
                            if _idle_for >= 1.2 and (_now - _last_wait_event_at) >= 1.0:
                                _wait_label, _wait_detail = _build_waiting_step(
                                    _idle_for,
                                    tool_active=bool(_tool_trace_started and not _tool_used),
                                    streamed=bool(_stream_chunks),
                                )
                                yield await _agent_step("waiting", _wait_detail, _wait_label, int(_idle_for))
                            await asyncio.sleep(0.02)
                            continue
                        _last_progress_at = asyncio.get_running_loop().time()
                        _last_wait_event_at = 0.0
                        if _item is None:
                            break
                        if isinstance(_item, tuple) and len(_item) == 2 and _item[0] == "__error__":
                            raise _item[1]
                        if isinstance(_item, dict):
                            if _item.get("_stream_reset"):
                                _reset_info = _item.get("_stream_reset") or {}
                                _dropped_text, _think_carry, _inside_think_block = _reset_stream_visible_state(
                                    _stream_chunks,
                                    _think_carry,
                                )
                                yield {
                                    "event": "stream_reset",
                                    "data": json.dumps(
                                        {"reason": str(_reset_info.get("reason") or "stream_reset")},
                                        ensure_ascii=False,
                                    ),
                                }
                                _reset_text = str(_reset_info.get("text") or "").strip()
                                _dropped_stream_prefix = _dropped_text or _reset_text or _dropped_stream_prefix
                                if _dropped_stream_prefix:
                                    S.debug_write("tool_call_stream_prefix_dropped", {
                                        "reason": str(_reset_info.get("reason") or "stream_reset"),
                                        "text_len": len(_dropped_stream_prefix),
                                        "text_preview": _dropped_stream_prefix[:120],
                                    })
                                continue
                            if _item.get("_tool_call"):
                                tc_info = _item["_tool_call"]
                                tc_name = tc_info.get("name", "")
                                tc_preview = str(tc_info.get("preview") or "").strip()
                                tc_process_meta = tc_info.get("process_meta") if isinstance(tc_info.get("process_meta"), dict) else {}
                                _MEMORY_TOOL_NAMES = {"recall_memory": "\u56de\u5fc6\u8bb0\u5fc6", "query_knowledge": "\u67e5\u8be2\u77e5\u8bc6"}
                                _tool_skill_display = _MEMORY_TOOL_NAMES.get(tc_name) or S.get_skill_display_name(tc_name)
                                if tc_name == "web_search":
                                    _tool_skill_display = "\u8054\u7f51\u641c\u7d22"
                                _tool_expected_output = _build_expected_output(
                                    phase="tool",
                                    tool_name=tc_name,
                                    preview=tc_preview,
                                    display_name=_tool_skill_display,
                                )
                                _tool_next_user_need = _build_next_user_need(
                                    tool_name=tc_name,
                                    preview=tc_preview,
                                    expected_output=_tool_expected_output,
                                )
                                _tool_handoff_note = (
                                    f"\u5148\u4ea4\u7ed9\u300c{_tool_skill_display}\u300d\u628a\u8fd9\u4e00\u6b65\u9700\u8981\u7684\u4f9d\u636e\u62ff\u5230"
                                    if _tool_skill_display
                                    else "\u5148\u62ff\u5230\u8fd9\u4e00\u6b65\u9700\u8981\u7684\u5173\u952e\u4f9d\u636e"
                                )
                                if tc_info.get("executing"):
                                    _tool_inflight_name = tc_name
                                    async for _evt in _emit_thinking_trace(force=True):
                                        yield _evt
                                    _tool_trace_started = True
                                    if not _dropped_stream_prefix:
                                        _dropped_stream_prefix = _drop_incomplete_tool_handoff_prefix(_stream_chunks)
                                        if _dropped_stream_prefix:
                                            yield {
                                                "event": "stream_reset",
                                                "data": json.dumps(
                                                    {"reason": "tool_handoff_prefix_dropped"},
                                                    ensure_ascii=False,
                                                ),
                                            }
                                            S.debug_write("tool_call_stream_prefix_dropped", {
                                                "tool_name": tc_name,
                                                "text_len": len(_dropped_stream_prefix),
                                                "text_preview": _dropped_stream_prefix[:120],
                                            })
                                    _comp.activity = "skill"
                                    skill_display = _tool_skill_display
                                    _is_mem_tool = tc_name in _MEMORY_TOOL_NAMES
                                    if tc_name == "web_search":
                                        _trace_label = "\u8054\u7f51\u641c\u7d22"
                                        skill_display = "\u8054\u7f51\u641c\u7d22"
                                    elif _is_mem_tool:
                                        _trace_label = "\u68c0\u7d22\u8bb0\u5fc6"
                                    else:
                                        _trace_label = "\u8c03\u7528\u6280\u80fd"
                                    _reason_note = _build_tool_reason_note(tc_name, tc_preview, skill_display)
                                    if _reason_note:
                                        _update_thinking_meta(
                                            reason_kind="tool_decision",
                                            goal=tc_preview or skill_display,
                                            decision_note=_reason_note,
                                            handoff_note=_tool_handoff_note,
                                            expected_output=_tool_expected_output,
                                            next_user_need=_tool_next_user_need,
                                        )
                                        _thinking_trace_text = _prefer_reason_note_for_tool(
                                            _thinking_trace_text or _thinking_trace_emitted or _default_think_detail,
                                            tool_name=tc_name,
                                            preview=tc_preview,
                                            reason_note=_reason_note,
                                            action_summary=_tool_action_summary,
                                        )
                                        async for _evt in _emit_thinking_trace(force=True):
                                            yield _evt
                                    elif not _trace_thinking_sent:
                                        async for _evt in _emit_default_thinking_trace():
                                            yield _evt
                                    _trace_detail = build_tool_execution_trace_detail(
                                        tool_name=tc_name,
                                        preview=tc_preview,
                                        skill_display=skill_display,
                                        process_meta=tc_process_meta,
                                    )
                                    yield await _trace(
                                        _trace_label,
                                        _trace_detail,
                                        "running",
                                        phase="tool",
                                        tool_name=tc_name,
                                        goal=tc_preview,
                                        handoff_note=_tool_handoff_note,
                                        expected_output=_tool_expected_output,
                                        next_user_need=_tool_next_user_need,
                                        reason_kind="tool_execution",
                                        full_detail=_trace_detail,
                                    )
                                elif tc_info.get("done"):
                                    if tc_info.get("synthetic") and not _dropped_stream_prefix and _stream_chunks:
                                        _dropped_stream_prefix = _drop_incomplete_tool_handoff_prefix(_stream_chunks)
                                        if _dropped_stream_prefix:
                                            yield {
                                                "event": "stream_reset",
                                                "data": json.dumps(
                                                    {"reason": "tool_handoff_prefix_dropped"},
                                                    ensure_ascii=False,
                                                ),
                                            }
                                            S.debug_write("tool_call_stream_prefix_dropped", {
                                                "tool_name": tc_name,
                                                "text_len": len(_dropped_stream_prefix),
                                                "text_preview": _dropped_stream_prefix[:120],
                                                "synthetic": True,
                                            })
                                    _tool_inflight_name = ""
                                    _tool_used = tc_name
                                    _tool_success = bool(tc_info.get("success"))
                                    _tool_run_meta = tc_info.get("run_meta") if isinstance(tc_info.get("run_meta"), dict) else {}
                                    _plan_update = _extract_task_plan_from_meta(_tool_run_meta)
                                    if _plan_update:
                                        _task_plan = _plan_update
                                        yield {"event": "plan", "data": json.dumps(_plan_update, ensure_ascii=False)}
                                    _tool_action_summary = str(tc_info.get("action_summary") or "").strip()
                                    _tool_response_text = str(tc_info.get("response") or "").strip()
                                    _comp.activity = "replying"
                                    _MEMORY_TOOL_NAMES2 = {"recall_memory": "\u56de\u5fc6\u8bb0\u5fc6", "query_knowledge": "\u67e5\u8be2\u77e5\u8bc6"}
                                    _dn = _MEMORY_TOOL_NAMES2.get(tc_name) or ("联网搜索" if tc_name == "web_search" else S.get_skill_display_name(tc_name))
                                    _is_mem2 = tc_name in _MEMORY_TOOL_NAMES2
                                    if tc_info.get("success"):
                                        if tc_name == "web_search":
                                            _done_label = "\u641c\u7d22\u5b8c\u6210"
                                        elif _is_mem2:
                                            _done_label = "\u8bb0\u5fc6\u5c31\u7eea"
                                        else:
                                            _done_label = "\u6280\u80fd\u5b8c\u6210"
                                        _done_detail = build_tool_done_trace_detail(
                                            tool_name=tc_name,
                                            preview=tc_preview,
                                            success=True,
                                            action_summary=str(tc_info.get("action_summary") or "").strip(),
                                            response=tc_info.get("response", ""),
                                            process_meta=tc_process_meta,
                                        ) or f"{_dn}\u5b8c\u6210"
                                        yield await _trace(
                                            _done_label,
                                            _done_detail,
                                            "done",
                                            step_key=_active_tool_step_key,
                                            phase="tool",
                                            tool_name=tc_name,
                                            goal=tc_preview,
                                            expected_output=_tool_expected_output,
                                            next_user_need=_tool_next_user_need,
                                            reason_kind="tool_result",
                                            full_detail=_done_detail,
                                        )
                                    else:
                                        if tc_name == "web_search":
                                            _fail_label = "\u641c\u7d22\u5931\u8d25"
                                        elif _is_mem2:
                                            _fail_label = "\u68c0\u7d22\u5931\u8d25"
                                        else:
                                            _fail_label = "\u6280\u80fd\u5931\u8d25"
                                        _fail_label = build_tool_done_label(
                                            _fail_label,
                                            success=False,
                                            process_meta=tc_process_meta,
                                        )
                                        _fail_detail = build_tool_done_trace_detail(
                                            tool_name=tc_name,
                                            preview=tc_preview,
                                            success=False,
                                            action_summary=str(tc_info.get("action_summary") or "").strip(),
                                            response=tc_info.get("response", ""),
                                            process_meta=tc_process_meta,
                                        ) or f"{_dn}\u5931\u8d25"
                                        yield await _trace(
                                            _fail_label,
                                            _fail_detail,
                                            "error",
                                            step_key=_active_tool_step_key,
                                            phase="tool",
                                            tool_name=tc_name,
                                            goal=tc_preview,
                                            expected_output=_tool_expected_output,
                                            next_user_need=_tool_next_user_need,
                                            reason_kind="tool_result",
                                            full_detail=_fail_detail,
                                        )
                            elif _item.get("_done"):
                                async for _evt in _emit_thinking_trace(force=True):
                                    yield _evt
                                _tool_used = _item.get("tool_used")
                                _tool_inflight_name = ""
                                if "run_meta" in _item and isinstance(_item.get("run_meta"), dict):
                                    _tool_run_meta = _item.get("run_meta") or {}
                                    _plan_update = _extract_task_plan_from_meta(_tool_run_meta)
                                    if _plan_update:
                                        _task_plan = _plan_update
                                        yield {"event": "plan", "data": json.dumps(_plan_update, ensure_ascii=False)}
                                if "success" in _item:
                                    _tool_success = bool(_item.get("success"))
                                if "tool_response" in _item:
                                    _tool_response_text = str(_item.get("tool_response") or _tool_response_text or "").strip()
                                _tool_action_summary = str(_item.get("action_summary") or _tool_action_summary or "").strip()
                                break
                            elif _item.get("_thinking"):
                                if not _tool_trace_started and not _trace_thinking_sent:
                                    async for _evt in _emit_default_thinking_trace():
                                        yield _evt
                            elif "_thinking_content" in _item:
                                if not _tool_trace_started:
                                    _thinking_trace_text = _append_thinking_text(
                                        _thinking_trace_text,
                                        str(_item.get("_thinking_content") or ""),
                                    )
                                    async for _evt in _emit_thinking_trace():
                                        yield _evt
                            continue
                        # 文本 token — 过滤 <think> 标签
                        _visible_parts, _think_carry, _inside_think_block, _saw_think = _consume_think_filtered_stream_text(
                            _think_carry,
                            _item,
                            in_think=_inside_think_block,
                        )
                        if _saw_think and not _trace_thinking_sent and not _tool_trace_started:
                            async for _evt in _emit_default_thinking_trace():
                                yield _evt
                        for _visible in _visible_parts:
                            if not _visible:
                                continue
                            _stream_chunks.append(_visible)
                            yield {"event": "stream", "data": json.dumps({"token": _visible}, ensure_ascii=False)}
                                # 超过 7 字符没出现 <think>，直接输出
                            if False:
                                if _think_buf.strip():
                                    _stream_chunks.append(_think_buf)
                                    yield {"event": "stream", "data": json.dumps({"token": _think_buf}, ensure_ascii=False)}
                            # else: 继续缓冲，等更多 token 到达再判断
                        if False:
                            _stream_chunks.append(_item)
                            yield {"event": "stream", "data": json.dumps({"token": _item}, ensure_ascii=False)}

                    _tail_parts, _think_carry, _inside_think_block, _tail_saw_think = _consume_think_filtered_stream_text(
                        _think_carry,
                        "",
                        in_think=_inside_think_block,
                        end_of_stream=True,
                    )
                    if _tail_saw_think and not _trace_thinking_sent and not _tool_trace_started:
                        async for _evt in _emit_default_thinking_trace():
                            yield _evt
                    for _tail in _tail_parts:
                        if not _tail:
                            continue
                        _stream_chunks.append(_tail)
                        yield {"event": "stream", "data": json.dumps({"token": _tail}, ensure_ascii=False)}
                    async for _evt in _emit_thinking_trace(force=True):
                        yield _evt
                    response = "".join(_stream_chunks)
                    S.debug_write("tool_call_stream_done", {
                        "chunks": len(_stream_chunks),
                        "len": len(response),
                        "tool_used": _tool_used,
                        "dropped_prefix_len": len(_dropped_stream_prefix),
                    })
                except Exception as _tce:
                    failure_message = f"\u5de5\u5177\u6267\u884c\u5f02\u5e38\uff1a{type(_tce).__name__}: {_tce}"
                    S.debug_write("tool_call_error", {
                        "error": failure_message,
                        "tool_inflight": _tool_inflight_name,
                        "tool_used": _tool_used,
                    })
                    if _tool_inflight_name:
                        _tool_used = _tool_inflight_name
                        _tool_success = False
                        _tool_response_text = failure_message if not _tool_response_text else f"{_tool_response_text}\n\n{failure_message}"
                        if not _tool_action_summary:
                            _tool_action_summary = _summarize_tool_response_text(_tool_response_text)
                        response = _tool_response_text
                        if _tool_action_summary:
                            yield await _trace(
                                "\u6280\u80fd\u5931\u8d25",
                                " \u00b7 ".join([p for p in [_tool_used, _tool_action_summary] if p]),
                                "error",
                            )
                    if not _stream_chunks and not _tool_inflight_name:
                        response = failure_message
                    if False and not _stream_chunks and not _tool_inflight_name:
                        # fallback 到非流式 tool_call
                        # legacy frontend non-stream fallback removed; keep branch unreachable for localized compatibility cleanup
                        tc_result = {}
                        response = tc_result.get("reply", "")
                        _tool_used = tc_result.get("tool_used")
                        _tool_run_meta = tc_result.get("run_meta") if isinstance(tc_result.get("run_meta"), dict) else {}
                        _plan_update = _extract_task_plan_from_meta(_tool_run_meta)
                        if _plan_update:
                            _task_plan = _plan_update
                            yield {"event": "plan", "data": json.dumps(_plan_update, ensure_ascii=False)}
                        _tool_success = tc_result.get("success") if _tool_used else None
                        _tool_response_text = str(tc_result.get("tool_response") or "").strip()
                        _action_summary = str(tc_result.get("action_summary") or "").strip()
                        _tool_action_summary = _action_summary or _tool_action_summary
                        if _tool_used and _action_summary:
                            yield await _trace(
                                "技能完成" if _tool_success else "技能失败",
                                " · ".join([p for p in [_tool_used, _action_summary] if p]),
                                "done" if _tool_success else "error",
                            )
                    elif _stream_chunks or _tool_inflight_name:
                        response = "".join(_stream_chunks)

                # 记录技能使用统计
                if _tool_used:
                    try:
                        run_event = _build_run_event(
                            success=bool(_tool_success) if _tool_success is not None else True,
                            meta=_tool_run_meta,
                            fallback_text=response,
                            fallback_summary=_tool_action_summary,
                        )
                        S.evolve(msg, _tool_used, run_event=run_event)
                    except Exception:
                        pass
                    route = {"mode": "skill", "skill": _tool_used, "reason": "tool_call", "source": "tool_call"}
                else:
                    route = {"mode": "chat", "skill": "none", "reason": "tool_call_direct", "source": "tool_call"}

                # ── CoD 闪念/溯源 + L6 埋点（tool_call 路径）──────────────
                try:
                    from core.runtime_state.state_loader import record_memory_stats
                    _RECALL_TOOLS = {"recall_memory", "query_knowledge"}
                    _tc_cod_used = bool(_tool_used and _tool_used in _RECALL_TOOLS)
                    # L6：tool_call 调的是真实技能（非记忆工具）= 技能执行
                    _l6_hit = 1 if (_tool_used and _tool_used not in _RECALL_TOOLS) else 0
                    record_memory_stats(
                        l6_hits=_l6_hit,
                        cod_used=_tc_cod_used,
                        count_query=False,
                    )
                except Exception:
                    pass

                # 跳到最终回复处理（不走下面的正常路径）
                # 清理 think 标签 + markdown
                try:
                    from core.reply_formatter import _clean_visible_reply_text

                    response = _clean_visible_reply_text(response)
                except Exception:
                    try:
                        response = _re.sub(r'<think>.*?</think>', '', response, flags=_re.S | _re.I).strip()
                    except Exception:
                        pass
                response = _strip_markdown(response)
                if not str(response or "").strip() and _tool_used:
                    try:
                        from core.reply_formatter import _build_tool_closeout_reply

                        response = _build_tool_closeout_reply(
                            success=bool(_tool_success) if _tool_success is not None else True,
                            action_summary=_tool_action_summary,
                            tool_response=_tool_response_text,
                            run_meta=_tool_run_meta,
                        )
                    except Exception:
                        pass
                response = _ensure_tool_call_failure_reply(
                    response,
                    tool_used=_tool_used or "",
                    tool_success=_tool_success,
                    tool_response=_tool_response_text,
                    action_summary=_tool_action_summary,
                    run_meta=_tool_run_meta,
                )
                # 情况兜底：tool_call 阶段仅输出“先做某事”的前置语而未返回 tool_result。
                # 这类内容说明链路中断，强制转为失败闭环，避免只回一句“我先…”后无下一步。
                if not _tool_used and _stream_chunks:
                    try:
                        from core.reply_formatter import _looks_like_tool_preamble, _summarize_tool_response_text
                        if _looks_like_tool_preamble(response):
                            response = _ensure_tool_call_failure_reply(
                                response,
                                tool_used="tool_call",
                                tool_success=False,
                                tool_response=_tool_response_text or response,
                                action_summary=_tool_action_summary or _summarize_tool_response_text(response),
                                run_meta=_tool_run_meta,
                            )
                    except Exception:
                        pass
                if _task_plan and _tool_success is False:
                    _blocked_plan = _block_task_plan_after_failure(
                        _task_plan,
                        goal_hint=msg,
                        tool_used=_tool_used or "",
                        action_summary=_tool_action_summary,
                        tool_response=_tool_response_text or response,
                    )
                    if _blocked_plan and _blocked_plan != _task_plan:
                        _task_plan = _blocked_plan
                        yield {"event": "plan", "data": json.dumps(_blocked_plan, ensure_ascii=False)}
                try:
                    from core.reply_formatter import l1_hygiene_clean
                    response, _pre_cleaned = l1_hygiene_clean(response, history)
                    if _pre_cleaned:
                        S.debug_write("l1_hygiene_pre_reply", {"removed": _pre_cleaned})
                except Exception:
                    pass
                S.debug_write("pre_reply_yield", {"response_len": len(response), "response_preview": response[:100]})
                await asyncio.sleep(0.05)
                yield {"event": "reply", "data": json.dumps(_build_reply_payload(response), ensure_ascii=False)}

                _comp.activity = "idle"
                _comp.reply_id = datetime.now().isoformat()
                summary = str(response or "").replace("\n", " ").strip()
                _comp.last_reply = summary[:60] + ("..." if len(summary) > 60 else "")
                _comp.last_reply_full = summary
                try:
                    from brain import _detect_emotion
                    _comp.emotion = _detect_emotion(response)
                except Exception:
                    _comp.emotion = "neutral"

                # 后台任务
                feedback_rule = None
                try:
                    feedback_rule = S.l7_record_feedback_v2(msg, history, background_tasks)
                except Exception:
                    pass
                # ── L7 埋点 ──
                if feedback_rule:
                    try:
                        from core.runtime_state.state_loader import record_memory_stats
                        record_memory_stats(l7_hits=1, count_query=False)
                    except Exception:
                        pass
                    awareness_evt = {
                        "type": "l7_feedback",
                        "summary": "记录反馈规则: " + feedback_rule.get("category", "未分类"),
                        "detail": {
                            "id": feedback_rule.get("id"),
                            "scene": feedback_rule.get("scene", ""),
                            "problem": feedback_rule.get("problem", ""),
                            "category": feedback_rule.get("category", ""),
                            "fix": feedback_rule.get("fix", ""),
                        },
                    }
                    S.awareness_push(awareness_evt)
                    yield {"event": "awareness", "data": json.dumps(awareness_evt, ensure_ascii=False)}
                    _l8_cfg = S.load_autolearn_config()
                    if _l8_cfg.get("enabled", True) and _l8_cfg.get("allow_feedback_relearn", True):
                        background_tasks.add_task(S.run_l8_feedback_relearn_task, feedback_rule)
                try:
                    S.l8_touch()
                    l8_config = S.load_autolearn_config()
                    if (
                        l8_config.get("enabled", True)
                        and l8_config.get("allow_web_search", True)
                        and l8_config.get("allow_knowledge_write", True)
                        and not feedback_rule
                        and not (l8 or [])
                    ):
                        background_tasks.add_task(S.run_l8_autolearn_task, msg, response, route, bool(l8))
                except Exception:
                    pass

                repair_payload = {}
                try:
                    import agent_final as _af
                    repair_payload = _af.build_repair_progress_payload(route, feedback_rule)
                    if repair_payload.get("show"):
                        yield {"event": "repair", "data": json.dumps(repair_payload, ensure_ascii=False)}
                except Exception:
                    pass

                S.debug_write("final_response", {"reply": response, "repair": repair_payload})
                try:
                    # L1 卫生检查：防止自我强化的毒教材
                    from core.reply_formatter import l1_hygiene_clean
                    response, _toxic = l1_hygiene_clean(response, history)
                    if _toxic:
                        S.debug_write("l1_hygiene", {"removed": _toxic})
                    S.add_to_history("nova", response)
                    _nova_entry = {"role": "nova", "content": response, "time": datetime.now().isoformat()}
                    if _collected_steps or _task_plan:
                        _process = {}
                        if _task_plan:
                            _process["plan"] = _task_plan
                        _process["steps"] = _normalize_persisted_process_steps(_collected_steps)
                        _nova_entry["process"] = _process
                    history.append(_nova_entry)
                    S.save_msg_history(history)
                except Exception:
                    pass
                try:
                    S.l2_add_memory(msg, response)
                except Exception:
                    pass
                return

        except Exception as exc:
            S.debug_write("chat_exception", {"error": str(exc)})
            S.trigger_self_repair_from_error("chat_exception", {"message": msg, "error": str(exc)}, background_tasks)
            response = "\u62b1\u6b49\uff0c\u51fa\u9519\u4e86"

        # 最终回复（清理 think 标签 + 剥掉 markdown 格式符号）
        try:
            from core.reply_formatter import _clean_visible_reply_text

            response = _clean_visible_reply_text(response)
        except Exception:
            try:
                response = _re.sub(r'<think>.*?</think>', '', response, flags=_re.S | _re.I).strip()
            except Exception:
                pass
        response = _strip_markdown(response)
        try:
            from core.reply_formatter import l1_hygiene_clean
            response, _pre_cleaned = l1_hygiene_clean(response, history)
            if _pre_cleaned:
                S.debug_write("l1_hygiene_pre_reply", {"removed": _pre_cleaned})
        except Exception:
            pass
        S.debug_write("pre_reply_yield", {"response_len": len(response), "response_preview": response[:100]})
        await asyncio.sleep(0.05)
        yield {"event": "reply", "data": json.dumps(_build_reply_payload(response), ensure_ascii=False)}
        S.debug_write("post_reply_yield", {"ok": True})

        _comp.activity = "idle"

        _comp.reply_id = datetime.now().isoformat()
        summary = str(response or "").replace("\n", " ").strip()
        _comp.last_reply = summary[:60] + ("..." if len(summary) > 60 else "")
        _comp.last_reply_full = summary

        # 更新伴侣情绪状态
        try:
            from brain import _detect_emotion
            _comp.emotion = _detect_emotion(response)
        except Exception:
            _comp.emotion = "neutral"

        # 后台任务
        feedback_rule = None
        try:
            feedback_rule = S.l7_record_feedback_v2(msg, history, background_tasks)
        except Exception:
            pass
        # ── L7 埋点 ──
        if feedback_rule:
            try:
                from core.runtime_state.state_loader import record_memory_stats
                record_memory_stats(l7_hits=1, count_query=False)
            except Exception:
                pass
        if feedback_rule:
            awareness_evt = {
                "type": "l7_feedback",
                "summary": "\u8bb0\u5f55\u53cd\u9988\u89c4\u5219: " + feedback_rule.get("category", "\u672a\u5206\u7c7b"),
                "detail": {
                    "id": feedback_rule.get("id"),
                    "scene": feedback_rule.get("scene", ""),
                    "problem": feedback_rule.get("problem", ""),
                    "category": feedback_rule.get("category", ""),
                    "fix": feedback_rule.get("fix", ""),
                },
            }
            S.awareness_push(awareness_evt)
            yield {"event": "awareness", "data": json.dumps(awareness_evt, ensure_ascii=False)}
            # 触发 L8 反馈重学
            _l8_cfg = S.load_autolearn_config()
            if _l8_cfg.get("enabled", True) and _l8_cfg.get("allow_feedback_relearn", True):
                background_tasks.add_task(S.run_l8_feedback_relearn_task, feedback_rule)
        try:
            S.l8_touch()
            l8_config = S.load_autolearn_config()
            if (
                l8_config.get("enabled", True)
                and l8_config.get("allow_web_search", True)
                and l8_config.get("allow_knowledge_write", True)
                and not feedback_rule
                and not (l8 or [])
                and route.get("intent") != "missing_skill"
            ):
                background_tasks.add_task(S.run_l8_autolearn_task, msg, response, route, bool(l8))
        except Exception as _post_exc:
            S.debug_write("post_reply_error", {"stage": "l8", "error": str(_post_exc)})

        repair_payload = {}
        try:
            import agent_final as _af
            repair_payload = _af.build_repair_progress_payload(route, feedback_rule)
            if repair_payload.get("show"):
                yield {"event": "repair", "data": json.dumps(repair_payload, ensure_ascii=False)}
        except Exception as _post_exc:
            S.debug_write("post_reply_error", {"stage": "repair", "error": str(_post_exc)})

        S.debug_write("final_response", {"reply": response, "repair": repair_payload})
        try:
            # L1 卫生检查：防止自我强化的毒教材
            from core.reply_formatter import l1_hygiene_clean
            response, _toxic = l1_hygiene_clean(response, history)
            if _toxic:
                S.debug_write("l1_hygiene", {"removed": _toxic})
            S.add_to_history("nova", response)
            _nova_entry = {"role": "nova", "content": response, "time": datetime.now().isoformat()}
            if _collected_steps:
                _nova_entry["process"] = {"steps": _normalize_persisted_process_steps(_collected_steps)}
            history.append(_nova_entry)
            S.save_msg_history(history)
        except Exception as _post_exc:
            S.debug_write("post_reply_error", {"stage": "save", "error": str(_post_exc)})

        try:
            S.l2_add_memory(msg, response)
        except Exception as exc:
            S.debug_write("l2_add_error", {"error": str(exc)})

      except Exception as _fatal:
        S.debug_write("event_stream_fatal", {"error": str(_fatal), "type": type(_fatal).__name__})
        import traceback
        S.debug_write("event_stream_traceback", {"tb": traceback.format_exc()})
        yield {"event": "reply", "data": json.dumps(_build_reply_payload(f"\u5185\u90e8\u9519\u8bef\uff1a{_fatal}"), ensure_ascii=False)}
      except BaseException as _base:
        S.debug_write("event_stream_cancelled", {"error": str(_base), "type": type(_base).__name__})
        raise

    return EventSourceResponse(event_stream(), ping=2)


@router.post("/chat/answer")
async def chat_answer(request: ChatAnswerRequest):
    from core.tool_adapter import ask_user_submit

    accepted = ask_user_submit(request.question_id, request.answer)
    S.debug_write("chat_answer_submit", {
        "question_id": request.question_id,
        "accepted": bool(accepted),
    })
    return {"ok": bool(accepted)}
