# Test Plan

Manual QA checklist for each sprint. Run before merging. Add new sections as sprints complete.

Each item is a discrete check that can be verified independently. Mark `[x]` when passing.

---

## How to run

1. Serve the web client: `python3 -m http.server 8080 --directory web/`
2. Open `http://localhost:8080` in a desktop browser (Chrome or Firefox)
3. Work through the checklist for any sprint whose code changed
4. For dark mode checks: click the ☀ toolbar button to toggle
5. For `prefers-reduced-motion`: DevTools → Rendering → Emulate CSS media feature

---

## Sprint 1 — Dead Code Wiring

### 1.1 `.new` class applied to recent nodes
- [ ] Nodes with `firstSeen` within the last 7 days have a green double-border
- [ ] Nodes older than 7 days do not have the green border
- [ ] After switching views, the `.new` class is re-applied to the new graph data

### 1.2 Double-click expands neighbors
- [ ] Double-clicking a node reveals any hidden (filtered-out) neighboring nodes
- [ ] After reveal, the view zooms/fits to the expanded neighborhood
- [ ] Double-clicking the canvas background fits all visible nodes

### 1.3 `prefers-reduced-motion` respected
- [ ] With "Emulate prefers-reduced-motion: reduce" enabled, layout runs without animation (nodes snap into place)
- [ ] `cy.animate()` zoom-to-neighborhood on double-click: instant, no slide
- [ ] `fitGraph()` on double-click background: instant
- [ ] CSS panel slide transitions are suppressed (handled by `reset.css` media query)

### 1.4 Hypothesis edges default-off
- [ ] On load, the "Hypothesis" checkbox in Relationship Kind is unchecked
- [ ] Hypothesis edges are hidden by default
- [ ] Checking "Hypothesis" and applying filters shows hypothesis edges
- [ ] Resetting filters leaves hypothesis unchecked

---

## Sprint 2 — Aesthetic Identity (CSS Foundation)

### 2.1 Typography
- [ ] App title uses Inter font (check DevTools → Computed → font-family)
- [ ] Filter panel section headers (Date Range, Entity Types, etc.) use Inter
- [ ] Tooltip header uses Inter
- [ ] Body text still uses system font stack (`--font-sans`), not Inter

### 2.2 App title
- [ ] Title renders with blue-to-purple gradient text (not plain black/white)
- [ ] Title is bold, 24px, with subtle letter-spacing
- [ ] **Dark mode:** gradient still visible against dark toolbar background

### 2.3 Toolbar breathing room
- [ ] Toolbar background is slightly off-white (tinted, not pure white) in light mode
- [ ] Toolbar background is slightly elevated in dark mode
- [ ] A thin vertical divider appears between the title and the View selector
- [ ] A thin vertical divider appears between the View selector group and the Date group
- [ ] Groups feel less dense than before (wider gap between them)

### 2.4 Filter panel — color dots + type grouping
- [ ] Entity types are grouped into 4 sections: People & Organizations / Technology / Knowledge / Context
- [ ] Each type has a small colored dot matching the node color on the graph
  - Org → blue, Model → purple, Paper → green, Event → red, etc.
- [ ] **Quick-filter pills:** "All" enables all available types
- [ ] **Quick-filter pills:** "Tech" enables only Model, Tool, Tech, Dataset, Benchmark
- [ ] **Quick-filter pills:** "Orgs" enables only Org, Person, Program
- [ ] **Quick-filter pills:** "None" disables all types
- [ ] The existing All / None text links below the list still work
- [ ] **Dark mode:** color dots are visible against the dark panel background

### 2.5 Detail panel stats grid
- [ ] Opening a node's detail panel shows the 2-column activity grid (7d/30d mentions, connections, velocity)
- [ ] No inline `style="grid-template-columns:..."` present in the rendered DOM (verify in DevTools)

---

## Sprint 3 — Toolbar Icons

### 3.1 / 3.2 Desktop icons (Lucide SVGs, 20×20)
- [ ] Zoom in button shows a magnifying glass with a `+` inside (not `+` text)
- [ ] Zoom out button shows a magnifying glass with a `−` inside
- [ ] Fit to view button shows four corner arrows (maximize-2)
- [ ] Re-layout button shows a circular clockwise arrow (refresh-cw)
- [ ] Minimap toggle button shows a folded map icon
- [ ] Theme toggle button shows a **sun** in light mode and a **moon** in dark mode (no text glyph)
- [ ] Toggling theme swaps the icon without a page reload or JS error
- [ ] Filter button shows a three-row horizontal sliders icon
- [ ] Help button shows a circle with a question mark inside
- [ ] All icons render in `currentColor` — they match the button text color in both themes
- [ ] DevTools → Elements: no Unicode characters (`☀`, `☾`, `⚙`, `▣`, `↻`, `⬜`, `?`) visible inside any `.btn-icon`
- [ ] `aria-label` is present on every toolbar button

### 3.3 Mobile icons (Lucide SVGs, 24×24)
- [ ] Mobile menu button (hamburger) shows three horizontal lines
- [ ] Mobile search button shows a magnifying glass
- [ ] Mobile filter button shows the same sliders-horizontal icon
- [ ] Mobile help button shows help-circle
- [ ] Mobile theme toggle in the hamburger menu shows sun/moon correctly
- [ ] All mobile icons are 24×24 (larger touch targets than desktop 20×20)

---

## Sprint 4 — Graph Canvas Polish

### 4.1 Node depth and texture
- [ ] All nodes have a **2.5px border** in their type color (20% darker than fill), not flat gray
- [ ] All nodes have a subtle drop shadow (faint underlay visible when zoomed in)
- [ ] Nodes with `velocity > 2` show a **colored halo** (type-colored, low opacity) extending beyond the node circle
- [ ] Standard nodes do **not** show a halo
- [ ] Selected nodes show an **8px blue glow** (`overlay-padding: 8`)
- [ ] DevTools console: `getCytoscapeStyles()` returns a `node[velocity > 2]` entry

### 4.2 Canvas dot-grid
- [ ] The graph canvas shows a **subtle 24px dot grid** in both light and dark mode
- [ ] Light mode: dots are gray-200 (`#E5E7EB`); dark mode: dots are gray-700 (`#374151`)
- [ ] Dot grid does not interfere with node/edge rendering at any zoom level
- [ ] Grid is present on initial load without needing to toggle theme

### 4.3 Edge arrow refinement
- [ ] Edges with `confidence < 0.5` have a **smaller arrowhead** (scale 0.6 vs 0.8)
- [ ] Hovering an edge shows the **relation type label** (e.g. `USES_TECH`) centered on the edge
- [ ] Edge label disappears when the cursor leaves
- [ ] Edge label has a light background pill so it reads over other elements
- [ ] Label rotates with edge direction (`text-rotation: autorotate`)

---

## Regression Checks (run after any sprint)

- [ ] **Open DevTools console before loading** — zero errors on initial page load (a JS SyntaxError here silences the entire app)
- [ ] All four views load without console errors: Trending, Claims, Mentions, Dependencies
- [ ] Search highlights matching nodes and dims others
- [ ] Filter panel opens and closes
- [ ] Confidence slider adjusts visible edges
- [ ] Date preset buttons (7d / 30d / 90d / All) update the graph
- [ ] Dark mode toggle switches theme cleanly
- [ ] Minimap toggle shows/hides navigator
- [ ] Re-layout button re-runs layout without errors
- [ ] Zoom in / out / fit buttons work
