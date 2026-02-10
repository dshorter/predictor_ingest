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

### 2. Structural diversity over volume

A good source list covers distinct **vantage points**, not just distinct topics:

| Vantage Point | Source Examples | Signal Type |
|---|---|---|
| Academic research | arXiv | New methods, benchmarks, datasets |
| Open-source ecosystem | Hugging Face | Model releases, community momentum |
| Major labs (industry) | OpenAI, Anthropic, Google AI | Product launches, partnerships, policy |
| Journalism | MIT Technology Review | Policy, societal impact, cross-domain |
| Technical analysis | The Gradient | Deep dives bridging academia and industry |

Each vantage point catches signals the others miss. Adding a second journalism
source adds less value than filling a missing vantage point.

### 3. The "small columnist" problem

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

### Tier 1 — Curated Feeds (current)

Hand-picked, high signal-to-noise sources ingested daily with full extraction.

| Source | Vantage Point | Volume | Limit |
|---|---|---|---|
| arXiv CS.AI | Academic | High (~50-100/day) | 20/run |
| Hugging Face Blog | Open-source | Low (few/week) | Unlimited |
| OpenAI Blog | Major lab | Low (few/week) | Unlimited |
| Anthropic Blog | Major lab | Low (few/week) | Unlimited |
| Google AI Blog | Major lab | Low-medium | Unlimited |
| MIT Technology Review | Journalism | Medium | Unlimited |
| The Gradient | Technical analysis | Low (few/month) | Unlimited |

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
"echo delay" scoring. Candidates: TLDR, Sherwood's Snacks, Ars Technica.

---

## The arXiv Volume Problem

arXiv CS.AI publishes 50-100 papers per day. Ingesting all of them would drown
out the other sources and consume disproportionate extraction tokens.

### Solution: Per-feed limits + two-pass triage

1. **Per-feed limit** (`limit: 20` in feeds.yaml) caps items per ingestion run.
   This is simple, deterministic, and keeps arXiv proportional.

2. **Two-pass triage** (future enhancement): arXiv RSS includes title + abstract
   in the feed XML itself. Phase 1 extracts entities from the abstract only
   (cheap — ~200-500 tokens). Phase 2 fetches the full paper only for items
   whose abstract mentions entities already in the graph or scores high on
   novelty. This is the practical answer to the "Heisenberg problem" — you don't
   know if a paper is worth the tokens until you read it, but the abstract gives
   you a low-cost observation before committing to the full measurement.

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

Non-RSS sources require custom scraping or API integration instead of
`feedparser`, which adds code complexity but negligible compute cost on a
self-hosted server.

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

## Evolution Strategy

### Short-term (V1)
- Enable all 7 Tier 1 feeds
- Apply per-feed limit to arXiv (20/run)
- Manually review graph entity tables periodically for watchlist candidates

### Medium-term (V1.5)
- Implement entity watchlist query (Tier 2)
- Add two-pass triage for arXiv (abstract-first extraction)
- Consider 1-2 additional vantage points if gaps emerge (e.g., government/policy:
  NIST, EU AI Act sources)

### Long-term (V2)
- Mainstream echo scoring (Tier 3)
- Source quality scoring based on extraction yield (entities per token)
- Automated watchlist surfacing in the Cytoscape UI
