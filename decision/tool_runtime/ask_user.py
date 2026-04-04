"""Shared ask_user state and tool behavior for post-LLM runtime pauses."""

import threading
import time


_ask_user_lock = threading.Lock()
_ask_user_pending = None
_ask_user_answer = None


def ask_user_submit(question_id: str, answer: str) -> bool:
    global _ask_user_answer
    with _ask_user_lock:
        if _ask_user_pending and _ask_user_pending.get("id") == question_id:
            _ask_user_answer = answer
            return True
    return False


def get_ask_user_pending() -> dict | None:
    with _ask_user_lock:
        return dict(_ask_user_pending) if _ask_user_pending else None


def execute_ask_user(arguments: dict, *, debug_write=None) -> dict:
    global _ask_user_pending, _ask_user_answer

    debug_write = debug_write or (lambda stage, data: None)
    question = str(arguments.get("question", "")).strip()
    options = arguments.get("options", [])
    if not question:
        return {"success": False, "response": "ask_user: 缺少 question 参数"}
    if not isinstance(options, list) or len(options) < 2:
        return {"success": False, "response": "ask_user: options 至少需要 2 个选项"}

    question_id = f"ask_{int(time.time() * 1000)}"

    with _ask_user_lock:
        _ask_user_pending = {"question": question, "options": options, "id": question_id}
        _ask_user_answer = None

    debug_write("ask_user_waiting", {"id": question_id, "question": question, "options": options})

    timeout = 120
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        with _ask_user_lock:
            if _ask_user_answer is not None:
                answer = _ask_user_answer
                _ask_user_pending = None
                _ask_user_answer = None
                debug_write("ask_user_answered", {"id": question_id, "answer": answer})
                return {"success": True, "response": f"用户选择了：{answer}"}
        time.sleep(0.3)

    with _ask_user_lock:
        _ask_user_pending = None
        _ask_user_answer = None
    debug_write("ask_user_timeout", {"id": question_id})
    return {"success": False, "response": "用户未在规定时间内回答，任务暂停。"}


def get_ask_user_tool_def() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "暂停当前任务，向用户提问并等待选择。用于需要用户决策的场景，如选题、确认方案、选择风格等。用户回答后任务继续。",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "向用户提出的问题"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "给用户的选项列表，至少 2 个，用户会从中选一个",
                    },
                },
                "required": ["question", "options"],
            },
        },
    }
