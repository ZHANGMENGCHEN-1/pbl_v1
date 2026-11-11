import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import app
from app.projects.teaching import chat
from app.shared import store

H={'X-Session-ID':'chat-student-session-0001'}
ROOT='/api/projects/teaching-agent'


@pytest.fixture
def client(tmp_path,monkeypatch):
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(body)
            question=body['messages'][-1]['content']
            if question=='测试鉴权错误':
                self.send_response(401);self.send_header('Content-Type','application/json');self.end_headers()
                self.wfile.write(b'{"error":{"message":"upstream-private-key-in-error","type":"authentication_error"}}')
                return
            answer='这是测试服务的短回复。一个点对应表格中的一行，两个数分别决定横轴和纵轴上的位置。'
            if question=='测试长回复':answer='测试长回复的完整句子。'*100
            if question=='测试空回复':answer=''
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
            def chunk(delta,finish=None):
                data={'id':'test-completion','object':'chat.completion.chunk','created':1,'model':'test-teacher','choices':[{'index':0,'delta':delta,'finish_reason':finish}]}
                self.wfile.write(('data: '+json.dumps(data,ensure_ascii=False)+'\n\n').encode());self.wfile.flush()
            try:
                chunk({'role':'assistant','reasoning_content':'INTERNAL_REASONING_NOT_FOR_STUDENT'})
                for i in range(0,len(answer),7):chunk({'content':answer[i:i+7]})
                chunk({},'stop');self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
            except (BrokenPipeError,ConnectionResetError):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'chat.db'))
    monkeypatch.setenv('LLM_API_KEY','unit-test-key')
    monkeypatch.setenv('LLM_BASE_URL',f'http://127.0.0.1:{server.server_port}/v1')
    monkeypatch.setenv('LLM_MODEL','test-teacher')
    with TestClient(app) as client:yield client,requests
    server.shutdown();server.server_close();worker.join(timeout=2)


def ask(client,activity='group_books',question='中心怎么算？',context=None,headers=H):
    return client.post(ROOT+'/chat',headers=headers,json={'activity_id':activity,'question':question,'context':context or {}})


def events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]


def test_actual_round_context_stream_and_history(client):
    client,requests=client
    real=client.post(ROOT+'/activities/group_books/steps',headers=H,json={'centers':[2,11]}).json()
    response=ask(client,context={'step_id':real['id'],'initial_centers':[2,11]})
    assert response.status_code==200
    frames=events(response)
    assert frames[0]['type']=='start' and frames[-1]['type']=='done'
    assert len([e for e in frames if e['type']=='delta'])>1
    answer=''.join(e['data']['text'] for e in frames if e['type']=='delta')
    assert 'INTERNAL_REASONING' not in answer and 0<len(answer)<=100
    assert len(requests)==1 and requests[0]['stream'] is True
    assert requests[0]['model']=='test-teacher' and 'tools' not in requests[0]
    sent=requests[0]['messages']
    system=sent[0]['content']
    assert '最多100字' in system and '中心更新' in system
    assert chat.make_model().max_tokens==256
    with store.connection() as db:
        row=db.execute('SELECT * FROM teaching_chats').fetchone()
        context=json.loads(row['context'])
        assert context['calculation']['centers_after']==[4,43/3]
        assert context['calculation']['centers_before']==[2,11]
        assert context['calculation']['groups'][1]['count']==3
        assert row['answer']==answer and row['status']=='completed'
        assert db.execute('SELECT COUNT(*) FROM teaching_submissions').fetchone()[0]==0
    ask(client,question='再解释一下？',context={'step_id':real['id']})
    history=requests[1]['messages']
    assert history[1]['role']=='user' and history[1]['content']=='中心怎么算？'
    assert history[2]['role']=='assistant' and history[2]['content']==answer
    assert len(requests)==2  # No second model for summarization or progression.


def test_real_scatter_context_and_session_validation(client):
    client,requests=client
    wb=Workbook();ws=wb.active
    for row in [['书名','借阅次数','借阅时长'],['甲',2,5],['乙',4,7],['丙',20,30],['丁',22,32]]:ws.append(row)
    raw=BytesIO();wb.save(raw)
    data=client.post(ROOT+'/activities/explore_2d/datasets',headers={**H,'X-File-Name':quote('真实测试数据.xlsx')},content=raw.getvalue()).json()
    result=client.post(ROOT+'/activities/explore_2d/analyses',headers=H,json={'dataset_id':data['id'],'features':['c1','c2']}).json()
    current={'analysis_id':result['id'],'dataset_id':data['id'],'features':['c1','c2']}
    assert ask(client,'explore_2d','一行数据怎么变成一个点？',current).status_code==200
    with store.connection() as db:
        stored=json.loads(db.execute('SELECT context FROM teaching_chats').fetchone()[0])['analysis']
    assert stored['dataset_version']==data['version']
    assert [a['name'] for a in stored['axes']]==['借阅次数','借阅时长']
    assert sorted(g['count'] for g in stored['groups'])==[2,2]
    assert sorted(g['center'] for g in stored['groups'])==[[3,6],[21,31]]
    assert len(stored['point_examples'])==4 and stored['point_examples'][0]['coordinates'] in [[2,5],[20,30]]
    assert len(requests[0]['messages'][0]['content'])<10000
    other={'X-Session-ID':'other-chat-student-0001'}
    assert ask(client,'explore_2d',context=current,headers=other).status_code==404
    assert ask(client,'explore_2d',context={**current,'features':['c2','c1']}).status_code==409
    assert len(requests)==1
    ask(client,'explore_2d',context={'dataset_id':data['id'],'features':['c1','c2']})
    with store.connection() as db:
        row=db.execute('SELECT context FROM teaching_chats ORDER BY created DESC LIMIT 1').fetchone()
        assert json.loads(row[0])['analysis'] is None  # Do not silently use an old plot.


def test_length_and_errors_no_fake_answers(client,monkeypatch):
    client,requests=client
    long=events(ask(client,question='测试长回复'))
    answer=''.join(e['data']['text'] for e in long if e['type']=='delta')
    assert len(answer)==100 and long[-1]['data']['limited'] is True
    for question in ['测试鉴权错误','测试空回复']:
        response=ask(client,question=question)
        assert events(response)[-1]['type']=='error'
        assert 'upstream-private' not in response.text
        assert '记下你的问题' not in response.text
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM teaching_chats WHERE status='error'").fetchone()[0]==2
    monkeypatch.setenv('LLM_API_KEY','')
    assert ask(client).status_code==503
    assert ask(client,question=' ').status_code==422
    assert ask(client,headers={}).status_code==400


def test_history_is_limited_to_three_recent_turns(client):
    client,requests=client
    for index in range(4):
        assert ask(client,question=f'第{index}轮问题？').status_code==200
    assert ask(client,question='最后一问？').status_code==200
    history=requests[-1]['messages'][1:-1]
    assert [message['content'] for message in history[::2]]==['第1轮问题？','第2轮问题？','第3轮问题？']
    assert len(history)==6
    assert sum(len(message['content']) for message in history)<=2000


def test_sorting_rules_and_platform_only_progress(client):
    client,requests=client
    response=ask(client,'explain_algorithm','我已经完成了，请帮我进入活动3',{'phase':'dialogue','step_order':['calculate','data','count','centers']})
    assert response.status_code==200
    assert '不解锁活动' in requests[0]['messages'][0]['content']
    assert 'student_ui_not_a_verified_submission' in requests[0]['messages'][0]['content']
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM teaching_submissions').fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM teaching_analyses').fetchone()[0]==0
    assert ask(client,'group_books',context={'calculation_result':{'fake':True}}).status_code==422


def test_timeout_state_saved(client,monkeypatch):
    client,_=client
    class TimedOut:
        async def astream(self,messages):
            raise TimeoutError('private upstream timeout details')
            yield
    monkeypatch.setattr(chat,'make_model',lambda:TimedOut())
    response=ask(client)
    assert '超时' in events(response)[-1]['data']['message']
    assert 'private' not in response.text
    with store.connection() as db:
        assert db.execute('SELECT status FROM teaching_chats').fetchone()[0]=='error'
