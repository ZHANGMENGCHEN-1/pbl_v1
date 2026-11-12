"""Identity snapshots and append-only teaching evidence. Times are server UTC."""
import json
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from ...shared import store
from .routes import PROJECT, BOOKS, get_step, session_id

router = APIRouter(prefix='/api/projects/teaching-agent', tags=['teaching'])


def student(session):
    with store.connection() as db:
        row = db.execute('SELECT class_name,student_number FROM teaching_students WHERE project=? AND session=?', (PROJECT, session)).fetchone()
    if not row:
        raise HTTPException(409, '请先填写班级和学号。')
    return dict(row)


def event(db, session, kind, activity=None, reference=None, data=None, event_id=None):
    identity = db.execute('SELECT class_name,student_number FROM teaching_students WHERE project=? AND session=?', (PROJECT, session)).fetchone()
    if not identity:
        return
    db.execute('INSERT OR IGNORE INTO teaching_events(id,project,session,class_name,student_number,activity,type,reference_id,data,created) VALUES(?,?,?,?,?,?,?,?,?,?)',
               (event_id or str(uuid4()), PROJECT, session, identity['class_name'], identity['student_number'], activity, kind, reference, json.dumps(data or {}, ensure_ascii=False), store.now()))


def init():
    with store.connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS teaching_events(id TEXT PRIMARY KEY,project TEXT,session TEXT,class_name TEXT,student_number TEXT,activity TEXT,type TEXT,reference_id TEXT,data TEXT,created TEXT);
        CREATE INDEX IF NOT EXISTS teaching_events_student ON teaching_events(class_name,student_number,created);
        CREATE INDEX IF NOT EXISTS teaching_events_session ON teaching_events(project,session,created);
        CREATE TABLE IF NOT EXISTS teaching_round_answers(id TEXT PRIMARY KEY,project TEXT,session TEXT,result_id TEXT,payload TEXT,created TEXT,class_name TEXT,student_number TEXT,request_id TEXT,attempt_no INTEGER);
        ''')
        for table in ('teaching_submissions', 'teaching_chats', 'teaching_steps', 'teaching_datasets', 'teaching_analyses'):
            columns = {r['name'] for r in db.execute(f'PRAGMA table_info({table})')}
            extra = {'class_name': 'TEXT', 'student_number': 'TEXT'}
            if table == 'teaching_submissions':
                extra.update(request_id='TEXT', attempt_no='INTEGER')
            if table == 'teaching_chats':
                extra.update(first_response_at='TEXT', model='TEXT', prompt_version='TEXT', stop_reason='TEXT')
            for name, kind in extra.items():
                if name not in columns:
                    db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {kind}')
            db.execute(f'CREATE INDEX IF NOT EXISTS {table}_student ON {table}(class_name,student_number,created)')
            # Old records remain NULL unless an actual registered session identifies them.
            db.execute(f'''UPDATE {table} SET class_name=(SELECT class_name FROM teaching_students s WHERE s.project={table}.project AND s.session={table}.session),
                         student_number=(SELECT student_number FROM teaching_students s WHERE s.project={table}.project AND s.session={table}.session)
                         WHERE class_name IS NULL AND EXISTS(SELECT 1 FROM teaching_students s WHERE s.project={table}.project AND s.session={table}.session)''')
            db.executescript(f'''
            CREATE TRIGGER IF NOT EXISTS {table}_identity AFTER INSERT ON {table}
            BEGIN
              UPDATE {table} SET class_name=(SELECT class_name FROM teaching_students WHERE project=NEW.project AND session=NEW.session),
              student_number=(SELECT student_number FROM teaching_students WHERE project=NEW.project AND session=NEW.session) WHERE id=NEW.id;
            END;
            ''')
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS teaching_submission_request ON teaching_submissions(project,session,activity,request_id) WHERE request_id IS NOT NULL')
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS teaching_round_request ON teaching_round_answers(project,session,request_id)')


def save_submission(db, session, activity, result_id, payload, request_id):
    existing = db.execute('SELECT * FROM teaching_submissions WHERE project=? AND session=? AND activity=? AND request_id=?', (PROJECT, session, activity, request_id)).fetchone()
    if existing:
        if existing['result_id'] != result_id or json.loads(existing['payload'])['student_result'] != payload['student_result']:
            raise HTTPException(409, '提交编号已用于其他答案，请重新提交。')
        return {'id': existing['id'], 'result_id': result_id, 'created': existing['created'], 'payload': json.loads(existing['payload']), 'attempt_no': existing['attempt_no']}
    attempt = db.execute('SELECT COUNT(*) FROM teaching_submissions WHERE project=? AND session=? AND activity=?', (PROJECT, session, activity)).fetchone()[0] + 1
    saved = {'id': str(uuid4()), 'result_id': result_id, 'created': store.now(), 'payload': payload, 'attempt_no': attempt}
    db.execute('INSERT INTO teaching_submissions(id,project,session,activity,result_id,payload,created,request_id,attempt_no) VALUES(?,?,?,?,?,?,?,?,?)',
               (saved['id'], PROJECT, session, activity, result_id, json.dumps(payload, ensure_ascii=False), saved['created'], request_id, attempt))
    event(db, session, 'submission_saved', activity, saved['id'], {'attempt_no': attempt})
    if activity != 'explain_algorithm' or payload['correct']:
        event(db, session, 'activity_completed', activity, saved['id'], event_id=f'completed:{session}:{activity}')
    return saved


class RoundInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    result_id: str = Field(min_length=1, max_length=80)
    groups: dict[str, StrictInt]
    request_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=80)


@router.post('/activities/group_books/round-answers')
def round_answers(body: RoundInput, x_session_id: str = Header(default='')):
    session = session_id(x_session_id)
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        result = get_step(db, session, body.result_id)
        if set(body.groups) != {b['id'] for b in BOOKS} or any(g not in (1, 2) for g in body.groups.values()):
            raise HTTPException(422, '请为五本书选择第1组或第2组。')
        previous = db.execute('SELECT * FROM teaching_round_answers WHERE project=? AND session=? AND request_id=?', (PROJECT, session, body.request_id)).fetchone()
        if previous:
            if previous['result_id'] != body.result_id or json.loads(previous['payload'])['groups'] != body.groups:
                raise HTTPException(409, '提交编号已用于其他答案。')
            return {'id': previous['id'], 'created': previous['created'], 'attempt_no': previous['attempt_no']}
        identity = student(session)
        attempt = db.execute('SELECT COUNT(*) FROM teaching_round_answers WHERE project=? AND session=? AND result_id=?', (PROJECT, session, body.result_id)).fetchone()[0] + 1
        saved = {'id': str(uuid4()), 'created': store.now(), 'attempt_no': attempt}
        payload = {'groups': body.groups, 'round': result['round'], 'centers': result['centers_before'], 'expected_groups': {b['id']: b['group'] + 1 for b in result['records']}}
        payload['correct'] = payload['groups'] == payload['expected_groups']
        db.execute('INSERT INTO teaching_round_answers VALUES(?,?,?,?,?,?,?,?,?,?)', (saved['id'], PROJECT, session, body.result_id, json.dumps(payload, ensure_ascii=False), saved['created'], identity['class_name'], identity['student_number'], body.request_id, attempt))
        event(db, session, 'round_answer_saved', 'group_books', saved['id'], {'attempt_no': attempt, 'correct': payload['correct']})
    return saved


class SortingInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    order: list[Literal['data', 'count', 'centers', 'calculate']] = Field(min_length=4, max_length=4)
    request_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=80)


@router.post('/activities/explain_algorithm/submissions')
def sorting(body: SortingInput, x_session_id: str = Header(default='')):
    session = session_id(x_session_id)
    if len(set(body.order)) != 4:
        raise HTTPException(422, '四个步骤都需要用到。')
    expected = ['data', 'count', 'centers', 'calculate']
    correct = body.order == expected
    reasons = [
        '先要拿到数据，整理好每本书的借阅次数，我们才知道要给哪些书分组。试着把“获取原始数据并整理”放到最前面。',
        '有了数据，要先想好分成几组，也就是需要几个中心点。还没确定数量，就不知道该选几个中心。把“确定中心点的数量”放在整理数据后面试试。',
        '先选好开始的中心，才能算每本书离哪个中心更近。试着把“随机选择中心点”放在“进行计算”前面。',
        '准备好数据、中心点的数量和开始的中心后，才开始计算距离、分组，再更新中心。把“进行计算”放在最后试试。',
    ]
    feedback = ('这个顺序很清楚！先整理数据，再确定需要几个中心，然后随机选出开始的中心，最后进行计算。计算时，我们会反复算距离、分组、更新中心，直到分组和中心稳定。你的排序已经提交了。'
                if correct else reasons[next(i for i, value in enumerate(body.order) if value != expected[i])] + ' 调整后可再次提交。')
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        return save_submission(db, session, 'explain_algorithm', None, {'kind': 'learning_result', 'student_result': {'order': body.order}, 'correct': correct, 'feedback': feedback, 'tool_result': {'order': ['data', 'count', 'centers', 'calculate']}}, body.request_id)


class EventInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=80)
    activity_id: Literal['group_books', 'explain_algorithm', 'explore_2d']
    type: Literal['activity_entered']


@router.post('/events')
def client_event(body: EventInput, x_session_id: str = Header(default='')):
    session = session_id(x_session_id)
    with store.connection() as db:
        event(db, session, body.type, body.activity_id, event_id=body.id)
    return {'saved': True}


@router.post('/chat/{id}/pause')
def pause_chat(id: str, x_session_id: str = Header(default='')):
    session = session_id(x_session_id)
    with store.connection() as db:
        row = db.execute('SELECT status,activity FROM teaching_chats WHERE id=? AND project=? AND session=?', (id, PROJECT, session)).fetchone()
        if not row:
            raise HTTPException(404, '找不到这次对话。')
        db.execute("UPDATE teaching_chats SET stop_reason='student_paused',status=CASE WHEN status='cancelled' THEN 'paused' ELSE status END WHERE id=?", (id,))
        event(db, session, 'chat_pause_requested', row['activity'], id, event_id=f'chat-pause:{id}')
    return {'saved': True}
