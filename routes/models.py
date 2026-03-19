"""LLM 模型管理路由"""
import json
from fastapi import APIRouter

router = APIRouter()


@router.get("/models")
async def list_models():
    from brain import get_models
    return get_models()


@router.post("/model/{name}")
async def switch_model(name: str):
    from brain import set_default_model
    ok = set_default_model(name)
    if ok:
        return {"ok": True, "current": name}
    return {"ok": False, "error": f"model '{name}' not found"}


@router.get("/models/config")
async def get_models_config():
    from brain import MODELS_CONFIG, _current_default
    return {"models": MODELS_CONFIG, "current": _current_default}


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
