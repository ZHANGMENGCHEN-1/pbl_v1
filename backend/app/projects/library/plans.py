"""Versioned task-spanning plan choices. Choices are categories, not scores."""
import json
from fastapi import HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from ...shared import store
from .project import PROJECT_ID

STRATEGIES = {
    "read_first": "先读懂任务和材料，再开始操作。",
    "try_first": "先试一次，再根据结果决定下一步。",
    "reuse_first": "先参考上次的做法，再决定怎么做。",
}
CHECKS = {
    "requirements": "对照任务要求，检查有没有完成。",
    "evidence": "回看数据和操作过程，检查结果有没有依据。",
    "comparison": "换一种做法试试，比较结果是否一致。",
}
REASONS = {
    "unmet_expectation": "上次这样做，没达到我的预期。",
    "found_problem": "上次发现了问题，这次想换个办法。",
    "different_task": "这次的任务不同，需要换个办法。",
}


class PlanCardInput(BaseModel):
    strategy: Literal["read_first", "try_first", "reuse_first"]
    check: Literal["requirements", "evidence", "comparison"]
    reason: Literal["unmet_expectation", "found_problem", "different_task"] | None = None
    phase: Literal["before", "during"]
    base_version: int = Field(ge=0)


def init():
    with store.connection() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS library_plan_versions(
            project TEXT, session TEXT, version INTEGER, activity TEXT,
            payload TEXT, created TEXT, PRIMARY KEY(project,session,version))""")


def latest(db, session):
    row=db.execute("SELECT payload FROM library_plan_versions WHERE project=? AND session=? ORDER BY version DESC LIMIT 1",(PROJECT_ID,session)).fetchone()
    return json.loads(row[0]) if row else None


def history(session):
    with store.connection() as db:
        return [json.loads(row[0]) for row in db.execute("SELECT payload FROM library_plan_versions WHERE project=? AND session=? ORDER BY version DESC",(PROJECT_ID,session))]


def save(session, activity, body):
    from . import state
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        state.require(db,session,activity)
        previous=latest(db,session)
        version=previous["version"] if previous else 0
        if body.base_version!=version:
            raise HTTPException(409,"计划已在其他页面更新，请刷新后再确认")
        changed=[key for key in ("strategy","check") if previous and previous[key]!=getattr(body,key)]
        if changed and not body.reason:
            raise HTTPException(422,"你修改了计划，请选择修改原因")
        if not changed and body.reason:
            raise HTTPException(422,"没有修改选择时，不需要填写修改原因")
        record={"version":version+1,"previous_version":version or None,"activity_id":activity,
                "strategy":body.strategy,"check":body.check,"reason":body.reason,
                "strategy_label":STRATEGIES[body.strategy],"check_label":CHECKS[body.check],
                "reason_label":REASONS.get(body.reason),"phase":body.phase,"changed_fields":changed,
                "kind":"initial" if not previous else "modified" if changed else "carried_forward" if previous["activity_id"]!=activity else "confirmed",
                "question_version":1,"submitted_at":store.now()}
        legacy=db.execute("SELECT text FROM library_plans WHERE session=? AND activity=?",(session,activity)).fetchone()
        already_converted=db.execute("SELECT 1 FROM library_plan_versions WHERE project=? AND session=? AND activity=? LIMIT 1",(PROJECT_ID,session,activity)).fetchone()
        if legacy and not already_converted:
            record["legacy_plan_text"]=legacy[0]
        db.execute("INSERT INTO library_plan_versions VALUES(?,?,?,?,?,?)",(PROJECT_ID,session,record["version"],activity,json.dumps(record,ensure_ascii=False),record["submitted_at"]))
        # Keep existing activity gates/delivery summaries compatible; historical
        # free-text plans are retained and never converted into guessed choices.
        text="我的做法："+STRATEGIES[body.strategy]+"\n我的检查方法："+CHECKS[body.check]
        db.execute("INSERT INTO library_plans VALUES(?,?,?,?) ON CONFLICT(session,activity) DO UPDATE SET text=excluded.text,submitted_at=excluded.submitted_at",(session,activity,text,record["submitted_at"]))
        db.execute("INSERT INTO library_plan_details VALUES(?,?,?) ON CONFLICT(session,activity) DO UPDATE SET addition=excluded.addition",(session,activity,text))
    store.action(PROJECT_ID,session,"plan_card_submitted",record)
    return state.get_state(session)
