"""Use teaching_chat_fixture_server.py and Vite :5174 -> backend :8001.
Tests real browser -> FastAPI -> ChatOpenAI -> local HTTP SSE test double.
"""
import asyncio
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from playwright.async_api import async_playwright,expect


async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(channel='msedge',headless=True,args=['--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page=await browser.new_page(viewport={'width':1500,'height':1000})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto('http://127.0.0.1:5174/projects/teaching-agent')
        await page.get_by_role('button',name='你好，小知',exact=True).click()
        await page.get_by_role('button',name='我们试试',exact=True).click()
        card=page.get_by_role('region',name='分组计算')
        await card.get_by_role('button',name='计算这一轮').click()
        input=page.get_by_role('textbox',name='和小知说说你的问题',exact=True)
        async def ask(text):
            await input.fill(text);await page.get_by_role('button',name='发送',exact=True).click()
        await ask('距离是什么意思？')
        await expect(page.locator('.teaching-robot-view')).to_have_attribute('data-mood','thinking')
        await expect(page.locator('.robot-chat-bubble .question-reply')).to_contain_text('数轴')
        assert await page.locator('.robot-chat-bubble .task-guidance').count()==0
        partial=await page.locator('.question-reply').inner_text()
        await expect(page.get_by_role('button',name='发送',exact=True)).to_be_visible()
        assert len(await page.locator('.question-reply').inner_text())>len(partial)
        await ask('测试暂停')
        await expect(page.locator('.question-reply')).to_contain_text('验证暂停')
        await page.get_by_role('button',name='暂停回复',exact=True).click()
        await expect(page.locator('.robot-chat-bubble')).to_contain_text('已暂停回复')
        paused=await page.locator('.question-reply').inner_text()
        await page.wait_for_timeout(650)
        assert await page.locator('.question-reply').inner_text()==paused
        for _ in range(15):
            audit=await (await page.request.get('http://127.0.0.1:8898/audit')).json()
            record=next((r for r in audit['chats'] if r['question']=='测试暂停'),None)
            if record and record['status']=='cancelled':break
            await page.wait_for_timeout(100)
        assert record and record['status']=='cancelled',record
        assert record['answer'] and paused.startswith(record['answer'][:6])
        await ask('测试错误')
        await expect(page.locator('.chat-error')).to_contain_text('没有完成')
        assert 'private-provider-details' not in await page.locator('.chat-error').inner_text()
        await ask('测试长回复')
        await expect(page.get_by_role('button',name='发送',exact=True)).to_be_visible(timeout=15000)
        assert len(await page.locator('.question-reply').inner_text())==100
        await card.get_by_role('button',name='用新中心计算下一轮').click()
        await card.get_by_role('button',name='用新中心计算下一轮').click()
        await card.get_by_role('button',name='填写结果',exact=True).click()
        for i,value in enumerate(['3','5.667','2','17']):await card.locator('form input').nth(i).fill(value)
        await card.get_by_role('button',name='提交结果，进入活动2').click()
        await expect(page.locator('.xiaozhi-speech')).to_contain_text('用自己的话')
        await ask('我还不太会总结步骤。')
        await expect(page.get_by_role('button',name='发送',exact=True)).to_be_visible()
        await expect(page.locator('.xiaozhi-speech .dialogue-reply')).to_be_visible()
        assert await page.locator('.algorithm-task').count()==0  # LLM cannot open or advance tasks.
        await page.get_by_role('button',name='进入活动2',exact=True).click()
        assert await page.locator('.robot-chat-bubble').count()==0
        task=page.get_by_role('region',name='算法步骤排序任务')
        for i,id in enumerate(['data','count','centers','calculate']):
            order=await task.locator('li').evaluate_all('(items)=>items.map(x=>x.dataset.stepId)')
            if order[i]!=id:await task.locator(f'li[data-step-id="{id}"]').drag_to(task.locator('li').nth(i))
        await task.get_by_role('button',name='提交排序结果').click()
        await page.get_by_role('button',name='进入活动3 →').click()
        await page.get_by_role('button',name='准备一张表格',exact=True).click()
        excel=page.get_by_role('region',name='二维聚类任务')
        assert await page.locator('.robot-chat-bubble').count()==0
        book=Workbook()
        for row in [['书名','借阅次数','借阅时长'],['甲',2,5],['乙',4,7],['丙',20,30],['丁',22,32]]:book.active.append(row)
        raw=BytesIO();book.save(raw)
        await excel.get_by_label('上传Excel文件',exact=True).set_input_files({'name':'小知真实数据.xlsx','mimeType':'application/octet-stream','buffer':raw.getvalue()})
        await excel.get_by_role('button',name='运行分组（K=2）').click()
        await expect(excel.locator('.scatter-view circle')).to_have_count(4)
        # No click on the scatter plot before asking: real point facts are supplied by the platform.
        await ask('表格的一行怎么变成图里的一个点？')
        await expect(page.get_by_role('button',name='发送',exact=True)).to_be_visible()
        await expect(page.locator('.question-reply')).to_contain_text('两个数一起确定图上的一个点')
        audit=await (await page.request.get('http://127.0.0.1:8898/audit')).json()
        current=next(r for r in audit['chats'] if r['question']=='表格的一行怎么变成图里的一个点？')
        context=current['context']['analysis']
        assert context['verified_from']=='database_real_kmeans'
        assert [f['name'] for f in context['axes']]==['借阅次数','借阅时长']
        assert context['sample_count']==4 and sorted(g['center'] for g in context['groups'])==[[3,6],[21,31]]
        first=next(r for r in audit['chats'] if r['question']=='距离是什么意思？')
        assert first['context']['calculation']['centers_after']==[4,43/3]
        assert all(len(r['answer'])<=100 for r in audit['chats'])
        assert all(request['stream'] is True and 'tools' not in request for request in audit['requests'])
        assert all(message.get('role')!='tool' for request in audit['requests'] for message in request['messages'])
        assert current['status']=='completed'
        Path('test-results').mkdir(exist_ok=True)
        await page.screenshot(path='test-results/teaching-live-chat.png',full_page=True)
        assert not errors,errors
        await browser.close()
        print('Passed: real HTTP/SSE model integration, incremental reply, thinking, upstream cancellation, errors, 100-char cap, three activity contexts, verified actual results and platform-only progression. Provider is a local test double, not a live paid model.')


if __name__=='__main__':asyncio.run(main())
