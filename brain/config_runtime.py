"""Model config loading/runtime state for brain."""

from __future__ import annotations

import json
import os


DEFAULT_ASSISTANT_SYSTEM_PROMPT = "你是当前对话助手。"
DEFAULT_CHAT_STYLE_PROMPT = "自然、直接、清楚地回应用户，优先遵守上层给出的事实和任务要求。"


def _load_raw_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "llm_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    parent_config = os.path.join(os.path.dirname(os.path.dirname(__file__)), "brain", "llm_config.json")
    if os.path.exists(parent_config):
        with open(parent_config, "r", encoding="utf-8") as handle:
            return json.load(handle)

    return {
        "api_key": "",
        "model": "MiniMax-M2.7",
        "base_url": "https://api.minimaxi.com/anthropic",
    }


def _normalize_raw_config(raw_config: dict) -> dict:
    if "models" in raw_config:
        return raw_config

    model_name = raw_config.get("model", "deepseek-chat")
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


config_path = os.path.join(os.path.dirname(__file__), "llm_config.json")
raw_config = _normalize_raw_config(_load_raw_config())
models_config = raw_config["models"]
current_default = raw_config.get("default", next(iter(models_config)))
llm_config = models_config.get(current_default) or next(iter(models_config.values()))
