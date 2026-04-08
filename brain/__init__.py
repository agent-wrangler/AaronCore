# Brain - 统一 LLM 调用层
# NOTE: 下方旧注释有历史残留；当前实际边界以本次收口为准，think/think_stream 不再负责 persona 注入或本地人格回复。
#
# ⚠️ 重要说明：
# 此文件主要负责 LLM 调用（llm_call、think、think_stream）和人格表达（think 函数中的 persona 处理）。
#
# 当前 AaronCore 的主流程不是在这里！
# 当前主流程是 LLM/tool_call 主导，详见：
#   docs/10-架构-architecture/NovaCore_当前真实流程文档.md
#
# 关键结论：
# - 当前默认预装：L1（对话历史）+ L4（人格图谱）+ session_context（L2轻量会话态）+ 少量L7
# - L2 持久记忆在 CoD 下默认按需拉取，不全量预装
# - dialogue_context 只做增量提示，不重复历史摘要
# - 当前主链是 tool_call 模式，LLM 自主决策是否调用工具
#
import json
import re
import os
from core.network_protocol import post_with_network_strategy as _post_with_network_strategy
from storage.paths import PERSONA_FILE as _PERSONA_FILE
from . import chat_runtime as _chat_runtime
from . import config_runtime as _config_runtime
from . import message_transforms as _message_transforms
from . import local_learning as _local_learning
from . import model_runtime as _model_runtime
from . import codex_cli_runtime as _codex_cli_runtime
from . import provider_runtime as _provider_runtime
from . import stream_runtime as _stream_runtime
from . import think_helpers as _think_helpers


def _extract_network_meta(resp) -> dict:
    return _provider_runtime.extract_network_meta(resp)


def _post_llm_request(url: str, **kwargs):
    return _post_with_network_strategy(url, **kwargs)

def _debug_proxy_fallback(stage: str, data: dict):
    return _provider_runtime.debug_proxy_fallback(stage, data)


def _env_proxy_values() -> dict:
    return _provider_runtime.env_proxy_values()


def _has_local_proxy_env() -> bool:
    return _provider_runtime.has_local_proxy_env()


def _should_retry_without_env(exc: Exception) -> bool:
    return _provider_runtime.should_retry_without_env(exc)


def _post_with_proxy_fallback(url: str, **kwargs):
    return _provider_runtime.post_with_proxy_fallback(url, **kwargs)


config_path = _config_runtime.config_path
_raw_config = _config_runtime.raw_config
MODELS_CONFIG = _config_runtime.models_config
_current_default = _config_runtime.current_default

# 兼容旧代码：LLM_CONFIG 指向当前默认模型
LLM_CONFIG = _config_runtime.llm_config
DEFAULT_ASSISTANT_SYSTEM_PROMPT = _config_runtime.DEFAULT_ASSISTANT_SYSTEM_PROMPT
DEFAULT_CHAT_STYLE_PROMPT = _config_runtime.DEFAULT_CHAT_STYLE_PROMPT


# ── 统一 LLM 调用层：MiniMax / DeepSeek 等优先走 OpenAI 兼容 tool_call；Anthropic 系模型走 Anthropic ──

_think_helpers.set_default_prompts(DEFAULT_ASSISTANT_SYSTEM_PROMPT, DEFAULT_CHAT_STYLE_PROMPT)


def _is_minimax_provider(cfg: dict) -> bool:
    return _provider_runtime.is_minimax_provider(cfg)


def _is_anthropic_provider(cfg: dict) -> bool:
    return _provider_runtime.is_anthropic_provider(cfg)


def _is_codex_cli_provider(cfg: dict) -> bool:
    return _provider_runtime.is_codex_cli_provider(cfg)


def validate_codex_cli_login(*, timeout: int = 10) -> tuple[bool, str]:
    return _provider_runtime.validate_codex_cli_login(timeout=timeout)


def _build_openai_base_url(base_url: str, cfg: dict | None = None) -> str:
    return _provider_runtime.build_openai_base_url(base_url, cfg)


def _minimax_toolcall_fallback_model(model_name: str) -> str:
    return _provider_runtime.minimax_toolcall_fallback_model(model_name)


def _is_minimax_invalid_chat_setting(status_code: int, body_text: str, cfg: dict) -> bool:
    return _provider_runtime.is_minimax_invalid_chat_setting(status_code, body_text, cfg)


def _is_minimax_server_tool_error(status_code: int, body_text: str, cfg: dict) -> bool:
    return _provider_runtime.is_minimax_server_tool_error(status_code, body_text, cfg)


def _with_minimax_fallback_cfg(cfg: dict, body_text: str, status_code: int) -> dict | None:
    return _provider_runtime.with_minimax_fallback_cfg(cfg, body_text, status_code)


def _build_openai_extra_body(cfg: dict) -> dict | None:
    return _provider_runtime.build_openai_extra_body(cfg)


def _build_anthropic_url(base_url: str) -> str:
    return _provider_runtime.build_anthropic_url(base_url)


def _split_system_and_messages(messages: list) -> tuple:
    return _message_transforms.split_system_and_messages(messages)


def _normalize_openai_messages(messages: list) -> list:
    return _message_transforms.normalize_openai_messages(messages)


def _normalize_reasoning_details(value) -> list[dict]:
    return _message_transforms.normalize_reasoning_details(value)


def _convert_messages_for_anthropic(messages: list) -> list:
    return _message_transforms.convert_messages_for_anthropic(messages)


def _convert_messages_for_anthropic_tools(messages: list) -> list:
    return _message_transforms.convert_messages_for_anthropic_tools(messages)


def _convert_tools_for_anthropic(tools: list | None) -> list | None:
    return _message_transforms.convert_tools_for_anthropic(tools)


def _anthropic_blocks_to_tool_calls(content_blocks: list) -> list:
    return _message_transforms.anthropic_blocks_to_tool_calls(content_blocks)


def llm_call(cfg: dict, messages: list, *, temperature: float = 0.7,
             max_tokens: int = 2000, timeout: int = 25,
             tools: list | None = None) -> dict:
    """统一 LLM 调用，返回 {"content": str, "usage": dict, "tool_calls": list|None}"""
    if _is_codex_cli_provider(cfg):
        return _llm_call_codex_cli(cfg, messages, temperature=temperature,
                                   max_tokens=max_tokens, timeout=timeout,
                                   tools=tools)
    if _is_anthropic_provider(cfg):
        return _llm_call_anthropic(cfg, messages, temperature=temperature,
                                   max_tokens=max_tokens, timeout=timeout,
                                   tools=tools)
        # Anthropic 不支持 tools 参数，忽略
        return _llm_call_anthropic(cfg, messages, temperature=temperature,
                                   max_tokens=max_tokens, timeout=timeout)
    return _llm_call_openai(cfg, messages, temperature=temperature,
                            max_tokens=max_tokens, timeout=timeout,
                            tools=tools)


def _llm_call_codex_cli(cfg: dict, messages: list, *, temperature: float = 0.7,
                        max_tokens: int = 2000, timeout: int = 25,
                        tools: list | None = None) -> dict:
    return _codex_cli_runtime.codex_cli_call(
        cfg,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        tools=tools,
    )


def _llm_stream_codex_cli(cfg: dict, messages: list, *, temperature: float = 0.7,
                          max_tokens: int = 2000, timeout: int = 25,
                          tools: list | None = None):
    yield from _codex_cli_runtime.codex_cli_call_stream(
        cfg,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        tools=tools,
    )


def _llm_call_openai(cfg: dict, messages: list, *, temperature: float = 0.7,
                     max_tokens: int = 2000, timeout: int = 25,
                     tools: list | None = None) -> dict:
    """OpenAI 兼容格式调用"""
    try:
        messages = _normalize_openai_messages(messages)
        base_url = _build_openai_base_url(cfg.get("base_url", ""), cfg)
        def _send(req_cfg: dict):
            body = {"model": req_cfg["model"], "messages": messages,
                    "temperature": temperature, "max_tokens": max_tokens}
            extra_body = _build_openai_extra_body(req_cfg)
            if extra_body:
                body.update(extra_body)
            if tools:
                body["tools"] = tools
            return _post_llm_request(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {req_cfg['api_key']}",
                         "Content-Type": "application/json"},
                json=body,
                timeout=timeout,
            )

        resp = _send(cfg)
        if resp.status_code != 200:
            retry_cfg = _with_minimax_fallback_cfg(cfg, getattr(resp, "text", ""), resp.status_code)
            if retry_cfg:
                resp = _send(retry_cfg)
        if resp.status_code != 200:
            return {"content": "", "usage": {}, "error": f"status {resp.status_code}: {resp.text[:200]}"}
        data = resp.json()
        msg = data.get("choices", [{}])[0].get("message", {})
        content = msg.get("content", "") or ""
        usage = data.get("usage", {})
        # 解析 tool_calls
        tool_calls = msg.get("tool_calls")
        reasoning_details = _normalize_reasoning_details(msg.get("reasoning_details"))
        result = {"content": content, "usage": usage}
        if tool_calls:
            result["tool_calls"] = tool_calls
        if reasoning_details:
            result["reasoning_details"] = reasoning_details
        return result
    except Exception as e:
        return {"content": "", "usage": {}, "error": str(e)}


def _llm_call_anthropic(cfg: dict, messages: list, *, temperature: float = 0.7,
                        max_tokens: int = 2000, timeout: int = 25,
                        tools: list | None = None) -> dict:
    """Anthropic 兼容格式调用"""
    url = _build_anthropic_url(cfg["base_url"])
    system_text, chat_msgs = _split_system_and_messages(messages)
    anthropic_msgs = _convert_messages_for_anthropic_tools(chat_msgs)

    if not anthropic_msgs:
        anthropic_msgs = [{"role": "user", "content": "."}]

    body = {
        "model": cfg["model"],
        "messages": anthropic_msgs,
        "max_tokens": max_tokens,
    }
    if system_text:
        body["system"] = system_text
    if temperature is not None:
        body["temperature"] = temperature
    anthropic_tools = _convert_tools_for_anthropic(tools)
    if anthropic_tools:
        body["tools"] = anthropic_tools

    try:
        resp = _post_llm_request(
            url,
            headers={"x-api-key": cfg["api_key"],
                     "Content-Type": "application/json",
                     "anthropic-version": "2023-06-01"},
            json=body,
            timeout=timeout,
        )
        if resp.status_code != 200:
            return {"content": "", "usage": {}, "error": f"status {resp.status_code}: {resp.text[:200]}"}
        data = resp.json()
        # Anthropic 响应格式：{"content": [{"type": "text", "text": "..."}], "usage": {...}}
        content_blocks = data.get("content", [])
        content = ""
        for block in content_blocks:
            if block.get("type") == "text":
                content += block.get("text", "")
        tool_calls = _anthropic_blocks_to_tool_calls(content_blocks)
        # 统一 usage 字段名（Anthropic 用 input_tokens/output_tokens）
        raw_usage = data.get("usage", {})
        usage = {
            "prompt_tokens": raw_usage.get("input_tokens", 0),
            "completion_tokens": raw_usage.get("output_tokens", 0),
            "prompt_cache_hit_tokens": raw_usage.get("cache_read_input_tokens", 0),
            "prompt_cache_miss_tokens": raw_usage.get("cache_creation_input_tokens", 0),
        }
        result = {"content": content, "usage": usage}
        if tool_calls:
            result["tool_calls"] = tool_calls
        return result
    except Exception as e:
        return {"content": "", "usage": {}, "error": str(e)}


def llm_call_stream(cfg: dict, messages: list, *, temperature: float = 0.7,
                    max_tokens: int = 2000, timeout: int = 25,
                    tools: list | None = None):
    """流式 LLM 调用，yield 每个 delta token (str)。结束后 yield 一个 dict 表示 usage。
    如果 LLM 返回 tool_calls，yield {"_tool_calls": [...]} 信号。"""
    if _is_codex_cli_provider(cfg):
        yield from _llm_stream_codex_cli(
            cfg,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            tools=tools,
        )
        return
    yield from _stream_runtime.llm_call_stream(
        cfg,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        tools=tools,
        is_anthropic_provider_fn=_is_anthropic_provider,
        stream_anthropic_fn=_llm_stream_anthropic,
        stream_openai_fn=_llm_stream_openai,
    )


def _llm_stream_openai(cfg: dict, messages: list, *, temperature: float = 0.7,
                       max_tokens: int = 2000, timeout: int = 25,
                       tools: list | None = None):
    yield from _stream_runtime.stream_openai(
        cfg,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        tools=tools,
        normalize_openai_messages_fn=_normalize_openai_messages,
        build_openai_base_url_fn=_build_openai_base_url,
        build_openai_extra_body_fn=_build_openai_extra_body,
        post_llm_request_fn=_post_llm_request,
        extract_network_meta_fn=_extract_network_meta,
        with_minimax_fallback_cfg_fn=_with_minimax_fallback_cfg,
        is_minimax_provider_fn=_is_minimax_provider,
        normalize_reasoning_details_fn=_normalize_reasoning_details,
        llm_call_openai_fn=_llm_call_openai,
    )
    return
    """OpenAI 兼容流式调用"""
    try:
        messages = _normalize_openai_messages(messages)
        base_url = _build_openai_base_url(cfg.get("base_url", ""), cfg)
        emitted_visible = False
        emitted_tool_calls = False
        response_meta = {}
        _reasoning_buffers = {}
        _content_buffer = ""

        def _extract_reasoning_text(delta: dict) -> str:
            if not isinstance(delta, dict):
                return ""
            parts = []
            reasoning_details = _normalize_reasoning_details(delta.get("reasoning_details"))
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
                            txt = item.get("text") or item.get("content") or item.get("thinking") or item.get("reasoning")
                            if isinstance(txt, str) and txt.strip():
                                parts.append(txt)
                elif isinstance(value, dict):
                    txt = value.get("text") or value.get("content")
                    if isinstance(txt, str) and txt.strip():
                        parts.append(txt)
            return "".join(parts)

        def _consume_reasoning_delta(delta: dict) -> str:
            details = _normalize_reasoning_details(delta.get("reasoning_details"))
            if not details:
                return _extract_reasoning_text(delta)
            parts = []
            for idx, item in enumerate(details):
                text = str(item.get("text") or "")
                if not text:
                    continue
                prev = str(_reasoning_buffers.get(idx) or "")
                if text.startswith(prev):
                    new_text = text[len(prev):]
                elif prev.startswith(text):
                    new_text = ""
                else:
                    new_text = text
                _reasoning_buffers[idx] = text
                if new_text:
                    parts.append(new_text)
            return "".join(parts)

        def _consume_content_delta(delta: dict, *, provider_cfg: dict) -> str:
            nonlocal _content_buffer
            token = str(delta.get("content", "") or "")
            if not token:
                return ""
            if not _is_minimax_provider(provider_cfg):
                return token
            prev = _content_buffer
            if token.startswith(prev):
                new_text = token[len(prev):]
            elif prev.startswith(token):
                new_text = ""
            else:
                new_text = token
            _content_buffer = token
            return new_text

        def _send(req_cfg: dict):
            body = {"model": req_cfg["model"], "messages": messages,
                    "temperature": temperature, "max_tokens": max_tokens,
                    "stream": True}
            extra_body = _build_openai_extra_body(req_cfg)
            if extra_body:
                body.update(extra_body)
            if tools:
                body["tools"] = tools
            return _post_llm_request(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {req_cfg['api_key']}",
                         "Content-Type": "application/json"},
                json=body,
                timeout=(10, 90),
                stream=True,
            )
        # timeout=(connect, read): connect 10s, read 90s (思考模型可能长时间不出 token)
        req_cfg = cfg
        resp = _send(req_cfg)
        response_meta = _extract_network_meta(resp)
        if resp.status_code != 200:
            retry_cfg = _with_minimax_fallback_cfg(cfg, getattr(resp, "text", ""), resp.status_code)
            if retry_cfg:
                req_cfg = retry_cfg
                resp = _send(req_cfg)
                response_meta = _extract_network_meta(resp)
        if resp.status_code != 200:
            try:
                from core.shared import debug_write
                debug_write("llm_stream_error", {
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
                })
            except Exception:
                pass
            return
        usage = {}
        # 累积 tool_calls chunks
        _tc_accum = {}  # index -> {"id", "type", "function": {"name", "arguments"}}
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
                reasoning_text = _consume_reasoning_delta(delta)
                if reasoning_text:
                    yield {"_thinking_content": reasoning_text}
                token = _consume_content_delta(delta, provider_cfg=req_cfg)
                if token:
                    emitted_visible = True
                    yield token
                # 累积 tool_calls delta
                tc_deltas = delta.get("tool_calls")
                if tc_deltas:
                    for tc_d in tc_deltas:
                        idx = tc_d.get("index", 0)
                        if idx not in _tc_accum:
                            _tc_accum[idx] = {
                                "id": tc_d.get("id", ""),
                                "type": tc_d.get("type", "function"),
                                "function": {"name": "", "arguments": ""},
                            }
                        if tc_d.get("id"):
                            _tc_accum[idx]["id"] = tc_d["id"]
                        fn = tc_d.get("function") or {}
                        if fn.get("name"):
                            _tc_accum[idx]["function"]["name"] += fn["name"]
                        if fn.get("arguments"):
                            _tc_accum[idx]["function"]["arguments"] += fn["arguments"]
                # 部分 API 在最后一个 chunk 返回 usage
                if chunk.get("usage"):
                    usage = chunk["usage"]
                # finish_reason == "tool_calls" 表示 LLM 选择了工具调用
                if finish_reason == "tool_calls" and _tc_accum:
                    tc_list = [_tc_accum[i] for i in sorted(_tc_accum.keys())]
                    emitted_tool_calls = True
                    yield {"_tool_calls": tc_list}
                    _tc_accum = {}
            except (json.JSONDecodeError, IndexError, KeyError):
                continue
        # 如果没有通过 finish_reason 触发但有累积的 tool_calls，也 yield 出来
        if _tc_accum:
            tc_list = [_tc_accum[i] for i in sorted(_tc_accum.keys())]
            emitted_tool_calls = True
            yield {"_tool_calls": tc_list}
        if not emitted_visible and not emitted_tool_calls:
            try:
                from core.shared import debug_write
                debug_write("llm_stream_empty_completion", {
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
                })
            except Exception:
                pass
            retry_result = _llm_call_openai(
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
    except Exception as _e:
        try:
            from core.shared import debug_write
            debug_write("llm_stream_exception", {
                "error": str(_e),
                "type": type(_e).__name__,
                "model": cfg.get("model", ""),
                "base_url": cfg.get("base_url", ""),
                "network_meta": response_meta if isinstance(locals().get("response_meta"), dict) else {},
            })
        except Exception:
            pass
        return


def _llm_stream_anthropic(cfg: dict, messages: list, *, temperature: float = 0.7,
                          max_tokens: int = 2000, timeout: int = 25,
                          tools: list | None = None):
    yield from _stream_runtime.stream_anthropic(
        cfg,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        tools=tools,
        build_anthropic_url_fn=_build_anthropic_url,
        split_system_and_messages_fn=_split_system_and_messages,
        convert_messages_for_anthropic_tools_fn=_convert_messages_for_anthropic_tools,
        convert_tools_for_anthropic_fn=_convert_tools_for_anthropic,
        post_llm_request_fn=_post_llm_request,
        llm_call_anthropic_fn=_llm_call_anthropic,
        extract_network_meta_fn=_extract_network_meta,
    )
    return
    """Anthropic 流式调用"""
    url = _build_anthropic_url(cfg["base_url"])
    system_text, chat_msgs = _split_system_and_messages(messages)
    anthropic_msgs = _convert_messages_for_anthropic_tools(chat_msgs)
    if not anthropic_msgs:
        anthropic_msgs = [{"role": "user", "content": "."}]
    body = {"model": cfg["model"], "messages": anthropic_msgs,
            "max_tokens": max_tokens, "stream": True}
    if system_text:
        body["system"] = system_text
    if temperature is not None:
        body["temperature"] = temperature
    anthropic_tools = _convert_tools_for_anthropic(tools)
    if anthropic_tools:
        body["tools"] = anthropic_tools
    try:
        resp = _post_llm_request(
            url,
            headers={"x-api-key": cfg["api_key"],
                     "Content-Type": "application/json",
                     "anthropic-version": "2023-06-01"},
            json=body,
            timeout=(10, 90),
            stream=True,
        )
        if resp.status_code != 200:
            return
        usage = {}
        _block_types = {}
        _tool_blocks = {}
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            try:
                event = json.loads(payload)
                etype = event.get("type", "")
                if etype == "content_block_start":
                    idx = int(event.get("index", 0) or 0)
                    block = event.get("content_block") or {}
                    block_type = str(block.get("type", "") or "")
                    _block_types[idx] = block_type
                    if block_type == "thinking":
                        yield {"_thinking": True}
                    elif block_type == "tool_use":
                        tool_input = block.get("input") or {}
                        _tool_blocks[idx] = {
                            "id": str(block.get("id", "") or ""),
                            "type": "function",
                            "function": {
                                "name": str(block.get("name", "") or ""),
                                "arguments": json.dumps(tool_input if isinstance(tool_input, dict) else {}, ensure_ascii=False),
                            },
                        }
                elif etype == "content_block_delta":
                    idx = int(event.get("index", 0) or 0)
                    block_type = _block_types.get(idx, "")
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
                        if idx not in _tool_blocks:
                            _tool_blocks[idx] = {
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        _tool_blocks[idx]["function"]["arguments"] += str(delta.get("partial_json", "") or "")
                elif etype == "content_block_stop":
                    pass
                elif etype == "message_delta":
                    raw_usage = event.get("usage", {})
                    if raw_usage:
                        usage = {
                            "prompt_tokens": raw_usage.get("input_tokens", 0),
                            "completion_tokens": raw_usage.get("output_tokens", 0),
                        }
                elif etype == "message_start":
                    msg = event.get("message", {})
                    raw_usage = msg.get("usage", {})
                    if raw_usage:
                        usage["prompt_tokens"] = raw_usage.get("input_tokens", 0)
            except (json.JSONDecodeError, KeyError):
                continue
        if _tool_blocks:
            yield {"_tool_calls": [_tool_blocks[i] for i in sorted(_tool_blocks.keys())]}
        yield {"_usage": usage}
    except Exception as _e:
        try:
            from core.shared import debug_write
            debug_write("llm_stream_exception_anthropic", {"error": str(_e), "type": type(_e).__name__})
        except Exception:
            pass
        return


def get_models() -> dict:
    return _model_runtime.get_models(MODELS_CONFIG, _current_default)


def get_current_model_name() -> str:
    return _model_runtime.get_current_model_name(LLM_CONFIG, _current_default)


def set_default_model(model_id: str) -> bool:
    global _current_default, LLM_CONFIG
    ok, new_default, new_cfg = _model_runtime.set_default_model(
        model_id,
        models_config=MODELS_CONFIG,
        raw_config=_raw_config,
        config_path=config_path,
    )
    if not ok:
        return False
    _current_default = new_default
    LLM_CONFIG = new_cfg
    _config_runtime.current_default = new_default
    _config_runtime.llm_config = new_cfg
    return True


def understand_intent(user_input: str) -> dict:
    return _model_runtime.understand_intent(user_input, llm_config=LLM_CONFIG, llm_call_fn=llm_call)


def _raw_llm(prompt: str, temperature=0.1, max_tokens=150, timeout=10) -> str:
    return _model_runtime.raw_llm(
        prompt,
        llm_config=LLM_CONFIG,
        llm_call_fn=llm_call,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def vision_llm_call(prompt: str, images: list = None) -> str:
    return _model_runtime.vision_llm_call(
        prompt,
        images=images,
        llm_config=LLM_CONFIG,
        models_config=MODELS_CONFIG,
        llm_call_openai_fn=_llm_call_openai,
    )


def _extract_skill_result(prompt: str) -> str:
    return _think_helpers._extract_skill_result(prompt)


def _detect_mode(prompt: str, context: str = '') -> str:
    return _think_helpers._detect_mode(prompt, context)


def _clean_llm_reply(text: str) -> str:
    return _think_helpers._clean_llm_reply(text)


def _detect_emotion(reply: str) -> str:
    return _think_helpers._detect_emotion(reply)


def _looks_bad_reply(text: str) -> tuple[bool, str]:
    return _think_helpers._looks_bad_reply(text)


def _explicit_chat_error_reply(use_cfg: dict, reason: str, detail: str = '') -> str:
    return _think_helpers._explicit_chat_error_reply(use_cfg, reason, detail)


def _build_think_prompts(prompt: str, context: str, mode: str) -> tuple[str, str]:
    return _think_helpers._build_think_prompts(prompt, context, mode)


def _split_formatted_prompt(prompt: str) -> tuple:
    return _think_helpers._split_formatted_prompt(prompt)


def think(prompt: str, context: str = "", image: str = None, model_id: str = None, images: list = None) -> dict:
    return _chat_runtime.think(
        prompt,
        context=context,
        image=image,
        model_id=model_id,
        images=images,
        llm_config=LLM_CONFIG,
        models_config=MODELS_CONFIG,
        detect_mode_fn=_detect_mode,
        build_think_prompts_fn=_build_think_prompts,
        llm_call_fn=llm_call,
        llm_call_openai_fn=_llm_call_openai,
        clean_llm_reply_fn=_clean_llm_reply,
        looks_bad_reply_fn=_looks_bad_reply,
        explicit_chat_error_reply_fn=_explicit_chat_error_reply,
        detect_emotion_fn=_detect_emotion,
    )

def think_stream(prompt: str, context: str = "", image: str = None, model_id: str = None, images: list = None):
    yield from _chat_runtime.think_stream(
        prompt,
        context=context,
        image=image,
        model_id=model_id,
        images=images,
        llm_config=LLM_CONFIG,
        models_config=MODELS_CONFIG,
        detect_mode_fn=_detect_mode,
        build_think_prompts_fn=_build_think_prompts,
        think_fn=think,
        llm_call_stream_fn=llm_call_stream,
    )




def _sync_name_in_persona(persona: dict, new_name: str):
    ai = persona.get('ai_profile')
    if isinstance(ai, dict):
        ai['identity'] = f'\u6211\u662f{new_name}\uff0c\u662f\u4e3b\u4eba\u7684\u672c\u5730\u667a\u80fd\u52a9\u624b\uff0c\u4e0d\u662f\u666e\u901a\u5ba2\u670d\u578bAI\u3002'
    rel = persona.get('relationship_profile')
    if isinstance(rel, dict):
        rel['relationship'] = f'{new_name}\u548c\u4e3b\u4eba\u662f\u4eb2\u8fd1\u3001\u957f\u671f\u76f8\u5904\u7684\u5173\u7cfb\u3002'
        rel['goal'] = f'\u8ba9\u4e3b\u4eba\u611f\u89c9\u662f\u5728\u548c\u719f\u6089\u7684{new_name}\u5bf9\u8bdd\uff0c\u800c\u4e0d\u662f\u5728\u5bf9\u7740\u4e00\u5957\u6a21\u677f\u7cfb\u7edf\u3002'


