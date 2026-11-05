"""Route checks against the isolated Vite 5174 / API 8001 test services."""
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser=p.chromium.launch(channel="msedge",headless=True)
    page=browser.new_page(viewport={"width":1500,"height":1000})
    errors=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:5174/')
    expect(page.locator('a[href="/projects/astronomy-lab"]').first).to_be_visible()
    expect(page.locator('a[href="/projects/library-recommendation"]').first).to_be_visible()
    page.locator('a[href="/projects/astronomy-lab"]').first.click()
    expect(page.locator('.agent-node')).to_have_count(3)
    page.reload()
    expect(page.locator('.agent-node')).to_have_count(3)
    page.get_by_role('link',name='项目首页',exact=True).click()
    expect(page).to_have_url('http://127.0.0.1:5174/')
    page.locator('a[href="/projects/library-recommendation"]').first.click()
    expect(page.locator('.library-plan-dialog')).to_be_visible()
    page.goto('http://127.0.0.1:5174/unknown-route')
    expect(page.get_by_role('heading',name='项目页面不存在')).to_be_visible()
    expect(page.locator('a[href="/projects/library-recommendation"]')).to_be_visible()
    assert not errors,errors
    browser.close()
    print('Home, project routes, deep-link reload and fallback passed.')
