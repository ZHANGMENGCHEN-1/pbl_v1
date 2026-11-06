"""Protocol-level integration: real LangChain agent + ChatOpenAI, local HTTP fixture.

This fixture is deliberately NOT a real LLM. It validates the complete tool-call
round trip without a key; provider verification is a separate opt-in smoke test.
"""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from app.main import app  # Load dotenv before tests override provider settings.
from app.projects.astronomy.runtime import execute
from app.projects.astronomy.schemas import AgentConfig
from app.projects.astronomy.project import default_config


def test_real_langchain_tool_roundtrip(monkeypatch, tmp_path, external_api, forecast_date):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            tool_messages = [m for m in body["messages"] if m["role"] == "tool"]
            if not tool_messages:
                message = {"role": "assistant", "content": None, "tool_calls": [{"id": "call_weather", "type": "function", "function": {"name": "weather", "arguments": json.dumps({"location": "北京", "date": forecast_date})}}, {"id": "call_astronomy", "type": "function", "function": {"name": "astronomy", "arguments": json.dumps({"location": "北京", "time": forecast_date + "T20:00:00+08:00"})}}]}
                reason = "tool_calls"
            else:
                assert len(tool_messages) == 2
                assert {json.loads(m["content"])["source"] for m in tool_messages} == {"Open-Meteo", "NASA/JPL Horizons"}
                message = {"role": "assistant", "content": "根据工具返回的数据，可以练习制定观测计划。"}
                reason = "stop"
            result = {"id": "chatcmpl-test", "object": "chat.completion", "created": 1, "model": "test-model", "choices": [{"index": 0, "message": message, "finish_reason": reason}], "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}}
            if body.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                message = result["choices"][0]["message"]
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
                chunk["choices"]=[{"index":0,"delta":{},"finish_reason":result["choices"][0]["finish_reason"]}]
                self.wfile.write(("data: "+json.dumps(chunk)+"\n\ndata: [DONE]\n\n").encode())
                self.wfile.flush()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("LLM_API_KEY", "test-not-real")
    monkeypatch.setenv("LLM_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    try:
        from fastapi.testclient import TestClient
        monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "roundtrip.db"))
        headers = {"X-Session-ID": "roundtrip-session-1234"}
        base = "/api/projects/astronomy-lab"
        with TestClient(app) as client:
            response = client.post(base + "/runs", headers=headers, json={"input": "北京明晚观星", "config": default_config()})
            assert response.status_code == 200
            events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
            history = client.get(base + "/runs", headers=headers).json()
            assert history[0]["status"] == "completed"
            detail = client.get(base + "/runs/" + history[0]["id"], headers=headers).json()
            assert len(detail["events"]) == len(events)
        kinds = [e["type"] for e in events]
        assert kinds.count("tool_call") == 2
        assert kinds.count("tool_result") == 2
        assert kinds[-2:] == ["final", "done"]
        assert events[-2]["data"]["answer"].startswith("根据工具返回")
        assert len(requests) == 2
        assert all(request["stream"] for request in requests)
        assert "llm_delta" in kinds
        assert kinds.index("llm_delta") < kinds.index("final")
        assert {t["function"]["name"] for t in requests[0]["tools"]} == {"weather", "astronomy"}
    finally:
        server.shutdown()
        server.server_close()


def test_agent_can_answer_without_tools(monkeypatch):
    from langchain_core.messages import AIMessage
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.outputs import ChatResult, ChatGeneration
    from app.shared import runtime

    class Model(BaseChatModel):
        @property
        def _llm_type(self):
            return "test"

        def bind_tools(self, tools, **kwargs):
            return self

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Agent 可以自主使用工具。"))])

    monkeypatch.setenv("LLM_API_KEY", "test-not-real")
    options={}
    def create_model(**kwargs):
        options.update(kwargs)
        return Model()
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS","1200")
    monkeypatch.setenv("LLM_MAX_RETRIES","0")
    monkeypatch.setattr(runtime, "ChatOpenAI", create_model)
    async def collect():
        return [item async for item in execute(AgentConfig(**default_config()), "什么是 Agent？")]
    events = asyncio.run(collect())
    assert not any(kind == "tool_call" for kind, _ in events)
    assert events[-1][0] == "final"
    assert options['max_tokens']==1200 and options['max_retries']==0
    assert options['streaming'] is True and options['disable_streaming'] is False


def test_provider_timeout_is_reported_clearly():
    from app.shared.runtime import public_error
    class OpenAITimeoutError(Exception):pass
    assert '模型响应超时' in public_error(OpenAITimeoutError())
