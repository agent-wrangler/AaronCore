import os
import re
import shutil
from pathlib import Path


def _extract_paths(query: str):
    raw = str(query or '').strip()
    quoted = re.findall(r'"([A-Za-z]:[^"]+)"', raw)
    if quoted:
        return quoted
    fallback = re.findall(r'([A-Za-z]:\\[^\s]+|[A-Za-z]:/[^\s]+)', raw)
    return fallback


def _normalize_path(p: str) -> Path:
    return Path(str(p).strip().strip('"'))


def execute(query, context=None):
    context = context if isinstance(context, dict) else {}
    fs_target = context.get('fs_target') if isinstance(context.get('fs_target'), dict) else {}
    fs_action = context.get('fs_action') if isinstance(context.get('fs_action'), dict) else {}
    target_info = fs_action.get('target') if isinstance(fs_action.get('target'), dict) else {}
    destination_info = fs_action.get('destination') if isinstance(fs_action.get('destination'), dict) else {}
    paths = _extract_paths(query)
    if len(paths) < 2:
        source_hint = str(target_info.get('path') or fs_target.get('path') or context.get('source_path') or '').strip()
        dest_hint = str(destination_info.get('path') or context.get('destination_path') or context.get('target_path') or '').strip()
        if source_hint and dest_hint:
            paths = [source_hint, dest_hint]
        elif len(paths) == 1 and dest_hint:
            paths = [paths[0], dest_hint]
        elif len(paths) == 0 and source_hint:
            paths = [source_hint]
    if len(paths) < 2:
        return '复制文件至少要给我两个路径：源路径和目标路径。最好都用引号包起来。'
    src = _normalize_path(paths[0])
    dst = _normalize_path(paths[1])
    if not src.exists():
        return f'源路径不存在：`{src}`'
    try:
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        return f'已复制：`{src}` → `{dst}`'
    except Exception as e:
        return f'复制失败：{e}'
