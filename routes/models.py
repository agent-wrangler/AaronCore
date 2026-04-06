"""LLM model management routes."""

import json

from fastapi import APIRouter

router = APIRouter()


def _provider_catalog() -> dict:
    from routes.chat_model_switch import PROVIDER_CATALOG

    return PROVIDER_CATALOG


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
    else:
        normalized.pop("auth_mode", None)
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


def _looks_like_placeholder(value: str) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return True
    placeholder_tokens = (
        "xxx",
        "your-api-key",
        "your_api_key",
        "your key",
        "please fill",
        "placeholder",
        "example.com",
    )
    return any(token in text for token in placeholder_tokens)


def _validate_api_model_config(cfg: dict) -> str:
    normalized = _normalize_model_config(cfg, fallback_model=str((cfg or {}).get("model") or ""))
    transport = str(normalized.get("transport") or "openai_api").strip().lower()
    if transport != "openai_api":
        return "Only API-backed models are supported in model management."

    base_url = str(normalized.get("base_url") or "").strip().rstrip("/")
    api_key = str(normalized.get("api_key") or "").strip()
    if not base_url or _looks_like_placeholder(base_url):
        return "Please fill in a valid Base URL."
    if not api_key or _looks_like_placeholder(api_key):
        return "Please fill in a valid API Key."
    return ""


def _is_visible_api_model(cfg: dict) -> bool:
    return _validate_api_model_config(cfg) == ""


def _classify_provider(model_id: str, cfg: dict, catalog: dict) -> str | None:
    model_id_l = str(model_id or "").strip().lower()
    model_name_l = str((cfg or {}).get("model") or "").strip().lower()
    base_url_l = str((cfg or {}).get("base_url") or "").strip().lower()

    for provider_key, provider_info in catalog.items():
        catalog_ids = {str(mid).strip().lower() for mid, _desc in provider_info.get("models", [])}
        if model_id_l in catalog_ids or model_name_l in catalog_ids:
            return provider_key
        if provider_key in model_id_l or provider_key in model_name_l:
            return provider_key
        for alias in provider_info.get("aliases", []):
            alias_l = str(alias).strip().lower()
            if alias_l and (alias_l in model_id_l or alias_l in model_name_l):
                return provider_key

    for provider_key, provider_info in catalog.items():
        url_hint = str(provider_info.get("url_hint") or "").strip().lower()
        if url_hint and url_hint in base_url_l:
            return provider_key
    return None


def _build_derived_model_config(model_id: str, donor_id: str, donor_cfg: dict, provider_key: str) -> dict:
    return {
        "model": model_id,
        "vision": bool(donor_cfg.get("vision", False)),
        "transport": "openai_api",
        "base_url": donor_cfg.get("base_url", ""),
        "api_key": donor_cfg.get("api_key", ""),
        "derived": True,
        "source_model": donor_id,
        "provider_key": provider_key,
    }


def _find_provider_donor(models_config: dict, target_model: str) -> tuple[str | None, str | None, dict | None]:
    catalog = _provider_catalog()
    provider_key = _classify_provider(target_model, {"model": target_model}, catalog)
    if not provider_key:
        return None, None, None

    for donor_id, raw_cfg in models_config.items():
        cfg = _normalize_model_config(raw_cfg, fallback_model=donor_id)
        if not _is_visible_api_model(cfg):
            continue
        if _classify_provider(donor_id, cfg, catalog) == provider_key:
            return provider_key, donor_id, cfg
    return provider_key, None, None


def _maybe_derive_model_config(models_config: dict, model_id: str) -> tuple[dict | None, str | None]:
    provider_key, donor_id, donor_cfg = _find_provider_donor(models_config, model_id)
    if not donor_cfg or not donor_id:
        return None, provider_key
    return _build_derived_model_config(model_id, donor_id, donor_cfg, provider_key or ""), provider_key


def _probe_api_model(cfg: dict, *, timeout: int = 8) -> tuple[bool, str]:
    import brain

    normalized = _normalize_model_config(cfg, fallback_model=str((cfg or {}).get("model") or ""))
    validation_error = _validate_api_model_config(normalized)
    if validation_error:
        return False, validation_error

    try:
        result = brain.llm_call(
            normalized,
            [{"role": "user", "content": "Reply with exactly: pong"}],
            max_tokens=8,
            timeout=timeout,
        )
    except Exception as exc:
        return False, f"Unable to reach the model API: {exc}"

    detail = str(result.get("error") or "").strip()
    if detail:
        return False, f"Model API returned an error: {detail}"
    return True, "Connection OK"


def _build_visible_model_summary(brain_module) -> dict:
    catalog = _provider_catalog()
    models = {}
    provider_donors = {}
    existing_catalog_keys = set()

    for model_id, raw_cfg in brain_module.MODELS_CONFIG.items():
        cfg = _normalize_model_config(raw_cfg, fallback_model=model_id)
        if not _is_visible_api_model(cfg):
            continue

        models[model_id] = {
            "model": cfg.get("model", model_id),
            "vision": cfg.get("vision", False),
            "base_url": cfg.get("base_url", ""),
            "transport": cfg.get("transport", "openai_api"),
        }
        existing_catalog_keys.add(str(model_id).strip().lower())
        existing_catalog_keys.add(str(cfg.get("model", model_id)).strip().lower())

        provider_key = _classify_provider(model_id, cfg, catalog)
        if provider_key and provider_key not in provider_donors:
            provider_donors[provider_key] = (model_id, cfg)

    for provider_key, (donor_id, donor_cfg) in provider_donors.items():
        for catalog_model_id, _desc in catalog.get(provider_key, {}).get("models", []):
            catalog_key = str(catalog_model_id).strip().lower()
            if not catalog_key or catalog_key in existing_catalog_keys:
                continue
            models[catalog_model_id] = {
                "model": catalog_model_id,
                "vision": donor_cfg.get("vision", False),
                "base_url": donor_cfg.get("base_url", ""),
                "transport": "openai_api",
                "derived": True,
                "provider_key": provider_key,
                "source_model": donor_id,
            }

    return {"models": models, "current": brain_module._current_default}


@router.get("/models")
async def list_models():
    import brain

    return _build_visible_model_summary(brain)


@router.post("/model/{name}")
async def switch_model(name: str):
    import brain
    from brain import validate_codex_cli_login

    created_derived = False
    if name in brain.MODELS_CONFIG:
        cfg = _normalize_model_config(brain.MODELS_CONFIG[name], fallback_model=name)
    else:
        cfg, provider_key = _maybe_derive_model_config(brain.MODELS_CONFIG, name)
        if not cfg:
            if provider_key:
                return {"ok": False, "error": f"Provider '{provider_key}' is not configured yet."}
            return {"ok": False, "error": f"model '{name}' not found"}
        created_derived = True

    transport = str(cfg.get("transport") or "openai_api").strip().lower()
    if transport == "codex_cli":
        ok, detail = validate_codex_cli_login(timeout=8)
        if not ok:
            return {"ok": False, "error": detail}
    else:
        ok, detail = _probe_api_model(cfg, timeout=8)
        if not ok:
            return {"ok": False, "error": detail}

    brain.MODELS_CONFIG[name] = cfg
    try:
        _save_models_file(brain)
    except Exception:
        pass

    ok = brain.set_default_model(name)
    if ok:
        return {"ok": True, "current": name, "derived": created_derived}
    return {"ok": False, "error": "switch failed"}


@router.post("/models/test")
async def test_model_config(request: dict):
    import brain

    model_id = str(request.get("id") or "").strip()
    config = request.get("config")

    if isinstance(config, dict) and config:
        cfg = _normalize_model_config(config, fallback_model=model_id)
    elif model_id and model_id in brain.MODELS_CONFIG:
        cfg = _normalize_model_config(brain.MODELS_CONFIG[model_id], fallback_model=model_id)
    elif model_id:
        cfg, provider_key = _maybe_derive_model_config(brain.MODELS_CONFIG, model_id)
        if not cfg:
            if provider_key:
                return {"ok": False, "error": f"Provider '{provider_key}' is not configured yet."}
            return {"ok": False, "error": "missing id or config"}
    else:
        return {"ok": False, "error": "missing id or config"}

    ok, detail = _probe_api_model(cfg, timeout=8)
    if ok:
        return {"ok": True, "detail": detail}
    return {"ok": False, "error": detail}


@router.get("/models/config")
async def get_models_config():
    from brain import MODELS_CONFIG, _current_default

    models = {mid: _normalize_model_config(cfg, fallback_model=mid) for mid, cfg in MODELS_CONFIG.items()}
    return {"models": models, "current": _current_default}


@router.get("/models/catalog")
async def get_models_catalog():
    from brain import MODELS_CONFIG, _current_default

    catalog = {}
    for provider_key, provider_info in _provider_catalog().items():
        catalog[provider_key] = {
            "aliases": provider_info["aliases"],
            "url_hint": provider_info["url_hint"],
            "models": [{"id": mid, "desc": desc} for mid, desc in provider_info["models"]],
        }
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
    validation_error = _validate_api_model_config(normalized)
    if validation_error:
        return {"ok": False, "error": validation_error}

    duplicate_id = _find_duplicate_model_id(
        brain.MODELS_CONFIG,
        model_name=normalized.get("model", mid),
        exclude_id=mid,
    )
    if duplicate_id:
        return {
            "ok": False,
            "error": f"model '{normalized.get('model', mid)}' already exists as '{duplicate_id}'. Edit that model instead of creating a duplicate.",
        }

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
        return {"ok": False, "error": "cannot delete the currently active model"}
    if mid not in brain.MODELS_CONFIG:
        return {"ok": False, "error": "model not found"}
    del brain.MODELS_CONFIG[mid]
    try:
        _save_models_file(brain)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True}
