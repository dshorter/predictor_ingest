# Playwright Web Tests — Guide

**Status:** Active
**Date:** 2026-03-29
**Location:** `tests/web/`

## Quick Start

```bash
npm install                    # one-time setup
npx playwright test            # run all web tests
npx playwright test tests/web/smoke.spec.js --config=tests/web/playwright.config.js --reporter=list
```

## Architecture

### The CDN Problem

The web client (`web/index.html`) loads Cytoscape.js, layout extensions, and fonts
from CDNs. This creates two problems for automated testing:

1. **Sandboxed environments** (CI runners, air-gapped machines) have no external
   network access — CDN requests time out at 30s and the app never initializes.
2. **CDN flakiness** makes tests non-deterministic — a slow CDN turns a passing
   test suite into a flaky one.

We hit this during initial setup: full-page tests against `index.html` timed out
every run because Cytoscape.js and fcose couldn't load from `cdn.jsdelivr.net`.

### Solution: Self-Contained Test Harness

Instead of loading the real `index.html`, each test file builds a **self-contained
HTML page** with:

1. **Real app CSS** — loaded from `web/css/` via `readFileSync` and inlined in a
   `<style>` tag. Tests validate real styling (semantic tokens, panel positioning).

2. **Cytoscape mock** — a lightweight mock that implements enough of the Cytoscape.js
   API for the app modules to function: `nodes()`, `edges()`, `elements()`,
   `getElementById()`, `on()`, `animate()`, `zoom()`, `pan()`, `fit()`, `resize()`,
   and element methods (`data()`, `position()`, `degree()`, `connectedEdges()`,
   `neighborhood()`, `select()`, `addClass()`, etc.).

3. **Real app JS modules** — loaded from `web/js/` via `readFileSync` and injected
   as `<script>` tags. This is the key insight: **we test real application code**
   against a mock graph engine, not a mock of our own code.

4. **Fixture data** — JSON files in `tests/web/fixtures/` that provide a known
   graph dataset (the Apex Studios fictional scenario from the guided tour spec).

5. **Inline HTTP server** — Node's `http.createServer` serves the built HTML on a
   random port. No external server process needed.

```
┌─────────────────────────────────────────────┐
│  Test HTML (built in memory)                │
│                                             │
│  ┌──────────┐  ┌────────────────────────┐   │
│  │ Real CSS │  │ DOM: toolbar, panels,  │   │
│  │ (inlined)│  │ cy container, etc.     │   │
│  └──────────┘  └────────────────────────┘   │
│                                             │
│  ┌──────────────────┐  ┌────────────────┐   │
│  │ Cytoscape Mock   │  │ Fixture JSON   │   │
│  │ (EleCollection,  │  │ (trending.json)│   │
│  │  MockElement)    │  │                │   │
│  └──────────────────┘  └────────────────┘   │
│                                             │
│  ┌──────────────────────────────────────┐   │
│  │ Real app JS: utils.js, panels.js,   │   │
│  │ whats-hot.js, search.js             │   │
│  └──────────────────────────────────────┘   │
│                                             │
│  ┌──────────────────────────────────────┐   │
│  │ Event wiring (mimics app.js setup)  │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### What This Pattern Tests

- **Panel logic** — open, close, mutual exclusivity, DOM manipulation
- **Keyboard shortcuts** — H for hot panel, ? for help, etc.
- **CSS classes** — semantic tokens, hidden/visible state, theme switching
- **Data flow** — fixture data → Cytoscape mock → app JS → rendered DOM
- **Interaction sequences** — node tap → detail panel → edge tap → evidence panel

### What This Pattern Does NOT Test

- Cytoscape.js rendering (canvas pixels, node positions, layout algorithms)
- CDN loading and initialization
- Real network requests
- Visual regression (screenshots)

For those, you'd need integration tests against the real `index.html` with bundled
(not CDN) dependencies — a future task.

## File Layout

```
tests/web/
├── playwright.config.js     # Playwright config (chromium, headless, bypassCSP)
├── smoke.spec.js            # Baseline smoke tests (29 tests)
├── lens.spec.js             # Regional lens tests (pre-existing)
└── fixtures/
    ├── domain.json           # Fixture domain config
    └── trending.json         # Fixture graph data (Apex Studios scenario)
```

## Cytoscape Mock Reference

The mock lives inside each test file's `buildTestHTML()` function. When adding
new tests that need additional Cytoscape API surface, extend the mock there.

### Currently Implemented

| Class / Object | Methods |
|----------------|---------|
| `EleCollection` | `length`, `filter`, `forEach`, `map`, `sort`, `slice`, `first`, `not`, `addClass`, `removeClass`, `unselect`, `select`, `edgesWith`, `[Symbol.iterator]` |
| `MockElement` | `data`, `id`, `position`, `hasClass`, `addClass`, `removeClass`, `select`, `unselect`, `isNode`, `isEdge`, `degree`, `connectedEdges`, `neighborhood`, `source`, `target`, `emit` |
| `window.cy` | `nodes`, `edges`, `elements`, `getElementById`, `on`, `animate`, `zoom`, `pan`, `extent`, `fit`, `resize`, `container` |

### Adding New Mock Methods

When a test fails with `foo is not a function`, it usually means the real app JS
calls a Cytoscape API method that the mock doesn't implement yet. The fix is:

1. Check the [Cytoscape.js docs](https://js.cytoscape.org/) for the method's
   expected signature and return value.
2. Add a minimal implementation to `MockElement` or `window.cy` in `buildTestHTML()`.
3. The implementation only needs to be correct enough for the test scenario —
   it doesn't need to be a full Cytoscape reimplementation.

**Example:** The `neighborhood()` method was added when `getHotList()` in
`whats-hot.js` called `node.neighborhood('node[type = "Document"]')`. The mock
implementation finds connected nodes via the edge list and optionally filters
by a `type` selector — just enough for the hot list to work.

## Fixture Data

`tests/web/fixtures/trending.json` uses the **Apex Studios** fictional dataset
from the guided tour spec (`docs/ux/guided-tour-spec.md`). It contains:

- **8 nodes:** Apex Studios, Nova Labs, Dr. Mira Chen, Helios, NeuralForge,
  Frontier Safety, SynthBench, Project Titan
- **9 edges:** LAUNCHED, CREATED, EVALUATED_ON, HIRED, PARTNERED_WITH,
  MENTIONS (x2), PUBLISHED, USES_TECH
- **Narratives** on 4 nodes (for What's Hot panel testing)
- **Evidence** on 4 edges (for evidence panel testing)

This dataset will also serve as the foundation for guided tour sample data
(Sprint 10).

## Writing New Tests

### Pattern

```javascript
test.describe('My Feature', () => {
  test('description', async ({ page }) => {
    await loadApp(page);  // navigates + waits for window.__ready

    // Trigger interactions via page.evaluate (calls real app functions)
    await page.evaluate(() => {
      const node = window.cy.getElementById('org:apex-studios');
      node.emit('tap');
    });

    // Assert DOM state via Playwright locators
    await expect(page.locator('#detail-panel')).not.toHaveClass(/hidden/);
  });
});
```

### Tips

- **Use `page.evaluate()`** to call app functions and trigger Cytoscape events.
  Don't try to click on the `#cy` canvas — there's no real Cytoscape rendering.
- **Use Playwright locators** (`page.locator()`, `expect().toHaveClass()`) for
  DOM assertions. These auto-retry with timeouts, making tests resilient to
  async panel animations.
- **Check `window.__ready`** before interacting. The `loadApp()` helper does
  this automatically.
- **Store animation args** on `window._lastCyAnimate` to assert zoom-to-node
  behavior (center coordinates, zoom level, offsets).

## Troubleshooting

### Tests time out at 30s

If you see tests hanging for 30s, the test is probably trying to load external
resources. Make sure your test uses the self-contained HTML approach, not a
direct `page.goto()` to `index.html`.

### `foo is not a function`

The Cytoscape mock is missing an API method. See "Adding New Mock Methods" above.

### `old_string is not unique` or element not found

Fixture data may have changed. Check `tests/web/fixtures/trending.json` matches
what the test expects (node IDs, edge IDs, data fields).

### Playwright version mismatch

The installed Playwright version must match the browser binaries. If you see
"browser revision is not downloaded", run:
```bash
npx playwright install chromium
```
If that fails in a sandboxed environment, ensure `package.json` pins a version
whose browsers are already available:
```bash
npm install --save-dev playwright@1.56.1 @playwright/test@1.56.1
```

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-28 | Self-contained HTML over full-page tests | CDN unreachable in sandbox; mock approach isolates app logic |
| 2026-03-28 | Cytoscape mock over bundled library | Faster tests (~6s for 29), no build step, tests focus on app code not rendering |
| 2026-03-28 | Fixture data reuses tour sample dataset | Single fictional dataset serves both testing and guided tour |
| 2026-03-29 | `neighborhood()` added to mock | `getHotList()` in whats-hot.js needs it for Document node lookup |
