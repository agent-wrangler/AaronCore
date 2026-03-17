"""独立进程执行多轮浏览器对话，追问由 LLM 生成"""
import sys
import os
import json
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
os.environ['no_proxy'] = 'localhost,127.0.0.1'

site = sys.argv[1]
msg = sys.argv[2]
port = int(sys.argv[3]) if len(sys.argv) > 3 else 9333
rounds = int(sys.argv[4]) if len(sys.argv) > 4 else 1

from playwright.sync_api import sync_playwright


# ── LLM 追问生成 ──

def _load_llm_config():
    """读取 brain/llm_config.json"""
    try:
        cfg_path = os.path.join(os.path.dirname(__file__), '..', '..', 'brain', 'llm_config.json')
        with open(cfg_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _generate_follow_up(conversation_so_far, llm_cfg):
    """用 LLM 基于对话历史生成下一轮追问"""
    if not llm_cfg:
        return None

    history_text = ""
    for item in conversation_so_far:
        history_text += f"我：{item['send']}\n对方：{item['reply'][:200]}\n\n"

    prompt = (
        "你正在和另一个AI对话。根据以下对话历史，生成一句自然的追问或回应。"
        "要求：1.基于对方刚说的内容 2.像真人聊天一样自然 3.可以追问细节、提出不同看法、或延伸话题 "
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
    subprocess.call(['taskkill', '/F', '/IM', 'brave.exe'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    # 找 Brave 路径
    brave_paths = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    ]
    brave_exe = next((p for p in brave_paths if os.path.exists(p)), None)
    if not brave_exe:
        return False
    env = os.environ.copy()
    for k in ["HTTP_PROXY","HTTPS_PROXY","http_proxy","https_proxy","ALL_PROXY","all_proxy"]:
        env.pop(k, None)
    subprocess.Popen(
        [brave_exe, f"--remote-debugging-port={port}", "--no-first-run", "--no-default-browser-check"],
        env=env
    )
    # 等待最多 15 秒
    for _ in range(30):
        time.sleep(0.5)
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=1)
            return True
        except Exception:
            pass
    return False


# ── 主流程 ──

llm_cfg = _load_llm_config()

# 确保浏览器就绪
if not _ensure_browser(port):
    print(json.dumps({"ok": False, "error": "浏览器未启动且无法自动打开，请手动启动 Brave 并开启调试端口"}, ensure_ascii=False))
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

    for i in range(rounds):
        reply = send_and_read(page, current_msg)
        conversation.append({"round": i + 1, "send": current_msg, "reply": reply[:300]})

        if rounds > 1 and i < rounds - 1:
            follow_up = _generate_follow_up(conversation, llm_cfg)
            if follow_up:
                current_msg = follow_up
            else:
                short = reply[:20]
                current_msg = f"\u4f60\u8bf4\u7684\u201c{short}\u201d\u8fd9\u90e8\u5206\u5f88\u6709\u610f\u601d\uff0c\u80fd\u518d\u5c55\u5f00\u8bf4\u8bf4\u5417\uff1f"

    print(json.dumps({"ok": True, "conversation": conversation}, ensure_ascii=False))

except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
finally:
    pw.stop()
