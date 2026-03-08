.PHONY: setup init-db ingest docpack extract extract-shadow shadow-only shadow-report health-report import resolve export trending copy-to-live dashboard-data pipeline post-extract daily test test-network test-all

# Configurable paths (override with: make export DATE=2026-01-15)
DB ?= data/db/predictor.db
DATE ?= $(shell date +%Y-%m-%d)
GRAPHS_DIR ?= data/graphs
DOCPACK ?= data/docpacks/daily_bundle_$(DATE).jsonl
BUDGET ?= 20
BUDGET_FLAG = $(if $(BUDGET),--budget $(BUDGET),)

# ── Setup ──────────────────────────────────────────────────────────────

setup:
	pip install -e .

init-db:
	python scripts/init_db.py --db $(DB)

# ── Pipeline steps ─────────────────────────────────────────────────────

ingest:
	python -m ingest.rss --config config/feeds.yaml --db $(DB)

docpack:
	python scripts/build_docpack.py --db $(DB) --all --label $(DATE)

extract:
	python scripts/run_extract.py --docpack $(DOCPACK) --escalate --db $(DB)

extract-shadow:
	python scripts/run_extract.py --docpack $(DOCPACK) --shadow --parallel --db $(DB)

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
	python scripts/run_export.py --db $(DB) --output-dir $(GRAPHS_DIR)/$(DOMAIN) --date $(DATE)

trending:
	python scripts/run_trending.py --db $(DB) --output-dir $(GRAPHS_DIR)/$(DOMAIN)/$(DATE)

copy-to-live:
	@mkdir -p web/data/graphs/live/$(DOMAIN)
	cp $(GRAPHS_DIR)/$(DOMAIN)/$(DATE)/*.json web/data/graphs/live/$(DOMAIN)/
	@echo "Copied $(GRAPHS_DIR)/$(DOMAIN)/$(DATE)/ → web/data/graphs/live/$(DOMAIN)/"

dashboard-data:
	python scripts/generate_dashboard_json.py --db $(DB)

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
	python scripts/run_pipeline.py --db $(DB) --date $(DATE) --graphs-dir $(GRAPHS_DIR) --copy-to-live $(BUDGET_FLAG) $(PIPELINE_FLAGS)

daily-manual:
	python scripts/run_pipeline.py --db $(DB) --date $(DATE) --graphs-dir $(GRAPHS_DIR) --skip-extract --copy-to-live $(BUDGET_FLAG) $(PIPELINE_FLAGS)

# ── Testing ────────────────────────────────────────────────────────────

test:
	pytest tests/ -m "not network and not llm_live"

test-network:
	python scripts/run_network_tests.py

test-all:
	pytest tests/ -v
