from __future__ import annotations

from datetime import datetime

from core.process_history import normalize_process_payload


class ChatHistoryTransaction:
    def __init__(
        self,
        history: list,
        *,
        save_msg_history,
        add_to_history=None,
        debug_write=None,
    ) -> None:
        self.history = history
        self.save_msg_history = save_msg_history
        self.add_to_history = add_to_history
        self.debug_write = debug_write
        self.pending_user_entry: dict | None = None
        self.assistant_history_saved = False

    def append_pending_user(self, content: str) -> dict:
        entry = {"role": "user", "content": content, "time": datetime.now().isoformat()}
        self.history.append(entry)
        self.save_msg_history(self.history)
        self.pending_user_entry = entry
        return entry

    def persist_assistant_entry(
        self,
        role: str,
        content: str,
        *,
        process: dict | None = None,
    ) -> bool:
        saved = persist_assistant_history_entry(
            self.history,
            role=role,
            content=content,
            process=process,
            save_msg_history=self.save_msg_history,
            add_to_history=self.add_to_history,
            debug_write=self.debug_write,
        )
        self.assistant_history_saved = bool(saved)
        return saved

    def rollback_pending_user(self, reason: str) -> bool:
        return rollback_pending_user_turn(
            self.history,
            self.pending_user_entry,
            assistant_history_saved=self.assistant_history_saved,
            reason=reason,
            save_msg_history=self.save_msg_history,
            debug_write=self.debug_write,
        )


def rollback_pending_user_history_turn(history: list | None, pending_entry: dict | None) -> bool:
    if not isinstance(history, list) or not history or not isinstance(pending_entry, dict):
        return False
    last = history[-1]
    if not isinstance(last, dict):
        return False
    pending_role = str(pending_entry.get("role") or "").strip().lower()
    pending_content = str(pending_entry.get("content") or "")
    pending_time = str(pending_entry.get("time") or "").strip()
    if pending_role != "user":
        return False
    if str(last.get("role") or "").strip().lower() != "user":
        return False
    if pending_time and str(last.get("time") or "").strip() != pending_time:
        return False
    if pending_content and str(last.get("content") or "") != pending_content:
        return False
    history.pop()
    return True


def persist_assistant_history_entry(
    history: list,
    *,
    role: str,
    content: str,
    process: dict | None = None,
    save_msg_history,
    add_to_history=None,
    debug_write=None,
) -> bool:
    entry = {
        "role": str(role or "").strip(),
        "content": content,
        "time": datetime.now().isoformat(),
    }
    normalized_process = normalize_process_payload(process)
    if normalized_process:
        entry["process"] = normalized_process
    if callable(add_to_history):
        try:
            add_to_history(entry["role"], content)
        except Exception as exc:
            if callable(debug_write):
                debug_write("history_text_append_failed", {"role": entry["role"], "error": str(exc)})
    history.append(entry)
    save_msg_history(history)
    return True


def rollback_pending_user_turn(
    history: list,
    pending_entry: dict | None,
    *,
    assistant_history_saved: bool,
    reason: str,
    save_msg_history,
    debug_write=None,
) -> bool:
    if assistant_history_saved:
        return False
    removed = rollback_pending_user_history_turn(history, pending_entry)
    if not removed:
        return False
    try:
        save_msg_history(history)
    except Exception as exc:
        if callable(debug_write):
            debug_write("history_user_turn_rollback_failed", {"reason": reason, "error": str(exc)})
        return False
    if callable(debug_write):
        debug_write("history_user_turn_rolled_back", {"reason": reason})
    return True
