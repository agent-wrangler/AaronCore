import io
import time
from datetime import datetime
from pathlib import Path

try:
    import pyautogui
    import pygetwindow as gw
    from PIL import Image
    _HAS_SCREEN = True
except ImportError:
    _HAS_SCREEN = False

from core.fs_protocol import build_operation_result, record_saved_artifact

SCREENSHOT_DIR = Path.home() / 'Desktop' / 'Nova截图'


def capture_full_screen() -> dict:
    if not _HAS_SCREEN:
        return build_operation_result(
            '缺少截图依赖（pyautogui / PIL）。',
            expected_state='screenshot_captured',
            observed_state='runtime_missing',
            drift_reason='screenshot_dependency_missing',
            repair_hint='install_pyautogui_and_pillow',
        )
    img = pyautogui.screenshot()
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    path = SCREENSHOT_DIR / f'{ts}_fullscreen.png'
    img.save(str(path))
    record_saved_artifact(str(path), 'png')
    return build_operation_result(
        f'已截取全屏截图，保存到：`{path.name}`',
        expected_state='screenshot_captured',
        observed_state='screenshot_saved',
        repair_succeeded=True,
        image_url=f'/screenshots/{path.name}',
    )


def capture_window(title_hint: str = '') -> dict:
    if not _HAS_SCREEN:
        return build_operation_result(
            '缺少截图依赖。',
            expected_state='window_screenshot_captured',
            observed_state='runtime_missing',
            drift_reason='screenshot_dependency_missing',
            repair_hint='install_pyautogui_and_pillow',
        )
    target_title = ''
    if title_hint:
        lowered = str(title_hint).strip().lower()
        for w in gw.getAllWindows():
            if w.title.strip() and lowered in w.title.lower():
                target_title = w.title
                break
    if not target_title:
        try:
            active = gw.getActiveWindow()
            if active and getattr(active, 'title', None):
                target_title = active.title
        except Exception:
            pass
    if not target_title:
        return capture_full_screen()

    try:
        wins = gw.getWindowsWithTitle(target_title)
        if not wins:
            return capture_full_screen()
        win = wins[0]
        win.activate()
        time.sleep(0.3)
        left, top, width, height = win.left, win.top, win.width, win.height
        if width <= 0 or height <= 0:
            return capture_full_screen()
        img = pyautogui.screenshot(region=(left, top, width, height))
    except Exception:
        img = pyautogui.screenshot()

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    safe_name = ''.join(c if c.isalnum() or c in ' _-' else '_' for c in target_title)[:30].strip() or 'window'
    path = SCREENSHOT_DIR / f'{ts}_{safe_name}.png'
    img.save(str(path))
    record_saved_artifact(str(path), 'png')
    return build_operation_result(
        f'已截取窗口：`{target_title}`',
        expected_state='window_screenshot_captured',
        observed_state='window_screenshot_saved',
        repair_succeeded=True,
        image_url=f'/screenshots/{path.name}',
    )


def capture_region(x: int, y: int, w: int, h: int) -> dict:
    if not _HAS_SCREEN:
        return build_operation_result(
            '缺少截图依赖。',
            expected_state='region_screenshot_captured',
            observed_state='runtime_missing',
            drift_reason='screenshot_dependency_missing',
            repair_hint='install_pyautogui_and_pillow',
        )
    if w <= 0 or h <= 0:
        return build_operation_result(
            '截图区域无效。',
            expected_state='region_screenshot_captured',
            observed_state='invalid_region',
            drift_reason='invalid_region',
            repair_hint='provide_valid_region',
        )
    img = pyautogui.screenshot(region=(x, y, w, h))
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    path = SCREENSHOT_DIR / f'{ts}_region_{x}_{y}_{w}_{h}.png'
    img.save(str(path))
    record_saved_artifact(str(path), 'png')
    return build_operation_result(
        f'已截取区域 ({x},{y},{w},{h})',
        expected_state='region_screenshot_captured',
        observed_state='region_screenshot_saved',
        repair_succeeded=True,
        image_url=f'/screenshots/{path.name}',
    )


def observe_screen() -> dict:
    if not _HAS_SCREEN:
        return build_operation_result(
            '缺少截图依赖。',
            expected_state='screen_observed',
            observed_state='runtime_missing',
            drift_reason='screenshot_dependency_missing',
            repair_hint='install_pyautogui_and_pillow',
        )
    screen_size = pyautogui.size()
    mouse_pos = pyautogui.position()
    try:
        active = gw.getActiveWindow()
        active_title = str(active.title).strip() if active and getattr(active, 'title', None) else ''
    except Exception:
        active_title = ''
    try:
        all_windows = [w.title for w in gw.getAllWindows() if w.title.strip()]
    except Exception:
        all_windows = []
    return build_operation_result(
        f'屏幕分辨率：{screen_size.width}x{screen_size.height}\n'
        f'鼠标位置：({mouse_pos.x}, {mouse_pos.y})\n'
        f'当前活动窗口：{active_title}\n'
        f'已打开窗口数：{len(all_windows)}',
        expected_state='screen_observed',
        observed_state='screen_observed',
        repair_succeeded=True,
    )


def execute(query, context=None):
    text = str(query or '').strip()
    context = context if isinstance(context, dict) else {}

    if any(w in text for w in ('全屏截图', '截全屏', '截屏', 'screenshot')):
        return capture_full_screen()
    if any(w in text for w in ('窗口截图', '截窗口', '截取窗口')):
        hint = text
        for w in ('窗口截图', '截窗口', '截取窗口', '截图', '截取', '的'):
            hint = hint.replace(w, '')
        return capture_window(hint.strip())
    if any(w in text for w in ('屏幕状态', '屏幕信息', '当前屏幕', '观察屏幕')):
        return observe_screen()

    return capture_window(text)
