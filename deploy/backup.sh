#!/usr/bin/env bash
# dCern backup — code bundle (always) + Postgres dump (when DATABASE_URL is set).
#
#   ./deploy/backup.sh [dest_dir]
#   DATABASE_URL="postgres://user:pass@host/db" ./deploy/backup.sh
#
# Restore code:  git clone dcern-code-<stamp>.bundle dcern
# Restore db:    pg_restore -d "$TARGET_URL" dcern-db-<stamp>.dump
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$HOME/dcern-backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DEST"

# 1. Code — full git bundle (all branches + history; restorable with `git clone`)
git -C "$REPO" bundle create "$DEST/dcern-code-$STAMP.bundle" --all
echo "code -> $DEST/dcern-code-$STAMP.bundle"

# 2. Database — pg_dump if a connection URL is provided (custom format = compressed)
if [ -n "${DATABASE_URL:-}" ]; then
  if command -v pg_dump >/dev/null 2>&1; then
    pg_dump "$DATABASE_URL" -Fc -f "$DEST/dcern-db-$STAMP.dump"
    echo "db   -> $DEST/dcern-db-$STAMP.dump"
  else
    echo "db   -> SKIPPED (pg_dump not installed — 'brew install libpq' then re-run)"
  fi
else
  echo "db   -> SKIPPED (set DATABASE_URL to also dump Postgres)"
fi

# 3. Retention — keep the 14 most recent of each kind (|| true: empty glob is fine)
ls -1t "$DEST"/dcern-code-*.bundle 2>/dev/null | tail -n +15 | xargs -r rm -f || true
ls -1t "$DEST"/dcern-db-*.dump     2>/dev/null | tail -n +15 | xargs -r rm -f || true

echo "done — backups in $DEST"
