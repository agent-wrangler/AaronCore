import os
import re
import shutil
from pathlib import Path


def _extract_path(query: str) -> str:
    raw = str(query or '').strip()
    m = re.search(r'"([A-Za-z]:[^"]+)"', raw)
    if m:
        return m.group(1)
    m = re.search(r'([A-Za-z]:\\[^\s]+|[A-Za-z]:/[^\s]+)', raw)
    if m:
        return m.group(1)
    return ''


def execute(query, context=None):
    context = context if isinstance(context, dict) else {}
    fs_target = context.get('fs_target') if isinstance(context.get('fs_target'), dict) else {}
    target_raw = _extract_path(query) or str(fs_target.get('path') or '').strip()
    if not target_raw:
        return '删除前至少要给我一个明确路径，最好直接带完整路径。'
    target = Path(target_raw)
    if not target.exists():
        return f'要删除的路径不存在：`{target}`'
    try:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return f'已删除：`{target}`'
    except Exception as e:
        return f'删除失败：{e}'
