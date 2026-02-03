# Manual Backend Workflow Guide

This guide walks you through the complete manual pipeline for the AI Trend Graph project, from ingesting RSS feeds to exporting graph data for visualization.

**Mode:** This guide covers **Mode B** (manual extraction via ChatGPT). Mode A (automated LLM API extraction) will be similar but with automated extraction instead of manual ChatGPT steps.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initialize Database](#initialize-database)
3. [Ingest RSS Feeds](#ingest-rss-feeds)
4. [Build Document Pack](#build-document-pack)
5. [Extract via ChatGPT (Mode B)](#extract-via-chatgpt-mode-b)
6. [Import Extractions](#import-extractions)
7. [Resolve Entities](#resolve-entities)
8. [Export Graph Data](#export-graph-data)
9. [View in Browser](#view-in-browser)
10. [Daily Routine (Cheat Sheet)](#daily-routine-cheat-sheet)
11. [Troubleshooting](#troubleshooting)
12. [Future: Mode A (API)](#future-mode-a-api)

---

## Prerequisites

### System Requirements
- Python 3.10 or later
- Git
- A modern web browser (for viewing the graph)
- Internet connection (for RSS ingestion)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd predictor_ingest
   ```

2. Install dependencies:
   ```bash
   make setup
   # Or manually:
   pip install -e .
   ```

3. Verify installation:
   ```bash
   pytest tests/ -m "not network"
   ```

**Note:** All data directories (`data/raw/`, `data/text/`, `data/docpacks/`, `data/extractions/`, `data/graphs/`) are created automatically by the scripts when needed.

---

## Initialize Database

Before running the pipeline for the first time, initialize the SQLite database:

```bash
make init-db
```

**What this does:**
- Creates `data/db/predictor.db`
- Executes the schema from `schemas/sqlite.sql`
- Creates tables: `documents`, `entities`, `relations`, `evidence`, `entity_aliases`

**Example output:**
```
Initializing database at data/db/predictor.db...
Database initialized successfully.
Created tables: documents, entities, relations, evidence, entity_aliases
```

**Note:** You only need to run this once. Running it again on an existing database is safe (it won't overwrite data).

---

## Ingest RSS Feeds

Fetch and clean articles from configured RSS feeds:

```bash
make ingest
```

**What this does:**
- Reads feed URLs from `config/feeds.yaml`
- Fetches RSS feed entries (articles, papers, blog posts)
- Downloads raw HTML to `data/raw/`
- Extracts clean text via readability to `data/text/`
- Inserts document records into the database with `status='cleaned'`

**Example output:**
```
Fetching feed: arXiv CS.AI (https://rss.arxiv.org/rss/cs.AI)
  - Fetched 15 entries
  - 12 new documents, 3 already in database

Fetching feed: Hugging Face Blog (https://huggingface.co/blog/feed.xml)
  - Fetched 8 entries
  - 6 new documents, 2 already in database

Fetching feed: OpenAI Blog (https://openai.com/blog/rss.xml)
  - Fetched 5 entries
  - 4 new documents, 1 already in database

Total: 22 new documents ingested
```

### Adding Custom Feeds

Edit `config/feeds.yaml` to add more RSS feeds:

```yaml
feeds:
  - name: "My Custom Feed"
    url: "https://example.com/feed.xml"
    type: rss
    enabled: true
```

### Ingesting a Single URL

To ingest a single article (not from RSS):

```bash
python -m ingest.rss --feed https://example.com/article-url
```

---

## Build Document Pack

Generate a bundle of documents for manual extraction via ChatGPT:

```bash
make docpack
```

**What this does:**
- Queries documents with `status='cleaned'` fetched on the current date
- Reads cleaned text from `data/text/`
- Generates two files:
  - `data/docpacks/daily_bundle_YYYY-MM-DD.jsonl` (machine-readable)
  - `data/docpacks/daily_bundle_YYYY-MM-DD.md` (human-readable for ChatGPT)

**Example output:**
```
Bundled 12 documents → data/docpacks/daily_bundle_2026-02-03.jsonl
Bundled 12 documents → data/docpacks/daily_bundle_2026-02-03.md
```

### Docpack Format

The `.md` file contains all documents in a structured format ready to paste into ChatGPT:

```markdown
# Daily Document Bundle — 2026-02-03

Extract entities, relations, and evidence from each document below.
Output one JSON object per document following the schema in schemas/extraction.json.
Required top-level fields: docId, extractorVersion, entities, relations, techTerms, dates.

---

## Document 1: CDC placed early bets on AI...

- **docId:** 2025-12-01_nextgov_409826
- **URL:** https://...
- **Source:** Nextgov
- **Published:** 2025-12-01

### Text

[Full cleaned article text here...]

---

## Document 2: ...
```

### Customizing Docpack Generation

To generate a bundle for a specific date or limit the number of documents:

```bash
python scripts/build_docpack.py --date 2026-02-01 --max-docs 10
```

**Options:**
- `--db PATH` - Database path (default: `data/db/predictor.db`)
- `--date YYYY-MM-DD` - Filter documents by fetch date (default: today)
- `--max-docs N` - Maximum documents in bundle (default: 20)
- `--output-dir PATH` - Output directory (default: `data/docpacks/`)

---

## Extract via ChatGPT (Mode B)

This is the **manual extraction step** where you use ChatGPT to extract structured data from documents.

### Step 1: Open ChatGPT

Go to [chat.openai.com](https://chat.openai.com) or your preferred ChatGPT interface.

### Step 2: Prepare the Extraction Prompt

Open the generated markdown file:

```bash
cat data/docpacks/daily_bundle_2026-02-03.md
```

### Step 3: Paste into ChatGPT

Copy the entire contents of the `.md` file and paste it into ChatGPT.

You can also say something like:

> "Extract entities, relations, and evidence from each document. Output one JSON object per document with these required fields: docId, extractorVersion, entities, relations, techTerms, dates. Follow the schema instructions in the document header."

### Step 4: Review and Save Extraction

ChatGPT will output JSON for each document. For each document's JSON:

1. **Copy the JSON** (just the JSON object for one document)
2. **Validate structure** - ensure it has: `docId`, `extractorVersion`, `entities`, `relations`, `techTerms`, `dates`
3. **Save to file** - save as `data/extractions/{docId}.json`

**Example:** If the `docId` is `2025-12-01_nextgov_409826`, save the JSON to:
```
data/extractions/2025-12-01_nextgov_409826.json
```

### Step 5: Quick Validation (Optional)

Validate a single extraction against the JSON Schema:

```bash
python -c "from src.schema import validate_extraction; import json; validate_extraction(json.load(open('data/extractions/2025-12-01_nextgov_409826.json')))"
```

**No output = valid. Error = fix the JSON and try again.**

### Extraction Format Reference

Each extraction JSON should look like this:

```json
{
  "docId": "2025-12-01_nextgov_409826",
  "extractorVersion": "0.1.0",
  "entities": [
    {
      "name": "CDC",
      "type": "Org",
      "aliases": ["Centers for Disease Control and Prevention"]
    },
    {
      "name": "GPT-5",
      "type": "Model"
    }
  ],
  "relations": [
    {
      "source": "CDC",
      "rel": "USES_MODEL",
      "target": "GPT-5",
      "kind": "asserted",
      "confidence": 0.9,
      "evidence": [
        {
          "docId": "2025-12-01_nextgov_409826",
          "url": "https://...",
          "published": "2025-12-01",
          "snippet": "The CDC is deploying GPT-5 for outbreak prediction..."
        }
      ]
    }
  ],
  "techTerms": ["machine learning", "outbreak prediction"],
  "dates": [],
  "notes": []
}
```

**Key rules:**
- All `asserted` relations **must** include at least one `evidence` object
- Entity `name` values must match exactly between `entities[]` and `relations[].source`/`.target`
- Use canonical relation types from the taxonomy (see `AGENTS.md`)

---

## Import Extractions

Import the extracted JSON files into the database:

```bash
make import
```

**What this does:**
- Validates each JSON file in `data/extractions/` against the schema
- Resolves entity names to canonical IDs (creates new entities or matches existing)
- Inserts relations with all metadata (confidence, kind, polarity, modality, time)
- Inserts evidence records with snippets and character spans
- Updates document status to `'extracted'`

**Example output:**
```
Importing extractions from data/extractions/...

Processing 2025-12-01_nextgov_409826.json...
  - 12 entities (8 new, 4 matched existing)
  - 18 relations
  - 15 evidence records

Processing 2025-12-02_huggingface_501234.json...
  - 9 entities (6 new, 3 matched existing)
  - 14 relations
  - 12 evidence records

Imported 5 extraction files:
  - 42 entities (31 new, 11 resolved to existing)
  - 67 relations
  - 53 evidence records
  - 5 documents marked as 'extracted'
```

### Dry Run (Validation Only)

To validate extractions without writing to the database:

```bash
python scripts/import_extractions.py --dry-run
```

**Example output:**
```
[DRY RUN] Validated 5 extraction files (no DB changes)
```

### Troubleshooting Import Errors

**"ValidationError: asserted relation must have evidence"**
- Solution: Add an `evidence` array to the relation with at least one evidence object

**"Entity not resolved" warning**
- Cause: Entity name in `relations[].source` or `.target` doesn't match any name in `entities[]`
- Solution: Ensure entity names are spelled exactly the same (case-sensitive)

**"Invalid JSON"**
- Solution: Use a JSON validator like [jsonlint.com](https://jsonlint.com) to fix syntax errors

---

## Resolve Entities

Merge duplicate entities and consolidate aliases:

```bash
make resolve
```

**What this does:**
- Finds duplicate entities using similarity matching (threshold: 0.85)
- Merges duplicates into a canonical entity
- Redirects all relations to the canonical entity ID
- Adds aliases from merged entities
- Updates `entity_aliases` table

**Example output:**
```
Resolution pass complete:
  - 142 entities checked
  - 7 merges performed
  - 14 aliases added
```

**Examples of merges:**
- `"OpenAI"` + `"OpenAI Inc"` → canonical: `org:openai`, alias: `"OpenAI Inc"`
- `"GPT-5"` + `"GPT 5"` → canonical: `model:gpt_5`, alias: `"GPT 5"`

### Adjusting the Similarity Threshold

To use a different similarity threshold (default: 0.85):

```bash
python scripts/run_resolve.py --threshold 0.90
```

**Higher threshold** (e.g., 0.95) = fewer merges, more precision
**Lower threshold** (e.g., 0.75) = more merges, more recall

### Dry Run

To see what would be merged without applying changes:

```bash
python scripts/run_resolve.py --dry-run
```

---

## Export Graph Data

Generate Cytoscape.js-compatible JSON files for visualization:

```bash
make export
make trending
```

**What this does:**

`make export` writes three views to `data/graphs/YYYY-MM-DD/`:
- `mentions.json` - Document ↔ Entity mentions
- `claims.json` - Entity ↔ Entity semantic relationships
- `dependencies.json` - Technical dependency relationships (USES_TECH, DEPENDS_ON, etc.)

`make trending` writes:
- `trending.json` - High-velocity/high-novelty entities and their relationships

**Example output:**
```
Exported 3 views to data/graphs/2026-02-03/:
  - mentions.json (24 nodes, 48 edges)
  - claims.json (18 nodes, 31 edges)
  - dependencies.json (12 nodes, 19 edges)

Exported trending view to data/graphs/2026-02-03/trending.json
  - 37 nodes, 52 edges (top 50 by trend score)
```

### Graph File Format

All exports use Cytoscape.js `elements` format:

```json
{
  "meta": {
    "view": "trending",
    "nodeCount": 37,
    "edgeCount": 52,
    "exportedAt": "2026-02-03T14:32:00Z",
    "dateRange": {"start": "2025-12-01", "end": "2026-02-03"}
  },
  "elements": {
    "nodes": [
      {
        "data": {
          "id": "org:cdc",
          "label": "CDC",
          "type": "Org",
          "aliases": ["Centers for Disease Control and Prevention"],
          "firstSeen": "2025-12-01",
          "lastSeen": "2026-02-03",
          "velocity": 2.3,
          "novelty": 0.8
        }
      }
    ],
    "edges": [
      {
        "data": {
          "id": "e:org:cdc->model:gpt_5",
          "source": "org:cdc",
          "target": "model:gpt_5",
          "rel": "USES_MODEL",
          "kind": "asserted",
          "confidence": 0.9
        }
      }
    ]
  }
}
```

### Customizing Export Date

To export for a specific date range:

```bash
python scripts/run_export.py --date 2026-02-01
```

This writes to `data/graphs/2026-02-01/`.

---

## View in Browser

Open the interactive graph visualization in your browser:

### Step 1: Copy Graph Files

Copy the exported graph data to where the web client expects it:

```bash
cp -r data/graphs/2026-02-03 web/data/graphs/
```

**Note:** The web client looks for graphs in `web/data/graphs/{date}/`.

### Step 2: Start a Local Web Server

```bash
python -m http.server 8000 --directory web
```

**Or using alternative servers:**
```bash
# Node.js http-server (if installed)
npx http-server web -p 8000

# PHP built-in server
php -S localhost:8000 -t web
```

### Step 3: Open in Browser

Navigate to:
```
http://localhost:8000
```

### Using the Graph

- **Change views:** Use the "View" dropdown (Trending, Claims, Mentions, Dependencies)
- **Search:** Type in the search box to find entities
- **Filter:** Click the gear icon (⚙) to open filters
- **Node details:** Click a node to see full details and relationships
- **Edge evidence:** Click an edge to see supporting evidence snippets
- **Help:** Press `?` or click the help button for full documentation

---

## Daily Routine (Cheat Sheet)

Once you have the initial setup complete, here's the streamlined daily workflow:

```bash
# Morning: Ingest new content and prepare for extraction
make pipeline
# → Runs: make ingest + make docpack
# → Outputs: data/docpacks/daily_bundle_YYYY-MM-DD.md

# ──────────────────────────────────────────────────
# MANUAL STEP: Paste .md into ChatGPT, save JSONs
# ──────────────────────────────────────────────────

# Afternoon: Import, resolve, export
make post-extract
# → Runs: make import + make resolve + make export + make trending

# Copy to web client
cp -r data/graphs/$(date +%Y-%m-%d) web/data/graphs/

# View
python -m http.server 8000 --directory web
# Open http://localhost:8000
```

**Time estimate:**
- Ingest + docpack: ~2 minutes
- ChatGPT extraction: ~5-15 minutes (depends on document count)
- Import + resolve + export: ~1-2 minutes
- **Total: ~10-20 minutes per day**

---

## Troubleshooting

### Database Issues

**"Database locked" error**
- Cause: Another process has the database open
- Solution: Close other connections or wait a moment

**Check database contents:**
```bash
sqlite3 data/db/predictor.db "SELECT COUNT(*) FROM entities;"
sqlite3 data/db/predictor.db "SELECT COUNT(*) FROM relations;"
sqlite3 data/db/predictor.db "SELECT COUNT(*) FROM documents WHERE status='extracted';"
```

### Extraction Issues

**Entities not appearing in graph**
- Check entity type is valid (15 types: Org, Person, Model, Tool, Dataset, Benchmark, Paper, Repo, Tech, Topic, Document, Event, Location, Program, Other)
- Verify entity was imported: `sqlite3 data/db/predictor.db "SELECT * FROM entities WHERE name LIKE '%OpenAI%';"`

**Relations missing**
- Ensure both source and target entities exist in `entities[]` array
- Verify `kind` is valid: `asserted`, `inferred`, or `hypothesis`
- Check `asserted` relations have at least one evidence object

**Low-confidence relations not showing**
- The web client filters edges with `confidence < 0.3` by default
- Adjust via the filter panel in the UI

### Import Warnings

**"WARNING: Skipping relation X → Y: entity not resolved"**
- Cause: Entity name mismatch between `entities[]` and `relations[]`
- Solution: Check spelling, case, and exact match

### Graph Rendering Issues

**Graph appears empty**
- Check the `meta.nodeCount` in the JSON file is > 0
- Verify you're viewing the correct date in the date selector
- Open browser console (F12) for JavaScript errors

**Nodes too small or too large**
- This is controlled by velocity/novelty scores
- Low scores = small nodes, high scores = large nodes
- Expected for graphs with low activity

### Re-importing a Single Document

If you need to fix and re-import a single document:

1. Delete the old relations:
   ```bash
   sqlite3 data/db/predictor.db "DELETE FROM relations WHERE doc_id='2025-12-01_nextgov_409826';"
   ```

2. Re-import just that file:
   ```bash
   python scripts/import_extractions.py --extractions-dir data/extractions
   ```

   The import script will skip documents that haven't changed.

---

## Future: Mode A (API)

**Mode A** (automated LLM API extraction) is planned but not yet implemented. When available:

- `make extract` will call the LLM API directly using the prompt from `src/extract/__init__.py`
- No ChatGPT copy/paste needed
- Same downstream steps (`make post-extract`) apply
- Extraction quality may vary by model (GPT-4, Claude, etc.)

**Current status:**
- ✅ Prompt template ready (`build_extraction_prompt()`)
- ✅ Schema validation ready
- ⏳ API integration pending

To add Mode A support:
1. Set your API key as an environment variable
2. Implement `scripts/run_extract.py` to call the LLM API
3. Update `Makefile` to add `extract` target
4. Run `make pipeline extract post-extract` for fully automated workflow

---

## Additional Resources

- **Project specification:** `AGENTS.md` (or `CLAUDE.md`)
- **Extraction schema:** `schemas/extraction.json`
- **Database schema:** `schemas/sqlite.sql`
- **UX documentation:** `docs/ux/README.md`
- **Feed configuration:** `config/feeds.yaml`

---

## Getting Help

If you encounter issues not covered in this guide:

1. Check the project's issue tracker
2. Review the extraction schema and ensure your JSON matches
3. Validate JSON with: `python -c "from src.schema import validate_extraction; import json; validate_extraction(json.load(open('FILE.json')))"`
4. Inspect database state with `sqlite3` queries
5. Check web browser console (F12) for JavaScript errors

Happy graphing! 📊
