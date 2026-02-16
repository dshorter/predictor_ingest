#!/usr/bin/env bash
# Deploy script — called by GitHub Actions after push to main
# Pulls latest code and restarts the predictor container if running
set -euo pipefail

REPO_DIR="/opt/predictor_ingest"
LOG_TAG="predictor-deploy"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    logger -t "$LOG_TAG" "$*"
}

cd "$REPO_DIR"

log "Pulling latest from origin/main..."
git fetch origin main
git reset --hard origin/main

log "Pull complete: $(git log --oneline -1)"

# Ensure the live graphs directory exists (gitignored, created by pipeline)
mkdir -p "$REPO_DIR/web/data/graphs/live"

# If running inside docker compose (alongside ai-agent-platform),
# rebuild and restart the predictor container
COMPOSE_DIR="/opt/ai-agent-platform"
if [ -f "$COMPOSE_DIR/docker-compose.yml" ] && \
   grep -q "predictor" "$COMPOSE_DIR/docker-compose.yml" 2>/dev/null; then

    log "Rebuilding predictor container..."
    cd "$COMPOSE_DIR"
    docker compose build predictor
    docker compose up -d predictor
    log "Predictor container restarted"

# Otherwise, just install deps directly on the host
else
    log "No docker compose with predictor service found, running directly"
    cd "$REPO_DIR"
    pip install -e . --quiet
    log "Dependencies updated"
fi

log "Deploy complete"
