// @ts-check
const { test, expect } = require('@playwright/test');
const { createServer } = require('http');
const { readFileSync } = require('fs');
const { join } = require('path');

const WEB_DIR = join(__dirname, '..', '..', 'web');

/**
 * Read a JS file from web/js/ and return its contents.
 */
function readWebJS(filename) {
  return readFileSync(join(WEB_DIR, 'js', filename), 'utf-8');
}

// Mock graph data: 6 nodes, some with region tags from Sprint 7B export
const MOCK_GRAPH_NODES = [
  { data: { id: 'location:atlanta', label: 'Atlanta', type: 'Location', region: ['southeast'] } },
  { data: { id: 'prod:movie_a', label: 'Movie A', type: 'Production', region: ['southeast'] } },
  { data: { id: 'person:director_x', label: 'Director X', type: 'Person', region: ['southeast'] } },
  { data: { id: 'prod:movie_c', label: 'Movie C', type: 'Production' } },
  { data: { id: 'person:director_z', label: 'Director Z', type: 'Person' } },
  { data: { id: 'studio:a24', label: 'A24', type: 'Studio', region: ['southeast'] } },
];

const MOCK_GRAPH_EDGES = [
  { data: { id: 'e:1', source: 'prod:movie_a', target: 'location:atlanta', rel: 'SHOOTS_IN', kind: 'asserted', confidence: 0.9 } },
  { data: { id: 'e:2', source: 'person:director_x', target: 'prod:movie_a', rel: 'DIRECTS', kind: 'asserted', confidence: 0.95 } },
  { data: { id: 'e:3', source: 'studio:a24', target: 'prod:movie_a', rel: 'PRODUCES', kind: 'asserted', confidence: 0.9 } },
  { data: { id: 'e:4', source: 'prod:movie_c', target: 'person:director_z', rel: 'DIRECTS', kind: 'asserted', confidence: 0.9 } },
  { data: { id: 'e:5', source: 'person:director_x', target: 'prod:movie_c', rel: 'DIRECTS', kind: 'asserted', confidence: 0.8 } },
];

// Film domain config with lenses
const FILM_CONFIG = {
  domain: 'film',
  title: 'Film Test',
  lenses: [
    { slug: 'all', label: 'All Regions' },
    { slug: 'southeast', label: 'Southeast US' },
  ],
};

// AI domain config — no lenses
const AI_CONFIG = {
  domain: 'ai',
  title: 'AI Test',
};

/**
 * Build a self-contained test HTML page with a lightweight Cytoscape mock.
 * This avoids CDN dependencies that aren't available in CI.
 */
function buildTestHTML(domainConfig) {
  const lensJS = readWebJS('lens.js');

  return `<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Lens Test</title></head>
<body>
<div id="app">
  <header id="toolbar">
    <div class="toolbar-left">
      <div class="toolbar-group">
        <label for="view-selector">View:</label>
        <select id="view-selector">
          <option value="trending" selected>Trending</option>
        </select>
      </div>
    </div>
    <div class="toolbar-right">
      <span id="graph-stats"></span>
    </div>
  </header>
</div>

<script>
// --- Minimal Cytoscape mock ---
// Implements just enough of the Cytoscape API for lens.js to work.
function createMockCy(nodes, edges) {
  const allElements = [];

  class EleCollection {
    constructor(eles) { this._eles = eles; }
    get length() { return this._eles.length; }
    filter(fn) { return new EleCollection(this._eles.filter(fn)); }
    not(selector) {
      if (typeof selector === 'string') {
        return new EleCollection(this._eles.filter(e => !e.hasClass(selector.replace('.', ''))));
      }
      const ids = new Set(selector._eles.map(e => e._data.id));
      return new EleCollection(this._eles.filter(e => !ids.has(e._data.id)));
    }
    addClass(cls) { this._eles.forEach(e => e.addClass(cls)); return this; }
    removeClass(cls) { this._eles.forEach(e => e.removeClass(cls)); return this; }
    edgesWith(other) {
      const nodeIds = new Set(other._eles.map(e => e._data.id));
      return new EleCollection(
        allElements.filter(e => e._group === 'edges' &&
          nodeIds.has(e._data.source) && nodeIds.has(e._data.target))
      );
    }
    forEach(fn) { this._eles.forEach(fn); }
    [Symbol.iterator]() { return this._eles[Symbol.iterator](); }
  }

  class MockElement {
    constructor(data, group) {
      this._data = data;
      this._group = group;
      this._classes = new Set();
    }
    data(key) { return key ? this._data[key] : this._data; }
    hasClass(cls) { return this._classes.has(cls); }
    addClass(cls) { this._classes.add(cls); return this; }
    removeClass(cls) { this._classes.delete(cls); return this; }
  }

  const nodeEles = nodes.map(n => new MockElement(n.data, 'nodes'));
  const edgeEles = edges.map(e => new MockElement(e.data, 'edges'));
  allElements.push(...nodeEles, ...edgeEles);

  return {
    nodes(selector) {
      if (selector) {
        const cls = selector.replace('.', '');
        return new EleCollection(nodeEles.filter(e => e.hasClass(cls)));
      }
      return new EleCollection(nodeEles);
    },
    edges(selector) {
      if (selector) {
        const cls = selector.replace('.', '');
        return new EleCollection(edgeEles.filter(e => e.hasClass(cls)));
      }
      return new EleCollection(edgeEles);
    },
    elements(selector) {
      if (selector) {
        const cls = selector.replace('.', '');
        return new EleCollection(allElements.filter(e => e.hasClass(cls)));
      }
      return new EleCollection(allElements);
    }
  };
}

// Build mock cy
const mockNodes = ${JSON.stringify(MOCK_GRAPH_NODES)};
const mockEdges = ${JSON.stringify(MOCK_GRAPH_EDGES)};
window.cy = createMockCy(mockNodes, mockEdges);
</script>

<!-- The actual lens.js under test -->
<script>${lensJS}</script>

<script>
// Initialize lens with domain config
const domainConfig = ${JSON.stringify(domainConfig)};
if (typeof initLens === 'function') {
  initLens(window.cy, domainConfig);
}
window.__ready = true;
</script>
</body></html>`;
}

/**
 * Start a server that serves the test HTML.
 */
function startServer() {
  return new Promise((resolve) => {
    const server = createServer((req, res) => {
      const url = new URL(req.url, 'http://localhost');
      const domain = url.searchParams.get('domain') || 'ai';
      const config = domain === 'film' ? FILM_CONFIG : AI_CONFIG;

      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(buildTestHTML(config));
    });

    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      resolve({ server, port, url: `http://127.0.0.1:${port}` });
    });
  });
}

// --- Test suite ---

let serverInfo;

test.beforeAll(async () => {
  serverInfo = await startServer();
});

test.afterAll(async () => {
  if (serverInfo?.server) serverInfo.server.close();
});

test.describe('Lens UI (Sprint 7C)', () => {

  test('lens dropdown renders for film domain', async ({ page }) => {
    await page.goto(`${serverInfo.url}/?domain=film`);
    await page.waitForFunction(() => window.__ready);

    const lensSelector = page.locator('#lens-selector');
    await expect(lensSelector).toBeVisible();

    const options = lensSelector.locator('option');
    await expect(options).toHaveCount(2);
    await expect(options.nth(0)).toHaveText('All Regions');
    await expect(options.nth(1)).toHaveText('Southeast US');
  });

  test('lens defaults to "All Regions"', async ({ page }) => {
    await page.goto(`${serverInfo.url}/?domain=film`);
    await page.waitForFunction(() => window.__ready);

    await expect(page.locator('#lens-selector')).toHaveValue('all');
  });

  test('selecting Southeast dims non-regional nodes', async ({ page }) => {
    await page.goto(`${serverInfo.url}/?domain=film`);
    await page.waitForFunction(() => window.__ready);

    await page.locator('#lens-selector').selectOption('southeast');
    await page.waitForTimeout(100);

    const result = await page.evaluate(() => {
      const cy = window.cy;
      return {
        dimmedNodes: cy.nodes('.region-dimmed').length,
        totalNodes: cy.nodes().length,
        dimmedEdges: cy.edges('.region-dimmed').length,
        totalEdges: cy.edges().length,
      };
    });

    // 4 nodes have region:southeast, 2 do not → 2 dimmed
    expect(result.dimmedNodes).toBe(2);
    expect(result.totalNodes).toBe(6);
  });

  test('selecting All Regions removes all dimming', async ({ page }) => {
    await page.goto(`${serverInfo.url}/?domain=film`);
    await page.waitForFunction(() => window.__ready);

    // Apply Southeast, then switch back to All
    await page.locator('#lens-selector').selectOption('southeast');
    await page.waitForTimeout(50);
    await page.locator('#lens-selector').selectOption('all');
    await page.waitForTimeout(50);

    const dimmed = await page.evaluate(() => {
      return window.cy.elements('.region-dimmed').length;
    });
    expect(dimmed).toBe(0);
  });

  test('stats update when lens is applied', async ({ page }) => {
    await page.goto(`${serverInfo.url}/?domain=film`);
    await page.waitForFunction(() => window.__ready);

    // Apply Southeast lens
    await page.locator('#lens-selector').selectOption('southeast');
    await page.waitForTimeout(100);

    const stats = await page.locator('#graph-stats').textContent();
    // 4 matching out of 6 total
    expect(stats).toContain('4/6 nodes');
  });

  test('stats reset when lens is cleared', async ({ page }) => {
    await page.goto(`${serverInfo.url}/?domain=film`);
    await page.waitForFunction(() => window.__ready);

    await page.locator('#lens-selector').selectOption('southeast');
    await page.waitForTimeout(50);
    await page.locator('#lens-selector').selectOption('all');
    await page.waitForTimeout(50);

    const stats = await page.locator('#graph-stats').textContent();
    expect(stats).toContain('6 nodes');
    expect(stats).not.toContain('/');
  });

  test('lens dropdown has correct label', async ({ page }) => {
    await page.goto(`${serverInfo.url}/?domain=film`);
    await page.waitForFunction(() => window.__ready);

    const label = page.locator('label[for="lens-selector"]');
    await expect(label).toBeVisible();
    await expect(label).toHaveText('Lens:');
  });

  test('edges between regional nodes are not dimmed', async ({ page }) => {
    await page.goto(`${serverInfo.url}/?domain=film`);
    await page.waitForFunction(() => window.__ready);

    await page.locator('#lens-selector').selectOption('southeast');
    await page.waitForTimeout(100);

    const undimmedEdges = await page.evaluate(() => {
      return window.cy.edges().not('.region-dimmed').length;
    });
    // e:1 (movie_a→atlanta), e:2 (director_x→movie_a), e:3 (a24→movie_a)
    // are between southeast nodes = 3 undimmed
    expect(undimmedEdges).toBe(3);
  });

  test('edges touching non-regional nodes are dimmed', async ({ page }) => {
    await page.goto(`${serverInfo.url}/?domain=film`);
    await page.waitForFunction(() => window.__ready);

    await page.locator('#lens-selector').selectOption('southeast');
    await page.waitForTimeout(100);

    const dimmedEdges = await page.evaluate(() => {
      return window.cy.edges('.region-dimmed').length;
    });
    // e:4 (movie_c→director_z) and e:5 (director_x→movie_c) touch non-regional nodes
    expect(dimmedEdges).toBe(2);
  });

});

test.describe('Lens UI — no lenses domain', () => {

  test('lens dropdown does not render for AI domain', async ({ page }) => {
    await page.goto(`${serverInfo.url}/?domain=ai`);
    await page.waitForFunction(() => window.__ready);

    const lensSelector = page.locator('#lens-selector');
    await expect(lensSelector).toHaveCount(0);
  });

  test('lens group element not present for AI domain', async ({ page }) => {
    await page.goto(`${serverInfo.url}/?domain=ai`);
    await page.waitForFunction(() => window.__ready);

    const lensGroup = page.locator('#lens-group');
    await expect(lensGroup).toHaveCount(0);
  });

});
