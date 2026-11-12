import hashlib
import json
from io import BytesIO
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import app
from app.shared import store

BASE = '/api/projects/teaching-agent/activities/explore_2d'
H = {'X-Session-ID': 'excel-student-session-001'}
OTHER = {'X-Session-ID': 'excel-student-session-002'}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path/'excel.db'))
    with TestClient(app) as client:
        for headers in [H,OTHER]:
            assert client.post('/api/projects/teaching-agent/student',headers=headers,json={'class_name':'七年级1班','student_number':'001'}).status_code==200
        yield client


def excel(rows, second=False):
    workbook=Workbook()
    sheet=workbook.active
    sheet.title='书籍数据'
    for row in rows:
        sheet.append(row)
    if second:
        workbook.create_sheet('不参与的表').append(['不能悄悄换表'])
    stream=BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def upload(client, rows=None, raw=None, headers=H, name='学生表格.xlsx'):
    return client.post(BASE+'/datasets', headers={**headers, 'X-File-Name':quote(name)}, content=raw if raw is not None else excel(rows))


def analyze(client, dataset, features=None, headers=H):
    return client.post(BASE+'/analyses',headers=headers,json={'dataset_id':dataset['id'],'features':features or dataset['default_features']})


def test_upload_real_analysis_submission_and_isolation(client):
    rows=[['书名','借阅次数','借阅时长'],['甲',1,2],['乙',2,3],['丙',20,30],['丁',21,31],['缺失',None,2],['文字','12',4],['公式','=1+2',4]]
    raw=excel(rows,second=True)
    response=upload(client,raw=raw)
    assert response.status_code==200
    data=response.json()
    assert data['row_count']==7 and data['sheet']=='书籍数据' and data['sheet_count']==2
    assert data['default_features']==['c1','c2']
    assert data['version']==hashlib.sha256(raw).hexdigest()
    assert data['preview'][5]['values'][1]=='12'  # Not coerced into a number.
    preview=client.post(BASE+'/preview',headers=H,json={'dataset_id':data['id'],'features':['c1','c2']}).json()
    assert preview['sample_count']==4
    assert [r['row'] for r in preview['excluded']]==[6,7,8]
    result=analyze(client,data).json()
    assert result['converged'] and result['sample_count']==4
    assert sorted(g['count'] for g in result['groups'])==[2,2]
    assert sorted(g['center'] for g in result['groups'])==[[1.5,2.5],[20.5,30.5]]
    assert result['features'][0]['name']=='借阅次数'
    assert result['dataset_version']==data['version']
    assert [p['row'] for p in result['points']]==[2,3,4,5]
    assert result['points'][0]['values']==['甲',1,2]
    assert result['teaching_context']['excluded_count']==3
    assert result['teaching_context']['scaling']=='none'
    # Incorrect but complete counts are preserved separately, not graded.
    body={'result_id':result['id'],'counts':[3,1],'description':'一组的两个数值比较小，另一组比较大。'}
    submitted=client.post(BASE+'/submissions',headers=H,json=body)
    assert submitted.status_code==200
    record=submitted.json()
    assert record['payload']['student_result']['counts']==[3,1]
    assert record['payload']['tool_result']['counts']==[2,2]
    assert client.get(BASE+'/analyses/'+result['id'],headers=H).json()==result
    assert client.get(BASE+'/datasets/'+data['id'],headers=OTHER).status_code==404
    assert analyze(client,data,headers=OTHER).status_code==404
    assert client.get(BASE+'/analyses/'+result['id'],headers=OTHER).status_code==404
    assert client.post(BASE+'/submissions',headers=OTHER,json=body).status_code==404
    with store.connection() as db:
        row=db.execute('SELECT * FROM teaching_datasets WHERE id=?',(data['id'],)).fetchone()
        assert row['raw_file']==raw and row['project']=='teaching-agent' and row['session']==H['X-Session-ID']
        saved=json.loads(db.execute('SELECT payload FROM teaching_submissions WHERE id=?',(record['id'],)).fetchone()[0])
        assert saved==record['payload']


def test_versions_immutable_and_no_silent_column_change(client):
    first=upload(client,[['名字','次数','时间'],['甲',1,2],['乙',3,4]]).json()
    second=upload(client,[['名字','次数','时间'],['甲',100,200],['乙',300,400]]).json()
    assert first['id']!=second['id'] and first['version']!=second['version']
    assert client.get(BASE+'/datasets/'+first['id'],headers=H).json()['preview'][0]['values']==['甲',1,2]
    assert analyze(client,first,['c0','c1']).status_code==422
    assert analyze(client,first,['c1','c1']).status_code==422
    assert analyze(client,first,['c1','unknown']).status_code==422
    swapped=analyze(client,first,['c2','c1']).json()
    assert [f['name'] for f in swapped['features']]==['时间','次数']
    assert swapped['points'][0]['coordinates']==[2,1]


@pytest.mark.parametrize('rows,message',[
    ([['x','x'],[1,2]],'重复'),
    ([['x',None],[1,2]],'列名'),
    ([['x','y']],'没有数据'),
])
def test_bad_structure(client,rows,message):
    response=upload(client,rows)
    assert response.status_code==422 and message in response.json()['detail']


def test_file_limits_and_bad_content(client):
    assert upload(client,raw=b'not excel').status_code==422
    assert upload(client,raw=b'').status_code==422
    assert upload(client,raw=b'x',name='file.csv').status_code==422
    assert upload(client,raw=b'x'*(5*1024*1024+1)).status_code==413
    assert upload(client,[['x','y']]+[[1,2]]*3001).status_code==422
    assert upload(client,[[f'c{i}' for i in range(51)],[1]*51]).status_code==422
    assert upload(client,[['x','y'],[1,2]],headers={}).status_code==400


def test_invalid_values_and_coincident_points(client):
    data=upload(client,[['x','y'],[1,2],[1,2],[None,3],[True,2],['5',3],[10**13,2]]).json()
    info=client.post(BASE+'/preview',headers=H,json={'dataset_id':data['id'],'features':['c0','c1']}).json()
    assert info['sample_count']==2 and len(info['excluded'])==4
    response=analyze(client,data)
    assert response.status_code==422 and '重合' in response.json()['detail']
    text=upload(client,[['书名','分类'],['甲','文学'],['乙','历史']]).json()
    assert text['default_features']==[]
    assert analyze(client,text,['c0','c1']).status_code==422


def test_submission_validation_and_multiple_rows(client):
    data=upload(client,[['x','y']]+[[i,i*2] for i in range(150)]).json()
    result=analyze(client,data).json()
    assert result['sample_count']==150 and sum(g['count'] for g in result['groups'])==150
    for counts,description in [([1,1],'有特点'),([True,149],'有特点'),([-1,151],'有特点'),([75,75],'   ')]:
        assert client.post(BASE+'/submissions',headers=H,json={'result_id':result['id'],'counts':counts,'description':description}).status_code==422
