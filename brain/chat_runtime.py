"""Chat/runtime orchestration helpers for brain.think interfaces."""

from __future__ import annotations


def _record_usage(usage: dict, *, scene: str, model: str) -> None:
    if not usage:
        return
    try:
        from core.runtime_state.state_loader import record_stats

        record_stats(
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            scene=scene,
            cache_write=usage.get("prompt_cache_miss_tokens", 0),
            cache_read=usage.get("prompt_cache_hit_tokens", 0),
            model=model,
        )
    except Exception:
        pass


def think(
    prompt: str,
    *,
    context: str = "",
    image: str = None,
    model_id: str = None,
    images: list = None,
    llm_config: dict,
    models_config: dict,
    detect_mode_fn,
    build_think_prompts_fn,
    llm_call_fn,
    llm_call_openai_fn,
    clean_llm_reply_fn,
    looks_bad_reply_fn,
    explicit_chat_error_reply_fn,
    detect_emotion_fn,
) -> dict:
    image_list = images or ([image] if image else [])
    mode = detect_mode_fn(prompt, context)

    use_cfg = llm_config
    if model_id and model_id in models_config:
        use_cfg = models_config[model_id]
    if image_list and not use_cfg.get("vision", False):
        for _, model_cfg in models_config.items():
            if model_cfg.get("vision", False):
                use_cfg = model_cfg
                break

    system_prompt, user_prompt = build_think_prompts_fn(prompt, context, mode)

    if image_list:
        messages = [{"role": "system", "content": system_prompt}]
        user_content = [{"type": "text", "text": user_prompt}]
        for item in image_list:
            url = item if item.startswith("http") else f"data:image/png;base64,{item}"
            user_content.append({"type": "image_url", "image_url": {"url": url}})
        messages.append({"role": "user", "content": user_content})
        call_fn = llm_call_openai_fn
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        call_fn = llm_call_fn

    for attempt in range(2):
        try:
            result = call_fn(use_cfg, messages, temperature=0.7, max_tokens=2000, timeout=25)
            if result.get("error"):
                print(f"[think] LLM error: {result['error']}")
                if attempt == 0:
                    continue
                return {
                    "thinking": "",
                    "reply": explicit_chat_error_reply_fn(
                        use_cfg,
                        "api_error",
                        str(result.get("error", ""))[:120],
                    ),
                    "emotion": "neutral",
                }

            usage = result.get("usage", {})
            _record_usage(
                usage,
                scene="skill" if mode in ("skill", "hybrid") else "chat",
                model=use_cfg.get("model", ""),
            )

            raw = result.get("content", "")
            cleaned = clean_llm_reply_fn(raw)
            bad, bad_reason = looks_bad_reply_fn(cleaned)
            if bad:
                print(f"[think] bad reply filtered: {repr(cleaned[:100])} reason={bad_reason}")
                return {
                    "thinking": "",
                    "reply": explicit_chat_error_reply_fn(use_cfg, bad_reason),
                    "emotion": "neutral",
                }

            return {
                "thinking": "",
                "reply": cleaned,
                "emotion": detect_emotion_fn(cleaned),
            }
        except Exception as exc:
            print(f"[think] attempt {attempt + 1} exception: {exc}")
            if attempt == 0:
                continue
            return {
                "thinking": "",
                "reply": explicit_chat_error_reply_fn(use_cfg, "exception", str(exc)[:120]),
                "emotion": "neutral",
            }

    return {
        "thinking": "",
        "reply": explicit_chat_error_reply_fn(use_cfg, "unknown"),
        "emotion": "neutral",
    }


def think_stream(
    prompt: str,
    *,
    context: str = "",
    image: str = None,
    model_id: str = None,
    images: list = None,
    llm_config: dict,
    models_config: dict,
    detect_mode_fn,
    build_think_prompts_fn,
    think_fn,
    llm_call_stream_fn,
):
    image_list = images or ([image] if image else [])
    mode = detect_mode_fn(prompt, context)

    use_cfg = llm_config
    if model_id and model_id in models_config:
        use_cfg = models_config[model_id]
    if image_list and not use_cfg.get("vision", False):
        for _, model_cfg in models_config.items():
            if model_cfg.get("vision", False):
                use_cfg = model_cfg
                break

    system_prompt, user_prompt = build_think_prompts_fn(prompt, context, mode)

    if image_list:
        result = think_fn(prompt, context=context, image=image, model_id=model_id, images=images)
        reply = result.get("reply", "")
        if reply:
            yield reply
        yield {"_done": True, "usage": {}}
        return

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    usage = {}
    try:
        for chunk in llm_call_stream_fn(
            use_cfg,
            messages,
            temperature=0.7,
            max_tokens=2000,
            timeout=25,
        ):
            if isinstance(chunk, dict):
                if chunk.get("_usage"):
                    usage = chunk["_usage"]
                else:
                    yield chunk
            else:
                yield chunk
    except Exception as exc:
        print(f"[think_stream] exception: {exc}")

    _record_usage(
        usage,
        scene="skill" if mode in ("skill", "hybrid") else "chat",
        model=use_cfg.get("model", ""),
    )
    yield {"_done": True, "usage": usage}
