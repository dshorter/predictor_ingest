# ADR-005: Regional Lens — Geographic Focus via Export Tagging, Not Scoring

**Status:** Accepted
**Date:** 2026-03-17
**Deciders:** dshorter, Claude (Opus 4.6)
**Sprint:** 7 (Regional Lens + Chatter Sources)

## Context

The film domain was launched 2026-03-17 tracking broad independent cinema.
Initial pipeline run (174 docs, 679 entities) showed 13% entity overlap — too
diffuse for strong trend detection. Discussion explored narrowing focus to the
Atlanta film scene, then expanded to the Southeast US production corridor
(Georgia, Louisiana, North Carolina, Tennessee, South Carolina) for better
source volume and richer cross-state signals (e.g., productions moving between
states based on tax incentive changes).

Key question: **Where in the pipeline should regional focus be enforced?**

## Decision

Regional focus is implemented as a **client-side lens** powered by
**export-time region tagging**, not as a scoring signal in article selection.

### What we build (Sprint 7B + 7C):

1. **Region lookup table** in `domains/film/domain.yaml` — maps Location entity
   names to region slugs (e.g., `Atlanta → southeast`, `New Orleans → southeast`)

2. **Export-time 2-hop propagation** in `src/graph/export.py` — after building
   the graph, find all Location nodes, look up their regions, then walk 2 hops
   outward tagging connected nodes with `region[]` arrays. A Production node
   connected via `SHOOTS_AT → Location:Atlanta` gets `region: ["southeast"]`.
   A Person who `DIRECTS → Production` inherits the tag.

3. **Lens dropdown** in the web UI toolbar — reads lens configuration from
   domain JSON (`web/data/domains/film.json`). Toggles `.region-dimmed` CSS
   class on nodes without matching region tags. Zero server calls.

### What we do NOT build:

- **No additive scoring signal** for regional relevance in `src/doc_select/`
- **No LLM-based relevance classification** at selection time
- **No subtractive penalty** for non-regional articles

## Alternatives Considered

### A. Additive scoring boost (rejected)

Add a `regional` signal (8% weight) to article selection scoring:
- 1.0 for local sources, 0.8 for national + keyword match, 0.5 baseline.

**Why rejected:**
- Redundant with feed selection — adding regional RSS feeds already ensures
  regional content flows in. Boosting on top double-rewards.
- Redundant with client lens — if the graph is already skewed regional by
  scoring, the lens provides diminishing returns.
- Violates domain-neutral scoring — the scoring layer should pick the best
  articles regardless of geography. Regional focus is a user preference
  (demand-side), not a pipeline constraint (supply-side).

### B. Dedicated Atlanta subdomain (rejected)

Create `domains/atl-film/` with only Atlanta-focused feeds and entity types.

**Why rejected:**
- Too few Atlanta-specific sources (~3-6 articles/day) to sustain the pipeline's
  10-20 doc/day design target.
- Loses national context — a Deadline article about Marvel moving to Trilith
  wouldn't be captured by Atlanta-only feeds.
- Duplicates domain config unnecessarily.

### C. LLM-based relevance scoring (rejected)

Use nano to classify each article's regional relevance before selection.

**Why rejected:**
- Adds LLM cost to a currently zero-cost CPU pipeline stage.
- Geographic references are explicit in text — keyword matching is sufficient
  and deterministic.
- Over-engineering for the signal quality available.

## Consequences

### Positive
- **Scoring stays domain-neutral** — no geographic bias baked into article
  selection. Preserves framework's domain-agnostic design (Sprint 6 principle).
- **User controls focus** — lens is opt-in at browse time. Full graph by default,
  regional focus on demand. Non-destructive.
- **Nuance handled at export** — 2-hop propagation captures indirect relationships
  (person → production → location) that keyword matching would miss.
- **Reusable across domains** — biosafety could have "US" vs "International" lenses.
  AI domain could have "Open Source" vs "Proprietary" lenses. The mechanism is
  generic.
- **Zero runtime cost** — tagging is CPU at export time; lens is CSS at browse time.

### Negative
- **Export JSON grows** — each node gains a `region[]` array. Marginal size increase.
- **Region lookup requires maintenance** — new filming locations need manual addition
  to the lookup table in domain.yaml.
- **2-hop propagation may over-tag** — a well-connected person who worked on one
  Southeast production could get tagged even if most of their work is elsewhere.
  Acceptable for V1; can add degree-weighted propagation later.

## Related
- [ADR-006](adr-006-chatter-sources.md) — Chatter source ingestion (same sprint)
- [domain-separation.md](domain-separation.md) — Framework vs domain boundary rules
- [date-filtering.md](date-filtering.md) — Precedent for "filter at query time, not ingest time"
