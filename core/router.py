# Router - 技能路由层
# 负责：意图解析、关系模式检测、技能候选识别、路由输出

import re

from core.skills import get_all_skills
from core.rule_runtime import has_rule


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

    return {
        'chat_score': chat_score,
        'skill_score': skill_score,
        'emotion_score': emotion_score,
        'matched_skill': matched_skill,
        'matched_keyword': matched_keyword,
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

    # 技能候选保护层：只要存在明确技能候选，就不能直接降为纯聊天
    if scores['matched_skill'] and scores['skill_score'] >= 2.0:
        route_type = 'hybrid' if scores['emotion_score'] > 0 else 'skill'
        return {
            'mode': route_type,
            'skill': scores['matched_skill'],
            'confidence': 0.9,
            'reason': f"命中技能候选: {scores['matched_keyword']}",
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
