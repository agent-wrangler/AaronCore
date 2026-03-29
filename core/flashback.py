# 闪回引擎 — 对话中自动关联旧记忆
# 用户说话时扫描情绪/话题线索 → 搜 L3+L2 → 命中则返回 hint
# hint 注入 system prompt，LLM 自己决定要不要自然地提到
#
# 设计原则：
#   1. 不是每句话都闪回，要有情绪/线索触发
#   2. hint 是建议不是命令，LLM 觉得不合适可以忽略
#   3. 宁可漏掉也不要硬凑，"不经意间的深刻"靠的是精准

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 触发词：用户话里有这些才启动闪回搜索 ──

# 情绪波动
_EMOTION = ["烦", "累", "难", "焦", "压力", "崩溃", "无语", "头疼",
            "开心", "高兴", "终于", "成功", "搞定", "爽"]
# 回忆线索
_RECALL = ["想起", "记得", "那天", "之前", "上次", "以前", "当初"]
# 重复感（暗示模式）
_PATTERN = ["又", "还是", "总是", "每次", "一直", "老是", "依然"]
# 决策/坚持
_RESOLVE = ["坚持", "放弃", "犹豫", "纠结", "选择", "决定"]

_ALL_CUES = _EMOTION + _RECALL + _PATTERN + _RESOLVE


def _has_cue(text: str) -> bool:
    """检查用户输入里有没有情绪/线索触发词"""
    return any(c in text for c in _ALL_CUES)


def _extract_keywords(text: str) -> list[str]:
    """从文本提取中文关键词（2字以上）"""
    words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
    # 去掉触发词本身和太常见的词
    stop = set(_ALL_CUES) | {"什么", "怎么", "可以", "不是", "就是",
                              "这个", "那个", "因为", "所以", "但是"}
    return list(set(w for w in words if w not in stop))


def _match_score(keywords: list[str], text: str) -> float:
    """关键词命中率"""
    if not keywords or not text:
        return 0.0
    hits = sum(1 for kw in keywords if kw in text)
    return hits / len(keywords)


def _load_l3() -> list:
    """直接读 L3 长期记忆"""
    try:
        path = ROOT / "memory_db" / "long_term.json"
        data = json.loads(path.read_text("utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _search_l2(query: str, limit: int = 5) -> list:
    """调用 L2 搜索"""
    try:
        from core.l2_memory import search_relevant
        return search_relevant(query, limit=limit)
    except Exception:
        return []


def detect_flashback(user_input: str) -> str | None:
    """
    扫描用户输入，搜索关联旧记忆，返回闪回 hint 或 None。

    返回的 hint 直接注入 system prompt，LLM 决定是否自然融入回复。
    """
    if not user_input or len(user_input) < 4:
        return None

    # 1. 没有情绪/线索触发词 → 不闪回
    if not _has_cue(user_input):
        return None

    # 2. 提取关键词
    keywords = _extract_keywords(user_input)
    if not keywords:
        return None

    # 3. 搜 L3 长期记忆
    best = None
    best_score = 0.0
    best_source = ""

    for mem in _load_l3():
        if not isinstance(mem, dict):
            continue
        event = mem.get("event", "")
        score = _match_score(keywords, event)
        if score > best_score and score >= 0.2:
            best_score = score
            best = mem
            best_source = "l3"

    # 4. L3 没找到好的 → 搜 L2
    if best_score < 0.3:
        for mem in _search_l2(user_input, limit=5):
            if not isinstance(mem, dict):
                continue
            mem_text = mem.get("user_text", "") + " " + mem.get("ai_text", "")
            score = _match_score(keywords, mem_text)
            if score > best_score and score >= 0.25:
                best_score = score
                best = mem
                best_source = "l2"

    if not best:
        return None

    # 5. 生成 hint
    if best_source == "l3":
        event = best.get("event", "")
        date = best.get("created_at", "")[:10]
        hint = (
            f"[联想] 你的记忆里闪过一段画面（{date}）：{event}\n"
            f"如果跟当前对话有自然的关联，可以不经意地提到这段记忆，"
            f"比如「你说的这个让我想起之前...」。"
            f"不要生硬，不相关就完全忽略这条提示。"
        )
    else:
        user_text = best.get("user_text", "")[:80]
        date = best.get("created_at", "")[:10]
        hint = (
            f"[联想] 你隐约记得之前的一段对话（{date}）：主人说过「{user_text}」\n"
            f"如果跟现在聊的内容有自然关联，可以不经意地提到。"
            f"不要生硬，不相关就完全忽略。"
        )

    return hint
