"""
Computer Use 技能 — 桌面代理 v1
操控 QQ、浏览器、桌面应用，代替用户完成操作。

能力：
- QQ 发消息（pywinauto 控件操作）
- 网页操作（Playwright 浏览器自动化）
- 桌面窗口（pyautogui 截屏/点击/打字）

进化方向：
- v2: 截屏 + 多模态 LLM 理解任意界面
- v3: 连续多步任务、任务记忆
"""

import os
import time
import json
import re

# ── 依赖检测 ──
_HAS_PYAUTOGUI = False
_HAS_PYWINAUTO = False
_HAS_PLAYWRIGHT = False

try:
    import pyautogui
    import pygetwindow as gw
    import pyperclip
    _HAS_PYAUTOGUI = True
except ImportError:
    pass

try:
    from pywinauto import Application, Desktop
    _HAS_PYWINAUTO = True
except ImportError:
    pass

try:
    from playwright.sync_api import sync_playwright
    _HAS_PLAYWRIGHT = True
except ImportError:
    pass


# ── QQ 操作 ──

def qq_send_message(group_name: str, message: str) -> str:
    """在指定 QQ 群里发送消息。"""
    if not _HAS_PYAUTOGUI or not _HAS_PYWINAUTO:
        return "缺少依赖：需要 pyautogui + pywinauto（pip install pyautogui pywinauto）"

    # 找到 QQ 主窗口
    qq_wins = [w for w in gw.getAllWindows() if w.title.strip() == 'QQ']
    if not qq_wins:
        return "没找到 QQ 窗口，请先打开 QQ"

    win = qq_wins[0]
    win.activate()
    time.sleep(0.5)

    # 用 pywinauto 读控件，找到目标群
    try:
        app = Application(backend='uia').connect(title='QQ')
        main_win = app.window(title='QQ')
        # 读取会话列表文本
        doc = main_win.child_window(control_type="Document")
        doc_text = doc.window_text()

        if group_name not in doc_text:
            return f"在 QQ 会话列表中没找到「{group_name}」，请确认群名或先把群聊置顶"

        # 在会话列表中找到群的位置并点击
        session_list = main_win.child_window(title="会话列表", control_type="Window")
        items = session_list.children()
        clicked = False
        for item in items:
            try:
                if group_name in item.window_text():
                    item.click_input()
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            # fallback: 用搜索
            return f"无法定位群「{group_name}」的位置，请手动点开该群后重试"

        time.sleep(1)

        # 找到群聊窗口
        group_wins = [w for w in gw.getAllWindows() if group_name in w.title]
        if not group_wins:
            return f"群「{group_name}」窗口没有打开"

        group_win = group_wins[0]
        group_win.activate()
        time.sleep(0.3)

        # 在输入框输入消息
        click_x = group_win.left + group_win.width // 2
        click_y = group_win.top + group_win.height - 160
        pyautogui.click(click_x, click_y)
        time.sleep(0.2)

        pyperclip.copy(message)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.2)

        # 发送
        pyautogui.press('enter')
        time.sleep(0.5)

        return f"已在「{group_name}」发送：{message}"

    except Exception as e:
        return f"QQ 操作失败：{e}"


def qq_read_messages(group_name: str) -> str:
    """读取指定 QQ 群的最新消息。"""
    if not _HAS_PYWINAUTO:
        return "缺少依赖：需要 pywinauto（pip install pywinauto）"

    try:
        app = Application(backend='uia').connect(title='QQ')
        main_win = app.window(title='QQ')
        doc = main_win.child_window(control_type="Document")
        doc_text = doc.window_text()

        # 从文本中提取目标群的最新消息
        lines = doc_text.split('\n')
        for line in lines:
            if group_name in line:
                return f"「{group_name}」最新：{line.strip()}"

        return f"没找到「{group_name}」的消息"
    except Exception as e:
        return f"读取失败：{e}"


# ── 浏览器操作 ──

def _connect_browser(port: int = 9333):
    """连接已打开的浏览器（需要用 --remote-debugging-port 启动）。"""
    if not _HAS_PLAYWRIGHT:
        return None, None, "缺少依赖：需要 playwright（pip install playwright && playwright install chromium）"

    os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
    os.environ['no_proxy'] = 'localhost,127.0.0.1'

    try:
        pw = sync_playwright().start()
        browser = pw.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
        return pw, browser, None
    except Exception as e:
        return None, None, f"连接浏览器失败：{e}。请用 --remote-debugging-port={port} 启动浏览器"


def web_chat(site: str, message: str, port: int = 9333) -> str:
    """在网页版 AI（豆包等）发送消息并获取回复。"""
    pw, browser, err = _connect_browser(port)
    if err:
        return err

    try:
        # 找到目标页面
        page = None
        for ctx in browser.contexts:
            for p in ctx.pages:
                if site.lower() in p.url.lower() or site in p.title():
                    page = p
                    break

        if not page:
            return f"没找到包含「{site}」的页面，请先在浏览器中打开"

        # 找输入框
        textarea = page.locator('textarea').first
        textarea.click()
        time.sleep(0.2)

        # 输入并发送
        textarea.fill(message)
        time.sleep(0.2)
        page.keyboard.press('Enter')

        # 等待回复（最多等 30 秒）
        time.sleep(5)
        for _ in range(25):
            # 检查是否还在生成（有停止按钮说明还在生成）
            stop_btns = page.locator('[aria-label*="stop"], [class*="stop"]').count()
            if stop_btns == 0:
                break
            time.sleep(1)

        time.sleep(1)

        # 读取回复
        result = page.evaluate('''() => {
            const all = document.querySelectorAll('[class*="markdown"], [class*="message-content"]');
            const texts = [];
            all.forEach(el => {
                const t = el.innerText.trim();
                if (t && t.length > 10) texts.push(t);
            });
            return texts.length ? texts[texts.length - 1] : "";
        }''')

        if result:
            return f"「{site}」回复：{result[:500]}"
        else:
            return f"消息已发送，但未能读取回复"

    except Exception as e:
        return f"网页操作失败：{e}"
    finally:
        pw.stop()


def desktop_list_windows() -> str:
    """列出当前桌面所有窗口。"""
    if not _HAS_PYAUTOGUI:
        return "缺少依赖：需要 pyautogui"

    windows = [w.title for w in gw.getAllWindows() if w.title.strip()]
    return "当前打开的窗口：\n" + "\n".join(f"  · {w}" for w in windows[:20])


# ── 技能入口 ──

def execute(user_input: str) -> str:
    """Computer Use 技能入口。解析用户意图，分发到具体操作。"""
    text = (user_input or "").strip()

    # QQ 发消息
    qq_send_match = re.search(r'(?:在|去)(?:QQ|qq).*?[「""](.+?)[」""].*?(?:发|说|回复)[：:]?\s*(.+)', text)
    if not qq_send_match:
        qq_send_match = re.search(r'(?:帮我|替我).*?(?:在|去).*?[「""](.+?)[」""].*?(?:发|说)[：:]?\s*(.+)', text)
    if qq_send_match:
        group = qq_send_match.group(1)
        msg = qq_send_match.group(2)
        return qq_send_message(group, msg)

    # QQ 读消息
    qq_read_match = re.search(r'(?:看看|读|查看).*?[「""](.+?)[」""].*?(?:消息|聊天)', text)
    if qq_read_match:
        group = qq_read_match.group(1)
        return qq_read_messages(group)

    # 网页聊天（豆包等）
    web_match = re.search(r'(?:问|去|在)(?:豆包|doubao|chatgpt|kimi)[：:]?\s*(.+)', text, re.I)
    if web_match:
        msg = web_match.group(1)
        site = '豆包' if '豆包' in text.lower() or 'doubao' in text.lower() else 'chatgpt'
        site_url = 'doubao' if site == '豆包' else site.lower()
        return web_chat(site_url, msg)

    # 列出窗口
    if any(w in text for w in ['什么窗口', '哪些窗口', '打开了什么', '桌面上有什么']):
        return desktop_list_windows()

    return (
        "Computer Use 技能支持：\n"
        "  · 在QQ群「群名」发：消息内容\n"
        "  · 看看「群名」的消息\n"
        "  · 问豆包：你的问题\n"
        "  · 桌面上打开了什么窗口\n"
        "\n示例：帮我在QQ群「超级 AI agent 个人助理」发：大家好"
    )
