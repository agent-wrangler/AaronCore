"""打开 QQ 群聊窗口（不发消息）"""
import sys
import json
import time

sys.stdout.reconfigure(encoding='utf-8')

group_name = sys.argv[1]

import pyautogui
import pygetwindow as gw
from pywinauto import Application, Desktop

try:
    # 激活 QQ（支持最小化/托盘状态）
    qq_wins = [w for w in gw.getAllWindows() if w.title.strip() == 'QQ']
    if qq_wins:
        w = qq_wins[0]
        if not w.isActive:
            try:
                w.restore()
                time.sleep(0.3)
            except:
                pass
            w.activate()
    else:
        # pygetwindow 找不到时用 pywinauto UIA 兜底（托盘最小化场景）
        try:
            desktop = Desktop(backend='uia')
            uia_wins = desktop.windows(title='QQ')
            if uia_wins:
                uia_wins[0].restore()
                time.sleep(0.3)
                uia_wins[0].set_focus()
            else:
                print(json.dumps({"ok": False, "error": "\u6ca1\u627e\u5230 QQ \u7a97\u53e3\uff0c\u8bf7\u786e\u8ba4 QQ \u5df2\u767b\u5f55"}, ensure_ascii=False))
                sys.exit(0)
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"\u6fc0\u6d3b QQ \u5931\u8d25: {e}"}, ensure_ascii=False))
            sys.exit(0)
    time.sleep(0.5)

    # 读会话列表找群
    app = Application(backend='uia').connect(title='QQ')
    main_win = app.window(title='QQ')
    try:
        session = main_win.child_window(title='会话列表', control_type='Window')
        sr = session.rectangle()
    except Exception as _win_err:
        if 'Error code from Windows: 0' in str(_win_err):
            time.sleep(0.5)
            session = main_win.child_window(title='会话列表', control_type='Window')
            sr = session.rectangle()
        else:
            raise
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

    # 确认群聊窗口打开了（支持折叠窗口，如"AI Agent等2个会话"）
    chat_win = None
    for w in gw.getAllWindows():
        title = w.title.strip()
        if title == group_name and w.width > 400:
            chat_win = w
            break
        if group_name in title and w.width > 400:
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
    err_str = str(e)
    # pywinauto 经典误报：Windows 返回错误码 0（实际是成功）但被当异常抛出
    if 'Error code from Windows: 0' in err_str:
        # 尝试直接检查群聊窗口是否已打开
        try:
            chat_win = None
            for w in gw.getAllWindows():
                title = w.title.strip()
                if title == group_name and w.width > 400:
                    chat_win = w
                    break
                if group_name in title and w.width > 400:
                    chat_win = w
                    break
            if not chat_win:
                for w in gw.getAllWindows():
                    if '\u4f1a\u8bdd' in w.title:
                        chat_win = w
                        break
            if chat_win:
                print(json.dumps({"ok": True, "title": chat_win.title}, ensure_ascii=False))
            else:
                print(json.dumps({"ok": False, "error": err_str}, ensure_ascii=False))
        except:
            print(json.dumps({"ok": False, "error": err_str}, ensure_ascii=False))
    else:
        print(json.dumps({"ok": False, "error": err_str}, ensure_ascii=False))
