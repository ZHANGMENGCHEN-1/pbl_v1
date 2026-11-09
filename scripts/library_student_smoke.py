"""Four-activity student UI: local streaming model, actual LangChain/tools/SQLite."""
from pathlib import Path
import re
from playwright.sync_api import sync_playwright,expect
from browser_delivery_helpers import submit_first_result


def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':1366,'height':900})
        page.set_default_timeout(12000)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:5174/projects/library-recommendation')
        Path('test-results').mkdir(exist_ok=True)

        def plan():
            card=page.locator('.plan-card')
            expect(card).to_be_visible()
            if card.locator('input:checked').count()==0:
                card.locator('input[value=read_first]').check();card.locator('input[value=evidence]').check()
            card.locator('button[type=submit]').click()
            expect(page.locator('.library-plan-dialog')).not_to_be_visible()

        def write():
            page.locator('.library-floating-actions').get_by_role('button',name='提交结果',exact=True).click()
            expect(page.locator('.library-delivery-panel')).to_be_visible()
            expect(page.locator('.library-delivery-dialog')).to_have_count(0)

        def side_by_side():
            left=page.locator('.library-execution').bounding_box()
            right=page.locator('.library-delivery-panel').bounding_box()
            assert left and right and left['x']+left['width']<=right['x']+1,(left,right)
            assert right['x']+right['width']<=1367,right
            assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
            expect(page.locator('.trace-output .final-answer')).to_be_visible()

        expect(page.locator('.plan-card fieldset')).to_have_count(2)
        page.keyboard.press('Escape');expect(page.locator('.plan-card')).to_be_visible()
        plan()
        page.get_by_role('button',name='计算一轮',exact=True).click()
        expect(page.locator('.center-experiment')).to_contain_text('14.333')
        page.get_by_role('button',name='用新中心，再算一轮',exact=True).click()
        expect(page.locator('.center-experiment')).to_contain_text('5.667')
        page.get_by_role('button',name='用新中心，再算一轮',exact=True).click()
        submit_first_result(page)
        plan()
        expect(page.locator('.library-execution')).to_have_count(0)
        expect(page.locator('.prompt-blocks li')).to_have_count(7)
        expect(page.get_by_role('combobox',name='模型',exact=True)).not_to_be_visible()
        while page.locator('.prompt-blocks li').evaluate_all('(rows)=>rows.findIndex(r=>r.dataset.step==="iterate")')>0:
            page.locator('.prompt-blocks li[data-step="iterate"] .block-actions button').first.click()
        write()
        panel=page.locator('.library-delivery-panel')
        page.locator('.library-floating-actions').get_by_role('button',name='提交结果',exact=True).click()
        expect(page.locator('.el-message--error')).to_contain_text('步骤还需要调整')
        page.get_by_role('button',name='收起填写区',exact=True).click()
        for position,step in enumerate(['data','count','centers','distance','assign','update','iterate']):
            while page.locator('.prompt-blocks li').evaluate_all('(rows,id)=>rows.findIndex(r=>r.dataset.step===id)',step)>position:
                page.locator(f'.prompt-blocks li[data-step="{step}"] .block-actions button').first.click()
        page.screenshot(path='test-results/student-simple-prompt.png',full_page=True)
        write();page.locator('.library-floating-actions').get_by_role('button',name='提交结果',exact=True).click()
        receipt=page.locator('.library-receipt-dialog')
        receipt.get_by_role('button',name='进入活动3',exact=True).click()
        plan()
        expect(page.locator('.library-layout')).not_to_have_class(re.compile('collapsed'))
        expect(page.locator('.library-settings')).to_contain_text('150 条记录')
        expect(page.get_by_role('button',name='运行聚类实验',exact=True)).to_have_count(0)
        expect(page.locator('.lab-tabs')).not_to_contain_text('分析结果')
        page.get_by_role('button',name='查看这张表',exact=True).click()
        expect(page.locator('.library-tool-data-dialog .el-table__body tr')).to_have_count(30)
        page.locator('.library-tool-data-dialog').get_by_role('button',name='关闭',exact=True).click()
        expect(page.locator('.lab-tabs button.active')).to_have_text('助手和工具')
        page.locator('.agent-node.run_kmeans_analysis').click()
        expect(page.get_by_role('spinbutton',name='随机种子',exact=True)).not_to_be_visible()
        expect(page.locator('.library-settings .el-input-number input').first).to_have_value('2')
        expect(page.locator('.test-input textarea')).to_have_value('')
        page.get_by_role('button',name='看看例子',exact=True).click()
        page.get_by_role('button',name='开始运行',exact=True).click()
        expect(page.locator('.run-badge.completed')).to_be_visible(timeout=25000)
        expect(page.locator('.trace-output .tool-evidence')).to_have_count(2)
        expect(panel).to_have_count(0)
        write();side_by_side()
        expect(panel.locator('.final-answer')).to_have_count(0)
        inputs=panel.locator('.student-result-row input')
        assert [inputs.nth(i).input_value() for i in range(2)]==['','']
        inputs.nth(0).fill('75')
        expect(page.locator('.library-floating-actions').get_by_role('button',name='提交结果',exact=True)).to_be_disabled()
        panel.get_by_role('button',name='先收起',exact=True).click()
        write()
        expect(panel.locator('.student-result-row input').first).to_have_value('75')
        panel.locator('.student-result-row input').nth(1).fill('75')
        side_by_side()
        page.screenshot(path='test-results/student-side-by-side-counts.png',full_page=True)
        page.locator('.library-floating-actions').get_by_role('button',name='提交结果',exact=True).click()
        receipt.locator('.receipt-details > summary').click()
        expect(receipt.locator('.analysis-viewer circle')).to_have_count(150)
        receipt.get_by_role('button',name='进入活动4',exact=True).click()
        plan()
        expect(page.locator('.library-layout')).not_to_have_class(re.compile('collapsed'))
        expect(page.locator('.library-settings')).to_contain_text('100 条记录')
        page.get_by_role('button',name='看看例子',exact=True).click()
        page.get_by_role('button',name='开始运行',exact=True).click()
        expect(page.locator('.run-badge.completed')).to_be_visible(timeout=25000)
        expect(panel).to_have_count(0)
        write();side_by_side()
        expect(page.locator('.trace-output .agent-purchase-reference')).to_be_visible()
        expect(panel.locator('.purchase-row')).to_have_count(2)
        for i in range(2):
            row=panel.locator('.purchase-row').nth(i)
            assert row.locator('.el-input-number input').input_value()==''
            assert row.locator(':scope > .el-input input').input_value()==''
            row.locator(':scope > .el-input input').fill('我的买书类型'+str(i+1))
            row.locator('.el-input-number input').fill('500')
        assert panel.locator('textarea').evaluate_all('(els)=>els.map(e=>e.value)')==['','']
        submit=page.locator('.library-floating-actions').get_by_role('button',name='提交结果',exact=True)
        panel.locator('textarea').first.fill('我参考每组人数和阅读喜好来分配买书数量。')
        panel.locator('textarea').nth(1).fill('还需要检查')
        expect(submit).to_be_disabled()
        reflection='我发现同学们喜欢的书不同，下次还要看看更多同学的想法。'
        panel.locator('textarea').nth(1).fill(reflection)
        expect(submit).to_be_enabled()
        page.screenshot(path='test-results/student-side-by-side-purchase.png',full_page=True)
        submit.click()
        receipt.locator('.receipt-details > summary').click()
        expect(receipt.locator('.student-reflection')).to_contain_text(reflection)
        expect(receipt.locator('.analysis-viewer circle')).to_have_count(100)
        receipt.get_by_role('button',name='完成，返回学习',exact=True).click()
        expect(page.locator('.library-progress')).to_contain_text('4 / 4')
        expect(page.locator('.library-floating-actions button')).to_have_count(3)
        page.get_by_role('button',name='查看我的提交',exact=True).click()
        drawer=page.locator('.library-records-drawer')
        expect(drawer.locator('.library-record-card')).to_have_count(4)
        expect(drawer.locator('.analysis-viewer')).to_have_count(0)
        expect(drawer.locator('.student-reflection')).to_contain_text(reflection)
        page.keyboard.press('Escape')
        page.get_by_role('button',name='查看我的计划',exact=True).click()
        expect(drawer.locator('.library-record-card')).to_have_count(4)
        page.keyboard.press('Escape')
        page.reload()
        expect(page.locator('.library-progress')).to_contain_text('4 / 4')
        plan()
        expect(page.locator('.trace-output .final-answer')).to_have_count(0)
        page.get_by_role('link',name='天文项目',exact=True).click()
        expect(page.locator('.agent-node')).to_have_count(3)
        expect(page.locator('.learning-intro h2')).to_have_text('月球与行星观测')
        assert not errors,errors
        browser.close()
        print('Passed four activities, simple controls, nonmodal side-by-side evidence at 1366px, drafts, manual results, 10-character guards, plans/history, refresh and astronomy.')


if __name__=='__main__':main()
