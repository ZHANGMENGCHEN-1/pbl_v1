import asyncio
import json
import os
from contextlib import aclosing
from typing import Literal
from uuid import uuid4
from urllib.parse import urlparse

from anyio import CancelScope
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool

from ...shared import store
from .routes import BOOKS, PROJECT, get_step, session_id
from .excel import owned_analysis, owned_dataset, selected_rows
from .pedagogy import TASKS, system_prompt
from . import meaning_making

router = APIRouter(prefix='/api/projects/teaching-agent', tags=['teaching-chat'])


def init():
    with store.connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS teaching_chats(
          id TEXT PRIMARY KEY,project TEXT,session TEXT,activity TEXT,question TEXT,
          answer TEXT,status TEXT,context TEXT,created TEXT,finished TEXT,error TEXT);
        CREATE INDEX IF NOT EXISTS teaching_chats_session ON teaching_chats(project,session,created);
        ''')
        db.execute("UPDATE teaching_chats SET status='interrupted',finished=? WHERE status='running'", (store.now(),))


class LearningContext(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    phase: Literal['dialogue', 'task'] = 'task'
    screen: Literal['task', 'reflection', 'introduction'] | None = None
    measurement_id: str | None = Field(default=None, min_length=1, max_length=80)
    step_id: str | None = Field(default=None, max_length=80)
    analysis_id: str | None = Field(default=None, max_length=80)
    dataset_id: str | None = Field(default=None, max_length=80)
    features: list[str] = Field(default_factory=list, max_length=2)
    initial_centers: list[float | None] = Field(default_factory=list, max_length=2)
    step_order: list[Literal['data', 'count', 'centers', 'calculate']] = Field(default_factory=list, max_length=4)


class ChatInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    activity_id: Literal['group_books', 'explain_algorithm', 'explore_2d']
    question: str = Field(min_length=1, max_length=2000)
    context: LearningContext = Field(default_factory=LearningContext)
    purpose: Literal['question', 'reflection_opening'] = 'question'

    @field_validator('question')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('请输入想问小知的问题。')
        return value.strip()


def short_analysis(result):
    value = result['teaching_context']
    return {**{key: value[key] for key in ('filename', 'sheet', 'dataset_id', 'dataset_version', 'sample_count', 'total_count', 'excluded_count', 'ranges', 'converged', 'iterations', 'distance', 'scaling', 'interpretation_limits')},
            'verified_from': 'database_real_kmeans', 'analysis_id': result['id'],
            'axes': [{'axis': axis, 'name': f['name'], 'field_id': f['id']} for axis, f in zip(['横轴', '纵轴'], result['features'])],
            'groups': [{'display_group': g['group'] + 1, 'count': g['count'], 'center': g['center']} for g in result['groups']],
            'point_examples': [{'excel_row': p['row'], 'coordinates': p['coordinates'], 'display_group': p['group'] + 1} for group in range(2) for p in [r for r in result['points'] if r['group'] == group][:2]],
            'excluded_examples': value['excluded'][:3], 'warnings': value['warnings'][:3]}


def learning_context(session, body):
    current = body.context
    context = {'activity_id': body.activity_id, 'phase': current.phase, 'progress_authority': 'platform_only'}
    context['current_task'] = {**TASKS[body.activity_id], 'activity_id': body.activity_id, 'screen': current.screen or ('reflection' if current.measurement_id else 'task' if current.phase == 'task' else 'introduction')}
    with store.connection() as db:
        if body.purpose == 'reflection_opening' and not current.measurement_id:
            raise HTTPException(422, '请先完成状态测量。')
        if current.measurement_id:
            measurement = db.execute('SELECT * FROM teaching_state_measurements WHERE id=? AND project=? AND session=? AND activity=?', (current.measurement_id, PROJECT, session, body.activity_id)).fetchone()
            if not measurement:
                raise HTTPException(404, '找不到当前活动的状态测量。')
            if measurement['source_route'] != 'meaning-making' or current.phase != 'dialogue' or context['current_task']['screen'] != 'reflection':
                raise HTTPException(403, '当前测量不用于意义建构对话。')
            context['meaning_making'] = {'measurement_id': measurement['id'], 'submission_id': measurement['submission_id'], 'questionnaire_version': measurement['questionnaire_version'], 'ratings': json.loads(measurement['ratings']), 'strategy_version': meaning_making.PROMPT_VERSION, 'generation_attempts': 1, 'delivery': 'streaming'}
            context['meaning_making']['strategy'] = meaning_making.select_strategy(context['meaning_making']['ratings'])
            completed = db.execute("""SELECT COUNT(*) FROM teaching_chats
                WHERE project=? AND session=? AND activity=? AND status='completed'
                AND json_extract(context, '$.meaning_making.measurement_id')=?
                AND COALESCE(json_extract(context, '$.current_task.screen'), 'reflection')=?""",
                (PROJECT, session, body.activity_id, current.measurement_id, context['current_task']['screen'])).fetchone()[0]
            turn = completed + 1
            context['meaning_making']['dialogue_turn'] = turn
            context['meaning_making']['response_mode'] = meaning_making.response_mode(turn)
            context['question_source'] = 'platform' if body.purpose == 'reflection_opening' else 'student'
        if body.activity_id == 'group_books':
            context['books'] = BOOKS
            context['student_selected_centers'] = current.initial_centers
            context['calculation'] = get_step(db, session, current.step_id)['teaching_context'] if current.step_id else None
        elif body.activity_id == 'explain_algorithm':
            context['student_draft_order'] = current.step_order
            context['draft_source'] = 'student_ui_not_a_verified_submission'
            row = db.execute("SELECT payload FROM teaching_submissions WHERE project=? AND session=? AND activity='group_books' ORDER BY created DESC,id DESC LIMIT 1", (PROJECT, session)).fetchone()
            payload = json.loads(row[0]) if row else None
            context['previous_calculation'] = payload['calculation_result']['teaching_context'] if payload else None
        else:
            context['analysis'] = None
            if current.dataset_id:
                data = owned_dataset(db, session, current.dataset_id)
                fields = {c['id']: c for c in data['columns']}
                if any(f not in fields for f in current.features):
                    raise HTTPException(409, '分析列与当前文件不一致，请重新选择后再提问。')
                context['uploaded_data'] = {'filename': data['filename'], 'sheet': data['sheet'], 'dataset_id': data['id'], 'version': data['version'], 'total_count': data['row_count'],
                                            'selected_columns': [{'id': f, 'name': fields[f]['name']} for f in current.features]}
                if len(set(current.features)) == 2:
                    _, valid, excluded = selected_rows(data, current.features)
                    context['uploaded_data'].update(valid_count=len(valid), excluded_count=len(excluded))
            if current.analysis_id:
                result = owned_analysis(db, session, current.analysis_id)
                if not current.dataset_id or result['dataset_id'] != current.dataset_id or [f['id'] for f in result['features']] != current.features:
                    raise HTTPException(409, '图表与当前文件或分析列不一致，请重新运行后再提问。')
                context['analysis'] = short_analysis(result)
        if current.measurement_id:
            row = db.execute('SELECT payload,result_id FROM teaching_submissions WHERE id=? AND project=? AND session=?', (measurement['submission_id'], PROJECT, session)).fetchone()
        else:
            row = db.execute('SELECT payload,result_id FROM teaching_submissions WHERE project=? AND session=? AND activity=? ORDER BY created DESC,id DESC LIMIT 1', (PROJECT, session, body.activity_id)).fetchone()
        if row:
            payload = json.loads(row[0])
            if current.measurement_id:
                context['measured_submission'] = {'student_result': payload['student_result'], 'actual_result': payload['tool_result'], 'comparison': payload.get('comparison'), 'correct': payload.get('correct'), 'feedback': payload.get('feedback')}
                if body.activity_id == 'group_books':
                    context['calculation'] = get_step(db, session, row['result_id'])['teaching_context']
                elif body.activity_id == 'explore_2d':
                    context['analysis'] = short_analysis(owned_analysis(db, session, row['result_id']))
            context['last_student_submission'] = {'student_result': payload['student_result'], 'actual_result': payload['tool_result'], 'result_source': 'saved_submission',
                                                  'matches_current_result': row['result_id'] in [current.step_id, current.analysis_id]}
        recent = db.execute("SELECT question,answer,context FROM teaching_chats WHERE project=? AND session=? AND activity=? AND status='completed' ORDER BY created DESC,id DESC LIMIT 12", (PROJECT, session, body.activity_id)).fetchall()
        history = [pair for pair in recent if json.loads(pair['context']).get('meaning_making', {}).get('measurement_id') == current.measurement_id][:3]
    bounded, size = [], 0
    for pair in history:
        size += len(pair['question']) + len(pair['answer'])
        if size > 2000:
            break
        bounded.append(pair)
    return context, list(reversed(bounded))


def make_model():
    if not os.getenv('LLM_API_KEY', '').strip():
        raise HTTPException(503, '小知还没有连接好，请老师检查模型设置后再试。')
    try:
        base_url = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1')
        model = os.getenv('LLM_MODEL', 'gpt-4o-mini')
        extra = {}
        if urlparse(base_url).hostname in ('open.bigmodel.cn', 'api.z.ai'):
            name = model.lower()
            if name.startswith('glm-5.3'):
                # GLM 5.3 rejects disabled thinking; low is its minimum effort.
                extra = {'thinking': {'type': 'enabled'}, 'reasoning_effort': 'low'}
            elif name in ('glm-5.2', 'glm-5.1', 'glm-5', 'glm-5-turbo', 'glm-5v-turbo', 'glm-4.6', 'glm-4.5'):
                extra = {'thinking': {'type': 'disabled'}}
        return ChatOpenAI(api_key=os.environ['LLM_API_KEY'], base_url=base_url,
                          model=model, temperature=0.4, extra_body=extra or None,
                          timeout=float(os.getenv('LLM_TIMEOUT_SECONDS', '60')), max_retries=0,
                          max_tokens=max(512, min(int(os.getenv('LLM_MAX_OUTPUT_TOKENS', '512')), 1200)),
                          streaming=True, stream_usage=False)
    except (ValueError, TypeError):
        raise HTTPException(503, '模型配置无法读取，请老师检查后端模型参数。')


def save_start(session, body, context):
    id = str(uuid4())
    with store.connection() as db:
        db.execute('INSERT INTO teaching_chats(id,project,session,activity,question,answer,status,context,created,finished,error) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                   (id, PROJECT, session, body.activity_id, body.question, '', 'running', json.dumps(context, ensure_ascii=False), store.now(), None, None))
        db.execute('UPDATE teaching_chats SET model=?,prompt_version=? WHERE id=?', (os.getenv('LLM_MODEL', 'gpt-4o-mini'), meaning_making.PROMPT_VERSION if context.get('meaning_making') else 'teaching-v2-short-natural', id))
        from .telemetry import event
        event(db, session, 'reflection_opening_requested' if body.purpose == 'reflection_opening' else 'help_requested', body.activity_id, id)
    return id


def save_finish(id, answer, status, error=None):
    with store.connection() as db:
        if status == 'cancelled':
            reason = db.execute('SELECT stop_reason FROM teaching_chats WHERE id=?', (id,)).fetchone()
            if reason and reason['stop_reason'] == 'student_paused':
                status = 'paused'
        db.execute('UPDATE teaching_chats SET answer=?,status=?,finished=?,error=? WHERE id=?', (answer, status, store.now(), error, id))
        from .telemetry import event
        row = db.execute('SELECT session,activity FROM teaching_chats WHERE id=?', (id,)).fetchone()
        event(db, row['session'], 'chat_finished', row['activity'], id, {'status': status}, event_id=f'chat-finished:{id}')


def save_first_response(id):
    with store.connection() as db:
        db.execute('UPDATE teaching_chats SET first_response_at=COALESCE(first_response_at,?) WHERE id=?', (store.now(), id))


def public_error(exc):
    name = type(exc).__name__
    if isinstance(exc, TimeoutError) or 'Timeout' in name:
        return '小知等模型回复超时了，你可以稍后再问一次。'
    if 'Authentication' in name or 'PermissionDenied' in name:
        return '模型连接的密钥或权限有问题，请老师检查后端配置。'
    if 'RateLimit' in name:
        return '现在提问有点多，或模型额度不足，请稍后再试。'
    return '这次模型回复没有完成，请稍后再试；如果一直失败，请老师检查模型服务。'


def content_text(chunk):
    content = chunk.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text')
    return ''


async def model_chunks(model, messages):
    """Keep cancellation and heartbeats working while waiting for model text."""
    async with aclosing(model.astream(messages)) as tokens:
        task = asyncio.create_task(anext(tokens, None))
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=8)
                if not done:
                    yield None
                    continue
                chunk = task.result()
                if chunk is None:
                    return
                yield chunk
                task = asyncio.create_task(anext(tokens, None))
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@router.post('/chat')
async def chat(body: ChatInput, request: Request, x_session_id: str = Header(default='')):
    session = session_id(x_session_id)
    context, history = await run_in_threadpool(learning_context, session, body)
    id = await run_in_threadpool(save_start, session, body, context)
    try:
        model = make_model()
    except Exception as exc:
        await run_in_threadpool(save_finish, id, '', 'error', public_error(exc))
        raise
    messages = [SystemMessage(content=meaning_making.system_prompt(context) if context.get('meaning_making') else system_prompt(body.activity_id, context))]
    for pair in history:
        messages.extend([HumanMessage(content=pair['question']), AIMessage(content=pair['answer'])])
    messages.append(HumanMessage(content=body.question))

    async def stream():
        answer, status, error = '', 'cancelled', None
        def event(kind, **data):
            return 'data: ' + json.dumps({'type': kind, 'data': data}, ensure_ascii=False) + '\n\n'
        try:
            yield event('start', chat_id=id)
            first_response = False
            async with asyncio.timeout(min(120, float(os.getenv('RUN_TIMEOUT_SECONDS', '90')))):
                async with aclosing(model_chunks(model, messages)) as chunks:
                    async for chunk in chunks:
                        if await request.is_disconnected():
                            return
                        if chunk is None:
                            yield ': keep-alive\n\n'
                            continue
                        delta = content_text(chunk)
                        if delta:
                            if not first_response:
                                await run_in_threadpool(save_first_response, id)
                                first_response = True
                            answer += delta
                            yield event('delta', text=delta)
            if not answer.strip():
                raise ValueError('empty_model_answer')
            status = 'completed'
            await run_in_threadpool(save_finish, id, answer, status)
            yield event('done', chat_id=id, status=status, limited=False)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            status, error = 'error', public_error(exc)
            yield event('error', message=error)
        finally:
            # One final write per reply (including partial output), never one write per token.
            if status != 'completed':
                # Finish recording partial output even when the stream is cancelled.
                with CancelScope(shield=True):
                    await run_in_threadpool(save_finish, id, answer, status, error)
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
