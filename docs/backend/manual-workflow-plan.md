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
| Trend scoring | `src/trend/__init__.py` → `TrendScorer.export_trending()` | Done |
| Feed config | `config/feeds.yaml` | Done — 3 feeds configured |
| DB schema | `schemas/sqlite.sql` | Done |
| Extraction schema | `schemas/extraction.json` | Done |

## What Needs to Be Built

### 1. Docpack Generator (`src/docpack/__init__.py` or `scripts/build_docpack.py`)

Pulls cleaned documents from DB, outputs:
- `data/docpacks/daily_bundle_YYYY-MM-DD.jsonl` — one JSON object per doc
- `data/docpacks/daily_bundle_YYYY-MM-DD.md` — markdown bundle for ChatGPT paste

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

**Markdown format**: Each doc as a section with metadata header + full text.
Include the extraction prompt at the top (from `build_extraction_prompt()`
or a simplified version referencing the schema).

**Inputs**: DB path, date filter (default: today's fetched docs), max docs
**Output**: Files written to `data/docpacks/`

### 2. Makefile

Thin wrappers around existing CLI commands:

```makefile
# Core targets
setup:        pip install -e .
init-db:      python scripts/init_db.py
ingest:       python -m ingest.rss --config config/feeds.yaml
docpack:      python scripts/build_docpack.py
import:       python scripts/import_extractions.py
resolve:      python scripts/run_resolve.py
export:       python scripts/run_export.py
trending:     python scripts/run_trending.py

# Convenience
pipeline:     ingest docpack  (stops here for Mode B)
post-extract: import resolve export trending

# Testing
test:         pytest tests/ -m "not network"
test-network: python scripts/run_network_tests.py
```

### 3. Orchestration Scripts

Thin scripts that wire existing module functions together:

#### `scripts/build_docpack.py`
```
- Parse args (--db, --date, --max-docs)
- Query documents table for status='cleaned' within date range
- For each doc: read text_path, build JSONL entry
- Write .jsonl and .md files to data/docpacks/
- Print summary (N docs bundled)
```

#### `scripts/import_extractions.py`
```
- Parse args (--db, --extractions-dir)
- Glob data/extractions/*.json
- For each file:
  - Call import_manual_extraction() (validates + returns dict)
  - For each entity: call db.insert_entity()
  - For each relation: call db.insert_relation()
  - For each evidence: call db.insert_evidence()
  - Update document status to 'extracted'
- Print summary (N docs imported, N entities, N relations)
```

#### `scripts/run_resolve.py`
```
- Parse args (--db, --threshold)
- Create EntityResolver(db)
- Call run_resolution_pass()
- Print summary (N merges performed)
```

#### `scripts/run_export.py`
```
- Parse args (--db, --output-dir, --date)
- Create GraphExporter(db)
- Call export_all_views(output_dir)
- Print summary (files written)
```

#### `scripts/run_trending.py`
```
- Parse args (--db, --output-dir, --top-n)
- Create TrendScorer(db)
- Call export_trending(output_dir, top_n)
- Print summary
```

### 4. User Walkthrough (`docs/backend/workflow-guide.md`)

Step-by-step guide covering:

#### Section 1: Prerequisites
- Python 3.10+
- pip install -e .
- Directory structure (data/raw, data/text, data/docpacks, data/extractions, data/graphs, data/db)

#### Section 2: Initialize
```bash
make init-db
# Creates data/db/predictor.db with schema
```

#### Section 3: Ingest
```bash
make ingest
# Fetches RSS feeds defined in config/feeds.yaml
# Stores raw HTML in data/raw/, cleaned text in data/text/
# Inserts document records into DB
```
- How to add custom feeds to feeds.yaml
- How to ingest a single URL: `python -m ingest.rss --feed URL`

#### Section 4: Build Docpack (Mode B prep)
```bash
make docpack
# Generates data/docpacks/daily_bundle_YYYY-MM-DD.jsonl
# Generates data/docpacks/daily_bundle_YYYY-MM-DD.md
```

#### Section 5: Extract via ChatGPT (Mode B)
- Open ChatGPT web
- Paste or upload the .md bundle
- Prompt: "Extract entities, relations, and evidence from these documents using this JSON schema: [link or paste schema]"
- Copy the JSON response
- Save each doc's extraction to `data/extractions/{docId}.json`
- Validation tip: `python -c "from src.schema import validate_extraction; ..."`

#### Section 6: Import Extractions
```bash
make import
# Validates each extraction against schema
# Stores entities, relations, evidence in DB
```

#### Section 7: Resolve Entities
```bash
make resolve
# Finds and merges duplicate entities (similarity matching)
# Updates aliases and redirects relations
```

#### Section 8: Export Graph
```bash
make export
# Writes Cytoscape JSON to data/graphs/YYYY-MM-DD/
#   mentions.json, claims.json, dependencies.json
make trending
# Computes trend scores, writes trending.json
```

#### Section 9: View in Browser
```bash
# Copy/symlink graph files to web/data/graphs/
# Serve: python -m http.server 8000 --directory web
# Open localhost:8000
```

#### Section 10: Daily Routine (cheat sheet)
```bash
make pipeline        # ingest + docpack
# ... manual ChatGPT extraction ...
make post-extract    # import + resolve + export + trending
```

#### Appendix A: Troubleshooting
- Common validation errors and fixes
- How to re-run extraction on a single doc
- How to check DB state: `sqlite3 data/db/predictor.db "SELECT count(*) FROM entities;"`

#### Appendix B: Mode A (API) — Future
- When API key is available
- `make extract` will call LLM directly
- Same downstream steps apply

---

## File List for Sonnet Session

### Create (new files):
1. `scripts/build_docpack.py` — docpack generator
2. `scripts/import_extractions.py` — extraction importer
3. `scripts/run_resolve.py` — entity resolution runner
4. `scripts/run_export.py` — graph export runner
5. `scripts/run_trending.py` — trend scoring runner
6. `Makefile` — all targets listed above
7. `docs/backend/workflow-guide.md` — user walkthrough (content from Section 4 above)

### Modify (existing files):
8. `README.md` — update Mode B section to reference workflow-guide.md

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
- Use `src/` imports (e.g., `from src.db import init_db, insert_entity`)
- Print clear progress messages to stdout (e.g., "Bundled 12 documents → data/docpacks/daily_bundle_2026-02-02.jsonl")
- Add `--dry-run` flag to import and resolve scripts
- All scripts should be runnable standalone OR via Makefile
- Keep the walkthrough concrete — show exact terminal output examples

---

## Branch Workflow

1. Pull latest main: `git pull origin main`
2. Create branch from main: `git checkout -b claude/backend-workflow-XXXXX`
3. Implement the 7 files listed above
4. Run `pytest tests/ -m "not network"` — ensure nothing breaks
5. PR to main
6. After merge, this session can pull: `git fetch origin main && git merge origin/main`
