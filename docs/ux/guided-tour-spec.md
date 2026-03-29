# Guided Tour — Design Spec

**Status:** Draft
**Date:** 2026-03-28
**Related:** Sprint 10 (DL-3), calendar task `tour-sample-data-20260325`

## Overview

A self-guided, 8-step product tour for first-time users. Uses **Driver.js** for
the spotlight/popover UI layer and custom orchestration code to operate the app
(fly to nodes, open panels, switch views) between steps.

**Two-layer model:**
- **Driver.js** — dims page, spotlights a DOM element, shows a popover with text
- **Tour script** — calls Cytoscape and app functions to manipulate the graph
  between steps (fly-to, select, open panels). Uses Driver.js `onHighlightStarted`
  hooks to trigger app actions before the spotlight lands.

**Trigger:** First load with no `localStorage` tour-completed flag, OR a "Take
the Tour" button in the help panel. Tour can be dismissed at any step.

---

## Tour Stops

Each stop defines: what the user sees, what the tour script does behind the
scenes, which DOM element Driver.js highlights, and what the sample data must
contain to make the stop work.

---

### Stop 1: "Welcome — This is a knowledge graph"

**Spotlight:** `#cy` (the full graph canvas)
**Script action:** None (graph is already loaded with trending view)
**Popover:**
> You're looking at a live knowledge graph — entities connected by
> relationships extracted from real sources. Nodes are sized by how
> fast they're trending.

**Sample data requirement:** The trending view should load with 15–25 nodes
and visible clusters. Not too sparse (feels empty), not too dense (feels
overwhelming). At least 2 visually distinct clusters with a bridge entity
connecting them.

---

### Stop 2: "Entities are the building blocks"

**Spotlight:** `#cy` (canvas, but camera has moved)
**Script action:**
1. `cy.animate()` — fly to a high-degree Org node (e.g., `org:apex-studios`)
2. Brief pause (400ms) for the animation to land

**Popover:**
> Each node is an entity — an organization, person, tool, or concept.
> The color tells you the type. The size tells you how fast it's trending.
> This one is Apex Studios — it's connected to many other entities.

**Sample data requirement:** One Org node with degree ≥ 6, high velocity,
and connections to at least 3 different entity types. Needs a recognizable
name (not a real company — sample data should be fictional to avoid confusion).

---

### Stop 3: "Click a node to see its story"

**Spotlight:** `#detail-panel`
**Script action:**
1. Select the Org node from Stop 2 → `openNodeDetailPanel(node)`
2. Detail panel opens with bounce animation
3. Driver.js highlights the panel after it settles (350ms delay)

**Popover:**
> The detail panel shows everything we know: when it first appeared,
> how active it is, and why it's trending. The narrative is generated
> by AI from the underlying evidence.

**Sample data requirement:** The spotlight node must have:
- `firstSeen` and `lastSeen` at least 7 days apart
- `mentionCount7d` ≥ 5 and `mentionCount30d` ≥ 15
- `velocity` > 1.5 (visibly "hot")
- `narrative` populated (e.g., "Apex Studios is trending due to its
  announcement of a new production facility and three partnership deals.")
- At least 4 connected edges with different relation types

---

### Stop 4: "Relationships link back to real sources"

**Spotlight:** `#evidence-panel`
**Script action:**
1. From the detail panel's relationship list, programmatically select an
   edge with good evidence (e.g., a PARTNERED_WITH edge)
2. `openEvidencePanel(edge)` — evidence panel replaces detail (bounce in)
3. Driver.js highlights evidence panel

**Popover:**
> Every relationship links back to the source document where it was found.
> You can see the exact snippet, the publication date, and a link to the
> original article. Nothing is asserted without evidence.

**Sample data requirement:** The selected edge must have:
- `kind: "asserted"`
- `confidence` ≥ 0.80
- At least 1 evidence entry with `title`, `source`, `published`, `snippet`
  (≤200 chars), and `url`
- The snippet should be a compelling, readable quote

---

### Stop 5: "What's Hot tells you where to look"

**Spotlight:** `#hot-panel`
**Script action:**
1. `toggleHotPanel()` — hot panel replaces evidence (bounce in)
2. Driver.js highlights hot panel

**Popover:**
> The What's Hot list ranks entities by velocity — how quickly they're
> gaining attention. Each entry includes a narrative explaining WHY it's
> trending. Click any item to fly to it on the graph.

**Sample data requirement:** At least 5 trending entities with:
- Varying velocity values (top entity > 3.0, bottom entity ~1.2)
- Narratives populated for at least the top 3
- At least one entity with `novelty` > 0.7 (newly appeared)
- Mix of entity types (Org, Person, Tool, Topic)

---

### Stop 6: "Filter to focus"

**Spotlight:** `#filter-panel`
**Script action:**
1. Close hot panel
2. Open the filter panel (right side) if collapsed
3. Driver.js highlights it

**Popover:**
> Use filters to narrow the graph by entity type, date range, or
> confidence level. Uncheck a type to hide those nodes. Drag the
> confidence slider to show only high-certainty relationships.

**Sample data requirement:** No special data requirements — the filter panel
is populated from whatever entity types exist in the graph. But the sample
data should include at least 4 different entity types so the checkboxes
look populated.

---

### Stop 7: "Switch views to change the lens"

**Spotlight:** The view-switcher buttons in the toolbar
**Script action:**
1. Close filter panel
2. Switch to the `claims` view via the view buttons
3. Brief pause for layout animation
4. Driver.js highlights the view-switcher toolbar group

**Popover:**
> Four views show different slices of the same data. **Trending** is your
> home base. **Claims** shows asserted relationships. **Mentions** shows
> co-occurrence. **Dependencies** shows tech stacks. Switch back to
> Trending when you're done exploring.

**Sample data requirement:** The claims view should look visually distinct
from trending — more edges, different layout density. Requires the sample
data to populate all four view JSON files with the same entity set but
different edge subsets.

---

### Stop 8: "You're ready — start exploring"

**Spotlight:** `#cy` (back to full canvas, trending view restored)
**Script action:**
1. Switch back to trending view
2. `cy.fit()` to show full graph
3. Close all panels

**Popover:**
> That's it! You're looking at sample data — feel free to click around
> and experiment. When you're ready for real data, hit the button below.
>
> **[Switch to Live Data]** · **[Keep Exploring]**

**Sample data requirement:** None beyond what previous stops require.

---

## Post-Tour Experience

The tour ends but the user stays in the sample dataset. This is intentional —
new users need a safe space to experiment without worrying about "breaking"
anything or getting lost in unfamiliar data.

### Sample data indicator

While viewing sample data, a persistent but unobtrusive banner appears at the
top of the graph canvas (or bottom of the toolbar):

```
📋 You're viewing sample data  ·  [Switch to live data →]  ·  [Retake tour]
```

- **Subtle styling:** muted background, small text, dismissible but reappears on
  next load if still on sample data
- The banner is driven by the `meta.isSample` flag in the loaded JSON
- "Switch to live data" navigates to `?domain=film` (or whatever the default
  domain is) — a page navigation, not a reload-in-place, so the URL is clean
- "Retake tour" resets `localStorage` tour flag and restarts

### Lifecycle

```
First visit (no localStorage flag)
  │
  ├─ Sample data auto-loads
  ├─ Tour auto-starts (can be skipped at any step)
  │
  ▼
Tour ends → user stays in sample data
  │
  ├─ Sample data banner visible
  ├─ User explores freely
  │
  ▼
User clicks "Switch to live data"
  │
  ├─ Navigates to ?domain=<default>
  ├─ localStorage: tour-completed = true
  ├─ Future visits go straight to live data
  │
  ▼
Returning user (tour-completed flag set)
  │
  ├─ Live data loads directly
  ├─ No banner, no tour
  └─ "Take the Tour" in help panel resets to sample data + tour
```

### Edge cases

- **User closes tab during tour:** Next visit, `tour-completed` is not set →
  sample data loads again, tour restarts from Step 1.
- **User dismisses tour at Step 3:** Tour ends, but they stay in sample data
  with the banner. They can retake or switch to live whenever ready.
- **User bookmarks the sample data URL:** Works fine — sample data loads,
  banner appears, "Switch to live data" is always available.
- **No live data available yet:** "Switch to live data" shows the empty state
  message ("No data yet. Run the pipeline to populate the graph."). This is
  expected for users who haven't run the pipeline.

---

## Sample Data Requirements Summary

The tour needs a single cohesive fictional dataset that satisfies all stops:

| Requirement | Min | Used in |
|-------------|-----|---------|
| Total nodes (trending view) | 15–25 | Stop 1 |
| Visible clusters | 2+ with bridge | Stop 1 |
| High-degree Org node | degree ≥ 6, velocity > 1.5 | Stop 2, 3 |
| Node with narrative | 1+ with full narrative text | Stop 3 |
| Edge with evidence | 1+ with snippet, source, URL | Stop 4 |
| Trending entities with narratives | 5+ (top 3 with narratives) | Stop 5 |
| Entity types represented | 4+ distinct types | Stop 6 |
| All four views populated | trending, claims, mentions, dependencies | Stop 7 |

### Fictional dataset concept

To avoid confusion with real-world entities, the sample data should use a
**fictional but plausible** scenario. Proposal:

**Domain:** A fictional AI startup ecosystem (close enough to the real AI domain
that the entity types and relationships feel natural)

**Cast:**
| Entity | Type | Role in tour |
|--------|------|-------------|
| Apex Studios | Org | High-degree spotlight node (Stop 2–3) |
| Nova Labs | Org | Secondary cluster anchor |
| Dr. Mira Chen | Person | Bridge between clusters |
| Helios | Model | Trending fast — just launched |
| SynthBench | Benchmark | Connected to Helios via EVALUATED_ON |
| NeuralForge | Tool | Used by both orgs (USES_TECH) |
| Project Titan | Program | Recently announced, high novelty |
| Frontier Safety | Topic | Cross-cutting topic connecting clusters |

**Story the data tells:**
- Apex Studios just announced Project Titan, a large-scale model training program
- Dr. Mira Chen left Nova Labs to join Apex (bridge entity, HIRED relation)
- Helios (a model by Apex) was benchmarked on SynthBench, outperforming competitors
- Nova Labs responded by partnering with NeuralForge on a competing tool
- Frontier Safety is a topic connecting both clusters through regulatory mentions

This gives us: two clusters (Apex world, Nova world), a bridge entity (Dr. Chen),
a trending entity with narrative (Helios), edges with evidence (the PARTNERED_WITH
between Nova and NeuralForge), and enough entity types to populate the filter panel.

---

## Technical Integration

### Driver.js setup
```html
<!-- CDN in index.html, after Cytoscape -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/driver.js/dist/driver.css">
<script src="https://cdn.jsdelivr.net/npm/driver.js/dist/driver.js.iife.js"></script>
```

### Tour script
New file: `web/js/tour.js`

```javascript
function startTour() {
  const driver = window.driver.js.driver;

  const tour = driver({
    showProgress: true,
    animate: true,
    smoothScroll: true,
    stagePadding: 8,
    stageRadius: 8,
    allowClose: true,
    onDestroyed: () => {
      localStorage.setItem('tour-completed', 'true');
    },
    steps: [
      {
        element: '#cy',
        popover: { title: 'Welcome', description: '...' }
      },
      {
        element: '#cy',
        popover: { title: 'Entities', description: '...' },
        onHighlightStarted: () => {
          // Fly to spotlight node
          const node = window.cy.getElementById('org:apex-studios');
          zoomToNode(node);
        }
      },
      {
        element: '#detail-panel',
        popover: { title: 'Node Details', description: '...' },
        onHighlightStarted: () => {
          const node = window.cy.getElementById('org:apex-studios');
          node.select();
          openNodeDetailPanel(node);
        }
      },
      // ... etc
    ]
  });

  tour.drive();
}
```

### Tour trigger logic
```javascript
// In app.js after graph loads:
if (!localStorage.getItem('tour-completed') && isSampleData()) {
  startTour();
}
```

### `isSampleData()` detection
The sample data JSON should include a flag in its `meta` block:
```json
{ "meta": { "isSample": true, "tourVersion": 1 } }
```

This prevents the tour from firing on real pipeline data.

---

## Open Questions

1. **Should the tour auto-start or require a click?** Decision: auto-start on
   sample data with a visible "Skip Tour" option at every step. User stays in
   sample data after the tour ends regardless — no pressure to complete it.

2. **Reduced motion:** Should the tour skip fly-to animations when
   `prefers-reduced-motion` is set? Driver.js respects it for its own animations;
   we'd need to check for our Cytoscape animations too.

3. **Mobile:** Driver.js works on mobile but our tour manipulates desktop panels.
   Defer mobile tour to after mobile panel architecture is settled.

4. **Tour versioning:** When new features are added, should the tour re-trigger?
   The `tourVersion` field in sample data meta + localStorage key like
   `tour-completed-v1` would handle this.

---

## Files Affected

| File | Change |
|------|--------|
| `web/js/tour.js` | New — tour step definitions + orchestration |
| `web/index.html` | Driver.js CDN tags, tour.js script tag |
| `web/js/app.js` | Auto-start logic after graph load |
| `web/data/sample/trending.json` | New — curated sample dataset |
| `web/data/sample/claims.json` | New — sample claims view |
| `web/data/sample/mentions.json` | New — sample mentions view |
| `web/data/sample/dependencies.json` | New — sample dependencies view |
| Help panel | "Take the Tour" button |
