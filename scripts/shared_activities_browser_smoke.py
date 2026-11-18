"""Verify all class entries against isolated fixture :8001 and Vite :5174."""
import asyncio
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from playwright.async_api import async_playwright, expect
from teaching_measurement_helpers import complete_survey, set_rating


async def arrange(task, desired):
    for index, step in enumerate(desired):
        order = await task.locator('li').evaluate_all('(items)=>items.map(x=>x.dataset.stepId)')
        for _ in range(order.index(step) - index):
            await task.locator(f'li[data-step-id="{step}"] .move-buttons button').first.click()


async def main():
    Path('test-results').mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel='msedge', headless=True)
        for slug in ['learning-activities', 'teaching-agent', 'meaning-making']:
            page = await browser.new_page(viewport={'width': 1500, 'height': 1000})
            errors = []
            chat_requests = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: chat_requests.append(request.post_data_json) if request.url.endswith('/chat') else None)
            await page.goto('http://127.0.0.1:5174/projects/' + slug)
            await page.get_by_label('班级', exact=True).fill('测试班')
            await page.get_by_label('学号', exact=True).fill('001')
            await page.get_by_role('button', name='确认并继续', exact=True).click()
            dialog = page.get_by_role('dialog', name='开始前，你现在感觉怎么样？', exact=True)
            await expect(dialog).to_be_visible()
            for slider in await dialog.get_by_role('slider').all():
                await set_rating(slider, 4)
            await dialog.get_by_role('button', name='开始活动1', exact=True).click()
            if slug != 'learning-activities':
                await page.get_by_role('button', name='进入活动1', exact=True).click()
            nav = page.get_by_role('navigation', name='学习活动')
            tabs = nav.get_by_role('button')
            await expect(tabs.nth(1)).to_be_disabled()
            await expect(tabs.nth(2)).to_be_disabled()
            card = page.get_by_role('region', name='分组计算')
            # Delay real API responses to observe the parent navigation busy guard.
            async def delay(route):
                await asyncio.sleep(.25)
                await route.continue_()
            await page.route('**/activities/group_books/steps', delay)
            async with page.expect_response(lambda r: '/group_books/steps' in r.url and r.request.method == 'POST') as response:
                await card.get_by_role('button', name='计算这一轮', exact=True).click()
                await expect(tabs.nth(0)).to_be_disabled()
            result = await (await response.value).json()
            for _ in range(20):
                await expect(tabs.nth(0)).to_be_enabled()
                for index, book in enumerate(result['records']):
                    await card.locator('table select').nth(index).select_option(str(book['group'] + 1))
                await card.get_by_role('button', name='保存本轮分组作答', exact=True).click()
                if result['converged']:
                    await card.get_by_role('button', name='填写结果', exact=True).click()
                    break
                async with page.expect_response(lambda r: '/group_books/steps' in r.url and r.request.method == 'POST') as response:
                    await card.get_by_role('button', name='用新中心计算下一轮', exact=True).click()
                result = await (await response.value).json()
            for index, group in enumerate(result['groups']):
                await card.locator('form input').nth(index * 2).fill(str(group['count']))
                await card.locator('form input').nth(index * 2 + 1).fill(str(group['center']))
            await card.get_by_role('button', name='提交结果，进入活动2', exact=True).click()
            await complete_survey(page, 1, robot=slug != 'learning-activities')
            await expect(tabs.nth(0)).to_be_enabled()
            await expect(tabs.nth(1)).to_be_enabled()
            await expect(tabs.nth(2)).to_be_disabled()
            if slug == 'meaning-making':
                await expect(page.locator('.xiaozhi-speech .reflection-composer')).to_be_visible()
                await expect(page.get_by_label('和小知说说你的问题', exact=True)).to_have_count(1)
                assert len(chat_requests) == 1
                opening = chat_requests[0]
                assert opening['purpose'] == 'reflection_opening'
                assert opening['context']['screen'] == 'reflection'
                measurement_id = opening['context']['measurement_id']
                for text in ['刚才有些困惑。', '后来我换了一个想法。', '我还想继续了解。']:
                    await page.get_by_label('和小知说说你的问题', exact=True).fill(text)
                    await page.get_by_role('button', name='发送', exact=True).click()
                    await expect(tabs.nth(1)).to_be_disabled()
                    await expect(tabs.nth(1)).to_be_enabled()
                audit = await (await page.request.get('http://127.0.0.1:8898/audit')).json()
                stages = [row['context']['meaning_making'] for row in audit['chats'] if row['context'].get('meaning_making', {}).get('measurement_id') == measurement_id]
                assert [stage['response_mode'] for stage in sorted(stages, key=lambda s: s['dialogue_turn'])] == ['awareness', 'interpretation', 'guidance', 'open']
            else:
                assert not chat_requests
                await expect(page.get_by_label('和小知说说你的问题', exact=True)).to_have_count(0)
            await page.get_by_role('button', name='继续前往活动2', exact=True).click()
            if slug != 'learning-activities':
                await page.get_by_role('button', name='进入活动2', exact=True).click()
            task = page.get_by_role('region', name='算法步骤排序任务')
            if slug != 'learning-activities':
                await page.get_by_label('和小知说说你的问题', exact=True).fill('这四张卡片要怎么排？')
                await page.get_by_role('button', name='发送', exact=True).click()
                await expect(tabs.nth(0)).to_be_disabled()
                await expect(tabs.nth(0)).to_be_enabled()
                await expect(page.locator('.question-reply')).to_contain_text('四张步骤卡片')
                assert chat_requests[-1]['context']['screen'] == 'task'
                assert not chat_requests[-1]['context'].get('measurement_id')
                assert chat_requests[-1].get('purpose', 'question') == 'question'
            await arrange(task, ['calculate', 'centers', 'count', 'data'])
            await task.get_by_role('button', name='提交排序结果', exact=True).click()
            await expect(tabs.nth(2)).to_be_disabled()
            await arrange(task, ['data', 'count', 'centers', 'calculate'])
            await task.get_by_role('button', name='提交排序结果', exact=True).click()
            await complete_survey(page, 2, robot=slug != 'learning-activities')
            await expect(tabs.nth(2)).to_be_enabled()
            if slug == 'teaching-agent':
                await expect(page.get_by_label('和小知说说你的问题', exact=True)).to_have_count(0)
                await expect(page.get_by_label('小知的话', exact=True)).to_contain_text('活动2已完成')
            elif slug == 'meaning-making':
                await expect(page.locator('.xiaozhi-speech .reflection-composer')).to_be_visible()
            await page.get_by_role('button', name='继续前往活动3', exact=True).click()
            excel = page.get_by_role('region', name='二维聚类任务')
            book = Workbook()
            for row in [['次数', '时长'], [1, 2], [2, 3], [20, 30], [21, 31]]:
                book.active.append(row)
            raw = BytesIO()
            book.save(raw)
            await page.route('**/explore_2d/analyses', delay)
            await excel.get_by_label('上传Excel文件', exact=True).set_input_files({'name': 'test.xlsx', 'mimeType': 'application/octet-stream', 'buffer': raw.getvalue()})
            async def fail_once(route):
                await asyncio.sleep(.25)
                await route.fulfill(status=503, json={'detail': '测试计算失败，请重试。'})
            await page.route('**/explore_2d/analyses', fail_once, times=1)
            await excel.get_by_role('button', name='运行分组（K=2）', exact=True).click()
            await expect(tabs.nth(0)).to_be_disabled()
            await expect(excel.get_by_role('alert')).to_contain_text('测试计算失败')
            await expect(tabs.nth(0)).to_be_enabled()
            async with page.expect_response(lambda r: '/analyses' in r.url and r.request.method == 'POST'):
                await excel.get_by_role('button', name='运行分组（K=2）', exact=True).click()
                await expect(tabs.nth(0)).to_be_disabled()
            await expect(excel.locator('.scatter-view circle')).to_have_count(4)
            await expect(tabs.nth(0)).to_be_enabled()
            for field in await excel.locator('form input').all():
                await field.fill('2')
            await excel.locator('form textarea').fill('一组大，一组小')
            await excel.get_by_role('button', name='提交结果', exact=True).click()
            await complete_survey(page, 3, robot=slug != 'learning-activities')
            for tab in await tabs.all():
                await expect(tab).to_be_enabled()
                await expect(tab).to_contain_text('✓')
            await tabs.nth(0).click()
            await expect(card.locator('tbody tr')).to_have_count(5)
            await page.set_viewport_size({'width': 390, 'height': 844})
            assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            await page.screenshot(path=f'test-results/shared-{slug}.png', full_page=True)
            assert not errors, errors
            await page.close()
            print('Passed:', slug, flush=True)
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
