"""LLM 模型管理路由"""
import json
import requests as _requests
from fastapi import APIRouter

router = APIRouter()


@router.get("/models")
async def list_models():
    from brain import get_models
    return get_models()


@router.post("/model/{name}")
async def switch_model(name: str):
    from brain import MODELS_CONFIG, set_default_model
    if name not in MODELS_CONFIG:
        return {"ok": False, "error": f"model '{name}' not found"}

    # 切换前验证 API 连通性
    cfg = MODELS_CONFIG[name]
    base_url = str(cfg.get("base_url", "")).strip().rstrip("/")
    api_key = str(cfg.get("api_key", "")).strip()
    model_name = str(cfg.get("model", name)).strip()

    if not base_url or not api_key or "xxx" in base_url or "xxx" in api_key:
        return {"ok": False, "error": "\u8be5\u6a21\u578b\u7684 API \u914d\u7f6e\u4e0d\u5b8c\u6574\uff0c\u8bf7\u5148\u7f16\u8f91\u586b\u5199 base_url \u548c api_key"}

    try:
        from brain import llm_call
        result = llm_call(cfg, [{"role": "user", "content": "hi"}],
                          max_tokens=5, timeout=8)
        if result.get("error"):
            detail = result["error"]
            msg = f"API \u8fd4\u56de\u9519\u8bef"
            if detail:
                msg += f"\uff1a{detail}"
            return {"ok": False, "error": msg}
    except Exception:
        return {"ok": False, "error": "\u65e0\u6cd5\u8fde\u63a5\u5230\u8be5\u6a21\u578b\u7684 API\uff0c\u8bf7\u68c0\u67e5 base_url \u548c\u7f51\u7edc"}

    ok = set_default_model(name)
    if ok:
        return {"ok": True, "current": name}
    return {"ok": False, "error": "switch failed"}


@router.get("/models/config")
async def get_models_config():
    from brain import MODELS_CONFIG, _current_default
    return {"models": MODELS_CONFIG, "current": _current_default}


@router.get("/models/catalog")
async def get_models_catalog():
    from brain import MODELS_CONFIG, _current_default
    from routes.chat import _PROVIDER_CATALOG
    catalog = {}
    for pkey, pinfo in _PROVIDER_CATALOG.items():
        catalog[pkey] = {
            "aliases": pinfo["aliases"],
            "url_hint": pinfo["url_hint"],
            "models": [{"id": mid, "desc": desc} for mid, desc in pinfo["models"]],
        }
    return {"catalog": catalog, "models": MODELS_CONFIG, "current": _current_default}


@router.post("/models/config")
async def save_model_config(request: dict):
    import brain
    mid = str(request.get("id", "")).strip()
    cfg = request.get("config", {})
    if not mid or not isinstance(cfg, dict):
        return {"ok": False, "error": "missing id or config"}
    brain.MODELS_CONFIG[mid] = cfg
    brain._raw_config["models"] = brain.MODELS_CONFIG
    try:
        json.dump(brain._raw_config, open(brain.config_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    except Exception as e:
        return {"ok": False, "error": str(e)}
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
        return {"ok": False, "error": "\u4e0d\u80fd\u5220\u9664\u5f53\u524d\u4f7f\u7528\u4e2d\u7684\u6a21\u578b"}
    if mid not in brain.MODELS_CONFIG:
        return {"ok": False, "error": "model not found"}
    del brain.MODELS_CONFIG[mid]
    brain._raw_config["models"] = brain.MODELS_CONFIG
    try:
        json.dump(brain._raw_config, open(brain.config_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True}
