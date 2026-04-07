import asyncio
import unittest

from routes.chat_thinking_trace import ChatThinkingTraceState


class ChatThinkingTraceStateTests(unittest.TestCase):
    def test_emit_default_only_once(self):
        async def _run():
            events = []

            async def _trace(label, detail, status, **kwargs):
                payload = {"label": label, "detail": detail, "status": status, **kwargs}
                events.append(payload)
                return payload

            state = ChatThinkingTraceState("\u5e2e\u6211\u770b\u770b\u65e5\u5fd7")
            first = await state.emit_default(_trace)
            second = await state.emit_default(_trace)

            self.assertIsNotNone(first)
            self.assertIsNone(second)
            self.assertEqual(len(events), 1)
            self.assertTrue(state.trace_sent)
            self.assertEqual(events[0]["phase"], "thinking")

        asyncio.run(_run())

    def test_append_emit_and_reset(self):
        async def _run():
            events = []

            async def _trace(label, detail, status, **kwargs):
                payload = {"label": label, "detail": detail, "status": status, **kwargs}
                events.append(payload)
                return payload

            state = ChatThinkingTraceState("\u770b\u770b Openclaw \u7fa4\u80fd\u529b")
            state.update_meta(
                reason_kind="tool_decision",
                goal="sense_environment",
                decision_note="\u5148\u786e\u8ba4\u73af\u5883",
            )
            state.append_text("\u5148\u770b\u5f53\u524d\u73af\u5883\u3002")
            emitted = await state.emit(_trace, force=True)
            self.assertIsNotNone(emitted)
            self.assertEqual(events[-1]["reason_kind"], "tool_decision")
            self.assertIn("\u5148\u770b\u5f53\u524d\u73af\u5883", events[-1]["detail"])

            state.apply_preferred_reason_note(
                tool_name="sense_environment",
                preview="Agent Openclaw",
                reason_note="\u6211\u5148\u8bfb\u4e00\u4e0b\u5f53\u524d\u73af\u5883\uff0c\u518d\u7ee7\u7eed\u56de\u7b54\u3002",
            )
            replaced = await state.emit(_trace, force=True)
            self.assertIsNotNone(replaced)
            self.assertIn("\u6211\u5148\u8bfb\u4e00\u4e0b\u5f53\u524d\u73af\u5883", events[-1]["detail"])

            state.reset()
            self.assertFalse(state.trace_sent)
            self.assertEqual(state.trace_text, "")
            self.assertEqual(state.trace_emitted, "")
            self.assertEqual(state.reason_kind, "decision")
            self.assertEqual(state.decision_note, state.default_detail)
            self.assertEqual(state.expected_output, "")
            self.assertEqual(state.next_user_need, "")

        asyncio.run(_run())

    def test_followup_segment_rotates_step_key(self):
        async def _run():
            events = []

            async def _trace(label, detail, status, **kwargs):
                payload = {"label": label, "detail": detail, "status": status, **kwargs}
                events.append(payload)
                return payload

            state = ChatThinkingTraceState("\u7ee7\u7eed\u5e2e\u6211\u68c0\u67e5")
            await state.emit_default(_trace)
            state.queue_followup_segment()
            self.assertTrue(state.activate_pending_segment())
            self.assertEqual(state.step_key, "thinking:decision:2")
            self.assertFalse(state.trace_sent)
            self.assertEqual(state.trace_text, "")

            followup = await state.emit_default(_trace)
            self.assertIsNotNone(followup)
            self.assertEqual(events[-1]["step_key"], "thinking:decision:2")
            self.assertIn("\u6211\u5148\u63a5\u4f4f\u4e0a\u4e00\u6b65\u7ed3\u679c", events[-1]["detail"])

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
