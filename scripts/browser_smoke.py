"""Optional browser smoke: pip install playwright, use installed Edge on Windows.
Start backend and Vite first. Does not require an LLM key.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:5173/projects/astronomy-lab")
        expect(page.locator(".learning-intro .eyebrow")).to_have_text("PROJECT 1")
        expect(page.locator(".agent-node")).to_have_count(3)
        prompt = page.locator(".configuration-panel textarea")
        prompt.fill("你是观星学习助手。必须说明数据来源，不编造天气。")
        page.get_by_role("button", name="保存配置", exact=True).click()
        expect(page.locator(".save-state")).to_have_text("配置已同步")
        page.locator(".agent-node.weather").click()
        switch = page.get_by_role("switch", name="启用 天气查询工具")
        switch.locator("..").click()
        expect(page.locator(".agent-node.weather")).to_have_class(__import__('re').compile("disabled"))
        page.get_by_role("button", name="保存配置", exact=True).click()
        expect(page.locator(".save-state")).to_have_text("配置已同步")
        page.get_by_role("button", name="完成这一步", exact=True).click()
        expect(page.locator(".learning-progress b")).to_have_text("1 / 4")
        page.reload()
        expect(page.locator(".configuration-panel textarea")).to_have_value("你是观星学习助手。必须说明数据来源，不编造天气。")
        expect(page.locator(".agent-node.weather")).to_have_class(__import__('re').compile("disabled"))
        expect(page.locator(".learning-progress b")).to_have_text("1 / 4")
        page.get_by_role("button", name="试试示例").click()
        expect(page.locator(".test-input textarea")).not_to_have_value("")
        page.get_by_role("button", name="Run Agent", exact=True).click()
        expect(page.locator(".trace-event.error")).to_contain_text("错误", timeout=15000)
        page.reload()
        expect(page.locator(".trace-event.error")).to_contain_text("错误")
        page.get_by_role("button", name=__import__('re').compile("运行历史")).click()
        expect(page.locator(".history-item")).to_have_count(1)
        page.locator(".history-item").click()
        expect(page.locator(".snapshot")).to_be_visible()
        # Resize and inspect desktop arrangement.
        separator = page.get_by_role("separator", name="调整执行面板高度")
        box = separator.bounding_box()
        page.mouse.move(box["x"] + 100, box["y"] + 2)
        page.mouse.down()
        page.mouse.move(box["x"] + 100, box["y"] - 60)
        page.mouse.up()
        page.locator(".agent-node.weather").click()
        Path("test-results").mkdir(exist_ok=True)
        page.screenshot(path="test-results/workspace.png", full_page=True)
        assert not errors, errors
        print("Browser smoke passed: node configuration, save/reload, tool toggle, learning progress, SSE error, history, resize; no page errors.")
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
