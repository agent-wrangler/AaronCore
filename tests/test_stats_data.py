import asyncio
import json
from types import SimpleNamespace

from core.runtime_state import state_loader
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


def test_load_assistant_name_payload_prefers_new_field(tmp_path, monkeypatch):
    (tmp_path / "persona.json").write_text(
        json.dumps(
            {
                "assistant_name": "小夏",
                "nova_name": "旧名",
                "name": "旧品牌名",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(data, "S", SimpleNamespace(PRIMARY_STATE_DIR=tmp_path))

    payload = data._load_assistant_name_payload()

    assert payload == {"name": "小夏"}


def test_nova_name_route_keeps_legacy_alias_but_returns_assistant_name(tmp_path, monkeypatch):
    (tmp_path / "persona.json").write_text(
        json.dumps({"assistant_name": "小夏", "nova_name": "旧名"}, ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(data, "S", SimpleNamespace(PRIMARY_STATE_DIR=tmp_path))

    assert asyncio.run(data.get_assistant_name()) == {"name": "小夏"}
    assert asyncio.run(data.get_nova_name()) == {"name": "小夏"}


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


def test_get_stats_uses_l5_and_l8_store_counts(tmp_path, monkeypatch):
    (tmp_path / "long_term.json").write_text("[]", encoding="utf-8")
    (tmp_path / "persona.json").write_text("{}", encoding="utf-8")
    (tmp_path / "knowledge.json").write_text(
        json.dumps(
            [
                {"name": "weather", "source": "manual"},
                {"name": "trace", "source": "l6_success_path"},
                {"name": "skip", "source": "l2_demand"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "knowledge_base.json").write_text(
        json.dumps(
            [
                {"name": "k1", "summary": "one"},
                {"name": "k2", "summary": "two"},
                {"name": "k3", "summary": "three"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(data, "should_show_l8_timeline_entry", lambda item: True)
    monkeypatch.setattr(data, "get_model_price", lambda _model: {"input": 2, "output": 4})
    monkeypatch.setattr(data, "MODEL_PRICES", {})
    monkeypatch.setattr(
        data,
        "S",
        SimpleNamespace(
            load_stats_data=lambda: {"memory": {}, "model": "deepseek-chat"},
            PRIMARY_STATE_DIR=tmp_path,
            is_legacy_l3_skill_log=lambda _item: False,
        ),
    )

    result = asyncio.run(data.get_stats())
    memory = result["stats"]["memory"]

    assert memory["real_l5_count"] == 2
    assert memory["real_l8_count"] == 3
