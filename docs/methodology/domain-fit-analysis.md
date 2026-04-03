# Domain Fit Analysis: Film vs Semiconductors
*Written: 2026-04-01 | Based on film domain data through 2026-03-31*

## Purpose

This document explains why the **semiconductors domain** is expected to outperform
the **film domain** for early trend detection, and defines the 7-day A/B experiment
(2026-04-01 through 2026-04-08) that will validate or refute this hypothesis.

---

## What "Good Shape" Means for This Pipeline

The pipeline's goal is to detect **emerging trends early** using velocity, novelty,
and bridge signals. To do that reliably, a domain needs:

| Criterion | Why It Matters |
|-----------|---------------|
| **Persistent entities** | Entities that recur across multiple sources over time build corroboration naturally. High-churn entities inflate the denominator without building signal. |
| **Multiple independent sources** | Cross-source corroboration is the primary trust signal. Domains covered by only 1-2 sources produce no corroboration regardless of volume. |
| **Corroborable claims** | Factual, verifiable statements (chip tape-out, node announcement, supply agreement) can be confirmed by a second source. Opinion and narrative content cannot. |
| **Meaningful velocity** | Story cycles that last weeks to months — not hours — allow the pipeline to detect acceleration before it's obvious. |
| **Actionable early detection** | There is a real use case for knowing something 1-2 weeks before consensus forms. |

---

## Film Domain Diagnosis (Observed: 2026-03-17 through 2026-03-31)

### Metrics at time of analysis

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Entity overlap (2+ docs) | 19% | 30% | LOW |
| Island entity rate | 36.9% | <25% | CRITICAL |
| Uncorroborated entities | 79.6% | <70% | HIGH |
| Edges/node | 2.56 | 2.0 | ✓ |
| Extraction coverage | 29.1% | — | Backlog: 1,057 |
| High-conf bad evidence gate | 71% fail | — | Noisy |

### Root cause: domain shape mismatch

**High novelty, high churn.** Film journalism is event-driven. Every week introduces
new productions, new crew attachments, new festival selections — entities that appear
once and never recur. The denominator grows as fast as corroborations, keeping overlap
permanently suppressed around 18–19% regardless of extraction volume.

**Observed denominator growth:** Each 25-doc batch adds ~300 new entities but moves
overlap by only ~1 percentage point. Clearing the entire 1,057-doc backlog (~$78)
would likely produce a one-time boost, then the ratio would stabilize near the same
floor as new ingestion resumes.

**Source quality variance.** 18 feeds with wide output variance (Script Magazine:
31.3 rel/doc vs Deadline: 6.3 rel/doc). Low-density sources add documents and new
entities but few corroborating edges.

**High island rate.** 36.9% of entities have zero connections in the graph. These
are extracted once, never seen again, and contribute nothing to overlap or velocity
signal. They inflate entity count while degrading graph quality.

### What film *is* good for

Film remains a valid **stress-test domain**: high entity churn, mixed source quality,
and low corroboration rate push the pipeline hard. Bugs found in film likely affect
other domains. It continues running at 25 docs/day as a baseline.

---

## Semiconductors Domain Hypothesis

### Why it should have better shape

**Persistent, named entities.** The semiconductor industry revolves around a small
number of specific, named things: TSMC N3E, H100 SXM5, CoWoS-L, ASML NXE:3800E.
These names appear repeatedly across every publication for months or years. Unlike
film productions (which peak and disappear), process nodes are discussed from
announcement through risk production through HVM — an 18-month cycle.

**Long storyline cycles.** A process node storyline (e.g., TSMC N2) runs from first
announcement → yield rumors → tape-out reports → first silicon → HVM qualification.
Each stage produces corroborating articles across multiple independent sources.
`max_age_days: 540` is set accordingly.

**Technical specificity reduces noise.** Sources are practitioner-grade: SemiAnalysis,
The Chip Letter, Semiconductor Engineering, Chips and Cheese. These outlets name
specific chips, specific process nodes, and specific supply chain relationships rather
than paraphrasing press releases. Evidence fidelity should be higher than film's 0.744
average.

**Supply chain inference amplifies signal.** Three inference rules are pre-wired:
- `Fab MANUFACTURES Chip + Company DESIGNS Chip → Fab SUPPLIES Company`
- `Chip USES_PROCESS Node + Fab FABRICATES Node → Fab MANUFACTURES Chip`
- Transitive DEPENDS_ON from 2-hop SUPPLIES chains

These rules generate additional edges from asserted facts, boosting edges/node and
cross-document connectivity without requiring additional extraction.

**Entity disambiguation is tractable.** The domain has known variant families:
`N3 / N3E / N3P`, `H100 / H100 SXM5 / H100 PCIe`, `TSMC / Taiwan Semiconductor / TSM`.
These are well-defined and the disambiguation prompt encodes the rules explicitly.
Merges here directly improve overlap by consolidating what the extractor sees as
separate entities into single canonical nodes.

### Expected outcome

Hypothesis: **semiconductors will reach 30%+ entity overlap within the first 30 days**,
compared to film which has been stuck at 18–19% after 45+ days of operation.

If the hypothesis is wrong (overlap stays low), it tells us the pipeline itself has
structural problems independent of domain shape — and that's equally valuable to know.

> **Why 30%?** At 30% overlap, enough entities have 2+ appearances to make velocity
> scoring reliable across a meaningful fraction of the graph. Below ~20%, most
> "velocity spikes" are just a second article appearing after a long gap — not
> acceleration. The 30% figure is a heuristic, not a derived threshold. See
> [semiconductor-domain-design.md](semiconductor-domain-design.md) for the full
> rationale and what a proper validation would look like.

---

## 7-Day Experiment: 2026-04-01 through 2026-04-08

### Setup

| Parameter | Film (control) | Semiconductors (experiment) |
|-----------|---------------|----------------------------|
| Docs/day | 25 (unchanged) | 25 (starting cold) |
| Batch model | claude-sonnet-4-6 | claude-sonnet-4-6 |
| Disambiguation | gpt-5-nano, all types, 500 pairs | gpt-5-nano, all types, 500 pairs |
| Synthesis | enabled | enabled |
| Inference rules | film rules | 3 supply chain rules |
| Feeds | 18 sources (current) | 8 sources (verify URLs before D1) |

### Pre-run checklist (before first semiconductors batch)

- [ ] Fix resolve stage error (currently failing on film; same code runs semiconductors)
- [ ] Verify all 8 feed URLs from VPS (`python scripts/diagnose_feeds.py --domain semiconductors`)
- [ ] Register `semiconductors` in `web/js/domain-switcher.js` KNOWN_DOMAINS
- [ ] Confirm `data/db/semiconductors.db` is created on first ingest
- [ ] Recalibrate or gate-override high-conf bad evidence gate (71% fail rate on film is noisy)
- [ ] Disable Go Into The Story feed (10 fetch errors/day, no successful fetches)

### Measurement checkpoints

**Day 3 (2026-04-04):**
- Are feeds producing documents?
- Entity type breakdown — are Chip, ProcessNode, Fab entities appearing?
- Any extractor errors or schema mismatches?
- Inference rules firing?

**Day 7 (2026-04-08) — primary comparison:**

| Metric | Film baseline | Semiconductors target | Decision |
|--------|--------------|----------------------|----------|
| Entity overlap | 19% | ≥25% | Domain shape better |
| Island entity rate | 36.9% | <30% | Graph connectivity better |
| Uncorroborated rate | 79.6% | <70% | Corroboration happening |
| Inference rule hits | — | ≥10 supply chain edges | Rules are firing |
| Evidence fidelity (avg) | 0.744 | ≥0.75 | Technical sources are cleaner |
| Rel/doc (top sources) | 6–31 | ≥12 avg | Dense extraction |

### Decision criteria

**Continue semiconductors as co-primary domain:**
- Overlap ≥25% after 7 days, OR
- Island rate clearly lower than film, OR
- Inference rules producing meaningful supply chain edges

**Reconsider / investigate:**
- Overlap <20% with no upward trend (possible: feeds weren't verifiable, content
  is paywalled, sources are lower density than expected)
- Feeds producing <10 docs/day (volume problem — need more or different sources)

**Abort semiconductors, diagnose pipeline:**
- Both domains stuck at ~19% overlap → structural pipeline problem, not domain shape

---

## Cost Model for Experiment

At $0.074/doc × 25 docs/day:
- 7-day semiconductors run: ~$13
- Film continues at same rate: ~$13
- Total experiment cost: **~$26**

Disambiguation adds ~$0.08/run (negligible). If inference rules fire heavily,
synthesis may add $0.01–0.05/day.

---

## What We Already Know from Film (Lessons Carried Forward)

1. **Token cost instrumentation is working.** Per-stage, per-model cost is visible
   in the health report. Use this to catch runaway costs early.

2. **Sonnet 4.6 quality: 0.88 avg.** This is the extraction model. Don't substitute
   nano for extraction — the quality gap (0.88 vs 0.69) is too large.

3. **Nano is appropriate for disambiguation.** $0.08 for 39 runs, 78% keep_separate,
   10% merge. Cheap enough to run on all entity types.

4. **`fatal: False` on non-critical stages masks failures.** The synthesize outage
   ran for 8 days undetected. Monitor stage status in health_report, not just
   pipeline status.

5. **Resolve stage error blocks disambiguation.** Fix it before the experiment starts
   or disambiguation won't run and merge decisions won't accumulate.

6. **Island entities are a leading indicator of domain fit.** If island rate is high
   after the first 50 docs, the domain is producing low-corroboration content and
   more extraction won't help.
