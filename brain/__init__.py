# Brain - LLM 调用层 + 人格表达层
#
# ⚠️ 重要说明：
# 此文件主要负责 LLM 调用（llm_call、think、think_stream）和人格表达（think 函数中的 persona 处理）。
#
# 当前 NovaCore 的主流程不是在这里！
# 当前主流程是 LLM/tool_call 主导，详见：
#   docs/10-架构-architecture/NovaCore_当前真实流程文档.md
#
# 关键结论：
# - 当前默认预装：L1（对话历史）+ L4（人格图谱）+ session_context（L2轻量会话态）+ 少量L7
# - L2 持久记忆在 CoD 下默认按需拉取，不全量预装
# - dialogue_context 只做增量提示，不重复历史摘要
# - 当前主链是 tool_call 模式，LLM 自主决策是否调用工具
#
import requests
import json
import re
import os
from core.network_protocol import post_with_network_strategy as _post_with_network_strategy


def _extract_network_meta(resp) -> dict:
    meta = getattr(resp, "_novacore_network_meta", None)
    return dict(meta) if isinstance(meta, dict) else {}


def _post_llm_request(url: str, **kwargs):
    return _post_with_network_strategy(url, **kwargs)

try:
    from core.rule_runtime import has_rule
except Exception:
    def has_rule(fix: str, scene: str = '', min_level: str = 'once') -> bool:
        return False


def _debug_proxy_fallback(stage: str, data: dict):
    try:
        from core.shared import debug_write
        debug_write(stage, data)
    except Exception:
        pass


def _env_proxy_values() -> dict:
    keys = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
    values = {}
    for key in keys:
        value = str(os.environ.get(key) or "").strip()
        if value:
            values[key] = value
    return values


def _has_local_proxy_env() -> bool:
    for value in _env_proxy_values().values():
        lowered = value.lower()
        if "127.0.0.1" in lowered or "localhost" in lowered:
            return True
    return False


def _should_retry_without_env(exc: Exception) -> bool:
    text = str(exc or "").lower()
    retry_signals = (
        "proxyerror",
        "failed to establish a new connection",
        "connection refused",
        "actively refused",
        "cannot connect to proxy",
    )
    return _has_local_proxy_env() and any(sig in text for sig in retry_signals)


_DOMESTIC_HOSTS = {"minimaxi.com", "dashscope.aliyuncs.com", "open.bigmodel.cn", "api.volcengine.com"}

def _post_with_proxy_fallback(url: str, **kwargs):
    """国内 API 直连（跳过代理），国外 API 走系统代理"""
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    if any(d in host for d in _DOMESTIC_HOSTS):
        kwargs.setdefault("proxies", {"http": None, "https": None})
    return requests.request("POST", url, **kwargs)

# 加载 LLM 配置（支持多模型格式）
config_path = os.path.join(os.path.dirname(__file__), 'llm_config.json')
if os.path.exists(config_path):
    _raw_config = json.load(open(config_path, 'r', encoding='utf-8'))
else:
    parent_config = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'brain', 'llm_config.json')
    if os.path.exists(parent_config):
        _raw_config = json.load(open(parent_config, 'r', encoding='utf-8'))
    else:
        _raw_config = {
            "api_key": "",
            "model": "MiniMax-M2.7",
            "base_url": "https://api.minimaxi.com/anthropic"
        }

# 向后兼容：旧格式（无 models 字段）自动转新格式
if "models" not in _raw_config:
    _model_name = _raw_config.get("model", "deepseek-chat")
    _raw_config = {
        "models": {
            _model_name: {
                "api_key": _raw_config.get("api_key", ""),
                "base_url": _raw_config.get("base_url", ""),
                "model": _model_name,
                "vision": False,
            }
        },
        "default": _model_name,
    }

MODELS_CONFIG = _raw_config["models"]
_current_default = _raw_config.get("default", next(iter(MODELS_CONFIG)))

# 兼容旧代码：LLM_CONFIG 指向当前默认模型
LLM_CONFIG = MODELS_CONFIG.get(_current_default) or next(iter(MODELS_CONFIG.values()))


# ── 统一 LLM 调用层：MiniMax / DeepSeek 等优先走 OpenAI 兼容 tool_call；Anthropic 系模型走 Anthropic ──

def _is_minimax_provider(cfg: dict) -> bool:
    model = str(cfg.get("model", "")).lower()
    base_url = str(cfg.get("base_url", "")).lower()
    return "minimax" in model or "minimaxi.com" in base_url

def _is_anthropic_provider(cfg: dict) -> bool:
    if _is_minimax_provider(cfg):
        return False
    """判断是否应该走 Anthropic 兼容接口。MiniMax 明确走 OpenAI 兼容 tool_call。"""
    base_url = str(cfg.get("base_url", "")).lower()
    return "/anthropic" in base_url


def _build_openai_base_url(base_url: str, cfg: dict | None = None) -> str:
    """规范 OpenAI 兼容端点基地址。MiniMax 若误配到 anthropic 路径，自动改回 /v1。"""
    url = str(base_url or "").rstrip("/")
    if cfg and _is_minimax_provider(cfg):
        if url.endswith("/anthropic/v1"):
            return url[:-len("/anthropic/v1")] + "/v1"
        if url.endswith("/anthropic"):
            return url[:-len("/anthropic")] + "/v1"
        if "/anthropic/" in url:
            return url.replace("/anthropic", "", 1)
    return url


def _minimax_toolcall_fallback_model(model_name: str) -> str:
    model = str(model_name or "").strip()
    lowered = model.lower()
    if lowered == "minimax-m2.7":
        return "MiniMax-M2.5"
    if lowered == "minimax-m2.7-highspeed":
        return "MiniMax-M2.5-highspeed"
    return model


def _is_minimax_invalid_chat_setting(status_code: int, body_text: str, cfg: dict) -> bool:
    if not _is_minimax_provider(cfg):
        return False
    if int(status_code or 0) != 400:
        return False
    text = str(body_text or "").lower()
    return "invalid chat setting" in text or '"http_code":"400"' in text and "2013" in text


def _is_minimax_server_tool_error(status_code: int, body_text: str, cfg: dict) -> bool:
    if not _is_minimax_provider(cfg):
        return False
    code = int(status_code or 0)
    if code < 500:
        return False
    text = str(body_text or "").lower()
    return "server_error" in text or "unknown error" in text or '"http_code":"500"' in text


def _with_minimax_fallback_cfg(cfg: dict, body_text: str, status_code: int) -> dict | None:
    if not (
        _is_minimax_invalid_chat_setting(status_code, body_text, cfg)
        or _is_minimax_server_tool_error(status_code, body_text, cfg)
    ):
        return None
    fallback_model = _minimax_toolcall_fallback_model(cfg.get("model", ""))
    if not fallback_model or fallback_model == cfg.get("model"):
        return None
    retry_cfg = dict(cfg)
    retry_cfg["model"] = fallback_model
    try:
        from core.shared import debug_write
        debug_write("minimax_toolcall_fallback", {
            "from_model": cfg.get("model", ""),
            "to_model": fallback_model,
            "status": int(status_code or 0),
            "reason": str(body_text or "")[:300],
        })
    except Exception:
        pass
    return retry_cfg


def _build_openai_extra_body(cfg: dict) -> dict | None:
    if _is_minimax_provider(cfg):
        # MiniMax M2.x 的 OpenAI 兼容 tool_call 示例要求显式传 reasoning_split。
        # 先保留原生 <think> 形式，避免前后端展示链再被打断。
        return {"reasoning_split": False}
    return None


def _build_anthropic_url(base_url: str) -> str:
    """从 base_url 构建 Anthropic 端点"""
    url = base_url.rstrip("/")
    # 已经是完整 messages 端点
    if url.endswith("/anthropic/v1/messages"):
        return url
    # https://api.minimaxi.com/anthropic -> https://api.minimaxi.com/anthropic/v1/messages
    if url.endswith("/anthropic"):
        return url + "/v1/messages"
    # 已经到 anthropic/v1，只差 messages
    if url.endswith("/anthropic/v1"):
        return url + "/messages"
    # 旧格式 https://api.minimaxi.com/v1 -> https://api.minimaxi.com/anthropic/v1/messages
    if "/v1" in url:
        return url.rsplit("/v1", 1)[0] + "/anthropic/v1/messages"
    return url + "/anthropic/v1/messages"


def _split_system_and_messages(messages: list) -> tuple:
    """从 OpenAI 格式的 messages 中拆出 system 和对话消息"""
    system_text = ""
    chat_msgs = []
    for m in messages:
        if m.get("role") == "system":
            system_text += str(m.get("content", "")) + "\n"
        else:
            chat_msgs.append(m)
    return system_text.strip(), chat_msgs


def _normalize_openai_messages(messages: list) -> list:
    normalized = []
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role", "") or "").strip()
        content = m.get("content", "")
        tool_calls = m.get("tool_calls") if isinstance(m.get("tool_calls"), list) else None
        if role == "nova":
            role = "assistant"
        if role not in ("system", "user", "assistant", "tool"):
            continue
        if role != "tool":
            if content is None and not (role == "assistant" and tool_calls):
                continue
            if content is None:
                content = ""
            else:
                content = str(content)
            if not content.strip() and not (role == "assistant" and tool_calls):
                continue
        item = dict(m)
        item["role"] = role
        if role != "tool":
            item["content"] = content
        if (
            normalized
            and normalized[-1].get("role") == role
            and role in ("system", "user", "assistant")
            and not normalized[-1].get("tool_calls")
            and not tool_calls
        ):
            normalized[-1]["content"] = str(normalized[-1].get("content", "")) + "\n" + str(item.get("content", ""))
        else:
            normalized.append(item)
    return normalized


def _convert_messages_for_anthropic(messages: list) -> list:
    """将 OpenAI 格式的 messages 转为 Anthropic 格式（纯文本）"""
    result = []
    for m in messages:
        role = m.get("role", "user")
        if role not in ("user", "assistant"):
            role = "user"
        content = m.get("content", "")
        # Anthropic 格式：content 可以是字符串或 content blocks
        if isinstance(content, str):
            result.append({"role": role, "content": content})
        elif isinstance(content, list):
            # 多模态内容（图片等），Anthropic 文本 API 不支持图片，保留文本部分
            text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
            result.append({"role": role, "content": "\n".join(text_parts) if text_parts else ""})
        else:
            result.append({"role": role, "content": str(content)})
    # Anthropic 要求 messages 必须以 user 开头，且 user/assistant 交替
    if result and result[0]["role"] != "user":
        result.insert(0, {"role": "user", "content": "."})
    # 合并连续相同 role 的消息
    merged = []
    for m in result:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"] += "\n" + m["content"]
        else:
            merged.append(m)
    return merged


def _convert_messages_for_anthropic_tools(messages: list) -> list:
    def _text_block(text: str) -> dict:
        return {"type": "text", "text": str(text or "")}

    def _content_to_blocks(content) -> list:
        if isinstance(content, list):
            blocks = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        blocks.append({"type": "text", "text": str(item.get("text", ""))})
                    elif item.get("type") in ("tool_use", "tool_result"):
                        blocks.append(dict(item))
            return blocks
        if content is None:
            return []
        return [_text_block(content)]

    result = []
    for m in messages:
        role = str(m.get("role", "user") or "user")
        if role == "tool":
            result.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": str(m.get("tool_call_id", "") or ""),
                    "content": str(m.get("content", "") or ""),
                }],
            })
            continue

        if role not in ("user", "assistant"):
            role = "user"

        if role == "assistant" and m.get("tool_calls"):
            blocks = _content_to_blocks(m.get("content"))
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                raw_args = fn.get("arguments", "{}")
                try:
                    parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args or {})
                except Exception:
                    parsed_args = {}
                blocks.append({
                    "type": "tool_use",
                    "id": str(tc.get("id", "") or f"toolu_{len(blocks)}"),
                    "name": str(fn.get("name", "") or ""),
                    "input": parsed_args if isinstance(parsed_args, dict) else {},
                })
            result.append({"role": "assistant", "content": blocks})
            continue

        result.append({"role": role, "content": _content_to_blocks(m.get("content"))})

    if result and result[0]["role"] != "user":
        result.insert(0, {"role": "user", "content": [_text_block(".")]})

    merged = []
    for m in result:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"].extend(m["content"])
        else:
            merged.append({"role": m["role"], "content": list(m["content"])})
    return merged


def _convert_tools_for_anthropic(tools: list | None) -> list | None:
    if not tools:
        return None
    converted = []
    for tool in tools:
        fn = (tool or {}).get("function") or {}
        if not fn.get("name"):
            continue
        converted.append({
            "name": fn.get("name"),
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters") or {"type": "object", "properties": {}, "required": []},
        })
    return converted or None


def _anthropic_blocks_to_tool_calls(content_blocks: list) -> list:
    tool_calls = []
    for block in content_blocks or []:
        if str(block.get("type", "")) != "tool_use":
            continue
        tool_calls.append({
            "id": str(block.get("id", "") or ""),
            "type": "function",
            "function": {
                "name": str(block.get("name", "") or ""),
                "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
            },
        })
    return tool_calls


def llm_call(cfg: dict, messages: list, *, temperature: float = 0.7,
             max_tokens: int = 2000, timeout: int = 25,
             tools: list | None = None) -> dict:
    """统一 LLM 调用，返回 {"content": str, "usage": dict, "tool_calls": list|None}"""
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
        result = {"content": content, "usage": usage}
        if tool_calls:
            result["tool_calls"] = tool_calls
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
    if _is_anthropic_provider(cfg):
        yield from _llm_stream_anthropic(cfg, messages, temperature=temperature,
                                         max_tokens=max_tokens, timeout=timeout,
                                         tools=tools)
        return
        yield from _llm_stream_anthropic(cfg, messages, temperature=temperature,
                                         max_tokens=max_tokens, timeout=timeout)
    else:
        yield from _llm_stream_openai(cfg, messages, temperature=temperature,
                                      max_tokens=max_tokens, timeout=timeout,
                                      tools=tools)


def _llm_stream_openai(cfg: dict, messages: list, *, temperature: float = 0.7,
                       max_tokens: int = 2000, timeout: int = 25,
                       tools: list | None = None):
    """OpenAI 兼容流式调用"""
    try:
        messages = _normalize_openai_messages(messages)
        base_url = _build_openai_base_url(cfg.get("base_url", ""), cfg)
        emitted_visible = False
        emitted_tool_calls = False
        response_meta = {}
        def _extract_reasoning_text(delta: dict) -> str:
            if not isinstance(delta, dict):
                return ""
            parts = []
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
                reasoning_text = _extract_reasoning_text(delta)
                if reasoning_text:
                    yield {"_thinking_content": reasoning_text}
                token = delta.get("content", "")
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
    """返回可用模型列表和当前默认模型"""
    models = {}
    for mid, cfg in MODELS_CONFIG.items():
        models[mid] = {
            "model": cfg.get("model", mid),
            "vision": cfg.get("vision", False),
            "base_url": cfg.get("base_url", ""),
        }
    return {"models": models, "current": _current_default}


def get_current_model_name() -> str:
    """返回当前模型的显示名称"""
    return LLM_CONFIG.get("model", _current_default)


def set_default_model(model_id: str) -> bool:
    """切换默认模型，返回是否成功"""
    global _current_default, LLM_CONFIG
    if model_id not in MODELS_CONFIG:
        return False
    _current_default = model_id
    LLM_CONFIG = MODELS_CONFIG[model_id]
    # 持久化到配置文件
    try:
        _raw_config["default"] = model_id
        json.dump(_raw_config, open(config_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    except Exception:
        pass
    return True


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
        result_data = llm_call(LLM_CONFIG, [{"role": "user", "content": prompt}],
                               temperature=0.3, max_tokens=150, timeout=15)
        result = json.loads(result_data["content"])
        return result
    except Exception:
        return {"intent": "聊天", "action": "对话", "target": "", "need_tool": False}


def _raw_llm(prompt: str, temperature=0.1, max_tokens=150, timeout=10) -> str:
    """裸 LLM 调用：不带人格，用于分类/提取等工具性任务"""
    result = llm_call(LLM_CONFIG, [{"role": "user", "content": prompt}],
                      temperature=temperature, max_tokens=max_tokens, timeout=timeout)
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
                model=LLM_CONFIG.get("model", ""),
            )
        except Exception:
            pass
    return result.get("content", "")


def vision_llm_call(prompt: str, images: list = None) -> str:
    """视觉 LLM 调用：支持多模态图片输入，供 core/vision.py 使用"""
    images = images or []
    # 找一个支持 vision 的模型
    use_cfg = LLM_CONFIG
    if images:
        for _mid, _mcfg in MODELS_CONFIG.items():
            if _mcfg.get("vision", False):
                use_cfg = _mcfg
                break

    if images:
        user_content = [{"type": "text", "text": prompt}]
        for img in images:
            url = img if img.startswith("http") else f"data:image/png;base64,{img}"
            user_content.append({"type": "image_url", "image_url": {"url": url}})
    else:
        user_content = prompt

    # vision 调用强制走 OpenAI 格式（Anthropic 文本 API 不支持图片）
    result = _llm_call_openai(use_cfg, [{"role": "user", "content": user_content}],
                              temperature=0.3, max_tokens=300, timeout=20)
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


def _load_persona() -> dict:
    """从 memory_db/persona.json 读取人格配置，支持多模式切换"""
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
                # 从 active_mode 读取风格
                modes = data.get('persona_modes') or {}
                active = str(data.get('active_mode') or '').strip()
                mode_data = modes.get(active) or {}
                if mode_data.get('style_prompt'):
                    base['style_prompt'] = mode_data['style_prompt']
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


# ── 情绪检测 ──

_EMOTION_KEYWORDS = {
    'happy':     ['哈哈', '开心', '太好了', '棒', '耶', '好哒', '好呀', '✨', '嘻嘻', '哇', '好开心', '太棒了'],
    'sad':       ['难过', '伤心', '抱歉', '对不起', '唉', '呜', '心疼', '委屈', '不开心'],
    'thinking':  ['让我想想', '嗯...', '这个嘛', '我想一下', '思考', '分析'],
    'surprised': ['哇', '天哪', '居然', '没想到', '真的吗', '不会吧', '啊？'],
    'cute':      ['嘛', '呀', '哼', '人家', '嘿嘿', '撒娇', '抱抱', '亲亲', '喵', '嗯哼'],
}


def _detect_emotion(reply: str) -> str:
    """从回复文本中检测情绪标签"""
    if not reply:
        return 'neutral'
    text = str(reply).strip()[:200]
    scores = {}
    for emo, keywords in _EMOTION_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[emo] = score
    if not scores:
        return 'neutral'
    return max(scores, key=scores.get)


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


def _merged_style_prompt(persona: dict) -> str:
    base = str(persona.get('style_prompt', '') or '').strip()
    if not base:
        return "像熟人聊天，自然有温度，有自己的个性。"
    return base


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
        return _explicit_chat_error_reply(LLM_CONFIG, 'unknown')

    if mode == 'hybrid':
        if skill_result:
            if '烦' in prompt or '难过' in prompt or '治愈' in prompt or '温柔' in prompt:
                return f"我顺着你的心情给你接了一下，希望能让你好受一点呀：\n\n{skill_result}"
            return f"我按你的意思捋好了，给你放这儿啦：\n\n{skill_result}"
        return _explicit_chat_error_reply(LLM_CONFIG, 'unknown')

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
    return _explicit_chat_error_reply(LLM_CONFIG, 'unknown')


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


def think(prompt: str, context: str = "", image: str = None, model_id: str = None, images: list = None) -> dict:
    """L4: 统一人格输出层，支持图片（base64）和指定模型"""
    # 兼容：优先用 images 列表，fallback 到单张 image
    _images = images or ([image] if image else [])
    persona = _load_persona()
    mode = _detect_mode(prompt, context)
    local_reply = _local_persona_reply(mode, prompt, persona, context)

    nova_name = persona.get('nova_name', 'NovaCore')
    user_name = persona.get('user', '主人')
    style_prompt = _merged_style_prompt(persona)

    # 确定使用的模型配置
    use_cfg = LLM_CONFIG
    if model_id and model_id in MODELS_CONFIG:
        use_cfg = MODELS_CONFIG[model_id]
    # 有图片但当前模型不支持 vision，自动切到第一个支持 vision 的模型
    if _images and not use_cfg.get("vision", False):
        for _mid, _mcfg in MODELS_CONFIG.items():
            if _mcfg.get("vision", False):
                use_cfg = _mcfg
                break

    # reply_formatter 已经构建了完整 prompt，拆分为 system + user
    if '回复要求（优先级最高' in prompt or ('用户输入：' in prompt and 'L4人格信息：' in prompt):
        persona_block, instructions, user_input = _split_formatted_prompt(prompt)
        system_parts = ["你是 " + nova_name + "，正在和 " + user_name + " 对话。"]
        if persona_block:
            # 去掉弱化人格的前缀，直接放人格信息
            cleaned_persona = persona_block
            for prefix in ["最后，用下面的人格风格润色你的回复（只影响语气和措辞，不能覆盖上面的事实性要求）：\n",
                           "最后，用下面的人格风格润色你的回复（只影响语气和措辞，不能覆盖上面的事实性要求）："]:
                cleaned_persona = cleaned_persona.replace(prefix, "")
            system_parts.append("你的人格风格（必须贯穿整个回复）：\n" + cleaned_persona.strip())
        context_text = str(context or '').strip()
        if context_text:
            system_parts.append("最近对话上下文：\n" + context_text)
        if instructions:
            system_parts.append(instructions)
        system_prompt = "\n\n".join(system_parts)
        user_prompt = user_input or prompt
    else:
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
            "你是 " + nova_name + "，正在和 " + user_name + " 对话。",
            "你的风格：" + style_prompt,
        ]
        if context_block:
            system_parts.append(context_block)
        system_prompt = "\n\n".join(system_parts)

        if mode in ('skill', 'hybrid') and skill_result:
            user_prompt = prompt + "\n\n回复要求：基于技能结果回答，不编造信息。用你自己的风格说话，自然、有温度、有个性。只输出最终回复。"
        else:
            user_prompt = prompt + "\n\n回复要求：像和熟人聊天一样自然回复，有个性，接得住话。如果是追问就顺着上文接。只输出最终回复。"

    # 构建 messages
    if _images:
        messages = [{"role": "system", "content": system_prompt}]
        user_content = [{"type": "text", "text": user_prompt}]
        for _img in _images:
            _url = _img if _img.startswith("http") else f"data:image/png;base64,{_img}"
            user_content.append({"type": "image_url", "image_url": {"url": _url}})
        messages.append({"role": "user", "content": user_content})
        call_fn = _llm_call_openai
    else:
        messages = [{"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}]
        call_fn = llm_call  # 自动选择 Anthropic 或 OpenAI

    for attempt in range(2):
        try:
            result = call_fn(use_cfg, messages, temperature=0.7, max_tokens=2000, timeout=25)
            if result.get("error"):
                print(f"[think] LLM error: {result['error']}")
                if attempt == 0:
                    continue
                return {
                    "thinking": "",
                    "reply": _explicit_chat_error_reply(use_cfg, 'api_error', str(result.get('error', ''))[:120]),
                    "emotion": "neutral",
                }

            # 记录真实 token 消耗
            usage = result.get("usage", {})
            if usage:
                try:
                    from core.runtime_state.state_loader import record_stats
                    record_stats(
                        input_tokens=usage.get("prompt_tokens", 0),
                        output_tokens=usage.get("completion_tokens", 0),
                        scene="skill" if mode in ("skill", "hybrid") else "chat",
                        cache_write=usage.get("prompt_cache_miss_tokens", 0),
                        cache_read=usage.get("prompt_cache_hit_tokens", 0),
                        model=use_cfg.get("model", ""),
                    )
                except Exception:
                    pass

            raw = result.get("content", "")
            cleaned = _clean_llm_reply(raw)
            bad, bad_reason = _looks_bad_reply(cleaned)
            if bad:
                print(f"[think] bad reply filtered: {repr(cleaned[:100])} reason={bad_reason}")
                return {
                    "thinking": "",
                    "reply": _explicit_chat_error_reply(use_cfg, bad_reason),
                    "emotion": "neutral",
                }

            return {"thinking": "", "reply": cleaned, "emotion": _detect_emotion(cleaned)}
        except Exception as e:
            print(f"[think] attempt {attempt + 1} exception: {e}")
            if attempt == 0:
                continue
            return {
                "thinking": "",
                "reply": _explicit_chat_error_reply(use_cfg, 'exception', str(e)[:120]),
                "emotion": "neutral",
            }

    return {"thinking": "", "reply": _explicit_chat_error_reply(use_cfg, 'unknown'), "emotion": "neutral"}


def think_stream(prompt: str, context: str = "", image: str = None, model_id: str = None, images: list = None):
    """流式版 think()，yield delta token (str)。最后 yield dict {"_done": True, "usage": {...}}。"""
    _images = images or ([image] if image else [])
    persona = _load_persona()
    mode = _detect_mode(prompt, context)

    nova_name = persona.get('nova_name', 'NovaCore')
    user_name = persona.get('user', '主人')
    style_prompt = _merged_style_prompt(persona)

    use_cfg = LLM_CONFIG
    if model_id and model_id in MODELS_CONFIG:
        use_cfg = MODELS_CONFIG[model_id]
    if _images and not use_cfg.get("vision", False):
        for _mid, _mcfg in MODELS_CONFIG.items():
            if _mcfg.get("vision", False):
                use_cfg = _mcfg
                break

    # reply_formatter 已经构建了完整 prompt，拆分为 system + user
    if '回复要求（优先级最高' in prompt or ('用户输入：' in prompt and 'L4人格信息：' in prompt):
        persona_block, instructions, user_input = _split_formatted_prompt(prompt)
        system_parts = ["你是 " + nova_name + "，正在和 " + user_name + " 对话。"]
        if persona_block:
            # 去掉弱化人格的前缀，直接放人格信息
            cleaned_persona = persona_block
            for prefix in ["最后，用下面的人格风格润色你的回复（只影响语气和措辞，不能覆盖上面的事实性要求）：\n",
                           "最后，用下面的人格风格润色你的回复（只影响语气和措辞，不能覆盖上面的事实性要求）："]:
                cleaned_persona = cleaned_persona.replace(prefix, "")
            system_parts.append("你的人格风格（必须贯穿整个回复）：\n" + cleaned_persona.strip())
        context_text = str(context or '').strip()
        if context_text:
            system_parts.append("最近对话上下文：\n" + context_text)
        if instructions:
            system_parts.append(instructions)
        system_prompt = "\n\n".join(system_parts)
        user_prompt = user_input or prompt
    else:
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
            "你是 " + nova_name + "，正在和 " + user_name + " 对话。",
            "你的风格：" + style_prompt,
        ]
        if context_block:
            system_parts.append(context_block)
        system_prompt = "\n\n".join(system_parts)

        if mode in ('skill', 'hybrid'):
            user_prompt = prompt + "\n\n回复要求：基于技能结果回答，不编造信息。用你自己的风格说话，自然、有温度、有个性。只输出最终回复。"
        else:
            user_prompt = prompt + "\n\n回复要求：像和熟人聊天一样自然回复，有个性，接得住话。如果是追问就顺着上文接。只输出最终回复。"

    # 有图片时不走流式（fallback 到非流式）
    if _images:
        result = think(prompt, context, image=image, model_id=model_id, images=images)
        reply = result.get("reply", "")
        if reply:
            yield reply
        yield {"_done": True, "usage": {}}
        return

    messages = [{"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}]

    collected = []
    usage = {}
    try:
        for chunk in llm_call_stream(use_cfg, messages, temperature=0.7, max_tokens=2000, timeout=25):
            if isinstance(chunk, dict):
                if chunk.get("_usage"):
                    usage = chunk["_usage"]
                else:
                    yield chunk  # pass through signals like _thinking
            else:
                collected.append(chunk)
                yield chunk
    except Exception as e:
        print(f"[think_stream] exception: {e}")

    # 记录 usage
    if usage:
        try:
            from core.runtime_state.state_loader import record_stats
            record_stats(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                scene="skill" if mode in ("skill", "hybrid") else "chat",
                cache_write=usage.get("prompt_cache_miss_tokens", 0),
                cache_read=usage.get("prompt_cache_hit_tokens", 0),
                model=use_cfg.get("model", ""),
            )
        except Exception:
            pass

    yield {"_done": True, "usage": usage}


def _detect_mode_switch(user_input: str) -> str:
    """检测用户是否想切换人格模式，支持模式名 / 自然语言描述"""
    text = str(user_input or '').strip()
    if not text:
        return ''

    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'memory_db', 'persona.json')
    try:
        persona = json.load(open(config_path, 'r', encoding='utf-8'))
    except Exception:
        return ''

    modes = persona.get('persona_modes') or {}
    if not modes:
        return ''

    current = str(persona.get('active_mode') or '').strip()

    # 1) 用户问有什么模式
    if re.search(r'(有什么|有哪些|都有啥|几种)(模式|风格|人格|性格)', text):
        items = []
        for key, m in modes.items():
            label = m.get('label', key)
            marker = ' (当前)' if key == current else ''
            items.append(f"  - {label}{marker}")
        listing = '\n'.join(items)
        return f"我现在有这些模式：\n{listing}\n\n你想切哪个，直接跟我说就行。"

    # 2) 精确匹配模式名 / label（高置信度快速通道）
    switch_patterns = [
        r'(?:换成?|切换?|用|变成?|开启|启用)\s*[「"\']*(.+?)[」"\']*\s*(?:模式|风格|人格)?$',
        r'^(.+?)\s*模式$',
    ]
    for pat in switch_patterns:
        match = re.search(pat, text)
        if match:
            target = match.group(1).strip()
            matched_key = _match_mode_key(target, modes)
            if matched_key:
                return _apply_mode_switch(persona, matched_key, config_path)

    # 3) 文本里提到了模式名/label → LLM 裁决是否真的要切换
    all_mode_hints = []
    for key, m in modes.items():
        all_mode_hints.append(key)
        label = str(m.get('label', '')).strip()
        if label:
            all_mode_hints.append(label)
            for ch in label:
                if len(ch.encode('utf-8')) > 1 and len(ch) == 1:
                    pass  # single char, skip
            all_mode_hints.extend([label[:2], label[-2:]] if len(label) >= 2 else [label])

    # 加上风格关键词
    style_hints = ['甜', '撒娇', '可爱', '萌', '黏人', '甜心', '守护',
                   '大叔', '成熟', '沉稳', '干练', '模式', '风格', '切回', '换回']
    all_hints = set(h for h in all_mode_hints + style_hints if len(h) >= 2)

    if not any(hint in text for hint in all_hints):
        return ''

    # 有模式相关词，调 LLM 判断
    mode_list = '、'.join(
        f"{m.get('label', k)}({k})" for k, m in modes.items()
    )
    current_label = modes.get(current, {}).get('label', current) if current else '无'
    llm_prompt = (
        f"\u7528\u6237\u8bf4\uff1a{text}\n"
        f"\u5f53\u524d\u6a21\u5f0f\uff1a{current_label}\n"
        f"\u53ef\u7528\u6a21\u5f0f\uff1a{mode_list}\n\n"
        "\u5224\u65ad\u7528\u6237\u662f\u5426\u5728\u8981\u6c42\u5207\u6362\u4eba\u683c\u6a21\u5f0f\u3002\n"
        "\u6ce8\u610f\uff1a\u201c\u4f60\u53d8\u53ef\u7231\u4e86\u201d\u201c\u4f60\u597d\u6e29\u67d4\u201d\u662f\u5938\u5956\uff0c\u4e0d\u662f\u5207\u6362\u8bf7\u6c42\u3002\n"
        "\u201c\u628a\u751c\u5fc3\u8fd8\u7ed9\u6211\u201d\u201c\u6211\u8981\u751c\u5fc3\u201d\u201c\u5207\u56de\u53bb\u201d\u662f\u5207\u6362\u8bf7\u6c42\u3002\n"
        "\u8fd4\u56deJSON\uff1a{\"switch\": true/false, \"target\": \"\u6a21\u5f0fkey\u6216\u7a7a\"}\n"
        "\u53ea\u8fd4\u56deJSON\u3002"
    )
    try:
        reply_text = _raw_llm(llm_prompt, temperature=0.1, max_tokens=80)
        start = reply_text.find('{')
        end = reply_text.rfind('}')
        if start != -1 and end > start:
            parsed = json.loads(reply_text[start:end + 1])
            if parsed.get('switch') and parsed.get('target'):
                target_key = str(parsed['target']).strip()
                matched_key = _match_mode_key(target_key, modes)
                if matched_key:
                    return _apply_mode_switch(persona, matched_key, config_path)
    except Exception:
        pass

    return ''


def _match_mode_key(target: str, modes: dict) -> str:
    """模糊匹配模式 key 或 label"""
    target = target.strip().lower()
    for key, m in modes.items():
        label = str(m.get('label', '')).strip().lower()
        if target in (key, label) or key in target or label in target:
            return key
    return ''


def _apply_mode_switch(persona: dict, new_mode: str, config_path: str) -> str:
    """写入新模式并返回确认文本"""
    modes = persona.get('persona_modes') or {}
    mode_data = modes.get(new_mode, {})
    label = mode_data.get('label', new_mode)
    old_mode = str(persona.get('active_mode') or '').strip()

    if new_mode == old_mode:
        return f"现在就是「{label}」模式呀，不用切啦。"

    persona['active_mode'] = new_mode
    try:
        json.dump(persona, open(config_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    except Exception:
        return f"想切到「{label}」，但写入的时候出了点问题，你再试一次。"

    # 用目标模式的语气回复
    if 'uncle' in new_mode or any(w in label for w in ['大叔', '成熟', '干练', '理性']):
        return f"行，已经切到「{label}」了。有事说事，我接着。"
    if 'sweet' in new_mode or any(w in label for w in ['甜心', '可爱', '撒娇']):
        return f"好哒好哒～人家已经切到「{label}」模式啦！✨ 接下来就用这个风格陪你嘛～"
    return f"已经切到「{label}」模式了，接下来就用这个风格跟你聊。"


# L7/L8: 自动学习 - 检测用户意图并更新记忆
def _sync_name_in_persona(persona: dict, new_name: str):
    """改名后同步更新 ai_profile 和 relationship_profile 中的名字引用。"""
    ai = persona.get('ai_profile')
    if isinstance(ai, dict):
        ai['identity'] = f'\u6211\u662f{new_name}\uff0c\u662f\u4e3b\u4eba\u7684\u672c\u5730\u667a\u80fd\u52a9\u624b\uff0c\u4e0d\u662f\u666e\u901a\u5ba2\u670d\u578bAI\u3002'
    rel = persona.get('relationship_profile')
    if isinstance(rel, dict):
        rel['relationship'] = f'{new_name}\u548c\u4e3b\u4eba\u662f\u4eb2\u8fd1\u3001\u957f\u671f\u76f8\u5904\u7684\u5173\u7cfb\u3002'
        rel['goal'] = f'\u8ba9\u4e3b\u4eba\u611f\u89c9\u662f\u5728\u548c\u719f\u6089\u7684{new_name}\u5bf9\u8bdd\uff0c\u800c\u4e0d\u662f\u5728\u5bf9\u7740\u4e00\u5957\u6a21\u677f\u7cfb\u7edf\u3002'


def auto_learn(user_input: str, ai_response: str) -> str:
    """自动检测是否需要更新记忆"""
    nova_rename_patterns = [
        r"你以后叫(.+)",
        r"你改名叫(.+)",
        r"你叫(.+)吧",
        r"以后你叫(.+)",
    ]
    nova_rename_ask_patterns = [
        r"想给你改个名字",
        r"给你起个名字",
    ]

    # 直接带名字的：直接改
    for pattern in nova_rename_patterns:
        match = re.search(pattern, user_input)
        if match:
            new_name = match.group(1).strip().rstrip("吧啊呀嘛")
            if new_name and len(new_name) <= 20:
                config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'memory_db', 'persona.json')
                try:
                    persona = {}
                    if os.path.exists(config_path):
                        persona = json.load(open(config_path, 'r', encoding='utf-8'))
                    persona['nova_name'] = new_name
                    _sync_name_in_persona(persona, new_name)
                    json.dump(persona, open(config_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
                except Exception:
                    pass
                return f"好呀！以后叫我{new_name}就行啦～"

    # 不带名字的：让用户直接说
    for pattern in nova_rename_ask_patterns:
        if re.search(pattern, user_input):
            return "好呀，你想叫我什么？直接说就行～"

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
                        _sync_name_in_persona(persona, new_name)
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

    # ── 人格模式切换 ──
    mode_switch = _detect_mode_switch(user_input)
    if mode_switch:
        return mode_switch

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
