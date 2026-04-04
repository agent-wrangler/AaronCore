import json

from storage.paths import FEEDBACK_RULES_FILE as RULES_FILE


LEVEL_WEIGHT = {
    "once": 1,
    "session": 2,
    "short_term": 3,
    "long_term": 4,
}


def load_rules():
    if RULES_FILE.exists():
        try:
            return json.loads(RULES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def get_active_rules(scene: str = "", min_level: str = "once"):
    rules = load_rules()
    threshold = LEVEL_WEIGHT.get(min_level, 1)
    active = [
        rule
        for rule in rules
        if rule.get("enabled", True) and LEVEL_WEIGHT.get(rule.get("level", "once"), 1) >= threshold
    ]
    if not scene:
        return active
    return [rule for rule in active if rule.get("scene") == scene]


def has_rule(fix: str, scene: str = "", min_level: str = "once") -> bool:
    return any(rule.get("fix") == fix for rule in get_active_rules(scene, min_level=min_level))


def invalidate_constraint_cache():
    return None


def get_active_constraints() -> list[dict]:
    # Legacy keyword routing constraints are fully retired from runtime.
    return []


def match_constraint(text: str, constraint: dict) -> bool:
    # Legacy keyword/pattern constraints are retired together with runtime routing constraints.
    return False
