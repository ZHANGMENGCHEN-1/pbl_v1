import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.shared import store

ROOT='/api/projects/teaching-agent'
H={'X-Session-ID':'meaning-measurement-session-01'}
OTHER={'X-Session-ID':'meaning-measurement-session-02'}
RATINGS={'difficulty':4,'boredom':2,'frustration':3,'self_efficacy':5}


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'measurement.db'))
    with TestClient(app) as client:
        for headers in [H,OTHER]:
            assert client.post(ROOT+'/student',headers=headers,json={'class_name':'C班','student_number':'001','source_route':'meaning-making'}).status_code==200
        yield client


def sorting(client,correct=True):
    order=['data','count','centers','calculate'] if correct else ['calculate','centers','count','data']
    return client.post(ROOT+'/activities/explain_algorithm/submissions',headers=H,json={'order':order}).json()


def measure(client,id,headers=H,request='measurement-1',ratings=None):
    return client.post(ROOT+'/state-measurements',headers=headers,json={'submission_id':id,'request_id':request,'ratings':RATINGS if ratings is None else ratings})


def test_measurement_identity_link_idempotency_and_events(client):
    saved=sorting(client)
    first=measure(client,saved['id'])
    assert first.status_code==200
    assert first.json()['ratings']==RATINGS and first.json()['activity_id']=='explain_algorithm'
    assert measure(client,saved['id']).json()==first.json()
    assert measure(client,saved['id'],request='retry-new-id').json()==first.json()
    assert measure(client,saved['id'],ratings={**RATINGS,'boredom':5}).status_code==409
    assert measure(client,saved['id'],headers=OTHER).status_code==404
    another=sorting(client)
    assert measure(client,another['id']).status_code==409
    with store.connection() as db:
        rows=db.execute('SELECT * FROM teaching_state_measurements').fetchall()
        assert len(rows)==1
        row=rows[0]
        assert row['class_name']=='C班' and row['student_number']=='001' and row['source_route']=='meaning-making'
        assert row['session']==H['X-Session-ID'] and row['submission_id']==saved['id'] and row['created']
        assert json.loads(row['ratings'])==RATINGS
        assert db.execute("SELECT COUNT(*) FROM teaching_events WHERE type='state_measurement_submitted'").fetchone()[0]==1


@pytest.mark.parametrize('value',[0,6,1.5,True,'4',None])
def test_invalid_rating_is_rejected(client,value):
    assert measure(client,sorting(client)['id'],ratings={**RATINGS,'difficulty':value}).status_code==422


def test_missing_answer_wrong_attempt_and_unknown_submission_rejected(client):
    assert measure(client,sorting(client,False)['id']).status_code==409
    missing={k:v for k,v in RATINGS.items() if k!='frustration'}
    assert measure(client,sorting(client)['id'],ratings=missing).status_code==422
    headers={'X-Session-ID':'ordinary-teaching-session-01'}
    client.post(ROOT+'/student',headers=headers,json={'class_name':'B班','student_number':'002'})
    assert measure(client,'unknown',headers=headers).status_code==404
    assert measure(client,'unknown').status_code==404


@pytest.mark.parametrize('source',['teaching-agent','learning-activities'])
def test_a_and_b_can_save_identical_measurements(client,source):
    headers={'X-Session-ID':'other-class-measure-session'}
    client.post(ROOT+'/student',headers=headers,json={'class_name':'测试班','student_number':'003','source_route':source})
    saved=client.post(ROOT+'/activities/explain_algorithm/submissions',headers=headers,json={'order':['data','count','centers','calculate']}).json()
    assert measure(client,saved['id'],headers=headers).status_code==200
    with store.connection() as db:
        assert db.execute('SELECT source_route FROM teaching_state_measurements').fetchone()[0]==source


def test_activity_one_final_submission_can_be_measured(client):
    path=ROOT+'/activities/group_books'
    step=client.post(path+'/steps',headers=H,json={'centers':[2,11]}).json()
    while not step['converged']:
        step=client.post(path+'/steps',headers=H,json={'previous_id':step['id']}).json()
    saved=client.post(path+'/submissions',headers=H,json={'result_id':step['id'],'counts':[3,2],'centers':step['centers_after']}).json()
    response=measure(client,saved['id'])
    assert response.status_code==200 and response.json()['activity_id']=='group_books'
