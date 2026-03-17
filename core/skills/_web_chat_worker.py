"""独立进程执行多轮浏览器对话"""
import sys
import os
import json
import time

os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
os.environ['no_proxy'] = 'localhost,127.0.0.1'

site = sys.argv[1]
msg = sys.argv[2]
port = int(sys.argv[3]) if len(sys.argv) > 3 else 9333
rounds = int(sys.argv[4]) if len(sys.argv) > 4 else 1

from playwright.sync_api import sync_playwright


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

    # 等内容稳定：连续 2 次读到相同内容且非空，说明回复完了
    time.sleep(4)
    prev_text = ""
    stable_count = 0
    for _ in range(40):  # 最多等 40 秒
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
        print(json.dumps({"ok": False, "error": f"没找到包含{site}的页面"}, ensure_ascii=False))
        sys.exit(0)

    conversation = []
    current_msg = msg

    for i in range(rounds):
        reply = send_and_read(page, current_msg)
        conversation.append({"round": i + 1, "send": current_msg, "reply": reply[:300]})

        if rounds > 1 and i < rounds - 1:
            # 用回复的内容生成下一轮的追问
            # 简单策略：基于回复提一个追问
            follow_ups = [
                f"有意思，能再展开说说吗？",
                f"这个观点我同意一部分，你怎么看反面的情况？",
                f"还有其他角度吗？",
                f"如果从实际应用来看呢？",
                f"你觉得未来会怎么发展？",
                f"能举个具体的例子吗？",
                f"总结一下你的核心观点？",
            ]
            current_msg = follow_ups[i % len(follow_ups)]

    print(json.dumps({"ok": True, "conversation": conversation}, ensure_ascii=False))

except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
finally:
    pw.stop()
