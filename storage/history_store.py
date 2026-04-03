import re
from datetime import datetime, timedelta

from storage.json_store import load_json_store, write_json
from storage.paths import LEGACY_HISTORY_FILE, PRIMARY_HISTORY_FILE


def load_msg_history():
    history = load_json_store(PRIMARY_HISTORY_FILE, LEGACY_HISTORY_FILE, [])
    if not isinstance(history, list):
        return []

    now = datetime.now()
    cutoff = now - timedelta(days=7)
    cleaned = []
    for item in history:
        try:
            item_time = datetime.fromisoformat(item.get("time", "2020-01-01"))
            if item_time > cutoff:
                cleaned.append(item)
        except Exception:
            cleaned.append(item)

    if len(cleaned) != len(history):
        write_json(PRIMARY_HISTORY_FILE, cleaned)
    return cleaned


def save_msg_history(history):
    write_json(PRIMARY_HISTORY_FILE, history)


def _estimate_recent_message_tokens(item: dict) -> int:
    if not isinstance(item, dict):
        return 0
    role = str(item.get("role") or "").strip()
    content = str(item.get("content") or item.get("summary") or item.get("event") or "").strip()
    text = f"{role} {content}".strip()
    if not text:
        return 0
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", text))
    latin_count = sum(len(token) for token in re.findall(r"[A-Za-z0-9_]+", text))
    other_count = max(len(text) - cjk_count - latin_count, 0)
    return max(1, cjk_count + ((latin_count + 3) // 4) + ((other_count + 1) // 2))


def get_recent_messages(history, limit=6, max_tokens=None):
    rows = [item for item in (history or []) if isinstance(item, dict)]
    if limit is None:
        parsed_limit = None
    else:
        try:
            parsed_limit = int(limit)
        except Exception:
            parsed_limit = 6
        if parsed_limit <= 0:
            return []

    if max_tokens is None:
        if parsed_limit is None:
            return rows
        return rows[-parsed_limit:]

    try:
        max_tokens = int(max_tokens)
    except Exception:
        max_tokens = 0
    if max_tokens <= 0:
        return rows[-limit:]

    selected = []
    used_tokens = 0
    for item in reversed(rows):
        estimated = _estimate_recent_message_tokens(item)
        over_limit = parsed_limit is not None and len(selected) >= parsed_limit
        over_budget = used_tokens + estimated > max_tokens
        if selected and (over_limit or over_budget):
            break
        selected.append(item)
        used_tokens += estimated
        if parsed_limit is not None and len(selected) >= parsed_limit:
            break
    return list(reversed(selected))
