"""Streaming LLM runtime helpers for brain."""

from __future__ import annotations

import json
import queue
import re
import threading
import time


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


def _coerce_usage_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _coerce_tool_calls(value) -> list | None:
    return value if isinstance(value, list) and value else None


def _stream_recovery_chunk_size(cfg: dict, *, default: int = 48) -> int:
    raw_value = cfg.get("stream_recovery_chunk_size")
    if raw_value in (None, ""):
        return default
    try:
        chunk_size = int(raw_value)
    except (TypeError, ValueError):
        return default
    return max(8, chunk_size)


def _stream_idle_timeout_seconds(cfg: dict, *, default: float = 90.0) -> float:
    raw_value = cfg.get("stream_idle_timeout_seconds", cfg.get("stream_idle_timeout"))
    if raw_value in (None, ""):
        return default
    try:
        idle_timeout = float(raw_value)
    except (TypeError, ValueError):
        return default
    return idle_timeout if idle_timeout > 0 else default


def _iter_lines_with_idle_watchdog(resp, *, idle_timeout_s: float):
    if idle_timeout_s <= 0:
        yield from resp.iter_lines(decode_unicode=True)
        return

    line_queue: queue.Queue = queue.Queue()
    sentinel = object()

    def _reader():
        try:
            for item in resp.iter_lines(decode_unicode=True):
                line_queue.put(("line", item))
        except BaseException as exc:  # pragma: no cover - exercised via queue handoff
            line_queue.put(("error", exc))
        finally:
            line_queue.put(("done", sentinel))

    threading.Thread(target=_reader, daemon=True).start()
    last_line_at = time.monotonic()
    while True:
        remaining = idle_timeout_s - (time.monotonic() - last_line_at)
        if remaining <= 0:
            try:
                close_fn = getattr(resp, "close", None)
                if callable(close_fn):
                    close_fn()
            except Exception:
                pass
            raise TimeoutError(f"stream idle timeout after {idle_timeout_s:.1f}s")
        try:
            kind, payload = line_queue.get(timeout=min(0.25, remaining))
        except queue.Empty:
            continue
        if kind == "line":
            last_line_at = time.monotonic()
            yield payload
            continue
        if kind == "error":
            raise payload
        return


def _debug_stream_recovery(stage: str, data: dict):
    try:
        from core.shared import debug_write

        debug_write(stage, data)
    except Exception:
        pass


def _split_stream_recovery_text(text: str, *, chunk_size: int):
    visible = str(text or "")
    if not visible:
        return []
    chunks: list[str] = []
    index = 0
    while index < len(visible):
        end = min(index + chunk_size, len(visible))
        if end < len(visible):
            preferred_end = -1
            for marker in ("\n\n", "\n", "。", "！", "？", ". ", "! ", "? ", "；", "; ", "，", ", ", " "):
                hit = visible.rfind(marker, index, end)
                if hit > index + max(6, chunk_size // 3):
                    preferred_end = max(preferred_end, hit + len(marker))
            if preferred_end > index:
                end = preferred_end
        chunks.append(visible[index:end])
        index = end
    return chunks


def _extract_status_code_from_error_text(text: str) -> int:
    match = re.search(r"\bstatus\s+(\d{3})\b", str(text or ""), re.I)
    if not match:
        return 0
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return 0


def _extract_error_payload(text: str) -> dict:
    raw = str(text or "").strip()
    if not raw:
        return {}
    json_start = raw.find("{")
    if json_start < 0:
        return {}
    try:
        payload = json.loads(raw[json_start:])
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _build_visible_provider_error_text(
    error_text: str,
    *,
    provider: str,
    status_code: int = 0,
) -> str:
    raw_text = str(error_text or "").strip()
    lowered = raw_text.lower()
    payload = _extract_error_payload(raw_text)
    error_block = payload.get("error") if isinstance(payload.get("error"), dict) else payload
    error_type = str((error_block or {}).get("type") or payload.get("type") or "").strip().lower()
    message = str((error_block or {}).get("message") or payload.get("message") or "").strip()
    http_code = status_code or _extract_status_code_from_error_text(raw_text)
    if not http_code:
        try:
            http_code = int((error_block or {}).get("http_code") or payload.get("http_code") or 0)
        except (TypeError, ValueError):
            http_code = 0

    if "insufficient_balance" in error_type or "insufficient balance" in lowered:
        return "当前模型接口余额不足，暂时无法继续。请充值后重试，或先切换到其他模型。"
    if "context window exceeds limit" in lowered or "invalid chat setting" in lowered or (
        http_code == 400 and "2013" in lowered
    ):
        return "当前模型请求失败：上下文太长，超过了该模型的限制。请重试，或切换到上下文更大的模型。"
    if any(
        token in lowered
        for token in (
            "proxyerror",
            "connection refused",
            "cannot connect to proxy",
            "failed to establish a new connection",
            "read timed out",
            "connect timeout",
            "timed out",
        )
    ):
        return "当前模型连接失败，请检查网络或代理设置后重试。"
    if http_code == 429:
        return "当前模型请求过于频繁，或该账户额度已不足。请稍后重试，或先切换到其他模型。"
    if http_code in (401, 403):
        return "当前模型鉴权失败，请检查 API Key 或权限配置。"
    if http_code == 400:
        if message:
            return f"当前模型请求失败：{message}"
        return "当前模型请求参数无效，暂时无法继续。请检查模型配置后重试。"
    if message and message.lower() != "unknown error":
        return f"当前模型请求失败：{message}"
    if http_code:
        provider_name = "模型接口" if provider == "openai" else f"{provider} 接口"
        return f"当前{provider_name}请求失败（HTTP {http_code}）。请稍后重试，或切换到其他模型。"
    return ""


def _yield_stream_recovery_from_blocking_call(
    *,
    cfg: dict,
    messages: list,
    temperature: float,
    max_tokens: int,
    timeout: int,
    tools: list | None,
    llm_call_fn,
    usage: dict,
    emitted_visible: bool,
    emitted_tool_calls: bool,
    reset_reason: str,
    provider: str,
    debug_payload: dict | None = None,
):
    if emitted_tool_calls or llm_call_fn is None:
        return False

    payload = {
        "provider": provider,
        "model": cfg.get("model", ""),
        "base_url": cfg.get("base_url", ""),
        "reset_reason": reset_reason,
        "emitted_visible": emitted_visible,
        "emitted_tool_calls": emitted_tool_calls,
    }
    if isinstance(debug_payload, dict):
        payload.update(debug_payload)
    _debug_stream_recovery("llm_stream_fallback_start", payload)

    retry_result = llm_call_fn(
        cfg,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        tools=tools,
    )
    retry_content = ""
    retry_usage = {}
    retry_tool_calls = None
    retry_error = ""
    retry_chunks = []
    if isinstance(retry_result, dict):
        retry_content = str(retry_result.get("content", "") or "")
        retry_usage = _coerce_usage_dict(retry_result.get("usage"))
        retry_tool_calls = _coerce_tool_calls(retry_result.get("tool_calls"))
        retry_error = str(retry_result.get("error", "") or "")
        retry_chunks = _split_stream_recovery_text(
            retry_content,
            chunk_size=_stream_recovery_chunk_size(cfg),
        )

    if not retry_chunks and not retry_tool_calls:
        fallback_error_text = _build_visible_provider_error_text(
            retry_error,
            provider=provider,
            status_code=int((payload.get("status") or 0) if isinstance(payload, dict) else 0),
        )
        if fallback_error_text:
            retry_chunks = _split_stream_recovery_text(
                fallback_error_text,
                chunk_size=_stream_recovery_chunk_size(cfg),
            )
        else:
            _debug_stream_recovery(
                "llm_stream_fallback_empty",
                {
                    **payload,
                    "error": retry_error,
                },
            )
            return False

    if emitted_visible:
        yield {
            "_stream_reset": {
                "reason": reset_reason,
            }
        }
    if retry_tool_calls:
        yield {"_tool_calls": retry_tool_calls}
    for chunk in retry_chunks:
        yield chunk
    yield {"_usage": retry_usage or usage}
    _debug_stream_recovery(
        "llm_stream_fallback_success",
        {
            **payload,
            "fallback_content_len": len(retry_content),
            "fallback_error_visible": bool(retry_chunks and not retry_content and not retry_tool_calls),
            "fallback_tool_calls": len(retry_tool_calls or []),
            "streamed_chunk_count": len(retry_chunks),
        },
    )
    return True


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
    response_meta = {}
    emitted_visible = False
    emitted_tool_calls = False
    usage = {}
    req_cfg = cfg
    try:
        messages = normalize_openai_messages_fn(messages)
        base_url = build_openai_base_url_fn(cfg.get("base_url", ""), cfg)
        reasoning_buffers = {}
        content_buffer = ""
        idle_timeout_s = _stream_idle_timeout_seconds(cfg)

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

        resp = send(req_cfg)
        response_meta = extract_network_meta_fn(resp)
        if resp.status_code != 200:
            retry_cfg = with_minimax_fallback_cfg_fn(cfg, getattr(resp, "text", ""), resp.status_code)
            if retry_cfg:
                req_cfg = retry_cfg
                resp = send(req_cfg)
                response_meta = extract_network_meta_fn(resp)
        if resp.status_code != 200:
            recovered = yield from _yield_stream_recovery_from_blocking_call(
                cfg=req_cfg,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                tools=tools,
                llm_call_fn=llm_call_openai_fn,
                usage=usage,
                emitted_visible=emitted_visible,
                emitted_tool_calls=emitted_tool_calls,
                reset_reason="stream_http_error_fallback",
                provider="openai",
                debug_payload={
                    "status": resp.status_code,
                    "body_preview": str(getattr(resp, "text", "") or "")[:200],
                    "network_meta": response_meta,
                },
            )
            if recovered:
                return
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

        tool_call_accum = {}
        saw_done = False
        for line in _iter_lines_with_idle_watchdog(resp, idle_timeout_s=idle_timeout_s):
            if not line:
                continue
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                saw_done = True
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
            tool_call_accum = {}

        if not saw_done and not emitted_tool_calls:
            recovered = yield from _yield_stream_recovery_from_blocking_call(
                cfg=req_cfg,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                tools=tools,
                llm_call_fn=llm_call_openai_fn,
                usage=usage,
                emitted_visible=emitted_visible,
                emitted_tool_calls=emitted_tool_calls,
                reset_reason="stream_incomplete_fallback",
                provider="openai",
                debug_payload={"network_meta": response_meta},
            )
            if recovered:
                return

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
            recovered = yield from _yield_stream_recovery_from_blocking_call(
                cfg=req_cfg,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                tools=tools,
                llm_call_fn=llm_call_openai_fn,
                usage=usage,
                emitted_visible=emitted_visible,
                emitted_tool_calls=emitted_tool_calls,
                reset_reason="stream_empty_completion_fallback",
                provider="openai",
                debug_payload={"network_meta": response_meta},
            )
            if recovered:
                return
        yield {"_usage": usage}
    except Exception as exc:
        pending_tool_calls = locals().get("tool_call_accum")
        if isinstance(pending_tool_calls, dict) and pending_tool_calls and not emitted_tool_calls:
            yield {"_tool_calls": [pending_tool_calls[i] for i in sorted(pending_tool_calls.keys())]}
            return
        recovered = yield from _yield_stream_recovery_from_blocking_call(
            cfg=req_cfg,
            messages=messages if isinstance(locals().get("messages"), list) else messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            tools=tools,
            llm_call_fn=llm_call_openai_fn,
            usage=usage,
            emitted_visible=emitted_visible,
            emitted_tool_calls=emitted_tool_calls,
            reset_reason="stream_exception_fallback",
            provider="openai",
            debug_payload={
                "error": str(exc),
                "type": type(exc).__name__,
                "network_meta": response_meta if isinstance(response_meta, dict) else {},
            },
        )
        if recovered:
            return
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
    llm_call_anthropic_fn,
    extract_network_meta_fn,
):
    response_meta = {}
    emitted_visible = False
    emitted_tool_calls = False
    usage = {}
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
        idle_timeout_s = _stream_idle_timeout_seconds(cfg)
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
        response_meta = extract_network_meta_fn(resp)
        if resp.status_code != 200:
            recovered = yield from _yield_stream_recovery_from_blocking_call(
                cfg=cfg,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                tools=tools,
                llm_call_fn=llm_call_anthropic_fn,
                usage=usage,
                emitted_visible=emitted_visible,
                emitted_tool_calls=emitted_tool_calls,
                reset_reason="stream_http_error_fallback",
                provider="anthropic",
                debug_payload={
                    "status": resp.status_code,
                    "body_preview": str(getattr(resp, "text", "") or "")[:200],
                    "network_meta": response_meta,
                },
            )
            if recovered:
                return
            return

        block_types = {}
        tool_blocks = {}
        saw_message_stop = False
        for line in _iter_lines_with_idle_watchdog(resp, idle_timeout_s=idle_timeout_s):
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
                            emitted_visible = True
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
                elif event_type == "message_stop":
                    saw_message_stop = True
            except (json.JSONDecodeError, KeyError):
                continue

        if tool_blocks:
            emitted_tool_calls = True
            yield {"_tool_calls": [tool_blocks[i] for i in sorted(tool_blocks.keys())]}
            tool_blocks = {}

        if not saw_message_stop and not emitted_tool_calls:
            recovered = yield from _yield_stream_recovery_from_blocking_call(
                cfg=cfg,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                tools=tools,
                llm_call_fn=llm_call_anthropic_fn,
                usage=usage,
                emitted_visible=emitted_visible,
                emitted_tool_calls=emitted_tool_calls,
                reset_reason="stream_incomplete_fallback",
                provider="anthropic",
                debug_payload={"network_meta": response_meta},
            )
            if recovered:
                return

        if not emitted_visible and not emitted_tool_calls:
            recovered = yield from _yield_stream_recovery_from_blocking_call(
                cfg=cfg,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                tools=tools,
                llm_call_fn=llm_call_anthropic_fn,
                usage=usage,
                emitted_visible=emitted_visible,
                emitted_tool_calls=emitted_tool_calls,
                reset_reason="stream_empty_completion_fallback",
                provider="anthropic",
                debug_payload={"network_meta": response_meta},
            )
            if recovered:
                return
        yield {"_usage": usage}
    except Exception as exc:
        pending_tool_blocks = locals().get("tool_blocks")
        if isinstance(pending_tool_blocks, dict) and pending_tool_blocks and not emitted_tool_calls:
            yield {"_tool_calls": [pending_tool_blocks[i] for i in sorted(pending_tool_blocks.keys())]}
            return
        recovered = yield from _yield_stream_recovery_from_blocking_call(
            cfg=cfg,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            tools=tools,
            llm_call_fn=llm_call_anthropic_fn,
            usage=usage,
            emitted_visible=emitted_visible,
            emitted_tool_calls=emitted_tool_calls,
            reset_reason="stream_exception_fallback",
            provider="anthropic",
            debug_payload={
                "error": str(exc),
                "type": type(exc).__name__,
                "network_meta": response_meta,
            },
        )
        if recovered:
            return
        try:
            from core.shared import debug_write

            debug_write(
                "llm_stream_exception_anthropic",
                {"error": str(exc), "type": type(exc).__name__},
            )
        except Exception:
            pass
        return
