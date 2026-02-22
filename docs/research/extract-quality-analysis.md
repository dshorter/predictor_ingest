# predictor_ingest — Extract Quality Evaluation & Model Escalation (Offline Batch)

**Purpose:** Define a token-aware, offline evaluation layer for `extract` outputs (entities/relations/evidence/dates/techTerms) that feed graph exports and a web UI.

**Operating mode:** Offline/batch ingest. **Thoroughness + trust > speed**.

---

## 1) Scope & principles

- Outputs are consumed by a graph UI; the “trust contract” is **click edge → see provenance**.
- Highest-risk failure is **silent graph poisoning**: plausible-but-fake evidence snippets, or edges that don’t bind to nodes.
- Prefer **deterministic validation** first; use probabilistic (LLM) steps only when they clearly reduce total cost or improve correctness.
- Track **tokens by stage/model** to avoid surprises as gates and optional judge steps are introduced.
- Keep evaluation mostly **domain-agnostic**; domain-specific thresholds should live in a domain profile/config where possible.

---

## 2) Current baseline (what exists today)

### 2.1 Model selection & routing
- Primary model is config-driven (env) with a default fallback.
- Understudy model is config-driven (env).
- Provider routing heuristic is currently based on model-id prefix (OpenAI vs Anthropic).
- Strict schema enforcement is used for OpenAI tool calls (`strict: true`).

### 2.2 Run modes
- **single:** primary only
- **shadow:** primary + understudy; compute overlap stats; does **not** select between outputs
- **escalation:** cheap pass → quality score → if low, rerun with specialist

### 2.3 Current quality score (high level)
- Weighted blend of: entity density, evidence coverage, avg confidence, relation/entity ratio, tech terms presence
- Escalate if `combined_score < threshold` (currently 0.6)

**Known gaps:**
- Evidence *presence* ≠ evidence *fidelity* (hallucinated snippets can pass)
- Confidence is easy to game
- Density/ratio are length-sensitive
- “tech_terms_min” is described in a domain-specific way in comments (should be domain-agnostic or moved to a domain profile)

---

## 3) Target evaluation architecture

Separate evaluation into 3 layers:

1) **Fidelity gates (non-negotiable):** prevent poisoned edges + broken provenance  
2) **Structure quality signals:** detect schema-valid but semantically broken output  
3) **Coverage signals:** density/recall-ish metrics (useful, but not safety-critical)

Decision logic:
- If **any gate fails** → escalate (or reject asserted edges)
- Else: compute structure/coverage score → decide escalate vs accept

---

## 4) Non-negotiable gates (CPU deterministic)

These gates add **0 model tokens** and should be run for every extraction.

### Gate A — Evidence fidelity (snippet-in-text)
**Goal:** ensure evidence snippets actually exist in the text the model saw.

Rule:
- For each **asserted** relation evidence snippet:
  - normalize whitespace + case
  - check substring match in the **exact model-input text** (cleaned article text; not raw HTML)
- `evidence_fidelity_rate = matched / asserted_snippets`

Recommended hard gate:
- If `evidence_fidelity_rate < 0.70` → escalate

Store debug:
- list of failed snippets (snippet, relation id, docId/url, optionally surrounding context window)

### Gate B — Orphan endpoint check
**Goal:** ensure every relation binds to existing nodes.

Rule:
- every relation `source` and `target` must match an entity name (case-insensitive / normalized)
- `orphan_rate = orphan_relations / total_relations`

Recommended hard gate:
- If `orphan_rate > 0` → escalate  
  (optionally allow a tiny tolerance only after resolver/alias strategy exists)

### Gate C — Zero-value patterns
**Goal:** catch “schema-valid but empty/useless” outputs.

Examples:
- If doc length is “large” and `n_entities == 0` → escalate
- If doc length is “large” and `n_relations == 0` → escalate
- If `n_entities > X` but `n_relations == 0` → escalate

**Note:** thresholds depend on doc length bins; tune during calibration.

### Gate D — High-confidence asserted + bad evidence
**Goal:** detect worst failure mode.

Rule:
- If relation is asserted, confidence is high, and evidence fidelity fails → immediate escalate

---

## 5) Deterministic signals to log (then decide what becomes gates)

These are cheap-ish CPU checks. Initially: **log** and use as score inputs; only promote to gates after calibration.

1) **Duplicate / fragmentation penalty**
- Normalize entity names; penalize large duplicate clusters
- Metrics: `dup_cluster_count`, `dup_entity_rate`

2) **Entity type sanity distribution**
- Metrics: `type_entropy`, `other_type_rate`
- Flag: extreme single-type dominance (esp. `Other` dominance)

3) **Relation kind distribution sanity**
- Metric: `asserted_fraction`
- Flag: `n_relations > 0` and `asserted == 0` (possible “mark everything inferred” gaming)

4) **Confidence calibration weirdness**
- Metrics: `confidence_mean`, `confidence_std`
- Flag: near-zero variance (“flat confidence”) + middling mean

5) **Self-loop / degenerate relation patterns**
- Metric: `self_loop_rate` where source == target

6) **Evidence snippet stats**
- Metrics: `avg_len`, `too_short_rate`, `too_long_rate`, `ellipsis_rate`

7) **Tech terms quality (domain-agnostic)**
- Metrics: `uniq_rate`, `junk_rate`, `overlap_with_entities_rate`
- Guidance: do not hard-gate until domain-profile decision is settled

8) **Dates usefulness (light)**
- Metric: unknown-resolution rate vs presence of explicit dates (log-only for now)

---

## 6) Optional Tier-3: LLM judge pass (probabilistic)

Use only if it reduces total cost (e.g., avoids frequent specialist re-extract calls).

Judge prompt asks for **counts/flags only**:
- “Do evidence snippets appear in the input text?” (Y/N + counts)
- “Any orphan endpoints?” (Y/N + counts)

Decision:
- Use judge only for borderline cases; escalate to specialist only if judge flags “yikes”.

---

## 7) Comparison matrix (CPU vs LLM intensity) + leaning status

Legend:
- **CPU deterministic:** no model tokens
- **LLM probabilistic:** adds token cost/variance

| Heuristic | Tier | CPU cost | LLM cost | Best role | Leaning |
|---|---:|---|---|---|---|
| Evidence fidelity (exact + normalized substring) | 1 | Low–Med | None | **Hard gate** | ✅ |
| Evidence fidelity near-match (fuzzy) | 2 | Med–High | None | Gate/score (only if needed) | 🟡 |
| Orphan endpoints | 1 | Low | None | **Hard gate** | ✅ |
| Zero-value patterns | 1 | Low | None | **Hard gate** | ✅ |
| High-conf asserted + bad evidence | 1 | Low | None | **Immediate escalate** | ✅ |
| Duplicate/fragmentation | 1 | Med (avoid O(n²)) | None | Penalty | ✅ |
| Type entropy / Other rate | 1 | Low | None | Penalty | ✅ |
| Kind distribution sanity | 1 | Low | None | Penalty / conditional gate | ✅/🟡 |
| Confidence variance weirdness | 1 | Low | None | Penalty | 🟡 |
| Snippet length/quality stats | 2 | Low | None | Penalty | 🟡 |
| Tech terms quality | 2 | Low–Med | None | Penalty | 🟡 |
| Date usefulness | 2 | Low–Med | None | Light penalty | 🟡 |
| Judge pass | 3 | Low | Med | Optional middle step | 🟡 |
| Specialist re-extract | 3 | Low | High | Final fallback | 🟡 |

✅ = adopt early; 🟡 = defer until calibration proves value

---

## 8) Structured per-doc quality report (v0)

### Why
- Calibration wants **more data**, not less.
- Enables UI-level filters later (e.g., “show only high-trust edges”).
- Makes token/cost tracking explicit.

### Recommended storage strategy
- Store **summary metrics** in SQLite for easy aggregation
- Store **verbose debug artifacts** (lists, full JSON) in `quality_artifacts` (or file paths)

### `_quality` (conceptual schema)
- `run`: run/stage/model metadata
- `tokens`: usage per stage
- `counts`: entity/relation breakdown
- `gates`: pass/fail + measured values + failed examples
- `signals`: quality features for calibration
- `decision`: accept/escalate + reason + thresholds snapshot

Example shape (abbrev):
~~~json
{
  "_quality": {
    "run": {
      "runId": "uuid",
      "docId": "doc_id",
      "mode": "single|shadow|escalation",
      "stage": "cheap_extract|judge|specialist_extract",
      "pipelineVersion": "git_sha_or_semver",
      "provider": "openai|anthropic",
      "model": "gpt-5-mini",
      "schemaVersion": "extraction_schema_tag",
      "startedAt": "2026-02-22T00:00:00Z",
      "durationMs": 1234,
      "status": "ok|error"
    },
    "tokens": {
      "promptTokens": 0,
      "completionTokens": 0,
      "totalTokens": 0,
      "inputChars": 0,
      "inputTokensEstimate": 0,
      "toolSchemaTokensEstimate": 0
    },
    "counts": {
      "entities": 0,
      "relations": 0,
      "asserted": 0,
      "inferred": 0,
      "hypothesis": 0,
      "techTerms": 0,
      "dates": 0
    },
    "gates": {
      "schemaValid": true,
      "zeroValue": { "passed": true, "reason": "" },
      "orphanEndpoints": { "passed": true, "orphanRate": 0.0, "orphans": [] },
      "evidenceFidelity": {
        "passed": true,
        "matchRate": 0.0,
        "method": "exact+normalized",
        "failedSnippets": []
      }
    },
    "signals": {
      "entityDensityPer1kChars": 0.0,
      "relEntityRatio": 0.0,
      "avgConfidence": 0.0,
      "confidenceStd": 0.0,
      "assertedFraction": 0.0,
      "typeEntropy": 0.0,
      "otherTypeRate": 0.0,
      "duplication": { "clusterCount": 0, "dupRate": 0.0 }
    },
    "decision": {
      "escalate": false,
      "reason": "gate_failed:evidenceFidelity|gate_failed:orphans|quality_low:...",
      "qualityScore": 0.0,
      "thresholds": { "evidenceFidelityMin": 0.7, "orphanMax": 0.0 }
    }
  }
}
~~~

---

## 9) Token / cost tracking requirements

Per model call (cheap/judge/specialist):
- model, provider, schemaVersion, duration
- prompt_tokens, completion_tokens, total_tokens
- input_chars + token estimate fallback

Per doc overall:
- total tokens across stages
- number of stages
- escalate reason (gate failure vs score-based)

---

## 10) TechTerms: domain-agnostic plan

- `techTerms` is useful across domains/sectors; keep the field in the core schema.
- Fix domain leakage by either:
  - (A) renaming scoring concept to domain-neutral (`concept_terms_*`), and/or
  - (B) moving “minimum tech terms” thresholds into a domain profile/config

For calibration:
- log tech term metrics
- avoid hard gate until domain profile decision is finalized

---

## 11) SQLite reporting: can it handle this?

SQLite remains a good fit for **single-user offline** batch calibration **if**:
- queryable metrics are stored in structured tables
- huge verbose debug payloads are stored as artifacts (not queried heavily as JSON)

Key caveat:
- avoid overwriting history; prefer **append-only** runs keyed by `run_id`.

---

## 12) SQLite “table trio” (runs / metrics / artifacts)

Use these tables to store structured metrics plus verbose payloads.

~~~sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS quality_runs (
  run_id TEXT PRIMARY KEY,              -- uuid
  doc_id TEXT NOT NULL,
  pipeline_stage TEXT NOT NULL,         -- 'cheap_extract'|'judge'|'specialist_extract'
  pipeline_version TEXT NOT NULL,       -- git sha / semver
  model TEXT NOT NULL,
  provider TEXT,
  schema_version TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  duration_ms INTEGER,
  status TEXT NOT NULL,                 -- 'ok'|'error'
  decision TEXT NOT NULL,               -- 'accept'|'escalate'|'reject'
  decision_reason TEXT,

  input_chars INTEGER,
  input_tokens_est INTEGER,

  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  total_tokens INTEGER,

  temperature REAL,
  max_output_tokens INTEGER,
  seed INTEGER,

  extra_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_quality_runs_doc_id     ON quality_runs(doc_id);
CREATE INDEX IF NOT EXISTS idx_quality_runs_stage      ON quality_runs(pipeline_stage);
CREATE INDEX IF NOT EXISTS idx_quality_runs_started_at ON quality_runs(started_at);

CREATE TABLE IF NOT EXISTS quality_metrics (
  run_id TEXT NOT NULL,
  metric_name TEXT NOT NULL,            -- e.g., 'evidence_fidelity_rate'
  metric_value REAL,
  metric_text TEXT,
  threshold_value REAL,
  threshold_text TEXT,
  passed INTEGER,                       -- 0/1
  severity INTEGER,                     -- 0=info, 1=warn, 2=gate
  notes TEXT,
  PRIMARY KEY (run_id, metric_name),
  FOREIGN KEY (run_id) REFERENCES quality_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_quality_metrics_name   ON quality_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_quality_metrics_passed ON quality_metrics(passed);

CREATE TABLE IF NOT EXISTS quality_artifacts (
  artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  artifact_type TEXT NOT NULL,          -- 'quality_report_v0','missing_evidence','orphans','dup_clusters', etc
  content_text TEXT,
  content_json TEXT,
  bytes INTEGER,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES quality_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_quality_artifacts_run_id ON quality_artifacts(run_id);
CREATE INDEX IF NOT EXISTS idx_quality_artifacts_type   ON quality_artifacts(artifact_type);
~~~

---

## 13) Implementation plan (living checklist)

### Phase 0 — instrumentation (no behavior change)
- [ ] Emit `_quality` (or DB records) per run/stage
- [ ] Log tokens per stage + per doc totals
- [ ] Record model/provider/schema/pipeline version

### Phase 1 — implement non-negotiable gates (CPU)
- [ ] Evidence fidelity (exact+normalized substring) vs **model-input text**
- [ ] Orphan endpoints
- [ ] Zero-value patterns
- [ ] High-conf + bad evidence immediate escalate

### Phase 2 — add deterministic signals (log-only at first)
- [ ] Dup/fragmentation
- [ ] Type entropy + Other rate
- [ ] Kind distribution sanity
- [ ] Confidence variance weirdness
- [ ] Snippet stats
- [ ] Tech terms quality metrics

### Phase 3 — calibration & tuning
- [ ] Run batches; summarize distributions
- [ ] Tune evidence fidelity threshold and zero-value thresholds
- [ ] Decide which signals graduate to gates (if any)
- [ ] Track escalation rate + token spend impact

### Phase 4 — optional LLM judge (only if cost-effective)
- [ ] Add judge for borderline cases
- [ ] Measure: judge tokens vs reduction in specialist escalations

---

## 14) Open questions / decision log

- Evidence fidelity hard threshold: start at 0.70, tune empirically
- Orphan tolerance: 0 vs small %, depends on resolver/alias plan
- Length bin thresholds for “zero-value”
- TechTerms: finalize domain-agnostic wording vs domain profile thresholding
- Whether to keep a single combined “quality score” after gates (optional)

---

## Appendix A — normalization recipes (deterministic)

### A1) Evidence snippet normalization
- lowercase
- collapse whitespace: `re.sub(r"\s+", " ", text)`
- optionally strip quotes/punctuation around snippet boundaries

### A2) Entity name normalization
- lowercase
- strip punctuation
- collapse whitespace
- optional: strip corporate suffixes only if resolver supports (e.g., “inc”, “llc”) — defer for now

---

## Appendix B — “leaning list” (current)

Adopt early:
- gates: evidence fidelity, orphans, zero-value, high-conf mismatch
- signals: duplicates, type sanity, kind sanity, snippet stats
- structured `_quality` report + tokens

Defer:
- fuzzy evidence matching
- LLM judge pass
- any domain-specific gating on tech terms