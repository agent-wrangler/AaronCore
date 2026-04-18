from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from storage.history_store import _estimate_recent_message_tokens, get_recent_messages


def _parse_int_list(raw: str, *, default: list[int]) -> list[int]:
    text = str(raw or "").strip()
    if not text:
        return list(default)
    values: list[int] = []
    for part in text.split(","):
        item = part.strip()
        if not item:
            continue
        try:
            value = int(item)
        except Exception:
            continue
        if value > 0:
            values.append(value)
    return values or list(default)


def _load_history(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"History file is not a list: {path}")
    return [item for item in payload if isinstance(item, dict)]


def _expand_history(history: list[dict], repeat: int) -> list[dict]:
    if repeat <= 1:
        return [dict(item) for item in history]
    expanded: list[dict] = []
    for index in range(repeat):
        for item in history:
            row = dict(item)
            content = str(row.get("content") or row.get("summary") or row.get("event") or "").strip()
            row["content"] = f"{content}\n[repeat-{index}]"
            expanded.append(row)
    return expanded


def _estimate_total_tokens(history: list[dict]) -> int:
    return sum(_estimate_recent_message_tokens(item) for item in history)


def build_report(
    history: list[dict],
    *,
    budgets: list[int],
    repeats: list[int],
) -> dict:
    scenarios = []
    for repeat in repeats:
        rows = _expand_history(history, repeat)
        full_tokens = _estimate_total_tokens(rows)
        budget_rows = []
        for budget in budgets:
            recent = get_recent_messages(rows, limit=None, max_tokens=budget)
            kept_tokens = _estimate_total_tokens(recent)
            saved_tokens = max(full_tokens - kept_tokens, 0)
            saved_pct = round((saved_tokens / full_tokens * 100), 2) if full_tokens else 0.0
            budget_rows.append(
                {
                    "budget": budget,
                    "kept_messages": len(recent),
                    "kept_tokens_est": kept_tokens,
                    "saved_tokens_est": saved_tokens,
                    "saved_pct": saved_pct,
                }
            )
        scenarios.append(
            {
                "repeat": repeat,
                "messages": len(rows),
                "full_tokens_est": full_tokens,
                "budgets": budget_rows,
            }
        )
    return {
        "source_messages": len(history),
        "source_tokens_est": _estimate_total_tokens(history),
        "scenarios": scenarios,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Estimate context token savings from recent-history budgeting.")
    parser.add_argument(
        "--history-file",
        default="state_data/msg_history.json",
        help="Path to a persisted chat history JSON file.",
    )
    parser.add_argument(
        "--budgets",
        default="2000,4000,6000,8000",
        help="Comma-separated recent-history token budgets to compare.",
    )
    parser.add_argument(
        "--repeats",
        default="1,5,10,20",
        help="Comma-separated multipliers to simulate longer continuous sessions.",
    )
    args = parser.parse_args()

    history_path = Path(args.history_file)
    history = _load_history(history_path)
    budgets = _parse_int_list(args.budgets, default=[2000, 4000, 6000, 8000])
    repeats = _parse_int_list(args.repeats, default=[1, 5, 10, 20])
    report = build_report(history, budgets=budgets, repeats=repeats)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
