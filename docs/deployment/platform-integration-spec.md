# Predictor Ingest — Deployment Spec for ai-agent-platform

This document is a complete spec for a session connected to the
`dshorter/ai-agent-platform` repo. It describes how to add the predictor
pipeline as a container service alongside the existing n8n/postgres/nginx
stack.

---

## Overview

The predictor pipeline needs:
- A Python 3.11 container that runs daily RSS ingestion, extraction, and
  graph export
- SQLite database persisted on a named volume
- Graph JSON output served by the existing nginx container
- Safe-reboot awareness (wait for pipeline, backup SQLite before shutdown)
- Cron-based daily schedule inside the container

The predictor does NOT need:
- PostgreSQL (it uses SQLite)
- Network ingress (it fetches RSS outbound; the web client is served by nginx)
- n8n integration (yet — that's a future option)

---

## 1. Dockerfile

Create `predictor/Dockerfile` in the `ai-agent-platform` repo:

```dockerfile
FROM python:3.11-slim

# System deps for lxml/beautifulsoup and sqlite
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    sqlite3 \
    cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone or copy the predictor repo
# Option A: mount as volume (recommended for dev)
# Option B: copy at build time (recommended for prod)
COPY . /app/

RUN pip install --no-cache-dir -e .

# Create data directories
RUN mkdir -p data/db data/raw data/text data/docpacks \
    data/extractions data/graphs

# Initialize database
RUN python scripts/init_db.py --db data/db/predictor.db

# Cron job: daily pipeline at 6:00 AM ET
RUN echo "0 6 * * * cd /app && make ingest >> /var/log/predictor-pipeline.log 2>&1" \
    > /etc/cron.d/predictor-pipeline \
    && chmod 0644 /etc/cron.d/predictor-pipeline \
    && crontab /etc/cron.d/predictor-pipeline

# Lock file location for safe-reboot awareness
ENV PIPELINE_LOCK=/app/data/pipeline.lock

# Healthcheck: verify DB exists and cron is running
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD test -f /app/data/db/predictor.db && pgrep cron > /dev/null

# Keep cron in foreground
CMD ["cron", "-f"]
```

**Notes for implementing session:**
- If mounting the predictor_ingest repo as a volume (dev mode), remove
  the `COPY . /app/` line and the `RUN pip install` / `RUN mkdir` / `RUN python`
  lines — those happen via an entrypoint script instead.
- For prod, copy the repo contents at build time.

---

## 2. Docker Compose Addition

Add this service to the existing `docker-compose.yml`:

```yaml
  predictor:
    build:
      context: ../predictor_ingest    # adjust path to where the repo lives
      dockerfile: Dockerfile
    container_name: predictor-pipeline
    restart: unless-stopped
    volumes:
      # Persist SQLite and all pipeline data across container recreation
      - predictor-data:/app/data
      # Share graph output with nginx for serving the web client
      - ./public/graphs:/app/data/graphs
      # Share web client files with nginx
      - ../predictor_ingest/web:/app/web:ro
    environment:
      - TZ=America/New_York
      # For Mode A (automated LLM extraction) — uncomment when ready:
      # - OPENAI_API_KEY=${OPENAI_API_KEY}
      # - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "test", "-f", "/app/data/db/predictor.db"]
      interval: 30s
      timeout: 5s
      retries: 3
```

Add to the `volumes:` section at the bottom of compose:

```yaml
  predictor-data:
    driver: local
```

Add to the nginx service volumes (so it can serve the web client and graph data):

```yaml
  web:
    image: nginx:alpine
    container_name: web-server
    ports:
      - "127.0.0.1:8080:80"
    volumes:
      - ./public:/usr/share/nginx/html
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      # Add these two lines:
      - ../predictor_ingest/web:/usr/share/nginx/html/predictor:ro
      - ./public/graphs:/usr/share/nginx/html/predictor/data/graphs:ro
```

After this, the web client is at `http://localhost:8080/predictor/` and
loads graph JSON from `http://localhost:8080/predictor/data/graphs/`.

---

## 3. Pipeline Lock File for Safe Reboot

The pipeline writes a lock file at start and removes it on completion.
This needs to be added to the predictor Makefile (in the predictor_ingest
repo, not the platform repo):

### Makefile changes (predictor_ingest repo)

Replace the `pipeline` and `post-extract` composite targets:

```makefile
pipeline:
	@touch data/pipeline.lock
	$(MAKE) ingest docpack
	@rm -f data/pipeline.lock

post-extract:
	@touch data/pipeline.lock
	$(MAKE) import resolve export trending
	@rm -f data/pipeline.lock
```

This creates `/app/data/pipeline.lock` during active runs (visible on
the `predictor-data` volume).

---

## 4. SQLite Backup Strategy

### 4.1 Daily backup (cron inside container)

Add a second cron entry in the Dockerfile:

```
# Backup SQLite daily at 5:30 AM (before 6:00 AM pipeline run)
30 5 * * * sqlite3 /app/data/db/predictor.db ".backup /app/data/db/backups/predictor_$(date +\%Y\%m\%d).db" 2>> /var/log/predictor-backup.log

# Retain 30 days of backups
35 5 * * * find /app/data/db/backups/ -name "predictor_*.db" -mtime +30 -delete
```

Create the backup directory in the Dockerfile:

```dockerfile
RUN mkdir -p data/db/backups
```

### 4.2 Pre-reboot backup (safe-reboot.sh modification)

Add this function to `usr_local_sbin_safe-reboot.sh`, called BEFORE
`docker compose down`:

```bash
backup_predictor_db() {
    log "Backing up predictor SQLite database..."

    # Wait for pipeline to finish if running
    local max_wait=120
    local waited=0
    while docker exec predictor-pipeline test -f /app/data/pipeline.lock 2>/dev/null; do
        if [ $waited -ge $max_wait ]; then
            log "WARNING: Predictor pipeline still running after ${max_wait}s, proceeding anyway"
            break
        fi
        log "Predictor pipeline in progress, waiting... (${waited}s/${max_wait}s)"
        sleep 5
        waited=$((waited + 5))
    done

    # Run SQLite online backup
    local backup_file="predictor_pre_reboot_$(date +%Y%m%d_%H%M%S).db"
    if docker exec predictor-pipeline \
        sqlite3 /app/data/db/predictor.db \
        ".backup /app/data/db/backups/${backup_file}"; then
        log "Predictor DB backed up: ${backup_file}"
    else
        log "WARNING: Predictor DB backup failed"
        # Do NOT abort reboot for this — the daily backup is the primary safety net
    fi
}
```

Call it in the safe-reboot sequence, after waiting for n8n executions
but before `docker compose down`:

```bash
# Existing: wait_for_executions
# Existing: backup_n8n_data
backup_predictor_db          # <-- add this line
# Existing: docker compose down
```

### 4.3 Backup verification

Add to `usr_local_sbin_agent-platform-health.sh`:

```bash
check_predictor_health() {
    log "Checking predictor pipeline health..."

    # Container running?
    if ! docker ps --format '{{.Names}}' | grep -q predictor-pipeline; then
        log "WARNING: predictor-pipeline container not running"
        return 1
    fi

    # DB exists and not empty?
    local db_size
    db_size=$(docker exec predictor-pipeline stat -c%s /app/data/db/predictor.db 2>/dev/null || echo 0)
    if [ "$db_size" -lt 1024 ]; then
        log "WARNING: predictor DB missing or too small (${db_size} bytes)"
        return 1
    fi

    # Recent backup exists (within last 48h)?
    local recent_backup
    recent_backup=$(docker exec predictor-pipeline \
        find /app/data/db/backups -name "predictor_*.db" -mtime -2 | head -1)
    if [ -z "$recent_backup" ]; then
        log "WARNING: No predictor DB backup in last 48 hours"
        return 1
    fi

    log "Predictor pipeline healthy (DB: ${db_size} bytes)"
    return 0
}
```

Call it from the main health check sequence alongside the existing checks.

---

## 5. Nginx Config Addition

If `nginx/nginx.conf` uses a simple static file config, the volume mounts
handle everything. If it has explicit `location` blocks, add:

```nginx
location /predictor/ {
    alias /usr/share/nginx/html/predictor/;
    try_files $uri $uri/ =404;
    add_header Cache-Control "no-cache";
}

location /predictor/data/graphs/ {
    alias /usr/share/nginx/html/predictor/data/graphs/;
    add_header Cache-Control "no-cache";
    add_header Access-Control-Allow-Origin "*";
}
```

`no-cache` ensures the client always gets fresh graph data after a pipeline run.

---

## 6. File Summary

### Files to CREATE in ai-agent-platform repo:

| File | Purpose |
|------|---------|
| `predictor/Dockerfile` | Container definition (Section 1) |

### Files to MODIFY in ai-agent-platform repo:

| File | Change |
|------|--------|
| `docker-compose.yml` | Add `predictor` service + `predictor-data` volume + nginx mounts (Section 2) |
| `docs/01-infrastructure/deployment/safe-reboot/usr_local_sbin_safe-reboot.sh` | Add `backup_predictor_db()` function (Section 4.2) |
| `docs/01-infrastructure/deployment/safe-reboot/usr_local_sbin_agent-platform-health.sh` | Add `check_predictor_health()` function (Section 4.3) |
| `nginx/nginx.conf` | Add predictor location blocks if needed (Section 5) |

### Files to MODIFY in predictor_ingest repo:

| File | Change |
|------|--------|
| `Makefile` | Add lock file creation/removal to composite targets (Section 3) |

---

## 7. Deployment Sequence

1. Build: `docker compose build predictor`
2. Start: `docker compose up -d predictor`
3. Verify: `docker logs predictor-pipeline`
4. Test pipeline manually: `docker exec predictor-pipeline make pipeline`
5. Check graph output: `ls public/graphs/`
6. Verify web client: `curl http://localhost:8080/predictor/`
7. Install updated safe-reboot scripts: `bash docs/01-infrastructure/deployment/safe-reboot/install.sh`
8. Test safe-reboot: verify it waits for pipeline lock and backs up SQLite

---

## 8. Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `TZ` | Yes | Timezone for cron schedule (default: America/New_York) |
| `OPENAI_API_KEY` | No (Mode A only) | For automated LLM extraction |
| `ANTHROPIC_API_KEY` | No (Mode A only) | Alternative LLM provider |

Pass API keys via `.env` file in the platform repo root (already gitignored).

---

## 9. Compatibility Notes

- **Python 3.11** — matches predictor's `requires-python >= 3.10`
- **SQLite** — bundled with Python; `sqlite3` CLI installed for backup commands
- **No port exposure** — predictor has no inbound ports; outbound only (RSS fetches)
- **Shared network** — joins `app-network` for potential future n8n integration
- **Volume persistence** — `predictor-data` survives container recreation and reboot
- **Safe reboot** — pipeline lock + pre-reboot backup integrates with existing shutdown sequence
