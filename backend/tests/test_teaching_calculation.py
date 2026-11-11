import pytest
from fastapi.testclient import TestClient
from app.main import app

BASE = '/api/projects/teaching-agent/activities/group_books'
HEADERS = {'X-Session-ID': 'teaching-test-session-123'}

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'teaching.db'))
    with TestClient(app) as client:
        yield client

def post(client, path, data, headers=HEADERS):
    return client.post(BASE + path, json=data, headers=headers)

def test_rounds_precision_and_submission(client):
    first = post(client, '/steps', {'centers': [2, 11]}).json()
    assert first['centers_after'] == [4, 43/3]
    assert [r['group'] for r in first['records']] == [0, 0, 1, 1, 1]
    assert first['records'][0]['distances'] == [0, 9]
    assert not first['converged']
    assert post(client, '/submissions', {'result_id':first['id'], 'counts':[2,3], 'centers':[4,14.3]}).status_code == 422
    assert post(client, '/steps', {'previous_id':first['id'], 'centers':[4,14.3]}).status_code == 422
    second = post(client, '/steps', {'previous_id':first['id']}).json()
    assert second['centers_before'] == [4,43/3]
    assert second['centers_after'] == [17/3,17]
    assert post(client, '/steps', {'previous_id':first['id']}).json()['id'] == second['id']
    third = post(client, '/steps', {'previous_id':second['id']}).json()
    assert third['converged'] and third['round'] == 3
    assert third['teaching_context']['groups'][0]['count'] == 3
    assert post(client, '/steps', {'previous_id':third['id']}).status_code == 409
    # A plausible but incorrect student answer is preserved and does not block progress.
    saved = post(client, '/submissions', {'result_id':third['id'], 'counts':[4,1], 'centers':[1,18]})
    assert saved.status_code == 200
    payload = saved.json()['payload']
    assert payload['student_result'] == {'counts':[4,1], 'centers':[1,18]}
    assert payload['tool_result'] == {'counts':[3,2], 'centers':[17/3,17]}
    state = client.get(BASE+'/state', headers=HEADERS).json()
    assert len(state['steps']) == 3 and len(state['submissions']) == 1
    assert state['submissions'][0]['payload'] == payload
    other={'X-Session-ID':'other-student-session-123'}
    assert client.get(BASE+'/state', headers=other).json()['steps'] == []
    assert post(client, '/steps', {'previous_id':first['id']}, other).status_code == 404
    assert post(client, '/submissions', {'result_id':third['id'], 'counts':[4,1], 'centers':[1,18]}, other).status_code == 404

def test_not_fixed_three_rounds_and_empty_group(client):
    r=post(client,'/steps',{'centers':[17/3,17]}).json()
    assert r['converged'] and r['round']==1
    assert post(client,'/submissions',{'result_id':r['id'],'counts':[3,3],'centers':[1,18]}).status_code==422
    assert post(client,'/steps',{'centers':[4,4]}).status_code==422
    assert post(client,'/steps',{'centers':[-1,21]}).status_code==422
    empty=post(client,'/steps',{'centers':[0,1]}).json()
    assert empty['warnings'] and empty['centers_after'][0]==0
    tie=post(client,'/steps',{'centers':[0,4]}).json()
    assert tie['records'][0]['group']==0
    assert client.get(BASE+'/state').status_code==400
