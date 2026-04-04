import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import self_repair


class SelfRepairTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmpdir.name)
        self.repo_root = self.state_dir / "repo"
        self.repo_root.mkdir(parents=True, exist_ok=True)
        self.reports_file = self.state_dir / "self_repair_reports.json"
        self.feedback_rules_file = self.state_dir / "feedback_rules.json"
        self._patcher = patch.multiple(
            self_repair,
            ROOT=self.repo_root,
            STATE_DIR=self.state_dir,
            REPORTS_FILE=self.reports_file,
            FEEDBACK_RULES_FILE=self.feedback_rules_file,
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmpdir.cleanup()

    def _read_reports(self):
        if not self.reports_file.exists():
            return []
        return json.loads(self.reports_file.read_text(encoding="utf-8"))

    def _write_repo_file(self, rel_path: str, content: str) -> Path:
        path = self.repo_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_create_routing_report_points_to_active_route_files(self):
        rule_item = {
            "id": "rule_1",
            "scene": "routing",
            "problem": "wrong_skill_selected",
            "fix": "adjust_skill_routing_for_scene",
            "user_feedback": "不是这个技能",
            "last_question": "你自己什么时候会修改自己的代码",
            "last_answer": "刚才被带去编程游戏了",
        }

        with patch.object(
            self_repair,
            "run_targeted_tests",
            return_value={"ran": True, "all_passed": True, "test_runs": [{"pattern": "tests/test_feedback_classifier.py", "ok": True}], "duration_ms": 12},
        ):
            report = self_repair.create_self_repair_report(
                rule_item,
                config={"self_repair_apply_mode": "confirm", "allow_self_repair_test_run": True},
                run_validation=True,
            )

        paths = [item["path"] for item in report["candidate_files"]]

        self.assertIn("decision/routing/route_resolver.py", paths)
        self.assertIn("routes/chat.py", paths)
        self.assertIn("agent_final.py", paths)
        test_paths = [item["path"] for item in report["suggested_tests"]]
        self.assertIn("tests/test_feedback_classifier.py", test_paths)
        self.assertIn("tests/test_trace_payload.py", test_paths)
        self.assertEqual(report["status"], "awaiting_confirmation")
        self.assertTrue(report["validation"]["ran"])
        self.assertTrue(report["validation"]["all_passed"])
        self.assertEqual(len(self._read_reports()), 1)

    def test_story_length_feedback_targets_story_files_and_tests(self):
        report = self_repair.build_self_repair_report(
            {
                "id": "rule_2",
                "scene": "story",
                "problem": "length_too_short",
                "fix": "story_should_expand_when_user_requests_more",
                "user_feedback": "有点短",
                "last_question": "讲个故事",
            },
            config={"self_repair_apply_mode": "suggest"},
        )

        paths = [item["path"] for item in report["candidate_files"]]
        test_paths = [item["path"] for item in report["suggested_tests"]]

        self.assertIn("skills/builtin/story.py", paths)
        self.assertIn("agent_final.py", paths)
        self.assertIn("tests/test_story_skill.py", test_paths)
        self.assertIn("tests/test_story_routing.py", test_paths)
        self.assertEqual(report["status"], "proposal_ready")

    def test_find_feedback_rule_uses_latest_when_rule_id_missing(self):
        self.feedback_rules_file.write_text(
            json.dumps(
                [
                    {"id": "rule_old", "created_at": "2026-03-14T01:00:00"},
                    {"id": "rule_new", "created_at": "2026-03-14T02:00:00"},
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        latest = self_repair.find_feedback_rule()
        explicit = self_repair.find_feedback_rule("rule_old")

        self.assertEqual(latest["id"], "rule_new")
        self.assertEqual(explicit["id"], "rule_old")

    def test_apply_self_repair_report_writes_patch_when_validation_passes(self):
        target = self._write_repo_file("decision/routing/route_resolver.py", "def route():\n    return 'wrong'\n")
        report = {
            "id": "repair_apply_ok",
            "created_at": "2026-03-14T03:00:00",
            "updated_at": "2026-03-14T03:00:00",
            "apply_mode": "confirm",
            "status": "awaiting_confirmation",
            "candidate_files": [{"path": "decision/routing/route_resolver.py", "reason": "修这里"}],
            "suggested_tests": [{"path": "tests/test_feedback_classifier.py", "reason": "回归"}],
            "validation": {"ran": True, "all_passed": True, "test_runs": [], "duration_ms": 8},
        }
        self_repair.save_self_repair_report(report)

        with patch.object(
            self_repair,
            "generate_self_repair_patch_plan",
            return_value={
                "ok": True,
                "summary": "把错误返回值改正",
                "allowed_paths": ["decision/routing/route_resolver.py"],
                "edits": [
                    {
                        "path": "decision/routing/route_resolver.py",
                        "old": "return 'wrong'",
                        "new": "return 'fixed'",
                        "reason": "修正返回值",
                    }
                ],
            },
        ), patch.object(
            self_repair,
            "run_targeted_tests",
            return_value={"ran": True, "all_passed": True, "test_runs": [{"pattern": "test_feedback_classifier.py", "ok": True}], "duration_ms": 15},
        ):
            saved = self_repair.apply_self_repair_report("repair_apply_ok", config={}, run_validation=True)

        self.assertEqual(target.read_text(encoding="utf-8"), "def route():\n    return 'fixed'\n")
        self.assertEqual(saved["status"], "applied")
        self.assertEqual(saved["apply_result"]["status"], "applied")
        self.assertTrue((self.state_dir / "self_repair_backups" / "repair_apply_ok").exists())

    def test_apply_self_repair_report_rolls_back_when_validation_fails(self):
        target = self._write_repo_file("decision/routing/route_resolver.py", "def route():\n    return 'wrong'\n")
        report = {
            "id": "repair_apply_fail",
            "created_at": "2026-03-14T04:00:00",
            "updated_at": "2026-03-14T04:00:00",
            "apply_mode": "confirm",
            "status": "awaiting_confirmation",
            "candidate_files": [{"path": "decision/routing/route_resolver.py", "reason": "修这里"}],
            "suggested_tests": [{"path": "tests/test_feedback_classifier.py", "reason": "回归"}],
            "validation": {"ran": True, "all_passed": True, "test_runs": [], "duration_ms": 8},
        }
        self_repair.save_self_repair_report(report)

        with patch.object(
            self_repair,
            "generate_self_repair_patch_plan",
            return_value={
                "ok": True,
                "summary": "先试着改一下",
                "allowed_paths": ["decision/routing/route_resolver.py"],
                "edits": [
                    {
                        "path": "decision/routing/route_resolver.py",
                        "old": "return 'wrong'",
                        "new": "return 'broken'",
                        "reason": "模拟失败补丁",
                    }
                ],
            },
        ), patch.object(
            self_repair,
            "run_targeted_tests",
            return_value={"ran": True, "all_passed": False, "test_runs": [{"pattern": "test_feedback_classifier.py", "ok": False}], "duration_ms": 18},
        ):
            saved = self_repair.apply_self_repair_report("repair_apply_fail", config={}, run_validation=True)

        self.assertEqual(target.read_text(encoding="utf-8"), "def route():\n    return 'wrong'\n")
        self.assertEqual(saved["status"], "rolled_back_after_failed_validation")
        self.assertEqual(saved["apply_result"]["status"], "rolled_back_after_failed_validation")
        self.assertTrue(saved["apply_result"]["rolled_back"])

    def test_preview_self_repair_report_saves_preview_edits(self):
        self._write_repo_file("decision/routing/route_resolver.py", "def route():\n    return 'wrong'\n")
        report = {
            "id": "repair_preview_ok",
            "created_at": "2026-03-14T05:00:00",
            "updated_at": "2026-03-14T05:00:00",
            "apply_mode": "confirm",
            "status": "awaiting_confirmation",
            "candidate_files": [{"path": "decision/routing/route_resolver.py", "reason": "修这里"}],
            "suggested_tests": [{"path": "tests/test_feedback_classifier.py", "reason": "回归"}],
            "validation": {"ran": True, "all_passed": True, "test_runs": [], "duration_ms": 8},
        }
        self_repair.save_self_repair_report(report)

        with patch.object(
            self_repair,
            "generate_self_repair_patch_plan",
            return_value={
                "ok": True,
                "summary": "先预览一下最小修改",
                "allowed_paths": ["decision/routing/route_resolver.py"],
                "edits": [
                    {
                        "path": "decision/routing/route_resolver.py",
                        "old": "return 'wrong'",
                        "new": "return 'fixed'",
                        "reason": "修正返回值",
                    }
                ],
            },
        ):
            saved = self_repair.preview_self_repair_report("repair_preview_ok", config={})

        self.assertEqual(saved["status"], "awaiting_confirmation")
        self.assertEqual(saved["patch_preview"]["status"], "preview_ready")
        self.assertEqual(saved["patch_preview"]["summary"], "先预览一下最小修改")
        self.assertEqual(saved["patch_preview"]["edits"][0]["path"], "decision/routing/route_resolver.py")
        self.assertEqual(saved["patch_preview"]["risk_level"], "medium")
        self.assertFalse(saved["patch_preview"]["auto_apply_ready"])
        self.assertTrue(saved["patch_preview"]["confirmation_required"])

    def test_preview_self_repair_report_auto_applies_low_risk_patch(self):
        target = self._write_repo_file("skills/builtin/story.py", "def render_story():\n    return 'short'\n")
        report = {
            "id": "repair_auto_apply_ok",
            "created_at": "2026-03-14T06:00:00",
            "updated_at": "2026-03-14T06:00:00",
            "apply_mode": "confirm",
            "status": "awaiting_confirmation",
            "candidate_files": [{"path": "skills/builtin/story.py", "reason": "修故事回复"}],
            "suggested_tests": [{"path": "tests/test_story_skill.py", "reason": "回归"}],
            "validation": {"ran": True, "all_passed": True, "test_runs": [], "duration_ms": 8},
        }
        self_repair.save_self_repair_report(report)

        with patch.object(
            self_repair,
            "generate_self_repair_patch_plan",
            return_value={
                "ok": True,
                "summary": "把故事回复调整得更完整",
                "allowed_paths": ["skills/builtin/story.py"],
                "edits": [
                    {
                        "path": "skills/builtin/story.py",
                        "old": "return 'short'",
                        "new": "return 'full'",
                        "reason": "修正故事回复",
                    }
                ],
            },
        ), patch.object(
            self_repair,
            "run_targeted_tests",
            return_value={"ran": True, "all_passed": True, "test_runs": [{"pattern": "test_story_skill.py", "ok": True}], "duration_ms": 14},
        ):
            saved = self_repair.preview_self_repair_report(
                "repair_auto_apply_ok",
                config={},
                auto_apply=True,
                run_validation=True,
            )

        self.assertEqual(target.read_text(encoding="utf-8"), "def render_story():\n    return 'full'\n")
        self.assertEqual(saved["status"], "applied")
        self.assertEqual(saved["apply_result"]["status"], "applied")
        self.assertTrue(saved["apply_result"]["auto_applied"])
        self.assertEqual(saved["patch_preview"]["risk_level"], "low")
        self.assertTrue(saved["patch_preview"]["auto_apply_ready"])
        self.assertFalse(saved["patch_preview"]["confirmation_required"])

    def test_preview_self_repair_report_keeps_medium_risk_patch_for_confirmation(self):
        target = self._write_repo_file("decision/routing/route_resolver.py", "def route():\n    return 'wrong'\n")
        report = {
            "id": "repair_auto_apply_wait",
            "created_at": "2026-03-14T07:00:00",
            "updated_at": "2026-03-14T07:00:00",
            "apply_mode": "confirm",
            "status": "awaiting_confirmation",
            "candidate_files": [{"path": "decision/routing/route_resolver.py", "reason": "修路由"}],
            "suggested_tests": [{"path": "tests/test_feedback_classifier.py", "reason": "回归"}],
            "validation": {"ran": True, "all_passed": True, "test_runs": [], "duration_ms": 8},
        }
        self_repair.save_self_repair_report(report)

        with patch.object(
            self_repair,
            "generate_self_repair_patch_plan",
            return_value={
                "ok": True,
                "summary": "先把路由条目整理出来",
                "allowed_paths": ["decision/routing/route_resolver.py"],
                "edits": [
                    {
                        "path": "decision/routing/route_resolver.py",
                        "old": "return 'wrong'",
                        "new": "return 'fixed'",
                        "reason": "修正路由结果",
                    }
                ],
            },
        ):
            saved = self_repair.preview_self_repair_report(
                "repair_auto_apply_wait",
                config={},
                auto_apply=True,
                run_validation=True,
            )

        self.assertEqual(target.read_text(encoding="utf-8"), "def route():\n    return 'wrong'\n")
        self.assertEqual(saved["status"], "awaiting_confirmation")
        self.assertIsNone(saved.get("apply_result"))
        self.assertEqual(saved["patch_preview"]["risk_level"], "medium")
        self.assertFalse(saved["patch_preview"]["auto_apply_ready"])
        self.assertTrue(saved["patch_preview"]["confirmation_required"])


if __name__ == "__main__":
    unittest.main()
