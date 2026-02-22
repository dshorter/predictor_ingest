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
- Perfect “truth.” We represent claims with provenance + confidence, and allow ambiguity.
- Full-scale distributed crawling.
- Heavy UI or backend. V1 is a thin static client + exported JSON.
- Deep NLP beyond extraction/resolution (we can iterate later).

---

## Core Principles

### Archive-first
Always store:
- raw HTML (or feed XML item data)
- cleaned text
- metadata (URL, source, publish date, fetch date, content hash)

Extraction can be re-run later as schemas improve.

### Provenance and auditability
Every non-trivial relationship must carry evidence:
- which document(s)
- the evidence span/snippet (≤ ~200 chars preferred)
- publish date and URL
- extractor version
- confidence score

### Separate “asserted” vs “inferred” vs “hypothesis”
We will never let inferred edges overwrite asserted edges.
Inferred/hypothesis edges must be clearly labeled and toggleable in the UI.

### Incremental updates
Daily run appends new documents and claims; graph is updated incrementally.
Avoid full rebuilds unless explicitly requested.

### Keep it simple for V1
Prefer plain Python + SQLite + JSONL. No complex infra required.

---

## Repository Layout (recommended)
- `src/`
  - `config/` (feed config loader, FeedConfig dataclass)
  - `db/` (database operations: entities, relations, evidence)
  - `schema/` (JSON Schema validation for extractions)
  - `ingest/` (RSS + web fetching CLI)
  - `extract/` (LLM prompts + parsing + validation)
  - `util/` (hashing, slugify, date parsing, HTML cleaning)
  - `clean/` (readability extraction, boilerplate removal, metadata extraction)
  - `resolve/` (entity resolution, similarity matching, alias merging)
  - `graph/` (Cytoscape export: mentions, claims, dependencies views)
  - `trend/` (velocity, novelty, bridge scoring; trending export)
- `config/` (runtime YAML configs)
  - `feeds.yaml` (RSS feed definitions)
- `data/` (gitignored)
  - `raw/` (raw HTML, raw feed snapshots)
  - `text/` (cleaned plain text)
  - `docpacks/` (daily bundles JSONL/MD)
  - `extractions/` (per-doc extracted JSON)
  - `graphs/` (exports for Cytoscape client)
  - `db/` (SQLite)
- `schemas/` (JSON Schema + SQLite schema)
  - `extraction.json` (JSON Schema for extraction output)
  - `sqlite.sql` (database schema)
- `scripts/` (helper scripts)
  - `run_network_tests.py` (local network test runner)
- `tests/` (pytest tests, network tests marked with `@pytest.mark.network`)
- `web/` (thin Cytoscape.js client; static site) *[planned]*
- `Makefile` *[planned]*
- `README.md`

---

## Data Contracts

### 1) Document record (SQLite)
**Table:** `documents`

- `doc_id` TEXT PRIMARY KEY
- `url` TEXT
- `source` TEXT (publisher or feed name)
- `title` TEXT
- `published_at` TEXT (ISO-8601 date or datetime; may be NULL if unknown)
- `fetched_at` TEXT (ISO-8601 datetime)
- `raw_path` TEXT
- `text_path` TEXT
- `content_hash` TEXT (hash of cleaned text)
- `status` TEXT (e.g., `fetched`, `cleaned`, `extracted`, `error`)
- `error` TEXT (nullable)

### 2) DocPack (daily bundle) — JSONL
One JSON object per line. Minimal fields:

```json
{
  "docId": "2025-12-01_nextgov_409826",
  "url": "https://…",
  "source": "Nextgov",
  "title": "CDC placed early bets on AI…",
  "published": "2025-12-01",
  "fetched": "2026-01-21T07:12:00Z",
  "text": "cleaned article text…"
}
```

Also generate `daily_bundle_YYYY-MM-DD.md` for “paste into ChatGPT” workflows.

### 3) Extraction Output — per document JSON
Write to `data/extractions/{docId}.json`.

Top-level:
- `docId` (string)
- `extractorVersion` (string; bump when prompts/schema changes)
- `entities` (list)
- `relations` (list)
- `techTerms` (list)
- `dates` (list)
- `notes` (list; optional warnings, ambiguity flags)

Entity object:
- `name` (string; surface form)
- `type` (enum; see Node Types)
- `aliases` (list[string], optional)
- `externalIds` (object, optional) e.g. `{"wikidata":"Q123"}`
- `idHint` (string, optional; if model suggests canonical id)

Relation object:
- `source` (string; entity name or idHint)
- `rel` (enum; canonical relation taxonomy below)
- `target` (string)
- `kind` (enum: `asserted` | `inferred` | `hypothesis`)
- `confidence` (float 0..1)
- `verbRaw` (string; as in text, optional)
- `polarity` (`pos` | `neg` | `unclear`, optional)
- `modality` (`observed` | `planned` | `speculative`, optional)
- `time` (object, optional; see Date model)
- `evidence` (list[Evidence]; MUST be non-empty for asserted edges)

Evidence object:
- `docId` (string)
- `url` (string)
- `published` (string ISO date/datetime or null)
- `snippet` (string; short quote/paraphrase)
- `charSpan` (object optional) `{ "start": 1234, "end": 1302 }`

Date model:
- Always keep raw: `text` (e.g., `"this fall"`)
- Normalize when possible:
  - `start` / `end` (ISO date)
  - `resolution` (e.g., `exact`, `range`, `anchored_to_published`, `unknown`)
  - `anchor` (e.g., published date used for “this fall”)

### 4) Cytoscape.js Export — `elements`
Write to `data/graphs/{date}/{view}.json`.

Views:
- `mentions.json` — Document ↔ Entity mentions
- `claims.json` — Semantic entity-to-entity relations
- `dependencies.json` — Dependency-only relations (`USES_*`, `DEPENDS_ON`, `REQUIRES`, etc.)
- `trending.json` — Filtered to high-velocity/high-novelty edges/nodes

Cytoscape format:

```json
{
  "elements": {
    "nodes": [
      {
        "data": {
          "id": "org:cdc",
          "label": "CDC",
          "type": "Org",
          "aliases": ["Centers for Disease Control and Prevention"],
          "firstSeen": "2025-12-01",
          "lastSeen": "2026-01-21"
        }
      }
    ],
    "edges": [
      {
        "data": {
          "id": "e:doc:2025-12-01_nextgov_409826->org:cdc",
          "source": "doc:2025-12-01_nextgov_409826",
          "target": "org:cdc",
          "rel": "MENTIONS",
          "kind": "asserted",
          "confidence": 1.0
        }
      }
    ]
  }
}
```

---

## Canonical IDs
We use stable IDs for graph nodes:
- `doc:{docId}`
- `org:{slug}`
- `person:{slug}`
- `tool:{slug}`
- `model:{slug}`
- `dataset:{slug}`
- `paper:{slug}` (or DOI-based)
- `repo:{slug}` (or URL-hash)
- `tech:{slug}`
- `topic:{slug}`
- `benchmark:{slug}`

Slug rules:
- lowercase
- alphanumerics + `_`
- strip punctuation
- keep short

Entity resolution can update canonical IDs; preserve backrefs via `aliases` and a mapping table:
- `entity_aliases(alias TEXT PRIMARY KEY, canonical_id TEXT NOT NULL)`

---

## Node Types (V1 enum)
- `Org`
- `Person`
- `Program`
- `Tool`
- `Model`
- `Dataset`
- `Benchmark`
- `Paper`
- `Repo`
- `Document`
- `Tech`
- `Topic`
- `Event`
- `Location`
- `Other`

---

## Relation Taxonomy (V1)
Keep canonical relations limited and stable.

Document relations:
- `MENTIONS`
- `CITES`
- `ANNOUNCES` (doc announces a thing)
- `REPORTED_BY` (optional)

Org/Person/Program:
- `LAUNCHED`
- `PUBLISHED`
- `UPDATED`
- `FUNDED`
- `PARTNERED_WITH`
- `ACQUIRED`
- `HIRED`
- `CREATED`
- `OPERATES`
- `GOVERNED_BY` (or `GOVERNS`)
- `REGULATES`
- `COMPLIES_WITH`

Tech/Model/Tool/Dataset:
- `USES_TECH`
- `USES_MODEL`
- `USES_DATASET`
- `TRAINED_ON`
- `EVALUATED_ON`
- `INTEGRATES_WITH`
- `DEPENDS_ON`
- `REQUIRES` (e.g., compute/hardware)
- `PRODUCES`
- `MEASURES` (benchmarks measure models)
- `AFFECTS` (optional; prefer inference/hypothesis)

Forecasting & detection:
- `PREDICTS`
- `DETECTS`
- `MONITORS`

Notes:
- Prefer `MENTIONS` as a base layer; only emit semantic edges when evidence supports them.
- Keep “COMPETES_WITH” and “REPLACES” as inferred/hypothesis unless explicitly stated.

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
Compute lightweight signals daily:
- `mention_count_7d`, `mention_count_30d`
- `velocity` (ratio or delta)
- `novelty` (days since firstSeen + rarity proxy)
- `bridge_delta` (optional)

Use these to build `trending.json` view.

---

## Cytoscape Client (web/)

A thin static Cytoscape.js client for interactive graph exploration. The graph serves as a **living map with geographic memory**—nodes maintain stable positions over time so that emerging clusters, declining topics, and cross-domain bridges become visually apparent.

### Quick Reference

- Static site (no backend required in V1)
- Loads `graphs/{date}/{view}.json`
- Default view: `trending.json` (not full graph)
- Four views: `trending`, `claims`, `mentions`, `dependencies`

### Core Features (V1)

| Feature | Description |
|---------|-------------|
| Search | Filter nodes by label/alias; highlight matches |
| Filter panel | Date range, entity types, relationship kinds, confidence threshold |
| Kind toggles | Show/hide asserted, inferred, hypothesis edges |
| Neighborhood highlight | Click node → dims non-neighbors; hover is tooltip-only |
| Node detail panel | Full metadata, relationships, source documents |
| Evidence panel | Click edge → view provenance with snippets and links |
| Zoom/pan/fit | Standard navigation; re-run layout button |

### Visual Encoding Summary

| Element | Encoding |
|---------|----------|
| Node size | Velocity (acceleration) + recency boost |
| Node color | Entity type (Org=blue, Model=violet, etc.) |
| Node opacity | Recency (fades as lastSeen ages) |
| Neighborhood highlight | Click node → neighbors stay visible, rest dims (opacity 0.15) |
| Edge style | Kind: solid=asserted, dashed=inferred, dotted=hypothesis |
| Edge thickness | Confidence score (0.5px to 4px) |
| Edge color | Gray default; green for new edges (<7 days) |

### Layout Strategy

| Version | Approach |
|---------|----------|
| V1 | Force-directed on each load (fcose algorithm) |
| V2 | Preset layout from stored positions; force-directed optional |

V2 position storage enables:
- Instant, stable rendering
- Geographic memory (conceptual drift is spatially visible)
- Time-lapse animation

### Detailed Specification

See **[docs/ux/README.md](docs/ux/README.md)** for comprehensive implementation guidelines. For common issues and fixes, see **[docs/ux/troubleshooting.md](docs/ux/troubleshooting.md)**.

Implementation guidelines include:

- Node and edge visual encoding (formulas, full color palette with hex codes)
- Label visibility rules and collision detection
- Interaction patterns (click, hover, drag, context menu)
- Tooltip content and styling
- Search and filter implementation (`GraphFilter` class)
- Progressive disclosure (overview → explore → detail → evidence)
- Layout algorithms and position storage format
- Temporal features (V1 filtering, V2 time-lapse animation)
- Toolbar and global controls
- Performance thresholds and optimizations
- Accessibility (keyboard navigation, screen reader, colorblind mode)
- Complete V1 vs V2 feature matrix
- Recommended file structure and dependencies

The UI guidelines document is implementation-ready for code generation.

### Cytoscape.js Gotchas (Lessons Learned)

These are hard-won lessons from development. Violating any of these will cause subtle, hard-to-debug issues:

1. **No CSS pseudo-selectors.** Cytoscape does **not** support `:hover` or `:focus` in its stylesheet. Use JS events to add/remove classes (e.g., `.hover`), then target those classes in styles. Only `:selected`, `:active`, `:grabbed` work natively.

2. **Colon-safe ID lookups.** Our canonical IDs use colons (`org:openai`, `model:gpt-5`). The `cy.$('#org:openai')` selector breaks because `#` uses CSS parsing where `:` is a pseudo-class separator. Always use `cy.getElementById('org:openai')` instead.

3. **Manual `cy.resize()` after container changes.** Cytoscape caches its container dimensions. If you toggle a panel that changes the `#cy` element's size, you must call `cy.resize()` (with a short `setTimeout` of ~50ms) or the graph won't redraw into the new bounds.

4. **fcose needs CDN sub-dependencies.** The `cytoscape-fcose` CDN bundle does **not** include `layout-base` and `cose-base`. Load those first, or fcose silently fails and falls back to `cose`. Always test layout availability with a try/catch around a dummy layout run, not by checking global variable names.

5. **Separate CSS classes for separate dimming contexts.** Search uses `.dimmed`; neighborhood highlighting uses `.neighborhood-dimmed`. If both used the same class, clearing one would clear the other. Any new feature that dims elements should use its own class.

See **[docs/ux/troubleshooting.md](docs/ux/troubleshooting.md)** for detailed symptoms, root causes, and fixes.

### Scale Considerations

| Node Count | Client Behavior |
|------------|-----------------|
| < 500 | Render all |
| 500–2,000 | Warn; suggest filtering |
| 2,000–5,000 | Auto-filter to trending; offer "load all" |
| > 5,000 | Require server-side filtering (V2) |

### Export Requirement

All view JSON files must include a `meta` object:

```json
{
  "meta": {
    "view": "trending",
    "nodeCount": 847,
    "edgeCount": 1392,
    "exportedAt": "2026-01-24T12:00:00Z",
    "dateRange": { "start": "2025-10-24", "end": "2026-01-24" }
  },
  "elements": { ... }
}
```

This enables client-side decisions about auto-filtering and user warnings.

---

## Quality Bar
- Add JSON Schemas and validate every extraction/export.
- Add unit tests for:
  - slugging + ID rules
  - date parsing basics
  - schema validation
  - export correctness (Cytoscape required fields)
- Log errors; never silently drop docs.

---

## Safety / Legal / Scraping Policy
- Be polite: set a clear User-Agent, rate-limit, and cache.
- Respect robots.txt where practical.
- Avoid paywalled or restricted content.
- Avoid collecting/storing PII/PHI beyond what appears in public pages; never attempt deanonymization.
- Store only what is needed for analysis and provenance.

---

## Developer Workflow (suggested)

### Current CLI commands
```bash
# Setup
pip install -e .

# Run RSS ingestion (with config or individual feeds)
python -m ingest.rss --config config/feeds.yaml
python -m ingest.rss --feed https://example.com/feed.xml

# Run tests (non-network tests run in any environment)
pytest tests/ -m "not network"

# Run network tests locally (requires internet access)
python scripts/run_network_tests.py
```

### Planned Makefile targets
- `make setup` (venv, deps)
- `make ingest`
- `make docpack`
- `make extract` (API) OR `make import_manual`
- `make resolve`
- `make export`
- `make web`
- `make test`

---

## Sources (V1)

Initial RSS feeds for technical AI content. Runtime configuration lives in `config/feeds.yaml`.

| Source | URL | Why |
|--------|-----|-----|
| arXiv CS.AI | `https://rss.arxiv.org/rss/cs.AI` | Academic papers; structured metadata (authors, affiliations); cites models/datasets/benchmarks |
| Hugging Face Blog | `https://huggingface.co/blog/feed.xml` | Model releases, dataset announcements, open-source ecosystem |
| OpenAI Blog | `https://openai.com/blog/rss.xml` | Major industry announcements, model launches, clear entity relationships |

These three provide coverage across:
- **Academic research** (arXiv)
- **Open-source ecosystem** (Hugging Face)
- **Industry announcements** (OpenAI)

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

#### UX & Visualization

| Document | Purpose |
|----------|---------|
| [docs/ux/README.md](docs/ux/README.md) | Cytoscape client implementation guidelines |
| [docs/ux/troubleshooting.md](docs/ux/troubleshooting.md) | Cytoscape.js gotchas and fixes |

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
