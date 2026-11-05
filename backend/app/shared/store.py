import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    path = Path(os.getenv("DATABASE_PATH", "data/workspace.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=15) as db:
        db.row_factory = sqlite3.Row
        yield db


def init():
    with connection() as db:
        db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS configs(project TEXT, session TEXT, config TEXT, updated TEXT, PRIMARY KEY(project,session));
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, project TEXT, session TEXT, input TEXT, config TEXT, status TEXT, created TEXT, finished TEXT);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, project TEXT, session TEXT, type TEXT, data TEXT, timestamp TEXT);
        CREATE TABLE IF NOT EXISTS actions(id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT, session TEXT, action TEXT, data TEXT, timestamp TEXT);
        CREATE INDEX IF NOT EXISTS runs_session ON runs(project,session,created);
        CREATE INDEX IF NOT EXISTS events_run ON events(run_id,id);
        """)
        db.execute("UPDATE runs SET status='interrupted', finished=? WHERE status='running'", (now(),))


def get_config(project, session, default):
    with connection() as db:
        row = db.execute("SELECT config FROM configs WHERE project=? AND session=?", (project, session)).fetchone()
    return json.loads(row[0]) if row else default


def action(project, session, name, data):
    with connection() as db:
        db.execute("INSERT INTO actions(project,session,action,data,timestamp) VALUES(?,?,?,?,?)", (project, session, name, json.dumps(data, ensure_ascii=False), now()))


def save_config(project, session, config, default):
    old = get_config(project, session, default)
    stamp = now()
    with connection() as db:
        db.execute("INSERT INTO configs VALUES(?,?,?,?) ON CONFLICT(project,session) DO UPDATE SET config=excluded.config,updated=excluded.updated", (project, session, json.dumps(config, ensure_ascii=False), stamp))
        for key, value in config.items():
            if old.get(key) != value:
                db.execute("INSERT INTO actions(project,session,action,data,timestamp) VALUES(?,?,?,?,?)", (project, session, "config_changed", json.dumps({"field": key, "before": old.get(key), "after": value}, ensure_ascii=False), stamp))
    return stamp


def create_run(project, session, user_input, config):
    run_id = str(uuid4())
    with connection() as db:
        db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)", (run_id, project, session, user_input, json.dumps(config, ensure_ascii=False), "running", now(), None))
    action(project, session, "run_clicked", {"run_id": run_id, "config": config})
    return run_id


def event(run_id, project, session, kind, data):
    item = {"type": kind, "data": data, "timestamp": now(), "run_id": run_id}
    with connection() as db:
        cursor = db.execute("INSERT INTO events(run_id,project,session,type,data,timestamp) VALUES(?,?,?,?,?,?)", (run_id, project, session, kind, json.dumps(data, ensure_ascii=False, default=str), item["timestamp"]))
        item["id"] = cursor.lastrowid
    return item


def finish(run_id, status):
    with connection() as db:
        db.execute("UPDATE runs SET status=?,finished=? WHERE id=?", (status, now(), run_id))


def history(project, session):
    with connection() as db:
        rows = db.execute("SELECT id,input,status,created,finished FROM runs WHERE project=? AND session=? ORDER BY created DESC LIMIT 50", (project, session)).fetchall()
    return [dict(r) for r in rows]


def detail(project, session, run_id):
    with connection() as db:
        row = db.execute("SELECT * FROM runs WHERE id=? AND project=? AND session=?", (run_id, project, session)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["config"] = json.loads(result["config"])
        result["events"] = [{**dict(e), "data": json.loads(e["data"])} for e in db.execute("SELECT * FROM events WHERE run_id=? ORDER BY id", (run_id,))]
    return result


def activities(project, session):
    with connection() as db:
        rows = db.execute("SELECT action,data,timestamp FROM actions WHERE project=? AND session=? ORDER BY id", (project, session)).fetchall()
    return [{**dict(row), "data": json.loads(row["data"])} for row in rows]
