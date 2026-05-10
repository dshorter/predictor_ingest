# Semiconductor Domain — 10-Day Experiment Findings

**Experiment window:** 2026-04-08 → 2026-04-18 (Days 1–10 of live operation)
**Author:** Operations log, compiled after Day 10
**Status:** Snapshot. Actions in §6 applied 2026-04-18.

---

## 1. Why this doc exists

The semiconductor domain was stood up as the fourth live domain (after AI/ML,
biosafety, and film) with an explicit design hypothesis captured in
[semiconductor-domain-design.md](semiconductor-domain-design.md): that a
small, analysis-weighted source stack (SemiAnalysis, The Chip Letter,
SemiWiki, Semiconductor Engineering, Chips and Cheese) anchored by two or
three trade-press velocity feeds would produce a graph whose **entity
overlap** — entities appearing in two or more documents — hit the
rule-of-thumb 30% target within ~10 days.

It did not. Overlap plateaued at **19–20%** and stayed there for eight
consecutive days, through 172 successfully extracted documents and 3,102
entities. This doc captures what we learned, what we changed, and what we
would need to add for the corpus to become the persistence-bearing graph
the design called for.

## 2. Day-by-day trajectory

| Day | Date       | Docs extracted | Entities | Overlap | Cost to date | Notes |
|-----|------------|----------------|----------|---------|--------------|-------|
| 1   | 2026-04-08 | ~20            | —        | —       | —            | First ingest; inference stage crashed (schema mismatch) |
| 2   | 2026-04-09 | 50             | 557      | 11%     | $2.30        | Gist script defaulted to AI domain (fixed) |
| 3   | 2026-04-10 | 68             | ~900     | 18%     | $5.40        | Inference schema fixed; first real overlap jump |
| 4   | 2026-04-11 | 86             | 1,599    | 20%     | $8.70        | Tom's Hardware starts dominating entity count |
| 5   | 2026-04-12 | 108            | 1,930    | 19%     | $12.10       | max_tokens=8192 truncation on dense articles (fixed → 16384) |
| 6   | 2026-04-13 | 125            | 2,340    | 19%     | $16.00       | Interrupted batch left two pending batches |
| 7   | 2026-04-14 | 141            | 2,610    | 20%     | $20.20       | EE Times and Register Hardware unreachable (day 1 of outage) |
| 8   | 2026-04-15 | 155            | 2,840    | 20%     | $24.40       | Overlap officially declared "stuck" |
| 9   | 2026-04-16 | 164            | 2,970    | 20%     | $28.76       | — |
| 10  | 2026-04-17 | 172            | 3,102    | 20%     | $29.96       | Root-cause analysis below |

Budget note: design target was ~$26 for the first month assuming Sonnet
extraction on 15–20 docs/day. Actual cost after 10 days is $29.96, slightly
over pace, driven by the Tom's Hardware volume surcharge rather than per-doc
price.

## 3. The 20% plateau — what is actually happening

### 3.1 The entity count is dominated by one source

Breaking the 172-doc / 3,102-entity corpus down by source:

| Source                    | Docs | % of docs | Entities | % of entities | Entities/doc |
|---------------------------|------|-----------|----------|---------------|--------------|
| Tom's Hardware            | 80   | 47%       | 2,047    | 66%           | 25.6         |
| Semiconductor Engineering | 31   | 18%       | 412      | 13%           | 13.3         |
| SemiWiki                  | 22   | 13%       | 238      | 8%            | 10.8         |
| SemiAnalysis              | 14   | 8%        | 168      | 5%            | 12.0         |
| Chips and Cheese          | 11   | 6%        | 124      | 4%            | 11.3         |
| The Chip Letter           | 7    | 4%        | 73       | 2%            | 10.4         |
| (EE Times / Register)     | 7    | 4%        | 40       | 1%            | 5.7          |

Tom's Hardware is **47% of documents and 66% of entities** despite being
explicitly designated a Tier-2 echo source. It produces roughly 2× the
entities-per-doc of every other feed.

### 3.2 Those entities are denominator pollution

The entities Tom's Hardware contributes are reliably the wrong kind for
persistence:

- Variant SKUs: `H100 SXM5 80GB`, `RX 7900 XTX reference`, `Arc A770 Limited Edition`
- Benchmark configs: `3DMark Time Spy Extreme`, `Cinebench R23 Multi`
- Test-rig components: specific motherboards, PSUs, memory kits
- Store-shelf product names that change per-article

None of these appear in a second document. They are born orphan and stay
orphan. Every such entity adds 1 to the denominator of the overlap metric
(`entities with 2+ docs / total entities`) and 0 to the numerator.

If we naïvely strip Tom's Hardware from the corpus:
- Docs: 172 → 92
- Entities: 3,102 → 1,055
- Entities seen in 2+ docs: ~620 (unchanged — they're in the other sources)
- Overlap: 20% → **~58%**

That counterfactual is too good to take at face value, but it quantifies
the pollution: more than half of our denominator is contributed by a source
that provides almost nothing to the numerator.

### 3.3 The anchor entities are healthy

The top corroborated entities across the corpus:

| Entity  | Doc count |
|---------|-----------|
| Intel   | 65        |
| NVIDIA  | 60        |
| AMD     | 54        |
| TSMC    | 41        |
| ASML    | 28        |
| Samsung | 22        |

This is exactly the shape the domain design asked for — a few high-centrality
anchor companies appearing across the entire date range. The graph's core is
well-formed. The 20% number is a **metric problem, not a graph-health
problem**, and that distinction is the most important thing we learned.

## 4. Re-reading the 30% target

The 30% figure in the domain design doc is a **rule-of-thumb heuristic**
carried over from film and AI, not a threshold derived from the semiconductor
corpus itself. The design doc itself flags this; we had not taken the flag
seriously.

Two reframings that would make the target meaningful for this domain:

**A. Trending-weighted overlap.** Compute overlap only over entities that
clear a minimum mention threshold in a rolling window (say, 3+ mentions in
30 days). This eliminates one-shot SKU entities by construction. Under this
definition, the current corpus sits at ~74%.

**B. Source-balanced overlap.** Weight each document's contribution to the
denominator by `1 / source_doc_count`. A feed that dominates the corpus
stops dominating the metric.

Both are reasonable; neither is implemented yet. For now we keep the raw
metric but annotate it, and we cut the pollutant source at ingest.

## 5. Related diagnosis — source health

Two Tier-2 feeds have been unreachable for 8+ consecutive days:

- **EE Times** (`https://www.eetimes.com/feed/`) — 502s from VPS
- **The Register Hardware** (`/hardware/semiconductors/headlines.atom`) —
  URL path may have changed; returns HTML not feed XML

These are listed in the deferred actions below. They're not contributing to
the plateau (they're not contributing anything), but leaving broken feeds
enabled distorts the pipeline health log.

## 6. Actions applied (Day 10)

1. **Tom's Hardware: `limit: 10` → `limit: 3`** in `domains/semiconductors/feeds.yaml`.
   Rationale: drop the volume, keep the velocity signal on genuinely
   significant product launches. Expected effect: overlap rises to
   25–28% within one week as the Tom's Hardware contribution ages out of
   the 30-day rolling entity pool.

2. **Earnings-call / SEC EDGAR / IR-RSS feeds added as disabled placeholders.**
   These are the persistence layer the current stack is missing. A 10-K or
   earnings call names the same supply-chain relationships every single
   quarter — that's exactly the kind of re-assertion the overlap metric is
   designed to reward. None of these are RSS-native; each needs a connector
   type that doesn't exist yet (`edgar`, `earnings`, `ir_rss`).

## 7. Deferred actions

- **Drop EE Times and The Register Hardware** (or fix their URLs) after
  one more week of confirmed unreachability.
- **Build the `edgar` connector.** Highest-leverage single item in the
  backlog for this domain. SEC provides per-CIK RSS feeds; no auth needed;
  filings are free-text. Start with NVIDIA, Intel, AMD, TSMC (20-F), ASML
  (20-F).
- **Build the `ir_rss` connector** — essentially a regular RSS connector
  with a per-feed metadata tag flagging the source as Tier-1 primary.
  Might not need a new type at all, just a convention.
- **Defer the `earnings` connector.** Transcripts are behind paywalls at
  Seeking Alpha; company IR pages host their own with a 3–7 day lag. This
  is a "V2 connector type" and can wait.
- **Implement trending-weighted overlap** in the pipeline health script.
  Quick win; the raw overlap number is actively misleading new readers.

## 8. Cost analysis

| Item                        | Budgeted | Actual  | Note |
|-----------------------------|----------|---------|------|
| LLM extraction (10 days)    | $22.00   | $27.60  | Tom's Hardware volume surcharge |
| Synthesis / narrative runs  | $3.00    | $2.06   | Fewer clusters than expected |
| Infra                       | $1.00    | $0.30   | — |
| **Total**                   | **$26.00** | **$29.96** | +15% over |

After the Tom's Hardware cut, per-day extraction cost should drop from
~$2.80 to ~$2.00, bringing the monthly projection back under budget even
with slightly higher per-article cost on the deeper sources.

## 9. What we actually learned

- **Rule-of-thumb thresholds don't transfer across domains.** The 30%
  overlap number made sense for film (bounded entity universe: titles,
  directors, festivals) and AI (heavy overlap on orgs and models). It
  doesn't transfer cleanly to a domain where half the trade press is
  product-review coverage.
- **One source can quietly define the shape of your graph.** Tom's Hardware
  was added as an echo source and produced the majority of the entity mass.
  We didn't catch this for 10 days because the aggregate number (3,102
  entities) looked healthy.
- **The anchor layer worked.** Intel, NVIDIA, AMD, TSMC, ASML corroborated
  across 20–65 documents each. The design's bet that analysis newsletters
  would keep re-naming the same core entities was correct.
- **The missing layer is primary-source filings.** News is fast and noisy;
  filings are slow and stable. A serious industry graph needs both. This
  is what the earnings-call addition in §6 is about.
- **Metric health ≠ graph health.** Always plot overlap-by-source and
  top-N entities before declaring a number "bad." The core graph was
  fine from Day 4 onward.

## 10. References

- [semiconductor-domain-design.md](semiconductor-domain-design.md) —
  original domain design and stated 30% target
- [deep-research-report.md](deep-research-report.md) — EDGAR and
  earnings-transcript notes (originally written for AI, applicable here)
- [prediction-methodology.md](prediction-methodology.md) — overlap metric
  definition and weight-tuning protocol
- `domains/semiconductors/feeds.yaml` — source stack with Day-10 edits
- `docs/backend/daily-run-log.md` — raw numbers behind §2
