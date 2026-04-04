"""Storage helpers for L2 memory state."""

from __future__ import annotations

from pathlib import Path

from storage.json_store import load_json, write_json


DEFAULT_CONFIG = {
    "total_rounds": 0,
    "last_summary_round": 0,
    "total_summaries": 0,
}


def load_entries(path: Path) -> list:
    return load_json(path, [])


def save_entries(path: Path, data: list) -> None:
    write_json(path, data)


def load_config(path: Path) -> dict:
    return load_json(path, dict(DEFAULT_CONFIG))


def save_config(path: Path, data: dict) -> None:
    write_json(path, data)


def build_stats(store: list, cfg: dict) -> dict:
    return {
        "total_memories": len(store),
        "total_rounds": cfg.get("total_rounds", 0),
        "total_summaries": cfg.get("total_summaries", 0),
        "high_value": sum(1 for item in store if item.get("importance", 0) >= 0.7),
        "crystallized": sum(1 for item in store if item.get("crystallized")),
    }
