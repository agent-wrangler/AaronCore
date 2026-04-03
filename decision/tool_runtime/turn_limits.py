from __future__ import annotations


DEFAULT_MAX_TURNS = 32
MAX_ALLOWED_MAX_TURNS = 200


def resolve_max_turns(bundle: dict | None, *, default: int = DEFAULT_MAX_TURNS) -> int:
    raw_candidates = []
    if isinstance(bundle, dict):
        raw_candidates.extend(
            [
                bundle.get("maxTurns"),
                bundle.get("max_turns"),
            ]
        )
        runtime_options = bundle.get("runtime_options")
        if isinstance(runtime_options, dict):
            raw_candidates.extend(
                [
                    runtime_options.get("maxTurns"),
                    runtime_options.get("max_turns"),
                ]
            )
        tool_runtime = bundle.get("tool_runtime")
        if isinstance(tool_runtime, dict):
            raw_candidates.extend(
                [
                    tool_runtime.get("maxTurns"),
                    tool_runtime.get("max_turns"),
                ]
            )

    for raw_value in raw_candidates:
        try:
            parsed = int(raw_value)
        except (TypeError, ValueError):
            continue
        if parsed <= 0:
            continue
        return min(parsed, MAX_ALLOWED_MAX_TURNS)

    return default


def build_turn_limit_meta(
    *,
    turns_used: int,
    max_turns: int,
    turn_limit_reached: bool,
    turn_reason: str = "",
) -> dict:
    return {
        "turns_used": max(0, int(turns_used)),
        "max_turns": max(1, int(max_turns)),
        "turn_limit_reached": bool(turn_limit_reached),
        "turn_reason": str(turn_reason or "").strip(),
    }


def build_max_turns_closeout_reply(
    formatter,
    *,
    max_turns: int,
    turns_used: int,
    success: bool | None,
    action_summary: str,
    tool_response: str,
    run_meta: dict | None,
) -> str:
    header = f"已达到当前工具往返轮次上限（{max_turns} 轮），我先在这里收口，避免继续空转。"
    fallback = formatter._build_tool_closeout_reply(
        success=bool(success) if success is not None else False,
        action_summary=action_summary,
        tool_response=tool_response,
        run_meta=run_meta if isinstance(run_meta, dict) else {},
    )
    if not fallback:
        return header
    if fallback.strip() == header:
        return header
    return f"{header}\n\n{fallback}".strip()
