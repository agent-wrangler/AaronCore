import json
import re
from pathlib import Path

from core.target_protocol import resolve_target_reference

_DANGEROUS_SUFFIXES = {'.exe', '.bat', '.cmd', '.ps1', '.lnk'}


def _extract_json_target(text: str) -> dict:
    raw = str(text or '').strip()
    if not (raw.startswith('{') and raw.endswith('}')):
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_all_abs_paths(text: str) -> list[str]:
    raw = str(text or '').strip()
    quoted = re.findall(r'"([A-Za-z]:\\[^"]+|[A-Za-z]:/[^"]+)"', raw)
    if quoted:
        return quoted
    return re.findall(r'([A-Za-z]:\\[^\s]+|[A-Za-z]:/[^\s]+)', raw)


def _extract_abs_path(text: str) -> str:
    paths = _extract_all_abs_paths(text)
    return paths[0] if paths else ''


def _extract_url(text: str) -> str:
    raw = str(text or '').strip()
    m = re.search(r'(https?://[^\s]+)', raw, flags=re.I)
    if m:
        return m.group(1)
    m = re.search(r'(?:^|\s)([\w.-]+\.[A-Za-z]{2,}(?:/\S*)?)(?:\s|$)', raw)
    if m and not re.search(r'[\u4e00-\u9fff]', m.group(1)) and m.group(1).lower() not in ('screenshot', 'desktop'):
        return m.group(1)
    return ''


def _detect_fs_action(text: str, explicit: str = '', has_url: bool = False) -> str:
    option = str(explicit or '').strip().lower()
    if option in {'list', 'ls', 'dir', 'list_dir', 'inspect', 'browse'}:
        return 'inspect'
    if option in {'open'}:
        return 'open'
    if option in {'launch_app', 'focus_window', 'ui_interact'}:
        return option
    if option in {'save', 'export', 'write'}:
        return 'save'
    if option in {'screenshot', 'capture', 'observe'}:
        return 'screenshot'
    if option in {'copy'}:
        return 'copy'
    if option in {'move', 'rename'}:
        return 'move'
    if option in {'delete', 'remove'}:
        return 'delete'

    raw = str(text or '').strip()
    if has_url:
        return 'open'
    if any(w in raw for w in ('保存', '导出', '存到', '写到')):
        return 'save'
    if any(w in raw for w in ('截图', '截屏', '屏幕截图', '窗口截图', '屏幕状态', '当前屏幕', '观察屏幕', '截个图', '截个屏', '截一下', 'screenshot')):
        return 'screenshot'
    if any(w in raw for w in ('点击', '点一下', '点开按钮', '输入', '键入', '双击', '右击', '右键')):
        return 'ui_interact'
    if any(w in raw for w in ('快捷键', 'ctrl+', 'alt+', 'Ctrl+', 'Alt+')):
        return 'ui_interact'
    if any(w in raw for w in ('最小化', '最大化', '还原窗口', '恢复窗口')):
        return 'ui_interact'
    if any(w in raw for w in ('切到窗口', '聚焦窗口', '切换到窗口')):
        return 'focus_window'
    if any(w in raw for w in ('打开客户端', '打开应用', '启动应用', '启动客户端')):
        return 'launch_app'
    if any(w in raw for w in ('关闭应用', '关闭客户端', '退出应用', '结束应用', '杀掉应用')):
        return 'close_app'
    if any(w in raw for w in ('复制', '拷贝', '备份')):
        return 'copy'
    if any(w in raw for w in ('移动', '挪', '重命名', '改名')):
        return 'move'
    if any(w in raw for w in ('删除', '删掉', '清空')):
        return 'delete'
    if any(w in raw for w in ('打开', '打开下', 'open', 'Open', 'OPEN')):
        return 'open'
    return 'inspect'


def _detect_target_kind(path_value: str = '', url: str = '', action: str = 'inspect', text: str = '') -> str:
    raw = str(text or '').strip()
    if action in {'launch_app', 'focus_window', 'ui_interact', 'close_app'}:
        return 'app'
    if action == 'screenshot':
        return 'screen'
    if url:
        return 'url'
    if not path_value:
        return 'artifact' if action == 'save' else 'folder'
    p = Path(path_value)
    if p.exists():
        return 'folder' if p.is_dir() else 'file'
    if p.suffix:
        return 'file'
    return 'folder'


def _build_fs_action(text: str) -> dict:
    raw = str(text or '').strip()
    parsed = _extract_json_target(raw)
    all_paths = _extract_all_abs_paths(raw)
    url = str(parsed.get('url') or '').strip() or _extract_url(raw)
    explicit = str(parsed.get('option') or parsed.get('action') or '').strip()
    action = _detect_fs_action(raw, explicit, bool(url))

    # 只有当检测到真正的动作（非默认 inspect）或有路径/URL 时，才做目标解析
    resolved_ref = {}
    ref_type = ''
    if action != 'inspect' or all_paths or url or explicit:
        resolved_ref = resolve_target_reference(raw, {})
        ref_type = str(resolved_ref.get('target_type') or '').strip()

    if action == 'open' and ref_type == 'app':
        action = 'launch_app'
    elif action == 'open' and ref_type == 'window':
        action = 'focus_window'
    # ref_type == 'unknown' 时不覆盖 action，让 LLM tool_call 自己判断
    # 旧逻辑：unknown 默认当 app 处理 → 导致网站打不开
    elif ref_type == 'url' and not url:
        url = str(resolved_ref.get('value') or '').strip()
        if url and not action.startswith('launch'):
            action = 'open'
    elif ref_type in {'app', 'window'} and action not in {'launch_app', 'focus_window', 'ui_interact'}:
        action = 'launch_app' if ref_type == 'app' else 'focus_window'

    target_path = str(parsed.get('path') or '').strip()
    if not target_path and action in {'open', 'inspect', 'delete'}:
        target_path = all_paths[0] if all_paths else ''
    if not target_path and '桌面' in raw and action in {'open', 'inspect', 'save'}:
        target_path = str(Path.home() / 'Desktop')

    destination = {}
    if action in {'copy', 'move'}:
        if len(all_paths) >= 2:
            target_path = all_paths[0]
            destination = {'path': all_paths[1]}
        elif target_path and '桌面' in raw:
            destination = {'path': str(Path.home() / 'Desktop')}
    elif action == 'save':
        if parsed.get('destination'):
            destination = {'path': str(parsed.get('destination')).strip()}
        elif target_path:
            destination = {'path': target_path}
            target_path = ''
        elif '桌面' in raw:
            destination = {'path': str(Path.home() / 'Desktop')}

    target_kind = _detect_target_kind(target_path, url, action, raw)
    if action in {'launch_app', 'focus_window', 'ui_interact'} and resolved_ref and ref_type in {'app', 'window'}:
        if resolved_ref.get('target_type') == 'app':
            resolved_target = {'app': resolved_ref.get('label') or resolved_ref.get('value'), 'path': str(resolved_ref.get('value') or '')}
        elif resolved_ref.get('target_type') == 'window':
            resolved_target = {'window': resolved_ref.get('value')}
        elif resolved_ref.get('target_type') == 'path':
            resolved_target = {'path': resolved_ref.get('value')}
        else:
            resolved_target = {'value': resolved_ref.get('value')}
        resolution = str(resolved_ref.get('resolution') or 'missing')
    elif ref_type == 'url' and url:
        resolved_target = {'url': url}
        resolution = str(resolved_ref.get('resolution') or 'resolved')
    else:
        resolved_target = {'url': url} if url else ({'path': target_path} if target_path else {})
        resolution = 'resolved' if (resolved_target or destination) else 'missing'
    requires_confirmation = False
    blocked_reason = ''
    risk_level = 'low'
    target_suffix = Path(target_path).suffix.lower() if target_path else ''
    if action == 'delete':
        risk_level = 'high'
        requires_confirmation = True
    elif action in {'copy', 'move'}:
        risk_level = 'medium'
    elif action == 'open' and target_suffix in _DANGEROUS_SUFFIXES:
        risk_level = 'high'
        requires_confirmation = True
        blocked_reason = 'dangerous_open_target'

    payload = parsed.get('payload') if isinstance(parsed.get('payload'), dict) else {}
    return {
        'domain': 'filesystem',
        'action': action,
        'target_kind': target_kind,
        'target': resolved_target,
        'destination': destination,
        'payload': payload,
        'options': {
            'open_mode': str(parsed.get('open_mode') or 'default').strip() or 'default',
            'overwrite': bool(parsed.get('overwrite', False)),
            'create_parents': True,
        },
        'safety': {
            'risk_level': risk_level,
            'requires_confirmation': requires_confirmation,
            'blocked_reason': blocked_reason,
        },
        'source': 'context_pull',
        'resolution': resolution,
    }


def pull_context_data(user_input: str, manifest: dict) -> dict:
    manifest = manifest if isinstance(manifest, dict) else {}
    needs = manifest.get('context_need') or []
    out = {}
    raw = str(user_input or '').strip()

    fs_action = _build_fs_action(raw)
    if fs_action.get('target') or fs_action.get('destination') or fs_action.get('action') in {'launch_app', 'focus_window', 'ui_interact', 'screenshot', 'close_app'}:
        out['fs_action'] = fs_action

    if 'Desktop_Files' in needs:
        target = fs_action.get('target') if isinstance(fs_action.get('target'), dict) else {}
        target_path = str(target.get('path') or '').strip() or _extract_abs_path(raw)
        if not target_path and '桌面' in raw:
            target_path = str(Path.home() / 'Desktop')
        if target_path:
            p = Path(target_path)
            legacy_option = fs_action.get('action') or 'inspect'
            if p.exists() and p.is_dir():
                entries = sorted([x.name + ('/' if x.is_dir() else '') for x in p.iterdir()], key=lambda x: x.lower())
                out['Desktop_Files'] = {'path': str(p), 'entries': entries[:100]}
                out['fs_target'] = {'path': str(p), 'option': legacy_option, 'source': 'context_pull'}
                if out.get('fs_action') and not out['fs_action'].get('target'):
                    out['fs_action']['target'] = {'path': str(p)}
                    out['fs_action']['target_kind'] = 'folder'
                    out['fs_action']['resolution'] = 'resolved'
            else:
                out['Desktop_Files'] = {'path': target_path, 'entries': [], 'error': 'path_not_found_or_not_dir'}
                out['fs_target'] = {'path': target_path, 'option': legacy_option, 'source': 'context_pull', 'error': 'path_not_found_or_not_dir'}

    return out
