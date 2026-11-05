import asyncio
import json
import re
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from ...shared import store
from . import runtime
from .project import PROJECT_ID, project, models, default_config
from .schemas import AgentConfig, RunRequest, Activity

router = APIRouter(prefix="/api/projects/" + PROJECT_ID, tags=["astronomy"])


def scope(session):
    if not session or not re.fullmatch(r"[a-zA-Z0-9-]{16,80}", session):
        raise HTTPException(400, "需要有效 X-Session-ID")


def validate_model(config):
    if config.model not in models():
        raise HTTPException(422, "模型不在服务端允许列表中")


@router.get("")
def get_project():
    return project()


@router.get("/config")
def get_config(x_session_id: str = Header(default="")):
    scope(x_session_id)
    defaults = default_config()
    config = store.get_config(PROJECT_ID, x_session_id, defaults)
    # A provider/model change must not leave a session on an obsolete model.
    if config["model"] not in models():
        config["model"] = defaults["model"]
        store.save_config(PROJECT_ID, x_session_id, config, defaults)
    return config


@router.put("/config")
def put_config(config: AgentConfig, x_session_id: str = Header(default="")):
    scope(x_session_id)
    validate_model(config)
    return {"saved_at": store.save_config(PROJECT_ID, x_session_id, config.model_dump(), default_config())}


@router.get("/runs")
def get_runs(x_session_id: str = Header(default="")):
    scope(x_session_id)
    return store.history(PROJECT_ID, x_session_id)


@router.get("/runs/{run_id}")
def get_run(run_id: str, x_session_id: str = Header(default="")):
    scope(x_session_id)
    result = store.detail(PROJECT_ID, x_session_id, run_id)
    if not result:
        raise HTTPException(404, "运行记录不存在")
    return result


@router.get("/activities")
def get_activities(x_session_id: str = Header(default="")):
    scope(x_session_id)
    return store.activities(PROJECT_ID, x_session_id)


@router.post("/activities")
def post_activity(activity: Activity, x_session_id: str = Header(default="")):
    scope(x_session_id)
    store.action(PROJECT_ID, x_session_id, activity.action, {"step": activity.step})
    return {"ok": True}


@router.post("/runs")
async def run(body: RunRequest, x_session_id: str = Header(default="")):
    scope(x_session_id)
    validate_model(body.config)
    if not body.input.strip():
        raise HTTPException(422, "请输入任务")
    run_id = store.create_run(PROJECT_ID, x_session_id, body.input, body.config.model_dump())

    async def stream():
        def emit(kind, data):
            e = store.event(run_id, PROJECT_ID, x_session_id, kind, data)
            return f"id: {e['id']}\ndata: {json.dumps(e, ensure_ascii=False, default=str)}\n\n"

        try:
            yield emit("run_start", {"input": body.input})
            async for kind, data in runtime.execute(body.config, body.input):
                yield emit(kind, data)
            store.finish(run_id, "completed")
            yield emit("done", {"status": "completed"})
        except asyncio.CancelledError:
            store.event(run_id, PROJECT_ID, x_session_id, "error", {"message": "客户端连接中断，运行已取消"})
            store.finish(run_id, "cancelled")
            raise
        except Exception as exc:
            yield emit("error", {"message": runtime.public_error(exc)})
            store.finish(run_id, "error")
            yield emit("done", {"status": "error"})

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
