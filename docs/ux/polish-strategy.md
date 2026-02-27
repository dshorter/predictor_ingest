# Polish Strategy ("Glow Up")

Visual, aesthetic, and interaction refinements that take the UI from "competent developer
tool" to "something someone would want to show off."

**Prerequisite:** Complete [Phase 1 of gap remediation](gap-remediation-plan.md) first.
Dead code and wiring gaps should be settled before polishing. No point shining something
that's not fully connected.

---

## Honest Assessment

The architecture is strong. The token system is real, the component separation is clean,
the visual encoding carries real information. None of that needs a rescue.

But it **looks like any internal dashboard.** If you squint, it could be a Grafana panel
or a Jira dependency view. The bones are there; the soul isn't. Specifically:

1. **No visual identity.** The toolbar is a flat gray bar with system fonts. Nothing says
   "this is a knowledge graph about AI trends." It could be anything.
2. **Toolbar feels like a cockpit.** Dense row of small controls. Functional but
   overwhelming on first open.
3. **Typography is flat.** System font stack at uniform sizes. No element draws your eye.
   No hierarchy beyond "bold vs not bold."
4. **Filter panel is a wall of checkboxes.** 15 entity types, each a plain checkbox with
   text. Usable but not inviting. Doesn't leverage the color system it already has.
5. **Graph nodes are bare circles with text.** Flat color fill, thin border, label below.
   This is the default Cytoscape look. No depth, no texture, no shape differentiation.
6. **"Built by engineers for engineers."** Everything is there. Nothing is delightful.
   Nobody opens it and thinks "I want to explore this."

**The goal isn't decoration. It's signal clarity + visual confidence.** A user should
open this and immediately feel: *this is a serious tool that respects my attention AND
looks like someone cared about it.*

Reference calibration: Linear, Figma, Raycast, Vercel Dashboard. Clean, confident,
information-dense but not cluttered.

---

## A0 — Aesthetic Identity (do this first within polish)

These changes address the "no visual identity" and "could be any dashboard" critique.
They're the highest-leverage aesthetic changes because they're what a user perceives
in the first 3 seconds.

### Typography upgrade

**Current:** `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto...` for everything.
Every text element looks the same weight.

**Target:** Introduce a single accent/display font for headings and the app title.
Body text stays as system stack (fast, readable).

**Concrete options (all free, CDN-available):**
- **Inter** — modern, slightly geometric, excellent at small sizes. Already the default
  for Linear, Vercel, and most modern dashboards. Safe choice.
- **Geist Sans** — Vercel's custom font. Slightly more personality than Inter. Narrower.
- **Plus Jakarta Sans** — warmer, more approachable. Good for titles at larger sizes.

**Approach:**
1. Add a single `<link>` for the chosen font (Google Fonts CDN or self-host)
2. Define `--font-display` in `tokens.css`
3. Apply to: `.app-title`, panel `h2`/`h3` headers, tooltip headers, stat labels
4. Body text stays as `--font-sans` (system stack)
5. Use `--font-mono` more aggressively for data values (counts, dates, percentages)

**Impact on current code:**
- `tokens.css`: add `--font-display` variable
- `toolbar.css`: `.app-title` uses `--font-display`
- `panel.css`: section headers use `--font-display`
- `index.html`: one `<link>` tag

**Why it matters:** Typography is the single highest-leverage visual change. One font
swap on headings transforms "generic dashboard" into "designed product."

**Effort:** ~20 minutes

### App title presence

**Current:** `.app-title` is `font-size: 18px; font-weight: 600`. Plain text in a bar.

**Target:** Make the title an anchor point:
- Use the display font at `--text-lg` or `--text-xl`
- Add subtle letter-spacing (`0.02em`)
- Consider a small visual mark: a colored dot, a graph icon, or a subtle gradient text
- The title should communicate "knowledge graph" without being heavy-handed

**Example (subtle):**
```css
.app-title {
  font-family: var(--font-display);
  font-size: var(--text-xl);
  font-weight: var(--weight-bold);
  letter-spacing: 0.02em;
  background: linear-gradient(135deg, var(--blue-600), var(--color-model));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
```

**Effort:** ~10 lines CSS

### Toolbar breathing room

**Current:** All controls packed in a single row with `gap: 12px`. Dense.

**Target:** Visual grouping with separators and hierarchy:
1. Add thin vertical dividers (`border-left: 1px solid var(--gray-200)`) between
   logical groups: [title | view+date | search | zoom+controls]
2. Increase gap between groups to `--space-5` or `--space-6`
3. Consider a subtle background tint for the toolbar (`var(--gray-50)` in light mode,
   slightly elevated from white) to give it visual weight
4. Toolbar controls that are secondary (zoom in/out, minimap toggle) can be slightly
   smaller or lower-contrast to reduce perceived density

**Effort:** ~30 lines CSS

### Filter panel: color dots + grouping

**Current:** 15 checkboxes in a flat list. Each is `☐ Org`, `☐ Person`, etc.

**Target:**
1. Add a colored dot (or small circle swatch) next to each entity type, matching the
   node color. This creates an immediate visual link: "the purple dot here = the purple
   nodes on the graph."
2. Group types into categories:
   - **People & Organizations:** Org, Person, Program
   - **Technology:** Model, Tool, Tech, Dataset, Benchmark
   - **Knowledge:** Paper, Repo, Topic
   - **Context:** Document, Event, Location, Other
3. Each group gets a label + collapsible section (already supported by `filter-section`)
4. Add a row of "Quick filter" pill buttons at the top: `All`, `Tech`, `Orgs`, `None`

**Implementation:**
```css
.entity-type-dot {
  width: 10px;
  height: 10px;
  border-radius: var(--radius-full);
  display: inline-block;
  margin-right: var(--space-1);
}
```

```javascript
// In filter population
checkbox.insertAdjacentHTML('afterend',
  `<span class="entity-type-dot" style="background: ${nodeTypeColors[type]}"></span>`
);
```

**Effort:** ~40 lines (CSS + JS)

---

## A1 — Graph Visual Richness (the big perception shift)

The graph canvas is where users spend 90% of their time. This is where "bare circles"
becomes "something I want to explore."

### Node shape differentiation

**Current:** Every node type is a circle. The only differentiator is color.

**Target:** Map entity types to Cytoscape.js supported shapes:

| Type | Shape | Rationale |
|------|-------|-----------|
| Org | round-rectangle | Institutional, structured |
| Person | ellipse | Human, organic |
| Model | diamond | Technical artifact, precision |
| Tool | round-pentagon | Utility, multi-faceted |
| Dataset | barrel | Storage, volume |
| Paper | round-tag | Document with pointer |
| Repo | octagon | Code (GitHub association) |
| Tech | hexagon | Technical, modular |
| Topic | round-rectangle | Container of ideas |
| Others | ellipse | Default organic |

**Why it matters:** Shape + color is a much stronger visual encoding than color alone.
Users can distinguish types even in dense clusters where colors blur together.

**Cytoscape supports:** `ellipse`, `triangle`, `round-triangle`, `rectangle`,
`round-rectangle`, `bottom-round-rectangle`, `cut-rectangle`, `barrel`, `rhomboid`,
`diamond`, `round-diamond`, `pentagon`, `round-pentagon`, `hexagon`, `round-hexagon`,
`concave-hexagon`, `heptagon`, `round-heptagon`, `octagon`, `round-octagon`, `star`,
`tag`, `round-tag`, `vee`

**Implementation:** In `styles.js`, add shape mapping:
```javascript
function getNodeShape(type) {
  const shapes = {
    'Org': 'round-rectangle',
    'Person': 'ellipse',
    'Model': 'diamond',
    'Tool': 'round-pentagon',
    'Dataset': 'barrel',
    'Paper': 'round-tag',
    'Repo': 'octagon',
    'Tech': 'hexagon',
    'Topic': 'round-rectangle',
    // defaults
  };
  return shapes[type] || 'ellipse';
}
```

Then in the base node style:
```javascript
'shape': function(ele) { return getNodeShape(ele.data('type')); }
```

**Effort:** ~25 lines. Zero dependencies. Massive perceptual impact.

### Node depth and texture

**Current:** Flat fill + thin border. Looks 2D.

**Target:** Add subtle depth cues:
1. **Border refinement:** Slightly thicker border (2.5px), slightly darker than fill
   (computed as 20% darker variant). This creates implicit depth.
2. **Background gradient (if supported):** Cytoscape doesn't natively support gradients
   on node backgrounds, BUT it supports `background-opacity` layered with
   `underlay-color` and `underlay-opacity` — which can simulate a shadow/depth effect.
3. **Selected node glow:** Use `overlay-color` + `overlay-opacity` + `overlay-padding`
   to create a visible glow around selected/hovered nodes.
4. **High-velocity halo:** Nodes with velocity > 2 get a subtle underlay halo:
   ```javascript
   'underlay-color': function(ele) {
     return ele.data('velocity') > 2
       ? nodeTypeColors[ele.data('type')]
       : 'transparent';
   },
   'underlay-opacity': 0.15,
   'underlay-padding': 8
   ```

**What NOT to do:**
- Don't use `background-image` with SVG data URIs (fragile, slow on large graphs)
- Don't try CSS-level node styling (Cytoscape renders on canvas, not DOM)
- Don't add pulsing animations (distracting, battery-draining)

**Effort:** ~30 lines in `styles.js`

### Canvas background

**Current:** Plain white (`#FFFFFF`) or dark (`#111827`). Nothing.

**Target:** A subtle dot grid or fine graph-paper pattern on the canvas background.
This is a small detail that makes the graph feel like it lives on a surface, not
floating in void.

**Implementation:** CSS background-image on `#cy`:
```css
#cy {
  background-image: radial-gradient(
    circle,
    var(--color-border-secondary) 1px,
    transparent 1px
  );
  background-size: 24px 24px;
}
```

Dark mode inverts to a very subtle lighter dot.

**Effort:** ~6 lines CSS. Instantly makes the canvas feel intentional.

### Edge arrow refinement

**Current:** Default triangle arrows, uniform gray.

**Target:**
- Slightly smaller arrow scale for low-confidence edges (0.6 vs 0.8)
- Edge label on hover (show relation type, e.g., "USES_TECH")
- Bezier curve style already exists — keep it

**Effort:** ~15 lines

---

## P1 — High Perceptual Impact (Interactions)

These address the "nothing is delightful" part of the critique — micro-interactions
that signal care.

### View switch transition

**Current:** Switching views (trending → claims) causes the graph to vanish and reappear
after a brief loading pause. No visual continuity.

**Target:** Smooth crossfade or opacity transition during the load-layout cycle.

**Approach:**
1. When view switch is triggered, fade the `#cy` container to 50% opacity (100ms)
2. Show a subtle inline spinner (not the full-screen overlay — that feels heavy)
3. Load new data, run layout
4. On `layoutstop`, fade `#cy` back to 100% (200ms)

**Why it matters:** View switching is one of the most frequent interactions. Every switch
currently feels like a page reload. A transition signals "same tool, different lens"
rather than "broken → loading → fixed."

**Files:** `web/js/app.js` (view switch handler), `web/css/graph/cytoscape.css` (transition)
**Effort:** ~30 lines

### Panel open/close animation smoothness

**Current:** Panels slide in with `transform: translateX()` and a 300ms transition.
The graph container resizes via CSS, which triggers Cytoscape to re-render.

**Observation:** The panel animations are fine. But the Cytoscape resize causes a visual
jump because `cy.resize()` is called synchronously. The graph content snaps to the new
bounds while the panel is still sliding.

**Target:** Defer `cy.resize()` until the panel transition completes (listen for
`transitionend`), or animate the Cytoscape container bounds in sync with the panel.

**Files:** `web/js/panels.js` (`updateCyContainer`), `web/js/app.js`
**Effort:** ~15 lines (add `transitionend` listener)

### Empty state design

**Current:** Empty state shows a centered icon + text message. Functional but generic.

**Target:** Add contextual guidance based on *why* it's empty:
- No data loaded → "Select a view to get started"
- All filtered out → "Your filters are hiding all nodes. Try widening your date range or enabling more entity types." + Reset Filters button
- Network error → Current error dialog (fine as-is)

**Files:** `web/js/graph.js` (empty state handler), `web/js/filter.js` (filter-caused empty)
**Effort:** ~40 lines

---

## P2 — Medium Perceptual Impact

### Detail panel inline styles → CSS classes

**Current:** The stats grid in the detail panel uses inline styles:
```javascript
`<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px">`
```

This breaks the "all styling via tokens" discipline that every other component follows.

**Target:** Extract to `.detail-stats-grid` class in `panel.css`:
```css
.detail-stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}
```

**Files:** `web/css/components/panel.css`, `web/js/panels.js`
**Effort:** ~10 lines

### Toolbar touch targets (desktop)

**Current:** Some toolbar buttons are 36×36px. The spec recommends ≥44×44px for
accessibility compliance (WCAG 2.5.5 Target Size).

**Assessment:** 36px is acceptable for desktop mouse interaction but fails the
accessibility spec. The mobile implementation correctly uses 48px.

**Target:** Increase `.btn-icon` to 40×40px minimum on desktop. Full 44px may crowd
the toolbar — test and decide.

**Files:** `web/css/components/button.css`
**Effort:** 1 line (change `width/height` on `.btn-icon`)

### Tooltip positioning edge cases

**Current:** Tooltips reposition to avoid viewport edges. But when a node is near
the bottom-right corner and both the detail panel (left) and filter panel (right)
are open, the available space can be very narrow.

**Target:** Account for open panel widths when computing available tooltip space.

**Files:** `web/js/tooltips.js` (positioning logic)
**Effort:** ~15 lines

### Search result count positioning

**Current:** Search result count ("5 nodes") is absolutely positioned inside the
search input. On narrow viewports or with long count text, it can overlap the
search text.

**Target:** Either:
- Move count below the input (small label)
- Or clip count to "5" instead of "5 nodes" when space is tight

**Files:** `web/css/components/toolbar.css`, `web/js/search.js`
**Effort:** ~10 lines

---

## P3 — Lower Priority Polish

### "What's New" temporal highlight mode

**Current:** The `.new` class exists for nodes. After Phase 1.1, it'll be auto-applied.
But there's no active toggle to "show me what changed."

**Target:** Add a toolbar toggle (or view preset) that:
1. Dims everything older than 7 days
2. Highlights new nodes with the green border
3. Highlights new edges
4. Shows a "What's New: 3 nodes, 5 edges" summary

This is a natural evolution after the `.new` class is wired (Phase 1.1).

**Files:** `web/js/app.js` (toggle), `web/js/filter.js` (temporal mode)
**Effort:** ~50 lines

### Loading skeleton for panels

**Current:** Panels show content immediately when opened (data is already in memory).
No loading state needed for current behavior.

**But:** If V2 adds lazy-loaded details (per `implementation.md`), panels will need
a loading state. A skeleton placeholder would look polished.

**Recommendation:** Skip for V1 unless panels start fetching data asynchronously.
Document as a V2 polish item.

### Minimap toggle animation

**Current:** Minimap shows/hides with opacity + translate. Acceptable.

**Could be nicer:** Scale from 0 at the corner (origin: bottom-right) for a more
natural "collapse into corner" feel. Very low priority.

### Dark mode transition

**Current:** Theme toggle is instant. All colors swap at once.

**Could be nicer:** A 200ms cross-fade on `background-color` and `color` transitions
on `<body>`. Most design-conscious apps do this. But it requires adding `transition`
to many elements, which can cause performance issues.

**Recommendation:** Skip unless it bothers users. The instant swap is fine.

---

## Sequencing

```
After Phase 1 gaps are closed:

A0 (aesthetic identity)   A1 (graph richness)      P1 (interactions)        P2+P3 (cleanup)
┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────┐    ┌─────────────┐
│ Typography upgrade   │ │ Node shape mapping   │ │ View transitions │    │ Inline CSS  │
│ App title presence   │ │ Node depth/texture   │ │ Panel resize     │    │ Touch target│
│ Toolbar breathing    │─▶│ Canvas dot grid      │─▶│   smoothness     │───▶│ Tooltip pos │
│ Filter color dots    │ │ Edge arrow refinement│ │ Contextual empty │    │ Search count│
│   + grouping         │ │ Velocity halo        │ │   states         │    │ What's New  │
└──────────────────────┘ └──────────────────────┘ └──────────────────┘    └─────────────┘
     ~2 sessions              ~2 sessions              ~2 sessions            ~1 session
```

**Total estimated sessions for A0 through P2:** ~7 focused sessions.

**Why A0 before A1:** Typography and toolbar changes affect every screen. Settle the
identity first, then enrich the graph. If you do A1 first, you'll be evaluating node
shapes against a toolbar that still looks generic — you can't judge the whole until
the frame is right.

**Why A1 before P1:** Node shapes and depth are what users stare at. View transitions
are nice but secondary to the primary visual artifact.

---

## What NOT to Polish

Explicit non-goals to avoid scope creep:

- **Don't add animations for their own sake.** Every transition must serve a
  purpose (continuity, orientation, feedback). No bouncing nodes.
- **Don't add a splash screen or onboarding wizard.** The help panel already
  exists and is comprehensive.
- **Don't use SVG background-image on nodes.** Fragile, slow on large graphs,
  not worth the maintenance cost for V1.
- **Don't add a custom color picker.** The token palette is intentional. Users
  shouldn't customize node colors — consistency is the point.
- **Don't chase "wow" screenshots at the expense of readability.** The graph
  should look good AND be readable at 9am on your second coffee. If depth cues
  or shape mapping reduces legibility, pull them back.
