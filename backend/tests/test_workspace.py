import json
import asyncio
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.projects.astronomy import runtime
from app.projects.astronomy.project import default_config
from app.projects.astronomy.schemas import AgentConfig
from app.projects.astronomy.tools import build_tools

BASE = "/api/projects/astronomy-lab"
HEADERS = {"X-Session-ID": "test-session-12345678"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with TestClient(app) as c:
        yield c


def frames(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def test_config_persists_and_logs_changes(client):
    config = client.get(BASE + "/config", headers=HEADERS).json()
    config["system_prompt"] = "你是一个测试助手"
    config["weather"]["enabled"] = False
    config["temperature"] = 0.8
    assert client.put(BASE + "/config", headers=HEADERS, json=config).status_code == 200
    assert client.get(BASE + "/config", headers=HEADERS).json() == config
    logs = client.get(BASE + "/activities", headers=HEADERS).json()
    assert {l["data"]["field"] for l in logs} == {"system_prompt", "weather", "temperature"}
    assert all(l["timestamp"] for l in logs)
    other = {"X-Session-ID": "other-session-123456"}
    assert client.get(BASE + "/config", headers=other).json() != config


def test_validation_and_scope(client):
    assert client.get(BASE + "/config").status_code == 400
    assert client.get("/api/projects/missing").status_code == 404
    config = default_config()
    config["temperature"] = 3
    assert client.put(BASE + "/config", headers=HEADERS, json=config).status_code == 422
    config["temperature"] = 0.5
    config["model"] = "unapproved-model"
    assert client.put(BASE + "/config", headers=HEADERS, json=config).status_code == 422


def test_provider_model_change_updates_saved_session(client, monkeypatch):
    config = default_config()
    config["system_prompt"] = "保留学生修改过的提示词"
    config["weather"]["enabled"] = False
    assert client.put(BASE + "/config", headers=HEADERS, json=config).status_code == 200
    monkeypatch.setenv("LLM_MODEL", "new-provider-model")
    monkeypatch.setenv("LLM_MODELS", "new-provider-model")
    updated = client.get(BASE + "/config", headers=HEADERS).json()
    assert updated == {**config, "model": "new-provider-model"}
    assert client.get(BASE, headers=HEADERS).json()["models"] == ["new-provider-model"]
    assert client.get(BASE + "/config", headers=HEADERS).json() == updated
    logs = client.get(BASE + "/activities", headers=HEADERS).json()
    assert any(log["data"].get("field") == "model" and log["data"]["after"] == "new-provider-model" for log in logs)


def test_missing_key_is_streamed_and_persisted(client):
    response = client.post(BASE + "/runs", headers=HEADERS, json={"input": "测试", "config": default_config()})
    assert response.headers["content-type"].startswith("text/event-stream")
    events = frames(response)
    assert [e["type"] for e in events] == ["run_start", "error", "done"]
    assert "LLM_API_KEY" in events[1]["data"]["message"]
    history = client.get(BASE + "/runs", headers=HEADERS).json()
    assert history[0]["status"] == "error"
    detail = client.get(BASE + "/runs/" + history[0]["id"], headers=HEADERS).json()
    assert detail["config"] == default_config()
    assert len(detail["events"]) == 3
    assert client.get(BASE + "/runs/" + history[0]["id"], headers={"X-Session-ID": "other-session-123456"}).status_code == 404


def test_sse_success_order_and_history(client, monkeypatch):
    async def fake_execute(config, user_input):
        yield "llm_start", {"node": "brain"}
        yield "tool_call", {"node": "weather", "input": {"location": "北京", "date": "2026-11-05"}}
        yield "tool_result", {"node": "weather", "output": {"source": "MOCK"}}
        yield "final", {"answer": "这是模拟观测建议"}
    monkeypatch.setattr(runtime, "execute", fake_execute)
    result = frames(client.post(BASE + "/runs", headers=HEADERS, json={"input": "测试观测", "config": default_config()}))
    assert [e["type"] for e in result] == ["run_start", "llm_start", "tool_call", "tool_result", "final", "done"]
    assert result[-1]["data"]["status"] == "completed"
    assert len({e["run_id"] for e in result}) == 1
    assert client.get(BASE + "/runs", headers=HEADERS).json()[0]["status"] == "completed"


def test_tools_honor_config_and_validate_dates(external_api, forecast_date):
    config = AgentConfig(**default_config())
    tools = {t.name: t for t in build_tools(config)}
    args = {"location": "北京", "date": forecast_date}
    c = asyncio.run(tools["weather"].ainvoke(args))
    assert c["source"] == "Open-Meteo"
    config.weather.units = "fahrenheit"
    f = asyncio.run(build_tools(config)[0].ainvoke(args))
    assert f["hourly"][0]["temperature_2m"] == c["hourly"][0]["temperature_2m"] * 9 / 5 + 32
    assert "YYYY-MM-DD" in asyncio.run(tools["weather"].ainvoke({"location": "北京", "date": "tomorrow"}))
    config.weather.enabled = False
    config.astronomy.enabled = False
    assert build_tools(config) == []


def test_learning_activity_persists(client):
    assert client.post(BASE + "/activities", headers=HEADERS, json={"action": "learning_step_completed", "step": 2}).status_code == 200
    assert client.get(BASE + "/activities", headers=HEADERS).json()[0]["data"]["step"] == 2


def test_errors_do_not_expose_credentials():
    assert "secret" not in runtime.public_error(RuntimeError("API key secret"))
