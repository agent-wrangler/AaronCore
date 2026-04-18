import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from core.fs_protocol import build_operation_result, normalize_user_special_path
from decision.tool_runtime.runtime_control import cooperative_sleep, raise_if_cancelled

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
USER_HOME = Path.home()
DEFAULT_TIMEOUT_SEC = 600
MAX_TIMEOUT_SEC = 1800
DEFAULT_STARTUP_WAIT_SEC = 4
MAX_STARTUP_WAIT_SEC = 20

_ALLOWED_EXECUTABLES = {
    "python",
    "python.exe",
    "py",
    "py.exe",
    "pip",
    "pip.exe",
    "pytest",
    "pytest.exe",
    "pyinstaller",
    "pyinstaller.exe",
    "npm",
    "npm.cmd",
    "npx",
    "npx.cmd",
    "node",
    "node.exe",
    "pnpm",
    "pnpm.cmd",
    "yarn",
    "yarn.cmd",
    "uv",
    "uv.exe",
    "cargo",
    "cargo.exe",
    "cmd",
    "cmd.exe",
}

_ALLOWED_PYTHON_MODULES = {"pip", "pytest", "pyinstaller", "unittest"}
_ALLOWED_PIP_COMMANDS = {"install", "list", "show", "freeze"}
_ALLOWED_NPM_COMMANDS = {"install", "run", "test", "pack", "ci", "exec"}
_ALLOWED_UV_COMMANDS = {"run", "sync", "pip"}
_ALLOWED_CARGO_COMMANDS = {"build", "test", "run", "install"}
_CONTROL_TOKENS = {"&&", "||", "|", ">", ">>", "<"}
_DANGEROUS_PATTERNS = (
    "remove-item",
    "del /f",
    "rmdir /s",
    "format ",
    "shutdown",
    "reboot",
    "taskkill",
    "reg delete",
    "git reset --hard",
    "git clean -fd",
)
_FILE_COPY_EXECUTABLES = {"cp", "copy"}
_FILE_MOVE_EXECUTABLES = {"mv", "move"}
_FILE_MANIPULATION_EXECUTABLES = _FILE_COPY_EXECUTABLES | _FILE_MOVE_EXECUTABLES
_DISALLOWED_HOME_CHILDREN = {"appdata"}
_BACKGROUND_DESCRIPTION_HINTS = (
    "启动",
    "启动服务",
    "启动应用",
    "本地启动",
    "launch",
    "start",
    "serve",
    "server",
    "dev server",
)
_BACKGROUND_NEGATIVE_HINTS = (
    "build",
    "构建",
    "打包",
    "package",
    "install",
    "安装",
    "test",
    "测试",
    "pytest",
)
_BACKGROUND_SCRIPT_STEMS = {"app", "server", "main", "manage"}
_BACKGROUND_MODULE_MARKERS = {"flask", "uvicorn", "http.server", "streamlit"}


def _coerce_dict(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _context_execution_lane(context: dict | None) -> str:
    payload = _coerce_dict(context)
    current_step_task = _coerce_dict(payload.get("current_step_task"))
    working_state = _coerce_dict(payload.get("working_state"))
    return str(
        current_step_task.get("execution_lane")
        or payload.get("execution_lane")
        or working_state.get("execution_lane")
        or ""
    ).strip().lower()


def _context_step_title(context: dict | None) -> str:
    payload = _coerce_dict(context)
    current_step_task = _coerce_dict(payload.get("current_step_task"))
    working_state = _coerce_dict(payload.get("working_state"))
    return str(
        current_step_task.get("title")
        or working_state.get("current_step")
        or ""
    ).strip()


def _context_fs_target_path(context: dict | None) -> str:
    payload = _coerce_dict(context)
    target = _coerce_dict(payload.get("fs_target"))
    path = str(target.get("path") or "").strip()
    if path:
        return path
    context_data = _coerce_dict(payload.get("context_data"))
    inherited_target = _coerce_dict(context_data.get("fs_target"))
    return str(inherited_target.get("path") or "").strip()


def _resolve_context_workdir(context: dict | None) -> Path | None:
    payload = _coerce_dict(context)
    if not (_context_execution_lane(payload) or _coerce_dict(payload.get("current_step_task"))):
        return None
    raw_target = _context_fs_target_path(payload)
    if not raw_target or raw_target.startswith(("http://", "https://")):
        return None
    resolved = _resolve_path(raw_target, base=WORKSPACE_ROOT)
    if resolved is None:
        return None
    candidate = resolved.parent if resolved.suffix else resolved
    if not _is_allowed_path(candidate):
        return None
    return candidate


def _allowed_roots() -> list[Path]:
    roots = [WORKSPACE_ROOT.resolve()]
    for name in ("Desktop", "Documents", "Downloads"):
        roots.append((USER_HOME / name).resolve())
    unique = []
    seen = set()
    for root in roots:
        key = str(root).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def _is_allowed_path(path: Path | None) -> bool:
    if path is None:
        return False
    target = path.resolve()
    for root in _allowed_roots():
        if target == root or root in target.parents:
            return True
    try:
        rel = target.relative_to(USER_HOME.resolve())
    except Exception:
        rel = None
    if rel is not None:
        if not rel.parts:
            return True
        if rel.parts[0].lower() in _DISALLOWED_HOME_CHILDREN:
            return False
        return True
    return False


def _resolve_path(raw: str, *, base: Path | None = None) -> Path | None:
    text = normalize_user_special_path(str(raw or "").strip())
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        relative_text = text
        if relative_text.startswith(".\\") or relative_text.startswith("./"):
            relative_text = relative_text[2:]
        path = (base or WORKSPACE_ROOT).resolve() / relative_text
    return path.resolve()


def _resolve_workdir(context: dict) -> Path:
    raw = str(context.get("workdir") or context.get("cwd") or "").strip()
    if raw:
        workdir = _resolve_path(raw, base=WORKSPACE_ROOT)
    else:
        workdir = _resolve_context_workdir(context) or WORKSPACE_ROOT.resolve()
    if workdir is None:
        return WORKSPACE_ROOT.resolve()
    return workdir


def _strip_outer_quotes(token: str) -> str:
    text = str(token or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def _split_command(command: str) -> list[str]:
    raw = str(command or "").strip()
    if not raw:
        return []
    try:
        tokens = shlex.split(raw, posix=False)
    except ValueError:
        return []
    cleaned = [_strip_outer_quotes(token) for token in tokens if str(token or "").strip()]
    return [token for token in cleaned if token]


def _summarize_output(stdout: str, stderr: str, limit: int = 6) -> str:
    lines = [line.strip() for line in (str(stdout or "") + "\n" + str(stderr or "")).splitlines() if line.strip()]
    if not lines:
        return ""
    tail = " | ".join(lines[-limit:])
    return tail[:500]


def _resolve_timeout(context: dict) -> int:
    raw = context.get("timeout_sec") or context.get("timeout") or DEFAULT_TIMEOUT_SEC
    try:
        value = int(raw)
    except Exception:
        value = DEFAULT_TIMEOUT_SEC
    return max(1, min(value, MAX_TIMEOUT_SEC))


def _resolve_startup_wait(context: dict) -> int:
    raw = context.get("startup_wait_sec") or context.get("startup_wait") or DEFAULT_STARTUP_WAIT_SEC
    try:
        value = int(raw)
    except Exception:
        value = DEFAULT_STARTUP_WAIT_SEC
    return max(1, min(value, MAX_STARTUP_WAIT_SEC))


def _repair_pyinstaller_args(argv: list[str]) -> tuple[list[str], list[str]]:
    repaired = []
    notes = []
    idx = 0
    while idx < len(argv):
        token = argv[idx]
        lowered = token.lower()
        if lowered == "--destpath":
            repaired.append("--distpath")
            notes.append("repaired --destpath to --distpath")
            idx += 1
            continue
        if token == "--" and idx + 1 < len(argv) and str(argv[idx + 1]).lower() == "noconfirm":
            repaired.append("--noconfirm")
            notes.append("repaired '-- noconfirm' to '--noconfirm'")
            idx += 2
            continue
        repaired.append(token)
        idx += 1
    return repaired, notes


def _looks_like_pyinstaller(argv: list[str]) -> bool:
    if not argv:
        return False
    first = str(argv[0]).lower()
    if first in {"pyinstaller", "pyinstaller.exe"}:
        return True
    return first in {"python", "python.exe", "py", "py.exe"} and len(argv) >= 3 and str(argv[1]) == "-m" and str(argv[2]).lower() == "pyinstaller"


def _infer_pyinstaller_artifacts(argv: list[str], workdir: Path) -> list[Path]:
    if not _looks_like_pyinstaller(argv):
        return []

    dist_dir = workdir / "dist"
    name = ""
    script_name = ""
    flags = {str(token).lower() for token in argv}
    skip_next = False
    for idx, token in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        lowered = str(token).lower()
        if lowered == "--distpath" and idx + 1 < len(argv):
            dist_dir = _resolve_path(argv[idx + 1], base=workdir) or dist_dir
            skip_next = True
            continue
        if lowered == "--name" and idx + 1 < len(argv):
            name = str(argv[idx + 1]).strip()
            skip_next = True
            continue
        if not str(token).startswith("-") and str(token).lower().endswith((".py", ".spec")):
            script_name = str(token)

    if not name and script_name:
        name = Path(script_name).stem
    if not name:
        return []

    exe_name = f"{name}.exe" if os.name == "nt" else name
    if "--onefile" in flags or "-f" in flags:
        return [(dist_dir / exe_name).resolve()]
    return [(dist_dir / name).resolve(), (dist_dir / name / exe_name).resolve()]


def _resolve_expected_artifacts(context: dict, workdir: Path, argv: list[str]) -> list[Path]:
    raw_items = context.get("expected_artifacts")
    if isinstance(raw_items, str):
        raw_items = [raw_items]
    if not isinstance(raw_items, list):
        raw_items = []
    if context.get("expected_artifact"):
        raw_items.append(context.get("expected_artifact"))

    paths = []
    for item in raw_items:
        resolved = _resolve_path(str(item or ""), base=workdir)
        if resolved is not None:
            paths.append(resolved)

    if paths:
        return paths
    return _infer_pyinstaller_artifacts(argv, workdir)


def _validate_command(argv: list[str], workdir: Path) -> tuple[bool, str, list[str], list[str]]:
    if not argv:
        return False, "missing_command", [], []
    if any(token in _CONTROL_TOKENS for token in argv):
        return False, "shell_control_operator", [], []

    lowered_command = " ".join(str(token).lower() for token in argv)
    if any(pattern in lowered_command for pattern in _DANGEROUS_PATTERNS):
        return False, "dangerous_command", [], []

    first = str(argv[0]).lower()
    if first in _FILE_MANIPULATION_EXECUTABLES:
        return False, "use_protocol_file_action", [], []
    if first not in _ALLOWED_EXECUTABLES:
        return False, "unsupported_executable", [], []

    repaired_argv = list(argv)
    repair_notes = []
    if _looks_like_pyinstaller(repaired_argv):
        repaired_argv, repair_notes = _repair_pyinstaller_args(repaired_argv)

    if first in {"cmd", "cmd.exe"}:
        if len(repaired_argv) < 3 or str(repaired_argv[1]).lower() != "/c":
            return False, "cmd_requires_script", [], []
        script_path = _resolve_path(repaired_argv[2], base=workdir)
        if script_path is None or script_path.suffix.lower() not in {".bat", ".cmd"} or not _is_allowed_path(script_path):
            return False, "unsafe_script_target", [], []
        repaired_argv[2] = str(script_path)
        return True, "", repaired_argv, repair_notes

    if first in {"pip", "pip.exe"}:
        if len(repaired_argv) < 2 or str(repaired_argv[1]).lower() not in _ALLOWED_PIP_COMMANDS:
            return False, "unsupported_pip_subcommand", [], []
        return True, "", repaired_argv, repair_notes

    if first in {"pytest", "pytest.exe", "pyinstaller", "pyinstaller.exe"}:
        return True, "", repaired_argv, repair_notes

    if first in {"npm", "npm.cmd", "pnpm", "pnpm.cmd", "yarn", "yarn.cmd", "npx", "npx.cmd"}:
        if len(repaired_argv) < 2 or str(repaired_argv[1]).lower() not in _ALLOWED_NPM_COMMANDS:
            return False, "unsupported_node_subcommand", [], []
        return True, "", repaired_argv, repair_notes

    if first in {"uv", "uv.exe"}:
        if len(repaired_argv) < 2 or str(repaired_argv[1]).lower() not in _ALLOWED_UV_COMMANDS:
            return False, "unsupported_uv_subcommand", [], []
        return True, "", repaired_argv, repair_notes

    if first in {"cargo", "cargo.exe"}:
        if len(repaired_argv) < 2 or str(repaired_argv[1]).lower() not in _ALLOWED_CARGO_COMMANDS:
            return False, "unsupported_cargo_subcommand", [], []
        return True, "", repaired_argv, repair_notes

    if first in {"node", "node.exe"}:
        if len(repaired_argv) < 2:
            return False, "missing_node_script", [], []
        script_path = _resolve_path(repaired_argv[1], base=workdir)
        if script_path is None or not _is_allowed_path(script_path):
            return False, "unsafe_node_script", [], []
        repaired_argv[1] = str(script_path)
        return True, "", repaired_argv, repair_notes

    if first in {"python", "python.exe", "py", "py.exe"}:
        if len(repaired_argv) < 2:
            return False, "missing_python_target", [], []
        if str(repaired_argv[1]) == "-m":
            if len(repaired_argv) < 3 or str(repaired_argv[2]).lower() not in _ALLOWED_PYTHON_MODULES:
                return False, "unsupported_python_module", [], []
            return True, "", repaired_argv, repair_notes
        if str(repaired_argv[1]).startswith("-"):
            return False, "unsupported_python_flags", [], []
        script_path = _resolve_path(repaired_argv[1], base=workdir)
        if script_path is None or script_path.suffix.lower() != ".py" or not _is_allowed_path(script_path):
            return False, "unsafe_python_script", [], []
        repaired_argv[1] = str(script_path)
        return True, "", repaired_argv, repair_notes

    return False, "unsupported_command", [], []


def _build_failure(reply: str, *, observed_state: str, drift_reason: str, repair_hint: str, command: str, verification_detail: str, repair_notes: list[str] | None = None) -> dict:
    result = build_operation_result(
        reply,
        expected_state="command_succeeded",
        observed_state=observed_state,
        drift_reason=drift_reason,
        repair_hint=repair_hint,
        repair_attempted=bool(repair_notes),
        repair_succeeded=False,
        action_kind="run_command",
        target_kind="process",
        target=command[:200],
        outcome="failed",
        display_hint="本地命令执行失败",
        verification_mode="command_runner",
        verification_detail=verification_detail,
    )
    result["verification"] = {
        "verified": False,
        "observed_state": observed_state,
        "detail": verification_detail,
    }
    return result


def _humanize_block_reason(reason: str) -> str:
    mapping = {
        "missing_command": "缺少命令",
        "shell_control_operator": "不允许命令链或重定向",
        "dangerous_command": "命令被安全策略拦截",
        "use_protocol_file_action": "文件操作应改用文件技能",
        "unsupported_executable": "可执行程序不在允许列表",
        "unsupported_pip_subcommand": "pip 子命令不受支持",
        "unsupported_node_subcommand": "Node 子命令不受支持",
        "unsupported_uv_subcommand": "uv 子命令不受支持",
        "unsupported_cargo_subcommand": "cargo 子命令不受支持",
        "missing_node_script": "缺少 Node 脚本路径",
        "unsafe_node_script": "Node 脚本路径不在允许范围",
        "missing_python_target": "缺少 Python 目标",
        "unsupported_python_module": "Python 模块不受支持",
        "unsupported_python_flags": "Python 启动参数不受支持",
        "unsafe_python_script": "Python 脚本路径不在允许范围",
        "cmd_requires_script": "cmd 只能执行 bat/cmd 脚本",
        "unsafe_script_target": "脚本路径不在允许范围",
        "unsupported_command": "命令不受支持",
    }
    return mapping.get(str(reason or "").strip(), "命令被当前策略拦截")


def _explicit_background_requested(context: dict) -> bool | None:
    raw = context.get("background")
    if isinstance(raw, bool):
        return raw
    text = str(raw or "").strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def _command_targets_persistent_process(argv: list[str]) -> bool:
    if not argv:
        return False
    first = str(argv[0]).lower()
    if first in {"npm", "npm.cmd", "pnpm", "pnpm.cmd", "yarn", "yarn.cmd"}:
        if len(argv) >= 3 and str(argv[1]).lower() == "run" and str(argv[2]).lower() in {"dev", "start", "serve"}:
            return True
        if len(argv) >= 2 and str(argv[1]).lower() in {"start", "serve"}:
            return True
        return False

    if first in {"uv", "uv.exe"} and len(argv) >= 3 and str(argv[1]).lower() == "run":
        lowered = " ".join(str(token).lower() for token in argv[2:])
        if any(marker in lowered for marker in _BACKGROUND_MODULE_MARKERS):
            return True
        for token in argv[2:]:
            token_text = str(token).strip()
            if token_text.lower().endswith(".py") and Path(token_text).stem.lower() in _BACKGROUND_SCRIPT_STEMS:
                return True
        return False

    if first in {"python", "python.exe", "py", "py.exe"}:
        if len(argv) >= 3 and str(argv[1]).lower() == "-m":
            return str(argv[2]).lower() in _BACKGROUND_MODULE_MARKERS
        if len(argv) >= 2:
            target = str(argv[1]).strip()
            if target.lower().endswith(".py") and Path(target).stem.lower() in _BACKGROUND_SCRIPT_STEMS:
                return True
        return False

    if first in {"node", "node.exe"} and len(argv) >= 2:
        target = str(argv[1]).strip()
        return target.lower().endswith((".js", ".mjs", ".cjs")) and Path(target).stem.lower() in _BACKGROUND_SCRIPT_STEMS

    return False


def _should_background_launch(context: dict, argv: list[str], expected_artifacts: list[Path]) -> bool:
    if expected_artifacts:
        return False
    if _context_execution_lane(context) == "verify" and _explicit_background_requested(context) is None:
        return False
    explicit = _explicit_background_requested(context)
    if explicit is not None:
        return explicit
    description = str(context.get("description") or "").strip().lower()
    if not description:
        return False
    if any(marker in description for marker in _BACKGROUND_NEGATIVE_HINTS):
        return False
    if not any(marker in description for marker in _BACKGROUND_DESCRIPTION_HINTS):
        return False
    return _command_targets_persistent_process(argv)


def _build_success_result(
    reply: str,
    *,
    expected_state: str,
    observed_state: str,
    target_kind: str,
    target: str,
    outcome: str,
    display_hint: str,
    verification_mode: str,
    verification_detail: str,
    repair_notes: list[str] | None = None,
) -> dict:
    result = build_operation_result(
        reply,
        expected_state=expected_state,
        observed_state=observed_state,
        repair_attempted=bool(repair_notes),
        repair_succeeded=bool(repair_notes),
        action_kind="run_command",
        target_kind=target_kind,
        target=target,
        outcome=outcome,
        display_hint=display_hint,
        verification_mode=verification_mode,
        verification_detail=verification_detail,
    )
    result["verification"] = {
        "verified": True,
        "observed_state": observed_state,
        "detail": verification_detail,
    }
    return result


def _launch_background_command(
    command: str,
    argv: list[str],
    *,
    workdir: Path,
    description: str,
    context: dict,
    repair_notes: list[str] | None = None,
) -> dict:
    startup_wait = _resolve_startup_wait(context)
    popen_kwargs = {
        "cwd": str(workdir),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "shell": False,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    try:
        process = subprocess.Popen(argv, **popen_kwargs)
    except FileNotFoundError:
        return _build_failure_detailed(
            "本地命令启动失败：系统里没找到这个可执行程序。",
            observed_state="command_not_found",
            drift_reason="command_not_found",
            repair_hint="install_or_use_supported_tooling",
            command=command,
            verification_detail="executable not found",
            display_hint="可执行程序不存在",
            repair_notes=repair_notes,
        )
    except Exception as exc:
        return _build_failure_detailed(
            f"本地命令启动失败：{str(exc)[:120]}",
            observed_state="command_exception",
            drift_reason="command_exception",
            repair_hint="inspect_command_and_runtime",
            command=command,
            verification_detail=str(exc)[:300],
            display_hint="本地命令启动异常",
            repair_notes=repair_notes,
        )

    cooperative_sleep(startup_wait, context, detail="run_command cancelled during background startup wait")
    if process.poll() is None:
        detail_parts = [f"pid={process.pid}", f"startup_wait={startup_wait}s", f"workdir={workdir}"]
        if repair_notes:
            detail_parts.append("; ".join(repair_notes))
        verification_detail = " | ".join(detail_parts)
        return _build_success_result(
            "本地命令已启动，并保持运行。",
            expected_state="process_running",
            observed_state="process_running",
            target_kind="process",
            target=str(process.pid),
            outcome="launched",
            display_hint=description or "已启动本地命令并保持运行",
            verification_mode="process_alive",
            verification_detail=verification_detail,
            repair_notes=repair_notes,
        )

    stdout, stderr = process.communicate()
    output_tail = _summarize_output(stdout, stderr)
    detail_parts = [f"exit_code={int(process.returncode or 0)}", f"startup_wait={startup_wait}s"]
    if repair_notes:
        detail_parts.append("; ".join(repair_notes))
    if output_tail:
        detail_parts.append(output_tail)
    return _build_failure_detailed(
        "本地命令启动后立刻退出了。",
        observed_state="process_exited_early",
        drift_reason="process_exited_early",
        repair_hint="inspect_command_output_or_missing_dependency",
        command=command,
        verification_detail=" | ".join(detail_parts),
        display_hint="本地命令启动后立即退出",
        repair_notes=repair_notes,
    )


def _extract_simple_file_operation(argv: list[str], workdir: Path) -> dict | None:
    if not argv:
        return None
    first = str(argv[0]).lower()
    if first not in _FILE_MANIPULATION_EXECUTABLES:
        return None

    operands = [str(token).strip() for token in argv[1:] if str(token).strip() and not str(token).startswith("-")]
    if len(operands) < 2:
        return {
            "action": "copy" if first in _FILE_COPY_EXECUTABLES else "move",
            "error": "missing_paths",
        }

    src = _resolve_path(operands[0], base=workdir)
    dst = _resolve_path(operands[1], base=workdir)
    return {
        "action": "copy" if first in _FILE_COPY_EXECUTABLES else "move",
        "src": src,
        "dst": dst,
    }


def _execute_simple_file_operation(op: dict, command: str) -> dict:
    action = str(op.get("action") or "").strip()
    src = op.get("src")
    dst = op.get("dst")
    if op.get("error") == "missing_paths" or src is None or dst is None:
        result = build_operation_result(
            "本地命令里的文件操作参数不完整，至少要给出源路径和目标路径。",
            expected_state="destination_exists",
            observed_state="missing_required_args",
            drift_reason="missing_required_args",
            repair_hint="provide_source_and_destination",
            action_kind=action,
            target_kind="file",
            target=str(dst or src or command)[:200],
            outcome="failed",
            display_hint="文件操作参数不完整",
            verification_mode="artifact_exists",
            verification_detail=f"delegated_from=run_command | command={command[:240]}",
        )
        result["verification"] = {
            "verified": False,
            "observed_state": "missing_required_args",
            "detail": f"delegated_from=run_command | command={command[:240]}",
        }
        return result

    if not _is_allowed_path(src) or not _is_allowed_path(dst):
        result = build_operation_result(
            "这条本地文件命令的路径超出了当前允许范围，暂时不执行。",
            expected_state="destination_exists",
            observed_state="unsafe_path",
            drift_reason="unsafe_path",
            repair_hint="use_workspace_desktop_documents_downloads",
            action_kind=action,
            target_kind="file",
            target=str(dst)[:200],
            outcome="failed",
            display_hint="本地文件命令路径不安全",
            verification_mode="artifact_exists",
            verification_detail=f"delegated_from=run_command | source={src} | destination={dst}",
        )
        result["verification"] = {
            "verified": False,
            "observed_state": "unsafe_path",
            "detail": f"delegated_from=run_command | source={src} | destination={dst}",
        }
        return result

    if not src.exists():
        result = build_operation_result(
            f"源路径不存在：`{src}`",
            expected_state="source_exists",
            observed_state="source_missing",
            drift_reason="source_missing",
            repair_hint="check_or_correct_source_path",
            action_kind=action,
            target_kind="file",
            target=str(src)[:200],
            outcome="failed",
            display_hint="源路径不存在",
            verification_mode="artifact_exists",
            verification_detail=f"delegated_from=run_command | source={src} | destination={dst}",
        )
        result["verification"] = {
            "verified": False,
            "observed_state": "source_missing",
            "detail": f"delegated_from=run_command | source={src} | destination={dst}",
        }
        return result

    try:
        if action == "copy":
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        elif action == "move":
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        else:
            raise ValueError(f"unsupported file action: {action}")
    except Exception as exc:
        detail = f"delegated_from=run_command | source={src} | destination={dst} | error={str(exc)[:200]}"
        result = build_operation_result(
            f"本地文件操作失败：{str(exc)[:120]}",
            expected_state="destination_exists",
            observed_state="file_operation_failed",
            drift_reason="file_operation_failed",
            repair_hint="inspect_source_destination_permissions",
            action_kind=action,
            target_kind="file",
            target=str(dst)[:200],
            outcome="failed",
            display_hint="本地文件操作失败",
            verification_mode="artifact_exists",
            verification_detail=detail,
        )
        result["verification"] = {
            "verified": False,
            "observed_state": "file_operation_failed",
            "detail": detail,
        }
        return result

    exists = dst.exists()
    detail = f"delegated_from=run_command | source={src} | destination={dst}"
    display = "已通过本地命令完成文件复制" if action == "copy" else "已通过本地命令完成文件移动"
    result = build_operation_result(
        "本地文件操作已完成。" if exists else "本地文件操作执行结束，但未确认到目标产物。",
        expected_state="destination_exists",
        observed_state="destination_exists" if exists else "destination_missing",
        drift_reason="" if exists else "destination_missing",
        repair_hint="" if exists else "check_destination",
        action_kind=action,
        target_kind="folder" if dst.is_dir() else "file",
        target=str(dst)[:200],
        outcome="verified" if exists else "failed",
        display_hint=display,
        verification_mode="artifact_exists",
        verification_detail=detail,
    )
    result["verification"] = {
        "verified": exists,
        "observed_state": "destination_exists" if exists else "destination_missing",
        "detail": detail,
    }
    return result


def _execute_legacy_run_command(query, context=None):
    context = context if isinstance(context, dict) else {}
    command = str(context.get("command") or context.get("cmd") or query or "").strip()
    description = str(context.get("description") or "").strip()
    workdir = _resolve_workdir(context)

    if not _is_allowed_path(workdir):
        return _build_failure(
            "工作目录不在允许范围内，暂时不能执行这个本地命令。",
            observed_state="unsafe_workdir",
            drift_reason="unsafe_workdir",
            repair_hint="use_workspace_or_desktop_related_directory",
            command=command,
            verification_detail=str(workdir),
        )

    if not workdir.exists():
        return _build_failure(
            "工作目录不存在，没法开始执行本地命令。",
            observed_state="workdir_missing",
            drift_reason="workdir_missing",
            repair_hint="check_or_correct_workdir",
            command=command,
            verification_detail=str(workdir),
        )

    argv = _split_command(command)
    file_op = _extract_simple_file_operation(argv, workdir)
    if file_op:
        return _execute_simple_file_operation(file_op, command)
    ok, reason, repaired_argv, repair_notes = _validate_command(argv, workdir)
    if not ok:
        if reason == "use_protocol_file_action":
            return _build_failure(
                "这不是 run_command（本地命令执行）该接的动作。文件复制、移动、删除请改用 file_copy / file_move / file_delete 这类协议技能。",
                observed_state="wrong_tool_selected",
                drift_reason="wrong_tool_selected",
                repair_hint="use_file_copy_or_file_move",
                command=command,
                verification_detail=f"file manipulation command should use protocol skill: {command[:240]}",
            )
        detail = reason if not command else f"{reason}: {command[:240]}"
        return _build_failure(
            "这条命令超出当前安全范围，暂时不执行。",
            observed_state="command_blocked",
            drift_reason="disallowed_command",
            repair_hint="use_supported_build_test_package_command",
            command=command,
            verification_detail=detail,
        )

    timeout_sec = _resolve_timeout(context)
    expected_artifacts = _resolve_expected_artifacts(context, workdir, repaired_argv)
    verification_mode = "artifact_exists" if expected_artifacts else "exit_code"

    try:
        completed = subprocess.run(
            repaired_argv,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        output_tail = _summarize_output(exc.stdout or "", exc.stderr or "")
        detail_parts = [f"timeout={timeout_sec}s"]
        if repair_notes:
            detail_parts.append("; ".join(repair_notes))
        if output_tail:
            detail_parts.append(output_tail)
        return _build_failure(
            "本地命令超时了，构建还没有在限定时间内完成。",
            observed_state="command_timeout",
            drift_reason="command_timeout",
            repair_hint="increase_timeout_or_reduce_scope",
            command=command,
            verification_detail=" | ".join(detail_parts),
            repair_notes=repair_notes,
        )
    except FileNotFoundError:
        return _build_failure(
            "本地命令启动失败：系统里没找到这个可执行程序。",
            observed_state="command_not_found",
            drift_reason="command_not_found",
            repair_hint="install_or_use_supported_tooling",
            command=command,
            verification_detail="executable not found",
            repair_notes=repair_notes,
        )
    except Exception as exc:
        return _build_failure(
            f"本地命令执行失败：{str(exc)[:120]}",
            observed_state="command_exception",
            drift_reason="command_exception",
            repair_hint="inspect_command_and_runtime",
            command=command,
            verification_detail=str(exc)[:300],
            repair_notes=repair_notes,
        )

    output_tail = _summarize_output(completed.stdout, completed.stderr)
    exit_code = int(completed.returncode or 0)
    missing_artifacts = [path for path in expected_artifacts if not path.exists()]
    verified = exit_code == 0 and not missing_artifacts

    detail_parts = [f"exit_code={exit_code}"]
    if repair_notes:
        detail_parts.append("; ".join(repair_notes))
    if expected_artifacts:
        detail_parts.append("artifacts=" + ", ".join(str(path) for path in expected_artifacts[:3]))
    if missing_artifacts:
        detail_parts.append("missing=" + ", ".join(str(path) for path in missing_artifacts[:3]))
    if output_tail:
        detail_parts.append(output_tail)
    verification_detail = " | ".join(detail_parts)

    if verified:
        target_kind = "artifact" if expected_artifacts else "process"
        target = str(expected_artifacts[0] if expected_artifacts else workdir)
        summary = description or ("已执行本地命令并确认产物" if expected_artifacts else "已执行本地命令")
        result = build_operation_result(
            "本地命令已执行完成。" if not expected_artifacts else "本地构建已完成，并确认产物已经生成。",
            expected_state="artifacts_ready" if expected_artifacts else "command_succeeded",
            observed_state="artifacts_ready" if expected_artifacts else "command_succeeded",
            repair_attempted=bool(repair_notes),
            repair_succeeded=bool(repair_notes),
            action_kind="run_command",
            target_kind=target_kind,
            target=target,
            outcome="verified",
            display_hint=summary,
            verification_mode=verification_mode,
            verification_detail=verification_detail,
        )
        result["verification"] = {
            "verified": True,
            "observed_state": "artifacts_ready" if expected_artifacts else "command_succeeded",
            "detail": verification_detail,
        }
        return result

    if expected_artifacts and not missing_artifacts:
        observed_state = "command_failed"
        drift_reason = "command_nonzero_exit"
        repair_hint = "inspect_command_output"
    elif expected_artifacts:
        observed_state = "artifact_missing"
        drift_reason = "artifact_missing"
        repair_hint = "fix_build_command_or_expected_artifact"
    else:
        observed_state = "command_failed"
        drift_reason = "command_nonzero_exit"
        repair_hint = "inspect_command_output"

    result = build_operation_result(
        "本地命令执行结束了，但结果没有通过验证。",
        expected_state="artifacts_ready" if expected_artifacts else "command_succeeded",
        observed_state=observed_state,
        drift_reason=drift_reason,
        repair_hint=repair_hint,
        repair_attempted=bool(repair_notes),
        repair_succeeded=False,
        action_kind="run_command",
        target_kind="artifact" if expected_artifacts else "process",
        target=str(expected_artifacts[0] if expected_artifacts else workdir),
        outcome="failed",
        display_hint="本地命令执行结束但未通过验证",
        verification_mode=verification_mode,
        verification_detail=verification_detail,
    )
    result["verification"] = {
        "verified": False,
        "observed_state": observed_state,
        "detail": verification_detail,
    }
    return result


def _build_failure_detailed(
    reply: str,
    *,
    observed_state: str,
    drift_reason: str,
    repair_hint: str,
    command: str,
    verification_detail: str,
    display_hint: str,
    repair_notes: list[str] | None = None,
) -> dict:
    result = build_operation_result(
        reply,
        expected_state="command_succeeded",
        observed_state=observed_state,
        drift_reason=drift_reason,
        repair_hint=repair_hint,
        repair_attempted=bool(repair_notes),
        repair_succeeded=False,
        action_kind="run_command",
        target_kind="process",
        target=command[:200],
        outcome="failed",
        display_hint=display_hint,
        verification_mode="command_runner",
        verification_detail=verification_detail,
    )
    result["verification"] = {
        "verified": False,
        "observed_state": observed_state,
        "detail": verification_detail,
    }
    return result


def execute(query, context=None):
    context = context if isinstance(context, dict) else {}
    raise_if_cancelled(context, detail="run_command cancelled before start")
    command = str(context.get("command") or context.get("cmd") or query or "").strip()
    description = str(context.get("description") or "").strip() or _context_step_title(context)
    workdir = _resolve_workdir(context)

    if not _is_allowed_path(workdir):
        return _build_failure_detailed(
            f"工作目录不在允许范围内：{workdir}",
            observed_state="unsafe_workdir",
            drift_reason="unsafe_workdir",
            repair_hint="use_workspace_or_desktop_related_directory",
            command=command,
            verification_detail=str(workdir),
            display_hint="工作目录不在允许范围",
        )

    if not workdir.exists():
        return _build_failure_detailed(
            f"工作目录不存在：{workdir}",
            observed_state="workdir_missing",
            drift_reason="workdir_missing",
            repair_hint="check_or_correct_workdir",
            command=command,
            verification_detail=str(workdir),
            display_hint="工作目录不存在",
        )

    argv = _split_command(command)
    file_op = _extract_simple_file_operation(argv, workdir)
    if file_op:
        return _execute_simple_file_operation(file_op, command)

    ok, reason, repaired_argv, repair_notes = _validate_command(argv, workdir)
    if not ok:
        if reason == "use_protocol_file_action":
            return _build_failure_detailed(
                "这不是 run_command 该接的动作。文件复制、移动、删除请改用 file_copy / file_move / file_delete。",
                observed_state="wrong_tool_selected",
                drift_reason="wrong_tool_selected",
                repair_hint="use_file_copy_or_file_move",
                command=command,
                verification_detail=f"file manipulation command should use protocol skill: {command[:240]}",
                display_hint="文件操作应改用文件技能",
            )
        detail = reason if not command else f"{reason}: {command[:240]}"
        return _build_failure_detailed(
            f"这条命令被当前策略拦截：{_humanize_block_reason(reason)}",
            observed_state="command_blocked",
            drift_reason="disallowed_command",
            repair_hint="use_supported_build_test_package_command",
            command=command,
            verification_detail=detail,
            display_hint=f"命令被拦截：{_humanize_block_reason(reason)}",
        )

    timeout_sec = _resolve_timeout(context)
    expected_artifacts = _resolve_expected_artifacts(context, workdir, repaired_argv)
    if _should_background_launch(context, repaired_argv, expected_artifacts):
        return _launch_background_command(
            command,
            repaired_argv,
            workdir=workdir,
            description=description,
            context=context,
            repair_notes=repair_notes,
        )

    verification_mode = "artifact_exists" if expected_artifacts else "exit_code"

    try:
        raise_if_cancelled(context, detail="run_command cancelled before subprocess.run")
        completed = subprocess.run(
            repaired_argv,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            shell=False,
        )
        raise_if_cancelled(context, detail="run_command cancelled after subprocess.run")
    except subprocess.TimeoutExpired as exc:
        output_tail = _summarize_output(exc.stdout or "", exc.stderr or "")
        detail_parts = [f"timeout={timeout_sec}s"]
        if repair_notes:
            detail_parts.append("; ".join(repair_notes))
        if output_tail:
            detail_parts.append(output_tail)
        return _build_failure_detailed(
            "本地命令执行超时了。",
            observed_state="command_timeout",
            drift_reason="command_timeout",
            repair_hint="increase_timeout_or_reduce_scope",
            command=command,
            verification_detail=" | ".join(detail_parts),
            display_hint="本地命令执行超时",
            repair_notes=repair_notes,
        )
    except FileNotFoundError:
        return _build_failure_detailed(
            "本地命令启动失败：系统里没找到这个可执行程序。",
            observed_state="command_not_found",
            drift_reason="command_not_found",
            repair_hint="install_or_use_supported_tooling",
            command=command,
            verification_detail="executable not found",
            display_hint="可执行程序不存在",
            repair_notes=repair_notes,
        )
    except Exception as exc:
        return _build_failure_detailed(
            f"本地命令执行异常：{str(exc)[:120]}",
            observed_state="command_exception",
            drift_reason="command_exception",
            repair_hint="inspect_command_and_runtime",
            command=command,
            verification_detail=str(exc)[:300],
            display_hint="本地命令执行异常",
            repair_notes=repair_notes,
        )

    output_tail = _summarize_output(completed.stdout, completed.stderr)
    exit_code = int(completed.returncode or 0)
    missing_artifacts = [path for path in expected_artifacts if not path.exists()]
    verified = exit_code == 0 and not missing_artifacts

    detail_parts = [f"exit_code={exit_code}"]
    if repair_notes:
        detail_parts.append("; ".join(repair_notes))
    if expected_artifacts:
        detail_parts.append("artifacts=" + ", ".join(str(path) for path in expected_artifacts[:3]))
    if missing_artifacts:
        detail_parts.append("missing=" + ", ".join(str(path) for path in missing_artifacts[:3]))
    if output_tail:
        detail_parts.append(output_tail)
    verification_detail = " | ".join(detail_parts)

    if verified:
        target_kind = "artifact" if expected_artifacts else "process"
        target = str(expected_artifacts[0] if expected_artifacts else workdir)
        summary = description or ("已执行本地命令并确认产物" if expected_artifacts else "已执行本地命令")
        return _build_success_result(
            "本地命令已执行完成。" if not expected_artifacts else "本地构建已完成，并确认产物已经生成。",
            expected_state="artifacts_ready" if expected_artifacts else "command_succeeded",
            observed_state="artifacts_ready" if expected_artifacts else "command_succeeded",
            target_kind=target_kind,
            target=target,
            outcome="verified",
            display_hint=summary,
            verification_mode=verification_mode,
            verification_detail=verification_detail,
            repair_notes=repair_notes,
        )

    if expected_artifacts and not missing_artifacts:
        observed_state = "command_failed"
        drift_reason = "command_nonzero_exit"
        repair_hint = "inspect_command_output"
    elif expected_artifacts:
        observed_state = "artifact_missing"
        drift_reason = "artifact_missing"
        repair_hint = "fix_build_command_or_expected_artifact"
    else:
        observed_state = "command_failed"
        drift_reason = "command_nonzero_exit"
        repair_hint = "inspect_command_output"

    summary_tail = output_tail or f"exit_code={exit_code}"
    result = build_operation_result(
        f"本地命令执行结束了，但没有通过验证：{summary_tail[:200]}",
        expected_state="artifacts_ready" if expected_artifacts else "command_succeeded",
        observed_state=observed_state,
        drift_reason=drift_reason,
        repair_hint=repair_hint,
        repair_attempted=bool(repair_notes),
        repair_succeeded=False,
        action_kind="run_command",
        target_kind="artifact" if expected_artifacts else "process",
        target=str(expected_artifacts[0] if expected_artifacts else workdir),
        outcome="failed",
        display_hint="本地命令执行失败",
        verification_mode=verification_mode,
        verification_detail=verification_detail,
    )
    result["verification"] = {
        "verified": False,
        "observed_state": observed_state,
        "detail": verification_detail,
    }
    return result
