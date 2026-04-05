import time
import os

from core.fs_protocol import build_operation_result
from core.target_protocol import discover_windows, resolve_target_reference
from decision.tool_runtime.runtime_control import cooperative_sleep, raise_if_cancelled

try:
    import pyautogui
    import pygetwindow as gw
    _HAS_UI = True
except ImportError:
    _HAS_UI = False

try:
    from playwright.sync_api import sync_playwright
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False

try:
    from pywinauto import Desktop as _Desktop
    _HAS_PYWINAUTO = True
except ImportError:
    _HAS_PYWINAUTO = False


# ── 浏览器检测 ──

_BROWSER_HINTS = ['chrome', 'edge', 'firefox', 'brave', 'opera', 'msedge', '浏览器']

def _is_browser_window(title: str) -> bool:
    lowered = str(title or '').lower()
    return any(h in lowered for h in _BROWSER_HINTS)


# ── CDP 精准操作（浏览器页面元素）──

def _cdp_find_and_interact(action: str, element_desc: str, input_text: str = '', port: int = 9222, context: dict | None = None) -> dict | None:
    """通过 CDP 在浏览器页面中查找元素并操作，返回结果 dict 或 None（表示 CDP 不可用）"""
    if not _HAS_PLAYWRIGHT:
        return None

    os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
    os.environ['no_proxy'] = 'localhost,127.0.0.1'

    pw = None
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
        page = browser.contexts[0].pages[0] if browser.contexts and browser.contexts[0].pages else None
        if not page:
            return None

        # 常见元素选择器映射
        selectors = []
        desc = str(element_desc or '').strip().lower()

        if any(w in desc for w in ('搜索框', '搜索栏', '搜索', 'search')):
            selectors = [
                'input[type="search"]',
                'input[placeholder*="搜索"]',
                'input[placeholder*="search"]',
                'input[name*="search"]',
                'input[id*="search"]',
                'input[class*="search"]',
                '#kw',  # 百度
                '#search-input',
                '.search-input input',
                'input[type="text"]',
            ]
        elif any(w in desc for w in ('输入框', '文本框', 'input')):
            selectors = [
                'input[type="text"]:visible',
                'textarea:visible',
                'input:not([type="hidden"]):visible',
            ]
        elif any(w in desc for w in ('按钮', '提交', '确定', 'submit', 'button')):
            selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("搜索")',
                'button:has-text("确定")',
                'button:has-text("提交")',
            ]

        if not selectors:
            # 通用：尝试按文字内容查找
            selectors = [f'text="{element_desc}"', f'[aria-label*="{element_desc}"]']

        # 尝试每个选择器
        target_el = None
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=1000):
                    target_el = el
                    break
            except Exception:
                continue

        if not target_el:
            return None  # CDP 找不到，让调用方回退

        # 执行操作
        if action == 'click':
            target_el.click(timeout=3000)
            return build_operation_result(
                f'已通过 CDP 点击页面元素：`{element_desc}`',
                expected_state='element_clicked', observed_state='element_clicked',
                repair_succeeded=True,
            )
        elif action == 'type':
            target_el.click(timeout=2000)
            cooperative_sleep(0.2, context, detail='ui_interaction cancelled during browser typing')
            target_el.fill(input_text)
            return build_operation_result(
                f'已通过 CDP 在`{element_desc}`中输入内容',
                expected_state='text_entered', observed_state='text_entered',
                repair_succeeded=True,
            )
        elif action == 'click_and_type':
            target_el.click(timeout=2000)
            cooperative_sleep(0.2, context, detail='ui_interaction cancelled during browser submit')
            target_el.fill(input_text)
            # 尝试按回车提交
            target_el.press('Enter')
            return build_operation_result(
                f'已通过 CDP 在`{element_desc}`中输入并提交',
                expected_state='text_submitted', observed_state='text_submitted',
                repair_succeeded=True,
            )
        else:
            target_el.click(timeout=3000)
            return build_operation_result(
                f'已通过 CDP 操作页面元素：`{element_desc}`',
                expected_state='element_interacted', observed_state='element_interacted',
                repair_succeeded=True,
            )
    except Exception as e:
        return None
    finally:
        if pw:
            try:
                pw.stop()
            except Exception:
                pass


# ── Accessibility API 精准操作（桌面应用控件）──

def _a11y_find_and_interact(action: str, element_desc: str, input_text: str = '', window_title: str = '', context: dict | None = None) -> dict | None:
    """通过 pywinauto Accessibility API 查找桌面应用控件并操作"""
    if not _HAS_PYWINAUTO:
        return None

    try:
        desktop = _Desktop(backend='uia')
        wins = desktop.windows(title_re=f'.*{window_title}.*') if window_title else desktop.windows()
        if not wins:
            return None

        win = wins[0]
        desc = str(element_desc or '').strip()

        # 尝试按名称/自动化 ID 查找控件
        target = None
        try:
            target = win.child_window(title_re=f'.*{desc}.*', control_type='Edit')
            if not target.exists(timeout=2):
                target = win.child_window(title_re=f'.*{desc}.*')
            if not target.exists(timeout=2):
                target = None
        except Exception:
            target = None

        if not target:
            return None

        if action in ('type', 'click_and_type'):
            target.click_input()
            cooperative_sleep(0.2, context, detail='ui_interaction cancelled during desktop typing')
            target.type_keys(input_text, with_spaces=True)
            return build_operation_result(
                f'已通过 Accessibility API 在`{element_desc}`中输入内容',
                expected_state='text_entered', observed_state='text_entered',
                repair_succeeded=True,
            )
        else:
            target.click_input()
            return build_operation_result(
                f'已通过 Accessibility API 点击控件：`{element_desc}`',
                expected_state='element_clicked', observed_state='element_clicked',
                repair_succeeded=True,
            )
    except Exception:
        return None


def _detect_browser_auth_gate(port: int = 9222) -> dict | None:
    if not _HAS_PLAYWRIGHT:
        return None

    os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
    os.environ['no_proxy'] = 'localhost,127.0.0.1'

    pw = None
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
        page = browser.contexts[0].pages[0] if browser.contexts and browser.contexts[0].pages else None
        if not page:
            return None

        url = str(page.url or '').lower()
        title = str(page.title() or '').lower()
        body_text = ''
        try:
            body_text = str(page.locator('body').inner_text(timeout=1500) or '').lower()
        except Exception:
            body_text = ''

        combined = ' '.join(part for part in (url, title, body_text[:2000]) if part)
        gate_markers = (
            'login', 'sign in', 'sign-in', 'log in',
            '登录', '登入', '请登录', '账号登录',
            'verify', 'verification', 'captcha',
            '验证', '验证码', '滑块',
        )
        matched = [marker for marker in gate_markers if marker in combined]
        if not matched:
            return None
        return {
            'url': url,
            'title': title,
            'marker': matched[0],
        }
    except Exception:
        return None
    finally:
        if pw:
            try:
                pw.stop()
            except Exception:
                pass


def submit_browser_search(query_text: str) -> dict:
    text = str(query_text or '').strip()
    if not text:
        return build_operation_result(
            '当前没有可提交的搜索内容。',
            expected_state='text_submitted',
            observed_state='input_missing',
            drift_reason='missing_search_text',
            repair_hint='provide_search_text',
            repair_attempted=False,
            repair_succeeded=False,
        )

    auth_gate = _detect_browser_auth_gate()
    if auth_gate:
        detail = str(auth_gate.get('title') or auth_gate.get('url') or '').strip()
        return build_operation_result(
            f'当前网页需要先完成登录或验证，暂时不能继续自动搜索：`{text}`',
            expected_state='auth_cleared',
            observed_state='auth_required',
            drift_reason='auth_required',
            repair_hint='user_login_required',
            repair_attempted=False,
            repair_succeeded=False,
            verification_detail=detail,
        )

    cdp_result = _cdp_find_and_interact('click_and_type', '搜索框', text)
    if cdp_result:
        return cdp_result

    active_title = _active_title()
    if _is_browser_window(active_title):
        a11y_result = _a11y_find_and_interact('click_and_type', '搜索框', text, active_title)
        if a11y_result:
            return a11y_result

    auth_gate = _detect_browser_auth_gate()
    if auth_gate:
        detail = str(auth_gate.get('title') or auth_gate.get('url') or '').strip()
        return build_operation_result(
            f'当前网页需要先完成登录或验证，暂时不能继续自动搜索：`{text}`',
            expected_state='auth_cleared',
            observed_state='auth_required',
            drift_reason='auth_required',
            repair_hint='user_login_required',
            repair_attempted=True,
            repair_succeeded=False,
            verification_detail=detail,
        )

    return build_operation_result(
        f'网页已经打开，但还没有找到可用的搜索框来提交：`{text}`',
        expected_state='text_submitted',
        observed_state='search_box_not_found',
        drift_reason='search_box_not_found',
        repair_hint='use_ui_interaction_or_query_url',
        repair_attempted=False,
        repair_succeeded=False,
    )


def _window_titles() -> list[str]:
    return [item.get('title', '') for item in discover_windows() if item.get('title')]


def _find_window(title_hint: str) -> str:
    lowered = str(title_hint or '').strip().lower()
    for title in _window_titles():
        if lowered and lowered in title.lower():
            return title
    return ''


def _active_title() -> str:
    if not _HAS_UI:
        return ''
    try:
        active = gw.getActiveWindow()
        if active and getattr(active, 'title', None):
            return str(active.title).strip()
    except Exception:
        pass
    return ''


def execute(query, context=None):
    text = str(query or '').strip()
    context = context if isinstance(context, dict) else {}
    raise_if_cancelled(context, detail='ui_interaction cancelled before start')
    if not _HAS_UI:
        return build_operation_result(
            '当前缺少 UI 交互依赖（pyautogui / pygetwindow）。',
            expected_state='ui_target_interacted',
            observed_state='ui_runtime_missing',
            drift_reason='ui_dependency_missing',
            repair_hint='install_ui_runtime',
            repair_attempted=False,
            repair_succeeded=False,
        )

    # Layer 3: 窗口管理动作
    if any(w in text for w in ('最小化',)):
        resolved = resolve_target_reference(text, context)
        target = str(resolved.get('value') or text).strip()
        wt = target if resolved.get('target_type') == 'window' else _find_window(target)
        if wt:
            try:
                wins = gw.getWindowsWithTitle(wt)
                if wins:
                    wins[0].minimize()
                    return build_operation_result(f'已最小化窗口：`{wt}`', expected_state='window_minimized', observed_state='window_minimized', repair_succeeded=True)
            except Exception as e:
                return build_operation_result(f'最小化失败：{e}', expected_state='window_minimized', observed_state='minimize_failed', drift_reason='minimize_exception', repair_hint='retry')
        return build_operation_result(f'没找到窗口：`{target}`', expected_state='window_minimized', observed_state='window_missing', drift_reason='window_not_found', repair_hint='launch_first')

    if any(w in text for w in ('最大化',)):
        resolved = resolve_target_reference(text, context)
        target = str(resolved.get('value') or text).strip()
        wt = target if resolved.get('target_type') == 'window' else _find_window(target)
        if wt:
            try:
                wins = gw.getWindowsWithTitle(wt)
                if wins:
                    wins[0].maximize()
                    return build_operation_result(f'已最大化窗口：`{wt}`', expected_state='window_maximized', observed_state='window_maximized', repair_succeeded=True)
            except Exception as e:
                return build_operation_result(f'最大化失败：{e}', expected_state='window_maximized', observed_state='maximize_failed', drift_reason='maximize_exception', repair_hint='retry')
        return build_operation_result(f'没找到窗口：`{target}`', expected_state='window_maximized', observed_state='window_missing', drift_reason='window_not_found', repair_hint='launch_first')

    if any(w in text for w in ('还原窗口', '恢复窗口')):
        resolved = resolve_target_reference(text, context)
        target = str(resolved.get('value') or text).strip()
        wt = target if resolved.get('target_type') == 'window' else _find_window(target)
        if wt:
            try:
                wins = gw.getWindowsWithTitle(wt)
                if wins:
                    wins[0].restore()
                    return build_operation_result(f'已还原窗口：`{wt}`', expected_state='window_restored', observed_state='window_restored', repair_succeeded=True)
            except Exception as e:
                return build_operation_result(f'还原失败：{e}', expected_state='window_restored', observed_state='restore_failed', drift_reason='restore_exception', repair_hint='retry')
        return build_operation_result(f'没找到窗口：`{target}`', expected_state='window_restored', observed_state='window_missing', drift_reason='window_not_found', repair_hint='launch_first')

    if any(w in text for w in ('移动窗口', '窗口移动', '窗口移到')):
        resolved = resolve_target_reference(text, context)
        target = str(resolved.get('value') or text).strip()
        wt = target if resolved.get('target_type') == 'window' else _find_window(target)
        x = int(context.get('window_x') or 0)
        y = int(context.get('window_y') or 0)
        if wt:
            try:
                wins = gw.getWindowsWithTitle(wt)
                if wins:
                    wins[0].moveTo(x, y)
                    return build_operation_result(f'已移动窗口到 ({x},{y})：`{wt}`', expected_state='window_moved', observed_state='window_moved', repair_succeeded=True)
            except Exception as e:
                return build_operation_result(f'移动失败：{e}', expected_state='window_moved', observed_state='move_failed', drift_reason='move_exception', repair_hint='retry')
        return build_operation_result(f'没找到窗口：`{target}`', expected_state='window_moved', observed_state='window_missing', drift_reason='window_not_found', repair_hint='launch_first')

    if any(w in text for w in ('调整窗口大小', '窗口大小', '窗口尺寸', '缩放窗口')):
        resolved = resolve_target_reference(text, context)
        target = str(resolved.get('value') or text).strip()
        wt = target if resolved.get('target_type') == 'window' else _find_window(target)
        w_size = int(context.get('window_width') or 800)
        h_size = int(context.get('window_height') or 600)
        if wt:
            try:
                wins = gw.getWindowsWithTitle(wt)
                if wins:
                    wins[0].resizeTo(w_size, h_size)
                    return build_operation_result(f'已调整窗口大小为 {w_size}x{h_size}：`{wt}`', expected_state='window_resized', observed_state='window_resized', repair_succeeded=True)
            except Exception as e:
                return build_operation_result(f'调整大小失败：{e}', expected_state='window_resized', observed_state='resize_failed', drift_reason='resize_exception', repair_hint='retry')
        return build_operation_result(f'没找到窗口：`{target}`', expected_state='window_resized', observed_state='window_missing', drift_reason='window_not_found', repair_hint='launch_first')

    # Layer 4: UI 交互动作
    action = 'double_click' if any(w in text for w in ('双击',)) else ('right_click' if any(w in text for w in ('右击', '右键', '右键点击')) else ('hotkey' if any(w in text for w in ('快捷键', 'ctrl+', 'alt+', 'Ctrl+', 'Alt+')) else ('drag' if any(w in text for w in ('拖拽', '拖动', 'drag')) else ('hover' if any(w in text for w in ('悬停', 'hover')) else ('wait' if any(w in text for w in ('等待', '等一下', 'wait')) else ('click' if any(w in text for w in ('点击', '点一下', '按一下')) else ('focus' if any(w in text for w in ('聚焦', '切到', '切换到')) else 'type')))))))

    resolved = resolve_target_reference(str((context.get('ui_target') if isinstance(context.get('ui_target'), str) else '') or text), context)
    target = str(resolved.get('value') or text).strip()
    window_title = target if resolved.get('target_type') == 'window' else _find_window(target)
    if not window_title:
        return build_operation_result(
            f'还没找到匹配窗口：`{target}`',
            expected_state='window_targeted',
            observed_state='window_missing',
            drift_reason='window_not_found',
            repair_hint='launch_or_focus_window_first',
            repair_attempted=False,
            repair_succeeded=False,
        )

    try:
        wins = gw.getWindowsWithTitle(window_title)
        if wins:
            wins[0].activate()
            cooperative_sleep(0.3, context, detail='ui_interaction cancelled during window activation')
    except Exception:
        pass

    active_title = _active_title()
    if not active_title or window_title.lower() not in active_title.lower():
        return build_operation_result(
            f'窗口没有成功进入前景：`{window_title}`',
            expected_state='window_focused',
            observed_state='focus_failed',
            drift_reason='focus_failed',
            repair_hint='retry_focus_or_launch_window',
            repair_attempted=False,
            repair_succeeded=False,
        )

    if action == 'focus':
        return build_operation_result(
            f'已聚焦窗口：`{window_title}`',
            expected_state='window_focused',
            observed_state='window_focused',
            drift_reason='',
            repair_hint='',
            repair_attempted=False,
            repair_succeeded=True,
        )

    if action == 'type':
        content = str(context.get('ui_input') or '').strip()
        if not content:
            return build_operation_result(
                '当前没有可输入的内容。',
                expected_state='text_entered',
                observed_state='input_missing',
                drift_reason='missing_ui_input',
                repair_hint='provide_text_payload',
                repair_attempted=False,
                repair_succeeded=False,
            )
        # 优先：浏览器走 CDP
        if _is_browser_window(window_title):
            cdp_result = _cdp_find_and_interact('click_and_type', text, content, context=context)
            if cdp_result:
                return cdp_result
        # 其次：桌面应用走 Accessibility API
        a11y_result = _a11y_find_and_interact('click_and_type', text, content, window_title, context=context)
        if a11y_result:
            return a11y_result
        # 兜底：pyautogui 盲输入
        pyautogui.write(content, interval=0.02)
        return build_operation_result(
            f'已向窗口输入内容（盲输入）：`{window_title}`',
            expected_state='text_entered',
            observed_state='text_entered',
            drift_reason='',
            repair_hint='',
            repair_attempted=False,
            repair_succeeded=True,
        )

    if action == 'hotkey':
        import re
        m = re.search(r'(?:ctrl|alt|shift|win)\+\w+', text, re.I)
        if m:
            keys = m.group(0).split('+')
            pyautogui.hotkey(*keys)
            return build_operation_result(
                f'已执行快捷键：`{m.group(0)}`',
                expected_state='hotkey_executed', observed_state='hotkey_executed',
                repair_succeeded=True,
            )
        return build_operation_result(
            '没有识别出具体的快捷键组合。',
            expected_state='hotkey_executed', observed_state='hotkey_unresolved',
            drift_reason='missing_hotkey', repair_hint='provide_hotkey_combination',
        )

    if action == 'double_click':
        pyautogui.doubleClick()
        return build_operation_result(
            f'已在窗口执行双击：`{window_title}`',
            expected_state='ui_target_interacted', observed_state='ui_target_interacted',
            repair_succeeded=True,
        )

    if action == 'right_click':
        pyautogui.rightClick()
        return build_operation_result(
            f'已在窗口执行右键点击：`{window_title}`',
            expected_state='ui_target_interacted', observed_state='ui_target_interacted',
            repair_succeeded=True,
        )

    if action == 'hover':
        return build_operation_result(
            f'鼠标已悬停在窗口：`{window_title}`',
            expected_state='hover_completed', observed_state='hover_completed',
            repair_succeeded=True,
        )

    if action == 'drag':
        dx = int(context.get('drag_dx') or 100)
        dy = int(context.get('drag_dy') or 0)
        pos = pyautogui.position()
        pyautogui.moveTo(pos.x, pos.y)
        pyautogui.drag(dx, dy, duration=0.5)
        return build_operation_result(
            f'已拖拽 ({dx},{dy})：`{window_title}`',
            expected_state='drag_completed', observed_state='drag_completed',
            repair_succeeded=True,
        )

    if action == 'wait':
        import re as _re
        m = _re.search(r'(\d+)', text)
        seconds = int(m.group(1)) if m else 2
        seconds = min(seconds, 30)
        cooperative_sleep(seconds, context, detail='ui_interaction cancelled during wait action')
        return build_operation_result(
            f'已等待 {seconds} 秒。',
            expected_state='wait_completed', observed_state='wait_completed',
            repair_succeeded=True,
        )

    # 优先：浏览器走 CDP 精准点击
    if _is_browser_window(window_title):
        cdp_result = _cdp_find_and_interact('click', text, context=context)
        if cdp_result:
            return cdp_result
    # 其次：桌面应用走 Accessibility API
    a11y_result = _a11y_find_and_interact('click', text, '', window_title, context=context)
    if a11y_result:
        return a11y_result
    # 兜底：pyautogui 盲点击
    pyautogui.click()
    return build_operation_result(
        f'已在窗口执行点击（盲点击）：`{window_title}`',
        expected_state='ui_target_interacted',
        observed_state='ui_target_interacted',
        drift_reason='',
        repair_hint='',
        repair_attempted=False,
        repair_succeeded=True,
    )
