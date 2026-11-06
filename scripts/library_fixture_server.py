"""Isolated browser-test server. Fake local LLM, real tools/SQLite; no paid API.
Never use this fixture as the production backend. Default ports: 8001 / 8899.
"""
import json
import os
from pathlib import Path
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.main import app
import uvicorn


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        messages = body["messages"]
        if any(m["role"] == "tool" for m in messages):
            values=[json.loads(m["content"]) for m in messages if m["role"]=="tool"]
            full=next((v for v in values if "groups" in v),None)
            if full and full["dataset_id"]=="reading_interest_students":
                groups=[g for g in full["groups"] if g["count"]>0]
                rows=[{"group":g["label"],"type":("偏文艺" if g["center"][0]<50 else "偏知识")+("短时阅读" if g["center"][1]<50 else "长时阅读"),"quantity":int(1000*g["count"]/full["sample_count"])} for g in groups]
                rows[0]["quantity"]+=1000-sum(r["quantity"] for r in rows)
                answer=json.dumps({"answer":"根据实际组中心和人数建议如下采购类型，合计1000册。","purchases":rows,"rationale":"参考100条调查记录的分组人数比例并兼顾不同需求；样本不能代表全校学生。"},ensure_ascii=False)
            else:
                answer="依据工具结果，两组分别为"+str([g["count"] for g in full["groups"]])+"，合计150条。" if full else "已经查看数据，接下来按照学生排列的步骤解释算法。"
            output = {"role": "assistant", "content": answer}
            reason = "stop"
        else:
            system = messages[0]["content"]
            dataset = re.search(r'"dataset_id":\s*"([^"]+)"', system).group(1)
            tools = [t["function"]["name"] for t in body["tools"]]
            calls = [{"id":"view","type":"function","function":{"name":"inspect_dataset","arguments":json.dumps({"dataset_id":dataset})}}]
            if "run_kmeans_analysis" in tools:
                calls.append({"id":"calculate","type":"function","function":{"name":"run_kmeans_analysis","arguments":"{}"}})
            output = {"role":"assistant","content":None,"tool_calls":calls}
            reason = "tool_calls"
        value = {"id":"fixture-completion","object":"chat.completion","created":1,"model":"fixture-model","choices":[{"index":0,"message":output,"finish_reason":reason}],"usage":{"prompt_tokens":10,"completion_tokens":10,"total_tokens":20}}
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            message = value["choices"][0]["message"]
            deltas = []
            if message.get("tool_calls"):
                deltas.append({"tool_calls":[{"index":i,**call} for i,call in enumerate(message["tool_calls"])]})
            else:
                content=message.get("content", "")
                deltas.extend({"content":content[i:i+8]} for i in range(0,len(content),8))
            for delta in deltas:
                chunk={"id":"fixture-stream","object":"chat.completion.chunk","created":1,"model":"test-model","choices":[{"index":0,"delta":delta,"finish_reason":None}]}
                self.wfile.write(("data: "+json.dumps(chunk,ensure_ascii=False)+"\n\n").encode())
                self.wfile.flush()
            chunk["choices"]=[{"index":0,"delta":{},"finish_reason":value["choices"][0]["finish_reason"]}]
            self.wfile.write(("data: "+json.dumps(chunk)+"\n\ndata: [DONE]\n\n").encode())
            self.wfile.flush()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(value, ensure_ascii=False).encode())


if __name__ == "__main__":
    output = ROOT / "test-results"
    output.mkdir(exist_ok=True)
    os.environ.update(LIBRARY_RESET_ON_REFRESH=os.getenv("FIXTURE_RESET_ON_REFRESH","false"), DATABASE_PATH=str(output / f"library-browser-{uuid4().hex}.db"), LLM_API_KEY="fixture-not-a-key", LLM_BASE_URL="http://127.0.0.1:8899/v1", LLM_MODEL="fixture-model", LLM_MODELS="fixture-model")
    server = ThreadingHTTPServer(("127.0.0.1",8899),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        uvicorn.run(app,host="127.0.0.1",port=8001)
    finally:
        server.shutdown()
        server.server_close()
