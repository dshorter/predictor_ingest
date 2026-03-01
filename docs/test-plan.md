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
