# Mobile UI Implementation — Session Summary

**Date:** February 14, 2026
**Branch:** `claude/explore-mobile-ui-TeVHj`
**Status:** Implementation complete, ready for manual testing on real devices
**Commits:** 3 (plan exploration → date fix → full implementation)

---

## 1. What We Built

A standalone mobile UI at `web/mobile/` for the AI Trend Graph Cytoscape.js client. The mobile UI shares data files and core JS modules with the existing desktop UI but has its own HTML, CSS, and interaction layer optimized for touch devices.

### Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `web/mobile/index.html` | ~240 | Mobile HTML shell: compact toolbar, full-screen `#cy`, bottom sheet, filter modal, search overlay, hamburger menu |
| `web/mobile/css/mobile.css` | ~530 | All mobile styles: 48px touch targets, bottom sheet snap points, search overlay, hamburger menu, filter modal, badges, overlays |
| `web/mobile/js/app-mobile.js` | ~350 | Mobile init, event handlers (tap/dbltap/long-press), view switching, theme toggle, search/menu wiring |
| `web/mobile/js/panels-mobile.js` | ~280 | Bottom sheet content rendering (node detail, edge evidence accordion), filter modal wiring, navigation helpers |
| `web/mobile/js/touch.js` | ~190 | `BottomSheetTouch` class (swipe with momentum-based snapping) + `LongPressDetector` class |
| **Total new** | **~1,590** | |

### Files Modified

| File | Change |
|------|--------|
| `web/index.html` | Added 6-line mobile detection redirect at top of `<body>`. This is the **only** change to the desktop UI. |

### Shared Modules (imported via `../js/` and `../css/`, not copied)

- **CSS:** `tokens.css` (design tokens, dark mode), `reset.css`, `base.css`, `badge.css` (component badges)
- **JS:** `utils.js` (date formatting, HTML escaping, overlays), `styles.js` (Cytoscape visual encoding), `filter.js` (`GraphFilter` class), `search.js` (search + highlight), `layout.js` (fcose layout with ratio-scaling), `graph.js` (data loading, `initializeGraph()`, stats)

---

## 2. The Journey: Discussion → Planning → Implementation

### Phase 1: Discussion & Exploration (prior session)

The initial conversation explored whether the mobile UI should be:

- **(A) Responsive CSS on top of the existing desktop UI** — media queries, collapsible panels
- **(B) A separate standalone mobile page** — own HTML/CSS/JS, shares data and core logic

**Decision: Option B (separate standalone page).** Rationale:
1. The desktop UI's panel system (left sidebar detail, right sidebar filters, bottom evidence panel) fundamentally conflicts with mobile interaction patterns (bottom sheets, full-screen modals)
2. Adding responsive CSS would mean extensive `@media` overrides that would be fragile and hard to maintain
3. A separate page can share ~70% of the JS logic (data loading, graph init, filtering, layout, styles) while having its own interaction layer
4. Zero risk of desktop regression — the desktop HTML/CSS/JS is untouched except for a trivial redirect snippet

### Phase 2: Planning (plan.md, prior session)

A detailed implementation plan was written covering:

- **Best practices research** — touch target sizing (48px per Material Design 3), bottom sheet patterns (Google Maps-style 3-snap-point), viewport detection, passive event listeners, `touch-action: manipulation`
- **Architecture decisions** — what to share vs. build new, relative path strategy for imports
- **UI design** — ASCII wireframe of mobile layout, component-by-component comparison table (desktop vs. mobile)
- **Bottom sheet behavior spec** — peek (100px) / half (40vh) / full (85vh) snap points, CSS `transform: translateY()` implementation, momentum-based snap-to-nearest
- **Auto-detection strategy** — `matchMedia` + UA sniffing, `?desktop=1` escape hatch, works through ngrok
- **7-step implementation plan** with specific deliverables per step
- **Risk assessment** — 5 risks rated by likelihood with mitigations

### Phase 3: Pre-Implementation Validation (this session)

Before coding, we validated:

1. **Date accuracy** — The plan header said "Feb 2025" but should be "Feb 2026". Fixed.
2. **Best practices currency** — Web search confirmed all practices in the plan are still current for 2026:
   - 48px touch targets remain the recommendation
   - Bottom sheets still show 25-30% higher engagement vs. traditional modals
   - Cytoscape.js v3.28.1 has mature touch support (pinch-zoom, tap, pan)
   - `touch-action: manipulation` still needed for some WebViews

### Phase 4: Implementation (this session)

Executed the 7-step plan sequentially. Key implementation decisions made during coding:

#### Decision: No minimap on mobile
The desktop uses `cytoscape-navigator` for a minimap. We deliberately excluded it because:
- The minimap has known bugs (transparent background not useful at scale, opaque background has other visual issues, selection rectangle not draggable)
- On mobile, pinch-zoom + fit-to-screen button covers the same navigation need
- The 180x140px minimap would consume too much screen real estate on a phone

#### Decision: Override `.hidden` for transition-based elements
The desktop uses `.hidden { display: none !important }` globally. For mobile elements that animate in/out (search overlay, filter modal, menu overlay), we override this with `display: flex/block` and use `transform: translateY()` + `pointer-events: none` instead, so CSS transitions work.

#### Decision: Momentum-based snap instead of pure position-based
The `BottomSheetTouch` class tracks drag velocity and uses it for snap decisions:
- Flick down at > 0.5 px/ms → always dismiss (regardless of position)
- Flick up at > 0.5 px/ms → always go to full (regardless of position)
- Slow drag → snap to nearest point based on `adjustedVisible = visibleHeight - velocity * 150`

#### Decision: Reuse `GraphFilter` class, rebuild UI
The shared `filter.js` provides the `GraphFilter` class which handles all filter logic (date ranges, entity types, relationship kinds, confidence thresholds). The mobile filter modal uses the same class instance but wires its own UI (full-screen modal with 48px touch targets instead of a 280px sidebar).

#### Decision: Evidence accordion instead of separate panel
On desktop, clicking an edge opens a separate evidence panel at the bottom. On mobile, evidence is rendered as an accordion inside the bottom sheet — first item auto-expanded, rest collapsed. This avoids the complexity of managing two competing bottom panels.

---

## 3. Architecture

```
web/
├── index.html              ← Desktop (+ 6-line mobile redirect)
├── css/                    ← Shared design system
│   ├── tokens.css          ← Design tokens (colors, spacing, dark mode)
│   ├── reset.css
│   ├── base.css
│   └── components/
│       └── badge.css       ← Badge styles (used by mobile)
├── js/                     ← Shared logic
│   ├── utils.js            ← Formatting, escaping, overlays
│   ├── styles.js           ← Cytoscape visual encoding
│   ├── filter.js           ← GraphFilter class
│   ├── search.js           ← Search + highlight
│   ├── layout.js           ← fcose layout engine
│   └── graph.js            ← Data loading, graph init
├── data/graphs/            ← Shared data (both UIs read from here)
│   ├── live/
│   ├── small/
│   ├── medium/
│   ├── large/
│   └── stress/
└── mobile/                 ← NEW: Mobile-specific
    ├── index.html          ← Mobile HTML shell
    ├── css/
    │   └── mobile.css      ← Mobile styles
    └── js/
        ├── app-mobile.js   ← Mobile init + event handlers
        ├── panels-mobile.js← Bottom sheet + filter modal
        └── touch.js        ← Swipe + long-press gestures
```

### Data flow

```
User taps node on phone
  → Cytoscape 'tap' event (built-in touch support)
    → app-mobile.js: initializeMobileEventHandlers()
      → clearNeighborhoodHighlight() + highlightNeighborhood()  [shared: app-mobile.js]
      → openNodeDetailSheet(node)  [mobile: panels-mobile.js]
        → Renders HTML into #bottom-sheet-content
        → MobileApp.sheetTouch.setState('half')  [mobile: touch.js]
          → CSS class toggle → CSS transform transition
```

### Module dependency chain (load order in HTML)

```
1. cytoscape.min.js        (CDN)
2. layout-base.js          (CDN, fcose dependency)
3. cose-base.js            (CDN, fcose dependency)
4. cytoscape-fcose.js      (CDN)
5. utils.js                (shared — no dependencies)
6. styles.js               (shared — depends on utils.js for truncateLabel, daysBetween)
7. filter.js               (shared — depends on utils.js for updateLabelVisibility ref)
8. search.js               (shared — depends on utils.js for announceToScreenReader)
9. layout.js               (shared — depends on utils.js, cytoscape, fcose)
10. graph.js               (shared — depends on utils.js, layout.js)
11. touch.js               (mobile — no dependencies)
12. panels-mobile.js       (mobile — depends on utils.js, touch.js)
13. app-mobile.js          (mobile — depends on everything above)
```

---

## 4. Desktop vs. Mobile: Component Mapping

| Component | Desktop Implementation | Mobile Implementation |
|-----------|----------------------|----------------------|
| **Toolbar** | 56px fixed header, all controls visible | 48px compact, hamburger menu for secondary controls |
| **Search** | Inline `<input>` in toolbar center | Expandable overlay: tap icon → full-width input |
| **Graph** | `#cy` shares space with panels (left/right/bottom margins) | `#cy` always full screen, no margin changes |
| **Node detail** | 280px left sidebar panel (`#detail-panel`) | Bottom sheet with 3 snap points (peek/half/full) |
| **Edge evidence** | 40vh bottom panel (`#evidence-panel`) | Accordion inside bottom sheet |
| **Filters** | 280px right sidebar (`#filter-panel`) | Full-screen modal overlay |
| **Minimap** | 180x140 `cytoscape-navigator` bottom-right | Not included (pinch-zoom covers the need) |
| **Tooltips** | Hover-triggered with 400ms delay | Disabled (no hover on touch devices) |
| **Zoom** | +/- buttons in toolbar | Pinch-zoom only (native Cytoscape) |
| **View selector** | `<select>` dropdown in toolbar | Buttons inside hamburger menu |
| **Theme toggle** | Icon button in toolbar | Button inside hamburger menu |
| **Help** | Right sidebar panel with tabs | Not yet implemented (future: full-screen overlay) |
| **Keyboard nav** | Arrow keys, /, ?, Escape | Not applicable |
| **Node interaction** | Click=select+detail, hover=tooltip, dblclick=zoom | Tap=select+detail, long-press=expand, dbltap=zoom |

---

## 5. Known Issues & Stalking Horse: Minimap

The desktop minimap (`cytoscape-navigator` extension) has three known issues that we noted during this implementation but did not attempt to fix:

### Issue 1: Transparent background not useful at scale
The navigator minimap renders with a transparent background by default. On large graphs (200+ nodes), the minimap becomes visually indistinguishable from the main graph behind it. The current CSS:
```css
/* cytoscape.css:90-94 */
.navigator-container .cytoscape-navigatorView {
  background-color: transparent !important;
  opacity: 1 !important;
  border: 2px solid #ff3333 !important;
}
```

### Issue 2: Opaque background causes other issues
Switching to an opaque background fixes readability but introduces other visual problems (details TBD — user reported but specifics not fully documented).

### Issue 3: Selection rectangle not draggable
The viewport rectangle in the minimap shows your current view but cannot be dragged to navigate. **Root cause hypothesis** (noted during implementation): The `cytoscape-navigator` extension's overlay element (`.cytoscape-navigatorOverlay`) handles click-to-pan but doesn't appear to wire up drag events on the viewport rectangle (`.cytoscape-navigatorView`). The extension may not expose a drag mode option — this might require a patch to the extension itself or a wrapper that intercepts touch/mouse events on the view rectangle and translates them to `cy.pan()` calls.

### Why this matters for mobile
We deliberately excluded the minimap from mobile. If/when these issues get resolved, a minimap could be valuable for tablet layouts (where screen real estate allows it). The fix would likely involve:
1. A semi-transparent background (e.g., `rgba(255,255,255,0.85)` / `rgba(17,24,39,0.85)` dark) instead of fully transparent or opaque
2. Custom drag handling on the viewport rectangle element
3. Different behavior profiles for desktop (always visible) vs. tablet (toggle) vs. phone (hidden)

---

## 6. What's Not Done (Testing & Polish)

The implementation is code-complete but needs manual testing:

- [ ] Test on iOS Safari (iPhone)
- [ ] Test on Chrome Android
- [ ] Test on Firefox Android
- [ ] Verify dark mode works end-to-end
- [ ] Test pinch-zoom doesn't conflict with browser zoom (viewport `user-scalable=no` is set)
- [ ] Test with small (15 nodes), medium (150 nodes), and large (500 nodes) sample data
- [ ] Verify filter apply/reset cycle works
- [ ] Test bottom sheet snap points feel natural (momentum tuning)
- [ ] Test through ngrok on actual phone (auto-redirect, relative paths)
- [ ] Test `?desktop=1` escape hatch from mobile redirect

### Potential follow-ups
- Help panel (full-screen overlay, not yet implemented)
- Orientation change handling (landscape mode)
- Tablet-specific layout (detect `>768px && touch` → hybrid with side panel)
- PWA support (service worker, "Add to Home Screen" manifest)

---

## 7. Estimated vs. Actual Size

| File | Planned | Actual | Delta |
|------|---------|--------|-------|
| `index.html` | ~120 | ~240 | +120 (more complete filter modal HTML, all overlays) |
| `mobile.css` | ~350 | ~530 | +180 (badges, overlays, utilities, reduced-motion) |
| `app-mobile.js` | ~350 | ~350 | On target |
| `panels-mobile.js` | ~250 | ~280 | +30 (evidence accordion) |
| `touch.js` | ~120 | ~190 | +70 (momentum logic, content-scroll-aware drag) |
| **Total** | **~1,190** | **~1,590** | **+400 (~34% over)** |

The overshoot is typical for front-end work — the plan accounted for core logic but not the full set of CSS rules needed for overlays, banners, badges, reduced-motion, and safe-area-inset handling.

---

## 8. Key Patterns for Future Sessions

### How to extend the mobile UI
1. All mobile-specific code lives in `web/mobile/`. Never modify desktop files (except `web/index.html` redirect).
2. To add a new feature, check if the logic exists in a shared module (`web/js/`). If yes, import it. If no, add the logic to a shared module and import from both desktop and mobile.
3. Bottom sheet content is rendered via string concatenation in `panels-mobile.js`. The pattern is: build HTML string → set `innerHTML` on `#bottom-sheet-content` → call `sheetTouch.setState('half')`.
4. New overlays (like a future help panel) should follow the filter modal pattern: `transform: translateY(100%)` → add `.visible` class → transition slides up.

### How to test
1. Serve from project root: `python -m http.server 8000` (or any static server)
2. Open `http://localhost:8000/web/` on desktop — should load desktop UI
3. Open same URL on phone (or with DevTools mobile emulation) — should redirect to `/web/mobile/`
4. Append `?desktop=1` to force desktop UI on mobile
5. Use browser DevTools → Device Toolbar to test different screen sizes without a real phone

### How the auto-redirect works
```
User visits /web/index.html on phone
  → <script> block at top of <body> runs before any rendering
    → Checks matchMedia('(max-width: 768px)') + UA regex
      → If mobile: location.href = './mobile/' + location.search
      → If ?desktop=1 in URL: skip redirect
      → If already on /mobile/ path: skip redirect
```
This works through ngrok and any static file server because it's pure client-side JavaScript with relative paths.
