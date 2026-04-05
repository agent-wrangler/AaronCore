"""Local Codex subscription transport helpers."""

from __future__ import annotations

import atexit
import json
import os
import shutil
import socket
import subprocess
import threading
import time

try:
    from websockets.sync.client import connect as _websocket_connect
except Exception:  # pragma: no cover - optional runtime dependency
    _websocket_connect = None


_CODEX_TRANSPORTS = {"codex_cli", "codex-subscription", "codex_subscription"}
_LOGIN_STATUS_CACHE = {"expires_at": 0.0, "result": (False, "")}
_APP_SERVER_LOCK = threading.Lock()
_APP_SERVER_STATE = {"proc": None, "url": "", "bin": ""}
_VALID_REASONING_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh"}
_VALID_REASONING_SUMMARIES = {"auto", "concise", "detailed", "none"}


def _debug_write(stage: str, data: dict) -> None:
    try:
        from core.shared import debug_write

        debug_write(stage, data)
    except Exception:
        pass


def _build_subprocess_kwargs(*, timeout: int, input_text: str | None = None) -> dict:
    kwargs = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
    }
    if input_text is not None:
        kwargs["input"] = input_text
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        kwargs["startupinfo"] = startupinfo
    return kwargs


def _build_popen_kwargs() -> dict:
    kwargs = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        kwargs["startupinfo"] = startupinfo
    return kwargs


def _find_codex_bin() -> str:
    candidates = ["codex.cmd", "codex"] if os.name == "nt" else ["codex"]
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return path
    return ""


def is_codex_cli_provider(cfg: dict | None) -> bool:
    if not isinstance(cfg, dict):
        return False
    transport = str(cfg.get("transport") or "").strip().lower()
    base_url = str(cfg.get("base_url") or "").strip().lower()
    auth_mode = str(cfg.get("auth_mode") or "").strip().lower()
    return (
        transport in _CODEX_TRANSPORTS
        or auth_mode in _CODEX_TRANSPORTS
        or base_url.startswith("codex://")
    )


def validate_codex_cli_login(*, timeout: int = 10) -> tuple[bool, str]:
    now = time.time()
    if _LOGIN_STATUS_CACHE["expires_at"] > now:
        return _LOGIN_STATUS_CACHE["result"]

    codex_bin = _find_codex_bin()
    if not codex_bin:
        result = (False, "Local Codex CLI not found. Please install Codex CLI first.")
        _LOGIN_STATUS_CACHE.update({"expires_at": now + 5, "result": result})
        return result

    try:
        proc = subprocess.run(
            [codex_bin, "login", "status"],
            **_build_subprocess_kwargs(timeout=max(int(timeout or 0), 5)),
        )
    except subprocess.TimeoutExpired:
        result = (False, "Checking local Codex login status timed out. Please try again.")
        _LOGIN_STATUS_CACHE.update({"expires_at": now + 3, "result": result})
        return result
    except Exception as exc:
        result = (False, f"Checking local Codex login status failed: {type(exc).__name__}: {exc}")
        _LOGIN_STATUS_CACHE.update({"expires_at": now + 3, "result": result})
        return result

    combined = "\n".join(
        part.strip() for part in (proc.stdout or "", proc.stderr or "") if str(part or "").strip()
    ).strip()
    lowered = combined.lower()
    if proc.returncode == 0 and "logged in" in lowered:
        result = (True, "")
        _LOGIN_STATUS_CACHE.update({"expires_at": now + 15, "result": result})
        return result
    if "not logged in" in lowered or "please login" in lowered:
        result = (False, "Local Codex is not logged in yet. Please run `codex login` first.")
        _LOGIN_STATUS_CACHE.update({"expires_at": now + 5, "result": result})
        return result
    if combined:
        result = (False, combined[:300])
        _LOGIN_STATUS_CACHE.update({"expires_at": now + 3, "result": result})
        return result
    result = (False, "Local Codex is currently unavailable. Please confirm it is installed and logged in.")
    _LOGIN_STATUS_CACHE.update({"expires_at": now + 3, "result": result})
    return result


def codex_cli_call(
    cfg: dict,
    messages: list,
    *,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    timeout: int = 25,
    tools: list | None = None,
) -> dict:
    return _codex_exec_call(
        cfg,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        tools=tools,
    )


def codex_cli_call_stream(
    cfg: dict,
    messages: list,
    *,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    timeout: int = 25,
    tools: list | None = None,
):
    del temperature, max_tokens
    ok, detail = validate_codex_cli_login(timeout=min(timeout, 10))
    if not ok:
        _debug_write("codex_app_stream_login_unavailable", {"detail": detail[:300]})
        yield {"_usage": {}}
        return

    emitted_any = False
    usage = {}
    try:
        for chunk in _codex_app_server_stream(cfg, messages, timeout=timeout, tools=tools):
            if isinstance(chunk, dict) and "_usage" in chunk:
                usage = chunk["_usage"] if isinstance(chunk.get("_usage"), dict) else {}
            else:
                emitted_any = True
            yield chunk
        return
    except Exception as exc:
        _debug_write(
            "codex_app_stream_fallback",
            {
                "error": str(exc),
                "type": type(exc).__name__,
                "model": str(cfg.get("model") or ""),
                "emitted_any": emitted_any,
            },
        )
        if emitted_any:
            if usage:
                yield {"_usage": usage}
            return

    fallback = _codex_exec_call(cfg, messages, timeout=timeout, tools=tools)
    content = str(fallback.get("content", "") or "")
    if content:
        yield content
    yield {"_usage": fallback.get("usage", {}) if isinstance(fallback.get("usage"), dict) else {}}


def _codex_exec_call(
    cfg: dict,
    messages: list,
    *,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    timeout: int = 25,
    tools: list | None = None,
) -> dict:
    del temperature, max_tokens
    ok, detail = validate_codex_cli_login(timeout=min(timeout, 10))
    if not ok:
        return {"content": "", "usage": {}, "error": detail}

    codex_bin = _find_codex_bin()
    if not codex_bin:
        return {"content": "", "usage": {}, "error": "Local Codex CLI not found."}

    prompt = _render_codex_prompt(messages, tools=tools)
    sandbox = _sanitize_codex_sandbox(cfg.get("sandbox"))
    cwd = str(cfg.get("cwd") or os.getcwd() or "").strip() or os.getcwd()

    command = [
        codex_bin,
        "exec",
        "--json",
        "--color",
        "never",
        "--sandbox",
        sandbox,
        "--skip-git-repo-check",
        "--cd",
        cwd,
        "--model",
        str(cfg.get("model") or "gpt-5.4").strip() or "gpt-5.4",
        "-",
    ]

    try:
        proc = subprocess.run(
            command,
            **_build_subprocess_kwargs(timeout=max(int(timeout or 0) + 30, 60), input_text=prompt),
        )
    except subprocess.TimeoutExpired:
        return {"content": "", "usage": {}, "error": "Local Codex timed out. Please try again."}
    except Exception as exc:
        return {"content": "", "usage": {}, "error": f"Calling local Codex failed: {type(exc).__name__}: {exc}"}

    return _parse_codex_exec_output(proc.stdout or "", stderr_text=proc.stderr or "", returncode=proc.returncode)


def _sanitize_codex_sandbox(value) -> str:
    sandbox = str(value or "read-only").strip().lower()
    if sandbox not in {"read-only", "workspace-write", "danger-full-access"}:
        sandbox = "read-only"
    return sandbox


def _parse_codex_reasoning_effort(cfg: dict) -> str | None:
    value = str(cfg.get("reasoning_effort") or cfg.get("effort") or "").strip().lower()
    return value if value in _VALID_REASONING_EFFORTS else None


def _parse_codex_reasoning_summary(cfg: dict) -> str | None:
    value = str(cfg.get("reasoning_summary") or cfg.get("summary") or "").strip().lower()
    return value if value in _VALID_REASONING_SUMMARIES else None


def _build_codex_thread_start_params(cfg: dict, *, cwd: str) -> dict:
    return {
        "model": str(cfg.get("model") or "gpt-5.4").strip() or "gpt-5.4",
        "cwd": cwd,
        "approvalPolicy": "never",
        "sandbox": _sanitize_codex_sandbox(cfg.get("sandbox")),
        "ephemeral": bool(cfg.get("ephemeral", True)),
        "experimentalRawEvents": False,
        "persistExtendedHistory": False,
    }


def _build_codex_turn_start_params(cfg: dict, *, thread_id: str, prompt: str) -> dict:
    params = {
        "threadId": thread_id,
        "input": [{"type": "text", "text": prompt, "text_elements": []}],
    }
    effort = _parse_codex_reasoning_effort(cfg)
    if effort:
        params["effort"] = effort
    summary = _parse_codex_reasoning_summary(cfg)
    if summary:
        params["summary"] = summary
    return params


def _pick_free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _terminate_process(proc, *, timeout: float = 3.0) -> None:
    if not proc:
        return
    try:
        if proc.poll() is not None:
            return
        proc.terminate()
        proc.wait(timeout=timeout)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _shutdown_app_server() -> None:
    with _APP_SERVER_LOCK:
        proc = _APP_SERVER_STATE.get("proc")
        _APP_SERVER_STATE.update({"proc": None, "url": "", "bin": ""})
    _terminate_process(proc, timeout=1.0)


atexit.register(_shutdown_app_server)


def _open_app_server_connection(url: str, *, timeout: float):
    if _websocket_connect is None:
        raise RuntimeError("websockets sync client is unavailable.")
    try:
        return _websocket_connect(
            url,
            open_timeout=max(float(timeout or 0), 1.0),
            close_timeout=1.0,
            compression=None,
            proxy=None,
        )
    except TypeError:
        return _websocket_connect(
            url,
            open_timeout=max(float(timeout or 0), 1.0),
            close_timeout=1.0,
            compression=None,
        )


def _start_app_server(codex_bin: str, *, timeout: float) -> tuple[subprocess.Popen, str]:
    last_error = None
    overall_deadline = time.time() + max(float(timeout or 0), 12.0)

    while time.time() < overall_deadline:
        port = _pick_free_local_port()
        url = f"ws://127.0.0.1:{port}"
        proc = None
        try:
            proc = subprocess.Popen(
                [codex_bin, "app-server", "--listen", url],
                **_build_popen_kwargs(),
            )
            probe_deadline = min(overall_deadline, time.time() + 8.0)
            while time.time() < probe_deadline:
                if proc.poll() is not None:
                    raise RuntimeError(f"codex app-server exited early with code {proc.returncode}")
                try:
                    with _open_app_server_connection(url, timeout=1.5):
                        return proc, url
                except Exception as exc:
                    last_error = exc
                    time.sleep(0.2)
        except Exception as exc:
            last_error = exc
        _terminate_process(proc)

    if last_error:
        raise RuntimeError(f"Failed to start codex app-server: {type(last_error).__name__}: {last_error}")
    raise RuntimeError("Failed to start codex app-server.")


def _ensure_app_server_url(codex_bin: str, *, timeout: float) -> str:
    with _APP_SERVER_LOCK:
        proc = _APP_SERVER_STATE.get("proc")
        url = str(_APP_SERVER_STATE.get("url") or "")
        active_bin = str(_APP_SERVER_STATE.get("bin") or "")
        if proc and proc.poll() is None and url and active_bin == codex_bin:
            return url

        if proc:
            _terminate_process(proc)

        new_proc, new_url = _start_app_server(codex_bin, timeout=timeout)
        _APP_SERVER_STATE.update({"proc": new_proc, "url": new_url, "bin": codex_bin})
        return new_url


def _send_json_rpc(ws, *, request_id: str, method: str, params: dict) -> None:
    ws.send(json.dumps({"id": request_id, "method": method, "params": params}, ensure_ascii=False))


def _recv_json_rpc(ws, *, timeout: float) -> dict:
    raw = ws.recv(timeout=max(float(timeout or 0), 1.0))
    if not isinstance(raw, str):
        raise RuntimeError("Codex app-server returned a non-text websocket frame.")
    return json.loads(raw)


def _json_rpc_error_message(message: dict) -> str:
    error = message.get("error") if isinstance(message.get("error"), dict) else {}
    detail = str(error.get("message") or "").strip()
    if detail:
        return detail
    return str(message or "")[:300]


def _wait_for_json_rpc_response(ws, request_id: str, *, timeout: float) -> dict:
    deadline = time.time() + max(float(timeout or 0), 1.0)
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise TimeoutError(f"Timed out waiting for Codex app-server response {request_id}.")
        message = _recv_json_rpc(ws, timeout=min(remaining, 15.0))
        if str(message.get("id") or "") == str(request_id):
            if message.get("error") is not None:
                raise RuntimeError(_json_rpc_error_message(message))
            result = message.get("result")
            return result if isinstance(result, dict) else {}


def _translate_thread_token_usage(token_usage: dict | None) -> dict:
    usage = token_usage if isinstance(token_usage, dict) else {}
    raw_last = usage.get("last") if isinstance(usage.get("last"), dict) else {}
    raw_total = usage.get("total") if isinstance(usage.get("total"), dict) else {}
    source = raw_last or raw_total
    prompt_tokens = int(source.get("inputTokens", 0) or 0)
    prompt_cache_hit_tokens = int(source.get("cachedInputTokens", 0) or 0)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": int(source.get("outputTokens", 0) or 0),
        "prompt_cache_hit_tokens": prompt_cache_hit_tokens,
        "prompt_cache_miss_tokens": max(prompt_tokens - prompt_cache_hit_tokens, 0),
        "reasoning_output_tokens": int(source.get("reasoningOutputTokens", 0) or 0),
    }


def _codex_app_server_stream(
    cfg: dict,
    messages: list,
    *,
    timeout: int = 25,
    tools: list | None = None,
):
    codex_bin = _find_codex_bin()
    if not codex_bin:
        raise RuntimeError("Local Codex CLI not found.")

    cwd = str(cfg.get("cwd") or os.getcwd() or "").strip() or os.getcwd()
    prompt = _render_codex_prompt(messages, tools=tools)
    url = _ensure_app_server_url(codex_bin, timeout=max(float(timeout or 0), 12.0))

    with _open_app_server_connection(url, timeout=max(float(timeout or 0), 12.0)) as ws:
        request_counter = 1

        def send_request(method: str, params: dict) -> str:
            nonlocal request_counter
            request_id = str(request_counter)
            request_counter += 1
            _send_json_rpc(ws, request_id=request_id, method=method, params=params)
            return request_id

        init_request_id = send_request(
            "initialize",
            {
                "clientInfo": {"name": "novacore", "title": "NovaCore", "version": "1.0"},
                "capabilities": {"experimentalApi": False},
            },
        )
        _wait_for_json_rpc_response(ws, init_request_id, timeout=10.0)

        thread_request_id = send_request("thread/start", _build_codex_thread_start_params(cfg, cwd=cwd))
        thread_response = _wait_for_json_rpc_response(ws, thread_request_id, timeout=max(float(timeout or 0), 12.0))
        thread = thread_response.get("thread") if isinstance(thread_response.get("thread"), dict) else {}
        thread_id = str(thread.get("id") or "").strip()
        if not thread_id:
            raise RuntimeError("Codex app-server did not return a thread id.")

        turn_request_id = send_request(
            "turn/start",
            _build_codex_turn_start_params(cfg, thread_id=thread_id, prompt=prompt),
        )

        turn_id = ""
        usage = {}
        agent_text_by_item: dict[str, str] = {}
        reasoning_mode_by_item: dict[str, str] = {}
        deadline = time.time() + max(float(timeout or 0) + 90.0, 120.0)

        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError("Local Codex app-server stream timed out.")

            message = _recv_json_rpc(ws, timeout=min(remaining, 90.0))
            if str(message.get("id") or "") == turn_request_id:
                if message.get("error") is not None:
                    raise RuntimeError(_json_rpc_error_message(message))
                result = message.get("result") if isinstance(message.get("result"), dict) else {}
                turn = result.get("turn") if isinstance(result.get("turn"), dict) else {}
                turn_id = str(turn.get("id") or turn_id).strip()
                continue

            method = str(message.get("method") or "").strip()
            if not method:
                continue
            params = message.get("params") if isinstance(message.get("params"), dict) else {}

            if method == "item/agentMessage/delta":
                item_id = str(params.get("itemId") or "").strip()
                delta = str(params.get("delta") or "")
                if not delta:
                    continue
                if item_id:
                    agent_text_by_item[item_id] = str(agent_text_by_item.get(item_id) or "") + delta
                yield delta
                continue

            if method == "item/reasoning/textDelta":
                item_id = str(params.get("itemId") or "").strip()
                delta = str(params.get("delta") or "")
                if delta:
                    if item_id:
                        reasoning_mode_by_item[item_id] = "full"
                    yield {"_thinking_content": delta}
                continue

            if method == "item/reasoning/summaryTextDelta":
                item_id = str(params.get("itemId") or "").strip()
                if item_id and reasoning_mode_by_item.get(item_id) == "full":
                    continue
                delta = str(params.get("delta") or "")
                if delta:
                    if item_id and item_id not in reasoning_mode_by_item:
                        reasoning_mode_by_item[item_id] = "summary"
                    yield {"_thinking_content": delta}
                continue

            if method == "item/completed":
                item = params.get("item") if isinstance(params.get("item"), dict) else {}
                item_type = str(item.get("type") or "").strip()
                item_id = str(item.get("id") or "").strip()
                if item_type == "agentMessage":
                    text = str(item.get("text") or "")
                    previous = str(agent_text_by_item.get(item_id) or "")
                    if text.startswith(previous):
                        missing = text[len(previous):]
                    elif previous.startswith(text):
                        missing = ""
                    else:
                        missing = text
                    agent_text_by_item[item_id] = text
                    if missing:
                        yield missing
                elif item_type == "reasoning" and item_id and item_id not in reasoning_mode_by_item:
                    content = item.get("content") if isinstance(item.get("content"), list) else []
                    fallback_text = "".join(str(part or "") for part in content if isinstance(part, str))
                    if fallback_text:
                        reasoning_mode_by_item[item_id] = "completed"
                        yield {"_thinking_content": fallback_text}
                continue

            if method == "thread/tokenUsage/updated":
                usage = _translate_thread_token_usage(params.get("tokenUsage"))
                continue

            if method == "turn/completed":
                turn = params.get("turn") if isinstance(params.get("turn"), dict) else {}
                current_turn_id = str(turn.get("id") or params.get("turnId") or "").strip()
                if turn_id and current_turn_id and current_turn_id != turn_id:
                    continue
                status = str(turn.get("status") or "").strip()
                if status == "failed":
                    error = turn.get("error") if isinstance(turn.get("error"), dict) else {}
                    detail = str(error.get("message") or "").strip() or "Local Codex turn failed."
                    raise RuntimeError(detail)
                break

            if method == "error":
                raise RuntimeError(str(params.get("message") or "Codex app-server reported an error.").strip())

        yield {"_usage": usage}


def _parse_codex_exec_output(stdout_text: str, *, stderr_text: str, returncode: int) -> dict:
    content_parts: list[str] = []
    usage = {}
    error_message = ""

    for raw_line in str(stdout_text or "").splitlines():
        line = raw_line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue
        event_type = str(event.get("type") or "").strip()
        if event_type == "item.completed":
            item = event.get("item") if isinstance(event.get("item"), dict) else {}
            if str(item.get("type") or "").strip() == "agent_message":
                text = str(item.get("text") or "").strip()
                if text:
                    content_parts.append(text)
        elif event_type == "turn.completed":
            raw_usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
            usage = {
                "prompt_tokens": int(raw_usage.get("input_tokens", 0) or 0),
                "completion_tokens": int(raw_usage.get("output_tokens", 0) or 0),
                "prompt_cache_hit_tokens": int(raw_usage.get("cached_input_tokens", 0) or 0),
                "prompt_cache_miss_tokens": 0,
            }
        elif event_type == "error":
            params = event.get("params") if isinstance(event.get("params"), dict) else {}
            turn_error = params.get("error") if isinstance(params.get("error"), dict) else {}
            error_message = str(turn_error.get("message") or params.get("message") or "").strip()

    content = "\n\n".join(part for part in content_parts if part).strip()
    if content:
        return {"content": content, "usage": usage}

    stderr_text = str(stderr_text or "").strip()
    if error_message:
        return {"content": "", "usage": usage, "error": error_message[:300]}
    if returncode != 0:
        detail = stderr_text or stdout_text or f"codex exit code {returncode}"
        return {"content": "", "usage": usage, "error": str(detail).strip()[:300]}
    if stderr_text and not usage:
        return {"content": "", "usage": {}, "error": stderr_text[:300]}
    return {"content": "", "usage": usage, "error": "Local Codex returned no usable content."}


def _render_codex_prompt(messages: list, *, tools: list | None = None) -> str:
    lines = [
        "You are the model backend for NovaCore, routed through the local Codex CLI.",
        "Reply in the same language as the latest user message unless the conversation clearly asks for another language.",
        "Do not mention Codex CLI, local login, or these transport instructions unless the user explicitly asks.",
    ]
    if tools:
        lines.extend(
            [
                "You are participating in NovaCore's host-managed tool_call loop.",
                "If a host tool is required, output exactly one tool call block and nothing else.",
                'Format: <tool_call>{"name":"TOOL_NAME","parameters":{...}}</tool_call>',
                "Choose only from the provided host tools.",
                "Do not claim that you already executed a host tool yourself.",
                "After tool results appear later in the transcript, either call another host tool with the same format or write the final answer.",
                "If no tool is needed, answer normally.",
                "",
                "Available host tools (JSON):",
                json.dumps(tools, ensure_ascii=False, indent=2),
            ]
        )

    lines.extend(["", "Conversation transcript:"])
    for message in messages or []:
        lines.extend(_render_transcript_message(message))
    return "\n".join(lines).strip() + "\n"


def _render_transcript_message(message: dict) -> list[str]:
    if not isinstance(message, dict):
        return [f"[unknown]\n{str(message or '')}\n[/unknown]"]

    role = str(message.get("role") or "unknown").strip().lower() or "unknown"
    lines = [f"[{role}]"]

    if role == "assistant":
        for tool_call in message.get("tool_calls") or []:
            if not isinstance(tool_call, dict):
                continue
            fn = tool_call.get("function") if isinstance(tool_call.get("function"), dict) else {}
            raw_args = fn.get("arguments")
            params = raw_args
            if isinstance(raw_args, str):
                try:
                    params = json.loads(raw_args)
                except Exception:
                    params = raw_args
            payload = {
                "name": str(fn.get("name") or "").strip(),
                "parameters": params if isinstance(params, dict) else params or {},
            }
            lines.append(f"<tool_call>{json.dumps(payload, ensure_ascii=False)}</tool_call>")

    if role == "tool":
        tool_call_id = str(message.get("tool_call_id") or "").strip()
        if tool_call_id:
            lines.append(f"[tool_call_id={tool_call_id}]")

    content_text = _stringify_message_content(message.get("content"))
    if content_text:
        lines.append(content_text)
    lines.append(f"[/{role}]")
    return lines


def _stringify_message_content(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                if item.strip():
                    parts.append(item.strip())
                continue
            if not isinstance(item, dict):
                text = str(item or "").strip()
                if text:
                    parts.append(text)
                continue
            item_type = str(item.get("type") or "").strip().lower()
            if item_type == "text":
                text = str(item.get("text") or "").strip()
                if text:
                    parts.append(text)
            elif item_type == "image_url":
                image_url = item.get("image_url") if isinstance(item.get("image_url"), dict) else {}
                url = str(image_url.get("url") or "").strip()
                if url:
                    parts.append(f"[image] {url}")
        return "\n".join(parts).strip()
    if content is None:
        return ""
    return str(content).strip()
