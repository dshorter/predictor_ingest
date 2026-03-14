# Backend Workflow Guide

Step-by-step guide for running the full pipeline:
ingest → clean → docpack → extract → import → resolve → export.

## Prerequisites

- Python 3.10+
- Install dependencies: `make setup` or `pip install -e .`
- Directories (`data/db/`, `data/raw/`, etc.) are created automatically by scripts

## Domain Selection

All pipeline commands support a `--domain` flag (or `DOMAIN=` Makefile variable,
or `PREDICTOR_DOMAIN` env var). Default domain is `ai`.

```bash
# These are equivalent:
make ingest DOMAIN=biosafety
python scripts/run_pipeline.py --domain biosafety
PREDICTOR_DOMAIN=biosafety make ingest
```

Databases are isolated per domain: `data/db/{domain}.db` (e.g., `data/db/ai.db`,
`data/db/biosafety.db`).

## 1. Initialize the Database

```bash
make init-db
# Creates data/db/ai.db with schema from schemas/sqlite.sql

make init-db DOMAIN=biosafety
# Creates data/db/biosafety.db
```

To use a custom path: `make init-db DB=path/to/custom.db`

## 2. Ingest RSS Feeds

```bash
make ingest
# Fetches RSS feeds defined in domains/ai/feeds.yaml
# Stores raw HTML in data/raw/, cleaned text in data/text/
# Inserts document records into DB with status='cleaned'

make ingest DOMAIN=biosafety
# Uses domains/biosafety/feeds.yaml
```

To ingest a single feed URL:
```bash
python -m ingest.rss --feed https://example.com/feed.xml
```

To add new sources, edit `domains/{domain}/feeds.yaml`:
```yaml
feeds:
  - name: "New Source"
    url: "https://example.com/feed.xml"
    type: rss
    enabled: true
```

## 3. Build Document Pack (Mode B Prep)

```bash
make docpack
# Generates data/docpacks/daily_bundle_YYYY-MM-DD.jsonl
# Generates data/docpacks/daily_bundle_YYYY-MM-DD.md
```

For a specific date: `make docpack DATE=2026-01-15`

## 4. Extract Entities and Relations

### Mode A — LLM API (when API key is available)

*Not yet automated. Use the evaluation harness for now:*
```bash
OPENAI_API_KEY=sk-... pytest tests/test_llm_eval.py -v -m llm_live -k openai
```

### Mode B — ChatGPT Web (manual)

1. Open the `.md` bundle from step 3
2. Paste or upload into ChatGPT
3. Prompt: *"Extract entities, relations, and evidence from each document. Output one JSON object per document with these required fields: docId, extractorVersion, entities, relations, techTerms, dates. Follow the schema in the document header."*
4. Copy each JSON response and save to `data/extractions/{docId}.json`
5. Quick validation:
   ```bash
   python -c "
   from schema import validate_extraction
   import json, sys
   validate_extraction(json.load(open(sys.argv[1])))
   print('Valid')
   " data/extractions/FILENAME.json
   ```

## 5. Import Extractions

```bash
make import
# Validates each extraction against JSON Schema
# Resolves entities (creates new or matches existing)
# Stores relations and evidence in DB
# Marks documents as 'extracted'
```

Validate without writing to DB: `python scripts/import_extractions.py --dry-run`

## 6. Resolve Entities

```bash
make resolve
# Finds duplicate entities via similarity matching (threshold: 0.85)
# Merges duplicates, redirects relations, adds aliases
```

Adjust threshold: `python scripts/run_resolve.py --threshold 0.90`

## 7. Export Graph Views

```bash
make export
# Writes Cytoscape JSON to data/graphs/YYYY-MM-DD/
#   mentions.json, claims.json, dependencies.json
# Default: last 30 days of articles (by published date)

make trending
# Computes trend scores, writes trending.json (Cytoscape format)
```

### Date range options

By default, exports include only articles published in the last 30 days
(`DEFAULT_DATE_WINDOW_DAYS` in `src/config/__init__.py`). Override with:

```bash
# Custom day window
python scripts/run_export.py --days 90

# No date filter (all data)
python scripts/run_export.py --days 0

# Explicit date range
python scripts/run_export.py --start-date 2025-12-01 --end-date 2026-01-31
```

See [docs/architecture/date-filtering.md](../architecture/date-filtering.md)
for the full architecture and rationale.

## 8. View in Browser

```bash
# Copy graph files to the web client directory:
cp -r data/graphs/$(date +%Y-%m-%d)/* web/data/graphs/latest/

# Serve the web client:
python -m http.server 8000 --directory web

# Open http://localhost:8000
```

## Daily Routine (Cheat Sheet)

```bash
# Morning: ingest and prepare for extraction (AI domain, default)
make pipeline           # ingest + docpack

# ... paste .md into ChatGPT, save extraction JSONs to data/extractions/ ...

# After extraction: import, resolve, export
make post-extract       # import + resolve + export + trending

# Deploy to web client
cp -r data/graphs/$(date +%Y-%m-%d)/* web/data/graphs/latest/

# Full daily pipeline (automated, Mode A)
make daily                        # AI domain (default)
make daily DOMAIN=biosafety       # Biosafety domain

# Verify domain routing is correct before a run
make daily-check
make daily-check DOMAIN=biosafety
```

## Additional Tools

```bash
# Export ontology JSON from domain profiles
make export_ontology

# Wipe all pipeline data for a domain (dry-run by default)
python scripts/wipe_domain_data.py --domain biosafety
python scripts/wipe_domain_data.py --domain biosafety --confirm  # actually delete

# Generate dashboard JSON for the pipeline monitoring page
python scripts/generate_dashboard_json.py

# Diagnose feed freshness
python scripts/diagnose_feeds.py
```

## Makefile Variables

All variables can be overridden:

```bash
make export DATE=2026-01-15
make import DB=data/db/custom.db
make trending GRAPHS_DIR=/var/www/graphs
make daily DOMAIN=biosafety
```

| Variable | Default | Description |
|----------|---------|-------------|
| `DOMAIN` | `ai` | Active domain (routes to `domains/{domain}/` and `data/db/{domain}.db`) |
| `DB` | `data/db/{domain}.db` | SQLite database path (auto-derived from domain if not set) |
| `DATE` | today | Date for filtering and output directories |
| `DAYS` | `30` | Date window in days (0 = all data) |
| `GRAPHS_DIR` | `data/graphs` | Base directory for graph exports |

## Troubleshooting

### "ValidationError: asserted relation must have evidence"
Add an `evidence` array to the relation in the extraction JSON. Every
asserted relation must include at least one evidence object with `docId`,
`url`, and `snippet`.

### "Entity not resolved" warning
Check that entity names in `relations[].source` and `relations[].target`
match entries in the `entities[]` array exactly.

### Check database state
```bash
# AI domain (default)
sqlite3 data/db/ai.db "SELECT count(*) FROM entities;"
sqlite3 data/db/ai.db "SELECT count(*) FROM relations;"
sqlite3 data/db/ai.db "SELECT count(*) FROM documents WHERE status='extracted';"

# Biosafety domain
sqlite3 data/db/biosafety.db "SELECT count(*) FROM entities;"
```

### Re-import a single extraction
```bash
python scripts/import_extractions.py --extractions-dir data/extractions --db data/db/ai.db
```
