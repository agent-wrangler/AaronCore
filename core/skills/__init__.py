# 技能注册中心
import os
import json
import importlib.util
from pathlib import Path

SKILLS_DIR = os.path.join(os.path.dirname(__file__))
_skill_registry = {}

# ── 技能商店状态持久化 ──
_STORE_PATH = Path(SKILLS_DIR).parent.parent / "memory_db" / "skill_store.json"


def _load_store() -> dict:
    if _STORE_PATH.exists():
        try:
            return json.loads(_STORE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"native": {}, "mcp": {}}


def _save_store(store: dict):
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def load_skill_metadata(skill_path):
    """加载 skill 元数据 json"""
    json_path = skill_path.with_suffix('.json')
    if json_path.exists():
        try:
            return json.load(open(json_path, 'r', encoding='utf-8'))
        except Exception as e:
            print(f"[Skills] Failed to load metadata {json_path.name}: {e}")
    return {}


def load_skills():
    """扫描 skills 目录，自动加载所有技能并注册"""
    global _skill_registry
    _skill_registry = {}
    store = _load_store()
    native = store.get("native", {})

    for f in os.listdir(SKILLS_DIR):
        if f.endswith('.json'):
            continue

        skill_path = os.path.join(SKILLS_DIR, f)
        if os.path.isfile(skill_path) and f.endswith('.py') and not f.startswith('_'):
            skill_name = f[:-3]
            meta = load_skill_metadata(Path(skill_path))

            try:
                spec = importlib.util.spec_from_file_location(skill_name, skill_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                exec_func = getattr(module, 'execute', None) or getattr(module, 'run', None)
                if callable(exec_func):
                    # 检查 skill_store.json 中的启用状态
                    enabled = native.get(skill_name, {}).get("enabled", True)
                    _skill_registry[skill_name] = {
                        'name': meta.get('name', skill_name),
                        'keywords': [],
                        'anti_keywords': [],
                        'description': meta.get('description', ''),
                        'parameters': meta.get('parameters'),
                        'priority': meta.get('priority', 10),
                        'category': meta.get('category', '\u901a\u7528'),
                        'status': 'ready' if enabled else 'disabled',
                        'enabled': enabled,
                        'source': 'native',
                        'execute': exec_func,
                        'metadata': meta,
                    }
                    print(f"[Skills] Loaded: {skill_name}" + ("" if enabled else " (disabled)"))
                else:
                    print(f"[Skills] Skipped {skill_name}: no execute/run function")
            except Exception as e:
                print(f"[Skills] Failed to load {skill_name}: {e}")

    # 加载 MCP 技能（如果有）
    mcp_skills = store.get("mcp", {})
    for skill_id, info in mcp_skills.items():
        if skill_id not in _skill_registry:
            _skill_registry[skill_id] = info

    return _skill_registry


def get_skill(name):
    """获取单个技能（disabled 的返回 None）"""
    if not _skill_registry:
        load_skills()
    skill = _skill_registry.get(name)
    if skill and skill.get('status') == 'disabled':
        return None
    return skill


def get_all_skills():
    """获取所有已启用的技能（路由和执行链使用）"""
    if not _skill_registry:
        load_skills()
    return {k: v for k, v in _skill_registry.items() if v.get('status') != 'disabled'}


def get_all_skills_for_ui():
    """获取全部技能（含 disabled），给前端展示用"""
    if not _skill_registry:
        load_skills()
    return _skill_registry


def set_skill_enabled(name: str, enabled: bool) -> bool:
    """切换技能启用/禁用状态，返回是否成功"""
    if not _skill_registry:
        load_skills()
    skill = _skill_registry.get(name)
    if not skill:
        return False
    skill['enabled'] = enabled
    skill['status'] = 'ready' if enabled else 'disabled'
    # 持久化
    store = _load_store()
    source = skill.get('source', 'native')
    section = store.setdefault(source, {})
    section[name] = {"enabled": enabled}
    _save_store(store)
    return True


def register_mcp_skill(skill_id: str, skill_info: dict):
    """注册一个 MCP 工具为技能（Phase 2 使用）"""
    if not _skill_registry:
        load_skills()
    skill_info['keywords'] = []
    skill_info['anti_keywords'] = []
    skill_info.setdefault('source', 'mcp')
    skill_info.setdefault('enabled', True)
    skill_info.setdefault('status', 'ready')
    _skill_registry[skill_id] = skill_info
    # 持久化到 store
    store = _load_store()
    mcp = store.setdefault("mcp", {})
    mcp[skill_id] = {"enabled": True}
    _save_store(store)


def unregister_mcp_skill(skill_id: str):
    """移除一个 MCP 技能"""
    _skill_registry.pop(skill_id, None)
    store = _load_store()
    store.get("mcp", {}).pop(skill_id, None)
    _save_store(store)


def execute_skill(skill_name, user_input):
    """兼容层：保留旧接口，内部仍走注册表"""
    skill = get_skill(skill_name)
    if skill and callable(skill.get('execute')):
        try:
            return skill['execute'](user_input)
        except Exception as e:
            return f"\u6267\u884c\u5931\u8d25: {str(e)[:50]}"
    return None


# 启动时自动加载
load_skills()
