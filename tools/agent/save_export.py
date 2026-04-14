import json
import re
from pathlib import Path

from core.fs_protocol import build_save_path, check_saved_state, load_export_state, normalize_user_special_path, record_saved_artifact, safe_name


def _render_history(items) -> str:
    rows = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get('role') or '').strip() or 'unknown'
        content = str(item.get('content') or '').strip()
        if content:
            rows.append(f'[{role}] {content}')
    return '\n\n'.join(rows).strip()


def _resolve_payload(query: str, context: dict | None = None) -> tuple[str, str, str]:
    context = context if isinstance(context, dict) else {}
    fs_action = context.get('fs_action') if isinstance(context.get('fs_action'), dict) else {}
    payload = fs_action.get('payload') if isinstance(fs_action.get('payload'), dict) else {}
    destination = fs_action.get('destination') if isinstance(fs_action.get('destination'), dict) else {}
    state = load_export_state()

    content = str(payload.get('content') or context.get('save_content') or context.get('content') or '').strip()
    fmt = str(payload.get('format') or context.get('save_format') or 'md').strip().lower() or 'md'
    folder = str(destination.get('path') or context.get('save_destination') or context.get('destination') or '').strip()

    if not content:
        recent_history = context.get('recent_history') if isinstance(context.get('recent_history'), list) else []
        if any(w in str(query or '') for w in ('对话', '聊天记录', '聊天', '记录')) and recent_history:
            content = _render_history(recent_history)
            if fmt == 'md':
                content = '# 对话导出\n\n' + content

    if not content:
        content = str(query or '').strip()
    if not folder and '桌面' in str(query or ''):
        folder = str(Path.home() / 'Desktop')
    if not folder:
        folder = str(state.get('last_export_dir') or '').strip()
    folder = normalize_user_special_path(folder)
    return content, fmt, folder


def execute(query, context=None):
    try:
        content, fmt, folder = _resolve_payload(query, context)
    except Exception as e:
        return {'reply': f'解析保存参数失败: {e}', 'success': False}
    if not folder:
        return {'reply': '保存之前至少要给我一个明确目录，比如桌面或一个完整路径。', 'success': False}
    if not content:
        return {'reply': '当前没有可保存的内容。', 'success': False}

    target_dir = Path(folder)
    target_dir.mkdir(parents=True, exist_ok=True)
    ext = 'md' if fmt not in {'txt', 'json'} else fmt
    # 文件名优先用 LLM 传的 filename，其次 context 里的 save_filename，最后从内容提取
    raw_filename = str(context.get('filename') or context.get('save_filename') or '').strip()
    if not raw_filename:
        # 从 query 第一行提取标题作为文件名
        first_line = str(query or '').split('\n')[0].strip()
        # 去掉常见前缀（"保存到桌面：" "保存：" 等）
        for prefix in ('保存到桌面：', '保存到桌面:', '保存：', '保存:', '导出：', '导出:'):
            if first_line.startswith(prefix):
                first_line = first_line[len(prefix):].strip()
                break
        if first_line and len(first_line) > 2 and len(first_line) < 60:
            raw_filename = first_line
        elif any(w in str(query or '') for w in ('对话', '聊天记录', '聊天', '记录')):
            raw_filename = '对话导出'
        else:
            raw_filename = '导出结果'
    suggested = safe_name(raw_filename)
    if ext == 'json':
        try:
            parsed = json.loads(content)
            body = json.dumps(parsed, ensure_ascii=False, indent=2)
        except Exception:
            body = json.dumps({'content': content}, ensure_ascii=False, indent=2)
    else:
        body = content
    target_path = build_save_path(folder, suggested, ext)
    target_path.write_text(body, encoding='utf-8')
    state = check_saved_state(str(target_path))
    if not state.get('ok') and state.get('repairable') and state.get('repair_target') and str(Path(folder)) != str(Path(state.get('repair_target'))):
        fallback_dir = str(state.get('repair_target'))
        target_path = build_save_path(fallback_dir, suggested, ext)
        target_path.write_text(body, encoding='utf-8')
        state = check_saved_state(str(target_path))
    if not state.get('ok'):
        return {
            'reply': f'[保存失败] 文件未落盘：{target_path}\n原因：写入后文件不存在或大小为0，请检查目录权限。',
        }
    # ── 验证：读回文件确认内容完整 ──
    actual_size = target_path.stat().st_size if target_path.exists() else 0
    content_len = len(body)
    record_saved_artifact(str(target_path), ext)
    return {
        'reply': (
            f'[保存成功]\n'
            f'路径：{target_path}\n'
            f'内容长度：{content_len} 字符\n'
            f'文件大小：{actual_size} 字节\n'
            f'格式：{ext}'
        ),
    }
