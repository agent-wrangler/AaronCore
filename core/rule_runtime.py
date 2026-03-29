import json
import time
import fnmatch
from datetime import datetime
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


# ── L7 路由约束 ──────────────────────────────────────────

_constraint_cache = None
_constraint_cache_time = 0
_CACHE_TTL = 60  # 秒，最多每分钟重新加载一次


def invalidate_constraint_cache():
    """写入新规则后调用，强制下次重新加载。"""
    global _constraint_cache, _constraint_cache_time
    _constraint_cache = None
    _constraint_cache_time = 0


def get_active_constraints() -> list[dict]:
    # Legacy keyword routing constraints are retired from runtime.
    return []
    """加载并缓存有效的 L7 路由约束。被 _score_text() 每条消息调用，必须快。"""
    global _constraint_cache, _constraint_cache_time
    now = time.time()
    if _constraint_cache is not None and (now - _constraint_cache_time) < _CACHE_TTL:
        return _constraint_cache

    rules = load_rules()
    constraints = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        c = rule.get("constraint")
        if not c or not isinstance(c, dict):
            continue
        # 置信度门槛：< 0.6 不作为路由约束
        if float(c.get("confidence", 0) or 0) < 0.6:
            continue
        # TTL 过期检查
        created = c.get("created_at") or rule.get("created_at", "")
        ttl_days = int(c.get("ttl_days", 30) or 30)
        if created:
            try:
                age = (datetime.now() - datetime.fromisoformat(created)).days
                if age > ttl_days:
                    continue
            except Exception:
                pass
        constraints.append(c)

    _constraint_cache = constraints
    _constraint_cache_time = now
    return constraints


def match_constraint(text: str, constraint: dict) -> bool:
    """检查用户输入是否匹配约束的 patterns/keywords。"""
    for kw in (constraint.get("keywords") or []):
        if kw and kw in text:
            return True
    for pat in (constraint.get("patterns") or []):
        if pat and fnmatch.fnmatch(text, pat):
            return True
    return False
