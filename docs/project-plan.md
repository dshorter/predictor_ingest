# Unified Project Plan

All backlog items across all docs, ordered by **codebase stability** — safest
changes first, riskiest last. Each sprint is ~2 hours of focused work (one day
at the current pace).

**Ordering principles:**
1. Fix existing wiring before adding features (dead code is a liability)
2. CSS-only changes before JS logic changes (lower blast radius)
3. Contained changes before cross-cutting ones
4. Honor dependency chains (downstream items wait for upstream)
5. Desktop-first — all UI work targets desktop; mobile adapts after

**Source docs:** Items are pulled from [gap-remediation-plan](ux/gap-remediation-plan.md),
[polish-strategy](ux/polish-strategy.md), [delight-backlog](ux/delight-backlog.md),
and [backlog](backlog.md). Each item cites its source.

**Model assignment:** Items marked **[Opus]** are complex enough to benefit from
Opus 4.6. Items marked **[Sonnet]** are straightforward and can be delegated to
Sonnet 4.6 using the existing spec docs as context. Items marked **[Manual]**
require human input or are data-dependent.

---

## Sprint 1 — Dead Code Wiring (Day 1) ✓ DONE

Fix features that are built but never activated. Zero new functionality — just
connecting wires that already exist. Lowest risk, highest embarrassment-to-fix ratio.

| # | Item | Source | Lines | Model |
|---|------|--------|-------|-------|
| 1.1 | Apply `.new` class to recent nodes | gap-remediation §1.1 | ~10 | [Sonnet] |
| 1.2 | Wire `dbltap` handlers (node → zoom neighborhood, bg → fit) | gap-remediation §1.2 | ~15 | [Sonnet] |
| 1.3 | Apply `prefers-reduced-motion` to layout/panels/tooltips | gap-remediation §1.3 | ~30 | [Sonnet] |
| 1.4 | Document hypothesis-unchecked-by-default decision | gap-remediation §2.2 | ~5 | [Sonnet] |

**Risk:** Near-zero. All code paths already exist.
**Stability gate:** Run desktop + mobile in browser, confirm no regressions.
**Completed:** 2026-02-27

---

## Sprint 2 — Aesthetic Identity: CSS Foundation (Days 2–3) ✓ DONE

CSS-only changes that establish visual identity. No JS logic changes. If anything
breaks, it's purely visual and immediately reversible.

| # | Item | Source | Lines | Model |
|---|------|--------|-------|-------|
| 2.1 | Typography upgrade (add display font, `--font-display` token) | polish-strategy §A0 | ~20 CSS + 1 HTML | [Sonnet] |
| 2.2 | App title presence (display font, letter-spacing, gradient) | polish-strategy §A0 | ~10 CSS | [Sonnet] |
| 2.3 | Toolbar breathing room (dividers, group spacing, background tint) | polish-strategy §A0 | ~30 CSS | [Sonnet] |
| 2.4 | Filter panel color dots + type grouping | polish-strategy §A0 | ~40 CSS+JS | [Sonnet] |
| 2.5 | Detail panel inline styles → CSS classes | polish-strategy §P2 | ~10 | [Sonnet] |

**Risk:** Low. CSS token system is well-established. Changes are additive.
**Stability gate:** Visual QA in light + dark mode, desktop + mobile.
**Completed:** 2026-02-28

---

## Sprint 3 — Toolbar Icons (Day 4) ✓ DONE

Replace Unicode glyphs with professional SVG icons. Natural to do right after
toolbar CSS changes settle.

| # | Item | Source | Lines | Model |
|---|------|--------|-------|-------|
| 3.1 | Download/inline ~10 Lucide SVG icons | delight-backlog §DL-5 | ~50 HTML | [Sonnet] |
| 3.2 | Update desktop toolbar HTML to use SVG icons | delight-backlog §DL-5 | ~30 HTML | [Sonnet] |
| 3.3 | Update mobile toolbar HTML to match | delight-backlog §DL-5 | ~20 HTML | [Sonnet] |

**Risk:** Low. Purely presentational. No JS logic changes.
**Dependency:** Sprint 2 (toolbar CSS must be settled first).
**Completed:** 2026-03-01
**Notes:** Theme toggle (sun/moon) implemented as CSS-driven swap via `[data-theme]`
on `<html>` — no JS changes required. `#theme-icon` span kept hidden for JS
compatibility. CSS toggle rules added to `button.css`.

---

## Sprint 4 — Graph Canvas Polish (Day 5) ✓ DONE

Cytoscape `styles.js` changes. Contained to one file. Changes how the graph
*looks* but not how it *behaves*.

| # | Item | Source | Lines | Model |
|---|------|--------|-------|-------|
| 4.1 | Node depth/texture (thicker borders, underlay shadow, velocity halo) | polish-strategy §A1 | ~30 JS | [Sonnet] |
| 4.2 | Canvas dot-grid background | polish-strategy §A1 | ~6 CSS | [Sonnet] |
| 4.3 | Edge arrow refinement (confidence-scaled arrow size) | polish-strategy §A1 | ~15 JS | [Sonnet] |

**Risk:** Low. All changes are Cytoscape style properties, not event logic.
**Stability gate:** Load all 4 views, confirm rendering at various zoom levels.
**Completed:** 2026-03-01
**Notes:** `darkenColor()` helper added for 20%-darker type-colored borders. Edge
hover label (relation type, autorotate) implemented as part of 4.3. Arrow scale
is a function rather than a second selector.

---

## Sprint 5 — Interaction Polish (Days 6–7) ✓ DONE

JS behavior changes for smoother interactions. Moderate risk — touches event
handling and layout timing.

| # | Item | Source | Lines | Model |
|---|------|--------|-------|-------|
| 5.1 | View switch crossfade (opacity transition during load) | polish-strategy §P1 / delight §DL-7a | ~30 JS + CSS | [Sonnet] |
| 5.2 | Panel resize choreography (defer `cy.resize()` to `transitionend`) | polish-strategy §P1 / delight §DL-7b | ~15 JS | [Sonnet] |
| 5.3 | Search fly-to animation (`cy.animate` instead of `cy.fit`) | delight §DL-7c | ~10 JS | [Sonnet] |
| 5.4 | Contextual empty states (why-aware messages + reset button) | polish-strategy §P1 / delight §DL-4 | ~40 JS + HTML | [Sonnet] |
| 5.5 | Tooltip positioning (account for open panel widths) | polish-strategy §P2 | ~15 JS | [Sonnet] |
| 5.6 | Search result count overflow fix | polish-strategy §P2 | ~10 CSS+JS | [Sonnet] |

**Risk:** Moderate. Event timing changes can cause subtle bugs. Test thoroughly.
**Stability gate:** Rapid view switching, panel toggle + zoom, search edge cases.
**Completed:** 2026-03-04
**Notes:** 5.2 (panel resize choreography) superseded by PR #118 — panels now overlay
the graph instead of shrinking it, so `cy.resize()` is not needed. The `opacity`
transition for view-switch crossfade (5.1) is retained; position transitions were
removed as they are no longer applicable to the overlay model.

---

## Sprint 6 — Domain Modularization (Days 8–11)

Refactor the codebase so that all domain-specific content (entity types, relation
taxonomy, extraction prompts, quality thresholds, suppressed entities) lives in a
structured domain directory (`domains/ai/`), loaded by the framework at runtime via
a `domain.yaml` profile. No new functionality — just moving config out of code.

This is the "plugin contract" described in
[domain-separation.md](architecture/domain-separation.md) and
[multi-domain-futures.md](architecture/multi-domain-futures.md): a domain is a
directory with a known file layout; the framework reads it instead of hardcoding values.

**Approach:** Monorepo with plugin architecture (Option D). No libraries, no
abstract base classes — just a YAML profile, a directory convention, and framework
code that reads config instead of hardcoding values. Adding a future domain =
adding a directory.

| # | Item | What changes | Lines | Model |
|---|------|-------------|-------|-------|
| 6.1 | Define `domain.yaml` schema | Write JSON Schema for domain profile format: entity types, relation taxonomy, ID prefixes, base relation type, quality thresholds, suppressed entities, prompt paths | ~80 YAML/JSON | [Opus] |
| 6.2 | Create `domains/ai/domain.yaml` | Populate AI domain profile from current hardcoded values in `schemas/extraction.json`, `src/extract/__init__.py`, `src/extract/prompts.py` | ~120 YAML | [Opus] |
| 6.3 | Create `domains/ai/prompts/` | Move extraction prompts and suppressed entity list from `src/extract/prompts.py` into `domains/ai/prompts/`. Framework keeps prompt-building logic; domain provides vocabulary, examples, suppressed terms | ~200 move+refactor | [Opus] |
| 6.4 | Create `domains/ai/views.yaml` | Move `config/views.yaml` content to domain directory. Framework loads views from domain path | ~30 move | [Opus] |
| 6.5 | Create `domains/ai/feeds.yaml` | Move `config/feeds.yaml` to domain directory | ~10 move | [Opus] |
| 6.6 | Parameterize `src/extract/__init__.py` | Load `RELATION_NORMALIZATION`, `QUALITY_THRESHOLDS`, `GATE_THRESHOLDS` from domain profile instead of hardcoding. Remove AI-specific constants from framework code | ~80 refactor | [Opus] |
| 6.7 | Parameterize `src/trend/__init__.py` | Replace hardcoded `'MENTIONS'` with base relation type from domain profile (3 occurrences: lines ~45, ~172, ~184) | ~15 refactor | [Opus] |
| 6.8 | Parameterize `src/schema/__init__.py` | Generate extraction JSON Schema dynamically from domain profile's entity types and relation taxonomy, instead of loading a static `schemas/extraction.json` | ~60 refactor | [Opus] |
| 6.9 | Add `--domain` CLI flag to pipeline entry points | `run_pipeline.py`, `build_docpack.py`, `import_manual.py`, `export_graph.py` accept `--domain ai` (default). Framework resolves to `domains/ai/` and loads profile | ~40 refactor | [Opus] |
| 6.10 | Domain profile validation on load | Framework validates `domain.yaml` against the schema from 6.1 at startup. Fail fast with clear error if profile is invalid or missing required fields | ~30 | [Opus] |
| 6.11 | Grep-audit: no domain strings in framework | Run automated check that `src/trend/`, `src/resolve/`, `src/graph/`, `src/db/`, `src/schema/` contain zero references to AI-specific entity types, relation names, or source URLs. Add as a test | ~30 test | [Opus] |

**Risk:** Moderate. This is a refactoring sprint — behavior should be identical before
and after. But it touches many files and changes how config is loaded. Careful
diffing required.
**Why Opus for all of Sprint 6:** This is a single cohesive refactor where all 11
tasks are tightly coupled. The domain profile schema (6.1) dictates every downstream
task. Splitting across models risks inconsistency in how config is structured vs consumed.
**Stability gate:** Full test suite passes. Pipeline produces identical output for AI
domain before and after. `grep` audit (6.11) passes. Manual smoke test: ingest →
extract → export → verify graph JSON is unchanged.
**Standing rule for all subsequent sprints:** No sprint may introduce hardcoded
domain-specific strings into framework code. The grep-audit test (6.11) enforces this
in CI.
**Completed:** 2026-03-07
**Notes:** All 11 items delivered in a single session. Key implementation decisions:
- `domains/_template/` created as scaffolding for new domains.
- `PREDICTOR_DOMAIN` env var supported alongside `--domain` CLI flag.
- Makefile targets wired with `DOMAIN=` variable (e.g., `make ingest DOMAIN=biosafety`).
- Grep-audit test (`test_domain_isolation.py`) validates zero AI-specific strings in
  framework modules. All tests pass.

---

## Sprint 6B — First Non-AI Domain: Biosafety (Day 11, bonus)

Proof-of-concept for the domain plugin architecture: stand up a complete second domain
from scratch to validate that Sprint 6's modularization actually works end-to-end.

| # | Item | What was done | Model |
|---|------|--------------|-------|
| 6B.1 | `domains/biosafety/domain.yaml` | Full domain profile: 14 entity types (incl. `SelectAgent`, `Facility`, `Regulation`), 35 canonical relations, 70+ normalization mappings, tuned quality/trend weights, 30+ suppressed entities | [Opus] |
| 6B.2 | `domains/biosafety/feeds.yaml` | 13 RSS feeds across 3 tiers: Federal Register, CDC EID, WHO DON, mBio, PNAS Micro (primary); CIDRAP, JHU CHS, Bulletin of Atomic Scientists, NTI, GAO (secondary); STAT News, Science (echo) | [Opus] |
| 6B.3 | `domains/biosafety/prompts/` | System, user, and single-message extraction prompts tailored to biosafety entity types and regulatory vocabulary | [Opus] |
| 6B.4 | `domains/biosafety/views.yaml` | Four graph views adapted for biosafety: mentions, claims, regulatory, trending | [Opus] |
| 6B.5 | DB isolation | `--domain` flag routes to `data/db/{domain}.db`, so domains have fully separate databases | [Opus] |
| 6B.6 | Web client parameterization | `web/data/domains/{domain}.json` config files; `app.js` reads domain from URL param (`?domain=biosafety`); filter panel dynamically loads entity types from domain config | [Opus] |
| 6B.7 | Domain profile validation tests | `test_domain_profile.py` validates both `ai` and `biosafety` profiles against JSON Schema | [Opus] |

**Risk:** Low. All changes are additive — no existing AI domain behavior modified.
**Stability gate:** All existing tests pass. Domain profile validation passes for both
domains. Grep-audit confirms framework remains domain-agnostic.
**Completed:** 2026-03-07
**Notes:** First `make daily DOMAIN=biosafety` run is next step to validate feed
ingestion. Feed URLs need live testing — some institutional feeds (WHO, JHU CHS) may
have changed structure since last verified.

---

## Sprint 7 — Regional Lens + Chatter Sources (Days 12–15)

Three sub-features that extend the pipeline's reach and give users geographic
focus. Motivated by narrowing the film domain to the Southeast US production
scene. See [ADR-005](architecture/adr-005-regional-lens.md) and
[ADR-006](architecture/adr-006-chatter-sources.md) for decision rationale.

**Key design decision:** No additive scoring signal for regional relevance.
Regional content enters via feeds (supply-side); user controls focus via lens
(demand-side). Scoring layer stays domain-neutral. See ADR-005 §Alternatives.

| # | Item | What changes | Lines | Model |
|---|------|-------------|-------|-------|
| 7A.1 | Substack feeds for film domain | Add 3–5 Southeast film Substack RSS URLs to `feeds.yaml`. Zero code changes — already RSS-compatible | ~15 YAML | [Sonnet] |
| 7A.2 | Bluesky AT Protocol fetcher | New `src/ingest/bluesky.py`: subscribe to keyword-filtered firehose, normalize posts to document schema, store in DB | ~150 Python | [Opus] |
| 7A.3 | Reddit API fetcher | New `src/ingest/reddit.py`: fetch posts/comments from target subreddits via free API tier, normalize to document schema | ~120 Python | [Opus] |
| 7A.4 | Source type field in documents table | Add `source_type` column (`rss`, `bluesky`, `reddit`) to distinguish provenance. Migration script | ~30 Python+SQL | [Sonnet] |
| 7B.1 | Region lookup table in domain config | Add `regions:` section to `domains/film/domain.yaml` mapping Location entity names → region slugs (e.g., `Atlanta: southeast`, `New Orleans: southeast`) | ~30 YAML | [Sonnet] |
| 7B.2 | Export-time region tagging | In `src/graph/export.py`: after building graph, propagate region tags from Location nodes through 2 hops. Write `region[]` array onto each node's data | ~80 Python | [Opus] |
| 7C.1 | Lens dropdown UI | New toolbar dropdown reading lens config from domain JSON. Toggles `.region-dimmed` class on nodes without matching region tag | ~60 JS+CSS | [Opus] |
| 7C.2 | Lens config in domain web JSON | Add `lenses[]` to `web/data/domains/film.json` defining available region filters | ~15 JSON | [Sonnet] |

**Risk:** Moderate. New ingest source types (7A.2, 7A.3) are the riskiest — external
API integration with rate limits and schema mapping. Region tagging (7B) and lens UI
(7C) are low risk — deterministic graph traversal and CSS class toggling.
**Why Opus for 7A.2/3, 7B.2, 7C.1:** New integration code + cross-cutting export
changes need holistic design. Substack (7A.1) and config items are straightforward.
**Stability gate:** Existing RSS ingest unaffected. New source types produce valid
document records. Region tags appear in exported JSON. Lens UI dims/undims correctly.
Grep-audit still passes (no domain-specific strings in framework).
**Dependency:** Southeast feed URLs need web search validation (scheduled 2026-03-18).

---

## Sprint 8 — "What's Hot and WHY" Feature (Days 16–19)

**Updated 2026-03-21:** The LLM Leverage Features work (PR #186, #188) shipped
the entire backend for this sprint ahead of schedule. Velocity computation,
trend scoring, and LLM-generated narratives are live in `trending.json` today.
Sprint 8 is now **frontend-only** — build the UI that consumes data that already
exists. Risk drops from Moderate to Low.

| # | Item | Source | Lines | Model | Status |
|---|------|--------|-------|-------|--------|
| 8.1 | Velocity delta computation in export script | delight §DL-1 | ~60 Python | [Opus] | **DONE** (PR #186: `TrendScorer.compute_velocity()`) |
| 8.2 | Include velocity delta in graph JSON export | delight §DL-1 | ~20 Python | [Opus] | **DONE** (PR #186: `trending.json` has velocity, novelty, trend_score, mention_count_7d/30d) |
| 8.2b | LLM narrative generation ("WHY" context) | ADR-007 | ~340 Python | [Opus] | **DONE** (PR #186: `src/trend/narratives.py`, per-domain style prompts) |
| 8.3 | `whats-hot.js` — ranked list with narratives | delight §DL-1 | ~190 JS | [Opus] | **DONE** (PR #190: pure-function module + DOM wiring) |
| 8.4 | Toolbar button + keyboard shortcut (`h`) | delight §DL-1 | ~18 JS+HTML | [Opus] | **DONE** (PR #190: flame icon, `h` key, toolbar handler) |
| 8.5 | Fly-to-neighborhood on item click | delight §DL-1 | ~20 JS | [Opus] | **DONE** (PR #190: `flyToHotNode()` → select → zoom → detail) |
| 8.6 | Panel CSS for hot list drawer | delight §DL-1 | ~150 CSS | [Opus] | **DONE** (PR #190–#193: flame border, bounce animation, hover-expand, film badges) |

**Risk:** Low. Pure frontend work consuming stable backend data. If it breaks,
it only breaks the hot list. No backend changes needed.
**Why Opus:** New JS module + toolbar integration + fly-to animation. Needs
holistic understanding of the existing UI component pattern.
**Stability gate:** Verify hot list populates from real `trending.json` data
(including narratives), fly-to works, drawer opens/closes cleanly. Confirm
existing views are unaffected.
**Completed:** 2026-03-21
**Notes:** Delivered in a single session across PRs #190–#193. Pure-function
architecture (`getHotList`, `renderHotItem`, `renderHotList`) separated from
DOM wiring for future Vitest unit testing. Polish additions beyond original
plan: animated flame gradient border, L→R bounce slide-in animation, narrative
hover-expand (2-line clamp → full on hover), film domain badge contrast fixes
(10 new type rules), toolbar/button semantic token contrast fixes, default badge
white-on-gray for dark mode.

**What changed from original plan:** The original Sprint 8 planned to ship with
"raw velocity-ranked entities" — just numbers. The LLM Leverage work (Sprint 8
backend, ADR-007) delivered LLM-generated narratives that explain WHY each entity
is trending. Example from first production run:

> *"The Hollywood Reporter is trending due to its coverage of Rosanna Arquette's
> open letter in response to Harvey Weinstein's prison interview claims."*

This leapfrogs the B.8→B.9 "insight artifacts" upgrade path. The panel ships
with rich content from day 1 instead of needing a future content upgrade.

**Data available in `trending.json` per node** (all populated today):
- `velocity` — 7d-vs-prior ratio (primary sort signal)
- `trend_score` — composite score (velocity + novelty + activity)
- `mention_count_7d` / `mention_count_30d` — raw mention counts
- `novelty` — how new/rare the entity is
- `narrative` — LLM-generated "WHY" explanation (1-2 sentences, when available)
- `type` — entity type for badge display
- `firstSeen` / `lastSeen` — for "new entity" indicators

**Remaining upgrade path (B.10–B.11):**
```
Sprint 8 (UI with narratives)     DONE: LLM narratives in trending.json
      │                                        │
      ▼                                        ▼
Sprint 8.3 ships with narratives ──► B.10 (backtest: are narratives
                                            actually accurate?)
                                           │
                                      B.11 (dedup so daily users
                                            don't see repeats)
```

---

## Sprint 8B — Hot Panel Polish + UI Tweaks (Day 20, 2026-03-22)

Quick-hit fixes from Sprint 8 user testing. All are small, contained changes.

| # | Item | Source | Est. | Model |
|---|------|--------|------|-------|
| 8B.1 | Panel text contrast — swap hardcoded `text-gray-*` utilities for semantic tokens in `panels.js` | backlog §GEV-7 | ~30 min | [Sonnet] |
| 8B.2 | Suppress node tap handler during `flyToHotNode` — prevent double panel-open | backlog §GEV-8 | ~15 min | [Sonnet] |
| 8B.3 | Anchor minimap — remove repositioning or add smooth transition | backlog §GEV-10 | ~15 min | [Sonnet] |
| 8B.4 | Node visibility when panel overlaps — offset `zoomToNode` target by panel width | backlog §GEV-9 | ~45 min | [Opus] |
| 8B.5 | Entity spotlight card — top-drop bounce, fwd/back navigation | backlog §GEV-6 | ~2 hr | [Opus] |

**Risk:** Low. Items 8B.1–8B.3 are mechanical find-and-replace or config tweaks.
8B.4 is a small UX improvement. 8B.2 redesigned as a panel architecture change.
**Dependency:** Sprint 8 (hot panel must exist).
**Completed:** 2026-03-28
**Notes:** All 5 items delivered. Key architectural decision: evidence panel moved
from bottom drawer to left sidebar. All left panels (detail, evidence, hot) are
now mutually exclusive with shared bounce-in animation. See
[ADR-009](architecture/adr-009-unified-left-panel-slot.md) for rationale.
8B.5 (entity spotlight card) deferred — overlaps with GEV-6 in backlog.

---

## Sprint 9 — Discovery Rewards (Days 21–23)

Builds on Sprint 1 (`.new` class wiring) and Sprint 8 (hot list signals).

| # | Item | Source | Lines | Model |
|---|------|--------|-------|-------|
| 9.1 | New-entity entrance glow (one-time pulse on `.new` nodes) | delight §DL-2a | ~20 JS+CSS | [Sonnet] |
| 9.2 | "N new since yesterday" toolbar badge | delight §DL-2b | ~30 JS+HTML+CSS | [Sonnet] |
| 9.3 | Staggered neighborhood reveal animation (desktop only) | delight §DL-2c | ~40 JS | [Opus] |
| 9.4 | "What's New" temporal highlight toggle | polish-strategy §P3 | ~50 JS | [Sonnet] |

**Risk:** Moderate. Animation timing is fiddly. Must respect `prefers-reduced-motion`.
**Dependency:** Sprint 1 (`.new` class), Sprint 8 (signals for badge counts).

---

## Sprint 10 — Guided Entry Point (Day 23)

Ties together What's Hot signals + discovery into a first-load experience.

| # | Item | Source | Lines | Model |
|---|------|--------|-------|-------|
| 10.1 | "Today's Highlights" overlay card (top 3 items, auto-dismiss) | delight §DL-3 | ~80 JS+CSS+HTML | [Opus] |
| 10.2 | `localStorage` flag per export date (don't re-show on refresh) | delight §DL-3 | ~10 JS | [Opus] |

**Risk:** Low-moderate. Overlay is additive. `localStorage` is straightforward.
**Dependency:** Sprint 8 (same signal data).

---

## Sprint 11 — Medium Gap Features (Days 24–27)

Spec features that were never built. Each is independent. Can be parallelized.

| # | Item | Source | Lines | Model |
|---|------|--------|-------|-------|
| 11.1 | Context menu (right-click: expand, hide, pin, select) | gap-remediation §3.1 | ~150 JS+HTML | [Opus] |
| 11.2 | Colorblind-safe palette + toggle | gap-remediation §3.2 | ~80 CSS+JS | [Sonnet] |
| 11.3 | Custom date range picker inputs | gap-remediation §3.3 | ~70 HTML+JS | [Sonnet] |
| 11.4 | Gzipped JSON export (build step) | gap-remediation §2.1 | ~20 script | [Sonnet] |

**Risk:** Context menu is moderate (extension loading, pin/hide state). Others are low.
**Why Opus for 11.1:** Pin-position and hide-node logic need layout integration + state
tracking that cross-cuts filter and layout modules.

---

## Sprint 12 — Branding & Wrap-up (Day 28)

| # | Item | Source | Lines | Model |
|---|------|--------|-------|-------|
| 12.1 | App title/branding swap (when name is decided) | delight §DL-6 | ~5 HTML+CSS | [Manual] |
| 12.2 | Minimap toggle animation (scale from corner) | polish-strategy §P3 | ~10 CSS | [Sonnet] |
| 12.3 | Final QA pass across all views, both themes, desktop | — | — | [Manual] |

**Dependency:** 12.1 blocked on branding decision (external).

---

## Sprint 13 — Trend Methodology Upgrade + Semiconductor Onboarding

Incorporates findings from the academic vetting review
([vetting.txt](methodology/research/vetting.txt)) and the semiconductor domain
design rationale ([semiconductor-domain-design.md](methodology/semiconductor-domain-design.md)).
Three layers: onboarding process documentation, framework formula fixes, and
semiconductor domain retrofit.

**Ordering rationale:** Layer 1 (guide) informs Layer 2 (framework fixes), which
must land before Layer 3 (semiconductor launch) so the new domain benefits from
corrected formulas on day one.

**Origin:** Discussion session 2026-04-04 reviewing vetting.txt against current
trending strategy. Key insight: our system is a *hypothesis generator* (curated
alerting), not a *hypothesis confirmer* (GDELT-scale detection). The onboarding
process should set that expectation and guide domain authors toward the parameters
that match their domain's shape.

### Layer 1 — Domain Design Guide

New document: `docs/guides/domain-design-guide.md`. Sits between the mechanical
template README (`domains/_template/README.md`) and the architecture docs
(`docs/architecture/domain-separation.md`). Captures methodological judgment that
took three domains to learn.

| # | Item | What | Model |
|---|------|------|-------|
| 13.1 | Domain Fitness Checklist | Shape test gate: entity persistence, source independence, claim corroborability, story cycle vs. velocity window, entity density. Rejection criteria with worked examples (semiconductors passes, film fails on persistence, academia fails on cycle speed). Based on `semiconductor-domain-design.md` §Domain Candidate Evaluation | [Opus] |
| 13.2 | Trend Calibration Worksheet | Per-domain parameter reasoning: story half-life → novelty λ, velocity window sizing, min-mention threshold, entity churn rate → novelty flooding risk. Worked examples for AI (fast churn, λ≈0.05), semiconductors (slow burn, λ≈0.02), biosafety (regulatory, λ≈0.03). Based on vetting.txt §2 (novelty decay) and semiconductor doc §30% Overlap Target | [Opus] |
| 13.3 | Source Selection Rationale Template | Required per-feed documentation: signal type, known limitations, editorial independence assessment, temporal fingerprinting risk. Semiconductor feeds section as the model. Based on vetting.txt §3 (source independence) and semiconductor doc §Feed Selection Rationale | [Opus] |
| 13.4 | Hypothesis-Generator Framing | Explicit expectation-setting: what the pipeline can/cannot claim at different maturity stages. Overlap rate health table (from semiconductor doc). Multi-signal fusion maturity roadmap: news-only → +structured signals → confirmation capability. Based on vetting.txt §8 (scale constraints) and discussion of GDELT vs. curated alerting | [Opus] |
| 13.5 | Inference Rules Phasing Guide | Start with 0–3 rules, run 2 weeks, check for false inferences, then expand. Mirrors normalization phasing lesson from biosafety post-mortem. Based on semiconductor doc §Supply Chain Inference and `docs/fix-details/new-domain-lessons-learned.md` | [Opus] |

**Output:** Single document covering 13.1–13.5.

### Layer 2 — Framework Formula Fixes (from vetting review)

Code changes to `src/trend/__init__.py` and domain configs. Each item includes
specific test requirements — tests should validate mathematical properties, not
just "returns a float."

| # | Item | What changes | Model |
|---|------|-------------|-------|
| 13.6 | Exponential novelty decay | Replace linear `1 - (age/max_age)` with `exp(-λ × days)` in `compute_novelty()`. λ configurable per domain via `trend_weights.novelty_decay_lambda` in `domain.yaml`. Default λ=0.05 (~14-day half-life). Vetting §2: "365-day linear age decay is inappropriate... exponential decay with λ ≈ 0.05–0.10 would better match empirical reality" | [Opus] |
| 13.7 | Corpus-normalized rarity | Replace `1/(1+ln(1+mentions))` with `log(1+N/(1+mentions))/log(1+N)` where N = total entity count. Vetting §2: "rarity function lacks corpus normalization... 100 mentions might be extremely common [or] rare" depending on corpus size | [Opus] |
| 13.8 | Min-mention velocity gate | Add `min_mentions_for_velocity` to `trend_weights` (default 3). Below threshold, velocity = 1.0 (neutral). Vetting §2: "minimum mention threshold (e.g., ≥3 mentions in either window) before velocity contributes to the composite score" | [Opus] |
| 13.9 | Update domain.yaml for all domains | Add new config keys with domain-appropriate values. AI: λ=0.05, min_mentions=3. Biosafety: λ=0.03, min_mentions=2. Semiconductors: λ=0.02, min_mentions=3. Film: λ=0.07 (fast cycle), min_mentions=2 | [Sonnet] |
| 13.10 | Update `domain-profile.json` schema | Add new optional keys with defaults so existing configs validate without changes | [Sonnet] |

**Test requirements for Layer 2** (not optional — these are the safety net):

- **13.6 tests:** Verify decay curve at 0, 7, 14, 30, 90, 365 days for multiple λ
  values. Edge cases: λ=0, negative age. Regression guard: old linear behavior must
  NOT be preserved. Property: monotonically decreasing with age.
- **13.7 tests:** Rarity at mentions=0, 1, 10, 100 for corpus sizes 50, 500, 5000.
  Edge case: single-entity corpus. Properties: monotonically decreasing with mentions;
  increasing with corpus size at fixed mentions.
- **13.8 tests:** Entity with 1 mention gets velocity 1.0. Entity with 3+ mentions
  gets real velocity. Threshold=0 disables gate. Regression guard: 1→2 mention
  scenario must NOT produce 2.0x velocity when threshold=3.
- **Cross-domain tests:** Same formula with AI params vs. semiconductor params produces
  qualitatively different but individually correct results.

### Layer 3 — Semiconductor Domain Retrofit + Launch Readiness

| # | Item | What | Model |
|---|------|------|-------|
| 13.11 | Semiconductor design guide audit | Walk semiconductor config through Domain Design Guide checklist (13.1–13.5). Document gaps in existing design rationale. Fill in: velocity window justification, novelty decay reasoning, source independence matrix. Output: addendum to `semiconductor-domain-design.md` | [Opus] |
| 13.12 | Overlap rate health check script | `scripts/check_domain_health.py` — computes entity overlap rate after N days of data. Outputs the overlap table from the semiconductor doc with actual numbers. Flags if <20% with warning | [Sonnet] |
| 13.13 | Source-type field preparation | Verify `source_type` column exists (Sprint 7 item 7A.4). If not yet landed, add it as prerequisite for future multi-signal fusion. Tag existing feeds as `rss` | [Sonnet] |

### Layer 4 — Logging, Instrumentation & Reporting

Formula changes without audit trails produce uninterpretable historical data.
Currently `trend_history` logs score outputs (velocity=1.23, novelty=0.45) but
not the configuration that produced them. The metrics gist
(`scripts/collect_metrics_gist.sh`) collects 10 files across batch jobs, feeds,
pipelines, and funnels but has **zero trend scoring visibility** — no trend_history
queries, no formula config capture, no scoring distribution data.

| # | Item | What | Model |
|---|------|------|-------|
| 13.14 | Add config snapshot columns to `trend_history` | Add columns to `schemas/sqlite.sql` and `_save_trend_history()`: `novelty_decay_lambda REAL`, `min_mentions_for_velocity INTEGER`, `corpus_entity_count INTEGER`, `velocity_gated INTEGER DEFAULT 0` (1 if velocity forced to 1.0 by gate). Makes every historical row self-describing — you can always tell which formula version produced which score | [Sonnet] |
| 13.15 | Add `trend_config` to pipeline run log | Log formula parameters in daily pipeline JSON (`data/logs/pipeline_*.json`) under a `trend_config` key: `{lambda, min_mentions, corpus_size, velocity_cap, activity_cap, weights}`. Also add `trend_config TEXT` column to `pipeline_runs` table for DB-backed queries. Makes formula changes visible in dashboard and gist without needing trend_history joins | [Sonnet] |
| 13.16 | Update health report for trend formula validation | Add section to `scripts/health_report.py`: velocity gate effectiveness (% entities gated vs. real velocity), novelty score distribution (quartiles — are scores bunched or spread?), corpus entity count trend over time. Ensures `02_health_report.txt` in the gist reflects formula behavior, not just pipeline throughput | [Sonnet] |
| 13.17 | Add trend scoring to metrics gist | Add file `11_trend_scoring.csv` to `scripts/collect_metrics_gist.sh`: query `trend_history` for last 7 days — entity_id, run_date, velocity, novelty, trend_score, velocity_gated, corpus_entity_count, novelty_decay_lambda. Also add `12_trend_config_history.csv`: per-run formula config from `pipeline_runs.trend_config`. Closes the blind spot where gist captures everything *except* the scoring that drives What's Hot | [Sonnet] |
| 13.18 | Add trending-layer signals to calibration report | Add three collectors + suggestion generators to `scripts/run_calibration_report.py` following the existing `collect_*` + `generate_suggestions()` pattern. Reads from `trend_history` table (available after 13.14 lands). **Three new signals:** (1) *Velocity gate saturation* — % of scored entities where `velocity_gated=1`. Threshold: >80% means `min_mentions_for_velocity` is too aggressive for this domain's volume; suggest lowering by 1. (2) *Novelty score compression* — distribution quartiles of novelty scores. Threshold: if 90%+ of entities have novelty <0.1 (λ too aggressive) or >0.8 (λ too slow); suggest adjusting `novelty_decay_lambda` by ±0.01. (3) *Trending list churn* — % overlap of top-10 `in_trending_view` entities between consecutive run_dates. Threshold: <10% day-over-day means scoring is unstable, >70% means scoring is stale; suggest reviewing composite weights. No auto-apply — suggestions logged to `tuning_log` table for review, same as existing six signals | [Sonnet] |

**Risk:** Low-moderate. Formula changes are mathematically simple but affect every
domain's trending output. The test suite is the safety net — tests should be written
*with old expected values first*, then updated after formula changes land.
Instrumentation items (Layer 4) should land *alongside* the formula changes in
Layer 2 so that the first run with new formulas is fully logged.

**Estimated effort:** ~2 sprint days. Layer 1 is a writing session. Layer 2 is
focused code changes with thorough tests. Layer 3 is light. Layer 4 is
straightforward schema + query additions but must be coordinated with Layer 2.

**Dependency:** The resolve bug noted in `semiconductor-domain-design.md` decision
log (2026-04-02: "O(n²) DB queries must be fixed on server before semiconductors
launches"). If unresolved, 13.11–13.13 wait for that fix.

**Future backlog (not this sprint):**

| Item | Priority | Trigger |
|------|----------|---------|
| Retrofit AI domain trend params | Medium | After 13.6–13.8 land; tune AI's weights using vetting recommendations |
| Source-count corroboration weighting | Medium | Implement the step-function from prediction-methodology.md §4.1 (1 source: 0.5×, 2: 0.75×, 3+: 1.0×) |
| Fix validation metric inconsistencies | Low | Update prediction-methodology.md §5.2: resolve FPR/precision contradiction, lower recall to 0.30–0.40, extend eval windows to T+180 |
| Multi-signal fusion: earnings transcripts | Low | After semiconductor domain has 30+ days of news-only data; SEC EDGAR ingest for TSMC/Intel/Samsung quarterly transcripts |
| Biosafety/film design guide audit | Low | Walk existing domains through 13.1–13.5 checklist; document known limitations |

---

## Sprint 14 — Backend Movers (Workstream A)

Backend half of the Movers + Focus Mode feature. Produces a new
`movers.json` export that surfaces the full scored entity population
(not just the top-50 Current Landscape) as the substrate for a tabular
movement-tracking UI. Adds the source-type registry that lets chatter
sources (`bluesky`, `reddit`) contribute velocity signal without
consuming extraction tokens.

**Design docs:** [docs/plans/movers-and-focus-mode.md](plans/movers-and-focus-mode.md)
(implementation plan + `movers.json` schema in Appendix A) and
[docs/free-text/movers-vs-current-landscape.md](free-text/movers-vs-current-landscape.md)
(design conversation).

**Origin:** Trends-view analysis discussion (May 2026). Insight: the
top-50 trending view is structurally biased toward established
entities; truly emerging entities (rank 140→75, just-appeared) need a
different lens. `trend_history` already persists the full scored
population daily — no backfill required. See PRs #254 and #255.

| # | Item | What | Model |
|---|------|------|-------|
| 14.1 | Source-type extraction registry | New config block in `src/ingest/dispatch.py` (or new `src/config/source_types.py`) mapping `source_type → { extract: bool }`. Set `bluesky` and `reddit` to `extract: false`; default `rss` / `substack` to `extract: true`. Registry is tied to source_type, not individual feeds | [Sonnet] |
| 14.2 | `doc_select` honors registry | Update `src/doc_select/` to filter out docs whose source_type is non-extracting before extraction-budget allocation. Unit test confirming bluesky/reddit docs are ingested but never extraction-queued | [Sonnet] |
| 14.3 | `run_movers.py` skeleton | New `scripts/run_movers.py` — argparse, dotenv prelude, domain bootstrap, DB init. Mirrors `scripts/run_trending.py` structure. Accepts `--domain`, `--db`, `--output-dir`, `--window-days` (default 7) | [Sonnet] |
| 14.4 | Movers row builder | SQL query reading `trend_history` for today + `today − window_days`. Compute `rank_delta`, `is_new`, `velocity_raw` (uncapped — re-derive from mention counts; do NOT pull capped `velocity` from trend_history). Join `entities` for label / type / first_seen. Join `mentions` × `documents` for `distinct_sources_7d`. Exact field contract: [plans/movers-and-focus-mode.md](plans/movers-and-focus-mode.md) Appendix A | [Opus] |
| 14.5 | `movers.json` schema | New `schemas/movers.json` JSON Schema matching Appendix A. Validate output of 14.4 against it before write. Match the existing schema convention used for the other four views | [Sonnet] |
| 14.6 | `make movers` target | Add `movers` target invoking `python scripts/run_movers.py --domain $(DOMAIN)`. Insert into `make daily` between `trending` and `copy-to-live`. Verify `copy-to-live` publishes movers.json automatically (it already globs `*.json` from the export dir) | [Sonnet] |
| 14.7 | Unit tests | rank Δ math, `is_new` behavior for entities lacking a prior-window row, empty `trend_history` corner case, source-type registry filtering, velocity_raw null when undefined. Must pass `tests/test_grep_audit.py` (no hardcoded domain logic) | [Sonnet] |
| 14.8 | All-domain smoke run | `make daily DOMAIN={ai,semiconductors,film,biosafety}`. Confirm non-empty movers.json. Qualitative check: film domain produces meaningfully different top entries than its trending top-50 — this is the proof-point that the new lens works. Confirm `feed_stats` shows bluesky/reddit docs ingested with zero extraction tokens | [Manual] |

**Output:** `data/graphs/{domain}/{date}/movers.json` published to
`web/data/graphs/live/{domain}/movers.json` for all four domains.

**Acceptance:** All four domains produce schema-valid movers.json on the
next `make daily` run. Chatter source token cost drops to zero. Film
domain movers surface noticeably different entities than its trending
top-50.

**Dependency:** None blocking. All "Before A" decisions locked per
[plans/movers-and-focus-mode.md](plans/movers-and-focus-mode.md)
§"Before A".

---

## Sprint 14B — Locked-neighborhood focus mode (Workstream C1, parallel with 14)

Fixes a pre-existing graph UX pain point: in neighborhood view of a
well-connected node, clicking an edge to a multiply-connected neighbor
drops the user back to the full-graph spaghetti, forcing them to
manually re-pick the 2nd / 3rd / 4th connections. Introduces a
**persistent focus state** that doesn't dissolve on click and operates
on focused entities instead of reverting to global view.

**Independently justified.** Even without Movers this is a graph UX win.
Also serves as the foundation for Sprint 16's universal Movers deep-link.

**Design docs:** [docs/plans/movers-and-focus-mode.md](plans/movers-and-focus-mode.md)
§"Workstream C1" and §"Graph focus mode — a convergent primitive."

| # | Item | What | Model |
|---|------|------|-------|
| 14B.1 | Focus state model | JS state in `web/js/graph.js` (or new `web/js/focus.js`): `{ focusedIds: Set<string>, active: bool }`. Persisted to URL as `?focus=<id>` (comma-separated for future multi-entity expansion) | [Sonnet] |
| 14B.2 | Entry gesture | Button labeled "Focus on this entity" on the node detail panel. **Do not** hijack left-click — existing transient-highlight click behavior stays unchanged | [Sonnet] |
| 14B.3 | Render in focus mode | When `focusActive`, dim all nodes outside `focusedIds` ∪ 1-hop neighbors. New CSS class `.focus-dimmed` (separate from `.neighborhood-dimmed` per ux/troubleshooting.md guidance about not mixing dimming contexts) | [Sonnet] |
| 14B.4 | Click-in-focus expand semantics | Clicking a peripheral (dimmed-but-visible neighbor) node adds it to `focusedIds`; re-render. Matches the original pain point — user keeps siblings visible while exploring | [Sonnet] |
| 14B.5 | Focus chip UI | Top-of-canvas chip / breadcrumb: "Focused: {label}" with close button. Multi-entity displays as "Focused: {label} + N more" | [Sonnet] |
| 14B.6 | Exit gestures | Esc key, chip close button, clearing `?focus=` from URL all exit focus mode | [Sonnet] |
| 14B.7 | URL round-trip | Page reload with `?focus=<id>` re-enters focus mode on that entity. Browser back/forward respect focus state | [Sonnet] |
| 14B.8 | Playwright tests | Self-contained harness: enter focus, expand via peripheral click, exit via esc, URL round-trip after reload | [Sonnet] |

**Output:** Locked-neighborhood mode on the existing graph page. No
backend changes.

**Acceptance:** Pre-existing pain point demonstrably fixed — user can
navigate between connected nodes without falling back to full graph.
Existing left-click transient highlight unchanged.

**Dependency:** None. Independent of Sprint 14; can ship in parallel.

---

## Sprint 15 — Movers Frontend V1 (Workstream B)

Standalone Movers page consuming `movers.json`. Table with five named
presets + Custom mode, inline detail panel, opportunistic graph
deep-link for top-50 entities. Universal entity deep-link arrives in
Sprint 16.

**Design docs:** [docs/plans/movers-and-focus-mode.md](plans/movers-and-focus-mode.md)
§"Workstream B" + §"Sort + filter UX" + Appendix A.

**Execution gate:** UI wireframe pass — column layout, preset chip
placement, detail panel positioning. Items 15.1, 15.3, 15.4, 15.6, 15.9
shape themselves around the wireframe; other items are wireframe-
independent and can start earlier.

**Wireframe v0:** [docs/ux/movers-wireframe.md](ux/movers-wireframe.md)
— drafted 2026-05-23, five open questions flagged at the bottom for
user signoff before coding begins.

| # | Item | What | Model |
|---|------|------|-------|
| 15.1 | `web/movers.html` shell | New page mirroring `dashboard.html` / `ontology.html` visual idiom. Toolbar with domain switcher (reuse `domain-switcher.js`), title, link back to graph view | [Sonnet] |
| 15.2 | Data loader | New `web/js/movers.js`: load `movers.json` for `?domain=<slug>`. Loading / empty / error states. Tolerate unknown fields (forward compat per Appendix A) | [Sonnet] |
| 15.3 | Table component | Render columns from Appendix A. Sticky header. Reuse `badge-type-{type}` classes. "NEW" badge for `is_new: true` rows. Rank Δ as ↑65 / ↓3 / — | [Sonnet] |
| 15.4 | Preset chip group | Five presets — Biggest climbers (default), Just appeared, Fastest accelerators, Emerging consensus, Sanity reference — + Custom. Each preset is a `{sort, filter}` tuple per plan doc §"Sort + filter UX" | [Sonnet] |
| 15.5 | Custom-mode controls | Sort dropdown (all columns) + filter pills (Hide top 50, First seen ≤ N days, entity type, min mentions). State persisted in URL | [Sonnet] |
| 15.6 | Detail side-panel | Slide-in from right (or below-row inline — wireframe-dependent). Entity label, type, mention timeline, top sources with favicons, sample evidence snippets with source links | [Opus] |
| 15.7 | Deep-link to graph (top-50 only) | "View in graph" link on rows where `in_trending_view: true` — deep-links to `index.html?domain=<slug>` and selects the node via existing `navigateToNode`. For `in_trending_view: false`, no link in V1 (Sprint 16 adds universal) | [Sonnet] |
| 15.8 | Navigation entry points | Movers link added to `index.html` toolbar. Add to `dashboard.html` if appropriate (decide during impl) | [Sonnet] |
| 15.9 | Basic responsive layout | Mobile screens must not break. Detail panel becomes overlay rather than slide-in. Mobile-tuned layout is V2 | [Sonnet] |
| 15.10 | Playwright smoke test | Self-contained harness with mock movers.json fixture: page loads, preset switching works, table renders, row click opens panel, deep-link works for top-50 entity | [Sonnet] |
| 15.11 | Manual QA across domains | Each preset surfaces something interesting in AI, semiconductors, biosafety, and **especially film**. Film is the proof-point for the new lens; if Movers doesn't make film useful, V1 has shipped without its main justification | [Manual] |

**Output:** Movers page live at `/movers.html?domain={slug}` for all
four domains.

**Acceptance:** All five presets demonstrably surface different views.
Custom mode allows arbitrary sort + filter compositions. Film domain
QA produces a "yes, this is genuinely useful" qualitative reaction.

**Dependency:** Sprint 14 (needs movers.json). Wireframe pass before
execution starts.

---

## Sprint 16 — Universal Movers deep-link via on-demand neighborhoods (Workstream C2)

Closes the loop on Movers ↔ graph navigation. Makes "View in graph"
work for *any* entity in Movers, not just the top-50 already in
trending.json. Requires per-entity neighborhood data published as
static files.

**Design docs:** [docs/plans/movers-and-focus-mode.md](plans/movers-and-focus-mode.md)
§"Workstream C2."

**Why static fan-out, not a dynamic endpoint:** The project's hosting
model is static. Per-entity neighborhood files (`{entity_id}.json`) are
cacheable, scale with the corpus, and don't require new infrastructure.
File count budget is the key open item — confirm during impl.

| # | Item | What | Model |
|---|------|------|-------|
| 16.1 | Neighborhood fan-out exporter | New `scripts/export_neighborhoods.py`. For each entity in `trend_history` with `mention_count_30d > 0`, write `data/graphs/{domain}/{date}/neighborhoods/{slug}.json` containing the entity, its 1-hop neighbors, and connecting edges. Cap at e.g. 30 neighbors by edge weight | [Opus] |
| 16.2 | File count budget verification | Per-domain file count check. Tune the inclusion threshold (default: any entity with 30d mentions) if counts get unwieldy. Document the chosen rule in the plan doc | [Sonnet] |
| 16.3 | Publish path | Verify `copy-to-live` publishes the `neighborhoods/` subdirectory correctly. Adjust glob if not | [Sonnet] |
| 16.4 | Graph page focus-fetch | When `?focus=<id>` lands on an entity not in current trending.json, fetch `neighborhoods/{slug}.json` from live data dir and inject those nodes/edges before entering focus mode (Sprint 14B) | [Opus] |
| 16.5 | Movers row universal link | Update Sprint 15.7 — "View in graph" link present on every row. Deep-link uses `?focus=<id>` URL param. Top-50 vs non-top-50 distinction in UI becomes informational only ("In Current Landscape" indicator) rather than affecting navigation availability | [Sonnet] |
| 16.6 | Cache freshness documentation | Document file size / count / freshness expectations in the plan doc. Note that ≤24h staleness is acceptable; daily pipeline run refreshes | [Manual] |
| 16.7 | Playwright test | Click Movers row → graph deep-link for an entity *not* in top-50 → focus mode loads its neighborhood | [Sonnet] |

**Output:** Universal Movers → graph navigation. Neighborhood files
published as part of `make daily`.

**Acceptance:** Any Movers row's "View in graph" link works. Graph
loads the entity's 1-hop neighborhood and enters focus mode.

**Dependency:** Sprint 14B (focus mode), Sprint 15 (Movers row link
target), Sprint 14 (`trend_history` is the iteration target for fan-out).

---

## Backend Track (parallel, data-dependent)

These items run independently of the UI work. Most are waiting on pipeline data.

| # | Item | Source | Status | Model |
|---|------|--------|--------|-------|
| B.1 | Entity type definitions in extraction prompt | backlog §EXT-1 | Waiting on data patterns | [Opus] |
| B.2 | Density score prompt tuning | backlog §EXT-2 | Waiting on full backlog extraction | [Manual] |
| B.3 | Confidence calibration rubric | backlog §EXT-3 | Waiting on full backlog extraction | [Opus] |
| B.4 | Extract stage batch size limit | backlog §PIPE-1 | Active workaround exists | [Sonnet] |
| B.5 | VentureBeat 429 retry reset | backlog §PIPE-2 | Low priority | [Sonnet] |
| B.6 | Anthropic Blog feed monitoring | backlog §SRC-1 | Monitor only | [Manual] |
| B.7 | Feed freshness verification | backlog §SRC-2 | Run diagnostic script | [Manual] |
| B.8 | Insight template spec (title templates + `so_what` stubs per category) | [trend-insights](research/trend-insights.md) §2–3 | Ready now (pure doc, no data dependency) | [Opus] |
| B.9 | Insight generator script (`scripts/generate_insights.py`) | [trend-insights](research/trend-insights.md) §6 Phase B | Blocked on ≥14 days pipeline data (~mid-March) | [Opus] |
| B.10 | Backtest harness for insight accuracy | [trend-insights](research/trend-insights.md) §6 Phase C | Blocked on ≥30 days pipeline data (~late March) | [Opus] |
| B.11 | Insight deduplication + storage (JSONL + SQLite) | [trend-insights](research/trend-insights.md) §8 | After B.9 | [Sonnet] |

---

## Deferred (V2 / as-needed)

Not scheduled. Documented so they're not forgotten.

| Item | Source | Trigger |
|------|--------|---------|
| Label collision detection | gap-remediation §4.1 | User complaints about overlap |
| Mobile CSS splitting | gap-remediation §4.2 | Next significant mobile CSS change |
| Dark mode crossfade | polish-strategy §P3 | If instant swap bothers users |
| Loading skeleton for panels | polish-strategy §P3 | V2 lazy-loaded details |

---

## Progress Summary

| Sprint | Status | Completed |
|--------|--------|-----------|
| 1 — Dead Code Wiring | ✓ Done | 2026-02-27 |
| 2 — Aesthetic Identity CSS | ✓ Done | 2026-02-28 |
| 3 — Toolbar Icons | ✓ Done | 2026-03-01 |
| 4 — Graph Canvas Polish | ✓ Done | 2026-03-01 |
| 5 — Interaction Polish | ✓ Done | 2026-03-04 |
| 6 — Domain Modularization | ✓ Done | 2026-03-07 |
| 6B — Biosafety Domain (bonus) | ✓ Done | 2026-03-07 |
| — Biosafety stabilization | ✓ Done | 2026-03-09 |
| — CI/CD deploy fix | ✓ Done | 2026-03-10 |
| — Pipeline dashboard | ✓ Done | 2026-03-01 |
| — Ontology reference page | ✓ Done | 2026-03-13 |
| — Domain switcher UI | ✓ Done | 2026-03-13 |
| — Film domain launch | ✓ Done | 2026-03-17 |
| — Film quality gate tuning | ✓ Done | 2026-03-17 |
| 7 — Regional Lens + Chatter Sources | Pending | — |
| 8 — What's Hot | ✓ Done | 2026-03-21 |
| 8B — Hot Panel Polish + UI Tweaks | ✓ Done | 2026-03-28 |
| 9 — Discovery Rewards | Pending | — |
| 10 — Guided Entry | Pending | — |
| 11 — Medium Gap Features | Pending | — |
| 12 — Branding & Wrap-up | Pending | — |
| 13 — Trend Methodology + Semiconductor Onboarding | Pending | — |
| 14 — Backend Movers | Pending | — |
| 14B — Locked-neighborhood focus mode | Implemented (smoke pending) | 2026-05-22 |
| 15 — Movers Frontend V1 | Pending | — |
| 16 — Universal Movers deep-link | Pending | — |

---

## Completion Estimate

| Metric | Value |
|--------|-------|
| Working pace | ~2 sprints/day (faster than original estimate) |
| Start date | 2026-02-27 |
| As of | 2026-04-04 (9 planned sprints + 7 unplanned items done in 36 days) |
| Sprints remaining | 5.5 sprints (7, 9–13) |
| Backend track | Parallel, partially blocked on data (≥30 days data now available) |
| Sprint 13 | Backend methodology track — independent of UI sprints 9–12 |
| **Revised target** | **~mid-April 2026** |

**Milestone (Sprint 6 + 6B, March 7):** Domain plugin architecture delivered AND
validated with biosafety as second domain. Framework is domain-agnostic, grep-audit
enforced in CI.

**Post-Sprint-6B unplanned work (March 7–14):** Five significant items landed outside
the original sprint plan:
- **Biosafety stabilization (March 7–9):** Fixed 6 dead RSS feeds, extraction prompt
  field specs, evidence array coercion, Python format string brace escaping,
  normalization map gaps (PUBLISHED_BY, day resolution). See
  [fix-details/README.md](fix-details/README.md).
- **CI/CD disk exhaustion (March 9–10):** 7 PRs over 24 hours to resolve GitHub Actions
  disk space failures caused by stale Docker context reference. See
  [fix-details/README.md](fix-details/README.md).
- **Pipeline dashboard (March 1):** `web/dashboard.html` + `scripts/generate_dashboard_json.py`
  for pipeline health monitoring.
- **Ontology reference page (March 13):** `web/ontology.html` + `scripts/export_ontology.py`
  for specialist-facing taxonomy visualization.
- **Domain switcher (March 13):** Interactive domain dropdown in toolbar with "About this
  Domain" certificate modal. `web/js/domain-switcher.js` as single source of truth for
  domain enumeration (`KNOWN_DOMAINS` registry).

**Impact on timeline:** Unplanned stabilization and infrastructure work consumed ~4 days
(March 7–10). Film domain launched March 17 with quality gate tuning. Sprint 7
(Regional Lens + Chatter Sources) inserted before What's Hot based on strategic
decision to focus film domain on Southeast US production scene. See ADR-005, ADR-006.

**Risks to timeline:**
- Sprint 7 (Regional Lens + Chatter) depends on web search to validate Southeast
  RSS feed availability (scheduled 2026-03-18 retry)
- Bluesky/Reddit API integration (7A.2/3) are new integration surface area —
  rate limits, schema mapping, error handling
- DL-1 (What's Hot, now Sprint 8) velocity delta requires backend data design
  decisions that could expand scope
- Context menu extension loading may have compatibility issues with current
  Cytoscape version
- Branding decision (DL-6) is externally blocked
- Biosafety feed reliability still being monitored (some institutional feeds
  intermittently 404)

---

## Sonnet 4.6 Delegation Notes

**Why most items are [Sonnet]:** The existing spec docs ([gap-remediation-plan](ux/gap-remediation-plan.md),
[polish-strategy](ux/polish-strategy.md), [delight-backlog](ux/delight-backlog.md))
already contain file paths, code snippets, and CSS examples. Sonnet 4.6 can execute
these with a task prompt like:

> "Implement item 2.1 from docs/ux/polish-strategy.md §A0 'Typography upgrade'.
> Read the spec, then make the changes to the files listed. Follow the design
> token discipline described in docs/ux/implementation.md §Design Token Usage."

No additional implementation docs are needed for [Sonnet] items.

**Why some items are [Opus]:** Cross-cutting features (What's Hot, context menu,
staggered reveal) touch multiple modules and need holistic design decisions that
aren't fully captured in any single spec doc. Writing Sonnet-ready specs for these
would cost roughly as many tokens as just implementing them.

**Practical recommendation:** Use Sonnet 4.6 for Sprints 1–5 and 10.2–10.4
(CSS, small JS, well-specified). Use Opus 4.6 for all of Sprint 6 (domain
modularization — all 11 tasks assigned to Opus for consistency since the sprint
is a single cohesive refactor), Sprint 7 (What's Hot), 8.3 (staggered reveal),
9 (guided entry), and 10.1 (context menu).
