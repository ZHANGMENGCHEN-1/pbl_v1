from playwright.sync_api import expect


def submit_first_result(page):
    page.locator('.library-stable-dialog').get_by_role('button',name='填写结果',exact=True).click()
    dialog=page.locator('.library-delivery-panel')
    expect(dialog).to_be_visible()
    inputs=dialog.locator('.student-result-row .el-input-number input')
    assert [inputs.nth(i).input_value() for i in range(4)]==['','','','']
    for i,value in enumerate([3,5.667,2,17]):inputs.nth(i).fill(str(value))
    page.locator('.library-floating-actions').get_by_role('button',name='提交结果',exact=True).click()
    receipt=page.locator('.library-receipt-dialog')
    expect(receipt).to_be_visible()
    receipt.locator('.receipt-details > summary').click()
    expect(receipt).to_contain_text('5.667')
    expect(receipt.locator('.el-table__body tr')).to_have_count(2)
    expect(page.locator('.center-experiment')).to_be_visible()
    receipt.get_by_role('button',name='进入活动2',exact=True).click()
