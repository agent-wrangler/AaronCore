from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path
from urllib import error, request


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_BASE_URL = "http://127.0.0.1:8090"
DEFAULT_TIMEOUT = 10


class AaronCoreError(RuntimeError):
    pass


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
    def __init__(self, *, show_steps: bool = False, stream_reset_notice: bool = True):
        self.show_steps = show_steps
        self.stream_reset_notice = stream_reset_notice
        self.printed_text = ""
        self.saw_stream = False

    def handle_event(self, event_name: str, data: str, client: AaronCoreClient) -> None:
        payload = parse_event_json(data)
        if event_name == "stream_reset":
            if self.stream_reset_notice and self.printed_text.strip():
                print("\n[stream reset: restarting reply]\n", file=sys.stderr)
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
            print(format_step_event(event_name, payload), file=sys.stderr)

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
        print(f"\n? {question}", file=sys.stderr)
        options = payload.get("options") or payload.get("choices")
        if isinstance(options, list):
            for index, item in enumerate(options, 1):
                label = item.get("label") if isinstance(item, dict) else item
                print(f"  {index}. {label}", file=sys.stderr)
        if not question_id:
            print("Cannot answer: backend did not provide a question id.", file=sys.stderr)
            return
        try:
            answer = input("> ").strip()
        except EOFError:
            answer = ""
        if not answer:
            print("Skipped empty answer.", file=sys.stderr)
            return
        if not client.submit_answer(question_id, answer):
            print("Backend did not accept the answer.", file=sys.stderr)

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


def format_step_event(event_name: str, payload: dict) -> str:
    label = first_text(payload, "label", "title", "name", "status")
    detail = first_text(payload, "detail", "message", "text")
    if label and detail:
        return f"[{event_name}] {label}: {detail}"
    if label:
        return f"[{event_name}] {label}"
    if detail:
        return f"[{event_name}] {detail}"
    return f"[{event_name}] {json.dumps(payload, ensure_ascii=False)}"


def run_chat(client: AaronCoreClient, message: str, *, show_steps: bool = False) -> int:
    printer = ChatPrinter(show_steps=show_steps)
    try:
        for event_name, data in client.chat_events(message):
            printer.handle_event(event_name, data, client)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except AaronCoreError as exc:
        print(str(exc), file=sys.stderr)
        print("Start the backend first, for example: python agent_final.py", file=sys.stderr)
        return 1
    return 0


def command_shell(args: argparse.Namespace) -> int:
    client = build_client(args)
    print("AaronCore CLI")
    print(f"Backend: {client.base_url}")
    print("Type /exit to quit, /doctor to check backend, /logs to tail logs.")
    while True:
        try:
            message = input("aaron> ").strip()
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
        if message == "/doctor":
            command_doctor(args)
            continue
        if message.startswith("/logs"):
            try:
                logs_args = build_parser().parse_args(["logs", *shlex.split(message)[1:]])
            except SystemExit:
                continue
            command_logs(logs_args)
            continue
        code = run_chat(client, message, show_steps=args.steps)
        if code not in {0, 130}:
            return code


def command_run(args: argparse.Namespace) -> int:
    message = " ".join(args.message).strip()
    if not message:
        print("Usage: aaron run \"your message\"", file=sys.stderr)
        return 2
    return run_chat(build_client(args), message, show_steps=args.steps)


def command_doctor(args: argparse.Namespace) -> int:
    client = build_client(args)
    print("AaronCore CLI doctor")
    print(f"- backend: {client.base_url}")
    ok = True
    try:
        health = client.get_json("/health", timeout=3)
        print(f"- /health: {health.get('status', 'unknown')}")
        print(f"- core_ready: {health.get('core_ready')}")
        print(f"- current_model: {health.get('current_model')}")
        print(f"- state_dir: {health.get('state_dir')}")
    except AaronCoreError as exc:
        ok = False
        print(f"- /health: failed ({exc})")
        print("- hint: start the backend with `python agent_final.py`")

    required = ["agent_final.py", "routes/chat.py", "memory", "state_data"]
    for rel in required:
        path = ROOT_DIR / rel
        exists = path.exists()
        ok = ok and exists
        print(f"- local {rel}: {'ok' if exists else 'missing'}")
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
    return run_chat(build_client(args), message, show_steps=args.steps)


def command_logs(args: argparse.Namespace) -> int:
    files = discover_log_files()
    if args.list:
        if not files:
            print("No log files found.")
            return 1
        for path in files:
            print(path)
        return 0

    target = Path(args.file).expanduser() if args.file else (files[0] if files else None)
    if not target:
        print("No log files found.", file=sys.stderr)
        return 1
    if not target.exists():
        print(f"Log file not found: {target}", file=sys.stderr)
        return 1
    print(f"==> {target}")
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

    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Send one message to the local AaronCore backend.")
    run_parser.add_argument("message", nargs=argparse.REMAINDER)
    run_parser.set_defaults(func=command_run)

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
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
