import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk

from app.main import app
from app.projects.teaching import chat, telemetry
from app.shared import store

ROOT = '/api/projects/teaching-agent'
H = {'X-Session-ID': 'telemetry-session-0001'}
OTHER = {'X-Session-ID': 'telemetry-session-0002'}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'telemetry.db'))
    with TestClient(app) as client:
        yield client


def register(client, headers=H):
    response = client.post(ROOT + '/student', headers=headers, json={'class_name': '七年级1班', 'student_number': '001'})
    assert response.status_code == 200


def test_identity_required_and_sorting_attempts_idempotent(client):
    path = ROOT + '/activities/explain_algorithm/submissions'
    wrong = {'order': ['calculate', 'centers', 'count', 'data'], 'request_id': 'attempt-1'}
    assert client.post(path, headers=H, json=wrong).status_code == 409
    register(client)
    one = client.post(path, headers=H, json=wrong).json()
    assert one['attempt_no'] == 1 and one['payload']['correct'] is False
    assert client.post(path, headers=H, json=wrong).json()['id'] == one['id']
    right = {'order': ['data', 'count', 'centers', 'calculate'], 'request_id': 'attempt-2'}
    two = client.post(path, headers=H, json=right).json()
    assert two['attempt_no'] == 2 and two['payload']['correct'] is True
    assert client.post(path, headers=H, json={**right, 'request_id': 'attempt-1'}).status_code == 409
    with store.connection() as db:
        records = db.execute('SELECT * FROM teaching_submissions ORDER BY attempt_no').fetchall()
        assert len(records) == 2
        assert all(r['class_name'] == '七年级1班' and r['student_number'] == '001' and r['created'] for r in records)
        events = db.execute('SELECT type FROM teaching_events').fetchall()
        assert [r['type'] for r in events].count('submission_saved') == 2
        assert [r['type'] for r in events].count('activity_completed') == 1
        assert [r['type'] for r in events].count('operation_failed') == 1


def test_round_answers_owned_and_preserved(client):
    register(client)
    register(client, OTHER)
    step = client.post(ROOT + '/activities/group_books/steps', headers=H, json={'centers': [2, 11]}).json()
    path = ROOT + '/activities/group_books/round-answers'
    wrong = {'result_id': step['id'], 'groups': {str(i): 1 for i in range(1, 6)}, 'request_id': 'round-1'}
    one = client.post(path, headers=H, json=wrong)
    assert one.status_code == 200
    assert client.post(path, headers=H, json=wrong).json()['id'] == one.json()['id']
    assert client.post(path, headers=OTHER, json=wrong).status_code == 404
    assert client.post(path, headers=H, json={**wrong, 'groups': {'1': 1}}).status_code == 422
    right = {**wrong, 'groups': {b['id']: b['group'] + 1 for b in step['records']}, 'request_id': 'round-2'}
    assert client.post(path, headers=H, json=right).json()['attempt_no'] == 2
    with store.connection() as db:
        rows = db.execute('SELECT * FROM teaching_round_answers ORDER BY attempt_no').fetchall()
        assert len(rows) == 2 and rows[0]['student_number'] == '001'
        assert json.loads(rows[0]['payload'])['correct'] is False
        assert json.loads(rows[1]['payload'])['correct'] is True
        assert db.execute('SELECT COUNT(*) FROM teaching_events WHERE type="activity_completed"').fetchone()[0] == 0


def test_chat_timestamps_identity_pause_and_failures(client, monkeypatch):
    register(client)
    register(client, OTHER)
    class Model:
        async def astream(self, messages):
            yield AIMessageChunk(content='先比较两边的距离。')
            yield AIMessageChunk(content='分到更近的中心。')
    monkeypatch.setattr(chat, 'make_model', lambda: Model())
    response = client.post(ROOT + '/chat', headers=H, json={'activity_id': 'group_books', 'question': '怎么分组？'})
    assert response.status_code == 200
    with store.connection() as db:
        row = db.execute('SELECT * FROM teaching_chats').fetchone()
        assert row['student_number'] == '001' and row['class_name'] == '七年级1班'
        assert row['created'] <= row['first_response_at'] <= row['finished']
        assert row['answer'] == '先比较两边的距离。分到更近的中心。'
        assert row['model'] and row['prompt_version'] and row['status'] == 'completed'
        id = row['id']
        db.execute("UPDATE teaching_chats SET status='cancelled' WHERE id=?", (id,))
    assert client.post(ROOT + f'/chat/{id}/pause', headers=OTHER).status_code == 404
    assert client.post(ROOT + f'/chat/{id}/pause', headers=H).status_code == 200
    chat.save_finish(id, '部分回复', 'cancelled')
    with store.connection() as db:
        assert db.execute('SELECT status FROM teaching_chats WHERE id=?', (id,)).fetchone()[0] == 'paused'
    def failure():
        raise RuntimeError('private provider detail')
    monkeypatch.setattr(chat, 'make_model', failure)
    with pytest.raises(RuntimeError, match='private provider detail'):
        client.post(ROOT + '/chat', headers=H, json={'activity_id': 'group_books', 'question': '失败也记录吗？'})
    with store.connection() as db:
        row = db.execute("SELECT * FROM teaching_chats WHERE status='error'").fetchone()
        assert row['question'] == '失败也记录吗？' and row['finished'] and row['student_number'] == '001'
        assert 'private' not in row['error']


def test_client_events_are_deduplicated_and_cannot_forge_success(client):
    register(client)
    data = {'id': 'entry-1', 'activity_id': 'group_books', 'type': 'activity_entered'}
    for _ in range(2):
        assert client.post(ROOT + '/events', headers=H, json=data).status_code == 200
    assert client.post(ROOT + '/events', headers=H, json={**data, 'id': 'fake', 'type': 'activity_completed'}).status_code == 422
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM teaching_events WHERE type="activity_entered"').fetchone()[0] == 1


def test_migration_preserves_unidentified_history(tmp_path, monkeypatch):
    from app.projects.teaching import routes, excel
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'legacy.db'))
    routes.init()
    excel.init()
    chat.init()
    with store.connection() as db:
        db.execute('INSERT INTO teaching_submissions(id,project,session,activity,payload,created) VALUES(?,?,?,?,?,?)', ('legacy', 'teaching-agent', 'legacy-session-0001', 'group_books', '{}', store.now()))
    telemetry.init()
    telemetry.init()
    with store.connection() as db:
        row = db.execute('SELECT * FROM teaching_submissions WHERE id="legacy"').fetchone()
        assert row['payload'] == '{}' and row['student_number'] is None and row['class_name'] is None
