"""聚焦复测：倾诉模式前端渲染（后端 3s 回复，为何 E2E 超时）"""
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5000"
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page()
    errs = []
    pg.on("console", lambda m: errs.append(m.text[:200]) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append("PAGEERROR: " + str(e)[:200]))
    pg.goto(BASE, timeout=20000)
    pg.wait_for_selector(".mode-btn", timeout=10000)
    pg.click('[data-mode="affection"]')
    pg.wait_for_timeout(600)
    pg.fill("#question-input", "我压力好大，感觉撑不住了")
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(900)
    before = pg.locator(".msg.paeg").count()
    print("before count:", before)
    try:
        pg.wait_for_function(
            "n => document.querySelectorAll('.msg.paeg').length > n",
            arg=before, timeout=60000)
        txt = pg.locator(".msg.paeg").last.inner_text()
        print("A3 前端渲染 OK:", txt[:80])
    except Exception as e:
        print("A3 前端超时; count=", pg.locator(".msg.paeg").count(),
              "console errors:", errs[:5])
    b.close()
