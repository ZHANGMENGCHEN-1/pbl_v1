"""A/B/C full activity flows. Requires the isolated teaching HTTP fixture on :8001."""
import asyncio
import json
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from playwright.async_api import async_playwright, expect
from teaching_measurement_helpers import complete_self_report, complete_survey, set_rating


async def main():
    Path('test-results').mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser=await p.chromium.launch(channel='msedge',headless=True,args=['--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        for class_name,slug in [('A班','learning-activities'),('B班','teaching-agent'),('C班','meaning-making')]:
            page=await browser.new_page(viewport={'width':1440,'height':1000})
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            await page.goto('http://127.0.0.1:5174/projects/'+slug)
            await page.get_by_label('班级',exact=True).fill(class_name)
            await page.get_by_label('学号',exact=True).fill('009')
            robot=slug!='learning-activities'
            await page.get_by_role('button',name='确认并继续',exact=True).click()
            await complete_self_report(page)
            if robot:await page.get_by_role('button',name='进入活动1',exact=True).click()
            card=page.get_by_role('region',name='分组计算')
            await card.get_by_role('button',name='计算这一轮',exact=True).click()
            for _ in range(2):await card.get_by_role('button',name='用新中心计算下一轮',exact=True).click()
            await card.get_by_role('button',name='填写结果',exact=True).click()
            for i,value in enumerate(['3','5.667','2','17']):await card.locator('form input').nth(i).fill(value)
            await card.get_by_role('button',name='提交结果，进入活动2',exact=True).click()

            async def survey(number,ratings):
                dialog=page.get_by_role('dialog',name=f'活动{number}：你的感受怎么样？',exact=True)
                await expect(dialog).to_be_visible()
                await expect(dialog.get_by_role('slider')).to_have_count(4)
                assert await dialog.locator('input[aria-valuetext^="\u5c1a\u672a\u4f5c\u7b54"]').count()==4
                assert await page.locator('.minimal-operation,.calculation-card,.algorithm-task,.excel-task').count()==0
                if not robot:
                    assert '小知' not in await page.locator('body').inner_text()
                    assert await page.locator('.teaching-robot-view,canvas,.minimal-composer').count()==0
                    await expect(page.get_by_role('region',name='活动回顾')).to_be_visible()
                else:
                    assert await page.locator('.minimal-scene.dialogue-focus').count()==1
                await dialog.get_by_role('button',name='保存并与小知交流' if robot else '保存学习感受',exact=True).click()
                await expect(dialog.get_by_role('alert')).to_contain_text('请为四个问题')
                if number==1:
                    midpoint=dialog.get_by_role('slider').first
                    await midpoint.click()
                    await expect(midpoint).to_have_value('3')
                    await expect(dialog.locator('input[aria-valuetext^="\u5c1a\u672a\u4f5c\u7b54"]')).to_have_count(3)
                    edge=dialog.get_by_role('slider').nth(1)
                    await edge.press('End')
                    await expect(edge).to_have_value('5')
                    await edge.press('Home')
                    await expect(edge).to_have_value('1')
                    await page.screenshot(path=f'test-results/{slug}-sliders.png',full_page=True)
                    if not robot:
                        await page.set_viewport_size({'width':390,'height':844})
                        assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                        await page.screenshot(path='test-results/state-sliders-mobile.png',full_page=True)
                        await page.set_viewport_size({'width':1440,'height':1000})
                    # Verify an unsaved survey remains open when the backend is unavailable.
                    await page.route('**/state-measurements',lambda route:route.fulfill(status=503,content_type='application/json',body=json.dumps({'detail':'retry-test'})),times=1)
                    for i,point in enumerate(ratings):await set_rating(dialog.locator('fieldset').nth(i).get_by_role('slider'),point)
                    await dialog.get_by_role('button',name='保存并与小知交流' if robot else '保存学习感受',exact=True).click()
                    await expect(dialog.get_by_role('alert')).to_contain_text('retry-test')
                await complete_survey(page,number,robot,ratings)
                if slug=='meaning-making':
                    await expect(page.locator('.xiaozhi-speech .minimal-composer')).to_have_count(1)
                    await expect(page.locator('.robot-stage .minimal-composer')).to_have_count(0)
                    await expect(page.get_by_label('和小知说说你的问题',exact=True)).to_have_count(1)
                    await expect(page.locator('.dialogue-reply')).to_be_visible(timeout=20000)
                    await expect(page.get_by_role('button',name='发送',exact=True)).to_be_visible(timeout=20000)
                    text=await page.locator('.dialogue-reply').inner_text()
                    assert 0<len(text)<=100 and '？' in text
                if number==1:await page.screenshot(path=f'test-results/{slug}-reflection.png',full_page=True)

            await survey(1,(4,2,3,5))
            if slug=='meaning-making':
                await page.get_by_label('和小知说说你的问题',exact=True).fill('我不太理解中心怎么更新。')
                await page.get_by_role('button',name='发送',exact=True).click()
                await expect(page.get_by_role('button',name='发送',exact=True)).to_be_visible(timeout=20000)
                assert len(await page.locator('.dialogue-reply').inner_text())<=100
            await page.get_by_role('button',name='继续前往活动2',exact=True).click()
            if robot:await page.get_by_role('button',name='进入活动2',exact=True).click()
            task=page.get_by_role('region',name='算法步骤排序任务')
            if robot:
                await expect(page.locator('.robot-chat-bubble')).to_contain_text('四张步骤卡片')
                await page.get_by_label('和小知说说你的问题',exact=True).fill('这一步怎么做？')
                await page.get_by_role('button',name='发送',exact=True).click()
                await expect(page.locator('.question-reply')).to_contain_text('四张步骤卡片')
                await expect(page.get_by_role('button',name='发送',exact=True)).to_be_visible()
            async def arrange(desired):
                for index,id in enumerate(desired):
                    order=await task.locator('li').evaluate_all('(items)=>items.map(x=>x.dataset.stepId)')
                    for _ in range(order.index(id)-index):await task.locator(f'li[data-step-id="{id}"] .move-buttons button').first.click()
            await arrange(['calculate','centers','count','data'])
            await task.get_by_role('button',name='提交排序结果',exact=True).click()
            await expect(task.get_by_role('status')).to_contain_text('我再想想')
            assert await page.locator('.state-measurement').count()==0
            await arrange(['data','count','centers','calculate'])
            await task.get_by_role('button',name='提交排序结果',exact=True).click()
            await survey(2,(1,5,1,5))
            await page.get_by_role('button',name='继续前往活动3',exact=True).click()
            if robot:await page.get_by_role('button',name='准备一张表格',exact=True).click()
            excel=page.get_by_role('region',name='二维聚类任务')
            book=Workbook()
            for row in [['名称','借阅次数','借阅时长'],['甲',2,5],['乙',4,7],['丙',20,30],['丁',22,32]]:book.active.append(row)
            raw=BytesIO();book.save(raw)
            await excel.get_by_label('上传Excel文件',exact=True).set_input_files({'name':class_name+'.xlsx','mimeType':'application/octet-stream','buffer':raw.getvalue()})
            await excel.get_by_role('button',name='运行分组（K=2）',exact=True).click()
            await expect(excel.locator('.scatter-view circle')).to_have_count(4)
            await excel.locator('form input').nth(0).fill('1')
            await excel.locator('form input').nth(1).fill('2')
            await excel.locator('form textarea').fill('一组较少，另一组较多。')
            await excel.get_by_role('button',name='提交结果',exact=True).click()
            await expect(excel.locator('form .submission-error')).to_contain_text('合计4条')
            assert await page.locator('.state-measurement').count()==0
            await excel.locator('form input').nth(0).fill('2')
            await excel.get_by_role('button',name='提交结果',exact=True).click()
            await survey(3,(1,1,1,1))
            if robot:await page.locator('.speech-actions').get_by_role('button',name='查看学习记录',exact=True).click()
            else:await page.locator('.activities-header').get_by_role('button',name='查看学习记录',exact=True).click()
            await expect(page.get_by_role('dialog',name='学习记录',exact=True)).to_be_visible()
            audit=await (await page.request.get('http://127.0.0.1:8898/audit')).json()
            student=next(r for r in audit['students'] if r['source_route']==slug and r['class_name']==class_name and r['student_number']=='009')
            measurements=[r for r in audit['measurements'] if r['session']==student['session']]
            assert len(measurements)==3
            assert {r['activity'] for r in measurements}=={'group_books','explain_algorithm','explore_2d'}
            assert all(r['class_name']==class_name and r['student_number']=='009' and r['created'] for r in measurements)
            chats=[r for r in audit['chats'] if r['session']==student['session']]
            if slug=='meaning-making':
                assert len(chats)==5 and all(r['status']=='completed' for r in chats)
                meaningful=[r for r in chats if 'meaning_making' in r['context']]
                assert [r['context']['meaning_making']['strategy'] for r in meaningful]==['Content','Content','Task','Self']
                assert all(r['prompt_version']=='meaning-making-v1' for r in meaningful)
                assert sum(r['context']['question_source']=='platform' for r in meaningful)==3
            elif robot:
                assert len(chats)==1 and 'meaning_making' not in chats[0]['context']
            else:
                assert not chats
            if robot:
                task_chat=next(r for r in chats if r['question']=='这一步怎么做？')
                assert task_chat['context']['current_task']['number']==2
                assert task_chat['context']['current_task']['screen']=='task'
                assert len(task_chat['context']['student_draft_order'])==4
            assert not errors,errors
            await page.close()
        await browser.close()
        print('Passed: A/B/C three-activity measurements, focused screens, validation and retry, identity-linked database evidence, C automatic strategy openings/follow-up <=100 chars, and no unintended A/B model calls.')


if __name__=='__main__':asyncio.run(main())
