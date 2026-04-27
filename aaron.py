from __future__ import annotations

import argparse
import asyncio
import contextlib
import getpass
import io
import json
import os
import queue
import shlex
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
from pathlib import Path
from urllib import error, request

if os.name == "nt":
    import msvcrt


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_BASE_URL = "http://127.0.0.1:8090"
DEFAULT_TIMEOUT = 10
CLI_VERSION = "0.3.0"
CHAT_WIDTH = 68
AARON_TAGLINE = "memory-first local agent shell"
WELCOME_RULE_WIDTH = 58
AARON_ASCII_LOGO: tuple[str, ...] = ()
SETUP_PROVIDER_ORDER = ("deepseek", "openai", "claude", "qwen", "minimax", "doubao", "glm", "kimi")
INTRO_FRAME_DELAY = 0.075
INTRO_HOLD_SECONDS = 0.45

ANSI = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "gray": "\033[90m",
}


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


class AaronCoreError(RuntimeError):
    pass


def should_color(stream=None, *, no_color: bool = False) -> bool:
    if no_color or os.environ.get("NO_COLOR") or os.environ.get("AARON_NO_COLOR"):
        return False
    if os.environ.get("AARON_FORCE_COLOR"):
        return True
    stream = stream or sys.stdout
    return bool(getattr(stream, "isatty", lambda: False)())


def paint(text: str, *styles: str, enabled: bool = True) -> str:
    if not enabled:
        return text
    prefix = "".join(ANSI.get(style, "") for style in styles)
    return f"{prefix}{text}{ANSI['reset']}" if prefix else text


def enable_virtual_terminal() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def model_config_status() -> dict:
    try:
        import brain
        from routes.models import _validate_api_model_config

        cfg = brain.get_current_llm_config()
        current = str(getattr(brain, "_current_default", "") or cfg.get("model") or "unknown")
        transport = str(cfg.get("transport") or "openai_api").strip().lower()
        if transport == "codex_cli":
            return {
                "ok": True,
                "needs_setup": False,
                "model": current,
                "summary": f"model ready: {current} via Codex CLI",
            }
        validation_error = _validate_api_model_config(cfg)
        if validation_error:
            return {
                "ok": False,
                "needs_setup": True,
                "model": current,
                "summary": f"setup needed: {validation_error}",
            }
        return {
            "ok": True,
            "needs_setup": False,
            "model": current,
            "summary": f"model ready: {current}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "needs_setup": True,
            "model": "unknown",
            "summary": f"setup check failed: {exc}",
        }


def startup_lines(*, health: dict | None, runtime_state: str, config_status: dict | None = None) -> list[str]:
    status = config_status or model_config_status()
    model = str((health or {}).get("current_model") or status.get("model") or "unknown")
    core_ready = bool((health or {}).get("core_ready"))
    runtime = "direct runtime" if runtime_state == "direct runtime" else runtime_state
    setup_line = "Ready to chat."
    command_line = "Type a message. /help for shortcuts."
    if status.get("needs_setup"):
        setup_line = "Model setup required before normal chat."
        command_line = "Run /setup now, or `aaron setup` from a normal terminal."
    return [
        f"AaronCore CLI v{CLI_VERSION}",
        "." * WELCOME_RULE_WIDTH,
        AARON_TAGLINE,
        "",
        f"model   {model}",
        f"runtime {runtime}",
        f"memory  {'core ready' if core_ready else 'core warming'}",
        f"config  {status.get('summary') or 'model status unknown'}",
        f"home    {compact_path(ROOT_DIR)}",
        "",
        setup_line,
        command_line,
    ]


def print_banner(*, health: dict | None, runtime_state: str, color: bool) -> None:
    status = model_config_status()
    for index, line in enumerate(startup_lines(health=health, runtime_state=runtime_state, config_status=status)):
        if index < len(AARON_ASCII_LOGO):
            print(paint(line, "cyan", "bold", enabled=color))
        elif line.startswith("AaronCore CLI"):
            print(paint(line, "cyan", "bold", enabled=color))
        elif "setup needed" in line or "setup check failed" in line or "setup required" in line:
            print(paint(line, "yellow", "bold", enabled=color))
        else:
            print(paint(line, "gray", enabled=color))


def print_shortcuts(*, color: bool) -> None:
    rows = [
        ("/help", "show shortcuts"),
        ("/setup", "configure model provider and API key"),
        ("/qq status", "check or stop QQ listening sessions"),
        ("/wechat status", "check or stop WeChat listening sessions"),
        ("/social list", "list social and communication handoff targets"),
        ("/status", "check local runtime"),
        ("/steps", "toggle verbose backend events"),
        ("/quiet", "toggle compact process lines"),
        ("/logs --lines 40", "tail recent logs"),
        ("/clear", "clear the terminal"),
        ("/exit", "leave AaronCore"),
    ]
    print()
    for command, detail in rows:
        print(paint(command.ljust(18), "cyan", "bold", enabled=color) + paint(detail, "gray", enabled=color))
    print()


def terminal_header(label: str, *, color: bool, style: str = "cyan", width: int = CHAT_WIDTH) -> str:
    label_text = f" {label} "
    available = max(2, width - len(label_text) - 2)
    return paint("+" + label_text + "-" * available + "+", style, "bold", enabled=color)


def terminal_footer(*, color: bool, width: int = CHAT_WIDTH) -> str:
    return paint("+" + "-" * max(2, width - 2) + "+", "gray", enabled=color)


def print_user_message(message: str, *, color: bool) -> None:
    print()
    print(terminal_header("You", color=color, style="green"))
    print(paint("| ", "green", enabled=color) + message)
    print(terminal_footer(color=color))


def read_shell_message(*, color: bool) -> str:
    print()
    print(terminal_header("You", color=color, style="green"))
    message = input(paint("| > ", "green", "bold", enabled=color))
    print(terminal_footer(color=color))
    return message.strip()


def compact_path(path: Path) -> str:
    try:
        home = Path.home().resolve()
        resolved = path.resolve()
        try:
            rel = resolved.relative_to(home)
            return "~" + os.sep + str(rel)
        except ValueError:
            return str(resolved)
    except Exception:
        return str(path)


def status_line(label: str, value: str, *, status: str = "info", color: bool = True) -> str:
    palette = {
        "ok": ("ok", "green"),
        "fail": ("fail", "red"),
        "warn": ("warn", "yellow"),
        "info": ("info", "cyan"),
    }
    badge, style = palette.get(status, palette["info"])
    return (
        paint(f"[{badge}]", style, "bold", enabled=color)
        + " "
        + paint(label.ljust(14), "gray", enabled=color)
        + " "
        + value
    )


def is_default_local_backend(client: "AaronCoreClient") -> bool:
    return client.base_url in {
        "http://127.0.0.1:8090",
        "http://localhost:8090",
    }


def try_health(client: "AaronCoreClient", *, timeout: int = 1) -> dict | None:
    try:
        health = client.get_json("/health", timeout=timeout)
    except AaronCoreError:
        return None
    return health if isinstance(health, dict) and health.get("status") else None


def start_backend_process(*, color: bool) -> subprocess.Popen | None:
    logs_dir = ROOT_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / "cli_backend.out.log"
    stderr_path = logs_dir / "cli_backend.err.log"
    env = os.environ.copy()
    env.setdefault("AARONCORE_ROOT", str(ROOT_DIR))
    env.setdefault("NOVACORE_ROOT", str(ROOT_DIR))
    env.setdefault("AARONCORE_DATA_DIR", str(ROOT_DIR))
    env.setdefault("NOVACORE_DATA_DIR", str(ROOT_DIR))

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    print(paint("starting ", "yellow", "bold", enabled=color) + "local AaronCore runtime...")
    with stdout_path.open("ab") as stdout, stderr_path.open("ab") as stderr:
        return subprocess.Popen(
            [sys.executable, str(ROOT_DIR / "agent_final.py")],
            cwd=str(ROOT_DIR),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            creationflags=creationflags,
        )


def ensure_backend(args: argparse.Namespace, *, color: bool) -> tuple[AaronCoreClient, dict | None, str]:
    client = build_client(args)
    if isinstance(client, DirectAaronCoreClient):
        try:
            health = client.get_json("/health", timeout=args.timeout)
        except AaronCoreError as exc:
            raise AaronCoreError(f"Direct AaronCore runtime failed to load: {exc}") from exc
        return client, health, "direct runtime"

    health = try_health(client, timeout=1)
    if health:
        return client, health, "ready"

    if getattr(args, "no_start", False) or not is_default_local_backend(client):
        return client, None, "offline"

    start_backend_process(color=color)
    deadline = time.time() + 35
    tick = 0
    while time.time() < deadline:
        health = try_health(client, timeout=2)
        if health:
            print(paint("ready ", "green", "bold", enabled=color) + "local runtime attached.")
            return client, health, "ready"
        tick += 1
        if tick % 4 == 0:
            print(paint(".", "gray", enabled=color), end="", flush=True)
        time.sleep(0.5)
    print()
    raise AaronCoreError(
        "AaronCore runtime did not become ready. Check logs/cli_backend.err.log and logs/cli_backend.out.log."
    )


class DirectAaronCoreClient:
    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = "direct"
        self.timeout = timeout
        self._runtime_loaded = False
        self._agent_final = None
        self._import_output = ""

    def _load_runtime(self) -> None:
        if self._runtime_loaded:
            return
        env = os.environ
        env.setdefault("AARONCORE_ROOT", str(ROOT_DIR))
        env.setdefault("NOVACORE_ROOT", str(ROOT_DIR))
        env.setdefault("AARONCORE_DATA_DIR", str(ROOT_DIR))
        env.setdefault("NOVACORE_DATA_DIR", str(ROOT_DIR))
        if str(ROOT_DIR) not in sys.path:
            sys.path.insert(0, str(ROOT_DIR))

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                import agent_final
        except Exception as exc:
            captured = (stdout_capture.getvalue() + stderr_capture.getvalue()).strip()
            detail = f"{exc}"
            if captured:
                detail = f"{detail}\n{captured}"
            raise AaronCoreError(detail) from exc

        self._agent_final = agent_final
        self._import_output = (stdout_capture.getvalue() + stderr_capture.getvalue()).strip()
        if os.environ.get("AARON_DEBUG_IMPORT") and self._import_output:
            print(self._import_output, file=sys.stderr)
        self._runtime_loaded = True

    @staticmethod
    def _run(coro):
        return asyncio.run(coro)

    def get_json(self, path: str, *, timeout: int | None = None) -> dict:
        self._load_runtime()
        normalized = path if path.startswith("/") else "/" + path
        if normalized == "/health":
            from routes.health import get_health

            result = self._run(get_health())
            return result if isinstance(result, dict) else {}
        raise AaronCoreError(f"Direct runtime does not expose {normalized}. Use --transport http for legacy HTTP endpoints.")

    def post_json(self, path: str, payload: dict, *, timeout: int | None = None) -> dict:
        self._load_runtime()
        normalized = path if path.startswith("/") else "/" + path
        if normalized == "/chat/answer":
            from routes.chat import ChatAnswerRequest, chat_answer

            result = self._run(chat_answer(ChatAnswerRequest(**payload)))
            return result if isinstance(result, dict) else {}
        raise AaronCoreError(f"Direct runtime does not expose {normalized}. Use --transport http for legacy HTTP endpoints.")

    def chat_events(self, message: str, *, ui_lang: str = "cli"):
        self._load_runtime()
        done = object()
        items: queue.Queue = queue.Queue()

        def worker() -> None:
            async def run_chat_stream() -> None:
                from fastapi import BackgroundTasks
                from routes.chat import ChatRequest, chat

                background_tasks = BackgroundTasks()
                response = await chat(ChatRequest(message=message, ui_lang=ui_lang), background_tasks)
                async for item in response.body_iterator:
                    items.put(normalize_direct_event(item))
                background = getattr(response, "background", None)
                if background is not None:
                    await background()

            try:
                asyncio.run(run_chat_stream())
            except BaseException as exc:
                items.put(exc)
            finally:
                items.put(done)

        thread = threading.Thread(target=worker, name="aaroncore-direct-chat", daemon=True)
        thread.start()

        while True:
            item = items.get()
            if item is done:
                break
            if isinstance(item, BaseException):
                raise AaronCoreError(str(item)) from item
            yield item

    def submit_answer(self, question_id: str, answer: str) -> bool:
        result = self.post_json("/chat/answer", {"question_id": question_id, "answer": answer})
        return bool(result.get("ok"))


class AaronCoreClient:
    def __init__(self, base_url: str | None = None, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = (base_url or os.environ.get("AARONCORE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        # Local agent traffic must not be hijacked by system HTTP proxies.
        self.opener = request.build_opener(request.ProxyHandler({}))

    def url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def get_json(self, path: str, *, timeout: int | None = None) -> dict:
        req = request.Request(
            self.url(path),
            method="GET",
            headers={"Accept": "application/json", "User-Agent": "AaronCore-CLI"},
        )
        try:
            with self.opener.open(req, timeout=timeout or self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
        except error.URLError as exc:
            raise AaronCoreError(f"Backend is not reachable at {self.base_url}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise AaronCoreError(f"Backend returned invalid JSON from {path}: {exc}") from exc

    def post_json(self, path: str, payload: dict, *, timeout: int | None = None) -> dict:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            self.url(path),
            data=data,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "AaronCore-CLI",
            },
        )
        try:
            with self.opener.open(req, timeout=timeout or self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
        except error.URLError as exc:
            raise AaronCoreError(f"Backend request failed at {self.base_url}{path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise AaronCoreError(f"Backend returned invalid JSON from {path}: {exc}") from exc

    def chat_events(self, message: str, *, ui_lang: str = "cli"):
        data = json.dumps({"message": message, "ui_lang": ui_lang}, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            self.url("/chat"),
            data=data,
            method="POST",
            headers={
                "Accept": "text/event-stream",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "AaronCore-CLI",
            },
        )
        try:
            with self.opener.open(req, timeout=None) as resp:
                yield from iter_sse_events(resp)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise AaronCoreError(f"/chat failed with HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise AaronCoreError(f"Backend is not reachable at {self.base_url}: {exc}") from exc

    def submit_answer(self, question_id: str, answer: str) -> bool:
        result = self.post_json("/chat/answer", {"question_id": question_id, "answer": answer})
        return bool(result.get("ok"))


def normalize_direct_event(item) -> tuple[str, str]:
    if isinstance(item, dict):
        event_name = str(item.get("event") or "message")
        data = item.get("data", "")
        if not isinstance(data, str):
            data = json.dumps(data, ensure_ascii=False)
        return event_name, data

    event_name = str(getattr(item, "event", "") or "message")
    data = getattr(item, "data", item)
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")
    elif not isinstance(data, str):
        data = json.dumps(data, ensure_ascii=False)
    return event_name, data


def iter_sse_events(resp):
    event_name = "message"
    data_lines: list[str] = []
    for raw_line in resp:
        line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line:
            if data_lines:
                yield event_name, "\n".join(data_lines)
            event_name = "message"
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        field, sep, value = line.partition(":")
        if not sep:
            continue
        if value.startswith(" "):
            value = value[1:]
        if field == "event":
            event_name = value or "message"
        elif field == "data":
            data_lines.append(value)
    if data_lines:
        yield event_name, "\n".join(data_lines)


class ChatPrinter:
    def __init__(
        self,
        *,
        show_steps: bool = False,
        compact_steps: bool = True,
        stream_reset_notice: bool = True,
        color: bool = False,
    ):
        self.show_steps = show_steps
        self.compact_steps = compact_steps
        self.stream_reset_notice = stream_reset_notice
        self.color = color
        self.printed_text = ""
        self.saw_stream = False
        self.assistant_started = False
        self.assistant_finished = False
        self.last_compact_step = ""

    def handle_event(self, event_name: str, data: str, client: AaronCoreClient) -> None:
        payload = parse_event_json(data)
        if event_name == "stream_reset":
            if self.stream_reset_notice and self.printed_text.strip():
                print(
                    "\n" + paint("[stream reset] restarting reply", "yellow", enabled=self.color) + "\n",
                    file=sys.stderr,
                )
            if self.assistant_started and not self.assistant_finished:
                self._finish_assistant_block()
            self.assistant_started = False
            self.assistant_finished = False
            self.printed_text = ""
            self.saw_stream = False
            return
        if event_name == "stream":
            self._print_stream_payload(payload)
            return
        if event_name == "reply":
            reply = str(payload.get("reply") or "")
            self._print_final_reply(reply)
            return
        if event_name == "ask_user":
            self._handle_ask_user(payload, client)
            return
        if self.show_steps and event_name not in {"message"}:
            print(format_step_event(event_name, payload, color=self.color), file=sys.stderr)
            return
        if self.compact_steps:
            self._print_compact_step(event_name, payload)

    def _print_stream_payload(self, payload: dict) -> None:
        self._ensure_assistant_block_started()
        full_text = payload.get("full_text")
        if isinstance(full_text, str):
            if full_text.startswith(self.printed_text):
                delta = full_text[len(self.printed_text) :]
            else:
                delta = "\n" + full_text
            self._write(delta)
            self.printed_text = full_text
            self.saw_stream = True
            return

        token = payload.get("token")
        if isinstance(token, str):
            self._write(token)
            self.printed_text += token
            self.saw_stream = True
            return

        append = payload.get("append")
        if isinstance(append, list):
            for item in append:
                if isinstance(item, dict):
                    markdown = str(item.get("markdown") or "")
                    if markdown:
                        self._write(markdown)
                        self.printed_text += markdown
                        self.saw_stream = True

    def _print_final_reply(self, reply: str) -> None:
        self._ensure_assistant_block_started()
        if reply.startswith(self.printed_text):
            self._write(reply[len(self.printed_text) :])
        elif not self.saw_stream:
            self._write(reply)
        elif reply.strip() and reply.strip() != self.printed_text.strip():
            self._write("\n" + reply)
        if reply:
            self.printed_text = reply
        if self.printed_text and not self.printed_text.endswith("\n"):
            print()
        self._finish_assistant_block()

    def _ensure_assistant_block_started(self) -> None:
        if self.assistant_started:
            return
        print()
        print(terminal_header("AaronCore", color=self.color, style="cyan"))
        self.assistant_started = True
        self.assistant_finished = False

    def _finish_assistant_block(self) -> None:
        if not self.assistant_started or self.assistant_finished:
            return
        print(terminal_footer(color=self.color))
        self.assistant_finished = True

    def _print_compact_step(self, event_name: str, payload: dict) -> None:
        if self.assistant_started or event_name not in {"trace", "agent_step", "plan"}:
            return
        line = format_compact_step_event(event_name, payload, color=self.color)
        if not line or line == self.last_compact_step:
            return
        self.last_compact_step = line
        print(line)

    def _handle_ask_user(self, payload: dict, client: AaronCoreClient) -> None:
        question_id = str(payload.get("id") or payload.get("question_id") or "").strip()
        question = first_text(payload, "question", "message", "prompt", "content", "text")
        if not question:
            question = "AaronCore needs your input."
        print("\n" + paint("? ", "cyan", "bold", enabled=self.color) + question, file=sys.stderr)
        options = payload.get("options") or payload.get("choices")
        if isinstance(options, list):
            for index, item in enumerate(options, 1):
                label = item.get("label") if isinstance(item, dict) else item
                print(paint(f"  {index}. ", "gray", enabled=self.color) + str(label), file=sys.stderr)
        if not question_id:
            print(paint("Cannot answer: backend did not provide a question id.", "red", enabled=self.color), file=sys.stderr)
            return
        try:
            answer = input(paint("> ", "cyan", enabled=self.color)).strip()
        except EOFError:
            answer = ""
        if not answer:
            print(paint("Skipped empty answer.", "yellow", enabled=self.color), file=sys.stderr)
            return
        if not client.submit_answer(question_id, answer):
            print(paint("Backend did not accept the answer.", "red", enabled=self.color), file=sys.stderr)

    def _write(self, text: str) -> None:
        if not text:
            return
        print(text, end="", flush=True)


def parse_event_json(data: str) -> dict:
    try:
        value = json.loads(data or "{}")
    except json.JSONDecodeError:
        return {"raw": data}
    return value if isinstance(value, dict) else {"value": value}


def first_text(payload: dict, *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def short_terminal_text(text: str, limit: int = 86) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def terminal_cell_width(text: str) -> int:
    width = 0
    for ch in str(text or ""):
        if unicodedata.combining(ch):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in {"F", "W"} else 1
    return width


def clip_terminal_cells(text: str, limit: int) -> str:
    out: list[str] = []
    width = 0
    for ch in str(text or ""):
        char_width = 0 if unicodedata.combining(ch) else (2 if unicodedata.east_asian_width(ch) in {"F", "W"} else 1)
        if width + char_width > limit:
            break
        out.append(ch)
        width += char_width
    return "".join(out)


def tail_terminal_cells(text: str, limit: int) -> str:
    out: list[str] = []
    width = 0
    for ch in reversed(str(text or "")):
        char_width = 0 if unicodedata.combining(ch) else (2 if unicodedata.east_asian_width(ch) in {"F", "W"} else 1)
        if width + char_width > limit:
            break
        out.append(ch)
        width += char_width
    return "".join(reversed(out))


def pad_terminal_cells(text: str, width: int) -> str:
    return str(text or "") + " " * max(0, width - terminal_cell_width(text))


def center_terminal_cells(text: str, width: int) -> str:
    text = str(text or "")
    padding = max(0, (width - terminal_cell_width(text)) // 2)
    return " " * padding + text


def wrap_terminal_cells(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for raw_line in str(text or "").splitlines() or [""]:
        current: list[str] = []
        current_width = 0
        for ch in raw_line:
            char_width = 0 if unicodedata.combining(ch) else (2 if unicodedata.east_asian_width(ch) in {"F", "W"} else 1)
            if current and current_width + char_width > width:
                lines.append("".join(current))
                current = [ch]
                current_width = char_width
            else:
                current.append(ch)
                current_width += char_width
        lines.append("".join(current))
    return lines or [""]


def format_compact_step_event(event_name: str, payload: dict, *, color: bool = False) -> str:
    if event_name == "plan":
        status = cli_display_detail(first_text(payload, "status", "stage", "state"))
        detail = cli_display_detail(first_text(payload, "summary", "title", "message", "detail"))
        if not status and not detail:
            return ""
        text = short_terminal_text(" ".join([p for p in [status, detail] if p]), 92)
        return paint("  plan ", "magenta", "bold", enabled=color) + paint(text, "gray", enabled=color)

    label = cli_display_label(first_text(payload, "label", "title", "name"))
    detail = cli_display_detail(first_text(payload, "detail", "message", "text", "full_detail"))
    phase = first_text(payload, "phase")
    status = first_text(payload, "status")
    if not label and phase == "complete":
        return ""
    if not label:
        label = phase or event_name
    if label in {"complete", "完成"} and not detail:
        return ""

    status_text = "ok" if status == "done" else ("!" if status == "error" else "..")
    style = "green" if status == "done" else ("red" if status == "error" else "yellow")
    head = paint(f"  {status_text} ", style, "bold", enabled=color)
    label_text = paint(label, "bold", enabled=color)
    if detail:
        return f"{head}{label_text}  {paint(short_terminal_text(detail), 'gray', enabled=color)}"
    return f"{head}{label_text}"


CLI_LABEL_EN = {
    "记忆加载": "Memory",
    "模型思考": "Thinking",
    "调用技能": "Tool",
    "技能完成": "Tool done",
    "技能失败": "Tool failed",
    "联网搜索": "Search",
    "搜索完成": "Search done",
    "搜索失败": "Search failed",
    "检索记忆": "Recall",
    "记忆就绪": "Memory ready",
    "检索失败": "Recall failed",
    "切换模型": "Model",
    "主链事故": "Runtime",
    "等待": "Waiting",
    "完成": "Done",
}

CLI_DETAIL_REPLACEMENTS = (
    ("正在读取最近对话、记忆和人格状态…", "loading recent dialogue, memory, and persona"),
    ("上下文载入完成", "context loaded"),
    ("首轮对话", "first turn"),
    ("记忆模块激活", "memory active"),
    ("人格图谱对齐", "persona aligned"),
    ("时间回忆已接入", "timeline recall attached"),
    ("判断是直接回答还是先调用工具", "deciding whether to answer or use tools"),
    ("正在等待模型继续输出", "waiting for model output"),
    ("正在继续分析下一步动作", "thinking through next step"),
    ("正在等待工具执行结果", "waiting for tool result"),
    ("这一轮更像是直接回应，不需要再调用工具。", "direct answer selected; no tool needed"),
    ("我会先结合当前对话上下文直接给出答复。", "answering from current context"),
    ("我先理解你这句", "understanding"),
    ("判断是直接回答还是先调用工具", "deciding whether to answer or use tools"),
    ("，判断是直接回答还是先调用工具。", "; deciding whether to answer or use tools"),
)


def cli_display_label(label: str) -> str:
    text = str(label or "").strip()
    return CLI_LABEL_EN.get(text, text)


def cli_display_detail(detail: str) -> str:
    text = str(detail or "").strip()
    if not text:
        return ""
    if "我先理解你这句" in text and "判断是直接回答还是先调用工具" in text:
        return "understanding the request; deciding whether to answer or use tools"
    for source, target in CLI_DETAIL_REPLACEMENTS:
        text = text.replace(source, target)
    text = text.replace("「", "\"").replace("」", "\"")
    return text


def format_step_event(event_name: str, payload: dict, *, color: bool = False) -> str:
    label = cli_display_label(first_text(payload, "label", "title", "name", "status"))
    detail = cli_display_detail(first_text(payload, "detail", "message", "text"))
    head = paint(f"[{event_name}]", "magenta", enabled=color)
    if label and detail:
        return f"{head} {paint(label, 'bold', enabled=color)}: {detail}"
    if label:
        return f"{head} {paint(label, 'bold', enabled=color)}"
    if detail:
        return f"{head} {detail}"
    return f"{head} {json.dumps(payload, ensure_ascii=False)}"


def can_use_tui(args: argparse.Namespace) -> bool:
    if getattr(args, "plain", False):
        return False
    if os.environ.get("AARON_PLAIN") or os.environ.get("AARONCORE_PLAIN"):
        return False
    if os.name != "nt":
        return False
    return bool(
        getattr(sys.stdin, "isatty", lambda: False)()
        and getattr(sys.stdout, "isatty", lambda: False)()
    )


class TerminalChatUI:
    def __init__(self, *, health: dict | None, runtime_state: str, color: bool, config_status: dict | None = None):
        self.health = health or {}
        self.runtime_state = runtime_state
        self.color = color
        self.config_status = config_status or model_config_status()
        self.blocks: list[dict] = [self._intro_block()]
        self.input_buffer = ""
        self.status = "ready"
        self.current_assistant_index: int | None = None
        self.last_process_key = ""
        self._active = False
        self._last_terminal_size: tuple[int, int] | None = None

    def _intro_block(self) -> dict:
        return {
            "role": "Intro",
            "text": "\n".join(startup_lines(health=self.health, runtime_state=self.runtime_state, config_status=self.config_status)),
        }

    def __enter__(self):
        enable_virtual_terminal()
        self._active = True
        self._write("\x1b[?1049h\x1b[2J\x1b[H\x1b[?25h")
        self.render_intro_animation()
        self.render()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._active = False
        self._write("\x1b[?25h\x1b[?1049l")

    @contextlib.contextmanager
    def suspended(self):
        was_active = self._active
        if was_active:
            self._active = False
            self._write("\x1b[?25h\x1b[?1049l")
        try:
            yield
        finally:
            if was_active:
                self._active = True
                self._write("\x1b[?1049h\x1b[2J\x1b[H\x1b[?25h")
                self.render()

    def _write(self, text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()

    def render_intro_animation(self) -> None:
        if os.environ.get("AARON_NO_INTRO") or os.environ.get("AARONCORE_NO_INTRO"):
            return
        if not self.color:
            return
        size = shutil.get_terminal_size((80, 24))
        width = max(52, min(size.columns, 120))
        height = max(14, size.lines)
        logo_lines = list(AARON_ASCII_LOGO)
        meta_lines = [
            f"AaronCore CLI v{CLI_VERSION}",
            "." * WELCOME_RULE_WIDTH,
            AARON_TAGLINE,
            "direct runtime / local memory / terminal-first",
        ]
        content_height = len(logo_lines) + len(meta_lines)
        top_padding = max(2, (height - content_height) // 2 - 1)

        def paint_intro(lines: list[str]) -> list[str]:
            painted: list[str] = []
            for index, line in enumerate(lines):
                centered = center_terminal_cells(line, width)
                if index < len(logo_lines):
                    painted.append(paint(centered, "cyan", "bold", enabled=self.color))
                elif not line:
                    painted.append("")
                elif line.startswith("AaronCore CLI"):
                    painted.append(paint(centered, "cyan", "bold", enabled=self.color))
                elif set(line) == {"."}:
                    painted.append(paint(centered, "gray", enabled=self.color))
                else:
                    painted.append(paint(centered, "gray", enabled=self.color))
            return painted

        full_content = [*logo_lines, *meta_lines]
        for visible_count in range(1, len(full_content) + 1):
            frame = [""] * top_padding + paint_intro(full_content[:visible_count])
            self._write("\x1b[H\x1b[J" + "\n".join(frame))
            time.sleep(INTRO_FRAME_DELAY)
        time.sleep(INTRO_HOLD_SECONDS)

    def add_user(self, text: str) -> None:
        self.blocks.append({"role": "You", "text": text})
        self.current_assistant_index = None
        self.render()

    def add_system(self, text: str) -> None:
        self.blocks.append({"role": "System", "text": text})
        self.current_assistant_index = None
        self.render()

    def set_status(self, text: str) -> None:
        self.status = short_terminal_text(text or "ready", 96)
        self.render()

    def add_process(self, text: str) -> None:
        text = str(text or "").strip()
        if not text:
            return
        self.status = "working"
        process_key = self._process_key(text)
        if process_key == self.last_process_key:
            self.render()
            return
        self.last_process_key = process_key
        if self.blocks and self.blocks[-1].get("role") == "Process" and self._process_key(self.blocks[-1].get("text")) == process_key:
            self.blocks[-1]["text"] = text
            self.render()
            return
        self.blocks.append({"role": "Process", "text": text})
        self.current_assistant_index = None
        self.render()

    def _process_key(self, text: str) -> str:
        text = " ".join(str(text or "").split())
        for marker in (" 1s", " 2s", " 3s", " 4s", " 5s", " 6s", " 7s", " 8s", " 9s"):
            if text.endswith(marker):
                text = text[: -len(marker)]
                break
        if text.startswith(".. Thinking"):
            return "thinking"
        return text

    def start_assistant(self) -> None:
        if self.current_assistant_index is not None:
            return
        self.blocks.append({"role": "AaronCore", "text": ""})
        self.current_assistant_index = len(self.blocks) - 1
        self.render()

    def append_assistant(self, text: str) -> None:
        if not text:
            return
        self.start_assistant()
        if self.current_assistant_index is None:
            return
        self.blocks[self.current_assistant_index]["text"] += text
        self.render()

    def set_assistant_text(self, text: str) -> None:
        self.start_assistant()
        if self.current_assistant_index is None:
            return
        self.blocks[self.current_assistant_index]["text"] = text
        self.render()

    def finish_assistant(self) -> None:
        self.current_assistant_index = None
        self.status = "ready"
        self.render()

    def clear(self) -> None:
        self.blocks = [self._intro_block()]
        self.current_assistant_index = None
        self.status = "ready"
        self.render()

    def read_message(self) -> str:
        self.input_buffer = ""
        self.status = "ready"
        self.render()
        while True:
            if os.name == "nt" and not msvcrt.kbhit():
                self.render_if_resized()
                time.sleep(0.05)
                continue
            ch = msvcrt.getwch()
            if ch in {"\x00", "\xe0"}:
                msvcrt.getwch()
                continue
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch in {"\r", "\n"}:
                message = self.input_buffer.strip()
                if message:
                    self.input_buffer = ""
                    self.render()
                    return message
                self.render()
                continue
            if ch == "\x08":
                self.input_buffer = self.input_buffer[:-1]
                self.render()
                continue
            if ch == "\x15":
                self.input_buffer = ""
                self.render()
                continue
            if ch == "\x1b":
                continue
            if ch == "\t":
                ch = "    "
            if ch >= " ":
                self.input_buffer += ch
                self.render()

    def render_if_resized(self) -> None:
        size = shutil.get_terminal_size((80, 24))
        current_size = (size.columns, size.lines)
        if current_size != self._last_terminal_size:
            self.render()

    def render(self) -> None:
        if not self._active:
            return
        size = shutil.get_terminal_size((80, 24))
        self._last_terminal_size = (size.columns, size.lines)
        width = max(52, min(size.columns, 120))
        height = max(14, size.lines)
        header_lines = self._header_lines(width)
        prompt_lines, cursor_col = self._prompt_lines(width)
        fixed_count = len(header_lines) + len(prompt_lines)
        body_height = max(3, height - fixed_count)
        body_lines = self._body_lines(width, body_height=body_height)
        if len(body_lines) <= body_height:
            visible_body = list(body_lines)
            while len(visible_body) < body_height:
                visible_body.append("")
        else:
            visible_body = body_lines[-body_height:]

        lines = []
        lines.extend(header_lines)
        lines.extend(visible_body)
        lines.extend(prompt_lines)
        lines = lines[:height]

        self._write("\x1b[?25l\x1b[H\x1b[J" + "\n".join(lines))
        # Keep the cursor on the prompt content line, not on the bottom border.
        cursor_row = max(1, len(lines) - 1)
        self._write(f"\x1b[{cursor_row};{cursor_col}H\x1b[?25h")

    def _header_lines(self, width: int) -> list[str]:
        return []

    def _body_lines(self, width: int, *, body_height: int | None = None) -> list[str]:
        lines: list[str] = []
        for block in self.blocks:
            role = str(block.get("role") or "")
            text = str(block.get("text") or "")
            lines.extend(self._block_lines(role, text, width, body_height=body_height))
        return lines

    def _block_lines(self, role: str, text: str, width: int, *, body_height: int | None = None) -> list[str]:
        if role == "Intro":
            lines = []
            parts = str(text or "").splitlines()
            if body_height is not None and body_height < len(parts) + 1:
                parts = self._compact_intro_parts(body_height)
            for index, part in enumerate(parts):
                clipped = clip_terminal_cells(part, width)
                if part in AARON_ASCII_LOGO or part.startswith("AaronCore CLI") or part == "AaronCore":
                    lines.append(paint(clipped, "cyan", "bold", enabled=self.color))
                elif set(part) == {"."}:
                    lines.append(paint(clipped, "gray", enabled=self.color))
                elif "setup needed" in part or "setup check failed" in part or "setup required" in part:
                    lines.append(paint(clipped, "yellow", "bold", enabled=self.color))
                else:
                    lines.append(paint(clipped, "gray", enabled=self.color))
            return [*lines, ""]

        if role == "Process":
            return [paint("  " + clip_terminal_cells(text, width - 2), "gray", enabled=self.color)]

        if role == "You":
            wrapped = self._wrap_text(text, max(10, width - 2))
            lines = [
                paint("> ", "green", "bold", enabled=self.color) + wrapped[0],
            ]
            lines.extend("  " + line for line in wrapped[1:])
            return ["", *lines]

        if role == "AaronCore":
            wrapped = self._wrap_text(text, max(10, width - 2))
            if not any(line.strip() for line in wrapped):
                return []
            lines = []
            for index, line in enumerate(wrapped):
                marker = "● " if index == 0 else "  "
                lines.append(paint(marker, "cyan", "bold", enabled=self.color) + line)
            return ["", *lines]

        wrapped = self._wrap_text(text, max(10, width - 2))
        lines = [paint("!", "yellow", "bold", enabled=self.color) + " " + wrapped[0]]
        lines.extend("  " + line for line in wrapped[1:])
        return ["", *lines]

    def _compact_intro_parts(self, body_height: int) -> list[str]:
        status = self.config_status or {}
        model = str(self.health.get("current_model") or status.get("model") or "unknown")
        runtime = "direct runtime" if self.runtime_state == "direct runtime" else self.runtime_state
        lines = [
            f"AaronCore CLI v{CLI_VERSION}",
            "." * 28,
            AARON_TAGLINE,
            f"model   {model}",
            f"runtime {runtime}",
            f"config  {status.get('summary') or 'model status unknown'}",
            "",
            "Type a message. /help for shortcuts.",
        ]
        if status.get("needs_setup"):
            lines[-1] = "Run /setup now, or `aaron setup` from a normal terminal."
        return lines[: max(1, body_height - 1)]

    def _wrap_text(self, text: str, width: int) -> list[str]:
        return wrap_terminal_cells(text, width)

    def _status_line(self, width: int) -> str:
        text = short_terminal_text(self.status or "ready", width - 9)
        return paint("status ", "yellow", "bold", enabled=self.color) + paint(text.ljust(width - 7), "gray", enabled=self.color)

    def _prompt_lines(self, width: int) -> tuple[list[str], int]:
        available = max(8, width - 2)
        display = tail_terminal_cells(self.input_buffer, available)
        prompt = paint("> ", "green", "bold", enabled=self.color) + display
        prompt = prompt + " " * max(0, width - 2 - terminal_cell_width(display))
        hint_left = "? /help for shortcuts"
        hint_right = clip_terminal_cells(self.status or "ready", max(10, width // 2))
        gap = max(1, width - len(hint_left) - len(hint_right))
        hint_text = (hint_left + " " * gap + hint_right)[:width]
        hint = paint(hint_text, "gray", enabled=self.color)
        cursor_col = min(width, 3 + terminal_cell_width(display))
        return [paint("-" * width, "gray", enabled=self.color), prompt, hint], cursor_col


class TuiChatPrinter:
    def __init__(self, ui: TerminalChatUI, *, show_steps: bool = False, compact_steps: bool = True):
        self.ui = ui
        self.show_steps = show_steps
        self.compact_steps = compact_steps
        self.printed_text = ""
        self.saw_stream = False

    def handle_event(self, event_name: str, data: str, client: AaronCoreClient) -> None:
        payload = parse_event_json(data)
        if event_name == "stream_reset":
            self.printed_text = ""
            self.saw_stream = False
            self.ui.finish_assistant()
            self.ui.add_process("stream reset: restarting reply")
            return
        if event_name == "stream":
            self._handle_stream(payload)
            return
        if event_name == "reply":
            reply = str(payload.get("reply") or "")
            self._handle_reply(reply)
            return
        if event_name == "ask_user":
            self._handle_ask_user(payload, client)
            return
        if self.show_steps:
            self._add_process(format_step_event(event_name, payload, color=False), persist=True)
            return
        if self.compact_steps and event_name in {"trace", "agent_step", "plan"}:
            self._add_process(format_compact_step_event(event_name, payload, color=False))

    def _add_process(self, text: str, *, persist: bool = False) -> None:
        text = str(text or "").strip()
        if not text:
            return
        if not persist and self._is_ephemeral_process(text):
            self.ui.set_status(text)
            return
        if self.saw_stream or self.ui.current_assistant_index is not None:
            return
        if self.ui.blocks and self.ui.blocks[-1].get("role") == "AaronCore":
            return
        self.ui.add_process(text)

    def _is_ephemeral_process(self, text: str) -> bool:
        normalized = " ".join(str(text or "").split())
        if normalized.startswith((".. Memory", "ok Memory", ".. Thinking", "ok Thinking")):
            return True
        if normalized.startswith((".. Waiting", "ok Waiting")):
            return True
        return False

    def _handle_stream(self, payload: dict) -> None:
        full_text = payload.get("full_text")
        if isinstance(full_text, str):
            self.ui.set_assistant_text(full_text)
            self.printed_text = full_text
            self.saw_stream = True
            return

        token = payload.get("token")
        if isinstance(token, str):
            self.ui.append_assistant(token)
            self.printed_text += token
            self.saw_stream = True
            return

        append = payload.get("append")
        if isinstance(append, list):
            for item in append:
                if isinstance(item, dict):
                    markdown = str(item.get("markdown") or "")
                    if markdown:
                        self.ui.append_assistant(markdown)
                        self.printed_text += markdown
                        self.saw_stream = True

    def _handle_reply(self, reply: str) -> None:
        if not self.saw_stream:
            self.ui.set_assistant_text(reply)
        elif reply and reply.strip() != self.printed_text.strip():
            self.ui.set_assistant_text(reply)
        self.printed_text = reply or self.printed_text
        self.ui.finish_assistant()

    def _handle_ask_user(self, payload: dict, client: AaronCoreClient) -> None:
        question_id = str(payload.get("id") or payload.get("question_id") or "").strip()
        question = first_text(payload, "question", "message", "prompt", "content", "text")
        if not question:
            question = "AaronCore needs your input."
        options = payload.get("options") or payload.get("choices")
        if isinstance(options, list):
            rendered_options = []
            for index, item in enumerate(options, 1):
                label = item.get("label") if isinstance(item, dict) else item
                rendered_options.append(f"{index}. {label}")
            if rendered_options:
                question = question + "\n" + "\n".join(rendered_options)
        self.ui.add_system(question)
        if not question_id:
            self.ui.add_system("Cannot answer: backend did not provide a question id.")
            return
        try:
            answer = self.ui.read_message().strip()
        except KeyboardInterrupt:
            self.ui.add_system("Skipped.")
            return
        if not answer:
            self.ui.add_system("Skipped empty answer.")
            return
        self.ui.add_user(answer)
        if not client.submit_answer(question_id, answer):
            self.ui.add_system("Backend did not accept the answer.")


def run_chat_tui(
    ui: TerminalChatUI,
    client: AaronCoreClient,
    message: str,
    *,
    show_steps: bool = False,
    compact_steps: bool = True,
) -> int:
    printer = TuiChatPrinter(ui, show_steps=show_steps, compact_steps=compact_steps)
    try:
        for event_name, data in client.chat_events(message):
            printer.handle_event(event_name, data, client)
    except KeyboardInterrupt:
        ui.add_system("Interrupted.")
        return 130
    except AaronCoreError as exc:
        ui.add_system(str(exc))
        return 1
    return 0


def run_chat(
    client: AaronCoreClient,
    message: str,
    *,
    show_steps: bool = False,
    compact_steps: bool = True,
    color: bool = False,
) -> int:
    printer = ChatPrinter(show_steps=show_steps, compact_steps=compact_steps, color=color)
    try:
        for event_name, data in client.chat_events(message):
            printer.handle_event(event_name, data, client)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except AaronCoreError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def command_shell_tui(args: argparse.Namespace) -> int:
    color = should_color(sys.stdout, no_color=args.no_color)
    try:
        client, health, runtime_state = ensure_backend(args, color=color)
    except AaronCoreError as exc:
        print(status_line("runtime", str(exc), status="fail", color=color), file=sys.stderr)
        return 1

    with TerminalChatUI(health=health, runtime_state=runtime_state, color=color, config_status=model_config_status()) as ui:
        while True:
            try:
                message = ui.read_message()
            except EOFError:
                return 0
            except KeyboardInterrupt:
                return 130
            if not message:
                continue
            if message in {"/exit", "/quit"}:
                return 0
            if message in {"/help", "?"}:
                ui.add_system(
                    "/help        show shortcuts\n"
                    "/setup       configure model provider and API key\n"
                    "/qq status   check QQ listening state\n"
                    "/qq stop     stop QQ listening in this AaronCore session\n"
                    "             start by saying: 帮我监听 QQ 群「群名」\n"
                    "/wechat status check WeChat listening state\n"
                    "/wechat stop   stop WeChat listening in this AaronCore session\n"
                    "               start by saying: 帮我监听微信「聊天名」\n"
                    "/social list   list social/communication platform targets\n"
                    "/social open Slack  open a platform handoff entry\n"
                    "/mcp         manage MCP servers\n"
                    "/status      check local runtime\n"
                    "/steps       toggle verbose backend events\n"
                    "/quiet       toggle compact process lines\n"
                    "/logs        show recent logs\n"
                    "/clear       clear this terminal view\n"
                    "/exit        leave AaronCore\n"
                    "--plain      launch the simple non-TUI terminal mode"
                )
                continue
            if message == "/setup":
                with ui.suspended():
                    code = command_setup(args)
                    print()
                    try:
                        input("Press Enter to return to AaronCore...")
                    except EOFError:
                        pass
                ui.config_status = model_config_status()
                ui.clear()
                ui.add_system("model setup finished" if code == 0 else "model setup did not complete")
                continue
            if message == "/mcp" or message.startswith("/mcp "):
                with ui.suspended():
                    try:
                        mcp_args = build_parser().parse_args(["mcp", *shlex.split(message)[1:]])
                        code = command_mcp(mcp_args)
                    except SystemExit:
                        code = 2
                        print("Usage: /mcp [list|add|search|install|connect|disconnect|remove]")
                    print()
                    try:
                        input("Press Enter to return to AaronCore...")
                    except EOFError:
                        pass
                ui.clear()
                ui.add_system("MCP command finished" if code == 0 else "MCP command did not complete")
                continue
            if message == "/qq" or message.startswith("/qq "):
                with ui.suspended():
                    try:
                        qq_args = build_parser().parse_args(["qq", *shlex.split(message)[1:]])
                        code = command_qq(qq_args)
                    except SystemExit:
                        code = 2
                        print("Usage: /qq [status|stop|logs]")
                    print()
                    try:
                        input("Press Enter to return to AaronCore...")
                    except EOFError:
                        pass
                ui.clear()
                ui.add_system("QQ command finished" if code == 0 else "QQ command did not complete")
                continue
            if message == "/wechat" or message.startswith("/wechat ") or message == "/wx" or message.startswith("/wx ") or message == "/微信" or message.startswith("/微信 "):
                with ui.suspended():
                    try:
                        parts = shlex.split(message)
                        wechat_args = build_parser().parse_args(["wechat", *parts[1:]])
                        code = command_wechat(wechat_args)
                    except SystemExit:
                        code = 2
                        print("Usage: /wechat [status|stop|logs]")
                    print()
                    try:
                        input("Press Enter to return to AaronCore...")
                    except EOFError:
                        pass
                ui.clear()
                ui.add_system("WeChat command finished" if code == 0 else "WeChat command did not complete")
                continue
            if message == "/social" or message.startswith("/social ") or message == "/comm" or message.startswith("/comm "):
                with ui.suspended():
                    try:
                        parts = shlex.split(message)
                        social_args = build_parser().parse_args(["social", *parts[1:]])
                        code = command_social(social_args)
                    except SystemExit:
                        code = 2
                        print("Usage: /social [list|open <platform>]")
                    print()
                    try:
                        input("Press Enter to return to AaronCore...")
                    except EOFError:
                        pass
                ui.clear()
                ui.add_system("Social command finished" if code == 0 else "Social command did not complete")
                continue
            if message in {"/steps", "/verbose"}:
                args.steps = not bool(args.steps)
                ui.add_system("steps: verbose" if args.steps else "steps: compact")
                continue
            if message == "/quiet":
                args.quiet = not bool(args.quiet)
                ui.add_system("process lines: hidden" if args.quiet else "process lines: compact")
                continue
            if message in {"/doctor", "/status"}:
                try:
                    latest_health = client.get_json("/health", timeout=3)
                    ui.add_system(
                        f"/health: {latest_health.get('status', 'unknown')}\n"
                        f"core_ready: {latest_health.get('core_ready')}\n"
                        f"model: {latest_health.get('current_model')}\n"
                        f"state_dir: {latest_health.get('state_dir')}"
                    )
                except AaronCoreError as exc:
                    ui.add_system(f"runtime check failed: {exc}")
                continue
            if message == "/clear":
                ui.clear()
                continue
            if message.startswith("/logs"):
                try:
                    logs_args = build_parser().parse_args(["logs", *shlex.split(message)[1:]])
                except SystemExit:
                    ui.add_system("Usage: /logs --lines 40")
                    continue
                files = discover_log_files()
                target = Path(logs_args.file).expanduser() if logs_args.file else (files[0] if files else None)
                if not target:
                    ui.add_system("No log files found.")
                    continue
                try:
                    ui.add_system(f"==> {target}\n{tail_text(target, logs_args.lines)}")
                except AaronCoreError as exc:
                    ui.add_system(str(exc))
                continue

            ui.add_user(message)
            code = run_chat_tui(ui, client, message, show_steps=args.steps, compact_steps=not args.quiet)
            if code not in {0, 130}:
                return code


def command_shell(args: argparse.Namespace) -> int:
    if can_use_tui(args):
        return command_shell_tui(args)

    color = should_color(sys.stdout, no_color=args.no_color)
    try:
        client, health, runtime_state = ensure_backend(args, color=color)
    except AaronCoreError as exc:
        print(status_line("runtime", str(exc), status="fail", color=color), file=sys.stderr)
        return 1
    print_banner(health=health, runtime_state=runtime_state, color=color)
    while True:
        try:
            message = read_shell_message(color=color)
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            return 130
        if not message:
            continue
        if message in {"/exit", "/quit"}:
            return 0
        if message in {"/help", "?"}:
            print_shortcuts(color=color)
            continue
        if message == "/setup":
            command_setup(args)
            continue
        if message == "/qq" or message.startswith("/qq "):
            try:
                qq_args = build_parser().parse_args(["qq", *shlex.split(message)[1:]])
            except SystemExit:
                print("Usage: /qq [status|stop|logs]")
                continue
            qq_args.no_color = args.no_color
            command_qq(qq_args)
            continue
        if message == "/wechat" or message.startswith("/wechat ") or message == "/wx" or message.startswith("/wx ") or message == "/微信" or message.startswith("/微信 "):
            try:
                parts = shlex.split(message)
                wechat_args = build_parser().parse_args(["wechat", *parts[1:]])
            except SystemExit:
                print("Usage: /wechat [status|stop|logs]")
                continue
            wechat_args.no_color = args.no_color
            command_wechat(wechat_args)
            continue
        if message == "/social" or message.startswith("/social ") or message == "/comm" or message.startswith("/comm "):
            try:
                parts = shlex.split(message)
                social_args = build_parser().parse_args(["social", *parts[1:]])
            except SystemExit:
                print("Usage: /social [list|open <platform>]")
                continue
            social_args.no_color = args.no_color
            command_social(social_args)
            continue
        if message in {"/steps", "/verbose"}:
            args.steps = not bool(args.steps)
            print(status_line("steps", "verbose" if args.steps else "compact", status="ok", color=color))
            continue
        if message == "/quiet":
            args.quiet = not bool(args.quiet)
            print(status_line("process", "hidden" if args.quiet else "compact", status="ok", color=color))
            continue
        if message in {"/doctor", "/status"}:
            command_doctor(args)
            continue
        if message == "/clear":
            os.system("cls" if os.name == "nt" else "clear")
            print_banner(health=try_health(client, timeout=1), runtime_state="ready", color=color)
            continue
        if message.startswith("/logs"):
            try:
                logs_args = build_parser().parse_args(["logs", *shlex.split(message)[1:]])
            except SystemExit:
                continue
            logs_args.no_color = args.no_color
            command_logs(logs_args)
            continue
        code = run_chat(client, message, show_steps=args.steps, compact_steps=not args.quiet, color=color)
        if code not in {0, 130}:
            return code


def command_run(args: argparse.Namespace) -> int:
    message = " ".join(args.message).strip()
    if not message:
        print("Usage: aaron run \"your message\"", file=sys.stderr)
        return 2
    color = should_color(sys.stdout, no_color=args.no_color)
    try:
        client, _, _ = ensure_backend(args, color=color)
    except AaronCoreError as exc:
        print(status_line("runtime", str(exc), status="fail", color=color), file=sys.stderr)
        return 1
    if color:
        print(paint("AaronCore", "cyan", "bold", enabled=color) + paint(" running one-shot", "gray", enabled=color))
    print_user_message(message, color=color)
    code = run_chat(client, message, show_steps=args.steps, compact_steps=not args.quiet, color=color)
    if code == 0 and getattr(sys.stdin, "isatty", lambda: False)():
        print(
            paint("tip ", "yellow", "bold", enabled=color)
            + "use `aaron chat` or just `aaron` for a continuous conversation.",
            file=sys.stderr,
        )
    return code


def command_doctor(args: argparse.Namespace) -> int:
    client = build_client(args)
    color = should_color(sys.stdout, no_color=args.no_color)
    print(paint("AaronCore CLI doctor", "bold", "cyan", enabled=color))
    print(status_line("transport", getattr(client, "base_url", "direct"), color=color))
    ok = True
    try:
        health = client.get_json("/health", timeout=3)
        print(status_line("/health", str(health.get("status", "unknown")), status="ok", color=color))
        print(status_line("core_ready", str(health.get("core_ready")), status="ok" if health.get("core_ready") else "warn", color=color))
        print(status_line("model", str(health.get("current_model")), color=color))
        print(status_line("state_dir", str(health.get("state_dir")), color=color))
    except AaronCoreError as exc:
        ok = False
        print(status_line("/health", str(exc), status="fail", color=color))
        print(status_line("hint", "try `aaron doctor --transport http` for the legacy localhost path", status="warn", color=color))

    setup_status = model_config_status()
    ok = ok and not bool(setup_status.get("needs_setup"))
    print(
        status_line(
            "model_config",
            str(setup_status.get("summary") or "unknown"),
            status="ok" if not setup_status.get("needs_setup") else "warn",
            color=color,
        )
    )

    required = ["agent_final.py", "routes/chat.py", "memory", "state_data"]
    for rel in required:
        path = ROOT_DIR / rel
        exists = path.exists()
        ok = ok and exists
        print(status_line(rel, "ok" if exists else "missing", status="ok" if exists else "fail", color=color))
    return 0 if ok else 1


def command_memory_search(args: argparse.Namespace) -> int:
    query = " ".join(args.query).strip()
    if not query:
        print("Usage: aaron memory search \"query\"", file=sys.stderr)
        return 2
    message = (
        "Search AaronCore memory for the following query and return the most relevant "
        "items with memory layer, source, and time if available. Do not browse the web.\n\n"
        f"Query: {query}"
    )
    color = should_color(sys.stdout, no_color=args.no_color)
    try:
        client, _, _ = ensure_backend(args, color=color)
    except AaronCoreError as exc:
        print(status_line("runtime", str(exc), status="fail", color=color), file=sys.stderr)
        return 1
    print_user_message(message, color=color)
    return run_chat(client, message, show_steps=args.steps, compact_steps=not args.quiet, color=color)


def command_logs(args: argparse.Namespace) -> int:
    color = should_color(sys.stdout, no_color=args.no_color)
    files = discover_log_files()
    if args.list:
        if not files:
            print("No log files found.")
            return 1
        for path in files:
            print(paint("- ", "gray", enabled=color) + str(path))
        return 0

    target = Path(args.file).expanduser() if args.file else (files[0] if files else None)
    if not target:
        print("No log files found.", file=sys.stderr)
        return 1
    if not target.exists():
        print(f"Log file not found: {target}", file=sys.stderr)
        return 1
    print(paint("==> ", "cyan", "bold", enabled=color) + paint(str(target), "gray", enabled=color))
    print(tail_text(target, args.lines), end="")
    return 0


def discover_log_files() -> list[Path]:
    roots = []
    for key in ("AARONCORE_DATA_DIR", "NOVACORE_DATA_DIR"):
        raw = os.environ.get(key)
        if raw:
            roots.append(Path(raw).expanduser())
    roots.append(ROOT_DIR)

    candidates: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        for directory in (root / "logs", root / "state_data" / "runtime_store"):
            if not directory.exists():
                continue
            for pattern in ("*.log", "*.jsonl", "*.txt"):
                for path in directory.glob(pattern):
                    resolved = path.resolve()
                    if resolved not in seen and path.is_file():
                        seen.add(resolved)
                        candidates.append(path)
    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates


def tail_text(path: Path, lines: int) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise AaronCoreError(f"Cannot read log file {path}: {exc}") from exc
    selected = content.splitlines()[-max(lines, 1) :]
    return "\n".join(selected) + ("\n" if selected else "")


def prompt_text(label: str, *, default: str = "", required: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{label}{suffix}: ").strip()
        if value:
            return value
        if default:
            return default
        if not required:
            return ""
        print("This value is required.")


def prompt_choice(title: str, choices: list[tuple[str, str]], *, default: int = 1, color: bool = True) -> str:
    print()
    print(paint(title, "cyan", "bold", enabled=color))
    for index, (_value, label) in enumerate(choices, 1):
        print(f"  {index}. {label}")
    while True:
        value = input(f"Choose [{default}]: ").strip()
        if not value:
            return choices[default - 1][0]
        if value.isdigit():
            index = int(value)
            if 1 <= index <= len(choices):
                return choices[index - 1][0]
        lowered = value.lower()
        for choice_value, label in choices:
            if lowered == choice_value.lower() or lowered == label.lower():
                return choice_value
        print("Please choose one of the listed options.")


def ask_yes_no(question: str, *, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    value = input(f"{question} [{suffix}]: ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes"}


def prompt_api_key(*, existing: bool) -> str:
    label = "API key (input hidden"
    if existing:
        label += ", Enter keeps the saved key"
    label += ")"
    while True:
        value = getpass.getpass(label + ": ").strip()
        if value:
            return value
        if existing:
            return ""
        print("API key is required for this provider.")


def provider_catalog() -> dict:
    from routes.chat_model_switch import PROVIDER_CATALOG

    return PROVIDER_CATALOG


def find_existing_model_id(models_config: dict, *, model_name: str, provider_key: str = "") -> str:
    from core import model_provider_config

    target = str(model_name or "").strip().lower()
    provider_key = str(provider_key or "").strip().lower()
    if not target:
        return ""
    for model_id, cfg in (models_config or {}).items():
        cfg = cfg if isinstance(cfg, dict) else {}
        existing_model = str(cfg.get("model") or model_id or "").strip().lower()
        if existing_model != target:
            continue
        existing_provider = model_provider_config.infer_provider_key(str(model_id), cfg)
        if not provider_key or not existing_provider or existing_provider == provider_key:
            return str(model_id)
    return ""


def save_cli_model_config(model_id: str, cfg: dict) -> dict:
    import brain
    from core import model_provider_config

    normalized = model_provider_config.normalize_model_config(cfg, fallback_model=model_id)
    raw_config = dict(getattr(brain, "_raw_config", {}) or {})
    models = dict(raw_config.get("models") or getattr(brain, "MODELS_CONFIG", {}) or {})
    models[model_id] = normalized
    raw_config["models"] = models
    raw_config["default"] = model_id
    brain.save_raw_config(raw_config)
    return normalized


def command_setup(args: argparse.Namespace) -> int:
    color = should_color(sys.stdout, no_color=getattr(args, "no_color", False))
    print()
    print(paint("AaronCore model setup", "cyan", "bold", enabled=color))
    print(paint("Keys stay local and are written to the ignored local config file.", "gray", enabled=color))
    print(paint("Flow: provider -> model -> hidden API key -> optional connection test.", "gray", enabled=color))

    try:
        import brain
        from routes.models import _probe_api_model, _validate_api_model_config
        from storage.paths import LLM_LOCAL_CONFIG_FILE
    except Exception as exc:
        print(status_line("setup", f"cannot load model config runtime: {exc}", status="fail", color=color))
        return 1

    status = model_config_status()
    print(status_line("current", str(status.get("summary") or "unknown"), status="ok" if not status.get("needs_setup") else "warn", color=color))

    catalog = provider_catalog()
    provider_choices = []
    for key in SETUP_PROVIDER_ORDER:
        info = catalog.get(key)
        if not info:
            continue
        models = ", ".join(mid for mid, _desc in info.get("models", [])[:2])
        provider_choices.append((key, f"{key} ({models})"))
    provider_choices.extend(
        [
            ("custom", "custom OpenAI-compatible endpoint"),
            ("codex_cli", "Codex CLI login (no API key stored by AaronCore)"),
        ]
    )
    provider_key = prompt_choice("Step 1/4  Provider", provider_choices, default=1, color=color)

    if provider_key == "codex_cli":
        model_id = prompt_choice(
            "Step 2/4  Codex CLI model",
            [
                ("gpt-5.4", "gpt-5.4"),
                ("gpt-5.4-mini", "gpt-5.4-mini"),
                ("gpt-4o", "gpt-4o"),
            ],
            default=1,
            color=color,
        )
        cfg = {
            "model": model_id,
            "base_url": "codex://local",
            "transport": "codex_cli",
            "auth_mode": "codex_cli",
            "api_mode": "codex_cli",
            "provider_key": "openai",
            "vision": False,
        }
        save_cli_model_config(model_id, cfg)
        print(status_line("saved", f"{model_id} is now the default model", status="ok", color=color))
        print(status_line("next", "run `aaroncore` to start chatting", status="ok", color=color))
        if getattr(args, "test", False) or ask_yes_no("Validate the local Codex CLI login now?", default=False):
            ok, detail = brain.validate_codex_cli_login(timeout=10)
            print(status_line("test", detail, status="ok" if ok else "fail", color=color))
            return 0 if ok else 1
        return 0

    models_config = getattr(brain, "MODELS_CONFIG", {}) or {}
    if provider_key == "custom":
        print()
        print(paint("Step 2/4  Custom model", "cyan", "bold", enabled=color))
        model_name = prompt_text("Model id", required=True)
        base_url = prompt_text("Base URL", required=True).rstrip("/")
        model_id = find_existing_model_id(models_config, model_name=model_name) or model_name
        existing_cfg = models_config.get(model_id, {}) if isinstance(models_config.get(model_id), dict) else {}
        print()
        print(paint("Step 3/4  API key", "cyan", "bold", enabled=color))
        key_value = prompt_api_key(existing=bool(existing_cfg.get("api_key")))
        api_key = key_value or str(existing_cfg.get("api_key") or "")
        cfg = {
            "model": model_name,
            "base_url": base_url,
            "api_key": api_key,
            "transport": "openai_api",
            "vision": False,
        }
    else:
        info = catalog[provider_key]
        model_choices = [(mid, f"{mid} - {desc}") for mid, desc in info.get("models", [])]
        model_choices.append(("custom", "custom model id for this provider"))
        selected_model = prompt_choice("Step 2/4  Model", model_choices, default=1, color=color)
        if selected_model == "custom":
            selected_model = prompt_text("Model id", required=True)
        base_url = prompt_text("Base URL", default=str(info.get("base_url") or "").rstrip("/"), required=True).rstrip("/")
        model_id = find_existing_model_id(models_config, model_name=selected_model, provider_key=provider_key) or selected_model
        existing_cfg = models_config.get(model_id, {}) if isinstance(models_config.get(model_id), dict) else {}
        print()
        print(paint("Step 3/4  API key", "cyan", "bold", enabled=color))
        key_value = prompt_api_key(existing=bool(existing_cfg.get("api_key")))
        api_key = key_value or str(existing_cfg.get("api_key") or "")
        cfg = {
            "model": selected_model,
            "base_url": base_url,
            "api_key": api_key,
            "transport": "openai_api",
            "provider_key": provider_key,
            "vision": bool(existing_cfg.get("vision", False)),
        }

    validation_error = _validate_api_model_config(cfg)
    if validation_error:
        print(status_line("config", validation_error, status="fail", color=color))
        return 1

    normalized = save_cli_model_config(model_id, cfg)
    print(status_line("saved", f"{model_id} is now the default model", status="ok", color=color))
    print(status_line("local_file", str(LLM_LOCAL_CONFIG_FILE), status="ok", color=color))

    base_url = str(normalized.get("base_url") or "").rstrip("/")
    print()
    print(paint("Step 4/4  Connection test", "cyan", "bold", enabled=color))
    test_question = f"Test connection now? This sends a tiny ping to {base_url} using the API key you entered."
    if getattr(args, "test", False) or ask_yes_no(test_question, default=False):
        ok, detail = _probe_api_model(normalized, timeout=8)
        print(status_line("test", detail, status="ok" if ok else "fail", color=color))
        return 0 if ok else 1
    print(status_line("next", "run `aaroncore` to start chatting", status="ok", color=color))
    return 0


def _init_mcp_cli_runtime():
    try:
        from core import mcp_client, mcp_registry
        from storage.paths import MCP_REGISTRY_CACHE_FILE, MCP_SERVERS_FILE
    except Exception as exc:
        raise AaronCoreError(f"cannot load MCP runtime: {exc}") from exc

    mcp_client.init(debug_write=lambda _stage, _data: None, servers_path=MCP_SERVERS_FILE)
    mcp_registry.init(debug_write=lambda _stage, _data: None, cache_path=MCP_REGISTRY_CACHE_FILE)
    return mcp_client, mcp_registry, MCP_SERVERS_FILE


def _run_async_blocking(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        result_queue: queue.Queue = queue.Queue(maxsize=1)

        def runner():
            try:
                result_queue.put((True, asyncio.run(coro)))
            except Exception as exc:
                result_queue.put((False, exc))

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()
        ok, payload = result_queue.get()
        if ok:
            return payload
        raise payload
    return asyncio.run(coro)


def _parse_env_overrides(values: list[str] | None) -> dict:
    env = {}
    for item in values or []:
        key, sep, value = str(item or "").partition("=")
        key = key.strip()
        if not sep or not key:
            raise AaronCoreError("Environment values must use KEY=VALUE.")
        env[key] = value
    return env


def _is_secret_env_name(name: str) -> bool:
    upper = str(name or "").upper()
    return any(token in upper for token in ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH", "CREDENTIAL"))


def _prompt_env_value(name: str, *, description: str = "", required: bool = False) -> str:
    label = name
    if description:
        label += f" - {description}"
    while True:
        if _is_secret_env_name(name):
            value = getpass.getpass(f"{label} (input hidden): ").strip()
        else:
            value = input(f"{label}: ").strip()
        if value or not required:
            return value
        print("This value is required.")


def _prompt_env_vars(env_vars: list[dict] | None) -> dict:
    env = {}
    for item in env_vars or []:
        name = str((item or {}).get("name") or "").strip()
        if not name:
            continue
        value = _prompt_env_value(
            name,
            description=str((item or {}).get("description") or "").strip(),
            required=bool((item or {}).get("required")),
        )
        if value:
            env[name] = value
    return env


def _print_mcp_servers(mcp_client, *, color: bool, servers_file: Path | None = None) -> None:
    available = mcp_client.is_available()
    print(status_line("mcp package", "available" if available else "missing: pip install mcp", status="ok" if available else "warn", color=color))
    if servers_file:
        print(status_line("config file", str(servers_file), status="ok", color=color))

    status = mcp_client.get_server_status()
    if not status:
        print("No MCP servers configured.")
        return

    for name, info in status.items():
        connected = bool(info.get("connected"))
        enabled = bool(info.get("enabled", True))
        tools = info.get("tools") or []
        state = "connected" if connected else ("enabled" if enabled else "disabled")
        print()
        print(paint(name, "cyan", "bold", enabled=color))
        print(f"  state: {state}")
        print(f"  transport: {info.get('transport', 'stdio')}")
        print(f"  tools: {len(tools)}")
        for tool in tools[:8]:
            if isinstance(tool, dict):
                desc = str(tool.get("description") or "").strip()
                desc = f" - {desc[:80]}" if desc else ""
                print(f"    - {tool.get('name')}{desc}")
        if len(tools) > 8:
            print(f"    ... {len(tools) - 8} more")


def _print_mcp_result(label: str, result: dict, *, color: bool) -> int:
    ok = bool((result or {}).get("ok"))
    detail = "ok" if ok else str((result or {}).get("error") or result)
    print(status_line(label, detail, status="ok" if ok else "fail", color=color))
    tools = (result or {}).get("tools") or (result or {}).get("connect", {}).get("tools") or []
    if tools:
        print(f"tools discovered: {len(tools)}")
        for tool in tools[:10]:
            if isinstance(tool, dict):
                print(f"  - {tool.get('name')}")
    return 0 if ok else 1


def _mcp_select_configured_server(mcp_client, title: str, *, color: bool) -> str:
    config = mcp_client.load_mcp_config()
    servers = sorted((config.get("servers") or {}).keys())
    if not servers:
        print("No MCP servers configured.")
        return ""
    choices = [(name, name) for name in servers]
    return prompt_choice(title, choices, default=1, color=color)


def _mcp_add_manual(mcp_client, *, color: bool) -> int:
    print()
    print(paint("Add MCP server", "cyan", "bold", enabled=color))
    name = prompt_text("Name", required=True)
    command = prompt_text("Command", default="npx", required=True)
    raw_args = prompt_text("Arguments (shell syntax, optional)")
    try:
        mcp_args = shlex.split(raw_args) if raw_args else []
    except ValueError as exc:
        print(status_line("args", str(exc), status="fail", color=color))
        return 1

    env = {}
    raw_env_names = prompt_text("Environment variable names (comma-separated, optional)")
    for env_name in [part.strip() for part in raw_env_names.split(",") if part.strip()]:
        value = _prompt_env_value(env_name)
        if value:
            env[env_name] = value

    result = mcp_client.add_server(name, command, mcp_args, "stdio", env if env else None)
    code = _print_mcp_result("saved", result, color=color)
    if code == 0 and ask_yes_no("Connect now? This starts the configured MCP command on this machine.", default=False):
        connect_result = _run_async_blocking(mcp_client.connect_server(name))
        return _print_mcp_result("connect", connect_result, color=color)
    return code


def _mcp_search_registry(mcp_registry, query: str, *, color: bool, limit: int = 12) -> list[dict]:
    print(status_line("registry", "searching...", status="info", color=color))
    results = mcp_registry.search_registry(query)[:limit]
    if not results:
        print("No registry matches found.")
        return []
    print()
    print(paint("Registry matches", "cyan", "bold", enabled=color))
    for index, item in enumerate(results, 1):
        title = item.get("title") or item.get("name")
        npm = item.get("npm_package") or ""
        desc = str(item.get("description") or "").strip()
        print(f"  {index}. {title}")
        if npm:
            print(f"     package: {npm}")
        if desc:
            print(f"     {desc[:120]}")
    return results


def _mcp_install_registry(mcp_client, mcp_registry, name: str, *, color: bool, env_overrides: dict | None = None, prompt_env: bool = False, connect: bool = False) -> int:
    config = mcp_registry.get_install_config(name)
    if not config:
        print(status_line("registry", f"not found: {name}", status="fail", color=color))
        return 1

    meta = config.get("_meta") or {}
    env = dict(config.get("env") or {})
    if prompt_env:
        prompted = _prompt_env_vars(meta.get("env_vars") or [])
        env.update(prompted)
    if env_overrides:
        env.update(env_overrides)
    env = {key: value for key, value in env.items() if value}

    result = mcp_client.add_server(
        config["name"],
        config["command"],
        config["args"],
        config["transport"],
        env if env else None,
    )
    code = _print_mcp_result("saved", result, color=color)
    if code != 0:
        return code
    print(status_line("command", " ".join([config["command"], *config["args"]]), status="info", color=color))
    if connect:
        connect_result = _run_async_blocking(mcp_client.connect_server(config["name"]))
        return _print_mcp_result("connect", connect_result, color=color)
    return 0


def _mcp_install_from_search(mcp_client, mcp_registry, *, color: bool) -> int:
    query = prompt_text("Search MCP registry", required=True)
    results = _mcp_search_registry(mcp_registry, query, color=color)
    if not results:
        return 1
    choices = [(str(index), f"{item.get('title') or item.get('name')} ({item.get('name')})") for index, item in enumerate(results, 1)]
    selected = prompt_choice("Install which MCP?", choices, default=1, color=color)
    target = results[int(selected) - 1]
    connect = ask_yes_no("Connect after saving? This may download/start the MCP package.", default=False)
    return _mcp_install_registry(
        mcp_client,
        mcp_registry,
        str(target.get("name") or ""),
        color=color,
        prompt_env=True,
        connect=connect,
    )


def _mcp_interactive(args: argparse.Namespace, mcp_client, mcp_registry, servers_file: Path) -> int:
    color = should_color(sys.stdout, no_color=getattr(args, "no_color", False))
    while True:
        print()
        print(paint("AaronCore MCP", "cyan", "bold", enabled=color))
        print(paint("Terminal-native MCP management. Servers are saved locally.", "gray", enabled=color))
        choice = prompt_choice(
            "Choose an action",
            [
                ("list", "list configured MCP servers"),
                ("add", "add a MCP server manually"),
                ("search", "search registry and install"),
                ("connect", "connect a configured server"),
                ("disconnect", "disconnect a server"),
                ("remove", "remove a saved server"),
                ("quit", "return"),
            ],
            default=1,
            color=color,
        )
        if choice == "quit":
            return 0
        if choice == "list":
            _print_mcp_servers(mcp_client, color=color, servers_file=servers_file)
        elif choice == "add":
            _mcp_add_manual(mcp_client, color=color)
        elif choice == "search":
            _mcp_install_from_search(mcp_client, mcp_registry, color=color)
        elif choice == "connect":
            name = _mcp_select_configured_server(mcp_client, "Connect which server?", color=color)
            if name:
                result = _run_async_blocking(mcp_client.connect_server(name))
                _print_mcp_result("connect", result, color=color)
        elif choice == "disconnect":
            name = _mcp_select_configured_server(mcp_client, "Disconnect which server?", color=color)
            if name:
                result = _run_async_blocking(mcp_client.disconnect_server(name))
                _print_mcp_result("disconnect", result, color=color)
        elif choice == "remove":
            name = _mcp_select_configured_server(mcp_client, "Remove which server?", color=color)
            if name and ask_yes_no(f"Remove saved MCP server '{name}'?", default=False):
                _run_async_blocking(mcp_client.disconnect_server(name))
                result = mcp_client.remove_server(name)
                _print_mcp_result("remove", result, color=color)
        print()
        try:
            input("Press Enter to continue...")
        except EOFError:
            return 0


def command_mcp(args: argparse.Namespace) -> int:
    color = should_color(sys.stdout, no_color=getattr(args, "no_color", False))
    try:
        mcp_client, mcp_registry, servers_file = _init_mcp_cli_runtime()
    except AaronCoreError as exc:
        print(status_line("mcp", str(exc), status="fail", color=color), file=sys.stderr)
        return 1

    action = str(getattr(args, "mcp_command", "") or "")
    try:
        if not action:
            return _mcp_interactive(args, mcp_client, mcp_registry, servers_file)
        if action in {"list", "ls"}:
            _print_mcp_servers(mcp_client, color=color, servers_file=servers_file)
            return 0
        if action == "add":
            env = _parse_env_overrides(getattr(args, "env", []))
            mcp_args = []
            raw_args = str(getattr(args, "mcp_arg_string", "") or "").strip()
            if raw_args:
                try:
                    mcp_args.extend(shlex.split(raw_args))
                except ValueError as exc:
                    raise AaronCoreError(f"Cannot parse --args: {exc}") from exc
            mcp_args.extend(getattr(args, "mcp_args", []) or [])
            result = mcp_client.add_server(
                args.name,
                args.command,
                mcp_args,
                "stdio",
                env if env else None,
            )
            code = _print_mcp_result("saved", result, color=color)
            if code == 0 and getattr(args, "connect", False):
                connect_result = _run_async_blocking(mcp_client.connect_server(args.name))
                return _print_mcp_result("connect", connect_result, color=color)
            return code
        if action == "search":
            query = " ".join(getattr(args, "query", [])).strip()
            _mcp_search_registry(mcp_registry, query, color=color, limit=20)
            return 0
        if action == "install":
            env = _parse_env_overrides(getattr(args, "env", []))
            return _mcp_install_registry(
                mcp_client,
                mcp_registry,
                args.name,
                color=color,
                env_overrides=env,
                connect=bool(getattr(args, "connect", False)),
            )
        if action == "connect":
            result = _run_async_blocking(mcp_client.connect_server(args.name))
            return _print_mcp_result("connect", result, color=color)
        if action == "disconnect":
            result = _run_async_blocking(mcp_client.disconnect_server(args.name))
            return _print_mcp_result("disconnect", result, color=color)
        if action == "remove":
            if not getattr(args, "yes", False) and not ask_yes_no(f"Remove saved MCP server '{args.name}'?", default=False):
                print("Cancelled.")
                return 1
            _run_async_blocking(mcp_client.disconnect_server(args.name))
            result = mcp_client.remove_server(args.name)
            return _print_mcp_result("remove", result, color=color)
    except AaronCoreError as exc:
        print(status_line("mcp", str(exc), status="fail", color=color), file=sys.stderr)
        return 1
    return 2


def _init_qq_cli_runtime():
    try:
        from tools.agent import computer_use as qq_runtime
        from storage.paths import CU_DEBUG_LOG_FILE, QQ_MONITOR_DEBUG_LOG_FILE
    except Exception as exc:
        raise AaronCoreError(f"cannot load QQ runtime: {exc}") from exc
    return qq_runtime, QQ_MONITOR_DEBUG_LOG_FILE, CU_DEBUG_LOG_FILE


def _print_qq_status(status: dict, *, color: bool) -> None:
    active = bool((status or {}).get("active"))
    groups = (status or {}).get("groups") or []
    if isinstance(groups, str):
        groups = [groups]
    group_text = ", ".join(str(item) for item in groups if str(item).strip())
    if not group_text:
        group_text = str((status or {}).get("group") or "")
    print(status_line("qq monitor", "active" if active else "inactive", status="ok" if active else "info", color=color))
    print(status_line("groups", group_text or "-", status="info", color=color))
    pids = (status or {}).get("pids") or {}
    if isinstance(pids, dict) and pids:
        pid_text = ", ".join(f"{name}:{pid}" for name, pid in pids.items())
        print(status_line("worker pids", pid_text, status="info", color=color))
    updated_at = str((status or {}).get("updated_at") or "").strip()
    if updated_at:
        print(status_line("updated", updated_at, status="info", color=color))


def _qq_log_paths() -> list[Path]:
    _qq_runtime, monitor_log, cu_log = _init_qq_cli_runtime()
    return [Path(monitor_log), Path(cu_log)]


def _print_qq_logs(*, lines: int, color: bool) -> int:
    paths = [path for path in _qq_log_paths() if path.exists()]
    if not paths:
        print("No QQ log files found.")
        return 1
    for index, path in enumerate(paths):
        if index:
            print()
        print(paint("==> ", "cyan", "bold", enabled=color) + paint(str(path), "gray", enabled=color))
        print(tail_text(path, lines), end="")
    return 0


def _qq_interactive(args: argparse.Namespace, qq_runtime, *, color: bool) -> int:
    while True:
        print()
        print(paint("AaronCore QQ", "cyan", "bold", enabled=color))
        print(paint("Say in chat: 帮我监听 QQ 群「群名」. This menu only manages sessions.", "gray", enabled=color))
        choice = prompt_choice(
            "Choose an action",
            [
                ("status", "show QQ listening status"),
                ("stop", "stop QQ listening in this AaronCore process"),
                ("logs", "show QQ monitor logs"),
                ("quit", "return"),
            ],
            default=1,
            color=color,
        )
        if choice == "quit":
            return 0
        if choice == "status":
            _print_qq_status(qq_runtime.qq_monitor_status(), color=color)
        elif choice == "stop":
            group = prompt_text("Group name (empty stops all)").strip() or None
            print(status_line("qq stop", qq_runtime.qq_stop_monitor(group), status="ok", color=color))
        elif choice == "logs":
            _print_qq_logs(lines=80, color=color)
        print()
        try:
            input("Press Enter to continue...")
        except EOFError:
            return 0


def command_qq(args: argparse.Namespace) -> int:
    color = should_color(sys.stdout, no_color=getattr(args, "no_color", False))
    try:
        qq_runtime, _monitor_log, _cu_log = _init_qq_cli_runtime()
    except AaronCoreError as exc:
        print(status_line("qq", str(exc), status="fail", color=color), file=sys.stderr)
        return 1

    action = str(getattr(args, "qq_command", "") or "")
    if not action:
        return _qq_interactive(args, qq_runtime, color=color)
    if action in {"status", "st"}:
        _print_qq_status(qq_runtime.qq_monitor_status(), color=color)
        return 0
    if action == "stop":
        group = " ".join(getattr(args, "group", []) or []).strip() or None
        result = qq_runtime.qq_stop_monitor(group)
        print(status_line("qq stop", result, status="ok", color=color))
        return 0
    if action == "logs":
        return _print_qq_logs(lines=max(1, int(getattr(args, "lines", 80) or 80)), color=color)
    return 2


def _init_wechat_cli_runtime():
    try:
        from tools.agent import computer_use as wechat_runtime
        from storage.paths import CU_DEBUG_LOG_FILE, WECHAT_MONITOR_DEBUG_LOG_FILE
    except Exception as exc:
        raise AaronCoreError(f"cannot load WeChat runtime: {exc}") from exc
    return wechat_runtime, WECHAT_MONITOR_DEBUG_LOG_FILE, CU_DEBUG_LOG_FILE


def _print_wechat_status(status: dict, *, color: bool) -> None:
    active = bool((status or {}).get("active"))
    chats = (status or {}).get("chats") or (status or {}).get("groups") or []
    if isinstance(chats, str):
        chats = [chats]
    chat_text = ", ".join(str(item) for item in chats if str(item).strip())
    if not chat_text:
        chat_text = str((status or {}).get("chat") or (status or {}).get("group") or "")
    print(status_line("wechat monitor", "active" if active else "inactive", status="ok" if active else "info", color=color))
    print(status_line("chats", chat_text or "-", status="info", color=color))
    pids = (status or {}).get("pids") or {}
    if isinstance(pids, dict) and pids:
        pid_text = ", ".join(f"{name}:{pid}" for name, pid in pids.items())
        print(status_line("worker pids", pid_text, status="info", color=color))
    updated_at = str((status or {}).get("updated_at") or "").strip()
    if updated_at:
        print(status_line("updated", updated_at, status="info", color=color))


def _wechat_log_paths() -> list[Path]:
    _wechat_runtime, monitor_log, cu_log = _init_wechat_cli_runtime()
    return [Path(monitor_log), Path(cu_log)]


def _print_wechat_logs(*, lines: int, color: bool) -> int:
    paths = [path for path in _wechat_log_paths() if path.exists()]
    if not paths:
        print("No WeChat log files found.")
        return 1
    for index, path in enumerate(paths):
        if index:
            print()
        print(paint("==> ", "cyan", "bold", enabled=color) + paint(str(path), "gray", enabled=color))
        print(tail_text(path, lines), end="")
    return 0


def _wechat_interactive(args: argparse.Namespace, wechat_runtime, *, color: bool) -> int:
    while True:
        print()
        print(paint("AaronCore WeChat", "cyan", "bold", enabled=color))
        print(paint("Say in chat: 帮我监听微信「聊天名」. This menu only manages sessions.", "gray", enabled=color))
        choice = prompt_choice(
            "Choose an action",
            [
                ("status", "show WeChat listening status"),
                ("stop", "stop WeChat listening in this AaronCore process"),
                ("logs", "show WeChat monitor logs"),
                ("quit", "return"),
            ],
            default=1,
            color=color,
        )
        if choice == "quit":
            return 0
        if choice == "status":
            _print_wechat_status(wechat_runtime.wechat_monitor_status(), color=color)
        elif choice == "stop":
            chat = prompt_text("Chat name (empty stops all)").strip() or None
            print(status_line("wechat stop", wechat_runtime.wechat_stop_monitor(chat), status="ok", color=color))
        elif choice == "logs":
            _print_wechat_logs(lines=80, color=color)
        print()
        try:
            input("Press Enter to continue...")
        except EOFError:
            return 0


def command_wechat(args: argparse.Namespace) -> int:
    color = should_color(sys.stdout, no_color=getattr(args, "no_color", False))
    try:
        wechat_runtime, _monitor_log, _cu_log = _init_wechat_cli_runtime()
    except AaronCoreError as exc:
        print(status_line("wechat", str(exc), status="fail", color=color), file=sys.stderr)
        return 1

    action = str(getattr(args, "wechat_command", "") or "")
    if not action:
        return _wechat_interactive(args, wechat_runtime, color=color)
    if action in {"status", "st"}:
        _print_wechat_status(wechat_runtime.wechat_monitor_status(), color=color)
        return 0
    if action == "stop":
        chat = " ".join(getattr(args, "chat", []) or []).strip() or None
        result = wechat_runtime.wechat_stop_monitor(chat)
        print(status_line("wechat stop", result, status="ok", color=color))
        return 0
    if action == "logs":
        return _print_wechat_logs(lines=max(1, int(getattr(args, "lines", 80) or 80)), color=color)
    return 2


def _init_social_cli_runtime():
    try:
        from tools.agent import computer_use as social_runtime
    except Exception as exc:
        raise AaronCoreError(f"cannot load social runtime: {exc}") from exc
    return social_runtime


def _social_interactive(args: argparse.Namespace, social_runtime, *, color: bool) -> int:
    while True:
        print()
        print(paint("AaronCore Social", "cyan", "bold", enabled=color))
        print(paint("List/open handoff targets. Sending and posting continue through normal chat/tool flow.", "gray", enabled=color))
        choice = prompt_choice(
            "Choose an action",
            [
                ("list", "list social and communication targets"),
                ("open", "open a platform handoff entry"),
                ("quit", "return"),
            ],
            default=1,
            color=color,
        )
        if choice == "quit":
            return 0
        if choice == "list":
            print(social_runtime.list_social_platforms())
        elif choice == "open":
            platform = prompt_text("Platform name", required=True).strip()
            print(status_line("social open", social_runtime.open_social_platform(platform), status="ok", color=color))
        print()
        try:
            input("Press Enter to continue...")
        except EOFError:
            return 0


def command_social(args: argparse.Namespace) -> int:
    color = should_color(sys.stdout, no_color=getattr(args, "no_color", False))
    try:
        social_runtime = _init_social_cli_runtime()
    except AaronCoreError as exc:
        print(status_line("social", str(exc), status="fail", color=color), file=sys.stderr)
        return 1

    action = str(getattr(args, "social_command", "") or "")
    if not action:
        return _social_interactive(args, social_runtime, color=color)
    if action in {"list", "ls"}:
        print(social_runtime.list_social_platforms())
        return 0
    if action == "open":
        platform = " ".join(getattr(args, "platform", []) or []).strip()
        if not platform:
            print("Usage: aaron social open <platform>", file=sys.stderr)
            return 2
        print(status_line("social open", social_runtime.open_social_platform(platform), status="ok", color=color))
        return 0
    return 2


def build_client(args: argparse.Namespace):
    transport = str(getattr(args, "transport", "") or os.environ.get("AARONCORE_TRANSPORT") or "").strip().lower()
    if not transport:
        transport = "http" if getattr(args, "url", None) else "direct"
    if transport == "http":
        return AaronCoreClient(base_url=args.url or os.environ.get("AARONCORE_URL") or DEFAULT_BASE_URL, timeout=args.timeout)
    if transport != "direct":
        raise AaronCoreError(f"Unknown transport: {transport}")
    return DirectAaronCoreClient(timeout=args.timeout)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aaron",
        description="AaronCore CLI: a thin terminal shell over the local memory-first agent runtime.",
    )
    parser.add_argument("--transport", choices=("direct", "http"), default=os.environ.get("AARONCORE_TRANSPORT", ""), help="Runtime transport. Default: direct in-process runtime.")
    parser.add_argument("--url", default=os.environ.get("AARONCORE_URL"), help="Legacy HTTP backend URL. Setting this uses the HTTP transport.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Timeout for non-streaming checks.")
    parser.add_argument("--steps", action="store_true", help="Print backend process events to stderr.")
    parser.add_argument("--quiet", action="store_true", help="Hide compact process lines in chat output.")
    parser.add_argument("--plain", action="store_true", help="Use the simple non-TUI terminal mode.")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI color and styled output.")
    parser.add_argument("--no-start", action="store_true", help="HTTP transport only: do not auto-start the localhost runtime.")

    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Send one message to the local AaronCore runtime.")
    run_parser.add_argument("message", nargs=argparse.REMAINDER)
    run_parser.set_defaults(func=command_run)

    chat_parser = subparsers.add_parser("chat", help="Start an interactive AaronCore terminal chat.")
    chat_parser.set_defaults(func=command_shell)

    setup_parser = subparsers.add_parser("setup", help="Configure the default LLM provider and API key.")
    setup_parser.add_argument("--test", action="store_true", help="Test the selected model after saving.")
    setup_parser.set_defaults(func=command_setup)

    qq_parser = subparsers.add_parser("qq", help="Inspect and manage QQ listening sessions.")
    qq_sub = qq_parser.add_subparsers(dest="qq_command")
    qq_parser.set_defaults(func=command_qq)

    qq_status = qq_sub.add_parser("status", aliases=["st"], help="Show QQ listening status.")
    qq_status.set_defaults(func=command_qq)

    qq_stop = qq_sub.add_parser("stop", help="Stop QQ listening in this AaronCore process.")
    qq_stop.add_argument("group", nargs=argparse.REMAINDER, help="Optional group name. Empty stops all tracked QQ monitors.")
    qq_stop.set_defaults(func=command_qq)

    qq_logs = qq_sub.add_parser("logs", help="Show QQ monitor logs.")
    qq_logs.add_argument("--lines", type=int, default=80, help="Number of lines to print.")
    qq_logs.set_defaults(func=command_qq)

    wechat_parser = subparsers.add_parser("wechat", aliases=["wx"], help="Inspect and manage WeChat listening sessions.")
    wechat_sub = wechat_parser.add_subparsers(dest="wechat_command")
    wechat_parser.set_defaults(func=command_wechat)

    wechat_status = wechat_sub.add_parser("status", aliases=["st"], help="Show WeChat listening status.")
    wechat_status.set_defaults(func=command_wechat)

    wechat_stop = wechat_sub.add_parser("stop", help="Stop WeChat listening in this AaronCore process.")
    wechat_stop.add_argument("chat", nargs=argparse.REMAINDER, help="Optional chat name. Empty stops all tracked WeChat monitors.")
    wechat_stop.set_defaults(func=command_wechat)

    wechat_logs = wechat_sub.add_parser("logs", help="Show WeChat monitor logs.")
    wechat_logs.add_argument("--lines", type=int, default=80, help="Number of lines to print.")
    wechat_logs.set_defaults(func=command_wechat)

    social_parser = subparsers.add_parser("social", aliases=["comm"], help="List or open social/communication handoff targets.")
    social_sub = social_parser.add_subparsers(dest="social_command")
    social_parser.set_defaults(func=command_social)

    social_list = social_sub.add_parser("list", aliases=["ls"], help="List supported social/communication targets.")
    social_list.set_defaults(func=command_social)

    social_open = social_sub.add_parser("open", help="Open a platform handoff target.")
    social_open.add_argument("platform", nargs=argparse.REMAINDER, help="Platform name, for example Slack or 飞书.")
    social_open.set_defaults(func=command_social)

    mcp_parser = subparsers.add_parser("mcp", help="Manage local MCP servers from the terminal.")
    mcp_sub = mcp_parser.add_subparsers(dest="mcp_command")
    mcp_parser.set_defaults(func=command_mcp)

    mcp_list = mcp_sub.add_parser("list", aliases=["ls"], help="List configured MCP servers.")
    mcp_list.set_defaults(func=command_mcp)

    mcp_add = mcp_sub.add_parser("add", help="Add a MCP server by command.")
    mcp_add.add_argument("name", help="Local server name.")
    mcp_add.add_argument("--command", required=True, help="Command to start the MCP server, for example npx or node.")
    mcp_add.add_argument("--args", dest="mcp_arg_string", default="", help='Startup args as one shell-style string, for example "-y package".')
    mcp_add.add_argument("--arg", dest="mcp_args", action="append", default=[], help="One startup argument. Repeat for multiple args.")
    mcp_add.add_argument("--env", action="append", default=[], help="Environment value as KEY=VALUE. Repeat for multiple vars.")
    mcp_add.add_argument("--connect", action="store_true", help="Connect immediately after saving.")
    mcp_add.set_defaults(func=command_mcp)

    mcp_search = mcp_sub.add_parser("search", help="Search the MCP registry.")
    mcp_search.add_argument("query", nargs=argparse.REMAINDER, help="Search terms.")
    mcp_search.set_defaults(func=command_mcp)

    mcp_install = mcp_sub.add_parser("install", help="Install a registry MCP server into local config.")
    mcp_install.add_argument("name", help="Registry server name.")
    mcp_install.add_argument("--env", action="append", default=[], help="Environment value as KEY=VALUE. Repeat for multiple vars.")
    mcp_install.add_argument("--connect", action="store_true", help="Connect immediately after saving.")
    mcp_install.set_defaults(func=command_mcp)

    mcp_connect = mcp_sub.add_parser("connect", help="Connect a configured MCP server.")
    mcp_connect.add_argument("name", help="Local server name.")
    mcp_connect.set_defaults(func=command_mcp)

    mcp_disconnect = mcp_sub.add_parser("disconnect", help="Disconnect a connected MCP server.")
    mcp_disconnect.add_argument("name", help="Local server name.")
    mcp_disconnect.set_defaults(func=command_mcp)

    mcp_remove = mcp_sub.add_parser("remove", help="Remove a saved MCP server.")
    mcp_remove.add_argument("name", help="Local server name.")
    mcp_remove.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    mcp_remove.set_defaults(func=command_mcp)

    doctor_parser = subparsers.add_parser("doctor", help="Check runtime and local files.")
    doctor_parser.set_defaults(func=command_doctor)

    memory_parser = subparsers.add_parser("memory", help="Memory-oriented commands.")
    memory_sub = memory_parser.add_subparsers(dest="memory_command", required=True)
    memory_search = memory_sub.add_parser("search", help="Ask AaronCore to search its memory through the normal chat runtime.")
    memory_search.add_argument("query", nargs=argparse.REMAINDER)
    memory_search.set_defaults(func=command_memory_search)

    logs_parser = subparsers.add_parser("logs", help="Tail local AaronCore log files.")
    logs_parser.add_argument("--lines", type=int, default=80, help="Number of lines to print.")
    logs_parser.add_argument("--list", action="store_true", help="List discovered log files.")
    logs_parser.add_argument("--file", default="", help="Specific log file to tail.")
    logs_parser.set_defaults(func=command_logs)

    parser.set_defaults(func=command_shell)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
