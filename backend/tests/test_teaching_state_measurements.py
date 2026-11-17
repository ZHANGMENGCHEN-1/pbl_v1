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


def test_survey_numbers_span_sessions_and_keep_entry_groups_separate(client):
    first=measure(client,sorting(client)['id']).json()
    assert (first['student_survey_no'],first['session_survey_no'],first['activity_survey_no'],first['activity_number'])==(1,1,1,2)
    second=measure(client,sorting(client)['id'],request='measurement-2').json()
    assert (second['student_survey_no'],second['session_survey_no'],second['activity_survey_no'])==(2,2,2)
    other=client.post(ROOT+'/activities/explain_algorithm/submissions',headers=OTHER,json={'order':['data','count','centers','calculate']}).json()
    third=measure(client,other['id'],headers=OTHER).json()
    assert (third['student_survey_no'],third['session_survey_no'],third['activity_survey_no'])==(3,1,1)
    b_headers={'X-Session-ID':'another-entry-session-0001'}
    client.post(ROOT+'/student',headers=b_headers,json={'class_name':'C班','student_number':'001','source_route':'teaching-agent'})
    b_submission=client.post(ROOT+'/activities/explain_algorithm/submissions',headers=b_headers,json={'order':['data','count','centers','calculate']}).json()
    b=measure(client,b_submission['id'],headers=b_headers).json()
    assert b['student_survey_no']==1
    with store.connection() as db:
        rows=db.execute('SELECT * FROM teaching_state_measurement_records ORDER BY submitted_at').fetchall()
        assert len(rows)==4 and rows[0]['difficulty']==4 and rows[0]['self_efficacy']==5
        assert rows[0]['questionnaire_version']=='learning-state-v1'


def test_survey_timing_and_retries_preserve_original_metadata(client):
    submission=sorting(client)
    body={'submission_id':submission['id'],'request_id':'timed-survey','ratings':RATINGS,
          'started_at':'2026-11-17T10:00:00+08:00','response_duration_ms':12345,'response_mode':'slider-5point-v1'}
    first=client.post(ROOT+'/state-measurements',headers=H,json=body).json()
    assert first['started_at']=='2026-11-17T02:00:00+00:00'
    assert first['response_duration_ms']==12345 and first['response_mode']=='slider-5point-v1'
    assert first['survey_phase']=='post_activity'
    retry=client.post(ROOT+'/state-measurements',headers=H,json={**body,'response_duration_ms':20000}).json()
    assert retry==first
    for invalid in [-1,True,1.5]:
        assert client.post(ROOT+'/state-measurements',headers=H,json={**body,'response_duration_ms':invalid}).status_code==422


def test_legacy_survey_migration_preserves_answers_and_stable_numbers(tmp_path,monkeypatch):
    from app.projects.teaching import measurements
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'old-surveys.db'))
    with store.connection() as db:
        db.execute('''CREATE TABLE teaching_state_measurements(id TEXT PRIMARY KEY,project TEXT,session TEXT,class_name TEXT,student_number TEXT,source_route TEXT,activity TEXT,submission_id TEXT,ratings TEXT,created TEXT,request_id TEXT)''')
        for id,session in [('old-1','session-1'),('old-2','session-1'),('old-3','session-2')]:
            db.execute('INSERT INTO teaching_state_measurements VALUES(?,?,?,?,?,?,?,?,?,?,?)',(id,'teaching-agent',session,'七年级1班','001','meaning-making','group_books',id,json.dumps(RATINGS),'2026-11-17T00:00:00+00:00',id))
        measurements.init(db)
        first=[dict(r) for r in db.execute('SELECT * FROM teaching_state_measurements ORDER BY id')]
        assert [r['student_survey_no'] for r in first]==[1,2,3]
        assert [r['session_survey_no'] for r in first]==[1,2,1]
        assert all(json.loads(r['ratings'])==RATINGS and r['started_at'] is None and r['response_duration_ms'] is None for r in first)
        assert all(r['questionnaire_version']=='legacy-unspecified' for r in first)
        measurements.init(db)
        assert [dict(r) for r in db.execute('SELECT * FROM teaching_state_measurements ORDER BY id')]==first
