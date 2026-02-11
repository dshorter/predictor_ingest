.PHONY: setup init-db ingest docpack extract shadow-only shadow-report import resolve export trending pipeline post-extract test test-network test-all

# Configurable paths (override with: make export DATE=2026-01-15)
DB ?= data/db/predictor.db
DATE ?= $(shell date +%Y-%m-%d)
GRAPHS_DIR ?= data/graphs
DOCPACK ?= data/docpacks/daily_bundle_$(DATE).jsonl

# ── Setup ──────────────────────────────────────────────────────────────

setup:
	pip install -e .

init-db:
	python scripts/init_db.py --db $(DB)

# ── Pipeline steps ─────────────────────────────────────────────────────

ingest:
	python -m ingest.rss --config config/feeds.yaml --db $(DB)

docpack:
	python scripts/build_docpack.py --db $(DB) --date $(DATE)

extract:
	python scripts/run_extract.py --docpack $(DOCPACK) --shadow --parallel --db $(DB)

shadow-only:
	python scripts/run_extract.py --docpack $(DOCPACK) --shadow-only --db $(DB)

shadow-report:
	python scripts/shadow_report.py --db $(DB)

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
	@touch data/pipeline.lock
	$(MAKE) ingest docpack
	@rm -f data/pipeline.lock

post-extract:
	@touch data/pipeline.lock
	$(MAKE) import resolve export trending
	@rm -f data/pipeline.lock

# ── Testing ────────────────────────────────────────────────────────────

test:
	pytest tests/ -m "not network and not llm_live"

test-network:
	python scripts/run_network_tests.py

test-all:
	pytest tests/ -v
