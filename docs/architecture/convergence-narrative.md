# ADR: Convergence of Four Vectors — March 2026

**Status:** Active — living document, updated as vectors advance
**Date:** 2026-03-04 (last updated 2026-03-14)
**Context:** Five workstreams that were planned independently are converging on the same ~2-week window (mid-to-late March 2026). Each is straightforward alone; the risk is in their intersection. This document tracks how they weave together so that any session — human or AI — can pick up the thread.

---

## The Vectors

### V1 — User-Facing Insights (the "So What" layer)

**Trigger:** After ~5 days of real pipeline data (early March 2026), trend scores
worked mechanically but felt unactionable. A velocity of 0.73 doesn't tell a reader
*what happened* or *why it matters*. The observation: we have signals, but no
articulation.

**Design response:** [docs/research/trend-insights.md](../research/trend-insights.md)
— an "insight articulation layer" that transforms raw scores into structured
artifacts (title, category, evidence, "so what").

**Where it lands in the plan:**
[docs/project-plan.md](../project-plan.md) Backend Track items B.8–B.11,
feeding into Sprint 7's "What's Hot" UI ([docs/ux/delight-backlog.md](../ux/delight-backlog.md) §DL-1).

**Current state of code:** `src/trend/__init__.py` computes velocity, novelty,
and bridge scores. No insight generation, no `velocity_delta`, no templates yet.
Sprint 7.3 (`whats-hot.js`) is designed to accept either raw scores or insight
objects — start simple, upgrade in place.

### V2 — Supplementary Data Sources

**Trigger:** The initial 14-feed RSS set ([config/feeds.yaml](../../config/feeds.yaml))
covers the core AI landscape, but the source-selection strategy
([docs/source-selection-strategy.md](../source-selection-strategy.md)) already
identifies gaps: GitHub Trending (code-level adoption signal), policy/regulatory
feeds (NIST, EU AI Act), patent databases, and academic APIs (OpenAlex).

**Design response:** The tier model (primary → secondary → echo) is documented.
The entity-watchlist concept (surface entities with rising mentions but no owned
primary source) exists in strategy but not in code.

**Where it converges:** Every new source type that isn't RSS/Atom needs a different
fetcher. Today `src/ingest/rss.py` is a monolith with no plugin interface. Adding
GitHub, web scraping, or API-based sources requires the connector pattern from V4.

### V3 — Deterministic vs LLM Cost Spectrum

**Trigger:** Running Claude Sonnet on every article costs ~$25/month at 20 docs/day.
The [quality gate analysis](../research/extract-quality-analysis.md) showed that
CPU-only checks (evidence fidelity, orphan endpoints, zero-value) catch the
majority of extraction failures *without spending a single token*. Meanwhile,
[llm-selection.md](../llm-selection.md) documents that Haiku 3.5 fails at 41%
schema pass rate because it invents relation types — but a normalization layer
could rescue it.

**The sweet spot hypothesis:** There is a point along the deterministic↔LLM
spectrum where a 3.5-class model (GPT-4.1 nano, Gemini 2.5 Flash, future
Claude Haiku) — paired with strict schema enforcement and CPU quality gates —
delivers "uniquely special results" at minimal API cost. The escalation
architecture (`src/extract/__init__.py`, `ESCALATION_THRESHOLD = 0.6`) is built
for exactly this: cheap model first → CPU gates → score → escalate to Sonnet only
when needed. Estimated cost drop: ~$25 → ~$8/month if 70% of articles pass nano.

**Reality check (2026-02-25 data):** The Feb 22–25 measurement period showed
**80% escalation rate** — the cheap model (gpt-5-nano) failed quality gates on
4 out of 5 documents. Dominant failure: orphan endpoints (relation target doesn't
match entity name). Prompt tuning was applied Feb 25 (3 lightweight additions to
Critical Rules). The 70%-pass / $8-month target is aspirational; actual calibration
is ongoing. If escalation stays above ~50%, the fallback is to run Sonnet directly
(~$25/month) — the cost delta is small enough that reliability may outweigh savings.
See [ext4 analysis](../fix-details/ext4-cheap-model-escalation-analysis.md).

**Where it converges:** This directly affects V1 (trend-insights uses a
deterministic-first philosophy — templates before LLM) and V4 (each domain
may have a different cost profile and sweet spot). The shadow mode comparison
infrastructure (`compare_extractions()`, `compute_entity_overlap()`) is already
implemented but has no automated cost reporting yet.

### V4 — Plugin Architecture (Domain Modularization)

**Trigger:** [docs/architecture/domain-separation.md](domain-separation.md)
defines the boundary between framework and domain config.
[multi-domain-futures.md](multi-domain-futures.md) sketches four candidate
domains (Biotech, Cybersecurity, Climate, Geopolitics). But today the separation
is convention-based (framework in `src/extract/__init__.py`, domain content in
`src/extract/prompts.py`) with no runtime enforcement.

**Design response:** Sprint 6 in the [project plan](../project-plan.md) created
`domains/ai/domain.yaml` — entity types, relation taxonomy, ID prefixes, quality
thresholds, prompt paths — and parameterized all framework modules to load from
that profile instead of hardcoding. The approach is deliberately minimal: no
abstract base classes, no plugin registry. A domain is a directory with a known
file layout; adding one means adding a directory.

**Current state (2026-03-14):** Sprint 6 + 6B completed 2026-03-07. Two domains
operational (AI, biosafety). Grep-audit test enforces domain-agnostic framework.
Domain switcher UI (`web/js/domain-switcher.js`) with `KNOWN_DOMAINS` registry
deployed. Biosafety stabilization required ~4 days of follow-up fixes for extraction
prompts, feed reliability, and mobile routing (see [fix-details/README.md](../fix-details/README.md)).

### V4.5 — Source Connectors (the `*.py` question)

**Trigger:** V2 needs non-RSS sources. V4 needs domain-specific source lists.
Today the `type` field in `FeedConfig` accepts `'rss'` or `'atom'` but the
ingestion layer doesn't dispatch on it — it's decorative metadata.

**Design response (implicit, not yet documented):** The natural pattern is:
`type: github_api` in a feed config dispatches to `src/ingest/github.py`;
`type: web_scrape` dispatches to `src/ingest/scraper.py`. Each connector is
a `*.py` file with a known entry point. No base class needed — just a function
signature convention (like `prompts.py` today). The `domains/ai/feeds.yaml`
from V4 would reference connector types; the framework resolves them.

---

## The Convergence Map

These vectors are **not independent**. Here is where they touch:

```
                        V3: Cost Spectrum
                    (deterministic ↔ LLM sweet spot)
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
     V1: Insights      V4: Plugin Arch    V4.5: Connectors
     (templates are     (each domain has   (each source type
      deterministic-    its own cost       needs its own
      first by design)  profile)           fetcher *.py)
              │               │               │
              │               ▼               │
              │        domains/ai/            │
              │          domain.yaml          │
              │            │    │             │
              │            │    └─────────────┘
              │            │     feeds.yaml references
              │            │     connector types
              ▼            ▼
         Sprint 7      Sprint 6
        "What's Hot"   Domain Modularization
              │            │
              └─────┬──────┘
                    │
                    ▼
          B.8–B.11 (insight artifacts)
          slot into whats-hot.js
          using domain-aware templates
```

### Critical intersections

| Intersection | What could go wrong | Mitigation |
|---|---|---|
| V1 × V3 | Insight templates assume a scoring model that changes when the cost tier changes | Templates reference signal names (`velocity`, `novelty`), not model names. Scoring formula is framework-level, not domain-level. |
| V1 × V4 | Insight categories are AI-specific (e.g., "Adoption Wave") but live in framework code | B.8 template spec must land in `domains/ai/`, not `src/trend/`. Sprint 6 must happen before or concurrently with B.9. |
| V2 × V4.5 | Adding a GitHub connector before the connector convention exists creates tech debt | Document the function signature convention in Sprint 6. Any connector added before Sprint 6 should follow the convention prophylactically. |
| V3 × V4 | Different domains may need different escalation thresholds | `ESCALATION_THRESHOLD` must move from hardcoded 0.6 to `domain.yaml`. Already identified in Sprint 6 item 6.6. |
| V4 × V4.5 | `feeds.yaml` moves to `domains/ai/feeds.yaml` but connector dispatch doesn't exist yet | Sprint 6 moves the file; connector dispatch is a separate PR. The `type` field is carried along harmlessly until dispatch is wired. |

---

## Sequencing (what depends on what)

```
DONE (as of 2026-03-14)
  ├── Sprint 6: domain.yaml schema, domains/ai/, framework parameterization ✓
  ├── Sprint 6B: biosafety domain + stabilization ✓
  ├── Domain switcher UI + ontology reference page ✓
  └── Pipeline dashboard ✓

NOW (unblocked, mid-March)
  ├── B.8: Write insight template spec (pure doc, no code dependency)
  ├── B.9: generate_insights.py (needs B.8 + data — ≥14 days data now available)
  └── Sprint 7: What's Hot UI shell (can use raw scores, doesn't need B.9)

~LATE MARCH (≥30 days data — reached ~March 14)
  ├── B.10: Backtest insight accuracy
  ├── B.11: Insight dedup + storage
  ├── Shadow mode evaluation: nano model vs Sonnet on real corpus
  ├── Sprint 7.3 upgrade: swap raw scores → insight artifacts
  └── V3 cost calibration: resolve 80% escalation rate or drop cheap-first

POST-V1 (framework is domain-parameterized ✓)
  ├── V4.5: Connector convention + first non-RSS source
  └── V2: Entity watchlist → curator-driven source expansion
```

---

## Decision Log

| Date | Decision | Rationale | Refs |
|---|---|---|---|
| 2026-03-03 | Deterministic-first for insight generation | Avoid LLM cost for something templates can handle; measure whether readers prefer LLM versions before paying for them | [trend-insights.md](../research/trend-insights.md) §4 |
| 2026-03-04 | Sprint 7.3 accepts raw scores OR insight objects | Decouples UI ship date from insight generation readiness; upgrade in place | [project-plan.md](../project-plan.md) Sprint 7 |
| 2026-03-04 | No abstract base classes for plugin/connector arch | Directory convention + function signatures are sufficient for V1; avoid premature abstraction | [domain-separation.md](domain-separation.md), [project-plan.md](../project-plan.md) Sprint 6 |
| 2026-03-04 | This convergence narrative created as standalone ADR | Source docs stay stable; narrative links out instead of modifying them; new sessions can reconstruct the "why" from one place | (this document) |
| 2026-03-07 | Sprint 6 + 6B delivered: domain modularization + biosafety proof-of-concept | V4 prerequisites met; framework is domain-agnostic with grep-audit enforcement | [project-plan.md](../project-plan.md) |
| 2026-03-09 | Biosafety stabilization: prompt fixes, feed repairs, mobile routing | First non-AI domain required ~4 days of follow-up fixes; template scaffolding needs structural pre-population | [fix-details/README.md](../fix-details/README.md) |
| 2026-03-13 | Domain switcher UI + ontology reference page shipped | `KNOWN_DOMAINS` registry in `domain-switcher.js` is now single source of truth for domain enumeration; ontology page visualizes domain taxonomy | [project-plan.md](../project-plan.md) |

---

## How to Use This Document

**If you are a new session** picking up this project: read this document first
for the big picture, then follow the links to source docs for detail. The
[project-plan.md](../project-plan.md) has the task-level breakdown; this document
explains *why those tasks exist and how they relate*.

**If you are advancing one of these vectors:** check the convergence map and
critical intersections above before making design decisions. The risk is not
in any single vector — it's in accidentally breaking an assumption that another
vector depends on.

**When updating:** Add a row to the Decision Log. Keep the convergence map
current. This document is the thread; the source docs are the fabric.
