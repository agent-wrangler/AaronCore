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

# ── 监听进程管理（支持多群） ──
_monitor_processes = {}  # {group_name: subprocess.Popen}
_MONITOR_STATE_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'memory_db', 'qq_monitor_state.json')


def _save_monitor_state(active, group=None):
    try:
        import json as _json
        groups = list(_monitor_processes.keys()) if active else []
        with open(_MONITOR_STATE_FILE, 'w', encoding='utf-8') as f:
            _json.dump({"active": len(groups) > 0, "groups": groups, "group": ", ".join(groups) if groups else None}, f, ensure_ascii=False)
    except: pass


def qq_monitor_status() -> dict:
    """返回监听状态（从文件读，跨模块实例可靠）"""
    try:
        import json as _json
        with open(_MONITOR_STATE_FILE, 'r', encoding='utf-8') as f:
            return _json.load(f)
    except:
        return {"active": False, "group": None, "groups": []}

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
    """在指定 QQ 群里发送消息。用子进程执行避免 FastAPI 兼容问题。"""
    import subprocess
    worker = os.path.join(os.path.dirname(__file__), '_qq_worker.py')
    try:
        result = subprocess.run(
            [sys.executable, '-u', worker, group_name, message],
            capture_output=True, timeout=30,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
        )
        raw = result.stdout.decode('utf-8', errors='replace') if isinstance(result.stdout, bytes) else result.stdout
        lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
        json_line = ""
        for line in reversed(lines):
            if line.startswith("{"):
                json_line = line
                break
        if not json_line:
            err = result.stderr.decode('utf-8', errors='replace')[:200] if isinstance(result.stderr, bytes) else str(result.stderr)[:200]
            return f"QQ 操作失败：{err}"
        data = json.loads(json_line)
        if data.get("ok"):
            return data.get("result", "已发送")
        else:
            return f"QQ 操作失败：{data.get('error', '未知错误')}"
    except subprocess.TimeoutExpired:
        return "QQ 操作超时"
    except Exception as e:
        return f"QQ 操作失败：{e}"


def qq_start_monitor(group_name: str, my_name: str = '\u6d74\u706b\u91cd\u751f') -> str:
    """启动 QQ 群监听（支持多群同时）。先打开群聊窗口，再启动后台监听进程。"""
    global _monitor_processes
    import subprocess

    # 已经在监听这个群了
    if group_name in _monitor_processes:
        p = _monitor_processes[group_name]
        if p.poll() is None:
            _save_monitor_state(True)
            return f"\u300c{group_name}\u300d\u5df2\u5728\u54cd\u5e94\u4e2d\uff0c\u65e0\u9700\u91cd\u590d\u5f00\u542f"

    # 先用 _qq_worker 打开群聊窗口
    open_worker = os.path.join(os.path.dirname(__file__), '_qq_open_group.py')
    try:
        result = subprocess.run(
            [sys.executable, '-u', open_worker, group_name],
            capture_output=True, timeout=25,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
        )
        raw = result.stdout.decode('utf-8', errors='replace') if isinstance(result.stdout, bytes) else result.stdout
        err = result.stderr.decode('utf-8', errors='replace') if isinstance(result.stderr, bytes) else str(result.stderr)
        try:
            with open("memory_db/cu_debug.log", "a", encoding="utf-8") as f:
                f.write(f"[open_group] stdout={raw[:200]} stderr={err[:200]}\n")
        except: pass
        data = json.loads(raw.strip().splitlines()[-1]) if raw.strip() else {}
        if not data.get("ok"):
            return f"QQ \u6253\u5f00\u7fa4\u300c{group_name}\u300d\u5931\u8d25\uff1a{data.get('error', '')}"
    except Exception as e:
        return f"QQ \u6253\u5f00\u7fa4\u5931\u8d25\uff1a{e}"

    # 启动监听 worker
    worker = os.path.join(os.path.dirname(__file__), '_qq_monitor_worker.py')
    proc = subprocess.Popen(
        [sys.executable, '-u', worker, group_name, my_name, '8'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
    )
    _monitor_processes[group_name] = proc
    _save_monitor_state(True)
    count = len([p for p in _monitor_processes.values() if p.poll() is None])
    suffix = f"\uff0c\u5f53\u524d\u5171\u54cd\u5e94 {count} \u4e2a\u7fa4" if count > 1 else ""
    return f"\u5df2\u5f00\u542f\u667a\u80fd\u4f1a\u8bdd\u54cd\u5e94\uff0c\u6b63\u5728\u54cd\u5e94\u300c{group_name}\u300d\u7684\u6240\u6709\u5bf9\u8bdd{suffix}\u3002\u8bf4\u201c\u505c\u6b62\u54cd\u5e94\u201d\u53ef\u4ee5\u5173\u95ed\u3002"


def qq_stop_monitor(target_group=None) -> str:
    """停止 QQ 群监听。target_group=None 时停止全部。"""
    global _monitor_processes
    if not _monitor_processes:
        _save_monitor_state(False)
        return "\u5f53\u524d\u6ca1\u6709\u5728\u54cd\u5e94\u4efb\u4f55\u7fa4"

    stopped = []
    if target_group and target_group in _monitor_processes:
        # 停止指定群
        p = _monitor_processes.pop(target_group)
        if p.poll() is None:
            try: p.kill(); p.wait(timeout=5)
            except: pass
        stopped.append(target_group)
    elif not target_group:
        # 停止全部
        for name, p in _monitor_processes.items():
            if p.poll() is None:
                try: p.kill(); p.wait(timeout=5)
                except: pass
            stopped.append(name)
        _monitor_processes.clear()

    _save_monitor_state(True)
    if stopped:
        names = '\u3001'.join(stopped)
        return f"\u5df2\u505c\u6b62\u54cd\u5e94\u300c{names}\u300d"
    return "\u5f53\u524d\u6ca1\u6709\u5728\u54cd\u5e94\u4efb\u4f55\u7fa4"


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


def web_chat(site: str, message: str, port: int = 9333, rounds: int = 1, original_goal: str = "", duration_sec: int = 0) -> str:
    """在网页版 AI（豆包等）发送消息并获取回复。用子进程执行避免 async 冲突。"""
    import subprocess
    worker = os.path.join(os.path.dirname(__file__), '_web_chat_worker.py')
    timeout = duration_sec + 60 if duration_sec > 0 else (60 if rounds <= 1 else min(rounds * 50 + 30, 600))
    try:
        result = subprocess.run(
            [sys.executable, '-u', worker, site, message, str(port), str(rounds), original_goal or message, str(duration_sec)],
            capture_output=True, timeout=timeout,
            env={
                **{k: v for k, v in os.environ.items() if 'proxy' not in k.lower()},
                'NO_PROXY': 'localhost,127.0.0.1',
                'no_proxy': 'localhost,127.0.0.1',
                'PYTHONIOENCODING': 'utf-8',
            },
        )
        if result.returncode != 0:
            err = result.stderr.decode('utf-8', errors='replace')[:200] if isinstance(result.stderr, bytes) else str(result.stderr)[:200]
            return f"浏览器操作失败：{err}"
        # stdout 解码 + 只取最后一行 JSON
        raw_out = result.stdout.decode('utf-8', errors='replace') if isinstance(result.stdout, bytes) else result.stdout
        stdout_lines = [l.strip() for l in raw_out.strip().splitlines() if l.strip()]
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


def _generate_first_msg(user_input: str, context: dict = None) -> str:
    """用 LLM 从用户指令+对话历史中提取话题，生成自然的第一句话发给对方 AI。"""
    try:
        cfg_path = os.path.join(os.path.dirname(__file__), '..', '..', 'brain', 'llm_config.json')
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        import urllib.request

        # 把最近对话历史拼成摘要，帮 LLM 推断当前话题
        history_hint = ""
        recent = (context or {}).get("recent_history", [])
        if recent:
            lines = []
            for m in recent[-6:]:
                role = "用户" if m.get("role") == "user" else "Nova"
                lines.append(f"{role}：{m.get('content','')[:100]}")
            history_hint = "最近的对话上下文：\n" + "\n".join(lines) + "\n\n"

        body = json.dumps({
            "model": cfg.get("model", ""),
            "messages": [{"role": "user", "content":
                f"{history_hint}"
                f"用户现在说：\u201c{user_input}\u201d\n"
                "请根据上下文推断用户真正想聊的话题，生成一句自然的开场白发给对方AI。"
                "要求：1.像真人聊天 2.只输出开场白那一句话 3.不要解释 "
                "4.必须紧扣用户真实意图，从上下文推断话题，不要自己发明无关话题"
            }],
            "max_tokens": 80,
        }).encode()
        req = urllib.request.Request(
            cfg.get("base_url", "").rstrip("/") + "/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {cfg.get('api_key', '')}",
            },
        )
        resp = urllib.request.urlopen(req, timeout=8).read()
        data = json.loads(resp)
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        # fallback：从 user_input 里提取关键词，至少不跑偏
        for kw in ["赚钱", "变现", "头条", "发文", "创业", "技能", "方案"]:
            if kw in user_input:
                return f"你觉得AI agent怎么在{kw}这个方向上落地？"
        return "你觉得AI agent现在最容易落地赚钱的方向是什么？"


# ── 技能入口 ──

def execute(user_input: str, context: dict = None) -> str:
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
        result = _do_execute(text, context or {})
        _log(f"[result] {result[:200] if result else 'None'}")
        return result
    except Exception as e:
        _log(f"[error] {traceback.format_exc()}")
        return f"执行失败：{e}"


def _do_execute(text: str, context: dict = None) -> str:
    """实际执行逻辑。"""

    # QQ 群监听（启动/停止）— 必须在 QQ 发消息之前
    if re.search(r'(?:停止|关闭|取消).*?(?:监听|监视|监控|响应)', text):
        return qq_stop_monitor()
    monitor_match = re.search(r'(?:监听|监视|监控|响应).*?(?:QQ|qq)(?:群)?[「""\s]*(.+)', text)
    if not monitor_match:
        monitor_match = re.search(r'(?:在|去|帮我).*?(?:QQ|qq)(?:群)?[「""\s]*(.+?)[」""]*(?:监听|监视|监控|自动回复|聊天|响应)', text)
    if not monitor_match:
        monitor_match = re.search(r'(?:QQ|qq)(?:群)?[「""\s]*(.+?)[」""\s]*(?:监听|监视|监控|自动回复|响应)', text)
    if not monitor_match:
        monitor_match = re.search(r'(?:开启|打开|启动).*?(?:智能|会话)?(?:响应|对话).*?(?:QQ|qq)?(?:群)?[「""\s]*(.+?)[」""\s]*$', text)
    if monitor_match:
        group = monitor_match.group(1).strip().rstrip('」""里面中内 ')
        return qq_start_monitor(group)

    # QQ 发消息（支持有引号和无引号两种写法）
    qq_send_match = re.search(r'(?:在|去)(?:QQ|qq)(?:群)?[「""\s]*(.+?)[」""\s]*(?:发|说|回复)[：:]?\s*(.+)', text)
    if not qq_send_match:
        qq_send_match = re.search(r'(?:帮我|替我).*?(?:在|去).*?(?:QQ|qq)(?:群)?[「""\s]*(.+?)[」""\s]*(?:发|说)[：:]?\s*(.+)', text)
    if qq_send_match:
        group = qq_send_match.group(1).strip()
        msg = qq_send_match.group(2).strip()
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
        duration_sec = 0
        if '分钟' in text:
            duration_sec = rounds * 60  # 真实秒数，worker 按时间控制
            rounds = 60  # 兜底上限，实际由 deadline 截断
        rounds = min(rounds, 20)
        site = '豆包' if '豆包' in text else 'chatgpt'
        site_url = 'doubao' if site == '豆包' else site.lower()
        first_msg = _generate_first_msg(text, context or {})
        goal_strip = re.sub(r'(?:去|和|找)?(?:豆包|doubao|chatgpt|kimi)(?:聊|对话|说说)?[\d分钟轮次个回合\s]*', '', text).strip()
        original_goal = goal_strip if len(goal_strip) > 4 else first_msg
        return web_chat(site_url, first_msg, rounds=rounds, original_goal=original_goal, duration_sec=duration_sec)

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
