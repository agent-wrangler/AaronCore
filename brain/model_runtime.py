import json


def get_models(models_config: dict, current_default: str) -> dict:
    models = {}
    for model_id, cfg in models_config.items():
        models[model_id] = {
            "model": cfg.get("model", model_id),
            "vision": cfg.get("vision", False),
            "base_url": cfg.get("base_url", ""),
        }
    return {"models": models, "current": current_default}


def get_current_model_name(llm_config: dict, current_default: str) -> str:
    return llm_config.get("model", current_default)


def set_default_model(
    model_id: str,
    *,
    models_config: dict,
    raw_config: dict,
    config_path: str = "",
    save_raw_config_fn=None,
) -> tuple[bool, str, dict]:
    if model_id not in models_config:
        return False, "", {}
    try:
        raw_config["default"] = model_id
        if callable(save_raw_config_fn):
            save_raw_config_fn(raw_config)
        elif config_path:
            with open(config_path, "w", encoding="utf-8") as handle:
                json.dump(raw_config, handle, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return True, model_id, models_config[model_id]


def understand_intent(user_input: str, *, llm_config: dict, llm_call_fn) -> dict:
    prompt = f"""用户说：{user_input}

分析用户意图，返回JSON：
{{
    "intent": "聊天/查天气/开网站/搜索/AI画图/其他",
    "action": "具体动作",
    "target": "目标(网站名/关键词等)",
    "need_tool": 如果用户要求查天气/开网站/搜索/画图，就是真，否则假
}}

只返回JSON。"""

    try:
        result_data = llm_call_fn(
            llm_config,
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=150,
            timeout=15,
        )
        return json.loads(result_data["content"])
    except Exception:
        return {"intent": "聊天", "action": "对话", "target": "", "need_tool": False}


def raw_llm(
    prompt: str,
    *,
    llm_config: dict,
    llm_call_fn,
    temperature=0.1,
    max_tokens=150,
    timeout=10,
) -> str:
    result = llm_call_fn(
        llm_config,
        [{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    usage = result.get("usage", {})
    if usage:
        try:
            from core.runtime_state.state_loader import record_stats

            record_stats(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                scene="route",
                cache_write=usage.get("prompt_cache_miss_tokens", 0),
                cache_read=usage.get("prompt_cache_hit_tokens", 0),
                model=llm_config.get("model", ""),
            )
        except Exception:
            pass
    return result.get("content", "")


def vision_llm_call(
    prompt: str,
    images: list | None = None,
    *,
    llm_config: dict,
    models_config: dict,
    llm_call_openai_fn,
) -> str:
    images = images or []
    use_cfg = llm_config
    if images:
        for _, cfg in models_config.items():
            if cfg.get("vision", False):
                use_cfg = cfg
                break

    if images:
        user_content = [{"type": "text", "text": prompt}]
        for image in images:
            url = image if image.startswith("http") else f"data:image/png;base64,{image}"
            user_content.append({"type": "image_url", "image_url": {"url": url}})
    else:
        user_content = prompt

    result = llm_call_openai_fn(
        use_cfg,
        [{"role": "user", "content": user_content}],
        temperature=0.3,
        max_tokens=300,
        timeout=20,
    )
    usage = result.get("usage", {})
    if usage:
        try:
            from core.runtime_state.state_loader import record_stats

            record_stats(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                scene="vision",
                cache_write=usage.get("prompt_cache_miss_tokens", 0),
                cache_read=usage.get("prompt_cache_hit_tokens", 0),
                model=use_cfg.get("model", ""),
            )
        except Exception:
            pass
    return result.get("content", "")
