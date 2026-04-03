from datetime import datetime, timedelta

from storage.json_store import load_json_store, write_json
from storage.model_config import load_current_model
from storage.paths import LEGACY_STATS_FILE, PRIMARY_STATS_FILE


def load_stats_data():
    stats = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "total_requests": 0,
        "cache_write_tokens": 0,
        "cache_read_tokens": 0,
        "model": load_current_model(),
        "last_used": "",
        "by_scene": {},
        "by_day": {},
    }
    saved = load_json_store(PRIMARY_STATS_FILE, LEGACY_STATS_FILE, {})
    if isinstance(saved, dict):
        stats.update(saved)
    stats, migrated = migrate_stats_data(stats)
    stats["model"] = load_current_model()
    if "by_scene" not in stats:
        stats["by_scene"] = {}
    if migrated:
        write_json(PRIMARY_STATS_FILE, stats)
    return stats


def _allocate_tokens_by_weight(total: int, weights: dict[str, int]) -> dict[str, int]:
    total = max(int(total), 0)
    clean = {str(k): max(int(v), 0) for k, v in (weights or {}).items()}
    if total <= 0 or not clean:
        return {k: 0 for k in clean}

    weight_sum = sum(clean.values())
    if weight_sum <= 0:
        keys = list(clean.keys())
        base = total // len(keys)
        remainder = total % len(keys)
        return {k: base + (1 if idx < remainder else 0) for idx, k in enumerate(keys)}

    allocated = {}
    remainders = []
    used = 0
    for key, weight in clean.items():
        exact = total * weight / weight_sum
        count = int(exact)
        allocated[key] = count
        used += count
        remainders.append((exact - count, key))

    for _, key in sorted(remainders, reverse=True)[: total - used]:
        allocated[key] += 1
    return allocated


def migrate_stats_data(stats: dict) -> tuple[dict, bool]:
    if not isinstance(stats, dict):
        return {}, False

    changed = False
    by_model = stats.get("by_model")
    if not isinstance(by_model, dict):
        by_model = {}
        stats["by_model"] = by_model
        changed = True

    normalized = {}
    model_inputs = {}
    missing_cache_fields = False
    for raw_key, raw_value in by_model.items():
        key = str(raw_key or "").lower()
        row = raw_value if isinstance(raw_value, dict) else {}
        normalized_row = {
            "input": max(int(row.get("input", 0)), 0),
            "output": max(int(row.get("output", 0)), 0),
            "requests": max(int(row.get("requests", 0)), 0),
            "cache_write": max(int(row.get("cache_write", 0)), 0),
            "cache_read": max(int(row.get("cache_read", 0)), 0),
        }
        if "cache_write" not in row or "cache_read" not in row:
            missing_cache_fields = True
        if key != raw_key or row != normalized_row:
            changed = True
        normalized[key] = normalized_row
        model_inputs[key] = normalized_row["input"]

    if normalized != by_model:
        stats["by_model"] = normalized
        by_model = normalized
        changed = True

    if by_model and missing_cache_fields:
        total_cache_write = max(int(stats.get("cache_write_tokens", 0)), 0)
        total_cache_read = max(int(stats.get("cache_read_tokens", 0)), 0)
        write_alloc = _allocate_tokens_by_weight(total_cache_write, model_inputs)
        read_alloc = _allocate_tokens_by_weight(total_cache_read, model_inputs)
        for key, row in by_model.items():
            if row.get("cache_write", 0) == 0 and total_cache_write > 0:
                row["cache_write"] = write_alloc.get(key, 0)
                changed = True
            if row.get("cache_read", 0) == 0 and total_cache_read > 0:
                row["cache_read"] = read_alloc.get(key, 0)
                changed = True

    if int(stats.get("stats_schema_version", 0) or 0) < 2:
        stats["stats_schema_version"] = 2
        changed = True

    meta = stats.get("stats_meta")
    if not isinstance(meta, dict):
        meta = {}
        stats["stats_meta"] = meta
        changed = True
    source = "estimated_from_input_share" if missing_cache_fields else "recorded"
    if by_model and meta.get("by_model_cache_source") != source:
        meta["by_model_cache_source"] = source
        changed = True

    return stats, changed


def record_stats(input_tokens: int = 0, output_tokens: int = 0, scene: str = "chat",
                 cache_write: int = 0, cache_read: int = 0, model: str = ""):
    inp = max(int(input_tokens), 0)
    out = max(int(output_tokens), 0)
    cw = max(int(cache_write), 0)
    cr = max(int(cache_read), 0)
    total = inp + out
    stats = load_stats_data()
    stats["input_tokens"] = stats.get("input_tokens", 0) + inp
    stats["output_tokens"] = stats.get("output_tokens", 0) + out
    stats["total_tokens"] = stats.get("total_tokens", 0) + total
    stats["total_requests"] = stats.get("total_requests", 0) + 1
    stats["cache_write_tokens"] = stats.get("cache_write_tokens", 0) + cw
    stats["cache_read_tokens"] = stats.get("cache_read_tokens", 0) + cr
    stats["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    by_scene = stats.setdefault("by_scene", {})
    scene_stats = by_scene.setdefault(scene, {"requests": 0, "tokens": 0})
    scene_stats["requests"] = scene_stats.get("requests", 0) + 1
    scene_stats["tokens"] = scene_stats.get("tokens", 0) + total

    today = datetime.now().strftime("%Y-%m-%d")
    by_day = stats.setdefault("by_day", {})
    day_stats = by_day.setdefault(today, {"tokens": 0, "requests": 0, "input": 0, "output": 0})
    day_stats["tokens"] = day_stats.get("tokens", 0) + total
    day_stats["requests"] = day_stats.get("requests", 0) + 1
    day_stats["input"] = day_stats.get("input", 0) + inp
    day_stats["output"] = day_stats.get("output", 0) + out

    if model:
        by_model = stats.setdefault("by_model", {})
        model_id = model.lower()
        model_stats = by_model.setdefault(
            model_id,
            {"input": 0, "output": 0, "requests": 0, "cache_write": 0, "cache_read": 0},
        )
        model_stats["input"] = model_stats.get("input", 0) + inp
        model_stats["output"] = model_stats.get("output", 0) + out
        model_stats["requests"] = model_stats.get("requests", 0) + 1
        model_stats["cache_write"] = model_stats.get("cache_write", 0) + cw
        model_stats["cache_read"] = model_stats.get("cache_read", 0) + cr

    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    stats["by_day"] = {key: value for key, value in by_day.items() if key >= cutoff}
    write_json(PRIMARY_STATS_FILE, stats)
    return stats


MODEL_PRICES = {
    "deepseek": {"input": 1, "output": 2},
    "minimax": {"input": 1, "output": 8},
    "qwen": {"input": 2, "output": 6},
    "glm": {"input": 1, "output": 1},
    "doubao": {"input": 0.8, "output": 2},
    "kimi": {"input": 12, "output": 12},
    "claude": {"input": 3, "output": 15},
    "openai": {"input": 2.5, "output": 10},
}


def get_model_price(model_name: str) -> dict:
    model_value = (model_name or "").lower()
    for key, value in MODEL_PRICES.items():
        if key in model_value:
            return value
    return {"input": 2, "output": 4}


def record_memory_stats(l2_searches: int = 0, l2_hits: int = 0,
                        l8_searches: int = 0, l8_hits: int = 0,
                        l3_queries: int = 0, l3_hits: int = 0,
                        l4_queries: int = 0, l4_hits: int = 0,
                        l5_queries: int = 0, l5_hits: int = 0,
                        l6_hits: int = 0, l7_hits: int = 0,
                        l1_count: int = 0, l3_count: int = 0,
                        l4_available: bool = False, l5_count: int = 0,
                        cod_used=None, count_query: bool = True):
    stats = load_stats_data()
    memory_stats = stats.get("memory")
    if not isinstance(memory_stats, dict):
        memory_stats = {
            "l2_searches": 0, "l2_hits": 0,
            "l8_searches": 0, "l8_hits": 0,
            "l3_queries": 0, "l3_hits": 0,
            "l4_queries": 0, "l4_hits": 0,
            "l5_queries": 0, "l5_hits": 0,
            "total_queries": 0, "full_layer_available": 0,
            "l1_count": 0, "l3_count": 0, "l4_available": 0, "l5_count": 0,
            "flash_count": 0, "trace_back_count": 0,
        }

    memory_stats["l2_searches"] = memory_stats.get("l2_searches", 0) + max(int(l2_searches), 0)
    memory_stats["l2_hits"] = memory_stats.get("l2_hits", 0) + max(int(l2_hits), 0)
    memory_stats["l8_searches"] = memory_stats.get("l8_searches", 0) + max(int(l8_searches), 0)
    memory_stats["l8_hits"] = memory_stats.get("l8_hits", 0) + max(int(l8_hits), 0)
    memory_stats["l3_queries"] = memory_stats.get("l3_queries", 0) + max(int(l3_queries), 0)
    memory_stats["l3_hits"] = memory_stats.get("l3_hits", 0) + max(int(l3_hits), 0)
    memory_stats["l4_queries"] = memory_stats.get("l4_queries", 0) + max(int(l4_queries), 0)
    memory_stats["l4_hits"] = memory_stats.get("l4_hits", 0) + max(int(l4_hits), 0)
    memory_stats["l5_queries"] = memory_stats.get("l5_queries", 0) + max(int(l5_queries), 0)
    memory_stats["l5_hits"] = memory_stats.get("l5_hits", 0) + max(int(l5_hits), 0)
    memory_stats["l6_hits"] = memory_stats.get("l6_hits", 0) + max(int(l6_hits), 0)
    memory_stats["l7_hits"] = memory_stats.get("l7_hits", 0) + max(int(l7_hits), 0)

    if count_query:
        memory_stats["total_queries"] = memory_stats.get("total_queries", 0) + 1
        layers_up = (1 if l1_count > 0 else 0) + (1 if l3_count > 0 else 0) + (1 if l4_available else 0) + (1 if l5_count > 0 else 0)
        memory_stats["full_layer_available"] = memory_stats.get("full_layer_available", 0) + layers_up
        memory_stats["l1_count"] = l1_count
        memory_stats["l3_count"] = l3_count
        memory_stats["l4_available"] = 1 if l4_available else 0
        memory_stats["l5_count"] = l5_count

    if cod_used is True:
        memory_stats["trace_back_count"] = memory_stats.get("trace_back_count", 0) + 1
    elif cod_used is False:
        memory_stats["flash_count"] = memory_stats.get("flash_count", 0) + 1

    memory_stats.setdefault("flash_count", 0)
    memory_stats.setdefault("trace_back_count", 0)
    stats["memory"] = memory_stats
    write_json(PRIMARY_STATS_FILE, stats)


def reset_stats():
    stats = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "total_requests": 0,
        "cache_write_tokens": 0,
        "cache_read_tokens": 0,
        "model": load_current_model(),
        "last_used": "",
        "by_scene": {},
        "memory": {
            "l2_searches": 0, "l2_hits": 0,
            "l8_searches": 0, "l8_hits": 0,
            "total_queries": 0, "full_layer_available": 0,
            "l1_count": 0, "l3_count": 0, "l4_available": 0, "l5_count": 0,
            "flash_count": 0, "trace_back_count": 0,
        },
    }
    write_json(PRIMARY_STATS_FILE, stats)
    return stats
