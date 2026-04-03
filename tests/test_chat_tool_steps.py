import unittest

from routes.chat_tool_steps import (
    build_tool_done_label,
    build_tool_done_trace_detail,
    build_tool_execution_trace_detail,
)


class ChatToolStepTests(unittest.TestCase):
    def test_execution_detail_surfaces_fallback_and_parallel_batch(self):
        detail = build_tool_execution_trace_detail(
            tool_name="search_text",
            preview="router.py 里的 route 关键字",
            skill_display="调用技能",
            process_meta={
                "attempt_kind": "fallback",
                "previous_tool": "run_command",
                "parallel_index": 1,
                "parallel_size": 2,
            },
        )

        self.assertIn("search_text", detail)
        self.assertIn("run_command", detail)
        self.assertIn("并行批次 1/2", detail)
        self.assertIn("目标：router.py 里的 route 关键字", detail)

    def test_done_detail_and_label_surface_blocked_and_runtime_failure(self):
        blocked_label = build_tool_done_label(
            "技能失败",
            success=False,
            process_meta={"outcome_kind": "blocked"},
        )
        blocked_detail = build_tool_done_trace_detail(
            tool_name="open_target",
            preview="桌面应用",
            success=False,
            action_summary="",
            response="需要用户登录后继续",
            process_meta={"outcome_kind": "blocked", "reason": "blocked_by_user_takeover"},
        )
        self.assertEqual(blocked_label, "等待接手")
        self.assertIn("需要用户接手", blocked_detail)

        runtime_label = build_tool_done_label(
            "技能失败",
            success=False,
            process_meta={"outcome_kind": "runtime_failure"},
        )
        runtime_detail = build_tool_done_trace_detail(
            tool_name="sense_environment",
            preview="",
            success=False,
            action_summary="",
            response="boom",
            process_meta={"outcome_kind": "runtime_failure", "reason": "tool_executor_exception"},
        )
        self.assertEqual(runtime_label, "技能中断")
        self.assertIn("执行时抛异常了", runtime_detail)

    def test_done_detail_surfaces_retry_and_fallback_success(self):
        retry_detail = build_tool_done_trace_detail(
            tool_name="write_file",
            preview="index.html",
            success=False,
            action_summary="缺少 content",
            response="",
            process_meta={"attempt_kind": "retry", "outcome_kind": "arg_failure"},
        )
        fallback_success = build_tool_done_trace_detail(
            tool_name="search_text",
            preview="TODO",
            success=True,
            action_summary="找到 6 条结果",
            response="",
            process_meta={"attempt_kind": "fallback"},
        )

        self.assertIn("参数还不完整", retry_detail)
        self.assertIn("切换路径后完成", fallback_success)


if __name__ == "__main__":
    unittest.main()
