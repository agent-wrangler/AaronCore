"""Tool-call usage accounting helpers."""


def record_tool_call_usage_stats(cfg: dict, usage: dict | None) -> None:
    usage = usage if isinstance(usage, dict) else {}
    try:
        from core.runtime_state.state_loader import record_stats

        record_stats(
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            scene="tool_call",
            cache_write=usage.get("prompt_cache_miss_tokens", 0),
            cache_read=usage.get("prompt_cache_hit_tokens", 0),
            model=cfg.get("model", ""),
        )
    except Exception:
        pass


def merge_tool_call_usage_totals(usage: dict, delta: dict | None) -> None:
    delta = delta if isinstance(delta, dict) else {}
    for key in ("prompt_tokens", "completion_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
        usage[key] = usage.get(key, 0) + delta.get(key, 0)
