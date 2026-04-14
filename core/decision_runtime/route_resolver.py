import re


def init(**kwargs):
    return None


def is_registered_skill_name(skill_name: str) -> bool:
    return False


def looks_like_news_request(text: str) -> bool:
    raw = str(text or '').strip()
    return any(word in raw for word in ('新闻', '头条', '热点', '今日新闻'))


def normalize_route_result(result, user_input: str = '', source: str = '') -> dict:
    result = result if isinstance(result, dict) else {}
    mode = str(result.get('mode') or 'chat').strip() or 'chat'
    skill = str(result.get('skill') or '').strip()
    normalized = dict(result)
    normalized['mode'] = mode
    normalized.setdefault('rewritten_input', user_input)
    normalized.setdefault('source', source or result.get('source') or 'fallback')
    if mode == 'skill' and skill:
        return {
            'mode': 'chat',
            'skill': skill,
            'intent': 'missing_skill',
            'missing_skill': skill,
            'rewritten_input': user_input,
            'source': normalized['source'],
        }
    return normalized


def detect_story_follow_up_route(bundle: dict | None = None):
    bundle = bundle if isinstance(bundle, dict) else {}
    text = str(bundle.get('user_input') or '').strip()
    if text not in {'然后呢', '后来呢', '接着呢', '继续', '继续讲'}:
        return None
    history = bundle.get('l2') or []
    if not isinstance(history, list):
        return None
    latest = next((item for item in reversed(history) if isinstance(item, dict) and item.get('role') in ('nova', 'assistant')), None)
    content = str((latest or {}).get('content') or '')
    if '《' in content and '》' in content:
        return {'mode': 'skill', 'skill': 'story', 'source': 'context', 'rewritten_input': text}
    return None


def resolve_route(bundle: dict | None = None) -> dict:
    bundle = bundle if isinstance(bundle, dict) else {}
    user_input = str(bundle.get('user_input') or '').strip()
    follow_up = detect_story_follow_up_route(bundle)
    if follow_up:
        return follow_up
    return {'mode': 'chat', 'skill': 'none', 'rewritten_input': user_input, 'source': 'fallback'}


def resolve_route_fast(bundle: dict | None = None) -> dict:
    return resolve_route(bundle)


def llm_route(*args, **kwargs) -> dict:
    return {'mode': 'chat', 'skill': 'none', 'source': 'fallback'}
