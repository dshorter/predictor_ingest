# Predictive Signal Methodology

How we go from raw source ingestion to actionable trend predictions, and how we
know whether those predictions are any good.

---

## 1. Overview

The system detects emerging AI trends by monitoring a curated set of public
sources, extracting structured claims, and computing composite signals over
time. It does **not** forecast specific events. Instead it answers:

> "Which entities/technologies are accelerating in discourse and structural
> importance, and which are decelerating?"

The output is a ranked list of trending entities with scores that combine
**velocity**, **novelty**, and **bridge centrality**. Those scores drive the
visual encoding in the graph UI and can be evaluated against ground truth
retrospectively.

---

## 2. Source Coverage

### 2.1 Minimum Viable Coverage

Predictions are only as good as the input corpus. We need enough diversity to
separate genuine signal from source-specific noise.

| Dimension          | V1 Target | Rationale |
|--------------------|-----------|-----------|
| Source count        | >= 10 distinct feeds | Avoid single-source bias |
| Source categories   | >= 3 categories (academic, industry, open-source) | Cross-domain triangulation |
| Daily document volume | 10-30 docs/day | Enough for statistical trends without overwhelming extraction |
| Fetch frequency     | 1x/day minimum | Daily cadence matches trend window granularity |
| Lag tolerance       | <= 24 hours from publish to ingest | Longer lag degrades velocity accuracy |

### 2.2 Current Sources (V1)

| Source | Category | Est. Volume |
|--------|----------|-------------|
| arXiv CS.AI | Academic | 10-30 papers/day |
| Hugging Face Blog | Open-source ecosystem | 2-5 posts/week |
| OpenAI Blog | Industry | 1-3 posts/week |

**Gap:** 3 sources is below the 10-source minimum. The immediate risk is that
a trend appearing in only one source looks identical to a trend confirmed
across many. Source expansion is the single highest-priority improvement for
prediction quality.

### 2.3 Planned Source Expansion

Priority additions (each adds a distinct category or viewpoint):

| Source | Category | Why |
|--------|----------|-----|
| Google DeepMind Blog | Industry (non-OpenAI) | Second major lab perspective |
| Anthropic Blog/Research | Industry | Third lab; different priorities |
| MIT Technology Review AI | Journalism | Synthesis/interpretation layer |
| The Gradient | Commentary/analysis | Independent academic commentary |
| Papers With Code (trending) | Benchmarks/leaderboards | Quantitative performance signals |
| GitHub Trending (ML topic) | Open-source activity | Code-level adoption signal |
| AI policy feeds (NIST, EU AI Act) | Regulation | Regulatory catalysts |
| Hacker News (AI filter) | Community discourse | Practitioner attention proxy |

### 2.4 Source Quality Attributes

Each source should be evaluated on:

- **Timeliness:** How quickly does it surface new information?
- **Signal density:** Ratio of extractable claims to total text.
- **Entity coverage:** Does it name specific tools, models, orgs?
- **Independence:** Does it overlap heavily with another source?

### 2.5 Source Selection as Methodology

Source selection is not administrative — it is a **methodological decision**
that directly affects prediction quality. Every source in the list shapes
which entities are visible, how quickly trends surface, and what biases exist
in the output. Treat the source list with the same rigor as the scoring
formulas.

**Principles:**

1. **Coverage mapping before adding.** Before adding a source, document which
   entity types and topic areas it primarily covers. This creates a coverage
   map that exposes gaps and redundancies.

2. **Category balance.** Maintain representation across source categories
   (academic, industry, open-source, journalism, policy, community). Over-
   weighting one category biases which signals arrive first.

3. **Topic coverage inventory.** For each major topic area the system tracks,
   at least 2-3 sources should provide regular coverage. If a topic depends
   on a single source, that topic's trend signals are fragile.

4. **Independence requirement.** Two sources that syndicate or republish each
   other's content count as one source for corroboration purposes. Prefer
   sources with original reporting or analysis.

5. **Volume balance.** A source producing 30 docs/day alongside one producing
   1 doc/week creates a volume imbalance that raw mention counts can't
   distinguish from genuine signal. Per-source normalization (Section 4)
   mitigates this, but extreme imbalances should be avoided at selection time.

### 2.6 Source Coverage Profile

Each source should have a documented **coverage profile** recording:

```yaml
source: "arXiv CS.AI"
category: "academic"
primary_entity_types: ["Paper", "Model", "Dataset", "Benchmark", "Person"]
primary_topics: ["machine learning", "NLP", "computer vision", "reinforcement learning"]
avg_volume: "10-30 docs/day"
timeliness: "same-day (preprint)"
signal_density: "high (structured metadata, explicit claims)"
independence: "primary source (not syndicated)"
added_date: "2026-01-15"
```

When the source list changes, these profiles enable impact assessment:
what coverage is being gained or lost.

### 2.7 Source Substitution Protocol

When a source must be replaced (it shuts down, degrades in quality, becomes
paywalled, etc.), the replacement is not arbitrary. The goal is **coverage
continuity** — the replacement should cover the same entity types and topic
areas as the source it replaces.

#### Why substitution matters

Each source carries an implicit "topic portfolio." Entities that were
primarily tracked through that source will experience an artificial signal
discontinuity when it disappears:

- **False deceleration:** Entities covered heavily by the old source lose
  mentions → velocity drops, even though nothing changed in the real world
- **False acceleration:** If the replacement source covers different topics,
  those topics gain mentions → velocity spikes artificially
- **Coverage gaps:** If a topic was only covered by the departing source
  and the replacement doesn't cover it, that topic becomes invisible to
  the system — the most dangerous failure mode, because it's silent

#### Substitution checklist

Before swapping a source:

1. **Pull the departing source's coverage profile** (Section 2.6)
2. **Identify entities primarily covered by this source** — entities where
   >50% of recent mentions came from this source
3. **Select a replacement that overlaps on primary entity types and topics.**
   Compare coverage profiles. A good replacement shares >= 60% of the
   departing source's primary_topics
4. **Check the replacement's independence** — don't replace a source with
   one that syndicates from a source you already have
5. **Apply a transition window** (see below)
6. **Log the substitution** in the source change log (Section 2.8)

#### Transition window

When a source is swapped, velocity calculations spanning the change date
are unreliable. To prevent false signals:

- **Dampening period:** 14 days (2x the standard velocity window)
- During the dampening period, mentions from the new source are weighted
  at 0.5x, ramping linearly to 1.0x by day 14
- Mentions from the old source in the historical window are kept at full
  weight (they're real data, just no longer growing)
- After day 14, the new source is treated as fully established

This ensures velocity ratios don't spike or crash due to the swap itself.

#### Batch substitution limits

| Sources swapped simultaneously | Risk level | Action |
|-------------------------------|------------|--------|
| 1 of 20 | Low | Standard transition window |
| 2-3 of 20 | Medium | Transition window + review top-20 trending for false signals |
| 4-5 of 20 (20-25%) | High | Extended dampening (21 days); flag all trending output as provisional |
| 6+ of 20 (>25%) | Critical | Treat as corpus re-initialization; reset velocity baselines |

### 2.8 Source Change Log

Every addition, removal, or substitution must be logged. This log is
essential for interpreting historical trend data — a velocity spike on
the same day a source was added is probably an artifact, not a real trend.

| Date | Action | Source | Replacement | Reason | Coverage Impact |
|------|--------|--------|-------------|--------|-----------------|
| (initial) | added | arXiv CS.AI | — | Initial source set | Academic papers |
| (initial) | added | Hugging Face Blog | — | Initial source set | Open-source ecosystem |
| (initial) | added | OpenAI Blog | — | Initial source set | Industry announcements |

This log should live in `config/source_changelog.yaml` and be machine-readable
so that the scoring pipeline can detect recent source changes and apply
transition dampening automatically.

---

## 3. Signal Distillation Pipeline

### 3.1 Architecture

```
Sources ──► Ingest ──► Clean ──► Extract ──► Resolve ──► Score ──► Rank
  │                                │            │          │
  │                                ▼            ▼          ▼
  │                           Structured    Canonical   Composite
  │                            claims       entities     scores
  │                                                       │
  └──────────────────────────────────────────────────────► Validate
                          (retrospective)
```

Each stage has a defined contract and quality gate.

### 3.2 Extraction Quality Gate

Before any signal scoring, extractions must pass:

1. **Schema validation** — JSON Schema conformance (`schemas/extraction.json`)
2. **Evidence requirement** — Every `asserted` relation has >= 1 evidence
   snippet with docId, URL, and quote
3. **Confidence bounds** — All confidence scores in [0.0, 1.0]
4. **Entity type constraint** — All entities use canonical type enum

Extractions that fail validation are rejected, not silently included.

### 3.3 Entity Resolution Quality Gate

Before scoring, entities must pass through resolution:

1. **Fuzzy match threshold** — Default 0.85 similarity (configurable)
2. **Alias tracking** — All merges recorded in `entity_aliases` table
3. **No silent overwrites** — Merges redirect, never delete

### 3.4 Signal Components

#### Velocity (weight: 0.40)

**What it measures:** Rate of change in mention frequency.

**Formula:**
```
velocity = mentions(t-7d..t) / mentions(t-14d..t-7d)
```

- `> 1.0` — accelerating
- `= 1.0` — steady
- `< 1.0` — decelerating
- New entities (no prior window): `mentions + 1` (high default)

**Normalization:** Capped at 5.0 for composite scoring (`velocity_factor = min(velocity, 5.0) / 5.0`).

**Known limitations:**
- Sensitive to low counts: 1 mention → 2 mentions = 2.0x velocity, which
  overstates significance at low volume
- Window size is fixed at 7 days; some trends develop over weeks
- Does not distinguish sustained acceleration from a single spike

**Planned improvements:**
- Bayesian smoothing for low-count entities (add pseudocounts)
- Multi-window velocity (7d, 14d, 30d) with weighted blend
- Spike detection vs. sustained trend classification

#### Novelty (weight: 0.30)

**What it measures:** How new and rare an entity is in our corpus.

**Formula:**
```
age_novelty = max(0, 1 - (days_since_first_seen / 365))
rarity = 1 / (1 + ln(1 + total_mentions))
novelty = 0.6 * age_novelty + 0.4 * rarity
```

- Brand new entity: ~1.0
- 6-month old entity with few mentions: ~0.5-0.7
- Year-old entity with many mentions: ~0.1-0.2

**Known limitations:**
- "First seen" is relative to when *we* started ingesting, not when the
  entity actually emerged
- A well-known entity we haven't seen before gets artificially high novelty
- Age decay is linear; real novelty probably decays faster initially

**Planned improvements:**
- Cross-reference first appearance against external sources (Wikidata,
  Wikipedia creation date) to calibrate true novelty
- Exponential decay curve instead of linear
- "Novel *to our corpus*" vs "novel *in the world*" distinction

#### Bridge Score (weight: 0.30 via activity proxy)

**What it measures:** Structural importance — how much an entity connects
different clusters in the knowledge graph.

**Formula:**
```
outgoing = count(distinct targets where entity is source, excluding MENTIONS)
incoming = count(distinct sources where entity is target, excluding MENTIONS)
bridge = sqrt((outgoing + 1) * (incoming + 1)) - 1
```

- Isolated entity: 0.0
- Well-connected hub: high score

**Known limitations:**
- Currently a static snapshot, not a delta over time
- Doesn't use true betweenness centrality (too expensive at scale)
- Treats all non-MENTIONS relations equally regardless of type

**Planned improvements:**
- `bridge_delta` — change in bridge score over time (7d window)
- Relation-type weighting (e.g., DEPENDS_ON is more structurally
  significant than MENTIONS)
- Approximate betweenness for high-degree nodes

#### Composite Trend Score

**Formula:**
```
trend_score = 0.40 * velocity_factor
            + 0.30 * novelty
            + 0.30 * activity_factor

where:
  velocity_factor = min(velocity, 5.0) / 5.0
  activity_factor = min(mention_count_7d, 20) / 20.0
```

**Design rationale:**
- Velocity is weighted highest because *acceleration* is the strongest
  leading indicator
- Novelty rewards new entrants that might be missed by pure volume
- Activity prevents zero-mention entities from scoring highly on novelty
  alone

**The weights (0.40 / 0.30 / 0.30) are initial hypotheses.** They should be
tuned based on validation results (Section 5).

---

## 4. Source Sufficiency Criteria

### 4.1 When Is a Signal "Real"?

A trend signal gains confidence when it is **corroborated across sources**.
Single-source signals should be flagged and downweighted.

| Corroboration Level | Description | Confidence Modifier |
|---------------------|-------------|---------------------|
| 1 source            | Uncorroborated | 0.5x weight |
| 2 sources           | Weak corroboration | 0.75x weight |
| 3+ sources          | Corroborated | 1.0x (full weight) |
| 3+ sources, 2+ categories | Strong corroboration | 1.25x weight |

**Not yet implemented.** This requires a `source_count` metric per entity
per time window.

### 4.2 Minimum Evidence Thresholds

| Metric | Minimum for "trending" | Minimum for "high confidence" |
|--------|------------------------|-------------------------------|
| mention_count_7d | >= 2 | >= 5 |
| Distinct source count | >= 1 | >= 3 |
| Distinct document count | >= 2 | >= 5 |
| Has asserted relation | No (mentions suffice) | Yes |

### 4.3 Query Frequency and Freshness

| Parameter | Value | Why |
|-----------|-------|-----|
| RSS poll interval | 1x daily | Matches 7-day trend window granularity |
| Fetch-to-score lag | < 24h | Velocity is meaningless if data is stale |
| Trend recompute | Daily (after ingest) | Aligned with pipeline cadence |
| Graph export | Daily | Client shows "as of" date |

---

## 5. Validation Framework

### 5.1 Why Validate?

Without validation, we cannot distinguish between:
- A methodology that detects real trends early
- A methodology that generates plausible-looking noise
- A methodology that detects trends but only after they're obvious

### 5.2 Retrospective Validation (Primary Method)

**Process:**

1. At time `T`, record the top-N trending entities and their scores
2. At time `T + Δ` (e.g., 30 days, 90 days), evaluate what actually happened
3. Score predictions against outcomes

**Outcome categories:**

| Outcome | Definition |
|---------|------------|
| **Confirmed trend** | Entity continued to accelerate or reached mainstream adoption |
| **Flash in the pan** | Entity spiked briefly then disappeared |
| **Slow burn** | Entity didn't spike but gradually increased (we missed it or scored it low) |
| **Correct negative** | Entity we didn't flag, and it didn't trend |

**Metrics:**

| Metric | Formula | Target (V1) |
|--------|---------|-------------|
| **Precision@10** | (confirmed trends in top 10) / 10 | >= 0.50 |
| **Precision@20** | (confirmed trends in top 20) / 20 | >= 0.40 |
| **Recall (known trends)** | (detected trends) / (total confirmed trends in period) | >= 0.60 |
| **Lead time** | Days between our first trending signal and mainstream coverage | > 0 (any lead) |
| **False positive rate** | (flash-in-pan in top 20) / 20 | <= 0.30 |

### 5.3 Ground Truth Sources

For retrospective validation, we need external ground truth:

| Source | What it tells us | Granularity |
|--------|-----------------|-------------|
| Google Trends (AI terms) | Public search interest over time | Weekly |
| Papers With Code (SOTA tables) | When a model/method achieves SOTA | Per-benchmark |
| GitHub star velocity | Open-source adoption rate | Daily |
| Major tech news coverage | Mainstream awareness | Per-article |
| Product launches / press releases | Industry adoption | Per-event |

### 5.4 Validation Cadence

| Interval | Action |
|----------|--------|
| Weekly | Snapshot top-20 trending entities with scores |
| Monthly | Review past month's snapshots against outcomes |
| Quarterly | Compute precision/recall/lead-time metrics; adjust weights if needed |

### 5.5 A/B Testing Weights

When adjusting composite weights (velocity/novelty/activity):

1. Run both old and new weights in parallel for >= 2 weeks
2. Compare precision@20 and false positive rate
3. Only adopt new weights if both metrics improve (or one improves with
   the other unchanged)
4. Document every weight change with rationale and validation results

---

## 6. Known Biases and Mitigations

| Bias | Description | Mitigation |
|------|-------------|------------|
| **Source selection bias** | Our feed list skews toward English, US/EU, large labs | Expand sources; track geographic/org diversity metrics |
| **Extraction bias** | LLM extractors may favor well-known entities | Monitor extraction recall by entity type; audit low-confidence extractions |
| **Volume bias** | High-volume sources dominate mention counts | Normalize mention counts per-source before aggregation |
| **Recency bias** | System favors new entities over genuinely important established ones | Novelty score is explicitly time-decayed; bridge score rewards established connectors |
| **Publication bias** | Sources publish about successes more than failures | Track `polarity` field; monitor ratio of positive to negative claims |
| **Survivorship bias** | We only see entities that get mentioned; silent failures are invisible | Cannot fully mitigate in V1; document as limitation |

---

## 7. Metrics Dashboard (Planned)

Track these metrics over time to assess system health:

### 7.1 Pipeline Health

| Metric | Healthy Range |
|--------|---------------|
| Docs ingested / day | 10-30 |
| Extraction success rate | >= 95% |
| Entity resolution merge rate | 5-15% per pass |
| Unique entities (cumulative) | Growing 5-20/week |
| Relations / document | 3-15 |

### 7.2 Signal Quality

| Metric | Healthy Range |
|--------|---------------|
| Entities with velocity > 1.0 | 10-40% of total |
| Entities with novelty > 0.7 | 5-20% of total |
| Average evidence snippets / asserted relation | >= 1.5 |
| Source diversity (distinct sources / entity in top 20) | >= 2.0 avg |

### 7.3 Prediction Quality

| Metric | Target |
|--------|--------|
| Precision@10 (30-day retrospective) | >= 0.50 |
| Precision@20 (30-day retrospective) | >= 0.40 |
| Recall (known major trends, quarterly) | >= 0.60 |
| Median lead time (days ahead of mainstream) | > 3 days |
| False positive rate (top 20) | <= 0.30 |

---

## 8. Weight Tuning Protocol

The composite score weights (`0.40 velocity + 0.30 novelty + 0.30 activity`)
are hypotheses. Here is the protocol for tuning them:

### 8.1 Prerequisites

- At least 30 days of daily trending snapshots
- At least 1 completed retrospective validation cycle
- Precision@20 and false positive rate computed for current weights

### 8.2 Procedure

1. Propose new weights based on validation findings
   - e.g., if velocity is generating too many flash-in-the-pan signals,
     reduce its weight and increase bridge/activity
2. Recompute historical trend scores with new weights (offline replay)
3. Compare precision/recall against same ground truth
4. If improved: run both weight sets in parallel for 14 days on live data
5. If still improved on live data: adopt new weights; document change

### 8.3 Weight Change Log

| Date | Old Weights | New Weights | Reason | P@20 Change |
|------|-------------|-------------|--------|-------------|
| (initial) | 0.40/0.30/0.30 | — | Starting hypothesis | — |

---

## 9. V1 vs V2 Scope

| Capability | V1 | V2 |
|------------|----|----|
| Velocity scoring | 7-day window ratio | Multi-window + Bayesian smoothing |
| Novelty scoring | Age + rarity | + external first-appearance calibration |
| Bridge scoring | Static snapshot | Delta over time |
| Source corroboration | Not weighted | Per-entity source diversity modifier |
| Volume normalization | Raw counts | Per-source normalized counts |
| Source substitution | Manual, no dampening | Transition windows + automated dampening |
| Source coverage profiles | Not tracked | Per-source YAML profiles with topic inventory |
| Validation | Manual retrospective review | Semi-automated with ground truth feeds |
| Weight tuning | Manual A/B | Offline replay + automated comparison |
| Spike vs. sustained | Not distinguished | Binary classifier on velocity curve shape |
| Confidence intervals | Point estimates only | Bootstrap CIs on trend scores |

---

## 10. Implementation Checklist

These are concrete next steps, ordered by impact on prediction quality:

- [ ] **Expand to >= 10 sources** across >= 4 categories
- [ ] **Add source_count metric** per entity per time window
- [ ] **Implement corroboration weighting** (Section 4.1)
- [ ] **Per-source mention normalization** to prevent volume bias
- [ ] **Weekly trending snapshot script** for validation data collection
- [ ] **Retrospective validation script** comparing snapshots to outcomes
- [ ] **bridge_delta metric** (bridge score change over 7d window)
- [ ] **Low-count Bayesian smoothing** for velocity
- [ ] **Multi-window velocity** (7d + 14d + 30d blend)
- [ ] **Pipeline health dashboard** (Section 7.1 metrics)
- [ ] **Spike vs. sustained trend classifier**
- [ ] **Source coverage profiles** for all active sources (Section 2.6)
- [ ] **Source change log** in `config/source_changelog.yaml` (Section 2.8)
- [ ] **Transition dampening** in velocity calculation after source swaps (Section 2.7)
- [ ] **Per-entity primary source tracking** to flag fragile single-source signals
