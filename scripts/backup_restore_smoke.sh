#!/usr/bin/env bash
set -euo pipefail

# AgentShield PostgreSQL recovery smoke test.
# SOURCE_DATABASE_URL defaults to DATABASE_URL.
# RESTORE_DATABASE_URL must point to an isolated restore target.
# Set ALLOW_DESTRUCTIVE_RESTORE=1 to execute the restore; otherwise the
# command performs a non-destructive backup/catalog verification only.

SOURCE_DATABASE_URL="${SOURCE_DATABASE_URL:-${DATABASE_URL:-}}"
RESTORE_DATABASE_URL="${RESTORE_DATABASE_URL:-}"
BACKUP_DIR="${BACKUP_DIR:-.tmp/backups}"

if [[ -z "$SOURCE_DATABASE_URL" || -z "$RESTORE_DATABASE_URL" ]]; then
  echo "SOURCE_DATABASE_URL and RESTORE_DATABASE_URL are required" >&2
  exit 2
fi

normalize_pg_url() {
  local value="$1"
  value="${value/postgresql+psycopg:\/\//postgresql:\/\/}"
  value="${value/postgres+psycopg:\/\//postgresql:\/\/}"
  printf '%s' "$value"
}

SOURCE_PG_URL="$(normalize_pg_url "$SOURCE_DATABASE_URL")"
RESTORE_PG_URL="$(normalize_pg_url "$RESTORE_DATABASE_URL")"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/agentshield-$(date -u +%Y%m%dT%H%M%SZ).dump"
trap 'rm -f "$BACKUP_FILE"' EXIT

echo "[1/4] Dump source database"
pg_dump --format=custom --no-owner --no-privileges --file="$BACKUP_FILE" "$SOURCE_PG_URL"
test -s "$BACKUP_FILE"

echo "[2/4] Validate backup catalog"
pg_restore --list "$BACKUP_FILE" >/dev/null

if [[ "${ALLOW_DESTRUCTIVE_RESTORE:-0}" != "1" ]]; then
  echo "[3/4] Restore skipped; set ALLOW_DESTRUCTIVE_RESTORE=1 for isolated restore verification"
  echo "[4/4] Backup verification passed"
  exit 0
fi

echo "[3/4] Restore into isolated target"
pg_restore --clean --if-exists --exit-on-error --no-owner --no-privileges \
  --dbname="$RESTORE_PG_URL" "$BACKUP_FILE"

echo "[4/4] Validate restored AgentShield schema"
python - "$RESTORE_DATABASE_URL" <<'PY'
import asyncio
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = sys.argv[1]
expected = {
    "agents", "agent_policies", "transactions", "transaction_features",
    "risk_predictions", "risk_decisions", "audit_events", "model_versions",
    "payment_orders", "provider_payments", "webhook_events",
}

async def main() -> None:
    engine = create_async_engine(url, pool_pre_ping=True)
    async with engine.connect() as connection:
        result = await connection.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        tables = {row[0] for row in result}
        missing = sorted(expected - tables)
        if missing:
            raise SystemExit(f"restored database missing tables: {missing}")
        await connection.execute(text("SELECT 1"))
    await engine.dispose()

asyncio.run(main())
PY
