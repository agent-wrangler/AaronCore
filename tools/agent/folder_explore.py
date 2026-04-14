import re
from pathlib import Path

from core.fs_protocol import build_operation_result

IMPORTANT_NAMES = {
    "readme.md",
    "claude.md",
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "main.py",
    "app.py",
    "index.js",
    "index.ts",
    "vite.config.js",
    "vite.config.ts",
    "tsconfig.json",
    "cargo.toml",
    "go.mod",
    ".env.example",
}
TEXT_SUFFIXES = {".md", ".txt", ".json", ".py", ".js", ".ts", ".tsx", ".jsx", ".toml", ".yml", ".yaml"}


def _extract_path(query: str) -> str:
    raw = str(query or "").strip()
    patterns = (
        r'"([A-Za-z]:\\[^"]+)"',
        r"([A-Za-z]:\\[^\s]+)",
        r'"([A-Za-z]:/[^"]+)"',
        r"([A-Za-z]:/[^\s]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, raw)
        if match:
            return match.group(1)
    return ""


def _pick_key_files(path: Path):
    files = [p for p in path.iterdir() if p.is_file()]
    scored = []
    for file_path in files:
        score = 0
        name = file_path.name.lower()
        if name in IMPORTANT_NAMES:
            score += 100
        if file_path.suffix.lower() in TEXT_SUFFIXES:
            score += 20
        if name.startswith("readme"):
            score += 50
        if name in {"main.py", "app.py", "package.json", "requirements.txt", "claude.md"}:
            score += 40
        scored.append((score, file_path))
    scored.sort(key=lambda item: (-item[0], item[1].name.lower()))
    return [file_path for _, file_path in scored[:3]]


def _read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig"):
        try:
            text = path.read_text(encoding=encoding)
            lines = text.splitlines()
            return "\n".join(lines[:60]).strip()
        except Exception:
            continue
    return ""


def _summarize_folder(path: Path, dirs, files, key_files, previews):
    lines = [f"我看过这个文件夹了：`{path}`"]
    lines.append(f"里面有 {len(dirs)} 个子目录，{len(files)} 个文件。")
    if dirs:
        lines.append("目录：")
        lines.extend([f"- {directory.name}/" for directory in dirs[:12]])
    if files:
        lines.append("文件：")
        lines.extend([f"- {file_path.name}" for file_path in files[:12]])
    if key_files:
        lines.append("\n我优先看了这几个关键文件：")
        for file_path in key_files:
            lines.append(f"- {file_path.name}")
    if previews:
        lines.append("\n初步判断：")
        for name, preview in previews:
            first = preview.splitlines()[0].strip() if preview else ""
            if first:
                lines.append(f"- {name}: {first[:120]}")
    lines.append("\n如果你愿意，我下一步可以继续：读某个具体文件、继续深挖某个子目录，或者总结这个目录是做什么的。")
    return "\n".join(lines)


def execute(query, context=None):
    context = context if isinstance(context, dict) else {}
    fs_target = context.get("fs_target") if isinstance(context.get("fs_target"), dict) else {}
    folder_path = (
        str(fs_target.get("path") or "").strip()
        or str(context.get("path") or "").strip()
        or str(context.get("target") or "").strip()
        or _extract_path(query)
    )
    if not folder_path:
        context_data = context.get("context_data") if isinstance(context.get("context_data"), dict) else {}
        fs_target = context_data.get("fs_target") if isinstance(context_data.get("fs_target"), dict) else {}
        folder_path = str(fs_target.get("path") or "").strip()

    if not folder_path:
        return build_operation_result(
            "这次没有收到要查看的文件夹目标，所以还没法开始浏览目录。"
            "如果上游已经知道目标目录，应该把它作为 `fs_target.path` 或 `path` 传进来；"
            "如果是用户直接指定，也可以给完整路径。",
            expected_state="directory_listed",
            observed_state="path_missing",
            drift_reason="missing_target",
            repair_hint="provide_or_pass_folder_target",
            repair_attempted=False,
            repair_succeeded=False,
            action_kind="resolve_directory",
            target_kind="directory",
            outcome="missing_target",
            display_hint="目录目标缺失",
            verification_mode="argument_check",
            verification_detail="missing:path",
        )

    path = Path(folder_path)
    if not path.exists() and path.suffix and path.parent.exists() and path.parent.is_dir():
        path = path.parent
    if path.exists() and path.is_file():
        path = path.parent

    if not path.exists():
        return build_operation_result(
            f"这个路径不存在：`{folder_path}`",
            expected_state="directory_listed",
            observed_state="path_missing",
            drift_reason="target_not_found",
            repair_hint="check_or_correct_path",
            repair_attempted=False,
            repair_succeeded=False,
            action_kind="resolve_directory",
            target_kind="directory",
            target=str(folder_path),
            outcome="unresolved",
            display_hint=f"目录未找到：{folder_path}",
            verification_mode="path_exists",
            verification_detail=f"path_not_found:{folder_path}",
        )

    if not path.is_dir():
        return build_operation_result(
            f"这个路径不是文件夹：`{folder_path}`",
            expected_state="directory_listed",
            observed_state="not_a_directory",
            drift_reason="not_a_directory",
            repair_hint="use_folder_target",
            repair_attempted=False,
            repair_succeeded=False,
            action_kind="resolve_directory",
            target_kind="directory",
            target=str(folder_path),
            outcome="not_a_directory",
            display_hint=f"目标不是目录：{folder_path}",
            verification_mode="path_type",
            verification_detail=f"not_a_directory:{folder_path}",
        )

    try:
        entries = list(path.iterdir())
    except Exception as exc:
        return build_operation_result(
            f"我没法读取这个文件夹：{exc}",
            expected_state="directory_listed",
            observed_state="read_failed",
            drift_reason="read_failed",
            repair_hint="check_permissions_or_retry",
            repair_attempted=False,
            repair_succeeded=False,
            action_kind="resolve_directory",
            target_kind="directory",
            target=str(path),
            outcome="read_failed",
            display_hint=f"目录读取失败：{path}",
            verification_mode="directory_read",
            verification_detail=f"read_failed:{type(exc).__name__}",
        )

    dirs = sorted([item for item in entries if item.is_dir()], key=lambda item: item.name.lower())
    files = sorted([item for item in entries if item.is_file()], key=lambda item: item.name.lower())
    key_files = _pick_key_files(path)
    previews = []
    for file_path in key_files:
        preview = _read_text_file(file_path)
        if preview:
            previews.append((file_path.name, preview))

    return build_operation_result(
        _summarize_folder(path, dirs, files, key_files, previews),
        expected_state="directory_listed",
        observed_state="directory_listed",
        drift_reason="",
        repair_hint="",
        repair_attempted=False,
        repair_succeeded=True,
        action_kind="resolve_directory",
        target_kind="directory",
        target=str(path),
        outcome="resolved",
        display_hint=f"已确认目录：{path}",
        verification_mode="directory_listed",
        verification_detail=f"dirs={len(dirs)} files={len(files)}",
    )
