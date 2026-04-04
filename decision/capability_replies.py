"""Capability and meta-intent reply helpers."""

from __future__ import annotations

from collections.abc import Callable


_SKILL_DISPLAY_NAME_FALLBACKS = {
    "weather": "天气查询",
    "news": "新闻抓取",
    "stock": "股票查询",
    "article": "写文章",
    "story": "讲故事",
    "draw": "AI 画图",
}


def looks_like_mojibake(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    suspicious_fragments = (
        "闁",
        "韫",
        "閼",
        "闂",
        "婵",
        "锟",
        "鎴",
        "澶",
        "鐨",
    )
    return any(fragment in value for fragment in suspicious_fragments)


def list_primary_capabilities(
    *,
    nova_core_ready: bool,
    get_all_skills: Callable[[], dict],
) -> list[str]:
    if not nova_core_ready:
        return ["陪你聊天"]

    preferred = ["weather", "story", "stock", "draw", "task_plan", "run_command", "run_code"]
    skills = get_all_skills() or {}
    labels: list[str] = []
    for name in preferred:
        info = skills.get(name)
        if not info:
            continue
        label = str(info.get("name") or name).strip()
        if label and label not in labels:
            labels.append(label)
    return labels or ["陪你聊天"]


def get_skill_display_name(
    skill_name: str,
    *,
    nova_core_ready: bool,
    get_all_skills: Callable[[], dict],
) -> str:
    name = str(skill_name or "").strip()
    if not name:
        return "技能"
    fallback = _SKILL_DISPLAY_NAME_FALLBACKS.get(name)
    if nova_core_ready:
        try:
            skill_info = (get_all_skills() or {}).get(name, {})
            label = str(skill_info.get("name") or name).strip()
            if fallback and looks_like_mojibake(label):
                return fallback
            return label or fallback or name
        except Exception:
            pass
    return fallback or name


def build_capability_chat_reply(
    route: dict | None = None,
    *,
    nova_core_ready: bool,
    get_all_skills: Callable[[], dict],
    build_self_repair_status: Callable[[], dict],
) -> str:
    route = route if isinstance(route, dict) else {}
    intent = str(route.get("intent") or "").strip()
    status = build_self_repair_status()

    if intent == "self_repair_capability":
        return (
            "我现在已经接上更省心的自修正了。现在这套能走到"
            "“收到负反馈 -> 生成修正提案 -> 列候选文件 -> 跑最小验证”这一步。\n\n"
            "如果只是低风险的小修小补，我会在后台直接尝试落补丁；"
            "只要改动碰到更核心的链路，我就先问你一次。"
            "如果补丁后的最小验证没过，我会自动回滚，不把坏改动留在源码里。"
        )

    if intent == "missing_skill":
        missing_skill = str(route.get("missing_skill") or route.get("skill") or "技能").strip() or "技能"
        label = get_skill_display_name(
            missing_skill,
            nova_core_ready=nova_core_ready,
            get_all_skills=get_all_skills,
        )
        if missing_skill == "news":
            return (
                f"我本来想按“{label}”这条路接住你这句，"
                "但这项能力现在没接上，所以我先不乱报“今天”的新闻，"
                "免得把旧信息当成现在。"
            )
        return f"我本来想按“{label}”这项能力接住你这句，不过它现在没接上，所以先不给你一条失效结果。"

    skills = "、".join(
        list_primary_capabilities(
            nova_core_ready=nova_core_ready,
            get_all_skills=get_all_skills,
        )
    )
    tail = "源码自修这边现在是：低风险小改动会先自己修，碰到更核心的链路再问你一次；如果验证不过，我会自动回滚。"
    if status.get("feedback_learning"):
        return f"我现在能陪你聊天，也能做这些：{skills}。{tail}"
    return f"我现在能陪你聊天，也能做这些：{skills}。"


def build_meta_bug_report_reply(
    route: dict | None = None,
    *,
    build_self_repair_status: Callable[[], dict],
) -> str:
    route = route if isinstance(route, dict) else {}
    status = build_self_repair_status()
    latest = str(status.get("latest_status_summary") or "").strip()

    if status.get("can_auto_apply_fixes"):
        return (
            "我会先进入排查模式，把这类话当成界面异常或路由误触发，"
            "不再直接跳去小游戏。\n\n"
            f"排查后会继续走自修复链路：生成修复提案、跑最小验证，低风险补丁会自动落地。{latest}"
        )

    return (
        "我会先进入排查模式，把这类话当成界面异常或路由误触发，"
        "不再直接跳去小游戏。\n\n"
        f"排查后会继续走修复链路：先生成修复提案和验证计划，不过不是每种情况都会自动改源码。{latest}"
    )


def build_answer_correction_reply(
    route: dict | None = None,
    *,
    build_self_repair_status: Callable[[], dict],
) -> str:
    route = route if isinstance(route, dict) else {}
    status = build_self_repair_status()
    latest = str(status.get("latest_status_summary") or "").strip()
    latest_tail = f" {latest}" if latest else ""
    return (
        "这句我会直接当成你在纠正我上一轮答偏了，"
        "不再往天气之类的技能上联想。\n\n"
        f"我先停掉错误路由，回到你刚才真正指出的那件事继续排查；这次纠偏也会记进修复链路里。{latest_tail}"
    )


def format_skill_error_reply(
    skill_name: str,
    error_text: str,
    user_input: str = "",
    *,
    get_skill_display_name: Callable[[str], str],
) -> str:
    del user_input
    label = get_skill_display_name(skill_name)
    error = str(error_text or "").strip()
    looks_like_news = skill_name == "news"

    if "未找到" in error or "没有可执行函数" in error:
        if looks_like_news:
            return f"我本来想按“{label}”这条路接住你这句，但这项能力现在没接上，所以我先不乱报今天的新闻，免得把旧信息当成现在。"
        return f"我本来想走“{label}”这项能力，不过它现在没接上，所以先不给你一条失效结果。"

    if "执行失败" in error:
        return f"我本来想走“{label}”这项能力，不过这次执行没跑通，所以先不把半截结果塞给你。"

    return f"我本来想走“{label}”这项能力，不过这次没接稳，所以先不给你一个不靠谱的结果。"


def format_story_reply(user_input: str, story_text: str) -> str:
    del user_input
    text = str(story_text or "").strip()
    if not text:
        return "我这次故事没接稳，你再戳我一下，我给你重新讲一个完整点的。"

    intro = "好呀，给你讲一个。"
    return f"{intro}\n\n{text}"


def prettify_trace_reason(route: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    reason = str(route.get("reason") or "").strip()
    source = str(route.get("source") or "").strip()
    skill = str(route.get("skill") or "").strip()

    if source == "context" and skill == "story":
        return "上一轮刚在讲故事，这句按续写处理。"

    mapping = {
        "命中故事追问延续语境": "识别到你是在接着上一段故事往下问。",
        "命中股票/指数查询意图": "识别到这是一个明确的行情查询请求。",
        "命中普通聊天语句": "这句更像普通聊天，没有必要调用技能。",
        "存在任务意图，进入技能候选混合路由": "这句带着明确任务意图，所以先按能力请求来处理。",
        "命中内容任务后画操作（继续/换题/推进阶段）": "识别到你是在继续推进之前那轮内容任务。",
        "鍛戒腑鏁呬簨杩介棶寤剁画璇": "识别到你是在接着上一段故事往下问。",
        "鍛戒腑鑲＄エ/鎸囨暟鏌ヨ鎰忓浘": "识别到这是一个明确的行情查询请求。",
        "鍛戒腑鏅€氳亰澶╄鍙?": "这句更像普通聊天，没有必要调用技能。",
        "瀛樺湪浠诲姟鎰忓浘锛岃繘鍏ユ妧鑳藉€欓€夋贩鍚堣矾鐢?": "这句带着明确任务意图，所以先按能力请求来处理。",
        "鍛戒腑鍐呭浠诲姟鍚庣画鎿嶄綔锛堢户缁?鎹㈤/鎺ㄨ繘闃舵锛?": "识别到你是在继续推进之前那轮内容任务。",
    }
    if reason in mapping:
        return mapping[reason]
    if reason.startswith("命中技能候选") or reason.startswith("鍛戒腑鎶€鑳藉€欓€"):
        return "命中了明确的技能候选，所以没有按闲聊处理。"
    mode = str(route.get("mode") or "").strip()
    if not reason and mode == "chat":
        return "这句更像普通聊天，没有必要调用技能。"
    return reason or "这句更像普通聊天，没有必要调用技能。"
