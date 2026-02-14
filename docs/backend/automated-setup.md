# Automated Pipeline Setup

One-time setup to get the automated daily pipeline running.

---

## Prerequisites

- Python 3.10+
- Server with internet access (for RSS fetching and API calls)
- Anthropic API key (for Sonnet extraction) OR OpenAI API key
- Optional: Second API key for understudy/escalation mode

---

## 1. Clone (skip if repo already exists)

```bash
git clone https://github.com/dshorter/predictor_ingest.git /opt/predictor_ingest
```

---

## 2. Install Python Environment

```bash
cd /opt/predictor_ingest

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .
```

**Note:** Always activate the venv before running pipeline commands:
```bash
source /opt/predictor_ingest/venv/bin/activate
```

---

## 3. Configure API Keys

Create a `.env` file in the repo root:

```bash
cat > .env << 'EOF'
# Primary model (Sonnet) — used for Mode A automated extraction
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

# Optional: Override primary model (default: claude-sonnet-4-20250514)
# PRIMARY_MODEL=claude-sonnet-4-20250514

# Optional: Understudy model for shadow/escalation mode
# UNDERSTUDY_MODEL=gpt-5-nano
# OPENAI_API_KEY=sk-your-openai-key
EOF

# Secure the file
chmod 600 .env
```

Load environment in your shell:

```bash
# Add to ~/.bashrc or ~/.zshrc for persistence
set -a; source /opt/predictor_ingest/.env; set +a
```

---

## 4. Initialize Database

```bash
make init-db
# Creates data/db/predictor.db with all tables
```

Verify:

```bash
sqlite3 data/db/predictor.db ".tables"
# Should show: documents entities entity_aliases evidence extraction_comparison relations
```

---

## 5. Verify API Connection

Test that the API key works:

```bash
# Quick test with the Anthropic SDK
python -c "
import anthropic
client = anthropic.Anthropic()
resp = client.messages.create(
    model='claude-sonnet-4-20250514',
    max_tokens=50,
    messages=[{'role': 'user', 'content': 'Say hello'}]
)
print('API OK:', resp.content[0].text)
"
```

Expected output: `API OK: Hello!` (or similar)

If you get an error:
- `AuthenticationError` — check your API key
- `Connection refused` — check internet/firewall
- `RateLimitError` — wait and retry

---

## 6. Configure Feeds

Review `config/feeds.yaml`:

```bash
cat config/feeds.yaml
```

Default feeds (7 sources):
- arXiv CS.AI (limit 20)
- Hugging Face Blog
- OpenAI Blog
- Anthropic Blog
- Google AI Blog
- MIT Technology Review
- The Gradient

Add or modify feeds as needed. Each feed needs:

```yaml
feeds:
  - name: "Source Name"
    url: "https://example.com/feed.xml"
    type: rss
    enabled: true
```

---

## 7. First Manual Run

Run the full pipeline with the orchestrator to verify everything works:

```bash
# Full automated pipeline (all 7 stages)
make daily

# Or if no API key — skip extraction (Mode B manual workflow)
make daily-manual
```

This runs all stages in order:
1. **ingest** — fetch RSS feeds, store raw HTML + cleaned text
2. **docpack** — bundle cleaned docs for extraction
3. **extract** — LLM extraction via API (skipped in `daily-manual`)
4. **import** — import extraction JSON into database
5. **resolve** — entity resolution / deduplication
6. **export** — export Cytoscape.js graph views (mentions, claims, dependencies)
7. **trending** — compute and export trending view

The orchestrator writes a structured JSON log to `data/logs/pipeline_YYYY-MM-DD.json`
and prints a one-liner summary.

You can also run individual stages via Make targets:

```bash
make ingest          # Stage 1
make docpack         # Stage 2
make extract         # Stage 3 (API mode with shadow)
make import          # Stage 4
make resolve         # Stage 5
make export          # Stage 6
make trending        # Stage 7
```

Or the legacy composite targets:

```bash
make pipeline        # ingest + docpack (with lock file)
make post-extract    # import + resolve + export + trending (with lock file)
```

---

## 8. Verify Output

Check the database has data:

```bash
sqlite3 data/db/predictor.db "
SELECT 'Documents:', count(*) FROM documents;
SELECT 'Entities:', count(*) FROM entities;
SELECT 'Relations:', count(*) FROM relations;
"
```

Check graph files:

```bash
ls -la data/graphs/$(date +%Y-%m-%d)/
# Should have: claims.json, dependencies.json, mentions.json, trending.json
```

Check run log:

```bash
cat data/logs/pipeline_$(date +%Y-%m-%d).json | python -m json.tool
```

Copy to web client and test:

```bash
# If not using --copy-to-live flag, manually copy:
cp -r data/graphs/$(date +%Y-%m-%d)/* web/data/graphs/live/

python -m http.server 8000 --directory web
# Open http://localhost:8000, select "Today's Graph" from Data dropdown
```

---

## 9. Configure Shadow Mode (Optional)

To run an understudy model alongside the primary model for comparison:

```bash
# Add to .env
UNDERSTUDY_MODEL=gpt-5-nano
OPENAI_API_KEY=sk-your-openai-key
```

Shadow results go to `extraction_comparison` table. Query them:

```bash
sqlite3 data/db/predictor.db "
SELECT understudy_model,
       COUNT(*) as docs,
       AVG(schema_valid) * 100 as pass_rate,
       AVG(entity_overlap_pct) as entity_overlap,
       AVG(relation_overlap_pct) as relation_overlap
FROM extraction_comparison
GROUP BY understudy_model;
"
```

For a detailed report:

```bash
make shadow-report
```

### Escalation Mode (Default)

The daily orchestrator uses escalation by default: cheap model (understudy) runs
first, and only escalates to the specialist (Sonnet) when quality heuristics fail.
This saves API cost on straightforward articles.

To disable escalation and run the primary model on every document with shadow
comparison instead:

```bash
python scripts/run_pipeline.py --no-escalate --copy-to-live
```

---

## 10. Set Up Daily Cron

Create a cron job for daily automated runs using the pipeline orchestrator:

```bash
# Edit crontab
crontab -e

# Add this line (runs at 6 AM daily)
0 6 * * * cd /opt/predictor_ingest && source venv/bin/activate && source .env && python scripts/run_pipeline.py --copy-to-live >> data/logs/cron.log 2>&1
```

Create the logs directory:

```bash
mkdir -p data/logs
```

The orchestrator handles:
- Running all 7 pipeline stages in order
- Lock file management for safe-reboot awareness
- Structured JSON run log (`data/logs/pipeline_YYYY-MM-DD.json`)
- Copying graphs to `web/data/graphs/live/` for the UI
- One-liner summary printed to stdout (captured by cron)

---

## 11. Verify Daily Run Log

After the first automated run, check:

```bash
# Cron output
tail -50 data/logs/cron.log

# Structured pipeline log
cat data/logs/pipeline_$(date +%Y-%m-%d).json | python -m json.tool
```

See `docs/backend/daily-run-log.md` for the log format and health check thresholds.

---

## Troubleshooting

### API errors during extraction

| Error | Cause | Fix |
|-------|-------|-----|
| `AuthenticationError` | Bad API key | Check `.env` file |
| `RateLimitError` | Too many requests | Extraction script has built-in delays |
| `InvalidRequestError` | Prompt too long | Article may be too large; check cleaning |

### No new documents after ingest

```bash
# Check feed connectivity
python -m ingest.rss --config config/feeds.yaml --limit 1

# Check for duplicates (same URL already fetched)
sqlite3 data/db/predictor.db "SELECT url, status FROM documents ORDER BY fetched_at DESC LIMIT 10;"
```

### Extraction validation failures

```bash
# Check specific extraction
python -c "
from schema import validate_extraction
import json, sys
sys.path.insert(0, 'src')
data = json.load(open('data/extractions/DOCID.json'))
validate_extraction(data)
print('Valid')
"
```

### Database locked

SQLite can only handle one writer at a time. The pipeline orchestrator uses a lock
file (`data/pipeline.lock`) to prevent concurrent runs. Don't run multiple pipeline
instances simultaneously.

### Pipeline run log shows failures

```bash
# Check which stages failed
python -c "
import json
log = json.load(open('data/logs/pipeline_$(date +%Y-%m-%d).json'))
print('Status:', log['status'])
for name, stage in log['stages'].items():
    if stage.get('status') not in ('ok', 'skipped'):
        print(f'  {name}: {stage}')
"
```

---

## File Checklist

After setup, you should have:

```
/opt/predictor_ingest/
├── .env                          # API keys (chmod 600)
├── venv/                         # Python virtual environment
├── config/feeds.yaml             # RSS feed configuration (7 sources)
├── data/
│   ├── db/predictor.db          # SQLite database
│   ├── raw/                      # Raw HTML files
│   ├── text/                     # Cleaned text files
│   ├── docpacks/                 # Daily JSONL bundles
│   ├── extractions/              # Per-document extraction JSON
│   ├── graphs/                   # Cytoscape export files
│   └── logs/                     # Pipeline run logs (JSON + cron.log)
```

---

## Next Steps

- **Deploy web client**: See `docs/deployment/platform-integration-spec.md`
- **Monitor quality**: Check `extraction_comparison` table weekly
- **Tune feeds**: Add/remove sources based on signal quality
- **Review trending**: Check `data/graphs/*/trending.json` for emerging entities
