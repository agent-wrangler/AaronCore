# route_resolver - 多阶段路由决策
# 从 agent_final.py 提取

import json

# ── 注入依赖 ──────────────────────────────────────────────
_nova_route = None
_debug_write = lambda stage, data: None
_think = None
_get_all_skills = lambda: {}
_nova_core_ready = False


def init(*, nova_route=None, debug_write=None, think=None,
         get_all_skills=None, nova_core_ready=False):
    global _nova_route, _debug_write, _think, _get_all_skills, _nova_core_ready
    if nova_route:
        _nova_route = nova_route
    if debug_write:
        _debug_write = debug_write
    if think:
        _think = think
    if get_all_skills:
        _get_all_skills = get_all_skills
    _nova_core_ready = nova_core_ready


# ── 路由 prompt ───────────────────────────────────────────

def build_router_prompt(bundle: dict) -> str:
    l1 = bundle["l1"]
    l3 = bundle["l3"]
    l4 = bundle["l4"]
    l5 = bundle["l5"]
    l8 = bundle.get("l8", [])
    msg = bundle["user_input"]

    return f"""
你是 NovaCore 的路由判断器。你要先判断这句话是普通聊天，还是需要技能执行。

用户输入：{msg}

L1最近对话：
{json.dumps(l1, ensure_ascii=False)}

L3长期记忆：
{json.dumps(l3, ensure_ascii=False)}

L4人格信息：
{json.dumps(l4, ensure_ascii=False)}

L5技能知识：
{json.dumps(l5, ensure_ascii=False)}

L8已学知识：
{json.dumps(l8, ensure_ascii=False)}

请只返回JSON：
{{
  "mode": "chat|skill",
  "skill": "weather|story|none",
  "reason": "简短说明",
  "rewritten_input": "如果需要技能，可重写成更适合技能执行的输入，否则原样返回"
}}
""".strip()


def normalize_route_result(route_result, user_input: str, source: str):
    if not isinstance(route_result, dict):
        return {
            "mode": "chat",
            "skill": "none",
            "reason": f"{source}_invalid",
            "rewritten_input": user_input,
            "source": source,
        }

    normalized = dict(route_result)
    normalized["mode"] = normalized.get("mode", "chat") or "chat"
    normalized["skill"] = normalized.get("skill") or "none"
    normalized["reason"] = normalized.get("reason", "") or ""
    normalized["rewritten_input"] = normalized.get("rewritten_input") or user_input
    normalized["source"] = source
    skill_name = str(normalized.get("skill") or "").strip()
    if normalized["mode"] in ("skill", "hybrid") and skill_name not in ("", "none") and not is_registered_skill_name(skill_name):
        normalized["mode"] = "chat"
        normalized["intent"] = normalized.get("intent") or "missing_skill"
        normalized["missing_skill"] = skill_name
    return normalized


def has_skill_target(route_result: dict) -> bool:
    return route_result.get("skill") not in ("none", "", None)


def is_registered_skill_name(skill_name: str) -> bool:
    name = str(skill_name or "").strip()
    if not name or name == "none" or not _nova_core_ready:
        return False
    try:
        return name in _get_all_skills()
    except Exception:
        return False


def looks_like_news_request(user_input: str) -> bool:
    text = str(user_input or "").strip()
    if not text:
        return False
    if any(word in text for word in ("新闻", "头条", "热点")):
        return True
    if "发生了什么" in text and any(word in text for word in ("今天", "最近", "最新")):
        return True
    return False


def detect_missing_capability_route(bundle: dict) -> dict | None:
    user_input = str((bundle or {}).get("user_input") or "").strip()
    if not user_input:
        return None

    if looks_like_news_request(user_input) and not is_registered_skill_name("news"):
        return normalize_route_result(
            {
                "mode": "skill",
                "skill": "news",
                "reason": "news_capability_missing",
                "intent": "missing_skill",
                "missing_skill": "news",
                "rewritten_input": user_input,
            },
            user_input,
            "heuristic",
        )

    return None


def detect_story_follow_up_route(bundle: dict) -> dict | None:
    user_input = str((bundle or {}).get("user_input") or "").strip()
    if not user_input:
        return None

    story_follow_up_words = ("继续讲", "接着讲", "然后呢", "后来呢", "接着呢", "讲长一点", "有点短", "太短")
    if not any(word in user_input for word in story_follow_up_words):
        return None

    recent = list((bundle or {}).get("l2") or [])
    last_assistant = ""
    for item in reversed(recent):
        if item.get("role") in ("nova", "assistant"):
            last_assistant = str(item.get("content") or "").strip()
            if last_assistant:
                break

    if "《" in last_assistant and "》" in last_assistant:
        return normalize_route_result(
            {
                "mode": "skill",
                "skill": "story",
                "reason": "story_follow_up_from_history",
                "rewritten_input": user_input,
            },
            user_input,
            "context",
        )
    return None


def llm_route(bundle: dict) -> dict:
    prompt = build_router_prompt(bundle)
    result = _think(prompt, "")
    text = result.get("reply", "") if isinstance(result, dict) else str(result)
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return normalize_route_result(parsed, bundle["user_input"], "llm")
    except Exception:
        pass
    return normalize_route_result({"mode": "chat", "skill": "none", "reason": "llm_route_fallback"}, bundle["user_input"], "llm")


def resolve_route(bundle: dict) -> dict:
    user_input = bundle["user_input"]
    contextual_story_route = detect_story_follow_up_route(bundle)
    if contextual_story_route is not None:
        _debug_write("context_story_route", contextual_story_route)
        return contextual_story_route

    missing_capability_route = detect_missing_capability_route(bundle)
    if missing_capability_route is not None:
        _debug_write("missing_capability_route", missing_capability_route)
        return missing_capability_route

    core_route = None

    if _nova_core_ready:
        try:
            core_route = normalize_route_result(_nova_route(user_input), user_input, "core")
            _debug_write("core_route", core_route)
            if has_skill_target(core_route):
                return core_route
            if core_route.get("mode") == "chat" and float(core_route.get("confidence", 0) or 0) >= 0.9:
                return core_route
        except Exception as exc:
            _debug_write("core_route_error", {"error": str(exc)})

    llm_candidate = llm_route(bundle)
    _debug_write("llm_route", llm_candidate)
    if has_skill_target(llm_candidate):
        return llm_candidate
    if core_route is not None:
        return core_route
    return llm_candidate
