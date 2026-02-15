# User-Facing Documentation — Comprehensive Plan

**Date:** February 15, 2026
**Status:** Planning
**Priority:** High (First-time user experience)

---

## 1. Current State: Language Style Analysis

### Three Voices, One Unified Tone

All existing user documentation shares a consistent approach but adapts to context:

| Document | Tone | Technical Level | Primary Use |
|----------|------|----------------|-------------|
| **Product Guide** (`docs/product/README.md`) | Direct, practical, confident | Mid-level technical | External reference, deep learning |
| **Glossary** (`web/help/glossary.html`) | Educational, authoritative | Detailed but accessible | Reference lookup, term definitions |
| **In-App Help** (`web/help/content.js`) | Friendly, encouraging, tutorial | Beginner-friendly | Quick answers, getting started |

### Common Style Patterns (to preserve):

- **Voice:** Second person ("you"), active voice, present tense
- **Sentence structure:** Short, clear, punchy. One idea per sentence.
- **Examples:** Concrete, using real entities (OpenAI, GPT-4, CDC)
- **Formatting:** Heavy use of tables, bullet lists, visual hierarchy
- **Bold for emphasis:** Key terms and actions bold on first mention
- **Analogies:** "Think of it like a map..." (Glossary style)
- **Action-oriented:** "Click any node" not "Nodes can be clicked"

### Style Guidelines for New Content:

```markdown
✅ DO:
- "Tap a node to see its connections" (direct, imperative)
- "Large nodes are accelerating" (concrete, active)
- Use tables for comparisons and reference info
- Use bullet lists for steps or options
- Bold first mention of domain terms
- Provide concrete examples with real entity names

❌ DON'T:
- "The user may wish to tap a node if they want to..." (passive, verbose)
- "Entities with high velocity metrics" (jargon without context)
- Write walls of text (break into lists or shorter paragraphs)
- Use "simply" or "just" (condescending)
- Assume prior knowledge in beginner docs
```

---

## 2. Missing Pieces — Gap Analysis

### A. Mobile-Specific User Documentation

**Status:** ❌ Does not exist
**Impact:** High — mobile users have no guidance on touch interactions
**Files to create:**
- `docs/product/README-mobile.md` (mobile-specific supplement to main Product Guide)
- OR: Add mobile sections to existing Product Guide with responsive CSS

**Content needed:**
- Touch gesture reference (tap, long-press, swipe, pinch-zoom)
- Bottom sheet behavior (peek/half/full snap points)
- Hamburger menu walkthrough
- Filter modal vs sidebar differences
- Mobile-optimized workflows
- What's different from desktop (no minimap, no tooltips, gesture-based zoom)
- What's the same (data, views, entities, relationships)

### B. First-Time User Experience (FTUE)

**Status:** ⚠️ Partial — help exists but no onboarding flow
**Impact:** Critical — users are dropped into a complex graph with no orientation
**Priority:** **HIGH** (user requested)

**Components:**

1. **Welcome Banner** (desktop + mobile)
   - Shown on first visit only (localStorage flag)
   - Brief message: "Welcome to the AI Trend Graph. New here? Take a quick tour or explore on your own."
   - Two CTAs: "Start Tour" | "Skip (show help later)"
   - Dismissible with X button
   - Beta flag toggle for testing (see Section 3)

2. **Mini-Tour / Guided Walkthrough** (desktop + mobile)
   - Step-by-step overlay annotations
   - Highlights specific UI elements in sequence
   - 5-7 steps maximum (attention span)
   - Can be exited at any time
   - Suggested flow (desktop):
     1. "This is a knowledge graph of AI trends" (intro + graph overview)
     2. "Click any node to see details" (highlight a mid-size node)
     3. "Search for entities here" (highlight search box)
     4. "Filter the graph" (highlight filter button)
     5. "Switch between views" (highlight view selector)
     6. "Get help anytime" (highlight ? button)
     7. "Ready to explore!" (dismiss)
   - Suggested flow (mobile):
     1. "Tap a node to see details" (highlight bottom sheet)
     2. "Swipe the sheet to see more" (demonstrate gesture)
     3. "Use the menu for controls" (highlight hamburger)
     4. "Search and filter" (highlight icons)
     5. "Ready!" (dismiss)

3. **Feature Discovery Prompts** (progressive disclosure)
   - Contextual tooltips appear after user completes basic actions
   - Example: After first node selection, show "💡 Click an edge to see evidence"
   - Appear once per feature, never again
   - Can be dismissed individually
   - Low priority for V1 (post-tour enhancement)

### C. Beta Flag System

**Status:** ❌ Does not exist
**Impact:** Medium — needed for testing FTUE without polluting real user experience
**Priority:** **HIGH** (required for FTUE testing)

**Requirements:**
- Globally accessible debug/test mode
- Triggered via URL param (`?beta=1` or `?ftue=1`)
- OR: localStorage toggle accessible from developer console
- OR: Hidden UI control (triple-click logo, Konami code, etc.)
- **Functions:**
  - Force welcome banner to show (ignore "already seen" flag)
  - Force mini-tour to restart from step 1
  - Show hidden debug info (node IDs, edge confidence, layout stats)
  - Optionally: skip tour auto-start for testing empty state
- **Must be easy to toggle** for rapid iteration during testing

**Suggested implementation:**
```javascript
// In utils.js or new debug.js module
const DebugMode = {
  enabled: false,

  init() {
    // Check URL param
    const params = new URLSearchParams(window.location.search);
    if (params.has('beta') || params.has('debug') || params.has('ftue')) {
      this.enabled = true;
      console.log('[DEBUG] Beta mode enabled');
    }

    // Check localStorage override
    if (localStorage.getItem('debugMode') === 'true') {
      this.enabled = true;
    }

    // Expose global for easy console access
    window.toggleDebug = () => {
      this.enabled = !this.enabled;
      localStorage.setItem('debugMode', this.enabled);
      console.log(`[DEBUG] Beta mode ${this.enabled ? 'ON' : 'OFF'}`);
    };
  },

  resetFTUE() {
    localStorage.removeItem('ftue-seen');
    localStorage.removeItem('tour-completed');
    console.log('[DEBUG] First-time user flags reset');
  }
};
```

### D. Screenshots and Visual Assets

**Status:** ⚠️ Placeholders exist in Product Guide, actual images unknown
**Impact:** Medium — documentation is less effective without visuals
**Priority:** Medium (can be generated post-implementation)

**Assets needed:**
- Desktop: 15+ screenshots referenced in `docs/product/README.md`
- Mobile: Equivalent mobile screenshots for mobile guide
- Annotated diagrams for complex interactions (filter combinations, view switching)
- Optionally: Short GIF/video clips for gesture demonstrations (bottom sheet swipe, pinch-zoom)

**Directory structure:**
```
docs/product/images/
├── desktop/
│   ├── overview.png
│   ├── view-trending.png
│   ├── view-claims.png
│   ├── node-colors.png
│   ├── click-node.png
│   ├── click-edge.png
│   └── ... (10 more)
└── mobile/
    ├── overview.png
    ├── bottom-sheet-peek.png
    ├── bottom-sheet-half.png
    ├── bottom-sheet-full.png
    ├── hamburger-menu.png
    ├── filter-modal.png
    └── ... (8-10 more)
```

### E. FAQ and Troubleshooting

**Status:** ❌ Does not exist
**Impact:** Low-medium — users may struggle with common issues
**Priority:** Low (post-V1)

**Content areas:**
- "Why are some nodes very small?" → Explain low velocity
- "Why can't I see certain entities?" → Explain filters, date ranges
- "What does 'hypothesis' mean?" → Link to glossary or explain confidence levels
- "How do I find a specific organization?" → Explain search
- "The graph is too dense to read" → Suggest filtering, trending view
- "How often does the graph update?" → Explain data pipeline schedule
- "Can I export this data?" → Future feature or current limitations

**Format:** Could be accordion section in help panel or separate page

---

## 3. Implementation Plan: First-Time User Experience

### Phase 1: Beta Flag System (prerequisite)

**Effort:** 1-2 hours
**Files to create/modify:**
- `web/js/debug.js` (new)
- `web/index.html` (import debug.js)
- `web/mobile/index.html` (import debug.js via relative path)

**Deliverables:**
- `?beta=1` URL parameter support
- `window.toggleDebug()` console command
- `DebugMode.resetFTUE()` helper
- localStorage persistence
- Console logging for debug actions

**Testing checklist:**
- [ ] `?beta=1` enables debug mode
- [ ] `window.toggleDebug()` persists across page reloads
- [ ] `DebugMode.resetFTUE()` clears welcome banner seen flag
- [ ] Works on both desktop and mobile

---

### Phase 2: Welcome Banner (desktop + mobile)

**Effort:** 2-3 hours
**Files to create/modify:**
- `web/js/ftue.js` (new — first-time user experience module)
- `web/css/components/ftue.css` (new — banner, tour styles)
- `web/index.html` (banner HTML, import ftue.js)
- `web/mobile/index.html` (mobile banner HTML, import ftue.js)

**Desktop banner design:**
```
┌────────────────────────────────────────────────────────────┐
│  👋  Welcome to the AI Trend Graph!                    [×] │
│  This graph shows emerging AI trends from news and         │
│  research. New here?                                        │
│                                                             │
│  [ 🎯 Start Quick Tour ]  [ 📖 View Guide ]  [ Skip ]     │
└────────────────────────────────────────────────────────────┘
```

**Mobile banner design:**
```
┌──────────────────────────────────┐
│  👋  Welcome!                [×] │
│  Track AI trends with this       │
│  interactive knowledge graph.    │
│                                   │
│  [ Start Tour ]  [ Skip ]        │
└──────────────────────────────────┘
```

**Behavior:**
- Appears on first visit (check `localStorage.getItem('ftue-seen')`)
- Positioned at top of graph canvas (overlays graph)
- Dismissible via X button or "Skip" CTA
- "Start Tour" triggers mini-tour (Phase 3)
- "View Guide" opens help panel (desktop) or help sheet (mobile)
- Sets `localStorage.setItem('ftue-seen', 'true')` on any dismissal
- Beta mode: always show if `DebugMode.enabled && !params.has('no-ftue')`

**Responsive behavior:**
- Desktop: 600px max-width, centered horizontally, 24px from top
- Mobile: 90% width, 16px margins, smaller padding
- Use design tokens for all spacing, colors, typography

**Accessibility:**
- Announced to screen readers on page load (use `#sr-announcer`)
- Keyboard accessible (Tab to CTAs, Enter/Space to activate, Escape to dismiss)
- Focus trapped inside banner until dismissed or tour started

**Testing checklist:**
- [ ] Shows on first visit (desktop)
- [ ] Shows on first visit (mobile)
- [ ] Does not show on subsequent visits
- [ ] Shows if beta mode enabled (even after dismissal)
- [ ] "Start Tour" launches mini-tour
- [ ] "View Guide" opens help
- [ ] "Skip" dismisses without launching tour
- [ ] X button dismisses
- [ ] Escape key dismisses
- [ ] Screen reader announces banner

---

### Phase 3: Mini-Tour / Guided Walkthrough (desktop)

**Effort:** 6-8 hours (desktop), 4-6 hours (mobile)
**Files to create/modify:**
- `web/js/tour.js` (new — tour step management, overlay rendering)
- `web/css/components/tour.css` (new — overlay, spotlight, tooltip styles)
- `web/js/ftue.js` (wire "Start Tour" CTA)

**Desktop tour steps:**

| Step | Target Element | Highlight | Tooltip Content | Position |
|------|----------------|-----------|-----------------|----------|
| 1 | `#cy` (graph canvas) | None (backdrop only) | "This is a knowledge graph of AI trends. **Nodes** are entities (orgs, models, tools). **Edges** are relationships." | Center overlay |
| 2 | First visible mid-size node | Spotlight circle | "**Click any node** to see its details and connections. Try it!" | Below node |
| 3 | `#search-box` (search input) | Rectangle | "**Search for entities** by name or alias. Press `/` to focus." | Below search |
| 4 | `#filter-toggle` (gear icon) | Rectangle | "**Filter the graph** by entity type, date, or confidence level." | Below button |
| 5 | `#view-selector` (dropdown) | Rectangle | "**Switch between views**: Trending, Claims, Mentions, Dependencies." | Below dropdown |
| 6 | `#help-button` (? icon) | Rectangle | "Get help anytime by clicking here or pressing `?`" | Below button |
| 7 | None | None | "**You're ready to explore!** 🎉 Click anywhere to start." | Center overlay |

**Mobile tour steps:**

| Step | Target Element | Highlight | Tooltip Content | Position |
|------|----------------|-----------|-----------------|----------|
| 1 | `#cy` | None | "This graph shows AI trends. **Tap** any node to see details." | Center (bottom sheet peek) |
| 2 | First visible node | Spotlight | "Tap this node. The **bottom sheet** shows its details." | Above node |
| 3 | `#bottom-sheet` | Rectangle | "**Swipe up** to expand. **Swipe down** to collapse or dismiss." | Above sheet |
| 4 | `#btn-menu` (hamburger) | Rectangle | "The **menu** has views, filters, and controls." | Below button |
| 5 | `#btn-search` | Rectangle | "**Search** and **filter** with these buttons." | Below button |
| 6 | None | None | "**Ready to explore!** 🎉" | Center |

**Visual design:**

```
┌─────────────────────────────────────────┐
│         [Step 2 of 6]          [ Skip ] │  ← Header bar
├─────────────────────────────────────────┤
│                                         │
│   💡 Click any node to see its         │  ← Tooltip card
│      details and connections.           │
│      Try it!                            │
│                                         │
│   [ ← Back ]            [ Next → ]     │  ← Navigation
└─────────────────────────────────────────┘
       ↓
    [ Highlighted node with spotlight ]

    Rest of UI dimmed (backdrop overlay with cutout)
```

**Implementation approach:**

1. **Backdrop overlay:** Full-screen `<div>` with `rgba(0,0,0,0.7)` and high z-index
2. **Spotlight cutout:** SVG mask or CSS `clip-path` to create "hole" around target element
3. **Tooltip card:** Positioned relative to target element, responsive to viewport edges
4. **Navigation:** "Back" (if not step 1), "Next" (if not last step), "Skip" (always)
5. **Progress:** "Step X of Y" indicator
6. **State management:** Track current step, localStorage completion flag
7. **Auto-advance option:** On step 2 (node click), detect click and auto-advance to step 3
8. **Exit:** Skip button, Escape key, or backdrop click (optional — may be too easy to accidentally dismiss)

**Libraries:**

Option A: **Build from scratch** (recommended for lightweight, no dependencies)
- Pros: Full control, no bundle bloat, matches existing code style
- Cons: More implementation time
- Estimated: 6-8 hours

Option B: **Use a library** (e.g., Shepherd.js, Intro.js, Driver.js)
- Pros: Faster implementation, battle-tested
- Cons: Bundle size, may not match design system, need to learn API
- Estimated: 3-4 hours + learning curve

**Recommendation:** Build from scratch. The tour is simple enough (7 steps max) that a custom solution will be cleaner and more maintainable than learning/integrating a third-party library.

**Accessibility:**
- Tour tooltip content announced to screen readers
- Keyboard navigation: Tab cycles through Back/Next/Skip buttons
- Arrow keys: Left=Back, Right=Next
- Enter/Space: Activate focused button
- Escape: Exit tour
- Focus management: Trap focus inside tour overlay, restore focus on exit

**Persistence:**
- `localStorage.setItem('tour-completed', 'true')` on completion or skip
- Never auto-start again (unless beta mode or user explicitly clicks "Start Tour" in help)
- Provide "Restart Tour" option in help panel (desktop) or help sheet (mobile)

**Testing checklist:**
- [ ] Tour starts from welcome banner "Start Tour" CTA
- [ ] Tour can be restarted from help panel
- [ ] All 6-7 steps display correctly
- [ ] Spotlight/highlight accurately targets elements
- [ ] Tooltip positions responsively (doesn't go off-screen)
- [ ] Back/Next/Skip buttons work
- [ ] Keyboard navigation works (arrows, Tab, Escape)
- [ ] Screen reader announces steps
- [ ] Completion flag prevents auto-start on next visit
- [ ] Beta mode allows re-running tour

---

### Phase 4: Mobile User Documentation

**Effort:** 3-4 hours (writing + formatting)
**Files to create:**
- `docs/product/README-mobile.md` (new)
- OR: Add mobile sections to existing `docs/product/README.md` with responsive CSS

**Approach A: Separate mobile guide**

Pros:
- Focused, mobile-specific content
- No risk of cluttering desktop docs
- Can be shorter and more action-oriented

Cons:
- Duplicate some content (views, entities, relationships are the same)
- Two files to maintain

**Approach B: Unified guide with responsive sections**

Pros:
- Single source of truth
- Shared content stays in sync
- Responsive CSS can show/hide platform-specific sections

Cons:
- More complex document structure
- Risk of confusion (which instructions apply to me?)

**Recommendation:** **Approach A (separate mobile guide)** for V1. Benefits:
- Faster to write (focus on mobile-specific interactions only)
- Easier to link from mobile help sheet
- Can reference main Product Guide for shared concepts ("See [Product Guide](#) for an explanation of entity types")

**Content outline (README-mobile.md):**

```markdown
# AI Trend Graph — Mobile Guide

Quick reference for using the AI Trend Graph on touch devices.

---

## Touch Interactions

| Gesture | Action |
|---------|--------|
| **Tap** a node | Select and show details in bottom sheet |
| **Long-press** a node | Expand to full-screen detail (future) |
| **Double-tap** background | Fit graph to screen |
| **Pinch-zoom** | Zoom in/out |
| **Drag** background | Pan the graph |
| **Swipe up** bottom sheet | Expand to half or full screen |
| **Swipe down** bottom sheet | Collapse to peek or dismiss |

---

## Bottom Sheet

The **bottom sheet** shows details for selected nodes or edges. It has three states:

- **Peek** (100px): Quick preview with entity name and type
- **Half** (~40% screen): Full details and relationships
- **Full** (~85% screen): Maximum content area

**Gestures:**
- Swipe up to expand
- Swipe down to collapse or dismiss
- Tap the dimmed graph area to dismiss

---

## Hamburger Menu

The **menu** (☰ button) contains:

- **Views:** Switch between Trending, Claims, Mentions, Dependencies
- **Date Range:** Filter by time (7d, 30d, 90d, All)
- **Actions:** Re-run layout, fit to screen, toggle theme
- **Help:** Links to this guide and the glossary

---

## Search and Filters

- **Search** (🔍 button): Opens full-screen search overlay. Type to filter, press Enter to zoom to matches.
- **Filter** (⚙️ button): Opens full-screen filter modal with entity types, confidence threshold, relationship kinds.

---

## What's Different from Desktop?

| Feature | Desktop | Mobile |
|---------|---------|--------|
| **Node details** | Left sidebar panel | Bottom sheet (swipeable) |
| **Filters** | Right sidebar panel | Full-screen modal |
| **Minimap** | Bottom-right corner | Not available (use pinch-zoom) |
| **Tooltips** | Hover on nodes/edges | Not available (tap to select) |
| **Zoom** | +/- buttons + scroll wheel | Pinch-zoom only |
| **Layout** | Re-run layout button | In hamburger menu |

---

## Tips for Mobile

- **Start with Trending view** — fewer nodes, easier to navigate on small screen
- **Use search** to quickly jump to entities you know
- **Filter aggressively** — mobile works best with <100 nodes
- **Pinch-zoom to explore clusters** — get close to see labels
- **Double-tap to reset** — fit-to-screen on background

---

## More Information

- **Entity types, relationships, scoring:** See [Product Guide](../README.md)
- **Term definitions:** See [Glossary](../../web/help/glossary.html)
```

**Effort:** ~3 hours to write, format, test links

---

### Phase 5: Help Panel Enhancements (optional)

**Effort:** 2-3 hours
**Priority:** Low (existing help is functional)

**Enhancements:**
- Add "Restart Tour" button to Quick Start tab
- Add link to Product Guide (desktop) or README-mobile (mobile)
- Add FAQ section to Topics accordion
- Context-sensitive help (e.g., clicking ? while filter panel open → auto-expand "Filtering" section)

---

## 4. Unified CSS Strategy

### Goal: One set of content, presentation adapts to environment

**Current status:** ✅ Already implemented!
- Mobile imports `../help/content.js` (same file as desktop)
- Mobile links to `../help/glossary.html` (same file as desktop)
- Glossary already has responsive CSS (`@media (max-width: 768px)`)

**Recommendation:** Continue this pattern for all new documentation.

### Guidelines for New Content:

1. **Content lives in shared locations:**
   - `web/help/content.js` — In-app help text
   - `web/help/glossary.html` — Glossary
   - `docs/product/README.md` — Product guide (external)
   - `docs/product/README-mobile.md` — Mobile supplement (external)

2. **CSS adapts presentation:**
   - Desktop: `web/css/components/help-panel.css`
   - Mobile: `web/mobile/css/mobile.css` (overrides)
   - Shared: `web/css/tokens.css` (design tokens for consistency)

3. **Responsive breakpoints:**
   - `max-width: 768px` → Mobile layout
   - `min-width: 769px` → Desktop layout
   - Use design tokens for all spacing, colors, typography

4. **Component-specific overrides (mobile):**
   ```css
   /* Mobile: bottom sheet instead of sidebar */
   @media (max-width: 768px) {
     .help-panel {
       display: none; /* Desktop sidebar hidden */
     }
     .help-sheet {
       display: flex; /* Mobile bottom sheet shown */
     }
   }
   ```

---

## 5. Implementation Timeline

| Phase | Effort | Dependencies | Priority |
|-------|--------|--------------|----------|
| **Phase 1: Beta flag** | 1-2 hours | None | **HIGH** (prerequisite) |
| **Phase 2: Welcome banner** | 2-3 hours | Phase 1 | **HIGH** |
| **Phase 3: Desktop tour** | 6-8 hours | Phase 2 | **HIGH** |
| **Phase 3b: Mobile tour** | 4-6 hours | Phase 2, 3 | **HIGH** |
| **Phase 4: Mobile guide** | 3-4 hours | None | Medium |
| **Phase 5: Help enhancements** | 2-3 hours | Phase 3 | Low |
| **Screenshots** | 4-6 hours | Phase 3 (capture after tour built) | Medium |

**Total effort:** ~23-32 hours for all phases
**Critical path for FTUE:** Phases 1-3 = ~9-13 hours

---

## 6. Testing Checklist (All Phases)

### Desktop FTUE
- [ ] Welcome banner shows on first visit
- [ ] Tour launches from banner "Start Tour" CTA
- [ ] All 7 tour steps display correctly
- [ ] Tour highlights correct elements
- [ ] Tour can be skipped at any step
- [ ] Tour completion flag prevents auto-start
- [ ] "Restart Tour" option in help panel works
- [ ] Beta mode (`?beta=1`) resets FTUE flags
- [ ] Screen reader announces tour steps
- [ ] Keyboard navigation works (arrows, Tab, Escape)

### Mobile FTUE
- [ ] Welcome banner shows on first visit (mobile)
- [ ] Tour launches from banner (mobile)
- [ ] All 6 mobile tour steps display correctly
- [ ] Bottom sheet tour step demonstrates swipe
- [ ] Tour can be skipped
- [ ] Tour completion flag persists
- [ ] "Restart Tour" in help sheet works
- [ ] Beta mode works on mobile

### Cross-Browser
- [ ] Desktop: Chrome, Firefox, Safari, Edge
- [ ] Mobile: iOS Safari, Chrome Android, Firefox Android

### Responsive
- [ ] Banner responsive on small desktop windows
- [ ] Tour tooltips don't overflow viewport edges
- [ ] Help panel/sheet responsive to orientation changes

### Accessibility
- [ ] Screen reader announces banner on page load
- [ ] Screen reader announces tour steps
- [ ] Keyboard navigation works (no mouse needed)
- [ ] Focus visible on all interactive elements
- [ ] Focus trapped in tour overlay
- [ ] Color contrast meets WCAG AA

---

## 7. Future Enhancements (Post-V1)

- **Video tutorials:** Short screencasts for complex workflows
- **Interactive examples:** Sandboxed mini-graphs for learning
- **Contextual tips:** Progressive disclosure prompts (appear once per feature)
- **FAQ section:** Common questions in help panel
- **Troubleshooting guide:** "Why is X happening?"
- **Keyboard shortcut cheatsheet:** Printable reference card
- **Onboarding quiz:** Test understanding after tour (gamification)
- **Feature announcements:** "What's new" modal on version updates

---

## 8. Open Questions

1. **Tour auto-advance:** Should step 2 (click node) auto-advance when user clicks a node, or require explicit "Next" click?
   - **Recommendation:** Auto-advance (more interactive, feels responsive)

2. **Tour dismissal:** Should clicking backdrop dismiss tour, or only Skip/Escape?
   - **Recommendation:** Backdrop click = dismiss (faster exit for impatient users)

3. **Mobile tour trigger:** Long-press on node (step 2) — is this needed in V1?
   - **Recommendation:** Defer to post-V1 (not implemented yet in mobile UI)

4. **Product Guide screenshots:** Generate now or after tour implementation?
   - **Recommendation:** After tour (can capture actual tour UI for consistency)

5. **Help panel "Restart Tour" placement:** In Quick Start tab or separate menu item?
   - **Recommendation:** Quick Start tab, at the bottom (natural endpoint after reading)

---

## Next Steps

1. **Review this plan** with stakeholders
2. **Confirm priorities** (Phases 1-3 are HIGH, rest are medium/low)
3. **Confirm style guidelines** (preserve existing tone, add mobile-specific voice)
4. **Begin implementation:**
   - Start with Phase 1 (beta flag) — small, isolated, unlocks testing
   - Proceed to Phase 2 (welcome banner) — high impact, moderate effort
   - Then Phase 3 (tour) — highest effort, highest value
5. **Test iteratively** on real devices throughout implementation
6. **Capture screenshots** after tour is complete
7. **Write mobile guide** (can be done in parallel with tour implementation)
