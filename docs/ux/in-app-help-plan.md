# In-App User Documentation — Implementation Plan

This is a structure-only outline for a Sonnet-powered session to implement.
No content is included — just the UI mechanics and topic skeleton.

---

## Part 1: UI Structure

### Entry Point

- **Help button** in toolbar-right (the `?` icon area), next to existing controls
- Keyboard shortcut: `?` key (when search is not focused)
- First-visit: auto-open help panel with a dismissible "welcome" card

### Panel Behavior

- **Slide-in panel** from the right side (reuses the same slot as node-detail panel)
- Panel width: ~350px (same as detail panel)
- Mutually exclusive with detail panel — opening help closes detail and vice versa
- Close via: X button, Escape key, clicking outside, or `?` again
- `cy.resize()` on open/close (same pattern as evidence panel)

### Panel Internal Layout

```
+----------------------------------+
| [X]  Help           [?] Search   |
+----------------------------------+
| [Tab: Quick Start] [Tab: Topics] |
+----------------------------------+
|                                  |
|  (content area — scrollable)     |
|                                  |
|                                  |
+----------------------------------+
```

- **Two tabs** inside the panel:
  1. **Quick Start** — single-page onboarding walkthrough
  2. **Topics** — accordion-style expandable sections

### Topic Navigation

- Accordion sections within the Topics tab
- Each section expands inline (no separate page/route)
- Sections can link to each other via anchor IDs
- Optional: context-sensitive — clicking `?` while a node is selected opens
  the "Reading the Graph" section; clicking while filter panel is open opens
  "Filtering"

### Visual Approach

- Same styling as existing panels (reuse panel CSS variables)
- Code/shortcut references in `<kbd>` tags
- Small inline diagrams via Unicode or simple SVG where needed
- No images in V1 (keeps it lightweight and easy to maintain)

---

## Part 2: Content Outline

### Tab 1: Quick Start

```
1. What am I looking at?
   - One sentence: "A knowledge graph of AI trends extracted from news and research"
   - Explain: nodes = entities, edges = relationships, size = activity

2. Basic navigation
   - Pan: click + drag background
   - Zoom: scroll wheel
   - Select: click a node
   - Deselect: click background or press Escape

3. Try it now (interactive prompts)
   - "Click any node to see its details →"
   - "Type a name in the search box →"
   - "Switch to Claims view using the dropdown →"

4. Keyboard shortcuts (compact table)
   - / = focus search
   - Escape = clear selection / close panel
   - Arrow keys = navigate between nodes
   - ? = toggle this help panel
   - +/- = zoom in/out
```

### Tab 2: Topics (Accordion Sections)

```
A. Views
   - What each view shows (trending, claims, mentions, dependencies)
   - When to use which view
   - What "trending" means (velocity + novelty scoring)

B. Reading the Graph
   - Node size = velocity/activity level
   - Node color = entity type (with legend/palette reference)
   - Node opacity = recency (fades as entity ages)
   - Edge style: solid = asserted, dashed = inferred, dotted = hypothesis
   - Edge thickness = confidence score
   - Edge color: gray = default, green = new (<7 days)

C. Interacting with Nodes
   - Click = select + highlight neighborhood
   - What the detail panel shows
   - Expanding neighbors (if implemented)
   - What "dimmed" nodes mean

D. Interacting with Edges
   - Click = view evidence panel
   - What evidence snippets are
   - Confidence scores explained
   - Asserted vs inferred vs hypothesis

E. Search
   - Searches node labels and aliases
   - Enter key zooms to matches
   - Clear with X button or Escape
   - Dimmed nodes = non-matches

F. Filtering
   - Entity type checkboxes
   - Confidence threshold slider
   - Date range presets (7d / 30d / 90d / All)
   - Kind toggles (asserted / inferred / hypothesis)
   - Filters combine (AND logic)

G. Data Tiers (if relevant to end users; may be dev-only)
   - What the Data dropdown controls
   - Dataset sizes and what they represent

H. Glossary
   - Entity types: Org, Person, Model, Tool, Dataset, Benchmark, Tech, Topic, etc.
   - Relationship kinds: asserted, inferred, hypothesis
   - Velocity, novelty, confidence
   - firstSeen / lastSeen
```

---

## Part 3: Files to Create

```
web/
  js/help.js          — Panel open/close, tab switching, accordion logic,
                        context-sensitive opening, keyboard shortcut
  css/components/
    help-panel.css    — Panel layout, accordion styles, kbd styling
  help/
    content.js        — Exported object/map of section content (HTML strings
                        or template literals). Keeping content in JS avoids
                        extra fetch requests for a static site.
```

Files to modify:
```
web/index.html        — Help panel HTML skeleton, help button in toolbar
web/js/app.js         — Wire help button, register ? shortcut
web/css/main.css      — Import help-panel.css (if not already auto-loaded)
```

---

## Part 4: Implementation Notes for Sonnet Session

- Reuse existing panel patterns from `panels.js` for open/close/resize
- Content should be plain HTML strings — no markdown parser needed
- Accordion can be pure CSS (`details`/`summary` elements) or lightweight JS
- The `<details>` HTML element is recommended — semantic, accessible, no JS needed
- Keep help content co-located in one file for easy editing
- Context-sensitive help is a nice-to-have; basic panel is the priority
- Test with screen reader: panel should announce when opened, sections should
  be navigable with arrow keys
