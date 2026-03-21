-- Documents table (ingested articles)
CREATE TABLE IF NOT EXISTS documents (
  doc_id TEXT PRIMARY KEY,
  url TEXT,
  source TEXT,
  source_type TEXT NOT NULL DEFAULT 'rss',  -- rss, bluesky, reddit, substack
  title TEXT,
  published_at TEXT,
  fetched_at TEXT,
  raw_path TEXT,
  text_path TEXT,
  content_hash TEXT,
  status TEXT,
  error TEXT,
  extracted_by TEXT,          -- model that produced the kept extraction
  quality_score REAL,         -- combined quality score (0.0-1.0)
  escalation_failed TEXT      -- non-NULL if specialist failed; contains error message
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

-- Bench table: qualified-but-budget-blocked articles for backfill on light days.
-- Articles that scored well enough to be selected but were bumped because the
-- daily budget cap was reached.  On days when fewer articles qualify than the
-- budget allows, bench articles backfill the remaining slots.
CREATE TABLE IF NOT EXISTS bench (
  doc_id TEXT PRIMARY KEY,
  quality_score REAL NOT NULL,
  scored_at TEXT NOT NULL,       -- date the article was originally scored (ISO date)
  expires_at TEXT NOT NULL,      -- date after which this bench entry is stale (ISO date)
  FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);

CREATE INDEX IF NOT EXISTS idx_bench_expires ON bench(expires_at);
CREATE INDEX IF NOT EXISTS idx_bench_quality ON bench(quality_score DESC);

-- =========================================================================
-- Operational analytics tables (Sprint 7)
-- These tables persist stats that were previously ephemeral (stdout / JSON
-- log files only).  They enable SQL-based debugging of the full document
-- funnel — from ingestion through trending — without log-file archaeology.
-- =========================================================================

-- Per-candidate scoring log — why each doc was selected, benched, or rejected.
-- One row per candidate per pipeline run.  Enables auditing "why didn't my
-- Bluesky articles get extracted?" by querying source_type + outcome.
CREATE TABLE IF NOT EXISTS doc_selection_log (
  doc_id            TEXT NOT NULL,
  run_date          TEXT NOT NULL,        -- ISO date of the pipeline run
  source            TEXT,
  source_type       TEXT,
  word_count        INTEGER,
  word_count_score  REAL,
  metadata_score    REAL,
  source_tier_score REAL,
  signal_type_score REAL,
  recency_score     REAL,
  combined_score    REAL,
  outcome           TEXT NOT NULL,        -- 'selected', 'benched', 'rejected'
  rejection_reason  TEXT,                 -- 'below_min_quality', 'budget_exceeded'
  PRIMARY KEY (doc_id, run_date)
);

CREATE INDEX IF NOT EXISTS idx_dsl_outcome ON doc_selection_log(outcome);
CREATE INDEX IF NOT EXISTS idx_dsl_source_type ON doc_selection_log(source_type);
CREATE INDEX IF NOT EXISTS idx_dsl_run_date ON doc_selection_log(run_date);

-- Per-feed health stats — one row per feed per pipeline run.
-- Tracks chronic feed problems and content volume by source.
CREATE TABLE IF NOT EXISTS feed_stats (
  run_date        TEXT NOT NULL,
  feed_name       TEXT NOT NULL,
  source_type     TEXT,
  docs_fetched    INTEGER DEFAULT 0,
  docs_new        INTEGER DEFAULT 0,
  docs_skipped    INTEGER DEFAULT 0,
  fetch_errors    INTEGER DEFAULT 0,
  error_message   TEXT,
  PRIMARY KEY (run_date, feed_name)
);

CREATE INDEX IF NOT EXISTS idx_feed_stats_date ON feed_stats(run_date);

-- Per-source extraction quality — aggregated extraction outcomes by source.
-- Answers "which feeds produce the worst extractions?" without manual joins.
CREATE TABLE IF NOT EXISTS source_extraction_quality (
  run_date           TEXT NOT NULL,
  source             TEXT NOT NULL,
  source_type        TEXT,
  docs_extracted     INTEGER DEFAULT 0,
  docs_escalated     INTEGER DEFAULT 0,
  docs_failed        INTEGER DEFAULT 0,
  avg_quality_score  REAL,
  entities_produced  INTEGER DEFAULT 0,
  relations_produced INTEGER DEFAULT 0,
  PRIMARY KEY (run_date, source)
);

CREATE INDEX IF NOT EXISTS idx_seq_date ON source_extraction_quality(run_date);

-- Entity trend scores over time — one row per entity per pipeline run.
-- Enables "how has velocity changed over 2 weeks?" queries and tracking
-- when entities enter/leave the trending view.
CREATE TABLE IF NOT EXISTS trend_history (
  entity_id         TEXT NOT NULL,
  run_date          TEXT NOT NULL,
  mention_count_7d  INTEGER,
  mention_count_30d INTEGER,
  velocity          REAL,
  novelty           REAL,
  bridge_score      REAL,
  trend_score       REAL,
  in_trending_view  INTEGER DEFAULT 0,  -- 1 if included in top-N export
  PRIMARY KEY (entity_id, run_date)
);

CREATE INDEX IF NOT EXISTS idx_th_run_date ON trend_history(run_date);
CREATE INDEX IF NOT EXISTS idx_th_trending ON trend_history(in_trending_view);

-- Durable pipeline run log — one row per daily run per domain.
-- Replaces ephemeral JSON log files for long-term health monitoring.
CREATE TABLE IF NOT EXISTS pipeline_runs (
  run_date          TEXT NOT NULL,
  domain            TEXT NOT NULL,
  status            TEXT NOT NULL,       -- 'success', 'partial', 'failed'
  duration_sec      REAL,
  started_at        TEXT,
  completed_at      TEXT,
  docs_ingested     INTEGER DEFAULT 0,
  docs_selected     INTEGER DEFAULT 0,
  docs_excluded     INTEGER DEFAULT 0,
  docs_extracted    INTEGER DEFAULT 0,
  docs_escalated    INTEGER DEFAULT 0,
  entities_new      INTEGER DEFAULT 0,
  entities_resolved INTEGER DEFAULT 0,
  relations_added   INTEGER DEFAULT 0,
  nodes_exported    INTEGER DEFAULT 0,
  edges_exported    INTEGER DEFAULT 0,
  trending_nodes    INTEGER DEFAULT 0,
  error_message     TEXT,
  -- LLM feature columns (Sprint 8)
  synthesis_batches       INTEGER DEFAULT 0,  -- cross-document synthesis batches processed
  synthesis_corroborated  INTEGER DEFAULT 0,  -- entities corroborated across docs
  synthesis_relations     INTEGER DEFAULT 0,  -- relations inferred via synthesis
  disambig_pairs          INTEGER DEFAULT 0,  -- gray-zone pairs evaluated by LLM
  disambig_merges         INTEGER DEFAULT 0,  -- LLM-confirmed entity merges
  disambig_kept_separate  INTEGER DEFAULT 0,  -- pairs LLM kept separate
  infer_rules             INTEGER DEFAULT 0,  -- inference rules evaluated
  infer_relations         INTEGER DEFAULT 0,  -- relations inferred via rules
  infer_skipped           INTEGER DEFAULT 0,  -- inferences skipped (already existed)
  narratives_generated    INTEGER DEFAULT 0,  -- trend narratives generated
  resolve_merges          INTEGER DEFAULT 0,  -- total entity merges (fuzzy + LLM)
  PRIMARY KEY (run_date, domain)
);

-- Per-stage funnel stats — tracks doc counts at each pipeline stage.
-- Answers "where did the 691 ingested docs go?" in a single query.
CREATE TABLE IF NOT EXISTS funnel_stats (
  run_date      TEXT NOT NULL,
  domain        TEXT NOT NULL,
  stage         TEXT NOT NULL,           -- 'ingest', 'select', 'extract', 'import',
                                         -- 'synthesize', 'resolve', 'infer', 'export', 'trending'
  docs_in       INTEGER DEFAULT 0,
  docs_out      INTEGER DEFAULT 0,
  docs_dropped  INTEGER DEFAULT 0,
  drop_reasons  TEXT,                    -- JSON: {"budget_exceeded": 12, "below_quality": 3}
  PRIMARY KEY (run_date, domain, stage)
);
