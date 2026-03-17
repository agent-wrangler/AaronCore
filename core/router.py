# Router - 技能路由层
# 负责：意图解析、关系模式检测、技能候选识别、路由输出

import re
import os
import json
import time

from core.skills import get_all_skills
from core.rule_runtime import has_rule

# 文章选择状态文件
_article_state_path = os.path.join(os.path.dirname(__file__), 'skills', '.article_state.json')


CHAT_WORDS = [
    '你好', '哈喽', '嗨', '在吗', '哈哈', '嘿嘿', '谢谢', '早上好', '晚上好', '你是谁', '你是？', '你叫什么', '你叫什么啊', '知道我是谁吗', '你还会什么', '你会什么'
]

EMOTION_WORDS = [
    '累', '烦', '心情', '难过', '开心', '郁闷', '压力', '治愈', '温柔', '安慰', '陪我'
]

TASK_WORDS = [
    '查', '生成', '画', '打开', '搜索', '搜', '帮我', '给我',
    '再来一个', '换一个', '长一点', '继续讲',
]
# 弱任务词：单独出现不加分，需要搭配技能关键词才有效
WEAK_TASK_WORDS = ['做', '写', '讲', '看', '来个', '想听', '想看', '想要']

# 请求结构词：表达"请你帮我做某事"的句式
REQUEST_STRUCTURE = ['帮我', '给我', '请你', '帮忙', '一下', '能不能帮', '可以帮']

# 自述模式：用户在陈述自身信息，不是下达任务
INFORM_PATTERNS = ['我在', '我叫', '我是', '我住', '人在', '定居']

# 讨论弱化词（扩展版）：命中时压制技能触发
DISCUSS_WORDS = [
    '或者', '都可以', '都行', '也行', '也可以',
    '好不好', '你觉得', '你说呢', '要不要',
    '还是说', '比如说', '比如', '什么的',
    # 新增：假设/探询/讨论句式
    '是不是', '我觉得', '如果', '假如', '万一',
]

# 探询词：单独出现是讨论，但搭配任务词时是请求
INQUIRY_WORDS = ['有没有', '能不能', '可不可以', '怎么样']

STOCK_HINT_WORDS = [
    '股票', '股价', '行情', '报价', '大盘', '指数', '纳指', '标普', '道指', '沪指', '深成指', '创业板', '上证', '美股', 'a股'
]

STOCK_QUERY_HINT_WORDS = ['多少', '怎么样', '现在', '涨跌', '查', '看下', '看一眼', '报价']
ABILITY_QUERY_WORDS = [
    '你会什么', '你还会什么', '你都会什么', '你能做什么', '你现在能做什么', '你能干什么', '你有哪些能力', '你会哪些技能'
]
SELF_REPAIR_QUERY_HINTS = [
    '修改自己的代码', '改自己的代码', '修自己的代码', '自己修正', '自我修正', '自动修正', '自己改代码', '自己修代码',
    '发现自己错了', '知道自己错了', '自己能修正', '自己能改', '自己能修', '自己学会修正'
]

# ── 交互阶段关键词库（v2 升级）──────────────────────────────────

# 纠偏词：用户正在纠正 Nova 的理解偏差
CORRECT_WORDS = [
    '不对', '不是这个意思', '我不是让你', '你理解错了', '你搞错了',
    '不是这样', '说错了', '答错了', '答偏了', '跑偏了', '你没听懂',
    '我没说', '我没让你', '看我问的什么', '我说的不是',
]

# 确认词：用户授权执行
CONFIRM_WORDS = [
    '那就这个', '开始吧', '就按你说的', '可以执行', '那就做吧',
    '就这样', '好的开始', '确认', '就这个', '那就按这个',
    '嗯就这样', '行就按这个来', '好你执行', '那就开始',
]

# 探索词：合并讨论+探询，但不含强假设词（单独处理）
EXPLORE_WORDS = [
    '或者', '都可以', '都行', '也行', '也可以',
    '好不好', '你觉得', '你说呢', '要不要',
    '还是说', '比如说', '比如', '什么的',
    '是不是', '我觉得',
    '有没有', '能不能', '可不可以', '怎么样',
    '有什么建议', '帮我想想', '比较一下', '试试',
    '举个例子', '有没有方案',
]

# 强假设词（独立处理，无条件 → explore）
STRONG_HYPOTHETICAL = ('如果', '假如', '万一')

# ── 语气关键词库 ────────────────────────────────────────────────

COMMAND_TONE_WORDS = ['帮我查', '查一下', '打开', '给我看', '帮我做', '帮我写', '帮我画']
REQUEST_TONE_WORDS = ['能不能帮', '可以帮我', '麻烦', '请你', '帮帮忙', '能帮我']
SUGGEST_TONE_WORDS = ['或者', '要不要', '可以试试', '不如', '要不', '试试看']
HYPOTHETICAL_TONE_WORDS = ('如果', '假如', '万一', '要是', '假设')
DISCUSS_TONE_WORDS = ['你觉得', '好不好', '怎么样', '你说呢', '你看呢']
CORRECT_TONE_WORDS = ['不对', '不是这个', '不是这样', '不是我说的', '你理解错了', '搞错了', '答偏了', '你没听懂', '不是这个意思', '我没说']
COMPLAINT_TONE_WORDS = ['又来了', '烦死了', '不好用', '怎么又', '老是', '总是', '一直']

# ── 阶段 → 旧 intent 映射 ──────────────────────────────────────

_STAGE_TO_INTENT = {
    'social':  'chat',
    'explore': 'discuss',
    'inform':  'inform',
    'request': 'task',
    'confirm': 'task',
    'correct': 'chat',
}


def _stage_to_legacy_intent(stage: str) -> str:
    """把 6 阶段映射回旧的 4 类 intent，保证向后兼容"""
    return _STAGE_TO_INTENT.get(stage, 'chat')


def classify_stage(text: str, scores: dict) -> str:
    """
    6 阶段交互识别（v2 升级）。
    返回: 'correct' | 'confirm' | 'inform' | 'explore' | 'request' | 'social'
    优先级从高到低排列。
    """
    text = (text or '').strip()
    if not text:
        return 'social'

    # ── P0: 纠偏最高优先 ──
    if any(w in text for w in CORRECT_WORDS):
        return 'correct'

    # ── P1: 确认阶段 ──
    if any(w in text for w in CONFIRM_WORDS):
        # 排除同时有强任务词+技能关键词的情况（"好的帮我查天气" → request）
        has_task = _has_task_signal(text)
        has_skill_kw = scores.get('matched_skill') is not None
        if not (has_task and has_skill_kw):
            return 'confirm'

    # ── P2: 自述 inform ──
    is_inform = any(p in text for p in INFORM_PATTERNS)
    if is_inform and not _has_task_signal(text):
        return 'inform'

    # ── P3: 假设/探索 ──
    if any(p in text for p in STRONG_HYPOTHETICAL):
        return 'explore'
    if any(w in text for w in EXPLORE_WORDS):
        has_task = _has_task_signal(text)
        has_skill_kw = scores.get('matched_skill') is not None
        # 多关键词命中（skill_score >= 2.0）说明是强技能信号，不算探索
        strong_skill = scores.get('skill_score', 0) >= 2.0 and has_skill_kw
        if not (has_task and has_skill_kw) and not strong_skill:
            return 'explore'

    # ── P4: 任务请求（复用 evidence 门槛）──
    evidence = 0
    if any(w in text for w in TASK_WORDS):
        evidence += 1
    if any(w in text for w in REQUEST_STRUCTURE):
        evidence += 1
    if scores.get('matched_skill') is not None:
        evidence += 1
    has_weak = any(w in text for w in WEAK_TASK_WORDS)
    if has_weak and scores.get('matched_skill') is not None:
        evidence = max(evidence, 2)
    if scores.get('skill_score', 0) >= 2.0 and scores.get('matched_skill') is not None:
        evidence = max(evidence, 2)
    if evidence >= 2:
        return 'request'

    # ── P5: 社交（闲聊+情绪）──
    if any(w in text for w in CHAT_WORDS) or any(w in text for w in EMOTION_WORDS):
        return 'social'

    # ── 默认 social ──
    return 'social'


def classify_tone(text: str) -> str:
    """
    7 语气识别，纯关键词规则。
    返回: 'correct' | 'complaint' | 'hypothetical' | 'command' | 'request' | 'suggest' | 'discuss'
    """
    text = (text or '').strip()
    if not text:
        return 'discuss'

    # 纠错/抱怨优先
    if any(w in text for w in CORRECT_TONE_WORDS):
        return 'correct'
    if any(w in text for w in COMPLAINT_TONE_WORDS):
        return 'complaint'

    # 假设态
    if any(w in text for w in HYPOTHETICAL_TONE_WORDS):
        return 'hypothetical'

    # 指令 vs 请求
    if any(w in text for w in COMMAND_TONE_WORDS):
        return 'command'
    if any(w in text for w in REQUEST_TONE_WORDS):
        return 'request'

    # 提议/讨论
    if any(w in text for w in SUGGEST_TONE_WORDS):
        return 'suggest'
    if any(w in text for w in DISCUSS_TONE_WORDS):
        return 'discuss'

    return 'discuss'


def detect_relationship_mode(text: str) -> str:
    """检测关系模式：assistant / friend / executor"""
    text_lower = text.lower()

    friend_keywords = ['累', '烦', '心情', '难过', '开心', '想聊', '陪我', '郁闷', '压力']
    if any(kw in text_lower for kw in friend_keywords):
        return 'friend'

    executor_keywords = ['规划', '做一个', '帮我完成', '项目', '系统', '设计', '开发']
    if any(kw in text_lower for kw in executor_keywords):
        return 'executor'

    return 'assistant'


def _is_suggestion_or_discussion(text: str) -> bool:
    """检测用户是在建议/讨论，而不是下达指令"""
    return any(p in text for p in DISCUSS_WORDS)


def _has_task_signal(text: str) -> bool:
    """检测是否有任务信号（动作词或请求结构）"""
    has_action = any(w in text for w in TASK_WORDS)
    has_request = any(w in text for w in REQUEST_STRUCTURE)
    return has_action or has_request


def classify_intent(text: str, scores: dict) -> str:
    """
    意图分层分类，在技能匹配之前先判断用户意图。
    返回: 'task' | 'discuss' | 'inform' | 'chat'
    只有 task 才允许进入技能匹配。
    """
    text = (text or '').strip()
    if not text:
        return 'chat'

    has_task = _has_task_signal(text)
    has_skill_kw = scores.get('matched_skill') is not None

    # ── discuss：讨论/建议/假设句式 ──
    # 但如果同时有明确任务词 + 技能关键词，说明是请求（如"能不能帮我查天气"）
    is_discuss = any(p in text for p in DISCUSS_WORDS)
    is_inquiry = any(p in text for p in INQUIRY_WORDS)

    # 强假设词（如果/假如/万一）：即使有任务词也走 discuss
    # "如果要画海报的话" 是假设，不是请求
    # 注意：STRONG_HYPOTHETICAL 已在模块级别定义
    is_hypothetical = any(p in text for p in STRONG_HYPOTHETICAL)

    if is_hypothetical:
        return 'discuss'
    if is_discuss and not (has_task and has_skill_kw):
        return 'discuss'
    if is_inquiry and not has_task and not has_skill_kw:
        return 'discuss'

    # ── inform：自述模式（我在X/我叫X）且无任务词 ──
    is_inform = any(p in text for p in INFORM_PATTERNS)
    if is_inform and not has_task:
        return 'inform'

    # ── task：组合证据门槛 ──
    # 至少满足 2 项：A.动作词 B.请求结构 C.技能关键词命中
    evidence = 0
    if any(w in text for w in TASK_WORDS):
        evidence += 1
    if any(w in text for w in REQUEST_STRUCTURE):
        evidence += 1
    if has_skill_kw:
        evidence += 1
    # 弱任务词 + 技能关键词也算 task
    has_weak = any(w in text for w in WEAK_TASK_WORDS)
    if has_weak and has_skill_kw:
        evidence = max(evidence, 2)
    # 多个技能关键词命中（skill_score >= 2.0）= 强技能信号，直接算 task
    # 例如"常州天气怎么样"命中了常州+天气两个关键词
    if scores.get('skill_score', 0) >= 2.0 and has_skill_kw:
        evidence = max(evidence, 2)

    if evidence >= 2:
        return 'task'

    # ── chat：默认 ──
    return 'chat'


# ── 复合句拆解 ──────────────────────────────────────────────

_CLAUSE_SPLITTERS = re.compile(
    r'[，,。！？；\n]|'
    r'(?<=.)(?:然后|接着|顺便|另外|还有)(?=.)'
)


def split_clauses(text: str) -> list[str]:
    """复合句拆成子句列表，单句原样返回 [text]"""
    parts = _CLAUSE_SPLITTERS.split(text)
    clauses = [p.strip() for p in parts if p.strip()]
    return clauses if clauses else [text]


def analyze_compound(text: str, skills: dict):
    """
    复合句分析：拆句 → 逐句分类 → 选出最强 task 子句。
    单句返回 None（信号：走原有路径）。
    """
    clauses = split_clauses(text)
    if len(clauses) <= 1:
        return None

    results = []
    for c in clauses:
        sc = _score_text(c, skills)
        stage = classify_stage(c, sc)
        intent = _stage_to_legacy_intent(stage)
        tone = classify_tone(c)
        results.append({
            'clause': c, 'intent': intent, 'stage': stage, 'tone': tone, 'scores': sc,
        })

    # 找最强 task 子句（skill_score 最高）
    task_results = [r for r in results if r['intent'] == 'task']
    if task_results:
        best = max(task_results, key=lambda r: r['scores'].get('skill_score', 0))
        return {
            'intent': 'task',
            'stage': best['stage'],
            'tone': best['tone'],
            'action_clause': best['clause'],
            'scores': best['scores'],
            'clauses': results,
        }

    # 无 task → 取最后一个子句的意图
    last = results[-1]
    return {
        'intent': last['intent'],
        'stage': last['stage'],
        'tone': last['tone'],
        'action_clause': last['clause'],
        'scores': last['scores'],
        'clauses': results,
    }


def _score_text(text: str, skills: dict):
    text = (text or '').strip()
    chat_score = 0.0
    skill_score = 0.0
    emotion_score = 0.0
    matched_skill = None
    matched_keyword = None
    matched_keyword_len = 0

    is_suggestion = _is_suggestion_or_discussion(text)

    for w in CHAT_WORDS:
        if w in text:
            chat_score += 1.0

    for w in EMOTION_WORDS:
        if w in text:
            emotion_score += 1.0
            chat_score += 0.25

    # 建议/讨论句式 → 额外 boost chat
    if is_suggestion:
        chat_score += 1.5

    for w in TASK_WORDS:
        if w in text:
            skill_score += 1.0

    # 弱任务词：只有已经命中了技能关键词时才加分（后面补加）
    has_weak_task = any(w in text for w in WEAK_TASK_WORDS)

    WEATHER_ACTION_WORDS = ('天气', '气温', '温度', '下雨', '晴天', '多少度', '冷不冷', '热不热', '穿什么')

    # L7 路由约束：加载动态阻断/抑制集合
    _blocked_skills = set()
    _suppressed_skills = set()
    try:
        from core.rule_runtime import get_active_constraints, match_constraint
        for c in get_active_constraints():
            if match_constraint(text, c):
                sk = c.get("skill", "")
                if sk:
                    if c.get("type") == "block_skill":
                        _blocked_skills.add(sk)
                    elif c.get("type") == "suppress_skill":
                        _suppressed_skills.add(sk)
    except Exception:
        pass

    for skill_name, info in skills.items():
        keywords = info.get('keywords', []) or info.get('trigger', [])
        anti_keywords = info.get('anti_keywords', []) or []

        # 反例库检查：命中反例则整个技能跳过
        if anti_keywords and any(ak in text for ak in anti_keywords):
            continue

        # L7 动态阻断：和 anti_keywords 同级
        if skill_name in _blocked_skills:
            continue

        # computer_use 关键词匹配时去掉空格（用户常说"和豆包 聊"而非"和豆包聊"）
        _text_for_match = text.replace(' ', '') if skill_name == 'computer_use' else text
        for kw in keywords:
            if kw and kw in _text_for_match:
                # 天气技能特殊处理：纯城市名不触发，必须搭配天气动作词
                if skill_name == 'weather' and kw not in WEATHER_ACTION_WORDS:
                    if not any(aw in text for aw in WEATHER_ACTION_WORDS):
                        continue  # "我在常州" 不触发天气

                # 短关键词（<3字）降权：可能是泛指而非真正的技能请求
                if len(kw) < 3:
                    skill_score += 1.0
                else:
                    skill_score += 2.0
                if matched_skill is None:
                    matched_skill = skill_name
                    matched_keyword = kw
                    matched_keyword_len = len(kw)

    # 弱任务词只在有技能关键词命中时才生效
    if has_weak_task and matched_skill:
        skill_score += 0.5

    # 建议/讨论句式压制技能分
    if is_suggestion and skill_score > 0:
        skill_score *= 0.5

    # L7 动态抑制：技能匹配了但被软抑制，分数减半
    if matched_skill and matched_skill in _suppressed_skills:
        skill_score *= 0.5

    return {
        'chat_score': chat_score,
        'skill_score': skill_score,
        'emotion_score': emotion_score,
        'matched_skill': matched_skill,
        'matched_keyword': matched_keyword,
        'matched_keyword_len': matched_keyword_len if matched_skill else 0,
    }


def _looks_like_stock_query(text: str) -> bool:
    raw = (text or '').strip()
    if not raw:
        return False

    lower = raw.lower()
    if any(word in lower for word in STOCK_HINT_WORDS):
        return True

    if re.search(r'\b(?:sh|sz)\d{6}\b', lower):
        return True

    if re.fullmatch(r'\d{6}', raw):
        return True

    if re.search(r'(?<!\d)\d{6}(?!\d)', raw) and any(word in raw for word in STOCK_QUERY_HINT_WORDS):
        return True

    ticker_tokens = [token.upper() for token in re.findall(r'(?<![A-Za-z])([A-Za-z]{2,5})(?![A-Za-z])', raw)]
    ticker_tokens = [token for token in ticker_tokens if token not in {'AI', 'OK', 'HI'}]
    if not ticker_tokens:
        return False

    if any(word in raw for word in STOCK_QUERY_HINT_WORDS + STOCK_HINT_WORDS):
        return True

    stripped = raw.strip()
    if stripped.isascii() and stripped.upper() in ticker_tokens and 2 <= len(stripped) <= 5:
        return True

    return False


def _looks_like_ability_query(text: str) -> bool:
    raw = (text or '').strip()
    if not raw:
        return False
    return any(word in raw for word in ABILITY_QUERY_WORDS)


def _looks_like_meta_bug_report(text: str) -> bool:
    raw = (text or '').strip()
    if not raw:
        return False

    issue_words = [
        '有问题', '感觉有问题', '不对', '怪怪的', '尴尬', '误触发', '触发错了',
        '老是', '总是', '一直', '又给搞了', '检查下', '看下这个路径', '看看这个路径',
    ]
    context_words = [
        '路径', '窗口', '弹窗', '页面', '界面', '对话里', '聊天里', '这句', '这句话',
        '上面那句', '只要', '一出现', '跳出来', '弹出来', '到窗口', '流程',
    ]
    trigger_words = ['出现', '触发', '跳出', '弹出', '打开']
    code_words = ['代码', '小游戏', 'run_code', '编程游戏']

    has_issue = any(word in raw for word in issue_words)
    has_context = any(word in raw for word in context_words)
    has_trigger = any(word in raw for word in trigger_words)
    has_code_topic = any(word in raw for word in code_words)

    return has_code_topic and ((has_issue and has_context) or (has_context and has_trigger))


def _looks_like_answer_correction(text: str) -> bool:
    raw = (text or '').strip()
    if not raw:
        return False

    correction_words = [
        '不是这个', '不是我刚才说的', '不是这个意思', '我说的不是这个', '答歪了',
        '理解错了', '你理解错了', '看我问的什么', '我没说', '没让你查', '别顺着这个',
        '你又犯傻了', '说的不是这个',
    ]
    context_words = [
        '刚才', '之前', '前面', '上一句', '上句', '上一条', '前一条',
        '你刚才', '你前面', '你发', '那句', '这句',
    ]
    skill_words = [
        '天气', '故事', '股票', '图片', '画图', '代码', '小游戏',
        'weather', 'story', 'stock', 'draw', 'run_code',
    ]

    has_correction = any(word in raw for word in correction_words)
    has_context = any(word in raw for word in context_words)
    has_skill_ref = any(word in raw for word in skill_words)

    if any(word in raw for word in ['看我问的什么', '看清我问的什么', '我问的什么']):
        return True
    if '我没说' in raw and has_skill_ref:
        return True
    if '不是这个' in raw and (has_context or has_skill_ref):
        return True
    return has_correction and (has_context or has_skill_ref)


def _looks_like_self_repair_query(text: str) -> bool:
    raw = (text or '').strip()
    if not raw:
        return False

    if any(word in raw for word in SELF_REPAIR_QUERY_HINTS):
        return True

    asks_about_self = any(word in raw for word in ['你自己', '自己', '自我', '自动'])
    asks_about_code = any(word in raw for word in ['代码', '路由', '本体', '源码'])
    asks_about_repair = any(word in raw for word in ['修改', '修正', '改', '修'])
    asks_about_timing = any(word in raw for word in ['什么时候', '何时', '啥时候', '能不能', '会不会', '能否'])
    return asks_about_self and asks_about_code and asks_about_repair and asks_about_timing


def _looks_like_article_selection(text: str) -> bool:
    """用户回复序号选新闻写文章（需要有未过期的文章选择状态）"""
    raw = (text or '').strip()
    if not raw:
        return False
    # 纯数字："3"
    # 第N条："第3条"
    # 带文章意图："帮我把1写成文章""把第3条写成文章""1号写一篇"
    has_number = bool(re.search(r'\d{1,2}', raw))
    is_pure_number = bool(re.match(r'^\d{1,2}$', raw))
    has_nth = bool(re.search(r'\u7b2c\s*\d{1,2}\s*[\u6761\u4e2a\u7bc7\u53f7]?', raw))
    has_article_intent = any(w in raw for w in ('\u5199\u6210\u6587\u7ae0', '\u5199\u7bc7\u6587\u7ae0', '\u5199\u6587\u7ae0', '\u5199\u4e00\u7bc7', '\u751f\u6210\u6587\u7ae0'))
    if not ((is_pure_number or has_nth) or (has_number and has_article_intent)):
        return False
    try:
        with open(_article_state_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return time.time() - data.get("time", 0) < 600
    except Exception:
        return False


def _looks_like_article_follow_up(text: str) -> bool:
    """用户对文章的后续操作：重写、自己改、满意"""
    raw = (text or '').strip()
    if not raw:
        return False
    follow_up_words = (
        '\u91cd\u5199', '\u4e0d\u6ee1\u610f', '\u518d\u5199\u4e00\u904d', '\u91cd\u65b0\u5199', '\u6362\u4e2a\u5199\u6cd5',
        '\u6211\u81ea\u5df1\u6539', '\u6211\u6765\u6539', '\u81ea\u5df1\u7f16\u8f91', '\u6211\u6539',
        '\u53ef\u4ee5', '\u6ee1\u610f', '\u4e0d\u9519', '\u631a\u597d', '\u5b9a\u7a3f',
    )
    if not any(w in raw for w in follow_up_words):
        return False
    try:
        with open(_article_state_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return (time.time() - data.get("time", 0) < 1800
                and data.get("last_article") is not None)
    except Exception:
        return False


def route(text: str) -> dict:
    """统一路由入口，返回标准结构"""
    role = detect_relationship_mode(text or '')
    text = text or ''
    skills = get_all_skills()
    scores = _score_text(text, skills)

    if '笑话' in text:
        return {
            'mode': 'chat',
            'skill': None,
            'confidence': 0.95 if has_rule('humor_request_should_use_llm_generation', 'joke') else 0.92,
            'reason': '命中笑话请求，当前不走 story 技能',
            'params': {},
            'role': role,
            'stage': 'request', 'tone': 'command',
            'chat_score': max(scores['chat_score'], 0.8),
            'skill_score': 0.0,
            'emotion_score': scores['emotion_score'],
        }

    story_follow_words = ['故事有点短', '有点短', '太短', '再讲一个', '换一个故事', '换个故事', '继续讲', '你就会讲这一个', '讲长一点']
    if any(w in text for w in story_follow_words):
        return {
            'mode': 'skill',
            'skill': 'story',
            'confidence': 0.88,
            'reason': '命中故事追问延续语境',
            'params': {},
            'role': role,
            'stage': 'request', 'tone': 'command',
            'chat_score': scores['chat_score'],
            'skill_score': max(scores['skill_score'], 2.0),
            'emotion_score': scores['emotion_score'],
        }

    if _looks_like_answer_correction(text):
        return {
            'mode': 'chat',
            'skill': None,
            'confidence': 0.97,
            'reason': '命中上一轮纠偏/澄清反馈',
            'intent': 'answer_correction',
            'params': {},
            'role': role,
            'stage': 'correct', 'tone': 'correct',
            'chat_score': max(scores['chat_score'], 1.2),
            'skill_score': 0.0,
            'emotion_score': scores['emotion_score'],
        }

    if _looks_like_article_selection(text):
        return {
            'mode': 'skill',
            'skill': 'article',
            'confidence': 0.95,
            'reason': '命中文章选择序号（有待选新闻列表）',
            'params': {},
            'role': role,
            'stage': 'confirm', 'tone': 'command',
            'chat_score': scores['chat_score'],
            'skill_score': max(scores['skill_score'], 2.5),
            'emotion_score': scores['emotion_score'],
        }

    if _looks_like_article_follow_up(text):
        return {
            'mode': 'skill',
            'skill': 'article',
            'confidence': 0.95,
            'reason': '\u547d\u4e2d\u6587\u7ae0\u540e\u7eed\u64cd\u4f5c\uff08\u91cd\u5199/\u81ea\u6539/\u786e\u8ba4\uff09',
            'params': {},
            'role': role,
            'stage': 'confirm', 'tone': 'command',
            'chat_score': scores['chat_score'],
            'skill_score': max(scores['skill_score'], 2.5),
            'emotion_score': scores['emotion_score'],
        }

    if _looks_like_stock_query(text):
        return {
            'mode': 'skill',
            'skill': 'stock',
            'confidence': 0.92,
            'reason': '命中股票/指数查询意图',
            'params': {},
            'role': role,
            'stage': 'request', 'tone': 'command',
            'chat_score': scores['chat_score'],
            'skill_score': max(scores['skill_score'], 2.2),
            'emotion_score': scores['emotion_score'],
        }

    # Computer Use：如果 _score_text 已匹配到 computer_use，直接高置信度返回
    if scores.get('matched_skill') == 'computer_use':
        return {
            'mode': 'skill',
            'skill': 'computer_use',
            'confidence': 0.95,
            'reason': '命中桌面代理: ' + str(scores.get('matched_keyword', '')),
            'params': {},
            'role': role,
            'stage': 'request', 'tone': 'command',
            'chat_score': scores['chat_score'],
            'skill_score': max(scores['skill_score'], 3.0),
            'emotion_score': scores['emotion_score'],
        }

    if _looks_like_meta_bug_report(text):
        return {
            'mode': 'chat',
            'skill': None,
            'confidence': 0.96,
            'reason': '命中界面异常/误触发反馈',
            'intent': 'meta_bug_report',
            'params': {},
            'role': role,
            'stage': 'correct', 'tone': 'complaint',
            'chat_score': max(scores['chat_score'], 1.1),
            'skill_score': 0.0,
            'emotion_score': scores['emotion_score'],
        }

    if _looks_like_self_repair_query(text):
        return {
            'mode': 'chat',
            'skill': None,
            'confidence': 0.97,
            'reason': '命中自修正能力提问',
            'intent': 'self_repair_capability',
            'params': {},
            'role': role,
            'stage': 'explore', 'tone': 'discuss',
            'chat_score': max(scores['chat_score'], 1.2),
            'skill_score': 0.0,
            'emotion_score': scores['emotion_score'],
        }

    if _looks_like_ability_query(text):
        return {
            'mode': 'chat',
            'skill': None,
            'confidence': 0.95,
            'reason': '命中能力范围提问',
            'intent': 'ability_capability',
            'params': {},
            'role': role,
            'stage': 'social', 'tone': 'discuss',
            'chat_score': max(scores['chat_score'], 1.0),
            'skill_score': 0.0,
            'emotion_score': scores['emotion_score'],
        }

    # ── 意图分层门控（v2：交互阶段 + 语气识别）──
    # 复合句：拆句后逐句分类，取最强 task 子句
    compound = analyze_compound(text, skills)
    if compound is not None:
        intent = compound['intent']
        stage = compound.get('stage', 'social')
        tone = compound.get('tone', 'discuss')
        scores = compound['scores']  # 用 action_clause 的 scores
    else:
        # 单句：新分类器
        stage = classify_stage(text, scores)
        tone = classify_tone(text)
        intent = _stage_to_legacy_intent(stage)

    # ── 纠偏优先：correct 阶段强制走 chat，清除技能分 ──
    if stage == 'correct':
        return {
            'mode': 'chat',
            'skill': None,
            'confidence': 0.92,
            'reason': '纠偏优先：用户正在纠正理解偏差',
            'intent': intent,
            'params': {},
            'role': role,
            'stage': stage, 'tone': tone,
            'chat_score': max(scores['chat_score'], 1.0),
            'skill_score': 0.0,
            'emotion_score': scores['emotion_score'],
        }

    if intent in ('discuss', 'inform', 'chat'):
        # 非任务意图 → 直接走 chat，不进技能匹配
        conf = 0.85 if intent == 'discuss' else (0.75 if intent == 'inform' else 0.6)
        return {
            'mode': 'chat',
            'skill': None,
            'confidence': conf,
            'reason': f'意图分类: {intent}（阶段: {stage}），不进技能匹配',
            'intent': intent,
            'params': {},
            'role': role,
            'stage': stage, 'tone': tone,
            'chat_score': max(scores['chat_score'], 0.5),
            'skill_score': scores['skill_score'],
            'emotion_score': scores['emotion_score'],
        }

    # ── intent == 'task'（来自 request 或 confirm 阶段）：走技能匹配逻辑 ──

    # 技能候选层：根据关键词具体程度分级置信度
    # 长关键词（>=3字）+ 有任务词 = 高置信度，直接走
    # 短关键词或无任务词 = 低置信度，交给 LLM 裁决
    if scores['matched_skill'] and scores['skill_score'] >= 2.0:
        kw_len = scores.get('matched_keyword_len', 0)
        has_task_word = scores['skill_score'] > 2.0  # 除了关键词还命中了 TASK_WORDS
        has_emotion = scores['emotion_score'] > 0

        if kw_len >= 3 and has_task_word:
            confidence = 0.95  # "查天气""写篇文章" — 高置信度
        elif kw_len >= 3:
            confidence = 0.85  # "天气""新闻" — 中高置信度
        elif has_task_word:
            confidence = 0.7   # 短关键词 + 任务词 — 中置信度
        else:
            confidence = 0.5   # 短关键词，无任务词 — 低置信度，需要 LLM 确认

        route_type = 'hybrid' if has_emotion else 'skill'
        return {
            'mode': route_type,
            'skill': scores['matched_skill'],
            'confidence': confidence,
            'reason': f"\u547d\u4e2d\u6280\u80fd\u5019\u9009: {scores['matched_keyword']}",
            'params': {},
            'role': role,
            'stage': stage, 'tone': tone,
            'chat_score': scores['chat_score'],
            'skill_score': scores['skill_score'],
            'emotion_score': scores['emotion_score'],
        }

    if scores['chat_score'] > 0 and scores['skill_score'] <= 0:
        return {
            'mode': 'chat',
            'skill': None,
            'confidence': 0.9,
            'reason': '命中普通聊天语句',
            'params': {},
            'role': role,
            'stage': stage, 'tone': tone,
            'chat_score': scores['chat_score'],
            'skill_score': scores['skill_score'],
            'emotion_score': scores['emotion_score'],
        }

    # 没有显式技能关键词，但存在弱任务意图时，低置信度交给 LLM
    if scores['skill_score'] > 0 and scores['matched_skill']:
        return {
            'mode': 'hybrid',
            'skill': scores['matched_skill'],
            'confidence': 0.45,
            'reason': '弱技能信号，需 LLM 确认',
            'params': {},
            'role': role,
            'stage': stage, 'tone': tone,
            'chat_score': scores['chat_score'],
            'skill_score': scores['skill_score'],
            'emotion_score': scores['emotion_score'],
        }

    # 有任务词但没命中任何技能关键词 → 纯聊天
    if scores['skill_score'] > 0 and not scores['matched_skill']:
        return {
            'mode': 'chat',
            'skill': None,
            'confidence': 0.7,
            'reason': '有任务词但无技能匹配，走聊天',
            'params': {},
            'role': role,
            'stage': stage, 'tone': tone,
            'chat_score': scores['chat_score'],
            'skill_score': scores['skill_score'],
            'emotion_score': scores['emotion_score'],
        }

    return {
        'mode': 'chat',
        'skill': None,
        'confidence': 0.6,
        'reason': '未命中技能候选，走普通对话',
        'params': {},
        'role': role,
        'stage': stage, 'tone': tone,
        'chat_score': scores['chat_score'],
        'skill_score': scores['skill_score'],
        'emotion_score': scores['emotion_score'],
    }
