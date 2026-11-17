"""Check all three classes against Vite :5174 and isolated backend :8001."""
import asyncio

from playwright.async_api import async_playwright, expect


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel='msedge', headless=True)
        for project in ('learning-activities', 'teaching-agent', 'meaning-making'):
            page = await browser.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.goto(f'http://127.0.0.1:5174/projects/{project}')
            await page.get_by_label('班级', exact=True).fill('分组流程测试班')
            await page.get_by_label('学号', exact=True).fill('001')
            if project != 'learning-activities':
                await page.get_by_role('button', name='确认并继续', exact=True).click()
            await page.get_by_role('button', name='进入活动1', exact=True).click()
            card = page.get_by_role('region', name='分组计算')
            await card.locator('.center-inputs input').nth(0).fill('2')
            await card.locator('.center-inputs input').nth(1).fill('11')
            async with page.expect_response(lambda r: r.url.endswith('/group_books/steps') and r.request.method == 'POST') as pending:
                await card.get_by_role('button', name='计算这一轮', exact=True).click()
            step = await (await pending.value).json()
            next_round = card.get_by_role('button', name='用新中心计算下一轮', exact=True)
            await expect(next_round).to_be_hidden()
            await expect(card.locator('.group-result')).to_have_count(0)
            for select in await card.locator('select').all():
                await select.select_option('1')
            await card.get_by_role('button', name='保存本轮分组作答', exact=True).click()
            wrong_names = '、'.join('《'+book['name']+'》' for book in step['records'] if book['group'] != 0)
            await expect(card.get_by_text('回答错误：'+wrong_names+'分错了，请修改。', exact=True)).to_be_visible()
            await expect(card.locator('.group-result')).to_have_count(0)
            await expect(next_round).to_be_hidden()
            for book in step['records']:
                await card.get_by_label(f"{book['name']}分到第几组", exact=True).select_option(str(book['group'] + 1))
            await card.get_by_role('button', name='保存本轮分组作答', exact=True).click()
            await expect(card.get_by_text('回答正确！', exact=True)).to_be_visible()
            await expect(card.locator('.group-result')).to_have_count(2)
            await expect(next_round).to_be_enabled()
            # Editing a verified answer closes the gate immediately.
            first = card.locator('select').first
            original = await first.input_value()
            await first.select_option('2' if original == '1' else '1')
            await expect(card.locator('.group-result')).to_have_count(0)
            await expect(next_round).to_be_hidden()
            await first.select_option(original)
            await expect(next_round).to_be_enabled()
            await next_round.click()
            await expect(card.locator('.group-result')).to_have_count(0)
            await expect(next_round).to_be_hidden()
            await card.get_by_text('查看前面的计算', exact=True).click()
            await card.get_by_role('button', name='第1轮', exact=True).click()
            await expect(card.locator('.group-result')).to_have_count(2)
            await card.get_by_role('button', name='回到最新一轮', exact=True).click()
            await expect(card.locator('.group-result')).to_have_count(0)
            assert not errors, errors
            await page.close()
            print(f'Passed round gate: {project}')
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
