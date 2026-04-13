import unittest
from unittest.mock import patch

from tools import runtime_quality_gate


class RuntimeQualityGateTests(unittest.TestCase):
    def test_build_quality_gate_report_defaults_to_replay_and_benchmark_summary(self):
        replay_payload = {
            "summary": {
                "total": 16,
                "passed": 16,
                "failed": 0,
                "suite_strict_default": True,
            },
            "results": [],
        }
        benchmark_rows = [
            {
                "id": "exp_demo",
                "orphaned": False,
                "best_score": 0.0,
                "keep_count": 0,
                "skip_count": 5,
                "crash_count": 0,
                "latest_status": "skip",
            },
            {
                "id": "exp_old",
                "orphaned": True,
                "best_score": 5.0,
                "keep_count": 1,
                "skip_count": 0,
                "crash_count": 0,
                "latest_status": "keep",
            },
        ]

        with (
            patch.object(runtime_quality_gate.live_llm_replay, "run_eval_suite", return_value=replay_payload),
            patch.object(runtime_quality_gate.benchmark_runner, "summarize_benchmark_results", return_value=benchmark_rows),
        ):
            report = runtime_quality_gate.build_quality_gate_report()

        self.assertEqual(report["summary"]["status"], "warn")
        self.assertTrue(report["summary"]["pass"])
        self.assertTrue(report["summary"]["strict_default"])
        self.assertEqual(report["summary"]["benchmark_mode"], "summary")
        self.assertEqual(report["summary"]["benchmark_warning_count"], 3)
        self.assertEqual(report["benchmark"]["summary"]["tracked_experiments"], 1)
        self.assertEqual(report["benchmark"]["summary"]["orphaned_experiments"], 1)

    def test_build_quality_gate_report_fails_when_benchmark_run_has_skip_or_crash(self):
        replay_payload = {
            "summary": {
                "total": 16,
                "passed": 16,
                "failed": 0,
                "suite_strict_default": True,
            },
            "results": [],
        }
        benchmark_payload = {
            "summary": {
                "total_experiments": 2,
                "total_runs": 2,
                "keep_count": 0,
                "discard_count": 0,
                "skip_count": 1,
                "crash_count": 1,
            },
            "results": [],
        }

        with (
            patch.object(runtime_quality_gate.live_llm_replay, "run_eval_suite", return_value=replay_payload),
            patch.object(runtime_quality_gate, "_build_benchmark_run_payload", return_value={**benchmark_payload, "mode": "run"}),
        ):
            report = runtime_quality_gate.build_quality_gate_report(benchmark_all=True)

        self.assertEqual(report["summary"]["status"], "fail")
        self.assertFalse(report["summary"]["pass"])
        self.assertEqual(report["summary"]["benchmark_failures"], 2)

    def test_build_quality_gate_report_supports_benchmark_dry_run(self):
        replay_payload = {
            "summary": {
                "total": 16,
                "passed": 16,
                "failed": 0,
                "suite_strict_default": True,
            },
            "results": [],
        }
        benchmark_payload = {
            "mode": "dry_run",
            "summary": {
                "total_experiments": 1,
                "experiment_ids": ["exp_demo"],
            },
            "results": [
                {
                    "experiment_id": "exp_demo",
                    "target_key": "skills/builtin/story.py",
                    "goal": "demo goal",
                    "rounds": 1,
                }
            ],
        }

        with (
            patch.object(runtime_quality_gate.live_llm_replay, "run_eval_suite", return_value=replay_payload),
            patch.object(runtime_quality_gate, "_build_benchmark_dry_run_payload", return_value=benchmark_payload),
        ):
            report = runtime_quality_gate.build_quality_gate_report(
                benchmark_experiment_ids=["exp_demo"],
                benchmark_dry_run=True,
            )

        self.assertEqual(report["summary"]["status"], "pass")
        self.assertEqual(report["summary"]["benchmark_mode"], "dry_run")
        self.assertEqual(report["benchmark"]["summary"]["experiment_ids"], ["exp_demo"])

    def test_build_quality_gate_report_hides_detail_rows_by_default(self):
        replay_payload = {
            "summary": {
                "total": 16,
                "passed": 16,
                "failed": 0,
                "suite_strict_default": True,
            },
            "results": [{"case": {"case_id": "demo"}}],
            "eval_suites": [],
        }
        benchmark_rows = [
            {
                "id": "exp_demo",
                "orphaned": False,
                "best_score": 100.0,
                "keep_count": 1,
                "skip_count": 0,
                "crash_count": 0,
                "latest_status": "keep",
            }
        ]

        with (
            patch.object(runtime_quality_gate.live_llm_replay, "run_eval_suite", return_value=replay_payload),
            patch.object(runtime_quality_gate.benchmark_runner, "summarize_benchmark_results", return_value=benchmark_rows),
        ):
            report = runtime_quality_gate.build_quality_gate_report()

        self.assertNotIn("results", report["replay"])
        self.assertNotIn("results", report["benchmark"])

    def test_build_quality_gate_report_includes_detail_rows_when_requested(self):
        replay_payload = {
            "summary": {
                "total": 16,
                "passed": 16,
                "failed": 0,
                "suite_strict_default": True,
            },
            "results": [{"case": {"case_id": "demo"}}],
            "eval_suites": [],
        }
        benchmark_rows = [
            {
                "id": "exp_demo",
                "orphaned": False,
                "best_score": 100.0,
                "keep_count": 1,
                "skip_count": 0,
                "crash_count": 0,
                "latest_status": "keep",
            }
        ]

        with (
            patch.object(runtime_quality_gate.live_llm_replay, "run_eval_suite", return_value=replay_payload),
            patch.object(runtime_quality_gate.benchmark_runner, "summarize_benchmark_results", return_value=benchmark_rows),
        ):
            report = runtime_quality_gate.build_quality_gate_report(include_details=True)

        self.assertEqual(report["replay"]["results"][0]["case"]["case_id"], "demo")
        self.assertEqual(report["benchmark"]["results"][0]["id"], "exp_demo")


if __name__ == "__main__":
    unittest.main()
