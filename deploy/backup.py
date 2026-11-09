"""Back up a running SQLite database safely, without printing environment secrets."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
from datetime import datetime, timezone

from dotenv import dotenv_values


def backup(root, destination, commit, web_root):
    root = Path(root).resolve()
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.chmod(destination, 0o700)
    env_file = root / "backend/.env"
    values = dotenv_values(env_file)
    configured = values.get("DATABASE_PATH") or os.environ.get("DATABASE_PATH") or "data/workspace.db"
    database = Path(configured)
    if not database.is_absolute():
        database = root / "backend" / database
    database = database.resolve()
    manifest = {
        "root": str(root), "commit": commit,
        "created": datetime.now(timezone.utc).isoformat(),
        "database_path": str(database), "database_backed_up": database.is_file(),
        "env_backed_up": env_file.is_file(),
        "frontend_backed_up": Path(web_root).is_dir(),
    }
    if env_file.is_file():
        shutil.copyfile(env_file, destination / "backend.env")
        os.chmod(destination / "backend.env", 0o600)
    if database.is_file():
        # Copying only a live .db file can miss committed data in its WAL.
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=30) as source:
            with sqlite3.connect(destination / "workspace.db") as target:
                source.backup(target)
        os.chmod(destination / "workspace.db", 0o600)
    if Path(web_root).is_dir():
        shutil.copytree(web_root, destination / "frontend")
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    os.chmod(destination / "manifest.json", 0o600)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("destination")
    parser.add_argument("commit")
    parser.add_argument("web_root")
    args = parser.parse_args()
    backup(args.root, args.destination, args.commit, args.web_root)
    print("Backup completed; environment contents were not printed.")
