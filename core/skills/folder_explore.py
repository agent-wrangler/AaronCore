import json
import os
import re
from pathlib import Path

from core.fs_protocol import build_operation_result

IMPORTANT_NAMES = {
    'readme.md', 'claude.md', 'package.json', 'requirements.txt', 'pyproject.toml',
    'setup.py', 'main.py', 'app.py', 'index.js', 'index.ts', 'vite.config.js',
    'vite.config.ts', 'tsconfig.json', 'cargo.toml', 'go.mod', '.env.example'
}
TEXT_SUFFIXES = {'.md', '.txt', '.json', '.py', '.js', '.ts', '.tsx', '.jsx', '.toml', '.yml', '.yaml'}


def _extract_path(query: str) -> str:
    raw = str(query or '').strip()
    m = re.search(r'"([A-Za-z]:\\[^\"]+)"', raw)
    if m:
        return m.group(1)
    m = re.search(r'([A-Za-z]:\\[^\s]+)', raw)
    if m:
        return m.group(1)
    m = re.search(r'"([A-Za-z]:/[^\"]+)"', raw)
    if m:
        return m.group(1)
    m = re.search(r'([A-Za-z]:/[^\s]+)', raw)
    if m:
        return m.group(1)
    return ''


def _pick_key_files(path: Path):
    files = [p for p in path.iterdir() if p.is_file()]
    scored = []
    for f in files:
        score = 0
        name = f.name.lower()
        if name in IMPORTANT_NAMES:
            score += 100
        if f.suffix.lower() in TEXT_SUFFIXES:
            score += 20
        if name.startswith('readme'):
            score += 50
        if name in {'main.py', 'app.py', 'package.json', 'requirements.txt', 'claude.md'}:
            score += 40
        scored.append((score, f))
    scored.sort(key=lambda x: (-x[0], x[1].name.lower()))
    return [f for _, f in scored[:3]]


def _read_text_file(path: Path) -> str:
    try:
        text = path.read_text(encoding='utf-8')
    except Exception:
        try:
            text = path.read_text(encoding='utf-8-sig')
        except Exception:
            return ''
    lines = text.splitlines()
    return '\n'.join(lines[:60]).strip()


def _summarize_folder(path: Path, dirs, files, key_files, previews):
    lines = [f'我看过这个文件夹了：`{path}`']
    lines.append(f'里面有 {len(dirs)} 个子目录，{len(files)} 个文件。')
    if dirs:
        lines.append('目录：')
        lines.extend([f'- {d.name}/' for d in dirs[:12]])
    if files:
        lines.append('文件：')
        lines.extend([f'- {f.name}' for f in files[:12]])
    if key_files:
        lines.append('\n我优先看了这几个关键文件：')
        for f in key_files:
            lines.append(f'- {f.name}')
    if previews:
        lines.append('\n初步判断：')
        for name, preview in previews:
            first = preview.splitlines()[0].strip() if preview else ''
            if first:
                lines.append(f'- {name}: {first[:120]}')
    lines.append('\n如果你愿意，我下一步可以继续：读某个具体文件、继续深挖某个子目录，或者总结这个目录是做什么的。')
    return '\n'.join(lines)


def execute(query, context=None):
    context = context if isinstance(context, dict) else {}
    fs_target = context.get('fs_target') if isinstance(context.get('fs_target'), dict) else {}
    folder_path = (
        str(fs_target.get('path') or '').strip()
        or str(context.get('path') or '').strip()
        or str(context.get('target') or '').strip()
        or _extract_path(query)
    )
    if not folder_path:
        context_data = context.get('context_data') if isinstance(context.get('context_data'), dict) else {}
        fs_target = context_data.get('fs_target') if isinstance(context_data.get('fs_target'), dict) else {}
        folder_path = str(fs_target.get('path') or '').strip()
    if not folder_path:
        return build_operation_result(
            '这次没有收到要查看的文件夹目标，所以还没法开始浏览目录。'
            '如果上游已经知道目标目录，应该把它作为 `fs_target.path` 或 `path` 传进来；'
            '如果是用户直接指定，也可以给完整路径。',
            expected_state='directory_listed',
            observed_state='path_missing',
            drift_reason='missing_target',
            repair_hint='provide_or_pass_folder_target',
            repair_attempted=False,
            repair_succeeded=False,
        )

    path = Path(folder_path)
    if not path.exists() and path.suffix and path.parent.exists() and path.parent.is_dir():
        path = path.parent
    if path.exists() and path.is_file():
        path = path.parent
    if not path.exists():
        return build_operation_result(
            f'这个路径不存在：`{folder_path}`',
            expected_state='directory_listed',
            observed_state='path_missing',
            drift_reason='target_not_found',
            repair_hint='check_or_correct_path',
            repair_attempted=False,
            repair_succeeded=False,
        )
    if not path.is_dir():
        return build_operation_result(
            f'这个路径不是文件夹：`{folder_path}`',
            expected_state='directory_listed',
            observed_state='not_a_directory',
            drift_reason='not_a_directory',
            repair_hint='use_folder_target',
            repair_attempted=False,
            repair_succeeded=False,
        )

    try:
        entries = list(path.iterdir())
    except Exception as e:
        return build_operation_result(
            f'我没法读取这个文件夹：{e}',
            expected_state='directory_listed',
            observed_state='read_failed',
            drift_reason='read_failed',
            repair_hint='check_permissions_or_retry',
            repair_attempted=False,
            repair_succeeded=False,
        )

    dirs = sorted([p for p in entries if p.is_dir()], key=lambda p: p.name.lower())
    files = sorted([p for p in entries if p.is_file()], key=lambda p: p.name.lower())
    key_files = _pick_key_files(path)
    previews = []
    for f in key_files:
        preview = _read_text_file(f)
        if preview:
            previews.append((f.name, preview))

    return build_operation_result(
        _summarize_folder(path, dirs, files, key_files, previews),
        expected_state='directory_listed',
        observed_state='directory_listed',
        drift_reason='',
        repair_hint='',
        repair_attempted=False,
        repair_succeeded=True,
    )
