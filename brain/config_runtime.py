"""Model config loading/runtime state for brain."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from storage.paths import LLM_CONFIG_FILE, LLM_LOCAL_CONFIG_FILE


DEFAULT_ASSISTANT_SYSTEM_PROMPT = "You are the assistant for the current conversation."
DEFAULT_CHAT_STYLE_PROMPT = (
    "Respond naturally, clearly, and helpfully while staying grounded in the conversation."
)


_DEFAULT_RAW_CONFIG = {
    "api_key": "",
    "model": "MiniMax-M2.7",
    "base_url": "https://api.minimaxi.com/anthropic",
}
_SECRET_MODEL_FIELDS = ("api_key",)


def _read_json_dict(path: Path) -> dict:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _deep_merge(base: dict, override: dict) -> dict:
    merged = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _load_raw_config() -> dict:
    public_config = _read_json_dict(LLM_CONFIG_FILE)
    local_config = _read_json_dict(LLM_LOCAL_CONFIG_FILE)
    base_config = public_config or deepcopy(_DEFAULT_RAW_CONFIG)
    return _deep_merge(base_config, local_config)


def _normalize_raw_config(raw_config: dict) -> dict:
    if isinstance(raw_config, dict) and "models" in raw_config and isinstance(raw_config.get("models"), dict) and raw_config["models"]:
        normalized = deepcopy(raw_config)
        default = str(normalized.get("default") or "").strip()
        if not default or default not in normalized["models"]:
            normalized["default"] = next(iter(normalized["models"]))
        return normalized

    raw_config = raw_config if isinstance(raw_config, dict) else {}
    model_name = str(raw_config.get("model", "deepseek-chat") or "deepseek-chat").strip() or "deepseek-chat"
    return {
        "models": {
            model_name: {
                "api_key": raw_config.get("api_key", ""),
                "base_url": raw_config.get("base_url", ""),
                "model": model_name,
                "vision": False,
            }
        },
        "default": model_name,
    }


def _split_raw_config(raw_config: dict) -> tuple[dict, dict]:
    normalized = _normalize_raw_config(raw_config)
    public_config = deepcopy(normalized)
    local_config: dict = {}

    models = public_config.get("models", {})
    if isinstance(models, dict):
        local_models = {}
        for model_id, cfg in models.items():
            public_entry = dict(cfg or {})
            local_entry = {}
            for field in _SECRET_MODEL_FIELDS:
                value = str(public_entry.get(field) or "")
                if value:
                    local_entry[field] = value
                if field in public_entry:
                    public_entry[field] = ""
            models[model_id] = public_entry
            if local_entry:
                local_models[model_id] = local_entry
        if local_models:
            local_config["models"] = local_models

    return public_config, local_config


def _write_json_dict(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _sync_runtime_state(merged_config: dict) -> None:
    global raw_config, models_config, current_default, llm_config
    raw_config = _normalize_raw_config(merged_config)
    models_config = raw_config["models"]
    current_default = raw_config.get("default", next(iter(models_config)))
    llm_config = models_config.get(current_default) or next(iter(models_config.values()))


def save_raw_config(raw_config_to_save: dict | None = None) -> dict:
    merged_config = _normalize_raw_config(raw_config_to_save or raw_config)
    public_config, local_config = _split_raw_config(merged_config)
    _write_json_dict(LLM_CONFIG_FILE, public_config)
    if local_config:
        _write_json_dict(LLM_LOCAL_CONFIG_FILE, local_config)
    elif LLM_LOCAL_CONFIG_FILE.exists():
        try:
            LLM_LOCAL_CONFIG_FILE.unlink()
        except Exception:
            pass
    _sync_runtime_state(merged_config)
    return deepcopy(raw_config)


def get_current_llm_config() -> dict:
    return deepcopy(llm_config)


config_path = str(LLM_CONFIG_FILE)
local_config_path = str(LLM_LOCAL_CONFIG_FILE)
_sync_runtime_state(_load_raw_config())
