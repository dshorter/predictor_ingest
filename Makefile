.PHONY: setup init-db ingest docpack import resolve export trending pipeline post-extract test test-network

# Default paths and configuration
DB ?= data/db/predictor.db
DATE ?= $(shell date +%Y-%m-%d)
GRAPHS_DIR ?= data/graphs

# ============================================================================
# Setup and initialization
# ============================================================================

setup:
	pip install -e .

init-db:
	python scripts/init_db.py --db $(DB)

# ============================================================================
# Ingestion and docpack generation (Mode B pre-extraction)
# ============================================================================

ingest:
	python -m ingest.rss --config config/feeds.yaml

docpack:
	python scripts/build_docpack.py --db $(DB) --date $(DATE)

# ============================================================================
# Post-extraction pipeline
# ============================================================================

import:
	python scripts/import_extractions.py --db $(DB)

resolve:
	python scripts/run_resolve.py --db $(DB)

export:
	python scripts/run_export.py --db $(DB) --output-dir $(GRAPHS_DIR) --date $(DATE)

trending:
	python scripts/run_trending.py --db $(DB) --output-dir $(GRAPHS_DIR)/$(DATE)

# ============================================================================
# Convenience composites
# ============================================================================

pipeline: ingest docpack

post-extract: import resolve export trending

# ============================================================================
# Testing
# ============================================================================

test:
	pytest tests/ -m "not network"

test-network:
	python scripts/run_network_tests.py

# ============================================================================
# Help
# ============================================================================

help:
	@echo "AI Trend Graph - Manual Workflow Makefile"
	@echo ""
	@echo "Setup and initialization:"
	@echo "  make setup       Install Python dependencies"
	@echo "  make init-db     Initialize SQLite database"
	@echo ""
	@echo "Daily workflow (Mode B):"
	@echo "  make pipeline    Run ingest + docpack (outputs .md for ChatGPT)"
	@echo "                   → Paste into ChatGPT, save extraction JSONs"
	@echo "  make post-extract Run import + resolve + export + trending"
	@echo ""
	@echo "Individual steps:"
	@echo "  make ingest      Fetch RSS feeds and clean content"
	@echo "  make docpack     Generate document bundle for extraction"
	@echo "  make import      Import extraction JSONs into database"
	@echo "  make resolve     Run entity resolution (merge duplicates)"
	@echo "  make export      Export graph data (mentions, claims, dependencies)"
	@echo "  make trending    Export trending entities with scores"
	@echo ""
	@echo "Testing:"
	@echo "  make test        Run unit tests (non-network)"
	@echo "  make test-network Run network integration tests"
	@echo ""
	@echo "Variables (override with make VAR=value ...):"
	@echo "  DB=$(DB)"
	@echo "  DATE=$(DATE)"
	@echo "  GRAPHS_DIR=$(GRAPHS_DIR)"
	@echo ""
	@echo "For full documentation, see docs/backend/workflow-guide.md"
