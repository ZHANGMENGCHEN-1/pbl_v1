#!/usr/bin/env bash
# Run as ecs-user: bash deploy/release.sh [--rollback /absolute/backup/directory]
set -Eeuo pipefail
umask 077

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"
SERVICE=pbl-backend
WEB_ROOT=/var/www/pbl
RELEASES=/var/www/pbl-releases
BACKUPS="${PBL_BACKUP_DIR:-$HOME/pbl-backups}"
PYTHON="$ROOT/.venv/bin/python"
HEALTH=http://127.0.0.1:8000/api/health
STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$$"
MODE=deploy
ROLLBACK_DIR=''
BACKUP_DIR=''

fail() { printf '\nERROR: %s\n' "$*" >&2; on_error; exit 1; }
on_error() {
    printf '\nRelease stopped. Do not assume the update succeeded.\n' >&2
    if [[ -n "$BACKUP_DIR" ]]; then
        printf 'Pre-update backup: %s\nRollback: bash deploy/release.sh --rollback "%s"\n' "$BACKUP_DIR" "$BACKUP_DIR" >&2
    fi
}
trap on_error ERR

main() {
if [[ $# -gt 0 ]]; then
    [[ $# -eq 2 && "$1" == --rollback ]] || fail 'Usage: bash deploy/release.sh [--rollback /absolute/backup/directory]'
    MODE=rollback
    ROLLBACK_DIR="$2"
fi
[[ "$EUID" -ne 0 ]] || fail 'Run as ecs-user, not with sudo; the script requests sudo only where needed.'
[[ -x "$PYTHON" ]] || fail 'Missing .venv/bin/python. Create the virtual environment first.'
[[ -f backend/.env ]] || fail 'Missing backend/.env. Configure server credentials first.'
for command in git npm curl sudo flock; do command -v "$command" >/dev/null || fail "Missing command: $command"; done

# Prevent two deployments from updating the same checkout simultaneously.
LOCK_FILE="$(git rev-parse --git-path pbl-release.lock)"
exec 9>"$LOCK_FILE"
flock -n 9 || fail 'Another deployment is running.'
[[ -z "$(git status --porcelain)" ]] || fail 'Uncommitted server changes detected. Review git status and the deployment guide; nothing was overwritten.'
sudo -v
[[ "$(sudo systemctl show "$SERVICE" -p WorkingDirectory --value)" == "$ROOT/backend" ]] || fail 'Service WorkingDirectory differs from this checkout. Check the systemd configuration.'

OLD_COMMIT="$(git rev-parse HEAD)"
if [[ "$MODE" == deploy ]]; then
    [[ "$(git branch --show-current)" == main ]] || fail 'Deployment requires branch main. After a rollback, run git switch main first.'
    git fetch origin main
    git merge-base --is-ancestor HEAD origin/main || fail 'Local and remote history diverged. No automatic merge or reset was attempted.'
else
    [[ "$ROLLBACK_DIR" == /* ]] || fail 'Use an absolute backup path.'
    TARGET_COMMIT="$("$PYTHON" - "$ROOT" "$ROLLBACK_DIR" <<'PY'
import json, sys
from pathlib import Path
root, backup = map(Path, sys.argv[1:])
data = json.loads((backup / 'manifest.json').read_text())
if Path(data['root']).resolve() != root.resolve():
    raise SystemExit('Backup belongs to a different checkout.')
if not data.get('frontend_backed_up') or not (backup / 'frontend/index.html').is_file():
    raise SystemExit('Backup has no frontend snapshot; manual recovery is required.')
print(data['commit'])
PY
)"
    git cat-file -e "$TARGET_COMMIT^{commit}"
fi

mkdir -p "$BACKUPS"
chmod 700 "$BACKUPS"
BACKUPS="$(cd "$BACKUPS" && pwd -P)"
case "$BACKUPS/" in "$ROOT/"*) fail 'Keep backups outside the Git checkout.';; esac
BACKUP_DIR="$BACKUPS/$STAMP-${OLD_COMMIT:0:8}"
"$PYTHON" deploy/backup.py "$ROOT" "$BACKUP_DIR" "$OLD_COMMIT" "$WEB_ROOT"
printf 'Pre-update backup: %s\n' "$BACKUP_DIR"

if [[ "$MODE" == deploy ]]; then
    git merge --ff-only origin/main
    (
        cd frontend
        npm ci
        npm run build
    )
    FRONTEND="$ROOT/frontend/dist"
else
    # Detach instead of resetting or rewriting main's history.
    git switch --detach "$TARGET_COMMIT"
    FRONTEND="$ROLLBACK_DIR/frontend"
fi
[[ -f "$FRONTEND/index.html" ]] || fail 'Frontend build/snapshot is missing index.html.'

# Prefer the committed, tested dependency versions when a lock file exists.
REQUIREMENTS=backend/requirements.txt
[[ ! -f backend/requirements-lock.txt ]] || REQUIREMENTS=backend/requirements-lock.txt
"$PYTHON" -m pip install -r "$REQUIREMENTS"

NEW_COMMIT="$(git rev-parse --short HEAD)"
RELEASE="$RELEASES/$STAMP-$NEW_COMMIT"
sudo install -d -m 755 "$RELEASES" "$RELEASE"
sudo cp -R "$FRONTEND/." "$RELEASE/"
sudo chmod -R a+rX "$RELEASE"

# Health-check the backend before replacing the public frontend.
sudo systemctl restart "$SERVICE"
healthy=false
for attempt in {1..30}; do
    if curl --fail --silent --max-time 3 "$HEALTH" >/dev/null; then healthy=true; break; fi
    sleep 1
done
[[ "$healthy" == true ]] || fail 'Backend health check failed. Check journalctl -u pbl-backend; frontend was not switched.'

# Preserve the original directory when adopting symlink-based releases.
if [[ -d "$WEB_ROOT" && ! -L "$WEB_ROOT" ]]; then
    sudo mv -T "$WEB_ROOT" "$RELEASES/legacy-$STAMP"
elif [[ -e "$WEB_ROOT" && ! -L "$WEB_ROOT" ]]; then
    fail '/var/www/pbl exists but is not a directory or symlink.'
fi
NEXT_LINK="/var/www/.pbl-next-$STAMP"
sudo ln -s "$RELEASE" "$NEXT_LINK"
sudo mv -Tf "$NEXT_LINK" "$WEB_ROOT"
curl --fail --silent --max-time 10 -H 'Host: 8.136.241.217' http://127.0.0.1/ >/dev/null
curl --fail --silent --max-time 10 -H 'Host: 8.136.241.217' http://127.0.0.1/api/health >/dev/null
printf '\nRelease completed: %s (%s)\nBackup: %s\n' "$NEW_COMMIT" "$MODE" "$BACKUP_DIR"
if [[ "$MODE" == rollback ]]; then
    printf 'Database and .env were NOT restored. Before your next update, run: git switch main\n'
fi
}

# Parse the whole release function before pulling updates to this script itself.
main "$@"
