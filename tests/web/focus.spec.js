// @ts-check
const { test, expect } = require('@playwright/test');
const { createServer } = require('http');
const { readFileSync } = require('fs');
const { join } = require('path');

const WEB_DIR = join(__dirname, '..', '..', 'web');

function readWebJS(filename) {
  return readFileSync(join(WEB_DIR, 'js', filename), 'utf-8');
}

/*
 * Mock graph:
 *
 *         alpha ─── beta ─── gamma
 *                    │
 *                  delta ─── epsilon
 *
 *   zeta (disconnected)
 *
 * Initial focus on `beta` → visible: {alpha, beta, gamma, delta};
 *                            dimmed: {epsilon, zeta}.
 * Clicking delta (peripheral) → visible: {alpha, beta, gamma, delta, epsilon};
 *                                dimmed: {zeta}.
 */
const MOCK_NODES = [
  { data: { id: 'alpha',   label: 'Alpha',   type: 'Org' } },
  { data: { id: 'beta',    label: 'Beta',    type: 'Person' } },
  { data: { id: 'gamma',   label: 'Gamma',   type: 'Tech' } },
  { data: { id: 'delta',   label: 'Delta',   type: 'Org' } },
  { data: { id: 'epsilon', label: 'Epsilon', type: 'Tech' } },
  { data: { id: 'zeta',    label: 'Zeta',    type: 'Tech' } },
];

const MOCK_EDGES = [
  { data: { id: 'e1', source: 'alpha', target: 'beta' } },
  { data: { id: 'e2', source: 'beta',  target: 'gamma' } },
  { data: { id: 'e3', source: 'beta',  target: 'delta' } },
  { data: { id: 'e4', source: 'delta', target: 'epsilon' } },
];

/**
 * Build a self-contained HTML page with a lightweight Cytoscape mock
 * sufficient for focus.js (closedNeighborhood, union, getElementById, etc).
 */
function buildTestHTML() {
  const focusJS = readWebJS('focus.js');
  const tooltipsJS = readWebJS('tooltips.js');

  return `<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Focus Test</title>
<style>
  .hidden { display: none !important; }
  #main-content { position: relative; width: 800px; height: 400px; }
  #tooltip { position: absolute; opacity: 0; }
  #tooltip.visible { opacity: 1; }
</style>
</head>
<body>
<div id="app">
  <main id="main-content"></main>
  <div id="tooltip" role="tooltip"></div>
</div>

<script>
// --- Minimal Cytoscape mock ---
function createMockCy(nodes, edges) {
  const nodeMap = new Map();
  const edgeMap = new Map();

  class MockEle {
    constructor(data, group) {
      this._data = data;
      this._group = group;
      this._classes = new Set();
    }
    _eleId() { return this._group + ':' + this._data.id; }
    // Element accessors used directly during forEach iteration. Real
    // Cytoscape wraps each iteration value in a single-element collection,
    // but exposing the same methods on the raw element keeps the mock simple.
    id() { return this._data.id; }
    data(key) { return key ? this._data[key] : this._data; }
    hasClass(cls) { return this._classes.has(cls); }
    addClass(cls) { this._classes.add(cls); return this; }
    removeClass(cls) { this._classes.delete(cls); return this; }
    source() { return nodeMap.get(this._data.source); }
    target() { return nodeMap.get(this._data.target); }
  }

  // Cytoscape's API: cy.getElementById, cy.nodes(), etc all return
  // Collections — methods like data() / hasClass() / id() delegate to
  // the first element. Edge cases (empty collection) return undefined.
  class Collection {
    constructor(eles) {
      const seen = new Set();
      this._eles = [];
      (eles || []).forEach(e => {
        if (!e) return;
        const k = e._eleId();
        if (seen.has(k)) return;
        seen.add(k);
        this._eles.push(e);
      });
    }
    get length() { return this._eles.length; }
    forEach(fn) { this._eles.forEach(fn); return this; }
    id() { return this._eles[0]?._data.id; }
    data(key) {
      const e = this._eles[0];
      if (!e) return undefined;
      return key ? e._data[key] : e._data;
    }
    hasClass(cls) { return this._eles.length > 0 && this._eles[0]._classes.has(cls); }
    addClass(cls) {
      const parts = Array.isArray(cls) ? cls : String(cls).split(/\\s+/);
      this._eles.forEach(e => parts.forEach(c => e._classes.add(c)));
      return this;
    }
    removeClass(cls) {
      const parts = Array.isArray(cls) ? cls : String(cls).split(/\\s+/);
      this._eles.forEach(e => parts.forEach(c => e._classes.delete(c)));
      return this;
    }
    union(other) {
      if (!other) return new Collection(this._eles);
      const list = other._eles || (Array.isArray(other) ? other : [other]);
      return new Collection(this._eles.concat(list));
    }
    closedNeighborhood(filter) {
      const all = [];
      this._eles.forEach(node => {
        if (node._group !== 'nodes') return;
        all.push(node);
        edges.forEach(e => {
          if (e.data.source === node._data.id) {
            const tgt = nodeMap.get(e.data.target);
            if (tgt) { all.push(tgt); all.push(edgeMap.get(e.data.id)); }
          } else if (e.data.target === node._data.id) {
            const src = nodeMap.get(e.data.source);
            if (src) { all.push(src); all.push(edgeMap.get(e.data.id)); }
          }
        });
      });
      let coll = new Collection(all);
      if (filter === 'node') coll = new Collection(coll._eles.filter(e => e._group === 'nodes'));
      else if (filter === 'edge') coll = new Collection(coll._eles.filter(e => e._group === 'edges'));
      return coll;
    }
  }

  nodes.forEach(n => {
    nodeMap.set(n.data.id, new MockEle(n.data, 'nodes'));
  });
  const edgeEles = [];
  edges.forEach(e => {
    const ele = new MockEle(e.data, 'edges');
    edgeMap.set(e.data.id, ele);
    edgeEles.push(ele);
  });

  return {
    collection() { return new Collection([]); },
    getElementById(id) {
      const ele = nodeMap.get(id) || edgeMap.get(id);
      return new Collection(ele ? [ele] : []);
    },
    nodes() { return new Collection(Array.from(nodeMap.values())); },
    edges() { return new Collection(edgeEles); },
    elements() {
      return new Collection(Array.from(nodeMap.values()).concat(edgeEles));
    },
    // Stub for cy.on — initializeTooltips registers Cytoscape event
    // handlers we don't exercise from JS; the tooltip click delegation
    // attaches to the DOM element, not Cytoscape.
    on() { return this; }
  };
}

const mockNodes = ${JSON.stringify(MOCK_NODES)};
const mockEdges = ${JSON.stringify(MOCK_EDGES)};
window.cy = createMockCy(mockNodes, mockEdges);
</script>

<!-- focus.js under test -->
<script>${focusJS}</script>

<!-- tooltips.js (delegated Focus button click handler under test) -->
<script>${tooltipsJS}</script>

<script>
// Wire global handlers (Esc + popstate).
if (typeof initFocusGlobalHandlers === 'function') {
  initFocusGlobalHandlers(window.cy);
}
// Wire tooltip click delegation (Sprint 14B follow-up).
if (typeof initializeTooltips === 'function') {
  initializeTooltips(window.cy);
}
// Re-enter focus from URL if ?focus= is present.
if (typeof initFocusFromUrl === 'function') {
  initFocusFromUrl(window.cy);
}
window.__ready = true;
</script>
</body></html>`;
}

function startServer() {
  return new Promise((resolve) => {
    const server = createServer((req, res) => {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(buildTestHTML());
    });
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      resolve({ server, port, url: `http://127.0.0.1:${port}` });
    });
  });
}

let serverInfo;

test.beforeAll(async () => {
  serverInfo = await startServer();
});

test.afterAll(async () => {
  if (serverInfo?.server) serverInfo.server.close();
});

test.describe('Focus mode — entry + dimming (Sprint 14B)', () => {

  test('enterFocus dims everything outside focused node + 1-hop neighbors', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    const result = await page.evaluate(() => {
      window.enterFocus(window.cy, 'beta');
      const dimmedNodes = [];
      const visibleNodes = [];
      window.cy.nodes().forEach(n => {
        (n.hasClass('focus-dimmed') ? dimmedNodes : visibleNodes).push(n.id());
      });
      return {
        active: window.isFocusActive(),
        focusedIds: Array.from(window.FocusState.focusedIds),
        dimmedNodes: dimmedNodes.sort(),
        visibleNodes: visibleNodes.sort()
      };
    });

    expect(result.active).toBe(true);
    expect(result.focusedIds).toEqual(['beta']);
    // beta's neighborhood: alpha, beta, gamma, delta. Dimmed: epsilon, zeta.
    expect(result.visibleNodes).toEqual(['alpha', 'beta', 'delta', 'gamma']);
    expect(result.dimmedNodes).toEqual(['epsilon', 'zeta']);
  });

  test('focus chip displays focused label', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    await page.evaluate(() => window.enterFocus(window.cy, 'beta'));

    const chip = page.locator('#focus-chip');
    await expect(chip).toBeVisible();
    await expect(chip.locator('.focus-chip-text')).toHaveText('Beta');
  });

  test('expandFocus adds peripheral neighbor to focused set', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    const result = await page.evaluate(() => {
      window.enterFocus(window.cy, 'beta');
      const peripheralCheck = window.isPeripheralNeighbor(window.cy, 'delta');
      window.expandFocus(window.cy, 'delta');
      const dimmed = [];
      const visible = [];
      window.cy.nodes().forEach(n => {
        (n.hasClass('focus-dimmed') ? dimmed : visible).push(n.id());
      });
      return {
        peripheralCheck,
        focusedIds: Array.from(window.FocusState.focusedIds).sort(),
        dimmed: dimmed.sort(),
        visible: visible.sort()
      };
    });

    expect(result.peripheralCheck).toBe(true);
    expect(result.focusedIds).toEqual(['beta', 'delta']);
    // beta-neighborhood ∪ delta-neighborhood = alpha, beta, gamma, delta, epsilon.
    expect(result.visible).toEqual(['alpha', 'beta', 'delta', 'epsilon', 'gamma']);
    expect(result.dimmed).toEqual(['zeta']);
  });

  test('chip shows "+N more" with multiple focused entities', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    await page.evaluate(() => {
      window.enterFocus(window.cy, 'beta');
      window.expandFocus(window.cy, 'delta');
    });

    const chipText = await page.locator('#focus-chip .focus-chip-text').textContent();
    expect(chipText).toBe('Beta + 1 more');
  });

  test('isPeripheralNeighbor returns false for already-focused id', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    const isPeripheral = await page.evaluate(() => {
      window.enterFocus(window.cy, 'beta');
      return window.isPeripheralNeighbor(window.cy, 'beta');
    });
    expect(isPeripheral).toBe(false);
  });

  test('isPeripheralNeighbor returns false for deeply-dimmed node', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    const isPeripheral = await page.evaluate(() => {
      window.enterFocus(window.cy, 'beta');
      // epsilon is 2 hops away from beta — outside 1-hop neighborhood
      return window.isPeripheralNeighbor(window.cy, 'epsilon');
    });
    expect(isPeripheral).toBe(false);
  });

});

test.describe('Focus mode — edges', () => {

  test('edges between visible nodes are not dimmed', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    const undimmed = await page.evaluate(() => {
      window.enterFocus(window.cy, 'beta');
      const out = [];
      window.cy.edges().forEach(e => {
        if (!e.hasClass('focus-dimmed')) out.push(e.data('id'));
      });
      return out.sort();
    });

    // e1 (alpha-beta), e2 (beta-gamma), e3 (beta-delta) connect visible nodes
    expect(undimmed).toEqual(['e1', 'e2', 'e3']);
  });

  test('edges touching dimmed nodes are dimmed', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    const dimmed = await page.evaluate(() => {
      window.enterFocus(window.cy, 'beta');
      const out = [];
      window.cy.edges().forEach(e => {
        if (e.hasClass('focus-dimmed')) out.push(e.data('id'));
      });
      return out.sort();
    });

    // e4 (delta-epsilon) — epsilon is dimmed, so this edge is dimmed too
    expect(dimmed).toEqual(['e4']);
  });

});

test.describe('Focus mode — exit gestures', () => {

  test('exitFocus clears state, dimming, and chip', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    const result = await page.evaluate(() => {
      window.enterFocus(window.cy, 'beta');
      window.exitFocus(window.cy);
      const dimmed = [];
      window.cy.nodes().forEach(n => {
        if (n.hasClass('focus-dimmed')) dimmed.push(n.id());
      });
      return {
        active: window.isFocusActive(),
        focusedSize: window.FocusState.focusedIds.size,
        dimmed
      };
    });

    expect(result.active).toBe(false);
    expect(result.focusedSize).toBe(0);
    expect(result.dimmed).toEqual([]);

    const chip = page.locator('#focus-chip');
    await expect(chip).toBeHidden();
  });

  test('Esc key exits focus mode', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    await page.evaluate(() => window.enterFocus(window.cy, 'beta'));
    expect(await page.evaluate(() => window.isFocusActive())).toBe(true);

    await page.keyboard.press('Escape');
    expect(await page.evaluate(() => window.isFocusActive())).toBe(false);
  });

  test('chip close button exits focus mode', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    await page.evaluate(() => window.enterFocus(window.cy, 'beta'));
    await page.locator('#focus-chip .focus-chip-close').click();
    expect(await page.evaluate(() => window.isFocusActive())).toBe(false);
  });

});

test.describe('Focus mode — URL state', () => {

  test('enterFocus writes ?focus= to URL', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    await page.evaluate(() => window.enterFocus(window.cy, 'beta'));

    const url = page.url();
    expect(url).toContain('focus=beta');
  });

  test('exitFocus removes ?focus= from URL', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    await page.evaluate(() => {
      window.enterFocus(window.cy, 'beta');
      window.exitFocus(window.cy);
    });
    expect(page.url()).not.toContain('focus=');
  });

  test('expandFocus updates URL with comma-separated ids', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    await page.evaluate(() => {
      window.enterFocus(window.cy, 'beta');
      window.expandFocus(window.cy, 'delta');
    });

    const url = page.url();
    expect(url).toMatch(/focus=beta(%2C|,)delta/);
  });

  test('reload with ?focus= re-enters focus mode', async ({ page }) => {
    await page.goto(`${serverInfo.url}/?focus=beta`);
    await page.waitForFunction(() => window.__ready);

    const result = await page.evaluate(() => ({
      active: window.isFocusActive(),
      focusedIds: Array.from(window.FocusState.focusedIds),
    }));

    expect(result.active).toBe(true);
    expect(result.focusedIds).toEqual(['beta']);

    const chip = page.locator('#focus-chip');
    await expect(chip).toBeVisible();
    await expect(chip.locator('.focus-chip-text')).toHaveText('Beta');
  });

  test('reload with ?focus= for unknown id strips param and stays in full graph', async ({ page }) => {
    await page.goto(`${serverInfo.url}/?focus=nonexistent`);
    await page.waitForFunction(() => window.__ready);

    const result = await page.evaluate(() => ({
      active: window.isFocusActive(),
      url: window.location.href,
    }));

    expect(result.active).toBe(false);
    expect(result.url).not.toContain('focus=');
  });

  test('browser back button exits focus mode', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    await page.evaluate(() => window.enterFocus(window.cy, 'beta'));
    expect(await page.evaluate(() => window.isFocusActive())).toBe(true);

    await page.goBack();
    expect(await page.evaluate(() => window.isFocusActive())).toBe(false);
  });

});

test.describe('Tooltip Focus action', () => {

  // Helper: inject the tooltip content that showNodeTooltip would render,
  // so we can exercise the delegated click handler without simulating a
  // real Cytoscape hover event (which our mock cy doesn't support).
  async function injectTooltipFor(page, nodeId) {
    await page.evaluate((id) => {
      const tooltip = document.getElementById('tooltip');
      tooltip.classList.add('visible');
      tooltip.innerHTML = `
        <div class="tooltip-actions">
          <span class="tooltip-hint">Click for details</span>
          <button type="button"
                  class="tooltip-action-btn"
                  data-tooltip-action="focus"
                  data-node-id="${id}">
            Focus
          </button>
        </div>
      `;
    }, nodeId);
  }

  test('clicking the Focus button engages focus mode', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    await injectTooltipFor(page, 'beta');
    await page.locator('#tooltip [data-tooltip-action="focus"]').click();

    const result = await page.evaluate(() => ({
      active: window.isFocusActive(),
      focusedIds: Array.from(window.FocusState.focusedIds),
    }));

    expect(result.active).toBe(true);
    expect(result.focusedIds).toEqual(['beta']);
  });

  test('clicking the Focus button hides the tooltip', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    await injectTooltipFor(page, 'beta');
    await expect(page.locator('#tooltip')).toHaveClass(/visible/);

    await page.locator('#tooltip [data-tooltip-action="focus"]').click();
    await expect(page.locator('#tooltip')).not.toHaveClass(/visible/);
  });

  test('Focus button URL state matches direct enterFocus', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    await injectTooltipFor(page, 'beta');
    await page.locator('#tooltip [data-tooltip-action="focus"]').click();

    expect(page.url()).toContain('focus=beta');
    await expect(page.locator('#focus-chip')).toBeVisible();
    await expect(page.locator('#focus-chip .focus-chip-text')).toHaveText('Beta');
  });

  test('Focus button focuses the right entity (delta, not beta)', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    // Inject a tooltip for delta, click its Focus button.
    await injectTooltipFor(page, 'delta');
    await page.locator('#tooltip [data-tooltip-action="focus"]').click();

    const focusedIds = await page.evaluate(() =>
      Array.from(window.FocusState.focusedIds)
    );
    expect(focusedIds).toEqual(['delta']);
  });

  test('click on tooltip background (non-button) does NOT engage focus', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    await injectTooltipFor(page, 'beta');
    // Click on the hint span — same tooltip element, but not the button.
    await page.locator('#tooltip .tooltip-hint').click();

    const active = await page.evaluate(() => window.isFocusActive());
    expect(active).toBe(false);
  });

  test('stopPropagation: button click does not bubble past the tooltip', async ({ page }) => {
    await page.goto(`${serverInfo.url}/`);
    await page.waitForFunction(() => window.__ready);

    // Install a sentinel handler on the document body. If the button
    // click bubbles past the tooltip's stopPropagation, this counter
    // will tick.
    await page.evaluate(() => {
      window.__bubbleCount = 0;
      document.body.addEventListener('click', (e) => {
        if (e.target.closest('[data-tooltip-action="focus"]')) {
          window.__bubbleCount += 1;
        }
      });
    });

    await injectTooltipFor(page, 'beta');
    await page.locator('#tooltip [data-tooltip-action="focus"]').click();

    const bubbleCount = await page.evaluate(() => window.__bubbleCount);
    expect(bubbleCount).toBe(0);
  });

});
