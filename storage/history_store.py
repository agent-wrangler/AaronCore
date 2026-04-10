import re
from datetime import datetime, timedelta

from storage.json_store import load_json_store, write_json
from storage.paths import LEGACY_HISTORY_FILE, PRIMARY_HISTORY_FILE


_TRANSIENT_ASSISTANT_NOTICE_PATTERNS = (
    re.compile(r"^当前模型接口余额不足，暂时无法继续。请充值后重试，或先切换到其他模型。?$"),
    re.compile(r"^当前模型请求失败：上下文太长，超过了该模型的限制。请重试，或切换到上下文更大的模型。?$"),
    re.compile(r"^当前模型连接失败，请检查网络或代理设置后重试。?$"),
    re.compile(r"^当前模型请求过于频繁，或该账户额度已不足。请稍后重试，或先切换到其他模型。?$"),
    re.compile(r"^当前模型鉴权失败，请检查 ?API Key ?或权限配置。?$"),
    re.compile(r"^当前模型请求参数无效，暂时无法继续。请检查模型配置后重试。?$"),
    re.compile(r"^当前模型请求失败：.+$"),
    re.compile(r"^当前.+接口请求失败（HTTP \d{3}）.*$"),
    re.compile(r"^Current model API balance is insufficient\. Unable to continue for now\. Please top up and try again, or switch to another model first\.?$", re.I),
    re.compile(r"^Current model request failed: the context is too long and exceeded this model's limit\..+$", re.I),
    re.compile(r"^Current model connection failed\. Please check your network or proxy settings and try again\.?$", re.I),
    re.compile(r"^Current model requests are too frequent, or the account balance/quota is insufficient\..+$", re.I),
    re.compile(r"^Current model authentication failed\. Please check the API key or permission settings\.?$", re.I),
    re.compile(r"^Current model request parameters are invalid\. Unable to continue for now\..+$", re.I),
    re.compile(r"^Current model request failed: .+$", re.I),
    re.compile(r"^Current .+ request failed \(HTTP \d{3}\)\..*$", re.I),
)

_TRANSIENT_MISSING_EXECUTION_PREFIX_PATTERNS = (
    re.compile(r"这一轮我还没有实际调用读取文件或目录的工具", re.I),
    re.compile(r"刚才那段带本地文件或目录结论的答复不可靠", re.I),
    re.compile(r"刚才那段不能算结果", re.I),
    re.compile(r"主人，刚才那个说.+?的回复不可靠", re.I),
    re.compile(r"主人，我刚才的回复有问题", re.I),
)

_TRANSIENT_MISSING_EXECUTION_FOLLOWUP_PATTERNS = (
    re.compile(r"我需要先真实读取相关目标", re.I),
    re.compile(r"我需要重新执行真实的检查", re.I),
    re.compile(r"我需要重新发起真实的读取或检查", re.I),
    re.compile(r"让我重新检查一下", re.I),
    re.compile(r"再回来给你总结", re.I),
)


def _is_transient_missing_execution_notice(normalized_text: str) -> bool:
    text = str(normalized_text or "").strip()
    if not text:
        return False
    if not any(pattern.search(text) for pattern in _TRANSIENT_MISSING_EXECUTION_PREFIX_PATTERNS):
        return False
    return any(pattern.search(text) for pattern in _TRANSIENT_MISSING_EXECUTION_FOLLOWUP_PATTERNS)


def is_transient_assistant_notice(item_or_text) -> bool:
    if isinstance(item_or_text, dict):
        role = str(item_or_text.get("role") or "").strip().lower()
        if role not in {"assistant", "nova"}:
            return False
        text = str(item_or_text.get("content") or "")
    else:
        text = str(item_or_text or "")

    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return False
    if _is_transient_missing_execution_notice(normalized):
        return True
    if len(normalized) > 180:
        return False
    return any(pattern.match(normalized) for pattern in _TRANSIENT_ASSISTANT_NOTICE_PATTERNS)


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
                if not is_transient_assistant_notice(item):
                    cleaned.append(item)
        except Exception:
            if not is_transient_assistant_notice(item):
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
    rows = [
        item
        for item in (history or [])
        if isinstance(item, dict) and not is_transient_assistant_notice(item)
    ]
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
