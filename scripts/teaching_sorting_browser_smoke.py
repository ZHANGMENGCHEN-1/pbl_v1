"""Real activity1 API -> activity2 shuffle, drag, feedback, submission, fresh reload.
Use isolated backend :8001 and Vite :5174 with API_TARGET pointing to :8001.
"""
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
        await card.get_by_role('button',name='计算这一轮').click()
        await card.get_by_role('button',name='用新中心计算下一轮').click()
        await card.get_by_role('button',name='用新中心计算下一轮').click()
        await card.get_by_role('button',name='填写结果',exact=True).click()
        for i,value in enumerate(['3','5.667','2','17']):
            await card.locator('form input').nth(i).fill(value)
        await card.get_by_role('button',name='提交结果，进入活动2').click()
        await expect(page.locator('.xiaozhi-speech')).to_contain_text('用自己的话')
        await page.get_by_role('button',name='进入活动2',exact=True).click()
        task=page.get_by_role('region',name='算法步骤排序任务')
        await expect(task.get_by_role('heading')).to_have_text('任务目标：总结K均值算法流程')
        assert await page.locator('.robot-chat-bubble').count()==0
        ids=['data','count','centers','calculate']
        initial=await task.locator('li').evaluate_all('(items)=>items.map(x=>x.dataset.stepId)')
        assert initial!=ids and sorted(initial)==sorted(ids)
        await task.get_by_role('button',name='提交排序结果').click()
        await expect(page.locator('.robot-chat-bubble')).to_contain_text('调整后可以再提交')
        assert await page.get_by_role('button',name='进入活动3 →').count()==0
        # Real HTML drag events via Playwright, not direct state mutation.
        for index,id in enumerate(ids):
            current=await task.locator('li').evaluate_all('(items)=>items.map(x=>x.dataset.stepId)')
            if current[index]!=id:
                await task.locator(f'li[data-step-id="{id}"]').drag_to(task.locator('li').nth(index))
        assert await task.locator('li').evaluate_all('(items)=>items.map(x=>x.dataset.stepId)')==ids
        await task.get_by_role('button',name='提交排序结果').click()
        await expect(page.locator('.robot-chat-bubble')).to_contain_text('你的排序已经提交了')
        await expect(page.get_by_role('button',name='进入活动3 →')).to_be_visible()
        Path('test-results').mkdir(exist_ok=True)
        await page.screenshot(path='test-results/teaching-sorting-feedback.png',full_page=True)
        await page.get_by_role('button',name='更多',exact=True).click()
        await page.get_by_role('menuitem',name='学习记录',exact=True).click()
        await expect(page.locator('.teaching-record-card').nth(1).locator('.preview-submission')).to_have_count(2)
        await page.keyboard.press('Escape')
        await page.get_by_role('button',name='进入活动3 →').click()
        await expect(page.locator('.xiaozhi-speech')).to_contain_text('借阅次数和借阅时长')
        await page.reload()
        await expect(page.locator('.xiaozhi-speech')).to_contain_text('你好，我是小知')
        await page.get_by_role('button',name='你好，小知',exact=True).click()
        await page.get_by_role('button',name='我们试试',exact=True).click()
        await expect(page.get_by_role('button',name='计算这一轮')).to_be_visible()
        await expect(page.locator('.calculation-card table')).to_have_count(0)
        assert not errors,errors
        await browser.close()
        print('Passed: real activity1 submission, dialogue transition, empty initial bubble, shuffled four cards, drag sorting, specific retry feedback, immutable attempt records, activity3 and fresh reload.')

if __name__=='__main__':asyncio.run(main())
