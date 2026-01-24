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
  - `resolve/` (entity resolution + alias merging) *[planned]*
  - `graph/` (Cytoscape export: mentions, claims, dependencies views)
  - `trend/` (basic scoring: velocity/novelty/bridge) *[planned]*
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

## Thin Cytoscape Client (web/)
Requirements:
- static site (no backend required in V1)
- loads selected `graphs/{date}/{view}.json`
- force-directed layout on load is acceptable for V1
- UI:
  - dataset selector (date/view)
  - search box (by label)
  - toggles: asserted / inferred / hypothesis
  - buttons: zoom in/out, fit, re-run layout
- on edge click: show provenance/evidence list

Keep dependencies minimal.

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

## Backlog (post-V1 ideas)
- Persist node positions (`preset` layout) for stability across days
- Add “follow-up query” generation for hypothesis edges (2-hop research discipline)
- Better entity resolution (Wikidata IDs for high-degree nodes)
- Community detection + clustering views
- Source-type enrichment (paper/repo/hiring/product changelog) for earlier weak signals
