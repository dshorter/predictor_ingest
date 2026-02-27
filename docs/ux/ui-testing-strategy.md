# UI Testing Strategy

Testing approach for the `web/` layer. The UI is a static Cytoscape.js client with
no build step, no framework, and no server-side rendering — the testing strategy
should match this simplicity.

---

## Current State

**What exists:**
- 6 test data directories (`small/`, `medium/`, `large/`, `stress/`, `latest/`, `live/`)
  with 4 graph views each (trending, claims, mentions, dependencies)
- The `small/` dataset (~15 nodes) is sized for rapid manual verification
- The `stress/` dataset (~2000 nodes) is sized for performance limit testing
- Backend tests exist under `tests/` (pytest), but they don't cover the UI layer

**What doesn't exist:**
- No automated UI tests of any kind
- No visual regression tests
- No accessibility audits (automated)
- No performance benchmarks (automated)
- No cross-browser testing

---

## Testing Layers

### Layer 1 — Unit Tests (JS logic, no DOM)

**What to test:** Pure functions that don't touch the DOM or Cytoscape instance.

**Tool:** Any lightweight JS test runner. Recommendations:
- **Vitest** (fast, ESM-native, zero-config) — preferred
- **Jest** (mature, widely known) — acceptable
- Node.js built-in test runner (`node --test`) — minimalist option

**Files to test:**

| File | Testable functions | Why |
|------|--------------------|-----|
| `utils.js` | `formatDate`, `daysAgo`, `isNewNode`, `truncateLabel`, `escapeHtml`, `capitalize`, `formatRelation`, `formatVelocity`, `formatDocId`, `extractDomain`, `debounce` | Pure transforms, easy to assert |
| `filter.js` | `GraphFilter` class (date range computation, type/kind toggling, confidence threshold) | Core business logic |
| `styles.js` | Node size calculation (velocity × recency × degree), opacity calculation | Visual encoding correctness |
| `layout.js` | Ratio-based parameter scaling (given N nodes and E edges, what are the fcose params?) | Algorithm correctness |

**Approach:**
1. Extract pure functions that currently read from `cy` or DOM into testable forms
   (accept data as arguments, return values)
2. Write tests against extracted functions
3. Keep original functions as thin wrappers that call the pure versions

**Example structure:**
```
web/
├── js/
│   ├── utils.js            # Already mostly pure
│   ├── filter.js            # GraphFilter needs mock cy for apply(), but config logic is pure
│   └── ...
└── tests/
    ├── utils.test.js
    ├── filter.test.js
    ├── styles.test.js
    └── layout.test.js
```

**Coverage target:** 100% of pure utility functions, 80%+ of filter/style/layout logic.

**Estimated effort:** 2–3 sessions to set up runner + write initial tests.

### Layer 2 — Integration Tests (JS + DOM, no browser)

**What to test:** Functions that manipulate the DOM but don't need a real browser
rendering engine.

**Tool:** Vitest + `jsdom` (or `happy-dom`) environment.

**What to cover:**

| Area | What to assert |
|------|----------------|
| Panel rendering | `openNodeDetailPanel(mockNode)` produces correct HTML structure |
| Tooltip rendering | Tooltip contains type badge, label, connection count |
| Search highlighting | Search applies `.dimmed` to non-matching nodes, `.search-match` to matches |
| Filter UI sync | `syncFilterUI(filter)` checks correct checkboxes |
| Theme toggle | `data-theme` attribute flips on `<html>` |

**Caveat:** Cytoscape.js requires a real DOM for its container. For integration tests
that need a `cy` instance, use `jsdom` with a mock container element. Cytoscape can
initialize in headless mode (`headless: true`) for testing purposes.

**Example:**
```javascript
import cytoscape from 'cytoscape';
import { GraphFilter } from '../js/filter.js';

test('GraphFilter hides nodes outside date range', () => {
  const cy = cytoscape({
    headless: true,
    elements: [
      { data: { id: 'a', lastSeen: '2026-02-25' } },
      { data: { id: 'b', lastSeen: '2026-01-01' } },
    ]
  });

  const filter = new GraphFilter(cy);
  filter.setDateRange('2026-02-01', '2026-02-28');
  filter.apply();

  expect(cy.getElementById('a').hasClass('filtered-out')).toBe(false);
  expect(cy.getElementById('b').hasClass('filtered-out')).toBe(true);
});
```

**Estimated effort:** 2–3 sessions.

### Layer 3 — Visual Regression Tests (browser-based)

**What to test:** The rendered graph looks correct — node colors, sizes, positions,
panel layouts, dark mode appearance.

**Tool:** **Playwright** (recommended) or Puppeteer.

**Approach:**
1. Serve `web/` locally (e.g., `python -m http.server` or `npx serve`)
2. Load each test data tier (small, medium, large)
3. Capture screenshots at defined states:
   - Default load (trending view)
   - Each view (claims, mentions, dependencies)
   - Dark mode
   - With filter panel open
   - With detail panel open (click first node)
   - With search active
   - Empty state (if testable)
4. Compare against baseline screenshots (pixel diff or perceptual hash)
5. Fail on diff above threshold (suggest ~1% for layout jitter tolerance)

**Screenshot matrix (initial):**

| State | Desktop | Mobile |
|-------|---------|--------|
| Trending view, light mode | ✓ | ✓ |
| Trending view, dark mode | ✓ | ✓ |
| Claims view | ✓ | — |
| Node selected, detail panel | ✓ | ✓ (bottom sheet) |
| Filter panel open | ✓ | ✓ (full screen) |
| Search with results | ✓ | ✓ |
| Empty state | ✓ | ✓ |
| Large graph (500 nodes) | ✓ | — |

**Important:** Force-directed layout is non-deterministic. Node positions will differ
between runs. Visual regression for the graph canvas itself needs either:
- **Seeded layout** (set `randomize: false` + fixed seed in fcose, if supported)
- **Structural assertions** instead of pixel comparison (e.g., "node X is rendered,"
  "panel contains text Y")
- **UI-only screenshots** (panels, toolbar, overlays — not the canvas)

**Recommendation for V1:** Start with UI-only screenshots (panels, toolbar, overlays,
empty/error states). Skip canvas screenshots until layout seeding is solved. The
canvas is tested by integration tests (Layer 2) asserting on Cytoscape state, not pixels.

**Estimated effort:** 3–4 sessions (including baseline capture).

### Layer 4 — Accessibility Audits (automated)

**What to test:** WCAG compliance, keyboard navigation, screen reader compatibility.

**Tools:**
- **axe-core** (via `@axe-core/playwright` or standalone) — automated WCAG scanning
- **Playwright** — for keyboard navigation flows

**What to cover:**

| Check | Tool | Frequency |
|-------|------|-----------|
| Color contrast (WCAG AA) | axe-core | Every PR |
| ARIA attribute validity | axe-core | Every PR |
| Focus order correctness | Playwright keyboard script | Weekly / on interaction changes |
| Keyboard navigation (Tab, Escape, Arrow) | Playwright | On interaction changes |
| Touch target size (≥44px) | axe-core + custom check | On button/input changes |

**Example Playwright a11y test:**
```javascript
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('page has no critical accessibility violations', async ({ page }) => {
  await page.goto('http://localhost:8080');
  await page.waitForSelector('#cy');

  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze();

  expect(results.violations.filter(v => v.impact === 'critical')).toHaveLength(0);
});
```

**Estimated effort:** 1–2 sessions.

### Layer 5 — Performance Benchmarks

**What to test:** Load time, layout time, interaction responsiveness at different scales.

**Tool:** Playwright with `page.evaluate()` for timing, or Chrome DevTools Protocol
(`CDP`) for Performance API access.

**Metrics to track:**

| Metric | Target | Dataset |
|--------|--------|---------|
| Time to first render | < 1s | small (15 nodes) |
| Time to layout complete | < 3s | medium (150 nodes) |
| Time to layout complete | < 8s | large (500 nodes) |
| Time to layout complete | < 20s | stress (2000 nodes) |
| Filter apply latency | < 100ms | medium |
| Search response time | < 200ms | medium |
| Panel open latency | < 50ms | any |

**Approach:**
1. Instrument key operations with `performance.mark()` / `performance.measure()`
2. Playwright test loads each dataset, reads timing marks
3. Assert against thresholds
4. Log results for trend tracking over time

**Estimated effort:** 2 sessions.

---

## Recommended Implementation Order

```
Layer 1 (unit)           Layer 2 (integration)     Layer 3–5 (browser-based)
┌──────────────────┐    ┌──────────────────────┐  ┌────────────────────────┐
│ Set up Vitest    │    │ Cytoscape headless    │  │ Playwright setup       │
│ Test utils.js    │    │ Test GraphFilter      │  │ UI-only screenshots    │
│ Test styles.js   │───▶│ Test panel HTML       │──▶│ axe-core a11y scan     │
│   calculations   │    │ Test search behavior  │  │ Performance benchmarks │
│ Test layout.js   │    │ Test theme toggle     │  │ Keyboard nav flows     │
│   scaling        │    │                       │  │                        │
└──────────────────┘    └──────────────────────┘  └────────────────────────┘
    2–3 sessions             2–3 sessions              5–6 sessions
```

**Total estimated effort:** ~12 sessions for full coverage across all layers.

**Minimum viable testing (recommend for now):**
- Layer 1 (unit tests for pure functions) — highest value per effort
- Layer 4 (axe-core scan) — catches real accessibility issues cheaply
- Combined: ~4 sessions

---

## CI Integration

Once tests exist, integrate into the workflow:

```yaml
# .github/workflows/ui-tests.yml (conceptual)
ui-tests:
  steps:
    - name: Unit tests
      run: cd web && npx vitest run

    - name: Start server
      run: cd web && npx serve -l 8080 &

    - name: Integration tests
      run: cd web && npx vitest run --environment jsdom

    - name: Playwright tests
      run: cd web && npx playwright test

    - name: Accessibility audit
      run: cd web && npx playwright test tests/a11y.spec.js
```

**Note:** The project currently has no `package.json` in `web/`. Setting up the test
infrastructure requires initializing one:

```bash
cd web
npm init -y
npm install -D vitest playwright @axe-core/playwright
```

This is a one-time setup cost. The test files themselves are lightweight.

---

## What NOT to Test

- **Cytoscape.js internals** — Don't test that `cy.fit()` works. That's Cytoscape's
  responsibility.
- **CSS rendering fidelity** — Don't assert exact pixel positions of styled elements.
  Assert that classes are applied; trust the browser to render them.
- **Third-party CDN availability** — Don't test that CDN scripts load. Use local
  fallbacks if reliability matters (see `troubleshooting.md`).
- **Every possible filter combination** — Test boundary cases (all on, all off,
  date edges), not every permutation.
- **Canvas pixel colors** — Cytoscape renders to a canvas. Asserting pixel colors
  is fragile. Assert on Cytoscape's data model (`.hasClass()`, `.visible()`,
  `.style()`) instead.
