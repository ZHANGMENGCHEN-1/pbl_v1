"""Full browser journey against library_fixture_server.py + Vite port 5174.
Real LangChain/tools/SQLite, explicit local model fixture, no external API calls.
"""
from pathlib import Path
import json
import re
from playwright.sync_api import sync_playwright, expect


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width":1600,"height":1100})
        page.set_default_timeout(10000)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("http://127.0.0.1:5174/projects/library-recommendation")
        expect(page.locator(".library-plan-dialog")).to_be_visible()
        assert page.get_by_role("button",name="返回工作台",exact=True).count()==0
        assert page.locator(".library-plan-dialog .el-dialog__headerbtn").count()==0
        page.keyboard.press("Escape")
        page.mouse.click(20,180)
        expect(page.locator(".library-plan-dialog")).to_be_visible()
        assert page.get_by_role("button",name="数据与预测",exact=True).count()==0
        expect(page.locator(".center-experiment")).to_have_count(0)
        assert page.locator(".library-activities button:disabled").count() == 3

        def submit_plan():
            expect(page.locator(".library-plan-dialog")).to_be_visible()
            if page.locator('.inherited-plan').count():
                expect(page.locator('.inherited-plan')).to_contain_text('我计划')
            page.locator(".library-plan-dialog textarea").fill("我计划根据本活动的数据与工具进行实验，检查分组和中心的具体数值，并说明依据。")
            page.get_by_role("button",name="提交计划，开始实验",exact=True).click()
            expect(page.locator(".library-plan-dialog")).not_to_be_visible()
            expect(page.locator(".library-layout")).to_have_class(re.compile("collapsed"))

        Path("test-results").mkdir(exist_ok=True)
        page.screenshot(path="test-results/library-planning-dialog.png",full_page=True)
        submit_plan()
        page.reload()
        expect(page.locator('.library-plan-dialog textarea')).to_have_value(re.compile('我计划'))
        submit_plan()
        expect(page.get_by_role("button",name="我的计划",exact=True)).to_be_visible()
        expect(page.locator(".library-plan-dialog")).not_to_be_visible()
        page.get_by_role("button",name="查看学习指南",exact=True).click()
        expect(page.locator(".library-learning-scroll")).to_be_visible()
        page.get_by_role("button",name="收起学习指南",exact=True).click()
        expect(page.locator(".library-learning-scroll")).not_to_be_visible()

        page.get_by_role("button",name="调用工具，计算一轮",exact=True).click()
        expect(page.locator(".center-experiment")).to_contain_text("14.333")
        page.get_by_role("button",name="使用新中心，计算下一轮",exact=True).click()
        expect(page.locator(".center-experiment")).to_contain_text("5.667")
        page.get_by_role("button",name="使用新中心，计算下一轮",exact=True).click()
        expect(page.locator('.library-stable-dialog')).to_contain_text('分组与中心已稳定，可以提交结果。')
        page.locator('.library-stable-dialog').get_by_role('button',name='确认',exact=True).click()
        submit_plan()
        expect(page.locator('.prompt-blocks li')).to_have_count(7)
        expect(page.locator('.library-settings h2')).to_have_text('计算助手大脑')
        expect(page.locator('.agent-node.run_kmeans_step')).to_have_count(0)
        expect(page.locator('.library-settings textarea')).to_have_value(re.compile('请排列第1个步骤模块'))
        page.locator('.prompt-blocks li[data-step="centers"]').get_by_role('button',name='下移选择中心点',exact=True).click()
        page.get_by_role('button',name='保存配置',exact=True).click()
        page.get_by_role('button',name=re.compile("^(提交交付物|完成并提交)$")).click()
        page.get_by_role('button',name='提交并解锁下一活动',exact=True).click()
        expect(page.locator('.el-message--error')).to_contain_text('步骤还需要调整')
        page.get_by_role('button',name='返回实验',exact=True).click()
        desired=['data','count','centers','distance','assign','update','iterate']
        for position,step in enumerate(desired):
            while page.locator('.prompt-blocks li').evaluate_all('(rows,id)=>rows.findIndex(r=>r.dataset.step===id)',step)>position:
                page.locator(f'.prompt-blocks li[data-step="{step}"] .block-actions button').first.click()
        expect(page.locator('.library-settings textarea')).to_have_value(re.compile('1. 获取原始数据'))
        page.get_by_role('button',name='保存配置',exact=True).click()
        expect(page.locator('.config-version')).to_contain_text('配置 v2')
        page.screenshot(path='test-results/library-prompt-sorting.png',full_page=True)
        page.reload()
        submit_plan()
        assert page.locator('.prompt-blocks li').evaluate_all('(rows)=>rows.map(r=>r.dataset.step)')==desired
        page.get_by_role('button',name='运行智能体',exact=True).click()
        expect(page.locator('.final-answer')).to_be_visible(timeout=20000)
        page.get_by_role('button',name=re.compile("^(提交交付物|完成并提交)$")).click()
        expect(page.locator('.library-delivery textarea')).to_have_count(0)
        page.get_by_role('button',name='提交并解锁下一活动',exact=True).click()
        submit_plan()
        page.get_by_role("button",name="Agent 画布",exact=True).click()
        page.locator('.agent-node.inspect_dataset').click()
        expect(page.locator('.library-settings')).to_contain_text('150 条记录')
        def choose_table(label):
            select=page.get_by_role('combobox',name='选择数据表',exact=True)
            page.locator('.library-settings .el-select').filter(has=select).click()
            listbox=select.get_attribute('aria-controls')
            page.locator(f'[id="{listbox}"]').get_by_role('option',name=label,exact=True).click()
        names=json.loads(Path('backend/datasets/library/manifest.json').read_text(encoding='utf-8'))
        choose_table(names['library_sample_1d']['name']+' · 1维')
        page.get_by_role('button',name='调用数据查看工具',exact=True).click()
        expect(page.locator('.library-tool-data-dialog')).to_contain_text('共 5 条记录')
        expect(page.locator('.library-tool-data-dialog .el-table__body tr')).to_have_count(5)
        page.locator('.library-tool-data-dialog').get_by_role('button',name='关闭',exact=True).click()
        choose_table(names['library_books_2d']['name']+' · 2维')
        page.get_by_role('button',name='调用数据查看工具',exact=True).click()
        expect(page.locator('.library-tool-data-dialog')).to_contain_text('共 150 条记录')
        expect(page.locator('.library-tool-data-dialog .el-table__body tr')).to_have_count(30)
        expect(page.locator('.library-tool-data-dialog')).to_contain_text('记录001')
        page.screenshot(path='test-results/library-selected-table.png',full_page=True)
        page.locator('.library-tool-data-dialog').get_by_role('button',name='关闭',exact=True).click()
        page.reload()
        submit_plan()
        expect(page.locator('.library-settings')).to_contain_text('150 条记录')
        page.locator(".agent-node.run_kmeans_analysis").click()
        expect(page.locator('.library-settings .el-input-number input').first).to_have_value('2')
        expect(page.locator('.library-settings .el-input-number input').first).to_be_disabled()
        page.get_by_role('button',name='运行智能体',exact=True).click()
        expect(page.locator('.library-delivery-dialog')).to_be_visible(timeout=20000)
        expect(page.locator('.library-delivery')).to_contain_text('合计 150 / 150 条')
        rows=page.locator('.library-delivery .el-table__body tr')
        expect(rows).to_have_count(2)
        counts=[int(rows.nth(i).locator('td').nth(1).inner_text()) for i in range(2)]
        assert sum(counts)==150
        expect(page.locator('.library-delivery textarea')).to_have_count(0)
        page.screenshot(path='test-results/library-group-counts.png',full_page=True)
        page.get_by_role('button',name='提交并解锁下一活动',exact=True).click()
        expect(page.locator('.inherited-plan')).to_contain_text('本活动补充')
        submit_plan()
        expect(page.locator('.library-settings')).to_contain_text('100 条记录')
        page.locator('.agent-node.brain').click()
        expect(page.locator('.library-settings textarea').first).to_have_value(re.compile('1. 获取原始数据'))
        expect(page.locator('.library-settings textarea').nth(1)).to_have_value(re.compile('实际选择'))
        page.get_by_role('button',name='运行智能体',exact=True).click()
        expect(page.locator('.library-delivery-dialog')).to_be_visible(timeout=20000)
        expect(page.locator('.purchase-row')).to_have_count(2)
        quantities=[int(v) for v in page.locator('.purchase-row .el-input-number input').evaluate_all('(inputs)=>inputs.map(i=>i.value)')]
        assert sum(quantities)==1000
        assert all(page.locator('.purchase-row > .el-input input').nth(i).input_value() for i in range(2))
        expect(page.locator('.library-delivery textarea').first).to_have_value(re.compile('100条调查记录'))
        page.locator('.library-delivery textarea').nth(1).fill('我检查了组中心与人数，保留当前建议，仍需核查样本代表性。')
        page.screenshot(path='test-results/library-reflection-dialog.png',full_page=True)
        page.get_by_role('button',name='提交成果与反思',exact=True).click()
        expect(page.locator(".library-progress")).to_contain_text("4 / 4")
        page.reload()
        expect(page.locator(".library-progress")).to_contain_text("4 / 4")
        submit_plan()
        Path("test-results").mkdir(exist_ok=True)
        page.screenshot(path="test-results/library-workspace.png",full_page=True)
        page.get_by_role("link",name="天文项目",exact=True).click()
        expect(page).to_have_url(re.compile("/projects/astronomy-lab$"))
        expect(page.locator(".agent-node")).to_have_count(3)
        expect(page.locator(".learning-intro h2")).to_have_text("月球与行星观测")
        page.get_by_role("link",name="图书馆项目",exact=True).click()
        expect(page.locator(".library-progress")).to_contain_text("4 / 4")
        assert not errors, errors
        print("Passed forced plan submission, no direct data tab, seven-block Prompt sorting, saved template, invalid order guards, selected Excel tables and 150-row two-group Agent delivery, 100-row real survey, automatic purchases and cumulative plans, four activities, delivery/reflection, reload, real fixture tool calling and astronomy preservation; no page errors.")
        browser.close()


if __name__ == "__main__":
    main()
