# Implementation Plan: Separate Mobile UI

## Approach
Create a standalone mobile UI at `web/mobile/` that shares data files and reusable JS modules with the existing desktop UI. The desktop UI remains completely untouched.

## Best Practices Alignment (Feb 2025)

| Practice | How we apply it |
|----------|----------------|
| **Touch target sizing** | 48px minimum per Material Design 3 / WCAG 2.2 (Level AAA is 44px, we exceed) |
| **Bottom sheet pattern** | Industry standard for mobile detail views (Google Maps, Apple Maps, Sheets). Use CSS `translate` + touch drag, not a modal library |
| **Viewport-based detection** | `matchMedia('(max-width: 768px)')` + UA sniff fallback. More reliable than UA alone since Chrome UA reduction (2023+) made strings less descriptive |
| **No JS framework** | Matches desktop — vanilla JS, no build step. Keeps it simple, zero bundle overhead |
| **`prefers-reduced-motion`** | Already in desktop tokens.css, we inherit it |
| **Dark mode** | Inherit `tokens.css` + `[data-theme]` system as-is |
| **Container queries** | Available in all modern mobile browsers since 2023. We'll use them for the bottom sheet sizing instead of viewport media queries where it makes sense |
| **`touch-action` CSS** | Explicit `touch-action: manipulation` on interactive elements to eliminate 300ms tap delay (still needed on some WebViews) |
| **Passive event listeners** | `{ passive: true }` on scroll/touch handlers for smooth 60fps scrolling |
| **Graph on mobile** | Cytoscape.js has built-in touch support (pinch-zoom, tap, pan). The library itself is mobile-ready. Our job is the surrounding chrome |

## What We Share vs. Build New

### Shared (import from `../js/` and `../css/`)
- `tokens.css` — design tokens, colors, dark mode
- `reset.css` — CSS reset
- `utils.js` — date formatting, HTML escaping, math helpers
- `styles.js` — Cytoscape visual encoding (node colors, sizes, edge styles)
- `graph.js` — data loading, `initializeGraph()`, stats
- `layout.js` — fcose layout (with mobile-tuned params passed as overrides)
- `filter.js` — `GraphFilter` class (logic reused, UI rebuilt for mobile)

### New (mobile-specific)
| File | Purpose | Est. lines |
|------|---------|-----------|
| `web/mobile/index.html` | Mobile shell, compact toolbar, full-screen graph | ~120 |
| `web/mobile/css/mobile.css` | Mobile layout, bottom sheets, compact toolbar, touch targets | ~350 |
| `web/mobile/js/app-mobile.js` | Mobile init, touch interactions, simplified toolbar | ~350 |
| `web/mobile/js/panels-mobile.js` | Bottom sheet detail, full-screen filter modal, evidence accordion | ~250 |
| `web/mobile/js/touch.js` | Swipe gestures for bottom sheet, long-press context | ~120 |

**Total new code: ~1,190 lines**

## Mobile UI Design

### Layout
```
┌──────────────────────────┐
│ [☰] AI Trends  [🔍] [⚙] │  ← 48px compact toolbar
├──────────────────────────┤
│                          │
│     CYTOSCAPE GRAPH      │  ← Full screen, no panels stealing space
│     (touch: pinch/pan)   │
│                          │
│                          │
├──────────────────────────┤
│ ▔▔▔  Node Name           │  ← Bottom sheet (drag handle)
│ Type: Model · 12 conns   │     Swipe up = full detail
│ Velocity: 2.1x ▲        │     Swipe down = dismiss
└──────────────────────────┘
```

### Key Differences from Desktop

| Component | Desktop | Mobile |
|-----------|---------|--------|
| Toolbar | 56px, all controls visible | 48px, hamburger menu for secondary controls |
| Search | Inline in toolbar center | Expandable: tap icon → full-width overlay |
| Graph | Shares space with side panels | Always full screen |
| Detail panel | 280px left sidebar | Bottom sheet (swipe up/down) |
| Filter panel | 280px right sidebar | Full-screen modal overlay |
| Evidence | 40vh bottom panel | Accordion inside detail bottom sheet |
| Help | 350px right sidebar | Separate full-screen overlay |
| Minimap | 180x140 bottom-right | Removed entirely |
| Node interaction | Click=select, hover=tooltip | Tap=select+detail sheet, long-press=context |
| View selector | Dropdown in toolbar | Inside hamburger menu |
| Date picker | Inline in toolbar | Inside hamburger menu |
| Zoom controls | Buttons in toolbar | Pinch-zoom only (native Cytoscape) |

### Bottom Sheet Behavior
- **Collapsed (peek):** ~80px showing node name + type badge
- **Half-expanded:** ~40vh showing key stats + relationships preview
- **Full-expanded:** ~85vh showing everything including evidence
- **Dismissed:** swipe down past collapsed threshold
- Implementation: CSS `transform: translateY()` + touch event tracking
- Snap points via `requestAnimationFrame` for smooth 60fps animation

### Auto-Detection & Redirect

In `web/index.html` — add a small script block at the top of `<body>`:

```javascript
// Mobile detection — redirect to mobile UI
(function() {
  // Skip if user explicitly chose desktop (URL param)
  if (location.search.includes('desktop=1')) return;
  // Skip if already on mobile path
  if (location.pathname.includes('/mobile')) return;

  var isMobile = window.matchMedia('(max-width: 768px)').matches
    || /Mobi|Android|iPhone|iPad/.test(navigator.userAgent);

  if (isMobile) {
    location.href = './mobile/' + location.search;
  }
})();
```

The mobile page includes a "View desktop version" link that appends `?desktop=1`.

This works transparently through ngrok — no path rewriting, no server-side detection needed.

## Implementation Steps

### Step 1: Scaffold mobile directory and HTML shell
- Create `web/mobile/index.html` with compact toolbar, full-screen `#cy` container, bottom sheet skeleton, filter modal skeleton
- Load shared CSS (`../css/tokens.css`, `../css/reset.css`) and shared JS modules
- Load Cytoscape + fcose from same CDNs
- Verify graph renders on a phone-width viewport

### Step 2: Mobile CSS
- Create `web/mobile/css/mobile.css`
- Compact 48px toolbar with hamburger menu
- Full-screen graph container
- Bottom sheet component (3 snap points, drag handle)
- Full-screen filter modal
- Touch-friendly 48px tap targets
- Search overlay (expands from icon)
- Inherit dark mode from tokens.css

### Step 3: Mobile app initialization (`app-mobile.js`)
- Simplified init: no minimap, no navigator
- Mobile-tuned layout params (larger `nodeSeparation`, bigger node minimum size)
- Lower scale thresholds (warn at 200 nodes instead of 500)
- Touch event handlers: tap=select, long-press=context menu
- Hamburger menu toggle for secondary controls
- Search overlay expand/collapse

### Step 4: Mobile panels (`panels-mobile.js`)
- Bottom sheet with touch-drag gestures
- Three snap points (peek/half/full)
- Node detail content (reuse HTML generation from `panels.js` but rendered into bottom sheet)
- Edge evidence as accordion sections within bottom sheet
- Full-screen filter modal (checkboxes, sliders — same filter logic, new layout)
- "Apply" closes modal and returns to graph

### Step 5: Touch gesture handling (`touch.js`)
- Bottom sheet swipe up/down with momentum
- Snap-to-nearest-point logic
- Long-press detection (500ms) for node context actions
- Coordinate with Cytoscape's built-in touch handling (don't fight it)
- `{ passive: true }` on scroll listeners

### Step 6: Auto-detection redirect
- Add mobile detection snippet to `web/index.html` (the ONLY change to the desktop UI)
- Add "View desktop version" link in mobile UI
- Test through ngrok on actual phone

### Step 7: Testing & polish
- Test on iOS Safari, Chrome Android, Firefox Android
- Verify dark mode works
- Verify pinch-zoom doesn't conflict with browser zoom (`<meta name="viewport" content="..., user-scalable=no">` for the mobile page only)
- Test with 15-node, 150-node, and 500-node sample data
- Verify filter apply/reset cycle works
- Test bottom sheet snap points feel natural

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Desktop UI regression | **Zero** | Only change is a 6-line redirect snippet in index.html |
| Cytoscape touch conflicts | Low | Cytoscape has mature touch support; we only handle gestures on our UI chrome, not the canvas |
| Bottom sheet janky on older phones | Medium | Use `transform` (GPU-composited), avoid `top`/`height` animation. Test on mid-range Android |
| fcose slow on phone CPU | Medium | Lower `numIter` for mobile, reduce scale thresholds, default to trending view |
| Shared JS module path issues | Low | Relative paths (`../js/utils.js`) work fine with static serving |

## Out of Scope (can add later)
- Offline/PWA support (service worker caching)
- Native-like "Add to Home Screen" manifest
- Haptic feedback on interactions
- Orientation change handling (landscape mode)
- Tablet-specific layout (could detect >768px && touch → show hybrid)
