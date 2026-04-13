import unittest

from tasks import continuity as continuity_module


class TaskContinuityModeTests(unittest.TestCase):
    def test_infer_query_mode_uses_state_for_location_requests(self):
        mode = continuity_module.infer_task_query_mode(
            "where is that file now",
            goal="Patch the admin page target",
            current_step="Update the HTML target",
            fs_target="C:/repo/templates/admin/index.html",
        )

        self.assertEqual(mode, "locate")

    def test_query_about_location_needs_target_state(self):
        referred = continuity_module.query_clearly_refers_to_active_task(
            "where is that file now",
            goal="Patch the admin page target",
            current_step="Update the HTML target",
            fs_target="C:/repo/templates/admin/index.html",
            task_status="active",
        )

        self.assertTrue(referred)

    def test_continue_does_not_resume_blocked_task_without_more_state(self):
        referred = continuity_module.query_clearly_refers_to_active_task(
            "continue this",
            goal="Patch the admin page target",
            current_step="Wait for the final credential",
            current_step_status="waiting_user",
            blocker="Need the final credential from the user",
            phase="blocked",
            task_status="blocked",
        )

        self.assertFalse(referred)

    def test_bare_continue_does_not_resume_waiting_user_task_even_if_goal_starts_with_continue(self):
        referred = continuity_module.query_clearly_refers_to_active_task(
            "继续",
            goal="继续处理抖音登录后的采集",
            current_step="等待用户登录",
            current_step_status="waiting_user",
            blocker="需要你先完成抖音登录",
            phase="blocked",
            task_status="blocked",
            runtime_status="waiting_user",
        )

        self.assertFalse(referred)

    def test_bare_continue_does_not_bind_active_task(self):
        referred = continuity_module.query_clearly_refers_to_active_task(
            "continue",
            goal="Patch the admin page target",
            current_step="Update the HTML target",
            recent_progress="Updated the sidebar target in the admin template",
            task_status="active",
        )

        self.assertFalse(referred)

    def test_continue_with_strong_reference_can_bind_active_task(self):
        referred = continuity_module.query_clearly_refers_to_active_task(
            "continue the admin page target task",
            goal="Patch the admin page target",
            current_step="Update the HTML target",
            recent_progress="Updated the sidebar target in the admin template",
            task_status="active",
        )

        self.assertTrue(referred)

    def test_blocker_question_can_match_blocked_task(self):
        referred = continuity_module.query_clearly_refers_to_active_task(
            "what is blocking it right now",
            goal="Patch the admin page target",
            current_step="Wait for the final credential",
            current_step_status="waiting_user",
            blocker="Need the final credential from the user",
            phase="blocked",
            task_status="blocked",
        )

        self.assertTrue(referred)

    def test_interrupt_question_uses_interrupted_runtime_state(self):
        mode = continuity_module.infer_task_query_mode(
            "what interrupted it just now",
            goal="Patch the admin page target",
            current_step="Verify the page target",
            recent_progress="Read the current admin template",
            runtime_status="interrupted",
            next_action="resume_or_close",
            latest_event_summary="sense_environment interrupted before verification completed",
            task_status="active",
        )

        self.assertEqual(mode, "interrupt")

    def test_interrupt_question_can_match_interrupted_task(self):
        referred = continuity_module.query_clearly_refers_to_active_task(
            "what interrupted it just now",
            goal="Patch the admin page target",
            current_step="Verify the page target",
            recent_progress="Read the current admin template",
            runtime_status="interrupted",
            next_action="resume_or_close",
            latest_event_summary="sense_environment interrupted before verification completed",
            task_status="active",
        )

        self.assertTrue(referred)

    def test_status_phrase_to_which_step_is_not_misclassified_as_locate(self):
        mode = continuity_module.infer_task_query_mode(
            "现在到哪了",
            goal="继续整理 AaronCore 项目",
            current_step="整理分类结构",
            recent_progress="检查桌面文件",
            fs_target="C:/Users/36459/Desktop",
            task_status="active",
        )

        self.assertEqual(mode, "status")

    def test_retry_request_with_existing_goal_is_not_forced_into_reference_mode(self):
        mode = continuity_module.infer_task_query_mode(
            "再试试看 能看到桌面的文件夹吗",
            goal="看下桌面的文件夹有哪些",
            current_step="查看桌面目录",
            fs_target="C:/Users/36459/Desktop",
            task_status="active",
        )

        self.assertEqual(mode, "")

    def test_action_request_with_explicit_path_is_not_misclassified_as_locate(self):
        mode = continuity_module.infer_task_query_mode(
            r"C:/Users/36459/Desktop/切格瓦拉 这个文件 你去看下",
            goal="看下桌面的文件夹有哪些",
            current_step="查看桌面目录",
            fs_target="C:/Users/36459/Desktop",
            task_status="active",
        )

        self.assertEqual(mode, "")

    def test_cjk_fragment_overlap_can_bind_retry_request_to_active_task(self):
        referred = continuity_module.query_clearly_refers_to_active_task(
            "再试试看 能看到桌面的文件夹吗",
            goal="看下桌面的文件夹有哪些",
            current_step="查看桌面目录",
            fs_target="C:/Users/36459/Desktop",
            task_status="active",
        )

        self.assertTrue(referred)

    def test_resolve_task_for_goal_does_not_resume_on_bare_continue(self):
        active = {
            "title": "Patch the admin page target",
            "stage": "Update the HTML target",
            "status": "active",
            "memory": {"last_user_reference": "Patch the admin page target"},
        }

        resolved = continuity_module.resolve_task_for_goal(
            "development",
            "continue",
            get_latest_active_task_by_kind=lambda kind: active,
        )

        self.assertIsNone(resolved)

    def test_resolve_task_for_goal_allows_continue_with_reference(self):
        active = {
            "title": "Patch the admin page target",
            "stage": "Update the HTML target",
            "status": "active",
            "memory": {"last_user_reference": "Patch the admin page target"},
        }

        resolved = continuity_module.resolve_task_for_goal(
            "development",
            "continue the admin page target task",
            get_latest_active_task_by_kind=lambda kind: active,
        )

        self.assertEqual(resolved, active)

    def test_waiting_user_completion_update_switches_to_continue_mode(self):
        mode = continuity_module.infer_task_query_mode(
            "我登录好了",
            goal="继续处理抖音登录后的采集",
            current_step="等待用户登录",
            current_step_status="waiting_user",
            blocker="需要你先完成抖音登录",
            phase="blocked",
            task_status="blocked",
            runtime_status="waiting_user",
            next_action="wait_for_user",
        )

        self.assertEqual(mode, "continue")

    def test_waiting_user_completion_update_can_resume_blocked_task(self):
        referred = continuity_module.query_clearly_refers_to_active_task(
            "我登录好了",
            goal="继续处理抖音登录后的采集",
            current_step="等待用户登录",
            current_step_status="waiting_user",
            blocker="需要你先完成抖音登录",
            phase="blocked",
            task_status="blocked",
            runtime_status="waiting_user",
            next_action="wait_for_user",
        )

        self.assertTrue(referred)

    def test_waiting_user_negative_completion_update_does_not_resume(self):
        referred = continuity_module.query_clearly_refers_to_active_task(
            "我还没登录好",
            goal="继续处理抖音登录后的采集",
            current_step="等待用户登录",
            current_step_status="waiting_user",
            blocker="需要你先完成抖音登录",
            phase="blocked",
            task_status="blocked",
            runtime_status="waiting_user",
            next_action="wait_for_user",
        )

        self.assertFalse(referred)

    def test_verify_failed_retry_request_switches_to_continue_mode(self):
        mode = continuity_module.infer_task_query_mode(
            "再试一下修这个",
            goal="继续修 AaronCore continuity",
            current_step="验证修复结果",
            recent_progress="检查 continuity 链路",
            phase="verify",
            task_status="active",
            runtime_status="verify_failed",
            next_action="retry_or_close",
            verification_status="failed",
            verification_detail="continuity 还会被一句闲聊误续接",
        )

        self.assertEqual(mode, "continue")

    def test_verify_failed_retry_request_can_resume_active_task(self):
        referred = continuity_module.query_clearly_refers_to_active_task(
            "再试一下修这个",
            goal="继续修 AaronCore continuity",
            current_step="验证修复结果",
            recent_progress="检查 continuity 链路",
            phase="verify",
            task_status="active",
            runtime_status="verify_failed",
            next_action="retry_or_close",
            verification_status="failed",
            verification_detail="continuity 还会被一句闲聊误续接",
        )

        self.assertTrue(referred)


if __name__ == "__main__":
    unittest.main()
