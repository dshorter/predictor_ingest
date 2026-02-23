-- Documents table (ingested articles)
CREATE TABLE IF NOT EXISTS documents (
  doc_id TEXT PRIMARY KEY,
  url TEXT,
  source TEXT,
  title TEXT,
  published_at TEXT,
  fetched_at TEXT,
  raw_path TEXT,
  text_path TEXT,
  content_hash TEXT,
  status TEXT,
  error TEXT
);

CREATE INDEX IF NOT EXISTS idx_documents_url ON documents(url);
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash);

-- Entities table (extracted entities with canonical IDs)
CREATE TABLE IF NOT EXISTS entities (
  entity_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  aliases TEXT,  -- JSON array of alias strings
  external_ids TEXT,  -- JSON object e.g. {"wikidata": "Q123"}
  -- first_seen and last_seen are derived from the PUBLISHED DATE of the
  -- source article, NOT the date our pipeline fetched it. This means:
  --   - Retroactive imports of older articles correctly backdate entities
  --   - Trend scores reflect real-world publication velocity
  --   - Client date filtering matches actual article age
  first_seen TEXT,  -- Earliest article published_at that mentions this entity (ISO date)
  last_seen TEXT    -- Latest article published_at that mentions this entity (ISO date)
);

CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);

-- Relations table (extracted relationships between entities)
CREATE TABLE IF NOT EXISTS relations (
  relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL,
  rel TEXT NOT NULL,
  target_id TEXT NOT NULL,
  kind TEXT NOT NULL,  -- asserted, inferred, hypothesis
  confidence REAL NOT NULL,
  doc_id TEXT,
  extractor_version TEXT,
  verb_raw TEXT,
  polarity TEXT,
  modality TEXT,
  time_text TEXT,
  time_start TEXT,
  time_end TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,  -- Pipeline insertion time (not article date)
  FOREIGN KEY (source_id) REFERENCES entities(entity_id),
  FOREIGN KEY (target_id) REFERENCES entities(entity_id),
  FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);

CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
CREATE INDEX IF NOT EXISTS idx_relations_rel ON relations(rel);
CREATE INDEX IF NOT EXISTS idx_relations_doc ON relations(doc_id);

-- Prevent duplicate relations from re-imports.  A relation is uniquely
-- identified by (source_id, rel, target_id, kind, doc_id).  The
-- COALESCE wrapper handles NULL doc_id values so the index still works.
CREATE UNIQUE INDEX IF NOT EXISTS idx_relations_dedup
    ON relations(source_id, rel, target_id, kind, COALESCE(doc_id, ''));

-- Evidence table (provenance for relations)
CREATE TABLE IF NOT EXISTS evidence (
  evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
  relation_id INTEGER NOT NULL,
  doc_id TEXT NOT NULL,
  url TEXT,
  published TEXT,
  snippet TEXT NOT NULL,
  char_start INTEGER,
  char_end INTEGER,
  FOREIGN KEY (relation_id) REFERENCES relations(relation_id),
  FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);

CREATE INDEX IF NOT EXISTS idx_evidence_relation ON evidence(relation_id);

-- Entity aliases table (for entity resolution)
CREATE TABLE IF NOT EXISTS entity_aliases (
  alias TEXT PRIMARY KEY,
  canonical_id TEXT NOT NULL,
  FOREIGN KEY (canonical_id) REFERENCES entities(entity_id)
);

CREATE INDEX IF NOT EXISTS idx_aliases_canonical ON entity_aliases(canonical_id);

-- Extraction comparison table (shadow mode understudy tracking)
-- Tracks how well understudy models perform vs the primary (Sonnet)
CREATE TABLE IF NOT EXISTS extraction_comparison (
  doc_id TEXT NOT NULL,
  run_date TEXT NOT NULL,
  understudy_model TEXT NOT NULL,

  -- Did it work at all?
  schema_valid INTEGER NOT NULL DEFAULT 0,  -- 0/1 boolean
  parse_error TEXT,

  -- Counts from primary (Sonnet)
  primary_entities INTEGER,
  primary_relations INTEGER,
  primary_tech_terms INTEGER,

  -- Counts from understudy
  understudy_entities INTEGER,
  understudy_relations INTEGER,
  understudy_tech_terms INTEGER,

  -- Match rates (computed after both complete)
  entity_overlap_pct REAL,
  relation_overlap_pct REAL,

  -- Timing
  primary_duration_ms INTEGER,
  understudy_duration_ms INTEGER,

  created_at TEXT DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (doc_id, understudy_model)
);

CREATE INDEX IF NOT EXISTS idx_comparison_model ON extraction_comparison(understudy_model);
CREATE INDEX IF NOT EXISTS idx_comparison_date ON extraction_comparison(run_date);

-- Quality evaluation runs (Phase 0 instrumentation + Phase 1 gates)
-- One row per extraction attempt (cheap pass, specialist pass, etc.)
CREATE TABLE IF NOT EXISTS quality_runs (
  run_id TEXT PRIMARY KEY,
  doc_id TEXT NOT NULL,
  pipeline_stage TEXT NOT NULL,        -- 'cheap_extract', 'specialist_extract'
  model TEXT NOT NULL,
  provider TEXT,
  started_at TEXT NOT NULL,
  duration_ms INTEGER,
  status TEXT NOT NULL,                -- 'ok', 'error'
  decision TEXT NOT NULL,              -- 'accept', 'escalate', 'reject'
  decision_reason TEXT,
  quality_score REAL,                  -- combined score from scoring function
  input_chars INTEGER,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  total_tokens INTEGER,
  extra_json TEXT,                     -- overflow for future fields
  FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);

CREATE INDEX IF NOT EXISTS idx_quality_runs_doc ON quality_runs(doc_id);
CREATE INDEX IF NOT EXISTS idx_quality_runs_stage ON quality_runs(pipeline_stage);
CREATE INDEX IF NOT EXISTS idx_quality_runs_started ON quality_runs(started_at);

-- Per-metric rows for each quality run (gates + signals)
-- Enables SQL aggregation across runs: AVG(metric_value) WHERE metric_name = 'evidence_fidelity_rate'
CREATE TABLE IF NOT EXISTS quality_metrics (
  run_id TEXT NOT NULL,
  metric_name TEXT NOT NULL,           -- e.g. 'evidence_fidelity_rate', 'orphan_rate'
  metric_value REAL,
  passed INTEGER,                      -- 0/1 — did this metric pass its threshold?
  severity INTEGER NOT NULL DEFAULT 0, -- 0=info, 1=warn, 2=gate
  threshold_value REAL,                -- threshold used for pass/fail
  notes TEXT,                          -- debug info (e.g. failed snippet list)
  PRIMARY KEY (run_id, metric_name),
  FOREIGN KEY (run_id) REFERENCES quality_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_quality_metrics_name ON quality_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_quality_metrics_passed ON quality_metrics(passed);
