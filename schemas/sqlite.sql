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
  first_seen TEXT,
  last_seen TEXT
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
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (source_id) REFERENCES entities(entity_id),
  FOREIGN KEY (target_id) REFERENCES entities(entity_id),
  FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);

CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
CREATE INDEX IF NOT EXISTS idx_relations_rel ON relations(rel);
CREATE INDEX IF NOT EXISTS idx_relations_doc ON relations(doc_id);

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
