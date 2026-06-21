#!/usr/bin/env bash
# MediBot launch script
# Usage:
#   ./launch.sh            # start API + frontend
#   ./launch.sh --ingest   # ingest all collections first, then start
#   ./launch.sh --stop     # kill API and frontend processes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_PORT=8000
FRONTEND_PORT=3000
LOG_DIR="$SCRIPT_DIR/.logs"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[medibot]${NC} $*"; }
success() { echo -e "${GREEN}[medibot]${NC} $*"; }
warn()    { echo -e "${YELLOW}[medibot]${NC} $*"; }
error()   { echo -e "${RED}[medibot]${NC} $*" >&2; }

# ── Stop mode ─────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--stop" ]]; then
    info "Stopping MediBot..."
    kill "$(lsof -ti :$API_PORT)"      2>/dev/null && success "API stopped"      || warn "API was not running"
    kill "$(lsof -ti :$FRONTEND_PORT)" 2>/dev/null && success "Frontend stopped" || warn "Frontend was not running"
    exit 0
fi

# ── Preflight checks ──────────────────────────────────────────────────────────
info "Running preflight checks..."

if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
    error ".env not found — copy .env.example and fill in your API keys"
    exit 1
fi

if ! command -v uv &>/dev/null; then
    error "uv not found — install with: curl -Lsf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

if ! command -v npm &>/dev/null; then
    error "npm not found — install Node.js from https://nodejs.org"
    exit 1
fi

# Read QDRANT_URL from .env (strip quotes)
QDRANT_URL=$(grep -E '^QDRANT_URL=' "$SCRIPT_DIR/.env" | head -1 | cut -d= -f2- | tr -d '"'"'" | xargs)
QDRANT_API_KEY=$(grep -E '^QDRANT_API_KEY=' "$SCRIPT_DIR/.env" | head -1 | cut -d= -f2- | tr -d '"'"'" | xargs || echo "")

# ── Qdrant connectivity check ─────────────────────────────────────────────────
info "Checking Qdrant connection at $QDRANT_URL ..."
if [[ -n "$QDRANT_API_KEY" ]]; then
    HTTP_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" \
        -H "api-key: $QDRANT_API_KEY" \
        "$QDRANT_URL/collections" 2>/dev/null || echo "000")
else
    HTTP_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" \
        "$QDRANT_URL/collections" 2>/dev/null || echo "000")
fi

if [[ "$HTTP_STATUS" == "200" ]]; then
    success "Qdrant is reachable"
else
    error "Cannot reach Qdrant at $QDRANT_URL (HTTP $HTTP_STATUS)"
    error "Check QDRANT_URL and QDRANT_API_KEY in .env"
    exit 1
fi

# frontend .env.local
if [[ ! -f "$SCRIPT_DIR/frontend/.env.local" ]]; then
    warn "frontend/.env.local missing — creating with default"
    echo "NEXT_PUBLIC_API_URL=http://localhost:$API_PORT" > "$SCRIPT_DIR/frontend/.env.local"
fi

# frontend node_modules
if [[ ! -d "$SCRIPT_DIR/frontend/node_modules" ]]; then
    info "Installing frontend dependencies..."
    npm install --prefix "$SCRIPT_DIR/frontend" --silent
fi

success "Preflight checks passed"

mkdir -p "$LOG_DIR"

# ── Optional ingestion ────────────────────────────────────────────────────────
if [[ "${1:-}" == "--ingest" ]]; then
    info "Ingesting all collections (this may take several minutes)..."
    uv run python -m ingestion --collections general clinical nursing billing equipment \
        2>&1 | tee "$LOG_DIR/ingestion.log"
    success "Ingestion complete"
fi

# ── FastAPI backend ───────────────────────────────────────────────────────────
if lsof -ti :"$API_PORT" &>/dev/null; then
    warn "Port $API_PORT busy — killing existing process"
    kill "$(lsof -ti :"$API_PORT")" 2>/dev/null || true
    sleep 1
fi

info "Starting API on http://localhost:$API_PORT ..."
uv run uvicorn api.main:app \
    --host 0.0.0.0 \
    --port "$API_PORT" \
    --reload \
    > "$LOG_DIR/api.log" 2>&1 &
API_PID=$!

for i in $(seq 1 20); do
    if curl -sf "http://localhost:$API_PORT/health" > /dev/null 2>&1; then
        success "API ready (PID $API_PID)"
        break
    fi
    [[ $i -eq 20 ]] && { error "API didn't start — check $LOG_DIR/api.log"; kill "$API_PID" 2>/dev/null; exit 1; }
    sleep 1
done

# ── Next.js frontend ──────────────────────────────────────────────────────────
if lsof -ti :"$FRONTEND_PORT" &>/dev/null; then
    warn "Port $FRONTEND_PORT busy — killing existing process"
    kill "$(lsof -ti :"$FRONTEND_PORT")" 2>/dev/null || true
    sleep 1
fi

info "Starting frontend on http://localhost:$FRONTEND_PORT ..."
npm run dev --prefix "$SCRIPT_DIR/frontend" \
    > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

for i in $(seq 1 30); do
    if curl -sf "http://localhost:$FRONTEND_PORT" > /dev/null 2>&1; then
        success "Frontend ready (PID $FRONTEND_PID)"
        break
    fi
    [[ $i -eq 30 ]] && { warn "Frontend not responding yet — check $LOG_DIR/frontend.log"; break; }
    sleep 1
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  MediBot is running!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Frontend :  http://localhost:$FRONTEND_PORT"
echo -e "  API      :  http://localhost:$API_PORT"
echo -e "  API docs :  http://localhost:$API_PORT/docs"
echo -e "  Qdrant   :  $QDRANT_URL/dashboard"
echo ""
echo -e "  Demo credentials:"
echo -e "    dr.mehta      / doctor123   (doctor)"
echo -e "    nurse.priya   / nurse123    (nurse)"
echo -e "    billing.ravi  / billing123  (billing_executive)"
echo -e "    tech.anand    / tech123     (technician)"
echo -e "    admin.sys     / admin123    (admin)"
echo ""
echo -e "  Logs : $LOG_DIR/"
echo -e "  Stop : ${CYAN}./launch.sh --stop${NC}   or   Ctrl+C"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

trap 'echo ""; info "Shutting down..."; kill "$API_PID" "$FRONTEND_PID" 2>/dev/null; exit 0' INT TERM
wait "$API_PID" "$FRONTEND_PID"
