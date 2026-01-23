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
  - `ingest/` (RSS + web fetching)
  - `clean/` (readability extraction, boilerplate removal)
  - `extract/` (LLM prompts + parsing + validation)
  - `resolve/` (entity resolution + alias merging)
  - `graph/` (Cytoscape export + views)
  - `trend/` (basic scoring: velocity/novelty/bridge)
  - `util/` (hashing, time parsing, logging)
- `data/` (gitignored)
  - `raw/` (raw HTML, raw feed snapshots)
  - `text/` (cleaned plain text)
  - `docpacks/` (daily bundles JSONL/MD)
  - `extractions/` (per-doc extracted JSON)
  - `graphs/` (exports for Cytoscape client)
  - `db/` (SQLite)
- `web/` (thin Cytoscape.js client; static site)
- `schemas/` (JSON Schemas for DocPack + Extraction + Graph)
- `tests/`
- `Makefile`
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
