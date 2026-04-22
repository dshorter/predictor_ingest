# AGENTS.md — Project Instructions (Domain-Agnostic Trend Graph → Cytoscape.js)

## Mission
Build a small, reliable, **domain-agnostic** pipeline that:
1) ingests ~10–20 new sources per day per domain (web pages + RSS),
2) archives raw content + cleaned text with metadata (archive-first),
3) extracts **entities**, **relationships**, **dates**, and **domain concepts** into a structured dataset,
4) resolves/merges entities over time (incremental, not perfect on day 1),
5) exports Cytoscape.js-ready JSON (`elements`) for interactive graph exploration,
6) supports **two operating modes**:
   - **Mode A:** automated extraction via an LLM API (when an API key is available)
   - **Mode B:** semi-manual extraction via ChatGPT web copy/paste or file upload (when an API key is not available)

The end product is a growing knowledge graph that can reveal **emerging trends early**, using velocity/novelty/bridge signals.

### Active Domains
- **AI/ML** (`domains/ai/`) — the original domain, fully operational
- **Biosafety** (`domains/biosafety/`) — added 2026-03-07. Monitors Federal Select
  Agent Program, dual-use research, gain-of-function policy, BSL facility oversight,
  and global health security governance. Entity types include `SelectAgent`,
  `Facility`, `Regulation`.
- **Film** (`domains/film/`) — independent film production, screenwriting, festivals,
  and distribution. Entity types include `Production`, `Festival`, `Distributor`,
  `Agency`, `Fund`. **This is the current Makefile default (`DOMAIN ?= film`).**
- **Semiconductors** (`domains/semiconductors/`) — fab process, chip architecture,
  GPU/accelerator compute, supply chain, and policy. Entity types include `Fab`,
  `Chip`, `Architecture`, `ProcessNode`, `Packaging`, `Material`, `Policy`.

### Multi-Domain Architecture (completed Sprint 6 + 6B)
- Each domain is a directory under `domains/` with `domain.yaml`, `feeds.yaml`,
  `views.yaml`, `inference_rules.yaml` (optional), and `prompts/`
- `--domain <name>` CLI flag (or `PREDICTOR_DOMAIN` env var) selects the active domain
- The Makefile uses `DOMAIN ?= film`; override with `make <target> DOMAIN=<slug>`
- Databases are isolated: `data/db/{domain}.db`; exports land in
  `data/graphs/{domain}/{date}/` and publish to `web/data/graphs/live/{domain}/`
- Web client accepts `?domain=<slug>` URL parameter; `web/js/domain-switcher.js`
  holds the `KNOWN_DOMAINS` registry (single source of truth for domain enumeration)
- `domains/_template/` provides scaffolding for new domains
- Framework code (`src/`) is domain-agnostic — enforced by `tests/test_grep_audit.py`

## Non-goals (V1)
- Perfect "truth." We represent claims with provenance + confidence, and allow ambiguity.
- Full-scale distributed crawling.
- Heavy UI or backend. V1 is a thin static client + exported JSON.
- Deep NLP beyond extraction/resolution (we can iterate later).

---

## Core Principles

### Archive-first
Always store raw HTML, cleaned text, and metadata (URL, source, publish date, fetch date, content hash). Extraction can be re-run later as schemas improve.

### Provenance and auditability
Every non-trivial relationship must carry evidence: document(s), snippet (≤ ~200 chars), publish date, URL, extractor version, confidence score.

### Separate "asserted" vs "inferred" vs "hypothesis"
Never let inferred edges overwrite asserted edges. Inferred/hypothesis edges must be clearly labeled and toggleable in the UI.

### Incremental updates
Daily run appends new documents and claims; graph is updated incrementally. Avoid full rebuilds unless explicitly requested.

### Keep it simple for V1
Prefer plain Python + SQLite + JSONL. No complex infra required.

---

## Repository Layout
- `src/` — framework code, all domain-agnostic:
  - `config/`, `db/`, `schema/`, `util/` — infrastructure
  - `ingest/` — `rss.py`, `bluesky.py`, `reddit.py`, `dispatch.py`, `run_all.py`
  - `clean/` — readability + boilerplate removal
  - `doc_select/` — article scoring / pre-extraction selection
  - `extract/` — LLM prompt building, parsing, quality gates (`prompts.py`)
  - `resolve/` — entity canonicalization, alias merging (`disambiguate.py`)
  - `infer/` — rule-driven inferred edges (per-domain `inference_rules.yaml`)
  - `synthesize/` — cross-document synthesis (runs after extraction)
  - `graph/` — Cytoscape.js export (4 views)
  - `trend/` — velocity/novelty/bridge scoring, narrative generation (`narratives.py`)
  - `domain/` — domain profile loader
- `domains/` — one directory per domain:
  - `domains/ai/`, `domains/biosafety/`, `domains/film/`, `domains/semiconductors/`
  - `domains/_template/` — scaffolding for new domains
  - Each contains `domain.yaml`, `feeds.yaml`, `views.yaml`, `inference_rules.yaml`
    (optional), and `prompts/` (`system.txt`, `user.txt`, `single_message.txt`,
    `disambiguate_system.txt`, `narrative_system.txt`, `synthesis_system.txt`)
- `config/` — legacy feed config (superseded by per-domain `feeds.yaml`)
- `data/` (gitignored) — `raw/`, `text/`, `docpacks/`, `extractions/`, `graphs/`, `db/`
  — all keyed by domain slug (e.g., `data/db/film.db`, `data/graphs/ai/2026-04-22/`)
- `schemas/` — `domain-profile.json`, `extraction.json`, `sqlite.sql`
- `scripts/` — pipeline orchestration and diagnostics (see Developer Workflow below)
- `tests/` — pytest tests; markers: `network`, `llm_live`. Includes
  `test_grep_audit.py` which enforces the domain-agnostic boundary in `src/`.
- `web/` — static Cytoscape.js client (desktop `index.html`, `dashboard.html`,
  `ontology.html`, `mobile/index.html`); domain-aware via `?domain=<slug>`
- `calendar/`, `diagnostics/` — operational artifacts (calendar events, log dumps)

---

## Data Contracts

Full schemas for documents, docpacks, extraction JSON, and Cytoscape export format: **[docs/schema/data-contracts.md](docs/schema/data-contracts.md)**

Key points:
- Documents table uses `status` field: `cleaned` → `extracted` → (via import)
- Extraction output: `{docId, extractorVersion, entities[], relations[], techTerms[], dates[]}`
- Graph export: `{meta: {view, nodeCount, edgeCount, exportedAt, dateRange}, elements: {nodes[], edges[]}}`
- Four graph views: `mentions.json`, `claims.json`, `dependencies.json`, `trending.json`

---

## Canonical IDs
Stable IDs for graph nodes: `doc:{docId}`, `org:{slug}`, `person:{slug}`, `tool:{slug}`, `model:{slug}`, `dataset:{slug}`, `paper:{slug}`, `repo:{slug}`, `tech:{slug}`, `topic:{slug}`, `benchmark:{slug}`

Slug rules: lowercase, alphanumerics + `_`, strip punctuation, keep short.

Entity resolution updates canonical IDs; backrefs preserved via `aliases` and `entity_aliases(alias TEXT PK, canonical_id TEXT NOT NULL)`.

---

## Node Types (V1 enum)
`Org`, `Person`, `Program`, `Tool`, `Model`, `Dataset`, `Benchmark`, `Paper`, `Repo`, `Document`, `Tech`, `Topic`, `Event`, `Location`, `Other`

---

## Relation Taxonomy (V1)

Document: `MENTIONS`, `CITES`, `ANNOUNCES`, `REPORTED_BY`

Org/Person/Program: `LAUNCHED`, `PUBLISHED`, `UPDATED`, `FUNDED`, `PARTNERED_WITH`, `ACQUIRED`, `HIRED`, `CREATED`, `OPERATES`, `GOVERNED_BY`/`GOVERNS`, `REGULATES`, `COMPLIES_WITH`

Tech/Model/Tool/Dataset: `USES_TECH`, `USES_MODEL`, `USES_DATASET`, `TRAINED_ON`, `EVALUATED_ON`, `INTEGRATES_WITH`, `DEPENDS_ON`, `REQUIRES`, `PRODUCES`, `MEASURES`, `AFFECTS`

Forecasting: `PREDICTS`, `DETECTS`, `MONITORS`

Prefer `MENTIONS` as base layer; only emit semantic edges when evidence supports them. Keep `COMPETES_WITH` and `REPLACES` as inferred/hypothesis unless explicitly stated.

---

## LLM Extraction Rules (critical)
1) Asserted relations MUST include evidence (snippet + docId).
2) Do not fabricate entities, dates, or relations.
3) If ambiguous, add `notes[]` and mark relation as `hypothesis` or omit it.
4) Convert verbs to canonical `rel`; preserve original as `verbRaw`.
5) Extract technology nouns as `Tech` nodes (or `techTerms[]`) and connect via `USES_TECH` when supported.
6) Keep evidence snippets short (≤ ~200 chars).
7) For dates: keep raw `text` always; normalize `start/end` when safe.

---

## Modes of Operation

### Mode A — Anthropic Batch API (current default; ADR-008)
Since 2026-03-25 (Sprint 9), Mode A uses the Anthropic Batch API instead of the
prior two-tier escalation scheme. The batch pipeline is:
1. `make docpack` — build JSONL from docs with `status='cleaned'`
2. `make submit` — submit batch to Anthropic Batch API, persist `batch_id`
3. `make collect` — poll and collect completed results into `data/extractions/{domain}/`
4. `make import` → `resolve` → `export` → `trending` → `copy-to-live`

`make daily` runs the full sequence for a domain. `make backlog` chunk-submits any
docs that were missed on prior runs. See
[docs/architecture/adr-008-batch-api-extraction.md](docs/architecture/adr-008-batch-api-extraction.md).

### Mode B — No API key (manual)
1) `make docpack` produces JSONL + MD bundle.
2) Paste/upload into ChatGPT web and request extraction in schema.
3) Save returned JSON under `data/extractions/{domain}/`.
4) `make import` validates and stores. Then run `make daily-manual` (skips extract).

Downstream steps (`resolve`, `export`, `trending`) do not care whether extractions
came from the batch API or manual workflow.

### Synthesis + Narratives
After extraction, `run_synthesize.py` runs per-domain synthesis (summarization /
cross-doc reasoning), and `run_trending.py --narratives` generates trending
narratives. These use the cheaper `NARRATIVE_MODEL` (default
`claude-haiku-4-5-20251001`); the primary extraction model is `PRIMARY_MODEL`
(default `claude-sonnet-4-6`).

---

## Trend Scoring (V1)
Compute lightweight signals daily: `mention_count_7d`, `mention_count_30d`, `velocity` (ratio or delta), `novelty` (days since firstSeen + rarity proxy), `bridge_delta` (optional). Use these to build `trending.json` view.

---

## Cytoscape Client (web/)

Thin static Cytoscape.js client for interactive graph exploration. Nodes maintain stable positions over time so emerging clusters and cross-domain bridges are visually apparent.

See **[docs/ux/README.md](docs/ux/README.md)** for the full implementation spec and **[docs/ux/troubleshooting.md](docs/ux/troubleshooting.md)** for Cytoscape.js gotchas.

### Cytoscape.js Gotchas (critical for any UI work)

1. **No CSS pseudo-selectors.** Use JS events to add/remove classes (e.g., `.hover`). Only `:selected`, `:active`, `:grabbed` work natively.
2. **Colon-safe ID lookups.** Use `cy.getElementById('org:openai')`, never `cy.$('#org:openai')` (colon breaks CSS selector parsing).
3. **Manual `cy.resize()` after container changes.** Call with `setTimeout(~50ms)` after toggling panels.
4. **fcose needs CDN sub-dependencies.** Load `layout-base` → `cose-base` → `cytoscape-fcose` in order, or fcose silently fails.
5. **Separate CSS classes for separate dimming contexts.** Search uses `.dimmed`; neighborhood highlighting uses `.neighborhood-dimmed`.

---

## Quality Bar
- Validate every extraction/export against JSON Schemas.
- **Extraction quality gates** (CPU, zero tokens) run before scoring on every extraction:
  - Evidence fidelity: snippet must exist in source text (≥70%)
  - Orphan endpoints: relation source/target must match an entity (0% tolerance)
  - Zero-value: non-trivial docs must produce ≥1 entity
  - High-confidence + bad evidence: immediate escalation
- Unit tests for: slugging + ID rules, date parsing, schema validation, export correctness, quality gates.
- Quality metrics logged to `quality_runs`/`quality_metrics` tables for calibration.
- Log errors; never silently drop docs.

---

## Safety / Legal / Scraping Policy
- Polite: clear User-Agent, rate-limit, cache. Respect robots.txt.
- Avoid paywalled/restricted content. No PII/PHI collection beyond public pages.
- Store only what is needed for analysis and provenance.

---

## Developer Workflow

```bash
pip install -e .
cp .env.example .env                                # Fill in ANTHROPIC_API_KEY

# Default domain is `film` (see Makefile `DOMAIN ?= film`).
# Override with DOMAIN=<slug> for any target:
make daily                                          # Full pipeline (film)
make daily DOMAIN=ai
make daily DOMAIN=biosafety
make daily DOMAIN=semiconductors

# Pipeline stages (per domain)
make ingest                                         # RSS/social ingestion
make docpack                                        # Build JSONL bundles
make submit                                         # Submit batch to Anthropic
make collect                                        # Collect completed batch
make backlog                                        # Submit any missed docs
make import                                         # Import extractions
make resolve                                        # Entity resolution
make export                                         # Cytoscape view export
make trending                                       # Trend scores + narratives
make copy-to-live                                   # Publish to web/data/graphs/live/

# Diagnostics & health
make health-report                                  # Pipeline health
make dashboard-data                                 # Dashboard JSON
make calibration-report                             # 7-day quality calibration
make export_ontology                                # Regenerate ontology JSON
python scripts/diagnose_feeds.py                    # Debug feed dedup
python scripts/wipe_domain_data.py --domain <slug>  # Reset a domain (dry-run default)

# Testing
make test                                           # Unit tests (no network, no LLM)
make test-network                                   # Network-dependent tests
make test-all                                       # Everything
pytest tests/ -m "not network and not llm_live"     # Equivalent to `make test`
```

See **[docs/backend/workflow-guide.md](docs/backend/workflow-guide.md)** for the complete step-by-step guide.
See **[docs/backend/operational-state.md](docs/backend/operational-state.md)** for current extraction mode, gate overrides, and env requirements per domain.

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Required for Mode A (batch API extraction + synthesis + narratives) |
| `PRIMARY_MODEL` | Primary extraction / synthesis model (default: `claude-sonnet-4-6`) |
| `NARRATIVE_MODEL` | Trending-narrative model (default: `claude-haiku-4-5-20251001`) |
| `UNDERSTUDY_MODEL` | Shadow-mode comparison model (default: `gpt-5-nano`) |
| `OPENAI_API_KEY` | Required only if `UNDERSTUDY_MODEL` is an OpenAI model |
| `PREDICTOR_DOMAIN` | Default domain if `--domain` / `DOMAIN=` is omitted |
| `BSKY_HANDLE` | Optional — Bluesky handle for social ingestion |

### Web Tests (Playwright)

```bash
npm install                                         # One-time: install Playwright
npx playwright test tests/web/smoke.spec.js --config=tests/web/playwright.config.js --reporter=list
```

Tests use a **self-contained HTML harness** with a Cytoscape mock — no CDN or network needed. Real app JS modules are loaded against mock graph data. See **[docs/testing/playwright-guide.md](docs/testing/playwright-guide.md)** for the full architecture and troubleshooting.

---

## Sources

Runtime configuration lives per-domain at `domains/<slug>/feeds.yaml` (the
top-level `config/feeds.yaml` is legacy). See
**[docs/source-selection-strategy.md](docs/source-selection-strategy.md)** for the
tier model and expansion strategy.

Ingestion supports three fetcher types, dispatched by `src/ingest/dispatch.py`:
- `rss` — RSS/Atom feeds (`src/ingest/rss.py`)
- `bluesky` — Bluesky posts (`src/ingest/bluesky.py`; requires `BSKY_HANDLE`)
- `reddit` — Reddit (`src/ingest/reddit.py`)

Example core sources by domain:
- **AI** — arXiv CS.AI, Hugging Face Blog, Anthropic/Google AI, TechCrunch,
  Ars Technica, The Verge, Simon Willison, Interconnects
- **Film** — Deadline, Variety, IndieWire, No Film School, John August
- **Semiconductors** — technical trade press, deep-analysis newsletters,
  practitioner community blogs
- **Biosafety** — Federal Register, CDC, WHO, GHSA, domain-specialist newsletters

---

## Architecture

### Domain Separation

The pipeline is split into a **domain-independent framework** (scoring, validation,
export, resolution) and **domain-specific configuration** (entity types, relation
taxonomy, sources, extraction prompts). This separation is intentional and must be
preserved. See **[docs/architecture/domain-separation.md](docs/architecture/domain-separation.md)**
for the boundary definition and enforcement rules.

### Key Documentation

#### Methodology & Architecture

| Document | Purpose |
|----------|---------|
| [docs/methodology/prediction-methodology.md](docs/methodology/prediction-methodology.md) | Signal distillation formulas, source requirements, validation framework, weight tuning protocol |
| [docs/methodology/semiconductor-domain-design.md](docs/methodology/semiconductor-domain-design.md) | Semiconductor domain design rationale, entity coverage targets |
| [docs/methodology/domain-fit-analysis.md](docs/methodology/domain-fit-analysis.md) | How well each candidate domain fits the framework |
| [docs/architecture/domain-separation.md](docs/architecture/domain-separation.md) | Boundary between framework and domain config; rules for what goes where |
| [docs/architecture/multi-domain-futures.md](docs/architecture/multi-domain-futures.md) | Post-V2 vision for applying the framework to other domains |
| [docs/architecture/date-filtering.md](docs/architecture/date-filtering.md) | Why published_at (not fetched_at) is used for filtering; 30-day default window; NULL handling |
| [docs/architecture/convergence-narrative.md](docs/architecture/convergence-narrative.md) | **Read first for big picture.** How 5 vectors (insights, sources, cost spectrum, plugin arch, connectors) converge mid-March; decision log |
| [docs/architecture/adr-005-regional-lens.md](docs/architecture/adr-005-regional-lens.md) | ADR-005: Regional-lens filtering |
| [docs/architecture/adr-006-chatter-sources.md](docs/architecture/adr-006-chatter-sources.md) | ADR-006: Chatter sources (Bluesky, Reddit) |
| [docs/architecture/adr-007-llm-leverage-features.md](docs/architecture/adr-007-llm-leverage-features.md) | ADR-007: LLM leverage features |
| [docs/architecture/adr-008-batch-api-extraction.md](docs/architecture/adr-008-batch-api-extraction.md) | **ADR-008: Replace two-tier escalation with Anthropic Batch API (current extraction mode)** |
| [docs/architecture/adr-009-unified-left-panel-slot.md](docs/architecture/adr-009-unified-left-panel-slot.md) | ADR-009: Unified left-panel slot (UI) |

#### Pipeline & Backend

| Document | Purpose |
|----------|---------|
| [docs/backend/operational-state.md](docs/backend/operational-state.md) | **Current extraction mode, gate config, and model for each domain. Read first when resuming work.** |
| [docs/backend/workflow-guide.md](docs/backend/workflow-guide.md) | Step-by-step guide for running the full pipeline (Mode A and Mode B) |
| [docs/backend/article-selection-scoring.md](docs/backend/article-selection-scoring.md) | Pre-extraction scoring signals, weights, bench backfill, thresholds, and change log |
| [docs/backend/calibration-report.md](docs/backend/calibration-report.md) | 7-day calibration report: gate pass rates, quality drift, suggested threshold moves |
| [docs/backend/daily-run-log.md](docs/backend/daily-run-log.md) | Pipeline health monitoring: JSON log format, per-stage metrics, healthy thresholds |
| [docs/backend/manual-workflow-plan.md](docs/backend/manual-workflow-plan.md) | Backend pipeline script specs (build_docpack, import, resolve, export, trending) |
| [docs/backend/automated-setup.md](docs/backend/automated-setup.md) | Deployment + cron setup on VPS |
| [docs/llm-selection.md](docs/llm-selection.md) | LLM model tiers, batch API architecture, shadow mode, cost model, quality scoring weights |
| [docs/source-selection-strategy.md](docs/source-selection-strategy.md) | Feed tier model (primary/secondary/echo), entity overlap strategy, coverage targets |
| [docs/guides/new-domain-features.md](docs/guides/new-domain-features.md) | How to onboard a new domain from `domains/_template/` |
| [docs/research/extract-quality-analysis.md](docs/research/extract-quality-analysis.md) | Quality gate design, evaluation architecture (Phase 0–4), calibration plan, CPU vs LLM cost matrix |
| [docs/research/trend-insights.md](docs/research/trend-insights.md) | Insight articulation layer: templates, categories, deterministic vs LLM generation, backtest protocol |

#### UX & Visualization

| Document | Purpose |
|----------|---------|
| [docs/ux/README.md](docs/ux/README.md) | Cytoscape client implementation guidelines |
| [docs/ux/troubleshooting.md](docs/ux/troubleshooting.md) | Cytoscape.js gotchas and fixes |
| [docs/ux/polish-strategy.md](docs/ux/polish-strategy.md) | Aesthetic mechanics: typography, toolbar, canvas, node depth |
| [docs/ux/delight-backlog.md](docs/ux/delight-backlog.md) | Engagement & discovery: What's Hot, guided entry, visual reward. Desktop-first. |
| [docs/ux/guided-tour-spec.md](docs/ux/guided-tour-spec.md) | Driver.js guided tour: 8 stops, sample data plan, post-tour sandbox experience |

#### Testing

| Document | Purpose |
|----------|---------|
| [docs/testing/playwright-guide.md](docs/testing/playwright-guide.md) | **Playwright web tests: self-contained harness, Cytoscape mock, fixture data, troubleshooting. Read before writing new web tests.** |
| [docs/test-plan.md](docs/test-plan.md) | Manual QA checklist per sprint |

#### Web Pages & Tools

| Page / Script | Purpose |
|---------------|---------|
| `web/index.html` | Main desktop graph explorer |
| `web/mobile.html` | Mobile-adapted graph explorer |
| `web/dashboard.html` | Pipeline health monitoring dashboard |
| `web/ontology.html` | Specialist-facing taxonomy/ontology reference |
| `web/js/domain-switcher.js` | Domain dropdown + "About this Domain" modal; `KNOWN_DOMAINS` registry is single source of truth for domain enumeration |
| `scripts/export_ontology.py` | Generates ontology JSON from domain profiles (`make export_ontology`) |
| `scripts/generate_dashboard_json.py` | Generates dashboard data from pipeline logs |
| `scripts/wipe_domain_data.py` | Safely resets all pipeline data for a domain (dry-run by default) |

#### Schema & Data

| Document | Purpose |
|----------|---------|
| [docs/schema/data-contracts.md](docs/schema/data-contracts.md) | Full schemas: documents table, docpack JSONL, extraction JSON, Cytoscape export |

#### Operational History

| Document | Purpose |
|----------|---------|
| [docs/fix-details/README.md](docs/fix-details/README.md) | Index of resolved production issues with root causes and lessons learned |
| [docs/backlog.md](docs/backlog.md) | Known issues and prompt-tuning observations awaiting action |
| [docs/project-plan.md](docs/project-plan.md) | Unified sprint plan across all backlogs, stability-ordered, with model assignments and timeline |

---

## Backlog (post-V1 ideas)
- Persist node positions (`preset` layout) for stability across days
- Add "follow-up query" generation for hypothesis edges (2-hop research discipline)
- Better entity resolution (Wikidata IDs for high-degree nodes)
- Community detection + clustering views
- Source-type enrichment (paper/repo/hiring/product changelog) for earlier weak signals

Multi-domain support is complete (Sprint 6 + 6B). Four domains are live: AI,
Biosafety, Film, Semiconductors. See
[docs/architecture/multi-domain-futures.md](docs/architecture/multi-domain-futures.md)
for the post-V2 vision.
