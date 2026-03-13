import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
RULES_FILE = ROOT / 'memory_db' / 'feedback_rules.json'


def _load_rules():
    if RULES_FILE.exists():
        try:
            return json.loads(RULES_FILE.read_text(encoding='utf-8'))
        except Exception:
            return []
    return []


def _save_rules(rules):
    RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    RULES_FILE.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding='utf-8')


def classify_feedback(user_feedback: str, last_question: str = '', last_answer: str = '') -> dict:
    text = f"{last_question}\n{last_answer}\n{user_feedback}".strip()

    if any(k in text for k in ['不是笑话', '这不是笑话', '不好笑']):
        return {
            'type': 'llm_rule',
            'scene': 'joke',
            'problem': 'output_not_matching_intent',
            'fix': 'humor_request_should_use_llm_generation',
            'level': 'short_term'
        }

    if any(k in text for k in ['太短', '有点短', '讲长一点']):
        return {
            'type': 'llm_rule',
            'scene': 'story',
            'problem': 'length_too_short',
            'fix': 'story_should_expand_when_user_requests_more',
            'level': 'session'
        }

    if any(k in text for k in ['不该查', '不该调用', '走错', '不是这个技能']):
        return {
            'type': 'skill_route',
            'scene': 'routing',
            'problem': 'wrong_skill_selected',
            'fix': 'adjust_skill_routing_for_scene',
            'level': 'short_term'
        }

    if any(k in text for k in ['你还会什么', '别回空话', '别太傻', '别套话']):
        return {
            'type': 'execution_policy',
            'scene': 'chat',
            'problem': 'fallback_too_generic',
            'fix': 'ability_queries_should_answer_capabilities_directly',
            'level': 'short_term'
        }

    return {
        'type': 'user_pref',
        'scene': 'general',
        'problem': 'generic_feedback',
        'fix': 'keep_observing_and_refine',
        'level': 'session'
    }


def record_feedback_rule(user_feedback: str, last_question: str = '', last_answer: str = '') -> dict:
    rule = classify_feedback(user_feedback, last_question, last_answer)
    rules = _load_rules()
    item = {
        'id': f"rule_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        'source': 'user_feedback',
        'created_at': datetime.now().isoformat(),
        'enabled': True,
        'user_feedback': user_feedback,
        'last_question': last_question,
        'last_answer': last_answer,
        **rule,
    }
    rules.append(item)
    _save_rules(rules[-200:])
    return item
