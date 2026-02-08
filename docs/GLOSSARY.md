# Project Glossary

**A comprehensive reference guide for understanding the AI Trend Graph knowledge graph pipeline.**

This glossary explains key concepts, terms, and technical vocabulary used throughout the project. It's designed for technically-educated readers who are new to knowledge graphs, trend analysis, or graph-based data visualization.

---

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Pipeline Stages](#pipeline-stages)
3. [Entity Types (Node Types)](#entity-types-node-types)
4. [Relationship Types (Edge Types)](#relationship-types-edge-types)
5. [Data Structures](#data-structures)
6. [Extraction and Processing](#extraction-and-processing)
7. [Graph Visualization](#graph-visualization)
8. [Scoring and Metrics](#scoring-and-metrics)
9. [Technical Infrastructure](#technical-infrastructure)

---

## Core Concepts

### Knowledge Graph
A **knowledge graph** is a structured representation of information that connects entities (like organizations, people, or technologies) through labeled relationships. Think of it like a map where:
- **Nodes** (circles) represent entities (e.g., "OpenAI", "GPT-4", "CDC")
- **Edges** (lines) represent relationships between entities (e.g., "OpenAI CREATED GPT-4")

Knowledge graphs make it easy to:
- See connections between different pieces of information
- Answer questions like "What technologies does this organization use?"
- Discover patterns and trends that aren't obvious in raw text

### Trend Analysis
The process of identifying which entities, relationships, or topics are gaining or losing attention over time. This project uses several signals:
- **Velocity**: How fast something is being mentioned more frequently
- **Novelty**: How new or rare something is
- **Bridge connections**: Entities that connect previously separate clusters

### Entity
An **entity** is any distinct "thing" we want to track in the knowledge graph. Examples:
- **Organizations**: OpenAI, CDC, Microsoft
- **People**: Sam Altman, Geoffrey Hinton
- **Technologies**: GPT-4, RAG (Retrieval-Augmented Generation), PyTorch
- **Models**: GPT-4, Claude, LLaMA
- **Datasets**: ImageNet, CommonCrawl

Each entity becomes a **node** in the graph.

### Relationship (Relation)
A **relationship** (or **relation**) describes how two entities are connected. Examples:
- "OpenAI LAUNCHED GPT-4"
- "CDC USES_MODEL GPT-4"
- "GPT-4 TRAINED_ON CommonCrawl"

Each relationship becomes an **edge** in the graph.

### Provenance
**Provenance** means tracking where information came from. For every claim in our graph, we record:
- Which document(s) mentioned it
- The exact text snippet (evidence)
- The publication date
- The source URL
- Confidence score

This makes the graph auditable—you can trace any claim back to its source.

### Archive-First
An **archive-first** approach means we save the raw, original content before doing anything else. Even if our extraction or analysis has bugs, we can always re-process the archived content later with improved methods.

We save:
- Raw HTML or feed XML
- Cleaned text version
- Metadata (URL, fetch date, content hash)

---

## Pipeline Stages

The pipeline is the step-by-step process that transforms raw web content into an interactive knowledge graph.

### 1. Ingestion
**Ingestion** is the first step: fetching content from sources (RSS feeds, web pages) and saving it to disk.

- **Input**: RSS feed URLs, web page URLs
- **Output**: Raw HTML/XML files, initial document records in database
- **Tools**: `src/ingest/` module

### 2. Cleaning
**Cleaning** converts raw HTML into readable plain text and extracts basic metadata.

- Removes boilerplate (headers, footers, ads, navigation)
- Extracts article title, publish date, author
- Saves cleaned text to `data/text/`
- **Tools**: `src/clean/` module (uses readability algorithms)

### 3. Extraction
**Extraction** is the core intelligence step: reading cleaned text and identifying entities, relationships, dates, and technology terms.

- **Mode A** (automated): Uses an LLM API (like GPT-4 or Claude) to analyze text
- **Mode B** (semi-manual): User pastes text into ChatGPT and copies back the structured output

**Output**: JSON file per document with entities, relations, evidence snippets

### 4. Validation
**Validation** checks that extracted data follows the correct format (JSON Schema) and contains required fields.

- Ensures all relationships have evidence
- Checks that dates are properly formatted
- Flags missing or malformed data
- **Tools**: JSON Schema validation (`schemas/extraction.json`)

### 5. Resolution
**Resolution** (or **entity resolution**) merges different mentions of the same entity.

For example:
- "OpenAI", "Open AI", "OpenAI Inc." → all resolve to canonical ID `org:openai`
- "GPT-4", "GPT4", "GPT 4" → all resolve to `model:gpt-4`

This prevents duplicate nodes in the graph.

**Tools**: `src/resolve/` module (uses fuzzy matching, aliases, external IDs)

### 6. Export
**Export** converts the internal database format into Cytoscape.js-compatible JSON for visualization.

Generates multiple **views**:
- `mentions.json`: Document-entity mention connections
- `claims.json`: Semantic entity-to-entity relationships
- `dependencies.json`: Technical dependency relationships only
- `trending.json`: Filtered to high-velocity/high-novelty items

**Output location**: `data/graphs/{date}/{view}.json`

---

## Entity Types (Node Types)

These are the categories of entities we track. Each has a specific prefix in its canonical ID.

| Type | Description | Example | Canonical ID |
|------|-------------|---------|--------------|
| **Org** | Organization (company, agency, non-profit) | OpenAI, CDC, Microsoft | `org:openai` |
| **Person** | Individual person | Sam Altman, Yann LeCun | `person:sam_altman` |
| **Program** | Government or organizational program | DARPA AI Next, EU AI Act | `program:ai_next` |
| **Tool** | Software tool or application | LangChain, AutoGPT | `tool:langchain` |
| **Model** | AI/ML model | GPT-4, Claude, LLaMA | `model:gpt-4` |
| **Dataset** | Training or evaluation dataset | ImageNet, LAION-5B | `dataset:imagenet` |
| **Benchmark** | Performance evaluation benchmark | MMLU, HellaSwag | `benchmark:mmlu` |
| **Paper** | Academic publication | "Attention Is All You Need" | `paper:attention_is_all_you_need` |
| **Repo** | Code repository | huggingface/transformers | `repo:transformers` |
| **Document** | Source document (article, blog post) | News article, blog post | `doc:2025-12-01_nextgov_409826` |
| **Tech** | Technology or technique | RAG, fine-tuning, RLHF | `tech:rag` |
| **Topic** | General topic or theme | AI safety, interpretability | `topic:ai_safety` |
| **Event** | Conference, launch event, announcement | NeurIPS 2025, GPT-4 launch | `event:neurips_2025` |
| **Location** | Geographic location | Silicon Valley, EU | `location:eu` |
| **Other** | Catch-all for entities that don't fit above categories | Various | `other:{slug}` |

---

## Relationship Types (Edge Types)

These are the canonical relationship labels we use. Each describes a specific type of connection.

### Document Relationships
| Relation | Meaning | Example |
|----------|---------|---------|
| **MENTIONS** | Document mentions an entity | Article mentions "OpenAI" |
| **CITES** | Document cites another document/paper | Blog post cites research paper |
| **ANNOUNCES** | Document announces something new | Press release announces new model |

### Organizational & People Relationships
| Relation | Meaning | Example |
|----------|---------|---------|
| **LAUNCHED** | Org/person launched a product/model | OpenAI LAUNCHED GPT-4 |
| **PUBLISHED** | Org/person published a paper/dataset | Google PUBLISHED PaLM paper |
| **UPDATED** | Org/person released an update | Anthropic UPDATED Claude |
| **FUNDED** | Org/person provided funding | Microsoft FUNDED OpenAI |
| **PARTNERED_WITH** | Collaboration between entities | OpenAI PARTNERED_WITH Microsoft |
| **ACQUIRED** | One org acquired another | Microsoft ACQUIRED GitHub |
| **HIRED** | Org hired a person | OpenAI HIRED Sam Altman |
| **CREATED** | Org/person created something | Meta CREATED LLaMA |
| **OPERATES** | Org operates a program/service | CDC OPERATES AI initiatives |
| **GOVERNS** / **GOVERNED_BY** | Governance relationship | EU GOVERNS AI Act |
| **REGULATES** | Regulatory oversight | FDA REGULATES medical AI |
| **COMPLIES_WITH** | Compliance relationship | System COMPLIES_WITH GDPR |

### Technical Relationships
| Relation | Meaning | Example |
|----------|---------|---------|
| **USES_TECH** | Uses a technology/technique | System USES_TECH RAG |
| **USES_MODEL** | Uses an AI model | Application USES_MODEL GPT-4 |
| **USES_DATASET** | Uses a dataset | Research USES_DATASET ImageNet |
| **TRAINED_ON** | Model trained on dataset | GPT-4 TRAINED_ON CommonCrawl |
| **EVALUATED_ON** | Model evaluated on benchmark | Claude EVALUATED_ON MMLU |
| **INTEGRATES_WITH** | Technical integration | LangChain INTEGRATES_WITH OpenAI |
| **DEPENDS_ON** | Dependency relationship | Tool DEPENDS_ON Python library |
| **REQUIRES** | Hard requirement (compute/hardware) | Model REQUIRES GPU cluster |
| **PRODUCES** | Generates output | Pipeline PRODUCES embeddings |
| **MEASURES** | Benchmark measures capability | MMLU MEASURES reasoning ability |

### Analysis Relationships
| Relation | Meaning | Example |
|----------|---------|---------|
| **PREDICTS** | Forecasting relationship | Model PREDICTS stock prices |
| **DETECTS** | Detection capability | System DETECTS anomalies |
| **MONITORS** | Monitoring relationship | Tool MONITORS model performance |

---

## Data Structures

### Document Record
A **document record** is the database entry for each ingested source document.

**Database table**: `documents`

**Key fields**:
- `doc_id`: Unique identifier (e.g., `2025-12-01_nextgov_409826`)
- `url`: Source URL
- `source`: Publisher name (e.g., "Nextgov", "arXiv")
- `title`: Article title
- `published_at`: When the article was published (ISO-8601 date)
- `fetched_at`: When we downloaded it (ISO-8601 datetime)
- `raw_path`: Path to raw HTML file
- `text_path`: Path to cleaned text file
- `content_hash`: Hash of cleaned text (for deduplication)
- `status`: Processing status (`fetched`, `cleaned`, `extracted`, `error`)

### DocPack (Daily Bundle)
A **DocPack** is a collection of all documents processed on a given day, bundled into two formats:

1. **JSONL file** (JSON Lines): One JSON object per line, machine-readable
2. **Markdown file**: Human-readable format for pasting into ChatGPT

Used for Mode B (manual extraction workflow).

### Extraction Output
**Extraction output** is the structured data extracted from a single document.

**File location**: `data/extractions/{docId}.json`

**Top-level structure**:
```json
{
  "docId": "2025-12-01_nextgov_409826",
  "extractorVersion": "1.0",
  "entities": [ /* list of entities */ ],
  "relations": [ /* list of relationships */ ],
  "techTerms": [ /* list of technology terms */ ],
  "dates": [ /* list of temporal references */ ],
  "notes": [ /* optional warnings or flags */ ]
}
```

### Entity Object
**Entity object** represents a single extracted entity.

**Structure**:
```json
{
  "name": "Centers for Disease Control and Prevention",
  "type": "Org",
  "aliases": ["CDC", "Centers for Disease Control"],
  "externalIds": {
    "wikidata": "Q583725"
  },
  "idHint": "org:cdc"
}
```

**Key fields**:
- `name`: How the entity appears in the text (surface form)
- `type`: Entity category (Org, Person, Model, etc.)
- `aliases`: Alternative names or abbreviations
- `externalIds`: Links to external databases (Wikidata, etc.)
- `idHint`: Suggested canonical ID (may be adjusted during resolution)

### Relation Object
**Relation object** represents a single extracted relationship.

**Structure**:
```json
{
  "source": "org:cdc",
  "rel": "USES_MODEL",
  "target": "model:gpt-4",
  "kind": "asserted",
  "confidence": 0.95,
  "verbRaw": "deployed",
  "polarity": "pos",
  "modality": "observed",
  "time": { /* temporal info */ },
  "evidence": [ /* evidence snippets */ ]
}
```

**Key fields**:
- `source`: Starting entity (canonical ID or name)
- `rel`: Relationship type (from canonical taxonomy)
- `target`: Ending entity
- `kind`: Confidence level in claim origin
  - `asserted`: Directly stated in source text
  - `inferred`: Logically derived from stated facts
  - `hypothesis`: Speculation or weak signal
- `confidence`: Numeric confidence score (0.0 to 1.0)
- `verbRaw`: The actual verb used in source text (e.g., "deployed", "announced")
- `polarity`: Sentiment (`pos`, `neg`, `unclear`)
- `modality`: Temporal status
  - `observed`: Already happened
  - `planned`: Stated future plan
  - `speculative`: Hypothetical or uncertain
- `time`: Temporal reference (when the relationship occurred/will occur)
- `evidence`: List of evidence snippets supporting this claim

### Evidence Object
**Evidence object** provides provenance for a claim.

**Structure**:
```json
{
  "docId": "2025-12-01_nextgov_409826",
  "url": "https://www.nextgov.com/artificial-intelligence/...",
  "published": "2025-12-01",
  "snippet": "The CDC deployed GPT-4 to analyze public health data",
  "charSpan": { "start": 1234, "end": 1302 }
}
```

**Key fields**:
- `docId`: Which document this evidence comes from
- `url`: Source URL
- `published`: Publication date
- `snippet`: Short quote from the text (≤200 characters)
- `charSpan`: Character positions in original text (optional)

### Date Model
**Date model** captures temporal references with varying precision.

**Structure**:
```json
{
  "text": "this fall",
  "start": "2025-09-01",
  "end": "2025-11-30",
  "resolution": "range",
  "anchor": "2025-12-01"
}
```

**Fields**:
- `text`: Original phrase from source text (always preserved)
- `start`: Normalized start date (ISO-8601)
- `end`: Normalized end date (ISO-8601)
- `resolution`: Precision level
  - `exact`: Specific date ("December 1, 2025")
  - `range`: Date range ("Q3 2025", "this fall")
  - `anchored_to_published`: Relative to publish date ("next month", "last year")
  - `unknown`: Cannot normalize
- `anchor`: Reference date used for normalization (usually publish date)

### Cytoscape Elements
**Cytoscape elements** is the JSON format used by Cytoscape.js for graph visualization.

**Structure**:
```json
{
  "meta": { /* metadata about the export */ },
  "elements": {
    "nodes": [ /* array of node objects */ ],
    "edges": [ /* array of edge objects */ ]
  }
}
```

**Node object**:
```json
{
  "data": {
    "id": "org:openai",
    "label": "OpenAI",
    "type": "Org",
    "aliases": ["OpenAI Inc.", "Open AI"],
    "firstSeen": "2025-10-15",
    "lastSeen": "2026-01-24"
  }
}
```

**Edge object**:
```json
{
  "data": {
    "id": "e:org:openai->model:gpt-4",
    "source": "org:openai",
    "target": "model:gpt-4",
    "rel": "LAUNCHED",
    "kind": "asserted",
    "confidence": 0.98
  }
}
```

---

## Extraction and Processing

### LLM (Large Language Model)
An **LLM** is an AI system trained on vast amounts of text that can understand and generate human-like text. Examples: GPT-4, Claude, LLaMA.

In this project, LLMs are used for **extraction**—reading article text and identifying entities, relationships, and other structured information.

### Extraction Mode
The project supports two **extraction modes**:

**Mode A (Automated)**:
- Uses LLM API (OpenAI, Anthropic, etc.)
- Fully automated: script sends text, receives structured JSON
- Requires API key and costs money per document

**Mode B (Semi-Manual)**:
- User pastes text into ChatGPT web interface
- User copies LLM's response back into a file
- Free (uses ChatGPT free tier)
- Slower but works without API access

### JSON Schema
A **JSON Schema** is a specification that defines the structure and validation rules for JSON data.

Example: Our extraction schema says:
- `entities` must be an array
- Each entity must have a `name` (string) and `type` (enum)
- `relations` must include `evidence` (non-empty array)

This catches errors early and ensures data quality.

### Entity Resolution
**Entity resolution** (also called **deduplication** or **record linkage**) is the process of determining when different text mentions refer to the same real-world entity.

**Challenges**:
- Variations: "GPT-4", "GPT4", "GPT 4"
- Abbreviations: "CDC" vs "Centers for Disease Control and Prevention"
- Ambiguity: "Apple" (fruit vs company)

**Techniques used**:
- String similarity (fuzzy matching)
- Alias lists
- External IDs (Wikidata, DOIs)
- Context clues (entity type, co-occurring entities)

### Canonical ID
A **canonical ID** is the single, stable identifier chosen to represent an entity across all documents.

**Format**: `{type}:{slug}`

**Examples**:
- `org:openai` (not `org:open_ai` or `org:openai_inc`)
- `model:gpt-4` (not `model:gpt4`)

**Benefits**:
- Consistency: All systems use the same ID
- Clarity: ID indicates entity type
- URL-safe: Can be used in file paths and URLs

### Slug
A **slug** is a URL-safe, human-readable identifier derived from a name.

**Rules**:
- Lowercase only
- Alphanumerics and underscores only
- No spaces or punctuation
- Short and memorable

**Examples**:
- "OpenAI" → `openai`
- "GPT-4" → `gpt_4`
- "Retrieval-Augmented Generation" → `rag`

### Confidence Score
A **confidence score** (0.0 to 1.0) represents how certain we are about a claim.

**Factors**:
- Explicitness: Direct quote vs paraphrase
- Source authority: Official announcement vs rumor
- Evidence quality: Multiple corroborating sources vs single mention
- Extraction quality: LLM returned high vs low confidence

**Usage**: Low-confidence claims can be filtered out in the UI or marked as "hypothesis."

---

## Graph Visualization

### Node
A **node** (also called **vertex**) is a visual element in the graph representing an entity.

**Visual properties**:
- **Position**: x, y coordinates on canvas
- **Size**: Scaled by velocity/importance
- **Color**: Indicates entity type
- **Opacity**: Fades with age (recency)
- **Label**: Entity name

### Edge
An **edge** (also called **link** or **arc**) is a visual element connecting two nodes, representing a relationship.

**Visual properties**:
- **Line style**: Solid (asserted), dashed (inferred), dotted (hypothesis)
- **Thickness**: Scaled by confidence score
- **Color**: Gray default; green for new edges
- **Direction**: Arrow indicates relationship direction

### Graph Layout
**Graph layout** is the algorithm that determines node positions.

**Layout types**:
- **Force-directed**: Nodes repel, edges act like springs → organic clustering
  - Used: fcose (fast Compound Spring Embedder)
- **Preset**: Nodes placed at stored coordinates → fast, stable positions
- **Hierarchical**: Nodes arranged in layers (not used in V1)

**Why it matters**: Good layout makes patterns visible; bad layout creates "hairball" graphs that are unreadable.

### Cytoscape.js
**Cytoscape.js** is a JavaScript library for visualizing and interacting with graphs in web browsers.

**Features**:
- Renders thousands of nodes/edges
- Interactive: pan, zoom, click, drag
- Customizable visual styling
- Layout algorithms built-in
- Event handling for user interactions

**Why we use it**: Industry-standard, performant, well-documented.

### Graph View
A **graph view** is a filtered or focused subset of the full knowledge graph.

**Views in this project**:
1. **Mentions view**: Shows which documents mention which entities (bipartite graph)
2. **Claims view**: Shows semantic entity-to-entity relationships (all relation types)
3. **Dependencies view**: Shows only technical dependency relationships (USES_*, DEPENDS_ON, REQUIRES)
4. **Trending view**: Shows only high-velocity, high-novelty nodes and edges

Each view is exported as a separate JSON file.

### Filter Panel
The **filter panel** is a UI component that lets users show/hide graph elements based on criteria:

- **Date range**: Show only entities/edges within a time period
- **Entity types**: Show only Orgs, Models, etc.
- **Relationship kinds**: Toggle asserted/inferred/hypothesis edges
- **Confidence threshold**: Hide low-confidence claims
- **Node search**: Highlight entities matching a query

### Neighborhood Highlighting
**Neighborhood highlighting** is an interaction pattern:

1. User clicks a node
2. Direct neighbors (connected nodes) stay visible and highlighted
3. All other nodes and edges are dimmed (low opacity)

This helps explore the local structure around a specific entity.

### Tooltip
A **tooltip** is a small popup that appears when you hover over a node or edge.

**Contents**:
- **Node tooltip**: Entity name, type, aliases
- **Edge tooltip**: Relationship type, confidence, evidence count

Tooltips provide quick context without opening a full detail panel.

### Detail Panel
The **detail panel** is a slide-out UI component showing comprehensive information about a selected node or edge.

**Node detail panel**:
- Full metadata (all aliases, external IDs)
- List of relationships (in/out edges)
- Source documents that mention this entity
- Timeline of mentions

**Edge detail panel** (Evidence panel):
- Relationship details (source, target, type, confidence)
- Provenance: all evidence snippets with links to source documents

---

## Scoring and Metrics

### Velocity
**Velocity** measures how fast an entity's mention frequency is increasing.

**Formula example**:
```
velocity = (mentions_last_7_days / mentions_previous_7_days) - 1
```

**Interpretation**:
- `velocity > 0`: Increasing mentions (accelerating trend)
- `velocity = 0`: Stable mention rate
- `velocity < 0`: Decreasing mentions (declining trend)

High velocity = emerging trend.

### Novelty
**Novelty** measures how new or rare an entity is.

**Factors**:
- Days since first seen (newer = more novel)
- Total mention count (rarer = more novel)

**Why it matters**: Novel entities are potential early signals of emerging trends.

### Bridge Score
**Bridge score** measures how well an entity connects different clusters or communities in the graph.

**Concept**: An entity with connections to multiple otherwise-separate groups acts as a "bridge" and may signal cross-domain innovation.

**Example**: A tool that connects both academic research and industrial deployment clusters could be a bridge entity.

### Trending Score
**Trending score** is a composite metric combining velocity, novelty, and bridge scores.

**Purpose**: Identify entities most likely to be important emerging trends.

High trending score = high priority for investigation.

### Mention Count
**Mention count** is simply the number of documents that mention an entity within a time window.

**Time windows**:
- `mention_count_7d`: Last 7 days
- `mention_count_30d`: Last 30 days
- `mention_count_total`: All time

### First Seen / Last Seen
**First seen** and **last seen** are timestamps tracking when an entity was first/last mentioned.

**Uses**:
- **First seen**: Calculate entity age (for novelty scoring)
- **Last seen**: Calculate recency (for visual opacity, filtering)

**Example**:
- Entity A: First seen 2025-10-01, last seen 2026-01-20 → Active for 3+ months, recently mentioned
- Entity B: First seen 2025-10-01, last seen 2025-10-15 → Short-lived, no recent mentions

---

## Technical Infrastructure

### RSS Feed
An **RSS feed** (Really Simple Syndication) is a standardized XML format for publishing frequently updated content.

**Structure**: Each feed item has:
- Title
- Link (URL)
- Description
- Publication date
- Author (optional)

**Why we use RSS**: Easy to monitor sources for new content without web scraping.

### SQLite
**SQLite** is a lightweight, file-based SQL database.

**Advantages**:
- No separate server process
- Single file storage
- Fast for small-to-medium datasets
- Excellent for local pipelines

**Usage in this project**: Stores document records, entity/relation data, aliases.

### JSONL (JSON Lines)
**JSONL** is a text format where each line is a complete, independent JSON object.

**Example**:
```
{"docId": "doc1", "title": "Article 1"}
{"docId": "doc2", "title": "Article 2"}
```

**Advantages**:
- Easy to stream/process line-by-line
- Append-friendly (add new entries at end)
- Human-readable but machine-parsable

**Usage**: Daily document bundles (DocPacks).

### Content Hash
A **content hash** is a unique fingerprint generated from file content.

**How it works**: Run content through a hash function (e.g., SHA-256) → get fixed-length string that changes if content changes.

**Uses**:
- **Deduplication**: Identical content → identical hash → skip re-processing
- **Change detection**: Re-fetch if hash differs

### ISO-8601
**ISO-8601** is the international standard format for dates and times.

**Formats**:
- Date only: `2025-12-01`
- Date and time: `2025-12-01T14:30:00Z`
- With timezone: `2025-12-01T14:30:00-05:00`

**Why it matters**: Sortable, unambiguous, widely supported.

### User-Agent
A **User-Agent** is an HTTP header that identifies the software making a web request.

**Good practice**: Set a clear User-Agent like `"AITrendGraph/1.0 (+https://example.com)"` so website operators know who's accessing their content.

**Why it matters**: Polite web scraping; some sites block requests without a User-Agent.

### Rate Limiting
**Rate limiting** means intentionally slowing down requests to avoid overwhelming a server.

**Example**: Wait 1 second between requests to the same domain.

**Why it matters**: Prevents getting IP-banned, reduces server load, is ethical.

### robots.txt
A **robots.txt** file is a standard used by websites to tell automated crawlers which pages they can/cannot access.

**Example**:
```
User-agent: *
Disallow: /admin/
```

**Best practice**: Check robots.txt before scraping and respect restrictions where practical.

### Readability Extraction
**Readability extraction** is the process of removing boilerplate (navigation, ads, footers) and keeping only the main article content.

**How it works**: Algorithms like Mozilla Readability analyze HTML structure to identify the primary content block.

**Output**: Clean text + metadata (title, author, publish date).

### Incremental Updates
**Incremental updates** means processing only new data, not re-processing everything from scratch.

**Benefits**:
- Faster: Only process new documents
- Efficient: Don't waste compute on unchanged data
- Scalable: Works as dataset grows

**Implementation**: Track processing status per document; skip documents already processed.

---

## Appendix: Example Workflow

To tie these concepts together, here's a complete example workflow:

1. **Ingestion**: Fetch new articles from arXiv RSS feed → save raw XML to `data/raw/`
2. **Cleaning**: Extract article text from XML → save to `data/text/`
3. **Extraction**: Send text to LLM API → receive JSON with entities and relations → save to `data/extractions/`
4. **Validation**: Check JSON against schema → flag errors
5. **Resolution**: Match "OpenAI" and "Open AI" → assign both to `org:openai`
6. **Storage**: Insert entities and relations into SQLite database
7. **Export**: Query database → generate Cytoscape JSON → save to `data/graphs/trending.json`
8. **Visualization**: Load `trending.json` in Cytoscape.js client → render interactive graph
9. **User interaction**: User clicks on "org:openai" node → sees detail panel with all relationships and source documents

---

## Quick Reference: Acronyms

| Acronym | Meaning |
|---------|---------|
| **AI** | Artificial Intelligence |
| **API** | Application Programming Interface |
| **CSV** | Comma-Separated Values |
| **DOI** | Digital Object Identifier |
| **HTML** | HyperText Markup Language |
| **HTTP** | HyperText Transfer Protocol |
| **JSON** | JavaScript Object Notation |
| **JSONL** | JSON Lines (one JSON object per line) |
| **LLM** | Large Language Model |
| **ML** | Machine Learning |
| **NLP** | Natural Language Processing |
| **RAG** | Retrieval-Augmented Generation |
| **RLHF** | Reinforcement Learning from Human Feedback |
| **RSS** | Really Simple Syndication |
| **SQL** | Structured Query Language |
| **URL** | Uniform Resource Locator |
| **XML** | eXtensible Markup Language |

---

## Further Reading

- **Knowledge Graphs**: See Stanford CS520 lecture notes or the book "Exploiting Linked Data and Knowledge Graphs in Large Organizations" (Springer)
- **Graph Visualization**: Cytoscape.js documentation (https://js.cytoscape.org)
- **Entity Resolution**: "Principles of Data Integration" by Doan, Halevy, Ives (Morgan Kaufmann)
- **Trend Detection**: "Mining of Massive Datasets" by Leskovec, Rajaraman, Ullman (Chapter 9: Recommendation Systems, adapted for trend signals)

---

**Document version**: 1.0
**Last updated**: 2026-02-07
**Maintained by**: Project contributors
