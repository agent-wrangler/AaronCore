# 技能自动加载器
import os
import importlib.util
import sys

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")

# 外部传入的SKILL_FUNCTIONS注册表
_external_registry = None

def set_registry(registry):
    """设置外部注册表"""
    global _external_registry
    _external_registry = registry

def load_skills():
    """自动扫描并加载 skills 目录下的技能"""
    loaded = []
    
    if not os.path.exists(SKILLS_DIR):
        os.makedirs(SKILLS_DIR)
        print(f"[Skills] Created skills directory: {SKILLS_DIR}")
        return loaded
    
    for filename in os.listdir(SKILLS_DIR):
        if filename.endswith('.py') and not filename.startswith('_'):
            skill_name = filename[:-3]  # 去掉 .py
            module_path = os.path.join(SKILLS_DIR, filename)
            
            try:
                spec = importlib.util.spec_from_file_location(skill_name, module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # 查找模块中的函数并注册 - 追加而非覆盖
                if _external_registry is not None:
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if callable(attr) and not attr_name.startswith('_'):
                            # 只添加不存在的
                            if attr_name not in _external_registry:
                                _external_registry[attr_name] = attr
                                print(f"[Skills] Registered: {attr_name}")
                
                loaded.append(skill_name)
                print(f"[Skills] Loaded: {skill_name}")
            except Exception as e:
                print(f"[Skills] Failed to load {skill_name}: {e}")
    
    return loaded
