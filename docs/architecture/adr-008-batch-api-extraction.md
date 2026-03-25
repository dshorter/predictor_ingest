# ADR-008: Replace Two-Tier Escalation Extraction with Anthropic Batch API

**Status:** Accepted
**Date:** 2026-03-25
**Deciders:** dshorter, Claude (Sonnet 4.6)
**Sprint:** 9 (Extraction Simplification)

## Context

### History of the two-tier system

The escalation architecture was introduced to manage API cost: run a cheap model
(gpt-5-nano) first; escalate to a specialist (claude-sonnet-4-6) only when quality
gates fail or the score falls below a threshold. The hypothesis was that a meaningful
fraction of documents would be "easy" and stay at the cheap tier.

**EXT-4 (2026-02-25)** — first real measurement after the scoring overhaul:

| Metric | Value | Target |
|--------|-------|--------|
| Escalation rate | 80% | < 50% |
| Avg quality (cheap kept) | 0.83 | — |
| Escalation failures | 7% | < 2% |

The analysis noted: *"Running Sonnet on everything would actually be cheaper."*
Option C (drop cheap-first) was deferred in favour of lightweight prompt tuning.

**Current state (2026-03-24)** — five weeks and ~250 extractions later:

| Metric | Then | Now | Movement |
|--------|------|-----|----------|
| Escalation rate | 80% | 69% | ↓ 11pp — did not reach 50% target |
| Escalation failures | 7% | 8% | ↑ slightly worse |
| Avg quality (cheap) | 0.83 | 0.69 | ↓ degraded on film corpus |
| Gate D pass rate | — | 29% | Gate catches real problems |

Prompt tuning moved the needle but never crossed the break-even threshold. The
cheap tier is now a net liability, not a savings mechanism.

### Failure modes that persist

**1. Empty JSON from nano (15 of 20 escalation failures)**
Nano returns a blank string for some documents. These fall back to the cheap
result, which is itself the blank string. The document gets silently skipped.

**2. Unterminated JSON on long documents (4 of 20 failures)**
Nano hits a context limit mid-output and truncates. No extraction is stored.

**3. Inverted relations in the graph**
Gate D (high-confidence + bad evidence) was disabled for the film domain after
generating too many false positives on trade-press paraphrase style. Without Gate D,
relations like `2001: A Space Odyssey WRITES Stanley Kubrick` (confidence 0.92)
entered the graph on 2026-03-24. Gate D was doing real work; disabling it was
a symptom of the cheap model's failure modes infecting the gate calibration.

**4. Ongoing maintenance cost**
Six configurable quality gates, per-domain threshold overrides, shadow mode
infrastructure, per-model quality scoring, and escalation decision logic represent
~680 lines of `run_extract.py` and ~250 lines of `src/extract/__init__.py` that
exist solely to manage the cheap tier. Any schema or prompt change requires
re-tuning across both models.

### Cost reality check

```
Current mixed approach (69% escalation):
  31% × nano_cost + 69% × sonnet_standard_cost
  ≈ 0.31 × (0.05 × S) + 0.69 × S   [nano ≈ 5% of Sonnet price]
  ≈ 0.016S + 0.69S
  ≈ 0.706 × S

Batch API, Sonnet only:
  100% × (0.50 × sonnet_standard_cost)
  = 0.50 × S
```

**Batch-only is ~29% cheaper than the current mixed approach** at today's 69%
escalation rate. The savings gap widens if escalation continues to drift upward.

### The four downstream LLM stages (ADR-007)

ADR-007 added entity disambiguation, cross-document synthesis, relation inference,
and trend narratives. These run after extraction and depend on extraction outputs —
they cannot be pre-submitted to a batch job alongside extraction.

However, their daily call volume is small:

| Stage | Calls/day | Avg tokens/call | Batch saving |
|-------|-----------|-----------------|--------------|
| Entity disambiguation | ~42 | Short (classification) | Negligible |
| Cross-doc synthesis | ~8 | Medium | Negligible |
| Relation inference | 0 (CPU) | — | n/a |
| Trend narratives | ~9 | Short | Negligible |

Batching these ~60 calls would save pennies while adding a second async wait cycle
to the pipeline. They remain as synchronous live calls (unchanged).

---

## Decision

Replace the two-tier cheap+escalate extraction with a single
**Anthropic Messages Batch API** submission using `claude-sonnet-4-6` throughout.
Downstream stages (disambiguation, synthesis, inference, narratives) are unchanged
— they continue as synchronous calls after batch results are collected.

This is **Pattern B**: batch the extraction stage only; live calls for everything
downstream.

---

## Alternatives Considered

### Alt A: Continue prompt tuning the cheap model

The February prompt tuning (EXT-4) moved escalation rate from 80% to 69% over five
weeks. Reaching the 50% break-even target would require a further 19pp drop. Given
that the remaining failures involve empty responses and unterminated JSON — not
addressable by prompt changes — there is no plausible prompt path to 50%.

**Rejected.** The mechanism is fundamentally wrong for the corpus, not
undertrained.

### Alt B: Batch API for extraction only ✅ Chosen

See Decision section.

### Alt C: Synchronous Sonnet for everything (no batch)

Same quality and simplicity as Alt B, but at full standard API pricing (1.41×
the batch cost). No change to pipeline timing — results available immediately.

Viable if async complexity is unacceptable. Kept as a fallback if the batch
pipeline introduces operational problems in the first two weeks.

**Not chosen** — the 29% cost saving over Alt C is material at scale and the
async complexity is bounded (one wait point, one new DB table).

### Alt D: Two batch submissions (extraction + downstream stages)

Submit extraction as Batch 1; after results arrive, submit disambiguation +
synthesis + narratives as Batch 2. Two async wait cycles per day.

The downstream stages represent ~60 short calls. At Sonnet batch pricing the
saving is negligible. Two async cycles double the pipeline's failure surface for
no meaningful return.

**Rejected.** Downstream stages stay live.

---

## Implementation

### Pipeline mechanism: staggered daily handoff

Each `make daily` run does two things: collect yesterday's batch results and
submit today's batch. No polling. The pipeline always exits fast.

```
Day N  make daily:
  Phase 1 — collect yesterday's batch (if pending):
    collect_batch → import → resolve → synthesize → infer → export → trending

  Phase 2 — prepare and submit today's batch:
    ingest → select → submit_batch → exit
    [Anthropic processes batch overnight; SLA 24h, typically minutes]

Day N+1  make daily:
  Phase 1 — collect yesterday's (Day N) batch → ...
  Phase 2 — submit Day N+1 batch → exit
```

The one-day extraction lag is acceptable: the trending view operates on 7d/30d
windows and the pipeline already carries a multi-week backlog. Same-day graph
freshness is not a current requirement.

### Pipeline flow (after)

```
collect_batch → NEW: check batch_jobs for pending job; if complete, stream
                result JSONL, parse + normalize, write extraction JSON files
import    → unchanged
resolve   → unchanged (42 live LLM calls)
synthesize→ unchanged (8 live LLM calls)
infer     → unchanged (CPU)
export    → unchanged
trending  → unchanged (9 live LLM calls)
ingest    → unchanged
select    → unchanged
submit_batch → NEW: build batch request from selected docpack, POST to
               /v1/messages/batches, store job_id + doc_ids in batch_jobs,
               exit immediately
```

### Code changes

**Deleted:**
- `run_escalation()` in `scripts/run_extract.py` (lines 333–512)
- `run_shadow_only()` + `ThreadPoolExecutor` shadow infrastructure
- `score_extraction_quality()` in `src/extract/__init__.py` (lines 259–366)
- `evaluate_extraction()` escalation decision logic (lines 612–670)
- `--shadow`, `--understudy-model` CLI flags
- DB tables: `quality_runs`, `quality_metrics`, `extraction_comparison`
- Document columns: `extracted_by`, `quality_score`, `escalation_failed`
- Domain config fields: `escalation_threshold`, gate threshold overrides

**Unchanged:**
- `parse_extraction_response()` — JSON parsing and validation
- `normalize_extraction()` — relation normalization against domain taxonomy
- All extraction prompts and `ANTHROPIC_EXTRACTION_SCHEMA`
- Quality gates A/B/C/D — role changes from escalation triggers to post-import
  QA logging. They run after each extraction result is collected, log to
  `quality_metrics` as before, but no longer make escalation decisions because
  there is no escalation path
- All downstream scripts, domain configs (minus escalation fields), DB schema
  outside the tables listed above

**Gate re-tuning (all domains):**

All four gates are re-enabled at thresholds calibrated for Sonnet quality, not
nano failure modes. The film domain's Gate A (evidence_fidelity) and Gate D
(high_conf_bad_evidence) overrides — introduced to suppress nano false positives —
are removed. Per-domain thresholds should be re-calibrated against Sonnet output
over the first two weeks of operation and documented in `operational-state.md`.

| Gate | Film override (removed) | Rationale |
|------|------------------------|-----------|
| Gate A (evidence_fidelity) | threshold=0.0 (disabled) | Nano paraphrased; Sonnet quotes faithfully |
| Gate D (high_conf_bad_evidence) | threshold=1.1 (disabled) | Nano inverted relations; Sonnet does not |

**Added:**
- `scripts/submit_batch.py` — build batch request from docpack, POST to
  `/v1/messages/batches`, store job_id
- `scripts/collect_batch.py` — poll status, stream results, write extraction
  JSON files, call import
- DB table `batch_jobs`:

```sql
CREATE TABLE batch_jobs (
    job_id        TEXT PRIMARY KEY,
    domain        TEXT NOT NULL,
    run_date      TEXT NOT NULL,
    submitted_at  TEXT NOT NULL,
    status        TEXT NOT NULL,   -- pending | complete | failed
    doc_ids       TEXT NOT NULL,   -- JSON array of doc_id strings
    result_file   TEXT,            -- path to downloaded JSONL result
    completed_at  TEXT
);
```

**Net code change:** approximately −600 lines `run_extract.py`,
−250 lines `src/extract/__init__.py`, +~200 lines across the two new scripts.

### `make` targets

| Target | Before | After |
|--------|--------|-------|
| `make daily` | ingest→select→extract→import→resolve→…→trending | collect→import→resolve→…→trending→ingest→select→submit |
| `make submit` | n/a | submit batch for selected docs, store job_id, exit |
| `make collect` | n/a | collect pending batch, write extraction files, import |
| `make extract` | run two-tier escalation (removed) | removed — replaced by submit + collect |
| `make backlog` | n/a | pre-populate batch_jobs with backlog chunks for drain |

### Edge cases and fallback

The collect phase opens each morning by querying `batch_jobs` for all jobs
with `status = 'pending'`, ordered by `submitted_at`. This handles every
steady-state and degraded scenario without branching logic in the caller:

| Morning state | Collect phase behaviour | Submit phase behaviour |
|---|---|---|
| Yesterday's batch complete | Import + full graph run | Ingest → submit → exit |
| Yesterday's batch still pending | Log warning, skip graph stages | Ingest → submit → exit |
| Yesterday's batch failed | Log error, trigger fallback (see below) | Ingest → submit → exit |
| Two days piled up, both complete | Import both sets → one combined graph run | Ingest → submit → exit |

**"Still pending" skip:** If the batch is not yet complete, the collect phase
skips all graph stages for that day and exits cleanly. The next morning it
finds two complete batches. Rather than running graph stages twice, it imports
both sets of extraction files and runs resolve → synthesize → infer → export →
trending once on the combined set. This is preferable to two separate passes:
cross-document synthesis and entity resolution see a wider article set, yielding
more corroboration and fewer island entities. Maximum pile-up depth under normal
conditions is two days — the Anthropic Batch API SLA is 24 hours.

**Failed batch fallback:** `collect_batch.py` detects `status == errored`
on a batch job and falls back to synchronous extraction, calling
`claude-sonnet-4-6` directly for each doc in `batch_jobs.doc_ids`, then
continuing with the normal import → graph stage sequence. The fallback is
logged to the pipeline run record. This preserves pipeline continuity for
testing and incident recovery without requiring manual intervention.

---

## Consequences

### Positive

- **~29% cost reduction** vs current mixed approach at 69% escalation rate.
- **~930 lines deleted** from the extraction path — the largest single
  simplification since the pipeline was built.
- **Consistent extraction quality** — Sonnet's 0.88 average vs nano's 0.69.
  No more quality bimodality or per-source gate calibration.
- **Gate D re-enabled** — the root cause of its disablement (nano failure modes)
  is gone. Inverted relations and fabricated high-confidence edges are caught again.
- **Escalation failure rate → 0%** — empty JSON from nano was the dominant
  escalation failure. There is no nano.
- **No more per-domain gate overrides** for nano-specific failure modes.
  Film domain's Gate A and D overrides can be removed.
- **761-doc backlog** drains automatically via the staggered handoff — pre-populate
  `batch_jobs` with the backlog split into chunks of ≤100 docs each; the daily
  collect phase drains one chunk per day at batch pricing with no special commands.

### Negative

- **One-day extraction lag.** Articles ingested today appear in the graph
  tomorrow. Acceptable given the 7d/30d trending window and current backlog
  depth; revisit if same-day freshness becomes a requirement.
- **Batch job tracking adds operational state.** A stale `pending` record in
  `batch_jobs` (e.g. from a killed run) needs to be detectable and recoverable.
  The fallback procedure handles this, but it is new surface area.
- **24h SLA.** In practice 25-doc batches complete in minutes, but the pipeline
  must not assume this. If a batch is still pending at the next day's collect
  phase, the collect phase skips graph stages and the two days are processed
  together the following morning. Maximum lag under normal conditions: 2 days.

### Risks

- **Batch API rate limits.** At 25 docs/day this is not a concern. The backlog
  drain strategy (≤100 docs per chunk, one chunk collected per daily run)
  keeps all batch jobs well within per-workspace limits.
- **Result format drift.** The Batch API returns a JSONL file per batch; each
  line is `{custom_id, result: {type, message}}`. The collector must handle
  `type == error` per-line without failing the whole batch.
- **Cost model assumption.** The 50% batch discount is current Anthropic pricing
  as of 2026-03-25. If pricing changes, Alt C (synchronous Sonnet) remains viable
  with no pipeline changes beyond swapping `submit_batch`/`collect_batch` for a
  direct API call.

---

## Related Documents

- [ext4-cheap-model-escalation-analysis.md](../fix-details/ext4-cheap-model-escalation-analysis.md) — origin of the escalation architecture and first measurement
- [adr-007-llm-leverage-features.md](adr-007-llm-leverage-features.md) — the four downstream LLM stages that are unaffected
- [docs/backend/operational-state.md](../backend/operational-state.md) — current gate overrides to be removed after migration
- [docs/llm-selection.md](../llm-selection.md) — cost model and model tier history
