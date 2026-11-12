import json
import math
import re
from uuid import uuid4

import numpy as np
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from ...shared import store
from ..library.clustering import one_step

PROJECT = "teaching-agent"
BOOKS = [{"id": str(i + 1), "name": name, "value": value} for i, (name, value) in enumerate([
    ("种梨", 2), ("傲慢与偏见", 6), ("如果历史是一群猫", 9), ("浙江寻宝记", 16), ("奇妙博物院", 18)])]
router = APIRouter(prefix="/api/projects/teaching-agent", tags=["teaching"])


def init():
    with store.connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS teaching_steps(id TEXT PRIMARY KEY, project TEXT, session TEXT, previous_id TEXT, result TEXT, created TEXT);
        CREATE INDEX IF NOT EXISTS teaching_steps_session ON teaching_steps(project,session);
        CREATE UNIQUE INDEX IF NOT EXISTS teaching_steps_next ON teaching_steps(project,session,previous_id) WHERE previous_id IS NOT NULL;
        CREATE TABLE IF NOT EXISTS teaching_submissions(id TEXT PRIMARY KEY, project TEXT, session TEXT, activity TEXT, result_id TEXT, payload TEXT, created TEXT);
        CREATE INDEX IF NOT EXISTS teaching_submissions_session ON teaching_submissions(project,session);
        CREATE TABLE IF NOT EXISTS teaching_students(project TEXT, session TEXT, class_name TEXT NOT NULL, student_number TEXT NOT NULL, created TEXT NOT NULL, PRIMARY KEY(project,session));
        """)


def session_id(value):
    if not re.fullmatch(r"[a-zA-Z0-9-]{16,80}", value):
        raise HTTPException(400, "学习会话无效，请刷新后重试。")
    return value


class StepInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    centers: list[float] | None = Field(default=None, min_length=2, max_length=2)
    previous_id: str | None = Field(default=None, min_length=1, max_length=80)


class StudentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    class_name: str = Field(min_length=1, max_length=80)
    student_number: str = Field(min_length=1, max_length=40)


@router.post("/student")
def register_student(body: StudentInput, x_session_id: str = Header(default="")):
    session = session_id(x_session_id)
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT class_name,student_number FROM teaching_students WHERE project=? AND session=?", (PROJECT, session)).fetchone()
        if existing and (existing['class_name'], existing['student_number']) != (body.class_name, body.student_number):
            raise HTTPException(409, "当前会话已关联其他学生，请重新开始后填写。")
        db.execute("INSERT OR IGNORE INTO teaching_students VALUES(?,?,?,?,?)", (PROJECT, session, body.class_name, body.student_number, store.now()))
        from .telemetry import event
        event(db, session, 'student_registered', event_id=f'registered:{session}')
    return {"session_id": session, "class_name": body.class_name, "student_number": body.student_number}


class SubmissionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result_id: str = Field(min_length=1, max_length=80)
    counts: list[StrictInt] = Field(min_length=2, max_length=2)
    centers: list[float] = Field(min_length=2, max_length=2)
    request_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=80)

    @field_validator("centers", mode="before")
    @classmethod
    def numeric_centers(cls, value):
        if not isinstance(value, list) or any(type(n) not in (int, float) or not math.isfinite(n) for n in value):
            raise ValueError("请填写两个有限数值的中心。")
        return value


def get_step(db, session, id):
    row = db.execute("SELECT result FROM teaching_steps WHERE id=? AND project=? AND session=?", (id, PROJECT, session)).fetchone()
    if not row:
        raise HTTPException(404, "找不到这次计算，请重新开始或刷新后重试。")
    return json.loads(row[0])


@router.get("/activities/group_books/state")
def state(x_session_id: str = Header(default="")):
    session = session_id(x_session_id)
    with store.connection() as db:
        steps = [json.loads(row[0]) for row in db.execute("SELECT result FROM teaching_steps WHERE project=? AND session=? ORDER BY created,id", (PROJECT, session))]
        submissions = [{**dict(row), "payload": json.loads(row["payload"])} for row in db.execute("SELECT id,result_id,payload,created FROM teaching_submissions WHERE project=? AND session=? AND activity='group_books' ORDER BY created,id", (PROJECT, session))]
    return {"books": BOOKS, "steps": steps, "submissions": submissions}


@router.post("/activities/group_books/steps")
def calculate(body: StepInput, x_session_id: str = Header(default="")):
    session = session_id(x_session_id)
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = get_step(db, session, body.previous_id) if body.previous_id else None
        if previous:
            if body.centers is not None:
                raise HTTPException(422, "下一轮由程序使用完整精度的新中心，请不要重新输入近似值。")
            if previous["converged"]:
                raise HTTPException(409, "分组和中心已经稳定，可以填写结果。")
            existing = db.execute("SELECT result FROM teaching_steps WHERE project=? AND session=? AND previous_id=?", (PROJECT, session, body.previous_id)).fetchone()
            if existing:
                return json.loads(existing[0])
            if previous["round"] >= 100:
                raise HTTPException(422, "计算轮数过多，请重新选择开始的中心。")
            centers = previous["centers_after"]
        else:
            centers = body.centers
            if not centers or any(not math.isfinite(n) or n < 0 or n > 20 for n in centers) or centers[0] == centers[1]:
                raise HTTPException(422, "请在0到20之间选择两个不同的中心。")
        frame = one_step(np.array([[book["value"]] for book in BOOKS], dtype=float), [[n] for n in centers])
        groups = [{"group": i, "count": frame["labels"].count(i), "values": [book["value"] for j, book in enumerate(BOOKS) if frame["labels"][j] == i], "center": frame["centers_after"][i][0]} for i in range(2)]
        context = {"activity_id": "group_books", "source": "python_numpy", "round": previous["round"] + 1 if previous else 1,
                   "records": [{**book, "group": frame["labels"][i], "distances": frame["distances"][i]} for i, book in enumerate(BOOKS)],
                   "centers_before": centers, "centers_after": [c[0] for c in frame["centers_after"]], "groups": groups,
                   "converged": frame["converged"], "warnings": frame["warnings"], "tie_policy": "距离相同归入第1组", "empty_group_policy": "空组保留原中心"}
        result = {"id": str(uuid4()), "previous_id": body.previous_id, "created": store.now(), "books": BOOKS, **context, "teaching_context": context}
        db.execute("INSERT INTO teaching_steps(id,project,session,previous_id,result,created) VALUES(?,?,?,?,?,?)", (result["id"], PROJECT, session, body.previous_id, json.dumps(result, ensure_ascii=False), result["created"]))
        from .telemetry import event
        event(db, session, 'calculation_completed', 'group_books', result['id'], {'round': result['round']})
    return result


@router.post("/activities/group_books/submissions")
def submit(body: SubmissionInput, x_session_id: str = Header(default="")):
    session = session_id(x_session_id)
    if any(n < 0 for n in body.counts) or sum(body.counts) != len(BOOKS):
        raise HTTPException(422, "请填写两组数量，合计5本书。")
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        result = get_step(db, session, body.result_id)
        if not result["converged"]:
            raise HTTPException(422, "请继续计算，等分组和中心稳定后再提交。")
        payload = {"kind": "learning_result", "student_result": {"counts": body.counts, "centers": body.centers}, "calculation_result": result,
                   "tool_result": {"counts": [g["count"] for g in result["groups"]], "centers": result["centers_after"]}, "teaching_context": result["teaching_context"]}
        payload['comparison'] = {'counts_match': body.counts == payload['tool_result']['counts'],
                                 'centers_match': [math.isclose(value, expected, rel_tol=0, abs_tol=0.001) for value, expected in zip(body.centers, result['centers_after'])],
                                 'center_absolute_tolerance': 0.001}
        from .telemetry import save_submission
        record = save_submission(db, session, 'group_books', body.result_id, payload, body.request_id)
    return record
