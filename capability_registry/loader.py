from capability_registry import get_all_skills, load_skills as _load_registry

_external_registry = None


def set_registry(registry):
    """Set an optional callable registry sink for compatibility."""
    global _external_registry
    _external_registry = registry


def load_skills():
    """Load runtime capabilities and optionally mirror execute handlers."""
    skills = _load_registry()
    if _external_registry is not None:
        for skill_name, info in skills.items():
            execute = info.get("execute") if isinstance(info, dict) else None
            if callable(execute) and skill_name not in _external_registry:
                _external_registry[skill_name] = execute
                print(f"[Skills] Registered: {skill_name}")
    return list(skills.keys())
