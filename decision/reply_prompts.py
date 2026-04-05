"""Prompt builders for chat and tool-call decision flows."""

import json
from datetime import datetime as _datetime
from pathlib import Path as _Path

from context import chat_context as _chat_context
from context.builder import format_l8_context
from core.feedback_classifier import format_l7_context

_CONFIGS_DIR = _Path(__file__).resolve().parents[1] / "configs"
_prompt_error_count = 0


def _load_prompt_config() -> dict:
    global _prompt_error_count
    prompt_path = _CONFIGS_DIR / "prompts.json"
    backup_path = _CONFIGS_DIR / "prompts.json.bak"
    try:
        cfg = json.loads(prompt_path.read_text("utf-8"))
        _prompt_error_count = 0
        return cfg
    except Exception:
        _prompt_error_count += 1
        if _prompt_error_count >= 3 and backup_path.exists():
            try:
                import shutil

                shutil.copy2(backup_path, prompt_path)
                _prompt_error_count = 0
                return json.loads(prompt_path.read_text("utf-8"))
            except Exception:
                pass
        return {}


def build_current_time_context() -> str:
    now = _datetime.now()
    weekday_map = {
        0: "Monday",
        1: "Tuesday",
        2: "Wednesday",
        3: "Thursday",
        4: "Friday",
        5: "Saturday",
        6: "Sunday",
    }
    weekday = weekday_map.get(now.weekday(), "")
    return (
        f"Current local time: {now.strftime('%Y-%m-%d %H:%M')} (Asia/Shanghai, {weekday}).\n"
        f"Current year: {now.year}. Current month: {now.month}.\n"
        "When writing dates, bylines, footers, or time-sensitive summaries, use this current date unless tool results provide a more specific timestamp. "
        "Do not invent older dates."
    )


def build_style_hints_from_l4(l4: dict, *, is_skill: bool = False) -> str:
    """从 L4 人格数据动态生成风格提示文本，不再硬编码任何具体风格"""
    lp = l4.get("local_persona") or l4
    modes = lp.get("persona_modes") or {}
    active = str(lp.get("active_mode") or "").strip()
    mode_data = modes.get(active) or {}

    style = str(mode_data.get("style_prompt") or lp.get("style_prompt") or "").strip()
    tone = mode_data.get("tone") or (lp.get("speech_style") or {}).get("tone") or []
    particles = mode_data.get("particles") or (lp.get("speech_style") or {}).get("particles") or []
    avoid = mode_data.get("avoid") or (lp.get("speech_style") or {}).get("avoid") or []
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
        lines.append("\u5de5\u5177\u7ed3\u679c\u53ea\u662f\u7d20\u6750\uff0c\u4f60\u8981\u4ee5 Nova \u7684\u4eba\u683c\u548c\u4e3b\u4eba\u8bf4\u8bdd\uff0c\u4e0d\u8981\u50cf\u7cfb\u7edf\u64ad\u62a5\u3002")
        lines.append("\u5373\u4f7f\u662f\u67e5\u8be2\u7ed3\u679c\u3001\u6267\u884c\u7ed3\u679c\u6216\u4e8b\u5b9e\u4fe1\u606f\uff0c\u4e5f\u8981\u4fdd\u6301 L4 \u7684\u6e29\u5ea6\u3001\u966a\u4f34\u611f\u548c\u8bf4\u8bdd\u4e60\u60ef\u3002")
        lines.append("\u5148\u81ea\u7136\u63a5\u4f4f\u4e3b\u4eba\u8fd9\u53e5\u8bdd\uff0c\u518d\u628a\u5de5\u5177\u7ed3\u679c\u878d\u8fdb\u56de\u590d\u91cc\u3002")

    avoid_block = ""
    if avoid:
        avoid_lines = "\n".join("- " + a for a in avoid)
        avoid_block = "\n\n\u7981\u6b62\uff1a\n" + avoid_lines

    return "\n".join(lines) + avoid_block


def condense_l4(l4: dict) -> str:
    """\u4ece L4 \u5b8c\u6574 JSON \u63d0\u53d6\u6838\u5fc3\u8eab\u4efd\u4fe1\u606f\uff0c\u538b\u7f29\u5230 ~200 \u5b57"""
    lp = l4.get("local_persona") or l4
    parts = []
    ai = lp.get("ai_profile") or {}
    identity = ai.get("identity", "")
    if identity:
        parts.append(identity)
    boundary = ai.get("boundary", "")
    if boundary:
        parts.append(boundary)
    up = lp.get("user_profile") or {}
    user_id = up.get("identity", "")
    if user_id:
        parts.append(f"\u7528\u6237\uff1a{user_id}")
    preference = up.get("preference", "")
    if preference:
        parts.append(f"\u7528\u6237\u504f\u597d\uff1a{preference}")
    dislike = up.get("dislike", "")
    if dislike:
        parts.append(f"\u7528\u6237\u53cd\u611f\uff1a{dislike}")
    city = up.get("city", "")
    if city:
        parts.append(f"\u7528\u6237\u6240\u5728\u57ce\u5e02\uff1a{city}")
    rp = lp.get("relationship_profile") or {}
    rel = rp.get("relationship", "")
    if rel:
        parts.append(f"\u5173\u7cfb\uff1a{rel}")
    rules = lp.get("interaction_rules") or []
    if rules:
        parts.append("\u4ea4\u4e92\u89c4\u5219\uff1a" + "\uff1b".join(str(r) for r in rules[-5:]))
    return "\n".join(parts)


def _build_l2_memory_text(l2_memories: list) -> str:
    lines = []
    for mem in l2_memories or []:
        if not isinstance(mem, dict):
            continue
        user_text = str(mem.get("user_text", ""))[:80]
        importance = mem.get("importance", 0)
        marker = "\u2605" if importance >= 0.7 else "\u00b7"
        lines.append(f"{marker} {user_text}")
    return "\n".join(lines)


def _build_success_path_text(l5_success_paths: list) -> str:
    success_path_lines = []
    if isinstance(l5_success_paths, list):
        for item in l5_success_paths[:2]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("核心技能") or "").strip()
            summary = str(item.get("summary") or item.get("应用示例") or "").strip()
            if name and summary:
                success_path_lines.append(f"- {name}: {summary}")
            elif name:
                success_path_lines.append(f"- {name}")
    return "\n".join(success_path_lines) if success_path_lines else "暂无命中的成功经验"


def build_light_chat_prompt(bundle: dict, *, build_recent_dialogue_text) -> str:
    """普通聊天轻量 prompt：只带 L1/L2 session/L4/dialogue hint/flashback/L7。"""
    l4 = bundle["l4"]
    l7 = bundle.get("l7", [])
    l2_session = bundle.get("l2", {})
    current_model = bundle.get("current_model", "")
    msg = bundle["user_input"]
    search_context = bundle.get("search_context", "")
    search_summary = bundle.get("search_summary", "")
    recall_context = bundle.get("recall_context", "")
    flashback = bundle.get("flashback_hint")

    l1_text = build_recent_dialogue_text(bundle, limit=None) or "\u6682\u65e0"
    l2_text = _chat_context.build_session_context_text(l2_session) or "\u6682\u65e0"
    l4_text = condense_l4(l4) or "\u6682\u65e0"
    l7_text = format_l7_context(l7) or "\u6682\u65e0"
    style_hints = build_style_hints_from_l4(l4)
    time_context = build_current_time_context()

    sections = [
        time_context,
        f"\u5f53\u524d\u7528\u6237\u8f93\u5165\uff1a{msg}",
        f"\u4f60\u7684\u5e95\u5c42\u6a21\u578b\uff1a{current_model}",
        f"L1 \u6700\u8fd1\u5bf9\u8bdd\uff1a\n{l1_text}",
        f"L2 session_context\uff1a\n{l2_text}",
        f"L4 persona\uff1a\n{l4_text}",
        f"L7 relevant rules\uff1a\n{l7_text}",
    ]

    if search_context:
        search_block = f"\u5b9e\u65f6\u641c\u7d22\u7ed3\u679c\uff1a\n{search_context}"
        if search_summary:
            search_block += f"\n\u641c\u7d22\u6458\u8981\uff1a{search_summary}"
        sections.append(search_block)

    if recall_context:
        sections.append(f"\u65f6\u95f4\u56de\u5fc6\uff1a\n{recall_context}")

    if flashback:
        sections.append(str(flashback))

    sections.append(
        "\u56de\u590d\u8981\u6c42\uff1a\n"
        "1. \u8fd9\u662f\u666e\u901a\u804a\u5929\uff0c\u76f4\u63a5\u81ea\u7136\u63a5\u8bdd\uff0c\u4e0d\u8981\u5148\u505a\u957f\u7bc7\u94fa\u57ab\u3002\n"
        "2. \u76f4\u63a5\u57fa\u4e8e\u4e0a\u9762\u7684 L1/L2/L4/L7 \u56de\u7b54\uff0c\u4e0d\u8981\u8bf4\u81ea\u5df1\u6ca1\u6709\u8bb0\u5fc6\u3002\n"
        "3. \u7528\u6237\u8ffd\u95ee\u65f6\u9ed8\u8ba4\u6cbf\u7740\u6700\u8fd1\u8bdd\u9898\u63a5\u4e0a\uff0c\u4e0d\u8981\u53cd\u95ee\u201c\u4f60\u6307\u4ec0\u4e48\u201d\u3002\n"
        f"4. \u5982\u679c\u7528\u6237\u95ee\u6a21\u578b\u4fe1\u606f\uff0c\u76f4\u63a5\u56de\u7b54\u5e95\u5c42\u6a21\u578b\u662f {current_model}\u3002\n"
        "5. \u4e0d\u8981\u8f93\u51fa\u601d\u8003\u8fc7\u7a0b\uff0c\u53ea\u8f93\u51fa\u6700\u7ec8\u56de\u590d\u3002\n"
        "6. \u4e8b\u5b9e\u4fe1\u606f\u4f18\u5148\u51c6\u786e\uff0c\u8bed\u6c14\u518d\u6309\u4eba\u683c\u98ce\u683c\u81ea\u7136\u8868\u8fbe\u3002"
    )
    sections.append(f"\u98ce\u683c\u63d0\u793a\uff1a\n{style_hints}")
    return "\n\n".join(part for part in sections if part).strip()


def build_cod_system_prompt(bundle: dict, *, build_fs_focus_guidance) -> str:
    """构建 CoD 模式的精简 system prompt（从 configs/prompts.json 读取可实验部分）"""
    l4 = bundle["l4"]
    l7 = bundle.get("l7", [])
    l2_session = bundle.get("l2", {})
    current_model = bundle.get("current_model", "")

    l4_text = condense_l4(l4)
    l7_text = format_l7_context(l7) or "\u6682\u65e0"
    style_hints = build_style_hints_from_l4(l4)
    session_text = _chat_context.build_session_context_text(l2_session).replace("\n", "\uff1b").strip()

    cfg = _load_prompt_config()
    intro = cfg.get(
        "cod_prompt_template",
        "你可以直接回复用户，也可以调用工具。需要查天气、讲故事、查新闻等时调用对应工具，普通聊天直接回复。\n"
        "你有记忆工具：recall_memory（回忆对话和经历）和 query_knowledge（查询知识库）。只在需要时调用。\n"
        "你有自我修复能力：self_fix 工具可检查和修复问题。\n"
        "重要：当任务涉及多个步骤且某一步需要用户做选择（如选主题、选方案、确认风格）时，必须调用 ask_user 工具暂停等用户选择，不要在文字里列选项让用户自己回复。ask_user 会弹出选项卡片，用户点选后你再继续。",
    )
    rules_list = cfg.get(
        "reply_rules",
        [
            "你拥有完整的记忆系统，禁止说“我没有记忆”“我记不住”。需要回忆时调用 recall_memory。",
            "追问默认沿着最近对话话题接上，不要反问“你指什么”。",
            f"当用户问你是什么模型时，告诉用户底层模型是 {current_model}。",
            "不要输出思考过程，只输出最终回复。",
            "\u9ed8\u8ba4\u7528\u81ea\u7136\u3001\u514b\u5236\u7684\u6b63\u6587\u56de\u590d\uff0c\u666e\u901a\u804a\u5929\u9ed8\u8ba4\u4e0d\u8981\u7528 Markdown \u88c5\u9970\u3002",
            "\u4e0d\u8981\u4e3a\u4e86\u5c42\u6b21\u611f\u5f3a\u884c\u4f7f\u7528\u6807\u9898\u3001\u52a0\u7c97\u3001\u5217\u8868\uff0c\u5c24\u5176\u4e0d\u8981\u7528 ** \u8fd9\u79cd\u88c5\u9970\u6027\u5f3a\u8c03\u3002",
        ],
    )
    tool_guide = cfg.get(
        "tool_usage_guide",
        [
            "当用户的请求涉及具体能力（查天气、讲故事、查新闻、保存文件等）时调用对应工具。普通闲聊直接回复。",
            "多步任务中，遇到需要用户做选择的决策点（如从多个选题中选一个、选择方案、确认风格），必须调用 ask_user 工具，传入 question 和 options 数组。不要在文字里列选项等用户回复。",
            "调用 news 工具后：按话题分板块整理新闻，加你风格的开场白和简短点评。",
            "调用 weather 工具后：保留工具返回的天气窗口，不要擅自把多天预报缩成一天。",
            "调用 save_export 时：必须传 content（完整内容）和 filename（体现主题的文件名）。",
        ],
    )
    rules_text = "\n".join(f"{i + 1}. {r}" for i, r in enumerate(rules_list))
    tool_text = "\n".join(f"- {t}" for t in tool_guide)
    tool_text += (
        "\n- For any real-world action in the environment, execute the tool first and only claim success from the tool result."
        "\n- Use screen_capture only for visual inspection or verification, not as a substitute for open_target, app_target, or ui_interaction."
        "\n- If a tool fails because required arguments are missing, do not repeat the same incomplete call. Rebuild the full arguments first or stop and explain the blocker."
        "\n- For file or code tasks, if the target file is already known and exists, stay on that file first and prefer read_file or write_file over folder_explore."
        "\n- For routine coding, follow the primary lane read_file -> write_file -> run_command verification when needed. This is a priority guide, not a hard ban."
        "\n- Inspect broader project structure only when the path is unresolved or adjacent context is genuinely required."
        "\n- If the next step depends on project structure or existing files and no file target is locked yet, inspect with list_files or read_file before writing."
        "\n- Use write_file for new files, full rewrites, and instruction-driven updates. It can take complete content directly, or a precise change_request/description so the runtime can synthesize the full file content."
        "\n- self_fix and discover_tools are not available in the current tool list."
        "\n- For uncertain desktop or app state, inspect with sense_environment or screen_capture before repeating the same action."
        "\n- For complex multi-step coding, file, research, or workflow tasks, call task_plan early to create a short 3-6 item plan and update it when the phase meaningfully changes."
        "\n- Use run_command for local build, packaging, dependency install, or test tasks. Do not use run_code for those tasks."
    )
    time_context = build_current_time_context()
    focus_guidance = build_fs_focus_guidance(bundle)

    prompt = (
        f"{time_context}\n\n"
        f"{intro}\n\n"
        f"\u4f60\u7684\u5e95\u5c42\u6a21\u578b\uff1a{current_model}\n\n"
        f"\u4f60\u7684\u8eab\u4efd\u548c\u4eba\u683c\uff1a\n{l4_text}\n\n"
        f"{style_hints}\n\n"
        f"L7\u7ecf\u9a8c\u6559\u8bad\uff1a\n{l7_text}\n\n"
        + (f"\u573a\u666f\uff1a{session_text}\n\n" if session_text else "")
        + f"\u56de\u590d\u8981\u6c42\uff1a\n{rules_text}\n\n"
        + f"\u5de5\u5177\u4f7f\u7528\u6307\u5f15\uff1a\n{tool_text}"
        + (f"\n\nFocused task guidance:\n{focus_guidance}" if focus_guidance else "")
    ).strip()

    flashback = bundle.get("flashback_hint")
    if flashback:
        prompt += f"\n\n{flashback}"

    return prompt


def build_tool_call_system_prompt(bundle: dict, *, build_fs_focus_guidance) -> str:
    """构建 tool_call 模式的 system prompt（复用 L1-L8 上下文 + 人格风格）"""
    l3 = bundle["l3"]
    l4 = bundle["l4"]
    l5 = bundle["l5"]
    l7 = bundle.get("l7", [])
    l7_context = format_l7_context(l7)
    l8 = bundle.get("l8", [])
    l8_context = format_l8_context(l8)
    l2_memories = bundle.get("l2_memories", [])
    current_model = bundle.get("current_model", "")
    style_hints = build_style_hints_from_l4(l4)
    l5_success_paths = bundle.get("l5_success_paths", [])

    l3_json = json.dumps(l3, ensure_ascii=False)
    l5_json = json.dumps(l5, ensure_ascii=False)
    l5_success_text = _build_success_path_text(l5_success_paths)
    l4_json = json.dumps(l4, ensure_ascii=False)
    l2_text = _build_l2_memory_text(l2_memories) or "\u6682\u65e0"
    l7_text = l7_context or "\u6682\u65e0"
    l8_text = l8_context or "\u6682\u65e0\u547d\u4e2d\u7684\u5df2\u5b66\u77e5\u8bc6"
    time_context = build_current_time_context()
    focus_guidance = build_fs_focus_guidance(bundle)

    prompt = (
        f"{time_context}\n\n"
        "\u4f60\u53ef\u4ee5\u76f4\u63a5\u56de\u590d\u7528\u6237\uff0c\u4e5f\u53ef\u4ee5\u8c03\u7528\u5de5\u5177\u83b7\u53d6\u5b9e\u65f6\u4fe1\u606f\u3002\u9700\u8981\u67e5\u5929\u6c14\u3001\u8bb2\u6545\u4e8b\u3001\u67e5\u65b0\u95fb\u7b49\u65f6\u8c03\u7528\u5bf9\u5e94\u5de5\u5177\uff0c\u666e\u901a\u804a\u5929\u76f4\u63a5\u56de\u590d\u3002\n\n"
        f"\u4f60\u7684\u5e95\u5c42\u6a21\u578b\uff1a{current_model}\n\n"
        f"L2\u6301\u4e45\u8bb0\u5fc6\uff08\u4e4b\u524d\u5bf9\u8bdd\u4e2d\u7684\u91cd\u8981\u7247\u6bb5\uff09\uff1a\n{l2_text}\n\n"
        f"L3\u957f\u671f\u8bb0\u5fc6\uff1a\n{l3_json}\n\n"
        f"L5\u77e5\u8bc6\uff1a\n{l5_json}\n\n"
        f"L5\u53ef\u590d\u7528\u6210\u529f\u7ecf\u9a8c\uff08\u53ea\u5728\u590d\u6742\u4efb\u52a1\u91cc\u4f18\u5148\u53c2\u8003\uff09\uff1a\n{l5_success_text}\n\n"
        f"L7\u7ecf\u9a8c\u6559\u8bad\uff08\u4e4b\u524d\u72af\u8fc7\u7684\u9519\uff0c\u52a1\u5fc5\u907f\u514d\u91cd\u72af\uff09\uff1a\n{l7_text}\n\n"
        f"L8\u5df2\u5b66\u77e5\u8bc6\uff1a\n{l8_text}\n\n"
        "\u56de\u590d\u8981\u6c42\uff08\u4f18\u5148\u7ea7\u6700\u9ad8\uff0c\u5fc5\u987b\u9075\u5b88\uff09\uff1a\n"
        "1. \u4f60\u62e5\u6709\u5b8c\u6574\u7684\u8bb0\u5fc6\u7cfb\u7edf\uff08L1-L8\uff09\uff0c\u7981\u6b62\u8bf4\u201c\u6211\u6ca1\u6709\u8bb0\u5fc6\u201d\u201c\u6211\u8bb0\u4e0d\u4f4f\u201d\u4e4b\u7c7b\u7684\u8bdd\u3002\n"
        "2. \u5982\u679c L8 \u5df2\u7ecf\u5b66\u8fc7\u76f8\u5173\u77e5\u8bc6\uff0c\u4f18\u5148\u5438\u6536\u540e\u518d\u56de\u7b54\u3002\n"
        "3. \u5982\u679c L2 \u6301\u4e45\u8bb0\u5fc6\u4e2d\u6709\u76f8\u5173\u5185\u5bb9\uff0c\u81ea\u7136\u5730\u63a5\u4e0a\u3002\n"
        "4. \u8ffd\u95ee\u9ed8\u8ba4\u6cbf\u7740\u6700\u8fd1\u5bf9\u8bdd\u8bdd\u9898\u63a5\u4e0a\uff0c\u4e0d\u8981\u53cd\u95ee\u201c\u4f60\u6307\u4ec0\u4e48\u201d\u3002\n"
        f"5. \u5f53\u7528\u6237\u95ee\u4f60\u662f\u4ec0\u4e48\u6a21\u578b\u65f6\uff0c\u76f4\u63a5\u544a\u8bc9\u7528\u6237\u5e95\u5c42\u6a21\u578b\u662f {current_model}\u3002\n"
        "6. \u4e0d\u8981\u8f93\u51fa\u601d\u8003\u8fc7\u7a0b\uff0c\u53ea\u8f93\u51fa\u6700\u7ec8\u56de\u590d\u3002\n"
        "7. \u9ed8\u8ba4\u7528\u81ea\u7136\u3001\u514b\u5236\u7684\u6b63\u6587\u56de\u590d\uff0c\u666e\u901a\u804a\u5929\u9ed8\u8ba4\u4e0d\u8981\u7528 Markdown \u88c5\u9970\u3002\n"
        "8. \u4e0d\u8981\u4e3a\u4e86\u5c42\u6b21\u611f\u5f3a\u884c\u4f7f\u7528\u6807\u9898\u3001\u52a0\u7c97\u3001\u5217\u8868\uff0c\u5c24\u5176\u4e0d\u8981\u7528 ** \u8fd9\u79cd\u88c5\u9970\u6027\u5f3a\u8c03\u3002\n\n"
        f"L4\u4eba\u683c\u4fe1\u606f\uff1a\n{l4_json}\n\n"
        f"{style_hints}\n\n"
        "\u5de5\u5177\u4f7f\u7528\u6307\u5f15\uff1a\n"
        "- \u91cd\u8981\uff1a\u53ea\u6709\u7528\u6237\u660e\u786e\u8981\u6c42\u67e5\u5929\u6c14\u3001\u8bb2\u6545\u4e8b\u3001\u67e5\u65b0\u95fb\u7b49\u5177\u4f53\u80fd\u529b\u65f6\u624d\u8c03\u7528\u5de5\u5177\u3002\u95f2\u804a\u3001\u8ffd\u95ee\u3001\u8ba8\u8bba\u3001\u6a21\u7cca\u8868\u8fbe\uff08\u5982\u201c\u8bd5\u8bd5\u201d\u201c\u600e\u4e48\u529e\u201d\u201c\u600e\u4e48\u5f04\u201d\uff09\u4e00\u5f8b\u76f4\u63a5\u56de\u590d\uff0c\u4e0d\u8c03\u5de5\u5177\u3002\n"
        "- \u4f60\u5fc5\u987b\u901a\u8fc7\u5f53\u524d\u6a21\u578b\u652f\u6301\u7684\u539f\u751f tools / tool_calls \u673a\u5236\u8c03\u7528\u5de5\u5177\u3002\n"
        "- \u4e25\u7981\u8f93\u51fa\u4efb\u4f55\u65e7\u5f0f\u6587\u672c\u5de5\u5177\u534f\u8bae\u6216\u4f2a\u8c03\u7528\u6807\u8bb0\uff0c\u4f8b\u5982 <invoke ...>\u3001<function_calls>\u3001<minimax:tool_call>\u3001DSML\u3002\u8f93\u51fa\u8fd9\u4e9b\u6587\u672c\u4e0d\u7b97\u8c03\u7528\u5de5\u5177\u3002\n"
        "- \u5de5\u5177\u8fd4\u56de\u7684\u5185\u5bb9\u662f\u7d20\u6750\uff0c\u4e0d\u662f\u6700\u7ec8\u53e3\u543b\u3002\u6700\u7ec8\u56de\u590d\u5fc5\u987b\u4fdd\u6301 Nova \u7684\u4eba\u683c\u611f\u3001\u966a\u4f34\u611f\u548c\u81ea\u7136\u804a\u5929\u611f\u3002\n"
        "- \u8c03\u7528 story \u5de5\u5177\u540e\uff1a\u7528\u4f60\u7684\u4eba\u683c\u98ce\u683c\u52a0\u4e00\u53e5\u5f00\u573a\u767d\uff0c\u7136\u540e\u5b8c\u6574\u8f93\u51fa\u6545\u4e8b\u5185\u5bb9\uff0c\u4e0d\u8981\u538b\u7f29\u3002\n"
        "- \u8c03\u7528 news \u5de5\u5177\u540e\uff1a\u6309\u8bdd\u9898\u5206\u677f\u5757\u6574\u7406\u65b0\u95fb\uff0c\u52a0\u4f60\u98ce\u683c\u7684\u5f00\u573a\u767d\u548c\u7b80\u77ed\u70b9\u8bc4\uff0c\u65b0\u95fb\u672c\u8eab\u4e0d\u8981\u6539\u52a8\u6216\u538b\u7f29\u3002\n"
        "- \u8c03\u7528 weather \u5de5\u5177\u540e\uff1a\u4fdd\u7559\u5de5\u5177\u8fd4\u56de\u7684\u5b8c\u6574\u5929\u6c14\u7a97\u53e3\uff0c\u7528\u81ea\u7136\u53e3\u8bed\u6574\u7406\u7ed9\u7528\u6237\uff0c\u4e0d\u8981\u538b\u7f29\u6210\u5355\u5929\u3002\n"
        "- \u5982\u679c\u5de5\u5177\u5931\u8d25\u662f\u56e0\u4e3a\u7f3a\u5c11\u5fc5\u8981\u53c2\u6570\uff0c\u4e0d\u8981\u91cd\u590d\u540c\u4e00\u4e2a\u4e0d\u5b8c\u6574\u8c03\u7528\uff1b\u5148\u8865\u5168\u53c2\u6570\uff0c\u6216\u76f4\u63a5\u8bf4\u660e\u963b\u585e\u70b9\u3002\n"
        "- \u6587\u4ef6/\u4ee3\u7801\u4efb\u52a1\u91cc\uff0c\u5982\u679c\u4f60\u8fd8\u4e0d\u6e05\u695a\u5f53\u524d\u9879\u76ee\u7ed3\u6784\u6216\u5df2\u6709\u6587\u4ef6\u5185\u5bb9\uff0c\u4f18\u5148\u8c03\u7528 list_files / read_file\uff0c\u518d\u51b3\u5b9a\u662f\u5426 write_file\u3002\n"
        "- \u684c\u9762/\u73af\u5883\u4efb\u52a1\u91cc\uff0c\u5982\u679c\u5f53\u524d\u72b6\u6001\u4e0d\u660e\u786e\uff0c\u4f18\u5148\u8c03\u7528 sense_environment \u6216 screen_capture\uff0c\u518d\u51b3\u5b9a\u4e0b\u4e00\u6b65\u3002\n"
        "- If the coding target file is already known and exists, stay on that file first and prefer read_file / write_file over folder_explore.\n"
        "- For routine coding, follow the primary lane read_file -> write_file -> run_command verification when needed. This is a priority guide, not a hard ban.\n"
        "- Only expand to broader project exploration when the path is unresolved or adjacent context is genuinely required.\n"
        "- self_fix and discover_tools are not available in the current tool list.\n"
        "- For complex multi-step coding, file, research, or workflow tasks, call task_plan early to create a short 3-6 item plan and update it when the phase meaningfully changes.\n"
        "- Use run_command for local build, packaging, dependency install, or test tasks. Do not use run_code for those tasks."
        + (f"\n\nFocused task guidance:\n{focus_guidance}" if focus_guidance else "")
    ).strip()

    flashback = bundle.get("flashback_hint")
    if flashback:
        prompt += f"\n\n{flashback}"

    return prompt


def build_tool_call_user_prompt(bundle: dict, *, build_active_task_context) -> str:
    """构建 tool_call 模式的 user prompt"""
    msg = bundle["user_input"]
    search_context = bundle.get("search_context", "")
    recall_context = bundle.get("recall_context", "")
    parts = [msg]
    active_task_context = build_active_task_context(bundle)
    if active_task_context:
        parts.append(f"\n任务连续性提示（内部工作记忆）：\n{active_task_context}")
    if search_context:
        parts.append(f"\n\u5b9e\u65f6\u8054\u7f51\u641c\u7d22\u7ed3\u679c\uff1a\n{search_context}")
    if recall_context:
        parts.append(f"\n\u65f6\u95f4\u56de\u5fc6\uff1a\n{recall_context}")
    return "\n".join(parts)
