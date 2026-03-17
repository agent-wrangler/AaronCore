"""打开 QQ 群聊窗口（不发消息）"""
import sys
import json
import time

sys.stdout.reconfigure(encoding='utf-8')

group_name = sys.argv[1]

import pyautogui
import pygetwindow as gw
from pywinauto import Application

try:
    # 激活 QQ
    qq_wins = [w for w in gw.getAllWindows() if w.title.strip() == 'QQ']
    if not qq_wins:
        print(json.dumps({"ok": False, "error": "没找到 QQ 窗口"}, ensure_ascii=False))
        sys.exit(0)
    qq_wins[0].activate()
    time.sleep(0.5)

    # 读会话列表找群
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
                if children and children[0].window_text().strip() == group_name:
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

    # 双击打开群聊
    rect = target.rectangle()
    pyautogui.doubleClick((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
    time.sleep(2)

    # 关掉资料卡
    for w in gw.getAllWindows():
        if '资料卡' in w.title:
            w.activate()
            pyautogui.press('escape')
            time.sleep(0.3)

    # 确认群聊窗口打开了
    chat_win = None
    for w in gw.getAllWindows():
        if w.title.strip() == group_name and w.width > 400:
            chat_win = w
            break
    if not chat_win:
        for w in gw.getAllWindows():
            if '会话' in w.title:
                chat_win = w
                break

    if chat_win:
        print(json.dumps({"ok": True, "title": chat_win.title}, ensure_ascii=False))
    else:
        print(json.dumps({"ok": False, "error": "群聊窗口未打开"}, ensure_ascii=False))

except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
