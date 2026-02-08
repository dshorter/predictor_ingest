# Automated Pipeline Setup

One-time setup to get the automated extraction pipeline running with Sonnet as primary.

---

## Prerequisites

- Python 3.10+
- Server with internet access (for RSS fetching and API calls)
- Anthropic API key (for Sonnet)
- Optional: Second API key for understudy (Gemini, OpenAI, or Haiku)

---

## 1. Clone and Install

```bash
# Clone the repo
git clone https://github.com/dshorter/predictor_ingest.git /opt/predictor_ingest
cd /opt/predictor_ingest

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .
```

---

## 2. Configure API Keys

Create a `.env` file in the repo root:

```bash
cat > .env << 'EOF'
# Primary model (Sonnet)
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

# Understudy model (pick one or more)
# OPENAI_API_KEY=sk-your-openai-key
# GOOGLE_API_KEY=your-google-api-key
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

## 3. Initialize Database

```bash
make init-db
# Creates data/db/predictor.db with all tables including extraction_comparison
```

Verify:

```bash
sqlite3 data/db/predictor.db ".tables"
# Should show: documents entities entity_aliases evidence extraction_comparison relations
```

---

## 4. Verify API Connection

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

## 5. Configure Feeds

Review `config/feeds.yaml`:

```bash
cat config/feeds.yaml
```

Default feeds:
- arXiv CS.AI
- Hugging Face Blog
- OpenAI Blog

Add or modify feeds as needed. Each feed needs:

```yaml
feeds:
  - name: "Source Name"
    url: "https://example.com/feed.xml"
    type: rss
    enabled: true
```

---

## 6. First Manual Run

Run each stage to verify everything works:

```bash
# Stage 1: Ingest RSS feeds
make ingest
# Check: data/raw/ and data/text/ should have new files

# Stage 2: Build document pack
make docpack
# Check: data/docpacks/daily_bundle_YYYY-MM-DD.jsonl exists

# Stage 3: Run extraction (this calls the API)
make extract
# Check: data/extractions/*.json files created

# Stage 4: Import to database
make import
# Check: entities and relations populated

# Stage 5: Resolve duplicates
make resolve

# Stage 6: Export graph views
make export

# Stage 7: Compute trending
make trending
# Check: data/graphs/YYYY-MM-DD/*.json files exist
```

Or run the full pipeline:

```bash
make pipeline      # ingest + docpack + extract
make post-extract  # import + resolve + export + trending
```

---

## 7. Verify Output

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

Copy to web client and test:

```bash
cp -r data/graphs/$(date +%Y-%m-%d)/* web/data/graphs/latest/
python -m http.server 8000 --directory web
# Open http://localhost:8000
```

---

## 8. Configure Shadow Mode (Optional)

To run an understudy model alongside Sonnet for comparison:

Edit your extraction config to enable shadow mode:

```python
# In the extraction runner, configure:
PRIMARY_MODEL = "claude-sonnet-4-20250514"
UNDERSTUDY_MODELS = ["gemini-2.5-flash"]  # or ["claude-haiku-4-5-20250901"]
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

---

## 9. Set Up Daily Cron

Create a cron job for daily automated runs:

```bash
# Edit crontab
crontab -e

# Add this line (runs at 6 AM daily)
0 6 * * * cd /opt/predictor_ingest && source venv/bin/activate && source .env && make pipeline && make post-extract >> data/logs/cron.log 2>&1
```

Create the logs directory:

```bash
mkdir -p data/logs
```

---

## 10. Verify Daily Run Log

After the first automated run, check:

```bash
# Cron output
tail -50 data/logs/cron.log

# Pipeline run summary (once implemented)
cat data/logs/pipeline_$(date +%Y-%m-%d).json
```

See `docs/backend/daily-run-log.md` for the log format and health check thresholds.

---

## Troubleshooting

### API errors during extraction

| Error | Cause | Fix |
|-------|-------|-----|
| `AuthenticationError` | Bad API key | Check `.env` file |
| `RateLimitError` | Too many requests | Add retry logic or slow down |
| `InvalidRequestError` | Prompt too long | Article may be too large; check cleaning |

### No new documents after ingest

```bash
# Check feed status
python -m ingest.rss --config config/feeds.yaml --dry-run

# Check for duplicates (same URL already fetched)
sqlite3 data/db/predictor.db "SELECT url, status FROM documents ORDER BY fetched_at DESC LIMIT 10;"
```

### Extraction validation failures

```bash
# Check specific extraction
python -c "
from schema import validate_extraction
import json
data = json.load(open('data/extractions/DOCID.json'))
validate_extraction(data)
print('Valid')
"
```

### Database locked

SQLite can only handle one writer at a time. Don't run multiple pipeline instances simultaneously.

---

## File Checklist

After setup, you should have:

```
/opt/predictor_ingest/
├── .env                          # API keys (chmod 600)
├── venv/                         # Python virtual environment
├── config/feeds.yaml             # RSS feed configuration
├── data/
│   ├── db/predictor.db          # SQLite database
│   ├── raw/                      # Raw HTML files
│   ├── text/                     # Cleaned text files
│   ├── docpacks/                 # Daily JSONL bundles
│   ├── extractions/              # Per-document extraction JSON
│   ├── graphs/                   # Cytoscape export files
│   └── logs/                     # Pipeline run logs
```

---

## Next Steps

- **Deploy web client**: See `docs/deployment/platform-integration-spec.md`
- **Monitor quality**: Check `extraction_comparison` table weekly
- **Tune feeds**: Add/remove sources based on signal quality
- **Review trending**: Check `data/graphs/*/trending.json` for emerging entities
