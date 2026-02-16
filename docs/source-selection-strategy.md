# Source Selection Strategy

## The Curation Problem

Source selection for trend detection has an irreducible human judgment component.
No algorithm picks sources as well as someone who is immersed in the space. The
initial feed list reflects deliberate structural diversity — academic research
(arXiv), open-source ecosystem (Hugging Face), industry announcements (OpenAI) —
not random coverage.

This document captures the reasoning behind our source selection approach, the
trade-offs we've considered, and the strategy for evolving the source list over
time.

---

## Design Principles

### 1. Prefer primary sources over aggregators

General-purpose tech newsletters (e.g., TLDR, Sherwood's Snacks, Morning Brew)
are **digest/curation layers**. Their AI coverage typically summarizes
announcements from the labs and papers that gained social traction. By the time
something appears in a general newsletter, it is usually 1-3 days behind the
primary source.

For trend detection, these are **lagging indicators, not leading ones**. They are
also **token-inefficient** for extraction: a single newsletter covering 8 topics
shallowly yields worse entity/relation extraction than 8 dedicated sources
covering those topics deeply.

**Exception:** General outlets could serve as a "mainstream penetration" signal —
when a story crosses from insider to mainstream awareness. This is a V2 feature
requiring explicit echo-detection logic, not simple ingestion.

### 2. Secondary sources are essential for entity overlap

**Update (Feb 2026):** While primary sources remain the foundation, operating
experience shows that 7 Tier 1 sources producing ~25 docs/day yields
insufficient entity overlap for meaningful trend detection. Entities need to
appear in **multiple independent documents** for velocity signals to work.

Secondary sources (TechCrunch, VentureBeat, Ars Technica, etc.) naturally
create this overlap by re-reporting the same entities from primary announcements.
A TechCrunch article about an OpenAI release creates a second mention of the
same entities — which is exactly what drives velocity scoring.

**Key insight:** secondary sources are lagging for *discovery* but essential for
*corroboration*. The tier/signal metadata in `feeds.yaml` lets us distinguish
between "first seen in a primary source" vs "confirmed across secondary sources"
without conflating the two.

### 3. Structural diversity over volume

A good source list covers distinct **vantage points**, not just distinct topics:

| Vantage Point | Source Examples | Signal Type |
|---|---|---|
| Academic research | arXiv | New methods, benchmarks, datasets |
| Open-source ecosystem | Hugging Face | Model releases, community momentum |
| Major labs (industry) | OpenAI, Anthropic, Google AI | Product launches, partnerships, policy |
| Journalism | MIT Technology Review | Policy, societal impact, cross-domain |
| Technical analysis | The Gradient, Interconnects | Deep dives bridging academia and industry |
| Tech press (secondary) | TechCrunch, VentureBeat, Ars Technica | Entity overlap, deployment coverage |
| Practitioner blogs | Simon Willison | Early adoption signals, tool evaluation |

Each vantage point catches signals the others miss. Adding a second journalism
source adds less value than filling a missing vantage point.

### 4. The "small columnist" problem

The most valuable early signal often comes from a source nobody is watching yet —
the researcher, blogger, or small publication doing original work before it gets
mainstream attention. This is the hardest source selection problem.

**We cannot solve this algorithmically in V1.** But we can make the graph
*assist* human curation:

- Entities that appear via extraction from Tier 1 sources — a `Person` or `Org`
  with rising `mention_count_7d` — but for which we have no primary source, are
  candidates for promotion.
- A periodic review of "high-mention, no-primary-source" entities gives the human
  curator a focused list to investigate.
- The human decides whether to add a feed. The graph focuses attention; it does
  not automate judgment.

---

## Tier Model

### Source quality metadata

Each feed in `feeds.yaml` carries two metadata fields:

- **`tier`** (1, 2, or 3): How original is the content?
- **`signal`** (primary, commentary, echo, community): What kind of signal does
  it provide?

These are tracked in `health_report.py` output so we can measure per-tier
contribution to entity overlap and graph density.

### Tier 1 — Primary/Original Sources (current)

Hand-picked, high signal-to-noise sources ingested daily with full extraction.
These are the first-mover sources: they publish original content, not re-reports.

| Source | Signal | Volume | Limit |
|---|---|---|---|
| arXiv CS.AI | primary | High (~50-100/day) | 20/run |
| Hugging Face Blog | primary | Low (few/week) | Unlimited |
| OpenAI Blog | primary | Low (few/week) | Unlimited |
| Anthropic Blog | primary | Low (few/week) | Unlimited |
| Google AI Blog | primary | Low-medium | Unlimited |
| MIT Technology Review | commentary | Medium | Unlimited |
| The Gradient | commentary | Low (few/month) | Unlimited |

### Tier 2 — Secondary Sources (expanding)

Secondary sources that re-report, analyze, or contextualize primary source
content. Essential for **entity overlap** — the same entities appearing across
multiple documents is what enables velocity scoring.

| Source | Signal | Why |
|---|---|---|
| TechCrunch AI | echo | High-volume; re-reports with enterprise context |
| VentureBeat AI | echo | Enterprise/funding angle; deployment coverage |
| Ars Technica AI | echo | Technical detail; slightly less lag than mainstream |
| The Verge AI | echo | Consumer/product angle; deployment announcements |
| Simon Willison | community | Practitioner blog; early adoption signal |
| Interconnects (Nathan Lambert) | commentary | RLHF/alignment expert; research-practice bridge |

**Rollout plan:** Enable Tier 2 sources incrementally (2-3 at a time), monitor
entity overlap rate in `health_report.py` to confirm they're adding signal not
just volume. If overlap rate doesn't improve after adding a source, reconsider.

### Tier 2 — Entity Watchlist (planned)

Graph-derived list of entities with rising mentions but no primary source in
Tier 1. Reviewed periodically by a human curator who decides whether to add a
new Tier 1 feed.

Implementation: a query against the graph DB that surfaces entities where
`mention_count_7d` is rising but `doc_id` sources are all indirect (mentions from
other articles, not the entity's own publications).

### Tier 3 — Mainstream Echo (future/V2)

A small set of general-audience tech outlets used **only** to measure when AI
stories cross into mainstream awareness. Not used for entity extraction; only for
"echo delay" scoring. Candidates: TLDR, Sherwood's Snacks.

---

## High-Volume Source Management

Some sources publish far more than can be cost-effectively extracted in full.
arXiv CS.AI alone produces 50-100 papers per day. Ingesting everything would
drown out other sources and consume disproportionate extraction tokens.

### Solution: Per-feed limits (V1)

`limit` in feeds.yaml caps items per ingestion run. Simple, deterministic, and
keeps any single source proportional. arXiv is currently set to 20/run.

### Solution: Two-pass triage (V2)

The fundamental tension: you don't know if a document is worth the extraction
tokens until you've read it, but reading *is* the cost. (The Heisenberg problem
of NLP.)

Two-pass triage resolves this for any source that provides a **cheap preview**:

| Source Type | Cheap Preview | Full Document |
|---|---|---|
| arXiv | Title + abstract (in RSS XML) | Full paper PDF |
| News aggregators | Headline + lead paragraph | Full article |
| GitHub releases | Release title + notes | Full repo/docs |
| Patent feeds | Title + abstract | Full filing |

**Phase 1 (cheap):** Extract entities from the preview only (~200-500 tokens).
Score against the existing graph — does this mention known entities? Does it
introduce novel ones?

**Phase 2 (selective):** Fetch and extract the full document only for items that
scored above a threshold in Phase 1. This concentrates token spend on documents
most likely to enrich the graph.

---

## Token Cost Considerations

LLM token cost is determined by **cleaned text length**, not by how the URL was
discovered. RSS vs. non-RSS vs. API — the ingestion method is irrelevant to
extraction cost.

| Source Type | Typical Cleaned Text | Relative Token Cost |
|---|---|---|
| Blog post (lab blogs) | 1,000-3,000 words | Low-medium |
| arXiv abstract only | 200-500 words | Very low |
| arXiv full paper | 5,000-15,000 words | High |
| News article | 500-1,500 words | Low |
| Multi-topic newsletter | 2,000-5,000 words | Medium, but low yield per entity |

The cost-per-useful-extraction is worst for multi-topic newsletters (many topics
covered shallowly) and best for focused blog posts or abstracts (one topic
covered with clear entity relationships).

---

## Following References: Why Not (Yet)

It is tempting to spider outward from extracted citations — follow the references,
discover hidden sources. The risks outweigh the benefits for V1:

- **Resource cost scales multiplicatively.** 10 sources citing 5 references each
  = 50 at depth 2, 250 at depth 3. Most will be noise.
- **Amplification bias.** Auto-following citations biases toward whatever current
  sources already discuss. It amplifies existing clusters rather than discovering
  orthogonal signals.
- **Quality degradation.** Hand-picked sources have known editorial standards. A
  reference three hops out could be a press release, a LinkedIn post, or a dead
  link.
- **The "small columnist" wouldn't appear.** The most valuable undiscovered source
  is doing original work nobody else cites yet. Citation-following is structurally
  unable to find them.

The entity watchlist (Tier 2) is a better mechanism: it surfaces *who* is being
talked about, and the human decides *whether* to follow that thread.

---

## Monitoring Source Effectiveness

Use `make health-report` to track whether sources are contributing to critical
mass. Key metrics to watch per source:

| Metric | What it tells you |
|---|---|
| Docs/day | Is the feed producing content? |
| Relations/doc | Is the content entity-rich enough to extract? |
| Entity overlap contribution | Does this source mention entities also seen elsewhere? |
| Last published date | Is the feed stale? |

If a source produces many docs but low relations/doc, it may be too shallow
for extraction. If it has high relations/doc but zero entity overlap with other
sources, it's covering a unique niche (valuable) or an irrelevant one (drop it).

---

## Evolution Strategy

### Short-term (current)
- All 7 Tier 1 feeds enabled
- Apply per-feed limit to arXiv (20/run)
- Enable 2-3 Tier 2 sources (start with TechCrunch AI, Ars Technica)
- Monitor entity overlap rate via `make health-report`
- Extract the ingestion backlog to build initial graph density

### Medium-term (V1.5)
- Enable remaining Tier 2 sources based on overlap contribution
- Implement entity watchlist query
- Add 1-2 policy/regulatory feeds (NIST, EU AI Act)
- Consider GitHub Trending (ML) for code-level adoption signal

### Long-term (V2)
- Two-pass triage for high-volume sources
- Mainstream echo scoring (Tier 3)
- Automated source quality scoring based on extraction yield
- Automated watchlist surfacing in the Cytoscape UI
