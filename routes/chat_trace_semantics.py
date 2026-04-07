from __future__ import annotations

import re


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def build_expected_output(*, phase: str, tool_name: str = "", preview: str = "", display_name: str = "") -> str:
    phase = _clean_text(phase).lower()
    preview = _clean_text(preview)
    display_name = _clean_text(display_name or tool_name)
    if phase == "thinking":
        return "\u5224\u65ad\u662f\u76f4\u63a5\u56de\u7b54\u8fd8\u662f\u5148\u8c03\u7528\u5de5\u5177"
    if phase != "tool":
        return ""
    if tool_name == "weather":
        return "\u6700\u65b0\u5929\u6c14\u548c\u4e00\u4e2a\u53ef\u76f4\u63a5\u7528\u7684\u7b80\u6d01\u7ed3\u8bba"
    if preview:
        return f"\u56f4\u7ed5\u300c{preview}\u300d\u62ff\u5230\u53ef\u9760\u7ed3\u679c"
    if display_name:
        return f"\u62ff\u5230 {display_name} \u7684\u5173\u952e\u7ed3\u679c"
    return "\u62ff\u5230\u8fd9\u4e00\u6b65\u9700\u8981\u7684\u5173\u952e\u4fe1\u606f"


def build_next_user_need(
    *,
    user_message: str = "",
    tool_name: str = "",
    preview: str = "",
    expected_output: str = "",
) -> str:
    preview = _clean_text(preview)
    expected_output = _clean_text(expected_output)
    user_message = _clean_text(user_message)
    if tool_name == "weather" or "\u5929\u6c14" in preview:
        return "\u4eca\u5929\u72b6\u6001\u3001\u51fa\u95e8\u5b89\u6392\u6216\u8981\u4e0d\u8981\u5e26\u4f1e"
    if tool_name == "web_search":
        return "\u6700\u65b0\u7ed3\u8bba\u3001\u600e\u4e48\u505a\uff0c\u6216\u8981\u4e0d\u8981\u7ee7\u7eed\u5c55\u5f00"
    if tool_name in {"recall_memory", "query_knowledge"}:
        return "\u628a\u4e0a\u4e0b\u6587\u63a5\u56de\u5f53\u524d\u95ee\u9898\u540e\u7684\u660e\u786e\u7ed3\u8bba"
    if any(token in user_message for token in ("\u4eca\u5929", "\u65b0\u7684\u4e00\u5929", "\u65e9\u5b89", "\u65e9\u4e0a")):
        return "\u4eca\u5929\u6700\u503c\u5f97\u5148\u5173\u6ce8\u7684\u5b9e\u65f6\u4fe1\u606f"
    if expected_output:
        return expected_output
    return "\u4e00\u4e2a\u80fd\u76f4\u63a5\u63a5\u4f4f\u5f53\u524d\u8bdd\u9898\u7684\u7ed3\u8bba"


def build_tool_reason_note(tool_name: str, preview: str, display_name: str) -> str:
    tool_name = _clean_text(tool_name)
    preview = _clean_text(preview)
    display_name = _clean_text(display_name or tool_name)
    if tool_name == "weather" and preview:
        if "\u5929\u6c14" not in preview:
            preview = f"{preview}\u5929\u6c14"
        return (
            f"\u8fd9\u662f\u5b9e\u65f6\u4fe1\u606f\uff0c\u76f4\u63a5\u51ed\u8bb0\u5fc6\u4e0d\u7a33\u3002"
            f"\u6211\u5148\u6838\u5b9e\u300c{preview}\u300d\u7684\u6700\u65b0\u5929\u6c14\uff0c\u518d\u6839\u636e\u7ed3\u679c"
            "\u7ed9\u4f60\u4e00\u4e2a\u7b80\u6d01\u7ed3\u8bba\u3002"
        )
    if preview:
        return (
            f"\u6211\u5148\u628a\u8fd9\u4e00\u6b65\u9700\u8981\u6838\u5b9e\u7684\u4fe1\u606f\u67e5\u6e05\u695a\uff0c"
            f"\u518d\u7ee7\u7eed\u56de\u7b54\u3002\u5f53\u524d\u5148\u8c03\u7528\u300c{display_name}\u300d\u786e\u8ba4"
            f"\u300c{preview}\u300d\u3002"
        )
    if display_name:
        return (
            f"\u6211\u5148\u8c03\u7528\u300c{display_name}\u300d\u628a\u5173\u952e\u4e8b\u5b9e\u62ff\u5230\uff0c"
            "\u518d\u7ee7\u7eed\u6574\u7406\u6700\u7ec8\u7b54\u590d\u3002"
        )
    return ""


def build_direct_reply_reason_note(*, has_context: bool = False) -> str:
    if has_context:
        return (
            "\u8fd9\u4e00\u8f6e\u66f4\u50cf\u662f\u76f4\u63a5\u56de\u5e94\uff0c\u4e0d\u9700\u8981\u518d\u8c03\u7528\u5de5\u5177\u3002"
            "\u6211\u4f1a\u5148\u7ed3\u5408\u5f53\u524d\u5bf9\u8bdd\u4e0a\u4e0b\u6587\u76f4\u63a5\u7ed9\u51fa\u7b54\u590d\u3002"
        )
    return (
        "\u8fd9\u4e00\u8f6e\u66f4\u50cf\u662f\u76f4\u63a5\u56de\u5e94\uff0c\u4e0d\u9700\u8981\u518d\u8c03\u7528\u5de5\u5177\u3002"
        "\u6211\u4f1a\u76f4\u63a5\u56f4\u7ed5\u4f60\u8fd9\u53e5\u8bdd\u7ed9\u51fa\u7b54\u590d\u3002"
    )


def append_thinking_text(existing: str, incoming: str) -> str:
    current = str(existing or "")
    piece = str(incoming or "")
    if not piece:
        return current
    if not current:
        return piece
    if current.endswith(piece):
        return current
    return current + piece


def normalize_thinking_trace_text(text: str) -> str:
    cleaned = str(text or "").replace("\r", " ").replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def looks_like_toolish_thinking_text(
    text: str,
    *,
    tool_name: str = "",
    preview: str = "",
    action_summary: str = "",
) -> bool:
    visible = normalize_thinking_trace_text(text)
    if not visible:
        return False
    lower = visible.lower()
    tool_lower = _clean_text(tool_name).lower()
    preview_text = _clean_text(preview)
    action_text = _clean_text(action_summary)
    if visible.startswith("{") or visible.startswith("["):
        return True
    if any(token in visible for token in ("http://", "https://")):
        return True
    if tool_lower and (lower.startswith(tool_lower) or f"{tool_lower} /" in lower or f"{tool_lower}:" in lower):
        return True
    if action_text and action_text in visible:
        return True
    if preview_text and preview_text in visible and len(visible) <= max(len(preview_text) + 40, 180):
        return True
    if re.match(r"^[a-z0-9_]+\s*[/:\-]\s*", lower) and len(visible) <= 180:
        return True
    if visible.count(" / ") >= 1 and len(visible) <= 160:
        return True
    return False


def prefer_reason_note_for_tool(
    current_text: str,
    *,
    tool_name: str = "",
    preview: str = "",
    reason_note: str = "",
    action_summary: str = "",
    default_think_detail: str = "",
) -> str:
    reason = normalize_thinking_trace_text(reason_note)
    current = normalize_thinking_trace_text(current_text)
    if not reason:
        return current
    if not current or current == normalize_thinking_trace_text(default_think_detail):
        return reason
    if looks_like_toolish_thinking_text(
        current,
        tool_name=tool_name,
        preview=preview,
        action_summary=action_summary,
    ):
        return reason
    if len(current) < 42:
        return reason
    return current
