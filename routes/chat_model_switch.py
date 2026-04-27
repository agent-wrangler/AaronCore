import json
import re

from core import model_provider_config as _provider_config


MODEL_SWITCH_RE = re.compile(
    r"(?:(?:^|\b)(?:switch(?:\s+to)?|use)\s+|\u5207\u6362(?:\u5230|\u6210)?\s*|\u6362\u6210\s*|\u6539\u6210\s*|\u7528\s*|^)"
    r"([A-Za-z0-9][\w\-.]*(?:[\-.]\w+)*)",
    re.IGNORECASE,
)


PROVIDER_CATALOG = {
    "deepseek": {
        "aliases": ["deepseek", "ds"],
        "url_hint": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "models": [
            ("deepseek-chat", "General chat, fast and cheap"),
            ("deepseek-reasoner", "Deeper reasoning"),
        ],
    },
    "openai": {
        "aliases": ["openai", "gpt", "chatgpt"],
        "url_hint": "openai",
        "base_url": "https://api.openai.com/v1",
        "models": [
            ("gpt-5.4", "Latest flagship for coding and reasoning"),
            ("gpt-5.4-mini", "Faster lower-cost flagship"),
            ("gpt-5.4-nano", "Cheapest lightweight option"),
            ("gpt-4o", "Multimodal flagship"),
            ("gpt-4o-mini", "Fast lightweight multimodal"),
            ("gpt-4.1", "Stable general-purpose model"),
            ("gpt-4.1-mini", "Smaller 4.1 variant"),
            ("gpt-4.1-nano", "Tiny low-cost 4.1"),
        ],
    },
    "claude": {
        "aliases": ["claude", "anthropic"],
        "url_hint": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "models": [
            ("claude-opus-4-6", "Strongest Claude model"),
            ("claude-sonnet-4-6", "Balanced main Claude model"),
            ("claude-haiku-4-5-20251001", "Fast lower-cost Claude model"),
        ],
    },
    "qwen": {
        "aliases": ["qwen", "\u901a\u4e49\u5343\u95ee", "\u5343\u95ee"],
        "url_hint": "dashscope",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": [
            ("qwen-plus", "Balanced main model"),
            ("qwen-turbo", "Fast lower-cost model"),
            ("qwen-max", "Stronger flagship"),
        ],
    },
    "minimax": {
        "aliases": ["minimax", "mm", "hailuo", "\u6d77\u87ba"],
        "url_hint": "minimax",
        "base_url": "https://api.minimaxi.com/v1",
        "models": [
            ("MiniMax-M2.7", "Latest main model"),
            ("MiniMax-M2.7-highspeed", "Fast M2.7"),
            ("MiniMax-M2.5", "Balanced M2.5"),
            ("MiniMax-M2.5-highspeed", "Fast M2.5"),
            ("MiniMax-M2.1", "Classic M2.1"),
            ("MiniMax-M2.1-highspeed", "Fast M2.1"),
            ("MiniMax-M2", "Base M2"),
        ],
    },
    "doubao": {
        "aliases": ["doubao", "\u8c46\u5305"],
        "url_hint": "volcengine",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "models": [
            ("doubao-1.5-pro-32k", "Main Doubao model"),
            ("doubao-1.5-lite-32k", "Lighter Doubao model"),
        ],
    },
    "glm": {
        "aliases": ["glm", "zhipu", "\u667a\u8c31", "chatglm"],
        "url_hint": "zhipuai",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": [
            ("glm-4-plus", "GLM flagship"),
            ("glm-4-flash", "GLM flash"),
        ],
    },
}


def _user_model_name(model_id: str, cfg: dict | None) -> str:
    config = cfg if isinstance(cfg, dict) else {}
    return str(config.get("display_name") or config.get("model") or model_id).strip() or str(model_id)


def _persist_models_config(brain_module) -> None:
    brain_module._raw_config["models"] = brain_module.MODELS_CONFIG
    saver = getattr(brain_module, "save_raw_config", None)
    if not callable(saver):
        raise RuntimeError("save_raw_config is required for redacted model config persistence.")
    saver(brain_module._raw_config)


def match_provider(target: str, models_config: dict) -> tuple[str | None, dict | None]:
    target_l = target.lower()
    target_prefix = target_l.split("-")[0].lower()

    for provider_key, provider_info in PROVIDER_CATALOG.items():
        aliases = [provider_key] + [str(alias).lower() for alias in provider_info["aliases"]]
        if target_l in aliases or target_prefix in aliases:
            for model_id, cfg in models_config.items():
                explicit_provider_key = _provider_config.infer_provider_key(model_id, cfg)
                if explicit_provider_key == provider_key:
                    return provider_key, cfg
                base_url_provider = _provider_config.provider_key_from_base_url((cfg or {}).get("base_url") or "")
                model_id_l = str(model_id or "").lower()
                if base_url_provider == provider_key or provider_key in model_id_l:
                    return provider_key, cfg
            return provider_key, None

    for model_id, cfg in models_config.items():
        explicit_provider_key = _provider_config.infer_provider_key(model_id, cfg)
        model_id_l = str(model_id or "").split("-")[0].lower()
        model_l = str((cfg or {}).get("model") or "").split("-")[0].lower()
        base_url = str((cfg or {}).get("base_url") or "").lower()
        base_url_provider = _provider_config.provider_key_from_base_url(base_url)
        if target_prefix == model_id_l or target_prefix == model_l or target_l in base_url:
            if explicit_provider_key:
                return explicit_provider_key, cfg
            if base_url_provider:
                return base_url_provider, cfg
            for provider_key in PROVIDER_CATALOG:
                if provider_key in model_id_l:
                    return provider_key, cfg
            return None, cfg
    return None, None


def is_vague_provider_name(target: str) -> bool:
    if "-" in target or "." in target:
        return False
    target_l = target.lower()
    for provider_key, provider_info in PROVIDER_CATALOG.items():
        aliases = [provider_key] + [str(alias).lower() for alias in provider_info["aliases"]]
        if target_l in aliases:
            return True
    return False


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
        model_id_l = str(model_id or "").lower()
        model_name = _user_model_name(model_id, cfg)
        explicit_provider_key = _provider_config.infer_provider_key(model_id, cfg)
        if provider_key:
            base_url = str((cfg or {}).get("base_url") or "").lower()
            base_url_provider = _provider_config.provider_key_from_base_url(base_url)
            if explicit_provider_key == provider_key or provider_key in model_id_l or base_url_provider == provider_key:
                tag = " [current]" if model_id == current_default else ""
                existing.append(f"  {model_name}{tag}")
        elif target.lower() in model_id_l:
            tag = " [current]" if model_id == current_default else ""
            existing.append(f"  {model_name}{tag}")

    if existing:
        lines.append("Configured:")
        lines.extend(existing)

    if provider_key and provider_key in PROVIDER_CATALOG:
        catalog_models = PROVIDER_CATALOG[provider_key]["models"]
        existing_names = {str((cfg or {}).get("model") or model_id).lower() for model_id, cfg in models_config.items()}
        suggestions = []
        for model_id, desc in catalog_models:
            if model_id.lower() not in existing_names:
                suggestions.append(f"  {model_id} ({desc})")
        if suggestions:
            if existing:
                lines.append("")
            lines.append("Also available:" if donor_cfg else "Common options:")
            lines.extend(suggestions)

    if not lines:
        return ""

    header = f"{target.upper()} models:\n"
    footer = "\n\nSay \"switch xxx\" or \"\u5207\u6362\u5230 xxx\" directly."
    if donor_cfg:
        footer += " Same-provider models will reuse the existing API config."
    else:
        footer += " This provider is not configured yet, so add one in Settings first."
    return header + "\n".join(lines) + footer


def is_placeholder_key(api_key: str) -> bool:
    if not api_key:
        return True
    key = str(api_key).strip()
    key_l = key.lower()
    if len(key) < 10:
        return True
    if "xxx" in key_l or "sk-xxx" in key_l:
        return True
    if "your-api-key" in key_l or "your_api_key" in key_l or "please fill" in key_l:
        return True
    if any("\u4e00" <= char <= "\u9fff" for char in key):
        return True
    if key.startswith(("\u4f60\u7684", "\u586b\u5199", "\u8bf7\u586b")):
        return True
    return False


def check_model_ready(model_id: str, cfg: dict) -> str | None:
    transport = _provider_config.normalize_transport(
        (cfg or {}).get("transport"),
        base_url=str((cfg or {}).get("base_url", "") or ""),
    )
    auth_mode = _provider_config.normalize_auth_mode((cfg or {}).get("auth_mode"), transport=transport)
    if transport == "codex_cli" or auth_mode == "codex_cli":
        try:
            import brain

            validate_login = getattr(brain, "validate_codex_cli_login", None)
            if callable(validate_login):
                ok, detail = validate_login(timeout=8)
                if not ok:
                    return detail or f"{model_id} is unavailable. Please confirm local Codex is logged in."
        except Exception:
            pass
        return None

    api_key = str((cfg or {}).get("api_key") or "").strip()
    base_url = str((cfg or {}).get("base_url") or "").strip()
    if not base_url:
        return f"{model_id} is missing Base URL. Run `aaron setup`, or use `/setup` inside chat."
    if is_placeholder_key(api_key):
        return f"{model_id} is missing API Key. Run `aaron setup`, or use `/setup` inside chat."
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
    if after and after[0] in "\u505a\u5199\u753b\u641c\u67e5\u627e\u5e2e\u6765\u804a\u8bf4\u8bb2\u770b":
        return None

    import brain

    models = brain.MODELS_CONFIG
    if target_l in {key.lower() for key in models}:
        model_id = next(key for key in models if key.lower() == target_l)
        if model_id == brain._current_default:
            return {
                "reply": f"Already using {_user_model_name(model_id, models[model_id])}.",
                "trace": f"current already {model_id}",
            }
        err = check_model_ready(model_id, models[model_id])
        if err:
            return {"reply": err, "trace": f"{model_id} config incomplete"}
        ok = brain.set_default_model(model_id)
        if ok:
            name = brain.get_current_model_name()
            return {
                "reply": f"Switched to {name}.",
                "trace": f"switched to {name}",
                "model_changed": True,
            }
        return {"reply": "Switch failed. Try again.", "trace": "switch failed"}

    if not is_vague_provider_name(target_l):
        for model_id, cfg in models.items():
            model_name = str((cfg or {}).get("model") or model_id).lower()
            display_name = str((cfg or {}).get("display_name") or "").lower()
            if (
                target_l in model_id.lower()
                or target_l in model_name
                or target_l == model_name
                or (display_name and (target_l in display_name or target_l == display_name))
            ):
                if model_id == brain._current_default:
                    return {
                        "reply": f"Already using {_user_model_name(model_id, cfg)}.",
                        "trace": f"current already {model_id}",
                    }
                err = check_model_ready(model_id, cfg)
                if err:
                    return {"reply": err, "trace": f"{model_id} config incomplete"}
                ok = brain.set_default_model(model_id)
                if ok:
                    name = brain.get_current_model_name()
                    return {
                        "reply": f"Switched to {name}.",
                        "trace": f"switched to {name}",
                        "model_changed": True,
                    }

    provider_key, donor_cfg = match_provider(target_l, models)
    if provider_key or donor_cfg:
        if is_vague_provider_name(target_l):
            reply = build_model_list_reply(target, provider_key, donor_cfg, models, brain._current_default)
            if reply:
                return {"reply": reply, "trace": f"list models for {target}"}
        elif donor_cfg and "-" in target:
            err = check_model_ready("donor", donor_cfg)
            if err:
                return {
                    "reply": "The donor API config is incomplete. Finish it in Settings first.",
                    "trace": "donor config incomplete",
                }
            new_cfg = {
                "api_key": donor_cfg["api_key"],
                "base_url": donor_cfg["base_url"],
                "model": target,
                "vision": donor_cfg.get("vision", False),
                "provider_key": donor_cfg.get("provider_key", provider_key or ""),
                "provider": donor_cfg.get("provider", ""),
                "transport": donor_cfg.get("transport", "openai_api"),
                "auth_mode": donor_cfg.get("auth_mode", "api_key"),
                "api_mode": donor_cfg.get("api_mode", "chat_completions"),
            }
            brain.MODELS_CONFIG[target] = new_cfg
            try:
                _persist_models_config(brain)
            except Exception as exc:
                brain.MODELS_CONFIG.pop(target, None)
                brain._raw_config["models"] = brain.MODELS_CONFIG
                return {
                    "reply": "Unable to save the derived model securely. Please try again from Settings.",
                    "trace": f"persist failed: {exc}",
                }
            ok = brain.set_default_model(target)
            if ok:
                return {
                    "reply": f"Created and switched to {target} using the same provider config.",
                    "trace": f"created and switched to {target}",
                    "model_changed": True,
                }

    return None
