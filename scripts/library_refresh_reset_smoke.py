"""Fixture backend must start with FIXTURE_RESET_ON_REFRESH=true."""
from playwright.sync_api import sync_playwright,expect
from browser_delivery_helpers import submit_first_result

with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1500,'height':1050})
    errors=[];resets=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:resets.append(r.url) if '/testing/reset-progress' in r.url else None)
    page.goto('http://127.0.0.1:5174/projects/library-recommendation')
    card=page.locator('.plan-card')
    card.locator('input[value=read_first]').check();card.locator('input[value=evidence]').check()
    card.locator('button[type=submit]').click()
    page.get_by_role('button',name='调用工具，计算一轮',exact=True).click()
    expect(page.locator('.center-experiment')).to_contain_text('14.333')
    page.get_by_role('button',name='使用新中心，计算下一轮',exact=True).click()
    expect(page.locator('.center-experiment')).to_contain_text('5.667')
    page.get_by_role('button',name='使用新中心，计算下一轮',exact=True).click()
    submit_first_result(page)
    card.locator('button[type=submit]').click()
    expect(page.locator('.prompt-blocks li')).to_have_count(7)
    assert len(resets)==1
    page.reload()
    expect(card).to_be_visible()
    expect(card.locator('input:checked')).to_have_count(0)
    expect(page.locator('.library-progress')).to_contain_text('0 / 4')
    assert len(resets)==2
    card.locator('input[value=read_first]').check();card.locator('input[value=evidence]').check()
    card.locator('button[type=submit]').click()
    expect(page.locator('.center-experiment')).to_be_visible()
    expect(page.locator('.prompt-blocks li')).to_have_count(0)
    page.get_by_role('link',name='项目首页',exact=True).click()
    page.locator('a[href="/projects/library-recommendation"]').first.click()
    expect(card.locator('input:checked')).to_have_count(0)
    assert len(resets)==3
    assert not errors,errors
    browser.close()
    print('Refresh and project re-entry reset library test records to a fresh activity1.')
