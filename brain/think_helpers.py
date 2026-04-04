import re

DEFAULT_ASSISTANT_SYSTEM_PROMPT = ""
DEFAULT_CHAT_STYLE_PROMPT = ""


def set_default_prompts(default_assistant_system_prompt: str, default_chat_style_prompt: str):
    global DEFAULT_ASSISTANT_SYSTEM_PROMPT, DEFAULT_CHAT_STYLE_PROMPT
    DEFAULT_ASSISTANT_SYSTEM_PROMPT = str(default_assistant_system_prompt or "")
    DEFAULT_CHAT_STYLE_PROMPT = str(default_chat_style_prompt or "")


def _extract_skill_result(prompt: str) -> str:
    """从 prompt 中提取技能结果骨架"""
    prompt = str(prompt or '')
    match = re.search(r'技能结果：\s*(.+?)(?:\n\s*L4人格信息：|\n\s*要求：|\Z)', prompt, flags=re.S)
    if match:
        return match.group(1).strip()
    return ''


def _clean_llm_reply(text: str) -> str:
    if not text:
        return ''

    text = str(text).strip()
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.S | re.I)
    text = re.sub(r'\[思考步骤\].*?\[最终回复\]', '', text, flags=re.S)
    text = text.replace('[最终回复]', '').replace('[思考步骤]', '').strip()

    bad_tokens = ['��', '\u0085', '?|', '?��', '???']
    for token in bad_tokens:
        text = text.replace(token, '')

    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text


def _detect_emotion(reply: str) -> str:
    """Legacy keyword emotion tagging is retired."""
    return 'neutral'


def _detect_mode(prompt: str, context: str = '') -> str:
    text = f"{prompt}\n{context}"
    if '技能结果：' in text:
        return 'skill'
    return 'chat'


def _looks_bad_reply(text: str) -> tuple[bool, str]:
    if not text:
        return True, 'empty_reply'
    text = str(text).strip()
    if '<think>' in text.lower():
        return True, 'think_tag_leaked'
    if '��' in text or '\u0085' in text:
        return True, 'encoding_corruption'
    if len(text) < 2:
        return True, 'reply_too_short'
    weird_count = len(re.findall(r'[\?�]', text))
    if weird_count >= max(6, len(text) // 5):
        return True, 'too_many_garbled_symbols'
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    ascii_words = re.findall(r'[A-Za-z]{2,}', text)
    if len(chinese_chars) < 2 and len(ascii_words) < 2:
        return True, 'insufficient_readable_text'
    if len(chinese_chars) == 0 and len(ascii_words) == 0:
        return True, 'no_readable_text'
    return False, ''


def _explicit_chat_error_reply(use_cfg: dict, reason: str, detail: str = '') -> str:
    model_name = str((use_cfg or {}).get('model') or '当前模型').strip()
    reason_map = {
        'api_error': '模型接口报错',
        'empty_reply': '模型返回了空内容',
        'think_tag_leaked': '模型返回里混入了 think 标签',
        'encoding_corruption': '模型返回内容出现乱码',
        'reply_too_short': '模型返回内容过短',
        'too_many_garbled_symbols': '模型返回内容包含过多异常符号',
        'insufficient_readable_text': '模型返回内容可读文本不足',
        'no_readable_text': '模型返回内容不可读',
        'exception': '模型调用抛出了异常',
        'unknown': '模型返回异常',
    }
    label = reason_map.get(reason, reason_map['unknown'])
    suffix = f'：{detail}' if detail else ''
    return f'当前聊天失败：{model_name}{label}{suffix}。'


def _build_think_prompts(prompt: str, context: str, mode: str) -> tuple[str, str]:
    """把上层 prompt 转成统一的 system/user messages，不在这里再做 persona 文件注入。"""
    if '回复要求（优先级最高' in prompt or ('用户输入：' in prompt and 'L4人格信息：' in prompt):
        persona_block, instructions, user_input = _split_formatted_prompt(prompt)
        system_parts = [DEFAULT_ASSISTANT_SYSTEM_PROMPT]
        if persona_block:
            cleaned_persona = persona_block
            for prefix in [
                "最后，用下面的人格风格润色你的回复（只影响语气和措辞，不能覆盖上面的事实性要求）：\n",
                "最后，用下面的人格风格润色你的回复（只影响语气和措辞，不能覆盖上面的事实性要求）：",
            ]:
                cleaned_persona = cleaned_persona.replace(prefix, "")
            system_parts.append("你的人格风格（由上游注入）：\n" + cleaned_persona.strip())
        context_text = str(context or '').strip()
        if context_text:
            system_parts.append("最近对话上下文：\n" + context_text)
        if instructions:
            system_parts.append(instructions)
        return "\n\n".join(system_parts), user_input or prompt

    skill_result = _extract_skill_result(prompt)
    context_text = str(context or '').strip()
    context_block = ""
    if context_text:
        context_block = f"""最近对话上下文：
{context_text}

联动要求：
1. 你必须针对用户最新这句话回复，这是最高优先级。
2. 如果用户最新这句话明显换了话题，立刻跟着换，不要继续聊旧话题。
3. 只有当用户最新这句话像追问（"然后呢""为什么""这个呢"）时，才承接上一轮话题。
4. 除非上下文确实没有指向，不要反问"你指什么""你说的是哪个"。"""

    system_parts = [
        DEFAULT_ASSISTANT_SYSTEM_PROMPT,
        "回复风格：" + DEFAULT_CHAT_STYLE_PROMPT,
    ]
    if context_block:
        system_parts.append(context_block)
    system_prompt = "\n\n".join(system_parts)

    if mode in ('skill', 'hybrid') and skill_result:
        user_prompt = prompt + "\n\n回复要求：基于技能结果回答，不编造信息。用自然、清楚、稳定的方式表达。只输出最终回复。"
    else:
        user_prompt = prompt + "\n\n回复要求：自然、直接地回应用户；如果是追问就顺着上文接。只输出最终回复。"

    return system_prompt, user_prompt


def _split_formatted_prompt(prompt: str) -> tuple:
    """将 reply_formatter 构建的完整 prompt 拆分为 (persona, instructions, user_input)。
    persona: 人格风格（放 system 开头，权重最高）
    instructions: 记忆/知识/回复要求（放 system 中段）
    user_input: 用户实际输入 + 搜索结果（放 user message）"""
    lines = prompt.split("\n")
    section = "pre"
    user_lines = []
    search_lines = []
    instruction_lines = []
    persona_lines = []

    in_persona = False
    for line in lines:
        if line.startswith("用户输入："):
            user_lines.append(line[len("用户输入："):])
            section = "user_input"
        elif section == "user_input" and (line.startswith("实时") or line.startswith("【实时") or line.startswith("时间回忆")):
            search_lines.append(line)
            section = "search"
        elif section == "user_input" and (line.startswith("你的底层模型") or line.startswith("L2") or line.startswith("L3") or line.startswith("回复要求")):
            instruction_lines.append(line)
            section = "system"
        elif section == "search" and (line.startswith("你的底层模型") or line.startswith("L2") or line.startswith("L3") or line.startswith("回复要求")):
            instruction_lines.append(line)
            section = "system"
        elif section == "user_input":
            user_lines.append(line)
        elif section == "search":
            search_lines.append(line)
        elif section == "system":
            # 检测人格区块开始
            if line.startswith("最后，用下面的人格风格") or line.startswith("L4人格信息"):
                in_persona = True
                persona_lines.append(line)
            elif in_persona:
                persona_lines.append(line)
            else:
                instruction_lines.append(line)

    user_input = "\n".join(user_lines).strip()
    search_block = "\n".join(search_lines).strip()
    instructions = "\n".join(instruction_lines).strip()
    persona = "\n".join(persona_lines).strip()

    if not user_input:
        return "", "", prompt

    user_part = user_input
    if search_block:
        user_part += "\n\n" + search_block

    return persona, instructions, user_part
