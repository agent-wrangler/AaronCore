import unittest
from unittest.mock import patch

from core.fs_protocol import build_operation_result
from tools.agent import open_target as open_target_module


class OpenTargetTests(unittest.TestCase):
    def test_open_target_propagates_auth_gate_from_browser_search(self):
        search_result = build_operation_result(
            "当前网页需要先完成登录或验证，暂时不能继续自动搜索：`AI`",
            expected_state="auth_cleared",
            observed_state="auth_required",
            drift_reason="auth_required",
            repair_hint="user_login_required",
            action_kind="open_url",
            target_kind="url",
            target="https://www.douyin.com",
            outcome="blocked",
            verification_mode="browser_search_submit",
            verification_detail="Douyin login popup",
        )

        with patch.object(
            open_target_module,
            "classify_open_target",
            return_value={"ok": True, "target_type": "url", "target": "https://www.douyin.com"},
        ), patch.object(
            open_target_module,
            "compose_remote_target_url",
            return_value={"url": "https://www.douyin.com", "search_term": "AI", "composed": False, "strategy": ""},
        ), patch.object(
            open_target_module,
            "_preflight_url_access",
            return_value={"available": True},
        ), patch.object(
            open_target_module,
            "_snapshot_before",
            return_value=(1, False),
        ), patch.object(
            open_target_module,
            "_open_url",
            return_value="chrome.exe",
        ), patch.object(
            open_target_module,
            "_verify_url_opened",
            return_value={"ok": True, "mode": "browser_started", "detail": "browser window opened"},
        ), patch.object(
            open_target_module,
            "submit_browser_search",
            return_value=search_result,
        ):
            result = open_target_module.execute("打开抖音搜索AI", {})

        self.assertEqual(result.get("drift", {}).get("reason"), "auth_required")
        self.assertEqual(result.get("drift", {}).get("repair_hint"), "user_login_required")
        self.assertEqual(result.get("state", {}).get("observed_state"), "auth_required")
        self.assertEqual(result.get("action", {}).get("outcome"), "blocked")
        self.assertIn("登录", result.get("reply", ""))


if __name__ == "__main__":
    unittest.main()
