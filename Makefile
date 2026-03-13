.PHONY: setup init-db ingest docpack extract extract-shadow shadow-only shadow-report health-report import resolve export trending copy-to-live dashboard-data export_ontology pipeline post-extract daily daily-check test test-network test-all

# Domain slug — all data paths derive from this
DOMAIN ?= ai
DOMAIN_FLAG = --domain $(DOMAIN)

# Configurable paths (override with: make export DATE=2026-01-15)
DB ?= data/db/$(DOMAIN).db
DATE ?= $(shell date +%Y-%m-%d)
GRAPHS_DIR ?= data/graphs/$(DOMAIN)
DOCPACK_DIR ?= data/docpacks/$(DOMAIN)
DOCPACK ?= $(DOCPACK_DIR)/daily_bundle_$(DATE).jsonl
EXTRACTIONS_DIR ?= data/extractions/$(DOMAIN)
BUDGET ?= 20
BUDGET_FLAG = $(if $(BUDGET),--budget $(BUDGET),)

# ── Setup ──────────────────────────────────────────────────────────────

setup:
	pip install -e .

init-db:
	python scripts/init_db.py --db $(DB)

# ── Pipeline steps ─────────────────────────────────────────────────────

ingest:
	python -m ingest.rss --config domains/$(DOMAIN)/feeds.yaml --db $(DB) --raw-dir data/raw/$(DOMAIN) --text-dir data/text/$(DOMAIN)

docpack:
	python scripts/build_docpack.py --db $(DB) --all --label $(DATE) --output-dir $(DOCPACK_DIR) $(DOMAIN_FLAG)

extract:
	python scripts/run_extract.py --docpack $(DOCPACK) --escalate --db $(DB) --output-dir $(EXTRACTIONS_DIR) $(DOMAIN_FLAG)

extract-shadow:
	python scripts/run_extract.py --docpack $(DOCPACK) --shadow --parallel --db $(DB) --output-dir $(EXTRACTIONS_DIR) $(DOMAIN_FLAG)

shadow-only:
	python scripts/run_extract.py --docpack $(DOCPACK) --shadow-only --db $(DB) --output-dir $(EXTRACTIONS_DIR) $(DOMAIN_FLAG)

shadow-report:
	python scripts/shadow_report.py --db $(DB) $(DOMAIN_FLAG)

health-report:
	python scripts/health_report.py --db $(DB) $(DOMAIN_FLAG)

import:
	python scripts/import_extractions.py --db $(DB) --extractions-dir $(EXTRACTIONS_DIR) $(DOMAIN_FLAG)

resolve:
	python scripts/run_resolve.py --db $(DB) $(DOMAIN_FLAG)

export:
	python scripts/run_export.py --db $(DB) --output-dir $(GRAPHS_DIR) --date $(DATE) $(DOMAIN_FLAG)

trending:
	python scripts/run_trending.py --db $(DB) --output-dir $(GRAPHS_DIR)/$(DATE) $(DOMAIN_FLAG)

copy-to-live:
	@mkdir -p web/data/graphs/live/$(DOMAIN)
	cp $(GRAPHS_DIR)/$(DATE)/*.json web/data/graphs/live/$(DOMAIN)/
	@echo "Copied $(GRAPHS_DIR)/$(DATE)/ → web/data/graphs/live/$(DOMAIN)/"

dashboard-data:
	python scripts/generate_dashboard_json.py --db $(DB) $(DOMAIN_FLAG)

export_ontology:
	python scripts/export_ontology.py --domain $(DOMAIN)

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
	python scripts/run_pipeline.py --db $(DB) --date $(DATE) --graphs-dir $(GRAPHS_DIR) --copy-to-live $(BUDGET_FLAG) $(DOMAIN_FLAG) $(PIPELINE_FLAGS)

daily-check:
	python scripts/run_pipeline.py --db $(DB) --date $(DATE) --graphs-dir $(GRAPHS_DIR) $(BUDGET_FLAG) $(DOMAIN_FLAG) --dry-run

daily-manual:
	python scripts/run_pipeline.py --db $(DB) --date $(DATE) --graphs-dir $(GRAPHS_DIR) --skip-extract --copy-to-live $(BUDGET_FLAG) $(DOMAIN_FLAG) $(PIPELINE_FLAGS)

# ── Data migration ────────────────────────────────────────────────────

migrate:
	python scripts/migrate_data_dirs.py

# ── Testing ────────────────────────────────────────────────────────────

test:
	pytest tests/ -m "not network and not llm_live"

test-network:
	python scripts/run_network_tests.py

test-all:
	pytest tests/ -v
