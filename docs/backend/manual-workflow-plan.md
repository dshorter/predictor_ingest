# Manual Backend Workflow — Sonnet Session Plan

## Purpose

Create a step-by-step guide + thin CLI orchestration so a user can run the
full pipeline manually: ingest RSS → clean → build docpack → extract via
ChatGPT → import → resolve → export graph JSON.

All core modules already exist and are functional. This session fills the
gaps: docpack generation, a Makefile, and a walkthrough document.

---

## What Already Works

| Step | Module | Status |
|------|--------|--------|
| DB init | `scripts/init_db.py` | Done |
| RSS ingest | `src/ingest/rss.py` | Done — CLI with `--config` / `--feed` |
| Content clean | `src/clean/__init__.py` | Done — called during ingest |
| Extraction prompt | `src/extract/__init__.py` → `build_extraction_prompt()` | Done |
| Manual import | `src/extract/__init__.py` → `import_manual_extraction()` | Done |
| Schema validation | `src/schema/__init__.py` → `validate_extraction()` | Done |
| Entity resolution | `src/resolve/__init__.py` → `EntityResolver.run_resolution_pass()` | Done |
| Graph export | `src/graph/__init__.py` → `GraphExporter.export_all_views()` | Done (mentions, claims, dependencies) |
| Trend scoring | `src/trend/__init__.py` → `TrendScorer.export_trending()` | Partial — see Known Gap below |
| Feed config | `config/feeds.yaml` | Done — 3 feeds configured |
| DB schema | `schemas/sqlite.sql` | Done |
| Extraction schema | `schemas/extraction.json` | Done |

### Known Gap: `trending.json` Format Mismatch

`TrendScorer.export_trending()` outputs a **flat scores list**:
```json
{
  "generated_at": "2026-02-03",
  "entities": [
    {"entity_id": "model:gpt_5", "name": "GPT-5", "type": "Model",
     "velocity": 2.3, "novelty": 0.8, "trend_score": 0.72, ...}
  ]
}
```

But the **web client expects Cytoscape `elements` format** (nodes + edges)
with a `meta` object. The `run_trending.py` script must bridge this gap by:
1. Getting trending entity IDs from `TrendScorer.get_trending()`
2. Using `GraphExporter` to export only those entities and their relations
3. Adding trend scores as extra fields on node `data` objects
4. Writing the result in Cytoscape format with `meta` object

See the detailed spec in the `run_trending.py` section below.

---

## What Needs to Be Built

### 1. Docpack Generator (`scripts/build_docpack.py`)

Pulls cleaned documents from DB, outputs:
- `data/docpacks/daily_bundle_YYYY-MM-DD.jsonl` — one JSON object per line
- `data/docpacks/daily_bundle_YYYY-MM-DD.md` — markdown bundle for ChatGPT paste

**CLI args:**
```
--db PATH          (default: data/db/predictor.db)
--date YYYY-MM-DD  (default: today; filters documents.fetched_at by date)
--max-docs N       (default: 20; cap on bundle size)
--output-dir PATH  (default: data/docpacks)
```

**DB query to get documents:**
```sql
SELECT doc_id, url, source, title, published_at, fetched_at, text_path
FROM documents
WHERE status IN ('fetched', 'cleaned')
  AND date(fetched_at) = ?
ORDER BY fetched_at DESC
LIMIT ?
```

**JSONL format** (per CLAUDE.md):
```json
{
  "docId": "2025-12-01_nextgov_409826",
  "url": "https://...",
  "source": "Nextgov",
  "title": "CDC placed early bets on AI...",
  "published": "2025-12-01",
  "fetched": "2026-01-21T07:12:00Z",
  "text": "cleaned article text..."
}
```

For each document, read the cleaned text from `text_path` (relative to repo root).
If `text_path` is null or file doesn't exist, skip with a warning.

**Markdown format** — exact template:
```markdown
# Daily Document Bundle — YYYY-MM-DD

Extract entities, relations, and evidence from each document below.
Output one JSON object per document following the schema in schemas/extraction.json.
Required top-level fields: docId, extractorVersion, entities, relations, techTerms, dates.

---

## Document 1: {title}

- **docId:** {docId}
- **URL:** {url}
- **Source:** {source}
- **Published:** {published}

### Text

{cleaned text content}

---

## Document 2: {title}
...
```

**Print on completion:**
```
Bundled 12 documents → data/docpacks/daily_bundle_2026-02-03.jsonl
Bundled 12 documents → data/docpacks/daily_bundle_2026-02-03.md
```

---

### 2. Import Script (`scripts/import_extractions.py`)

This is the most complex script. It must map extraction JSON fields to
the DB function signatures correctly.

**CLI args:**
```
--db PATH              (default: data/db/predictor.db)
--extractions-dir PATH (default: data/extractions)
--dry-run              (validate only, don't write to DB)
```

**Critical: Use `EntityResolver` for entity-to-ID mapping.**

The extraction JSON has entity `name` and `type` strings. The DB requires
canonical `entity_id` values (e.g., `org:openai`). You MUST use the
resolver to create/find entities, NOT manually construct IDs.

**Pseudocode with exact function calls:**
```python
from pathlib import Path
from src.db import init_db, insert_relation, insert_evidence
from src.extract import import_manual_extraction, EXTRACTOR_VERSION
from src.resolve import EntityResolver

conn = init_db(db_path)
resolver = EntityResolver(conn, threshold=0.85)

for json_file in sorted(extractions_dir.glob("*.json")):
    # Step 1: Validate extraction (raises ExtractionError if invalid)
    extraction = import_manual_extraction(json_file, extractions_dir)
    doc_id = extraction["docId"]

    # Step 2: Resolve entities → get name-to-ID mapping
    # This calls resolver.resolve_or_create() for each entity,
    # which either finds an existing match or inserts a new one.
    name_to_id = resolver.resolve_extraction(extraction)
    # Returns: {"OpenAI": "org:openai", "GPT-5": "model:gpt_5", ...}

    # Step 3: Insert relations using resolved IDs
    for rel in extraction.get("relations", []):
        source_id = name_to_id.get(rel["source"])
        target_id = name_to_id.get(rel["target"])

        if not source_id or not target_id:
            print(f"  WARNING: Skipping relation {rel['source']} → {rel['target']}: "
                  f"entity not resolved")
            continue

        # Extract optional time fields
        time_obj = rel.get("time", {})

        relation_id = insert_relation(
            conn,
            source_id=source_id,
            rel=rel["rel"],
            target_id=target_id,
            kind=rel["kind"],
            confidence=rel["confidence"],
            doc_id=doc_id,
            extractor_version=extraction.get("extractorVersion", EXTRACTOR_VERSION),
            verb_raw=rel.get("verbRaw"),
            polarity=rel.get("polarity"),
            modality=rel.get("modality"),
            time_text=time_obj.get("text"),
            time_start=time_obj.get("start"),
            time_end=time_obj.get("end"),
        )

        # Step 4: Insert evidence for this relation
        for ev in rel.get("evidence", []):
            char_span = ev.get("charSpan", {})
            insert_evidence(
                conn,
                relation_id=relation_id,
                doc_id=ev["docId"],
                url=ev["url"],
                published=ev.get("published"),
                snippet=ev["snippet"],
                char_start=char_span.get("start"),
                char_end=char_span.get("end"),
            )

    # Step 5: Update document status
    conn.execute(
        "UPDATE documents SET status = 'extracted' WHERE doc_id = ?",
        (doc_id,)
    )
    conn.commit()
```

**Key field mappings (extraction JSON → DB function params):**

| Extraction JSON field | DB function | DB param |
|----------------------|-------------|----------|
| entity.name | `EntityResolver.resolve_or_create()` | `name` |
| entity.type | `EntityResolver.resolve_or_create()` | `entity_type` |
| entity.aliases | `EntityResolver.resolve_or_create()` | `aliases` (kwarg) |
| entity.externalIds | `EntityResolver.resolve_or_create()` | `external_ids` (kwarg) |
| relation.source | name_to_id lookup | `source_id` |
| relation.target | name_to_id lookup | `target_id` |
| relation.rel | `insert_relation()` | `rel` |
| relation.kind | `insert_relation()` | `kind` |
| relation.confidence | `insert_relation()` | `confidence` |
| relation.verbRaw | `insert_relation()` | `verb_raw` |
| relation.polarity | `insert_relation()` | `polarity` |
| relation.modality | `insert_relation()` | `modality` |
| relation.time.text | `insert_relation()` | `time_text` |
| relation.time.start | `insert_relation()` | `time_start` |
| relation.time.end | `insert_relation()` | `time_end` |
| evidence.docId | `insert_evidence()` | `doc_id` |
| evidence.url | `insert_evidence()` | `url` |
| evidence.published | `insert_evidence()` | `published` |
| evidence.snippet | `insert_evidence()` | `snippet` |
| evidence.charSpan.start | `insert_evidence()` | `char_start` |
| evidence.charSpan.end | `insert_evidence()` | `char_end` |

**Print on completion:**
```
Imported 5 extraction files:
  - 42 entities (31 new, 11 resolved to existing)
  - 67 relations
  - 53 evidence records
  - 5 documents marked as 'extracted'
```

If `--dry-run`:
```
[DRY RUN] Validated 5 extraction files (no DB changes)
```

---

### 3. Resolve Script (`scripts/run_resolve.py`)

**CLI args:**
```
--db PATH          (default: data/db/predictor.db)
--threshold FLOAT  (default: 0.85; similarity threshold)
--dry-run          (report merges without applying)
```

**Code:**
```python
from src.db import init_db
from src.resolve import EntityResolver

conn = init_db(db_path)
resolver = EntityResolver(conn, threshold=args.threshold)
stats = resolver.run_resolution_pass()
# stats returns: {"entities_checked": N, "merges": N, "aliases_added": N}
```

**Print on completion:**
```
Resolution pass complete:
  - 142 entities checked
  - 7 merges performed
  - 14 aliases added
```

---

### 4. Export Script (`scripts/run_export.py`)

**CLI args:**
```
--db PATH          (default: data/db/predictor.db)
--output-dir PATH  (default: data/graphs/{today's date})
--date YYYY-MM-DD  (used for output subdirectory name; default: today)
```

The `--date` arg determines the output subdirectory: `data/graphs/2026-02-03/`.

**Code:**
```python
from src.db import init_db
from src.graph import GraphExporter

conn = init_db(db_path)
exporter = GraphExporter(conn)
output_dir = Path(args.output_dir) / args.date  # e.g., data/graphs/2026-02-03
paths = exporter.export_all_views(output_dir)
# Writes: mentions.json, claims.json, dependencies.json
```

**Print on completion:**
```
Exported 3 views to data/graphs/2026-02-03/:
  - mentions.json (24 nodes, 48 edges)
  - claims.json (18 nodes, 31 edges)
  - dependencies.json (12 nodes, 19 edges)
```

To get node/edge counts for the summary, read back the JSON files or
count from the returned data before writing.

---

### 5. Trending Script (`scripts/run_trending.py`)

**This script must bridge the format gap** between `TrendScorer` (flat scores)
and the web client (Cytoscape elements format).

**CLI args:**
```
--db PATH          (default: data/db/predictor.db)
--output-dir PATH  (default: data/graphs/{today's date})
--top-n INT        (default: 50; max trending entities)
```

**Code — do NOT just call `export_trending()`:**
```python
from src.db import init_db
from src.graph import GraphExporter, build_node, build_edge
from src.trend import TrendScorer
from src.util import utc_now_iso

conn = init_db(db_path)
scorer = TrendScorer(conn)
exporter = GraphExporter(conn)

# Step 1: Get trending entity IDs
trending = scorer.get_trending(limit=args.top_n)
trending_ids = {t["entity_id"] for t in trending}
trend_lookup = {t["entity_id"]: t for t in trending}

# Step 2: Get all relations where BOTH source and target are trending
all_relations = exporter._get_relations()
filtered_relations = [
    r for r in all_relations
    if r["source_id"] in trending_ids and r["target_id"] in trending_ids
]

# Step 3: Get entities and build Cytoscape nodes
all_entities = exporter._get_entities()
filtered_entities = [e for e in all_entities if e["entity_id"] in trending_ids]

nodes = []
for entity in filtered_entities:
    node = build_node(entity)
    # Enrich with trend scores
    scores = trend_lookup.get(entity["entity_id"], {})
    node["data"]["velocity"] = scores.get("velocity", 0)
    node["data"]["novelty"] = scores.get("novelty", 0)
    node["data"]["trend_score"] = scores.get("trend_score", 0)
    node["data"]["mention_count_7d"] = scores.get("mention_count_7d", 0)
    node["data"]["mention_count_30d"] = scores.get("mention_count_30d", 0)
    nodes.append(node)

edges = [build_edge(r) for r in filtered_relations]

# Step 4: Write Cytoscape format with meta object
output = {
    "meta": {
        "view": "trending",
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
        "exportedAt": utc_now_iso(),
        "dateRange": {"start": "...", "end": "..."}  # from min/max entity first_seen/last_seen
    },
    "elements": {
        "nodes": nodes,
        "edges": edges,
    }
}

output_path = output_dir / "trending.json"
# Write JSON...
```

**Print on completion:**
```
Exported trending view to data/graphs/2026-02-03/trending.json
  - 37 nodes, 52 edges (top 50 by trend score)
```

---

### 6. Makefile

```makefile
.PHONY: setup init-db ingest docpack import resolve export trending pipeline post-extract test test-network

# Default DB and output paths
DB ?= data/db/predictor.db
DATE ?= $(shell date +%Y-%m-%d)
GRAPHS_DIR ?= data/graphs

setup:
	pip install -e .

init-db:
	python scripts/init_db.py --db $(DB)

ingest:
	python -m ingest.rss --config config/feeds.yaml

docpack:
	python scripts/build_docpack.py --db $(DB) --date $(DATE)

import:
	python scripts/import_extractions.py --db $(DB)

resolve:
	python scripts/run_resolve.py --db $(DB)

export:
	python scripts/run_export.py --db $(DB) --output-dir $(GRAPHS_DIR) --date $(DATE)

trending:
	python scripts/run_trending.py --db $(DB) --output-dir $(GRAPHS_DIR)/$(DATE)

# Convenience composites
pipeline: ingest docpack

post-extract: import resolve export trending

# Testing
test:
	pytest tests/ -m "not network"

test-network:
	python scripts/run_network_tests.py
```

Notes for Sonnet:
- Use `?=` for variables so they can be overridden: `make export DATE=2026-01-15`
- `import` is a Python keyword but fine as a Makefile target
- Tab-indent all recipe lines (Makefile requirement)

---

### 7. User Walkthrough (`docs/backend/workflow-guide.md`)

Step-by-step guide covering:

#### Section 1: Prerequisites
- Python 3.10+
- `pip install -e .`
- Directory structure created automatically by scripts (`os.makedirs`)

#### Section 2: Initialize
```bash
make init-db
# Creates data/db/predictor.db with schema from schemas/sqlite.sql
```

#### Section 3: Ingest
```bash
make ingest
# Fetches RSS feeds defined in config/feeds.yaml
# Stores raw HTML in data/raw/, cleaned text in data/text/
# Inserts document records into DB with status='cleaned'
```
- How to add custom feeds to `config/feeds.yaml`
- How to ingest a single URL: `python -m ingest.rss --feed URL`

#### Section 4: Build Docpack (Mode B prep)
```bash
make docpack
# Generates data/docpacks/daily_bundle_YYYY-MM-DD.jsonl
# Generates data/docpacks/daily_bundle_YYYY-MM-DD.md
```

#### Section 5: Extract via ChatGPT (Mode B)
1. Open ChatGPT web
2. Paste or upload the `.md` bundle
3. Tell ChatGPT: "Extract entities, relations, and evidence from each document. Output one JSON object per document with these required fields: docId, extractorVersion, entities, relations, techTerms, dates. Follow the schema in the document header."
4. Copy each document's JSON response
5. Save to `data/extractions/{docId}.json` (one file per document)
6. Quick validation: `python -c "from src.schema import validate_extraction; import json; validate_extraction(json.load(open('data/extractions/FILENAME.json')))"`

#### Section 6: Import Extractions
```bash
make import
# Validates each extraction against JSON Schema
# Resolves entities (creates new or matches existing)
# Stores relations and evidence in DB
# Marks documents as 'extracted'
```

#### Section 7: Resolve Entities
```bash
make resolve
# Finds duplicate entities via similarity matching (threshold: 0.85)
# Merges duplicates, redirects relations, adds aliases
```

#### Section 8: Export Graph
```bash
make export
# Writes Cytoscape JSON to data/graphs/YYYY-MM-DD/
#   mentions.json, claims.json, dependencies.json

make trending
# Computes trend scores, writes trending.json (Cytoscape format)
```

#### Section 9: View in Browser
```bash
# Copy graph files to where the web client expects them:
cp -r data/graphs/2026-02-03 web/data/graphs/

# Serve the web client:
python -m http.server 8000 --directory web

# Open http://localhost:8000
```

#### Section 10: Daily Routine (cheat sheet)
```bash
make pipeline        # ingest + docpack → outputs .md for ChatGPT
# ... paste into ChatGPT, save extraction JSONs ...
make post-extract    # import + resolve + export + trending
cp -r data/graphs/$(date +%Y-%m-%d) web/data/graphs/
```

#### Appendix A: Troubleshooting
- "ValidationError: asserted relation must have evidence" → Add `evidence` array to the relation
- "Entity not resolved" warning → Check entity names match between `entities[]` and `relations[].source`/`.target`
- Check DB state: `sqlite3 data/db/predictor.db "SELECT count(*) FROM entities;"`
- Re-import single doc: `python scripts/import_extractions.py --extractions-dir data/extractions --db data/db/predictor.db`

#### Appendix B: Mode A (API) — Future
- When API key is available, `make extract` will call LLM directly
- Same downstream steps (`make post-extract`) apply
- Prompt is already built: `build_extraction_prompt()` in `src/extract/__init__.py`

---

## File List for Sonnet Session

### Create (new files):
1. `scripts/build_docpack.py` — docpack generator
2. `scripts/import_extractions.py` — extraction importer (most complex; see detailed spec above)
3. `scripts/run_resolve.py` — entity resolution runner
4. `scripts/run_export.py` — graph export runner
5. `scripts/run_trending.py` — trending export with Cytoscape format bridging
6. `Makefile` — all targets listed above
7. `docs/backend/workflow-guide.md` — user walkthrough (content from Section 4 above)

### Modify (existing files):
8. `README.md` — update Mode B section to reference `docs/backend/workflow-guide.md`

### Do NOT modify:
- Any `src/` module code (it's all functional)
- Any `web/` files
- `schemas/` files
- `config/feeds.yaml`

---

## Implementation Notes for Sonnet

- Each script should be self-contained with `argparse` and `if __name__ == "__main__"`
- Default DB path: `data/db/predictor.db`
- Default data dirs: `data/docpacks/`, `data/extractions/`, `data/graphs/`
- Create directories with `os.makedirs(path, exist_ok=True)` — don't assume they exist
- Use `src/` imports (e.g., `from src.db import init_db, insert_relation`)
- Print clear progress messages to stdout (see examples in each script section)
- Add `--dry-run` flag to import and resolve scripts
- All scripts should be runnable standalone OR via Makefile
- Keep the walkthrough concrete — show exact terminal output examples
- Use `Path` objects from `pathlib` for all file paths
- Handle missing files gracefully (warn and skip, don't crash the whole batch)

---

## Branch Workflow

1. Pull latest main: `git pull origin main`
2. Create branch from main: `git checkout -b claude/backend-workflow-XXXXX`
3. Implement the 7 files listed above
4. Run `pytest tests/ -m "not network"` — ensure nothing breaks
5. PR to main
6. After merge, this session can pull: `git fetch origin main && git merge origin/main`
