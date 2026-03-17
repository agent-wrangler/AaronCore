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
import sys
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
        # 绕过代理（Clash 等会拦截 localhost）
        os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
        os.environ['no_proxy'] = 'localhost,127.0.0.1'
        pw = sync_playwright().start()
        browser = pw.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
        return pw, browser, None
    except Exception as e:
        return None, None, f"连接浏览器失败：{e}。请用 --remote-debugging-port={port} 启动浏览器"


def web_chat(site: str, message: str, port: int = 9333, rounds: int = 1) -> str:
    """在网页版 AI（豆包等）发送消息并获取回复。用子进程执行避免 async 冲突。"""
    import subprocess
    worker = os.path.join(os.path.dirname(__file__), '_web_chat_worker.py')
    timeout = 60 if rounds <= 1 else min(rounds * 50 + 30, 600)
    try:
        result = subprocess.run(
            [sys.executable, worker, site, message, str(port), str(rounds)],
            capture_output=True, text=True, timeout=timeout,
            env={
                **{k: v for k, v in os.environ.items() if 'proxy' not in k.lower()},
                'NO_PROXY': 'localhost,127.0.0.1',
                'no_proxy': 'localhost,127.0.0.1',
            },
        )
        if result.returncode != 0:
            return f"浏览器操作失败：{result.stderr[:200]}"
        # stdout 可能包含 Node.js 的 warning，只取最后一行 JSON
        stdout_lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        json_line = ""
        for line in reversed(stdout_lines):
            if line.startswith("{"):
                json_line = line
                break
        if not json_line:
            return f"浏览器操作失败：无法解析返回结果"
        data = json.loads(json_line)
        if data.get("ok"):
            # 多轮对话
            conv = data.get("conversation")
            if conv and len(conv) > 1:
                lines = [f"和「{site}」聊了 {len(conv)} 轮：\n"]
                for item in conv:
                    lines.append(f"第{item['round']}轮 我说：{item['send']}")
                    lines.append(f"　　它说：{item['reply'][:150]}\n")
                return "\n".join(lines)
            # 单轮
            elif conv and len(conv) == 1:
                return f"「{site}」回复：{conv[0]['reply']}"
            # 旧格式兼容
            return f"「{site}」回复：{data.get('reply', '')}"
        else:
            return f"浏览器操作失败：{data.get('error', '未知错误')}"
    except subprocess.TimeoutExpired:
        return "浏览器操作超时，豆包可能还在回复中"
    except Exception as e:
        return f"浏览器操作失败：{e}"


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

    # 调试日志
    import traceback
    def _log(msg):
        try:
            with open("memory_db/cu_debug.log", "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except: pass

    _log(f"[input] {text}")

    try:
        result = _do_execute(text)
        _log(f"[result] {result[:200] if result else 'None'}")
        return result
    except Exception as e:
        _log(f"[error] {traceback.format_exc()}")
        return f"执行失败：{e}"


def _do_execute(text: str) -> str:
    """实际执行逻辑。"""

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

    # 网页多轮聊天 — 只要同时出现"豆包"和"X轮/X分钟"就算多轮
    rounds_match = re.search(r'(\d+)\s*(?:轮|分钟|次|个回合)', text)
    has_target = re.search(r'(?:豆包|doubao|chatgpt|kimi)', text, re.I)
    if rounds_match and has_target:
        rounds = int(rounds_match.group(1))
        if '分钟' in text:
            rounds = max(rounds * 2, 2)
        rounds = min(rounds, 20)
        site = '豆包' if '豆包' in text else 'chatgpt'
        site_url = 'doubao' if site == '豆包' else site.lower()
        # 提取 topic：去掉指令性词汇，留下话题内容
        topic = text
        for noise in ['去', '和', '跟', '让', '叫', '豆包', '聊', '轮', '分钟', '次', '个回合',
                       '关于', '的话题', '的事', '回来', '总结', '给我', '随便', '聊点什么',
                       '帮我', '一下', '那边', rounds_match.group(0)]:
            topic = topic.replace(noise, '')
        topic = re.sub(r'\s+', '', topic).strip('，, 。')
        if topic:
            first_msg = f"我们来聊聊{topic}吧，你先说说你的看法"
        else:
            first_msg = "你好，我们来聊聊天吧，随便聊点什么有趣的话题"
        return web_chat(site_url, first_msg, rounds=rounds)

    # 网页单轮聊天（豆包等）
    web_match = re.search(r'(?:问|去|在|用|让|叫)(?:一下|下)?(?:豆包|doubao|chatgpt|kimi)[：:，,]?\s*(.+)', text, re.I)
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
