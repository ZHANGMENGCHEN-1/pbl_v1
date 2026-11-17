import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.shared import store

ROOT = '/api/projects/teaching-agent'
H = {'X-Session-ID': 'self-report-session-01'}
RATINGS = {
    'value_importance': 5,
    'interest': 4,
    'knowledge_importance': 5,
    'performance_efficacy': 3,
    'difficult_knowledge_efficacy': 2,
    'overall_efficacy': 4,
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'self-report.db'))
    with TestClient(app) as client:
        assert client.post(ROOT + '/student', headers=H, json={'class_name': 'B班', 'student_number': '001', 'source_route': 'teaching-agent'}).status_code == 200
        yield client


def submit(client, ratings=None, request='self-report-1', headers=H):
    return client.post(ROOT + '/self-report', headers=headers, json={
        'ratings': RATINGS if ratings is None else ratings,
        'request_id': request,
        'started_at': '2026-11-17T10:00:00+08:00',
        'response_duration_ms': 42000,
        'response_mode': 'slider-5point-v1',
        'questionnaire_version': 'learning-self-report-v1',
    })


def test_six_item_self_report_saves_identity_and_is_idempotent(client):
    first = submit(client)
    assert first.status_code == 200
    saved = first.json()
    assert saved['ratings'] == RATINGS
    assert saved['started_at'] == '2026-11-17T02:00:00+00:00'
    assert saved['response_duration_ms'] == 42000
    assert submit(client).json() == saved
    assert submit(client, request='retry-new-id').json() == saved
    assert submit(client, ratings={**RATINGS, 'interest': 5}).status_code == 409
    with store.connection() as db:
        rows = db.execute('SELECT * FROM teaching_self_reports').fetchall()
        assert len(rows) == 1
        row = rows[0]
        assert row['class_name'] == 'B班' and row['student_number'] == '001'
        assert row['source_route'] == 'teaching-agent' and row['session'] == H['X-Session-ID']
        assert json.loads(row['ratings']) == RATINGS
        assert db.execute("SELECT COUNT(*) FROM teaching_events WHERE type='self_report_submitted'").fetchone()[0] == 1


@pytest.mark.parametrize('value', [0, 6, 1.5, True, '4', None])
def test_invalid_self_report_rating_is_rejected(client, value):
    assert submit(client, ratings={**RATINGS, 'interest': value}).status_code == 422


def test_missing_answers_and_missing_identity_are_rejected(client):
    missing = {key: value for key, value in RATINGS.items() if key != 'overall_efficacy'}
    assert submit(client, ratings=missing).status_code == 422
    other = {'X-Session-ID': 'self-report-session-02'}
    assert submit(client, headers=other).status_code == 409


@pytest.mark.parametrize('source', ['teaching-agent', 'meaning-making', 'learning-activities'])
def test_three_class_entries_can_submit_same_questionnaire(tmp_path, monkeypatch, source):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / f'{source}.db'))
    with TestClient(app) as client:
        headers = {'X-Session-ID': f'{source}-self-report-01'}
        assert client.post(ROOT + '/student', headers=headers, json={'class_name': '测试班', 'student_number': '003', 'source_route': source}).status_code == 200
        response = submit(client, headers=headers)
        assert response.status_code == 200 and response.json()['ratings'] == RATINGS
        with store.connection() as db:
            row = db.execute('SELECT source_route,ratings FROM teaching_self_reports').fetchone()
            assert row['source_route'] == source and json.loads(row['ratings']) == RATINGS
            record = db.execute('SELECT * FROM teaching_self_report_records').fetchone()
            assert record['value_importance'] == 5 and record['overall_efficacy'] == 4
