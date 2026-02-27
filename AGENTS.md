# AGENTS.md — Project Instructions (AI Trend Graph → Cytoscape.js)

## Mission
Build a small, reliable pipeline that:
1) ingests ~10–20 new AI-related sources per day (web pages + RSS),
2) archives raw content + cleaned text with metadata (archive-first),
3) extracts **entities**, **relationships**, **dates**, and **technology concepts** into a structured dataset,
4) resolves/merges entities over time (incremental, not perfect on day 1),
5) exports Cytoscape.js-ready JSON (`elements`) for interactive graph exploration,
6) supports **two operating modes**:
   - **Mode A:** automated extraction via an LLM API (when an API key is available)
   - **Mode B:** semi-manual extraction via ChatGPT web copy/paste or file upload (when an API key is not available)

The end product is a growing knowledge graph that can reveal **emerging trends early**, using velocity/novelty/bridge signals.

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
- `src/` — `config/`, `db/`, `schema/`, `ingest/`, `extract/`, `util/`, `clean/`, `resolve/`, `graph/`, `trend/`
- `config/feeds.yaml` — RSS feed definitions
- `data/` (gitignored) — `raw/`, `text/`, `docpacks/`, `extractions/`, `graphs/`, `db/`
- `schemas/` — `extraction.json` (JSON Schema), `sqlite.sql` (DB schema)
- `scripts/` — pipeline orchestration and helper scripts
- `tests/` — pytest tests; network tests marked with `@pytest.mark.network`
- `web/` — thin Cytoscape.js client (static site)

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

### Mode A — LLM API available
- `make extract` calls an LLM with strict JSON output.
- Validate output with JSON Schema.

### Mode B — No API key (manual)
1) `make docpack` produces JSONL + MD bundle.
2) Paste/upload into ChatGPT web and request extraction in schema.
3) Save returned JSON under `data/extractions/`.
4) `make import_manual` validates and stores.

Downstream steps (`resolve`, `export`) must not care whether extractions came from API or manual.

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
python -m ingest.rss --config config/feeds.yaml    # RSS ingestion
python scripts/run_pipeline.py                      # Full daily pipeline
pytest tests/ -m "not network"                      # Unit tests
python scripts/diagnose_feeds.py                    # Debug feed dedup
```

See **[docs/backend/workflow-guide.md](docs/backend/workflow-guide.md)** for the complete step-by-step guide.

---

## Sources (V1)

Runtime configuration in `config/feeds.yaml`. See **[docs/source-selection-strategy.md](docs/source-selection-strategy.md)** for tier model and expansion strategy.

Core sources: arXiv CS.AI (academic), Hugging Face Blog (open-source), Anthropic/Google AI (industry), TechCrunch/Ars Technica/The Verge (echo/velocity), Simon Willison/Interconnects (community).

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
| [docs/architecture/domain-separation.md](docs/architecture/domain-separation.md) | Boundary between framework and domain config; rules for what goes where |
| [docs/architecture/multi-domain-futures.md](docs/architecture/multi-domain-futures.md) | Post-V2 vision for applying the framework to other domains |
| [docs/architecture/date-filtering.md](docs/architecture/date-filtering.md) | Why published_at (not fetched_at) is used for filtering; 30-day default window; NULL handling |

#### Pipeline & Backend

| Document | Purpose |
|----------|---------|
| [docs/backend/workflow-guide.md](docs/backend/workflow-guide.md) | Step-by-step guide for running the full pipeline (Mode A and Mode B) |
| [docs/backend/daily-run-log.md](docs/backend/daily-run-log.md) | Pipeline health monitoring: JSON log format, per-stage metrics, healthy thresholds |
| [docs/backend/manual-workflow-plan.md](docs/backend/manual-workflow-plan.md) | Backend pipeline script specs (build_docpack, import, resolve, export, trending) |
| [docs/llm-selection.md](docs/llm-selection.md) | LLM model tiers, escalation mode architecture, shadow mode, cost model, quality scoring weights |
| [docs/source-selection-strategy.md](docs/source-selection-strategy.md) | Feed tier model (primary/secondary/echo), entity overlap strategy, coverage targets |
| [docs/research/extract-quality-analysis.md](docs/research/extract-quality-analysis.md) | Quality gate design, evaluation architecture (Phase 0–4), calibration plan, CPU vs LLM cost matrix |

#### UX & Visualization

| Document | Purpose |
|----------|---------|
| [docs/ux/README.md](docs/ux/README.md) | Cytoscape client implementation guidelines |
| [docs/ux/troubleshooting.md](docs/ux/troubleshooting.md) | Cytoscape.js gotchas and fixes |
| [docs/ux/polish-strategy.md](docs/ux/polish-strategy.md) | Aesthetic mechanics: typography, toolbar, canvas, node depth |
| [docs/ux/delight-backlog.md](docs/ux/delight-backlog.md) | Engagement & discovery: What's Hot, guided entry, visual reward. Desktop-first. |

#### Schema & Data

| Document | Purpose |
|----------|---------|
| [docs/schema/data-contracts.md](docs/schema/data-contracts.md) | Full schemas: documents table, docpack JSONL, extraction JSON, Cytoscape export |

#### Operational History

| Document | Purpose |
|----------|---------|
| [docs/fix-details/README.md](docs/fix-details/README.md) | Index of resolved production issues with root causes and lessons learned |
| [docs/backlog.md](docs/backlog.md) | Known issues and prompt-tuning observations awaiting action |

---

## Backlog (post-V1 ideas)
- Persist node positions (`preset` layout) for stability across days
- Add "follow-up query" generation for hypothesis edges (2-hop research discipline)
- Better entity resolution (Wikidata IDs for high-degree nodes)
- Community detection + clustering views
- Source-type enrichment (paper/repo/hiring/product changelog) for earlier weak signals
- Multi-domain support (see [docs/architecture/multi-domain-futures.md](docs/architecture/multi-domain-futures.md))
