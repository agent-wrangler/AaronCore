def init(**kwargs):
    return None


def is_registered_skill_name(skill_name: str) -> bool:
    return False


def normalize_route_result(result, user_input: str = "", source: str = "") -> dict:
    result = result if isinstance(result, dict) else {}
    mode = str(result.get("mode") or "chat").strip() or "chat"
    skill = str(result.get("skill") or "").strip()
    normalized = dict(result)
    normalized["mode"] = mode
    normalized.setdefault("rewritten_input", user_input)
    normalized.setdefault("source", source or result.get("source") or "fallback")
    if mode == "skill" and skill:
        return {
            "mode": "chat",
            "skill": skill,
            "intent": "missing_skill",
            "missing_skill": skill,
            "rewritten_input": user_input,
            "source": normalized["source"],
        }
    return normalized


def resolve_route(bundle: dict | None = None) -> dict:
    bundle = bundle if isinstance(bundle, dict) else {}
    user_input = str(bundle.get("user_input") or "").strip()
    return {"mode": "chat", "skill": "none", "rewritten_input": user_input, "source": "fallback"}


def resolve_route_fast(bundle: dict | None = None) -> dict:
    return resolve_route(bundle)


def llm_route(*args, **kwargs) -> dict:
    return {"mode": "chat", "skill": "none", "source": "fallback"}
