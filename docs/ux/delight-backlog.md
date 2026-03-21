# Delight Backlog

Items that take the UI from "everything works" to "someone wants to show this to a friend."
Separate from [polish-strategy.md](polish-strategy.md) (aesthetic mechanics) and
[v1-gaps.md](v1-gaps.md) (functional gaps). This doc is about **engagement, discovery,
and emotional response.**

**Guiding principle: Desktop-first.** All design decisions, layouts, and interaction
patterns are designed for desktop (mouse, large viewport, keyboard) first. Mobile
adaptations follow and may be simplified — but desktop is the primary experience and
must never be compromised for mobile parity.

---

## DL-1: "What's Hot and WHY" Quick-Access View — SHIPPED

**Priority:** High — this is the single highest-delight feature because it gives users
a reason to come back daily.

**Status (2026-03-21):** SHIPPED. Backend (PR #186/#188) + frontend (PR #190/#191/#193)
all merged. Flame toolbar button, `h` keyboard shortcut, ranked list with velocity
indicators and LLM narratives, fly-to-node on click, bounce slide-in animation,
animated flame gradient border, full narrative drill-through in detail panel.

**Problem:** The trending view exists but it's buried in a dropdown alongside three other
views. There's no sense of "what changed since yesterday?" Users have to explore the
full graph and notice differences themselves.

**Backend status (2026-03-21):** COMPLETE. The LLM Leverage Features work (PR #186,
#188, ADR-007) shipped all backend data requirements ahead of Sprint 8. Each trending
entity in `trending.json` now carries velocity, trend score, mention counts, AND an
LLM-generated narrative explaining WHY it's trending. Example from first production run:

> *"The Hollywood Reporter is trending due to its coverage of Rosanna Arquette's
> open letter in response to Harvey Weinstein's prison interview claims."*

Narratives are generated per-domain with domain-appropriate tone (film: trade-press
concise, AI: technical, biosafety: regulatory). Sprint 8 is now **frontend-only**.

**Feature:**

A persistent, easy-to-reach "What's Hot" entry point (button or small drawer) that shows
a ranked list of entities with the **largest recent increase** in relevant metrics:

- Primary signal: velocity delta (change in velocity over last 7 days)
- Secondary signals: mention count spike (7d vs 30d ratio), new entity appearance
  (firstSeen within 3 days), bridge score increase (new cross-cluster connections)
- **WHY context:** LLM-generated narrative subtitle explaining the trend driver

**Behavior:**
1. Button in toolbar (or prominent position) opens a compact ranked list
2. Each item shows: entity name, type badge, spark indicator (e.g., arrow + delta value)
3. **Below the entity name: narrative subtitle** (1-2 sentences explaining WHY)
4. Click an item → graph flies to that node's neighborhood, highlights it, opens detail panel
5. List updates on each data load; no persistence needed for V1
6. Max 10 items — this is a highlight reel, not a leaderboard

**Desktop interaction:**
- Drawer slides in from left or appears as a popover near the button
- Keyboard shortcut: `h` (for hot) or similar
- Clicking an item does a smooth `cy.animate({ center, zoom })` to the neighborhood

**Mobile adaptation:**
- Bottom sheet peek state shows top 3 items (name + narrative only, no spark indicator)
- Swipe up for full list

**What makes this delightful:**
- It answers the most natural question: "What should I look at today?"
- The narrative subtitle answers the follow-up: "Why should I care?"
- The fly-to-neighborhood animation creates a sense of guided exploration
- Seeing velocity *change* (not just absolute values) surfaces genuinely surprising signals

**Data available in `trending.json` per node** (all populated today):
- `velocity` — 7d-vs-prior ratio (primary sort signal)
- `trend_score` — composite score (velocity + novelty + activity)
- `mention_count_7d` / `mention_count_30d` — raw mention counts
- `novelty` — how new/rare the entity is
- `narrative` — LLM-generated WHY explanation (present when available)
- `type` — entity type for badge display
- `firstSeen` / `lastSeen` — for "new entity" indicators

**Files affected:**
- New: `web/js/whats-hot.js`
- Modified: `web/js/app.js` (toolbar button, keyboard shortcut), `web/css/components/panel.css`
  (drawer styles)
- ~~Modified: `src/graph/__init__.py` or export script (velocity delta computation)~~
  **No longer needed — backend is complete**

---

## DL-2: Visual Reward for Discovery

**Priority:** High — addresses the "explore and feel nothing" problem.

**Problem:** When you find something interesting — a new cluster, a hot entity, a
surprising connection — the UI gives zero feedback beyond a border color change. There's
no sense of uncovering something.

**Items (each is small, implement independently):**

### DL-2a: New-entity entrance glow

When the graph loads or a view switches, nodes with `firstSeen` within the last 7 days
get a brief, subtle pulse animation (one cycle, ~800ms). Not bouncing — a single soft
glow that fades. This draws the eye to "what's new here" without being distracting.

**Implementation:** CSS `@keyframes` on the `.new` class (which already exists but is
never applied — see [v1-gaps.md](v1-gaps.md)). Apply `.new` to qualifying nodes on load.
Add `animation: glow-once 800ms ease-out` to the `.new` style. Use Cytoscape's
`overlay-opacity` animated via `ele.animate()` for a canvas-rendered glow.

**Desktop:** Full animation. **Mobile:** Respect `prefers-reduced-motion`.

### DL-2b: "N new since yesterday" badge

A small badge on the toolbar or near the view selector showing how many new entities
and edges appeared since the previous data load. Example: "🔵 3 new entities · 7 new edges"

Clicking the badge activates a temporary filter mode that dims everything except new items
(reuse the `.dimmed` / `.new` class system).

### DL-2c: Neighborhood fly-to with staggered reveal

When a user clicks a node and the neighborhood highlights, instead of instant dimming,
stagger the reveal: center node appears first (100ms), then direct neighbors fade in
(200ms), then edges draw in (300ms). Total animation: ~600ms. This creates a sense of
the graph "opening up" around the selected entity.

**Caution:** Must respect `prefers-reduced-motion`. Must not block interaction (use
`requestAnimationFrame`, not `setTimeout` chains). Desktop-only for V1 — mobile gets
instant reveal.

---

## DL-3: Guided Entry Point

**Priority:** Medium — addresses the "opens to a wall of nodes" first-impression problem.

**Problem:** The app opens to whichever view was last active (or trending by default).
For a new user or a returning user, the first 10 seconds are undirected: "here's a graph,
figure it out." There's no invitation to explore.

**Feature:**

On first load (or when a new data export is detected), show a brief "Today's Highlights"
overlay or card — not a modal, not a wizard. A card that appears in the top-left or
center of the graph for ~5 seconds (or until dismissed) showing:

- "3 new entities today: [Entity A], [Entity B], [Entity C]"
- "Fastest mover: [Entity X] (+2.3 velocity)"
- "[Entity Y] now connected to [Entity Z] (new bridge)"

Each item is clickable (fly-to-neighborhood). The card has a "Dismiss" / "×" button and
auto-fades after the timeout.

**Why this works:** It gives the user a **starting point** without forcing a flow. They
can ignore it and explore freely, or follow a thread. It transforms "here's a graph"
into "here's what's interesting in this graph."

**Implementation:**
- Data: reuse the same signals as DL-1 (What's Hot). The card is essentially a condensed
  version of the What's Hot list.
- Overlay: positioned absolutely over the graph, translucent background, auto-dismiss.
- Persistence: `localStorage` flag per export date to avoid re-showing on refresh.

**Desktop:** Card in top-left, sized ~300px wide. **Mobile:** Bottom sheet peek showing
top 2 items.

---

## DL-4: Contextual Empty States

**Priority:** Medium — the current "No graph data" message is the worst first impression.

**Problem:** When the graph is empty (no data, all filtered out, error), the message is
generic and unhelpful. It feels like something is broken.

**Target states:**

| Condition | Current message | Better message |
|-----------|----------------|----------------|
| No data loaded | "No graph data" | "No data yet. Run the pipeline to populate the graph, or load sample data." |
| All filtered out | "No graph data" | "All nodes are hidden by your current filters. Try widening the date range or enabling more entity types." + **Reset Filters** button |
| Network/load error | Error dialog | Fine as-is (already descriptive) |
| View has no qualifying nodes | "No graph data" | "No [trending/claim/etc.] nodes in the current date range. Try expanding to 30 or 90 days." |

**Implementation:** `web/js/graph.js` empty state handler needs to receive *why* the
graph is empty (no data vs. filtered out vs. view-specific) and render accordingly. The
filter-caused empty state should include a one-click reset.

---

## DL-5: Professional Toolbar Icons

**Priority:** Medium — the Unicode glyphs (`☀`, `☾`, `⚙`, `▣`, `↻`, `⬜`) render
inconsistently across platforms and signal "prototype."

**Target:** Replace all toolbar icon glyphs with a consistent icon set. Candidates:

| Icon set | License | Approach | Notes |
|----------|---------|----------|-------|
| Lucide | ISC (free) | Inline SVG or sprite | Fork of Feather, active maintenance, 1400+ icons |
| Heroicons | MIT (free) | Inline SVG | Tailwind team, 300+ icons, very clean |
| Phosphor | MIT (free) | Inline SVG or webfont | 7000+ icons, 6 weights |

**Recommendation:** Lucide — it has the right balance of completeness, visual weight,
and active maintenance. Inline SVG (not webfont) for best rendering control.

**Mapping:**

| Current glyph | Purpose | Lucide icon name |
|---------------|---------|-----------------|
| `+` | Zoom in | `zoom-in` |
| `−` | Zoom out | `zoom-out` |
| `⬜` | Fit to screen | `maximize-2` |
| `↻` | Re-layout | `refresh-cw` |
| `▣` | Minimap toggle | `map` |
| `☀` / `☾` | Theme toggle | `sun` / `moon` |
| `⚙` | Filters | `sliders-horizontal` |
| `?` | Help | `help-circle` |
| `☰` | Mobile menu | `menu` |
| `🔍` | Search | `search` |

**Implementation:** Download only the needed SVGs (~10 icons), inline them in the HTML
or load as a small sprite. No full icon font needed.

**Desktop-first note:** Icon sizing targets desktop (20×20px in 36–40px buttons). Mobile
scales up to 24×24px in 48px buttons as it already does.

---

## DL-6: App Title & Branding Placeholder

**Priority:** Medium — tied to upcoming branding decisions.

**Problem:** The app title ("AI Trend Graph") is descriptive but generic. The title
treatment in [polish-strategy.md](polish-strategy.md) (gradient text, display font) is
ready to implement but blocked on the actual brand name.

**Action items:**
1. Decide on the product name (separate from this doc — branding discussion)
2. Reserve space in the toolbar for a small logo mark (16–24px square) to the left of
   the title text
3. Implement the title treatment from polish-strategy.md § A0 once the name is decided
4. Ensure the title area supports a single-line name up to ~25 characters without
   toolbar reflow

**Placeholder approach:** Keep "AI Trend Graph" but apply the display font + subtle
treatment from polish-strategy.md now. Swap the text when branding is decided.

---

## DL-7: Cinematic Transitions

**Priority:** Low — nice-to-have once the above items land.

**Problem:** All state changes (view switch, panel open, filter apply) are functional
but flat. They happen correctly; they don't *feel* like anything.

**Items:**

### DL-7a: View switch crossfade

When switching views, fade the graph to 50% opacity (100ms), swap data, run layout,
fade back to 100% on `layoutstop` (200ms). Currently the graph vanishes and reappears.
See [polish-strategy.md](polish-strategy.md) § P1 for implementation details.

### DL-7b: Panel resize choreography

Defer `cy.resize()` until `transitionend` fires on the panel, so the graph content
doesn't snap while the panel is still sliding. See polish-strategy.md § P1.

### DL-7c: Search fly-to

When search finds matches and the user presses Enter, instead of instant `cy.fit()`,
use `cy.animate({ fit: { eles: matches, padding: 50 } }, { duration: 400 })` for a
smooth camera move.

---

## DL-8: Domain Mini-Themes

**Priority:** Low — visual polish that adds personality per domain.

**Problem:** All domains share the same blue accent color for panel borders,
buttons, and highlights. This misses an opportunity to reinforce domain identity
visually. A film/entertainment domain could feel warmer (reds, oranges), while
a biosafety domain could feel more clinical (teals, whites).

**Approach:** Extend the existing token system with domain-scoped CSS custom
properties. Each domain's `web/data/domains/<slug>.json` would provide an
accent palette that overrides the default blue tokens.

**Examples:**
- **Film:** Flame gradient border (already prototyped on hot panel), warm
  orange accent, gold highlights
- **Biosafety:** Teal/green accent, clinical whites, red for select agents
- **AI:** Keep default blue (technical, neutral)

**Implementation:**
- Add `accentColors` to domain JSON config: `{ primary, secondary, gradient }`
- `loadDomainConfig()` in `app.js` already injects `--color-{type}` vars —
  extend to inject `--color-accent`, `--color-accent-secondary`
- Panel borders, toolbar active states, and hot-panel flame border all read
  from these tokens
- Fallback to current blue when domain config doesn't specify accents

**Files likely affected:** Domain JSON configs, `web/js/app.js`
(`loadDomainConfig`), `web/css/tokens.css` (accent variable declarations),
`web/css/components/panel.css` (accent references)

---

## Design Decisions Log

Decisions made during planning that constrain future work:

| Decision | Rationale | Date |
|----------|-----------|------|
| Desktop-first, always | Desktop is the primary use case. Mobile is a simplified adaptation, never the design driver. | 2026-02-27 |
| All nodes are circles | Different shapes create visual noise ("afflicted flowchart"). Color-by-type is sufficient encoding. | 2026-02-27 |
| Touch targets are done | Mobile already enforces 48px minimums with `touch-action: manipulation`. Cross-OS inconsistency makes further touch refinement unreliable. | 2026-02-27 |
| Separate delight doc | Keep this doc small and focused. Aesthetic mechanics live in polish-strategy.md. Functional gaps live in v1-gaps.md. | 2026-02-27 |

---

## Sequencing

```
DL-1 (What's Hot)     DL-2 (Discovery)     DL-3 (Entry Point)    DL-4–7 (Polish)
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐
│ Velocity delta   │  │ New-entity glow  │  │ Today's card     │  │ Empty states   │
│   computation    │  │ "N new" badge    │  │ Auto-dismiss     │  │ Toolbar icons  │
│ Ranked list UI   │──▶│ Staggered reveal │──▶│ localStorage     │──▶│ Branding       │
│ Fly-to-neighbor  │  │                  │  │   per export     │  │ Transitions    │
│ Keyboard shortcut│  │                  │  │                  │  │                │
└──────────────────┘  └──────────────────┘  └──────────────────┘  └────────────────┘
```

**Why this order:**
- DL-1 provides the data signals that DL-2 and DL-3 also need
- DL-2 makes the graph feel alive (prerequisite for DL-3 to feel earned)
- DL-3 ties DL-1 + DL-2 together into a first-load experience
- DL-4–7 are independent polish items that can land in any order
