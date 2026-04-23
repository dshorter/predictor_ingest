// @ts-check
/**
 * Baseline Smoke Tests
 *
 * Tests the web app's JS modules with fixture graph data.
 * Uses a self-contained HTML page with a Cytoscape mock (no CDN needed).
 * Loads the actual app JS files (panels.js, whats-hot.js, etc.) to test
 * real panel logic, mutual exclusivity, and interaction handlers.
 */
const { test, expect } = require('@playwright/test');
const { createServer } = require('http');
const { readFileSync } = require('fs');
const { join } = require('path');

const WEB_DIR = join(__dirname, '..', '..', 'web');
const FIXTURES_DIR = join(__dirname, 'fixtures');

/** Read a file from web/ */
function readWeb(rel) {
  return readFileSync(join(WEB_DIR, rel), 'utf-8');
}

// Fixture data
const FIXTURE_TRENDING = JSON.parse(readFileSync(join(FIXTURES_DIR, 'trending.json'), 'utf-8'));

/**
 * Build a self-contained test HTML page.
 * Includes a Cytoscape mock + the real app JS modules.
 */
function buildTestHTML() {
  // Load real app JS files
  const utilsJS = readWeb('js/utils.js');
  const panelsJS = readWeb('js/panels.js');
  const whatsHotJS = readWeb('js/whats-hot.js');
  const searchJS = readWeb('js/search.js');

  // Load real CSS
  const mainCSS = [
    readWeb('css/tokens.css'),
    readWeb('css/reset.css'),
    readWeb('css/base.css'),
    readWeb('css/components/toolbar.css'),
    readWeb('css/components/panel.css'),
    readWeb('css/components/button.css'),
    readWeb('css/components/badge.css'),
    readWeb('css/graph/cytoscape.css'),
    readWeb('css/utilities.css'),
  ].join('\n');

  const fixture = JSON.stringify(FIXTURE_TRENDING);

  return `<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="UTF-8">
  <title>Smoke Test Harness</title>
  <style>${mainCSS}</style>
</head>
<body>
  <header id="toolbar" class="toolbar">
    <div class="toolbar-left">
      <h1 id="app-title" class="app-title">Test Domain</h1>
      <div class="toolbar-group">
        <select id="view-selector">
          <option value="trending" selected>Trending</option>
          <option value="claims">Claims</option>
          <option value="mentions">Mentions</option>
          <option value="dependencies">Dependencies</option>
        </select>
      </div>
      <input id="search-input" type="text" placeholder="Search nodes...">
    </div>
    <div class="toolbar-right">
      <button id="hot-toggle" title="What's Hot (H)">🔥</button>
      <button id="theme-toggle" title="Toggle theme">☀</button>
      <button id="navigator-toggle" title="Toggle minimap">🗺</button>
      <span id="graph-stats"></span>
    </div>
  </header>

  <main id="graph-container" style="position:relative; width:100%; height:600px;">
    <div id="cy" style="width:100%; height:100%;"></div>

    <!-- Filter panel (right) -->
    <aside id="filter-panel" class="panel panel-right collapsed">
      <button class="panel-close" aria-label="Close">&times;</button>
      <div id="filter-content">Filter controls</div>
    </aside>

    <!-- Detail panel (left) -->
    <aside id="detail-panel" class="panel panel-left hidden">
      <button class="panel-close" aria-label="Close">&times;</button>
      <div id="detail-content"></div>
    </aside>

    <!-- What's Hot panel (left) -->
    <aside id="hot-panel" class="panel panel-left hidden" role="complementary" aria-label="What's Hot">
      <button class="panel-close" aria-label="Close">&times;</button>
      <div id="hot-content"></div>
    </aside>

    <!-- Evidence panel (left — Sprint 8B.2) -->
    <aside id="evidence-panel" class="panel panel-left hidden">
      <button class="panel-close" aria-label="Close">&times;</button>
      <div id="evidence-content"></div>
    </aside>

    <!-- Help panel (right) -->
    <aside id="help-panel" class="panel panel-right hidden" role="dialog" aria-labelledby="help-title">
      <button class="panel-close" aria-label="Close">&times;</button>
      <div>Help content</div>
    </aside>

    <!-- Navigator -->
    <div id="cy-navigator" class="navigator-container hidden"></div>
  </main>

  <!-- Accessibility live region -->
  <div id="sr-announcer" aria-live="polite" class="invisible" style="position:absolute;left:-9999px;"></div>

<script>
// ========================================================================
// Cytoscape Mock — implements enough API for panels, search, and hot list
// ========================================================================
(function() {
  const fixture = ${fixture};
  const _nodes = [];
  const _edges = [];
  const _handlers = {};

  class EleCollection {
    constructor(eles) { this._eles = eles; }
    get length() { return this._eles.length; }
    filter(fn) { return new EleCollection(this._eles.filter(fn)); }
    forEach(fn) { this._eles.forEach(fn); }
    map(fn) { return this._eles.map(fn); }
    sort(fn) { return new EleCollection([...this._eles].sort(fn)); }
    slice(a,b) { return new EleCollection(this._eles.slice(a,b)); }
    first() { return this._eles[0]; }
    not(sel) {
      if (typeof sel === 'string') {
        const cls = sel.replace('.','');
        return new EleCollection(this._eles.filter(e => !e.hasClass(cls)));
      }
      const ids = new Set(sel._eles.map(e => e._data.id));
      return new EleCollection(this._eles.filter(e => !ids.has(e._data.id)));
    }
    addClass(cls) { this._eles.forEach(e => e.addClass(cls)); return this; }
    removeClass(cls) { this._eles.forEach(e => e.removeClass(cls)); return this; }
    unselect() { this._eles.forEach(e => e._selected = false); return this; }
    select() { this._eles.forEach(e => e._selected = true); return this; }
    show() { this._eles.forEach(e => e.removeClass('filtered-out')); return this; }
    edges() {
      return new EleCollection(this._eles.filter(e => e._group === 'edges'));
    }
    nodes() {
      return new EleCollection(this._eles.filter(e => e._group === 'nodes'));
    }
    edgesWith(other) {
      const ids = new Set(other._eles.map(e => e._data.id));
      return new EleCollection(_edges.filter(e =>
        ids.has(e._data.source) && ids.has(e._data.target)));
    }
    [Symbol.iterator]() { return this._eles[Symbol.iterator](); }
  }

  class MockElement {
    constructor(data, group) {
      this._data = { ...data };
      this._group = group;
      this._classes = new Set();
      this._selected = false;
      this._position = { x: Math.random()*500, y: Math.random()*400 };
    }
    data(key) { return key !== undefined ? this._data[key] : this._data; }
    id() { return this._data.id; }
    position(key) { return key ? this._position[key] : {...this._position}; }
    hasClass(cls) { return this._classes.has(cls); }
    addClass(cls) { this._classes.add(cls); return this; }
    removeClass(cls) { this._classes.delete(cls); return this; }
    select() { this._selected = true; return this; }
    unselect() { this._selected = false; return this; }
    isNode() { return this._group === 'nodes'; }
    isEdge() { return this._group === 'edges'; }
    degree() {
      return _edges.filter(e =>
        e._data.source === this._data.id || e._data.target === this._data.id
      ).length;
    }
    connectedEdges() {
      return new EleCollection(_edges.filter(e =>
        e._data.source === this._data.id || e._data.target === this._data.id
      ));
    }
    source() {
      return _nodes.find(n => n._data.id === this._data.source) || this;
    }
    target() {
      return _nodes.find(n => n._data.id === this._data.target) || this;
    }
    neighborhood(sel) {
      // Return connected nodes, optionally filtered by selector like 'node[type = "Document"]'
      const connectedIds = new Set();
      _edges.forEach(e => {
        if (e._data.source === this._data.id) connectedIds.add(e._data.target);
        if (e._data.target === this._data.id) connectedIds.add(e._data.source);
      });
      let neighbors = _nodes.filter(n => connectedIds.has(n._data.id));
      if (sel) {
        const typeMatch = sel.match(/type\s*=\s*"([^"]+)"/);
        if (typeMatch) {
          neighbors = neighbors.filter(n => n._data.type === typeMatch[1]);
        }
      }
      return new EleCollection(neighbors);
    }
    closedNeighborhood() {
      // Self + neighbor nodes + connecting edges (matches Cytoscape semantics)
      const connectedIds = new Set();
      const connectedEdges = [];
      _edges.forEach(e => {
        if (e._data.source === this._data.id) {
          connectedIds.add(e._data.target);
          connectedEdges.push(e);
        }
        if (e._data.target === this._data.id) {
          connectedIds.add(e._data.source);
          connectedEdges.push(e);
        }
      });
      const neighbors = _nodes.filter(n => connectedIds.has(n._data.id));
      return new EleCollection([this, ...neighbors, ...connectedEdges]);
    }
    show() { this._classes.delete('filtered-out'); return this; }
    emit(event) {
      const handlers = _handlers[event + '-' + this._group] || [];
      handlers.forEach(fn => fn({ target: this }));
    }
  }

  // Build elements from fixture
  fixture.elements.nodes.forEach(n => _nodes.push(new MockElement(n.data, 'nodes')));
  fixture.elements.edges.forEach(e => _edges.push(new MockElement(e.data, 'edges')));

  // The mock cy object
  window.cy = {
    nodes(sel) {
      if (sel) {
        const cls = sel.replace('.','');
        return new EleCollection(_nodes.filter(e => e.hasClass(cls)));
      }
      return new EleCollection(_nodes);
    },
    edges(sel) {
      if (sel) {
        const cls = sel.replace('.','');
        return new EleCollection(_edges.filter(e => e.hasClass(cls)));
      }
      return new EleCollection(_edges);
    },
    elements(sel) {
      const all = [..._nodes, ..._edges];
      if (sel) {
        const cls = sel.replace('.','');
        return new EleCollection(all.filter(e => e.hasClass(cls)));
      }
      return new EleCollection(all);
    },
    getElementById(id) {
      const el = _nodes.find(n => n._data.id === id) || _edges.find(e => e._data.id === id);
      // Return a collection-like that also acts as an element
      if (el) {
        el.length = 1;
        return el;
      }
      return { length: 0, data: () => null };
    },
    on(event, selectorOrFn, fn) {
      if (typeof selectorOrFn === 'string') {
        // cy.on('tap', 'node', fn)
        const group = selectorOrFn === 'node' ? 'nodes' : 'edges';
        const key = event + '-' + group;
        if (!_handlers[key]) _handlers[key] = [];
        _handlers[key].push(fn);
      }
    },
    animate(opts) {
      // Store last animation for assertions
      window._lastCyAnimate = opts;
      return Promise.resolve();
    },
    zoom() { return 1.5; },
    pan() { return { x: 0, y: 0 }; },
    extent() { return { x1: -200, y1: -200, x2: 200, y2: 200 }; },
    fit() {},
    resize() {},
    container() { return document.getElementById('cy'); },
    _statsText: '8 nodes · 9 edges',
  };

  // Update graph stats
  const statsEl = document.getElementById('graph-stats');
  if (statsEl) statsEl.textContent = '8 nodes · 9 edges';
})();

// Stubs for functions used by panels/hot but defined in other modules
function escapeHtml(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function formatDate(d) { return d || 'Unknown'; }
function formatVelocity(v) { return v != null ? v.toFixed(1) + 'x' : '—'; }
function formatRelation(r) { return r ? r.replace(/_/g,' ') : ''; }
function formatDocId(id) { return id || ''; }
function extractDomain(url) { if (!url) return ''; try { return new URL(url).hostname; } catch { return ''; } }
function capitalize(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ''; }
function truncateLabel(s, n) { return s && s.length > n ? s.slice(0,n) + '…' : (s || ''); }
// Mirrors app.js — defined here so dbltap tests can assert dimming
function highlightNeighborhood(cy, node) {
  if (cy.nodes('.search-match').length > 0) return;
  const neighborhood = node.closedNeighborhood();
  cy.elements().addClass('neighborhood-dimmed');
  neighborhood.removeClass('neighborhood-dimmed');
  neighborhood.edges().removeClass('neighborhood-dimmed');
}
function clearNeighborhoodHighlight(cy) {
  cy.elements().removeClass('neighborhood-dimmed');
}
function announceToScreenReader(msg) {
  const el = document.getElementById('sr-announcer');
  if (el) el.textContent = msg;
}
var prefersReducedMotion = true; // skip animations in tests
</script>

<!-- Load real app JS modules -->
<script>${utilsJS}</script>
<script>${panelsJS}</script>
<script>${whatsHotJS}</script>

<script>
// Wire up event handlers that app.js normally sets up
(function() {
  const cy = window.cy;

  // Node tap → open detail panel
  cy.on('tap', 'node', (e) => {
    const node = e.target;
    cy.elements().unselect();
    node.select();
    clearNeighborhoodHighlight(cy);
    highlightNeighborhood(cy, node);
    openNodeDetailPanel(node);
  });

  // Edge tap → open evidence panel
  cy.on('tap', 'edge', (e) => {
    const edge = e.target;
    cy.elements().unselect();
    edge.select();
    clearNeighborhoodHighlight(cy);
    openEvidencePanel(edge);
  });

  // Node dbltap → zoom to neighborhood + highlight + open panel
  // (mirrors app.js initializeEventHandlers)
  cy.on('dbltap', 'node', (e) => {
    const node = e.target;
    node.closedNeighborhood().removeClass('filtered-out').show();
    navigateToNode(node.id(), { zoom: 'neighborhood', updatePanel: true });
  });

  // Initialize panel close buttons
  initializePanels(cy);

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    const ae = document.activeElement;
    if (ae && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA')) return;
    if (e.key === 'h') { toggleHotPanel(); e.preventDefault(); }
    if (e.key === '?') {
      const hp = document.getElementById('help-panel');
      if (hp) hp.classList.toggle('hidden');
      e.preventDefault();
    }
  });

  // Theme toggle
  document.getElementById('theme-toggle')?.addEventListener('click', () => {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme');
    html.setAttribute('data-theme', current === 'dark' ? 'light' : 'dark');
  });

  // Hot toggle button
  document.getElementById('hot-toggle')?.addEventListener('click', () => toggleHotPanel());

  window.__ready = true;
})();
</script>
</body></html>`;
}

// --- Server ---

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

/** Navigate and wait for the mock app to be ready */
async function loadApp(page) {
  await page.goto(serverInfo.url);
  await page.waitForFunction(() => window.__ready === true, { timeout: 10000 });
}


// =========================================================================
//  1. Graph Loading
// =========================================================================

test.describe('Graph Loading', () => {

  test('app loads and renders nodes', async ({ page }) => {
    await loadApp(page);
    const nodeCount = await page.evaluate(() => window.cy.nodes().length);
    expect(nodeCount).toBe(8);
  });

  test('app renders edges', async ({ page }) => {
    await loadApp(page);
    const edgeCount = await page.evaluate(() => window.cy.edges().length);
    expect(edgeCount).toBe(9);
  });

  test('nodes have correct data properties', async ({ page }) => {
    await loadApp(page);
    const apex = await page.evaluate(() => {
      const n = window.cy.getElementById('org:apex-studios');
      return n.length > 0 ? n.data() : null;
    });
    expect(apex).not.toBeNull();
    expect(apex.label).toBe('Apex Studios');
    expect(apex.type).toBe('Org');
    expect(apex.velocity).toBe(2.8);
    expect(apex.narrative).toContain('Project Titan');
  });

  test('graph stats are displayed', async ({ page }) => {
    await loadApp(page);
    const stats = await page.locator('#graph-stats').textContent();
    expect(stats).toContain('8 nodes');
    expect(stats).toContain('9 edges');
  });
});


// =========================================================================
//  2. Panel Interactions
// =========================================================================

test.describe('Panel Interactions', () => {

  test('tapping a node opens the detail panel', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => {
      window.cy.getElementById('org:apex-studios').emit('tap');
    });
    await expect(page.locator('#detail-panel')).not.toHaveClass(/hidden/);
  });

  test('detail panel shows correct node info', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => {
      window.cy.getElementById('org:apex-studios').emit('tap');
    });
    const text = await page.locator('#detail-content').textContent();
    expect(text).toContain('Apex Studios');
    expect(text).toContain('Org');
    expect(text).toContain('Project Titan');
  });

  test('detail panel uses semantic tokens, not hardcoded grays (8B.1)', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => {
      window.cy.getElementById('org:apex-studios').emit('tap');
    });
    const html = await page.locator('#detail-content').innerHTML();
    expect(html).not.toContain('text-gray-');
    expect(html).not.toContain('bg-gray-');
    expect(html).toContain('text-secondary');
    expect(html).toContain('bg-secondary');
  });

  test('tapping an edge opens the evidence panel', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => {
      window.cy.getElementById('e:apex-titan').emit('tap');
    });
    await expect(page.locator('#evidence-panel')).not.toHaveClass(/hidden/);
  });

  test('evidence panel shows edge info and snippet', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => {
      window.cy.getElementById('e:apex-titan').emit('tap');
    });
    const text = await page.locator('#evidence-content').textContent();
    expect(text).toContain('Apex Studios');
    expect(text).toContain('Project Titan');
    expect(text).toContain('TechCrunch');
    expect(text).toContain('large-scale model training');
  });

  test('evidence panel is a left panel (8B.2)', async ({ page }) => {
    await loadApp(page);
    const classes = await page.locator('#evidence-panel').getAttribute('class');
    expect(classes).toContain('panel-left');
    expect(classes).not.toContain('panel-bottom');
  });

  test('mutual exclusivity: node tap closes evidence panel', async ({ page }) => {
    await loadApp(page);

    // Open evidence
    await page.evaluate(() => window.cy.getElementById('e:apex-titan').emit('tap'));
    await expect(page.locator('#evidence-panel')).not.toHaveClass(/hidden/);

    // Tap node → evidence should close, detail should open
    await page.evaluate(() => window.cy.getElementById('org:apex-studios').emit('tap'));
    await expect(page.locator('#detail-panel')).not.toHaveClass(/hidden/);
    await expect(page.locator('#evidence-panel')).toHaveClass(/hidden/);
  });

  test('mutual exclusivity: hot panel closes detail panel', async ({ page }) => {
    await loadApp(page);

    // Open detail
    await page.evaluate(() => window.cy.getElementById('org:apex-studios').emit('tap'));
    await expect(page.locator('#detail-panel')).not.toHaveClass(/hidden/);

    // Open hot → detail should close
    await page.evaluate(() => toggleHotPanel());
    await expect(page.locator('#hot-panel')).not.toHaveClass(/hidden/);
    await expect(page.locator('#detail-panel')).toHaveClass(/hidden/);
  });

  test('mutual exclusivity: edge tap closes hot panel', async ({ page }) => {
    await loadApp(page);

    // Open hot
    await page.evaluate(() => toggleHotPanel());
    await expect(page.locator('#hot-panel')).not.toHaveClass(/hidden/);

    // Tap edge → hot should close, evidence should open
    await page.evaluate(() => window.cy.getElementById('e:apex-titan').emit('tap'));
    await expect(page.locator('#evidence-panel')).not.toHaveClass(/hidden/);
    await expect(page.locator('#hot-panel')).toHaveClass(/hidden/);
  });

  test('panel-left-open class added when left panel opens', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => window.cy.getElementById('org:apex-studios').emit('tap'));
    await expect(page.locator('#cy')).toHaveClass(/panel-left-open/);
  });

  test('panel-left-open class removed when left panel closes', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => window.cy.getElementById('org:apex-studios').emit('tap'));
    await page.locator('#detail-panel .panel-close').click();
    await expect(page.locator('#cy')).not.toHaveClass(/panel-left-open/);
  });

  test('close button works on detail panel', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => window.cy.getElementById('org:apex-studios').emit('tap'));
    await expect(page.locator('#detail-panel')).not.toHaveClass(/hidden/);
    await page.locator('#detail-panel .panel-close').click();
    await expect(page.locator('#detail-panel')).toHaveClass(/hidden/);
  });
});


// =========================================================================
//  3. What's Hot Panel
// =========================================================================

test.describe("What's Hot Panel", () => {

  test('H key opens hot panel', async ({ page }) => {
    await loadApp(page);
    await page.keyboard.press('h');
    await expect(page.locator('#hot-panel')).not.toHaveClass(/hidden/);
  });

  test('hot panel lists trending entities', async ({ page }) => {
    await loadApp(page);
    await page.keyboard.press('h');
    const count = await page.locator('.hot-item').count();
    expect(count).toBeGreaterThan(0);
    expect(count).toBeLessThanOrEqual(10);
  });

  test('hot panel shows narratives', async ({ page }) => {
    await loadApp(page);
    await page.keyboard.press('h');
    const count = await page.locator('.hot-narrative').count();
    expect(count).toBeGreaterThan(0);
    const text = await page.locator('.hot-narrative').first().textContent();
    expect(text.length).toBeGreaterThan(10);
  });

  test('H key toggles hot panel closed', async ({ page }) => {
    await loadApp(page);
    await page.keyboard.press('h');
    await expect(page.locator('#hot-panel')).not.toHaveClass(/hidden/);
    await page.keyboard.press('h');
    await expect(page.locator('#hot-panel')).toHaveClass(/hidden/);
  });

  test('hot toggle button works', async ({ page }) => {
    await loadApp(page);
    await page.locator('#hot-toggle').click();
    await expect(page.locator('#hot-panel')).not.toHaveClass(/hidden/);
  });
});


// =========================================================================
//  4. Toolbar & Theme
// =========================================================================

test.describe('Toolbar & Theme', () => {

  test('toolbar is visible', async ({ page }) => {
    await loadApp(page);
    await expect(page.locator('#toolbar')).toBeVisible();
  });

  test('theme toggle switches to dark mode', async ({ page }) => {
    await loadApp(page);
    await page.locator('#theme-toggle').click();
    const theme = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme')
    );
    expect(theme).toBe('dark');
  });

  test('theme toggle switches back to light mode', async ({ page }) => {
    await loadApp(page);
    await page.locator('#theme-toggle').click();
    await page.locator('#theme-toggle').click();
    const theme = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme')
    );
    expect(theme).toBe('light');
  });

  test('search input is visible', async ({ page }) => {
    await loadApp(page);
    await expect(page.locator('#search-input')).toBeVisible();
  });

  test('? key opens help panel', async ({ page }) => {
    await loadApp(page);
    await page.keyboard.press('?');
    await expect(page.locator('#help-panel')).not.toHaveClass(/hidden/);
  });

  test('view selector is visible with 4 options', async ({ page }) => {
    await loadApp(page);
    await expect(page.locator('#view-selector')).toBeVisible();
    const options = page.locator('#view-selector option');
    await expect(options).toHaveCount(4);
  });
});


// =========================================================================
//  5. Zoom Offset (Sprint 8B.4)
// =========================================================================

test.describe('Zoom Offset with Panel Open (8B.4)', () => {

  test('zoomToNode applies offset when left panel is open', async ({ page }) => {
    await loadApp(page);

    // Open detail panel first
    await page.evaluate(() => window.cy.getElementById('org:apex-studios').emit('tap'));
    await expect(page.locator('#detail-panel')).not.toHaveClass(/hidden/);

    // Call zoomToNode and check the animate args
    const result = await page.evaluate(() => {
      window._lastCyAnimate = null;
      const node = window.cy.getElementById('org:apex-studios');
      zoomToNode(node);
      return window._lastCyAnimate;
    });

    expect(result).not.toBeNull();
    expect(result.center).toBeDefined();
    expect(result.center.x).toBeDefined();
    expect(result.center.y).toBeDefined();
    // The center.x should be offset LEFT of the node position (panel compensation)
    const nodeX = await page.evaluate(() =>
      window.cy.getElementById('org:apex-studios').position('x')
    );
    expect(result.center.x).toBeLessThan(nodeX);
  });

  test('zoomToNode has no offset when no panel is open', async ({ page }) => {
    await loadApp(page);

    const result = await page.evaluate(() => {
      window._lastCyAnimate = null;
      const node = window.cy.getElementById('org:apex-studios');
      zoomToNode(node);
      return {
        animate: window._lastCyAnimate,
        nodeX: node.position('x')
      };
    });

    // With no panel open, center.x should equal node.x (no offset)
    expect(result.animate.center.x).toBe(result.nodeX);
  });
});


// =========================================================================
//  6. Double-Click: Zoom to Neighborhood
// =========================================================================
//
// Regression coverage for the "double-click should zoom to the neighborhood
// AND highlight it" behavior. Previously dbltap fired two conflicting
// animations (fit-neighborhood then zoom-to-node-2x); the second overrode
// the first so the user saw a single-node zoom. The fix routes everything
// through navigateToNode({zoom:'neighborhood'}) which owns the single animation.

test.describe('Double-Click: Zoom to Neighborhood', () => {

  test('dbltap on node triggers a fit animation (not a center+zoom animation)', async ({ page }) => {
    await loadApp(page);

    const result = await page.evaluate(() => {
      window._lastCyAnimate = null;
      window.cy.getElementById('org:apex-studios').emit('dbltap');
      return window._lastCyAnimate;
    });

    expect(result).not.toBeNull();
    // zoom-to-neighborhood uses { fit: { eles, padding } }, NOT { center, zoom }
    expect(result.fit).toBeDefined();
    expect(result.fit.eles).toBeDefined();
    expect(result.center).toBeUndefined();
    expect(result.zoom).toBeUndefined();
  });

  test('dbltap fits to the closed neighborhood (self + neighbors + edges)', async ({ page }) => {
    await loadApp(page);

    const count = await page.evaluate(() => {
      window._lastCyAnimate = null;
      window.cy.getElementById('org:apex-studios').emit('dbltap');
      // closedNeighborhood includes the node itself, its neighbors, and their connecting edges.
      // For apex-studios in the fixture that's clearly > 1 element.
      return window._lastCyAnimate.fit.eles.length;
    });

    expect(count).toBeGreaterThan(1);
  });

  test('dbltap applies neighborhood-dimmed to non-neighbor nodes', async ({ page }) => {
    await loadApp(page);

    const dimming = await page.evaluate(() => {
      const cy = window.cy;
      const target = cy.getElementById('org:apex-studios');
      target.emit('dbltap');

      const neighborhoodIds = new Set(
        target.closedNeighborhood()._eles.map(e => e._data.id)
      );

      let dimmedOutside = 0;
      let dimmedInside = 0;
      cy.elements().forEach(el => {
        const inNeighborhood = neighborhoodIds.has(el._data.id);
        if (el.hasClass('neighborhood-dimmed')) {
          if (inNeighborhood) dimmedInside++;
          else dimmedOutside++;
        }
      });
      return { dimmedInside, dimmedOutside };
    });

    // Non-neighbors should be dimmed; the neighborhood itself should NOT be dimmed.
    expect(dimming.dimmedOutside).toBeGreaterThan(0);
    expect(dimming.dimmedInside).toBe(0);
  });

  test('dbltap opens the detail panel for the target node', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => {
      window.cy.getElementById('org:apex-studios').emit('dbltap');
    });
    await expect(page.locator('#detail-panel')).not.toHaveClass(/hidden/);
    const text = await page.locator('#detail-content').textContent();
    expect(text).toContain('Apex Studios');
  });

  test('dbltap selects the target node', async ({ page }) => {
    await loadApp(page);
    const selected = await page.evaluate(() => {
      const node = window.cy.getElementById('org:apex-studios');
      node.emit('dbltap');
      return node._selected;
    });
    expect(selected).toBe(true);
  });

  test('dbltap reveals filtered-out neighbors so they are included in the fit', async ({ page }) => {
    await loadApp(page);

    const result = await page.evaluate(() => {
      const cy = window.cy;
      const target = cy.getElementById('org:apex-studios');
      // Pre-filter: hide every neighbor of apex-studios
      target.closedNeighborhood()._eles
        .filter(e => e._data.id !== target._data.id)
        .forEach(e => e.addClass('filtered-out'));

      const hiddenBefore = cy.elements().filter(e => e.hasClass('filtered-out')).length;

      target.emit('dbltap');

      const hiddenAfter = cy.elements().filter(e => e.hasClass('filtered-out')).length;
      return { hiddenBefore, hiddenAfter };
    });

    expect(result.hiddenBefore).toBeGreaterThan(0);
    // dbltap must un-hide the neighborhood so they're visible for the fit
    expect(result.hiddenAfter).toBeLessThan(result.hiddenBefore);
  });
});
