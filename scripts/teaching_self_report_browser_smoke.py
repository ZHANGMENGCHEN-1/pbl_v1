"""Check the six-item pre-learning self-report across A/B/C with local Vite :5174 and fixture :8001."""
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright, expect
from teaching_measurement_helpers import set_rating

BASE = 'http://127.0.0.1:5174'
RATINGS = (5, 4, 5, 3, 2, 4)


async def main():
    Path('test-results').mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel='msedge', headless=True)
        for class_name, slug in [('A班', 'learning-activities'), ('B班', 'teaching-agent'), ('C班', 'meaning-making')]:
            page = await browser.new_page(viewport={'width': 1280, 'height': 900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.goto(BASE + '/projects/' + slug)
            await page.get_by_label('班级', exact=True).fill(class_name)
            await page.get_by_label('学号', exact=True).fill('010')
            await page.get_by_role('button', name='确认并继续', exact=True).click()

            dialog = page.get_by_role('dialog', name='课前自我报告', exact=True)
            await expect(dialog).to_be_visible()
            sliders = dialog.get_by_role('slider')
            await expect(sliders).to_have_count(6)
            await expect(dialog.get_by_text('非常不同意', exact=True)).to_have_count(6)
            await expect(dialog.get_by_text('非常同意', exact=True)).to_have_count(6)
            submit = dialog.get_by_role('button', name='提交并继续', exact=True)
            await expect(submit).to_be_disabled()
            for index, point in enumerate(RATINGS[:-1]):
                await set_rating(sliders.nth(index), point)
            await expect(submit).to_be_disabled()
            await set_rating(sliders.nth(5), RATINGS[-1])
            await expect(submit).to_be_enabled()
            await page.screenshot(path=f'test-results/self-report-{slug}.png', full_page=True)
            await submit.click()
            await expect(dialog).to_have_count(0)

            if slug == 'learning-activities':
                await expect(page.get_by_role('heading', name='活动1：给五本书分组', exact=True)).to_be_visible()
            else:
                await expect(page.get_by_label('小知的话', exact=True)).to_contain_text('图书馆想把')
                await page.get_by_role('button', name='进入活动1', exact=True).click()

            audit = await (await page.request.get('http://127.0.0.1:8898/audit')).json()
            report = next(r for r in audit['self_reports'] if r['source_route'] == slug and r['class_name'] == class_name and r['student_number'] == '010')
            assert json.loads(report['ratings']) == {
                'value_importance': 5,
                'interest': 4,
                'knowledge_importance': 5,
                'performance_efficacy': 3,
                'difficult_knowledge_efficacy': 2,
                'overall_efficacy': 4,
            }
            assert report['questionnaire_version'] == 'learning-self-report-v1'
            assert report['response_mode'] == 'slider-5point-v1' and report['started_at'] and report['response_duration_ms'] >= 0
            assert not errors, errors
            await page.close()

        await browser.close()
        print('Passed: A/B/C six-item self-report gate, endpoint labels, response persistence, and default flow.')


if __name__ == '__main__':
    asyncio.run(main())
