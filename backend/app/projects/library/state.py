import json
from uuid import uuid4
from fastapi import HTTPException
from ...shared import store
from .project import ACTIVITY_IDS, ACTIVITIES, PROJECT_ID, default_config, TASK_PROMPTS
from .datasets import load, require_dataset
from .prompt import TEMPLATE, upgrade_saved_prompt


def init():
    with store.connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS library_configs(session TEXT, activity TEXT, revision INTEGER, config TEXT, PRIMARY KEY(session,activity));
        CREATE TABLE IF NOT EXISTS library_submissions(id TEXT PRIMARY KEY, session TEXT, activity TEXT, revision INTEGER, payload TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS library_drafts(session TEXT, activity TEXT, payload TEXT, PRIMARY KEY(session,activity));
        CREATE TABLE IF NOT EXISTS library_predictions(id TEXT PRIMARY KEY, session TEXT, activity TEXT, revision INTEGER, previous_id TEXT, payload TEXT, result_id TEXT);
        CREATE TABLE IF NOT EXISTS library_analyses(id TEXT PRIMARY KEY, session TEXT, activity TEXT, revision INTEGER, kind TEXT, result TEXT, run_id TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS library_runs(id TEXT PRIMARY KEY, session TEXT, activity TEXT, revision INTEGER);
        CREATE TABLE IF NOT EXISTS library_plans(session TEXT, activity TEXT, text TEXT, submitted_at TEXT, PRIMARY KEY(session,activity));
        CREATE TABLE IF NOT EXISTS library_dataset_views(session TEXT, activity TEXT, dataset_version TEXT, payload TEXT, created TEXT, PRIMARY KEY(session,activity,dataset_version));
        CREATE TABLE IF NOT EXISTS library_plan_details(session TEXT, activity TEXT, addition TEXT, PRIMARY KEY(session,activity));
        CREATE INDEX IF NOT EXISTS library_submissions_session ON library_submissions(session,activity);
        CREATE INDEX IF NOT EXISTS library_analyses_session ON library_analyses(session,activity);
        """)


def unlocked(db, session):
    completed = {r[0] for r in db.execute("SELECT DISTINCT activity FROM library_submissions WHERE session=?", (session,))}
    count = 0
    for id in ACTIVITY_IDS:
        if id not in completed:
            break
        count += 1
    return count


def require(db, session, activity):
    if activity not in ACTIVITY_IDS:
        raise HTTPException(404, "学习活动不存在")
    if ACTIVITY_IDS.index(activity) > unlocked(db, session):
        raise HTTPException(403, "请先提交前一个活动的交付物")


def require_plan(db, session, activity):
    plan = db.execute("SELECT 1 FROM library_plans WHERE session=? AND activity=?", (session, activity)).fetchone()
    legacy = db.execute("SELECT 1 FROM library_submissions WHERE session=? AND activity=?", (session, activity)).fetchone()
    if not plan and not legacy:
        raise HTTPException(403, "请先提交本活动的学习计划，再开始实验")


def config(db, session, activity):
    row = db.execute("SELECT revision,config FROM library_configs WHERE session=? AND activity=?", (session, activity)).fetchone()
    if row:
        value = json.loads(row[1])
        value.pop("run_kmeans_step", None)
        if activity == "explain_algorithm" and "prompt_steps" not in value:
            value["prompt_steps"] = []
            if row[0] == 0:
                value["system_prompt"] = TEMPLATE
            db.execute("UPDATE library_configs SET config=? WHERE session=? AND activity=?", (json.dumps(value, ensure_ascii=False), session, activity))
        changed=False
        upgraded=upgrade_saved_prompt(value["system_prompt"])
        if upgraded!=value["system_prompt"]:
            value["system_prompt"]=upgraded;changed=True
        if activity == "explore_2d":
            if value["experiment"]["dataset_id"] == "library_sample_2d":
                value["experiment"]["dataset_id"] = "library_books_2d";changed=True
            if value["experiment"]["k"]!=2:
                value["experiment"]["k"]=2;changed=True
        if activity == "recommend_purchase" and value["experiment"]["dataset_id"] == "reading_interest_survey":
            value["experiment"].update(dataset_id="reading_interest_students",features=["content_preference","duration_preference"],k=2);changed=True
        if activity in TASK_PROMPTS and "task_prompt" not in value:
            value["task_prompt"]=TASK_PROMPTS[activity];changed=True
        if changed:
            db.execute("UPDATE library_configs SET config=?,revision=? WHERE session=? AND activity=?",(json.dumps(value,ensure_ascii=False),row[0]+1,session,activity))
            return {"revision":row[0]+1,"config":value}
        return {"revision": row[0], "config": value}
    value = default_config()
    value["experiment"]["dataset_id"] = ACTIVITIES[ACTIVITY_IDS.index(activity)]["dataset_id"]
    if activity == "explore_2d":
        value["experiment"]["features"] = ["borrow_count", "borrow_days"]
    if activity == "recommend_purchase":
        value["experiment"].update(features=["content_preference", "duration_preference"], k=2)
    for previous in reversed(ACTIVITY_IDS[:ACTIVITY_IDS.index(activity)]):
        saved = db.execute("SELECT config FROM library_configs WHERE session=? AND activity=?", (session, previous)).fetchone()
        if saved:
            old = json.loads(saved[0])
            for field in ["model", "temperature", "system_prompt", "prompt_steps", "inspect_dataset", "run_kmeans_analysis"]:
                if field in old:value[field] = old[field]
            break
    if activity == "explain_algorithm":
        value["system_prompt"] = TEMPLATE
        value["prompt_steps"] = []
    value["task_prompt"]=TASK_PROMPTS.get(activity, "")
    value["system_prompt"]=upgrade_saved_prompt(value["system_prompt"])
    # Freeze inherited defaults on first access so revision 0 is a real snapshot,
    # rather than changing silently when an earlier activity's Prompt is edited.
    db.execute("INSERT OR IGNORE INTO library_configs VALUES(?,?,0,?)", (session, activity, json.dumps(value, ensure_ascii=False)))
    row = db.execute("SELECT revision,config FROM library_configs WHERE session=? AND activity=?", (session, activity)).fetchone()
    return {"revision": row[0], "config": json.loads(row[1])}


def check_config(activity, value):
    index = ACTIVITY_IDS.index(activity)
    ex = value["experiment"]
    require_dataset(activity, ex["dataset_id"])
    data = load(ex["dataset_id"])
    if not set(ex["features"]) <= set(data["features"]) or len(set(ex["features"])) != len(ex["features"]):
        raise HTTPException(422, "特征不在当前数据集中或存在重复")
    if index < 2 and ex != default_config()["experiment"]:
        raise HTTPException(403, "前两个活动使用固定的一维实验参数")
    if index == 2 and ex["k"] != 2:
        raise HTTPException(422, "活动三需要将150条二维数据分成2组，K应为2")


def get_state(session):
    with store.connection() as db:
        count = unlocked(db, session)
        result = []
        for i, activity in enumerate(ACTIVITIES):
            latest = db.execute("SELECT id,revision,payload,created FROM library_submissions WHERE session=? AND activity=? ORDER BY created DESC LIMIT 1", (session, activity["id"])).fetchone()
            draft = db.execute("SELECT payload FROM library_drafts WHERE session=? AND activity=?", (session, activity["id"])).fetchone()
            item = {"id": activity["id"], "title": activity["title"], "status": "submitted" if i < count else "available" if i == count else "locked"}
            if i <= count:
                item.update(activity)
                item["submission"] = {**dict(latest), "payload": json.loads(latest["payload"])} if latest else None
                item["draft"] = json.loads(draft[0]) if draft else {}
                plan = db.execute("SELECT text,submitted_at FROM library_plans WHERE session=? AND activity=?", (session, activity["id"])).fetchone()
                detail=db.execute("SELECT addition FROM library_plan_details WHERE session=? AND activity=?",(session,activity["id"])).fetchone()
                item["plan"] = {**dict(plan), "addition":detail[0] if detail else plan["text"]} if plan else None
                item["inherited_plan"] = inherited_plan(db,session,activity["id"])

            result.append(item)
        return {"completed": count, "activities": result}


def analysis(db, session, activity, id):
    row = db.execute("SELECT * FROM library_analyses WHERE id=? AND session=? AND activity=?", (id, session, activity)).fetchone()
    if not row:
        raise HTTPException(404, "计算记录不存在或不属于本活动")
    return {**dict(row), "result": json.loads(row["result"])}


def save_analysis(db, session, activity, revision, kind, result, run_id=None):
    id = str(uuid4())
    result = {**result, "analysis_id": id}
    db.execute("INSERT INTO library_analyses VALUES(?,?,?,?,?,?,?,?)", (id, session, activity, revision, kind, json.dumps(result, ensure_ascii=False), run_id, store.now()))
    return result


def check_revision(db, session, activity, revision):
    value = config(db, session, activity)
    if value["revision"] != revision:
        raise HTTPException(409, "配置已更新，请重新加载并运行")
    return value["config"]


def inherited_plan(db,session,activity):
    for previous in reversed(ACTIVITY_IDS[:ACTIVITY_IDS.index(activity)]):
        row=db.execute("SELECT text FROM library_plans WHERE session=? AND activity=?",(session,previous)).fetchone()
        if row:
            return {"activity_id":previous,"title":ACTIVITIES[ACTIVITY_IDS.index(previous)]["title"],"text":row[0]}
    return None
