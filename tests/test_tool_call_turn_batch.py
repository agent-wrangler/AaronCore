import json
import threading
import time
import unittest
from unittest.mock import patch

import core.reply_formatter as reply_formatter_module
from decision.tool_runtime import batch as batch_module
from decision.tool_runtime.ledger import ToolCallRecord


class ToolCallTurnBatchTests(unittest.TestCase):
    def test_append_tool_batch_to_messages_repairs_missing_ids_and_missing_tool_results(self):
        outcome = batch_module.ToolCallBatchOutcome(state=batch_module.create_tool_call_batch_state())
        outcome.tool_calls = [
            {
                "type": "function",
                "function": {
                    "name": "folder_explore",
                    "arguments": json.dumps({"query": "src"}, ensure_ascii=False),
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_text",
                    "arguments": json.dumps({"query": "TODO"}, ensure_ascii=False),
                },
            },
        ]
        outcome.records = [
            ToolCallRecord(
                call_id="folder_explore_1",
                tool_name="folder_explore",
                status="completed",
                success=True,
                response="folder ok",
                action_summary="folder ok",
                order=0,
            ),
            ToolCallRecord(
                call_id="search_text_2",
                tool_name="search_text",
                status="completed",
                success=True,
                response="search ok",
                action_summary="search ok",
                order=1,
            ),
        ]
        outcome.tool_messages = [
            {"role": "tool", "tool_call_id": "", "content": "folder ok"},
        ]

        messages = []
        batch_module.append_tool_batch_to_messages(messages, outcome, bundle={})

        assistant_message = next(message for message in messages if message.get("role") == "assistant")
        self.assertEqual(
            [item.get("id") for item in assistant_message.get("tool_calls") or []],
            ["folder_explore_1", "search_text_2"],
        )
        tool_messages = [message for message in messages if message.get("role") == "tool"]
        self.assertEqual(
            [(message.get("tool_call_id"), message.get("content")) for message in tool_messages],
            [("folder_explore_1", "folder ok"), ("search_text_2", "search ok")],
        )

    def test_append_tool_batch_to_messages_drops_orphan_and_duplicate_tool_results(self):
        outcome = batch_module.ToolCallBatchOutcome(state=batch_module.create_tool_call_batch_state())
        outcome.tool_calls = [
            {
                "id": "call_a",
                "type": "function",
                "function": {
                    "name": "folder_explore",
                    "arguments": json.dumps({"query": "src"}, ensure_ascii=False),
                },
            }
        ]
        outcome.records = [
            ToolCallRecord(
                call_id="call_a",
                tool_name="folder_explore",
                status="completed",
                success=True,
                response="folder ok",
                action_summary="folder ok",
                order=0,
            )
        ]
        outcome.tool_messages = [
            {"role": "tool", "tool_call_id": "call_a", "content": "ok"},
            {"role": "tool", "tool_call_id": "call_a", "content": "ok with more detail"},
            {"role": "tool", "tool_call_id": "orphan_call", "content": "should drop"},
        ]

        messages = []
        batch_module.append_tool_batch_to_messages(messages, outcome, bundle={})

        tool_messages = [message for message in messages if message.get("role") == "tool"]
        self.assertEqual(tool_messages, [{"role": "tool", "tool_call_id": "call_a", "content": "ok with more detail"}])

    def test_unified_reply_with_tools_runs_safe_batch_calls_in_parallel(self):
        active = {"count": 0}
        overlap_seen = threading.Event()
        lock = threading.Lock()

        def fake_llm_call(_cfg, _messages, **_kwargs):
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_parallel_1",
                        "type": "function",
                        "function": {
                            "name": "folder_explore",
                            "arguments": json.dumps({"query": "src"}, ensure_ascii=False),
                        },
                    },
                    {
                        "id": "call_parallel_2",
                        "type": "function",
                        "function": {
                            "name": "weather",
                            "arguments": json.dumps({"city": "Shanghai"}, ensure_ascii=False),
                        },
                    },
                ],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            }

        def fake_tool_executor(name, args, _context):
            with lock:
                active["count"] += 1
                if active["count"] >= 2:
                    overlap_seen.set()
            time.sleep(0.05)
            with lock:
                active["count"] -= 1
            return {
                "success": True,
                "response": f"{name} ok",
                "meta": {"action": {"action_kind": name, "target_kind": "mixed"}},
            }

        bundle = {
            "user_input": "先看目录再查天气",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call", side_effect=[fake_llm_call(None, None), {"content": "Done.", "usage": {}}]), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"):
            result = reply_formatter_module.unified_reply_with_tools(bundle, [], fake_tool_executor)

        self.assertTrue(overlap_seen.is_set())
        self.assertEqual(result.get("tools_used"), ["folder_explore", "weather"])
        self.assertEqual(result.get("reply"), "Done.")

    def test_unified_reply_with_tools_keeps_safe_batch_calls_serial_outside_inspect_lane(self):
        active = {"count": 0}
        overlap_seen = threading.Event()
        lock = threading.Lock()

        def fake_llm_call(_cfg, _messages, **_kwargs):
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_verify_1",
                        "type": "function",
                        "function": {
                            "name": "folder_explore",
                            "arguments": json.dumps({"query": "src"}, ensure_ascii=False),
                        },
                    },
                    {
                        "id": "call_verify_2",
                        "type": "function",
                        "function": {
                            "name": "search_text",
                            "arguments": json.dumps({"query": "TODO"}, ensure_ascii=False),
                        },
                    },
                ],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            }

        def fake_tool_executor(name, args, _context):
            with lock:
                active["count"] += 1
                if active["count"] >= 2:
                    overlap_seen.set()
            time.sleep(0.05)
            with lock:
                active["count"] -= 1
            return {
                "success": True,
                "response": f"{name} ok",
                "meta": {"action": {"action_kind": name, "target_kind": "file"}},
            }

        bundle = {
            "user_input": "先检查一下目录和 TODO",
            "l1": [],
            "l2": {
                "working_state": {
                    "execution_lane": "verify",
                    "current_step_task": {
                        "task_id": "step_verify",
                        "title": "Run verification checks",
                        "status": "in_progress",
                        "execution_lane": "verify",
                    },
                }
            },
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call", side_effect=[fake_llm_call(None, None), {"content": "Done.", "usage": {}}]), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"):
            result = reply_formatter_module.unified_reply_with_tools(bundle, [], fake_tool_executor)

        self.assertFalse(overlap_seen.is_set())
        self.assertEqual(result.get("tools_used"), ["folder_explore", "search_text"])
        self.assertEqual(result.get("reply"), "Done.")

    def test_unified_reply_with_tools_keeps_write_batches_serial(self):
        active = {"count": 0}
        overlap_seen = threading.Event()
        lock = threading.Lock()

        def fake_llm_call(_cfg, _messages, **_kwargs):
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_serial_1",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": json.dumps({"file_path": "a.txt", "content": "a"}, ensure_ascii=False),
                        },
                    },
                    {
                        "id": "call_serial_2",
                        "type": "function",
                        "function": {
                            "name": "folder_explore",
                            "arguments": json.dumps({"query": "src"}, ensure_ascii=False),
                        },
                    },
                ],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            }

        def fake_tool_executor(name, args, _context):
            with lock:
                active["count"] += 1
                if active["count"] >= 2:
                    overlap_seen.set()
            time.sleep(0.05)
            with lock:
                active["count"] -= 1
            return {
                "success": True,
                "response": f"{name} ok",
                "meta": {"action": {"action_kind": name, "target_kind": "mixed"}},
            }

        bundle = {
            "user_input": "先写文件再看目录",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call", side_effect=[fake_llm_call(None, None), {"content": "Done.", "usage": {}}]), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"):
            result = reply_formatter_module.unified_reply_with_tools(bundle, [], fake_tool_executor)

        self.assertFalse(overlap_seen.is_set())
        self.assertEqual(result.get("tools_used"), ["write_file", "folder_explore"])
        self.assertEqual(result.get("reply"), "Done.")

    def test_unified_reply_with_tools_executes_multiple_tool_calls_in_same_non_stream_turn(self):
        seen_messages = []
        call_count = {"value": 0}
        executed = []

        def fake_llm_call(_cfg, messages, **_kwargs):
            seen_messages.append(messages)
            call_count["value"] += 1
            if call_count["value"] == 1:
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_batch_1",
                            "type": "function",
                            "function": {
                                "name": "folder_explore",
                                "arguments": json.dumps({"query": "a.py"}, ensure_ascii=False),
                            },
                        },
                        {
                            "id": "call_batch_2",
                            "type": "function",
                            "function": {
                                "name": "search_text",
                                "arguments": json.dumps({"query": "TODO"}, ensure_ascii=False),
                            },
                        },
                    ],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 2},
                    "reasoning_details": [{"text": "Inspect both sources first."}],
                }
            return {
                "content": "Done.",
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            }

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {
                "success": True,
                "response": f"{name} ok",
                "meta": {"action": {"action_kind": name, "target_kind": "file"}},
            }

        bundle = {
            "user_input": "看看 a.py 的结构并搜一个 TODO",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call", side_effect=fake_llm_call), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"):
            result = reply_formatter_module.unified_reply_with_tools(bundle, [], fake_tool_executor)

        self.assertEqual(call_count["value"], 2)
        self.assertEqual([name for name, _args in executed], ["folder_explore", "search_text"])
        assistant_messages = [
            message
            for message in seen_messages[1]
            if isinstance(message, dict) and message.get("role") == "assistant" and message.get("tool_calls")
        ]
        self.assertEqual(len(assistant_messages[0]["tool_calls"]), 2)
        tool_messages = [
            message
            for message in seen_messages[1]
            if isinstance(message, dict) and message.get("role") == "tool"
        ]
        self.assertEqual(len(tool_messages), 2)
        self.assertEqual(result.get("tools_used"), ["folder_explore", "search_text"])
        self.assertEqual(result.get("action_count"), 2)
        self.assertTrue(result.get("batch_mode"))
        self.assertEqual(result.get("reply"), "Done.")

    def test_unified_reply_with_tools_retries_non_stream_followup_handoff_before_closing(self):
        call_count = {"value": 0}
        executed = []

        def fake_llm_call(_cfg, _messages, **_kwargs):
            call_count["value"] += 1
            if call_count["value"] == 1:
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_followup_search",
                            "type": "function",
                            "function": {
                                "name": "search_text",
                                "arguments": json.dumps({"query": "TODO"}, ensure_ascii=False),
                            },
                        }
                    ],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 2},
                }
            if call_count["value"] == 2:
                return {
                    "content": "我先继续处理下一步。",
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2},
                }
            if call_count["value"] == 3:
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_followup_write",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": json.dumps({"file_path": "result.txt", "content": "done"}, ensure_ascii=False),
                            },
                        }
                    ],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2},
                }
            return {
                "content": "Done.",
                "usage": {"prompt_tokens": 2, "completion_tokens": 1},
            }

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {
                "success": True,
                "response": f"{name} ok",
                "meta": {"action": {"action_kind": name, "target_kind": "file"}},
            }

        bundle = {
            "user_input": "继续把结果落到文件里",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
            "max_turns": 5,
        }

        with patch.object(reply_formatter_module, "_llm_call", side_effect=fake_llm_call), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"):
            result = reply_formatter_module.unified_reply_with_tools(bundle, [], fake_tool_executor)

        self.assertEqual(call_count["value"], 4)
        self.assertEqual([name for name, _args in executed], ["search_text", "write_file"])
        self.assertEqual(result.get("tools_used"), ["search_text", "write_file"])
        self.assertEqual(result.get("reply"), "Done.")

    def test_unified_reply_with_tools_budgets_tool_result_context_per_tool_and_per_batch(self):
        seen_messages = []
        call_count = {"value": 0}

        def fake_llm_call(_cfg, messages, **_kwargs):
            seen_messages.append(messages)
            call_count["value"] += 1
            if call_count["value"] == 1:
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_budget_1",
                            "type": "function",
                            "function": {
                                "name": "folder_explore",
                                "arguments": json.dumps({"query": "alpha"}, ensure_ascii=False),
                            },
                        },
                        {
                            "id": "call_budget_2",
                            "type": "function",
                            "function": {
                                "name": "search_text",
                                "arguments": json.dumps({"query": "beta"}, ensure_ascii=False),
                            },
                        },
                    ],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 2},
                }
            return {
                "content": "Done.",
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            }

        def fake_tool_executor(name, _args, _context):
            return {
                "success": True,
                "response": f"{name} result " + ("X" * 180),
                "meta": {"action": {"action_kind": name, "target_kind": "file"}},
            }

        bundle = {
            "user_input": "看两个很长的工具结果",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
            "tool_runtime": {
                "tool_result_max_chars": 150,
                "tool_batch_result_budget_chars": 240,
            },
        }

        with patch.object(reply_formatter_module, "_llm_call", side_effect=fake_llm_call), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"):
            reply_formatter_module.unified_reply_with_tools(bundle, [], fake_tool_executor)

        tool_messages = [
            message
            for message in seen_messages[1]
            if isinstance(message, dict) and message.get("role") == "tool"
        ]
        self.assertEqual(len(tool_messages), 2)
        self.assertTrue(all(len(str(message.get("content") or "")) <= 150 for message in tool_messages))
        self.assertTrue(sum(len(str(message.get("content") or "")) for message in tool_messages) <= 240)
        self.assertTrue(
            all("[tool result truncated for context]" in str(message.get("content") or "") for message in tool_messages)
        )

    def test_unified_reply_with_tools_stream_executes_multiple_tool_calls_in_same_turn(self):
        seen_messages = []
        executed = []

        def fake_stream(_cfg, messages, **_kwargs):
            seen_messages.append(messages)
            has_tool_result = any(isinstance(message, dict) and message.get("role") == "tool" for message in messages)
            if not has_tool_result:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_stream_batch_1",
                            "type": "function",
                            "function": {
                                "name": "folder_explore",
                                "arguments": json.dumps({"query": "a.py"}, ensure_ascii=False),
                            },
                        },
                        {
                            "id": "call_stream_batch_2",
                            "type": "function",
                            "function": {
                                "name": "search_text",
                                "arguments": json.dumps({"query": "TODO"}, ensure_ascii=False),
                            },
                        },
                    ]
                }
                yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 2}}
                return

            yield "Done."
            yield {"_usage": {"prompt_tokens": 4, "completion_tokens": 2}}

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {
                "success": True,
                "response": f"{name} ok",
                "meta": {"action": {"action_kind": name, "target_kind": "file"}},
            }

        bundle = {
            "user_input": "先看 a.py 再搜 TODO",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_llm_call", lambda *_a, **_k: {"content": "", "usage": {}}
        ), patch.object(reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], fake_tool_executor))

        self.assertEqual([name for name, _args in executed], ["folder_explore", "search_text"])
        executing_events = [
            chunk
            for chunk in chunks
            if isinstance(chunk, dict) and chunk.get("_tool_call", {}).get("executing")
        ]
        self.assertEqual(len(executing_events), 2)
        self.assertEqual(executing_events[0].get("_tool_call", {}).get("process_meta", {}).get("parallel_size"), 2)
        executing_group_ids = {
            event.get("_tool_call", {}).get("process_meta", {}).get("parallel_group_id")
            for event in executing_events
        }
        self.assertEqual(len(executing_group_ids), 1)
        self.assertTrue(next(iter(executing_group_ids)))
        assistant_messages = [
            message
            for message in seen_messages[1]
            if isinstance(message, dict) and message.get("role") == "assistant" and message.get("tool_calls")
        ]
        self.assertEqual(len(assistant_messages[0]["tool_calls"]), 2)
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertEqual(done.get("tools_used"), ["folder_explore", "search_text"])
        self.assertEqual(done.get("action_count"), 2)
        self.assertTrue(done.get("batch_mode"))
        self.assertEqual(done.get("tool_used"), "search_text")

    def test_unified_reply_with_tools_stream_keeps_parallel_grouping_for_explicit_inspect_lane(self):
        seen_messages = []
        executed = []

        def fake_stream(_cfg, messages, **_kwargs):
            seen_messages.append(messages)
            has_tool_result = any(isinstance(message, dict) and message.get("role") == "tool" for message in messages)
            if not has_tool_result:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_stream_inspect_1",
                            "type": "function",
                            "function": {
                                "name": "folder_explore",
                                "arguments": json.dumps({"query": "a.py"}, ensure_ascii=False),
                            },
                        },
                        {
                            "id": "call_stream_inspect_2",
                            "type": "function",
                            "function": {
                                "name": "search_text",
                                "arguments": json.dumps({"query": "TODO"}, ensure_ascii=False),
                            },
                        },
                    ]
                }
                yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 2}}
                return

            yield "Done."
            yield {"_usage": {"prompt_tokens": 4, "completion_tokens": 2}}

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {
                "success": True,
                "response": f"{name} ok",
                "meta": {"action": {"action_kind": name, "target_kind": "file"}},
            }

        bundle = {
            "user_input": "先看看 a.py 再搜 TODO",
            "l1": [],
            "l2": {
                "working_state": {
                    "execution_lane": "inspect",
                    "current_step_task": {
                        "task_id": "step_inspect",
                        "title": "Inspect the current chain",
                        "status": "in_progress",
                        "execution_lane": "inspect",
                    },
                }
            },
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_llm_call", lambda *_a, **_k: {"content": "", "usage": {}}
        ), patch.object(reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], fake_tool_executor))

        self.assertEqual([name for name, _args in executed], ["folder_explore", "search_text"])
        executing_events = [
            chunk
            for chunk in chunks
            if isinstance(chunk, dict) and chunk.get("_tool_call", {}).get("executing")
        ]
        self.assertEqual(len(executing_events), 2)
        self.assertEqual(executing_events[0].get("_tool_call", {}).get("process_meta", {}).get("execution_lane"), "inspect")
        self.assertEqual(executing_events[0].get("_tool_call", {}).get("process_meta", {}).get("parallel_size"), 2)
        executing_group_ids = {
            event.get("_tool_call", {}).get("process_meta", {}).get("parallel_group_id")
            for event in executing_events
        }
        self.assertEqual(len(executing_group_ids), 1)
        self.assertTrue(next(iter(executing_group_ids)))
        assistant_messages = [
            message
            for message in seen_messages[1]
            if isinstance(message, dict) and message.get("role") == "assistant" and message.get("tool_calls")
        ]
        self.assertEqual(len(assistant_messages[0]["tool_calls"]), 2)
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertEqual(done.get("tools_used"), ["folder_explore", "search_text"])

    def test_unified_reply_with_tools_stream_replays_parallel_done_events_by_completion_order(self):
        def fake_stream(_cfg, messages, **_kwargs):
            has_tool_result = any(isinstance(message, dict) and message.get("role") == "tool" for message in messages)
            if not has_tool_result:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_parallel_slow",
                            "type": "function",
                            "function": {
                                "name": "folder_explore",
                                "arguments": json.dumps({"query": "slow"}, ensure_ascii=False),
                            },
                        },
                        {
                            "id": "call_parallel_fast",
                            "type": "function",
                            "function": {
                                "name": "search_text",
                                "arguments": json.dumps({"query": "fast"}, ensure_ascii=False),
                            },
                        },
                    ]
                }
                yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 2}}
                return

            yield "Done."
            yield {"_usage": {"prompt_tokens": 4, "completion_tokens": 2}}

        def fake_tool_executor(name, _args, _context):
            if name == "folder_explore":
                time.sleep(0.05)
            else:
                time.sleep(0.01)
            return {
                "success": True,
                "response": f"{name} ok",
                "meta": {"action": {"action_kind": name, "target_kind": "file"}},
            }

        bundle = {
            "user_input": "并行读两个目标",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_llm_call", lambda *_a, **_k: {"content": "", "usage": {}}
        ), patch.object(reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], fake_tool_executor))

        done_events = [
            chunk
            for chunk in chunks
            if isinstance(chunk, dict) and chunk.get("_tool_call", {}).get("done")
        ]
        self.assertEqual(
            [event.get("_tool_call", {}).get("process_meta", {}).get("parallel_completed_count") for event in done_events[:2]],
            [1, 2],
        )
        self.assertEqual(
            [event.get("_tool_call", {}).get("name") for event in done_events[:2]],
            ["search_text", "folder_explore"],
        )

    def test_unified_reply_with_tools_stream_closes_missing_parallel_results_before_fatal_closeout(self):
        def fake_stream(_cfg, messages, **_kwargs):
            has_tool_result = any(isinstance(message, dict) and message.get("role") == "tool" for message in messages)
            if not has_tool_result:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_parallel_fail",
                            "type": "function",
                            "function": {
                                "name": "folder_explore",
                                "arguments": json.dumps({"query": "slow"}, ensure_ascii=False),
                            },
                        },
                        {
                            "id": "call_parallel_ok",
                            "type": "function",
                            "function": {
                                "name": "search_text",
                                "arguments": json.dumps({"query": "fast"}, ensure_ascii=False),
                            },
                        },
                    ]
                }
                yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 2}}
                return

            yield "Done."
            yield {"_usage": {"prompt_tokens": 4, "completion_tokens": 2}}

        def fake_tool_executor(name, _args, _context):
            if name == "folder_explore":
                time.sleep(0.02)
                raise RuntimeError("boom")
            time.sleep(0.01)
            return {
                "success": True,
                "response": f"{name} ok",
                "meta": {"action": {"action_kind": name, "target_kind": "file"}},
            }

        bundle = {
            "user_input": "并行里一个成功一个炸掉",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_llm_call", lambda *_a, **_k: {"content": "", "usage": {}}
        ), patch.object(reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], fake_tool_executor))

        done_events = [
            chunk
            for chunk in chunks
            if isinstance(chunk, dict) and chunk.get("_tool_call", {}).get("done")
        ]
        self.assertEqual(len(done_events), 2)
        self.assertEqual(
            [event.get("_tool_call", {}).get("process_meta", {}).get("parallel_completed_count") for event in done_events],
            [1, 2],
        )
        self.assertEqual(done_events[0].get("_tool_call", {}).get("name"), "search_text")
        self.assertTrue(done_events[0].get("_tool_call", {}).get("success"))
        self.assertEqual(done_events[1].get("_tool_call", {}).get("name"), "folder_explore")
        self.assertFalse(done_events[1].get("_tool_call", {}).get("success"))
        self.assertTrue(done_events[1].get("_tool_call", {}).get("synthetic"))
        self.assertEqual(done_events[1].get("_tool_call", {}).get("reason"), "tool_executor_exception")
        final_done = next(chunk for chunk in reversed(chunks) if isinstance(chunk, dict) and chunk.get("_done"))
        self.assertEqual(final_done.get("action_count"), 2)
        self.assertTrue(final_done.get("batch_mode"))

    def test_unified_reply_with_tools_stream_closes_later_prepared_calls_after_parallel_exception(self):
        def fake_stream(_cfg, messages, **_kwargs):
            has_tool_result = any(isinstance(message, dict) and message.get("role") == "tool" for message in messages)
            if not has_tool_result:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_parallel_fail",
                            "type": "function",
                            "function": {
                                "name": "folder_explore",
                                "arguments": json.dumps({"query": "slow"}, ensure_ascii=False),
                            },
                        },
                        {
                            "id": "call_parallel_ok",
                            "type": "function",
                            "function": {
                                "name": "search_text",
                                "arguments": json.dumps({"query": "fast"}, ensure_ascii=False),
                            },
                        },
                        {
                            "id": "call_after_parallel",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": json.dumps({"file_path": "a.txt", "content": "x"}, ensure_ascii=False),
                            },
                        },
                    ]
                }
                yield {"_usage": {"prompt_tokens": 5, "completion_tokens": 2}}
                return

            yield "Done."
            yield {"_usage": {"prompt_tokens": 4, "completion_tokens": 2}}

        def fake_tool_executor(name, _args, _context):
            if name == "folder_explore":
                time.sleep(0.02)
                raise RuntimeError("boom")
            if name == "write_file":
                raise AssertionError("write_file should not execute after earlier parallel failure")
            time.sleep(0.01)
            return {
                "success": True,
                "response": f"{name} ok",
                "meta": {"action": {"action_kind": name, "target_kind": "file"}},
            }

        bundle = {
            "user_input": "并行炸掉后后续工具也要直接收尾",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_llm_call", lambda *_a, **_k: {"content": "", "usage": {}}
        ), patch.object(reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], fake_tool_executor))

        done_events = [
            chunk
            for chunk in chunks
            if isinstance(chunk, dict) and chunk.get("_tool_call", {}).get("done")
        ]
        self.assertEqual(len(done_events), 3)
        self.assertEqual(
            [event.get("_tool_call", {}).get("name") for event in done_events],
            ["search_text", "folder_explore", "write_file"],
        )
        self.assertEqual(
            [event.get("_tool_call", {}).get("reason") for event in done_events],
            ["", "tool_executor_exception", "tool_executor_exception"],
        )
        self.assertEqual(done_events[2].get("_tool_call", {}).get("success"), False)
        self.assertTrue(done_events[2].get("_tool_call", {}).get("synthetic"))
        final_done = next(chunk for chunk in reversed(chunks) if isinstance(chunk, dict) and chunk.get("_done"))
        self.assertEqual(final_done.get("action_count"), 3)
        final_result_reasons = {
            item.get("name"): item.get("reason")
            for item in final_done.get("tool_results") or []
            if isinstance(item, dict)
        }
        self.assertEqual(
            final_result_reasons,
            {
                "folder_explore": "tool_executor_exception",
                "search_text": "",
                "write_file": "tool_executor_exception",
            },
        )

    def test_unified_reply_with_tools_stream_marks_failed_tool_switch_as_fallback(self):
        executed = []
        stream_call_index = {"value": 0}

        def fake_stream(_cfg, _messages, **_kwargs):
            current = stream_call_index["value"]
            stream_call_index["value"] += 1
            if current == 0:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_run_command_1",
                            "type": "function",
                            "function": {
                                "name": "run_command",
                                "arguments": json.dumps({"command": "grep foo | head -20"}, ensure_ascii=False),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 3, "completion_tokens": 1}}
                return
            if current == 1:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_search_text_1",
                            "type": "function",
                            "function": {
                                "name": "search_text",
                                "arguments": json.dumps({"query": "foo"}, ensure_ascii=False),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 3, "completion_tokens": 1}}
                return
            yield "Done."
            yield {"_usage": {"prompt_tokens": 2, "completion_tokens": 1}}

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            if name == "run_command":
                return {
                    "success": False,
                    "error": "命令被拦截：不允许命令链或重定向",
                    "meta": {"action": {"action_kind": name, "target_kind": "command"}},
                }
            return {
                "success": True,
                "response": "search_text ok",
                "meta": {"action": {"action_kind": name, "target_kind": "file"}},
            }

        bundle = {
            "user_input": "继续查代码",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
            "max_turns": 4,
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], fake_tool_executor))

        self.assertEqual([name for name, _args in executed], ["run_command", "search_text"])
        search_exec = next(
            chunk
            for chunk in chunks
            if isinstance(chunk, dict)
            and chunk.get("_tool_call", {}).get("executing")
            and chunk.get("_tool_call", {}).get("name") == "search_text"
        )
        self.assertEqual(search_exec.get("_tool_call", {}).get("process_meta", {}).get("attempt_kind"), "fallback")
        self.assertEqual(search_exec.get("_tool_call", {}).get("process_meta", {}).get("previous_tool"), "run_command")

    def test_unified_reply_with_tools_stream_retries_followup_handoff_before_closing(self):
        executed = []
        stream_call_index = {"value": 0}

        def fake_stream(_cfg, _messages, **_kwargs):
            current = stream_call_index["value"]
            stream_call_index["value"] += 1
            if current == 0:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_followup_search",
                            "type": "function",
                            "function": {
                                "name": "search_text",
                                "arguments": json.dumps({"query": "TODO"}, ensure_ascii=False),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 3, "completion_tokens": 1}}
                return
            if current == 1:
                yield "我先继续处理下一步。"
                yield {"_usage": {"prompt_tokens": 3, "completion_tokens": 1}}
                return
            if current == 2:
                yield {
                    "_tool_calls": [
                        {
                            "id": "call_followup_write",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": json.dumps({"file_path": "result.txt", "content": "done"}, ensure_ascii=False),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 3, "completion_tokens": 1}}
                return
            yield "Done."
            yield {"_usage": {"prompt_tokens": 2, "completion_tokens": 1}}

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {
                "success": True,
                "response": f"{name} ok",
                "meta": {"action": {"action_kind": name, "target_kind": "file"}},
            }

        bundle = {
            "user_input": "继续把结果落到文件里",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
            "max_turns": 5,
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], fake_tool_executor))

        self.assertEqual(stream_call_index["value"], 4)
        self.assertEqual([name for name, _args in executed], ["search_text", "write_file"])
        final_done = next(chunk for chunk in reversed(chunks) if isinstance(chunk, dict) and chunk.get("_done"))
        self.assertEqual(final_done.get("tools_used"), ["search_text", "write_file"])
        self.assertEqual(final_done.get("action_count"), 2)
        self.assertIn("Done.", [chunk for chunk in chunks if isinstance(chunk, str)])

    def test_unified_reply_with_tools_stream_honors_explicit_max_turns(self):
        executed = []
        stream_call_index = {"value": 0}

        def fake_stream(_cfg, _messages, **_kwargs):
            current = stream_call_index["value"]
            stream_call_index["value"] += 1
            yield {
                "_tool_calls": [
                    {
                        "id": f"call_stream_limit_{current}",
                        "type": "function",
                        "function": {
                            "name": "search_text",
                            "arguments": json.dumps({"query": f"round-{current}"}, ensure_ascii=False),
                        },
                    }
                ]
            }
            yield {"_usage": {"prompt_tokens": 1, "completion_tokens": 1}}

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {
                "success": True,
                "response": f"{name} ok {args.get('query')}",
                "meta": {"action": {"action_kind": name, "target_kind": "file"}},
            }

        bundle = {
            "user_input": "一直查代码直到我叫停",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
            "max_turns": 3,
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], fake_tool_executor))

        self.assertEqual(len(executed), 3)
        self.assertTrue(
            any(
                isinstance(chunk, str) and "已达到当前工具往返轮次上限（3 轮）" in chunk
                for chunk in chunks
            )
        )
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertEqual(done.get("turns_used"), 3)
        self.assertEqual(done.get("max_turns"), 3)
        self.assertTrue(done.get("turn_limit_reached"))
        self.assertEqual(done.get("turn_reason"), "max_turns_reached")

    def test_unified_reply_with_tools_honors_explicit_max_turns(self):
        executed = []
        llm_call_index = {"value": 0}

        def fake_llm_call(_cfg, _messages, **_kwargs):
            current = llm_call_index["value"]
            llm_call_index["value"] += 1
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": f"call_non_stream_limit_{current}",
                        "type": "function",
                        "function": {
                            "name": "search_text",
                            "arguments": json.dumps({"query": f"round-{current}"}, ensure_ascii=False),
                        },
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {
                "success": True,
                "response": f"{name} ok {args.get('query')}",
                "meta": {"action": {"action_kind": name, "target_kind": "file"}},
            }

        bundle = {
            "user_input": "一直查代码直到我叫停",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
            "max_turns": 3,
        }

        with patch.object(reply_formatter_module, "_llm_call", side_effect=fake_llm_call), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"):
            result = reply_formatter_module.unified_reply_with_tools(bundle, [], fake_tool_executor)

        self.assertEqual(len(executed), 3)
        self.assertIn("已达到当前工具往返轮次上限（3 轮）", result.get("reply", ""))
        self.assertEqual(result.get("turns_used"), 3)
        self.assertEqual(result.get("max_turns"), 3)
        self.assertTrue(result.get("turn_limit_reached"))
        self.assertEqual(result.get("turn_reason"), "max_turns_reached")

    def test_unified_reply_with_tools_is_not_capped_at_three_followup_rounds(self):
        executed = []
        llm_call_index = {"value": 0}

        def fake_llm_call(_cfg, _messages, **_kwargs):
            current = llm_call_index["value"]
            llm_call_index["value"] += 1
            if current <= 4:
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": f"call_non_stream_round_{current}",
                            "type": "function",
                            "function": {
                                "name": "search_text",
                                "arguments": json.dumps({"query": f"round-{current}"}, ensure_ascii=False),
                            },
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                }

            return {
                "content": "Done after many rounds.",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {
                "success": True,
                "response": f"{name} ok {args.get('query')}",
                "meta": {"action": {"action_kind": name, "target_kind": "file"}},
            }

        bundle = {
            "user_input": "连续查很多轮代码",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
            "max_turns": 6,
        }

        with patch.object(reply_formatter_module, "_llm_call", side_effect=fake_llm_call), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"):
            result = reply_formatter_module.unified_reply_with_tools(bundle, [], fake_tool_executor)

        self.assertEqual(len(executed), 5)
        self.assertEqual(result.get("reply"), "Done after many rounds.")
        self.assertEqual(result.get("turns_used"), 6)
        self.assertEqual(result.get("max_turns"), 6)
        self.assertFalse(result.get("turn_limit_reached"))

    def test_unified_reply_with_tools_stream_is_not_capped_at_forty_followup_rounds(self):
        executed = []
        stream_call_index = {"value": 0}

        def fake_stream(_cfg, _messages, **_kwargs):
            current = stream_call_index["value"]
            stream_call_index["value"] += 1
            if current <= 40:
                yield {
                    "_tool_calls": [
                        {
                            "id": f"call_stream_round_{current}",
                            "type": "function",
                            "function": {
                                "name": "search_text",
                                "arguments": json.dumps({"query": f"round-{current}"}, ensure_ascii=False),
                            },
                        }
                    ]
                }
                yield {"_usage": {"prompt_tokens": 1, "completion_tokens": 1}}
                return

            yield "Done after many rounds."
            yield {"_usage": {"prompt_tokens": 1, "completion_tokens": 1}}

        def fake_tool_executor(name, args, _context):
            executed.append((name, args))
            return {
                "success": True,
                "response": f"{name} ok {args.get('query')}",
                "meta": {"action": {"action_kind": name, "target_kind": "file"}},
            }

        bundle = {
            "user_input": "连续查很多轮代码",
            "l1": [],
            "l4": {},
            "dialogue_context": "",
            "max_turns": 50,
        }

        with patch.object(reply_formatter_module, "_llm_call_stream", side_effect=fake_stream), patch.object(
            reply_formatter_module, "_build_tool_call_system_prompt", return_value="system"
        ), patch.object(
            reply_formatter_module, "_build_tool_call_user_prompt", return_value="user"
        ):
            chunks = list(reply_formatter_module.unified_reply_with_tools_stream(bundle, [], fake_tool_executor))

        self.assertEqual(len(executed), 41)
        self.assertTrue(any(isinstance(chunk, str) and chunk == "Done after many rounds." for chunk in chunks))
        done = chunks[-1]
        self.assertEqual(done.get("_done"), True)
        self.assertEqual(done.get("action_count"), 41)
        self.assertEqual(done.get("tool_used"), "search_text")
        self.assertEqual(done.get("max_turns"), 50)
        self.assertFalse(done.get("turn_limit_reached"))


if __name__ == "__main__":
    unittest.main()
