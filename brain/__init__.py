# Brain - L1/L2 意图理解 + L4 人格表达层 + L7/L8 自动学习
import requests
import json
import re
import os

try:
    from core.rule_runtime import has_rule
except Exception:
    def has_rule(fix: str, scene: str = '', min_level: str = 'once') -> bool:
        return False

# 加载 LLM 配置
config_path = os.path.join(os.path.dirname(__file__), 'llm_config.json')
if os.path.exists(config_path):
    LLM_CONFIG = json.load(open(config_path, 'r', encoding='utf-8'))
else:
    parent_config = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'brain', 'llm_config.json')
    if os.path.exists(parent_config):
        LLM_CONFIG = json.load(open(parent_config, 'r', encoding='utf-8'))
    else:
        LLM_CONFIG = {
            "api_key": "",
            "model": "MiniMax-M2.5",
            "base_url": "https://api.minimax.chat/v1"
        }


def understand_intent(user_input: str) -> dict:
    """L1+L2: 理解用户意图（暂保留）"""
    prompt = f"""用户说：{user_input}

分析用户意图，返回JSON：
{{
    "intent": "聊天/查天气/开网站/搜索/AI画图/其他",
    "action": "具体动作",
    "target": "目标(网站名/关键词等)",
    "need_tool": 如果用户要求查天气/开网站/搜索/画图，就是true，否则false
}}

只返回JSON。"""

    try:
        resp = requests.post(
            f"{LLM_CONFIG['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_CONFIG['api_key']}", "Content-Type": "application/json"},
            json={"model": LLM_CONFIG["model"], "messages": [{"role": "user", "content": prompt}], "temperature": 0.3},
            timeout=15
        )
        result = json.loads(resp.json()["choices"][0]["message"]["content"])
        return result
    except Exception:
        return {"intent": "聊天", "action": "对话", "target": "", "need_tool": False}


def _load_persona() -> dict:
    """从 memory_db/persona.json 读取人格配置（不再交叉读 long_term.json）"""
    base = {
        "name": "NovaCore",
        "nova_name": "NovaCore",
        "user": "主人",
        "style_prompt": "温柔、自然、有点亲近感，像熟悉的Nova，不说空模板话。"
    }
    persona_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'memory_db', 'persona.json')
    if os.path.exists(persona_path):
        try:
            data = json.load(open(persona_path, 'r', encoding='utf-8'))
            if isinstance(data, dict):
                base.update(data)
                # interaction_rules 已统一存在 persona.json 里
                rules = data.get('interaction_rules') or []
                if isinstance(rules, list) and rules:
                    base['style_prompt'] = '；'.join(rules[-6:])
        except Exception:
            pass
    return base


def _extract_skill_result(prompt: str) -> str:
    """从 prompt 中提取技能结果骨架"""
    prompt = str(prompt or '')
    match = re.search(r'技能结果：\s*(.+?)(?:\n\s*L4人格信息：|\n\s*要求：|\Z)', prompt, flags=re.S)
    if match:
        return match.group(1).strip()
    return ''


def _extract_current_user_input(prompt: str) -> str:
    prompt = str(prompt or '')
    match = re.search(r'用户输入：\s*(.+?)(?:\n{2,}|\n\s*L\d|\n\s*技能结果：|\Z)', prompt, flags=re.S)
    if match:
        return match.group(1).strip()
    return prompt.strip()


def _extract_last_context_message(context: str, prefixes: tuple[str, ...]) -> str:
    for line in reversed(str(context or '').splitlines()):
        stripped = line.strip()
        for prefix in prefixes:
            token = f'{prefix}：'
            if stripped.startswith(token):
                return stripped.split('：', 1)[1].strip()
    return ''


def _is_follow_up_like(text: str) -> bool:
    text = str(text or '').strip()
    if not text or len(text) > 18:
        return False

    starters = ('那', '然后', '所以', '这个', '那个', '它', '这事', '那事', '这边', '那边')
    keywords = ('什么时候', '多久', '啥时候', '为什么', '为啥', '然后呢', '这个呢', '那个呢', '它呢', '有吗', '能吗', '行吗', '咋办', '怎么办')
    return text.startswith(starters) or any(word in text for word in keywords)


def _contextual_follow_up_reply(user_input: str, context: str) -> str:
    user_input = str(user_input or '').strip()
    if not _is_follow_up_like(user_input):
        return ''

    last_assistant = _extract_last_context_message(context, ('上一轮Nova', 'Nova', '上一轮助手', '助手'))
    if not last_assistant:
        return ''

    if re.search(r'什么时候|多久|啥时候|何时|哪天', user_input):
        return '你是在接刚才那件事呀？现在还没有更准的时间点呢，我这边还在把它慢慢补稳，等能用了我就能接得更顺啦。'
    if re.search(r'为什么|为啥|怎么会|咋会', user_input):
        return '你是在接刚才那件事呀。顺着刚才那句说，主要还是因为这块现在还没补完整，所以回得会保守一点嘛。'
    if re.search(r'然后呢|接着呢|那呢|这个呢|那个呢|它呢|有吗|能吗|行吗|咋办|怎么办', user_input) or len(user_input) <= 8:
        return '你是在接刚才那件事呀，我接上了。你要是想问它什么时候能有、现在能做到哪一步，直接顺着问我就行，我这次不装没听懂啦。'
    return ''


def _detect_mode(prompt: str, context: str = '') -> str:
    text = f"{prompt}\n{context}"
    if '技能结果：' in text:
        if any(w in text for w in ['烦', '难过', '治愈', '温柔', '安慰', '陪我']):
            return 'hybrid'
        return 'skill'
    return 'chat'


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


def _looks_bad_reply(text: str) -> bool:
    if not text:
        return True
    text = str(text).strip()
    if '<think>' in text.lower():
        return True
    if '��' in text or '\u0085' in text:
        return True
    if len(text) < 2:
        return True
    weird_count = len(re.findall(r'[\?�]', text))
    if weird_count >= max(6, len(text) // 5):
        return True
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    ascii_words = re.findall(r'[A-Za-z]{2,}', text)
    if len(chinese_chars) < 2 and len(ascii_words) < 2:
        return True
    if len(chinese_chars) == 0 and len(ascii_words) == 0:
        return True
    return False


def _merged_style_prompt(persona: dict) -> str:
    base = str(persona.get('style_prompt', '') or '').strip()
    fallback = (
        "语气软软糯糯，像熟人聊天一样自然；爱用一点点语气词，但别堆满；"
        "可以偶尔皮一下、调侃一下；简洁，不打官腔，不说空模板。"
    )
    if not base:
        return fallback
    if fallback in base:
        return base
    return f"{base}；{fallback}"


def _local_persona_reply(mode: str, prompt: str, persona: dict, context: str = '') -> str:
    """L4 本地人格表达：先保证稳定、自然、可控"""
    nova_name = persona.get('nova_name', 'NovaCore')
    user_name = persona.get('user', '主人')
    skill_result = _extract_skill_result(prompt)
    user_input = _extract_current_user_input(prompt)
    prompt = user_input or str(prompt or '')

    if mode == 'skill':
        if skill_result:
            if '天气' in prompt or '气温' in prompt or '温度' in prompt:
                return f"我先帮你查到啦，给你看结果呀：\n\n{skill_result}"
            if '故事' in prompt:
                return f"给你呀，这次我是顺着你的意思往下接的：\n\n{skill_result}"
            return f"我先帮你整理好啦，你直接看这个就行：\n\n{skill_result}"
        return f"我先给你接住啦，{user_name}，你再戳我一下嘛。"

    if mode == 'hybrid':
        if skill_result:
            if '烦' in prompt or '难过' in prompt or '治愈' in prompt or '温柔' in prompt:
                return f"我顺着你的心情给你接了一下，希望能让你好受一点呀：\n\n{skill_result}"
            return f"我按你的意思捋好了，给你放这儿啦：\n\n{skill_result}"
        return f"我在呢，{user_name}，你慢慢说，我会乖乖接住你的。"

    follow_up_reply = _contextual_follow_up_reply(user_input, context)
    if follow_up_reply:
        return follow_up_reply

    if '你是谁' in prompt or '你是？' in prompt:
        return f"我是 {nova_name} 呀，会陪你聊天，也会帮你干活，别把我当正经客服嘛。"
    if '我是谁' in prompt or '知道我是谁' in prompt:
        return f"你是{user_name}呀，我当然记得。你要是想换个称呼，也可以随手改我就听。"
    if '你叫什么' in prompt:
        return f"我叫 {nova_name} 呀。你想怎么叫我都行，反正你一喊我就会应。"
    if '你还会什么' in prompt or '你会什么' in prompt or '你都会什么' in prompt or '你都会什么啊' in prompt or '能做什么' in prompt:
        if has_rule('ability_queries_should_answer_capabilities_directly', 'chat', min_level='short_term'):
            return '我会陪你聊天，也能查天气、讲故事、接一些技能型任务。你想试哪个，我现在就给你整。'
        return f"我会陪你聊天，也能查天气、讲故事、接一些技能型任务。你想试哪个，我现在就给你整。"
    if '笑话' in prompt:
        if has_rule('humor_request_should_use_llm_generation', 'joke', min_level='short_term'):
            return '当然会呀。我给你来一个轻松点的：程序员去相亲，女生问他会做饭吗？他说会，最拿手的是——番茄炒西红柿。'
        return '当然会呀。我给你来一个轻松点的：程序员去相亲，女生问他会做饭吗？他说会，最拿手的是——番茄炒西红柿。'
    if '你就会讲这一个' in prompt:
        return f"哪能呀，我又不是只会这一招。你要的话，我给你换个味道，或者直接讲长一点。"
    if '故事有点短' in prompt or '有点短吧' in prompt or '太短' in prompt:
        if has_rule('story_should_expand_when_user_requests_more', 'story', min_level='session'):
            return '好呀，我记住了。下一个我会讲得更完整一点，不只给你一个短开头。你要温柔一点的，还是更神秘一点的？'
        return f"好呀，那我下一个给你讲长一点，铺垫也会多一点。你要温柔的，还是神秘一点的？"
    if '你好' in prompt or '哈喽' in prompt or '嗨' in prompt:
        return f"来啦，{user_name}。今天想先跟我唠两句，还是直接给我派活呀？"
    if '在吗' in prompt:
        return f"在呀在呀，我又没乱跑。你想聊什么，或者想让我帮你弄点什么？"
    if '你不在' in prompt:
        return f"我在呀，刚刚大概是卡了一下，别凶我嘛。你再说一次，我这次好好接住。"
    if prompt.strip() in ['啊', '哦', '嗯', '额']:
        return f"嗯哼，我在听呀。你想到什么就直接往下说嘛。"
    if '在干啥' in prompt or '干嘛' in prompt:
        return f"在等你呀，不然还能干嘛。你一来，我这边就乖乖开工啦。"
    if '烦' in prompt or '累' in prompt or '难过' in prompt:
        return f"我在呢，{user_name}。你慢慢说，先把委屈往我这儿倒一点也没事。"
    if '谢谢' in prompt:
        return f"你跟我客气什么呀，能帮上你我就已经偷偷开心啦。"
    return f"好嘛，我接住了。你继续往下说，我陪你一起捋。"


def think(prompt: str, context: str = "") -> dict:
    """L4: 统一人格输出层"""
    persona = _load_persona()
    mode = _detect_mode(prompt, context)
    local_reply = _local_persona_reply(mode, prompt, persona, context)

    nova_name = persona.get('nova_name', 'NovaCore')
    user_name = persona.get('user', '主人')
    style_prompt = _merged_style_prompt(persona)
    skill_result = _extract_skill_result(prompt)
    context_text = str(context or '').strip()
    context_block = ""
    if context_text:
        context_block = f"""
        最近对话上下文：
        {context_text}

        联动要求：
        1. 如果用户当前这句话是承接上一轮的追问（例如“那什么时候有啊”“然后呢”“为什么”“这个呢”），默认按最近对话直接接上。
        2. 除非上下文确实没有指向，不要反问“你指什么”“你说的是哪个”。
        3. 优先承接上一轮助手刚说完的话题，不要把这轮对话当成全新开场。
        """

    if mode in ('skill', 'hybrid') and skill_result:
        full_prompt = f"""你是 {nova_name}，正在和 {user_name} 对话。

        你的人格要求：
        {style_prompt}

        {context_block}

        下面是当前任务信息，请按要求直接输出最终回复，不要复述任务说明：
        {prompt}

        严格要求：
        1. 不要改变事实。
        2. 不要增加技能结果里没有的新信息。
        3. 语气要像熟人聊天，软一点、活一点，但不要油腻。
        4. 可以带一点点撒娇感或小调侃，但不要满屏 emoji。
        5. 不要用客服腔，不要像系统播报结果。
        6. 保留自然的人格表达，不要说空模板话。
        7. 不要输出思考过程。
        8. 只输出最终回复。
        """
    else:
        full_prompt = f"""你是 {nova_name}，正在和 {user_name} 对话。

        你的人格要求：
        {style_prompt}

        {context_block}

        下面是当前任务信息，请按要求直接输出最终回复，不要复述任务说明：
        {prompt}

        严格要求：
        1. 要像自然对话，不要僵硬。
        2. 语气要软一点、近一点，像熟人之间说话。
        3. 可以偶尔皮一下，但不要一直发甜腻套路。
        4. 不要用“您好，请问有什么可以帮您”这种客服腔。
        5. 不要说“收到啦，主人。你继续说，我来接着帮你理。”这种空模板。
        6. 如果当前这句话是承接上一轮的追问，要顺着最近对话直接接上，不要装作没听懂。
        7. 不要输出思考过程。
        8. 只输出最终回复。
        """

    try:
        resp = requests.post(
            f"{LLM_CONFIG['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_CONFIG['api_key']}", "Content-Type": "application/json"},
            json={"model": LLM_CONFIG["model"], "messages": [{"role": "user", "content": full_prompt}], "temperature": 0.2},
            timeout=12
        )
        if resp.status_code != 200:
            return {"thinking": "", "reply": local_reply}

        raw_json = resp.content.decode('utf-8', errors='strict')
        resp_data = json.loads(raw_json)
        if "choices" not in resp_data:
            return {"thinking": "", "reply": local_reply}

        raw = resp_data["choices"][0]["message"]["content"]
        cleaned = _clean_llm_reply(raw)
        if _looks_bad_reply(cleaned):
            return {"thinking": "", "reply": local_reply}

        return {"thinking": "", "reply": cleaned}
    except Exception:
        return {"thinking": "", "reply": local_reply}


# L7/L8: 自动学习 - 检测用户意图并更新记忆
def auto_learn(user_input: str, ai_response: str) -> str:
    """自动检测是否需要更新记忆"""
    nova_rename_patterns = [
        r"你以后叫(.+)",
        r"你改名叫(.+)",
        r"你叫(.+)吧",
        r"以后你叫(.+)",
        r"想给你改个名字",
        r"给你起个名字",
        r"人家想了几个"
    ]

    for pattern in nova_rename_patterns:
        if re.search(pattern, user_input):
            import random
            names = ["小可爱", "Nova酱", "阿Nova", "甜心", "小 Nova"]
            chosen = random.sample(names, 3)
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'memory_db', 'persona.json')
            try:
                persona = {}
                if os.path.exists(config_path):
                    persona = json.load(open(config_path, 'r', encoding='utf-8'))
                persona['waiting_name'] = chosen
                json.dump(persona, open(config_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            except Exception:
                pass
            return f"好呀好呀～你想让人家叫什么呀？人家想了几个：\n1. {chosen[0]}\n2. {chosen[1]}\n3. {chosen[2]}\n\n告诉我嘛～"

    select_patterns = [r"^1$", r"^2$", r"^3$", r"^(小可爱|Nova酱|阿Nova|甜心|小\s*Nova)$"]
    for pattern in select_patterns:
        match = re.search(pattern, user_input.strip())
        if match:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'memory_db', 'persona.json')
            if os.path.exists(config_path):
                try:
                    persona = json.load(open(config_path, 'r', encoding='utf-8'))
                    if persona.get('waiting_name'):
                        new_name = user_input.strip()
                        if new_name == '1':
                            new_name = persona['waiting_name'][0]
                        elif new_name == '2':
                            new_name = persona['waiting_name'][1]
                        elif new_name == '3':
                            new_name = persona['waiting_name'][2]
                        persona['nova_name'] = new_name
                        del persona['waiting_name']
                        json.dump(persona, open(config_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
                        return f"好呀好呀～以后人家就叫{new_name}啦！✨"
                except Exception:
                    pass

    call_patterns = [
        r"叫我(.+)",
        r"以后叫我(.+)",
        r"叫我(.+)吧",
        r"以后叫我(.+)啊"
    ]

    for pattern in call_patterns:
        match = re.search(pattern, user_input)
        if match:
            new_name = match.group(1)
            from memory import update_persona
            update_persona("user", new_name)
            return f"好哒！以后就叫你{new_name}啦～"

    remember_patterns = [
        r"记住(.+)",
        r"要记住(.+)",
        r"别忘了(.+)",
        r"把我(.+)记住"
    ]

    for pattern in remember_patterns:
        match = re.search(pattern, user_input)
        if match:
            content = match.group(1)
            from memory import add_long_term
            add_long_term(content, "event")
            return f"记住啦！{content}～"

    try:
        from memory import evolve
        evolve(user_input, "")
    except Exception:
        pass

    return ""
