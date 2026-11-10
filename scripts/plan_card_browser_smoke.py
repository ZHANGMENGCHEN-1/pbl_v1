from browser_delivery_helpers import submit_first_result
"""Unified plan cards: fixture backend8001 and Vite5174; no paid model calls."""
from playwright.sync_api import sync_playwright,expect
from pathlib import Path

with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1500,'height':1050})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:5174/projects/library-recommendation')
    card=page.locator('.plan-card')
    expect(card.locator('fieldset')).to_have_count(2)
    expect(card.locator('input:checked')).to_have_count(0)
    expect(card.locator('button[type=submit]')).to_be_disabled()
    page.keyboard.press('Escape')
    expect(card).to_be_visible()
    card.locator('input[value=read_first]').check()
    card.locator('input[value=evidence]').check()
    card.locator('button[type=submit]').click()
    page.get_by_role('button',name='调用工具，计算一轮',exact=True).click()
    expect(page.locator('.center-experiment')).to_contain_text('14.333')
    page.get_by_role('button',name='查看我的计划',exact=True).click()
    page.get_by_role('button',name='查看或修改当前计划',exact=True).click()
    expect(card.locator('input[value=read_first]')).to_be_checked()
    expect(card.locator('.plan-reason')).to_have_count(0)
    card.locator('input[value=try_first]').check()
    expect(card.locator('.plan-reason')).to_be_visible()
    expect(card.locator('button[type=submit]')).to_be_disabled()
    card.locator('input[value=read_first]').check()
    expect(card.locator('.plan-reason')).to_have_count(0)
    card.locator('input[value=try_first]').check()
    card.locator('input[value=found_problem]').check()
    Path('test-results').mkdir(exist_ok=True)
    page.screenshot(path='test-results/unified-plan-edit.png',full_page=True)
    card.locator('button[type=submit]').click()
    expect(card).not_to_be_visible()
    expect(page.locator('.center-experiment')).to_contain_text('14.333')
    page.get_by_role('button',name='使用新中心，计算下一轮',exact=True).click()
    expect(page.locator('.center-experiment')).to_contain_text('5.667')
    page.get_by_role('button',name='使用新中心，计算下一轮',exact=True).click()
    submit_first_result(page)
    expect(card).to_be_visible()
    expect(card.locator('input[value=try_first]')).to_be_checked()
    expect(card.locator('input[value=evidence]')).to_be_checked()
    expect(card.locator('.plan-reason')).to_have_count(0)
    card.locator('button[type=submit]').click()
    page.reload()
    expect(card.locator('input[value=try_first]')).to_be_checked()
    expect(card.locator('.plan-reason')).to_have_count(0)
    card.locator('button[type=submit]').click()
    history=page.evaluate("""async()=>{const r=await fetch('/api/projects/library-recommendation/plan-history',{headers:{'X-Session-ID':localStorage.getItem('orbit-session-v1')}});return r.json()}""")
    assert [r['version'] for r in history]==[4,3,2,1]
    assert history[2]['phase']=='during' and history[2]['reason']=='found_problem'
    assert history[1]['kind']=='carried_forward' and history[0]['kind']=='confirmed'
    blocks=page.locator('.prompt-blocks li')
    before=blocks.evaluate_all('(rows)=>rows.map(r=>r.dataset.step)')
    source=page.locator(f'.prompt-blocks li[data-step="{before[0]}"]')
    target=page.locator(f'.prompt-blocks li[data-step="{before[2]}"]')
    target.scroll_into_view_if_needed()
    box=target.bounding_box()
    source.drag_to(target,target_position={'x':30,'y':box['height']-4})
    after=blocks.evaluate_all('(rows)=>rows.map(r=>r.dataset.step)')
    assert after==[before[1],before[2],before[0],*before[3:]],after
    last=after[-1]
    page.locator(f'.prompt-blocks li[data-step="{last}"]').drag_to(blocks.first,target_position={'x':30,'y':3})
    assert blocks.first.get_attribute('data-step')==last
    expect(page.locator('.prompt-blocks li.moving')).to_have_count(0)
    expect(page.locator('.library-settings textarea').first).not_to_have_value('')
    page.get_by_role('button',name='保存配置',exact=True).click()
    assert not errors,errors
    browser.close()
    print('Unified plan initial choices, revision reason, in-task continuity, carry-forward, refresh and history passed.')
