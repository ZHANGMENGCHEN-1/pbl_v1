import json
import pytest
from fastapi import HTTPException
from app.shared import store
from app.projects.library.decisions import parse, validate_purchases
from test_library import client, cfg, save, agent_run, B, H
from test_library_datasets import unlock_second


def test_reusable_prompt_migrates_saved_scaffold_preserving_student_edits(client):
    from app.projects.library.prompt import INTRO, ENDING, render, ORDER
    unlock_second(client)
    value=cfg(client,2)
    old=render(ORDER).replace(INTRO,'你是计算助手，帮助七年级学生根据借阅次数把五本书分成2组。请按照下面的步骤执行并解释，不跳过步骤。')
    old=old.replace('使用学生配置的分组数量K，设置K个中心点。','本次分为2组，中心点数量为2。').replace('根据所选数据的特征维度，初始化K个中心点。','例如选择2和11作为初始中心。')
    old=old.replace(ENDING,'先使用数据查看工具获取数据，不编造数据。计算时展示距离、分组和新中心；距离相同时归入第1组，空组保留原中心。保留计算精度，展示时可取近似值。说明迭代何时停止。')+'\n我补充的规则：先检查字段含义。'
    value['config']['system_prompt']=old
    with store.connection() as db:db.execute('UPDATE library_configs SET config=? WHERE session=? AND activity=?',(json.dumps(value['config']),H['X-Session-ID'],'explore_2d'))
    migrated=cfg(client,2)
    assert migrated['revision']==value['revision']+1
    assert migrated['config']['system_prompt']==render(ORDER)+'\n我补充的规则：先检查字段含义。'
    assert cfg(client,2)==migrated


def test_plans_build_on_previous_additions(client):
    unlock_second(client)
    client.post(B+'/activities/group_books/plan',headers=H,json={'text':'第一步先选中心并检查分组是否稳定。'})
    response=client.post(B+'/activities/explain_algorithm/plan',headers=H,json={'text':'第二步补充：排列算法步骤，明确迭代的停止条件。'})
    second=response.json()['activities'][1]
    assert second['inherited_plan']['text']=='第一步先选中心并检查分组是否稳定。'
    assert '第一步先选中心' in second['plan']['text'] and '第二步补充' in second['plan']['text']
    third=response.json()['activities'][2]
    assert third['plan'] is None
    assert '第一步先选中心' in third['inherited_plan']['text']
    assert '第二步补充' in third['inherited_plan']['text']
    response=client.post(B+'/activities/explore_2d/plan',headers=H,json={'text':'第三步补充：让Agent分成两组，检查合计150条。'})
    assert response.json()['completed']==2
    plan=response.json()['activities'][2]['plan']
    assert all(word in plan['text'] for word in ['第一步先选中心','第二步补充','第三步补充'])
    assert plan['addition'].startswith('第三步补充')
    changed=client.post(B+'/activities/explore_2d/plan',headers=H,json={'text':'第三步修改：核查数据表和两个特征，合计150条。'}).json()['activities'][2]['plan']
    assert '第三步补充' not in changed['text'] and changed['text'].count('第二步补充')==1
    assert client.get(B+'/learning',headers=H).json()['activities'][2]['plan']==changed
    other={'X-Session-ID':'new-plan-evolution-session'}
    assert client.get(B+'/learning',headers=other).json()['activities'][0]['plan'] is None


def test_decisions_validate_model_output_without_fabricating():
    result={'groups':[{'label':0,'count':40},{'label':1,'count':60}]}
    valid={'answer':'根据真实组中心解释两组不同阅读需求。','purchases':[{'group':0,'type':'文艺短篇','quantity':400},{'group':1,'type':'知识长篇','quantity':600}], 'rationale':'参考样本人数比例，但样本不能代表全校。'}
    assert parse('```json\n'+json.dumps(valid)+'\n```',result)==valid
    for rows in [valid['purchases'][:1],[{**valid['purchases'][0],'quantity':399},valid['purchases'][1]],[valid['purchases'][0],valid['purchases'][0]],[{**valid['purchases'][0],'quantity':True},valid['purchases'][1]]]:
        with pytest.raises(HTTPException):validate_purchases(rows,result)
    with pytest.raises(HTTPException):parse('模型只输出一段话，没有给出数量表。',result)


def test_agent_evidence_and_automatic_purchase_delivery(client,monkeypatch):
    unlock_second(client)
    value=cfg(client,2)
    value['config']['experiment']['k']=3
    with_plan=client.post(B+'/activities/explore_2d/plan',headers=H,json={'text':'让Agent调用工具分组并检查150条记录。'})
    assert with_plan.status_code==200
    assert client.put(B+'/config?activity_id=explore_2d&revision=0',headers=H,json=value['config']).status_code==422
    value['config']['experiment']['k']=2
    run_id=agent_run(client,monkeypatch,2,value)
    assert client.post(B+'/activities/explore_2d/submit',headers={'X-Session-ID':'another-student-session-123'},json={'payload':{'run_id':run_id,'group_counts':[{'group':0,'count':75},{'group':1,'count':75}]}}).status_code==403
    response=client.post(B+'/activities/explore_2d/submit',headers=H,json={'payload':{'run_id':run_id,'group_counts':[{'group':0,'count':75},{'group':1,'count':75}]}})
    assert response.status_code==200,response.text
    value=cfg(client,3)
    assert value['config']['experiment']['dataset_id']=='reading_interest_students'
    assert value['config']['experiment']['k']==2
    assert '实际选择' in value['config']['task_prompt']
    options=client.get(B+'/activities/recommend_purchase/datasets',headers=H).json()
    assert {d['id'] for d in options}=={'library_sample_1d','library_books_2d','reading_interest_students'}
    browsing=cfg(client,3)
    browsing['config']['experiment'].update(dataset_id='library_sample_1d',features=['borrow_count'])
    browsing=save(client,3,browsing)
    inspected=client.post(B+f"/activities/recommend_purchase/tools/inspect_dataset?revision={browsing['revision']}",headers=H)
    assert inspected.status_code==200 and inspected.json()['row_count']==5
    browsing['config']['experiment'].update(dataset_id='reading_interest_students',features=['content_preference','duration_preference'])
    value=save(client,3,browsing)
    run_id=agent_run(client,monkeypatch,3,value)
    detail=client.get(B+'/runs/'+run_id,headers=H).json()
    decision=next(e['data']['decision'] for e in detail['events'] if e['type']=='final')
    assert sum(r['quantity'] for r in decision['purchases'])==1000
    assert client.post(B+'/activities/recommend_purchase/submit',headers=H,json={'payload':{'run_id':run_id,'reflection':'我需要自己填写采购类型与数量。'}}).status_code==422
    assert client.post(B+'/activities/recommend_purchase/submit',headers=H,json={'payload':{'run_id':run_id,'group_counts':[{'group':0,'count':75},{'group':1,'count':75}]}}).status_code==422
    for rationale, reflection in [('', '我检查了各组人数和需求，但仍需要核查样本。'), ('不足十字', '我检查了各组人数和需求，但仍需要核查样本。'), ('我参考各组人数和阅读偏好分配采购数量。', '太短'), ('         ', '我检查了各组人数和需求，但仍需要核查样本。')]:
        rejected=client.post(B+'/activities/recommend_purchase/submit',headers=H,json={'payload':{'run_id':run_id,'purchases':decision['purchases'],'rationale':rationale,'reflection':reflection}})
        assert rejected.status_code==422
    response=client.post(B+'/activities/recommend_purchase/submit',headers=H,json={'payload':{'run_id':run_id,'purchases':decision['purchases'],'rationale':'我参考各组人数和阅读偏好分配采购数量。','reflection':'我根据人数分配，但还需要核查样本的代表性。'}})
    assert response.status_code==200,response.text
    saved=response.json()['activities'][3]['submission']['payload']
    assert saved['purchases']==decision['purchases'] and saved['rationale']=='我参考各组人数和阅读偏好分配采购数量。'


def test_old_survey_configuration_migrates_without_overwriting_prompt(client,monkeypatch):
    unlock_second(client)
    value=cfg(client,2)
    run_id=agent_run(client,monkeypatch,2,value)
    client.post(B+'/activities/explore_2d/submit',headers=H,json={'payload':{'run_id':run_id,'group_counts':[{'group':0,'count':75},{'group':1,'count':75}]}})
    value=cfg(client,3)
    old=value['config']
    old['experiment'].update(dataset_id='reading_interest_survey',k=3)
    old['system_prompt']='学生自己已经写好的算法规则。'
    old.pop('task_prompt',None)
    with store.connection() as db:db.execute('UPDATE library_configs SET config=? WHERE session=? AND activity=?',(json.dumps(old),H['X-Session-ID'],'recommend_purchase'))
    migrated=cfg(client,3)
    assert migrated['revision']==value['revision']+1
    assert migrated['config']['experiment']['dataset_id']=='reading_interest_students'
    assert migrated['config']['system_prompt']==old['system_prompt']
    assert cfg(client,3)==migrated


def test_purchase_delivery_records_students_unsuitable_table_choice(client,monkeypatch):
    unlock_second(client)
    value=cfg(client,2)
    run_id=agent_run(client,monkeypatch,2,value)
    client.post(B+'/activities/explore_2d/submit',headers=H,json={'payload':{'run_id':run_id,'group_counts':[{'group':0,'count':75},{'group':1,'count':75}]}})
    value=cfg(client,3)
    value['config']['experiment'].update(dataset_id='library_sample_1d',features=['borrow_count'])
    value=save(client,3,value)
    run_id=agent_run(client,monkeypatch,3,value)
    analyses=client.get(B+'/activities/recommend_purchase/analyses',headers=H).json()
    assert analyses[0]['result']['dataset_id']=='library_sample_1d'
    assert analyses[0]['result']['sample_count']==5
    detail=client.get(B+'/runs/'+run_id,headers=H).json()
    decision=next(e['data']['decision'] for e in detail['events'] if e['type']=='final')
    response=client.post(B+'/activities/recommend_purchase/submit',headers=H,json={'payload':{'run_id':run_id,'purchases':decision['purchases'],'rationale':'我参考各组人数和阅读偏好分配采购数量。','reflection':'我使用了借阅次数，但需要反思这能否代表阅读兴趣。'}})
    assert response.status_code==200,response.text
    saved=response.json()['activities'][3]['submission']['payload']
    assert saved['analysis_id']==analyses[0]['id']
    assert cfg(client,3)['config']['experiment']['dataset_id']=='library_sample_1d'
