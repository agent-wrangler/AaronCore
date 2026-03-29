import os
import re
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
    paths = _extract_paths(query)
    if len(paths) < 2 and fs_target.get('path'):
        paths = [str(fs_target.get('path'))]
    if len(paths) < 2:
        return '移动或重命名至少要给我两个路径：原路径和新路径。最好都用引号包起来。'
    src = _normalize_path(paths[0])
    dst = _normalize_path(paths[1])
    if not src.exists():
        return f'原路径不存在：`{src}`'
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return f'已移动/重命名：`{src}` → `{dst}`'
    except Exception as e:
        return f'移动/重命名失败：{e}'
