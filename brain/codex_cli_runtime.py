"""Local Codex CLI transport for subscription-backed model access."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time


_CODEX_TRANSPORTS = {"codex_cli", "codex-subscription", "codex_subscription"}
_LOGIN_STATUS_CACHE = {"expires_at": 0.0, "result": (False, "")}


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

    codex_bin = shutil.which("codex")
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
    del temperature, max_tokens
    ok, detail = validate_codex_cli_login(timeout=min(timeout, 10))
    if not ok:
        return {"content": "", "usage": {}, "error": detail}

    codex_bin = shutil.which("codex")
    if not codex_bin:
        return {"content": "", "usage": {}, "error": "Local Codex CLI not found."}

    prompt = _render_codex_prompt(messages, tools=tools)
    sandbox = str(cfg.get("sandbox") or "read-only").strip().lower()
    if sandbox not in {"read-only", "workspace-write", "danger-full-access"}:
        sandbox = "read-only"
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
