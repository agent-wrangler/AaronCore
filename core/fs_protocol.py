import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlparse

EXPORT_STATE_PATH = Path(__file__).resolve().parent.parent / 'memory_db' / 'file_export_state.json'
DANGEROUS_SUFFIXES = {'.exe', '.bat', '.cmd', '.ps1', '.lnk'}
INVALID_CHARS = r'[\\/:*?"<>|]'


def normalize_user_special_path(raw_path: str) -> str:
    text = str(raw_path or '').strip()
    if not text:
        return ''

    normalized = text.replace('\\', '/').strip()
    home = Path.home()
    special_dirs = {
        'desktop': home / 'Desktop',
        'documents': home / 'Documents',
        'downloads': home / 'Downloads',
        '桌面': home / 'Desktop',
        '文档': home / 'Documents',
        '下载': home / 'Downloads',
    }

    key = normalized.lower()
    if key in special_dirs:
        return str(special_dirs[key])

    for alias, base in special_dirs.items():
        prefix = f'{alias}/'
        if key.startswith(prefix):
            remain = normalized[len(prefix):].lstrip('/').strip()
            return str((base / remain).resolve()) if remain else str(base)

    m = re.match(r'^[A-Za-z]:/Users/[^/]+/(Desktop|Documents|Downloads)(/.*)?$', normalized, re.I)
    if m:
        folder = m.group(1)
        remain = str(m.group(2) or '').lstrip('/').strip()
        base = home / folder
        return str((base / remain).resolve()) if remain else str(base)

    m = re.match(r'^/Users/[^/]+/(Desktop|Documents|Downloads)(/.*)?$', normalized, re.I)
    if m:
        folder = m.group(1)
        remain = str(m.group(2) or '').lstrip('/').strip()
        base = home / folder
        return str((base / remain).resolve()) if remain else str(base)

    return text


def _normalize_search_text(value: str) -> str:
    cleaned = str(value or '').strip().lower()
    cleaned = re.sub(r'^(打开|进入|访问|搜索|搜一下|搜|查找|查一下|查|导航到|去)\s*', '', cleaned)
    cleaned = re.sub(r'(百度地图|高德地图|谷歌地图|google maps|baidu map|amap|地图)', '', cleaned)
    cleaned = re.sub(r'[\s\-_/,:：。、“”"\'`]+', '', cleaned)
    return cleaned


def _extract_search_term(raw_input: str) -> str:
    text = str(raw_input or '').strip()
    if not text:
        return ''
    patterns = [
        r'(?:搜索|搜一下|搜|查找|查一下|查|定位到|导航到|去)\s*[：:\s]*([^\n]+)$',
        r'地图\s*(?:里|中)?\s*(?:搜索|搜一下|搜|查找|查)\s*[：:\s]*([^\n]+)$',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            candidate = str(match.group(1) or '').strip()
            candidate = re.sub(r'^(一下|一下子)\s*', '', candidate)
            candidate = candidate.strip(' ，,。！？!?.')
            return candidate
    return ''


def _normalize_search_text_v2(value: str) -> str:
    cleaned = str(value or '').strip().lower()
    for prefix in ('打开', '进入', '访问', '搜索', '搜一下', '搜', '查找', '查', '定位到', '导航到', '去'):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    for token in ('百度地图', '高德地图', '谷歌地图', 'google maps', 'baidu map', 'amap', '地图'):
        cleaned = cleaned.replace(token, '')
    cleaned = re.sub(r'[\s\\-_/,:：，。、“”"\'`]+', '', cleaned)
    return cleaned


def _extract_search_term_v2(raw_input: str) -> str:
    text = str(raw_input or '').strip()
    if not text:
        return ''
    markers = ('搜索', '搜一下', '搜', '查找', '查', '定位到', '导航到', '去')
    for marker in markers:
        idx = text.rfind(marker)
        if idx != -1:
            candidate = text[idx + len(marker):].strip(' ：:，,。.!！？?')
            if candidate:
                return candidate
    if '地图' in text:
        candidate = text.split('地图', 1)[-1].strip()
        candidate = candidate.lstrip(' ：:，,。.!！？?')
        for marker in markers:
            if candidate.startswith(marker):
                candidate = candidate[len(marker):].strip(' ：:，,。.!！？?')
        if candidate:
            return candidate
    return ''


def compose_remote_target_url(target_url: str, raw_input: str) -> dict:
    url = str(target_url or '').strip()
    search_term = _extract_search_term_v2(raw_input)
    if not url:
        return {'url': '', 'search_term': '', 'composed': False, 'strategy': ''}
    if not search_term:
        return {'url': url, 'search_term': '', 'composed': False, 'strategy': ''}

    parsed = urlparse(url)
    domain = str(parsed.netloc or '').lower()
    path = str(parsed.path or '').lower()
    encoded = quote(search_term)

    if 'map.baidu.com' in domain or 'ditu.baidu.com' in domain:
        return {
            'url': f'https://map.baidu.com/search/{encoded}',
            'search_term': search_term,
            'composed': True,
            'strategy': 'baidu_map_query_url',
        }

    if ('google.' in domain and '/maps' in path) or domain == 'maps.google.com':
        return {
            'url': f'https://www.google.com/maps/search/?api=1&query={encoded}',
            'search_term': search_term,
            'composed': True,
            'strategy': 'google_maps_query_url',
        }

    return {'url': url, 'search_term': search_term, 'composed': False, 'strategy': ''}


def build_action_meta(*, action_kind: str = '', target_kind: str = '', target: str = '', outcome: str = '', display_hint: str = '', verification_mode: str = '', verification_detail: str = '') -> dict:
    return {
        'action_kind': str(action_kind or '').strip(),
        'target_kind': str(target_kind or '').strip(),
        'target': str(target or '').strip(),
        'outcome': str(outcome or '').strip(),
        'display_hint': str(display_hint or '').strip(),
        'verification_mode': str(verification_mode or '').strip(),
        'verification_detail': str(verification_detail or '').strip(),
    }


def summarize_action_meta(action: dict | None) -> str:
    action = action if isinstance(action, dict) else {}
    if not action:
        return ''
    display_hint = str(action.get('display_hint') or '').strip()
    if display_hint:
        return display_hint
    action_kind = str(action.get('action_kind') or '').strip()
    target_kind = str(action.get('target_kind') or '').strip()
    target = str(action.get('target') or '').strip()
    outcome = str(action.get('outcome') or '').strip()
    parts = [part for part in [action_kind, target_kind, outcome] if part]
    if target:
        parts.append(target)
    return ' / '.join(parts[:4]).strip()


def build_operation_result(reply: str, *, expected_state: str = '', observed_state: str = '', drift_reason: str = '', repair_hint: str = '', repair_attempted: bool = False, repair_succeeded: bool = False, image_url: str = '', action_kind: str = '', target_kind: str = '', target: str = '', outcome: str = '', display_hint: str = '', verification_mode: str = '', verification_detail: str = '') -> dict:
    result = {
        'reply': str(reply or '').strip(),
        'state': {
            'expected_state': str(expected_state or '').strip(),
            'observed_state': str(observed_state or '').strip(),
        },
        'drift': {
            'reason': str(drift_reason or '').strip(),
            'repair_hint': str(repair_hint or '').strip(),
        },
        'repair_attempted': bool(repair_attempted),
        'repair_succeeded': bool(repair_succeeded),
        'action': build_action_meta(
            action_kind=action_kind,
            target_kind=target_kind,
            target=target,
            outcome=outcome,
            display_hint=display_hint,
            verification_mode=verification_mode,
            verification_detail=verification_detail,
        ),
    }
    if image_url:
        result['image_url'] = str(image_url).strip()
    return result


def verify_post_condition(action: str, target_value: str = '', **kwargs) -> dict:
    try:
        import pygetwindow as _gw
        _has_gw = True
    except ImportError:
        _has_gw = False

    if action in {'open', 'inspect'}:
        p = Path(str(target_value or '').strip())
        if p.exists():
            return {'ok': True, 'expected': f'{action}_succeeded', 'observed': 'target_exists', 'drift': '', 'hint': ''}
        return {'ok': False, 'expected': f'{action}_succeeded', 'observed': 'target_missing_after_action', 'drift': 'post_action_target_missing', 'hint': 'check_or_correct_path'}

    if action == 'open_url':
        # 验证：窗口标题是否包含目标关键词
        url_hint = str(target_value or '').strip().lower()
        # 从 URL 提取域名/关键词作为匹配依据
        import re
        _domain_match = re.search(r'(?:https?://)?(?:www\.)?([^/]+)', url_hint)
        _domain = _domain_match.group(1).split('.')[0] if _domain_match else ''
        _search_term = _extract_search_term_v2(kwargs.get('search_term') or '')
        _search_term_norm = _normalize_search_text_v2(_search_term)
        if _has_gw and (_domain or _search_term):
            try:
                import time
                time.sleep(1)  # 等页面加载
                all_titles = [w.title.lower() for w in _gw.getAllWindows() if w.title.strip()]
                check_words = [w for w in [_domain, _search_term_norm] if w]
                if any(any(w in t for w in check_words) for t in all_titles):
                    return {'ok': True, 'expected': 'url_opened', 'observed': 'page_title_matched', 'drift': '', 'hint': ''}
                if _search_term_norm:
                    return {
                        'ok': False,
                        'expected': 'url_search_visible',
                        'observed': 'search_term_not_visible',
                        'drift': 'search_term_not_visible',
                        'hint': 'search_with_query_url_or_ui_interaction',
                    }
            except Exception:
                pass
        return {'ok': True, 'expected': 'url_opened', 'observed': 'url_opened_unverified', 'drift': '', 'hint': ''}

    if action == 'save':
        p = Path(str(target_value or '').strip())
        exists = p.exists()
        return {'ok': exists, 'expected': 'artifact_saved', 'observed': 'artifact_present' if exists else 'artifact_missing', 'drift': '' if exists else 'artifact_not_persisted', 'hint': '' if exists else 'fallback_to_desktop'}

    if action in {'launch_app', 'focus_window'}:
        if not _has_gw:
            return {'ok': False, 'expected': 'window_visible', 'observed': 'ui_runtime_missing', 'drift': 'no_pygetwindow', 'hint': 'install_pygetwindow'}
        hint_value = str(kwargs.get('window_title') or kwargs.get('app_label') or target_value or '').strip().lower()
        if hint_value.endswith('.exe'):
            hint_value = Path(hint_value).stem.lower()
        hint_variants = [hint_value] if hint_value else []
        try:
            from core.target_protocol import _PINYIN_MAP
            reverse_map = {str(py).lower(): str(cn) for cn, py in _PINYIN_MAP.items()}
            if hint_value in reverse_map:
                hint_variants.append(reverse_map[hint_value].lower())
            for cn, py in _PINYIN_MAP.items():
                cn_lower = str(cn).lower()
                py_lower = str(py).lower()
                if cn_lower == hint_value and py_lower not in hint_variants:
                    hint_variants.append(py_lower)
                if py_lower == hint_value and cn_lower not in hint_variants:
                    hint_variants.append(cn_lower)
        except Exception:
            pass
        try:
            active = _gw.getActiveWindow()
            active_title = str(active.title).strip().lower() if active and getattr(active, 'title', None) else ''
        except Exception:
            active_title = ''
        if hint_variants and active_title and any(v and v in active_title for v in hint_variants):
            return {'ok': True, 'expected': 'window_focused', 'observed': 'window_focused', 'drift': '', 'hint': ''}
        try:
            all_titles = [w.title for w in _gw.getAllWindows() if w.title.strip()]
        except Exception:
            all_titles = []
        if any(any(v and v in t.lower() for v in hint_variants) for t in all_titles):
            return {'ok': True, 'expected': 'window_visible', 'observed': 'window_visible', 'drift': '', 'hint': ''}
        return {'ok': False, 'expected': 'window_visible', 'observed': 'window_not_detected', 'drift': 'window_not_detected', 'hint': 'retry_or_check_startup_delay'}

    if action == 'ui_interact':
        # 轻量验证：检查活跃窗口是否仍在前台
        if _has_gw:
            expected_window = str(kwargs.get('window_title') or '').strip().lower()
            if expected_window:
                try:
                    active = _gw.getActiveWindow()
                    active_title = str(active.title).strip().lower() if active and getattr(active, 'title', None) else ''
                except Exception:
                    active_title = ''
                if expected_window in active_title:
                    return {'ok': True, 'expected': 'ui_interacted', 'observed': 'window_still_focused', 'drift': '', 'hint': ''}
                return {'ok': False, 'expected': 'ui_interacted', 'observed': 'window_lost_focus', 'drift': 'focus_lost_after_interact', 'hint': 'refocus_window'}
        return {'ok': True, 'expected': 'ui_interacted', 'observed': 'ui_interacted', 'drift': '', 'hint': ''}

    if action in {'copy', 'move'}:
        dst = str(kwargs.get('destination') or '').strip()
        if dst:
            exists = Path(dst).exists()
            return {'ok': exists, 'expected': 'destination_exists', 'observed': 'present' if exists else 'missing', 'drift': '' if exists else 'destination_missing', 'hint': '' if exists else 'check_destination'}
        return {'ok': True, 'expected': 'op_completed', 'observed': 'op_completed', 'drift': '', 'hint': ''}

    if action == 'delete':
        gone = not Path(str(target_value or '').strip()).exists()
        return {'ok': gone, 'expected': 'target_deleted', 'observed': 'target_gone' if gone else 'target_still_exists', 'drift': '' if gone else 'delete_incomplete', 'hint': '' if gone else 'retry_delete_or_check_permissions'}

    return {'ok': True, 'expected': 'unknown_action', 'observed': 'assumed_ok', 'drift': '', 'hint': ''}


def load_export_state() -> dict:
    try:
        if EXPORT_STATE_PATH.exists():
            data = json.loads(EXPORT_STATE_PATH.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                if data.get('last_export_path'):
                    data['last_export_path'] = normalize_user_special_path(data.get('last_export_path'))
                if data.get('last_export_dir'):
                    data['last_export_dir'] = normalize_user_special_path(data.get('last_export_dir'))
                return data
    except Exception:
        pass
    return {}


def save_export_state(state: dict):
    EXPORT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXPORT_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


def safe_name(name: str, fallback: str = '导出结果') -> str:
    cleaned = re.sub(INVALID_CHARS, '', str(name or '').strip())[:60].strip()
    return cleaned or fallback


def classify_open_target(target_value: str) -> dict:
    raw = str(target_value or '').strip()
    if not raw:
        return {
            'ok': False,
            'reason': 'missing_target',
            'expected_state': 'target_resolved',
            'observed_state': 'target_missing',
            'drift_reason': 'missing_target',
            'repair_hint': 'provide_explicit_target',
            'repairable': False,
        }
    if raw.startswith('http://') or raw.startswith('https://'):
        parsed = urlparse(raw)
        if parsed.scheme not in {'http', 'https'}:
            return {
                'ok': False,
                'reason': 'unsupported_url_scheme',
                'target': raw,
                'expected_state': 'url_openable',
                'observed_state': 'unsupported_scheme',
                'drift_reason': 'unsupported_url_scheme',
                'repair_hint': 'use_http_or_https',
                'repairable': True,
                'repair_target': 'https://' + raw.split('://', 1)[-1],
            }
        return {
            'ok': True,
            'target_type': 'url',
            'target': raw,
            'risk_level': 'low',
            'requires_confirmation': False,
            'expected_state': 'url_opened',
            'observed_state': 'url_resolved',
            'drift_reason': '',
            'repair_hint': '',
            'repairable': False,
        }
    if re.match(r'^[\w.-]+\.[A-Za-z]{2,}(/.*)?$', raw):
        repaired = 'https://' + raw
        return {
            'ok': False,
            'reason': 'missing_url_scheme',
            'target': raw,
            'expected_state': 'url_openable',
            'observed_state': 'scheme_missing',
            'drift_reason': 'missing_url_scheme',
            'repair_hint': 'auto_prefix_https',
            'repairable': True,
            'repair_target': repaired,
        }
    target = Path(raw)
    if not target.exists():
        return {
            'ok': False,
            'reason': 'target_not_found',
            'target': str(target),
            'expected_state': 'path_exists',
            'observed_state': 'path_missing',
            'drift_reason': 'target_not_found',
            'repair_hint': 'check_or_correct_path',
        }
    if target.is_file() and target.suffix.lower() in DANGEROUS_SUFFIXES:
        return {
            'ok': False,
            'reason': 'dangerous_open_target',
            'target': str(target),
            'risk_level': 'high',
            'requires_confirmation': True,
            'expected_state': 'safe_target_ready',
            'observed_state': 'dangerous_target_blocked',
            'drift_reason': 'dangerous_open_target',
            'repair_hint': 'confirm_or_use_safe_target',
        }
    return {
        'ok': True,
        'target_type': 'folder' if target.is_dir() else 'file',
        'target': str(target),
        'risk_level': 'low',
        'requires_confirmation': False,
        'expected_state': 'target_opened',
        'observed_state': 'target_ready',
        'drift_reason': '',
        'repair_hint': '',
    }


def check_saved_state(path: str) -> dict:
    p = Path(str(path or '').strip())
    exists = p.exists()
    return {
        'ok': bool(path) and exists,
        'path': str(p),
        'exists': exists,
        'is_file': p.is_file(),
        'is_dir': p.is_dir(),
        'expected_state': 'artifact_saved',
        'observed_state': 'artifact_present' if exists else 'artifact_missing',
        'drift_reason': '' if exists else 'artifact_not_persisted',
        'repair_hint': '' if exists else 'fallback_to_desktop',
        'repairable': not exists,
        'repair_target': str(Path.home() / 'Desktop') if not exists else '',
    }


def build_save_path(folder: str, filename: str, fmt: str) -> Path:
    target_dir = Path(normalize_user_special_path(folder) or folder)
    target_dir.mkdir(parents=True, exist_ok=True)
    ext = 'md' if fmt not in {'txt', 'json'} else fmt
    ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    return target_dir / f'{ts}_{safe_name(filename)}.{ext}'


def record_saved_artifact(path: str, fmt: str):
    target = Path(str(path))
    save_export_state({
        'last_export_path': str(target),
        'last_export_dir': str(target.parent),
        'last_export_format': str(fmt or '').strip(),
        'updated_at': datetime.now().isoformat(),
    })


def attempt_fs_repair(skill_name: str, context: dict | None = None, meta: dict | None = None) -> dict:
    context = context if isinstance(context, dict) else {}
    meta = meta if isinstance(meta, dict) else {}
    drift = meta.get('drift') if isinstance(meta.get('drift'), dict) else {}
    state = meta.get('state') if isinstance(meta.get('state'), dict) else {}
    fs_action = context.get('fs_action') if isinstance(context.get('fs_action'), dict) else {}
    target = fs_action.get('target') if isinstance(fs_action.get('target'), dict) else {}
    destination = fs_action.get('destination') if isinstance(fs_action.get('destination'), dict) else {}

    if skill_name == 'open_target':
        current_target = str(target.get('url') or target.get('path') or '').strip()
        if drift.get('reason') == 'missing_url_scheme' and current_target:
            repaired = 'https://' + current_target.split('://', 1)[-1]
            return {'repairable': True, 'updated_context': {'fs_action': {**fs_action, 'target': {'url': repaired}, 'target_kind': 'url'}, 'fs_target': context.get('fs_target') or {}}, 'rewritten_input': repaired}
        export_state = load_export_state()
        if drift.get('reason') == 'target_not_found' and export_state.get('last_export_dir'):
            repaired = str(export_state.get('last_export_dir'))
            return {'repairable': True, 'updated_context': {'fs_action': {**fs_action, 'target': {'path': repaired}, 'target_kind': 'folder'}, 'fs_target': {'path': repaired, 'option': 'open', 'source': 'fs_protocol_repair'}}, 'rewritten_input': repaired}

    if skill_name == 'folder_explore':
        export_state = load_export_state()
        current_path = str((context.get('fs_target') or {}).get('path') or '').strip() if isinstance(context.get('fs_target'), dict) else ''
        if drift.get('reason') == 'target_not_found' and export_state.get('last_export_dir'):
            repaired = str(export_state.get('last_export_dir'))
            return {'repairable': True, 'updated_context': {'fs_target': {'path': repaired, 'option': 'inspect', 'source': 'fs_protocol_repair'}}, 'rewritten_input': repaired}
        if drift.get('reason') == 'target_not_found' and '桌面' in current_path:
            repaired = str(Path.home() / 'Desktop')
            return {'repairable': True, 'updated_context': {'fs_target': {'path': repaired, 'option': 'inspect', 'source': 'fs_protocol_repair'}}, 'rewritten_input': repaired}
        if drift.get('reason') == 'not_a_directory' and current_path:
            repaired = str(Path(current_path).parent)
            if repaired and repaired != current_path:
                return {'repairable': True, 'updated_context': {'fs_target': {'path': repaired, 'option': 'inspect', 'source': 'fs_protocol_repair'}}, 'rewritten_input': repaired}

    if skill_name == 'app_target':
        if drift.get('reason') in {'window_not_detected', 'focus_failed'}:
            return {'repairable': True, 'updated_context': context, 'rewritten_input': context.get('last_user_input') or '', 'sleep_before': 2}

    if skill_name == 'ui_interaction':
        if drift.get('reason') in {'window_not_found', 'focus_failed'}:
            return {'repairable': True, 'updated_context': context, 'rewritten_input': context.get('last_user_input') or '', 'sleep_before': 1}

    if skill_name == 'save_export':
        if drift.get('reason') == 'artifact_not_persisted':
            repaired_dir = str(Path.home() / 'Desktop')
            new_destination = {'path': repaired_dir}
            return {'repairable': True, 'updated_context': {**context, 'save_destination': repaired_dir, 'fs_action': {**fs_action, 'destination': new_destination}}, 'rewritten_input': context.get('save_content') or ''}

    return {'repairable': False}
