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


def _load_config_dict(config_file: Path | None, load_json: Callable[[Path, object], object]) -> dict:
    if config_file is None:
        return {}
    data = load_json(config_file, {})
    return data if isinstance(data, dict) else {}


def _split_secret_config(config: dict, *, default_config: dict, secret_keys: tuple[str, ...]) -> tuple[dict, dict]:
    public_config = dict(config)
    secret_config = {}
    for key in secret_keys:
        if key not in public_config:
            continue
        value = public_config.get(key, default_config.get(key, ""))
        if value not in ("", None):
            secret_config[key] = value
        public_config[key] = default_config.get(key, "")
    return public_config, secret_config


def load_autolearn_config(
    *,
    config_file: Path,
    secret_config_file: Path | None,
    secret_keys: tuple[str, ...],
    default_config: dict,
    load_json: Callable[[Path, object], object],
    write_json: Callable[[Path, object], None],
    file_lock,
) -> dict:
    with file_lock:
        stored = _load_config_dict(config_file, load_json)
        secret_stored = _load_config_dict(secret_config_file, load_json)
        config = dict(default_config)
        for key, value in stored.items():
            if key in config:
                config[key] = value
        for key, value in secret_stored.items():
            if key in config:
                config[key] = value
        public_config, secret_config = _split_secret_config(
            config,
            default_config=default_config,
            secret_keys=secret_keys,
        )
        if (not config_file.exists()) or stored != public_config:
            write_json(config_file, public_config)
        if secret_config_file is not None:
            if secret_config:
                if secret_stored != secret_config:
                    write_json(secret_config_file, secret_config)
            elif secret_config_file.exists():
                try:
                    secret_config_file.unlink()
                except Exception:
                    pass
        return config


def save_autolearn_config(
    config: dict,
    *,
    config_file: Path,
    secret_config_file: Path | None,
    secret_keys: tuple[str, ...],
    default_config: dict,
    write_json: Callable[[Path, object], None],
    file_lock,
) -> dict:
    merged = dict(default_config)
    if isinstance(config, dict):
        for key, value in config.items():
            if key in merged:
                merged[key] = value
    public_config, secret_config = _split_secret_config(
        merged,
        default_config=default_config,
        secret_keys=secret_keys,
    )
    with file_lock:
        write_json(config_file, public_config)
        if secret_config_file is not None:
            if secret_config:
                write_json(secret_config_file, secret_config)
            elif secret_config_file.exists():
                try:
                    secret_config_file.unlink()
                except Exception:
                    pass
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
