import os
import re
from pathlib import Path
from urllib.parse import urlparse

from .fs import _extract_search_term_v2, load_export_state, normalize_user_special_path

try:
    import pygetwindow as gw
    _HAS_WINDOWS = True
except ImportError:
    _HAS_WINDOWS = False

SHORTCUT_DIRS = [
    Path.home() / 'Desktop',
    Path.home() / 'AppData' / 'Roaming' / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs',
]

PROGRAM_DIRS = [
    Path('C:/Program Files'),
    Path('C:/Program Files (x86)'),
    Path.home() / 'AppData' / 'Local' / 'Programs',
    Path.home() / 'AppData' / 'Local',
]


_PINYIN_MAP = {
    '微信': 'weixin', '钉钉': 'dingding', '飞书': 'feishu', '豆包': 'doubao',
    '网易': 'netease', '百度': 'baidu', '淘宝': 'taobao', '京东': 'jingdong',
    '抖音': 'douyin', '快手': 'kuaishou', '哔哩': 'bilibili', '知乎': 'zhihu',
    '腾讯': 'tencent', '阿里': 'ali', '字节': 'bytedance', '美团': 'meituan',
    '高德': 'amap', '有道': 'youdao', '网易云': 'neteasecloud', '酷狗': 'kugou',
    '迅雷': 'xunlei', '搜狗': 'sougou', '夸克': 'quark',
}

_KNOWN_WEB_TARGETS = (
    ("百度地图", "https://map.baidu.com"),
    ("高德地图", "https://www.amap.com"),
    ("谷歌地图", "https://maps.google.com"),
    ("百度", "https://www.baidu.com"),
    ("谷歌邮箱", "https://mail.google.com"),
    ("gmail", "https://mail.google.com"),
    ("谷歌", "https://www.google.com"),
    ("google", "https://www.google.com"),
    ("淘宝", "https://www.taobao.com"),
    ("京东", "https://www.jd.com"),
    ("抖音", "https://www.douyin.com"),
    ("b站", "https://www.bilibili.com"),
    ("bilibili", "https://www.bilibili.com"),
    ("知乎", "https://www.zhihu.com"),
    ("微博", "https://weibo.com"),
)

_WEB_HINT_TOKENS = (
    "网页",
    "网站",
    "网址",
    "浏览器",
    "官网",
    "首页",
    "search",
    "browser",
    "website",
    "webpage",
    "web page",
    "homepage",
    "home page",
)


def _pinyin_expand(text: str) -> list[str]:
    variants = [text]
    for cn, py in _PINYIN_MAP.items():
        if cn in text:
            variants.append(text.replace(cn, py))
            variants.append(py)
    return list(set(v for v in variants if v))


def _normalize(text: str) -> str:
    return ''.join(str(text or '').strip().lower().split())


def _web_search_term(text: str) -> str:
    try:
        return str(_extract_search_term_v2(text) or "").strip()
    except Exception:
        return ""


def _looks_like_web_request(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    lowered = raw.lower()
    if raw.startswith(("http://", "https://")):
        return True
    if re.search(r'^[\w.-]+\.[A-Za-z]{2,}(/.*)?$', raw):
        return True
    if _web_search_term(raw):
        return True
    return any(token in raw or token in lowered for token in _WEB_HINT_TOKENS)


def extract_explicit_local_path(text: str) -> str:
    raw = str(text or '').strip()
    if not raw:
        return ''

    patterns = (
        re.compile(r'"([A-Za-z]:\\[^"]+|[A-Za-z]:/[^"]+)"'),
        re.compile(r'([A-Za-z]:[\\/][^\s`<>"\]]+)'),
        re.compile(r'((?:桌面|文档|下载|Desktop|Documents|Downloads)[\\/][^\s`<>"\]]+)', re.I),
    )
    for pattern in patterns:
        match = pattern.search(raw)
        if not match:
            continue
        candidate = str(match.group(1) or '').strip().strip(".,;:()[]{}<>\"'，。！？；：")
        if not candidate:
            continue
        normalized = str(normalize_user_special_path(candidate.replace('\\', '/')) or candidate).strip()
        if len(normalized) > 3 and normalized.endswith(('/', '\\')):
            normalized = normalized.rstrip('/\\')
        if normalized:
            return normalized
    return ''


def _extract_explicit_local_path(text: str) -> str:
    return extract_explicit_local_path(text)


def _looks_like_app_path(path: str) -> bool:
    raw = str(path or '').strip()
    if not raw:
        return False
    try:
        path_obj = Path(raw)
    except Exception:
        return False
    if path_obj.is_dir():
        return False
    return path_obj.suffix.lower() in {'.exe', '.lnk', '.bat', '.cmd', '.ps1', '.msc'}


def resolve_lnk_target(lnk_path: str) -> str:
    try:
        import subprocess
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             f"(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk_path}').TargetPath"],
            capture_output=True, timeout=5, encoding='utf-8', errors='replace',
        )
        target = result.stdout.strip()
        if target and Path(target).exists():
            return target
    except Exception:
        pass
    return ''


# ── 缓存：应用和快捷方式列表，首次调用时扫描，10分钟后过期 ──
_app_cache = None
_shortcut_cache = None
_app_cache_time = 0

# ── LLM 目标解析缓存 ──
_llm_target_cache = {}

_ACTION_PREFIXES = (
    "打开桌面上的",
    "打开桌面",
    "打开",
    "启动",
    "运行",
    "进入",
    "帮我打开",
    "请打开",
    "打开一下",
)


def _strip_action_words(text: str) -> str:
    cleaned = str(text or "").strip()
    for prefix in _ACTION_PREFIXES:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    cleaned = re.sub(r"^(桌面上的|桌面上|桌面的|应用|客户端)", "", cleaned).strip()
    cleaned = re.sub(r"(应用|客户端)$", "", cleaned).strip()
    return cleaned or str(text or "").strip()


def _resolve_known_web_target(text: str) -> dict | None:
    raw = str(text or "").strip()
    if not raw:
        return None

    lowered = raw.lower()
    clean_text = _strip_action_words(raw)
    clean_norm = _normalize(clean_text)
    exact_suffixes = {"首页", "官网", "网站", "网页", "浏览器", "网址"}

    for alias, url in _KNOWN_WEB_TARGETS:
        alias_norm = _normalize(alias)
        if not alias_norm:
            continue
        if clean_norm == alias_norm or any(clean_norm == alias_norm + _normalize(suffix) for suffix in exact_suffixes):
            return {
                "target_type": "url",
                "value": url,
                "label": alias,
                "resolution": "resolved",
                "source": "known_web_target",
            }

    if not _looks_like_web_request(raw):
        return None

    for alias, url in _KNOWN_WEB_TARGETS:
        alias_norm = _normalize(alias)
        alias_lower = alias.lower()
        if alias_lower in lowered or alias_norm in clean_norm:
            return {
                "target_type": "url",
                "value": url,
                "label": alias,
                "resolution": "resolved",
                "source": "known_web_target",
            }
    return None


def _llm_resolve_target(text: str) -> dict | None:
    """本地解析失败时，让 LLM 判断目标是 app、网页还是文件，并返回 URL/名称。
    结果会缓存，同一个目标不会重复调用 LLM。"""
    norm = text.strip().lower()
    if not norm or len(norm) > 100:
        return None

    # 缓存命中
    if norm in _llm_target_cache:
        return _llm_target_cache[norm]

    try:
        from core.shared import debug_write
    except Exception:
        debug_write = lambda *a: None

    try:
        from agent_final import _raw_llm_call
    except Exception:
        return None

    prompt = (
        "用户想操作一个目标。请判断这个目标是什么类型，返回JSON。\n\n"
        f"用户说：{text}\n\n"
        "规则：\n"
        "1. 如果是网站或网页服务，返回 {\"type\":\"url\",\"value\":\"根据意图推断并补全的网址\",\"label\":\"名称\"}\n"
        "2. 如果是本地应用程序，返回 {\"type\":\"app\",\"value\":\"应用名或可执行目标\",\"label\":\"名称\"}\n"
        "3. 如果不确定，返回 {\"type\":\"unknown\"}\n"
        "只返回JSON。"
    )

    try:
        raw = _raw_llm_call(prompt) or ''
        # 剥掉 <think> 标签
        if '<think>' in raw and '</think>' in raw:
            raw = raw[raw.index('</think>') + len('</think>'):]
        elif '<think>' in raw:
            raw = ''
        raw = raw.strip()

        debug_write("llm_target_resolve_raw", {"input": text, "raw": raw[:300]})

        import json
        start = raw.find('{')
        end = raw.rfind('}')
        if start != -1 and end > start:
            parsed = json.loads(raw[start:end + 1])
            t = str(parsed.get('type', '')).strip().lower()
            v = str(parsed.get('value', '')).strip()
            label = str(parsed.get('label', '')).strip()

            if t == 'url' and v:
                if not v.startswith('http'):
                    v = 'https://' + v
                result = {'target_type': 'url', 'value': v, 'label': label or v, 'resolution': 'resolved', 'source': 'llm_resolve'}
                _llm_target_cache[norm] = result
                debug_write("llm_target_resolved", {"type": "url", "value": v, "label": label})
                return result
            elif t == 'app' and v:
                result = {'target_type': 'app', 'value': v, 'label': label or v, 'resolution': 'partial', 'source': 'llm_resolve'}
                _llm_target_cache[norm] = result
                debug_write("llm_target_resolved", {"type": "app", "value": v, "label": label})
                return result

        # LLM 也不确定
        _llm_target_cache[norm] = None
    except Exception as e:
        try:
            debug_write("llm_target_resolve_error", {"error": str(e)})
        except Exception:
            pass

    return None


def discover_shortcuts() -> list[dict]:
    global _shortcut_cache
    if _shortcut_cache is not None:
        return _shortcut_cache
    rows = []
    for base in SHORTCUT_DIRS:
        if not base.exists():
            continue
        try:
            for path in base.rglob('*.lnk'):
                rows.append({'label': path.stem, 'path': str(path), 'source': 'shortcut'})
        except Exception:
            continue
    _shortcut_cache = rows
    return rows


def discover_shortcuts_fast() -> list[dict]:
    rows = []
    seen = set()
    for base in SHORTCUT_DIRS:
        if not base.exists():
            continue
        search_dirs = [base]
        try:
            for child in base.iterdir():
                if child.is_dir():
                    search_dirs.append(child)
        except Exception:
            pass
        for folder in search_dirs:
            try:
                for path in folder.glob('*.lnk'):
                    key = str(path).lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append({'label': path.stem, 'path': str(path), 'source': 'shortcut_fast'})
            except Exception:
                continue
    return rows


def _find_local_app_path_fast(label: str) -> str:
    cleaned = _strip_action_words(label)
    candidates = []
    for variant in _pinyin_expand(cleaned):
        norm = _normalize(variant)
        if not norm:
            continue
        candidates.append(norm)
        compact = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", variant.lower())
        if compact:
            candidates.append(compact)
    tokens = []
    for item in candidates:
        if item and item not in tokens:
            tokens.append(item)

    searchable_tokens = []
    for token in tokens:
        ascii_token = re.sub(r'[^a-z0-9]+', '', token.lower())
        if len(ascii_token) >= 2 and ascii_token not in searchable_tokens:
            searchable_tokens.append(ascii_token)
    if not searchable_tokens:
        return ''

    direct_candidates = []
    for base in PROGRAM_DIRS:
        for token in searchable_tokens:
            token_title = token[:1].upper() + token[1:]
            direct_candidates.extend(
                [
                    base / token / f"{token}.exe",
                    base / token / f"{token_title}.exe",
                    base / token / "Application" / f"{token}.exe",
                    base / token / "Application" / f"{token_title}.exe",
                    base / token_title / f"{token}.exe",
                    base / token_title / f"{token_title}.exe",
                    base / token_title / "Application" / f"{token}.exe",
                    base / token_title / "Application" / f"{token_title}.exe",
                ]
            )
    for candidate in direct_candidates:
        try:
            if candidate.exists():
                return str(candidate)
        except Exception:
            continue

    best_path = ''
    best_score = 0
    for base in PROGRAM_DIRS:
        if not base.exists():
            continue
        patterns = []
        for token in searchable_tokens:
            patterns.extend(
                [
                    f"*{token}*.exe",
                    f"*{token}*\\*.exe",
                    f"*{token}*\\*{token}*.exe",
                    f"*{token}*\\*\\*{token}*.exe",
                ]
            )
        for pattern in patterns:
            try:
                matches = base.glob(pattern)
            except Exception:
                matches = []
            for match in matches:
                try:
                    if not match.is_file():
                        continue
                    name_parts = [
                        _normalize(match.stem),
                        _normalize(match.parent.name),
                        _normalize(match.parent.parent.name) if match.parent.parent else '',
                    ]
                    score = 0
                    for token in tokens:
                        if not token:
                            continue
                        for part in name_parts:
                            if not part:
                                continue
                            if token == part:
                                score = max(score, 100)
                            elif token in part:
                                score = max(score, 80)
                            elif part in token and len(part) >= 3:
                                score = max(score, 50)
                    if score > best_score:
                        best_score = score
                        best_path = str(match)
                except Exception:
                    continue
    return best_path if best_score >= 80 else ''


def discover_installed_apps() -> list[dict]:
    global _app_cache, _app_cache_time
    import time as _t
    now = _t.time()
    if _app_cache is not None and (now - _app_cache_time) < 600:
        return _app_cache
    rows = []
    for base in PROGRAM_DIRS:
        if not base.exists():
            continue
        try:
            for exe in base.rglob('*.exe'):
                parent = exe.parent.name
                rows.append({'label': exe.stem, 'dir_label': parent, 'path': str(exe), 'source': 'installed_exe'})
        except Exception:
            continue
    _app_cache = rows
    _app_cache_time = now
    return rows


def discover_windows() -> list[dict]:
    if not _HAS_WINDOWS:
        return []
    try:
        return [{'title': w.title, 'source': 'window'} for w in gw.getAllWindows() if w.title.strip()]
    except Exception:
        return []


def resolve_local_app_reference(raw: str, context: dict | None = None) -> dict:
    text = str(raw or '').strip()
    context = context if isinstance(context, dict) else {}
    if not text:
        return {'target_type': 'unknown', 'value': text, 'resolution': 'missing', 'source': 'local_app_unresolved'}
    clean_text = _strip_action_words(text)

    fs_action = context.get('fs_action') if isinstance(context.get('fs_action'), dict) else {}
    target = fs_action.get('target') if isinstance(fs_action.get('target'), dict) else {}
    if target:
        if target.get('window'):
            return {'target_type': 'window', 'value': str(target.get('window')), 'resolution': 'resolved', 'source': 'fs_action'}
        if target.get('path') and _looks_like_app_path(str(target.get('path'))):
            return {
                'target_type': 'app',
                'value': str(target.get('path')),
                'label': str(target.get('app') or target.get('path')),
                'resolution': 'resolved',
                'source': 'fs_action',
            }
        if target.get('app'):
            app_value = str(target.get('app')).strip()
            exe_path = _find_local_app_path(app_value)
            return {
                'target_type': 'app',
                'value': exe_path or app_value,
                'label': app_value,
                'resolution': 'resolved' if exe_path else 'partial',
                'source': 'fs_action',
            }

    if _resolve_known_web_target(text):
        return {'target_type': 'unknown', 'value': text, 'resolution': 'missing', 'source': 'known_web_target'}
    if _web_search_term(text):
        return {'target_type': 'unknown', 'value': text, 'resolution': 'missing', 'source': 'web_search_request'}

    explicit_path = _extract_explicit_local_path(text) or _extract_explicit_local_path(clean_text)
    if explicit_path and not _looks_like_app_path(explicit_path):
        return {'target_type': 'unknown', 'value': explicit_path, 'resolution': 'missing', 'source': 'explicit_path_non_app'}
    if Path(text).exists() and _looks_like_app_path(text):
        return {'target_type': 'app', 'value': text, 'label': Path(text).stem, 'resolution': 'resolved', 'source': 'direct_path'}
    if Path(clean_text).exists() and _looks_like_app_path(clean_text):
        return {'target_type': 'app', 'value': clean_text, 'label': Path(clean_text).stem, 'resolution': 'resolved', 'source': 'direct_path'}

    norm_variants = [_normalize(v) for v in _pinyin_expand(clean_text)]

    windows = discover_windows()
    for item in windows:
        win_norm = _normalize(item.get('title', ''))
        if any(v and v in win_norm for v in norm_variants):
            return {'target_type': 'window', 'value': item.get('title'), 'resolution': 'resolved', 'source': 'window'}

    shortcuts = discover_shortcuts_fast()
    best_shortcut = _match_best_shortcut(shortcuts, norm_variants)
    if not best_shortcut:
        shortcuts = discover_shortcuts()
        best_shortcut = _match_best_shortcut(shortcuts, norm_variants)
    if best_shortcut:
        lnk_path = best_shortcut.get('path', '')
        exe_path = resolve_lnk_target(lnk_path) if lnk_path.lower().endswith('.lnk') else lnk_path
        return {
            'target_type': 'app',
            'value': exe_path or lnk_path,
            'label': best_shortcut.get('label'),
            'resolution': 'resolved',
            'source': 'shortcut',
        }

    fast_path = _find_local_app_path_fast(clean_text)
    if fast_path:
        return {
            'target_type': 'app',
            'value': fast_path,
            'label': Path(fast_path).stem,
            'resolution': 'resolved',
            'source': 'installed_exe_fast',
        }
    installed = discover_installed_apps()
    best_exe = _match_best(installed, norm_variants, match_fields=['label', 'dir_label', 'path'])
    if best_exe:
        return {
            'target_type': 'app',
            'value': best_exe.get('path'),
            'label': best_exe.get('dir_label') or best_exe.get('label'),
            'resolution': 'resolved',
            'source': 'installed_exe',
        }

    return {'target_type': 'unknown', 'value': text, 'resolution': 'missing', 'source': 'local_app_unresolved'}


def resolve_target_reference(raw: str, context: dict | None = None) -> dict:
    text = str(raw or '').strip()
    context = context if isinstance(context, dict) else {}
    export_state = load_export_state()
    known_web_target = _resolve_known_web_target(text)
    web_search_term = _web_search_term(text)

    # ── 0. 已有结构化目标（context 里已解析好的）──
    fs_action = context.get('fs_action') if isinstance(context.get('fs_action'), dict) else {}
    target = fs_action.get('target') if isinstance(fs_action.get('target'), dict) else {}
    if target:
        if target.get('url'):
            return {'target_type': 'url', 'value': str(target.get('url')), 'resolution': 'resolved', 'source': 'fs_action'}
        if target.get('path'):
            return {'target_type': 'path', 'value': str(target.get('path')), 'resolution': 'resolved', 'source': 'fs_action'}
        if target.get('window'):
            return {'target_type': 'window', 'value': str(target.get('window')), 'resolution': 'resolved', 'source': 'fs_action'}
        if target.get('app'):
            return {'target_type': 'app', 'value': str(target.get('app')), 'label': str(target.get('app')), 'resolution': 'resolved', 'source': 'fs_action'}

    # ── 1. 显式 URL ──
    if text.startswith('http://') or text.startswith('https://'):
        return {'target_type': 'url', 'value': text, 'resolution': 'resolved', 'source': 'direct_url'}
    if re.match(r'^[\w.-]+\.[A-Za-z]{2,}(/.*)?$', text):
        return {'target_type': 'url', 'value': text, 'resolution': 'partial', 'source': 'url_without_scheme'}

    explicit_path = _extract_explicit_local_path(text)
    if explicit_path:
        path_obj = Path(explicit_path)
        return {
            'target_type': 'path',
            'value': explicit_path,
            'resolution': 'resolved' if path_obj.exists() else 'partial',
            'source': 'direct_path',
        }

    # ── 2. 已有 path 上下文 ──
    if known_web_target:
        return known_web_target

    path = str((context.get('fs_action') or {}).get('target', {}).get('path') or '').strip() if isinstance((context.get('fs_action') or {}).get('target'), dict) else ''
    if path:
        return {'target_type': 'path', 'value': path, 'resolution': 'resolved', 'source': 'fs_action'}

    # ── 3. 导出状态续接 ──
    if any(w in text for w in ('打开保存位置', '打开保存目录')) and export_state.get('last_export_dir'):
        return {'target_type': 'path', 'value': str(export_state.get('last_export_dir')), 'resolution': 'resolved', 'source': 'export_state'}
    if any(w in text for w in ('打开刚才那个结果', '打开刚才保存的文件', '打开刚才导出的文件')) and export_state.get('last_export_path'):
        return {'target_type': 'path', 'value': str(export_state.get('last_export_path')), 'resolution': 'resolved', 'source': 'export_state'}

    # ── 4. 已打开的窗口匹配（快速，不涉及文件扫描）──
    norm = _normalize(text)
    norm_variants = [_normalize(v) for v in _pinyin_expand(text)]
    windows = discover_windows()
    for item in windows:
        win_norm = _normalize(item.get('title', ''))
        if any(v and v in win_norm for v in norm_variants):
            return {'target_type': 'window', 'value': item.get('title'), 'resolution': 'resolved', 'source': 'window'}

    # ── 5. LLM 理解层：判断目标类型（app/url/file）──
    llm_result = _llm_resolve_target(text)
    if llm_result:
        # 如果 LLM 说是本地 app，帮它找到 exe 路径
        if llm_result.get('target_type') == 'app':
            app_label = llm_result.get('label') or llm_result.get('value') or ''
            exe_path = _find_local_app_path(app_label)
            if exe_path:
                llm_result['value'] = exe_path
                llm_result['resolution'] = 'resolved'
        return llm_result

    if web_search_term or _looks_like_web_request(text):
        return {'target_type': 'unknown', 'value': text, 'resolution': 'missing', 'source': 'web_request_unresolved'}

    # ── 6. 纯本地兜底（LLM 不可用时）──
    installed = discover_installed_apps()
    best_exe = _match_best(installed, norm_variants, match_fields=['label', 'dir_label', 'path'])
    if best_exe:
        return {'target_type': 'app', 'value': best_exe.get('path'), 'label': best_exe.get('dir_label') or best_exe.get('label'), 'resolution': 'resolved', 'source': 'installed_exe'}

    shortcuts = discover_shortcuts()
    best = _match_best_shortcut(shortcuts, norm_variants)
    if best:
        lnk_path = best.get('path', '')
        exe_path = resolve_lnk_target(lnk_path) if lnk_path.lower().endswith('.lnk') else lnk_path
        return {'target_type': 'app', 'value': exe_path or lnk_path, 'label': best.get('label'), 'resolution': 'resolved', 'source': 'shortcut'}

    return {'target_type': 'unknown', 'value': text, 'resolution': 'missing', 'source': 'unresolved'}


def _find_local_app_path(label: str) -> str:
    """根据 LLM 给出的 app 名称，在本地找到对应的 exe 路径"""
    if not label:
        return ''
    fast_path = _find_local_app_path_fast(label)
    if fast_path:
        return fast_path
    norm_variants = [_normalize(v) for v in _pinyin_expand(_strip_action_words(label))]
    shortcuts = discover_shortcuts_fast()
    best_sc = _match_best_shortcut(shortcuts, norm_variants)
    if not best_sc:
        shortcuts = discover_shortcuts()
        best_sc = _match_best_shortcut(shortcuts, norm_variants)
    if best_sc:
        lnk_path = best_sc.get('path', '')
        return resolve_lnk_target(lnk_path) if lnk_path.lower().endswith('.lnk') else lnk_path
    installed = discover_installed_apps()
    best = _match_best(installed, norm_variants, match_fields=['label', 'dir_label', 'path'])
    if best:
        return best.get('path', '')
    return ''


def _match_best(items: list[dict], norm_variants: list[str], match_fields: list[str] = None) -> dict | None:
    """通用模糊匹配：在 items 中找最佳匹配"""
    best = None
    best_score = 0
    for item in items:
        score = 0
        for field in (match_fields or ['label']):
            field_norm = _normalize(item.get(field, ''))
            if not field_norm:
                continue
            for v in norm_variants:
                if not v:
                    continue
                if v == field_norm:
                    score = max(score, 100)
                elif v in field_norm:
                    score = max(score, 70)
                elif field_norm in v:
                    score = max(score, 50)
        if score > best_score:
            best = item
            best_score = score
    return best


def _match_best_shortcut(shortcuts: list[dict], norm_variants: list[str]) -> dict | None:
    """快捷方式匹配"""
    best = None
    best_score = 0
    for item in shortcuts:
        label = _normalize(item.get('label', ''))
        if not label:
            continue
        score = 0
        for v in norm_variants:
            if not v:
                continue
            if v == label:
                score = max(score, 100)
            elif v in label:
                score = max(score, 70)
            elif label in v:
                score = max(score, 50)
        if score > best_score:
            best = item
            best_score = score
    return best
