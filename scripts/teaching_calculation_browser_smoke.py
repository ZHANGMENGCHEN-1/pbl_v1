"""Run against Vite :5174 proxying the isolated backend :8001."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, expect

async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(channel='msedge',headless=True,args=['--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page=await browser.new_page(viewport={'width':1440,'height':1000})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto('http://127.0.0.1:5174/projects/teaching-agent')
        await page.get_by_role('button',name='你好，小知',exact=True).click()
        await page.get_by_role('button',name='我们试试',exact=True).click()
        card=page.get_by_role('region',name='分组计算')
        await card.locator('input').nth(0).fill('2')
        await card.locator('input').nth(1).fill('11')
        await card.get_by_role('button',name='计算这一轮',exact=True).click()
        await expect(card.get_by_role('spinbutton',name='第1组的新中心',exact=True)).to_have_value('')
        await card.get_by_role('button',name='用新中心计算下一轮').click()
        await expect(card.get_by_text('第1组：2、6、9，共3本。',exact=True)).to_be_visible()
        await card.get_by_role('button',name='用新中心计算下一轮').click()
        await expect(card.get_by_text('分组和中心都没有变化',exact=False)).to_be_visible()
        assert await card.locator('select').count()==0
        assert await card.get_by_role('button',name='重新选中心').count()==0
        await expect(card.get_by_role('spinbutton',name='第1组的新中心',exact=True)).to_have_value('')
        await card.get_by_text('查看前面的计算',exact=True).click()
        await card.get_by_role('button',name='第1轮',exact=True).click()
        await card.get_by_role('spinbutton',name='第1组的新中心',exact=True).fill('4')
        await card.get_by_role('button',name='回到最新一轮',exact=True).click()
        await expect(card.get_by_role('spinbutton',name='第1组的新中心',exact=True)).to_have_value('')
        flow=await page.locator('.xiaozhi-speech').inner_text()
        await page.locator('.robot-stage textarea').fill('怎么计算？')
        await page.get_by_role('button',name='发送',exact=True).click()
        await expect(page.locator('.robot-chat-bubble')).to_contain_text('答疑还在准备中')
        assert await page.locator('.xiaozhi-speech').inner_text()==flow
        await expect(page.get_by_role('button',name='发送',exact=True)).to_be_visible()
        await page.screenshot(path='test-results/teaching-calculation-new-layout.png',full_page=True)
        await card.get_by_role('button',name='填写结果',exact=True).click()
        inputs=card.locator('form input')
        for i in range(4):
            assert await inputs.nth(i).input_value()==''
        # Intentionally different from the actual answer: no correctness gate.
        for i,value in enumerate(['4','1','1','18']):
            await inputs.nth(i).fill(value)
        await card.get_by_role('button',name='提交结果，进入活动2').click()
        await expect(page.locator('.xiaozhi-speech')).to_contain_text('步骤')
        stored=await page.evaluate("JSON.parse(localStorage.getItem('orbit-teaching-agent-learning-v1'))")
        assert stored['activeActivityId']=='explain_algorithm'
        record=stored['activities']['group_books']['submissions'][0]['payload']['calculation']
        assert record['payload']['student_result']=={'counts':[4,1],'centers':[1,18]}
        assert record['payload']['tool_result']['counts']==[3,2]
        response=await page.request.get('http://127.0.0.1:5174/api/projects/teaching-agent/activities/group_books/state',headers={'X-Session-ID':stored['sessionId']})
        server=await response.json()
        assert len(server['steps'])==3 and len(server['submissions'])==1
        await page.reload()
        await page.get_by_role('button',name='你好，小知',exact=True).click()
        await page.get_by_role('button',name='继续学习',exact=True).click()
        await expect(page.locator('.xiaozhi-speech')).to_contain_text('步骤')
        await page.get_by_role('button',name='更多',exact=True).click()
        await page.get_by_role('menuitem',name='学习记录',exact=True).click()
        await expect(page.get_by_text('我的填写：两组各4、1本；中心1、18。')).to_be_visible()
        Path('test-results').mkdir(exist_ok=True)
        await page.screenshot(path='test-results/teaching-calculation-records.png',full_page=True)
        assert not errors, errors
        await browser.close()
        print('Passed browser: three real rounds, review, empty manual fields, non-matching answer accepted, server storage, stage2 and reload.')

if __name__=='__main__':asyncio.run(main())
