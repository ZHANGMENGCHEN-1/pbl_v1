"""Dataset selection must affect preview, saved settings and actual analysis."""
import json
import numpy as np
from openpyxl import Workbook
from app.projects.library import datasets
from app.projects.library.tools import build_tools
from test_library import client, unlock_first, cfg, save, plan, B, H, ORDER


def unlock_second(client):
    unlock_first(client)
    value=cfg(client,1)
    value['config']['prompt_steps']=ORDER
    save(client,1,value)
    response=client.post(B+'/activities/explain_algorithm/submit',headers=H,json={'payload':{}})
    assert response.status_code==200,response.text


def test_selected_workbook_persists_and_controls_tools(client):
    assert client.get(B+'/activities/explore_2d/datasets',headers=H).status_code==403
    first=client.get(B+'/activities/group_books/datasets',headers=H).json()
    assert [d['id'] for d in first]==['library_sample_1d']
    assert client.get(B+'/activities/group_books/dataset?dataset_id=library_books_2d',headers=H).status_code==403
    unlock_second(client)
    options=client.get(B+'/activities/explore_2d/datasets',headers=H).json()
    assert {d['id'] for d in options}=={'library_sample_1d','library_books_2d'}
    assert all('preview' not in d and 'records' not in d for d in options)
    value=cfg(client,2)
    assert value['config']['experiment']['dataset_id']=='library_books_2d'
    metadata=client.get(B+'/activities/explore_2d/dataset',headers=H).json()
    assert metadata['row_count']==150 and metadata['preview']==[]
    plan(client,2)
    actual=client.post(B+'/activities/explore_2d/tools/inspect_dataset?revision=0',headers=H).json()
    assert actual['row_count']==150 and len(actual['preview'])==30
    assert actual['preview'][0]=={'borrow_count':7,'borrow_days':2,'id':'R001','name':'记录001'}
    assert actual['fields'][1]['unit']
    full=client.post(B+'/activities/explore_2d/analyses?revision=0',headers=H).json()
    assert full['sample_count']==150 and len(full['centers'][0])==2
    value['config']['experiment'].update(dataset_id='library_sample_1d',features=['borrow_count'])
    value=save(client,2,value)
    assert cfg(client,2)==value
    data=client.post(B+f"/activities/explore_2d/tools/inspect_dataset?revision={value['revision']}",headers=H).json()
    assert data['id']=='library_sample_1d' and data['row_count']==5
    tool=next(t for t in build_tools(H['X-Session-ID'],'explore_2d',value['revision'],value['config'],None) if t.name=='inspect_dataset')
    # A model cannot override the student's saved selection.
    assert isinstance(tool.invoke({'dataset_id':'library_books_2d'}),str)
    result=client.post(B+f"/activities/explore_2d/analyses?revision={value['revision']}",headers=H).json()
    assert result['sample_count']==5 and len(result['centers'][0])==1
    assert client.post(B+'/activities/explore_2d/tools/inspect_dataset?revision=0',headers=H).status_code==409
    assert client.get(B+'/activities/explore_2d/dataset?dataset_id=../../.env',headers=H).status_code==403
    assert client.get(B+'/activities/explore_2d/dataset?dataset_id=reading_interest_survey',headers=H).status_code==403
    assert client.get(B+'/activities/explore_2d/dataset?dataset_id=library_sample_2d',headers=H).status_code==403
    other={'X-Session-ID':'other-table-session-1234'}
    assert client.get(B+'/activities/explore_2d/datasets',headers=other).status_code==403


def test_retired_sample_selection_migrates_once(client):
    from app.shared import store
    unlock_second(client)
    value=cfg(client,2)
    value['config']['experiment']['dataset_id']='library_sample_2d'
    with store.connection() as db:
        db.execute('UPDATE library_configs SET config=? WHERE session=? AND activity=?',(json.dumps(value['config']),H['X-Session-ID'],'explore_2d'))
    migrated=cfg(client,2)
    assert migrated['revision']==value['revision']+1
    assert migrated['config']['experiment']['dataset_id']=='library_books_2d'
    assert cfg(client,2)==migrated


def test_additional_registered_third_feature_needs_no_schema_change(client,tmp_path,monkeypatch):
    unlock_second(client)
    value=cfg(client,2)
    path=tmp_path/'three.xlsx'
    book=Workbook()
    book.active.append(['次数','时长','评价'])
    for row in [(1,2,3),(2,3,5),(10,20,80),(15,24,90),(18,30,95)]:book.active.append(row)
    book.save(path)
    entry={'name':'三维测试表','file':'three.xlsx','features':['borrow_count','borrow_days','rating'],
           'column_map':{'次数':'borrow_count','时长':'borrow_days','评价':'rating'},
           'field_definitions':{'rating':{'label':'评价','unit':'分'}},
           'source':'测试构造样本','demo':True,'activities':['explore_2d']}
    (tmp_path/'manifest.json').write_text(json.dumps({'test_3d':entry}),encoding='utf-8')
    monkeypatch.setattr(datasets,'ROOT',tmp_path)
    options=client.get(B+'/activities/explore_2d/datasets',headers=H).json()
    assert options[0]['dimensions']==3
    value['config']['experiment'].update(dataset_id='test_3d',features=entry['features'])
    value=save(client,2,value)
    result=client.post(B+f"/activities/explore_2d/analyses?revision={value['revision']}",headers=H).json()
    assert result['sample_count']==5 and len(result['centers'][0])==3
    assert result['fields'][2]['label']=='评价'
    for group in result['groups']:
        rows=[r for r,label in zip(result['records'],result['labels']) if label==group['label']]
        if rows:assert np.allclose(group['center'],np.mean([[r[f] for f in entry['features']] for r in rows],axis=0))
