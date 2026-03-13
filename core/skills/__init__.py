# 技能注册中心
import os
import json
import importlib.util
from pathlib import Path

SKILLS_DIR = os.path.join(os.path.dirname(__file__))
_skill_registry = {}


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
                    _skill_registry[skill_name] = {
                        'name': meta.get('name', skill_name),
                        'keywords': meta.get('keywords', []),
                        'description': meta.get('description', ''),
                        'priority': meta.get('priority', 10),
                        'category': meta.get('category', '通用'),
                        'status': 'ready',
                        'execute': exec_func,
                        'metadata': meta,
                    }
                    print(f"[Skills] Loaded: {skill_name}")
                else:
                    print(f"[Skills] Skipped {skill_name}: no execute/run function")
            except Exception as e:
                print(f"[Skills] Failed to load {skill_name}: {e}")

    return _skill_registry


def get_skill(name):
    """获取单个技能"""
    if not _skill_registry:
        load_skills()
    return _skill_registry.get(name)


def get_all_skills():
    """获取所有技能"""
    if not _skill_registry:
        load_skills()
    return _skill_registry


def execute_skill(skill_name, user_input):
    """兼容层：保留旧接口，内部仍走注册表"""
    skill = get_skill(skill_name)
    if skill and callable(skill.get('execute')):
        try:
            return skill['execute'](user_input)
        except Exception as e:
            return f"执行失败: {str(e)[:50]}"
    return None


# 启动时自动加载
load_skills()
