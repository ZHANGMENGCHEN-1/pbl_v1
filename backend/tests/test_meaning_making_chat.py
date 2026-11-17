import asyncio
import json
import threading

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk

from app.main import app
from app.projects.teaching import chat, meaning_making
from app.shared import store

ROOT='/api/projects/teaching-agent'
H={'X-Session-ID':'meaning-chat-session-0001'}


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'meaning.db'))
    with TestClient(app) as client:
        yield client


def measurement(client,source='meaning-making',ratings=None,headers=H):
    assert client.post(ROOT+'/student',headers=headers,json={'class_name':'测试班','student_number':'001','source_route':source}).status_code==200
    submission=client.post(ROOT+'/activities/explain_algorithm/submissions',headers=headers,json={'order':['data','count','centers','calculate']}).json()
    response=client.post(ROOT+'/state-measurements',headers=headers,json={'submission_id':submission['id'],'request_id':submission['id'],'ratings':ratings or {'difficulty':4,'boredom':2,'frustration':1,'self_efficacy':5}})
    assert response.status_code==200
    return response.json()


def ask(client,id,headers=H,activity='explain_algorithm',purpose='reflection_opening'):
    return client.post(ROOT+'/chat',headers=headers,json={'activity_id':activity,'question':'我已填写刚才的学习感受。','purpose':purpose,'context':{'phase':'dialogue','measurement_id':id}})


def frames(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]


@pytest.mark.parametrize('ratings,expected',[
    ({'difficulty':4,'boredom':1,'frustration':1,'self_efficacy':5},'Content'),
    ({'difficulty':1,'boredom':5,'frustration':1,'self_efficacy':5},'Task'),
    ({'difficulty':1,'boredom':1,'frustration':4,'self_efficacy':5},'Experience'),
    ({'difficulty':1,'boredom':1,'frustration':1,'self_efficacy':2},'Self'),
    ({'difficulty':3,'boredom':3,'frustration':3,'self_efficacy':3},'Positive'),
    ({'difficulty':5,'boredom':5,'frustration':5,'self_efficacy':1},'Experience'),
    ({'difficulty':5,'boredom':5,'frustration':4,'self_efficacy':1},'Experience'),
    ({'difficulty':5,'boredom':5,'frustration':1,'self_efficacy':5},'Task'),
    ({'difficulty':4,'boredom':5,'frustration':4,'self_efficacy':2},'Experience'),
    ({'difficulty':5,'boredom':4,'frustration':1,'self_efficacy':1},'Task'),
    ({'difficulty':5,'boredom':3,'frustration':3,'self_efficacy':2},'Self'),
    ({'difficulty':4,'boredom':4,'frustration':4,'self_efficacy':2},'Experience'),
])
def test_strategy_selection(ratings,expected):
    assert meaning_making.select_strategy(ratings)==expected


def test_prompt_uses_owned_ratings_and_saved_evidence(client,monkeypatch):
    saved=measurement(client)
    calls=[]
    class Model:
        async def astream(self,messages):
            calls.append(messages)
            yield AIMessageChunk(content='可以先说说你已经理解的部分。')
            yield AIMessageChunk(content='刚才哪个环节最难理解？')
    monkeypatch.setattr(chat,'make_model',lambda:Model())
    response=ask(client,saved['id'])
    events=frames(response)
    assert events[-1]['type']=='done'
    assert len(calls)==1 and 'Content：' in calls[0][0].content and '最多100字' in calls[0][0].content
    with store.connection() as db:
        row=db.execute('SELECT * FROM teaching_chats').fetchone()
        context=json.loads(row['context'])
        assert context['meaning_making']['strategy']=='Content'
        assert context['meaning_making']['measurement_id']==saved['id']
        assert context['meaning_making']['generation_attempts']==1
        assert context['question_source']=='platform'
        assert context['measured_submission']['correct'] is True
        assert context['measured_submission']['student_result']['order']==['data','count','centers','calculate']
        assert row['prompt_version']==meaning_making.PROMPT_VERSION and len(row['answer'])<=100
        assert db.execute("SELECT COUNT(*) FROM teaching_events WHERE type='reflection_opening_requested'").fetchone()[0]==1
    ask(client,saved['id'],purpose='question')
    with store.connection() as db:
        contexts=[json.loads(row[0]) for row in db.execute('SELECT context FROM teaching_chats')]
        assert all(row['meaning_making']['strategy']=='Content' for row in contexts)
        assert any(row['question_source']=='student' for row in contexts)


def test_tied_ratings_send_explicit_experience_guidance(client,monkeypatch):
    saved=measurement(client,ratings={'difficulty':4,'boredom':4,'frustration':4,'self_efficacy':2})
    calls=[]
    class Model:
        async def astream(self,messages):
            calls.append(messages)
            yield AIMessageChunk(content='遇到困难时感到沮丧，是可以理解的。刚才哪个时刻让你有这种感受？')
    monkeypatch.setattr(chat,'make_model',lambda:Model())
    assert frames(ask(client,saved['id']))[-1]['type']=='done'
    prompt=calls[0][0].content
    assert '本轮执行策略：Experience' in prompt
    assert meaning_making.STRATEGY_GUIDANCE['Experience'] in prompt
    assert meaning_making.STRATEGY_GUIDANCE['Content'] not in prompt
    assert prompt.index('本轮执行策略：Experience') > prompt.index('当前活动要求')
    assert '{{activity_rules}}' not in prompt and '{{context}}' not in prompt
    assert '信息科学课的学习伙伴' in prompt
    assert '不用“我很在意”' in prompt
    assert '示例中的活动和感受不能当作当前学生的事实' in prompt
    with store.connection() as db:
        row=db.execute('SELECT context,prompt_version FROM teaching_chats').fetchone()
        assert json.loads(row['context'])['meaning_making']['strategy']=='Experience'
        assert row['prompt_version']==meaning_making.PROMPT_VERSION


def test_dialogue_cycles_two_inquiries_then_guidance(client,monkeypatch):
    saved=measurement(client)
    calls=[]
    class Model:
        async def astream(self,messages):
            calls.append(messages)
            yield AIMessageChunk(content='测试回复。')
    monkeypatch.setattr(chat,'make_model',lambda:Model())
    # Exceeds the 12-row history window: cadence must use all completed turns.
    for turn in range(1,16):
        assert frames(ask(client,saved['id'],purpose='reflection_opening' if turn==1 else 'question'))[-1]['type']=='done'
        expected='guidance' if turn%3==0 else 'inquiry'
        assert meaning_making.RESPONSE_MODES[expected] in calls[-1][0].content
    with store.connection() as db:
        contexts=[json.loads(row[0])['meaning_making'] for row in db.execute('SELECT context FROM teaching_chats ORDER BY created,id')]
        assert sorted(c['dialogue_turn'] for c in contexts)==list(range(1,16))
        assert sum(c['response_mode']=='guidance' for c in contexts)==5
        db.execute("UPDATE teaching_chats SET status='error'")
    # Failed/paused replies must not consume a turn.
    body=chat.ChatInput(activity_id='explain_algorithm',question='继续',context={'phase':'dialogue','measurement_id':saved['id']})
    context,_=chat.learning_context(H['X-Session-ID'],body)
    assert context['meaning_making']['dialogue_turn']==1
    with store.connection() as db:
        db.execute("UPDATE teaching_chats SET status='completed'")
    body.context.screen='introduction'
    context,_=chat.learning_context(H['X-Session-ID'],body)
    assert context['meaning_making']['dialogue_turn']==1
    other=measurement(client)
    ask(client,other['id'])
    assert meaning_making.RESPONSE_MODES['inquiry'] in calls[-1][0].content


def test_measurement_cannot_be_cross_used_or_applied_to_b(client,monkeypatch):
    saved=measurement(client)
    other={'X-Session-ID':'meaning-chat-session-0002'}
    ordinary=measurement(client,source='teaching-agent',headers=other)
    assert ask(client,saved['id'],headers=other).status_code==404
    assert ask(client,saved['id'],activity='group_books').status_code==404
    assert ask(client,ordinary['id'],headers=other).status_code==403
    assert ask(client,None).status_code==422
    class Model:
        async def astream(self,messages):
            assert '根据strategy' not in messages[0].content
            yield AIMessageChunk(content='普通回复。'*40)
    monkeypatch.setattr(chat,'make_model',lambda:Model())
    response=client.post(ROOT+'/chat',headers=other,json={'activity_id':'explain_algorithm','question':'解释一下？'})
    assert frames(response)[-1]['type']=='done'
    assert len(''.join(e['data']['text'] for e in frames(response) if e['type']=='delta'))>100


@pytest.mark.parametrize('fail',[False,True])
def test_finish_write_runs_outside_stream_event_loop(client,monkeypatch,fail):
    saved=measurement(client)
    loop_threads=[]
    write_threads=[]
    original=chat.save_finish
    class Model:
        async def astream(self,messages):
            loop_threads.append(threading.get_ident())
            yield AIMessageChunk(content='已生成的正文。')
            if fail:
                raise RuntimeError('test failure')
    def finish(*args,**kwargs):
        write_threads.append(threading.get_ident())
        return original(*args,**kwargs)
    monkeypatch.setattr(chat,'make_model',lambda:Model())
    monkeypatch.setattr(chat,'save_finish',finish)
    result=frames(ask(client,saved['id']))
    assert result[-1]['type']==('error' if fail else 'done')
    assert len(write_threads)==1 and write_threads[0]!=loop_threads[0]
    with store.connection() as db:
        row=db.execute('SELECT answer,status FROM teaching_chats').fetchone()
        assert row['answer']=='已生成的正文。'
        assert row['status']==('error' if fail else 'completed')


def test_c_reply_streams_before_model_finishes(client,monkeypatch):
    saved=measurement(client)
    produced=[]
    class Model:
        async def astream(self,messages):
            produced.append('first')
            yield AIMessageChunk(content='先看看已完成的小步骤。')
            produced.append('second')
            yield AIMessageChunk(content='刚才哪里最难理解？')
    class Request:
        async def is_disconnected(self):return False
    monkeypatch.setattr(chat,'make_model',lambda:Model())
    async def run():
        body=chat.ChatInput(activity_id='explain_algorithm',question='回顾刚才的感受',context={'phase':'dialogue','measurement_id':saved['id']})
        response=await chat.chat(body,Request(),H['X-Session-ID'])
        async with chat.aclosing(response.body_iterator) as stream:
            assert '"start"' in await anext(stream)
            first=await anext(stream)
            assert '先看看已完成的小步骤。' in first and produced==['first']
            second=await anext(stream)
            assert '刚才哪里最难理解？' in second and produced==['first','second']
            assert '"done"' in await anext(stream)
    asyncio.run(run())


def test_overlong_c_reply_is_not_buffered_cut_or_regenerated(client,monkeypatch):
    saved=measurement(client)
    calls=[]
    text='测试完整回复的句子。'*30
    class Model:
        async def astream(self,messages):
            calls.append(messages)
            for start in range(0,len(text),7):
                yield AIMessageChunk(content=text[start:start+7])
    monkeypatch.setattr(chat,'make_model',lambda:Model())
    events=frames(ask(client,saved['id']))
    deltas=[frame['data']['text'] for frame in events if frame['type']=='delta']
    assert len(calls)==1 and len(deltas)>1
    assert ''.join(deltas)==text and events[-1]['type']=='done'
    with store.connection() as db:
        row=db.execute('SELECT * FROM teaching_chats').fetchone()
        assert row['answer']==text
        assert json.loads(row['context'])['meaning_making']['delivery']=='streaming'


@pytest.mark.parametrize('base,model,expected',[
    ('https://open.bigmodel.cn/api/paas/v4','glm-5.3-flash',{'thinking':{'type':'enabled'},'reasoning_effort':'low'}),
    ('https://api.z.ai/api/paas/v4','GLM-5.3',{'thinking':{'type':'enabled'},'reasoning_effort':'low'}),
    ('https://open.bigmodel.cn/api/paas/v4','glm-5.2',{'thinking':{'type':'disabled'}}),
    ('https://api.openai.com/v1','gpt-4o-mini',None),
    ('http://127.0.0.1:8898/v1','fixture-teacher',None),
])
def test_provider_thinking_options(monkeypatch,base,model,expected):
    monkeypatch.setenv('LLM_API_KEY','unit-test-key')
    monkeypatch.setenv('LLM_BASE_URL',base)
    monkeypatch.setenv('LLM_MODEL',model)
    assert chat.make_model().extra_body==expected


def test_reflection_history_is_scoped_to_the_current_measurement(client,monkeypatch):
    calls=[]
    class Model:
        async def astream(self,messages):
            calls.append(messages)
            yield AIMessageChunk(content='我们来回顾四张步骤卡片。哪一步还不清楚？')
    monkeypatch.setattr(chat,'make_model',lambda:Model())
    first=measurement(client)
    ask(client,first['id'])
    second=measurement(client)
    assert ask(client,second['id']).status_code==200
    assert len(calls[1])==2  # No earlier submission's reflection is replayed.
    assert '活动2：围绕步骤顺序' in calls[1][0].content
    with store.connection() as db:
        context=json.loads(db.execute('SELECT context FROM teaching_chats WHERE context LIKE ?',('%'+second['id']+'%',)).fetchone()[0])
        assert context['current_task']['number']==2 and context['current_task']['screen']=='reflection'
