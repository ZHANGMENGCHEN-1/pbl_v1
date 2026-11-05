import json
from uuid import uuid4
import numpy as np
from fastapi import HTTPException
from ...shared import store
from . import state, clustering
from .project import PROJECT_ID, ACTIVITY_IDS, ACTIVITIES
from .datasets import load, preview, require_dataset
from .prompt import validate, render
from .decisions import validate_purchases


def record_prediction(session, activity, payload):
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        state.require(db, session, activity)
        state.require_plan(db, session, activity)
        if activity != ACTIVITY_IDS[0]:
            raise HTTPException(403, "当前活动不使用手动预测")
        cfg = state.config(db, session, activity)
        data_version = load(cfg["config"]["experiment"]["dataset_id"])["version"]
        viewed = db.execute("SELECT payload FROM library_dataset_views WHERE session=? AND activity=? AND dataset_version=?", (session, activity, data_version)).fetchone()
        if not viewed:
            raise HTTPException(403, "请先调用数据查看工具，获得本活动的数据后再提交预测")
        if len(json.loads(viewed[0])["preview"]) < 5:
            raise HTTPException(403, "请调用数据查看工具完整查看五个样本，再填写预测")
        previous = payload.get("previous_step_id")
        if previous:
            value = state.analysis(db, session, activity, previous)
            if value["kind"] != "step" or value["revision"] != cfg["revision"]:
                raise HTTPException(409, "上一轮记录与当前设置不匹配")
            if value["result"]["dataset_version"] != load(value["result"]["dataset_id"])["version"]:
                raise HTTPException(409, "数据已更新，请从初始中心重新开始")
            if value["result"]["converged"]:
                raise HTTPException(422, "此实验已经收敛，可提交成果或重新开始")
        if any(label not in [0, 1] for label in payload["labels"]) or any(len(c) != 1 for c in payload["centers"]) or not np.isfinite(np.array(payload["centers"])).all():
            raise HTTPException(422, "请选择两组，并填写两个有限数值的中心点")
        id = str(uuid4())
        db.execute("INSERT INTO library_predictions VALUES(?,?,?,?,?,?,NULL)", (id, session, activity, cfg["revision"], previous, json.dumps(payload)))
    store.action(PROJECT_ID, session, "prediction_submitted", {"activity_id": activity, "prediction_id": id, **payload})
    return {"prediction_id": id}


def step(session, activity, revision, prediction_id, run_id=None):
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        state.require(db, session, activity)
        state.require_plan(db, session, activity)
        cfg = state.check_revision(db, session, activity, revision)
        if activity != ACTIVITY_IDS[0]:
            raise HTTPException(403, "当前活动未启用一轮计算工具")
        row = db.execute("SELECT * FROM library_predictions WHERE id=? AND session=? AND activity=?", (prediction_id, session, activity)).fetchone()
        if not row:
            raise HTTPException(403, "请先提交本轮预测，不能直接请求答案")
        if row["revision"] != revision:
            raise HTTPException(409, "预测对应的配置已变化，请重新预测")
        if row["result_id"]:
            return state.analysis(db, session, activity, row["result_id"])["result"]
        previous = state.analysis(db, session, activity, row["previous_id"])["result"] if row["previous_id"] else None
        centers = previous["centers"] if previous else [[2], [11]]
        result = clustering.analyze(cfg["experiment"], centers, step_only=True)
        prediction = json.loads(row["payload"])
        result.update(round=(previous["round"] + 1 if previous else 1), previous_step_id=row["previous_id"], prediction_id=prediction_id,
                      prediction=prediction, prediction_match=prediction["labels"] == result["labels"] and bool(np.allclose(prediction["centers"], result["centers"], atol=0.02, rtol=0)))
        result = state.save_analysis(db, session, activity, revision, "step", result, run_id)
        db.execute("UPDATE library_predictions SET result_id=? WHERE id=?", (result["analysis_id"], prediction_id))
    store.action(PROJECT_ID, session, "step_calculated", {"activity_id": activity, "analysis_id": result["analysis_id"], "source": "agent" if run_id else "practice"})
    return result


def center_step(session, activity, revision, centers, previous_id=None):
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        state.require(db, session, activity)
        state.require_plan(db, session, activity)
        if activity != ACTIVITY_IDS[0]:
            raise HTTPException(403, "数轴实验只用于活动一")
        cfg = state.check_revision(db, session, activity, revision)
        if not np.isfinite(centers).all() or any(v < 0 or v > 20 for v in centers) or centers[0] == centers[1]:
            raise HTTPException(422, "请选择0到20之间两个不同的中心点")
        previous = None
        if previous_id:
            item = state.analysis(db, session, activity, previous_id)
            previous = item["result"]
            if item["kind"] != "step" or item["revision"] != revision or previous["dataset_version"] != load(cfg["experiment"]["dataset_id"])["version"]:
                raise HTTPException(409, "上一轮记录与当前实验不匹配")
            if previous["converged"] or not np.allclose(np.array(centers), np.array(previous["centers"]).flatten(), atol=1e-10, rtol=0):
                raise HTTPException(422, "请使用上一轮的新中心，或重新开始实验")
        result = clustering.analyze(cfg["experiment"], [[v] for v in centers], step_only=True)
        result.update(round=previous["round"] + 1 if previous else 1, previous_step_id=previous_id, interaction="center_selection")
        result = state.save_analysis(db, session, activity, revision, "step", result, None)
    store.action(PROJECT_ID, session, "center_step_calculated", {"activity_id": activity, "centers": centers, "previous_step_id": previous_id, "analysis_id": result["analysis_id"]})
    return result


def full(session, activity, revision, run_id=None):
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        state.require(db, session, activity)
        state.require_plan(db, session, activity)
        cfg = state.check_revision(db, session, activity, revision)
        if activity not in ACTIVITY_IDS[2:] or not cfg["run_kmeans_analysis"]["enabled"]:
            raise HTTPException(403, "完整聚类尚未解锁或工具未启用")
        result = clustering.analyze(cfg["experiment"])
        result = state.save_analysis(db, session, activity, revision, "full", result, run_id)
    store.action(PROJECT_ID, session, "analysis_calculated", {"activity_id": activity, "analysis_id": result["analysis_id"], "source": "agent" if run_id else "practice"})
    return result


def inspect(session, activity, revision, dataset_id, count, run_id=None):
    with store.connection() as db:
        state.require(db, session, activity)
        state.require_plan(db, session, activity)
        cfg = state.check_revision(db, session, activity, revision)
        if not cfg["inspect_dataset"]["enabled"] or cfg["experiment"]["dataset_id"] != dataset_id:
            raise HTTPException(403, "只能查看当前活动已启用的数据集")
        require_dataset(activity, dataset_id)
        value = {**preview(dataset_id, max(1, min(30, count))), "loaded": True, "quality_checked": True}
        old = db.execute("SELECT payload FROM library_dataset_views WHERE session=? AND activity=? AND dataset_version=?", (session, activity, value["version"])).fetchone()
        if not old or json.loads(old[0])["id"] != dataset_id or len(json.loads(old[0])["preview"]) <= len(value["preview"]):
            db.execute("INSERT INTO library_dataset_views VALUES(?,?,?,?,?) ON CONFLICT(session,activity,dataset_version) DO UPDATE SET payload=excluded.payload,created=excluded.created", (session, activity, value["version"], json.dumps(value, ensure_ascii=False), store.now()))
    store.action(PROJECT_ID, session, "tool_test_result" if run_id is None else "dataset_tool_result", {"activity_id": activity, "tool": "inspect_dataset", "revision": revision, "run_id": run_id, "input": {"dataset_id": dataset_id, "preview_rows": count}, "output": value})
    return value


def completed_run(db, session, activity, id, revision):
    row = db.execute("SELECT r.status,m.revision FROM runs r JOIN library_runs m ON m.id=r.id WHERE r.id=? AND r.project=? AND r.session=? AND m.activity=?", (id, PROJECT_ID, session, activity)).fetchone()
    if not row or row["status"] != "completed":
        raise HTTPException(422, "请选择本活动一次已完成的智能体运行")
    if row["revision"] != revision:
        raise HTTPException(409, "所选运行使用了旧配置，请用当前配置重新运行")
    answer = db.execute("SELECT data FROM events WHERE run_id=? AND type='final' ORDER BY id DESC LIMIT 1", (id,)).fetchone()
    if not answer:
        raise HTTPException(422, "所选运行没有最终回答")
    return json.loads(answer[0])["answer"]


def submit(session, activity, payload):
    def text(name, minimum=6):
        value = payload.get(name)
        if not isinstance(value, str) or len(value.strip()) < minimum or len(value) > 12000:
            raise HTTPException(422, f"请完整填写{name}，并说明具体依据")

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        state.require(db, session, activity)
        state.require_plan(db, session, activity)
        cfg = state.config(db, session, activity)
        revision = cfg["revision"]

        def evidence(id):
            item = state.analysis(db, session, activity, id)
            if item["result"]["dataset_version"] != load(item["result"]["dataset_id"])["version"]:
                raise HTTPException(409, "数据文件已更新，请重新进行实验")
            return item

        if activity == ACTIVITY_IDS[0]:
            text("plan")
            item = evidence(payload.get("analysis_id", ""))
            if item["kind"] != "step" or not item["result"]["converged"] or not (item["result"].get("interaction") == "center_selection" or item["result"].get("prediction_match")):
                raise HTTPException(422, "请继续逐轮预测，直到分组稳定且最终预测与工具结果一致")
        elif activity == ACTIVITY_IDS[1]:
            if revision == 0:
                raise HTTPException(422, "请先排列七个步骤并保存 System Prompt")
            steps = cfg["config"].get("prompt_steps", [])
            validate(steps)
            if cfg["config"]["system_prompt"] != render(steps):
                raise HTTPException(422, "Prompt 与排序不一致，请重新保存")
            payload["prompt_steps"] = steps
            payload["system_prompt"] = cfg["config"]["system_prompt"]
        elif activity == ACTIVITY_IDS[2]:
            run_id=payload.get("run_id", "")
            payload["agent_answer"]=completed_run(db,session,activity,run_id,revision)
            item=run_evidence(db,session,activity,run_id,revision)
            payload["analysis_id"]=item["id"]
            payload["group_counts"]=[{"group":g["label"],"count":g["count"]} for g in item["result"]["groups"]]
            payload["total"]=item["result"]["sample_count"]
        else:
            text("reflection")
            run_id=payload.get("run_id", "")
            payload["agent_answer"]=completed_run(db,session,activity,run_id,revision)
            item=run_evidence(db,session,activity,run_id,revision)
            row=db.execute("SELECT data FROM events WHERE run_id=? AND type='final' ORDER BY id DESC LIMIT 1",(run_id,)).fetchone()
            decision=json.loads(row[0]).get("decision") if row else None
            if not decision:
                raise HTTPException(422,"请重新运行Agent，生成包含类型与数量的采购建议")
            validate_purchases(decision.get("purchases"),item["result"])
            purchases=payload.get("purchases") or decision["purchases"]
            validate_purchases(purchases,item["result"])
            payload["purchases"]=purchases
            payload["rationale"]=payload.get("rationale") or decision["rationale"]
            text("rationale")
            payload["agent_decision"]=decision
            payload["analysis_id"]=item["id"]
        id = str(uuid4())
        db.execute("INSERT INTO library_submissions VALUES(?,?,?,?,?,?)", (id, session, activity, revision, json.dumps(payload, ensure_ascii=False), store.now()))
    store.action(PROJECT_ID, session, "submission_accepted", {"activity_id": activity, "submission_id": id, "revision": revision})
    return state.get_state(session)


def run_evidence(db,session,activity,run_id,revision,require_completed=True):
    row=db.execute("SELECT r.status,m.revision FROM runs r JOIN library_runs m ON m.id=r.id WHERE r.id=? AND r.project=? AND r.session=? AND m.activity=?",(run_id,PROJECT_ID,session,activity)).fetchone()
    if not row or (require_completed and row["status"]!="completed"):
        raise HTTPException(422,"请选择本活动已完成、实际调用工具的Agent运行")
    if row["revision"]!=revision:
        raise HTTPException(409,"所选运行属于旧配置，请重新运行Agent")
    used=db.execute("SELECT data FROM events WHERE run_id=? AND type='tool_result'",(run_id,)).fetchall()
    if not any(json.loads(r[0]).get("tool")=="inspect_dataset" and json.loads(r[0]).get("status","success")=="success" for r in used):
        raise HTTPException(422,"请让Agent在本次运行中实际调用数据查看工具和完整聚类工具")
    found=db.execute("SELECT id FROM library_analyses WHERE session=? AND activity=? AND run_id=? AND revision=? AND kind='full' ORDER BY created DESC LIMIT 1",(session,activity,run_id,revision)).fetchone()
    if not found:
        raise HTTPException(422,"本次Agent尚未实际完成完整聚类工具调用")
    item=state.analysis(db,session,activity,found[0]);result=item["result"]
    cfg=state.check_revision(db,session,activity,revision)
    expected="library_books_2d" if activity=="explore_2d" else cfg["experiment"]["dataset_id"]
    features=["borrow_count","borrow_days"] if activity=="explore_2d" else cfg["experiment"]["features"]
    if result["dataset_id"]!=expected or cfg["experiment"]["dataset_id"]!=expected or set(result["experiment"]["features"])!=set(features):
        raise HTTPException(422,"请使用本活动的二维数据表及两个特征运行Agent")
    if result["dataset_version"]!=load(expected)["version"]:
        raise HTTPException(409,"数据已更新，请重新运行Agent")
    if not result["converged"]:
        raise HTTPException(422,"本次聚类尚未稳定，请重新运行")
    if activity=="explore_2d" and (result["sample_count"]!=150 or result["excluded"]):
        raise HTTPException(422,"活动三交付需要全部150条有效记录")
    if activity=="explore_2d" and (result["experiment"]["k"]!=2 or len([g for g in result["groups"] if g["count"]>0])!=2):
        raise HTTPException(422,"活动三需要将150条数据分成两个非空组")
    return item
