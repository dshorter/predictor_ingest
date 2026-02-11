# Predictor Ingest

A pipeline for building AI trend knowledge graphs from RSS feeds and web sources. Extracts entities, relationships, and trends to produce Cytoscape.js-ready visualizations.
[![Deploy to VPS](https://github.com/dshorter/predictor_ingest/actions/workflows/deploy.yml/badge.svg)](https://github.com/dshorter/predictor_ingest/actions/workflows/deploy.yml)
## Overview

```
RSS Feeds → Ingest → Clean → Extract → Resolve → Graph/Trend → Cytoscape.js
```

The pipeline:
1. **Ingests** RSS feeds and web pages
2. **Cleans** HTML to extract article content
3. **Extracts** entities and relationships (via LLM or manual)
4. **Resolves** duplicate entities into canonical forms
5. **Exports** Cytoscape.js graph views
6. **Scores** entities for velocity, novelty, and bridge metrics

## Installation

```bash
# Clone and install
git clone <repo-url>
cd predictor_ingest
pip install -e .

# Or install dependencies directly
pip install feedparser requests beautifulsoup4 pyyaml jsonschema
```

## Quick Start

### 1. Configure Feeds

Edit `config/feeds.yaml`:

```yaml
feeds:
  - name: "arXiv CS.AI"
    url: "https://rss.arxiv.org/rss/cs.AI"
    type: rss
    enabled: true
```

### 2. Run Ingestion

```bash
# Ingest from configured feeds
python -m ingest.rss --config config/feeds.yaml

# Or specify a feed directly
python -m ingest.rss --feed https://example.com/feed.xml --limit 10
```

### 3. Extract Entities

**Mode A: LLM API** (when API key available)
```bash
# Coming soon - requires LLM integration
```

**Mode B: Manual** (paste into ChatGPT)
```bash
# Generate document bundle for manual extraction
# Then save extraction JSON to data/extractions/
```

### 4. Export Graph

```python
from db import init_db
from graph import GraphExporter

conn = init_db("data/db/ingest.sqlite")
exporter = GraphExporter(conn)

# Export all views
exporter.export_all_views("data/graphs/2026-01-24")
# Creates: claims.json, mentions.json, dependencies.json
```

### 5. Compute Trends

```python
from trend import TrendScorer

scorer = TrendScorer(conn)
trending = scorer.get_trending(limit=20)
scorer.export_trending("data/graphs/2026-01-24")
# Creates: trending.json
```

## Project Structure

```
predictor_ingest/
├── src/
│   ├── config/     # Feed configuration loader
│   ├── db/         # SQLite database operations
│   ├── schema/     # JSON Schema validation
│   ├── ingest/     # RSS/web fetching CLI
│   ├── extract/    # LLM prompt building and parsing
│   ├── util/       # Hashing, slugify, date parsing
│   ├── clean/      # Readability extraction, boilerplate removal
│   ├── resolve/    # Entity resolution, alias merging
│   ├── graph/      # Cytoscape.js export
│   └── trend/      # Velocity, novelty, bridge scoring
├── config/
│   └── feeds.yaml  # RSS feed configuration
├── schemas/
│   ├── extraction.json  # JSON Schema for extractions
│   └── sqlite.sql       # Database schema
├── tests/          # pytest test suite
├── data/           # Runtime data (gitignored)
│   ├── raw/        # Raw HTML
│   ├── text/       # Cleaned text
│   ├── extractions/# Per-doc extraction JSON
│   ├── graphs/     # Cytoscape exports
│   └── db/         # SQLite database
└── web/            # Cytoscape.js viewer (planned)
```

## Graph Views

The pipeline exports multiple graph views:

| View | Description |
|------|-------------|
| `claims.json` | Entity-to-entity semantic relations (CREATED, USES_TECH, etc.) |
| `mentions.json` | Document-to-entity MENTIONS edges |
| `dependencies.json` | Dependency relations only (USES_*, TRAINED_ON, etc.) |
| `trending.json` | Entities ranked by trend score |

## Entity Types

- `Org` - Organizations (OpenAI, Google DeepMind)
- `Person` - Researchers, executives
- `Model` - AI models (GPT-4, Gemini)
- `Dataset` - Training/eval datasets
- `Benchmark` - Evaluation benchmarks (MMLU)
- `Tech` - Technologies (Transformer, RLHF)
- `Paper` - Research papers
- `Repo` - Code repositories
- `Tool` - Software tools
- `Topic` - Research topics
- `Event` - Conferences, launches
- `Location` - Places

## Relation Types

**Document relations:** MENTIONS, CITES, ANNOUNCES

**Semantic relations:** CREATED, PUBLISHED, FUNDED, PARTNERED_WITH, ACQUIRED, HIRED

**Dependencies:** USES_TECH, USES_MODEL, USES_DATASET, TRAINED_ON, EVALUATED_ON, DEPENDS_ON, REQUIRES

## Trend Signals

| Signal | Description |
|--------|-------------|
| `mention_count_7d` | Mentions in last 7 days |
| `mention_count_30d` | Mentions in last 30 days |
| `velocity` | Ratio of recent to previous mentions |
| `novelty` | Based on entity age and rarity |
| `bridge_score` | Connectivity/centrality measure |

## Testing

```bash
# Run all non-network tests
pytest tests/ -m "not network"

# Run with verbose output
pytest tests/ -v -m "not network"

# Run network tests (requires internet)
python scripts/run_network_tests.py
```

**Test coverage:** 223 non-network tests across 10 modules.

## Configuration

### Environment Variables

*None required for basic operation.*

### Feed Configuration

See `config/feeds.yaml` for RSS feed definitions:

```yaml
feeds:
  - name: "Feed Name"
    url: "https://example.com/feed.xml"
    type: rss        # or atom
    enabled: true    # set false to skip
```

## Documentation

- **[Product Guide](docs/product/README.md)** - UI walkthrough, visual encoding, workflows, and screenshot guide
- **AGENTS.md** - Detailed specification and design decisions
- **[UX Implementation](docs/ux/README.md)** - Cytoscape client technical specs and design tokens
- **schemas/extraction.json** - JSON Schema for extraction output
- **schemas/sqlite.sql** - Database schema

## License

*TBD*

## Contributing

*TBD*
