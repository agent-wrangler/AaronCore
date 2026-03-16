# reply_formatter - 回复格式化、trace 构建、统一回复生成
# 从 agent_final.py 提取

import json

from core.context_builder import format_l8_context, summarize_event_value
from core.feedback_classifier import format_l7_context
from core.route_resolver import looks_like_news_request

# ── 注入依赖 ──────────────────────────────────────────────
_think = None


def _build_style_hints_from_l4(l4: dict, *, is_skill: bool = False) -> str:
    """从 L4 人格数据动态生成风格提示文本，不再硬编码任何具体风格"""
    modes = l4.get("persona_modes") or {}
    active = str(l4.get("active_mode") or "").strip()
    mode_data = modes.get(active) or {}

    style = str(mode_data.get("style_prompt") or l4.get("style_prompt") or "").strip()
    tone = mode_data.get("tone") or (l4.get("speech_style") or {}).get("tone") or []
    particles = mode_data.get("particles") or (l4.get("speech_style") or {}).get("particles") or []
    avoid = mode_data.get("avoid") or (l4.get("speech_style") or {}).get("avoid") or []
    expression = str(mode_data.get("expression") or "").strip()
    interaction = str(mode_data.get("interaction_style") or "").strip()

    lines = []
    if style:
        lines.append(style)
    if expression:
        lines.append(expression)
    if interaction:
        lines.append(interaction)
    if tone:
        lines.append("\u8bed\u6c14\u5173\u952e\u8bcd\uff1a" + "\u3001".join(tone))
    if particles:
        lines.append("\u5e38\u7528\u8bed\u6c14\u8bcd\uff1a" + "\u3001".join(particles))
    if is_skill:
        lines.append("\u628a\u6280\u80fd\u7ed3\u679c\u81ea\u7136\u878d\u8fdb\u804a\u5929\u8bed\u6c14\u91cc\uff0c\u4e0d\u8981\u50cf\u7cfb\u7edf\u64ad\u62a5\u3002")

    avoid_block = ""
    if avoid:
        avoid_lines = "\n".join("- " + a for a in avoid)
        avoid_block = "\n\n\u7981\u6b62\uff1a\n" + avoid_lines

    return "\n".join(lines) + avoid_block
_debug_write = lambda stage, data: None
_nova_core_ready = False
_get_all_skills = lambda: {}
_nova_execute = lambda route_result, skill_input: {"success": False}
_evolve = lambda user_input, skill_name: None
_load_autolearn_config = lambda: {}
_load_self_repair_reports = lambda: []
_find_feedback_rule = lambda msg, history: None


def init(*, think=None, debug_write=None, nova_core_ready=False,
         get_all_skills=None, nova_execute=None, evolve=None,
         load_autolearn_config=None, load_self_repair_reports=None,
         find_feedback_rule=None):
    global _think, _debug_write, _nova_core_ready, _get_all_skills
    global _nova_execute, _evolve, _load_autolearn_config
    global _load_self_repair_reports, _find_feedback_rule
    if think:
        _think = think
    if debug_write:
        _debug_write = debug_write
    _nova_core_ready = nova_core_ready
    if get_all_skills:
        _get_all_skills = get_all_skills
    if nova_execute:
        _nova_execute = nova_execute
    if evolve:
        _evolve = evolve
    if load_autolearn_config:
        _load_autolearn_config = load_autolearn_config
    if load_self_repair_reports:
        _load_self_repair_reports = load_self_repair_reports
    if find_feedback_rule:
        _find_feedback_rule = find_feedback_rule


# ── 学习/修复状态摘要 ────────────────────────────────────

def _build_learning_summary(config: dict) -> str:
    if not bool(config.get("enabled", True)):
        return "自动学习已关闭，反馈只会停留在当前会话里。"
    if bool(config.get("allow_feedback_relearn", True)):
        if bool(config.get("allow_web_search", True)) and bool(config.get("allow_knowledge_write", True)):
            return "会先记住负反馈，必要时补学并写回知识库。"
        if bool(config.get("allow_knowledge_write", True)):
            return "会先记住负反馈，并把纠偏结论沉淀到知识库。"
        return "会先记住负反馈，但暂时不会长期沉淀到知识库。"
    return "现在不会把负反馈沉淀成纠偏记录。"


def _build_repair_summary(config: dict) -> str:
    planning_enabled = bool(config.get("allow_self_repair_planning", True))
    test_run_enabled = bool(config.get("allow_self_repair_test_run", True))
    auto_apply_enabled = bool(config.get("allow_self_repair_auto_apply", True))
    apply_mode = str(config.get("self_repair_apply_mode") or "confirm").strip() or "confirm"

    if not planning_enabled:
        return "目前只做学习纠偏，不会主动整理修复方案。"
    if not test_run_enabled:
        return "会先整理修法，但动手前还不会自动自查。"
    if not auto_apply_enabled:
        return "会先整理修法并自己检查，真正动手前先停下来给你看。"
    if apply_mode == "suggest":
        return "低风险会自己继续，中高风险先给你看方案。"
    return "低风险会自己继续，中高风险只确认一次。"


def _build_latest_status_summary(latest: dict, latest_preview: dict, latest_apply: dict) -> str:
    apply_status = str((latest_apply or {}).get("status") or "").strip()
    if apply_status:
        if apply_status in {"applied", "applied_without_validation"} and bool(latest_apply.get("auto_applied")):
            return "最近一次反馈已经在后台自动落成修改。"
        if apply_status == "applied":
            return "最近一次反馈已经真正动手修改并通过了自查。"
        if apply_status == "applied_without_validation":
            return "最近一次反馈已经动手修改，但还没有跑自查。"
        if apply_status.startswith("rolled_back"):
            return "最近一次尝试已经自动回滚，没有把坏补丁留在源码里。"
        return "最近一次反馈已经走到动手阶段，但结果还需要进一步确认。"

    preview_status = str((latest_preview or {}).get("status") or "").strip()
    if preview_status == "preview_ready":
        if bool(latest_preview.get("auto_apply_ready")):
            return "最近一次反馈已经整理成低风险补丁，会继续在后台往下处理。"
        if bool(latest_preview.get("confirmation_required", True)):
            return "最近一次反馈已经整理出改法，只等一次确认。"
        return "最近一次反馈已经整理出改法，这次不用额外确认。"

    latest_status = str((latest or {}).get("status") or "").strip()
    if latest_status:
        return "最近一次反馈已经被记进纠偏链路，后面会沿着这条线继续学习或修正。"
    return "最近还没有新的纠偏记录。"


def build_self_repair_status() -> dict:
    l8_config = _load_autolearn_config()
    all_reports = _load_self_repair_reports()
    latest = all_reports[0] if all_reports else {}
    latest_preview = latest.get("patch_preview") or {}
    latest_apply = latest.get("apply_result") or {}
    planning_enabled = bool(l8_config.get("allow_self_repair_planning", True))
    test_run_enabled = bool(l8_config.get("allow_self_repair_test_run", True))
    auto_apply_enabled = bool(l8_config.get("allow_self_repair_auto_apply", True))
    apply_mode = str(l8_config.get("self_repair_apply_mode") or "confirm").strip() or "confirm"
    learning_summary = _build_learning_summary(l8_config)
    repair_summary = _build_repair_summary(l8_config)

    return {
        "stage": "controlled_patch_loop" if planning_enabled else "feedback_learning_only",
        "feedback_learning": bool(l8_config.get("allow_feedback_relearn", True)),
        "web_learning": bool(l8_config.get("allow_web_search", True)),
        "knowledge_write": bool(l8_config.get("allow_knowledge_write", True)),
        "planning_enabled": planning_enabled,
        "test_run_enabled": test_run_enabled,
        "auto_apply_enabled": auto_apply_enabled,
        "skill_generation": bool(l8_config.get("allow_skill_generation", False)),
        "apply_mode": apply_mode,
        "report_count": len(all_reports),
        "latest_report_id": str(latest.get("id") or ""),
        "latest_report_status": str(latest.get("status") or ""),
        "latest_summary": str(latest.get("summary") or ""),
        "latest_apply_status": str(latest_apply.get("status") or ""),
        "latest_risk_level": str(latest_preview.get("risk_level") or latest.get("risk_level") or ""),
        "latest_auto_apply_ready": bool(latest_preview.get("auto_apply_ready")),
        "latest_confirmation_required": bool(latest_preview.get("confirmation_required", True)),
        "learning_summary": learning_summary,
        "repair_summary": repair_summary,
        "autonomy_summary": f"{learning_summary.rstrip('。')}；{repair_summary}",
        "latest_status_summary": _build_latest_status_summary(latest, latest_preview, latest_apply),
        "can_patch_source_code": True,
        "can_plan_repairs": planning_enabled,
        "can_run_source_tests": test_run_enabled,
        "can_auto_apply_fixes": planning_enabled and test_run_enabled and auto_apply_enabled,
    }
# PLACEHOLDER_CAPABILITIES

def list_primary_capabilities() -> list[str]:
    if not _nova_core_ready:
        return ["陪你聊天"]

    preferred = ["weather", "story", "stock", "draw", "run_code"]
    skills = _get_all_skills()
    labels = []
    for name in preferred:
        info = skills.get(name)
        if not info:
            continue
        label = str(info.get("name") or name).strip()
        if label and label not in labels:
            labels.append(label)
    return labels or ["陪你聊天"]


def get_skill_display_name(skill_name: str) -> str:
    name = str(skill_name or "").strip()
    if not name:
        return "技能"
    if _nova_core_ready:
        try:
            skill_info = _get_all_skills().get(name, {})
            return str(skill_info.get("name") or name)
        except Exception:
            pass
    return name


# ── 特殊意图回复 ──────────────────────────────────────────

def build_capability_chat_reply(route: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    intent = str(route.get("intent") or "").strip()
    status = build_self_repair_status()

    if intent == "self_repair_capability":
        return (
            "我现在已经接上更省心的自修正啦。现在这套能走到“收到负反馈 -> 生成修正提案 -> 列候选文件 -> 跑最小测试”这一步。\n\n"
            "如果只是低风险的小修小补，我会在后台直接尝试落补丁；只要改动碰到更核心的链路，我就先问你一次。"
            "如果补丁后的最小验证没过，我会自动回滚，不把坏改动留在源码里。"
        )

    if intent == "missing_skill":
        missing_skill = str(route.get("missing_skill") or route.get("skill") or "技能").strip() or "技能"
        label = get_skill_display_name(missing_skill)
        prompt = str(route.get("rewritten_input") or "").strip()
        if missing_skill == "news" or looks_like_news_request(prompt):
            return f"我本来想按「{label}」这条路接住你这句，但这项能力现在没接上，所以我先不乱报“今天”的新闻，免得把旧信息当成现在。"
        return f"我本来想按「{label}」这条能力接住你这句，不过它现在没接上，所以先不拿一条失效结果糊弄你。"

    skills = "、".join(list_primary_capabilities())
    tail = "源码自修这边现在是：低风险小改动会先自己修，碰到更核心的链路再问你一次；如果验证不过，我会自动回滚。"
    if status["feedback_learning"]:
        return f"我现在能陪你聊天，也能做这些：{skills}。{tail}"
    return f"我现在能陪你聊天，也能做这些：{skills}。"
# PLACEHOLDER_META_REPLIES

def build_meta_bug_report_reply(route: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    status = build_self_repair_status()
    latest = str(status.get("latest_status_summary") or "").strip()

    if status.get("can_auto_apply_fixes"):
        return (
            "我会先进入排查模式，把这类话当成界面异常或路由误触发，不再直接跳去小游戏。\n\n"
            f"排查后会继续走自修复链路：生成修复提案、跑最小验证，低风险补丁会自动落地。{latest}"
        )

    return (
        "我会先进入排查模式，把这类话当成界面异常或路由误触发，不再直接跳去小游戏。\n\n"
        f"排查后会继续走修复链路：先生成修复提案和验证计划，不过不是每种情况都会自动改源码。{latest}"
    )


def build_answer_correction_reply(route: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    status = build_self_repair_status()
    latest = str(status.get("latest_status_summary") or "").strip()
    latest_tail = f" {latest}" if latest else ""
    return (
        "这句我会直接当成你在纠正我上一轮答偏了，不再往天气之类的技能上联想。\n\n"
        f"我先停掉错误路由，回到你刚才真正指出的那件事继续排查；这次纠偏也会记进修复链路里。{latest_tail}"
    )


# ── 统一聊天回复 ──────────────────────────────────────────

def unified_chat_reply(bundle: dict, route: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    intent = str(route.get("intent") or "").strip()
    if intent in {"self_repair_capability", "ability_capability", "missing_skill"}:
        return build_capability_chat_reply(route)
    if intent == "meta_bug_report":
        return build_meta_bug_report_reply(route)
    if intent == "answer_correction":
        return build_answer_correction_reply(route)

    l3 = bundle["l3"]
    l4 = bundle["l4"]
    l5 = bundle["l5"]
    l7 = bundle.get("l7", [])
    l7_context = format_l7_context(l7)
    l8 = bundle.get("l8", [])
    l8_context = format_l8_context(l8)
    l2_memories = bundle.get("l2_memories", [])
    l2_context = ""
    if l2_memories:
        lines = []
        for mem in l2_memories:
            user_text = str(mem.get("user_text", ""))[:80]
            importance = mem.get("importance", 0)
            marker = "\u2605" if importance >= 0.7 else "\u00b7"
            lines.append(f"{marker} {user_text}")
        l2_context = "\n".join(lines)
    dialogue_context = bundle.get("dialogue_context", "")
    msg = bundle["user_input"]
    search_context = bundle.get("search_context", "")
    search_summary = bundle.get("search_summary", "")

    # 如果有实时搜索结果，构建增强 prompt
    search_block = ""
    if search_context:
        search_block = f"""
实时联网搜索结果（刚刚搜到的，必须基于这些真实内容回复，不要编造）：
{search_context}
搜索摘要：{search_summary}

重要：你刚刚真的去联网搜索了，请基于上面的搜索结果整理回复。不要说"我去查一下"之类的话，你已经查完了，直接告诉用户你学到了什么。
"""

    style_hints = _build_style_hints_from_l4(l4)

    prompt = f"""
用户输入：{msg}
{search_block}

L3长期记忆：
{json.dumps(l3, ensure_ascii=False)}

L2持久记忆（之前对话中的重要片段）：
{l2_context or "暂无"}

L4人格信息：
{json.dumps(l4, ensure_ascii=False)}

你必须严格按照 L4 人格信息中的风格规则来回复！

{style_hints}

L5知识：
{json.dumps(l5, ensure_ascii=False)}

L7经验教训（之前犯过的错，务必避免重犯）：
{l7_context or "暂无"}

L8已学知识：
{l8_context or "暂无命中的已学知识"}

要求：
1. 这是普通聊天，直接自然回复。
2. 根据 L4 里的风格规则来确定语气。
3. 如果 L8 已经学过和当前问题有关的知识，优先吸收后再回答，不要像第一次见到这个问题。
4. 如果 L2 持久记忆中有和当前话题相关的内容，自然地接上，体现你记得之前聊过的事。
5. 如果用户这句话是承接上一轮的追问（例如"那什么时候有啊""然后呢""为什么""这个呢"），默认沿着最近对话的话题直接接上，不要反问"你指什么"。
6. 不要死板，不要空模板。
7. 不要输出思考过程。
8. 只输出最终回复。
""".strip()
    result = _think(prompt, dialogue_context)
    reply = result.get("reply", "") if isinstance(result, dict) else str(result)
    if (not reply) or ("��" in str(reply)) or len(str(reply).strip()) < 2:
        return "我在呢，你直接说，我会认真接着你的话聊。"
    return str(reply).strip()


# ── 技能回复格式化 ────────────────────────────────────────

def format_skill_fallback(skill_response: str) -> str:
    text = str(skill_response or "").strip()
    if not text:
        return "我先帮你接住啦，不过这次结果有点没贴稳，你再戳我一下嘛。"
    return f"我先帮你整理好啦：\n\n{text}"


def format_skill_error_reply(skill_name: str, error_text: str, user_input: str = "") -> str:
    label = get_skill_display_name(skill_name)
    error = str(error_text or "").strip()
    prompt = str(user_input or "").strip()
    looks_like_news = skill_name == "news" or looks_like_news_request(prompt)

    if "未找到" in error or "没有可执行函数" in error:
        if looks_like_news:
            return f"我本来把这句看成了「{label}」这类请求，但这项能力现在没接上，所以我先不乱报今天的新闻，免得把旧信息当成现在。"
        return f"我本来想走「{label}」这条能力，不过它这会儿没接上，所以先不拿一条失效结果糊弄你。"

    if "执行失败" in error:
        return f"我本来想走「{label}」这条能力，不过这次执行没跑稳，所以先不把半截结果塞给你。"

    return f"我本来想走「{label}」这条能力，不过这次没接稳，所以先不乱给你一个不靠谱的结果。"


def format_story_reply(user_input: str, story_text: str) -> str:
    text = str(story_text or "").strip()
    if not text:
        return "我这次故事没接稳，你再戳我一下，我给你重新讲一个完整点的。"

    prompt = str(user_input or "").strip()
    if any(word in prompt for word in ("继续讲", "然后呢", "后来呢", "接着讲")):
        intro = "来，我接着往下讲。"
    elif any(word in prompt for word in ("有点短", "太短", "讲长一点", "完整一点", "详细一点")):
        intro = "这次我给你讲完整一点，你慢慢看。"
    elif any(word in prompt for word in ("再讲一个", "换一个故事", "换个故事")):
        intro = "那我换一个味道，重新给你讲一个。"
    else:
        intro = "好呀，给你讲一个。"
    return f"{intro}\n\n{text}"


# ── Trace 构建 ────────────────────────────────────────────

def prettify_trace_reason(route: dict) -> str:
    route = route if isinstance(route, dict) else {}
    reason = str(route.get("reason") or "").strip()
    source = str(route.get("source") or "").strip()
    skill = str(route.get("skill") or "").strip()

    if source == "context" and skill == "story":
        return "上一轮刚在讲故事，这句按续写处理。"

    mapping = {
        "命中故事追问延续语境": "识别到你是在接着上一段故事往下问。",
        "命中股票/指数查询意图": "识别到这是一条明确的行情查询请求。",
        "命中普通聊天语句": "这句更像普通聊天，没有必要调用技能。",
        "存在任务意图，进入技能候选/混合路由": "这句带着明确任务意图，所以先按能力请求来处理。",
    }
    if reason in mapping:
        return mapping[reason]
    if reason.startswith("命中技能候选:"):
        return "命中了明确的技能关键词，所以没有按闲聊处理。"
    if reason == "story_follow_up_from_history":
        return "上一轮刚在讲故事，这句按续写处理。"
    mode = str(route.get("mode") or "").strip()
    if not reason and mode == "chat":
        return "这句更像普通聊天，没有必要调用技能。"
    return reason or "这句更像普通聊天，没有必要调用技能。"


def build_trace_summary(route: dict, skill_trace: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    skill_trace = skill_trace if isinstance(skill_trace, dict) else {}
    mode = str(route.get("mode") or "chat").strip()
    skill_name = str(route.get("skill") or "").strip()
    skill_label = get_skill_display_name(skill_name)
    success = skill_trace.get("success")
    source = str(route.get("source") or "").strip()

    if source == "context" and skill_name == "story":
        summary = "我知道你是在接着刚才那段故事问，所以就顺着往下讲啦。"
    elif skill_name == "weather":
        summary = "这句我就没跟你绕啦，直接去看天气了。"
    elif skill_name == "stock":
        summary = "这句我先去翻了下行情，再回来跟你说。"
    elif skill_name == "story":
        summary = "我猜你现在是想听故事，所以先把故事线接住啦。"
    elif mode == "hybrid":
        summary = f"这句像是在让我帮你办点事，我就先走「{skill_label}」那条路了。"
    else:
        summary = f"我先按「{skill_label}」这条路接住你这句啦。"

    if success is False:
        if summary.endswith("。"):
            return summary[:-1] + "，不过这次没接稳。"
        return summary + "不过这次没接稳。"
    return summary



def build_repair_progress_payload(route: dict | None = None, feedback_rule: dict | None = None) -> dict:
    route = route if isinstance(route, dict) else {}
    feedback_rule = feedback_rule if isinstance(feedback_rule, dict) else {}
    intent = str(route.get("intent") or "").strip()
    feedback_type = str(feedback_rule.get("type") or "").strip()

    if not feedback_type and intent not in {"meta_bug_report", "answer_correction"}:
        return {"show": False}

    status = build_self_repair_status()
    can_plan = bool(status.get("can_plan_repairs"))
    headline = "已记录反馈"
    detail = "我先把这次反馈记下了。"
    item = "当前事项：先把这次问题记进修复链路。"
    if intent == "answer_correction":
        headline = "已收到纠偏"
        detail = "我先把这次答偏和错路由记下来了。"
        item = "当前事项：回看上一轮的答复和被误触发的技能。"
    if can_plan:
        detail += " 接下来会继续看修复提案、验证结果和是否需要回滚。"
    else:
        detail += " 现在还没打开自动修复规划，所以会先停在记录这一步。"

    return {
        "show": True,
        "watch": can_plan,
        "label": "修复进度",
        "stage": "logged",
        "headline": headline,
        "detail": detail,
        "item": item,
        "progress": 22,
        "poll_ms": 1600,
        "max_polls": 10,
    }


# ── 统一技能回复 ──────────────────────────────────────────

def unified_skill_reply(bundle: dict, skill_name: str, skill_input: str) -> dict:
    route_result = {"mode": "skill", "skill": skill_name, "params": {}, "role": "assistant"}
    # 把 L4 用户上下文传给 executor，技能可按需读取
    skill_context = {}
    l4 = bundle.get("l4") or {}
    if isinstance(l4, dict):
        up = l4.get("user_profile") or {}
        if isinstance(up, dict):
            skill_context["user_city"] = str(up.get("city") or "").strip()
            skill_context["user_identity"] = str(up.get("identity") or "").strip()
    execute_result = _nova_execute(route_result, skill_input, skill_context) if _nova_core_ready else {"success": False}
    _debug_write("execute_result", execute_result)
    if not execute_result.get("success"):
        error_text = str(execute_result.get("error", "") or "").strip()
        if "未找到" in error_text or "没有可执行函数" in error_text:
            _debug_write("skill_missing", {"skill": skill_name, "input": skill_input, "error": error_text})
        else:
            _debug_write("skill_failed", {"skill": skill_name, "input": skill_input, "error": error_text})
        return {
            "reply": format_skill_error_reply(skill_name, error_text, bundle.get("user_input", "")),
            "trace": {"skill": skill_name, "success": False, "error": error_text},
        }

    try:
        _evolve(bundle["user_input"], skill_name)
    except Exception as exc:
        _debug_write("evolve_error", {"skill": skill_name, "error": str(exc)})

    skill_response = execute_result.get("response", "")
    if skill_name == "story":
        return {
            "reply": format_story_reply(bundle["user_input"], skill_response),
            "trace": {"skill": skill_name, "success": True},
        }

    # 新闻类技能：技能已输出中文翻译+分板块的列表，直接透传
    if skill_name == "news":
        return {
            "reply": skill_response,
            "trace": {"skill": skill_name, "success": True},
        }

    dialogue_context = bundle.get("dialogue_context", "")
    skill_style_hints = _build_style_hints_from_l4(bundle.get("l4") or {}, is_skill=True)
    prompt = f"""
用户输入：{bundle['user_input']}

技能结果：
{skill_response}
{news_extra}

L4人格信息：
{json.dumps(bundle['l4'], ensure_ascii=False)}

你必须严格按照 L4 人格信息中的风格规则来回复！

{skill_style_hints}

要求：
1. 必须严格基于技能结果回答，不能改事实。
2. 根据 L4 里的风格规则来确定语气。
3. 如果用户这句话是在接上一轮继续追问，要自然接着前文说，不要像重新开了一个话题。
4. 用统一的人格口吻输出，不要像系统提示。
5. 不要输出思考过程。
6. 只输出最终回复。
""".strip()
    result = _think(prompt, dialogue_context)
    reply = result.get("reply", "") if isinstance(result, dict) else str(result)
    if (not reply) or ("��" in str(reply)) or len(str(reply).strip()) < 2:
        return {
            "reply": format_skill_fallback(skill_response),
            "trace": {"skill": skill_name, "success": True},
        }
    return {
        "reply": str(reply).strip(),
        "trace": {"skill": skill_name, "success": True},
    }
