import asyncio
import json
import unittest

from routes.chat_trace_state import ChatTraceState


class ChatTraceStateTests(unittest.TestCase):
    def test_trace_state_tracks_tool_step_and_waiting_context(self):
        async def _run():
            state = ChatTraceState()
            running = await state.trace(
                "调用技能",
                "正在搜索 TODO",
                "running",
                phase="tool",
                tool_name="search_text",
            )
            running_payload = json.loads(running["data"])
            self.assertEqual(running_payload["phase"], "tool")
            self.assertTrue(running_payload["step_key"].startswith("tool:"))
            self.assertEqual(state.active_tool_step_key, running_payload["step_key"])

            wait_label, wait_detail = state.build_waiting_step(2, tool_active=True)
            self.assertEqual(wait_label, "调用技能")
            self.assertIn("2s", wait_detail)

            done = await state.trace(
                "技能完成",
                "找到结果",
                "done",
                phase="tool",
                tool_name="search_text",
                step_key=state.active_tool_step_key,
            )
            done_payload = json.loads(done["data"])
            self.assertEqual(done_payload["step_key"], running_payload["step_key"])
            self.assertEqual(state.active_tool_step_key, "")

        asyncio.run(_run())

    def test_reset_progress_tracking_and_replace_collected_steps(self):
        async def _run():
            state = ChatTraceState()
            await state.trace("模型思考", "先分析一下", "running", phase="thinking")
            state.replace_collected_steps([{"step_key": "kept"}])
            self.assertEqual(state.collected_steps, [{"step_key": "kept"}])
            state.reset_progress_tracking()
            self.assertEqual(state.last_progress_label, "")
            self.assertEqual(state.last_progress_detail, "")
            self.assertEqual(state.last_progress_step_key, "")
            self.assertEqual(state.active_tool_step_key, "")
            self.assertEqual(state.step_key_counts, {})

        asyncio.run(_run())


    def test_parallel_tool_steps_keep_separate_step_keys(self):
        async def _run():
            state = ChatTraceState()
            first = await state.trace(
                "调用技能",
                "同步检查 A",
                "running",
                phase="tool",
                tool_name="list_files",
                parallel_group_id="parallel:1:1:batch",
                parallel_index=1,
                parallel_size=2,
                parallel_tools=["list_files", "read_file"],
            )
            second = await state.trace(
                "调用技能",
                "同步检查 B",
                "running",
                phase="tool",
                tool_name="read_file",
                parallel_group_id="parallel:1:1:batch",
                parallel_index=2,
                parallel_size=2,
                parallel_tools=["list_files", "read_file"],
            )
            first_payload = json.loads(first["data"])
            second_payload = json.loads(second["data"])
            self.assertNotEqual(first_payload["step_key"], second_payload["step_key"])
            self.assertTrue(first_payload["step_key"].startswith("parallel:1:1:batch:1:"))
            self.assertTrue(second_payload["step_key"].startswith("parallel:1:1:batch:2:"))

            first_done = await state.trace(
                "技能完成",
                "A 完成",
                "done",
                phase="tool",
                tool_name="list_files",
                parallel_group_id="parallel:1:1:batch",
                parallel_index=1,
                parallel_size=2,
                parallel_completed_count=1,
                parallel_success_count=1,
                parallel_failure_count=0,
            )
            first_done_payload = json.loads(first_done["data"])
            self.assertEqual(first_done_payload["step_key"], first_payload["step_key"])

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
