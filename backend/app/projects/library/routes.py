import asyncio
import json
import re
from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from ...shared import store, runtime
from ...shared.settings import models
from . import state, engine
from .project import PROJECT_ID, project, ACTIVITY_IDS, ACTIVITIES
from .schemas import Config, RunInput, Prediction, Payload, PlanInput, CenterStep
from .tools import build_tools
from .datasets import preview, load, available, require_dataset
from .prompt import render
from .decisions import FORMAT, parse

router = APIRouter(prefix="/api/projects/" + PROJECT_ID, tags=["library"])


def session_id(value):
    if not re.fullmatch(r"[a-zA-Z0-9-]{16,80}", value):
        raise HTTPException(400, "需要有效 X-Session-ID")
    return value


@router.get("")
def metadata():
    # Locked teaching content is fetched only through the guarded learning API.
    p = project()
    p["activities"] = [{"id": a["id"], "title": a["title"]} for a in p["activities"]]
    return p


@router.get("/learning")
def learning(x_session_id: str = Header(default="")):
    return state.get_state(session_id(x_session_id))


@router.get("/config")
def get_config(activity_id: str = Query(...), x_session_id: str = Header(default="")):
    session = session_id(x_session_id)
    with store.connection() as db:
        state.require(db, session, activity_id)
        return state.config(db, session, activity_id)


@router.put("/config")
def save_config(body: Config, activity_id: str = Query(...), revision: int = Query(..., ge=0), x_session_id: str = Header(default="")):
    session = session_id(x_session_id)
    value = body.model_dump()
    if value["model"] not in models():
        raise HTTPException(422, "模型不在服务端允许列表中")
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        state.require(db, session, activity_id)
        state.require_plan(db, session, activity_id)
        old = state.check_revision(db, session, activity_id, revision)
        state.check_config(activity_id, value)
        if activity_id == "explain_algorithm" and value["prompt_steps"]:
            value["system_prompt"] = render(value["prompt_steps"])
        if activity_id == ACTIVITY_IDS[0]:
            raise HTTPException(403, "先完成手工分组，活动二才开放智能体配置")
        db.execute("INSERT INTO library_configs VALUES(?,?,?,?) ON CONFLICT(session,activity) DO UPDATE SET revision=excluded.revision,config=excluded.config", (session, activity_id, revision + 1, json.dumps(value, ensure_ascii=False)))
    store.action(PROJECT_ID, session, "config_changed", {"activity_id": activity_id, "before": old, "after": value, "revision": revision + 1})
    return {"revision": revision + 1, "config": value}


@router.put("/activities/{activity}/draft")
def save_draft(activity: str, body: Payload, x_session_id: str = Header(default="")):
    session = session_id(x_session_id)
    encoded = json.dumps(body.payload, ensure_ascii=False)
    if len(encoded) > 40000:
        raise HTTPException(422, "草稿内容过长")
    with store.connection() as db:
        state.require(db, session, activity)
        db.execute("INSERT INTO library_drafts VALUES(?,?,?) ON CONFLICT(session,activity) DO UPDATE SET payload=excluded.payload", (session, activity, encoded))
    return {"saved": True}


@router.post("/activities/{activity}/plan")
def submit_plan(activity: str, body: PlanInput, x_session_id: str = Header(default="")):
    session = session_id(x_session_id)
    text = body.text.strip()
    if len(text) < 6:
        raise HTTPException(422, "请说明准备分析什么数据，以及怎样检查结果")
    with store.connection() as db:
        state.require(db, session, activity)
        base=state.inherited_plan(db,session,activity)
        combined=(base["text"]+"\n\n【本活动补充】\n" if base else "")+text
        db.execute("INSERT INTO library_plans VALUES(?,?,?,?) ON CONFLICT(session,activity) DO UPDATE SET text=excluded.text,submitted_at=excluded.submitted_at", (session, activity, combined, store.now()))
        db.execute("INSERT INTO library_plan_details VALUES(?,?,?) ON CONFLICT(session,activity) DO UPDATE SET addition=excluded.addition",(session,activity,text))
    store.action(PROJECT_ID, session, "plan_submitted", {"activity_id": activity, "text": combined, "addition":text, "inherited_from":base["activity_id"] if base else None})
    # Planning completes the SRL planning phase, not the whole learning activity.
    return state.get_state(session)


@router.post("/activities/{activity}/submit")
def submit(activity: str, body: Payload, x_session_id: str = Header(default="")):
    if len(json.dumps(body.payload)) > 50000:
        raise HTTPException(422, "交付内容过长")
    return engine.submit(session_id(x_session_id), activity, body.payload)


@router.post("/activities/{activity}/predictions")
def prediction(activity: str, body: Prediction, x_session_id: str = Header(default="")):
    return engine.record_prediction(session_id(x_session_id), activity, body.model_dump())


@router.get("/activities/{activity}/predictions")
def predictions(activity: str, x_session_id: str = Header(default="")):
    session = session_id(x_session_id)
    with store.connection() as db:
        state.require(db, session, activity)
        return [dict(r) for r in db.execute("SELECT id,previous_id,result_id,revision FROM library_predictions WHERE session=? AND activity=? ORDER BY rowid DESC LIMIT 50", (session, activity))]


@router.post("/activities/{activity}/practice-steps/{prediction_id}")
def practice(activity: str, prediction_id: str, revision: int = Query(...), x_session_id: str = Header(default="")):
    return engine.step(session_id(x_session_id), activity, revision, prediction_id)


@router.post("/activities/{activity}/analyses")
def analyze(activity: str, revision: int = Query(...), x_session_id: str = Header(default="")):
    return engine.full(session_id(x_session_id), activity, revision)


@router.post("/activities/{activity}/center-steps")
def center_step(activity: str, body: CenterStep, revision: int = Query(..., ge=0), x_session_id: str = Header(default="")):
    return engine.center_step(session_id(x_session_id), activity, revision, body.centers, body.previous_step_id)


@router.get("/activities/{activity}/analyses")
def analyses(activity: str, x_session_id: str = Header(default="")):
    session = session_id(x_session_id)
    with store.connection() as db:
        state.require(db, session, activity)
        return [{**dict(r), "result": json.loads(r["result"])} for r in db.execute("SELECT * FROM library_analyses WHERE session=? AND activity=? ORDER BY created DESC LIMIT 100", (session, activity))]


@router.get("/activities/{activity}/dataset")
def dataset(activity: str, dataset_id: str | None = Query(default=None), x_session_id: str = Header(default="")):
    session = session_id(x_session_id)
    with store.connection() as db:
        state.require(db, session, activity)
        cfg = state.config(db, session, activity)
        selected = dataset_id or cfg["config"]["experiment"]["dataset_id"]
        require_dataset(activity, selected)
        data = load(selected)
        row = db.execute("SELECT payload FROM library_dataset_views WHERE session=? AND activity=? AND dataset_version=?", (session, activity, data["version"])).fetchone()
        if row and json.loads(row[0])["id"] == selected:
            return json.loads(row[0])
    # The initial page needs field definitions for configuration, not raw rows.
    return {**{k:v for k,v in data.items() if k != "records"}, "preview": [], "issues": [], "loaded": False, "quality_checked": False}


@router.get("/activities/{activity}/datasets")
def datasets(activity: str, x_session_id: str = Header(default="")):
    session = session_id(x_session_id)
    with store.connection() as db:
        state.require(db, session, activity)
    return available(activity)


@router.post("/activities/{activity}/tools/inspect_dataset")
def inspect_tool(activity: str, revision: int = Query(...), x_session_id: str = Header(default="")):
    session = session_id(x_session_id)
    with store.connection() as db:
        state.require(db, session, activity)
        state.require_plan(db, session, activity)
        cfg = state.check_revision(db, session, activity, revision)
    # Manual tool testing executes exactly the same LangChain tool as the Agent.
    tool = next((t for t in build_tools(session, activity, revision, cfg, None) if t.name == "inspect_dataset"), None)
    if tool is None:
        raise HTTPException(403, "数据查看工具未启用")
    value = tool.invoke({"dataset_id": cfg["experiment"]["dataset_id"], "preview_rows": 30})
    if not isinstance(value, dict):
        raise HTTPException(422, str(value))
    return value


@router.get("/runs")
def runs(activity_id: str = Query(...), x_session_id: str = Header(default="")):
    session = session_id(x_session_id)
    with store.connection() as db:
        state.require(db, session, activity_id)
        return [dict(r) for r in db.execute("SELECT r.id,r.input,r.status,r.created,m.revision FROM runs r JOIN library_runs m ON m.id=r.id WHERE r.project=? AND r.session=? AND m.activity=? ORDER BY r.created DESC LIMIT 50", (PROJECT_ID, session, activity_id))]


@router.get("/runs/{run_id}")
def run_detail(run_id: str, x_session_id: str = Header(default="")):
    result = store.detail(PROJECT_ID, session_id(x_session_id), run_id)
    if not result:
        raise HTTPException(404, "运行记录不存在")
    return result


@router.post("/runs")
async def run(body: RunInput, x_session_id: str = Header(default="")):
    session = session_id(x_session_id)
    if not body.input.strip():
        raise HTTPException(422, "请输入任务")
    with store.connection() as db:
        state.require(db, session, body.activity_id)
        if body.activity_id == ACTIVITY_IDS[0]:
            raise HTTPException(403, "先独立预测并核对，活动二再开放智能体运行")
        state.require_plan(db, session, body.activity_id)
        cfg = state.check_revision(db, session, body.activity_id, body.revision)
        if cfg["model"] not in models():
            raise HTTPException(422, "所选模型已不可用，请重新保存模型配置")
    version = load(cfg["experiment"]["dataset_id"])["version"]
    run_id = store.create_run(PROJECT_ID, session, body.input, {**cfg, "activity_id": body.activity_id, "revision": body.revision, "dataset_version": version})
    with store.connection() as db:
        db.execute("INSERT INTO library_runs VALUES(?,?,?,?)", (run_id, session, body.activity_id, body.revision))
    tools = build_tools(session, body.activity_id, body.revision, cfg, run_id, dataset_version=version)
    context = f"当前图书馆学习活动：{ACTIVITIES[ACTIVITY_IDS.index(body.activity_id)]['title']}。工具使用已保存实验配置：{json.dumps(cfg['experiment'], ensure_ascii=False)}。先用数据查看工具获取原始数据。活动二请依据学生System Prompt的步骤解释算法，可演示计算，但不得声称调用了不存在的计算工具。活动三、四的数值分析必须调用已启用的完整聚类工具，以实际返回为准；组号从0开始，向学生显示为第1、2…组。不编造数据、数量或具体书名。工具失败时如实说明。"


    context += "\n学生本活动任务要求：" + cfg.get("task_prompt", "")
    if body.activity_id == "recommend_purchase":context += "\n按学生当前选择的数据表和特征分析，不得自动换表、补充缺失字段或把借阅数据说成阅读兴趣调查。采购任务目标为1000册，数据是否支持决策应根据实际字段说明。\n" + FORMAT

    async def stream():
        def emit(kind, data):
            event = store.event(run_id, PROJECT_ID, session, kind, data)
            return "data: " + json.dumps(event, ensure_ascii=False, default=str) + "\n\n"
        try:
            yield emit("run_start", {"input": body.input})
            async for kind, data in runtime.execute(Config(**cfg), body.input, tools=tools, context=context):
                if kind == "final" and body.activity_id in ["explore_2d", "recommend_purchase"]:
                    with store.connection() as db:
                        item=engine.run_evidence(db,session,body.activity_id,run_id,body.revision,require_completed=False)
                    if body.activity_id == "recommend_purchase":
                        decision=parse(data["answer"],item["result"])
                        data={**data,"answer":decision["answer"],"decision":decision}
                    else:
                        data={**data,"group_counts":[{"group":g["label"],"count":g["count"]} for g in item["result"]["groups"]],"total":item["result"]["sample_count"]}
                yield emit(kind, data)
            store.finish(run_id, "completed")
            yield emit("done", {"status": "completed"})
        except asyncio.CancelledError:
            store.event(run_id, PROJECT_ID, session, "error", {"message": "连接中断，运行已取消"})
            store.finish(run_id, "cancelled")
            raise
        except Exception as exc:
            store.finish(run_id, "error")
            yield emit("error", {"message": str(exc.detail) if isinstance(exc, HTTPException) else runtime.public_error(exc)})
            yield emit("done", {"status": "error"})
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
