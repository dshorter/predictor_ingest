# Backend Workflow Guide

Step-by-step guide for running the full pipeline:
ingest → clean → docpack → extract → import → resolve → export.

## Prerequisites

- Python 3.10+
- Install dependencies: `make setup` or `pip install -e .`
- Directories (`data/db/`, `data/raw/`, etc.) are created automatically by scripts

## 1. Initialize the Database

```bash
make init-db
# Creates data/db/predictor.db with schema from schemas/sqlite.sql
```

To use a custom path: `make init-db DB=path/to/custom.db`

## 2. Ingest RSS Feeds

```bash
make ingest
# Fetches RSS feeds defined in config/feeds.yaml
# Stores raw HTML in data/raw/, cleaned text in data/text/
# Inserts document records into DB with status='cleaned'
```

To ingest a single feed URL:
```bash
python -m ingest.rss --feed https://example.com/feed.xml
```

To add new sources, edit `config/feeds.yaml`:
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
# Morning: ingest and prepare for extraction
make pipeline           # ingest + docpack

# ... paste .md into ChatGPT, save extraction JSONs to data/extractions/ ...

# After extraction: import, resolve, export
make post-extract       # import + resolve + export + trending

# Deploy to web client
cp -r data/graphs/$(date +%Y-%m-%d)/* web/data/graphs/latest/
```

## Makefile Variables

All variables can be overridden:

```bash
make export DATE=2026-01-15
make import DB=data/db/custom.db
make trending GRAPHS_DIR=/var/www/graphs
```

| Variable | Default | Description |
|----------|---------|-------------|
| `DB` | `data/db/predictor.db` | SQLite database path |
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
sqlite3 data/db/predictor.db "SELECT count(*) FROM entities;"
sqlite3 data/db/predictor.db "SELECT count(*) FROM relations;"
sqlite3 data/db/predictor.db "SELECT count(*) FROM documents WHERE status='extracted';"
```

### Re-import a single extraction
```bash
python scripts/import_extractions.py --extractions-dir data/extractions --db data/db/predictor.db
```
