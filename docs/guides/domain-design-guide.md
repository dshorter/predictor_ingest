# Domain Design Guide

Methodological guide for onboarding new domains into the predictor_ingest
pipeline. Sits between the mechanical template (`domains/_template/README.md`)
and the architecture docs (`docs/architecture/domain-separation.md`).

**Audience:** Developers adding a new domain.
**Origin:** Sprint 13 (items 13.1-13.5), distilled from three domains of
operational experience (AI, biosafety, semiconductors) plus a film domain
that exposed boundary cases.

---

## 1. Domain Fitness Checklist

Before writing any YAML, answer these five questions. A domain that fails
two or more is a poor fit for this pipeline at current scale.

### 1.1 Entity Persistence

> Do the entities in this domain persist across weeks or months?

The pipeline tracks entities over time to compute velocity and novelty. If
entities are ephemeral (appear once, never again), the graph has no
cross-document signal.

| Domain | Verdict | Reasoning |
|--------|---------|-----------|
| Semiconductors | Pass | Companies, fabs, process nodes persist for years |
| AI/ML | Pass | Orgs, models, tools persist; new ones weekly |
| Film | Pass (borderline) | Studios/directors persist; individual productions are temporary but last months in press |
| Breaking news | **Fail** | Stories are one-shot; entities rarely recur |
| Academia | **Fail** | Papers rarely recur in news after publication week |

**Rule of thumb:** If <30% of entities from week 1 appear again in week 3,
the domain likely fails this test.

### 1.2 Source Independence

> Are there 3+ editorially independent sources covering this domain?

Single-source or correlated-source domains produce echo, not corroboration.
The pipeline needs independent editorial voices to generate meaningful
overlap rates.

**Minimum:** 3 independent sources. **Target:** 5+ for robust signal.

**Independence test:** If Source A publishes a story, does Source B produce
its own reporting (independent) or rewrite Source A's article (echo)?

### 1.3 Claim Corroborability

> Do multiple sources report on the same entities regularly?

This directly drives the **entity overlap rate** — the key critical-mass
metric. Without cross-document entity overlap, the graph is a collection
of disconnected islands.

| Overlap Rate | Interpretation |
|--------------|---------------|
| <10% | Too sparse — graph is mostly islands |
| 10-20% | Emerging — some signal, high false positive rate |
| 20-30% | Useful — corroboration becoming reliable |
| **30%+** | Mature — trend signals trustworthy |

**Target:** 30% overlap within 30 days of operation.

### 1.4 Story Cycle vs. Velocity Window

> Does the domain's news cycle produce measurable change within a 7-day window?

The default velocity calculation compares a 7-day window to the previous
7-day window. If the domain's natural cadence is longer (quarterly earnings,
annual regulations), velocity signals will be sparse.

| Domain | Cycle | Fit |
|--------|-------|-----|
| AI/ML | Daily/weekly product launches | Excellent |
| Film | Weekly production news | Good |
| Biosafety | Monthly/quarterly regulatory actions | Adequate (lower velocity cap helps) |
| Semiconductors | Quarterly earnings + sporadic process announcements | Adequate (spike-driven) |
| Climate policy | Annual COP cycles | **Poor** — too slow for 7-day windows |

**Mitigation:** Lower `velocity_cap` and `min_mentions_for_velocity` for
slower domains. Future: configurable velocity window width.

### 1.5 Entity Density

> Does typical source material mention 3+ extractable entities per article?

Low-density sources (opinion pieces, editorials) produce sparse graphs.
The pipeline needs entity-rich source material.

**Measure after first extraction run:** `entities_new / docs_extracted`
in the pipeline log. If yield is consistently <3 entities/doc, the domain's
sources may be too opinion-heavy.

---

## 2. Trend Calibration Worksheet

Each domain needs tuned trend parameters in `domain.yaml` under
`trend_weights`. This section explains the reasoning behind each parameter.

### 2.1 Novelty Decay Lambda

**Parameter:** `novelty_decay_lambda`
**Formula:** `age_novelty = exp(-lambda * age_days)`
**Key relationship:** `half_life_days = ln(2) / lambda ~= 0.693 / lambda`

| Domain | Lambda | Half-Life | Reasoning |
|--------|--------|-----------|-----------|
| AI/ML | 0.05 | ~14 days | New models/tools appear weekly; 2-week-old news is stale |
| Biosafety | 0.03 | ~23 days | Regulatory cycles are slower; a new rule stays "new" for weeks |
| Semiconductors | 0.02 | ~35 days | Process node storylines span quarters; slowest decay |
| Film | 0.07 | ~10 days | Production news cycles fast; rapid turnover |

**How to choose for a new domain:**
1. Ask: "How many days after first mention does an entity stop being 'new'?"
2. That's roughly the half-life. Compute `lambda = 0.693 / half_life_days`.
3. Start conservative (lower lambda), adjust after 2 weeks of data.

### 2.2 Min-Mention Velocity Gate

**Parameter:** `min_mentions_for_velocity`
**Effect:** Entities with fewer recent mentions get velocity = 1.0 (neutral)

| Domain | Threshold | Reasoning |
|--------|-----------|-----------|
| AI/ML | 3 | High volume; 3 mentions is a low bar |
| Semiconductors | 3 | Similar volume expectation |
| Biosafety | 2 | Fewer daily sources; 2 is already meaningful |
| Film | 2 | Regional sources produce fewer mentions per entity |

**Rule of thumb:** Set to `max(2, typical_daily_mentions / 5)`. If most
entities get 1-2 mentions/week, threshold of 2 is right. If entities
routinely get 5+/week, threshold of 3 prevents noise.

### 2.3 Composite Weights

**Parameters:** `velocity`, `novelty`, `activity` (must sum to 1.0)

| Domain | V / N / A | Reasoning |
|--------|-----------|-----------|
| AI/ML | 0.4 / 0.3 / 0.3 | Velocity-driven — "what's accelerating" matters most |
| Biosafety | 0.35 / 0.35 / 0.30 | Balanced — novelty matters for new regulations |
| Semiconductors | 0.4 / 0.3 / 0.3 | Velocity-driven — earnings spikes are key signal |
| Film | 0.4 / 0.3 / 0.3 | Standard profile |

**Adjusting:** Use the calibration report (Sprint 13) trending churn signal.
If churn is >70% (stale), increase velocity weight. If <10% (unstable),
increase activity weight for stability.

### 2.4 Novelty Flooding Risk

When many new entities appear daily, novelty scores compress toward the
middle — everyone is "somewhat new." Monitor with:
- Calibration report signal: novelty compression (13.18)
- If 90%+ of entities have novelty <0.1: lambda is too aggressive (decrease)
- If 90%+ of entities have novelty >0.8: lambda is too slow (increase)

---

## 3. Source Selection Rationale Template

Every feed in `feeds.yaml` should document these four dimensions. Use
`domains/semiconductors/feeds.yaml` as the model.

### Per-Feed Documentation

```yaml
- name: "Source Name"
  url: "https://..."
  # Required documentation:
  signal_type: "What unique signal does this feed provide?"
  #   Examples: "earnings analysis", "policy tracking", "community commentary",
  #   "academic preprints", "product launches"
  limitations: "Known blind spots or biases"
  #   Examples: "24-48h delay", "US-only coverage", "editorializes heavily"
  independence: "Editorial independence assessment"
  #   Examples: "Independent trade press", "Aggregates Reuters wire",
  #   "Same publisher as Feed X (correlated)"
  temporal_risk: "Does this source republish old content with new dates?"
  #   Examples: "Clean — only new articles", "Includes full archive in RSS",
  #   "Republishes evergreen content with updated dates"
```

### Independence Matrix

For each pair of feeds, assess editorial independence:

| | Feed A | Feed B | Feed C |
|---|--------|--------|--------|
| Feed A | - | Independent | Same publisher |
| Feed B | Independent | - | Independent |
| Feed C | Same publisher | Independent | - |

**Minimum independent clusters:** 3. Fewer means the domain is
effectively single-source.

### Temporal Fingerprinting Risk

Feeds that republish old content with new dates break velocity calculation.
If a source's RSS includes its full archive, every pipeline run "discovers"
old articles as new, creating false velocity spikes.

**Mitigation:** Content hashing (`content_hash` in documents table)
catches exact duplicates. Near-duplicates need the `published_at` filter
(30-day default window).

---

## 4. Hypothesis-Generator Framing

### What the Pipeline Is

This pipeline is a **hypothesis generator** — a curated alerting system
that surfaces emerging entities and velocity changes for human review.

At current scale (10-20 sources/day per domain), the system can:
- Surface **emerging entities** early via novelty signal
- Detect **velocity changes** in well-tracked entities
- Identify **bridge entities** connecting otherwise separate clusters
- Generate **"What's Hot and WHY"** narratives for human consumption

### What the Pipeline Is NOT

The system **cannot**:
- **Confirm predictions** with statistical significance (not enough data)
- **Detect events** in real-time (daily batch cadence)
- **Replace human judgment** on trend importance
- **Measure causal relationships** (it tracks co-occurrence, not causation)

### Maturity Stages

| Stage | Overlap Rate | Sources | Capability |
|-------|-------------|---------|-----------|
| **News-only (current)** | 20-30% | 10-20 RSS feeds | Hypothesis generation, novelty/velocity alerts |
| **+Structured signals** | 30-40% | + earnings, filings, registries | Corroboration across signal types |
| **Confirmation capable** | 40%+ | + expert annotations, ground truth | Retroactive validation of predictions |

Each domain starts at Stage 1. The semiconductor domain design doc
estimates reaching Stage 2 after adding SEC EDGAR earnings transcripts.

### Communicating Uncertainty

Every insight from this pipeline should be framed as:
- "Entity X is **emerging** (novelty signal)" — not "X will be important"
- "Entity Y is **accelerating** (velocity signal)" — not "Y is winning"
- "Entities A and B are **newly connected** (bridge signal)" — not "A and B are partnering"

---

## 5. Inference Rules Phasing Guide

Lesson learned from biosafety stabilization and semiconductor design.

### The Problem

Inference rules that fire on day 1 — before the extraction prompt is tuned —
produce false inferences that pollute the graph. These are hard to clean up
because inferred relations look legitimate in the UI.

### The Protocol

1. **Launch with 0-3 rules.** Start conservative. The semiconductor domain
   launched with 3 supply-chain rules (`inference_rules.yaml`).

2. **Run 2 weeks with monitoring.** Check:
   - `scripts/run_calibration_report.py` — orphan edge rate
   - `SELECT COUNT(*) FROM relations WHERE kind='inferred'` — total inferred
   - Manual spot-check: are inferred relations plausible?

3. **Expand if accurate.** Add 2-3 rules per iteration. Each new rule gets
   a 1-week observation period.

4. **Set confidence_discount conservatively.** Start at 0.5-0.6 for new rules.
   Increase to 0.7-0.8 only after validation.

### What Goes Wrong Without Phasing

From the biosafety post-mortem (`docs/fix-details/new-domain-lessons-learned.md`):
- Normalization map gaps caused unmapped relation types to fail validation
- Missing field specs in extraction prompts produced malformed output
- Both issues were caught quickly but required emergency fixes

The same pattern applies to inference: launch simple, validate, expand.

### Rule Design Checklist

For each inference rule, document:
- [ ] **Antecedent pattern:** What relation chain triggers this rule?
- [ ] **Consequent:** What new relation is inferred?
- [ ] **False positive scenario:** When would this rule fire incorrectly?
- [ ] **Validation query:** SQL to check inferred relations for plausibility
- [ ] **Confidence discount:** Starting value (0.5-0.6 recommended)

---

## Quick-Start Checklist for New Domains

```
[ ] Pass 3+ of 5 fitness criteria (Section 1)
[ ] Choose novelty_decay_lambda based on domain half-life (Section 2.1)
[ ] Set min_mentions_for_velocity based on expected volume (Section 2.2)
[ ] Document all feeds with signal_type and independence (Section 3)
[ ] Build independence matrix — minimum 3 clusters (Section 3)
[ ] Frame expectations as hypothesis generation (Section 4)
[ ] Launch with 0-3 inference rules (Section 5)
[ ] Run check_domain_health.py after 7 days — target 20% overlap
[ ] Run calibration report after 14 days — check for anomalies
[ ] Review and expand inference rules after 14 days
```
