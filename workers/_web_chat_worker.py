"""独立进程执行多轮浏览器对话，追问由 LLM 生成"""
import sys
import os
import json
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
os.environ['no_proxy'] = 'localhost,127.0.0.1'

site = sys.argv[1]
msg = sys.argv[2]
port = int(sys.argv[3]) if len(sys.argv) > 3 else 9333
rounds = int(sys.argv[4]) if len(sys.argv) > 4 else 1
original_goal = sys.argv[5] if len(sys.argv) > 5 else msg
duration_sec = int(sys.argv[6]) if len(sys.argv) > 6 else 0  # >0 时按时间控制，忽略 rounds

from playwright.sync_api import sync_playwright


# ── LLM 追问生成 ──

def _load_llm_config():
    """读取 brain/llm_config.json"""
    try:
        from brain import get_current_llm_config

        cfg = get_current_llm_config()
        if isinstance(cfg, dict) and cfg.get("model"):
            return cfg
    except Exception:
        pass
    return None


def _generate_follow_up(conversation_so_far, llm_cfg, original_goal=""):
    """用 LLM 基于对话历史生成下一轮追问，始终锚定原始目标"""
    if not llm_cfg:
        return None

    history_text = ""
    for item in conversation_so_far:
        history_text += f"我：{item['send']}\n对方：{item['reply'][:200]}\n\n"

    goal_line = f"你的任务目标是：【{original_goal}】。无论对方说什么，你的追问必须围绕这个目标展开，不要被对方带偏话题。\n\n" if original_goal else ""

    prompt = (
        f"{goal_line}"
        "你正在和另一个AI对话。根据以下对话历史，生成一句自然的追问。"
        "要求：1.紧扣任务目标，不跟随对方跑题 2.像真人聊天一样自然 3.追问对方给出更具体、可落地的内容 "
        "4.不要重复之前问过的 5.只输出一句话，不要解释\n\n"
        f"对话历史：\n{history_text}"
        "你的下一句："
    )

    try:
        body = json.dumps({
            "model": llm_cfg.get("model", ""),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 100,
        }).encode()
        req = urllib.request.Request(
            llm_cfg.get("base_url", "").rstrip("/") + "/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {llm_cfg.get('api_key', '')}",
            },
        )
        resp = urllib.request.urlopen(req, timeout=10).read()
        data = json.loads(resp)
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


# ── 页面操作 ──

def _read_last_reply(page):
    """读取页面上最后一条 AI 回复。"""
    return page.evaluate('''() => {
        const all = document.querySelectorAll('[class*="markdown"], [class*="message-content"]');
        const texts = [];
        all.forEach(el => {
            const t = el.innerText.trim();
            if (t && t.length > 10) texts.push(t);
        });
        return texts.length ? texts[texts.length - 1] : "";
    }''')


def send_and_read(page, message):
    """发一条消息，等回复稳定后再读取。"""
    # 先记住发送前的最后一条内容
    old_reply = _read_last_reply(page) or ""

    textarea = page.locator('textarea').first
    textarea.click()
    time.sleep(0.2)
    textarea.fill(message)
    time.sleep(0.2)
    page.keyboard.press('Enter')

    # 第一阶段：等新回复出现（内容和发送前不同）
    time.sleep(3)
    for _ in range(30):
        curr = _read_last_reply(page) or ""
        if curr and curr != old_reply:
            break
        time.sleep(1)

    # 第二阶段：等回复稳定（连续 3 次相同 = 说完了）
    prev_text = ""
    stable_count = 0
    for _ in range(45):
        curr_text = _read_last_reply(page) or ""
        if curr_text and curr_text == prev_text:
            stable_count += 1
            if stable_count >= 3:
                break
        else:
            stable_count = 0
        prev_text = curr_text
        time.sleep(1)

    return prev_text or ""


def _debug_port_ready(port: int, timeout_sec: float = 15.0) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def _launch_browser_with_debug_port(browser_exe: str, process_name: str, port: int) -> bool:
    import subprocess

    env = os.environ.copy()
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
        env.pop(key, None)

    launch_args = [
        browser_exe,
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
        "--new-window",
    ]

    try:
        subprocess.Popen(launch_args, env=env)
    except Exception:
        return False

    if _debug_port_ready(port, timeout_sec=4.0):
        return True

    subprocess.call(['taskkill', '/F', '/IM', process_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)

    try:
        subprocess.Popen(launch_args, env=env)
    except Exception:
        return False

    return _debug_port_ready(port)


def _bundled_browser_candidates():
    browser_root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    if not browser_root:
        return []

    root = Path(browser_root)
    if not root.exists():
        return []

    candidates = []
    for child in sorted(root.iterdir(), reverse=True):
        if not child.is_dir() or not child.name.startswith("chromium-"):
            continue
        chrome_path = child / "chrome-win" / "chrome.exe"
        if chrome_path.exists():
            candidates.append(("bundled-chromium", [str(chrome_path)]))
    return candidates


def _ensure_browser(port: int) -> bool:
    """检查浏览器调试端口是否就绪，没有则关掉已有 Brave 再用调试参数重启。"""
    import subprocess
    # 先检查是否已经在监听
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=2)
        return True
    except Exception:
        pass
    # 没有调试端口 → 先杀掉已有 Brave 进程（它没带调试参数，新进程会被合并进去）
    browser_candidates = _bundled_browser_candidates() + [
        (
            "chrome.exe",
            [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ],
        ),
        (
            "msedge.exe",
            [
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            ],
        ),
        (
            "brave.exe",
            [
                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            ],
        ),
    ]
    # 找 Brave 路径
    for process_name, browser_paths in browser_candidates:
        browser_exe = next((path for path in browser_paths if os.path.exists(path)), None)
        if browser_exe and _launch_browser_with_debug_port(browser_exe, process_name, port):
            return True
    return False


# ── 主流程 ──

llm_cfg = _load_llm_config()

# 确保浏览器就绪
if not _ensure_browser(port):
    print(json.dumps({"ok": False, "error": f"Browser did not start automatically. Please launch Chrome, Edge, or Brave with --remote-debugging-port={port}"}, ensure_ascii=False))
    sys.exit(0)

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
    page = None
    for ctx in browser.contexts:
        for p in ctx.pages:
            if site.lower() in p.url.lower() or site in p.title():
                page = p
                break

    if not page:
        # 没找到页面 → 自动新开一个标签
        site_urls = {
            "doubao": "https://www.doubao.com/chat/",
            "chatgpt": "https://chat.openai.com/",
            "kimi": "https://kimi.moonshot.cn/",
        }
        target_url = site_urls.get(site.lower(), f"https://www.{site}.com/")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        page.goto(target_url)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(3)  # 等页面渲染

    conversation = []
    current_msg = msg
    deadline = time.time() + duration_sec if duration_sec > 0 else None
    max_rounds = 60 if deadline else rounds  # 时间模式最多60轮兜底

    for i in range(max_rounds):
        # 时间模式：到时间就停
        if deadline and time.time() >= deadline:
            break

        reply = send_and_read(page, current_msg)
        conversation.append({"round": i + 1, "send": current_msg, "reply": reply[:300]})

        # 判断是否继续
        has_next = (deadline and time.time() < deadline) or (not deadline and i < rounds - 1)
        if not has_next:
            break

        follow_up = _generate_follow_up(conversation, llm_cfg, original_goal=original_goal)
        if follow_up:
            current_msg = follow_up
        else:
            current_msg = f"回到正题，关于【{original_goal[:30]}】，能给我更具体可落地的建议吗？"

    print(json.dumps({"ok": True, "conversation": conversation}, ensure_ascii=False))

except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
finally:
    pw.stop()
