from playwright.async_api import expect


async def complete_self_report(page, ratings=(5, 4, 5, 4, 4, 4)):
    dialog = page.get_by_role('dialog', name='课前自我报告', exact=True)
    await expect(dialog).to_be_visible()
    for i, point in enumerate(ratings):
        await set_rating(dialog.locator('fieldset').nth(i).get_by_role('slider'), point)
    await dialog.get_by_role('button', name='提交并继续', exact=True).click()
    await expect(dialog).to_have_count(0)


async def complete_survey(page, number, robot=True, ratings=(4, 2, 3, 5)):
    dialog = page.get_by_role('dialog', name=f'活动{number}：你的感受怎么样？', exact=True)
    await expect(dialog).to_be_visible()
    for i, point in enumerate(ratings):
        await set_rating(dialog.locator('fieldset').nth(i).get_by_role('slider'), point)
    await dialog.get_by_role('button', name='保存并与小知交流' if robot else '保存学习感受', exact=True).click()
    await expect(dialog).to_have_count(0)


async def set_rating(slider, point):
    await slider.focus()
    await slider.press("Home")
    for _ in range(point - 1):
        await slider.press("ArrowRight")
