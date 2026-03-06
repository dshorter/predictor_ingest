# Predictor Ingest

[![Deploy to VPS](https://github.com/dshorter/predictor_ingest/actions/workflows/deploy.yml/badge.svg)](https://github.com/dshorter/predictor_ingest/actions/workflows/deploy.yml)

![version](https://img.shields.io/badge/dynamic/toml?url=https://raw.githubusercontent.com/dshorter/predictor_ingest/main/pyproject.toml&query=$.project.version&label=version&prefix=v)
![python](https://img.shields.io/badge/dynamic/toml?url=https://raw.githubusercontent.com/dshorter/predictor_ingest/main/pyproject.toml&query=$.tool.versions.python&label=python)
![feedparser](https://img.shields.io/badge/dynamic/toml?url=https://raw.githubusercontent.com/dshorter/predictor_ingest/main/pyproject.toml&query=$.tool.versions.feedparser&label=feedparser)
![requests](https://img.shields.io/badge/dynamic/toml?url=https://raw.githubusercontent.com/dshorter/predictor_ingest/main/pyproject.toml&query=$.tool.versions.requests&label=requests)
![beautifulsoup4](https://img.shields.io/badge/dynamic/toml?url=https://raw.githubusercontent.com/dshorter/predictor_ingest/main/pyproject.toml&query=$.tool.versions.beautifulsoup4&label=beautifulsoup4)
![pyyaml](https://img.shields.io/badge/dynamic/toml?url=https://raw.githubusercontent.com/dshorter/predictor_ingest/main/pyproject.toml&query=$.tool.versions.pyyaml&label=pyyaml)
![jsonschema](https://img.shields.io/badge/dynamic/toml?url=https://raw.githubusercontent.com/dshorter/predictor_ingest/main/pyproject.toml&query=$.tool.versions.jsonschema&label=jsonschema)

A pipeline for building AI trend knowledge graphs from RSS feeds and web sources. Extracts entities, relationships, and trends to produce Cytoscape.js-ready visualizations with an interactive web client.

## Overview

```
RSS Feeds → Ingest → Clean → [Doc Select] → Extract → Resolve → Graph/Trend → Cytoscape.js
```

The pipeline:
1. **Ingests** RSS feeds and web pages (archive-first: raw HTML + cleaned text stored with metadata)
2. **Cleans** HTML to extract article content
3. **Selects** documents for extraction (scored by word count, metadata quality, source tier, signal type)
4. **Extracts** entities and relationships (via LLM API or manual ChatGPT paste)
5. **Resolves** duplicate entities into canonical forms
6. **Exports** four Cytoscape.js graph views
7. **Scores** entities for velocity, novelty, and bridge metrics

## Installation

```bash
git clone <repo-url>
cd predictor_ingest
make setup          # pip install -e .
make init-db        # create data/db/predictor.db
```

## Quick Start

### 1. Configure Feeds

Edit `config/feeds.yaml`:

```yaml
feeds:
  - name: "arXiv CS.AI"
    url: "https://rss.arxiv.org/rss/cs.AI"
    type: rss
    enabled: true
```

### 2. Run the Full Daily Pipeline

**Mode A: LLM API available**

```bash
export ANTHROPIC_API_KEY=sk-...   # or OPENAI_API_KEY
make daily                        # ingest → docpack → extract → resolve → export → trending → copy-to-live
```

**Mode B: No API key (manual ChatGPT)**

```bash
make daily-manual    # ingest → docpack → (skip extract) → resolve → export → trending → copy-to-live
# Then: upload the docpack to ChatGPT, save returned JSON to data/extractions/
make import          # validate and import manual extractions
make post-extract    # resolve → export → trending → copy-to-live
```

### 3. Run Steps Individually

```bash
make ingest          # Fetch RSS feeds → DB
make docpack         # Build JSONL bundle for extraction
make extract         # LLM extraction with escalation (Mode A)
make import          # Import & validate manual extractions (Mode B)
make resolve         # Merge duplicate entities
make export          # Export graph JSON views
make trending        # Compute trend scores → trending.json
make copy-to-live    # Copy graphs to web/data/graphs/live/
make dashboard-data  # Generate pipeline health JSON for dashboard
make health-report   # Print pipeline health summary
```

### 4. View the Graph

Open `web/index.html` in a browser (or serve it statically). The client automatically loads from `web/data/graphs/live/`.

> For mobile: `web/mobile/index.html` — a separate responsive layout auto-detected by `index.html`.

## Makefile Reference

| Target | Description |
|--------|-------------|
| `make setup` | Install Python package in editable mode |
| `make init-db` | Initialize SQLite database |
| `make ingest` | Fetch all enabled RSS feeds |
| `make docpack` | Build daily JSONL document bundle |
| `make extract` | LLM extraction with auto-escalation |
| `make extract-shadow` | Run main + shadow model in parallel |
| `make shadow-only` | Run shadow model only (no DB write) |
| `make shadow-report` | Print cheap-vs-main quality comparison |
| `make health-report` | Print pipeline health summary |
| `make import` | Validate + import manual extractions |
| `make resolve` | Entity resolution pass |
| `make export` | Export graph JSON views |
| `make trending` | Compute and export trend scores |
| `make copy-to-live` | Publish graph files to web client |
| `make dashboard-data` | Regenerate dashboard metrics JSON |
| `make pipeline` | `ingest + docpack` (with lock file) |
| `make post-extract` | `import → resolve → export → trending → copy-to-live` |
| `make daily` | Full automated daily run (Mode A) |
| `make daily-manual` | Daily run skipping extraction (Mode B) |
| `make test` | Non-network, non-LLM unit tests |
| `make test-network` | Network integration tests |
| `make test-all` | All tests |

Overridable variables: `DB`, `DATE`, `GRAPHS_DIR`, `DOCPACK`, `BUDGET`.

## Project Structure

```
predictor_ingest/
├── src/
│   ├── config/       # Feed configuration loader
│   ├── db/           # SQLite database operations
│   ├── schema/       # JSON Schema validation
│   ├── ingest/       # RSS/web fetching CLI
│   ├── extract/      # LLM prompt building, parsing, quality gates
│   ├── doc_select/   # Document scoring and selection for extraction
│   ├── util/         # Hashing, slugify, date parsing
│   ├── clean/        # Readability extraction, boilerplate removal
│   ├── resolve/      # Entity resolution, alias merging
│   ├── graph/        # Cytoscape.js export
│   └── trend/        # Velocity, novelty, bridge scoring
├── config/
│   └── feeds.yaml    # RSS feed configuration
├── schemas/
│   ├── extraction.json  # JSON Schema for extraction output
│   └── sqlite.sql       # Database schema
├── scripts/          # Pipeline orchestration and helper scripts
├── tests/            # pytest test suite (20 modules)
├── diagnostics/      # Runtime diagnostic output
├── data/             # Runtime data (gitignored)
│   ├── raw/          # Raw HTML
│   ├── text/         # Cleaned text
│   ├── docpacks/     # Daily JSONL bundles
│   ├── extractions/  # Per-doc extraction JSON
│   ├── graphs/       # Dated Cytoscape exports
│   └── db/           # predictor.db (SQLite)
└── web/              # Cytoscape.js interactive viewer
    ├── index.html    # Desktop graph explorer
    ├── dashboard.html# Pipeline health dashboard
    ├── mobile/       # Responsive mobile UI
    ├── help/         # In-app help system
    ├── js/           # app, filter, graph, layout, panels,
    │                 #   search, styles, tooltips, utils, help
    ├── css/          # Design token system + component partials
    └── data/graphs/live/  # Live graph JSON (copied by make copy-to-live)
```

## LLM Extraction

### Extractor v2.0.0 Features

- **Escalation mode** (`--escalate`): auto-escalates low-confidence or low-yield extractions to a stronger model
- **Shadow mode** (`--shadow`, `--shadow-only`): runs a cheap model in parallel for quality comparison without DB writes
- **Budget controls** (`--budget N`): cap daily LLM spend (default: `$20`)
- **Quality gates (CPU, zero tokens)**: four non-negotiable gates run on every extraction before scoring:
  - *Evidence fidelity* — snippet must appear in source text (≥70%)
  - *Orphan endpoints* — relation source/target must match a declared entity (0% tolerance)
  - *Zero-value* — non-trivial documents must yield ≥1 entity
  - *High-confidence + bad evidence* — immediate escalation trigger
- Environment variables: `ANTHROPIC_API_KEY` (Claude) or `OPENAI_API_KEY` (OpenAI)

## Graph Views

| View | Description |
|------|-------------|
| `claims.json` | Entity-to-entity semantic relations (CREATED, USES_TECH, etc.) |
| `mentions.json` | Document-to-entity MENTIONS edges |
| `dependencies.json` | Dependency relations only (USES_*, TRAINED_ON, etc.) |
| `trending.json` | Entities ranked by trend score |

Each export includes `meta` (view, nodeCount, edgeCount, exportedAt, dateRange) and `elements` (nodes, edges) in Cytoscape.js format.

## Entity Types

`Org`, `Person`, `Program`, `Tool`, `Model`, `Dataset`, `Benchmark`, `Paper`, `Repo`, `Document`, `Tech`, `Topic`, `Event`, `Location`, `Other`

## Relation Types

**Document:** `MENTIONS`, `CITES`, `ANNOUNCES`, `REPORTED_BY`

**Org/Person/Program:** `LAUNCHED`, `PUBLISHED`, `UPDATED`, `FUNDED`, `PARTNERED_WITH`, `ACQUIRED`, `HIRED`, `CREATED`, `OPERATES`, `GOVERNED_BY`/`GOVERNS`, `REGULATES`, `COMPLIES_WITH`

**Tech/Model/Tool/Dataset:** `USES_TECH`, `USES_MODEL`, `USES_DATASET`, `TRAINED_ON`, `EVALUATED_ON`, `INTEGRATES_WITH`, `DEPENDS_ON`, `REQUIRES`, `PRODUCES`, `MEASURES`, `AFFECTS`

**Forecasting:** `PREDICTS`, `DETECTS`, `MONITORS`

Prefer `MENTIONS` as the base layer; only emit semantic edges when evidence supports them.

## Trend Signals

| Signal | Description |
|--------|-------------|
| `mention_count_7d` | Mentions in last 7 days |
| `mention_count_30d` | Mentions in last 30 days |
| `velocity` | Ratio of recent to previous mentions |
| `novelty` | Based on entity age and rarity |
| `bridge_score` | Connectivity/centrality measure |

## Web Client

The static Cytoscape.js client at `web/index.html` provides:

- Four graph views switchable from the toolbar
- Node search with live result count
- Neighborhood highlighting and dimming
- Filter panel (by node type, relation type, date range)
- In-app help (`web/help/`)
- Dark mode / theme toggle
- Minimap navigator (cytoscape-navigator)
- Mobile-responsive layout auto-detected and redirected to `web/mobile/`
- Pipeline health dashboard at `web/dashboard.html`

## Testing

```bash
make test              # non-network, non-LLM unit tests
make test-network      # network integration tests (requires internet)
make test-all          # all tests

# Or directly:
pytest tests/ -m "not network and not llm_live"
```

**Test coverage:** ~209 non-network tests across 20 modules.

Markers: `network` (requires internet), `llm_live` (requires API key).

## Environment Variables

| Variable | Required For |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Mode A extraction via Claude |
| `OPENAI_API_KEY` | Mode A extraction via OpenAI |

No environment variables required for ingestion, manual import, or graph export.

## Configuration

### Feed Configuration (`config/feeds.yaml`)

```yaml
feeds:
  - name: "Feed Name"
    url: "https://example.com/feed.xml"
    type: rss        # or atom
    tier: 1          # 1=primary, 2=secondary, 3=echo
    enabled: true    # set false to skip
```

### Makefile Overrides

```bash
make daily DB=data/db/custom.db DATE=2026-03-01 BUDGET=10
```

## Documentation

#### Methodology & Architecture

| Document | Purpose |
|----------|---------|
| [docs/methodology/prediction-methodology.md](docs/methodology/prediction-methodology.md) | Signal formulas, source requirements, weight tuning |
| [docs/architecture/domain-separation.md](docs/architecture/domain-separation.md) | Framework vs. domain-config boundary |
| [docs/architecture/convergence-narrative.md](docs/architecture/convergence-narrative.md) | Big-picture decision log — read first |
| [docs/architecture/date-filtering.md](docs/architecture/date-filtering.md) | Why `published_at` is used; NULL handling |
| [docs/architecture/multi-domain-futures.md](docs/architecture/multi-domain-futures.md) | Post-V2 multi-domain vision |

#### Pipeline & Backend

| Document | Purpose |
|----------|---------|
| [docs/backend/workflow-guide.md](docs/backend/workflow-guide.md) | Step-by-step pipeline guide (Mode A & B) |
| [docs/backend/daily-run-log.md](docs/backend/daily-run-log.md) | JSON log format, per-stage metrics, healthy thresholds |
| [docs/backend/manual-workflow-plan.md](docs/backend/manual-workflow-plan.md) | Script specs for docpack, import, resolve, export, trending |
| [docs/llm-selection.md](docs/llm-selection.md) | LLM tiers, escalation, shadow mode, cost model |
| [docs/source-selection-strategy.md](docs/source-selection-strategy.md) | Feed tier model, entity overlap strategy |
| [docs/research/extract-quality-analysis.md](docs/research/extract-quality-analysis.md) | Quality gate design, evaluation architecture, calibration |
| [docs/research/trend-insights.md](docs/research/trend-insights.md) | Insight articulation layer, templates, backtest protocol |

#### UX & Visualization

| Document | Purpose |
|----------|---------|
| [docs/product/README.md](docs/product/README.md) | UI walkthrough, visual encoding, workflows, screenshots |
| [docs/ux/README.md](docs/ux/README.md) | Cytoscape client implementation guidelines |
| [docs/ux/troubleshooting.md](docs/ux/troubleshooting.md) | Cytoscape.js gotchas and fixes |
| [docs/ux/dark-mode-implementation.md](docs/ux/dark-mode-implementation.md) | Dark mode / theme toggle |
| [docs/ux/polish-strategy.md](docs/ux/polish-strategy.md) | Aesthetic mechanics: typography, toolbar, canvas |

#### Schema & Data

| Document | Purpose |
|----------|---------|
| [docs/schema/data-contracts.md](docs/schema/data-contracts.md) | Full schemas: documents table, docpack JSONL, extraction JSON, Cytoscape export |
| [GLOSSARY.md](GLOSSARY.md) | Term definitions |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

#### Operational History

| Document | Purpose |
|----------|---------|
| [docs/fix-details/README.md](docs/fix-details/README.md) | Index of resolved production issues with root causes |
| [docs/backlog.md](docs/backlog.md) | Known issues and prompt-tuning observations |
| [docs/project-plan.md](docs/project-plan.md) | Sprint plan, model assignments, timeline |

## License

*TBD*

## Contributing

*TBD*
