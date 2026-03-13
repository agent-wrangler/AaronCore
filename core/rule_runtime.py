import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_FILE = ROOT / 'memory_db' / 'feedback_rules.json'


def load_rules():
    if RULES_FILE.exists():
        try:
            return json.loads(RULES_FILE.read_text(encoding='utf-8'))
        except Exception:
            return []
    return []


LEVEL_WEIGHT = {
    'once': 1,
    'session': 2,
    'short_term': 3,
    'long_term': 4,
}


def get_active_rules(scene: str = '', min_level: str = 'once'):
    rules = load_rules()
    threshold = LEVEL_WEIGHT.get(min_level, 1)
    active = [r for r in rules if r.get('enabled', True) and LEVEL_WEIGHT.get(r.get('level', 'once'), 1) >= threshold]
    if not scene:
        return active
    return [r for r in active if r.get('scene') == scene]


def has_rule(fix: str, scene: str = '', min_level: str = 'once') -> bool:
    rules = get_active_rules(scene, min_level=min_level)
    return any(r.get('fix') == fix for r in rules)
