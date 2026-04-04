"""Summary helpers for L2 memory."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from memory.l2 import hygiene as _l2_hygiene
from storage.json_store import load_json, write_json


def clean_summary(text: str) -> str:
    text = _l2_hygiene.sanitize_summary_text(text)
    text = re.sub(
        r"[\U0001f300-\U0001f9ff\u2728\u2705\u274c\u2764\u2b50\u26a1\u2600-\u26ff\u2700-\u27bf]",
        "",
        text,
    )
    text = re.sub(r"[\uff08\(][^\uff09\)]{0,30}[\uff09\)]", "", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = text.strip()
    if _l2_hygiene.looks_internal_reasoning(text):
        return ""
    if len(text) > 100:
        text = text[:100]
    return text


def gen_summary(
    mems,
    start,
    end,
    *,
    summary_interval: int,
    llm_call,
    think,
    build_signal_profile: Callable[[str], set[str]],
    normalize_signal_text: Callable[[str], str],
) -> str:
    dialog = ""
    for item in mems[-summary_interval:]:
        dialog += f"\u7528\u6237: {item.get('user_text','')}\nAI: {item.get('ai_text','')[:100]}\n\n"
    prompt = (
        f"\u4ee5\u4e0b\u662f\u7b2c{start}\u8f6e\u5230\u7b2c{end}\u8f6e\u7684\u5bf9\u8bdd\u8bb0\u5f55\uff0c"
        "\u8bf7\u75281-2\u53e5\u8bdd\u63d0\u70bc\u7528\u6237\u7684\u884c\u4e3a\u548c\u5173\u6ce8\u70b9\uff08\u7528\u6237\u505a\u4e86\u4ec0\u4e48\u3001\u95ee\u4e86\u4ec0\u4e48\u3001\u8868\u8fbe\u4e86\u4ec0\u4e48\u504f\u597d\uff09\u3002\n"
        "\u8981\u6c42\uff1a\n"
        "1. \u53ea\u5173\u6ce8\u7528\u6237\u884c\u4e3a\uff0c\u4e0d\u8981\u590d\u8ff0AI\u7684\u56de\u590d\u5185\u5bb9\n"
        "2. \u4e0d\u8981\u7528\u8868\u60c5/\u8bed\u6c14\u8bcd/\u89d2\u8272\u626e\u6f14\u8bed\u53e5\n"
        "3. \u7528\u7b80\u6d01\u7684\u9648\u8ff0\u53e5\uff0c\u4e0d\u8981\u5217\u6e05\u5355\n"
        "4. \u63a7\u5236\u5728 50 \u5b57\u5185\n\n"
        + dialog[:2000]
    )
    if llm_call:
        try:
            text = (llm_call(prompt) or "").strip()
            if len(text) > 5:
                return clean_summary(text)
        except Exception:
            pass
    if think:
        try:
            result = think(prompt, "")
            if isinstance(result, dict):
                text = str(result.get("reply", "")).strip()
            else:
                text = str(result or "").strip()
            if len(text) > 5:
                return clean_summary(text)
        except Exception:
            pass

    key_points = []
    for item in mems:
        user_text = str(item.get("user_text", "") or "").strip()
        if not user_text:
            continue
        profile = build_signal_profile(user_text)
        normalized = normalize_signal_text(user_text)
        if float(item.get("importance", 0.0) or 0.0) >= 0.65:
            key_points.append(user_text[:40])
        elif len(normalized) >= 10 and (
            "meta:question" in profile
            or "meta:structured" in profile
            or "meta:mixed_script" in profile
        ):
            key_points.append(user_text[:40])
    if key_points:
        return f"\u5bf9\u8bdd\u8981\u70b9\uff08\u7b2c{start}-{end}\u8f6e\uff09\uff1a" + "\uff1b".join(key_points[:5])
    return f"\u7b2c{start}-{end}\u8f6e\u4e3a\u4e00\u822c\u6027\u4ea4\u6d41\u3002"


def auto_summary(
    cfg,
    store,
    *,
    summary_interval: int,
    l3_file: Path,
    save_config: Callable[[dict], None],
    gen_summary: Callable[[list, int, int], str],
    debug_write: Callable[[str, dict], None],
) -> None:
    total = cfg.get("total_rounds", 0)
    last = cfg.get("last_summary_round", 0)
    if total - last < summary_interval:
        return
    recent = store[-summary_interval:]
    if len(recent) < 10:
        return
    summary = gen_summary(recent, last + 1, total)
    if not summary:
        return
    try:
        l3 = load_json(l3_file, [])
        l3.append(
            {
                "event": summary,
                "type": "event",
                "source": "l2_auto_summary",
                "metadata": {"start_round": last + 1, "end_round": total},
                "created_at": datetime.now().isoformat(),
            }
        )
        write_json(l3_file, l3)
    except Exception:
        pass
    cfg["last_summary_round"] = total
    cfg["total_summaries"] = cfg.get("total_summaries", 0) + 1
    save_config(cfg)
    debug_write("l2_summary", {"rounds": f"{last + 1}-{total}"})


def format_l2_context(memories: list) -> str:
    if not memories:
        return ""
    lines = []
    for item in memories:
        user_text = item.get("user_text", "")[:80]
        ai_text = item.get("ai_text", "")[:60]
        importance = item.get("importance", 0)
        marker = "\u2605" if importance >= 0.7 else "\u00b7"
        line = f"{marker} {user_text}"
        if ai_text:
            line += f" \u2192 {ai_text}"
        lines.append(line)
    return "\n".join(lines)
