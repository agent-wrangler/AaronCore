"""独立进程执行 QQ 发消息"""
import sys
import os
import json
import time

sys.stdout.reconfigure(encoding='utf-8')

group_name = sys.argv[1]
message = sys.argv[2]

import pyautogui
import pygetwindow as gw
import pyperclip
from pywinauto import Application

try:
    # 1. 激活 QQ
    qq_wins = [w for w in gw.getAllWindows() if w.title.strip() == 'QQ']
    if not qq_wins:
        print(json.dumps({"ok": False, "error": "没找到 QQ 窗口"}, ensure_ascii=False))
        sys.exit(0)
    qq_wins[0].activate()
    time.sleep(0.5)

    # 2. 读会话列表精确匹配
    app = Application(backend='uia').connect(title='QQ')
    main_win = app.window(title='QQ')
    session = main_win.child_window(title='会话列表', control_type='Window')

    sr = session.rectangle()
    pyautogui.click((sr.left + sr.right) // 2, (sr.top + sr.bottom) // 2)
    time.sleep(0.2)
    pyautogui.hotkey('ctrl', 'Home')
    time.sleep(0.5)

    target = None
    for _ in range(10):
        for item in session.children():
            try:
                children = item.children()
                if children:
                    name = children[0].window_text().strip()
                    if name == group_name:
                        rect = item.rectangle()
                        if rect.top > 0:
                            target = item
                            break
            except:
                continue
        if target:
            break
        pyautogui.scroll(-5, x=(sr.left + sr.right) // 2, y=(sr.top + sr.bottom) // 2)
        time.sleep(0.3)

    if not target:
        print(json.dumps({"ok": False, "error": f"会话列表中没找到「{group_name}」"}, ensure_ascii=False))
        sys.exit(0)

    # 3. 点击群聊
    rect = target.rectangle()
    pyautogui.click((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
    time.sleep(1.5)

    # 4. 找群聊窗口，发送消息
    chat_win = None
    for w in gw.getAllWindows():
        if '会话' in w.title:
            chat_win = w
            break
    if not chat_win:
        print(json.dumps({"ok": False, "error": f"打开群「{group_name}」失败"}, ensure_ascii=False))
        sys.exit(0)

    chat_win.activate()
    time.sleep(0.3)
    pyautogui.click(chat_win.left + chat_win.width // 2, chat_win.top + chat_win.height - 80)
    time.sleep(0.3)
    pyperclip.copy(message)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.3)
    pyautogui.press('enter')
    time.sleep(0.5)

    print(json.dumps({"ok": True, "result": f"已在「{group_name}」发送：{message}"}, ensure_ascii=False))

except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
