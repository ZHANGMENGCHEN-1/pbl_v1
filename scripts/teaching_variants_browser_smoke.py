"""Run with teaching_chat_fixture_server.py and Vite :5174 -> :8001.
Uses an isolated SQLite database and a local model test double, never paid models.
"""
import asyncio
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from playwright.async_api import async_playwright, expect
from teaching_measurement_helpers import complete_survey

BASE = 'http://127.0.0.1:5174'


async def identify(page, direct=False):
    await page.get_by_label('班级', exact=True).fill('七年级1班')
    await page.get_by_label('学号', exact=True).fill('001')
    await page.get_by_role('button', name='进入活动1' if direct else '确认并继续', exact=True).click()


async def arrange(task, desired):
    for index, id in enumerate(desired):
        order = await task.locator('li').evaluate_all('(items)=>items.map(x=>x.dataset.stepId)')
        for _ in range(order.index(id) - index):
            await task.locator(f'li[data-step-id="{id}"] .move-buttons button').first.click()


async def main():
    Path('test-results').mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel='msedge', headless=True, args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        page = await browser.new_page(viewport={'width': 1500, 'height': 1000})
        errors = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        await page.goto(BASE)
        await expect(page.locator('.home-project-card')).to_have_count(3)
        for slug in ['teaching-agent', 'meaning-making', 'learning-activities']:
            assert await page.locator(f'.home-project-card[href="/projects/{slug}"]').count() == 1
        await page.screenshot(path='test-results/learning-variants-home.png', full_page=True)
        for slug in ['teaching-agent', 'meaning-making']:
            await page.goto(BASE + '/projects/' + slug)
            await expect(page.get_by_label('小知的话', exact=True)).to_contain_text('你好，我是小知')
            await identify(page)
            await expect(page.get_by_label('小知的话', exact=True)).to_contain_text('图书馆想把')
            await page.get_by_role('button', name='进入活动1', exact=True).click()
            await page.get_by_role('button', name='计算这一轮', exact=True).click()
            await expect(page.locator('.calculation-card tbody tr')).to_have_count(5)
            if slug == 'meaning-making':
                await page.get_by_label('和小知说说你的问题', exact=True).fill('中心是什么？')
                await page.get_by_role('button', name='发送', exact=True).click()
                await expect(page.locator('.question-reply')).to_contain_text('距离')
                await expect(page.get_by_role('button', name='发送', exact=True)).to_be_visible()

        before = await (await page.request.get('http://127.0.0.1:8898/audit')).json()
        await page.goto(BASE + '/projects/learning-activities')
        assert await page.locator('.teaching-robot-view,.minimal-composer,.xiaozhi-speech,canvas').count() == 0
        await identify(page, direct=True)
        await expect(page.get_by_role('heading', name='活动1：给五本书分组', exact=True)).to_be_visible()
        nav = page.get_by_role('navigation', name='学习活动')
        await expect(nav.get_by_role('button', name='活动2：整理分组的方法')).to_be_disabled()
        await expect(nav.get_by_role('button', name='活动3：探索二维分组')).to_be_disabled()
        card = page.get_by_role('region', name='分组计算')
        await card.get_by_role('button', name='计算这一轮', exact=True).click()
        for i in range(5):
            await card.locator('table select').nth(i).select_option('1' if i < 2 else '2')
        await card.get_by_role('button', name='保存本轮分组作答', exact=True).click()
        await expect(card.get_by_role('status')).to_contain_text('本轮作答已保存')
        for _ in range(2):
            await card.get_by_role('button', name='用新中心计算下一轮', exact=True).click()
        await card.get_by_role('button', name='填写结果', exact=True).click()
        for i, value in enumerate(['3', '5.667', '2', '17']):
            await card.locator('form input').nth(i).fill(value)
        await card.get_by_role('button', name='提交结果，进入活动2', exact=True).click()
        await complete_survey(page,1,robot=False)
        await page.get_by_role('button',name='继续前往活动2',exact=True).click()
        task = page.get_by_role('region', name='算法步骤排序任务')
        await expect(task).to_be_visible()
        await arrange(task, ['calculate', 'centers', 'count', 'data'])
        await task.get_by_role('button', name='提交排序结果', exact=True).click()
        await expect(task.get_by_role('status')).to_contain_text('我再想想')
        await expect(nav.get_by_role('button', name='活动3：探索二维分组')).to_be_disabled()
        await arrange(task, ['data', 'count', 'centers', 'calculate'])
        await task.get_by_role('button', name='提交排序结果', exact=True).click()
        await complete_survey(page,2,robot=False)
        await page.get_by_role('button', name='继续前往活动3', exact=True).click()
        excel = page.get_by_role('region', name='二维聚类任务')
        book = Workbook()
        for row in [['名称', '借阅次数', '借阅时长'], ['甲', 2, 5], ['乙', 4, 7], ['丙', 20, 30], ['丁', 22, 32]]:
            book.active.append(row)
        raw = BytesIO()
        book.save(raw)
        await excel.get_by_label('上传Excel文件', exact=True).set_input_files({'name': '学习活动.xlsx', 'mimeType': 'application/octet-stream', 'buffer': raw.getvalue()})
        await excel.get_by_role('button', name='运行分组（K=2）', exact=True).click()
        await expect(excel.locator('.scatter-view circle')).to_have_count(4)
        for i in range(2):
            await excel.locator('form input').nth(i).fill('2')
        await excel.locator('form textarea').fill('一组借阅次数和时长较少，另一组较多。')
        await excel.get_by_role('button', name='提交结果', exact=True).click()
        await complete_survey(page,3,robot=False)
        await page.locator('.activities-header').get_by_role('button', name='查看学习记录', exact=True).click()
        await expect(page.get_by_role('region', name='学习记录')).to_contain_text('两组数量：2、2')
        await page.get_by_role('button', name='Close this dialog').click()
        assert '小知' not in await page.locator('body').inner_text()
        await page.screenshot(path='test-results/learning-activities-completed.png', full_page=True)
        audit = await (await page.request.get('http://127.0.0.1:8898/audit')).json()
        assert len(audit['requests']) == len(before['requests'])
        assert {r['source_route'] for r in audit['students']} == {'teaching-agent', 'meaning-making', 'learning-activities'}
        pure = next(r for r in audit['students'] if r['source_route'] == 'learning-activities')
        submissions = [r for r in audit['submissions'] if r['session'] == pure['session']]
        assert len(submissions) == 4
        assert {r['activity'] for r in submissions} == {'group_books', 'explain_algorithm', 'explore_2d'}
        assert all(r['student_number'] == '001' for r in submissions)
        assert not any(r['session'] == pure['session'] for r in audit['chats'])
        assert len([r for r in audit['round_answers'] if r['session'] == pure['session']]) == 1
        await nav.get_by_role('button', name='活动1：给五本书分组').click()
        await expect(card.locator('tbody tr')).to_have_count(5)
        await expect(card.get_by_role('button', name='填写结果', exact=True)).to_be_visible()
        mobile = await browser.new_page(viewport={'width': 390, 'height': 844})
        await mobile.goto(BASE + '/projects/learning-activities')
        await expect(mobile.get_by_label('班级', exact=True)).to_be_visible()
        assert await mobile.evaluate('document.documentElement.scrollWidth<=innerWidth')
        await mobile.screenshot(path='test-results/learning-activities-mobile.png', full_page=True)
        assert not errors, errors
        await browser.close()
        print('Passed: three home links, original/copy onboarding and chat, direct task onboarding, all three activities, incorrect and correct sorting attempts, owned database evidence, zero pure-mode model calls, review and mobile layout.')


if __name__ == '__main__':
    asyncio.run(main())
