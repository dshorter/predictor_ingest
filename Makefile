.PHONY: setup init-db ingest docpack import resolve export trending pipeline post-extract test test-network test-all

# Configurable paths (override with: make export DATE=2026-01-15)
DB ?= data/db/predictor.db
DATE ?= $(shell date +%Y-%m-%d)
GRAPHS_DIR ?= data/graphs
LOCK_FILE ?= /app/data/pipeline.lock

# ── Setup ──────────────────────────────────────────────────────────────

setup:
	pip install -e .

init-db:
	python scripts/init_db.py --db $(DB)

# ── Pipeline steps ─────────────────────────────────────────────────────

ingest:
	python -m ingest.rss --config config/feeds.yaml

docpack:
	python scripts/build_docpack.py --db $(DB) --date $(DATE)

import:
	python scripts/import_extractions.py --db $(DB)

resolve:
	python scripts/run_resolve.py --db $(DB)

export:
	python scripts/run_export.py --db $(DB) --output-dir $(GRAPHS_DIR) --date $(DATE)

trending:
	python scripts/run_trending.py --db $(DB) --output-dir $(GRAPHS_DIR)/$(DATE)

# ── Composites ─────────────────────────────────────────────────────────

pipeline:
	@touch $(LOCK_FILE)
	$(MAKE) ingest docpack
	@rm -f $(LOCK_FILE)

post-extract:
	@touch $(LOCK_FILE)
	$(MAKE) import resolve export trending
	@rm -f $(LOCK_FILE)

# ── Testing ────────────────────────────────────────────────────────────

test:
	pytest tests/ -m "not network and not llm_live"

test-network:
	python scripts/run_network_tests.py

test-all:
	pytest tests/ -v
