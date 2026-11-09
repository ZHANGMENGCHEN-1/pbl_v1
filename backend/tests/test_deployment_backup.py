"""Deployment backups must preserve live WAL data and keep secrets off stdout."""
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

spec = importlib.util.spec_from_file_location("deployment_backup", Path(__file__).resolve().parents[2] / "deploy/backup.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_backup_includes_live_wal_data_and_env(tmp_path, capsys):
    root = tmp_path / "app"
    backend = root / "backend"
    backend.mkdir(parents=True)
    (backend / ".env").write_text("DATABASE_PATH=data/classroom.db\nLLM_API_KEY=secret-for-test\n")
    (backend / "data").mkdir()
    database = backend / "data/classroom.db"
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("previous release")
    with sqlite3.connect(database) as live:
        live.execute("PRAGMA journal_mode=WAL")
        live.execute("PRAGMA wal_autocheckpoint=0")
        live.execute("CREATE TABLE records(value TEXT)")
        live.execute("INSERT INTO records VALUES('committed student work')")
        live.commit()
        assert Path(str(database) + "-wal").is_file()
        backup = tmp_path / "backup"
        manifest = module.backup(root, backup, "abc123", web)
        with sqlite3.connect(backup / "workspace.db") as saved:
            assert saved.execute("SELECT value FROM records").fetchone()[0] == "committed student work"
    assert "secret-for-test" in (backup / "backend.env").read_text()
    assert (backup / "frontend/index.html").read_text() == "previous release"
    assert manifest["commit"] == "abc123"
    assert "secret-for-test" not in capsys.readouterr().out
    assert "secret-for-test" not in (backup / "manifest.json").read_text()


def test_missing_database_is_not_created(tmp_path):
    root = tmp_path / "app"
    (root / "backend").mkdir(parents=True)
    (root / "backend/.env").write_text("DATABASE_PATH=data/missing.db\n")
    backup = tmp_path / "backup"
    module.backup(root, backup, "old", tmp_path / "missing-web")
    manifest = json.loads((backup / "manifest.json").read_text())
    assert not manifest["database_backed_up"]
    assert not manifest["frontend_backed_up"]
    assert not (root / "backend/data/missing.db").exists()


def test_backup_uses_absolute_configured_database_and_refuses_overwrite(tmp_path):
    root = tmp_path / "app"
    (root / "backend").mkdir(parents=True)
    database = tmp_path / "external.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE records(id INTEGER)")
    (root / "backend/.env").write_text(f"DATABASE_PATH={database.as_posix()}\n")
    backup = tmp_path / "backup"
    module.backup(root, backup, "old", tmp_path / "missing-web")
    assert (backup / "workspace.db").is_file()
    with pytest.raises(FileExistsError):
        module.backup(root, backup, "new", tmp_path / "missing-web")
