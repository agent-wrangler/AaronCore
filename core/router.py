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
    '查', '做', '生成', '画', '写', '打开', '搜索', '搜', '讲', '看', '帮我', '给我', '来个', '想听', '想看', '想要', '再来一个', '换一个', '长一点', '继续讲'
]

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


def _score_text(text: str, skills: dict):
    text = (text or '').strip()
    chat_score = 0.0
    skill_score = 0.0
    emotion_score = 0.0
    matched_skill = None
    matched_keyword = None
    matched_keyword_len = 0

    for w in CHAT_WORDS:
        if w in text:
            chat_score += 1.0

    for w in EMOTION_WORDS:
        if w in text:
            emotion_score += 1.0
            chat_score += 0.25

    for w in TASK_WORDS:
        if w in text:
            skill_score += 1.0

    for skill_name, info in skills.items():
        keywords = info.get('keywords', []) or info.get('trigger', [])
        for kw in keywords:
            if kw and kw in text:
                skill_score += 2.0
                if matched_skill is None:
                    matched_skill = skill_name
                    matched_keyword = kw
                    matched_keyword_len = len(kw)

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
    if not (re.match(r'^\d{1,2}$', raw) or re.search(r'第\s*\d{1,2}\s*[条个篇]', raw)):
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
            'chat_score': scores['chat_score'],
            'skill_score': max(scores['skill_score'], 2.2),
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
            'chat_score': max(scores['chat_score'], 1.0),
            'skill_score': 0.0,
            'emotion_score': scores['emotion_score'],
        }

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
            'chat_score': scores['chat_score'],
            'skill_score': scores['skill_score'],
            'emotion_score': scores['emotion_score'],
        }

    # 没有显式技能关键词，但存在明显任务意图时，先不掉进纯聊天
    if scores['skill_score'] > 0:
        return {
            'mode': 'hybrid',
            'skill': scores['matched_skill'],
            'confidence': 0.65,
            'reason': '存在任务意图，进入技能候选/混合路由',
            'params': {},
            'role': role,
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
        'chat_score': scores['chat_score'],
        'skill_score': scores['skill_score'],
        'emotion_score': scores['emotion_score'],
    }
