import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from tools import benchmark_runner


class BenchmarkRunnerTests(unittest.TestCase):
    def test_list_benchmark_experiments_reports_best_score(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            experiments_path = Path(tmpdir) / "experiments.json"
            experiments_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "exp_demo",
                            "target_key": "skills/builtin/story.py",
                            "goal": "demo goal",
                            "rounds": 2,
                            "results": [{"round": 1, "score": 61.0, "status": "keep"}],
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            rows = benchmark_runner.list_benchmark_experiments(path=experiments_path)

        self.assertEqual(rows[0]["id"], "exp_demo")
        self.assertEqual(rows[0]["best_score"], 61.0)

    def test_summarize_benchmark_results_combines_experiments_and_tsv_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            experiments_path = root / "experiments.json"
            results_path = root / "results.tsv"
            experiments_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "exp_demo",
                            "target_key": "skills/builtin/story.py",
                            "target_label": "故事技能",
                            "goal": "demo goal",
                            "rounds": 2,
                            "status": "completed",
                            "results": [{"round": 1, "score": 61.0, "status": "keep"}],
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            with results_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, delimiter="\t")
                writer.writerow(benchmark_runner.RESULTS_HEADER)
                writer.writerow(("exp_demo", 1, "abc111", 61.0, "keep", "demo goal", "2026-04-14T03:30:00"))
                writer.writerow(("exp_demo", 2, "abc222", 55.0, "discard", "demo goal", "2026-04-14T03:31:00"))
                writer.writerow(("exp_orphan", 1, "abc333", 20.0, "crash", "orphan goal", "2026-04-14T03:32:00"))

            rows = benchmark_runner.summarize_benchmark_results(
                experiments_file=experiments_path,
                results_file=results_path,
            )

        self.assertEqual(rows[0]["id"], "exp_demo")
        self.assertEqual(rows[0]["history_runs"], 2)
        self.assertEqual(rows[0]["latest_status"], "discard")
        self.assertEqual(rows[0]["latest_commit"], "abc222")
        self.assertEqual(rows[0]["keep_count"], 1)
        self.assertEqual(rows[0]["discard_count"], 1)
        self.assertEqual(rows[1]["id"], "exp_orphan")
        self.assertTrue(rows[1]["orphaned"])
        self.assertEqual(rows[1]["crash_count"], 1)

    def test_load_benchmark_results_supports_legacy_rows_without_commit_column(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            results_path = Path(tmpdir) / "results.tsv"
            with results_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, delimiter="\t")
                writer.writerow(benchmark_runner.RESULTS_HEADER)
                writer.writerow(("exp_demo", 1, 0, "skip", "empty", "2026-04-14T03:30:00"))

            rows = benchmark_runner.load_benchmark_results(results_path)

        self.assertEqual(rows[0]["experiment"], "exp_demo")
        self.assertEqual(rows[0]["commit"], "-")
        self.assertEqual(rows[0]["score"], 0.0)
        self.assertEqual(rows[0]["status"], "skip")
        self.assertEqual(rows[0]["description"], "empty")
        self.assertEqual(rows[0]["time"], "2026-04-14T03:30:00")

    def test_run_benchmark_experiment_appends_tsv_and_updates_best_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            experiments_path = root / "experiments.json"
            results_path = root / "results.tsv"
            experiments_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "exp_demo",
                            "target_key": "skills/builtin/story.py",
                            "goal": "demo goal",
                            "rounds": 2,
                            "results": [],
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            scores = iter((80.0, 70.0))
            report = benchmark_runner.run_benchmark_experiment(
                "exp_demo",
                rounds=2,
                experiments_file=experiments_path,
                results_file=results_path,
                scorer=lambda target_key, goal: next(scores),
                commit="abc123",
                now_provider=iter(("2026-04-14T03:30:00", "2026-04-14T03:31:00")).__next__,
            )

            stored = json.loads(experiments_path.read_text(encoding="utf-8"))
            with results_path.open("r", encoding="utf-8", newline="") as handle:
                tsv_rows = list(csv.DictReader(handle, delimiter="\t"))

        self.assertEqual(report["best_result"]["score"], 80.0)
        self.assertEqual(stored[0]["best_result"]["score"], 80.0)
        self.assertEqual(stored[0]["results"][0]["status"], "keep")
        self.assertEqual(stored[0]["results"][1]["status"], "discard")
        self.assertEqual(tsv_rows[0]["status"], "keep")
        self.assertEqual(tsv_rows[1]["status"], "discard")
        self.assertEqual(tsv_rows[0]["commit"], "abc123")

    def test_run_benchmark_suite_runs_all_selected_experiments(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            experiments_path = root / "experiments.json"
            results_path = root / "results.tsv"
            experiments_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "exp_demo_a",
                            "target_key": "skills/builtin/story.py",
                            "goal": "goal a",
                            "rounds": 1,
                            "results": [],
                        },
                        {
                            "id": "exp_demo_b",
                            "target_key": "skills/builtin/story.py",
                            "goal": "goal b",
                            "rounds": 1,
                            "results": [],
                        },
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            scores = iter((80.0, 0.0))
            report = benchmark_runner.run_benchmark_suite(
                experiments_file=experiments_path,
                results_file=results_path,
                scorer=lambda target_key, goal: next(scores),
                commit="abc123",
                now_provider=iter(("2026-04-14T03:30:00", "2026-04-14T03:31:00")).__next__,
            )

        self.assertEqual(report["summary"]["total_experiments"], 2)
        self.assertEqual(report["summary"]["total_runs"], 2)
        self.assertEqual(report["summary"]["keep_count"], 1)
        self.assertEqual(report["summary"]["skip_count"], 1)
        self.assertEqual(report["summary"]["best_score"], 80.0)

    def test_archive_orphaned_benchmark_results_moves_unknown_history_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            experiments_path = root / "experiments.json"
            results_path = root / "results.tsv"
            archive_path = root / "results.orphaned.tsv"
            experiments_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "exp_demo",
                            "target_key": "skills/builtin/story.py",
                            "goal": "demo goal",
                            "rounds": 1,
                            "results": [],
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            with results_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, delimiter="\t")
                writer.writerow(benchmark_runner.RESULTS_HEADER)
                writer.writerow(("exp_demo", 1, "abc111", 80.0, "keep", "demo goal", "2026-04-14T03:30:00"))
                writer.writerow(("exp_old", 1, "abc222", 10.0, "skip", "old goal", "2026-04-14T03:31:00"))

            report = benchmark_runner.archive_orphaned_benchmark_results(
                experiments_file=experiments_path,
                results_file=results_path,
                archive_file=archive_path,
            )
            kept_rows = benchmark_runner.load_benchmark_results(results_path)
            archived_rows = benchmark_runner.load_benchmark_results(archive_path)

        self.assertEqual(report["tracked_rows_kept"], 1)
        self.assertEqual(report["orphaned_rows_archived"], 1)
        self.assertEqual(len(kept_rows), 1)
        self.assertEqual(kept_rows[0]["experiment"], "exp_demo")
        self.assertEqual(len(archived_rows), 1)
        self.assertEqual(archived_rows[0]["experiment"], "exp_old")

    def test_lab_verify_score_target_handles_generic_json_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "payload.json"
            target.write_text(json.dumps({"demo": [1, 2, 3]}, ensure_ascii=False), encoding="utf-8")

            spec = importlib.util.spec_from_file_location(
                "lab_verify_test_module",
                Path(__file__).resolve().parents[1] / "state_data" / "runtime_store" / "lab" / "verify.py",
            )
            module = importlib.util.module_from_spec(spec)
            assert spec is not None and spec.loader is not None
            spec.loader.exec_module(module)

            score = module.score_target(str(target), "demo goal")

        self.assertGreater(score, 50.0)


if __name__ == "__main__":
    unittest.main()
