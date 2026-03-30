"""核心对话路由：/chat SSE 流式"""
import asyncio
import json
import requests
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import re as _re
from core import shared as S
from routes import companion as _comp


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


def _normalize_persisted_process_steps(steps: list | None) -> list[dict]:
    rows = []
    for item in steps or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        detail = str(item.get("detail") or "").strip()
        status = str(item.get("status") or "").strip().lower()
        if status not in {"done", "error"}:
            continue
        if not label and not detail:
            continue
        row = {
            "label": label,
            "detail": detail,
            "status": "error" if status == "error" else "done",
        }
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


def _get_tool_call_enabled() -> bool:
    """tool_call 总开关，由配置控制。"""
    try:
        from core.state_loader import PRIMARY_STATE_DIR
        cfg = json.loads((PRIMARY_STATE_DIR / "tool_call_config.json").read_text("utf-8"))
        return bool(cfg.get("enabled", True))
    except Exception:
        return True


def _get_cod_enabled() -> bool:
    """CoD (Context-on-Demand) \u6a21\u5f0f\u5f00\u5173"""
    try:
        from core.state_loader import PRIMARY_STATE_DIR
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

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    image: str | None = None
    images: list[str] | None = None


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

        async def _trace(label, detail, status="running"):
            _collected_steps.append({"label": label, "detail": detail, "status": status})
            return {"event": "trace", "data": json.dumps({"label": label, "detail": detail, "status": status}, ensure_ascii=False)}

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
                return f"这类问题直接查实时天气更稳，我先确认「{preview}」的天气结果。"
            if preview:
                return f"我判断这一步更适合先调用「{display_name}」，目标：{preview}。"
            if display_name:
                return f"我判断这一步更适合先调用「{display_name}」来推进。"
            return ""

        pending_awareness = S.awareness_pull()
        for evt in pending_awareness:
            yield {"event": "awareness", "data": json.dumps(evt, ensure_ascii=False)}

        # ── CoD / tool_call 开关提前判断 ──
        _tool_call_unavailable_reason = _get_tool_call_unavailable_reason()
        _use_tool_call = _tool_call_unavailable_reason is None
        _use_cod = _use_tool_call and _get_cod_enabled()

        # Step 1: 记忆加载
        l1 = S.get_recent_messages(_history_for_context, 10)
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
            from core.state_loader import record_memory_stats
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
            from core.flashback import detect_flashback
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
                yield {"event": "reply", "data": json.dumps({"reply": response}, ensure_ascii=False)}
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
                yield {"event": "reply", "data": json.dumps({"reply": response}, ensure_ascii=False)}
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
                yield {"event": "reply", "data": json.dumps({"reply": response}, ensure_ascii=False)}
                _comp.activity = "idle"
                S.add_to_history("nova", response)
                history.append({"role": "nova", "content": response, "time": datetime.now().isoformat()})
                S.save_msg_history(history)
                return

            # ── tool_call 模式分支 ──
            if _use_tool_call:
                from core.tool_adapter import build_tools_list, build_tools_list_cod, execute_tool_call
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
                _think_buf = ""
                _think_done = False
                _tool_trace_started = False
                _msg_short = msg[:20] + ("\u2026" if len(msg) > 20 else "")
                _default_think_detail = f"\u6211\u5148\u7406\u89e3\u4f60\u8fd9\u53e5\u300c{_msg_short}\u300d\uff0c\u5224\u65ad\u662f\u76f4\u63a5\u56de\u7b54\u8fd8\u662f\u5148\u8c03\u7528\u5de5\u5177\u3002"
                # 立即发出思考卡片，不等 LLM 首 token
                yield await _trace("\u6a21\u578b\u601d\u8003", _default_think_detail, "running")
                _trace_thinking_sent = True
                async def _emit_default_thinking_trace():
                    nonlocal _trace_thinking_sent
                    if not _trace_thinking_sent:
                        yield await _trace("\u6a21\u578b\u601d\u8003", _default_think_detail, "running")
                        _trace_thinking_sent = True

                try:
                    import queue, threading
                    _q = queue.Queue()
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
                            await asyncio.sleep(0.02)
                            continue
                        if _item is None:
                            break
                        if isinstance(_item, tuple) and len(_item) == 2 and _item[0] == "__error__":
                            raise _item[1]
                        if isinstance(_item, dict):
                            if _item.get("_tool_call"):
                                tc_info = _item["_tool_call"]
                                tc_name = tc_info.get("name", "")
                                tc_preview = str(tc_info.get("preview") or "").strip()
                                if tc_info.get("executing"):
                                    _tool_trace_started = True
                                    _comp.activity = "skill"
                                    _MEMORY_TOOL_NAMES = {"recall_memory": "\u56de\u5fc6\u8bb0\u5fc6", "query_knowledge": "\u67e5\u8be2\u77e5\u8bc6"}
                                    skill_display = _MEMORY_TOOL_NAMES.get(tc_name) or S.get_skill_display_name(tc_name)
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
                                        yield await _trace("\u6a21\u578b\u601d\u8003", _reason_note, "running")
                                        _trace_thinking_sent = True
                                    elif not _trace_thinking_sent:
                                        yield await _trace("\u6a21\u578b\u601d\u8003", _default_think_detail, "running")
                                        _trace_thinking_sent = True
                                    _trace_parts = [tc_name] if tc_name else []
                                    if tc_preview:
                                        _trace_parts.append(f"\u76ee\u6807\uff1a{tc_preview}")
                                    elif tc_name:
                                        _trace_parts.append(f"\u6b63\u5728\u6267\u884c {tc_name}\u2026")
                                    _trace_detail = " \u00b7 ".join([p for p in _trace_parts if p]) or f"\u6b63\u5728{skill_display}\u2026"
                                    yield await _trace(_trace_label, _trace_detail, "running")
                                elif tc_info.get("done"):
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
                                        _done_detail = str(tc_info.get("action_summary") or "").strip()
                                        if not _done_detail:
                                            _done_detail = _summarize_tool_response_text(tc_info.get("response", ""))
                                        if not _done_detail:
                                            _done_detail = f"{_dn}\u5b8c\u6210"
                                        if tc_name:
                                            _done_detail = " \u00b7 ".join([p for p in [tc_name, _done_detail] if p])
                                        yield await _trace(_done_label, _done_detail, "done")
                                    else:
                                        if tc_name == "web_search":
                                            _fail_label = "\u641c\u7d22\u5931\u8d25"
                                        elif _is_mem2:
                                            _fail_label = "\u68c0\u7d22\u5931\u8d25"
                                        else:
                                            _fail_label = "\u6280\u80fd\u5931\u8d25"
                                        _fail_detail = str(tc_info.get("action_summary") or tc_info.get("response") or "").strip()
                                        if not _fail_detail:
                                            _fail_detail = f"{_dn}\u5931\u8d25"
                                        if tc_preview:
                                            _fail_detail = f"\u76ee\u6807\uff1a{tc_preview}"
                                        if tc_name:
                                            _fail_detail = " \u00b7 ".join([p for p in [tc_name, _fail_detail] if p])
                                        yield await _trace(_fail_label, _fail_detail, "error")
                            elif _item.get("_done"):
                                _tool_used = _item.get("tool_used")
                                if "run_meta" in _item and isinstance(_item.get("run_meta"), dict):
                                    _tool_run_meta = _item.get("run_meta") or {}
                                    _plan_update = _extract_task_plan_from_meta(_tool_run_meta)
                                    if _plan_update:
                                        _task_plan = _plan_update
                                        yield {"event": "plan", "data": json.dumps(_plan_update, ensure_ascii=False)}
                                if "success" in _item:
                                    _tool_success = bool(_item.get("success"))
                                _tool_action_summary = str(_item.get("action_summary") or _tool_action_summary or "").strip()
                                break
                            elif _item.get("_thinking"):
                                if not _tool_trace_started and not _trace_thinking_sent:
                                    yield await _trace("\u6a21\u578b\u601d\u8003", _default_think_detail, "running")
                                    _trace_thinking_sent = True
                            continue
                        # 文本 token — 过滤 <think> 标签
                        if not _tool_trace_started and not _trace_thinking_sent and not _think_buf:
                            async for _evt in _emit_default_thinking_trace():
                                yield _evt
                        if not _think_done:
                            _think_buf += _item
                            if '<think>' in _think_buf.lower():
                                if not _trace_thinking_sent and not _tool_trace_started:
                                    yield await _trace("\u6a21\u578b\u601d\u8003", _default_think_detail, "running")
                                    _trace_thinking_sent = True
                                _close_match = _re.search(r'</think>', _think_buf, flags=_re.I)
                                if _close_match:
                                    _think_done = True
                                    _after = _think_buf[_close_match.end():]
                                    if _after.strip():
                                        _stream_chunks.append(_after)
                                        yield {"event": "stream", "data": json.dumps({"token": _after}, ensure_ascii=False)}
                            elif len(_think_buf) > 7:
                                # 超过 7 字符没出现 <think>，直接输出
                                _think_done = True
                                if _think_buf.strip():
                                    _stream_chunks.append(_think_buf)
                                    yield {"event": "stream", "data": json.dumps({"token": _think_buf}, ensure_ascii=False)}
                            # else: 继续缓冲，等更多 token 到达再判断
                        else:
                            _stream_chunks.append(_item)
                            yield {"event": "stream", "data": json.dumps({"token": _item}, ensure_ascii=False)}

                    response = "".join(_stream_chunks)
                    S.debug_write("tool_call_stream_done", {"chunks": len(_stream_chunks), "len": len(response), "tool_used": _tool_used})
                except Exception as _tce:
                    S.debug_write("tool_call_error", {"error": str(_tce)})
                    if not _stream_chunks:
                        # fallback 到非流式 tool_call
                        from core.reply_formatter import unified_reply_with_tools
                        tc_result = unified_reply_with_tools(bundle, tools, execute_tool_call)
                        response = tc_result.get("reply", "")
                        _tool_used = tc_result.get("tool_used")
                        _tool_run_meta = tc_result.get("run_meta") if isinstance(tc_result.get("run_meta"), dict) else {}
                        _plan_update = _extract_task_plan_from_meta(_tool_run_meta)
                        if _plan_update:
                            _task_plan = _plan_update
                            yield {"event": "plan", "data": json.dumps(_plan_update, ensure_ascii=False)}
                        _tool_success = True if _tool_used else None
                        _action_summary = str(tc_result.get("action_summary") or "").strip()
                        _tool_action_summary = _action_summary or _tool_action_summary
                        if _tool_used and _action_summary:
                            yield await _trace("\u6280\u80fd\u5b8c\u6210", " \u00b7 ".join([p for p in [_tool_used, _action_summary] if p]), "done")
                    else:
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
                    from core.state_loader import record_memory_stats
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
                    response = _re.sub(r'<think>.*?</think>', '', response, flags=_re.S | _re.I).strip()
                except Exception:
                    pass
                response = _strip_markdown(response)
                response = _ensure_tool_call_failure_reply(
                    response,
                    tool_used=_tool_used or "",
                    tool_success=_tool_success,
                    tool_response=_tool_response_text,
                    action_summary=_tool_action_summary,
                    run_meta=_tool_run_meta,
                )
                S.debug_write("pre_reply_yield", {"response_len": len(response), "response_preview": response[:100]})
                await asyncio.sleep(0.05)
                yield {"event": "reply", "data": json.dumps({"reply": response}, ensure_ascii=False)}

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
                        from core.state_loader import record_memory_stats
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
            response = _re.sub(r'<think>.*?</think>', '', response, flags=_re.S | _re.I).strip()
        except Exception:
            pass
        response = _strip_markdown(response)
        S.debug_write("pre_reply_yield", {"response_len": len(response), "response_preview": response[:100]})
        await asyncio.sleep(0.05)
        yield {"event": "reply", "data": json.dumps({"reply": response}, ensure_ascii=False)}
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
                from core.state_loader import record_memory_stats
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
        yield {"event": "reply", "data": json.dumps({"reply": f"\u5185\u90e8\u9519\u8bef\uff1a{_fatal}"}, ensure_ascii=False)}
      except BaseException as _base:
        S.debug_write("event_stream_cancelled", {"error": str(_base), "type": type(_base).__name__})
        raise

    return EventSourceResponse(event_stream(), ping=2)
