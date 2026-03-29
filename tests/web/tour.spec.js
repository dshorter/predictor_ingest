// @ts-check
/**
 * Tour Tests — Guided tour orchestration layer
 *
 * Tests tour.js functions (banner, sample detection, step callbacks,
 * localStorage lifecycle) using the self-contained mock approach.
 * Driver.js is NOT loaded — we test the orchestration, not the popover UI.
 */
const { test, expect } = require('@playwright/test');
const { createServer } = require('http');
const { readFileSync } = require('fs');
const { join } = require('path');

const WEB_DIR = join(__dirname, '..', '..', 'web');
const SAMPLE_DIR = join(WEB_DIR, 'data', 'sample');

function readWeb(rel) {
  return readFileSync(join(WEB_DIR, rel), 'utf-8');
}

const SAMPLE_TRENDING = JSON.parse(readFileSync(join(SAMPLE_DIR, 'trending.json'), 'utf-8'));

/**
 * Build test harness with tour.js loaded.
 * Includes a minimal Driver.js mock so startTour() doesn't bail.
 */
function buildTestHTML() {
  const utilsJS = readWeb('js/utils.js');
  const panelsJS = readWeb('js/panels.js');
  const whatsHotJS = readWeb('js/whats-hot.js');
  const tourJS = readWeb('js/tour.js');

  const mainCSS = [
    readWeb('css/tokens.css'),
    readWeb('css/reset.css'),
    readWeb('css/base.css'),
    readWeb('css/components/toolbar.css'),
    readWeb('css/components/panel.css'),
    readWeb('css/components/button.css'),
    readWeb('css/components/badge.css'),
    readWeb('css/components/tour.css'),
    readWeb('css/graph/cytoscape.css'),
    readWeb('css/utilities.css'),
  ].join('\n');

  const fixture = JSON.stringify(SAMPLE_TRENDING);

  return `<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="UTF-8">
  <title>Tour Test Harness</title>
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
      <span id="graph-stats"></span>
    </div>
  </header>

  <main id="graph-container" style="position:relative; width:100%; height:600px;">
    <div id="cy" style="width:100%; height:100%;"></div>

    <aside id="filter-panel" class="panel panel-right collapsed">
      <button class="panel-close" aria-label="Close">&times;</button>
      <div id="filter-content">Filter controls</div>
    </aside>

    <aside id="detail-panel" class="panel panel-left hidden">
      <button class="panel-close" aria-label="Close">&times;</button>
      <div id="detail-content"></div>
    </aside>

    <aside id="hot-panel" class="panel panel-left hidden" role="complementary" aria-label="What's Hot">
      <button class="panel-close" aria-label="Close">&times;</button>
      <div id="hot-content"></div>
    </aside>

    <aside id="evidence-panel" class="panel panel-left hidden">
      <button class="panel-close" aria-label="Close">&times;</button>
      <div id="evidence-content"></div>
    </aside>

    <aside id="help-panel" class="panel panel-right hidden" role="dialog">
      <button class="panel-close" aria-label="Close">&times;</button>
      <div>Help content</div>
    </aside>
  </main>

  <div id="sr-announcer" aria-live="polite" style="position:absolute;left:-9999px;"></div>

<script>
// ========================================================================
// Cytoscape Mock (same as smoke tests, with neighborhood support)
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
    edges() { return new EleCollection(this._eles.filter(e => e._group === 'edges')); }
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
    neighborhood(sel) {
      const connectedIds = new Set();
      _edges.forEach(e => {
        if (e._data.source === this._data.id) connectedIds.add(e._data.target);
        if (e._data.target === this._data.id) connectedIds.add(e._data.source);
      });
      let neighbors = _nodes.filter(n => connectedIds.has(n._data.id));
      if (sel) {
        const typeMatch = sel.match(/type\\s*=\\s*"([^"]+)"/);
        if (typeMatch) {
          neighbors = neighbors.filter(n => n._data.type === typeMatch[1]);
        }
      }
      return new EleCollection(neighbors);
    }
    closedNeighborhood() {
      const connectedIds = new Set([this._data.id]);
      _edges.forEach(e => {
        if (e._data.source === this._data.id) connectedIds.add(e._data.target);
        if (e._data.target === this._data.id) connectedIds.add(e._data.source);
      });
      const neighbors = [..._nodes, ..._edges].filter(el => connectedIds.has(el._data.id) || connectedIds.has(el._data.source) || connectedIds.has(el._data.target));
      const col = new EleCollection(neighbors);
      col.edges = () => new EleCollection(neighbors.filter(e => e._group === 'edges'));
      return col;
    }
    source() {
      return _nodes.find(n => n._data.id === this._data.source) || this;
    }
    target() {
      return _nodes.find(n => n._data.id === this._data.target) || this;
    }
    emit(event) {
      const handlers = _handlers[event + '-' + this._group] || [];
      handlers.forEach(fn => fn({ target: this }));
    }
  }

  fixture.elements.nodes.forEach(n => _nodes.push(new MockElement(n.data, 'nodes')));
  fixture.elements.edges.forEach(e => _edges.push(new MockElement(e.data, 'edges')));

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
      if (el) {
        el.length = 1;
        return el;
      }
      return { length: 0, data: () => null };
    },
    on(event, selectorOrFn, fn) {
      if (typeof selectorOrFn === 'string') {
        const group = selectorOrFn === 'node' ? 'nodes' : 'edges';
        const key = event + '-' + group;
        if (!_handlers[key]) _handlers[key] = [];
        _handlers[key].push(fn);
      }
    },
    animate(opts) {
      window._lastCyAnimate = opts;
      return Promise.resolve();
    },
    zoom() { return 1.5; },
    pan() { return { x: 0, y: 0 }; },
    extent() { return { x1: -200, y1: -200, x2: 200, y2: 200 }; },
    fit() { window._cyFitCalled = true; },
    resize() {},
    container() { return document.getElementById('cy'); },
  };

  const statsEl = document.getElementById('graph-stats');
  if (statsEl) statsEl.textContent = '18 nodes · 24 edges';

  // Set graph meta (as graph.js would)
  window._graphMeta = fixture.meta;
})();

// Stubs
function escapeHtml(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function formatDate(d) { return d || 'Unknown'; }
function formatVelocity(v) { return v != null ? v.toFixed(1) + 'x' : '—'; }
function formatRelation(r) { return r ? r.replace(/_/g,' ') : ''; }
function formatDocId(id) { return id || ''; }
function extractDomain(url) { if (!url) return ''; try { return new URL(url).hostname; } catch { return ''; } }
function capitalize(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ''; }
function truncateLabel(s, n) { return s && s.length > n ? s.slice(0,n) + '…' : (s || ''); }
function highlightNeighborhood() {}
function clearNeighborhoodHighlight() {}
function announceToScreenReader(msg) {
  const el = document.getElementById('sr-announcer');
  if (el) el.textContent = msg;
}
var prefersReducedMotion = true;

// Minimal Driver.js mock — enough for startTour() to run
window.driver = {
  js: {
    driver: function(opts) {
      window._driverOpts = opts;
      window._driverSteps = opts.steps;
      return {
        drive: function() { window._tourStarted = true; },
        destroy: function() {
          if (opts.onDestroyed) opts.onDestroyed();
          window._tourDestroyed = true;
        },
        getActiveIndex: function() { return 0; },
        isActive: function() { return window._tourStarted && !window._tourDestroyed; }
      };
    }
  }
};
</script>

<!-- Load real app JS modules -->
<script>${utilsJS}</script>
<script>${panelsJS}</script>
<script>${whatsHotJS}</script>
<script>${tourJS}</script>

<script>
// Wire up basic event handlers
(function() {
  const cy = window.cy;
  cy.on('tap', 'node', (e) => {
    const node = e.target;
    cy.elements().unselect();
    node.select();
    openNodeDetailPanel(node);
  });
  cy.on('tap', 'edge', (e) => {
    const edge = e.target;
    cy.elements().unselect();
    edge.select();
    openEvidencePanel(edge);
  });
  initializePanels(cy);

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

async function loadApp(page) {
  await page.goto(serverInfo.url);
  await page.waitForFunction(() => window.__ready === true, { timeout: 10000 });
}

// =========================================================================
//  1. Sample Data Detection
// =========================================================================

test.describe('Sample Data Detection', () => {
  test('isSampleData returns true when meta.isSample is set', async ({ page }) => {
    await loadApp(page);
    const result = await page.evaluate(() => isSampleData());
    expect(result).toBe(true);
  });

  test('isSampleData returns false when meta has no isSample flag', async ({ page }) => {
    await loadApp(page);
    const result = await page.evaluate(() => {
      window._graphMeta = { view: 'trending', nodeCount: 10 };
      return isSampleData();
    });
    expect(result).toBe(false);
  });
});

// =========================================================================
//  2. Tour Lifecycle (localStorage)
// =========================================================================

test.describe('Tour Lifecycle', () => {
  test('tour is not completed by default', async ({ page }) => {
    await loadApp(page);
    const result = await page.evaluate(() => isTourCompleted());
    expect(result).toBe(false);
  });

  test('markTourCompleted sets localStorage flag', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => markTourCompleted());
    const result = await page.evaluate(() => isTourCompleted());
    expect(result).toBe(true);
  });

  test('resetTour clears the completed flag', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => {
      markTourCompleted();
      resetTour();
    });
    const result = await page.evaluate(() => isTourCompleted());
    expect(result).toBe(false);
  });
});

// =========================================================================
//  3. Sample Banner
// =========================================================================

test.describe('Sample Banner', () => {
  test('showSampleBanner creates the banner element', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => showSampleBanner());
    await expect(page.locator('#sample-banner')).toBeVisible();
  });

  test('banner contains switch-to-live and retake-tour links', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => showSampleBanner());
    const banner = page.locator('#sample-banner');
    await expect(banner.locator('.sample-banner-link')).toHaveCount(2);
    await expect(banner.locator('.sample-banner-link').first()).toContainText('live data');
    await expect(banner.locator('.sample-banner-link').last()).toContainText('Retake tour');
  });

  test('showSampleBanner is idempotent', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => {
      showSampleBanner();
      showSampleBanner();
      showSampleBanner();
    });
    await expect(page.locator('#sample-banner')).toHaveCount(1);
  });

  test('hideSampleBanner removes the banner', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => {
      showSampleBanner();
      hideSampleBanner();
    });
    await expect(page.locator('#sample-banner')).toHaveCount(0);
  });
});

// =========================================================================
//  4. Tour Steps
// =========================================================================

test.describe('Tour Steps', () => {
  test('buildTourSteps returns 8 steps', async ({ page }) => {
    await loadApp(page);
    const count = await page.evaluate(() => buildTourSteps().length);
    expect(count).toBe(8);
  });

  test('each step has element and popover with title', async ({ page }) => {
    await loadApp(page);
    const steps = await page.evaluate(() =>
      buildTourSteps().map(s => ({
        element: s.element,
        title: s.popover.title,
        hasDescription: s.popover.description.length > 10
      }))
    );
    for (const step of steps) {
      expect(step.element).toBeTruthy();
      expect(step.title).toBeTruthy();
      expect(step.hasDescription).toBe(true);
    }
  });

  test('Stop 2 callback flies to spotlight node', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => {
      const steps = buildTourSteps();
      steps[1].onHighlightStarted(); // Stop 2: entities
    });
    const animated = await page.evaluate(() => !!window._lastCyAnimate);
    expect(animated).toBe(true);
  });

  test('Stop 3 callback opens detail panel', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => {
      const steps = buildTourSteps();
      steps[2].onHighlightStarted(); // Stop 3: detail panel
    });
    await expect(page.locator('#detail-panel')).not.toHaveClass(/hidden/);
  });

  test('Stop 4 callback opens evidence panel', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => {
      const steps = buildTourSteps();
      steps[3].onHighlightStarted(); // Stop 4: evidence
    });
    await expect(page.locator('#evidence-panel')).not.toHaveClass(/hidden/);
    // Detail panel should be closed (mutual exclusivity)
    await expect(page.locator('#detail-panel')).toHaveClass(/hidden/);
  });

  test('Stop 5 callback opens hot panel', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => {
      const steps = buildTourSteps();
      steps[4].onHighlightStarted(); // Stop 5: hot panel
    });
    await expect(page.locator('#hot-panel')).not.toHaveClass(/hidden/);
  });

  test('Stop 6 callback opens filter panel', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => {
      const steps = buildTourSteps();
      // First open hot panel (as if coming from Stop 5)
      steps[4].onHighlightStarted();
      // Then move to Stop 6
      steps[5].onHighlightStarted();
    });
    // Filter panel should be open (not collapsed)
    await expect(page.locator('#filter-panel')).not.toHaveClass(/collapsed/);
    // Hot panel should be closed
    await expect(page.locator('#hot-panel')).toHaveClass(/hidden/);
  });

  test('Stop 8 callback closes all panels and fits graph', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => {
      const steps = buildTourSteps();
      // Open some panels first
      steps[2].onHighlightStarted(); // detail
      // Then trigger Stop 8
      steps[7].onHighlightStarted(); // go explore
    });
    await expect(page.locator('#detail-panel')).toHaveClass(/hidden/);
    await expect(page.locator('#hot-panel')).toHaveClass(/hidden/);
    const fitCalled = await page.evaluate(() => window._cyFitCalled);
    expect(fitCalled).toBe(true);
  });
});

// =========================================================================
//  5. Tour Start (with Driver.js mock)
// =========================================================================

test.describe('Tour Start', () => {
  test('startTour invokes Driver.js with 8 steps', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => startTour());
    const started = await page.evaluate(() => window._tourStarted);
    expect(started).toBe(true);
    const stepCount = await page.evaluate(() => window._driverSteps.length);
    expect(stepCount).toBe(8);
  });

  test('tour destroy callback marks tour completed', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => {
      startTour();
      // Simulate user finishing tour
      window._tourDriver.destroy();
    });
    const completed = await page.evaluate(() => isTourCompleted());
    expect(completed).toBe(true);
  });

  test('initTour shows banner and starts tour when sample data loaded', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => initTour());
    // Banner should appear immediately
    await expect(page.locator('#sample-banner')).toBeVisible();
    // Tour starts after 600ms delay
    await page.waitForFunction(() => window._tourStarted === true, { timeout: 3000 });
  });

  test('initTour does not start tour if already completed', async ({ page }) => {
    await loadApp(page);
    await page.evaluate(() => {
      markTourCompleted();
      initTour();
    });
    // Banner should still show (we're on sample data)
    await expect(page.locator('#sample-banner')).toBeVisible();
    // But tour should NOT have started
    await page.waitForTimeout(800);
    const started = await page.evaluate(() => window._tourStarted);
    expect(started).toBeFalsy();
  });
});

// =========================================================================
//  6. Sample Data Content Validation
// =========================================================================

test.describe('Sample Data Content', () => {
  test('trending view has 18 nodes', async ({ page }) => {
    await loadApp(page);
    const count = await page.evaluate(() => window.cy.nodes().length);
    expect(count).toBe(18);
  });

  test('spotlight node (Apex Studios) has degree >= 6', async ({ page }) => {
    await loadApp(page);
    const degree = await page.evaluate(() =>
      window.cy.getElementById('org:apex-studios').degree()
    );
    expect(degree).toBeGreaterThanOrEqual(6);
  });

  test('spotlight node has narrative', async ({ page }) => {
    await loadApp(page);
    const narrative = await page.evaluate(() =>
      window.cy.getElementById('org:apex-studios').data('narrative')
    );
    expect(narrative).toBeTruthy();
    expect(narrative.length).toBeGreaterThan(20);
  });

  test('evidence edge has snippet and source', async ({ page }) => {
    await loadApp(page);
    const evidence = await page.evaluate(() => {
      const edge = window.cy.getElementById('e:nova-forge');
      const ev = edge.data('evidence');
      return ev && ev.length > 0 ? ev[0] : null;
    });
    expect(evidence).toBeTruthy();
    expect(evidence.snippet).toBeTruthy();
    expect(evidence.source).toBeTruthy();
    expect(evidence.url).toBeTruthy();
  });

  test('at least 5 entities have velocity > 0 for hot panel', async ({ page }) => {
    await loadApp(page);
    const count = await page.evaluate(() => {
      let c = 0;
      window.cy.nodes().forEach(n => { if (n.data('velocity') > 0) c++; });
      return c;
    });
    expect(count).toBeGreaterThanOrEqual(5);
  });

  test('at least 4 distinct entity types', async ({ page }) => {
    await loadApp(page);
    const typeCount = await page.evaluate(() => {
      const types = new Set();
      window.cy.nodes().forEach(n => types.add(n.data('type')));
      return types.size;
    });
    expect(typeCount).toBeGreaterThanOrEqual(4);
  });

  test('graph meta has isSample and tourVersion', async ({ page }) => {
    await loadApp(page);
    const meta = await page.evaluate(() => window._graphMeta);
    expect(meta.isSample).toBe(true);
    expect(meta.tourVersion).toBe(1);
  });
});
