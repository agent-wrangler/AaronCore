import json
import re
import shutil
import subprocess
import tomllib
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urlparse

EXPORT_STATE_PATH = Path(__file__).resolve().parent.parent / 'memory_db' / 'file_export_state.json'
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DANGEROUS_SUFFIXES = {'.exe', '.bat', '.cmd', '.ps1', '.lnk'}
INVALID_CHARS = r'[\\/:*?"<>|]'
PROTOCOL_REQUIRED_FIELDS = {
    'write_file': ('file_path', 'content'),
    'edit_file': ('file_path', 'change_request'),
    'search_replace': ('file_path', 'old_text', 'new_text'),
    'apply_unified_diff': ('file_path', 'patch'),
}


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


def build_protocol_exec_result(
    success: bool,
    reply: str,
    *,
    error: str = '',
    expected_state: str = '',
    observed_state: str = '',
    drift_reason: str = '',
    repair_hint: str = '',
    repair_attempted: bool = False,
    repair_succeeded: bool = False,
    image_url: str = '',
    action_kind: str = '',
    target_kind: str = '',
    target: str = '',
    outcome: str = '',
    display_hint: str = '',
    verification_mode: str = '',
    verification_detail: str = '',
    post_condition: dict | None = None,
    verified: bool | None = None,
    verification_explicit: bool = False,
) -> dict:
    operation = build_operation_result(
        reply,
        expected_state=expected_state,
        observed_state=observed_state,
        drift_reason=drift_reason,
        repair_hint=repair_hint,
        repair_attempted=repair_attempted,
        repair_succeeded=repair_succeeded,
        image_url=image_url,
        action_kind=action_kind,
        target_kind=target_kind,
        target=target,
        outcome=outcome,
        display_hint=display_hint,
        verification_mode=verification_mode,
        verification_detail=verification_detail,
    )
    meta = {
        'state': operation.get('state') if isinstance(operation.get('state'), dict) else {},
        'drift': operation.get('drift') if isinstance(operation.get('drift'), dict) else {},
        'action': operation.get('action') if isinstance(operation.get('action'), dict) else {},
        'repair_attempted': bool(operation.get('repair_attempted', False)),
        'repair_succeeded': bool(operation.get('repair_succeeded', False)),
    }
    if image_url:
        meta['image_url'] = str(image_url).strip()
    if isinstance(post_condition, dict) and post_condition:
        meta['post_condition'] = dict(post_condition)
    verification = {}
    if verified is not None or verification_explicit:
        verification['verified'] = verified if verified is None else bool(verified)
    verification_observed = str(
        observed_state
        or ((post_condition or {}).get('observed') if isinstance(post_condition, dict) else '')
        or ''
    ).strip()
    if verification_observed:
        verification['observed_state'] = verification_observed
    if verification_mode:
        verification['verification_mode'] = str(verification_mode).strip()
    if verification_detail:
        verification['verification_detail'] = str(verification_detail).strip()
    if verification:
        meta['verification'] = verification
    return {
        'success': bool(success),
        'response': str(reply or '').strip(),
        'error': None if success else str(error or reply or '').strip(),
        'meta': meta,
    }


def resolve_user_file_target(file_path: str, *, workspace_root: Path | None = None) -> Path | None:
    raw = normalize_user_special_path(str(file_path or '').replace('\\', '/').strip())
    if not raw:
        return None
    root = (workspace_root or WORKSPACE_ROOT).resolve()
    target = Path(raw)
    if not target.is_absolute():
        target = (root / raw.lstrip('./')).resolve()

        if '/' not in raw and '\\' not in raw:
            state = load_export_state()
            last_dir = normalize_user_special_path(str(state.get('last_export_dir') or '').strip())
            last_path = normalize_user_special_path(str(state.get('last_export_path') or '').strip())
            if last_dir:
                last_dir_path = Path(last_dir)
                candidate = (last_dir_path / raw).resolve()

                def _norm_stem(p: str) -> str:
                    stem = Path(str(p or '')).stem
                    stem = re.sub(r'^\d{4}-\d{2}-\d{2}_\d{6}_', '', stem)
                    return stem.strip().lower()

                raw_stem = _norm_stem(raw)
                last_stem = _norm_stem(last_path)
                same_topic = bool(raw_stem and last_stem and (raw_stem == last_stem or raw_stem in last_stem or last_stem in raw_stem))
                if candidate.exists() or same_topic:
                    return candidate
        return target
    return target.resolve()


def is_system_protected_target(target: str | Path | None) -> bool:
    if not target:
        return True
    target_str = str(target).replace('\\', '/')
    protected_prefixes = (
        'C:/Windows',
        'C:/Program Files',
        'C:/Program Files (x86)',
        'C:/ProgramData',
    )
    return any(target_str.startswith(prefix) for prefix in protected_prefixes)


def is_novacore_protected_write_target(target: str | Path | None) -> bool:
    if not target:
        return True
    try:
        root = WORKSPACE_ROOT.resolve()
        target_path = Path(target).resolve()
    except Exception:
        return True

    try:
        rel = target_path.relative_to(root)
    except Exception:
        return False

    protected_roots = {
        Path('brain'),
        Path('core'),
        Path('routes'),
        Path('shell'),
        Path('static/js'),
        Path('static/css'),
        Path('configs'),
    }
    protected_files = {
        Path('agent_final.py'),
        Path('output.html'),
        Path('start_nova.bat'),
        Path('AGENTS.md'),
        Path('CLAUDE.md'),
    }
    if rel in protected_files:
        return True
    return any(rel == p or p in rel.parents for p in protected_roots)


def is_allowed_write_target(target: str | Path | None) -> bool:
    if not target:
        return False
    return not is_system_protected_target(target) and not is_novacore_protected_write_target(target)


def missing_required_protocol_fields(tool_name: str, tool_args: dict | None) -> list[str]:
    args = dict(tool_args or {})
    normalized_tool = str(tool_name or '').strip()
    missing = []
    for field in PROTOCOL_REQUIRED_FIELDS.get(normalized_tool, ()):
        if normalized_tool == 'search_replace' and field == 'new_text':
            aliases = ('new_text', 'replacement', 'replace_text', 'after')
            if not any(alias in args for alias in aliases):
                missing.append(field)
            continue
        if normalized_tool == 'apply_unified_diff' and field == 'patch':
            aliases = ('patch', 'diff', 'unified_diff')
            if not any(alias in args for alias in aliases):
                missing.append(field)
            continue
        value = args.get(field)
        if isinstance(value, str):
            if not value.strip():
                missing.append(field)
        elif value in (None, [], {}):
            missing.append(field)
    return missing


def protocol_arg_failure_signature(tool_name: str, tool_args: dict | None, missing_fields: list[str]) -> dict:
    args = dict(tool_args or {})
    target = str(
        args.get('file_path')
        or args.get('path')
        or args.get('target')
        or args.get('filename')
        or ''
    ).strip().lower()
    return {
        'tool': str(tool_name or '').strip(),
        'target': target,
        'missing_fields': tuple(sorted(str(field).strip() for field in missing_fields if str(field).strip())),
    }


def has_same_protocol_arg_failure_recently(recent_attempts: list[dict], signature: dict) -> bool:
    for item in reversed(recent_attempts[-4:]):
        if not isinstance(item, dict):
            continue
        if item.get('success') is not False:
            continue
        previous = item.get('arg_failure')
        if isinstance(previous, dict) and previous == signature:
            return True
    return False


def build_protocol_arg_failure_feedback(tool_name: str, tool_args: dict | None, missing_fields: list[str]) -> str:
    signature = protocol_arg_failure_signature(tool_name, tool_args, missing_fields)
    target = signature.get('target') or '未提供目标'
    if tool_name == 'write_file' and 'content' in missing_fields:
        return (
            '执行失败: 缺少 content。\n'
            f'write_file 必须同时提供 file_path 和完整文件内容；当前目标是 {target}。\n'
            '不要重复只带 file_path 的调用。\n'
            '如果你已经知道这个文件要写什么，就直接重新调用 write_file，并把该文件的完整 content 一次性传入。\n'
            '如果还缺项目结构或相邻文件信息，先调用 list_files / read_file 再决定写入。\n'
            '只有在文件内容真的依赖用户选择，或你确实缺少必要上下文时，才停止工具调用并向用户解释阻塞。'
        )
    return f"执行失败: 缺少必要参数 {', '.join(missing_fields)}。请补全参数后再继续。"


def build_protocol_arg_failure_system_note(tool_name: str, tool_args: dict | None, missing_fields: list[str]) -> str:
    signature = protocol_arg_failure_signature(tool_name, tool_args, missing_fields)
    target = signature.get('target') or 'unknown target'
    missing = ', '.join(signature.get('missing_fields') or ())
    if tool_name == 'write_file':
        return (
            f'The previous write_file call for {target} failed because required arguments were missing: {missing}. '
            'Do not repeat the same incomplete write_file call. '
            'If you already know what the file should contain, immediately call write_file again with the same file_path and the COMPLETE file content string. '
            'If you still need project structure or neighboring file context, inspect with list_files or read_file first, then rebuild the full content. '
            'Only stop calling tools and explain the blocker if the file content genuinely depends on a missing user choice or missing context you cannot infer.'
        )
    return (
        f'The previous tool call failed because required arguments were missing: {missing}. '
        'Do not repeat the same incomplete call. Either provide the missing arguments or stop and explain the blocker.'
    )


def build_protocol_retry_note(tool_name: str, tool_args: dict | None, exec_result: dict | None) -> str:
    if not isinstance(exec_result, dict) or exec_result.get('success', False):
        return ''

    missing_fields = missing_required_protocol_fields(tool_name, tool_args)
    if missing_fields:
        return build_protocol_arg_failure_system_note(tool_name, tool_args, missing_fields)

    file_tools = {'write_file', 'read_file', 'list_files'}
    environment_tools = {'open_target', 'app_target', 'ui_interaction', 'folder_explore', 'sense_environment', 'screen_capture'}
    command_tools = {'run_command'}

    if tool_name in file_tools:
        return (
            'The previous file/code action failed. Do not repeat the exact same call blindly. '
            'If the current project structure or nearby files may matter, inspect with list_files or read_file first, then choose the next action.'
        )

    if tool_name in environment_tools:
        return (
            'The previous environment action failed. Do not repeat the exact same desktop action blindly. '
            'Inspect the current state with sense_environment or screen_capture first, then choose the next step.'
        )

    if tool_name in command_tools:
        return (
            'The previous local build, package, install, or test command failed. '
            'Do not blindly repeat the same command. Inspect the output, workdir, and expected_artifacts first, '
            'then adjust the command or fix the relevant files.'
        )

    return (
        'The previous tool call failed. Do not repeat the same failing call without changing arguments, checking state, or choosing a more informative tool first.'
    )


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

    if action in {'write', 'write_file', 'edit_file', 'search_replace', 'apply_unified_diff'}:
        p = Path(str(target_value or '').strip())
        exists = p.exists()
        return {
            'ok': exists,
            'expected': 'file_written',
            'observed': 'file_written' if exists else 'file_missing_after_write',
            'drift': '' if exists else 'write_not_persisted',
            'hint': '' if exists else 'retry_or_check_write_target',
        }

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


class _BestEffortHTMLVerifier(HTMLParser):
    pass


def _verification_success(mode: str, detail: str, *, observed_state: str = 'file_verified') -> dict:
    return {
        'verified': True,
        'verification_mode': str(mode or '').strip(),
        'verification_detail': str(detail or '').strip(),
        'observed_state': str(observed_state or 'file_verified').strip(),
        'drift_reason': '',
        'repair_hint': '',
    }


def _verification_failure(
    mode: str,
    detail: str,
    *,
    observed_state: str = 'file_invalid_syntax',
    drift_reason: str = 'file_verification_failed',
    repair_hint: str = 'fix_file_syntax',
) -> dict:
    return {
        'verified': False,
        'verification_mode': str(mode or '').strip(),
        'verification_detail': str(detail or '').strip(),
        'observed_state': str(observed_state or 'file_invalid_syntax').strip(),
        'drift_reason': str(drift_reason or 'file_verification_failed').strip(),
        'repair_hint': str(repair_hint or 'fix_file_syntax').strip(),
    }


def _verification_unverified(mode: str, detail: str, *, observed_state: str = 'file_unverified') -> dict:
    return {
        'verified': None,
        'verification_mode': str(mode or '').strip(),
        'verification_detail': str(detail or '').strip(),
        'observed_state': str(observed_state or 'file_unverified').strip(),
        'drift_reason': '',
        'repair_hint': '',
    }


def _format_verification_exception(exc: Exception) -> str:
    exc_type = type(exc).__name__.strip()
    message = str(exc or '').strip()
    return f'{exc_type}: {message}'.strip(': ')


def _looks_like_jinja_template(target: Path, content: str = '', verifier_hint: str = '') -> bool:
    suffix = str(target.suffix or '').lower()
    if suffix in {'.j2', '.jinja', '.jinja2'}:
        return True

    hint = str(verifier_hint or '').strip().lower()
    if hint in {'jinja', 'jinja2', 'template', 'jinja_template'}:
        return True

    text = str(content or '')
    if any(marker in text for marker in ('{{', '{%', '{#')):
        if 'templates' in {str(part).lower() for part in target.parts}:
            return True
        if suffix in {'.html', '.htm', '.txt', '.xml', '.svg'}:
            return True
    return False


def _extract_markdown_front_matter(content: str) -> dict:
    text = str(content or '')
    if not text.startswith('---'):
        return {'present': False, 'content': '', 'error': ''}

    match = re.match(r'\A---[ \t]*\r?\n(.*?)(?:\r?\n)(---|\.\.\.)[ \t]*(?:\r?\n|$)', text, flags=re.S)
    if not match:
        return {
            'present': True,
            'content': '',
            'error': 'unterminated_front_matter',
        }
    return {
        'present': True,
        'content': str(match.group(1) or ''),
        'error': '',
    }


def verify_file_change(target, *, content: str | None = None, verifier_hint: str | None = None, context: dict | None = None) -> dict:
    _ = context if isinstance(context, dict) else {}
    path = Path(target)
    text = content
    if text is None:
        try:
            text = path.read_text(encoding='utf-8')
        except Exception as exc:
            return _verification_failure(
                'file_read',
                _format_verification_exception(exc),
                observed_state='file_read_failed',
                drift_reason='file_read_failed',
                repair_hint='check_file_encoding_or_permissions',
            )

    text = str(text)
    suffix = str(path.suffix or '').lower()

    if _looks_like_jinja_template(path, text, str(verifier_hint or '')):
        try:
            from jinja2 import Environment

            Environment().parse(text)
            return _verification_success('jinja_parse', 'Jinja template parsed successfully.')
        except Exception as exc:
            return _verification_failure(
                'jinja_parse',
                _format_verification_exception(exc),
                drift_reason='jinja_parse_failed',
                repair_hint='fix_jinja_syntax',
            )

    if suffix == '.py':
        try:
            compile(text, str(path), 'exec')
            return _verification_success('python_compile', 'Python source compiled successfully.')
        except Exception as exc:
            return _verification_failure(
                'python_compile',
                _format_verification_exception(exc),
                drift_reason='python_compile_failed',
                repair_hint='fix_python_syntax',
            )

    if suffix == '.json':
        try:
            json.loads(text)
            return _verification_success('json_parse', 'JSON parsed successfully.')
        except Exception as exc:
            return _verification_failure(
                'json_parse',
                _format_verification_exception(exc),
                drift_reason='json_parse_failed',
                repair_hint='fix_json_syntax',
            )

    if suffix == '.toml':
        try:
            tomllib.loads(text)
            return _verification_success('toml_parse', 'TOML parsed successfully.')
        except Exception as exc:
            return _verification_failure(
                'toml_parse',
                _format_verification_exception(exc),
                drift_reason='toml_parse_failed',
                repair_hint='fix_toml_syntax',
            )

    if suffix in {'.yaml', '.yml'}:
        try:
            import yaml

            yaml.safe_load(text)
            return _verification_success('yaml_parse', 'YAML parsed successfully.')
        except ImportError:
            return _verification_unverified('unverified_no_parser', 'YAML parser is not available in the local runtime.')
        except Exception as exc:
            return _verification_failure(
                'yaml_parse',
                _format_verification_exception(exc),
                drift_reason='yaml_parse_failed',
                repair_hint='fix_yaml_syntax',
            )

    if suffix in {'.js', '.mjs', '.cjs'}:
        node_bin = shutil.which('node')
        if not node_bin:
            return _verification_unverified('unverified_no_parser', 'Node.js is not available, so JavaScript syntax was not verified.')
        try:
            completed = subprocess.run(
                [node_bin, '--check', str(path)],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            return _verification_unverified('node_check_unverified', 'Node.js syntax check timed out before returning a result.')
        except Exception as exc:
            return _verification_unverified('node_check_unverified', _format_verification_exception(exc))
        if completed.returncode == 0:
            return _verification_success('node_check', 'JavaScript syntax check passed.')
        detail = '\n'.join(part for part in [completed.stdout, completed.stderr] if str(part or '').strip()).strip()
        return _verification_failure(
            'node_check',
            detail or 'node --check returned a non-zero exit code.',
            drift_reason='javascript_check_failed',
            repair_hint='fix_javascript_syntax',
        )

    if suffix in {'.html', '.htm'}:
        try:
            parser = _BestEffortHTMLVerifier()
            parser.feed(text)
            parser.close()
            return _verification_unverified(
                'html_best_effort',
                'HTML received a best-effort structure check only; no strict verifier is configured.',
            )
        except Exception as exc:
            return _verification_unverified(
                'html_best_effort',
                f'HTML best-effort parser could not finish cleanly: {_format_verification_exception(exc)}',
            )

    if suffix == '.css':
        return _verification_unverified(
            'unverified_no_parser',
            'CSS was written successfully, but no reliable local CSS parser is configured.',
        )

    if suffix == '.md':
        front_matter = _extract_markdown_front_matter(text)
        if front_matter.get('present'):
            if front_matter.get('error'):
                return _verification_failure(
                    'markdown_front_matter',
                    str(front_matter.get('error') or 'invalid_front_matter'),
                    observed_state='file_invalid_front_matter',
                    drift_reason='markdown_front_matter_invalid',
                    repair_hint='fix_markdown_front_matter',
                )
            try:
                import yaml

                yaml.safe_load(str(front_matter.get('content') or ''))
            except ImportError:
                return _verification_unverified(
                    'unverified_no_parser',
                    'Markdown front matter exists, but no YAML parser is available for verification.',
                )
            except Exception as exc:
                return _verification_failure(
                    'markdown_front_matter',
                    _format_verification_exception(exc),
                    observed_state='file_invalid_front_matter',
                    drift_reason='markdown_front_matter_invalid',
                    repair_hint='fix_markdown_front_matter',
                )
            return _verification_unverified(
                'markdown_front_matter_only',
                'Markdown front matter parsed successfully, but the Markdown body itself was not strictly verified.',
            )
        return _verification_unverified(
            'unverified_no_parser',
            'Markdown was written successfully, but no reliable Markdown syntax verifier is configured.',
        )

    return _verification_unverified(
        'unverified_no_parser',
        f'No file-level verifier is configured for {suffix or "this file type"}.',
    )


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


def build_protocol_arg_failure_feedback(tool_name: str, tool_args: dict | None, missing_fields: list[str]) -> str:
    signature = protocol_arg_failure_signature(tool_name, tool_args, missing_fields)
    target = signature.get('target') or '未提供目标'
    if tool_name == 'write_file' and 'content' in missing_fields:
        return (
            '执行失败: 缺少 content。\n'
            f'write_file 必须同时提供 file_path 和完整文件内容；当前目标是 {target}。\n'
            '不要重复只带 file_path 的调用。\n'
            '如果你已经知道这个文件要写什么，就直接重新调用 write_file，并把该文件的完整 content 一次性传入。\n'
            '如果你已经有准确的 unified diff 补丁，直接调用 apply_unified_diff。\n'
            '如果你已经知道文件里哪段 old_text 要替换成 new_text，直接调用 search_replace。\n'
            '如果是在已有文件上按需求修改，直接调用 edit_file，传 file_path + change_request。\n'
            '如果还缺项目结构或相邻文件信息，先调用 list_files / read_file 再决定写入。\n'
            '只有在文件内容真的依赖用户选择，或你确实缺少必要上下文时，才停止工具调用并向用户解释阻塞。'
        )
    if tool_name == 'edit_file' and 'change_request' in missing_fields:
        return (
            '执行失败: 缺少 change_request。\n'
            f'edit_file 需要目标文件和要怎么改的明确说明；当前目标是 {target}。\n'
            '请写明要改哪里、要达到什么效果。如果还需要上下文，先调用 list_files / read_file。'
        )
    if tool_name == 'search_replace':
        if 'old_text' in missing_fields:
            return (
                '执行失败: 缺少 old_text。\n'
                f'search_replace 需要明确知道要替换的原始文本；当前目标是 {target}。\n'
                '请提供文件里当前实际存在的精确文本片段；如果还不确定，先调用 read_file。'
            )
        if 'new_text' in missing_fields:
            return (
                '执行失败: 缺少 new_text。\n'
                f'search_replace 需要明确知道替换成什么；当前目标是 {target}。\n'
                '请提供 new_text；如果是删除旧文本，也要显式传空字符串而不是省略字段。'
            )
    if tool_name == 'apply_unified_diff' and 'patch' in missing_fields:
        return (
            '执行失败: 缺少 patch。\n'
            f'apply_unified_diff 需要明确的 unified diff 补丁；当前目标是 {target}。\n'
            '请传 patch；如果你还没有精确 diff，先用 search_replace 或 edit_file。'
        )
    return f"执行失败: 缺少必要参数 {', '.join(missing_fields)}。请补全参数后再继续。"


def build_protocol_arg_failure_system_note(tool_name: str, tool_args: dict | None, missing_fields: list[str]) -> str:
    signature = protocol_arg_failure_signature(tool_name, tool_args, missing_fields)
    target = signature.get('target') or 'unknown target'
    missing = ', '.join(signature.get('missing_fields') or ())
    if tool_name == 'write_file':
        return (
            f'The previous write_file call for {target} failed because required arguments were missing: {missing}. '
            'Do not repeat the same incomplete write_file call. '
            'If you already know what the file should contain, immediately call write_file again with the same file_path and the COMPLETE file content string. '
            'If you already have a precise unified diff patch for this file, call apply_unified_diff instead. '
            'If you already know the exact old_text and new_text for a local change, call search_replace instead. '
            'If the target file already exists and you need to modify it from instructions, call edit_file with the same file_path and a precise change_request instead. '
            'If you still need project structure or neighboring file context, inspect with list_files or read_file first, then rebuild the full content. '
            'Only stop calling tools and explain the blocker if the file content genuinely depends on a missing user choice or missing context you cannot infer.'
        )
    if tool_name == 'edit_file':
        return (
            f'The previous edit_file call for {target} failed because required arguments were missing: {missing}. '
            'Do not repeat the same incomplete edit_file call. '
            'Call edit_file again with the same file_path and a precise change_request that describes the intended modification. '
            'If you still need surrounding project context, inspect with list_files or read_file first. '
            'Only stop calling tools if the change request depends on a missing user choice you cannot infer.'
        )
    if tool_name == 'search_replace':
        return (
            f'The previous search_replace call for {target} failed because required arguments were missing: {missing}. '
            'Do not repeat the same incomplete search_replace call. '
            'Call search_replace again with the same file_path, the exact existing old_text, and an explicit new_text field. '
            'If you are not certain what text currently exists in the file, inspect with read_file first.'
        )
    if tool_name == 'apply_unified_diff':
        return (
            f'The previous apply_unified_diff call for {target} failed because required arguments were missing: {missing}. '
            'Do not repeat the same incomplete patch call. '
            'Call apply_unified_diff again with the same file_path and a valid unified diff patch string. '
            'If you do not already have a precise diff, prefer search_replace or edit_file.'
        )
    return (
        f'The previous tool call failed because required arguments were missing: {missing}. '
        'Do not repeat the same incomplete call. Either provide the missing arguments or stop and explain the blocker.'
    )


def build_protocol_retry_note(tool_name: str, tool_args: dict | None, exec_result: dict | None) -> str:
    if not isinstance(exec_result, dict) or exec_result.get('success', False):
        return ''

    missing_fields = missing_required_protocol_fields(tool_name, tool_args)
    if missing_fields:
        return build_protocol_arg_failure_system_note(tool_name, tool_args, missing_fields)

    file_tools = {'write_file', 'edit_file', 'search_replace', 'apply_unified_diff', 'read_file', 'list_files'}
    environment_tools = {'open_target', 'app_target', 'ui_interaction', 'folder_explore', 'sense_environment', 'screen_capture'}
    command_tools = {'run_command'}

    if tool_name in file_tools:
        return (
            'The previous file/code action failed. Do not repeat the exact same call blindly. '
            'If the current project structure or nearby files may matter, inspect with list_files or read_file first, then choose the next action.'
        )

    if tool_name in environment_tools:
        return (
            'The previous environment action failed. Do not repeat the exact same desktop action blindly. '
            'Inspect the current state with sense_environment or screen_capture first, then choose the next step.'
        )

    if tool_name in command_tools:
        return (
            'The previous local build, package, install, or test command failed. '
            'Do not blindly repeat the same command. Inspect the output, workdir, and expected_artifacts first, '
            'then adjust the command or fix the relevant files.'
        )

    return (
        'The previous tool call failed. Do not repeat the same failing call without changing arguments, checking state, or choosing a more informative tool first.'
    )


def _strip_llm_code_fence(text: str) -> str:
    content = str(text or '').strip()
    if not content.startswith('```'):
        return content
    lines = content.splitlines()
    if lines and lines[0].startswith('```'):
        lines = lines[1:]
    if lines and lines[-1].strip() == '```':
        lines = lines[:-1]
    return '\n'.join(lines).strip()


def _parse_unified_diff_hunks(patch_text: str) -> tuple[list[dict], str]:
    text = _strip_llm_code_fence(patch_text)
    lines = text.splitlines()
    hunks: list[dict] = []
    current: dict | None = None
    header_re = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')

    for raw_line in lines:
        line = str(raw_line)
        if line.startswith(('diff --git ', 'index ', '--- ', '+++ ')):
            continue
        if line.startswith('@@ '):
            match = header_re.match(line)
            if not match:
                return [], f'malformed_hunk_header:{line[:120]}'
            current = {
                'old_start': int(match.group(1) or '0'),
                'old_count': int(match.group(2) or '1'),
                'new_start': int(match.group(3) or '0'),
                'new_count': int(match.group(4) or '1'),
                'lines': [],
                'no_newline': False,
            }
            hunks.append(current)
            continue
        if line == r'\ No newline at end of file':
            if current is not None:
                current['no_newline'] = True
            continue
        if current is None:
            if not line.strip():
                continue
            return [], f'no_hunk_header_before_line:{line[:120]}'
        if not line:
            return [], 'malformed_hunk_line:empty'
        prefix = line[0]
        if prefix not in {' ', '+', '-'}:
            return [], f'malformed_hunk_line:{line[:120]}'
        current['lines'].append((prefix, line[1:]))

    if not hunks:
        return [], 'no_hunks_found'
    return hunks, ''


def _apply_unified_diff_to_text(original_content: str, patch_text: str) -> tuple[str, dict]:
    hunks, parse_error = _parse_unified_diff_hunks(patch_text)
    if parse_error:
        raise ValueError(parse_error)

    original_lines = original_content.splitlines()
    had_trailing_newline = original_content.endswith('\n')
    result_lines: list[str] = []
    original_index = 0
    added_lines = 0
    removed_lines = 0

    for hunk in hunks:
        old_start = max(0, int(hunk.get('old_start') or 0) - 1)
        if old_start < original_index or old_start > len(original_lines):
            raise ValueError(f'hunk_target_out_of_range:{old_start + 1}')
        result_lines.extend(original_lines[original_index:old_start])
        idx = old_start
        for prefix, text in hunk.get('lines') or []:
            if prefix == ' ':
                if idx >= len(original_lines) or original_lines[idx] != text:
                    raise ValueError(f'context_mismatch:{text[:120]}')
                result_lines.append(original_lines[idx])
                idx += 1
            elif prefix == '-':
                if idx >= len(original_lines) or original_lines[idx] != text:
                    raise ValueError(f'remove_mismatch:{text[:120]}')
                idx += 1
                removed_lines += 1
            elif prefix == '+':
                result_lines.append(text)
                added_lines += 1
        original_index = idx

    result_lines.extend(original_lines[original_index:])
    updated_content = '\n'.join(result_lines)
    trailing_newline = had_trailing_newline and not bool((hunks[-1] or {}).get('no_newline'))
    if result_lines and trailing_newline:
        updated_content += '\n'
    return updated_content, {'hunk_count': len(hunks), 'added_lines': added_lines, 'removed_lines': removed_lines}


def _generate_edited_file_content(target: Path, original_content: str, change_request: str) -> str:
    from brain import LLM_CONFIG, llm_call_stream

    prompt = (
        'You are modifying an existing local file.\n'
        'Return ONLY the final complete file content.\n'
        'Do not explain changes.\n'
        'Do not wrap the answer in markdown fences.\n\n'
        f'File path: {target}\n'
        f'Change request: {change_request}\n\n'
        'Current file content:\n'
        '```text\n'
        f'{original_content}\n'
        '```'
    )

    chunks = []
    for token in llm_call_stream(
        dict(LLM_CONFIG),
        [{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=8192,
        timeout=60,
    ):
        if isinstance(token, str):
            chunks.append(token)

    rewritten = _strip_llm_code_fence(''.join(chunks))
    if not rewritten:
        raise ValueError('model_returned_empty_content')
    if original_content and len(rewritten) < max(20, int(len(original_content) * 0.2)):
        raise ValueError('model_returned_truncated_content')
    return rewritten


def execute_write_file_action(arguments: dict | None, *, user_input: str = '') -> dict:
    args = dict(arguments or {})
    file_path = str(
        args.get('file_path', '')
        or args.get('path', '')
        or args.get('target', '')
        or args.get('filename', '')
        or ''
    ).strip()
    content = str(args.get('content', '') or '')
    description = str(args.get('description', '') or '').strip()

    missing = missing_required_protocol_fields('write_file', {'file_path': file_path, 'content': content})
    target_hint = file_path.strip()
    if missing:
        feedback = build_protocol_arg_failure_feedback('write_file', {'file_path': file_path, 'content': content}, missing)
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='write_ready',
            observed_state='missing_required_args',
            drift_reason='missing_required_args',
            repair_hint='provide_complete_file_content',
            repair_attempted=False,
            repair_succeeded=False,
            action_kind='write_file',
            target_kind='file',
            target=target_hint,
            outcome='blocked',
            display_hint=f"写入文件缺少必要参数：{Path(target_hint).name if target_hint else '未提供目标'}",
            verification_mode='argument_check',
            verification_detail=f"missing_fields={','.join(missing)}",
            verified=False,
        )

    target = resolve_user_file_target(file_path)
    if not target:
        feedback = '执行失败: 缺少 file_path。'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='write_ready',
            observed_state='path_unresolved',
            drift_reason='missing_write_target',
            repair_hint='provide_valid_file_path',
            action_kind='write_file',
            target_kind='file',
            target='',
            outcome='unresolved',
            display_hint='写入文件时没有解析出目标路径',
            verification_mode='path_resolution',
            verification_detail='target_unresolved',
            verified=False,
        )

    if not is_allowed_write_target(target):
        feedback = f"执行失败: 目标路径不可写入：`{target}`"
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='write_allowed',
            observed_state='write_blocked',
            drift_reason='write_target_protected',
            repair_hint='choose_safe_workspace_path',
            action_kind='write_file',
            target_kind='file',
            target=str(target),
            outcome='blocked',
            display_hint=f"写入被保护策略拦下：{target.name}",
            verification_mode='write_guard',
            verification_detail='protected_target',
            verified=False,
        )

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
    except Exception as exc:
        feedback = f"写入失败: {exc}"
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='file_written',
            observed_state='write_exception',
            drift_reason='write_exception',
            repair_hint='check_path_permissions_or_content',
            action_kind='write_file',
            target_kind='file',
            target=str(target),
            outcome='failed',
            display_hint=f"写入文件失败：{target.name}",
            verification_mode='write_exception',
            verification_detail=str(exc),
            verified=False,
        )

    post = verify_post_condition('write_file', str(target))
    summary = description or f"已写入文件：{target}"
    if not bool(post.get('ok', False)):
        return build_protocol_exec_result(
            False,
            f"{summary}\n路径：{target}",
            error='写入后未检测到目标文件',
            expected_state=str(post.get('expected') or 'file_written'),
            observed_state=str(post.get('observed') or 'file_written'),
            drift_reason=str(post.get('drift') or ''),
            repair_hint=str(post.get('hint') or ''),
            repair_attempted=False,
            repair_succeeded=False,
            action_kind='write_file',
            target_kind='file',
            target=str(target),
            outcome='write_unconfirmed',
            display_hint=f"写入后未确认文件：{target.name}",
            verification_mode='path_exists',
            verification_detail=str(target),
            post_condition=post,
            verified=False,
        )

    verification = verify_file_change(target, content=content, context={'user_input': user_input})
    verification_mode = str(verification.get('verification_mode') or 'path_exists')
    verification_detail = str(verification.get('verification_detail') or str(target))
    verification_state = verification.get('verified')
    if verification_state is False:
        return build_protocol_exec_result(
            False,
            f"{summary}\n路径：{target}\n文件已写入，但语义核验失败：{verification_detail}",
            error=f'文件已写入，但语义核验失败：{verification_detail}',
            expected_state='file_verified',
            observed_state=str(verification.get('observed_state') or 'file_invalid_syntax'),
            drift_reason=str(verification.get('drift_reason') or 'file_verification_failed'),
            repair_hint=str(verification.get('repair_hint') or 'fix_file_syntax'),
            repair_attempted=False,
            repair_succeeded=False,
            action_kind='write_file',
            target_kind='file',
            target=str(target),
            outcome='written_but_invalid',
            display_hint=f"文件已写入但核验失败：{target.name}",
            verification_mode=verification_mode,
            verification_detail=verification_detail,
            post_condition=post,
            verified=False,
            verification_explicit=True,
        )

    unverified = verification_state is None
    return build_protocol_exec_result(
        True,
        f"{summary}\n路径：{target}",
        error='',
        expected_state='file_written' if unverified else 'file_verified',
        observed_state=str(verification.get('observed_state') or ('file_unverified' if unverified else 'file_verified')),
        drift_reason='',
        repair_hint='',
        repair_attempted=False,
        repair_succeeded=True,
        action_kind='write_file',
        target_kind='file',
        target=str(target),
        outcome='written',
        display_hint=f"已写入文件（未核验）：{target.name}" if unverified else f"已写入文件：{target.name}",
        verification_mode=verification_mode,
        verification_detail=verification_detail,
        post_condition=post,
        verified=verification_state,
        verification_explicit=True,
    )


def execute_edit_file_action(arguments: dict | None, *, user_input: str = '') -> dict:
    args = dict(arguments or {})
    file_path = str(
        args.get('file_path', '')
        or args.get('path', '')
        or args.get('target', '')
        or args.get('filename', '')
        or ''
    ).strip()
    change_request = str(
        args.get('change_request', '')
        or args.get('instructions', '')
        or args.get('problem', '')
        or args.get('description', '')
        or user_input
        or ''
    ).strip()

    missing = missing_required_protocol_fields('edit_file', {'file_path': file_path, 'change_request': change_request})
    target_hint = file_path.strip()
    if missing:
        feedback = build_protocol_arg_failure_feedback(
            'edit_file',
            {'file_path': file_path, 'change_request': change_request},
            missing,
        )
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='edit_ready',
            observed_state='missing_required_args',
            drift_reason='missing_required_args',
            repair_hint='provide_change_request',
            repair_attempted=False,
            repair_succeeded=False,
            action_kind='edit_file',
            target_kind='file',
            target=target_hint,
            outcome='blocked',
            display_hint=f"修改文件缺少必要参数：{Path(target_hint).name if target_hint else '未提供目标'}",
            verification_mode='argument_check',
            verification_detail=f"missing_fields={','.join(missing)}",
            verified=False,
        )

    target = resolve_user_file_target(file_path)
    if not target:
        feedback = '执行失败: 缺少 file_path。'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='edit_ready',
            observed_state='path_unresolved',
            drift_reason='missing_edit_target',
            repair_hint='provide_valid_file_path',
            action_kind='edit_file',
            target_kind='file',
            target='',
            outcome='unresolved',
            display_hint='修改文件时没有解析出目标路径',
            verification_mode='path_resolution',
            verification_detail='target_unresolved',
            verified=False,
        )

    if not target.exists() or not target.is_file():
        feedback = f'执行失败: 目标文件不存在：{target}'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='editable_file_present',
            observed_state='file_missing',
            drift_reason='edit_target_missing',
            repair_hint='read_or_create_target_first',
            action_kind='edit_file',
            target_kind='file',
            target=str(target),
            outcome='blocked',
            display_hint=f'目标文件不存在：{target.name}',
            verification_mode='path_exists',
            verification_detail=str(target),
            verified=False,
        )

    if not is_allowed_write_target(target):
        feedback = f'执行失败: 目标路径不可修改：`{target}`'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='edit_allowed',
            observed_state='edit_blocked',
            drift_reason='write_target_protected',
            repair_hint='choose_safe_workspace_path',
            action_kind='edit_file',
            target_kind='file',
            target=str(target),
            outcome='blocked',
            display_hint=f'修改被保护策略拦下：{target.name}',
            verification_mode='write_guard',
            verification_detail='protected_target',
            verified=False,
        )

    try:
        original_content = target.read_text(encoding='utf-8')
    except Exception as exc:
        feedback = f'读取失败: {exc}'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='file_readable',
            observed_state='read_exception',
            drift_reason='read_exception',
            repair_hint='check_path_permissions_or_encoding',
            action_kind='edit_file',
            target_kind='file',
            target=str(target),
            outcome='failed',
            display_hint=f'读取目标文件失败：{target.name}',
            verification_mode='read_exception',
            verification_detail=str(exc),
            verified=False,
        )

    try:
        updated_content = _generate_edited_file_content(target, original_content, change_request)
    except Exception as exc:
        feedback = f'修改失败: {exc}'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='edited_content_ready',
            observed_state='generation_failed',
            drift_reason='edit_generation_failed',
            repair_hint='refine_change_request_or_read_context',
            action_kind='edit_file',
            target_kind='file',
            target=str(target),
            outcome='failed',
            display_hint=f'生成修改内容失败：{target.name}',
            verification_mode='content_generation',
            verification_detail=str(exc),
            verified=False,
        )

    try:
        target.write_text(updated_content, encoding='utf-8')
        observed_content = target.read_text(encoding='utf-8')
    except Exception as exc:
        feedback = f'写入失败: {exc}'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='file_edited',
            observed_state='write_exception',
            drift_reason='write_exception',
            repair_hint='check_path_permissions_or_content',
            action_kind='edit_file',
            target_kind='file',
            target=str(target),
            outcome='failed',
            display_hint=f'修改文件失败：{target.name}',
            verification_mode='write_exception',
            verification_detail=str(exc),
            verified=False,
        )

    verified = observed_content == updated_content
    post = {
        'ok': verified,
        'expected': 'file_edited',
        'observed': 'file_edited' if verified else 'file_edit_unconfirmed',
        'drift': '' if verified else 'edit_not_persisted',
        'hint': '' if verified else 'retry_or_check_write_target',
    }
    summary = f'已修改文件：{target}'
    if not verified:
        return build_protocol_exec_result(
            False,
            f"{summary}\n变更：{change_request}",
            error='修改后未能确认文件内容已持久化',
            expected_state='file_edited',
            observed_state=str(post.get('observed') or ''),
            drift_reason=str(post.get('drift') or ''),
            repair_hint=str(post.get('hint') or ''),
            repair_attempted=False,
            repair_succeeded=False,
            action_kind='edit_file',
            target_kind='file',
            target=str(target),
            outcome='edit_unconfirmed',
            display_hint=f'修改后未确认文件：{target.name}',
            verification_mode='content_roundtrip',
            verification_detail=str(target),
            post_condition=post,
            verified=False,
        )

    verification = verify_file_change(target, content=observed_content, context={'change_request': change_request, 'user_input': user_input})
    verification_mode = str(verification.get('verification_mode') or 'content_roundtrip')
    verification_detail = str(verification.get('verification_detail') or str(target))
    verification_state = verification.get('verified')
    if verification_state is False:
        return build_protocol_exec_result(
            False,
            f"{summary}\n变更：{change_request}\n文件已修改，但语义核验失败：{verification_detail}",
            error=f'文件已修改，但语义核验失败：{verification_detail}',
            expected_state='file_verified',
            observed_state=str(verification.get('observed_state') or 'file_invalid_syntax'),
            drift_reason=str(verification.get('drift_reason') or 'file_verification_failed'),
            repair_hint=str(verification.get('repair_hint') or 'fix_file_syntax'),
            repair_attempted=False,
            repair_succeeded=False,
            action_kind='edit_file',
            target_kind='file',
            target=str(target),
            outcome='edited_but_invalid',
            display_hint=f'文件已修改但核验失败：{target.name}',
            verification_mode=verification_mode,
            verification_detail=verification_detail,
            post_condition=post,
            verified=False,
            verification_explicit=True,
        )

    unverified = verification_state is None
    return build_protocol_exec_result(
        True,
        f"{summary}\n变更：{change_request}",
        error='',
        expected_state='file_edited' if unverified else 'file_verified',
        observed_state=str(verification.get('observed_state') or ('file_unverified' if unverified else 'file_verified')),
        drift_reason='',
        repair_hint='',
        repair_attempted=False,
        repair_succeeded=True,
        action_kind='edit_file',
        target_kind='file',
        target=str(target),
        outcome='edited',
        display_hint=f'已修改文件（未核验）：{target.name}' if unverified else f'已修改文件：{target.name}',
        verification_mode=verification_mode,
        verification_detail=verification_detail,
        post_condition=post,
        verified=verification_state,
        verification_explicit=True,
    )


def execute_search_replace_action(arguments: dict | None, *, user_input: str = '') -> dict:
    args = dict(arguments or {})
    file_path = str(
        args.get('file_path', '')
        or args.get('path', '')
        or args.get('target', '')
        or args.get('filename', '')
        or ''
    ).strip()
    old_text = args.get('old_text')
    if old_text is None:
        old_text = args.get('search_text')
    if old_text is None:
        old_text = args.get('find_text')
    if old_text is None:
        old_text = args.get('before')
    old_text = str(old_text or '')

    new_text_value = None
    for key in ('new_text', 'replacement', 'replace_text', 'after'):
        if key in args:
            new_text_value = args.get(key)
            break
    new_text = '' if new_text_value is None else str(new_text_value)
    replace_all_raw = args.get('replace_all', False)
    if isinstance(replace_all_raw, str):
        replace_all = replace_all_raw.strip().lower() in {'1', 'true', 'yes', 'y', 'on'}
    else:
        replace_all = bool(replace_all_raw)

    missing = missing_required_protocol_fields(
        'search_replace',
        {'file_path': file_path, 'old_text': old_text, 'new_text': new_text, **args},
    )
    target_hint = file_path.strip()
    if missing:
        feedback = build_protocol_arg_failure_feedback(
            'search_replace',
            {'file_path': file_path, 'old_text': old_text, 'new_text': new_text, **args},
            missing,
        )
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='search_replace_ready',
            observed_state='missing_required_args',
            drift_reason='missing_required_args',
            repair_hint='provide_search_replace_arguments',
            repair_attempted=False,
            repair_succeeded=False,
            action_kind='search_replace',
            target_kind='file',
            target=target_hint,
            outcome='blocked',
            display_hint=f"替换文本缺少必要参数：{Path(target_hint).name if target_hint else '未提供目标'}",
            verification_mode='argument_check',
            verification_detail=f"missing_fields={','.join(missing)}",
            verified=False,
        )

    target = resolve_user_file_target(file_path)
    if not target:
        feedback = '执行失败: 缺少 file_path。'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='search_replace_ready',
            observed_state='path_unresolved',
            drift_reason='missing_replace_target',
            repair_hint='provide_valid_file_path',
            action_kind='search_replace',
            target_kind='file',
            target='',
            outcome='unresolved',
            display_hint='替换文本时没有解析出目标路径',
            verification_mode='path_resolution',
            verification_detail='target_unresolved',
            verified=False,
        )

    if not target.exists() or not target.is_file():
        feedback = f'执行失败: 目标文件不存在：{target}'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='replace_target_present',
            observed_state='file_missing',
            drift_reason='replace_target_missing',
            repair_hint='read_or_create_target_first',
            action_kind='search_replace',
            target_kind='file',
            target=str(target),
            outcome='blocked',
            display_hint=f'目标文件不存在：{target.name}',
            verification_mode='path_exists',
            verification_detail=str(target),
            verified=False,
        )

    if not is_allowed_write_target(target):
        feedback = f'执行失败: 目标路径不可修改：`{target}`'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='replace_allowed',
            observed_state='replace_blocked',
            drift_reason='write_target_protected',
            repair_hint='choose_safe_workspace_path',
            action_kind='search_replace',
            target_kind='file',
            target=str(target),
            outcome='blocked',
            display_hint=f'替换被保护策略拦下：{target.name}',
            verification_mode='write_guard',
            verification_detail='protected_target',
            verified=False,
        )

    try:
        original_content = target.read_text(encoding='utf-8')
    except Exception as exc:
        feedback = f'读取失败: {exc}'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='file_readable',
            observed_state='read_exception',
            drift_reason='read_exception',
            repair_hint='check_path_permissions_or_encoding',
            action_kind='search_replace',
            target_kind='file',
            target=str(target),
            outcome='failed',
            display_hint=f'读取目标文件失败：{target.name}',
            verification_mode='read_exception',
            verification_detail=str(exc),
            verified=False,
        )

    occurrences = original_content.count(old_text)
    if occurrences <= 0:
        feedback = f'执行失败: 目标文件里没有找到指定 old_text：{target}'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='match_found',
            observed_state='match_missing',
            drift_reason='search_text_not_found',
            repair_hint='read_file_or_use_more_precise_old_text',
            action_kind='search_replace',
            target_kind='file',
            target=str(target),
            outcome='blocked',
            display_hint=f'未找到可替换文本：{target.name}',
            verification_mode='text_match',
            verification_detail='match_count=0',
            verified=False,
        )

    if occurrences > 1 and not replace_all:
        feedback = (
            f'执行失败: old_text 在目标文件里匹配到 {occurrences} 处，单次替换不够明确：{target}\n'
            '请提供更精确的 old_text，或者显式传 replace_all=true。'
        )
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='single_match_found',
            observed_state='multiple_matches',
            drift_reason='search_text_ambiguous',
            repair_hint='use_more_precise_old_text_or_replace_all',
            action_kind='search_replace',
            target_kind='file',
            target=str(target),
            outcome='blocked',
            display_hint=f'替换文本匹配过多：{target.name}',
            verification_mode='text_match',
            verification_detail=f'match_count={occurrences}',
            verified=False,
        )

    if old_text == new_text:
        feedback = (
            f'执行失败: old_text 和 new_text 完全相同，没有实际变更：{target}\n'
            '请确认你要替换成的新内容，或者改用 read_file 先检查当前文件。'
        )
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='effective_change_ready',
            observed_state='no_effective_change',
            drift_reason='search_replace_noop',
            repair_hint='provide_distinct_new_text',
            action_kind='search_replace',
            target_kind='file',
            target=str(target),
            outcome='blocked',
            display_hint=f'替换内容没有变化：{target.name}',
            verification_mode='argument_check',
            verification_detail='old_text_equals_new_text',
            verified=False,
        )

    updated_content = (
        original_content.replace(old_text, new_text)
        if replace_all
        else original_content.replace(old_text, new_text, 1)
    )

    try:
        target.write_text(updated_content, encoding='utf-8')
        observed_content = target.read_text(encoding='utf-8')
    except Exception as exc:
        feedback = f'写入失败: {exc}'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='file_replaced',
            observed_state='write_exception',
            drift_reason='write_exception',
            repair_hint='check_path_permissions_or_content',
            action_kind='search_replace',
            target_kind='file',
            target=str(target),
            outcome='failed',
            display_hint=f'替换文本失败：{target.name}',
            verification_mode='write_exception',
            verification_detail=str(exc),
            verified=False,
        )

    verified = observed_content == updated_content
    replaced_count = occurrences if replace_all else 1
    post = {
        'ok': verified,
        'expected': 'file_edited',
        'observed': 'file_edited' if verified else 'file_edit_unconfirmed',
        'drift': '' if verified else 'replace_not_persisted',
        'hint': '' if verified else 'retry_or_check_write_target',
    }
    summary = f'已替换文件内容：{target}'
    detail = f'匹配 {occurrences} 处，实际替换 {replaced_count} 处'
    if not verified:
        return build_protocol_exec_result(
            False,
            f"{summary}\n{detail}",
            error='替换后未能确认文件内容已持久化',
            expected_state='file_edited',
            observed_state=str(post.get('observed') or ''),
            drift_reason=str(post.get('drift') or ''),
            repair_hint=str(post.get('hint') or ''),
            repair_attempted=False,
            repair_succeeded=False,
            action_kind='search_replace',
            target_kind='file',
            target=str(target),
            outcome='edit_unconfirmed',
            display_hint=f'替换后未确认文件：{target.name}',
            verification_mode='content_roundtrip',
            verification_detail=f'{target} | match_count={occurrences} | replaced_count={replaced_count}',
            post_condition=post,
            verified=False,
        )

    verification = verify_file_change(target, content=observed_content, context={'user_input': user_input})
    verification_mode = str(verification.get('verification_mode') or 'content_roundtrip')
    verification_detail = str(
        verification.get('verification_detail')
        or f'{target} | match_count={occurrences} | replaced_count={replaced_count}'
    )
    verification_state = verification.get('verified')
    if verification_state is False:
        return build_protocol_exec_result(
            False,
            f"{summary}\n{detail}\n文件已替换，但语义核验失败：{verification_detail}",
            error=f'文件已替换，但语义核验失败：{verification_detail}',
            expected_state='file_verified',
            observed_state=str(verification.get('observed_state') or 'file_invalid_syntax'),
            drift_reason=str(verification.get('drift_reason') or 'file_verification_failed'),
            repair_hint=str(verification.get('repair_hint') or 'fix_file_syntax'),
            repair_attempted=False,
            repair_succeeded=False,
            action_kind='search_replace',
            target_kind='file',
            target=str(target),
            outcome='edited_but_invalid',
            display_hint=f'文件已替换但核验失败：{target.name}',
            verification_mode=verification_mode,
            verification_detail=verification_detail,
            post_condition=post,
            verified=False,
            verification_explicit=True,
        )

    unverified = verification_state is None
    return build_protocol_exec_result(
        True,
        f"{summary}\n{detail}",
        error='',
        expected_state='file_edited' if unverified else 'file_verified',
        observed_state=str(verification.get('observed_state') or ('file_unverified' if unverified else 'file_verified')),
        drift_reason='',
        repair_hint='',
        repair_attempted=False,
        repair_succeeded=True,
        action_kind='search_replace',
        target_kind='file',
        target=str(target),
        outcome='edited',
        display_hint=f'已替换文件内容（未核验）：{target.name}' if unverified else f'已替换文件内容：{target.name}',
        verification_mode=verification_mode,
        verification_detail=verification_detail,
        post_condition=post,
        verified=verification_state,
        verification_explicit=True,
    )


def execute_apply_unified_diff_action(arguments: dict | None, *, user_input: str = '') -> dict:
    args = dict(arguments or {})
    file_path = str(
        args.get('file_path', '')
        or args.get('path', '')
        or args.get('target', '')
        or args.get('filename', '')
        or ''
    ).strip()
    patch_text = str(
        args.get('patch', '')
        or args.get('diff', '')
        or args.get('unified_diff', '')
        or ''
    )

    missing = missing_required_protocol_fields(
        'apply_unified_diff',
        {'file_path': file_path, 'patch': patch_text, **args},
    )
    target_hint = file_path.strip()
    if missing:
        feedback = build_protocol_arg_failure_feedback(
            'apply_unified_diff',
            {'file_path': file_path, 'patch': patch_text, **args},
            missing,
        )
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='patch_ready',
            observed_state='missing_required_args',
            drift_reason='missing_required_args',
            repair_hint='provide_unified_diff_patch',
            repair_attempted=False,
            repair_succeeded=False,
            action_kind='apply_unified_diff',
            target_kind='file',
            target=target_hint,
            outcome='blocked',
            display_hint=f"补丁应用缺少必要参数：{Path(target_hint).name if target_hint else '未提供目标'}",
            verification_mode='argument_check',
            verification_detail=f"missing_fields={','.join(missing)}",
            verified=False,
        )

    target = resolve_user_file_target(file_path)
    if not target:
        feedback = '执行失败: 缺少 file_path。'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='patch_ready',
            observed_state='path_unresolved',
            drift_reason='missing_patch_target',
            repair_hint='provide_valid_file_path',
            action_kind='apply_unified_diff',
            target_kind='file',
            target='',
            outcome='unresolved',
            display_hint='应用补丁时没有解析出目标路径',
            verification_mode='path_resolution',
            verification_detail='target_unresolved',
            verified=False,
        )

    if not target.exists() or not target.is_file():
        feedback = f'执行失败: 目标文件不存在：{target}'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='patch_target_present',
            observed_state='file_missing',
            drift_reason='patch_target_missing',
            repair_hint='read_or_create_target_first',
            action_kind='apply_unified_diff',
            target_kind='file',
            target=str(target),
            outcome='blocked',
            display_hint=f'目标文件不存在：{target.name}',
            verification_mode='path_exists',
            verification_detail=str(target),
            verified=False,
        )

    if not is_allowed_write_target(target):
        feedback = f'执行失败: 目标路径不可修改：`{target}`'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='patch_allowed',
            observed_state='patch_blocked',
            drift_reason='write_target_protected',
            repair_hint='choose_safe_workspace_path',
            action_kind='apply_unified_diff',
            target_kind='file',
            target=str(target),
            outcome='blocked',
            display_hint=f'补丁被保护策略拦下：{target.name}',
            verification_mode='write_guard',
            verification_detail='protected_target',
            verified=False,
        )

    try:
        original_content = target.read_text(encoding='utf-8')
    except Exception as exc:
        feedback = f'读取失败: {exc}'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='file_readable',
            observed_state='read_exception',
            drift_reason='read_exception',
            repair_hint='check_path_permissions_or_encoding',
            action_kind='apply_unified_diff',
            target_kind='file',
            target=str(target),
            outcome='failed',
            display_hint=f'读取目标文件失败：{target.name}',
            verification_mode='read_exception',
            verification_detail=str(exc),
            verified=False,
        )

    try:
        updated_content, patch_stats = _apply_unified_diff_to_text(original_content, patch_text)
    except Exception as exc:
        feedback = f'补丁应用失败: {exc}'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='patch_applied',
            observed_state='patch_rejected',
            drift_reason='patch_apply_failed',
            repair_hint='fix_patch_or_read_file_first',
            action_kind='apply_unified_diff',
            target_kind='file',
            target=str(target),
            outcome='failed',
            display_hint=f'补丁未能应用：{target.name}',
            verification_mode='patch_apply',
            verification_detail=str(exc),
            verified=False,
        )

    if updated_content == original_content:
        feedback = (
            f'执行失败: 这个 unified diff 没有产生实际变更：{target}\n'
            '请检查 patch 是否真的对应当前文件内容。'
        )
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='effective_patch_ready',
            observed_state='no_effective_change',
            drift_reason='patch_noop',
            repair_hint='provide_effective_patch',
            action_kind='apply_unified_diff',
            target_kind='file',
            target=str(target),
            outcome='blocked',
            display_hint=f'补丁没有产生变化：{target.name}',
            verification_mode='patch_apply',
            verification_detail='patch_no_effective_change',
            verified=False,
        )

    try:
        target.write_text(updated_content, encoding='utf-8')
        observed_content = target.read_text(encoding='utf-8')
    except Exception as exc:
        feedback = f'写入失败: {exc}'
        return build_protocol_exec_result(
            False,
            feedback,
            error=feedback,
            expected_state='patch_persisted',
            observed_state='write_exception',
            drift_reason='write_exception',
            repair_hint='check_path_permissions_or_patch_content',
            action_kind='apply_unified_diff',
            target_kind='file',
            target=str(target),
            outcome='failed',
            display_hint=f'补丁写入失败：{target.name}',
            verification_mode='write_exception',
            verification_detail=str(exc),
            verified=False,
        )

    verified = observed_content == updated_content
    post = {
        'ok': verified,
        'expected': 'file_edited',
        'observed': 'file_edited' if verified else 'file_edit_unconfirmed',
        'drift': '' if verified else 'patch_not_persisted',
        'hint': '' if verified else 'retry_or_check_write_target',
    }
    detail = (
        f"hunks={patch_stats.get('hunk_count', 0)} | "
        f"added_lines={patch_stats.get('added_lines', 0)} | "
        f"removed_lines={patch_stats.get('removed_lines', 0)}"
    )
    if not verified:
        return build_protocol_exec_result(
            False,
            f"已应用 unified diff：{target}\n{detail}",
            error='补丁写入后未能确认文件内容已持久化',
            expected_state='file_edited',
            observed_state=str(post.get('observed') or ''),
            drift_reason=str(post.get('drift') or ''),
            repair_hint=str(post.get('hint') or ''),
            repair_attempted=False,
            repair_succeeded=False,
            action_kind='apply_unified_diff',
            target_kind='file',
            target=str(target),
            outcome='edit_unconfirmed',
            display_hint=f'补丁后未确认文件：{target.name}',
            verification_mode='content_roundtrip',
            verification_detail=f'{target} | {detail}',
            post_condition=post,
            verified=False,
        )

    verification = verify_file_change(target, content=observed_content, context={'user_input': user_input})
    verification_mode = str(verification.get('verification_mode') or 'content_roundtrip')
    verification_detail = str(verification.get('verification_detail') or f'{target} | {detail}')
    verification_state = verification.get('verified')
    if verification_state is False:
        return build_protocol_exec_result(
            False,
            f"已应用 unified diff：{target}\n{detail}\n补丁已写入，但语义核验失败：{verification_detail}",
            error=f'补丁已写入，但语义核验失败：{verification_detail}',
            expected_state='file_verified',
            observed_state=str(verification.get('observed_state') or 'file_invalid_syntax'),
            drift_reason=str(verification.get('drift_reason') or 'file_verification_failed'),
            repair_hint=str(verification.get('repair_hint') or 'fix_file_syntax'),
            repair_attempted=False,
            repair_succeeded=False,
            action_kind='apply_unified_diff',
            target_kind='file',
            target=str(target),
            outcome='edited_but_invalid',
            display_hint=f'补丁已写入但核验失败：{target.name}',
            verification_mode=verification_mode,
            verification_detail=verification_detail,
            post_condition=post,
            verified=False,
            verification_explicit=True,
        )

    unverified = verification_state is None
    return build_protocol_exec_result(
        True,
        f"已应用 unified diff：{target}\n{detail}",
        error='',
        expected_state='file_edited' if unverified else 'file_verified',
        observed_state=str(verification.get('observed_state') or ('file_unverified' if unverified else 'file_verified')),
        drift_reason='',
        repair_hint='',
        repair_attempted=False,
        repair_succeeded=True,
        action_kind='apply_unified_diff',
        target_kind='file',
        target=str(target),
        outcome='edited',
        display_hint=f'已应用补丁（未核验）：{target.name}' if unverified else f'已应用补丁：{target.name}',
        verification_mode=verification_mode,
        verification_detail=verification_detail,
        post_condition=post,
        verified=verification_state,
        verification_explicit=True,
    )


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
