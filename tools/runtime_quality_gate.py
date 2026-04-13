from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools import benchmark_runner, live_llm_replay


def _parse_ids(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _coerce_round(value, *, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _build_benchmark_summary_payload(rows: list[dict]) -> dict:
    tracked = [item for item in rows if not bool(item.get("orphaned"))]
    orphaned = [item for item in rows if bool(item.get("orphaned"))]
    tracked_scoreless = [item for item in tracked if float(item.get("best_score") or 0.0) <= 0.0]
    tracked_latest_problem = [
        item
        for item in tracked
        if str(item.get("latest_status") or "").strip().lower() in {"skip", "crash"}
    ]
    warnings = []
    if tracked_scoreless:
        warnings.append(f"{len(tracked_scoreless)} tracked benchmark experiments have no positive score yet.")
    if orphaned:
        warnings.append(f"{len(orphaned)} orphaned benchmark histories are present in results.tsv.")
    if tracked_latest_problem:
        warnings.append(
            f"{len(tracked_latest_problem)} tracked benchmark experiments most recently ended in skip/crash."
        )
    return {
        "mode": "summary",
        "summary": {
            "total_rows": len(rows),
            "tracked_experiments": len(tracked),
            "orphaned_experiments": len(orphaned),
            "tracked_scoreless_experiments": len(tracked_scoreless),
            "tracked_latest_problem_experiments": len(tracked_latest_problem),
            "warning_count": len(warnings),
        },
        "warnings": warnings,
        "results": rows,
    }


def _build_benchmark_dry_run_payload(experiment_ids: list[str] | None = None, *, rounds: int | None = None) -> dict:
    selected = benchmark_runner.select_benchmark_experiments(experiment_ids)
    return {
        "mode": "dry_run",
        "summary": {
            "total_experiments": len(selected),
            "experiment_ids": [str(item.get("id") or "").strip() for item in selected],
            "rounds": int(rounds or 0) if rounds else 0,
        },
        "results": [
            {
                "experiment_id": str(item.get("id") or "").strip(),
                "target_key": str(item.get("target_key") or "").strip(),
                "goal": str(item.get("goal") or "").strip(),
                "rounds": max(1, _coerce_round(rounds, default=_coerce_round(item.get("rounds"), default=1))),
            }
            for item in selected
        ],
    }


def _build_benchmark_run_payload(experiment_ids: list[str] | None = None, *, rounds: int | None = None) -> dict:
    payload = benchmark_runner.run_benchmark_suite(
        experiment_ids=experiment_ids,
        rounds=rounds,
    )
    payload["mode"] = "run"
    return payload


def build_quality_gate_report(
    *,
    replay_suite_ids: Iterable[str] | None = None,
    replay_case_ids: Iterable[str] | None = None,
    replay_preset_ids: Iterable[str] | None = None,
    replay_live: bool = False,
    model_id: str = "",
    cod_mode: bool = False,
    show_prompts: bool = False,
    benchmark_all: bool = False,
    benchmark_experiment_ids: Iterable[str] | None = None,
    benchmark_rounds: int | None = None,
    benchmark_dry_run: bool = False,
    include_details: bool = False,
) -> dict:
    selected_suites = [str(item or "").strip() for item in replay_suite_ids or () if str(item or "").strip()]
    if not selected_suites:
        selected_suites = ["full_runtime_regressions"]

    replay_payload = live_llm_replay.run_eval_suite(
        suite_ids=selected_suites,
        case_ids=replay_case_ids,
        preset_ids=replay_preset_ids,
        model_id=model_id,
        cod_mode=cod_mode,
        dry_run=not replay_live,
        show_prompts=show_prompts,
    )

    benchmark_ids = [str(item or "").strip() for item in benchmark_experiment_ids or () if str(item or "").strip()]
    if benchmark_all and benchmark_ids:
        raise ValueError("benchmark_all and benchmark_experiment_ids cannot be combined")

    if benchmark_all or benchmark_ids:
        if benchmark_dry_run:
            benchmark_payload = _build_benchmark_dry_run_payload(
                benchmark_ids or None,
                rounds=benchmark_rounds,
            )
        else:
            benchmark_payload = _build_benchmark_run_payload(
                benchmark_ids or None,
                rounds=benchmark_rounds,
            )
    else:
        benchmark_payload = _build_benchmark_summary_payload(benchmark_runner.summarize_benchmark_results())

    replay_summary = replay_payload.get("summary", {}) if isinstance(replay_payload, dict) else {}
    benchmark_summary = benchmark_payload.get("summary", {}) if isinstance(benchmark_payload, dict) else {}
    benchmark_mode = str(benchmark_payload.get("mode") or "summary")
    replay_failed = int(replay_summary.get("failed", 0))
    benchmark_failures = 0
    if benchmark_mode == "run":
        benchmark_failures = int(benchmark_summary.get("crash_count", 0)) + int(benchmark_summary.get("skip_count", 0))

    warning_count = int(benchmark_summary.get("warning_count", 0)) if benchmark_mode == "summary" else 0
    passed = replay_failed == 0 and benchmark_failures == 0

    replay_report = {
        "summary": replay_summary,
        "eval_suites": replay_payload.get("eval_suites", []) if isinstance(replay_payload, dict) else [],
    }
    benchmark_report = {
        "mode": benchmark_mode,
        "summary": benchmark_summary,
    }
    if "warnings" in benchmark_payload:
        benchmark_report["warnings"] = list(benchmark_payload.get("warnings") or [])
    if include_details:
        if isinstance(replay_payload, dict) and "results" in replay_payload:
            replay_report["results"] = replay_payload.get("results", [])
        if isinstance(benchmark_payload, dict) and "results" in benchmark_payload:
            benchmark_report["results"] = benchmark_payload.get("results", [])

    return {
        "summary": {
            "pass": passed,
            "status": "pass" if passed and warning_count == 0 else ("warn" if passed else "fail"),
            "strict_default": bool(replay_summary.get("suite_strict_default")),
            "replay_total": int(replay_summary.get("total", 0)),
            "replay_passed": int(replay_summary.get("passed", 0)),
            "replay_failed": replay_failed,
            "benchmark_mode": benchmark_mode,
            "benchmark_failures": benchmark_failures,
            "benchmark_warning_count": warning_count,
        },
        "replay": replay_report,
        "benchmark": benchmark_report,
    }


def _emit_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the runtime replay eval gate and benchmark health checks together.",
    )
    parser.add_argument(
        "--replay-suite",
        dest="replay_suite_ids",
        default="full_runtime_regressions",
        help="Comma-separated replay eval suite ids. Defaults to full_runtime_regressions.",
    )
    parser.add_argument(
        "--replay-case",
        dest="replay_case_ids",
        default="",
        help="Optional comma-separated replay case ids.",
    )
    parser.add_argument(
        "--replay-preset",
        dest="replay_preset_ids",
        default="",
        help="Optional comma-separated replay preset ids.",
    )
    parser.add_argument(
        "--live-replay",
        action="store_true",
        help="Call the live model for replay instead of using dry-run prompt/runtime checks.",
    )
    parser.add_argument("--model", default="", help="Optional model id for replay.")
    parser.add_argument("--cod-mode", action="store_true", help="Use CoD tool schema for replay.")
    parser.add_argument("--show-prompts", action="store_true", help="Include replay prompts in the output.")
    parser.add_argument("--details", action="store_true", help="Include full replay/benchmark result details.")
    parser.add_argument(
        "--benchmark-all",
        action="store_true",
        help="Run all benchmark experiments instead of only summarizing benchmark history.",
    )
    parser.add_argument(
        "--benchmark",
        dest="benchmark_ids",
        default="",
        help="Comma-separated benchmark experiment ids to run.",
    )
    parser.add_argument(
        "--benchmark-rounds",
        type=int,
        default=0,
        help="Optional round override for benchmark runs.",
    )
    parser.add_argument(
        "--benchmark-dry-run",
        action="store_true",
        help="Preview the selected benchmark experiments without running scoring.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 when the overall quality gate fails.",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="Disable replay-suite strict-by-default behavior.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    replay_suite_ids = _parse_ids(args.replay_suite_ids)
    benchmark_ids = _parse_ids(args.benchmark_ids)
    if args.benchmark_all and benchmark_ids:
        parser.error("--benchmark cannot be combined with --benchmark-all")

    payload = build_quality_gate_report(
        replay_suite_ids=replay_suite_ids,
        replay_case_ids=_parse_ids(args.replay_case_ids),
        replay_preset_ids=_parse_ids(args.replay_preset_ids),
        replay_live=bool(args.live_replay),
        model_id=args.model,
        cod_mode=bool(args.cod_mode),
        show_prompts=bool(args.show_prompts),
        benchmark_all=bool(args.benchmark_all),
        benchmark_experiment_ids=benchmark_ids,
        benchmark_rounds=args.benchmark_rounds or None,
        benchmark_dry_run=bool(args.benchmark_dry_run),
        include_details=bool(args.details),
    )
    _emit_json(payload)

    strict_mode = bool(args.strict or (not args.no_strict and payload.get("summary", {}).get("strict_default")))
    if strict_mode and not bool(payload.get("summary", {}).get("pass")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
