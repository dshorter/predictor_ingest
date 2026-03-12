#!/usr/bin/env bash
# Deploy script — called by GitHub Actions after push to main (or a feature branch)
# Pulls latest code and updates dependencies directly on the host.
#
# Usage: ./scripts/deploy.sh [BRANCH]
#   BRANCH defaults to "main" if not provided.

set -euo pipefail

BRANCH="${1:-main}"
REPO_DIR="/opt/predictor_ingest"
LOG_TAG="predictor-deploy"
DEPLOY_LOG="$REPO_DIR/data/logs/deploy.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    logger -t "$LOG_TAG" "$*"
    mkdir -p "$(dirname "$DEPLOY_LOG")"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] branch=$BRANCH $*" >> "$DEPLOY_LOG"
}

cd "$REPO_DIR"

if [ -f "$REPO_DIR/data/pipeline.lock" ]; then
    log "WARNING: pipeline.lock exists — pipeline may be running. Deploying anyway."
fi

log "Deploying branch '$BRANCH' from origin..."
git fetch origin "$BRANCH"

git checkout "origin/$BRANCH" -- .
git reset "origin/$BRANCH"

log "Deploy complete for branch '$BRANCH': $(git log --oneline -1)"

# Ensure runtime directories exist
mkdir -p "$REPO_DIR/data/raw"
mkdir -p "$REPO_DIR/data/text"
mkdir -p "$REPO_DIR/data/db"
mkdir -p "$REPO_DIR/data/docpacks"
mkdir -p "$REPO_DIR/data/extractions"
mkdir -p "$REPO_DIR/data/graphs"
mkdir -p "$REPO_DIR/data/logs"
mkdir -p "$REPO_DIR/data/reports"
mkdir -p "$REPO_DIR/web/data/graphs/live"

# ==========================================
# NO MORE DOCKER! RUNNING STRICTLY ON METAL
# ==========================================

log "Updating dependencies on the host..."
cd "$REPO_DIR"

# If you use a virtual environment, you would activate it here.
# e.g., source venv/bin/activate 

# ==========================================
# NO MORE DOCKER! RUNNING STRICTLY ON METAL
# ==========================================

log "Updating dependencies on the host..."
cd "$REPO_DIR"

# Check if the virtual environment exists. If not, create it.
if [ ! -d "venv" ]; then
    log "Creating new Python virtual environment..."
    # Make sure python3-venv is installed on the server (apt install python3-venv)
    python3 -m venv venv
fi

# Activate the virtual environment
source venv/bin/activate

# Install dependencies inside the isolated environment
pip install -e . --quiet

log "Dependencies updated. Deploy complete."
