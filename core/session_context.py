# L2 记忆提炼 — 从原始对话中提取结构化的短期认知
# 轻量实现：纯规则提取，不调 LLM，不用向量

import re
from datetime import datetime

# ── 话题检测关键词 ────────────────────────────────────────────
_TOPIC_RULES: list[tuple[list[str], str]] = [
    (["天气", "气温", "温度", "下雨", "下雪"], "天气"),
    (["股票", "股价", "涨", "跌", "大盘"], "股票"),
    (["画", "海报", "图片", "图"], "画图"),
    (["故事", "讲个", "小说", "童话"], "故事"),
    (["代码", "编程", "python", "bug", "报错"], "编程"),
    (["笑话", "段子", "搞笑"], "笑话"),
    (["新闻", "热点", "头条"], "新闻"),
    (["学习", "教程", "怎么做", "如何"], "学习"),
    (["MCP", "FastAPI", "API", "模型"], "技术"),
]

# ── 情绪检测关键词 ────────────────────────────────────────────
_MOOD_RULES: list[tuple[list[str], str]] = [
    (["累", "烦", "郁闷", "难过", "压力", "焦虑", "崩溃"], "低落"),
    (["开心", "哈哈", "太好了", "不错", "棒", "厉害"], "积极"),
    (["生气", "什么鬼", "搞什么", "垃圾", "废物"], "不满"),
    (["不对", "错了", "不是", "答偏了", "没听懂"], "纠正"),
    (["谢谢", "感谢", "辛苦"], "感谢"),
]

# ── 意图检测 ─────────────────────────────────────────────────
_INTENT_RULES: list[tuple[list[str], str]] = [
    (["帮我", "帮忙", "做一个", "写一个", "生成"], "任务委托"),
    (["什么是", "为什么", "怎么", "如何", "原理"], "知识提问"),
    (["讲个", "来个", "说个", "唱个"], "内容请求"),
    (["继续", "接着", "然后呢", "后来呢"], "延续追问"),
    (["你好", "嗨", "在吗", "早", "晚安"], "打招呼"),
]

# ── 交互阶段检测 ──────────────────────────────────────────────
# 请求阶段：用户明确要求执行某件事
_STAGE_REQUEST = [
    "帮我", "帮忙", "去做", "去找", "去问", "去查", "去看", "去发",
    "你去", "你帮", "你来", "你能不能", "能不能帮", "麻烦你", "麻烦帮",
    "执行", "运行", "启动", "打开", "发送", "查一下", "查下", "搜一下",
]
# 确认阶段：用户在确认/授权执行
_STAGE_CONFIRM = [
    "好的", "行", "可以", "就这样", "开始吧", "那就", "确认", "没问题",
    "就按", "按这个", "就这么", "搞吧", "干吧",
]
# 探索阶段：用户在讨论/提议，不是要求立即执行
_STAGE_EXPLORE = [
    "要不", "或者", "也可以", "感觉", "觉得", "是不是", "能不能",
    "如果", "假设", "要是", "万一", "考虑", "想想",
]
# 纠偏阶段：用户在纠正
_STAGE_CORRECT = [
    "不对", "不是", "错了", "不是这个", "不是这样", "我说的是",
    "你理解错了", "不是让你", "我只是",
]

# ── 语用态度检测 ──────────────────────────────────────────────
# 指令态：强烈执行意图
_ATTITUDE_COMMAND = [
    "去", "帮我去", "你去", "立刻", "马上", "现在", "直接",
    "必须", "一定要", "赶紧",
]
# 提议态：轻度建议，不强求
_ATTITUDE_SUGGEST = [
    "要不", "或者", "也行", "也可以", "都行", "随便", "无所谓",
]
# 讨论态：纯探讨，不要求执行
_ATTITUDE_DISCUSS = [
    "感觉", "觉得", "好像", "应该", "可能", "大概", "理论上",
    "按道理", "一般来说",
]

def _detect_topics(all_user_text: str) -> list[str]:
    """从用户文本中识别话题。"""
    found = []
    for keywords, topic in _TOPIC_RULES:
        if any(kw in all_user_text for kw in keywords):
            found.append(topic)
    return found or ["闲聊"]


def _detect_interaction_stage(current_input: str, user_texts: list[str]) -> str:
    """检测当前交互阶段。"""
    text = current_input.strip()
    # 纠偏优先级最高
    if any(w in text for w in _STAGE_CORRECT):
        return "纠偏"
    if any(w in text for w in _STAGE_CONFIRM):
        return "确认"
    if any(w in text for w in _STAGE_REQUEST):
        return "请求"
    if any(w in text for w in _STAGE_EXPLORE):
        return "探索"
    return "社交"


def _detect_attitude(current_input: str) -> str:
    """检测语用态度。"""
    text = current_input.strip()
    if any(w in text for w in _ATTITUDE_COMMAND):
        return "指令"
    if any(w in text for w in _ATTITUDE_SUGGEST):
        return "提议"
    if any(w in text for w in _ATTITUDE_DISCUSS):
        return "讨论"
    return "中性"



    """从用户文本中识别话题。"""
    found = []
    for keywords, topic in _TOPIC_RULES:
        if any(kw in all_user_text for kw in keywords):
            found.append(topic)
    return found or ["闲聊"]


def _detect_mood(user_texts: list[str]) -> str:
    """从最近几条用户消息中感知情绪，越近的权重越高。"""
    # 只看最近 3 条
    recent = user_texts[-3:] if user_texts else []
    text = " ".join(recent)
    for keywords, mood in _MOOD_RULES:
        if any(kw in text for kw in keywords):
            return mood
    return "平稳"


def _detect_intents(user_texts: list[str]) -> list[str]:
    """追踪用户最近的意图模式。"""
    intents = []
    seen = set()
    for text in reversed(user_texts[-5:]):
        for keywords, intent in _INTENT_RULES:
            if intent not in seen and any(kw in text for kw in keywords):
                intents.append(intent)
                seen.add(intent)
    return intents or ["自由对话"]


def _detect_follow_up(user_texts: list[str], nova_texts: list[str], current_input: str) -> dict:
    """检测需要延续的上下文线索。"""
    ctx: dict = {}

    # 故事延续：上一条 Nova 回复里有书名号
    if nova_texts:
        last_nova = nova_texts[-1]
        titles = re.findall(r"《(.+?)》", last_nova)
        if titles:
            ctx["story_title"] = titles[-1]

    # 追问检测：当前输入很短且像承接上文
    if current_input:
        text = current_input.strip()
        follow_words = ("继续", "接着", "然后呢", "后来呢", "接着呢", "还有呢", "呢", "吗")
        if len(text) <= 10 and any(text.endswith(w) or text.startswith(w) for w in follow_words):
            ctx["is_follow_up"] = True

    # 纠正检测：用户在纠正上一轮回复
    if user_texts and len(user_texts) >= 2:
        last_user = user_texts[-1]
        correction_words = ("不对", "不是", "错了", "我说的是", "不是这个")
        if any(w in last_user for w in correction_words):
            ctx["is_correction"] = True

    # 重复提问检测：用户连续问类似的问题
    if len(user_texts) >= 3:
        recent_3 = [t.strip() for t in user_texts[-3:]]
        if len(set(recent_3)) == 1:
            ctx["repeated_question"] = recent_3[0]

    return ctx


def extract_session_context(history: list, current_input: str = "") -> dict:
    """
    从最近对话中提炼结构化短期认知。

    返回 L2 板块：
    - topics:    话题识别 — 这轮对话在聊什么
    - mood:      情绪感知 — 用户当前情绪状态
    - intents:   意图追踪 — 用户的意图模式
    - follow_up: 上下文延续 — 需要接住的上下文线索
    """
    messages = history[-12:] if history else []
    user_texts = []
    nova_texts = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role", "")
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            user_texts.append(content)
        elif role in ("nova", "assistant"):
            nova_texts.append(content)

    if current_input:
        user_texts.append(current_input)

    all_user_text = " ".join(user_texts).lower()

    # ── 板块 1: 话题识别 ──
    topics = _detect_topics(all_user_text)

    # ── 板块 2: 情绪感知 ──
    mood = _detect_mood(user_texts)

    # ── 板块 3: 意图追踪 ──
    intents = _detect_intents(user_texts)

    # ── 板块 4: 上下文延续 ──
    follow_up = _detect_follow_up(user_texts, nova_texts, current_input)

    # ── 板块 5: 交互阶段 ──
    stage = _detect_interaction_stage(current_input, user_texts)

    # ── 板块 6: 语用态度 ──
    attitude = _detect_attitude(current_input)

    return {
        "topics": topics,
        "mood": mood,
        "intents": intents,
        "follow_up": follow_up,
        "stage": stage,
        "attitude": attitude,
    }
