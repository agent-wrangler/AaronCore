# route_resolver - 多阶段路由决策
# 从 agent_final.py 提取

import json

# ── 注入依赖 ──────────────────────────────────────────────
_nova_route = None
_debug_write = lambda stage, data: None
_think = None
_get_all_skills = lambda: {}
_nova_core_ready = False
_search_l2 = None  # L2 持久记忆检索
_llm_call = None   # 裸 LLM 调用（不带人格，用于意图分类）


def init(*, nova_route=None, debug_write=None, think=None,
         get_all_skills=None, nova_core_ready=False, search_l2=None,
         llm_call=None):
    global _nova_route, _debug_write, _think, _get_all_skills, _nova_core_ready, _search_l2, _llm_call
    if nova_route:
        _nova_route = nova_route
    if debug_write:
        _debug_write = debug_write
    if think:
        _think = think
    if get_all_skills:
        _get_all_skills = get_all_skills
    _nova_core_ready = nova_core_ready
    if search_l2:
        _search_l2 = search_l2
    if llm_call:
        _llm_call = llm_call


# ── 路由 prompt ───────────────────────────────────────────

def _fmt_l2_for_router(l2_memories):
    if not l2_memories:
        return "暂无"
    items = [m.get("user_text", "")[:50] for m in (l2_memories or [])[:3]]
    return json.dumps(items, ensure_ascii=False)


def build_router_prompt(bundle: dict) -> str:
    l1 = bundle["l1"]
    l2 = bundle["l2"]
    l3 = bundle["l3"]
    l4 = bundle["l4"]
    l5 = bundle["l5"]
    l8 = bundle.get("l8", [])
    msg = bundle["user_input"]
    l2_memories = bundle.get("l2_memories", [])

    # L2 提炼摘要
    l2_summary = ""
    if isinstance(l2, dict):
        parts = []
        topics = l2.get("topics") or []
        if topics and topics != ["闲聊"]:
            parts.append(f"当前话题：{'、'.join(topics)}")
        mood = l2.get("mood") or ""
        if mood and mood != "平稳":
            parts.append(f"用户情绪：{mood}")
        intents = l2.get("intents") or []
        if intents and intents != ["自由对话"]:
            parts.append(f"意图模式：{'→'.join(intents)}")
        follow_up = l2.get("follow_up") or {}
        if follow_up.get("is_correction"):
            parts.append("用户正在纠正上一轮回复")
        if follow_up.get("is_follow_up"):
            parts.append("用户在追问上文")
        if follow_up.get("story_title"):
            parts.append(f"上文在讲故事《{follow_up['story_title']}》")
        l2_summary = "；".join(parts) if parts else "普通闲聊"
    else:
        l2_summary = json.dumps(l2, ensure_ascii=False)

    return f"""
你是 NovaCore 的路由判断器。你要先判断这句话是普通聊天，还是需要技能执行。

用户输入：{msg}

L1最近对话：
{json.dumps(l1, ensure_ascii=False)}

L2会话理解：
{l2_summary}

L2持久记忆：
{_fmt_l2_for_router(l2_memories)}

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
    # 透传 v2 新字段（交互阶段 + 语气）
    for field in ("stage", "tone"):
        if field in route_result:
            normalized[field] = route_result[field]
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

    # L2 提炼结果里有 story_title 说明上文在讲故事
    l2 = (bundle or {}).get("l2") or {}
    follow_up = l2.get("follow_up") or {} if isinstance(l2, dict) else {}
    if follow_up.get("story_title"):
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

    # 兼容：如果 l2 还是原始消息列表，走旧逻辑
    if isinstance(l2, list):
        last_assistant = ""
        for item in reversed(l2):
            if isinstance(item, dict) and item.get("role") in ("nova", "assistant"):
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


def llm_route_lite(bundle: dict, core_route: dict = None) -> dict:
    """轻量 LLM 意图分类 — ~200 token prompt，L2 压缩上下文"""
    msg = bundle["user_input"]

    # L2 场景摘要（已压缩）
    l2 = bundle.get("l2") or {}
    l2_brief = ""
    if isinstance(l2, dict):
        parts = []
        topics = l2.get("topics") or []
        if topics and topics != ["\u95f2\u804a"]:
            parts.append("\u8bdd\u9898\uff1a" + "\u3001".join(topics))
        mood = l2.get("mood") or ""
        if mood and mood != "\u5e73\u7a33":
            parts.append("\u60c5\u7eea\uff1a" + mood)
        fu = l2.get("follow_up") or {}
        if fu.get("is_follow_up"):
            parts.append("\u7528\u6237\u5728\u8ffd\u95ee\u4e0a\u6587")
        l2_brief = "\uff1b".join(parts) if parts else "\u666e\u901a\u95f2\u804a"

    # L2 持久记忆检索（按关键词捞相关条目，已压缩）
    l2_mem = ""
    if _search_l2:
        try:
            hits = _search_l2(msg, limit=3)
            if hits:
                l2_mem = "\uff1b".join(
                    str(h.get("user_text", ""))[:40] for h in hits if h.get("user_text")
                )
        except Exception:
            pass

    # 最近 2 轮对话（从 L1 取）
    l1 = bundle.get("l1") or []
    recent = ""
    if l1:
        last_items = l1[-4:] if len(l1) >= 4 else l1
        recent = " / ".join(
            f"{item.get('role','')}:{str(item.get('content',''))[:30]}"
            for item in last_items if isinstance(item, dict)
        )

    # 可用技能列表（含简要描述，帮 LLM 判断）
    skill_names = []
    try:
        for name, info in _get_all_skills().items():
            label = info.get("name", name)
            desc = info.get("description", "")
            if desc:
                skill_names.append(f"{name}({label}: {desc[:30]})")
            else:
                skill_names.append(f"{name}({label})")
    except Exception:
        pass
    skills_str = "\u3001".join(skill_names) if skill_names else "weather,story,news,article"

    # 关键词路由的候选（只传中高置信度的，低置信度的别带偏 LLM）
    hint = ""
    core_conf = float((core_route or {}).get("confidence", 0) or 0) if core_route else 0
    if core_route and core_route.get("skill") not in ("none", "", None) and core_conf >= 0.7:
        hint = (
            "\n\u5173\u952e\u8bcd\u8def\u7531\u5019\u9009\uff1a"
            + str(core_route.get("skill", ""))
            + "\uff08\u547d\u4e2d\u5173\u952e\u8bcd\uff1a" + str(core_route.get("reason", "")) + "\uff09"
            + "\n\u4f46\u4e0d\u786e\u5b9a\u662f\u5426\u6b63\u786e\uff0c\u8bf7\u4f60\u5224\u65ad\u3002"
        )

    prompt = (
        "\u4f60\u662f\u610f\u56fe\u5206\u7c7b\u5668\u3002\u5224\u65ad\u7528\u6237\u8fd9\u53e5\u8bdd\u7684\u610f\u56fe\u3002\n\n"
        "\u7528\u6237\u8bf4\uff1a" + msg + "\n"
        "\u6700\u8fd1\u5bf9\u8bdd\uff1a" + (recent or "\u65e0") + "\n"
        "\u573a\u666f\uff1a" + l2_brief + "\n"
        + ("\u76f8\u5173\u8bb0\u5fc6\uff1a" + l2_mem + "\n" if l2_mem else "")
        + "\u53ef\u7528\u6280\u80fd\uff1a" + skills_str + "\n"
        + hint + "\n\n"
        "\u8fd4\u56deJSON\uff1a{\"intent\":\"chat\u6216\u6280\u80fd\u540d\",\"reason\":\"\u4e00\u53e5\u8bdd\"}\n"
        "\u53ea\u8fd4\u56deJSON\u3002"
    )

    _debug_write("llm_route_lite_prompt", {"prompt": prompt, "tokens_est": len(prompt)})

    # 用裸 LLM 调用（不走 think 的人格层），fallback 到 think
    text = ""
    if _llm_call:
        try:
            text = _llm_call(prompt) or ""
        except Exception:
            pass
    if not text and _think:
        result = _think(prompt, "")
        text = result.get("reply", "") if isinstance(result, dict) else str(result)
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(text[start:end + 1])
            intent = str(parsed.get("intent", "chat")).strip().lower()
            reason = str(parsed.get("reason", "")).strip()
            if intent == "chat" or intent not in [s for s in (_get_all_skills() or {})]:
                return normalize_route_result(
                    {"mode": "chat", "skill": "none", "reason": f"llm_lite: {reason}"},
                    msg, "llm_lite"
                )
            return normalize_route_result(
                {"mode": "skill", "skill": intent, "reason": f"llm_lite: {reason}",
                 "rewritten_input": parsed.get("rewritten_input", msg)},
                msg, "llm_lite"
            )
    except Exception:
        pass
    return normalize_route_result(
        {"mode": "chat", "skill": "none", "reason": "llm_lite_fallback"},
        msg, "llm_lite"
    )


def llm_route(bundle: dict) -> dict:
    prompt = build_router_prompt(bundle)
    text = ""
    if _llm_call:
        try:
            text = _llm_call(prompt) or ""
        except Exception:
            pass
    if not text and _think:
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

    # ── 阶段 0：硬编码上下文规则（不走 LLM）──
    contextual_story_route = detect_story_follow_up_route(bundle)
    if contextual_story_route is not None:
        _debug_write("context_story_route", contextual_story_route)
        return contextual_story_route

    missing_capability_route = detect_missing_capability_route(bundle)
    if missing_capability_route is not None:
        _debug_write("missing_capability_route", missing_capability_route)
        return missing_capability_route

    # ── 阶段 1：关键词路由（router.py）──
    core_route = None
    if _nova_core_ready:
        try:
            core_route = normalize_route_result(_nova_route(user_input), user_input, "core")
            _debug_write("core_route", core_route)
            confidence = float(core_route.get("confidence", 0) or 0)

            # 纠偏优先短路：correct 阶段直接返回，不让 LLM 翻盘
            if core_route.get("stage") == "correct":
                _debug_write("route_decision", {"action": "correct_priority", "stage": "correct"})
                return core_route

            # 高置信度（>= 0.9）：直接走，不需要 LLM 确认
            if confidence >= 0.9:
                _debug_write("route_decision", {"action": "core_high_conf", "confidence": confidence})
                return core_route

            # 意图分类明确为非任务（discuss/inform）→ 直接走 chat，不让 LLM 翻盘
            core_intent = core_route.get("intent", "")
            if core_intent in ("discuss", "inform") and confidence >= 0.75:
                _debug_write("route_decision", {"action": "intent_gate_chat", "intent": core_intent, "confidence": confidence})
                return core_route

            # chat 意图 + 无技能信号 → 也不让 LLM 翻盘（防止 LLM 被历史上下文带偏）
            if core_intent == "chat" and not has_skill_target(core_route):
                core_skill_score = float(core_route.get("skill_score", 0) or 0)
                if core_skill_score <= 0:
                    _debug_write("route_decision", {"action": "intent_gate_pure_chat", "confidence": confidence})
                    return core_route

        except Exception as exc:
            _debug_write("core_route_error", {"error": str(exc)})

    # ── 阶段 2：轻量 LLM 裁决（~200 token，L2 压缩上下文）──
    try:
        lite_result = llm_route_lite(bundle, core_route=core_route)
        _debug_write("llm_route_lite", lite_result)

        # LLM 明确识别出技能
        if has_skill_target(lite_result):
            _debug_write("route_decision", {"action": "lite_skill", "skill": lite_result.get("skill")})
            return lite_result

        # LLM 说是 chat，且关键词路由也没有强候选 → 直接 chat
        if core_route is None or not has_skill_target(core_route):
            _debug_write("route_decision", {"action": "lite_chat"})
            return lite_result

        # LLM 说 chat，但关键词路由有候选（中低置信度）→ 信 LLM，走 chat
        core_conf = float(core_route.get("confidence", 0) or 0)
        if core_conf < 0.7:
            _debug_write("route_decision", {"action": "lite_override_low_conf", "core_conf": core_conf})
            return lite_result

        # 关键词置信度 0.7-0.9 且 LLM 说 chat → 保守起见信 LLM
        _debug_write("route_decision", {"action": "lite_override_mid_conf", "core_conf": core_conf})
        return lite_result

    except Exception as exc:
        _debug_write("llm_route_lite_error", {"error": str(exc)})

    # ── 阶段 3：兜底（保守回退）──
    # lite 失败了，保守处理：只有高置信度关键词结果才保留，否则走 chat
    if core_route is not None:
        core_conf = float(core_route.get("confidence", 0) or 0)
        if core_conf >= 0.85:
            _debug_write("route_decision", {"action": "fallback_core_high_conf", "confidence": core_conf})
            return core_route
        # 低置信度 → 不确定时宁可不执行
        _debug_write("route_decision", {"action": "fallback_conservative_chat", "core_conf": core_conf})
        return normalize_route_result(
            {"mode": "chat", "skill": "none", "reason": "llm_failed_conservative_fallback"},
            user_input, "fallback"
        )

    # 最后兜底：重量级 LLM 路由（完整 L1-L8 上下文）
    llm_candidate = llm_route(bundle)
    _debug_write("llm_route_heavy", llm_candidate)
    return llm_candidate
