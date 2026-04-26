from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from urllib import error, request


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_BASE_URL = "http://127.0.0.1:8090"
DEFAULT_TIMEOUT = 10
CLI_VERSION = "0.2.0"

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


def print_banner(*, health: dict | None, runtime_state: str, color: bool) -> None:
    width = 68
    title = f"AaronCore CLI v{CLI_VERSION}"
    subtitle = "memory-first local agent shell"
    model = str((health or {}).get("current_model") or "unknown")
    core_ready = bool((health or {}).get("core_ready"))
    status = "runtime ready" if runtime_state == "ready" else runtime_state
    meta = f"{model}  |  {'core ready' if core_ready else 'core warming'}  |  {status}"
    location = compact_path(ROOT_DIR)
    print(paint("+" + "-" * width + "+", "cyan", enabled=color))
    print(
        paint("| ", "cyan", enabled=color)
        + paint(title.ljust(width - 2), "bold", "cyan", enabled=color)
        + paint(" |", "cyan", enabled=color)
    )
    print(
        paint("| ", "cyan", enabled=color)
        + paint(subtitle.ljust(width - 2), "dim", enabled=color)
        + paint(" |", "cyan", enabled=color)
    )
    print(
        paint("| ", "cyan", enabled=color)
        + paint(meta[: width - 2].ljust(width - 2), "gray", enabled=color)
        + paint(" |", "cyan", enabled=color)
    )
    print(
        paint("| ", "cyan", enabled=color)
        + paint(location[: width - 2].ljust(width - 2), "gray", enabled=color)
        + paint(" |", "cyan", enabled=color)
    )
    print(paint("+" + "-" * width + "+", "cyan", enabled=color))
    print(paint("? ", "gray", enabled=color) + "for shortcuts")


def print_shortcuts(*, color: bool) -> None:
    rows = [
        ("/help", "show shortcuts"),
        ("/status", "check local runtime"),
        ("/logs --lines 40", "tail recent logs"),
        ("/clear", "clear the terminal"),
        ("/exit", "leave AaronCore"),
    ]
    print()
    for command, detail in rows:
        print(paint(command.ljust(18), "cyan", "bold", enabled=color) + paint(detail, "gray", enabled=color))
    print()


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
    def __init__(self, *, show_steps: bool = False, stream_reset_notice: bool = True, color: bool = False):
        self.show_steps = show_steps
        self.stream_reset_notice = stream_reset_notice
        self.color = color
        self.printed_text = ""
        self.saw_stream = False

    def handle_event(self, event_name: str, data: str, client: AaronCoreClient) -> None:
        payload = parse_event_json(data)
        if event_name == "stream_reset":
            if self.stream_reset_notice and self.printed_text.strip():
                print(
                    "\n" + paint("[stream reset] restarting reply", "yellow", enabled=self.color) + "\n",
                    file=sys.stderr,
                )
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

    def _print_stream_payload(self, payload: dict) -> None:
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


def format_step_event(event_name: str, payload: dict, *, color: bool = False) -> str:
    label = first_text(payload, "label", "title", "name", "status")
    detail = first_text(payload, "detail", "message", "text")
    head = paint(f"[{event_name}]", "magenta", enabled=color)
    if label and detail:
        return f"{head} {paint(label, 'bold', enabled=color)}: {detail}"
    if label:
        return f"{head} {paint(label, 'bold', enabled=color)}"
    if detail:
        return f"{head} {detail}"
    return f"{head} {json.dumps(payload, ensure_ascii=False)}"


def run_chat(client: AaronCoreClient, message: str, *, show_steps: bool = False, color: bool = False) -> int:
    printer = ChatPrinter(show_steps=show_steps, color=color)
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


def command_shell(args: argparse.Namespace) -> int:
    color = should_color(sys.stdout, no_color=args.no_color)
    try:
        client, health, runtime_state = ensure_backend(args, color=color)
    except AaronCoreError as exc:
        print(status_line("runtime", str(exc), status="fail", color=color), file=sys.stderr)
        return 1
    print_banner(health=health, runtime_state=runtime_state, color=color)
    while True:
        try:
            message = input(paint("> ", "cyan", "bold", enabled=color)).strip()
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
        code = run_chat(client, message, show_steps=args.steps, color=color)
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
    code = run_chat(client, message, show_steps=args.steps, color=color)
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
    print(status_line("backend", client.base_url, color=color))
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
        print(status_line("hint", "start the backend with `python agent_final.py`", status="warn", color=color))

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
    return run_chat(client, message, show_steps=args.steps, color=color)


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


def build_client(args: argparse.Namespace) -> AaronCoreClient:
    return AaronCoreClient(base_url=args.url, timeout=args.timeout)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aaron",
        description="AaronCore CLI: a thin terminal shell over the local memory-first agent runtime.",
    )
    parser.add_argument("--url", default=os.environ.get("AARONCORE_URL", DEFAULT_BASE_URL), help="AaronCore backend URL.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout for non-streaming checks.")
    parser.add_argument("--steps", action="store_true", help="Print backend process events to stderr.")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI color and styled output.")
    parser.add_argument("--no-start", action="store_true", help="Do not auto-start the local runtime.")

    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Send one message to the local AaronCore backend.")
    run_parser.add_argument("message", nargs=argparse.REMAINDER)
    run_parser.set_defaults(func=command_run)

    chat_parser = subparsers.add_parser("chat", help="Start an interactive AaronCore terminal chat.")
    chat_parser.set_defaults(func=command_shell)

    doctor_parser = subparsers.add_parser("doctor", help="Check backend and local runtime files.")
    doctor_parser.set_defaults(func=command_doctor)

    memory_parser = subparsers.add_parser("memory", help="Memory-oriented commands.")
    memory_sub = memory_parser.add_subparsers(dest="memory_command", required=True)
    memory_search = memory_sub.add_parser("search", help="Ask AaronCore to search its memory through /chat.")
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
