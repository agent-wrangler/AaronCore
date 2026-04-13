from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from storage.paths import LAB_DIR


EXPERIMENTS_FILE = LAB_DIR / "experiments.json"
RESULTS_FILE = LAB_DIR / "results.tsv"
VERIFY_SCRIPT_FILE = LAB_DIR / "verify.py"
RESULTS_HEADER = ("experiment", "iteration", "commit", "score", "status", "description", "time")


def _load_json_list(path: Path) -> list[dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _save_json_list(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def load_benchmark_experiments(path: Path = EXPERIMENTS_FILE) -> list[dict]:
    return _load_json_list(path)


def load_benchmark_results(path: Path = RESULTS_FILE) -> list[dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, delimiter="\t")
            header = next(reader, None)
            if not header:
                return []
            rows = []
            for raw in reader:
                if not isinstance(raw, list):
                    continue
                if len(raw) >= len(RESULTS_HEADER):
                    mapped = dict(zip(RESULTS_HEADER, raw))
                elif len(raw) == len(RESULTS_HEADER) - 1:
                    mapped = {
                        "experiment": raw[0],
                        "iteration": raw[1],
                        "commit": "-",
                        "score": raw[2],
                        "status": raw[3],
                        "description": raw[4],
                        "time": raw[5],
                    }
                else:
                    continue
                experiment_id = str(mapped.get("experiment") or "").strip()
                if not experiment_id:
                    continue
                rows.append(
                    {
                        "experiment": experiment_id,
                        "iteration": _coerce_round(mapped.get("iteration"), default=0),
                        "commit": str(mapped.get("commit") or "").strip(),
                        "score": _coerce_score(mapped.get("score"), default=0.0),
                        "status": str(mapped.get("status") or "").strip(),
                        "description": str(mapped.get("description") or "").strip(),
                        "time": str(mapped.get("time") or "").strip(),
                    }
                )
            return rows
    except Exception:
        return []


def get_benchmark_experiment(experiment_id: str, *, path: Path = EXPERIMENTS_FILE) -> dict | None:
    wanted = str(experiment_id or "").strip()
    if not wanted:
        return None
    for item in load_benchmark_experiments(path):
        if str(item.get("id") or "").strip() == wanted:
            return item
    return None


def _existing_results(experiment: dict) -> list[dict]:
    rows = experiment.get("results")
    if not isinstance(rows, list):
        return []
    return [item for item in rows if isinstance(item, dict)]


def _coerce_round(value, *, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _coerce_score(value, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _resolve_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parents[1],
        )
    except Exception:
        return "-"
    commit = str(result.stdout or "").strip()
    return commit or "-"


def _load_verify_module(verify_script: Path = VERIFY_SCRIPT_FILE):
    module_name = f"lab_verify_{abs(hash(str(verify_script.resolve())))}"
    spec = importlib.util.spec_from_file_location(module_name, verify_script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load verify script: {verify_script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def score_target(target_key: str, goal: str, *, verify_script: Path = VERIFY_SCRIPT_FILE) -> float:
    module = _load_verify_module(verify_script)
    scorer = getattr(module, "score_target", None)
    if not callable(scorer):
        raise RuntimeError(f"Verify script does not expose score_target(): {verify_script}")
    return float(scorer(target_key, goal))


def _ensure_results_file(path: Path = RESULTS_FILE) -> None:
    if path.exists() and path.read_text(encoding="utf-8").strip():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(RESULTS_HEADER)


def _append_results_row(row: dict, *, path: Path = RESULTS_FILE) -> None:
    _ensure_results_file(path)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow([row.get(key, "") for key in RESULTS_HEADER])


def _write_results_rows(rows: list[dict], *, path: Path = RESULTS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(RESULTS_HEADER)
        for row in rows:
            writer.writerow([row.get(key, "") for key in RESULTS_HEADER])


def _best_score(experiment: dict) -> float:
    scores = []
    best_result = experiment.get("best_result")
    if isinstance(best_result, dict):
        scores.append(_coerce_score(best_result.get("score")))
    for item in _existing_results(experiment):
        scores.append(_coerce_score(item.get("score")))
    return max(scores) if scores else 0.0


def _next_iteration(experiment: dict) -> int:
    rounds = [_coerce_round(item.get("round")) for item in _existing_results(experiment)]
    if not rounds:
        return 1
    return max(rounds) + 1


def _status_for_score(score: float, previous_best: float) -> str:
    if score <= 0:
        return "skip"
    if score >= previous_best:
        return "keep"
    return "discard"


def _now_iso() -> str:
    return datetime.now().isoformat()


def _best_score_from_history(rows: list[dict]) -> float:
    scores = [_coerce_score(item.get("score")) for item in rows if isinstance(item, dict)]
    return max(scores) if scores else 0.0


def _latest_history_result(rows: list[dict]) -> dict:
    filtered = [item for item in rows if isinstance(item, dict)]
    if not filtered:
        return {}
    return filtered[-1]


def _status_counts(rows: list[dict]) -> dict[str, int]:
    counts = {"keep": 0, "discard": 0, "skip": 0, "crash": 0}
    for item in rows:
        status = str(item.get("status") or "").strip().lower()
        if status in counts:
            counts[status] += 1
    return counts


def select_benchmark_experiments(
    experiment_ids: list[str] | None = None,
    *,
    path: Path = EXPERIMENTS_FILE,
) -> list[dict]:
    rows = load_benchmark_experiments(path)
    wanted = [str(item or "").strip() for item in experiment_ids or () if str(item or "").strip()]
    if not wanted:
        return rows
    indexed = {
        str(item.get("id") or "").strip(): item
        for item in rows
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    selected = []
    missing = []
    for experiment_id in wanted:
        item = indexed.get(experiment_id)
        if item is None:
            missing.append(experiment_id)
            continue
        selected.append(item)
    if missing:
        raise KeyError(", ".join(missing))
    return selected


def list_benchmark_experiments(path: Path = EXPERIMENTS_FILE) -> list[dict]:
    rows = []
    for item in load_benchmark_experiments(path):
        rows.append(
            {
                "id": str(item.get("id") or "").strip(),
                "target_key": str(item.get("target_key") or "").strip(),
                "target_label": str(item.get("target_label") or "").strip(),
                "goal": str(item.get("goal") or "").strip(),
                "rounds": _coerce_round(item.get("rounds"), default=1),
                "status": str(item.get("status") or "").strip(),
                "best_score": _best_score(item),
            }
        )
    return rows


def summarize_benchmark_results(
    *,
    experiments_file: Path = EXPERIMENTS_FILE,
    results_file: Path = RESULTS_FILE,
) -> list[dict]:
    experiments = load_benchmark_experiments(experiments_file)
    history_rows = load_benchmark_results(results_file)
    history_by_experiment: dict[str, list[dict]] = {}
    for item in history_rows:
        experiment_id = str(item.get("experiment") or "").strip()
        if not experiment_id:
            continue
        history_by_experiment.setdefault(experiment_id, []).append(item)

    summaries = []
    known_ids: set[str] = set()
    for experiment in experiments:
        experiment_id = str(experiment.get("id") or "").strip()
        known_ids.add(experiment_id)
        history = history_by_experiment.get(experiment_id, [])
        latest = _latest_history_result(history)
        counts = _status_counts(history)
        summaries.append(
            {
                "id": experiment_id,
                "target_key": str(experiment.get("target_key") or "").strip(),
                "target_label": str(experiment.get("target_label") or "").strip(),
                "goal": str(experiment.get("goal") or "").strip(),
                "configured_rounds": _coerce_round(experiment.get("rounds"), default=1),
                "status": str(experiment.get("status") or "").strip(),
                "stored_runs": len(_existing_results(experiment)),
                "history_runs": len(history),
                "best_score": max(_best_score(experiment), _best_score_from_history(history)),
                "latest_score": _coerce_score(latest.get("score"), default=0.0) if latest else 0.0,
                "latest_status": str(latest.get("status") or "").strip(),
                "latest_time": str(latest.get("time") or "").strip(),
                "latest_commit": str(latest.get("commit") or "").strip(),
                "keep_count": counts["keep"],
                "discard_count": counts["discard"],
                "skip_count": counts["skip"],
                "crash_count": counts["crash"],
                "orphaned": False,
            }
        )

    for experiment_id, history in history_by_experiment.items():
        if experiment_id in known_ids:
            continue
        latest = _latest_history_result(history)
        counts = _status_counts(history)
        summaries.append(
            {
                "id": experiment_id,
                "target_key": "",
                "target_label": "",
                "goal": "",
                "configured_rounds": 0,
                "status": "orphaned",
                "stored_runs": 0,
                "history_runs": len(history),
                "best_score": _best_score_from_history(history),
                "latest_score": _coerce_score(latest.get("score"), default=0.0) if latest else 0.0,
                "latest_status": str(latest.get("status") or "").strip(),
                "latest_time": str(latest.get("time") or "").strip(),
                "latest_commit": str(latest.get("commit") or "").strip(),
                "keep_count": counts["keep"],
                "discard_count": counts["discard"],
                "skip_count": counts["skip"],
                "crash_count": counts["crash"],
                "orphaned": True,
            }
        )

    return summaries


def archive_orphaned_benchmark_results(
    *,
    experiments_file: Path = EXPERIMENTS_FILE,
    results_file: Path = RESULTS_FILE,
    archive_file: Path | None = None,
) -> dict:
    archive_target = archive_file or results_file.with_name("results.orphaned.tsv")
    experiment_ids = {
        str(item.get("id") or "").strip()
        for item in load_benchmark_experiments(experiments_file)
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    rows = load_benchmark_results(results_file)
    tracked_rows = []
    orphaned_rows = []
    for row in rows:
        experiment_id = str(row.get("experiment") or "").strip()
        if experiment_id in experiment_ids:
            tracked_rows.append(row)
        else:
            orphaned_rows.append(row)

    if orphaned_rows:
        existing_archive_rows = load_benchmark_results(archive_target)
        _write_results_rows([*existing_archive_rows, *orphaned_rows], path=archive_target)
    _write_results_rows(tracked_rows, path=results_file)

    return {
        "results_file": str(results_file),
        "archive_file": str(archive_target),
        "tracked_rows_kept": len(tracked_rows),
        "orphaned_rows_archived": len(orphaned_rows),
        "experiment_ids": sorted(experiment_ids),
    }


def run_benchmark_experiment(
    experiment_id: str,
    *,
    rounds: int | None = None,
    experiments_file: Path = EXPERIMENTS_FILE,
    results_file: Path = RESULTS_FILE,
    verify_script: Path = VERIFY_SCRIPT_FILE,
    scorer=None,
    commit: str = "",
    now_provider=None,
) -> dict:
    rows = load_benchmark_experiments(experiments_file)
    wanted = str(experiment_id or "").strip()
    if not wanted:
        raise ValueError("experiment_id is required")

    target_index = -1
    for index, item in enumerate(rows):
        if str(item.get("id") or "").strip() == wanted:
            target_index = index
            break
    if target_index < 0:
        raise KeyError(experiment_id)

    experiment = dict(rows[target_index])
    target_key = str(experiment.get("target_key") or "").strip()
    goal = str(experiment.get("goal") or "").strip()
    run_rounds = max(1, _coerce_round(rounds, default=_coerce_round(experiment.get("rounds"), default=1)))
    current_best = _best_score(experiment)
    start_iteration = _next_iteration(experiment)
    commit_hash = str(commit or "").strip() or _resolve_git_commit()
    now_fn = now_provider or _now_iso
    score_fn = scorer or (lambda target, requested_goal: score_target(target, requested_goal, verify_script=verify_script))

    experiment_results = _existing_results(experiment)
    latest_time = ""
    best_result = experiment.get("best_result") if isinstance(experiment.get("best_result"), dict) else None
    run_results = []

    for offset in range(run_rounds):
        iteration = start_iteration + offset
        run_at = str(now_fn()).strip() or _now_iso()
        latest_time = run_at
        try:
            score = float(score_fn(target_key, goal))
            status = _status_for_score(score, current_best)
            error = ""
        except Exception as exc:
            score = 0.0
            status = "crash"
            error = str(exc)

        result_entry = {
            "round": iteration,
            "score": score,
            "status": status,
            "time": run_at,
            "commit": commit_hash,
        }
        if error:
            result_entry["error"] = error
        experiment_results.append(result_entry)
        run_results.append(result_entry)

        _append_results_row(
            {
                "experiment": wanted,
                "iteration": iteration,
                "commit": commit_hash,
                "score": score,
                "status": status,
                "description": goal or target_key,
                "time": run_at,
            },
            path=results_file,
        )

        if status == "keep":
            current_best = score
            best_result = dict(result_entry)

    experiment["results"] = experiment_results
    experiment["status"] = "completed"
    experiment["updated_at"] = latest_time
    experiment["completed_at"] = latest_time
    if best_result is not None:
        experiment["best_result"] = best_result
    rows[target_index] = experiment
    _save_json_list(experiments_file, rows)

    return {
        "experiment_id": wanted,
        "target_key": target_key,
        "goal": goal,
        "rounds_run": run_rounds,
        "results": run_results,
        "best_result": best_result,
        "verify_script": str(verify_script),
        "results_file": str(results_file),
        "experiments_file": str(experiments_file),
    }


def run_benchmark_suite(
    experiment_ids: list[str] | None = None,
    *,
    rounds: int | None = None,
    experiments_file: Path = EXPERIMENTS_FILE,
    results_file: Path = RESULTS_FILE,
    verify_script: Path = VERIFY_SCRIPT_FILE,
    scorer=None,
    commit: str = "",
    now_provider=None,
) -> dict:
    selected = select_benchmark_experiments(experiment_ids, path=experiments_file)
    reports = []
    status_totals = {"keep": 0, "discard": 0, "skip": 0, "crash": 0}
    best_scores = []

    for experiment in selected:
        report = run_benchmark_experiment(
            str(experiment.get("id") or "").strip(),
            rounds=rounds,
            experiments_file=experiments_file,
            results_file=results_file,
            verify_script=verify_script,
            scorer=scorer,
            commit=commit,
            now_provider=now_provider,
        )
        reports.append(report)
        best_result = report.get("best_result")
        if isinstance(best_result, dict):
            best_scores.append(_coerce_score(best_result.get("score")))
        for result in report.get("results", []):
            status = str(result.get("status") or "").strip().lower()
            if status in status_totals:
                status_totals[status] += 1

    return {
        "summary": {
            "total_experiments": len(reports),
            "total_runs": sum(len(item.get("results", [])) for item in reports),
            "experiment_ids": [str(item.get("experiment_id") or "").strip() for item in reports],
            "keep_count": status_totals["keep"],
            "discard_count": status_totals["discard"],
            "skip_count": status_totals["skip"],
            "crash_count": status_totals["crash"],
            "best_score": max(best_scores) if best_scores else 0.0,
            "results_file": str(results_file),
            "experiments_file": str(experiments_file),
            "verify_script": str(verify_script),
        },
        "results": reports,
    }


def _emit_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run benchmark experiments backed by lab/verify.py and results.tsv.")
    parser.add_argument("--list", action="store_true", help="List benchmark experiments and exit.")
    parser.add_argument("--summary", action="store_true", help="Summarize benchmark history from experiments.json and results.tsv.")
    parser.add_argument("--all", action="store_true", help="Run every benchmark experiment in experiments.json.")
    parser.add_argument(
        "--archive-orphaned",
        action="store_true",
        help="Move orphaned results.tsv rows into results.orphaned.tsv and keep only tracked experiment history.",
    )
    parser.add_argument("--experiment", default="", help="Benchmark experiment id from experiments.json.")
    parser.add_argument("--rounds", type=int, default=0, help="Optional round override.")
    parser.add_argument("--dry-run", action="store_true", help="Print the selected experiment without running scoring.")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 when any run crashes or skips.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.list:
        _emit_json(list_benchmark_experiments())
        return 0

    if args.summary:
        _emit_json(summarize_benchmark_results())
        return 0

    if args.archive_orphaned:
        _emit_json(archive_orphaned_benchmark_results())
        return 0

    if args.all and str(args.experiment or "").strip():
        parser.error("--experiment cannot be combined with --all")

    if args.all:
        selected = select_benchmark_experiments()
        if args.dry_run:
            payload = {
                "experiment_ids": [str(item.get("id") or "").strip() for item in selected],
                "experiments": [
                    {
                        "experiment_id": str(item.get("id") or "").strip(),
                        "target_key": str(item.get("target_key") or "").strip(),
                        "goal": str(item.get("goal") or "").strip(),
                        "rounds": max(1, _coerce_round(args.rounds, default=_coerce_round(item.get("rounds"), default=1))),
                    }
                    for item in selected
                ],
                "results_file": str(RESULTS_FILE),
                "experiments_file": str(EXPERIMENTS_FILE),
                "verify_script": str(VERIFY_SCRIPT_FILE),
            }
            _emit_json(payload)
            return 0

        payload = run_benchmark_suite(
            rounds=args.rounds or None,
        )
        _emit_json(payload)
        summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
        if args.strict and (int(summary.get("crash_count", 0)) > 0 or int(summary.get("skip_count", 0)) > 0):
            return 1
        return 0

    if not str(args.experiment or "").strip():
        parser.error("--experiment is required unless --list, --summary, --archive-orphaned, or --all is used")

    experiment = get_benchmark_experiment(args.experiment)
    if experiment is None:
        parser.error(f"Unknown benchmark experiment: {args.experiment}")

    if args.dry_run:
        payload = {
            "experiment_id": str(experiment.get("id") or "").strip(),
            "target_key": str(experiment.get("target_key") or "").strip(),
            "goal": str(experiment.get("goal") or "").strip(),
            "rounds": max(1, _coerce_round(args.rounds, default=_coerce_round(experiment.get("rounds"), default=1))),
            "verify_script": str(VERIFY_SCRIPT_FILE),
            "results_file": str(RESULTS_FILE),
            "experiments_file": str(EXPERIMENTS_FILE),
        }
        _emit_json(payload)
        return 0

    payload = run_benchmark_experiment(
        args.experiment,
        rounds=args.rounds or None,
    )
    _emit_json(payload)
    if args.strict and any(item.get("status") in {"crash", "skip"} for item in payload.get("results", [])):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
