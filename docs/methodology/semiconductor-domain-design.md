# Semiconductor Domain Design Rationale
*Written: 2026-04-02 | Captures reasoning from design session, not reconstructable from config alone*

## Why This Document Exists

The `domains/semiconductors/` config files capture *what* was built. This document
captures *why* — the domain candidate evaluation, the source selection reasoning, and
the architectural decisions that aren't obvious from YAML alone. Future sessions should
read this before modifying the domain.

---

## Domain Candidate Evaluation

The pipeline works best when a domain has **persistent entities and corroborable claims**.
Several candidates were evaluated before landing on semiconductors.

### Candidates Rejected

**Academia / Research**
- Papers take months from preprint to citation. Story cycles are measured in quarters,
  not weeks. The pipeline's 7-day velocity window produces no signal.
- Entity churn is moderate but corroboration is slow: a paper cited in 3 sources over
  6 months doesn't produce useful velocity signal.
- Verdict: too slow-moving for early trend detection.

**Entertainment (beyond film)**
- Same structural problem as film: event-driven journalism, high entity churn, low
  corroboration. TV show announcements, casting news, streaming deals — all appear once
  and vanish.
- Verdict: different domain, identical shape problem.

**Finance / Economics**
- High volume, persistent entities (companies, indices, rates), but heavily paywalled.
  WSJ, Bloomberg, FT are not accessible via public RSS. Free alternatives are echo
  chambers with no independent corroboration.
- Verdict: source access problem, not a shape problem.

**AI / ML (primary domain)**
- Already running. Has a shape problem: new models, papers, and tools release
  constantly, inflating the entity denominator faster than corroboration accumulates.
- Kept as the primary production domain but acknowledged as a harder shape for overlap.
- AI/ML is where the pipeline started and where the most extraction history exists —
  not worth abandoning, but not the experimental target.

**Biosafety (second domain)**
- Already running. Good entity persistence (select agents, regulations, facilities
  don't change daily). But the news cycle is slow and ingest volume is low.
- Kept running but not the experimental target.

### Semiconductors: Why It Passes the Shape Test

| Shape criterion | Film | Semiconductors |
|-----------------|------|----------------|
| Persistent entities | ✗ New productions weekly | ✓ TSMC N3E discussed for 18+ months |
| Multiple independent sources | Partial | ✓ 8 technical outlets with different angles |
| Corroborable claims | ✗ Narrative / opinion heavy | ✓ Tape-out, yield, node specs are factual |
| Story cycle length | Days–weeks | Weeks–months (node → HVM: 18 months) |
| Actionable early detection | Low | ✓ Supply chain shifts visible weeks early |
| Inference potential | Low | ✓ Supply chain chains auto-infer SUPPLIES edges |

---

## GPU and Accelerator Coverage

A motivating question was whether the pipeline could detect GPU/accelerator trends.
Semiconductors is the **natural home** for this signal — not AI/ML.

In the AI/ML domain, H100 and Blackwell appeared as entities but were mixed in with
model releases, research papers, and API announcements. The signal was diluted: a GPU
cluster procurement story and a transformer architecture paper get equal weight.

In the semiconductors domain:
- `H100`, `H200`, `B200` are `Chip` entities with explicit `USES_PROCESS`,
  `USES_PACKAGING`, and `DESIGNS` edges
- `CoWoS`, `HBM3e` are `Packaging`/`Material` entities — the bottleneck signals
- `TSMC`, `Samsung Foundry` are `Fab` entities — the supply constraint signals
- Demand (AI workloads) drives supply (packaging capacity) which constrains availability
  (GPU allocation) — the full chain is representable

An early observation from the AI/ML domain: H100 and Blackwell appeared in the top-5
trending entities, then dropped off the "What's Hot" list within 1–2 weeks — not
because they became less important, but because the AI/ML corpus moved to other topics.
In a dedicated semiconductor domain, GPU storylines would have the context (competing
process nodes, CoWoS capacity, HBM supply) to stay coherent over multi-month cycles.

---

## The 30% Overlap Target: What It Actually Represents

The 30% overlap target is a **rule-of-thumb heuristic, not a derived threshold**. It
was chosen based on intuition about when velocity signals become reliable, and has not
been empirically validated. This section documents what it's meant to represent and
what validation would look like.

### Why overlap matters for velocity

Velocity requires at least two data points to compute. An entity appearing in only one
document has undefined velocity — you can't distinguish "emerging trend" from "random
mention."

| Overlap rate | What it means for trend signals |
|--------------|--------------------------------|
| <20% | Most entities have 1 document. Velocity is undefined for 80%+ of the graph. Trending output is mostly noise. |
| 20–25% | Some corroboration exists but most trends are single-source. Velocity computable for ~20–25% of entities, unreliable for the rest. |
| 30% | Enough entities have 2+ appearances to compute velocity across a meaningful fraction of the graph. Bridge detection starts to work. |
| >40% | Velocity is reliable, novelty scoring stabilizes, bridge entities are meaningful rather than lucky. |

At 30%, an entity with 6 mentions in the last 7 days vs 2 in the prior 7 days = 3× velocity.
That ratio means something when the entity has a multi-week history. At 19% overlap
(film's current state), most "velocity spikes" are just a second article appearing after
a long gap — not acceleration.

### What reaching 30% would actually unlock

1. **Reliable velocity scoring.** The `velocity_cap: 5.0` in trend weights becomes
   meaningful because enough entities have historical mention counts to normalize against.

2. **Bridge entity detection.** A node connecting two otherwise disconnected clusters
   is only a meaningful early signal if both clusters have their own internal corroboration.
   At low overlap, every entity is potentially a bridge but none are significant.

3. **Noise-resistant trending.** The "What's Hot" list stabilizes — entities stay on
   it because they're genuinely accelerating, not because they just got their second
   ever mention.

### Why 30% is unvalidated

The number was chosen without a backtest. A proper validation would:
1. Take a domain with known historical trends (e.g., the TSMC N3 ramp in 2022–2023)
2. Run the pipeline historically with overlap at 19%, 25%, 30%, 35%
3. Measure whether the "What's Hot" list at each overlap rate would have surfaced the
   trend before consensus coverage

This backtest is in the backlog but hasn't been run. The 30% target should be treated
as a starting hypothesis, not a validated threshold.

---

## Feed Selection Rationale

Eight feeds were selected for the initial semiconductor domain. Selection criteria:
public RSS access, practitioner-grade content, distinct editorial angle from the others,
known reliability, semiconductor specificity (not general tech).

### Selected Feeds

**SemiAnalysis** (`semianalysis.com`)
- Why: David Kanter and Dylan Patel produce the most technically precise supply chain
  and process node analysis available publicly. First to publish detailed HBM capacity
  numbers, CoWoS bottleneck analysis, and fab utilization estimates.
- Signal type: Supply chain depth, capacity constraints, cost-per-wafer analysis.
- Known limitation: Deep-dive articles are infrequent (2–4/week). Volume is low but
  density per article should be very high.

**The Chip Letter** (`thechipletter.substack.com`)
- Why: Anton Shilov covers process node technology from a different angle than
  SemiAnalysis — more architecture-focused, less supply chain. Provides cross-source
  corroboration on the same node announcements.
- Signal type: Process node architecture, transistor density, EUV lithography.

**Semiconductor Engineering** (`semiengineering.com`)
- Why: Broadest coverage of any semiconductor outlet. Covers equipment, materials,
  packaging, design tools, and policy. High volume (10–20 articles/day).
- Signal type: Industry breadth, emerging packaging/material trends, standards.

**Chips and Cheese** (`chipsandcheese.com`)
- Why: Architecture deep-dives and benchmarks for consumer and datacenter chips.
  Unique in combining microarchitecture analysis with measured performance data.
  Key for GPU/accelerator trend detection.
- Signal type: Chip architecture, benchmark comparisons, IPC analysis.

**EE Times** (`eetimes.com`)
- Why: Long-running trade publication. Good coverage of policy (CHIPS Act, export
  controls), M&A, and standards. Provides the regulatory/business layer.
- Signal type: Policy, business, standards bodies.

**The Register — Hardware** (`theregister.com/hardware/`)
- Why: Fast news cycle, picks up rumors and leaks early. Often first to report on
  supply chain disruptions, product cancellations, and earnings surprises.
- Signal type: Breaking news, rumors, supply disruptions.

**SemiWiki** (`semiwiki.com`)
- Why: Community blog with practitioner contributors. Captures perspectives from
  engineers and analysts not published elsewhere.
- Signal type: Practitioner commentary, tool ecosystem, design methodology.

**Tom's Hardware** (`tomshardware.com`)
- Why: High-volume benchmark-heavy coverage. Useful for GPU/CPU performance comparison
  entities and product launch tracking.
- Signal type: Product launches, benchmarks, consumer GPU.

### Feeds Considered but Not Included

**Real World Tech** — Technically excellent (David Kanter's older work) but RSS
feed is inconsistent. Marked disabled in feeds.yaml; verify before enabling.

**AnandTech** — Site is archived/dormant as of 2023. Not a live feed.

**IEEE Spectrum** — Too broad (covers all engineering). Semiconductor coverage
is diluted by robotics, energy, and medicine content.

**Bluesky / Reddit** — Placeholders exist in feeds.yaml. Semiconductor Twitter
migration to Bluesky is incomplete; signal-to-noise is currently poor.
Re-evaluate after 30 days of production data.

---

## Supply Chain Inference: Why Three Rules Are Enough for V1

The three inference rules in `inference_rules.yaml` were chosen to cover the most
common supply chain pattern without over-specifying:

```
fab_supplies_designer:   Fab MANUFACTURES Chip + Company DESIGNS Chip → Fab SUPPLIES Company
fab_manufactures_via_process: Chip USES_PROCESS Node + Fab FABRICATES Node → Fab MANUFACTURES Chip
supply_chain_dependency: transitive SUPPLIES chain → DEPENDS_ON (2-hop)
```

Rule 1 is the primary business signal: TSMC supplies NVIDIA because TSMC makes the
H100 and NVIDIA designed it. This relationship is never explicitly stated in most
articles — it's assumed background knowledge. The inference rule surfaces it explicitly.

Rule 2 recovers manufacturing facts when the fab is mentioned only in the context of
the process node, not the chip directly. Common pattern in technical articles.

Rule 3 creates dependency edges that power the "supply chain resilience" topic cluster.
NVIDIA DEPENDS_ON TSMC becomes visible through the chain.

More rules can be added as the domain matures, but starting sparse avoids false
inference explosions in the first weeks of operation.

---

## Expected Entity Distribution at Steady State

Based on the 8 feeds and domain coverage, approximate entity distribution after
30 days of production (illustrative, not measured):

| Type | Expected share | Primary sources |
|------|---------------|-----------------|
| Company | 20–25% | All feeds |
| Chip | 15–20% | Chips and Cheese, Tom's Hardware, SemiAnalysis |
| Person | 10–15% | SemiAnalysis, The Chip Letter (named analysts/CEOs) |
| ProcessNode | 8–12% | SemiAnalysis, The Chip Letter, Semiconductor Engineering |
| Architecture | 8–10% | Chips and Cheese, SemiAnalysis |
| Packaging | 5–8% | SemiAnalysis, Semiconductor Engineering |
| Fab | 5–8% | All feeds |
| Policy | 3–5% | EE Times, The Register |
| Other types | remainder | — |

Low Person share (vs film's 39%) is a positive indicator: the domain is entity-dense
in the *things* (chips, nodes, fabs) rather than the *people*, which means corroboration
accumulates on durable technical entities rather than on human names that change roles.

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-01 | Selected semiconductors as experiment domain | Best shape fit after evaluating 5 candidates |
| 2026-04-01 | Set `max_age_days: 540` | Process node storylines run 18 months; shorter window loses historical corroboration |
| 2026-04-01 | Disabled `entity_types_to_disambiguate: []` (all types) | Same as film — nano is cheap enough, and ProcessNode variant merging is critical |
| 2026-04-01 | 8 feeds, not 12–15 | Source quality over volume; technical feeds produce more relations/doc than general tech |
| 2026-04-01 | 3 inference rules only | Start sparse; avoid false inference explosion in first 30 days |
| 2026-04-02 | Experiment start delayed | Resolve bug (O(n²) DB queries) must be fixed on server before semiconductors launches |
