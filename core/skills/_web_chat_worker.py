"""独立进程执行浏览器操作，避免 FastAPI async 冲突"""
import sys
import os
import json
import time

os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
os.environ['no_proxy'] = 'localhost,127.0.0.1'

site = sys.argv[1]  # doubao
msg = sys.argv[2]   # 问题内容
port = int(sys.argv[3]) if len(sys.argv) > 3 else 9333

from playwright.sync_api import sync_playwright

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

    textarea = page.locator('textarea').first
    textarea.click()
    time.sleep(0.2)
    textarea.fill(msg)
    time.sleep(0.2)
    page.keyboard.press('Enter')

    # 等回复
    time.sleep(5)
    for _ in range(25):
        stop_btns = page.locator('[aria-label*="stop"], [class*="stop"]').count()
        if stop_btns == 0:
            break
        time.sleep(1)
    time.sleep(1)

    result = page.evaluate('''() => {
        const all = document.querySelectorAll('[class*="markdown"], [class*="message-content"]');
        const texts = [];
        all.forEach(el => {
            const t = el.innerText.trim();
            if (t && t.length > 10) texts.push(t);
        });
        return texts.length ? texts[texts.length - 1] : "";
    }''')

    print(json.dumps({"ok": True, "reply": result[:500]}, ensure_ascii=False))
except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
finally:
    pw.stop()
