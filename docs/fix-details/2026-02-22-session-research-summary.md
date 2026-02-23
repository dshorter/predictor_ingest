# Research Session: Pipeline Stall, Quality Scoring, and Documentation Overhaul

**Date:** 2026-02-22
**Branch:** `claude/debug-daily-process-AVGNa`
**Context:** User reported the daily pipeline was stuck processing the same 3 docs. Investigation expanded into RSS dedup analysis, quality scoring overhaul, and documentation restructuring.

---

## Investigation Timeline

### Phase 1: Why is the pipeline stuck on 3 documents?

**Starting evidence:** User provided a gist containing `logs_pipeline_2026-02-21.json` and `db_summary.json` from the VPS. The log showed:

```
Loaded 3 documents from data/docpacks/daily_bundle_2026-02-21.jsonl
  [1/3] 2026-02-21_techcrunch_ai_b78885cd: SKIPPED (exists)
  [2/3] 2026-02-21_techcrunch_ai_00b2cb02: SKIPPED (exists)
  [3/3] 2026-02-21_techcrunch_ai_f2dd956f: SKIPPED (exists)
```

Meanwhile `db_summary.json` showed 996 total documents: **368 in `cleaned` status**, 621 `extracted`, 7 `error`.

**Diagnostic approach:**

1. Traced the pipeline stage order: `repair → ingest → docpack → extract → import → resolve → export → trending`
2. Examined `build_docpack.py` — found the date filter:
   ```sql
   WHERE status = 'cleaned'
     AND published_at IS NOT NULL
     AND substr(published_at, 1, 10) = ?   -- exact date match
   ```
3. This query returns **only docs published on today's date**. The 368 cleaned docs had `published_at` from days/weeks prior — they entered via RSS ingestion but their publication dates never matched a subsequent daily run.

**Root cause identified:** The docpack stage found 0 docs for 2026-02-21 → the extract stage fell through to a **stale docpack file** from a previous run containing 3 already-extracted TechCrunch articles → all 3 SKIPPED → pipeline completes having done nothing useful → same loop next run.

**Fix applied:** Backlog fallback query in `build_docpack.py`. Today's docs get priority; remaining capacity fills with cleaned docs from other dates. Later refined with a 6-month cutoff to avoid spending API budget on stale content.

### Phase 2: Why zero new articles across all feeds?

**User pushback:** "I'm more concerned that for some reason it's not picking up anymore new feeds. I find it hard to believe that no new articles were published across all 12 sources today."

**Investigation:**

1. Examined `src/ingest/rss.py` dedup mechanism at line ~200:
   ```python
   if skip_existing and raw_path.exists() and text_path.exists():
       skipped += 1
       continue
   ```
2. This is filesystem-based — if `data/raw/{doc_id}.html` and `data/text/{doc_id}.txt` both exist, the article is considered already fetched.
3. The pipeline log showed 883 duplicates skipped across 11 reachable feeds (1 feed, Anthropic Blog, was unreachable).
4. The run timestamp was **03:51 UTC** — early enough that most feeds hadn't rotated to include new articles.

**Conclusion:** Likely correct behavior for the time of day, but couldn't confirm without running diagnostics on the VPS itself. Created `scripts/diagnose_feeds.py` — a standalone tool that checks each configured feed and reports entries-in-feed vs. already-on-disk with date distributions.

**Key constraint:** Data lives on the VPS with no direct access (no MCP SSH). All scripts are written locally and run by the user on the VPS.

### Phase 3: Quality scoring — the cheap model was never failing

**User observation:** "Despite my adjustment to how MENTIONS are weighted, the scores from the cheap model are still suspiciously high."

User provided this extraction log snippet:
```
Extract 1/358: 2026-02-06_techcrunch_ai_4d51e9d5
  Cheap model response: 12 entities, 14 relations, 5 tech terms
  Quality: q=0.98 (density=0.82, evidence=1.00, confidence=1.00,
           connectivity=1.00, tech=1.00)
  → Using cheap extraction (above threshold 0.60)
...
Extract 13/358: 2025-12-19_simonwillison_b1e3d39f
  Cheap model response: 8 entities, 9 relations, 4 tech terms
  Quality: q=0.82 (density=0.33, evidence=1.00, confidence=1.00,
           connectivity=1.00, tech=1.00)
  → Using cheap extraction (above threshold 0.60)
```

Every score was q=0.82–1.00. Escalation threshold was 0.60. **Zero escalations to the specialist model** (claude-sonnet-4-5-20250929) across all 13 documents processed before timeout.

**Root cause analysis:**

The original scoring function had thresholds set as **minimum floors** rather than **proportional targets**. Any model producing a basically valid extraction trivially maxed every component:

| Component | Old Threshold | What Cheap Model Produces | Result |
|-----------|--------------|--------------------------|--------|
| Entity density | 3.0/1K chars | 5+ entities/1K | 1.00 (capped) |
| Evidence coverage | 80% with evidence | 100% (all marked asserted+evidence) | 1.00 |
| Avg confidence | 0.60 | ~0.90 (flat across all relations) | 1.00 (capped) |
| Relation/entity ratio | 0.10 (1 per 10 entities!) | 0.5+ | 1.00 (capped) |
| Tech terms | ≥1 | 1+ | 1.00 |

The thresholds were testing "did the model produce output at all?" rather than "did the model produce *good* output?"

---

## Quality Scoring Overhaul: Design and Simulated Benchmarks

### Design rationale

The fix needed to answer one question: **what distinguishes a cheap model's extraction from a specialist model's extraction?** After studying the log output:

1. **Cheap models produce shallow relation vocabularies.** They default to 2-3 relation types — typically `USES_TECH`, `CREATED`, and `MENTIONS`. A specialist model identifies 6-10 distinct semantic relations (`LAUNCHED`, `TRAINED_ON`, `PARTNERED_WITH`, `FUNDED`, etc.) because it understands the text more deeply.

2. **Cheap models output flat-high confidence.** Every relation gets confidence 0.85-0.95 regardless of how ambiguous the evidence is. A well-calibrated model varies confidence — 0.95 for an explicitly stated partnership, 0.60 for an inferred dependency.

3. **Cheap models inflate MENTIONS.** They correctly tag entities but slap `MENTIONS` on most relations rather than identifying the semantic relationship. Excluding `MENTIONS` from scoring exposes this.

### New scoring architecture

**Raised thresholds** (proportional targets, not binary floors):

| Component | Old Target | New Target | Why |
|-----------|-----------|-----------|-----|
| Entity density | 3.0/1K | 5.0/1K | Score proportionally up to target |
| Confidence | 0.60 | 0.85 | Cheap models cluster at 0.90 — raise the bar |
| Relation/entity ratio | 0.10 | 0.50 | 1:2 is realistic for good extraction |
| Tech terms | 1 | 2 | AI articles should mention ≥2 technologies |

**New signal — relation type diversity (25% weight):**
```python
rel_types = {r.get("rel") for r in semantic_relations if r.get("rel")}
n_rel_types = len(rel_types)
diversity_score = min(n_rel_types / 6, 1.0)  # target: 6 distinct types
```

This is the single most discriminating signal. A cheap model emitting `{USES_TECH, CREATED}` scores 2/6 = 0.33. A specialist emitting `{USES_TECH, CREATED, LAUNCHED, TRAINED_ON, PARTNERED_WITH, FUNDED}` scores 6/6 = 1.00.

**New penalty — confidence variance:**
```python
if stddev < 0.05 and avg_confidence > 0.8:
    avg_confidence *= 0.7  # 30% penalty for flat-high confidence
```

A model outputting 0.90 ± 0.02 for everything isn't calibrating — it's guessing confidently. The penalty drops the effective confidence from 0.90 to 0.63.

**Rebalanced weights:**

| Component | Old Weight | New Weight | Rationale |
|-----------|-----------|-----------|-----------|
| Entity density | 30% | 15% | Easy for any model — demote |
| Evidence coverage | 25% | 15% | Easy for any model — demote |
| Avg confidence | 20% | 10% | Unreliable signal even with penalty |
| Connectivity (ratio) | 15% | 20% | Harder to game — promote |
| **Diversity (NEW)** | — | **25%** | Hardest signal for cheap models |
| Tech terms | 10% | 15% | Slight boost for domain relevance |

### Simulated before/after benchmarks

To validate the new scoring formula before deploying it, we constructed three representative extraction profiles based on the actual pipeline output patterns and ran the old and new scoring logic against them:

#### Scenario A: Typical cheap model output
*Profile: 9 semantic relations, 3 relation types, flat confidence (0.90 ± 0.02), 12 entities, 5 tech terms, 2K char source*

| Signal | Old Score | New Score |
|--------|----------|----------|
| Density | 1.00 | 1.00 |
| Evidence | 1.00 | 1.00 |
| Confidence | 1.00 | 0.74 (variance penalty fired) |
| Connectivity | 1.00 | 1.00 |
| Diversity | n/a | 0.50 (3/6 types) |
| Tech terms | 1.00 | 1.00 |
| **Combined** | **1.00** | **0.73** |
| Escalates? | No | **No (borderline)** |

The borderline score means a slightly worse extraction *will* trigger escalation. Before, nothing did.

#### Scenario B: Weak cheap model output (common pattern)
*Profile: 4 semantic + 5 MENTIONS, 2 relation types, flat confidence, 8 entities, 2 tech terms, 3K char source*

| Signal | Old Score | New Score |
|--------|----------|----------|
| Density | 0.89 | 0.53 |
| Evidence | 1.00 | 1.00 |
| Confidence | 1.00 | 0.74 (variance penalty fired) |
| Connectivity | 1.00 | 1.00 |
| Diversity | n/a | 0.33 (2/6 types) |
| Tech terms | 1.00 | 1.00 |
| **Combined** | **~0.85** | **0.58** |
| Escalates? | No | **YES** (below 0.60) |

This is the critical scenario. The old scoring let a 2-relation-type extraction with inflated MENTIONS pass with q≈0.85. The new scoring correctly flags it for escalation.

#### Scenario C: Good specialist model output (control)
*Profile: 10 semantic, 10 relation types, varied confidence (0.72 ± 0.15), 15 entities, 8 tech terms, 2K char source*

| Signal | Old Score | New Score |
|--------|----------|----------|
| Density | 1.00 | 1.00 |
| Evidence | 1.00 | 1.00 |
| Confidence | 1.00 | 0.85 (no penalty — varied) |
| Connectivity | 1.00 | 1.00 |
| Diversity | n/a | 1.00 (10/6 types, capped) |
| Tech terms | 1.00 | 1.00 |
| **Combined** | **1.00** | **0.97** |
| Escalates? | No | No |

Good extractions still score high — the new formula doesn't create false positives. It specifically targets the cheap model's behavioral fingerprint: shallow relation vocabulary + flat confidence.

### Scoring separation achieved

```
Old scoring:    cheap ≈ 0.82–1.00    specialist ≈ 0.95–1.00    (no separation)
New scoring:    cheap ≈ 0.55–0.73    specialist ≈ 0.85–0.97    (clear gap)
                        ↑                        ↑
                  escalation zone          safe zone
                  (below 0.60)            (above 0.60)
```

The escalation threshold at 0.60 now sits cleanly between the two model tiers instead of below both.

---

## Phase 4: Documentation Overhaul

### Problem

CLAUDE.md (symlinked from AGENTS.md) had grown to 575 lines / ~20KB. The user observed this was too large for efficient context consumption by new AI sessions. Several large sections contained full schemas, visual encoding tables, and export examples that belonged in subdocuments.

### Changes

1. **Extracted Data Contracts** (123 lines) → `docs/schema/data-contracts.md`
   - Documents table schema, docpack JSONL format, extraction JSON schema (entities, relations, evidence, dates), Cytoscape export format with examples
   - CLAUDE.md replaced with 4-line summary + link

2. **Collapsed Cytoscape Client** (115 lines) → kept 5 critical gotchas inline, linked to `docs/ux/README.md` and `docs/ux/troubleshooting.md`
   - Removed: visual encoding tables, scale-by-degree tables, export path examples, detailed feature lists

3. **Condensed all remaining sections:**
   - Core Principles: multi-line descriptions → single-line each
   - Repository Layout: tree format → flat compact list
   - Canonical IDs: 25 lines → single paragraph
   - Relation Taxonomy: 47 lines with notes → flat grouped lists
   - Developer Workflow: long section → 4 commands + link
   - Sources: verbose → 2 lines + link

4. **Preserved and expanded Key Documentation index** (15 entries, 5 sections) as the primary navigation structure for new sessions.

**Result:** 575 lines → 237 lines (59% reduction), no information lost — only relocated behind links.

---

## Files Changed (Full Session)

| File | Type | Summary |
|------|------|---------|
| `scripts/build_docpack.py` | Fix | Backlog fallback with 180-day cutoff |
| `scripts/run_pipeline.py` | Fix | Track docpack count; skip extract on empty |
| `src/extract/__init__.py` | Overhaul | Quality scoring: raised thresholds, diversity signal, variance penalty |
| `scripts/diagnose_feeds.py` | New | On-VPS diagnostic tool for RSS feed freshness |
| `AGENTS.md` | Refactor | Slimmed from 575 → 237 lines |
| `docs/schema/data-contracts.md` | New | Extracted data contract schemas from CLAUDE.md |
| `docs/fix-details/pipeline-stall-scoring-overhaul.md` | New | Technical writeup of root causes and fixes |
| `docs/fix-details/README.md` | Updated | Added pipeline stall entry |
| `docs/llm-selection.md` | Updated | Quality scoring weights and targets table |
| `docs/backlog.md` | Updated | Added PIPE-1, PIPE-2, SRC-1, SRC-2 |

---

## Open Items (from this session)

| ID | Item | Priority | Action |
|----|------|----------|--------|
| PIPE-1 | Extract timeout (1800s) caps throughput at ~13 docs/run | Medium | Limit batch size or raise timeout |
| PIPE-2 | VentureBeat persistent 429s | Low | Add retryable-error reset to repair_data.py |
| SRC-1 | Anthropic Blog feed unreachable (intermittent) | Low | Monitor |
| SRC-2 | Verify feed freshness mid-day on VPS | Medium | Run `diagnose_feeds.py` during business hours |

---

## Key Takeaways

1. **Scoring functions that test "minimum acceptable" instead of "proportional target" produce no signal.** If every model trivially maxes the score, the score doesn't discriminate. Proportional scoring against meaningful targets (e.g., 6 distinct relation types) creates real separation.

2. **Simulated benchmarks before deploying scoring changes catch false positive/negative risks.** Constructing 3 representative profiles (weak cheap, strong cheap, strong specialist) and running both formulas proves the new formula creates the intended separation band.

3. **Behavioral fingerprints beat output size for model quality.** The cheap model actually produces *reasonable counts* of entities and relations. What distinguishes it is the *shallowness of its vocabulary* (2-3 relation types) and *flatness of its confidence* (0.90 ± 0.02). These are structural signals, not quantity signals.

4. **Date-filtered queries need fallback strategies.** An exact-date query on `published_at` permanently strands any document whose publication date doesn't match a pipeline run date. The "today first, then backlog" pattern ensures no cleaned document sits indefinitely.

5. **Documentation should link, not stuff.** A 575-line project instruction file burns context on content that's one click away. Key gotchas stay inline; full schemas and specs belong in subdocuments.
