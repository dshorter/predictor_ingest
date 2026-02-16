.PHONY: setup init-db ingest docpack extract extract-escalate shadow-only shadow-report health-report import resolve export trending copy-to-live pipeline post-extract daily test test-network test-all

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

extract-escalate:
	python scripts/run_extract.py --docpack $(DOCPACK) --escalate --db $(DB)

shadow-only:
	python scripts/run_extract.py --docpack $(DOCPACK) --shadow-only --db $(DB)

shadow-report:
	python scripts/shadow_report.py --db $(DB)

health-report:
	python scripts/health_report.py --db $(DB)

import:
	python scripts/import_extractions.py --db $(DB)

resolve:
	python scripts/run_resolve.py --db $(DB)

export:
	python scripts/run_export.py --db $(DB) --output-dir $(GRAPHS_DIR) --date $(DATE)

trending:
	python scripts/run_trending.py --db $(DB) --output-dir $(GRAPHS_DIR)/$(DATE)

copy-to-live:
	@mkdir -p web/data/graphs/live
	cp $(GRAPHS_DIR)/$(DATE)/*.json web/data/graphs/live/
	@echo "Copied $(GRAPHS_DIR)/$(DATE)/ → web/data/graphs/live/"

# ── Composites ─────────────────────────────────────────────────────────

pipeline:
	@touch data/pipeline.lock
	$(MAKE) ingest docpack
	@rm -f data/pipeline.lock

post-extract:
	@touch data/pipeline.lock
	$(MAKE) import resolve export trending copy-to-live
	@rm -f data/pipeline.lock

daily:
	python scripts/run_pipeline.py --db $(DB) --date $(DATE) --graphs-dir $(GRAPHS_DIR) --copy-to-live

daily-manual:
	python scripts/run_pipeline.py --db $(DB) --date $(DATE) --graphs-dir $(GRAPHS_DIR) --skip-extract --copy-to-live

# ── Testing ────────────────────────────────────────────────────────────

test:
	pytest tests/ -m "not network and not llm_live"

test-network:
	python scripts/run_network_tests.py

test-all:
	pytest tests/ -v
