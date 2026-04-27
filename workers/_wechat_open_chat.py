"""打开微信聊天窗口（不发消息）。"""
import json
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

chat_name = sys.argv[1] if len(sys.argv) > 1 else ""

import pyautogui
import pygetwindow as gw
import pyperclip
from pywinauto import Desktop


def _find_wechat_window():
    for w in gw.getAllWindows():
        title = (w.title or "").strip()
        if not title or "卸载微信" in title:
            continue
        if title == "微信" or title == "WeChat" or "微信" in title or "WeChat" in title:
            if w.width > 300 and w.height > 300:
                return w
    try:
        desktop = Desktop(backend="uia")
        wins = desktop.windows(title_re=".*(微信|WeChat).*")
        for win in wins:
            title = (win.window_text() or "").strip()
            if "卸载微信" in title:
                continue
            win.restore()
            time.sleep(0.2)
            return win
    except Exception:
        pass
    return None


def _activate(win):
    try:
        if getattr(win, "isMinimized", False):
            win.restore()
            time.sleep(0.2)
        win.activate()
    except Exception:
        try:
            win.set_focus()
        except Exception:
            return False
    time.sleep(0.4)
    return True


try:
    if not chat_name:
        print(json.dumps({"ok": False, "error": "缺少微信聊天名"}, ensure_ascii=False))
        sys.exit(0)

    win = _find_wechat_window()
    if not win:
        print(json.dumps({"ok": False, "error": "没找到微信窗口，请确认微信已登录"}, ensure_ascii=False))
        sys.exit(0)
    if not _activate(win):
        print(json.dumps({"ok": False, "error": "激活微信失败"}, ensure_ascii=False))
        sys.exit(0)

    left = getattr(win, "left", None)
    top = getattr(win, "top", None)
    width = getattr(win, "width", None)
    if left is None:
        rect = win.rectangle()
        left, top, width = rect.left, rect.top, rect.right - rect.left

    # WeChat desktop keeps search near the upper-left side bar. Ctrl+F works in
    # most builds; the click fallback covers older layouts.
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.2)
    pyperclip.copy(chat_name)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.4)
    pyautogui.press("enter")
    time.sleep(1.0)

    # Fallback: click the visual search area and repeat.
    pyautogui.click(int(left + min(max(width * 0.22, 130), 260)), int(top + 48))
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "a")
    pyperclip.copy(chat_name)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.4)
    pyautogui.press("enter")
    time.sleep(1.0)

    print(json.dumps({"ok": True, "result": f"已打开微信聊天：{chat_name}"}, ensure_ascii=False))
except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))

