.PHONY: setup init-db ingest docpack submit collect health-report import resolve export trending copy-to-live dashboard-data export_ontology post-extract daily daily-check test test-network test-all migrate-batch backlog calibration-report

# Domain slug — all data paths derive from this
DOMAIN ?= film
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

submit:
	python scripts/submit_batch.py --db $(DB) --domain $(DOMAIN) --docpack $(DOCPACK) --date $(DATE)

collect:
	python scripts/collect_batch.py --db $(DB) --domain $(DOMAIN) --output-dir $(EXTRACTIONS_DIR)

migrate-batch:
	python scripts/migrate_batch_api.py --db $(DB)

backlog:
	python scripts/submit_backlog.py --db $(DB) --domain $(DOMAIN) --chunk-size 100

health-report:
	python scripts/health_report.py --db $(DB) $(DOMAIN_FLAG)

import:
	python scripts/import_extractions.py --db $(DB) --extractions-dir $(EXTRACTIONS_DIR) $(DOMAIN_FLAG)

resolve:
	python scripts/run_resolve.py --db $(DB) $(DOMAIN_FLAG)

export:
	python scripts/run_export.py --db $(DB) --output-dir $(GRAPHS_DIR) --date $(DATE) $(DOMAIN_FLAG)

trending:
	python scripts/run_trending.py --db $(DB) --output-dir $(GRAPHS_DIR)/$(DATE) --narratives $(DOMAIN_FLAG)

copy-to-live:
	@mkdir -p web/data/graphs/live/$(DOMAIN)
	cp $(GRAPHS_DIR)/$(DATE)/*.json web/data/graphs/live/$(DOMAIN)/
	@echo "Copied $(GRAPHS_DIR)/$(DATE)/ → web/data/graphs/live/$(DOMAIN)/"

dashboard-data:
	python scripts/generate_dashboard_json.py --db $(DB) $(DOMAIN_FLAG)

export_ontology:
	python scripts/export_ontology.py --domain $(DOMAIN)

# ── Composites ─────────────────────────────────────────────────────────

post-collect:
	@touch data/pipeline.lock
	$(MAKE) import resolve export trending copy-to-live
	@rm -f data/pipeline.lock

daily:
	python scripts/run_pipeline.py --db $(DB) --date $(DATE) --graphs-dir $(GRAPHS_DIR) --copy-to-live $(BUDGET_FLAG) $(DOMAIN_FLAG) $(PIPELINE_FLAGS)

daily-check:
	python scripts/run_pipeline.py --db $(DB) --date $(DATE) --graphs-dir $(GRAPHS_DIR) $(BUDGET_FLAG) $(DOMAIN_FLAG) --dry-run

daily-manual:
	python scripts/run_pipeline.py --db $(DB) --date $(DATE) --graphs-dir $(GRAPHS_DIR) --skip-extract --copy-to-live $(BUDGET_FLAG) $(DOMAIN_FLAG) $(PIPELINE_FLAGS)

calibration-report:
	python scripts/run_calibration_report.py --db $(DB) --domain $(DOMAIN) --days 7

calibration-report-log:
	python scripts/run_calibration_report.py --db $(DB) --domain $(DOMAIN) --days 7 --log-suggestions

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
