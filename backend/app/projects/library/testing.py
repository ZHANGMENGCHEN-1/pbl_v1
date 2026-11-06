"""Explicit, opt-in reset for local classroom-workspace testing."""
import os
from fastapi import HTTPException
from ...shared import store
from .project import PROJECT_ID


def reset_on_refresh():
    return os.getenv("LIBRARY_RESET_ON_REFRESH", "false").strip().lower() in {"true", "1", "yes"}


def reset_progress(session):
    if not reset_on_refresh():
        raise HTTPException(403, "自动重置仅在测试开关开启时可用")
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        counts={}
        for table in ("library_submissions","library_drafts","library_plans","library_plan_details","library_plan_versions","library_configs","library_predictions","library_analyses","library_runs","library_dataset_views"):
            condition="session=?"+(" AND project=?" if table=="library_plan_versions" else "")
            args=(session,PROJECT_ID) if table=="library_plan_versions" else (session,)
            counts[table]=db.execute(f"SELECT COUNT(*) FROM {table} WHERE {condition}",args).fetchone()[0]
            db.execute(f"DELETE FROM {table} WHERE {condition}",args)
        for table in ("events","runs","actions","configs"):
            db.execute(f"DELETE FROM {table} WHERE project=? AND session=?",(PROJECT_ID,session))
    store.action(PROJECT_ID,session,"testing_progress_reset",counts)
    return {"reset":True}
