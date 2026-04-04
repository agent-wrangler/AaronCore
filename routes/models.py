"""LLM model management routes."""

import json

from fastapi import APIRouter

router = APIRouter()


def _normalize_model_config(cfg: dict, *, fallback_model: str = "") -> dict:
    normalized = dict(cfg or {})
    transport = str(normalized.get("transport") or "").strip().lower()
    if not transport:
        base_url = str(normalized.get("base_url") or "").strip().lower()
        transport = "codex_cli" if base_url.startswith("codex://") else "openai_api"
    normalized["transport"] = transport

    model_name = str(normalized.get("model") or fallback_model or "").strip()
    if model_name:
        normalized["model"] = model_name
    normalized["vision"] = bool(normalized.get("vision", False))

    if transport == "codex_cli":
        normalized["auth_mode"] = "codex_cli"
        normalized.pop("api_key", None)
        normalized["base_url"] = "codex://local"
    return normalized


def _save_models_file(brain_module) -> None:
    brain_module._raw_config["models"] = brain_module.MODELS_CONFIG
    with open(brain_module.config_path, "w", encoding="utf-8") as handle:
        json.dump(brain_module._raw_config, handle, ensure_ascii=False, indent=2)


def _find_duplicate_model_id(models_config: dict, *, model_name: str, exclude_id: str = "") -> str:
    target = str(model_name or "").strip().lower()
    if not target:
        return ""

    exclude = str(exclude_id or "").strip()
    for model_id, cfg in models_config.items():
        if exclude and model_id == exclude:
            continue
        existing_name = str((cfg or {}).get("model") or model_id or "").strip().lower()
        if existing_name == target:
            return model_id
    return ""


@router.get("/models")
async def list_models():
    from brain import get_models

    return get_models()


@router.post("/model/{name}")
async def switch_model(name: str):
    import brain
    from brain import llm_call, validate_codex_cli_login

    if name not in brain.MODELS_CONFIG:
        return {"ok": False, "error": f"model '{name}' not found"}

    cfg = _normalize_model_config(brain.MODELS_CONFIG[name], fallback_model=name)
    transport = str(cfg.get("transport") or "openai_api").strip().lower()
    base_url = str(cfg.get("base_url", "")).strip().rstrip("/")
    api_key = str(cfg.get("api_key", "")).strip()

    if transport == "codex_cli":
        ok, detail = validate_codex_cli_login(timeout=8)
        if not ok:
            return {"ok": False, "error": detail}
    else:
        if not base_url or not api_key or "xxx" in base_url or "xxx" in api_key:
            return {
                "ok": False,
                "error": "该模型的 API 配置不完整，请先编辑填写 base_url 和 api_key",
            }
        try:
            result = llm_call(cfg, [{"role": "user", "content": "hi"}], max_tokens=5, timeout=8)
            if result.get("error"):
                detail = result["error"]
                msg = "API 返回错误"
                if detail:
                    msg += f"：{detail}"
                return {"ok": False, "error": msg}
        except Exception:
            return {"ok": False, "error": "无法连接到该模型的 API，请检查 base_url 和网络"}

    brain.MODELS_CONFIG[name] = cfg
    try:
        _save_models_file(brain)
    except Exception:
        pass

    ok = brain.set_default_model(name)
    if ok:
        return {"ok": True, "current": name}
    return {"ok": False, "error": "switch failed"}


@router.get("/models/config")
async def get_models_config():
    from brain import MODELS_CONFIG, _current_default

    models = {mid: _normalize_model_config(cfg, fallback_model=mid) for mid, cfg in MODELS_CONFIG.items()}
    return {"models": models, "current": _current_default}


@router.get("/models/catalog")
async def get_models_catalog():
    from brain import MODELS_CONFIG, _current_default, validate_codex_cli_login
    from routes.chat import _PROVIDER_CATALOG

    codex_ready, _ = validate_codex_cli_login(timeout=5)
    catalog = {}
    for pkey, pinfo in _PROVIDER_CATALOG.items():
        catalog[pkey] = {
            "aliases": pinfo["aliases"],
            "url_hint": pinfo["url_hint"],
            "models": [{"id": mid, "desc": desc} for mid, desc in pinfo["models"]],
        }
        if pkey == "openai":
            catalog[pkey]["subscription_ready"] = bool(codex_ready)
    models = {mid: _normalize_model_config(cfg, fallback_model=mid) for mid, cfg in MODELS_CONFIG.items()}
    return {"catalog": catalog, "models": models, "current": _current_default}


@router.post("/models/config")
async def save_model_config(request: dict):
    import brain

    mid = str(request.get("id", "")).strip()
    cfg = request.get("config", {})
    if not mid or not isinstance(cfg, dict):
        return {"ok": False, "error": "missing id or config"}

    normalized = _normalize_model_config(cfg, fallback_model=mid)
    duplicate_id = _find_duplicate_model_id(
        brain.MODELS_CONFIG,
        model_name=normalized.get("model", mid),
        exclude_id=mid,
    )
    if duplicate_id:
        return {
            "ok": False,
            "error": f"model '{normalized.get('model', mid)}' already exists as '{duplicate_id}'. Edit that model to switch its connection instead of creating a duplicate.",
        }
    if normalized.get("transport") != "codex_cli":
        if not str(normalized.get("base_url") or "").strip():
            return {"ok": False, "error": "missing base_url"}
        if not str(normalized.get("api_key") or "").strip():
            return {"ok": False, "error": "missing api_key"}

    brain.MODELS_CONFIG[mid] = normalized
    try:
        _save_models_file(brain)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    if len(brain.MODELS_CONFIG) == 1:
        brain.set_default_model(mid)
    return {"ok": True}


@router.delete("/models/config")
async def delete_model_config(request: dict):
    import brain

    mid = str(request.get("id", "")).strip()
    if not mid:
        return {"ok": False, "error": "missing id"}
    if mid == brain._current_default:
        return {"ok": False, "error": "不能删除当前使用中的模型"}
    if mid not in brain.MODELS_CONFIG:
        return {"ok": False, "error": "model not found"}
    del brain.MODELS_CONFIG[mid]
    try:
        _save_models_file(brain)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True}
