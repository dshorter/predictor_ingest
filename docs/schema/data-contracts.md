# Data Contracts

Detailed schemas for all data formats flowing through the pipeline.

---

## 1) Document record (SQLite)
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

## 2) DocPack (daily bundle) — JSONL
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

Also generate `daily_bundle_YYYY-MM-DD.md` for "paste into ChatGPT" workflows.

## 3) Extraction Output — per document JSON
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
- `type` (enum; see Node Types in CLAUDE.md)
- `aliases` (list[string], optional)
- `externalIds` (object, optional) e.g. `{"wikidata":"Q123"}`
- `idHint` (string, optional; if model suggests canonical id)

Relation object:
- `source` (string; entity name or idHint)
- `rel` (enum; canonical relation taxonomy — see CLAUDE.md)
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
  - `anchor` (e.g., published date used for "this fall")

## 4) Cytoscape.js Export — `elements`
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
