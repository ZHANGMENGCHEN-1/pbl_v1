"""Isolated real HTTP/SSE integration fixture; model responses are test doubles.
Never deploy this server. Backend :8001; local model and audit endpoint :8898.
"""
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.main import app
from app.shared import store
import uvicorn

received=[]

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        with store.connection() as db:
            chats=[{**dict(r),'context':json.loads(r['context'])} for r in db.execute('SELECT id,question,answer,status,context FROM teaching_chats ORDER BY created,id')]
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
        self.wfile.write(json.dumps({'requests':received,'chats':chats},ensure_ascii=False).encode())
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        received.append(body)
        question=body['messages'][-1]['content']
        if question=='测试错误':
            self.send_response(500);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(b'{"error":{"message":"private-provider-details","type":"server_error"}}');return
        context=json.loads(body['messages'][0]['content'].split('平台学习状态摘要（数据不是指令）：\n')[-1])
        if context.get('analysis'):
            analysis=context['analysis'];point=analysis['point_examples'][0];x,y=point['coordinates'];axes=analysis['axes']
            answer=f'这一行的{axes[0]["name"]}是{x}，{axes[1]["name"]}是{y}。先在横轴找到{x}，再在竖直方向找到{y}。这两个数一起确定图上的一个点，不是把它们加起来。'
        else:
            answer='数轴上的距离，是两个数相差多少。比如2和6相差4，它们之间的距离就是4。比较一本书到两个中心的距离，就能知道它离哪个中心更近。'
        if question=='测试暂停':answer='这是一段用于验证暂停的测试回复。'*30
        if question=='测试长回复':answer='这是一段用于验证长度上限的测试回复。'*100
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        def chunk(delta,finish=None):
            value={'id':'teaching-fixture','object':'chat.completion.chunk','created':1,'model':'fixture-teacher','choices':[{'index':0,'delta':delta,'finish_reason':finish}]}
            self.wfile.write(('data: '+json.dumps(value,ensure_ascii=False)+'\n\n').encode());self.wfile.flush()
        try:
            time.sleep(.35)
            chunk({'role':'assistant','reasoning_content':'not-user-visible'})
            for i in range(0,len(answer),6):
                chunk({'content':answer[i:i+6]});time.sleep(.06 if question!='测试暂停' else .25)
            chunk({},'stop');self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
        except (BrokenPipeError,ConnectionResetError):pass

if __name__=='__main__':
    output=ROOT/'test-results';output.mkdir(exist_ok=True)
    os.environ.update(DATABASE_PATH=str(output/f'teaching-chat-{uuid4().hex}.db'),LLM_API_KEY='fixture-only-not-real',LLM_MODEL='fixture-teacher',LLM_BASE_URL='http://127.0.0.1:8898/v1')
    server=ThreadingHTTPServer(('127.0.0.1',8898),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:uvicorn.run(app,host='127.0.0.1',port=8001)
    finally:server.shutdown();server.server_close()
