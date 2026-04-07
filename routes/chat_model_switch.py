import json
import re


MODEL_SWITCH_RE = re.compile(
    r'(?:换成?|切换?到?|改[成用]|用)\s*'
    r'([a-zA-Z0-9][\w\-\.]*(?:[\-\.]\w+)*)',
    re.IGNORECASE,
)


PROVIDER_CATALOG = {
    "deepseek": {
        "aliases": ["deepseek", "ds"],
        "url_hint": "deepseek",
        "models": [
            ("deepseek-chat", "V3 日常对话，快且便宜"),
            ("deepseek-reasoner", "R1 深度推理，慢但智商高"),
        ],
    },
    "openai": {
        "aliases": ["openai", "gpt", "chatgpt"],
        "url_hint": "openai",
        "models": [
            ("gpt-5.4", "最新主力，复杂推理 / 编码"),
            ("gpt-5.4-mini", "高性价比主力，速度更快"),
            ("gpt-5.4-nano", "最便宜，适合轻任务"),
            ("gpt-4o", "多模态旗舰，支持图片"),
            ("gpt-4o-mini", "轻量快速，性价比高"),
            ("gpt-4.1", "最新主力模型"),
            ("gpt-4.1-mini", "轻量版 4.1"),
            ("gpt-4.1-nano", "极速版，最便宜"),
        ],
    },
    "claude": {
        "aliases": ["claude", "anthropic"],
        "url_hint": "anthropic",
        "models": [
            ("claude-sonnet-4-20250514", "Sonnet 4 均衡型"),
            ("claude-3-5-haiku-20241022", "Haiku 3.5 极速"),
        ],
    },
    "qwen": {
        "aliases": ["qwen", "通义千问", "千问"],
        "url_hint": "dashscope",
        "models": [
            ("qwen-plus", "主力模型，性价比高"),
            ("qwen-turbo", "极速版，最便宜"),
            ("qwen-max", "旗舰版，最强"),
        ],
    },
    "minimax": {
        "aliases": ["minimax", "mm", "hailuo", "海螺"],
        "url_hint": "minimax",
        "models": [
            ("MiniMax-M2.7", "M2.7 最新主力"),
            ("MiniMax-M2.7-highspeed", "M2.7 极速版"),
            ("MiniMax-M2.5", "M2.5 均衡型"),
            ("MiniMax-M2.5-highspeed", "M2.5 极速版"),
            ("MiniMax-M2.1", "M2.1 经典版"),
            ("MiniMax-M2.1-highspeed", "M2.1 极速版"),
            ("MiniMax-M2", "M2 基础版"),
        ],
    },
    "doubao": {
        "aliases": ["doubao", "豆包"],
        "url_hint": "volcengine",
        "models": [
            ("doubao-1.5-pro-32k", "1.5 Pro 主力"),
            ("doubao-1.5-lite-32k", "1.5 Lite 轻量"),
        ],
    },
    "glm": {
        "aliases": ["glm", "zhipu", "智谱", "chatglm"],
        "url_hint": "zhipuai",
        "models": [
            ("glm-4-plus", "GLM-4 Plus 旗舰"),
            ("glm-4-flash", "GLM-4 Flash 免费"),
        ],
    },
}


def match_provider(target: str, models_config: dict) -> tuple[str | None, dict | None]:
    target_l = target.lower()
    target_prefix = target_l.split("-")[0].lower()
    for provider_key, provider_info in PROVIDER_CATALOG.items():
        if target_l in provider_info["aliases"] or target_prefix in provider_info["aliases"]:
            for model_id, cfg in models_config.items():
                base_url = str(cfg.get("base_url", "")).lower()
                model_id_l = model_id.lower()
                if provider_info["url_hint"] in base_url or provider_key in model_id_l:
                    return provider_key, cfg
            return provider_key, None

    for model_id, cfg in models_config.items():
        model_id_l = model_id.split("-")[0].lower()
        model_l = str(cfg.get("model", "")).split("-")[0].lower()
        base_url = str(cfg.get("base_url", "")).lower()
        if target_prefix == model_id_l or target_prefix == model_l or target_l in base_url:
            for provider_key, provider_info in PROVIDER_CATALOG.items():
                if provider_info["url_hint"] in base_url or provider_key in model_id_l:
                    return provider_key, cfg
            return None, cfg
    return None, None


def is_vague_provider_name(target: str) -> bool:
    if "-" in target or "." in target:
        return False
    target_l = target.lower()
    return any(target_l in provider_info["aliases"] for provider_info in PROVIDER_CATALOG.values())


def build_model_list_reply(
    target: str,
    provider_key: str | None,
    donor_cfg: dict | None,
    models_config: dict,
    current_default: str,
) -> str:
    lines = []
    existing = []
    for model_id, cfg in models_config.items():
        model_id_l = model_id.lower()
        model_name = str(cfg.get("model", model_id))
        if provider_key:
            provider_info = PROVIDER_CATALOG.get(provider_key, {})
            url_hint = provider_info.get("url_hint", provider_key)
            base_url = str(cfg.get("base_url", "")).lower()
            if provider_key in model_id_l or url_hint in base_url:
                tag = " ← 当前" if model_id == current_default else ""
                existing.append(f"  {model_name}{tag}")
        elif target.lower() in model_id_l:
            tag = " ← 当前" if model_id == current_default else ""
            existing.append(f"  {model_name}{tag}")

    if existing:
        lines.append("已配置的：")
        lines.extend(existing)

    if provider_key and provider_key in PROVIDER_CATALOG:
        catalog_models = PROVIDER_CATALOG[provider_key]["models"]
        existing_names = {str(cfg.get("model", model_id)).lower() for model_id, cfg in models_config.items()}
        suggestions = []
        for model_id, desc in catalog_models:
            if model_id.lower() not in existing_names:
                suggestions.append(f"  {model_id}（{desc}）")
        if suggestions:
            if existing:
                lines.append("")
            lines.append("还可以用：" if donor_cfg else "常见模型：")
            lines.extend(suggestions)

    if not lines:
        return ""

    header = f"{target.upper()} 有这些模型：\n"
    footer = "\n\n直接说“换成 xxx”就行，"
    if donor_cfg:
        footer += "同厂商的我会自动复用 API 配置。"
    else:
        footer += "不过这个厂商还没配置 API，需要先在设置里添加一个。"
    return header + "\n".join(lines) + footer


def is_placeholder_key(api_key: str) -> bool:
    if not api_key:
        return True
    key = str(api_key).strip()
    if len(key) < 10:
        return True
    if "xxx" in key.lower() or "sk-xxx" in key.lower():
        return True
    if any("\u4e00" <= char <= "\u9fff" for char in key):
        return True
    if key.startswith(("你的", "填写", "请填")):
        return True
    return False


def check_model_ready(model_id: str, cfg: dict) -> str | None:
    api_key = str(cfg.get("api_key", "")).strip()
    base_url = str(cfg.get("base_url", "")).strip()
    if not base_url:
        return f"{model_id} 还没配置 base_url，去设置页填一下再切。"
    if is_placeholder_key(api_key):
        return f"{model_id} 的 API key 还没填，去设置页填一下再切。"
    return None


def detect_model_switch(text: str) -> dict | None:
    text = str(text or "").strip()
    if len(text) > 60 or len(text) < 3:
        return None
    match = MODEL_SWITCH_RE.search(text)
    if not match:
        return None

    target = match.group(1).strip()
    target_l = target.lower()
    after = text[match.end():].strip()
    if after and after[0] in "做写画搜查找帮来聊说讲看":
        return None

    import brain

    models = brain.MODELS_CONFIG
    if target_l in {key.lower() for key in models}:
        model_id = next(key for key in models if key.lower() == target_l)
        if model_id == brain._current_default:
            return {
                "reply": f"已经在用 {models[model_id].get('model', model_id)} 了呀～",
                "trace": f"当前已是 {model_id}",
            }
        err = check_model_ready(model_id, models[model_id])
        if err:
            return {"reply": err, "trace": f"{model_id} 配置不完整"}
        ok = brain.set_default_model(model_id)
        if ok:
            name = brain.get_current_model_name()
            return {
                "reply": f"好的，已经切到 {name} 了，接下来用这个模型跟你聊。",
                "trace": f"已切换到 {name}",
                "model_changed": True,
            }
        return {"reply": "切换失败了，你再试一次。", "trace": "切换失败"}

    if not is_vague_provider_name(target_l):
        for model_id, cfg in models.items():
            model_name = str(cfg.get("model", model_id)).lower()
            if target_l in model_id.lower() or target_l in model_name or target_l == model_name:
                if model_id == brain._current_default:
                    return {
                        "reply": f"已经在用 {cfg.get('model', model_id)} 了呀～",
                        "trace": f"当前已是 {model_id}",
                    }
                err = check_model_ready(model_id, cfg)
                if err:
                    return {"reply": err, "trace": f"{model_id} 配置不完整"}
                ok = brain.set_default_model(model_id)
                if ok:
                    name = brain.get_current_model_name()
                    return {
                        "reply": f"好的，已经切到 {name} 了，接下来用这个模型跟你聊。",
                        "trace": f"已切换到 {name}",
                        "model_changed": True,
                    }

    provider_key, donor_cfg = match_provider(target_l, models)
    if provider_key or donor_cfg:
        if is_vague_provider_name(target_l):
            reply = build_model_list_reply(target, provider_key, donor_cfg, models, brain._current_default)
            if reply:
                return {"reply": reply, "trace": f"列出 {target} 可用模型"}
        elif donor_cfg and "-" in target:
            err = check_model_ready("donor", donor_cfg)
            if err:
                return {
                    "reply": "同厂商的 API 配置不完整，去设置页填好 key 再切。",
                    "trace": "同厂商配置不完整",
                }
            new_cfg = {
                "api_key": donor_cfg["api_key"],
                "base_url": donor_cfg["base_url"],
                "model": target,
                "vision": donor_cfg.get("vision", False),
            }
            brain.MODELS_CONFIG[target] = new_cfg
            brain._raw_config["models"] = brain.MODELS_CONFIG
            try:
                with open(brain.config_path, "w", encoding="utf-8") as handle:
                    json.dump(brain._raw_config, handle, ensure_ascii=False, indent=2)
            except Exception:
                pass
            ok = brain.set_default_model(target)
            if ok:
                return {
                    "reply": f"好的，已自动添加并切换到 {target}，复用了同厂商的 API 配置。",
                    "trace": f"自动创建 + 切换到 {target}",
                    "model_changed": True,
                }

    return None
