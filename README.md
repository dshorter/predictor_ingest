# Predictor Ingest

[![Deploy to VPS](https://github.com/dshorter/predictor_ingest/actions/workflows/deploy.yml/badge.svg)](https://github.com/dshorter/predictor_ingest/actions/workflows/deploy.yml)
[![GitHub Release](https://img.shields.io/github/v/release/dshorter/predictor_ingest?include_prereleases&label=release)](https://github.com/dshorter/predictor_ingest/releases)
![version](https://img.shields.io/badge/dynamic/toml?url=https://raw.githubusercontent.com/dshorter/predictor_ingest/main/pyproject.toml&query=$.project.version&label=version&prefix=v)
![python](https://img.shields.io/badge/dynamic/toml?url=https://raw.githubusercontent.com/dshorter/predictor_ingest/main/pyproject.toml&query=$.tool.versions.python&label=python)
![stage](https://img.shields.io/badge/stage-beta-orange)
![SQLite](https://img.shields.io/badge/storage-SQLite-003B57?logo=sqlite&logoColor=white)
![Cytoscape.js](https://img.shields.io/badge/viz-Cytoscape.js-F7DF1E)

A pipeline for building AI trend knowledge graphs from RSS feeds and web sources. Extracts entities, relationships, and trends — then exports interactive Cytoscape.js visualizations that reveal emerging patterns early.

## Overview

```
RSS Feeds → Ingest → Clean → Extract → Resolve → Export → Cytoscape.js
              │                  │                    │
            SQLite          LLM / Manual          4 graph views
           (archive)       (with quality gates)   + trend scores
```

The pipeline:
1. **Ingests** ~40 RSS feeds and web pages daily (archive-first into SQLite)
2. **Cleans** HTML via readability extraction and boilerplate removal
3. **Extracts** entities and relationships via LLM API with escalation (**Mode A**) or semi-manual ChatGPT workflow (**Mode B**)
4. **Validates** extractions through quality gates (evidence fidelity, orphan detection, confidence scoring)
5. **Resolves** duplicate entities into canonical forms with alias tracking
6. **Exports** four Cytoscape.js graph views (mentions, claims, dependencies, trending)
7. **Scores** entities for velocity, novelty, and bridge metrics to surface emerging trends

## Quick Start

```bash
# Install
git clone <repo-url> && cd predictor_ingest
pip install -e .

# Initialize database
make init-db

# Run the full daily pipeline (ingest → extract → resolve → export → trending)
make daily

# Or run steps individually
make ingest          # Fetch RSS feeds
make docpack         # Build document bundles
make extract         # LLM extraction (Mode A, requires API key)
make import          # Import manual extractions (Mode B)
make resolve         # Entity resolution
make export          # Generate graph views
make trending        # Compute trend scores
make copy-to-live    # Publish to web client
```

### Mode A — LLM API (automated)

With an API key configured, `make extract` calls the LLM with strict JSON output, validates against the extraction schema, and runs quality gates. Supports escalation (retry with stronger model on failure) and shadow mode (compare understudy models).

### Mode B — Manual (no API key)

```bash
make docpack                    # Produces JSONL + MD bundle
# → Paste/upload into ChatGPT, request extraction in schema format
# → Save returned JSON to data/extractions/
make import                     # Validates and stores extractions
```

Both modes feed into the same downstream pipeline (`resolve → export → trending`).

## Pipeline Commands

| Target | Description |
|--------|-------------|
| **Setup** | |
| `make setup` | Install package in editable mode |
| `make init-db` | Initialize SQLite database |
| **Pipeline Steps** | |
| `make ingest` | Fetch RSS feeds into database |
| `make docpack` | Build JSONL bundles for extraction |
| `make extract` | Run LLM extraction with escalation |
| `make extract-shadow` | Run extraction with shadow model comparison |
| `make import` | Import manual extraction JSON |
| `make resolve` | Entity resolution and canonicalization |
| `make export` | Generate Cytoscape.js graph views |
| `make trending` | Compute trend scores |
| `make copy-to-live` | Copy graphs to web client |
| **Composites** | |
| `make daily` | Full automated pipeline (all steps) |
| `make daily-manual` | Pipeline without extraction (for Mode B) |
| `make pipeline` | Ingest + docpack only |
| `make post-extract` | Import → resolve → export → trending → copy-to-live |
| **Diagnostics** | |
| `make health-report` | Pipeline health metrics |
| `make shadow-report` | Shadow model performance comparison |
| `make dashboard-data` | Generate dashboard JSON |
| **Testing** | |
| `make test` | Run unit tests (no network/LLM) |
| `make test-network` | Run network-dependent tests |
| `make test-all` | Run all tests |

Overridable variables: `DB`, `DATE`, `GRAPHS_DIR`, `DOCPACK`, `BUDGET`.

## Web Client — AI Trend Graph Viewer

The pipeline's end product is an interactive Cytoscape.js knowledge graph explorer in [`web/`](web/). It runs as a static site — no backend needed beyond the exported JSON files.

**Features:**
- **4 graph views** — Trending, Claims, Mentions, Dependencies (switchable from toolbar)
- **Force-directed layout** — fcose with automatic clustering
- **Search & filter** — by entity type, relationship kind, confidence threshold, date range
- **Node detail panel** — aliases, connections, evidence snippets, trend scores
- **Edge evidence panel** — provenance with source snippets and URLs
- **Minimap** — navigator overlay for large graphs
- **Dark mode** — system-aware with manual toggle
- **Mobile** — dedicated touch-optimized viewer at `web/mobile/`
- **Sample data** — small/medium/large/stress tiers for testing without live data
- **Accessibility** — ARIA roles, keyboard navigation, screen reader announcements

**Serving locally:**
```bash
make copy-to-live    # Publish latest export to web/data/graphs/live/
cd web && python -m http.server 8000
# Open http://localhost:8000
```

See [`web/README.md`](web/README.md) for architecture, file inventory, and Cytoscape.js gotchas.

## Project Structure

```
predictor_ingest/
├── src/
│   ├── config/          # Feed configuration loader
│   ├── db/              # SQLite database operations
│   ├── schema/          # JSON Schema validation
│   ├── ingest/          # RSS/web fetching CLI
│   ├── clean/           # Readability extraction, boilerplate removal
│   ├── extract/         # LLM prompt building, parsing, quality gates
│   ├── doc_select/      # Document selection for extraction
│   ├── resolve/         # Entity resolution, alias merging
│   ├── graph/           # Cytoscape.js export (4 views)
│   ├── trend/           # Velocity, novelty, bridge scoring
│   └── util/            # Hashing, slugify, date parsing
├── config/
│   ├── feeds.yaml       # ~40 RSS feed definitions (tiered)
│   └── views.yaml       # Graph view definitions
├── schemas/
│   ├── extraction.json  # JSON Schema for extraction output
│   └── sqlite.sql       # Database schema (10+ tables)
├── scripts/             # 18 pipeline and diagnostic scripts
├── tests/               # pytest suite (18 modules, ~209 tests)
│   └── fixtures/        # Test data and sample extractions
├── web/                 # Cytoscape.js viewer (live)
│   ├── index.html       # Desktop graph explorer
│   ├── dashboard.html   # Dashboard / insights view
│   ├── mobile/          # Mobile-optimized viewer
│   ├── js/              # App logic, graph, layout, search, filters
│   ├── css/             # Design tokens, components, graph styles
│   ├── help/            # In-app help and glossary
│   └── data/graphs/     # Exported graph JSON (live/, latest/, etc.)
├── docs/                # 50+ documentation files
└── data/                # Runtime data (gitignored)
    ├── raw/             # Raw HTML
    ├── text/            # Cleaned text
    ├── docpacks/        # Document bundles
    ├── extractions/     # Per-doc extraction JSON
    ├── graphs/          # Cytoscape exports by date
    └── db/              # SQLite database
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

> **See also:** [LLM model tiers, escalation architecture, cost model](docs/llm-selection.md) · [Quality gate design and calibration](docs/research/extract-quality-analysis.md)

## Graph Views

| View | Description |
|------|-------------|
| `mentions.json` | Document-to-entity MENTIONS edges |
| `claims.json` | Entity-to-entity semantic relations (CREATED, USES_TECH, etc.) |
| `dependencies.json` | Dependency relations only (USES_*, TRAINED_ON, etc.) |
| `trending.json` | Entities ranked by trend score with velocity/novelty metrics |

Each export includes `meta` (view, nodeCount, edgeCount, exportedAt, dateRange) and `elements` (nodes, edges) in Cytoscape.js format.

> **See also:** [Full export schema and Cytoscape format](docs/schema/data-contracts.md)

## Entity Types

`Org` · `Person` · `Program` · `Tool` · `Model` · `Dataset` · `Benchmark` · `Paper` · `Repo` · `Tech` · `Topic` · `Event` · `Location` · `Document` · `Other`

Canonical ID format: `{type}:{slug}` (e.g., `org:openai`, `model:gpt-4`, `tech:transformer`)

## Relation Taxonomy

**Document:** MENTIONS, CITES, ANNOUNCES, REPORTED_BY

**Org / Person / Program:** LAUNCHED, PUBLISHED, UPDATED, FUNDED, PARTNERED_WITH, ACQUIRED, HIRED, CREATED, OPERATES, GOVERNED_BY/GOVERNS, REGULATES, COMPLIES_WITH

**Tech / Model / Tool / Dataset:** USES_TECH, USES_MODEL, USES_DATASET, TRAINED_ON, EVALUATED_ON, INTEGRATES_WITH, DEPENDS_ON, REQUIRES, PRODUCES, MEASURES, AFFECTS

**Forecasting:** PREDICTS, DETECTS, MONITORS

Prefer `MENTIONS` as the base layer; only emit semantic edges when evidence supports them.

> **See also:** [Canonical IDs, slugging rules, and relation taxonomy](AGENTS.md)

## Trend Signals

| Signal | Description |
|--------|-------------|
| `mention_count_7d` | Mentions in last 7 days |
| `mention_count_30d` | Mentions in last 30 days |
| `velocity` | Ratio of recent to previous mentions |
| `novelty` | Based on entity age and rarity |
| `bridge_score` | Cross-domain connectivity measure |

> **See also:** [Signal formulas, velocity/novelty/bridge scoring details](docs/methodology/prediction-methodology.md) · [Trend insights and templates](docs/research/trend-insights.md)

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

> **See also:** [UI walkthrough, visual encoding, screenshots](docs/product/README.md) · [Cytoscape client implementation guide](docs/ux/README.md) · [Cytoscape.js gotchas and fixes](docs/ux/troubleshooting.md) · [Dark mode implementation](docs/ux/dark-mode-implementation.md)

## Testing

```bash
make test              # Unit tests (no network, no LLM)
make test-network      # Network-dependent tests
make test-all          # Everything
```

~209 unit tests across 18 modules. Network and LLM tests are marked separately and excluded by default.

Markers: `network` (requires internet), `llm_live` (requires API key).

## Environment Variables

| Variable | Required For |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Mode A extraction via Claude |
| `OPENAI_API_KEY` | Mode A extraction via OpenAI |

No environment variables required for ingestion, manual import, or graph export.

## Deployment

CI/CD via GitHub Actions:
- **`deploy.yml`** — On push to `main` (or manual dispatch with branch selection): run tests → SSH deploy to VPS
- **`release.yml`** — On tag push (`v*`): run tests → create GitHub Release (detects pre-release from tag)

### Feed Configuration

Feeds are defined in `config/feeds.yaml`, organized by tier:

```yaml
feeds:
  - name: "arXiv CS.AI"
    url: "https://rss.arxiv.org/rss/cs.AI"
    type: rss
    tier: 1
    signal_type: primary
    enabled: true
```

**Tier model:** Primary (academic + industry blogs) → Secondary (aggregators) → Echo (tech press)

> **See also:** [Feed tier model, source selection strategy](docs/source-selection-strategy.md)

### Makefile Overrides

```bash
make daily DB=data/db/custom.db DATE=2026-03-01 BUDGET=10
```

## Documentation

> **New here?** Start with [docs/backend/workflow-guide.md](docs/backend/workflow-guide.md) for a step-by-step pipeline walkthrough, then [docs/architecture/convergence-narrative.md](docs/architecture/convergence-narrative.md) for the big-picture design decisions.

### Architecture & Methodology

| Document | Purpose |
|----------|---------|
| [Convergence Narrative](docs/architecture/convergence-narrative.md) | **Read first.** How 5 vectors converge; decision log |
| [Domain Separation](docs/architecture/domain-separation.md) | Framework vs. domain config boundary |
| [Multi-Domain Futures](docs/architecture/multi-domain-futures.md) | Post-V2 vision for other domains |
| [Date Filtering](docs/architecture/date-filtering.md) | Why published_at, 30-day window, NULL handling |
| [Prediction Methodology](docs/methodology/prediction-methodology.md) | Signal formulas, validation, weight tuning |
| [LLM Selection](docs/llm-selection.md) | Model tiers, escalation, shadow mode, cost model |

### Pipeline & Backend

| Document | Purpose |
|----------|---------|
| [Workflow Guide](docs/backend/workflow-guide.md) | Step-by-step Mode A and Mode B — **start here** |
| [Daily Run Log](docs/backend/daily-run-log.md) | Pipeline health monitoring, per-stage metrics |
| [Manual Workflow Plan](docs/backend/manual-workflow-plan.md) | Script specs for Mode B pipeline |
| [Source Selection](docs/source-selection-strategy.md) | Feed tier model, coverage targets |
| [Extract Quality](docs/research/extract-quality-analysis.md) | Quality gates, evaluation phases, calibration |
| [Trend Insights](docs/research/trend-insights.md) | Insight templates, deterministic vs LLM generation |

### UX & Visualization

| Document | Purpose |
|----------|---------|
| [Product Guide](docs/product/README.md) | UI walkthrough, visual encoding, workflows |
| [UX Implementation](docs/ux/README.md) | Cytoscape client technical specs |
| [Design Tokens](docs/ux/design-tokens.md) | Colors, spacing, typography |
| [Visual Encoding](docs/ux/visual-encoding.md) | Node/edge encoding rules |
| [Troubleshooting](docs/ux/troubleshooting.md) | Cytoscape.js gotchas and fixes |
| [Polish Strategy](docs/ux/polish-strategy.md) | Typography, toolbar, canvas, node depth |
| [Accessibility](docs/ux/accessibility.md) | A11y compliance |
| [Dark Mode](docs/ux/dark-mode-implementation.md) | Dark mode / theme toggle |

### Schema & Data

| Document | Purpose |
|----------|---------|
| [Data Contracts](docs/schema/data-contracts.md) | Full schemas: documents, docpack, extraction, export |
| [Glossary](GLOSSARY.md) | Terminology definitions |
| [Changelog](CHANGELOG.md) | Release history |

### Operations

| Document | Purpose |
|----------|---------|
| [Project Plan](docs/project-plan.md) | Sprint plan, model assignments, timeline |
| [Backlog](docs/backlog.md) | Known issues, prompt-tuning observations |
| [Fix Details](docs/fix-details/README.md) | Resolved production issues, root causes, lessons |

## License

*TBD*

## Contributing

*TBD*
