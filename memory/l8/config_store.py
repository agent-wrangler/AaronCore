"""Config persistence helpers for L8."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


DEFAULT_CONFIG = {
    "enabled": True,
    "allow_web_search": True,
    "allow_knowledge_write": True,
    "allow_feedback_relearn": True,
    "allow_self_repair_planning": True,
    "allow_self_repair_test_run": True,
    "allow_self_repair_auto_apply": True,
    "allow_skill_generation": False,
    "mode": "shadow",
    "self_repair_apply_mode": "confirm",
    "self_repair_test_timeout_sec": 45,
    "min_query_length": 4,
    "search_timeout_sec": 8,
    "max_results": 5,
    "max_summary_length": 360,
    "search_engine": "tavily",
    "tavily_api_key": "",
    "brave_api_key": "",
}


def load_autolearn_config(
    *,
    config_file: Path,
    default_config: dict,
    load_json: Callable[[Path, object], object],
    write_json: Callable[[Path, object], None],
    file_lock,
) -> dict:
    with file_lock:
        stored = load_json(config_file, {})
        config = dict(default_config)
        if isinstance(stored, dict):
            for key, value in stored.items():
                if key in config:
                    config[key] = value
        if (not config_file.exists()) or (not isinstance(stored, dict)) or stored != config:
            write_json(config_file, config)
        return config


def save_autolearn_config(
    config: dict,
    *,
    config_file: Path,
    default_config: dict,
    write_json: Callable[[Path, object], None],
    file_lock,
) -> dict:
    merged = dict(default_config)
    if isinstance(config, dict):
        for key, value in config.items():
            if key in merged:
                merged[key] = value
    with file_lock:
        write_json(config_file, merged)
    return merged


def update_autolearn_config(
    patch: dict,
    *,
    load_autolearn_config_fn: Callable[[], dict],
    save_autolearn_config_fn: Callable[[dict], dict],
) -> dict:
    current = load_autolearn_config_fn()
    if isinstance(patch, dict):
        for key, value in patch.items():
            if key in current:
                current[key] = value
    return save_autolearn_config_fn(current)
