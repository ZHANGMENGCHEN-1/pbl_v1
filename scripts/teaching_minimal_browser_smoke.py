"""Minimal robot-led entry and progressively revealed stages; frontend on 5174."""
from pathlib import Path
from playwright.sync_api import sync_playwright,expect


def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':1366,'height':900})
        errors=[];api=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:api.append(r.url) if '/api/' in r.url else None)
        page.goto('http://127.0.0.1:5174/projects/teaching-agent')
        expect(page.locator('.xiaozhi-speech')).to_contain_text('你好，我是小知')
        expect(page.locator('.teaching-chat')).to_have_count(0)
        expect(page.locator('.activity-preview-card')).to_have_count(0)
        expect(page.locator('textarea')).to_have_count(0)
        expect(page.locator('.current-activity-summary')).to_have_count(0)
        expect(page.locator('.minimal-scene')).not_to_contain_text('框架预览')
        expect(page.locator('.robot-3d-controls')).to_have_count(0)
        Path('test-results').mkdir(exist_ok=True)
        page.screenshot(path='test-results/teaching-minimal-hello.png',full_page=True)
        def welcome():
            page.get_by_role('button',name='你好，小知',exact=True).click()
            expect(page.locator('.xiaozhi-speech')).to_contain_text('图书馆')
            page.get_by_role('button',name='我们试试',exact=True).click()
        def more(item):
            page.get_by_role('button',name='更多',exact=True).click()
            page.get_by_role('menuitem',name=item,exact=True).click()
        welcome()
        card=page.locator('.calculation-card')
        expect(card).to_have_count(1)
        expect(page.get_by_role('button',name='计算这一轮',exact=True)).to_be_enabled()
        expect(card.locator('textarea')).to_have_count(0)
        page.get_by_role('spinbutton',name='开始的中心1',exact=True).fill('4')
        input=page.get_by_role('textbox',name='和小知说说你的问题',exact=True)
        input.fill('这里先保存问题')
        page.reload()
        expect(page.locator('.xiaozhi-speech')).to_contain_text('你好，我是小知')
        welcome()
        expect(page.get_by_role('spinbutton',name='开始的中心1',exact=True)).to_have_value('4')
        expect(input).to_have_value('这里先保存问题')
        input.dispatch_event('keydown',{'key':'Enter','isComposing':True,'bubbles':True})
        expect(page.get_by_role('button',name='暂停引导',exact=True)).to_have_count(0)
        input.fill('中心是什么意思？');input.press('Enter')
        expect(page.get_by_role('button',name='暂停引导',exact=True)).to_be_visible()
        expect(page.get_by_role('button',name='发送',exact=True)).to_be_visible(timeout=10000)
        expect(page.locator('.robot-chat-bubble')).to_contain_text('答疑还在准备中')
        expect(page.get_by_role('button',name='先看看下一步 →',exact=True)).to_have_count(0)
        more('功能说明')
        expect(page.locator('.el-message-box')).to_contain_text('后台真实计算')
        page.locator('.el-message-box').get_by_role('button',name='知道了',exact=True).click()
        page.set_viewport_size({'width':390,'height':844})
        page.wait_for_function('document.documentElement.scrollWidth<=innerWidth')
        more('重新开始')
        page.locator('.el-message-box').get_by_role('button',name='重新开始',exact=True).click()
        expect(page.locator('.xiaozhi-speech')).to_contain_text('你好，我是小知')
        expect(card).to_have_count(0)
        page.screenshot(path='test-results/teaching-minimal-mobile.png',full_page=True)
        assert not errors,errors
        assert all('/activities/group_books/state' in url for url in api),api
        browser.close()
        print('Passed minimal bubble entry, scenario before controls, hidden workspace/meta, progressive three-stage operations, draft restore, optional dialogue, honest pending actions, records in menu, reset and mobile.')


if __name__=='__main__':main()
