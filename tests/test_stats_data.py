import asyncio
from types import SimpleNamespace

from core import state_loader
from routes import data


def test_record_stats_tracks_cache_fields_per_model(tmp_path, monkeypatch):
    primary_stats = tmp_path / "stats.json"
    legacy_stats = tmp_path / "legacy_stats.json"

    monkeypatch.setattr(state_loader, "PRIMARY_STATS_FILE", primary_stats)
    monkeypatch.setattr(state_loader, "LEGACY_STATS_FILE", legacy_stats)
    monkeypatch.setattr(state_loader, "load_current_model", lambda: "deepseek-chat")

    stats = state_loader.record_stats(
        input_tokens=120,
        output_tokens=30,
        scene="chat",
        cache_write=80,
        cache_read=40,
        model="DeepSeek-Chat",
    )

    model_stats = stats["by_model"]["deepseek-chat"]
    assert stats["input_tokens"] == 120
    assert stats["output_tokens"] == 30
    assert stats["cache_write_tokens"] == 80
    assert stats["cache_read_tokens"] == 40
    assert model_stats["input"] == 120
    assert model_stats["output"] == 30
    assert model_stats["requests"] == 1
    assert model_stats["cache_write"] == 80
    assert model_stats["cache_read"] == 40


def test_update_stats_forwards_cache_and_model_fields():
    captured = {}

    def fake_record_stats(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    original_shared = data.S
    data.S = SimpleNamespace(record_stats=fake_record_stats)
    try:
        result = asyncio.run(
            data.update_stats(
                {
                    "input_tokens": 12,
                    "output_tokens": 3,
                    "scene": "tool_call",
                    "cache_write": 8,
                    "cache_read": 4,
                    "model": "minimax-m2.7",
                }
            )
        )
    finally:
        data.S = original_shared

    assert result == {"ok": True, "stats": {"ok": True}}
    assert captured == {
        "input_tokens": 12,
        "output_tokens": 3,
        "scene": "tool_call",
        "cache_write": 8,
        "cache_read": 4,
        "model": "minimax-m2.7",
    }


def test_migrate_stats_data_backfills_model_cache_fields():
    stats, changed = state_loader.migrate_stats_data(
        {
            "cache_write_tokens": 30,
            "cache_read_tokens": 12,
            "by_model": {
                "DeepSeek-Chat": {"input": 90, "output": 10, "requests": 3},
                "minimax-m2.7": {"input": 30, "output": 5, "requests": 1},
            },
        }
    )

    assert changed is True
    assert stats["stats_schema_version"] == 2
    assert stats["stats_meta"]["by_model_cache_source"] == "estimated_from_input_share"
    assert sum(v["cache_write"] for v in stats["by_model"].values()) == 30
    assert sum(v["cache_read"] for v in stats["by_model"].values()) == 12
    assert stats["by_model"]["deepseek-chat"]["cache_write"] == 22
    assert stats["by_model"]["deepseek-chat"]["cache_read"] == 9
    assert stats["by_model"]["minimax-m2.7"]["cache_write"] == 8
    assert stats["by_model"]["minimax-m2.7"]["cache_read"] == 3


def test_load_stats_data_auto_migrates_legacy_stats_file(tmp_path, monkeypatch):
    primary_stats = tmp_path / "stats.json"
    legacy_stats = tmp_path / "legacy_stats.json"
    primary_stats.write_text(
        """{
  "input_tokens": 120,
  "output_tokens": 20,
  "cache_write_tokens": 40,
  "cache_read_tokens": 10,
  "by_model": {
    "DeepSeek-Chat": {"input": 120, "output": 20, "requests": 2}
  }
}""",
        encoding="utf-8",
    )

    monkeypatch.setattr(state_loader, "PRIMARY_STATS_FILE", primary_stats)
    monkeypatch.setattr(state_loader, "LEGACY_STATS_FILE", legacy_stats)
    monkeypatch.setattr(state_loader, "load_current_model", lambda: "deepseek-chat")

    stats = state_loader.load_stats_data()

    assert stats["by_model"]["deepseek-chat"]["cache_write"] == 40
    assert stats["by_model"]["deepseek-chat"]["cache_read"] == 10
    assert stats["stats_schema_version"] == 2
    assert '"cache_write": 40' in primary_stats.read_text(encoding="utf-8")
