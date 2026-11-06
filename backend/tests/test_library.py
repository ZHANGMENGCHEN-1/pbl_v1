import json
import numpy as np
import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from app.main import app
from app.shared import runtime
from app.projects.library import clustering, state, engine
from app.projects.library.prompt import ORDER, INITIAL_ORDER, TEMPLATE, render
from app.projects.library.tools import build_tools

B = "/api/projects/library-recommendation"
H = {"X-Session-ID": "library-test-session-1234"}
IDS = ["group_books", "explain_algorithm", "explore_2d", "recommend_purchase"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("LLM_API_KEY", "fixture-only")
    with TestClient(app) as value:
        yield value


def cfg(client, index):
    r = client.get(B + "/config", params={"activity_id": IDS[index]}, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def plan(client, index):
    r=client.post(B+f"/activities/{IDS[index]}/plan",headers=H,json={"text":"我准备根据数据进行实验，并核查每轮中心和分组，解释结果与局限。"})
    assert r.status_code==200,r.text


def save(client, index, value):
    plan(client,index)
    r = client.put(B + "/config", params={"activity_id": IDS[index], "revision": value["revision"]}, headers=H, json=value["config"])
    assert r.status_code == 200, r.text
    return r.json()


def predict(client, index, labels, centers, previous=None):
    plan(client,index)
    value=cfg(client,index)
    inspected=client.post(B+f"/activities/{IDS[index]}/tools/inspect_dataset?revision={value['revision']}",headers=H)
    assert inspected.status_code==200,inspected.text
    r = client.post(B + f"/activities/{IDS[index]}/predictions", headers=H, json={"labels": labels, "centers": centers, "previous_step_id": previous})
    assert r.status_code == 200, r.text
    return r.json()["prediction_id"]


def verify(client, index, prediction, revision=0):
    r = client.post(B + f"/activities/{IDS[index]}/practice-steps/{prediction}", headers=H, params={"revision": revision})
    assert r.status_code == 200, r.text
    return r.json()


def unlock_first(client):
    p = predict(client, 0, [0,0,1,1,1], [[4],[14.33]])
    a = verify(client, 0, p)
    p = predict(client, 0, [0,0,0,1,1], [[5.67],[17]], a["analysis_id"])
    a = verify(client, 0, p)
    p = predict(client, 0, [0,0,0,1,1], [[5.67],[17]], a["analysis_id"])
    a = verify(client, 0, p)
    assert a["converged"] and a["prediction_match"]
    r = client.post(B + "/activities/group_books/submit", headers=H, json={"payload": {"plan": "根据借阅次数分组，计算中心并检查分组是否稳定", "analysis_id": a["analysis_id"], "student_result":{"counts":[g["count"] for g in a["groups"]],"centers":[c[0] for c in a["centers"]]}}})
    assert r.status_code == 200, r.text
    return a


def test_center_selection_rounds(client):
    url=B+"/activities/group_books/center-steps?revision=0"
    assert client.post(url,headers=H,json={"centers":[2,11]}).status_code==403
    plan(client,0)
    assert client.post(url,headers=H,json={"centers":[2,2]}).status_code==422
    assert client.post(url,headers=H,json={"centers":[-1,11]}).status_code==422
    first=client.post(url,headers=H,json={"centers":[2,11]}).json()
    assert first["labels"]==[0,0,1,1,1]
    assert np.allclose(first["centers"],[[4],[43/3]])
    assert first["iterations"][0]["distances"][2]==[7,2]
    assert client.post(url,headers=H,json={"centers":[4,14.3],"previous_step_id":first["analysis_id"]}).status_code==422
    other={"X-Session-ID":"another-center-session-1234"}
    client.post(B+"/activities/group_books/plan",headers=other,json={"text":"选择中心并观察距离分组的变化"})
    assert client.post(url,headers=other,json={"centers":[4,43/3],"previous_step_id":first["analysis_id"]}).status_code in (403,404)
    second=client.post(url,headers=H,json={"centers":[4,43/3],"previous_step_id":first["analysis_id"]}).json()
    assert second["labels"]==[0,0,0,1,1]
    third=client.post(url,headers=H,json={"centers":[c[0] for c in second["centers"]],"previous_step_id":second["analysis_id"]}).json()
    assert third["converged"]
    payload={"plan":"根据借阅次数分组并检查中心变化", "analysis_id":third["analysis_id"],"student_result":{"counts":[3,2],"centers":[5.667,17]}}
    response=client.post(B+"/activities/group_books/submit",headers=H,json={"payload":payload})
    assert response.status_code==200,response.text
    assert response.json()["completed"]==1


class ToolModel(BaseChatModel):
    dataset: str
    purchase: bool = False
    prediction: str = ""
    names: list[str] = []

    @property
    def _llm_type(self):
        return "library-test-fixture"

    def bind_tools(self, tools, **kwargs):
        return self.model_copy(update={"names": [t.name for t in tools]})

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if any(isinstance(m, ToolMessage) for m in messages):
            outputs = [json.loads(m.content) for m in messages if isinstance(m, ToolMessage)]
            assert all(isinstance(v, dict) for v in outputs)
            full=next((v for v in outputs if "groups" in v),None)
            if self.purchase and full:
                groups=[g for g in full["groups"] if g["count"]>0]
                rows=[{"group":g["label"],"type":"偏文艺短时阅读" if g["center"][0]<50 else "偏知识的阅读", "quantity":int(1000*g["count"]/full["sample_count"])} for g in groups]
                rows[0]["quantity"]+=1000-sum(r["quantity"] for r in rows)
                message=AIMessage(content=json.dumps({"answer":"依据调查聚类结果推荐采购类型与数量，合计1000册。", "purchases":rows,"rationale":"按照本次100条样本的组中心和人数分配，样本不能代表全校。"},ensure_ascii=False))
            else:
                message = AIMessage(content="根据工具的真实计算，本次分组与中心已返回。"+str([g["count"] for g in full["groups"]] if full else ""))
        else:
            calls = [{"name": "inspect_dataset", "args": {"dataset_id": self.dataset}, "id": "inspect"}]
            if "run_kmeans_step" in self.names:
                calls.append({"name": "run_kmeans_step", "args": {"prediction_id": self.prediction}, "id": "step"})
            elif "run_kmeans_analysis" in self.names:
                calls.append({"name": "run_kmeans_analysis", "args": {}, "id": "full"})
            message = AIMessage(content="", tool_calls=calls)
        return ChatResult(generations=[ChatGeneration(message=message)])


def agent_run(client, monkeypatch, index, value, prediction=""):
    plan(client,index)
    monkeypatch.setattr(runtime, "ChatOpenAI", lambda **kwargs: ToolModel(dataset=value["config"]["experiment"]["dataset_id"], prediction=prediction, purchase=index==3))
    r = client.post(B + "/runs", headers=H, json={"activity_id": IDS[index], "revision": value["revision"], "input": "请调用工具核对，并解释结果"})
    assert r.status_code == 200, r.text
    events = [json.loads(line[6:]) for line in r.text.splitlines() if line.startswith("data: ")]
    assert events[-1]["data"]["status"] == "completed", events
    assert sum(e["type"] == "tool_result" for e in events) == (1 if index==1 else 2)
    return events[0]["run_id"]


def test_preserves_astronomy_and_server_locks(client):
    projects = client.get("/api/projects").json()
    assert {p["id"] for p in projects} == {"astronomy-lab", "library-recommendation"}
    assert client.get("/api/projects/astronomy-lab").status_code == 200
    c = client.get("/api/projects/astronomy-lab/config", headers=H).json()
    assert "weather" in c and "inspect_dataset" not in c
    learning = client.get(B + "/learning", headers=H).json()
    assert [a["status"] for a in learning["activities"]] == ["available","locked","locked","locked"]
    assert "body" not in learning["activities"][1]
    assert client.get(B + "/config?activity_id=explore_2d", headers=H).status_code == 403
    assert client.post(B + "/activities/explore_2d/analyses?revision=0", headers=H).status_code == 403
    assert client.post(B + "/activities/group_books/analyses?revision=0", headers=H).status_code == 403
    assert client.post(B + "/activities/group_books/practice-steps/guessed-id?revision=0", headers=H).status_code == 403
    assert client.post(B + "/activities", headers=H, json={"action":"learning_step_completed","step":3}).status_code == 404
    first = cfg(client,0)
    assert client.put(B+"/config?activity_id=group_books&revision=0", headers=H, json=first["config"]).status_code == 403


def test_prediction_rounds_and_session_isolation(client):
    p = predict(client,0,[0,0,1,1,1],[[4],[14.33]])
    value = verify(client,0,p)
    assert value["labels"] == [0,0,1,1,1]
    assert value["prediction_match"]
    assert np.allclose(value["centers"],[[4],[43/3]])
    assert verify(client,0,p)["analysis_id"] == value["analysis_id"]
    other = {"X-Session-ID":"another-library-session"}
    assert client.post(B+f"/activities/group_books/practice-steps/{p}?revision=0", headers=other).status_code == 403
    assert client.get(B+"/activities/group_books/analyses",headers=other).json()==[]
    assert client.post(B+"/activities/group_books/submit",headers=H,json={"payload":{"plan":"这是一个完整的计划","analysis_id":value["analysis_id"]}}).status_code == 422


def test_full_learning_journey_and_stale_evidence(client, monkeypatch):
    unlock_first(client)
    value = cfg(client,1)
    assert value["config"]["system_prompt"]==TEMPLATE
    value["config"]["prompt_steps"]=ORDER
    value = save(client,1,value)
    assert value["config"]["system_prompt"]==render(ORDER)
    agent_run(client,monkeypatch,1,value)
    r=client.post(B+"/activities/explain_algorithm/submit",headers=H,json={"payload":{}})
    assert r.status_code==200,r.text
    assert r.json()["activities"][1]["submission"]["payload"]["prompt_steps"]==ORDER
    value=cfg(client,2)
    assert value["config"]["system_prompt"]==render(ORDER)
    assert value["config"]["prompt_steps"]==ORDER
    assert value["config"]["experiment"]["k"]==2
    assert "150" in value["config"]["task_prompt"]
    manual=client.post(B+"/activities/explore_2d/analyses?revision=0",headers=H)
    assert manual.status_code==403
    plan(client,2)
    manual=client.post(B+"/activities/explore_2d/analyses?revision=0",headers=H).json()
    assert client.post(B+"/activities/explore_2d/submit",headers=H,json={"payload":{"analysis_id":manual["analysis_id"]}}).status_code==422
    run_id=agent_run(client,monkeypatch,2,value)
    r=client.post(B+"/activities/explore_2d/submit",headers=H,json={"payload":{"run_id":run_id,"group_counts":[{"group":0,"count":75},{"group":1,"count":75}]}})
    assert r.status_code==200,r.text
    delivery=r.json()["activities"][2]["submission"]["payload"]
    assert sum(g["count"] for g in delivery["group_counts"])==150 and len(delivery["group_counts"])==2
    value=cfg(client,3)
    earlier=cfg(client,1)
    earlier["config"]["system_prompt"]="修改早期活动，不应悄悄覆盖已打开的后续活动配置"
    save(client,1,earlier)
    assert cfg(client,3)==value
    run_id=agent_run(client,monkeypatch,3,value)
    analyses=client.get(B+"/activities/recommend_purchase/analyses",headers=H).json()
    result=analyses[0]["result"]
    assert not result["demo"] and result["sample_count"]==100
    assert value["config"]["experiment"]["k"]==2
    groups=[g for g in result["groups"] if g["count"]>0]
    purchases=[{"group":g["label"],"type":f"需求类型{g['label']+1}","quantity":1000//len(groups)} for g in groups]
    purchases[0]["quantity"]+=1000-sum(p["quantity"] for p in purchases)
    body={"run_id":run_id,"purchases":purchases,"rationale":"按演示问卷组中心解释需求，参考样本人数分配但不能代表全校","reflection":"我检查了中心与人数，保留当前方案，下次需要核查真实调查的代表性"}
    bad={**body,"purchases":[{**p,"quantity":0} for p in purchases]}
    assert client.post(B+"/activities/recommend_purchase/submit",headers=H,json={"payload":bad}).status_code==422
    accepted=client.post(B+"/activities/recommend_purchase/submit",headers=H,json={"payload":body})
    assert accepted.status_code==200,accepted.text
    assert accepted.json()["completed"]==4
    assert accepted.json()["activities"][3]["submission"]["payload"]["agent_answer"]
    assert accepted.json()["activities"][3]["submission"]["payload"]["agent_decision"]["purchases"]
    value=save(client,3,value)
    assert client.post(B+"/activities/recommend_purchase/submit",headers=H,json={"payload":body}).status_code==409
    assert client.post(B+"/runs",headers=H,json={"activity_id":IDS[3],"revision":0,"input":"绕过旧配置"}).status_code==409
    assert client.get(B+"/learning",headers=H).json()["completed"]==4


def test_drafts_persist_and_reading_dataset_is_not_tool_enablement(client):
    text={"plan":"我计划依据借阅次数分组，并检查每轮中心"}
    assert client.put(B+"/activities/group_books/draft",headers=H,json={"payload":text}).status_code==200
    assert client.get(B+"/learning",headers=H).json()["activities"][0]["draft"]==text
    dataset=client.get(B+"/activities/group_books/dataset",headers=H).json()
    assert dataset["row_count"]==5 and dataset["issues"]==[]
    assert dataset["preview"]==[] and dataset["loaded"] is False
    assert client.get(B+"/learning").status_code==400


def test_plan_is_persisted_without_unlocking_next_activity(client):
    assert client.post(B+"/activities/group_books/predictions",headers=H,json={"labels":[0,0,1,1,1],"centers":[[4],[14.33]]}).status_code==403
    plan="我计划按借阅次数分组，通过计算均值核查中心是否稳定。"
    r=client.post(B+"/activities/group_books/plan",headers=H,json={"text":plan})
    assert r.status_code==200,r.text
    assert r.json()["completed"]==0
    assert r.json()["activities"][1]["status"]=="locked"
    assert r.json()["activities"][0]["plan"]["text"]==plan
    reloaded=client.get(B+"/learning",headers=H).json()
    assert reloaded["activities"][0]["plan"]["submitted_at"]
    assert client.post(B+"/activities/explain_algorithm/plan",headers=H,json={"text":plan}).status_code==403
    assert client.post(B+"/activities/group_books/plan",headers=H,json={"text":"      "}).status_code==422
    other={"X-Session-ID":"other-planning-session-12"}
    assert client.get(B+"/learning",headers=other).json()["activities"][0]["plan"] is None


def test_data_rows_require_actual_enabled_tool_invocation(client):
    plan(client,0)
    before=client.get(B+"/activities/group_books/dataset",headers=H).json()
    assert before["preview"]==[] and not before["loaded"]
    prediction={"labels":[0,0,1,1,1],"centers":[[4],[14.33]]}
    assert client.post(B+"/activities/group_books/predictions",headers=H,json=prediction).status_code==403
    called=client.post(B+"/activities/group_books/tools/inspect_dataset?revision=0",headers=H)
    assert called.status_code==200,called.text
    assert called.json()["loaded"] and len(called.json()["preview"])==5
    assert client.get(B+"/activities/group_books/dataset",headers=H).json()["preview"]==called.json()["preview"]
    partial=engine.inspect(H["X-Session-ID"],IDS[0],0,"library_sample_1d",1)
    assert len(partial["preview"])==1
    assert len(client.get(B+"/activities/group_books/dataset",headers=H).json()["preview"])==5
    assert client.post(B+"/activities/group_books/predictions",headers=H,json=prediction).status_code==200
    other={"X-Session-ID":"other-dataset-reader-1234"}
    assert client.get(B+"/activities/group_books/dataset",headers=other).json()["preview"]==[]
    unlock_first(client)
    value=cfg(client,1)
    value["config"]["inspect_dataset"]["enabled"]=False
    value=save(client,1,value)
    r=client.post(B+f"/activities/explain_algorithm/tools/inspect_dataset?revision={value['revision']}",headers=H)
    assert r.status_code==403
    assert client.get(B+"/activities/explain_algorithm/dataset",headers=H).json()["preview"]==[]


def test_shared_cluster_engine_and_invalid_parameters():
    experiment={"dataset_id":"library_sample_1d","features":["borrow_count"],"k":2,"scaling":"none","seed":42}
    full=clustering.analyze(experiment,[[2],[11]])
    assert full["converged"] and full["labels"]==[0,0,0,1,1]
    centers=[[2],[11]]
    for frame in full["iterations"]:
        one=clustering.analyze(experiment,centers,True)
        assert one["iterations"][0]==frame
        centers=one["centers"]
    assert full["excluded"]==[]
    with pytest.raises(Exception):
        clustering.analyze({**experiment,"features":["../../secret"]})


def test_standardized_centers_return_original_units():
    ex={"dataset_id":"library_sample_2d","features":["borrow_count","borrow_days"],"k":2,"scaling":"standard","seed":42}
    result=clustering.analyze(ex)
    for group in result["groups"]:
        raw=np.array([[r[f] for f in ex["features"]] for i,r in enumerate(result["records"]) if result["labels"][i]==group["label"]])
        if len(raw):
            assert np.allclose(raw.mean(axis=0),group["center"])


def test_prompt_sorting_submission_and_saved_config(client):
    unlock_first(client)
    value=cfg(client,1)
    assert value["config"]["system_prompt"]==TEMPLATE
    assert value["config"]["prompt_steps"]==[]
    assert "run_kmeans_step" not in client.get(B).json()["tools"]
    plan(client,1)
    assert [t.name for t in build_tools(H["X-Session-ID"],IDS[1],0,value["config"],None)]==["inspect_dataset"]
    assert client.post(B+"/activities/explain_algorithm/submit",headers=H,json={"payload":{}}).status_code==422
    value["config"]["prompt_steps"]=INITIAL_ORDER
    value=save(client,1,value)
    assert client.post(B+"/activities/explain_algorithm/submit",headers=H,json={"payload":{}}).status_code==422
    value["config"]["prompt_steps"]=ORDER
    value["config"]["system_prompt"]="客户端故意不更新，服务端仍应按真实排序生成"
    value=save(client,1,value)
    assert value["config"]["system_prompt"]==render(ORDER)
    assert cfg(client,1)==value
    response=client.post(B+"/activities/explain_algorithm/submit",headers=H,json={"payload":{}})
    assert response.status_code==200,response.text
    assert response.json()["completed"]==2
    saved=response.json()["activities"][1]["submission"]["payload"]
    assert saved["system_prompt"]==render(ORDER)
    assert saved["prompt_steps"]==ORDER
    # A different session cannot submit this unlocked activity or reuse its plan.
    assert client.post(B+"/activities/explain_algorithm/submit",headers={"X-Session-ID":"another-prompt-session-12"},json={"payload":{}}).status_code==403
    value["config"]["prompt_steps"]=["data"]*7
    assert client.put(B+f"/config?activity_id=explain_algorithm&revision={value['revision']}",headers=H,json=value["config"]).status_code==422
