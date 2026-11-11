"""End-to-end against isolated backend :8001 + Vite :5174, no LLM calls."""
import asyncio
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from playwright.async_api import async_playwright, expect


def workbook(rows):
    book=Workbook()
    for row in rows:
        book.active.append(row)
    stream=BytesIO()
    book.save(stream)
    return stream.getvalue()


async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(channel='msedge',headless=True,args=['--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page=await browser.new_page(viewport={'width':1600,'height':1100})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto('http://127.0.0.1:5174/projects/teaching-agent')
        await page.get_by_role('button',name='你好，小知',exact=True).click()
        await page.get_by_role('button',name='我们试试',exact=True).click()
        card=page.get_by_role('region',name='分组计算')
        await card.get_by_role('button',name='计算这一轮').click()
        for _ in range(2):await card.get_by_role('button',name='用新中心计算下一轮').click()
        await card.get_by_role('button',name='填写结果',exact=True).click()
        for i,value in enumerate(['3','5.667','2','17']):await card.locator('form input').nth(i).fill(value)
        await card.get_by_role('button',name='提交结果，进入活动2').click()
        await page.get_by_role('button',name='进入活动2',exact=True).click()
        sorting=page.get_by_role('region',name='算法步骤排序任务')
        for index,id in enumerate(['data','count','centers','calculate']):
            current=await sorting.locator('li').evaluate_all('(items)=>items.map(x=>x.dataset.stepId)')
            if current[index]!=id:await sorting.locator(f'li[data-step-id="{id}"]').drag_to(sorting.locator('li').nth(index))
        await sorting.get_by_role('button',name='提交排序结果').click()
        await expect(sorting.get_by_role('status')).to_have_text('提交成功！')
        await page.get_by_role('button',name='进入活动3 →').click()
        await page.get_by_role('button',name='准备一张表格').click()
        task=page.get_by_role('region',name='二维聚类任务')
        await expect(task.get_by_role('tab',name='上传与运行')).to_have_attribute('aria-selected','true')
        await expect(task.get_by_role('tab',name='看看分组结果',exact=True)).to_be_disabled()
        assert await page.locator('.robot-chat-bubble').count()==0
        file=task.get_by_label('上传Excel文件',exact=True)
        await file.set_input_files({'name':'坏表.xlsx','mimeType':'application/octet-stream','buffer':b'bad file'})
        await expect(task.get_by_role('alert')).to_contain_text('无法读取')
        rows=[['书名','借阅次数','借阅时长']]+[[f'书{i+1}',(i%75)+1+(100 if i>=75 else 0),(i%75)*2+(200 if i>=75 else 0)] for i in range(150)]+[['缺次数',None,10],['文字次数','很多',5]]
        raw=workbook(rows)
        await file.set_input_files({'name':'课堂数据.xlsx','mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','buffer':raw})
        await expect(task.locator('.dataset-heading')).to_contain_text('152条记录')
        await expect(task.locator('.preview-table th')).to_have_text(['借阅次数','借阅时长'])
        await expect(task.get_by_label('横轴用哪一列？',exact=True)).to_have_value('c1')
        await expect(task.get_by_label('纵轴用哪一列？',exact=True)).to_have_value('c2')
        assert await task.locator('.scatter-view').count()==0
        await task.get_by_text('哪些记录没有参与？',exact=True).click()
        await expect(task.locator('.data-quality')).to_contain_text('Excel第152行')
        await expect(task.locator('.data-quality')).to_contain_text('Excel第153行')
        async with page.expect_response(lambda r:'/explore_2d/analyses' in r.url and r.request.method=='POST') as computed:
            await task.get_by_role('button',name='运行分组（K=2）').click()
        analysis=await (await computed.value).json()
        await expect(task.get_by_role('tab',name='看看分组结果',exact=True)).to_have_attribute('aria-selected','true')
        await expect(task.locator('.preview-table')).not_to_be_visible()
        await expect(task.locator('.scatter-view circle')).to_have_count(150)
        assert [f['name'] for f in analysis['features']]==['借阅次数','借阅时长']
        assert sum(g['count'] for g in analysis['groups'])==150
        await expect(page.locator('.robot-chat-bubble')).to_contain_text('横轴是“借阅次数”')
        chart=task.get_by_role('region',name='分组散点图')
        assert await chart.locator('select,.original-record').count()==0
        ticks=await chart.locator('.chart-grid text').all_text_contents()
        assert all(float(t.replace(',','')).is_integer() for t in ticks)
        assert ticks.count('0')==2
        form=task.get_by_role('form',name='提交二维分组结果')
        for i in range(2):assert await form.locator('input').nth(i).input_value()==''
        assert await form.locator('textarea').input_value()==''
        # No point interaction or exact-match grading is required to submit.
        for i,value in enumerate(['149','1']):await form.locator('input').nth(i).fill(value)
        await form.locator('textarea').fill('一组借阅次数少、时长短，另一组次数多、时长长。')
        await task.get_by_role('tab',name='上传与运行').click()
        await expect(task.locator('.preview-table')).to_be_visible()
        await expect(task.locator('.scatter-view')).not_to_be_visible()
        await task.get_by_role('tab',name='看看分组结果',exact=True).click()
        await expect(form.locator('input').nth(0)).to_have_value('149')
        await expect(form.locator('textarea')).to_have_value('一组借阅次数少、时长短，另一组次数多、时长长。')
        async with page.expect_response(lambda r:'/explore_2d/submissions' in r.url) as submitted:
            await form.get_by_role('button',name='提交结果',exact=True).click()
        record=await (await submitted.value).json()
        await expect(form.get_by_role('status')).to_have_text('提交成功！')
        assert record['payload']['student_result']['counts']==[149,1]
        assert record['payload']['tool_result']['counts']==[g['count'] for g in analysis['groups']]
        graph_box=await task.locator('.analysis-result').bounding_box()
        form_box=await form.bounding_box()
        assert form_box['x']>graph_box['x']+graph_box['width']-1
        assert abs(form_box['y']-graph_box['y'])<5
        Path('test-results').mkdir(exist_ok=True)
        await task.locator('.results-and-submission').screenshot(path='test-results/teaching-excel-results.png')
        # Selecting another column invalidates the plot and reruns only that selection.
        await task.get_by_role('tab',name='上传与运行').click()
        await task.get_by_label('横轴用哪一列？',exact=True).select_option('c0')
        await expect(task.locator('.scatter-view')).to_have_count(0)
        await expect(task.locator('.data-quality')).to_contain_text('至少需要2条完整的数值记录')
        await expect(task.get_by_role('tab',name='看看分组结果',exact=True)).to_be_disabled()
        await expect(task.get_by_role('button',name='运行分组（K=2）')).to_be_disabled()
        await file.set_input_files({'name':'重合数据.xlsx','mimeType':'application/octet-stream','buffer':workbook([['x','y'],[1,2],[1,2]])})
        await task.get_by_role('button',name='运行分组（K=2）').click()
        await expect(task.get_by_role('alert')).to_contain_text('重合')
        assert await task.locator('.scatter-view').count()==0
        await page.set_viewport_size({'width':390,'height':844})
        overflow=await page.evaluate("Array.from(document.querySelectorAll('body *')).map(e=>({tag:e.tagName,cls:e.className,left:e.getBoundingClientRect().left,right:e.getBoundingClientRect().right})).filter(e=>e.right>innerWidth+1||e.left < -1).slice(0,20)")
        assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),overflow
        assert not errors,errors
        await browser.close()
        print('Passed: 150-point real Excel upload/preview, exclusions, selected axes, true computation, plot, record inspection, side-by-side manual submission, invalidation, corrupt/coincident data errors and mobile.')


if __name__=='__main__':asyncio.run(main())
