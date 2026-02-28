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

## Sprint 1 — Dead Code Wiring (Day 1)

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

---

## Sprint 2 — Aesthetic Identity: CSS Foundation (Days 2–3)

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

---

## Sprint 3 — Toolbar Icons (Day 4)

Replace Unicode glyphs with professional SVG icons. Natural to do right after
toolbar CSS changes settle.

| # | Item | Source | Lines | Model |
|---|------|--------|-------|-------|
| 3.1 | Download/inline ~10 Lucide SVG icons | delight-backlog §DL-5 | ~50 HTML | [Sonnet] |
| 3.2 | Update desktop toolbar HTML to use SVG icons | delight-backlog §DL-5 | ~30 HTML | [Sonnet] |
| 3.3 | Update mobile toolbar HTML to match | delight-backlog §DL-5 | ~20 HTML | [Sonnet] |

**Risk:** Low. Purely presentational. No JS logic changes.
**Dependency:** Sprint 2 (toolbar CSS must be settled first).

---

## Sprint 4 — Graph Canvas Polish (Day 5)

Cytoscape `styles.js` changes. Contained to one file. Changes how the graph
*looks* but not how it *behaves*.

| # | Item | Source | Lines | Model |
|---|------|--------|-------|-------|
| 4.1 | Node depth/texture (thicker borders, underlay shadow, velocity halo) | polish-strategy §A1 | ~30 JS | [Sonnet] |
| 4.2 | Canvas dot-grid background | polish-strategy §A1 | ~6 CSS | [Sonnet] |
| 4.3 | Edge arrow refinement (confidence-scaled arrow size) | polish-strategy §A1 | ~15 JS | [Sonnet] |

**Risk:** Low. All changes are Cytoscape style properties, not event logic.
**Stability gate:** Load all 4 views, confirm rendering at various zoom levels.

---

## Sprint 5 — Interaction Polish (Days 6–7)

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
| 6.4 | Create `domains/ai/views.yaml` | Move `config/views.yaml` content to domain directory. Framework loads views from domain path | ~30 move | [Sonnet] |
| 6.5 | Create `domains/ai/feeds.yaml` | Move `config/feeds.yaml` to domain directory | ~10 move | [Sonnet] |
| 6.6 | Parameterize `src/extract/__init__.py` | Load `RELATION_NORMALIZATION`, `QUALITY_THRESHOLDS`, `GATE_THRESHOLDS` from domain profile instead of hardcoding. Remove AI-specific constants from framework code | ~80 refactor | [Opus] |
| 6.7 | Parameterize `src/trend/__init__.py` | Replace hardcoded `'MENTIONS'` with base relation type from domain profile (3 occurrences: lines ~45, ~172, ~184) | ~15 refactor | [Sonnet] |
| 6.8 | Parameterize `src/schema/__init__.py` | Generate extraction JSON Schema dynamically from domain profile's entity types and relation taxonomy, instead of loading a static `schemas/extraction.json` | ~60 refactor | [Opus] |
| 6.9 | Add `--domain` CLI flag to pipeline entry points | `run_pipeline.py`, `build_docpack.py`, `import_manual.py`, `export_graph.py` accept `--domain ai` (default). Framework resolves to `domains/ai/` and loads profile | ~40 refactor | [Sonnet] |
| 6.10 | Domain profile validation on load | Framework validates `domain.yaml` against the schema from 6.1 at startup. Fail fast with clear error if profile is invalid or missing required fields | ~30 | [Sonnet] |
| 6.11 | Grep-audit: no domain strings in framework | Run automated check that `src/trend/`, `src/resolve/`, `src/graph/`, `src/db/`, `src/schema/` contain zero references to AI-specific entity types, relation names, or source URLs. Add as a test | ~30 test | [Sonnet] |

**Risk:** Moderate. This is a refactoring sprint — behavior should be identical before
and after. But it touches many files and changes how config is loaded. Careful
diffing required.
**Why Opus for 6.1–6.3, 6.6, 6.8:** Cross-cutting changes that need holistic
understanding of how entity types, relations, and thresholds flow through the
pipeline. Getting the domain profile schema right is the critical design decision.
**Stability gate:** Full test suite passes. Pipeline produces identical output for AI
domain before and after. `grep` audit (6.11) passes. Manual smoke test: ingest →
extract → export → verify graph JSON is unchanged.
**Standing rule for all subsequent sprints:** No sprint may introduce hardcoded
domain-specific strings into framework code. The grep-audit test (6.11) enforces this
in CI.

---

## Sprint 7 — "What's Hot" Feature (Days 12–15)

The first genuinely new feature. Requires backend changes (velocity delta
computation) and a new frontend component. Highest complexity in the plan.

| # | Item | Source | Lines | Model |
|---|------|--------|-------|-------|
| 7.1 | Velocity delta computation in export script | delight §DL-1 | ~60 Python | [Opus] |
| 7.2 | Include velocity delta in graph JSON export | delight §DL-1 | ~20 Python | [Opus] |
| 7.3 | `whats-hot.js` — ranked list UI component | delight §DL-1 | ~120 JS | [Opus] |
| 7.4 | Toolbar button + keyboard shortcut (`h`) | delight §DL-1 | ~15 JS+HTML | [Opus] |
| 7.5 | Fly-to-neighborhood on item click | delight §DL-1 | ~25 JS | [Opus] |
| 7.6 | Panel CSS for hot list drawer | delight §DL-1 | ~40 CSS | [Opus] |

**Risk:** Moderate. Backend data flow change + new UI component. But isolated —
if it breaks, it only breaks the hot list.
**Why Opus:** Cross-cutting feature touching backend export, new JS module, toolbar
integration, and fly-to animation. Needs holistic understanding of the data flow.
**Stability gate:** Verify hot list populates from real export data, fly-to works,
drawer opens/closes cleanly. Confirm existing views are unaffected.

---

## Sprint 8 — Discovery Rewards (Days 16–18)

Builds on Sprint 1 (`.new` class wiring) and Sprint 7 (hot list signals).

| # | Item | Source | Lines | Model |
|---|------|--------|-------|-------|
| 8.1 | New-entity entrance glow (one-time pulse on `.new` nodes) | delight §DL-2a | ~20 JS+CSS | [Sonnet] |
| 8.2 | "N new since yesterday" toolbar badge | delight §DL-2b | ~30 JS+HTML+CSS | [Sonnet] |
| 8.3 | Staggered neighborhood reveal animation (desktop only) | delight §DL-2c | ~40 JS | [Opus] |
| 8.4 | "What's New" temporal highlight toggle | polish-strategy §P3 | ~50 JS | [Sonnet] |

**Risk:** Moderate. Animation timing is fiddly. Must respect `prefers-reduced-motion`.
**Dependency:** Sprint 1 (`.new` class), Sprint 7 (signals for badge counts).

---

## Sprint 9 — Guided Entry Point (Day 19)

Ties together What's Hot signals + discovery into a first-load experience.

| # | Item | Source | Lines | Model |
|---|------|--------|-------|-------|
| 9.1 | "Today's Highlights" overlay card (top 3 items, auto-dismiss) | delight §DL-3 | ~80 JS+CSS+HTML | [Opus] |
| 9.2 | `localStorage` flag per export date (don't re-show on refresh) | delight §DL-3 | ~10 JS | [Opus] |

**Risk:** Low-moderate. Overlay is additive. `localStorage` is straightforward.
**Dependency:** Sprint 7 (same signal data).

---

## Sprint 10 — Medium Gap Features (Days 20–23)

Spec features that were never built. Each is independent. Can be parallelized.

| # | Item | Source | Lines | Model |
|---|------|--------|-------|-------|
| 10.1 | Context menu (right-click: expand, hide, pin, select) | gap-remediation §3.1 | ~150 JS+HTML | [Opus] |
| 10.2 | Colorblind-safe palette + toggle | gap-remediation §3.2 | ~80 CSS+JS | [Sonnet] |
| 10.3 | Custom date range picker inputs | gap-remediation §3.3 | ~70 HTML+JS | [Sonnet] |
| 10.4 | Gzipped JSON export (build step) | gap-remediation §2.1 | ~20 script | [Sonnet] |

**Risk:** Context menu is moderate (extension loading, pin/hide state). Others are low.
**Why Opus for 10.1:** Pin-position and hide-node logic need layout integration + state
tracking that cross-cuts filter and layout modules.

---

## Sprint 11 — Branding & Wrap-up (Day 24)

| # | Item | Source | Lines | Model |
|---|------|--------|-------|-------|
| 11.1 | App title/branding swap (when name is decided) | delight §DL-6 | ~5 HTML+CSS | [Manual] |
| 11.2 | Minimap toggle animation (scale from corner) | polish-strategy §P3 | ~10 CSS | [Sonnet] |
| 11.3 | Final QA pass across all views, both themes, desktop | — | — | [Manual] |

**Dependency:** 11.1 blocked on branding decision (external).

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

## Completion Estimate

| Metric | Value |
|--------|-------|
| Working pace | ~2 hours/day |
| Start date | 2026-02-27 |
| Sprints | 11 sprints, ~24 working days |
| Backend track | Parallel, partially blocked on data |
| Calendar weeks | ~5 weeks (weekdays only) |
| **Target completion** | **~April 1–4, 2026** |

**Risks to timeline:**
- Sprint 6 (domain modularization) touches many files; refactoring regressions
  could spill into extra days
- DL-1 (What's Hot) velocity delta requires backend data design decisions that
  could expand scope
- Context menu extension loading may have compatibility issues with current
  Cytoscape version
- Branding decision (DL-6) is externally blocked
- Backend items are data-dependent and may shift

**Buffer:** The estimate has no slack built in. A realistic date with ~20% buffer
would be **~April 8, 2026**.

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

**Practical recommendation:** Use Sonnet 4.6 for Sprints 1–5, 6.4–6.5, 6.7, 6.9–6.11,
and 10.2–10.4 (CSS, small JS, config moves, well-specified). Use Opus 4.6 for
Sprint 6.1–6.3, 6.6, 6.8 (domain profile design + framework parameterization),
Sprint 7 (What's Hot), 8.3 (staggered reveal), 9 (guided entry), and 10.1 (context menu).
