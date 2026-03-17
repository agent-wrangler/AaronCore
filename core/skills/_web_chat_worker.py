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
    textarea = page.locator('textarea').first
    textarea.click()
    time.sleep(0.2)
    textarea.fill(message)
    time.sleep(0.2)
    page.keyboard.press('Enter')

    time.sleep(4)
    prev_text = ""
    stable_count = 0
    for _ in range(40):
        curr_text = _read_last_reply(page) or ""
        if curr_text and curr_text == prev_text:
            stable_count += 1
            if stable_count >= 2:
                break
        else:
            stable_count = 0
        prev_text = curr_text
        time.sleep(1)
    return prev_text or ""


# ── 主流程 ──

llm_cfg = _load_llm_config()

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
        print(json.dumps({"ok": False, "error": f"\u6ca1\u627e\u5230\u5305\u542b{site}\u7684\u9875\u9762"}, ensure_ascii=False))
        sys.exit(0)

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
