"""模型配置技能：通过对话添加、切换、删除、查看 LLM 模型"""
import re
import requests

# 已知厂商：用户只需给 key，自动填 base_url 和 model
KNOWN_PROVIDERS = {
    "minimax": {"base_url": "https://api.minimaxi.com/v1", "model": "MiniMax-M2.7"},
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
    "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "glm": {"base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-flash"},
    "doubao": {"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "doubao-1.5-pro-32k"},
    "claude": {"base_url": "https://api.anthropic.com/v1", "model": "claude-sonnet-4-20250514"},
    "kimi": {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
}


def _extract_key(text):
    """从用户输入中提取 API key"""
    m = re.search(r'(sk-[a-zA-Z0-9_-]{20,})', text)
    if m:
        return m.group(1)
    m = re.search(r'(eyJ[a-zA-Z0-9_-]{20,})', text)
    if m:
        return m.group(1)
    # 兜底：找最长的连续字母数字串（至少20位）
    tokens = re.findall(r'[a-zA-Z0-9_-]{20,}', text)
    return tokens[0] if tokens else None


def _detect_provider(text):
    """从用户输入中识别厂商"""
    text_lower = text.lower()
    for name in KNOWN_PROVIDERS:
        if name in text_lower:
            return name
    return None


def _validate_api(base_url, api_key, model_name):
    """验证 API 连通性，返回 (ok, error_msg)"""
    try:
        from brain import llm_call
        cfg = {"base_url": base_url, "api_key": api_key, "model": model_name}
        result = llm_call(cfg, [{"role": "user", "content": "hi"}],
                          max_tokens=5, timeout=10)
        if result.get("error"):
            return False, result["error"]
        return True, None
    except Exception as e:
        return False, f"无法连接：{e}"


def _save_config():
    """持久化当前配置到文件"""
    import brain
    brain._raw_config["models"] = brain.MODELS_CONFIG
    saver = getattr(brain, "save_raw_config", None)
    if not callable(saver):
        raise RuntimeError("save_raw_config is required for redacted model config persistence.")
    saver(brain._raw_config)


def _list_models():
    """列出所有模型"""
    import brain
    models = brain.MODELS_CONFIG
    current = brain._current_default
    if not models:
        return "还没有配置任何模型。你可以说\u201c添加 deepseek 模型 key 是 sk-xxx\u201d来添加。"
    lines = []
    for mid, cfg in models.items():
        mark = " \u2190 当前" if mid == current else ""
        model_name = cfg.get("model", mid)
        lines.append(f"  {mid}（{model_name}）{mark}")
    return "已配置的模型：\n" + "\n".join(lines)


def _switch_model(text):
    """切换模型"""
    import brain
    tl = text.lower()

    # 1) 精确匹配已有模型 ID
    for mid in brain.MODELS_CONFIG:
        if mid.lower() == tl or mid.lower() in tl.split():
            cfg = brain.MODELS_CONFIG[mid]
            api_key = str(cfg.get("api_key", "")).strip()
            if not api_key or len(api_key) < 10 or any('\u4e00' <= c <= '\u9fff' for c in api_key):
                return f"{mid} 的 API key 还没填，去设置页填好再切换。"
            ok = brain.set_default_model(mid)
            if ok:
                return f"已切换到 {mid}，后续对话会用这个模型回复。"
            return f"切换失败，请检查 {mid} 的配置。"

    # 2) 提取用户想要的模型名（如 MiniMax-M2.5）
    m = re.search(r'(?:切换|换到|换成|用到|改成)\s*([a-zA-Z0-9][\w\-\.]*(?:[\-\.]\w+)*)', tl, re.IGNORECASE)
    target = m.group(1).strip() if m else ""
    if not target:
        # fallback: 找输入中最长的模型名样式的 token
        tokens = re.findall(r'[a-zA-Z][\w\-\.]*(?:[\-\.]\w+)+', text)
        target = max(tokens, key=len) if tokens else ""

    # 3) 模糊匹配已有模型的 model name
    if target:
        target_l = target.lower()
        for mid, cfg in brain.MODELS_CONFIG.items():
            model_name = str(cfg.get("model", mid)).lower()
            if target_l == model_name or target_l == mid.lower():
                api_key = str(cfg.get("api_key", "")).strip()
                if not api_key or len(api_key) < 10:
                    return f"{mid} 的 API key 还没填，去设置页填好再切换。"
                ok = brain.set_default_model(mid)
                if ok:
                    return f"已切换到 {cfg.get('model', mid)}，后续对话会用这个模型回复。"

        # 4) 同厂商不同型号：复用已有配置的 API key 和 base_url，创建新模型
        target_prefix = target_l.split("-")[0]
        for mid, cfg in brain.MODELS_CONFIG.items():
            mid_prefix = mid.split("-")[0].lower()
            model_prefix = str(cfg.get("model", "")).split("-")[0].lower()
            if target_prefix == mid_prefix or target_prefix == model_prefix:
                api_key = str(cfg.get("api_key", "")).strip()
                if not api_key or len(api_key) < 10:
                    return f"同厂商的 API key 还没填，去设置页填好再切换。"
                new_cfg = {
                    "api_key": cfg["api_key"],
                    "base_url": cfg["base_url"],
                    "model": target,
                    "vision": cfg.get("vision", False),
                }
                brain.MODELS_CONFIG[target] = new_cfg
                _save_config()
                ok = brain.set_default_model(target)
                if ok:
                    return f"已自动添加并切换到 {target}，复用了同厂商的 API 配置。"
                return f"添加了 {target} 但切换失败，请检查配置。"

    available = "、".join(brain.MODELS_CONFIG.keys())
    return f"没找到你说的模型。当前可用：{available}"


def _search_context_for_model_info(context):
    """从对话历史中搜索 API key 和厂商信息"""
    if not isinstance(context, dict):
        return None, None
    history = context.get("recent_history") or []
    found_key = None
    found_provider = None
    for item in reversed(history):
        content = str(item.get("content") or "")
        if not found_key:
            found_key = _extract_key(content)
        if not found_provider:
            found_provider = _detect_provider(content)
        if found_key and found_provider:
            break
    return found_key, found_provider


def _add_model(text, context=None):
    """添加新模型"""
    import brain
    provider = _detect_provider(text)
    api_key = _extract_key(text)

    # 当前输入缺信息时，从对话历史中补全
    if not api_key or not provider:
        ctx_key, ctx_provider = _search_context_for_model_info(context)
        if not api_key and ctx_key:
            api_key = ctx_key
        if not provider and ctx_provider:
            provider = ctx_provider

    if not api_key:
        if provider:
            return f"识别到 {provider}，但没找到 key。请把完整的 API key 发给我，格式像 sk-xxxxx。"
        return "请告诉我要添加哪个厂商的模型，以及 API key。\n例如：\u201c添加 minimax 模型 key 是 sk-xxx\u201d\n\n支持的厂商：" + "、".join(KNOWN_PROVIDERS.keys())

    if not provider:
        return "拿到 key 了，但不确定是哪家的。请说明厂商名，比如：\u201c这是 minimax 的 key\u201d\n\n支持自动配置的厂商：" + "、".join(KNOWN_PROVIDERS.keys())

    preset = KNOWN_PROVIDERS[provider]
    base_url = preset["base_url"]
    model_name = preset["model"]
    model_id = provider

    # 验证连通性
    ok, err = _validate_api(base_url, api_key, model_name)
    if not ok:
        return f"{provider} 的 API 验证失败（{err}）。请检查 key 是否正确。"

    # 写入配置
    brain.MODELS_CONFIG[model_id] = {
        "api_key": api_key,
        "base_url": base_url,
        "model": model_name,
        "vision": False,
    }
    _save_config()

    # 如果是第一个模型，自动设为默认
    if len(brain.MODELS_CONFIG) == 1:
        brain.set_default_model(model_id)
        return f"{provider} 配置成功并已设为当前模型。验证通过，可以正常使用了。"

    return f"{provider} 配置成功，验证通过。当前使用的还是 {brain._current_default}，想切换的话说\u201c切换到 {model_id}\u201d。"


def _delete_model(text):
    """删除模型"""
    import brain
    for mid in brain.MODELS_CONFIG:
        if mid in text.lower():
            if mid == brain._current_default:
                return f"不能删除当前正在使用的模型 {mid}。先切换到别的模型再删。"
            del brain.MODELS_CONFIG[mid]
            _save_config()
            return f"已删除 {mid}。"
    available = "、".join(brain.MODELS_CONFIG.keys())
    return f"没找到你说的模型。当前已配置：{available}"


def _current_model():
    """显示当前模型"""
    import brain
    mid = brain._current_default
    cfg = brain.MODELS_CONFIG.get(mid, {})
    model_name = cfg.get("model", mid)
    return f"当前使用的是 {mid}（{model_name}）"


def execute(user_input: str, context: dict = None) -> str:
    text = user_input.strip()
    tl = text.lower()

    # 列出模型
    if any(kw in tl for kw in ["列出", "有哪些", "所有模型", "模型列表"]):
        return _list_models()

    # 当前模型
    if any(kw in tl for kw in ["当前模型", "现在用的", "在用什么", "用的什么"]):
        return _current_model()

    # 删除模型
    if any(kw in tl for kw in ["删除模型", "删掉", "移除"]):
        return _delete_model(text)

    # 切换模型
    if any(kw in tl for kw in ["切换", "换到", "用到", "改成", "换成"]):
        return _switch_model(text)

    # 添加模型（含 key 或厂商名）
    if any(kw in tl for kw in ["添加", "接入", "配置", "对接", "加个", "加一个"]) or _extract_key(text):
        return _add_model(text, context)

    # 兜底：尝试从上下文推断是否要添加模型
    ctx_key, ctx_provider = _search_context_for_model_info(context)
    if ctx_key or ctx_provider:
        return _add_model(text, context)
    return _list_models()
