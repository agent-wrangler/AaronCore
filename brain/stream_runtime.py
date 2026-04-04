"""Streaming LLM runtime helpers for brain."""

from __future__ import annotations

import json


def llm_call_stream(
    cfg: dict,
    messages: list,
    *,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    timeout: int = 25,
    tools: list | None = None,
    is_anthropic_provider_fn,
    stream_anthropic_fn,
    stream_openai_fn,
):
    if is_anthropic_provider_fn(cfg):
        yield from stream_anthropic_fn(
            cfg,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            tools=tools,
        )
        return
    yield from stream_openai_fn(
        cfg,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        tools=tools,
    )


def stream_openai(
    cfg: dict,
    messages: list,
    *,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    timeout: int = 25,
    tools: list | None = None,
    normalize_openai_messages_fn,
    build_openai_base_url_fn,
    build_openai_extra_body_fn,
    post_llm_request_fn,
    extract_network_meta_fn,
    with_minimax_fallback_cfg_fn,
    is_minimax_provider_fn,
    normalize_reasoning_details_fn,
    llm_call_openai_fn,
):
    try:
        messages = normalize_openai_messages_fn(messages)
        base_url = build_openai_base_url_fn(cfg.get("base_url", ""), cfg)
        emitted_visible = False
        emitted_tool_calls = False
        response_meta = {}
        reasoning_buffers = {}
        content_buffer = ""

        def extract_reasoning_text(delta: dict) -> str:
            if not isinstance(delta, dict):
                return ""
            parts = []
            reasoning_details = normalize_reasoning_details_fn(delta.get("reasoning_details"))
            if reasoning_details:
                return "".join(str(item.get("text") or "") for item in reasoning_details)
            for key in ("reasoning_content", "reasoning", "thinking", "thinking_content"):
                value = delta.get(key)
                if isinstance(value, str) and value.strip():
                    parts.append(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and item.strip():
                            parts.append(item)
                        elif isinstance(item, dict):
                            text = item.get("text") or item.get("content") or item.get("thinking") or item.get("reasoning")
                            if isinstance(text, str) and text.strip():
                                parts.append(text)
                elif isinstance(value, dict):
                    text = value.get("text") or value.get("content")
                    if isinstance(text, str) and text.strip():
                        parts.append(text)
            return "".join(parts)

        def consume_reasoning_delta(delta: dict) -> str:
            details = normalize_reasoning_details_fn(delta.get("reasoning_details"))
            if not details:
                return extract_reasoning_text(delta)
            parts = []
            for idx, item in enumerate(details):
                text = str(item.get("text") or "")
                if not text:
                    continue
                prev = str(reasoning_buffers.get(idx) or "")
                if text.startswith(prev):
                    new_text = text[len(prev):]
                elif prev.startswith(text):
                    new_text = ""
                else:
                    new_text = text
                reasoning_buffers[idx] = text
                if new_text:
                    parts.append(new_text)
            return "".join(parts)

        def consume_content_delta(delta: dict, *, provider_cfg: dict) -> str:
            nonlocal content_buffer
            token = str(delta.get("content", "") or "")
            if not token:
                return ""
            if not is_minimax_provider_fn(provider_cfg):
                return token
            prev = content_buffer
            if token.startswith(prev):
                new_text = token[len(prev):]
            elif prev.startswith(token):
                new_text = ""
            else:
                new_text = token
            content_buffer = token
            return new_text

        def send(req_cfg: dict):
            body = {
                "model": req_cfg["model"],
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            extra_body = build_openai_extra_body_fn(req_cfg)
            if extra_body:
                body.update(extra_body)
            if tools:
                body["tools"] = tools
            return post_llm_request_fn(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {req_cfg['api_key']}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=(10, 90),
                stream=True,
            )

        req_cfg = cfg
        resp = send(req_cfg)
        response_meta = extract_network_meta_fn(resp)
        if resp.status_code != 200:
            retry_cfg = with_minimax_fallback_cfg_fn(cfg, getattr(resp, "text", ""), resp.status_code)
            if retry_cfg:
                req_cfg = retry_cfg
                resp = send(req_cfg)
                response_meta = extract_network_meta_fn(resp)
        if resp.status_code != 200:
            try:
                from core.shared import debug_write

                debug_write(
                    "llm_stream_error",
                    {
                        "status": resp.status_code,
                        "body": resp.text[:500],
                        "model": req_cfg.get("model", ""),
                        "base_url": cfg.get("base_url", ""),
                        "roles": [str(m.get("role", "")) for m in messages],
                        "message_count": len(messages),
                        "tail_preview": [
                            {
                                "role": str(m.get("role", "")),
                                "content": str(m.get("content", ""))[:120],
                            }
                            for m in messages[-3:]
                        ],
                        "network_meta": response_meta,
                    },
                )
            except Exception:
                pass
            return

        usage = {}
        tool_call_accum = {}
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
                choice = chunk.get("choices", [{}])[0]
                delta = choice.get("delta", {})
                finish_reason = choice.get("finish_reason")
                reasoning_text = consume_reasoning_delta(delta)
                if reasoning_text:
                    yield {"_thinking_content": reasoning_text}
                token = consume_content_delta(delta, provider_cfg=req_cfg)
                if token:
                    emitted_visible = True
                    yield token

                tc_deltas = delta.get("tool_calls")
                if tc_deltas:
                    for tc_delta in tc_deltas:
                        idx = tc_delta.get("index", 0)
                        if idx not in tool_call_accum:
                            tool_call_accum[idx] = {
                                "id": tc_delta.get("id", ""),
                                "type": tc_delta.get("type", "function"),
                                "function": {"name": "", "arguments": ""},
                            }
                        if tc_delta.get("id"):
                            tool_call_accum[idx]["id"] = tc_delta["id"]
                        fn = tc_delta.get("function") or {}
                        if fn.get("name"):
                            tool_call_accum[idx]["function"]["name"] += fn["name"]
                        if fn.get("arguments"):
                            tool_call_accum[idx]["function"]["arguments"] += fn["arguments"]

                if chunk.get("usage"):
                    usage = chunk["usage"]
                if finish_reason == "tool_calls" and tool_call_accum:
                    emitted_tool_calls = True
                    yield {"_tool_calls": [tool_call_accum[i] for i in sorted(tool_call_accum.keys())]}
                    tool_call_accum = {}
            except (json.JSONDecodeError, IndexError, KeyError):
                continue

        if tool_call_accum:
            emitted_tool_calls = True
            yield {"_tool_calls": [tool_call_accum[i] for i in sorted(tool_call_accum.keys())]}
        if not emitted_visible and not emitted_tool_calls:
            try:
                from core.shared import debug_write

                debug_write(
                    "llm_stream_empty_completion",
                    {
                        "model": req_cfg.get("model", ""),
                        "base_url": cfg.get("base_url", ""),
                        "message_count": len(messages),
                        "roles": [str(m.get("role", "")) for m in messages],
                        "tail_preview": [
                            {
                                "role": str(m.get("role", "")),
                                "content": str(m.get("content", ""))[:160],
                            }
                            for m in messages[-3:]
                        ],
                        "network_meta": response_meta,
                    },
                )
            except Exception:
                pass
            retry_result = llm_call_openai_fn(
                req_cfg,
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                tools=tools,
            )
            retry_tool_calls = retry_result.get("tool_calls") if isinstance(retry_result.get("tool_calls"), list) else None
            retry_content = str(retry_result.get("content", "") or "")
            retry_usage = retry_result.get("usage", {}) if isinstance(retry_result.get("usage"), dict) else {}
            if retry_tool_calls:
                yield {"_tool_calls": retry_tool_calls}
            if retry_content:
                yield retry_content
            yield {"_usage": retry_usage or usage}
            return
        yield {"_usage": usage}
    except Exception as exc:
        try:
            from core.shared import debug_write

            debug_write(
                "llm_stream_exception",
                {
                    "error": str(exc),
                    "type": type(exc).__name__,
                    "model": cfg.get("model", ""),
                    "base_url": cfg.get("base_url", ""),
                    "network_meta": response_meta if isinstance(locals().get("response_meta"), dict) else {},
                },
            )
        except Exception:
            pass
        return


def stream_anthropic(
    cfg: dict,
    messages: list,
    *,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    timeout: int = 25,
    tools: list | None = None,
    build_anthropic_url_fn,
    split_system_and_messages_fn,
    convert_messages_for_anthropic_tools_fn,
    convert_tools_for_anthropic_fn,
    post_llm_request_fn,
):
    url = build_anthropic_url_fn(cfg["base_url"])
    system_text, chat_msgs = split_system_and_messages_fn(messages)
    anthropic_msgs = convert_messages_for_anthropic_tools_fn(chat_msgs)
    if not anthropic_msgs:
        anthropic_msgs = [{"role": "user", "content": "."}]

    body = {
        "model": cfg["model"],
        "messages": anthropic_msgs,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if system_text:
        body["system"] = system_text
    if temperature is not None:
        body["temperature"] = temperature
    anthropic_tools = convert_tools_for_anthropic_fn(tools)
    if anthropic_tools:
        body["tools"] = anthropic_tools

    try:
        resp = post_llm_request_fn(
            url,
            headers={
                "x-api-key": cfg["api_key"],
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json=body,
            timeout=(10, 90),
            stream=True,
        )
        if resp.status_code != 200:
            return

        usage = {}
        block_types = {}
        tool_blocks = {}
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            try:
                event = json.loads(payload)
                event_type = event.get("type", "")
                if event_type == "content_block_start":
                    idx = int(event.get("index", 0) or 0)
                    block = event.get("content_block") or {}
                    block_type = str(block.get("type", "") or "")
                    block_types[idx] = block_type
                    if block_type == "thinking":
                        yield {"_thinking": True}
                    elif block_type == "tool_use":
                        tool_input = block.get("input") or {}
                        tool_blocks[idx] = {
                            "id": str(block.get("id", "") or ""),
                            "type": "function",
                            "function": {
                                "name": str(block.get("name", "") or ""),
                                "arguments": json.dumps(
                                    tool_input if isinstance(tool_input, dict) else {},
                                    ensure_ascii=False,
                                ),
                            },
                        }
                elif event_type == "content_block_delta":
                    idx = int(event.get("index", 0) or 0)
                    block_type = block_types.get(idx, "")
                    delta = event.get("delta", {})
                    delta_type = str(delta.get("type", "") or "")
                    if block_type == "thinking":
                        think_token = delta.get("thinking") or delta.get("text") or ""
                        if think_token:
                            yield {"_thinking_content": think_token}
                    if block_type == "text":
                        token = delta.get("text", "") or delta.get("partial_json", "")
                        if token:
                            yield token
                    if block_type == "tool_use" and delta_type == "input_json_delta":
                        if idx not in tool_blocks:
                            tool_blocks[idx] = {
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        tool_blocks[idx]["function"]["arguments"] += str(delta.get("partial_json", "") or "")
                elif event_type == "message_delta":
                    raw_usage = event.get("usage", {})
                    if raw_usage:
                        usage = {
                            "prompt_tokens": raw_usage.get("input_tokens", 0),
                            "completion_tokens": raw_usage.get("output_tokens", 0),
                        }
                elif event_type == "message_start":
                    msg = event.get("message", {})
                    raw_usage = msg.get("usage", {})
                    if raw_usage:
                        usage["prompt_tokens"] = raw_usage.get("input_tokens", 0)
            except (json.JSONDecodeError, KeyError):
                continue

        if tool_blocks:
            yield {"_tool_calls": [tool_blocks[i] for i in sorted(tool_blocks.keys())]}
        yield {"_usage": usage}
    except Exception as exc:
        try:
            from core.shared import debug_write

            debug_write(
                "llm_stream_exception_anthropic",
                {"error": str(exc), "type": type(exc).__name__},
            )
        except Exception:
            pass
        return
