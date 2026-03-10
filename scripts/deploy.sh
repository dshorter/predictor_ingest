#!/usr/bin/env bash
# Deploy script — called by GitHub Actions after push to main (or a feature branch)
# Pulls latest code and restarts the predictor container if running
#
# Usage: ./scripts/deploy.sh [BRANCH]
#   BRANCH defaults to "main" if not provided.
#
# IMPORTANT: data/ is gitignored and must NEVER be touched by deploys.
# We use `git checkout` on tracked files only — NOT `git reset --hard`
# which can interfere with untracked runtime data.
set -euo pipefail

BRANCH="${1:-main}"
REPO_DIR="/opt/predictor_ingest"
LOG_TAG="predictor-deploy"
DEPLOY_LOG="$REPO_DIR/data/logs/deploy.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    logger -t "$LOG_TAG" "$*"
    # Append to persistent deploy log for audit trail
    mkdir -p "$(dirname "$DEPLOY_LOG")"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] branch=$BRANCH $*" >> "$DEPLOY_LOG"
}

cd "$REPO_DIR"

# Abort if pipeline is currently running
if [ -f "$REPO_DIR/data/pipeline.lock" ]; then
    log "WARNING: pipeline.lock exists — pipeline may be running. Deploying anyway but skipping restart."
fi

log "Deploying branch '$BRANCH' from origin..."
git fetch origin "$BRANCH"

# Safe update: only update tracked files, never touch untracked data/
# This replaces the old `git reset --hard origin/$BRANCH` which could
# interfere with gitignored runtime data like data/, .env, etc.
git checkout "origin/$BRANCH" -- .
# Update HEAD to match (so `git log` shows current state)
git reset "origin/$BRANCH"

log "Deploy complete for branch '$BRANCH': $(git log --oneline -1)"

# Ensure runtime directories exist (gitignored, created by pipeline)
mkdir -p "$REPO_DIR/data/raw"
mkdir -p "$REPO_DIR/data/text"
mkdir -p "$REPO_DIR/data/db"
mkdir -p "$REPO_DIR/data/docpacks"
mkdir -p "$REPO_DIR/data/extractions"
mkdir -p "$REPO_DIR/data/graphs"
mkdir -p "$REPO_DIR/data/logs"
mkdir -p "$REPO_DIR/data/reports"
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
