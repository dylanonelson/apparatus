#!/usr/bin/env bash
# Start all Apparatus services inside the development container.
# Run this after entering the container via run-claude-container.sh.
#
# Prerequisites:
#   PostgreSQL must be running on the host (port 5432).
#   The container connects to it via host.docker.internal.
#
# Services started:
#   Readium CLI — EPUB content server on port 15080
#   Pub API     — Go service on port 8091
#   Reader API  — FastAPI service on port 8000
#   Frontend    — Next.js dev server on port 3000
#
# Logs are written to /tmp/apparatus-logs/<service>.log

set -euo pipefail

LOG_DIR="/tmp/apparatus-logs"
mkdir -p "$LOG_DIR"

DB_HOST="host.docker.internal"

# ── Helper ───────────────────────────────────────────────────────────
log() { echo "[start-services] $*"; }

# ── 1. Wait for host PostgreSQL ──────────────────────────────────────
log "Waiting for PostgreSQL on $DB_HOST:5432..."
retries=30
while ! pg_isready -h "$DB_HOST" -p 5432 -q 2>/dev/null; do
    retries=$((retries - 1))
    if [[ $retries -le 0 ]]; then
        log "ERROR: PostgreSQL on $DB_HOST:5432 is not reachable."
        log "Make sure PostgreSQL is running on the host before starting the container."
        exit 1
    fi
    sleep 0.5
done
log "PostgreSQL ready on $DB_HOST:5432"

# ── 2. Set default environment variables ─────────────────────────────
# These can be overridden by .env files in each service directory or by
# passing --env-file to run-claude-container.sh.
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@${DB_HOST}:5432/apparatus}"
export READER_API_PUBLIC_URL="${READER_API_PUBLIC_URL:-http://localhost:8000}"
export CONTENT_SERVICE_URL="${CONTENT_SERVICE_URL:-http://localhost:8091}"
export READIUM_SERVICE_URL="${READIUM_SERVICE_URL:-http://localhost:15080}"

# ── 3. Install dependencies (in parallel) ───────────────────────────
log "Installing dependencies..."

(cd /app/frontend && pnpm install --frozen-lockfile 2>&1 | tail -1) &
PID_PNPM=$!

(cd /app/reader_api && uv sync 2>&1 | tail -1) &
PID_UV=$!

(cd /app/publication_api && go mod download 2>&1 | tail -1) &
PID_GO=$!

wait $PID_PNPM && log "  frontend deps installed" || log "  WARNING: frontend deps failed"
wait $PID_UV   && log "  reader_api deps installed" || log "  WARNING: reader_api deps failed"
wait $PID_GO   && log "  publication_api deps installed" || log "  WARNING: publication_api deps failed"

# ── 4. Database migrations ───────────────────────────────────────────
log "Running database migrations..."
(cd /app/reader_api && uv run alembic upgrade head 2>&1) | tail -3
log "Migrations complete"

# ── 5. Start Readium CLI ────────────────────────────────────────────
log "Starting Readium CLI on :15080..."
readium serve \
    --file-directory /app/ebook_files \
    --address 0.0.0.0 \
    --port 15080 \
    >"$LOG_DIR/readium.log" 2>&1 &

# ── 6. Start Publication API ────────────────────────────────────────
log "Starting Publication API on :8091..."
(cd /app/publication_api && \
    PUBLICATION_SERVER_PORT=8091 \
    PUBLICATIONS_DIR=publications \
    go run ./cmd/server \
    >"$LOG_DIR/publication_api.log" 2>&1) &

# ── 7. Start Reader API ────────────────────────────────────────────
log "Starting Reader API on :8000..."
(cd /app/reader_api && \
    uv run uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
    >"$LOG_DIR/reader_api.log" 2>&1) &

# ── 8. Start Frontend ──────────────────────────────────────────────
log "Starting Frontend on :3000..."
(cd /app/frontend && \
    pnpm run dev -- --hostname 0.0.0.0 \
    >"$LOG_DIR/frontend.log" 2>&1) &

# Give services a moment to start
sleep 2

echo ""
echo "=== Apparatus services started ==="
echo ""
echo "  Frontend:        http://localhost:3000"
echo "  Reader API:      http://localhost:8000"
echo "  Publication API: http://localhost:8091"
echo "  Readium CLI:     http://localhost:15080"
echo "  Database:        postgresql://${DB_HOST}:5432/apparatus"
echo ""
echo "  Logs:            $LOG_DIR/<service>.log"
echo "  Stop all:        pkill -f 'readium|uvicorn|go run|next dev' 2>/dev/null"
echo ""
