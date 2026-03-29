"""时间回忆 — 按时间范围检索对话历史并摘要，注入 prompt 让 Nova 能回答\u201c今天聊了什么\u201d类问题"""

import re
from datetime import datetime, timedelta
from core.json_store import load_json
from core.state_loader import PRIMARY_STATE_DIR

_llm_call = None
_debug_write = lambda stage, data: None

L2_FILE = PRIMARY_STATE_DIR / "l2_short_term.json"
HISTORY_FILE = PRIMARY_STATE_DIR / "msg_history.json"


def init(*, llm_call=None, debug_write=None):
    global _llm_call, _debug_write
    if llm_call:
        _llm_call = llm_call
    if debug_write:
        _debug_write = debug_write


# ── 回忆词 ──
_RECALL_WORDS = [
    "\u804a\u4e86", "\u5e72\u4e86", "\u505a\u4e86", "\u8bf4\u4e86", "\u8ba8\u8bba\u4e86", "\u8c08\u4e86", "\u95ee\u4e86",
    "\u804a\u8fc7", "\u8bf4\u8fc7", "\u505a\u8fc7", "\u8c08\u8fc7",
    "\u804a\u4ec0\u4e48", "\u5e72\u4ec0\u4e48", "\u505a\u4ec0\u4e48", "\u8bf4\u4ec0\u4e48",
    "\u804a\u5565", "\u5e72\u5565", "\u505a\u5565",
    "\u56de\u5fc6", "\u603b\u7ed3", "\u804a\u7684",
]

def _has_recall_word(text: str) -> bool:
    for w in _RECALL_WORDS:
        if w in text:
            return True
    return False


# ── 时间解析 ──

def _parse_time_range(text: str):
    """解析时间词，返回 (time_label, start_dt, end_dt) 或 None"""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 最近N天
    m = re.search(r"\u6700\u8fd1(\d+)\u5929", text)
    if m:
        n = int(m.group(1))
        return (f"\u6700\u8fd1{n}\u5929", today_start - timedelta(days=n - 1), now)

    # 具体日期：3月15号 / 3月15日
    m = re.search(r"(\d{1,2})\u6708(\d{1,2})[\u53f7\u65e5]?", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        try:
            target = now.replace(month=month, day=day, hour=0, minute=0, second=0, microsecond=0)
            end = target.replace(hour=23, minute=59, second=59)
            return (f"{month}\u6708{day}\u65e5", target, end)
        except ValueError:
            pass

    # 固定时间词
    if "\u4eca\u5929" in text or "\u4eca\u65e5" in text:
        return ("\u4eca\u5929", today_start, now)
    if "\u6628\u5929" in text:
        yd = today_start - timedelta(days=1)
        return ("\u6628\u5929", yd, yd.replace(hour=23, minute=59, second=59))
    if "\u524d\u5929" in text:
        bd = today_start - timedelta(days=2)
        return ("\u524d\u5929", bd, bd.replace(hour=23, minute=59, second=59))
    if "\u4e0a\u5468" in text:
        days_since_mon = now.weekday()
        this_mon = today_start - timedelta(days=days_since_mon)
        last_mon = this_mon - timedelta(days=7)
        last_sun = this_mon - timedelta(seconds=1)
        return ("\u4e0a\u5468", last_mon, last_sun)
    if "\u8fd9\u5468" in text or "\u672c\u5468" in text:
        days_since_mon = now.weekday()
        this_mon = today_start - timedelta(days=days_since_mon)
        return ("\u8fd9\u5468", this_mon, now)
    if "\u4e0a\u4e2a\u6708" in text:
        first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_prev = first_this - timedelta(seconds=1)
        first_prev = last_prev.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return ("\u4e0a\u4e2a\u6708", first_prev, last_prev)
    if "\u8fd9\u4e2a\u6708" in text or "\u672c\u6708" in text:
        first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return ("\u8fd9\u4e2a\u6708", first_this, now)

    return None


def detect_recall_intent(user_input: str):
    """检测回忆意图，返回 dict 或 None"""
    if not user_input or len(user_input) < 4:
        return None
    text = user_input.strip()
    time_info = _parse_time_range(text)
    if not time_info:
        return None
    if not _has_recall_word(text):
        return None
    label, start_dt, end_dt = time_info
    return {
        "is_recall": True,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "time_label": label,
    }


def recall_by_time(start_dt, end_dt, time_label, history=None) -> str:
    """按时间范围检索对话历史并摘要"""
    # 1. 从 msg_history.json 过滤用户消息
    all_msgs = load_json(HISTORY_FILE, [])
    user_msgs = []
    for m in all_msgs:
        t = m.get("time", "")
        role = m.get("role", "")
        if role != "user":
            continue
        try:
            msg_time = datetime.fromisoformat(t)
        except (ValueError, TypeError):
            continue
        if start_dt <= msg_time <= end_dt:
            user_msgs.append({"content": m.get("content", ""), "time": t, "dt": msg_time})

    # 2. 从 l2_short_term.json 过滤
    l2_store = load_json(L2_FILE, [])
    l2_entries = []
    for entry in l2_store:
        ca = entry.get("created_at", "")
        try:
            entry_time = datetime.fromisoformat(ca)
        except (ValueError, TypeError):
            continue
        if start_dt <= entry_time <= end_dt:
            l2_entries.append(entry)

    _debug_write("recall_fetch", {
        "time_label": time_label,
        "user_msgs": len(user_msgs),
        "l2_entries": len(l2_entries),
    })

    if not user_msgs and not l2_entries:
        return f"{time_label}\u6ca1\u6709\u627e\u5230\u5bf9\u8bdd\u8bb0\u5f55\u3002"

    # 3. 根据数量选择摘要方式
    if len(user_msgs) <= 40:
        return _format_topic_list(user_msgs, l2_entries, time_label)
    else:
        return _summarize(user_msgs, l2_entries, time_label)


def _time_period(dt):
    h = dt.hour
    if h < 6:
        return "\u51cc\u6668"
    if h < 12:
        return "\u4e0a\u5348"
    if h < 18:
        return "\u4e0b\u5348"
    return "\u665a\u4e0a"


def _format_topic_list(user_msgs, l2_entries, time_label) -> str:
    """消息 <= 40 条时，按时段分组直接列出"""
    groups = {}
    for m in user_msgs:
        period = _time_period(m["dt"])
        if period not in groups:
            groups[period] = []
        content = m["content"].strip()
        if len(content) > 60:
            content = content[:60] + "..."
        time_str = m["dt"].strftime("%H:%M")
        groups[period].append(f"{time_str} {content}")

    lines = [f"{time_label}\u5171 {len(user_msgs)} \u6761\u7528\u6237\u6d88\u606f\uff1a"]
    for period in ["\u51cc\u6668", "\u4e0a\u5348", "\u4e0b\u5348", "\u665a\u4e0a"]:
        items = groups.get(period)
        if not items:
            continue
        lines.append(f"\n{period}\uff1a")
        for item in items:
            lines.append(f"\u00b7 {item}")

    # 补充 L2 关键词
    if l2_entries:
        kws = set()
        for e in l2_entries:
            for kw in e.get("keywords", []):
                kws.add(kw)
        if kws:
            kw_str = "\u3001".join(list(kws)[:15])
            lines.append(f"\n\u6838\u5fc3\u8bdd\u9898\uff1a{kw_str}")

    return "\n".join(lines)


def _summarize(user_msgs, l2_entries, time_label) -> str:
    """消息 > 40 条时，用 LLM 摘要，失败则规则兜底"""
    if _llm_call:
        result = _summarize_with_llm(user_msgs, l2_entries, time_label)
        if result:
            return result
    return _fallback_extract(user_msgs, l2_entries, time_label)


def _summarize_with_llm(user_msgs, l2_entries, time_label) -> str:
    """LLM 摘要：取前15+后15条，控制 prompt 大小"""
    sample = []
    head = user_msgs[:15]
    tail = user_msgs[-15:] if len(user_msgs) > 30 else user_msgs[15:]
    for m in head + tail:
        content = m["content"].strip()[:60]
        time_str = m["dt"].strftime("%H:%M")
        sample.append(f"[{time_str}] {content}")

    prompt = (
        f"\u4ee5\u4e0b\u662f\u7528\u6237\u5728{time_label}\u7684\u5bf9\u8bdd\u8bb0\u5f55\uff08\u5171{len(user_msgs)}\u6761\u7528\u6237\u6d88\u606f\uff09\u3002\n"
        f"\u8bf7\u7528 3-5 \u4e2a\u8981\u70b9\u603b\u7ed3\u804a\u4e86\u54ea\u4e9b\u8bdd\u9898\uff0c\u6bcf\u4e2a\u8981\u70b9\u4e00\u53e5\u8bdd\uff0c\u5e26\u5927\u81f4\u65f6\u95f4\u6bb5\u3002\n"
        f"\u4e0d\u8981\u7528\u8868\u60c5\u7b26\u53f7\uff0c\u4e0d\u8981\u89d2\u8272\u626e\u6f14\u8bed\u6c14\uff0c\u53ea\u8f93\u51fa\u8981\u70b9\u5217\u8868\u3002\n\n"
    )
    prompt += "\n".join(sample)

    try:
        result = _llm_call(prompt)
        if result and len(result.strip()) > 10:
            return f"{time_label}\u5bf9\u8bdd\u6458\u8981\uff08\u5171{len(user_msgs)}\u6761\u6d88\u606f\uff09\uff1a\n{result.strip()}"
    except Exception:
        pass
    return ""


def _fallback_extract(user_msgs, l2_entries, time_label) -> str:
    """规则兜底：L2 关键词 + L1 消息前缀去重"""
    # L2 关键词
    kws = set()
    for e in l2_entries:
        for kw in e.get("keywords", []):
            kws.add(kw)

    # L1 消息前缀去重
    seen = set()
    topics = []
    for m in user_msgs:
        prefix = m["content"].strip()[:15]
        if prefix and prefix not in seen:
            seen.add(prefix)
            topics.append(prefix)
        if len(topics) >= 20:
            break

    lines = [f"{time_label}\u5171 {len(user_msgs)} \u6761\u5bf9\u8bdd\u3002"]
    if kws:
        kw_str = "\u3001".join(list(kws)[:15])
        lines.append(f"\u6838\u5fc3\u8bdd\u9898\uff1a{kw_str}")
    if topics:
        topic_str = "\u3001".join(topics)
        lines.append(f"\u7528\u6237\u63d0\u5230\u8fc7\uff1a{topic_str}")
    return "\n".join(lines)
