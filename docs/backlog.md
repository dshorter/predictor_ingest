# Backlog

Items discovered during development and early operation. Grouped by area,
roughly prioritized within each group. Items will move out of here as they
get scheduled into work.

---

## Extraction & Prompt Tuning

### EXT-1: Entity type definitions missing from LLM prompt

**Observed:** 2026-02-21 | **Priority:** Medium (accumulate data first)

The system prompt lists entity types as a bare enum with no definitions,
examples, or disambiguation rules. The GLOSSARY.md has good descriptions
but they never reach the prompt. This causes inconsistent classification:

- **Model vs Tool** — "ChatGPT" tagged as Model in one doc, Tool in another
- **Tech vs Topic** — "machine learning" could go either way
- **Tech vs Model** — "LLMs" classified as both `tech:llms` and `model:llms`

**Likely fix:** Inject GLOSSARY definitions + disambiguation rules into
`build_extraction_system_prompt()` in `src/extract/__init__.py` (~line 237).
Also need entity resolution to merge duplicates already created.

**Waiting on:** More days of pipeline output to see the full pattern of
misclassifications before tuning.

### EXT-2: Density score prompt tuning

**Observed:** 2026-02-23 | **Priority:** Medium (wait for full backlog)

Density scores vary significantly by source type (arXiv papers vs blog posts
vs news articles). Prompt tuning should wait until the full backlog is
extracted so we have representative density numbers across all ~10 source
types. Tuning against partial data risks overfitting to academic content.

**Waiting on:** Backlog extraction to complete across all source types.

### EXT-3: Add confidence calibration guidance to extraction prompt

**Observed:** 2026-02-23 | **Priority:** Medium (wait for full backlog)

Sonnet produces uniformly high confidence scores (0.85–0.95) with low
variance, making the UI confidence slider almost useless as a filter. The
current prompt says `confidence: 0.0 to 1.0` but gives no rubric for what
different levels mean.

Contributing factors beyond model disposition:
- MAX aggregation in graph export ratchets confidence upward as more docs
  cover the same entities (`src/graph/__init__.py:359`)
- MENTIONS relations are hardcoded to 1.0 (`scripts/import_extractions.py:183`)
- Quality gates create survivorship bias toward high-confidence edges

**Likely fix:** Add explicit calibration rubric to the extraction prompt, e.g.:
- 0.5–0.7 for indirect/implied relationships
- 0.8+ only for explicitly stated facts with direct evidence
- Reserve 0.95+ for relationships stated in the document's headline/thesis

**Waiting on:** Full backlog extraction to establish baseline confidence
distribution across all source types before tuning.

### EXT-4: Analyze cheap model failure patterns for prompt tuning

**Observed:** 2026-02-24 | **Priority:** Medium (actionable now that backlog is done)

The cheap model (gpt-5-nano) frequently triggers escalation due to quality
gate failures — most commonly orphan endpoints (relations pointing to entities
not in the `entities[]` array). Example: doc `2026-02-05_google_ai_blog_daae96d0`
scored q=0.44 with 18 orphans.

When escalation fires, the specialist (Sonnet) sometimes also fails due to
near-miss schema violations (e.g. `PRODUCED` instead of `PRODUCES` — now fixed
by normalization). In those cases the system falls back to the cheap result
with `_escalationFailed` set, wasting both API calls.

**Analysis needed:**
- Query `documents WHERE escalation_failed IS NOT NULL` to find all fallback cases
- Categorize cheap model failure reasons: orphans vs low density vs evidence gaps
- Check whether orphan failures correlate with specific source types or doc lengths
- Determine if prompt changes (e.g. "every relation source/target MUST appear in
  entities[]") would reduce orphan rate enough to avoid escalation

**Data sources:** `quality_metrics` table, extraction JSON `_escalationFailed`
and `_qualityScore` fields, `shadow_report.py` output.

**Depends on:** Backlog extraction complete (done). Schema normalization fix (done).

---

## Entity Resolution

*(items will accumulate here)*

---

## Graph Export & Visualization

*(items will accumulate here)*

---

## Pipeline & Infrastructure

### PIPE-1: Extract stage timeout on large backlog

**Observed:** 2026-02-22 | **Priority:** Medium

When 358 backlog docs are bundled, the extract stage hits the 1800s (30 min)
timeout after processing only ~13 documents. Each cheap-model extraction
takes 80–150s, so the timeout caps throughput at ~12–20 docs per run.

**Options:**
- Raise extract timeout (but pipeline total time grows proportionally)
- Limit backlog batch size in `build_docpack.py` (e.g., 50 per run)
- Process backlog in chunks across multiple daily runs (self-draining)

**Current workaround:** The pipeline continues to import/resolve/export after
the timeout, and subsequent runs pick up where the backlog left off since
`--skip-existing` prevents re-extracting completed docs.

### PIPE-2: VentureBeat persistent 429 rate limiting

**Observed:** 2026-02-22 | **Priority:** Low

All 7 VentureBeat articles returned HTTP 429 (Too Many Requests). The ingest
stage makes no retry attempt by design (see `fetch_once()`). VentureBeat
articles remain in `status='error'` and are never retried on subsequent runs.

**Possible fix:** Add a `repair_data.py` option to reset retryable errors
(429, 5xx) back to a state that allows re-fetching on the next run.

---

## Sources & Ingestion

### SRC-1: Anthropic Blog feed unreachable

**Observed:** 2026-02-22 | **Priority:** Low

The Anthropic Blog RSS feed (`https://www.anthropic.com/news/rss.xml`) was
unreachable during the pipeline run. This is intermittent — the feed has
worked in previous runs. Monitor for persistent failure.

### SRC-2: Verify feed freshness mid-day

**Observed:** 2026-02-22 | **Priority:** Medium

The 03:51 UTC pipeline run found 0 new articles across 11 feeds. This may
be correct (early morning, feeds hadn't rotated) but needs verification.

**Diagnostic:** Run `python scripts/diagnose_feeds.py` during business hours
to confirm feeds are returning new entries. If consistently showing 0 new,
investigate whether feed caching or the dedup mechanism is too aggressive.
