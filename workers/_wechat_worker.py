"""独立进程执行微信发消息。"""
import json
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

chat_name = sys.argv[1] if len(sys.argv) > 1 else ""
message = sys.argv[2] if len(sys.argv) > 2 else ""

import pyautogui
import pygetwindow as gw
import pyperclip


def _find_wechat_window():
    for w in gw.getAllWindows():
        title = (w.title or "").strip()
        if not title or "卸载微信" in title:
            continue
        if title == "微信" or title == "WeChat" or "微信" in title or "WeChat" in title:
            if w.width > 300 and w.height > 300:
                return w
    return None


def _open_chat(chat_name):
    win = _find_wechat_window()
    if not win:
        return None, "没找到微信窗口，请确认微信已登录"
    try:
        if win.isMinimized:
            win.restore()
            time.sleep(0.2)
        win.activate()
    except Exception:
        return None, "激活微信失败"
    time.sleep(0.4)

    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.2)
    pyperclip.copy(chat_name)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.4)
    pyautogui.press("enter")
    time.sleep(1.0)

    pyautogui.click(int(win.left + min(max(win.width * 0.22, 130), 260)), int(win.top + 48))
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "a")
    pyperclip.copy(chat_name)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.4)
    pyautogui.press("enter")
    time.sleep(1.0)
    return win, ""


try:
    if not chat_name:
        print(json.dumps({"ok": False, "error": "缺少微信聊天名"}, ensure_ascii=False))
        sys.exit(0)
    if not message:
        print(json.dumps({"ok": False, "error": "缺少要发送的消息"}, ensure_ascii=False))
        sys.exit(0)

    win, err = _open_chat(chat_name)
    if not win:
        print(json.dumps({"ok": False, "error": err}, ensure_ascii=False))
        sys.exit(0)

    win.activate()
    time.sleep(0.3)
    pyautogui.click(win.left + win.width // 2, win.top + win.height - 70)
    time.sleep(0.2)
    pyperclip.copy(message)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.4)

    print(json.dumps({"ok": True, "result": f"已在微信「{chat_name}」发送：{message}"}, ensure_ascii=False))
except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))

