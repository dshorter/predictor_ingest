/**
 * Movers Frontend (Sprint 15)
 *
 * Loads movers.json for the selected domain and (eventually) renders
 * the table + preset chips + detail panel. This file ships items 15.2
 * (data loader) and the AppState wiring that subsequent items depend on.
 *
 * See docs/ux/movers-wireframe.md for the locked-in layout decisions
 * and docs/plans/movers-and-focus-mode.md §Appendix A for the data
 * contract.
 */

const MoversState = {
  domain: null,       // resolved domain slug
  data: null,         // { meta, rows[] } from movers.json
  loading: false,
  error: null,
};

const DEFAULT_DOMAIN = 'film';

/**
 * Get the active domain slug from the URL, defaulting to film.
 */
function resolveDomain() {
  const params = new URLSearchParams(window.location.search);
  const slug = params.get('domain');
  if (!slug) return DEFAULT_DOMAIN;
  // If KNOWN_DOMAINS is loaded, validate against it; otherwise trust the URL.
  if (typeof KNOWN_DOMAINS !== 'undefined') {
    const known = KNOWN_DOMAINS.some(d => d.slug === slug);
    if (!known) {
      console.warn(`[movers] unknown domain "${slug}", falling back to ${DEFAULT_DOMAIN}`);
      return DEFAULT_DOMAIN;
    }
  }
  return slug;
}

/**
 * URL for the published movers.json of a given domain.
 */
function moversDataUrl(domain) {
  return `data/graphs/live/${domain}/movers.json`;
}

/**
 * Load movers.json for the current domain.
 * Sets MoversState.data on success, MoversState.error on failure.
 * Returns the parsed object on success, or null on failure.
 *
 * Tolerates unknown fields per Appendix A's forward-compat note —
 * we don't validate the shape strictly here; the table renderer
 * defensive-reads each field.
 */
async function loadMoversData(domain) {
  MoversState.loading = true;
  MoversState.error = null;
  renderLoadingState();

  const url = moversDataUrl(domain);
  try {
    const resp = await fetch(url);
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status} loading ${url}`);
    }
    // Parse-as-text-first per the Safari quirk noted in graph.js:
    // .json() on an HTML error page throws cryptically.
    const text = await resp.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      throw new Error(`Invalid JSON from ${url}: ${text.substring(0, 100)}`);
    }
    if (!data.meta || !Array.isArray(data.rows)) {
      throw new Error(`Invalid movers.json shape: missing meta or rows[]`);
    }

    MoversState.data = data;
    MoversState.loading = false;
    renderDataState();
    return data;
  } catch (err) {
    console.error('[movers] load failed:', err);
    MoversState.error = err.message || String(err);
    MoversState.loading = false;
    MoversState.data = null;
    renderErrorState();
    return null;
  }
}

/* -------------------------------------------------------------------------
 * Rendering — minimal scaffolding only. The table, preset chips, and
 * detail panel come in items 15.3 / 15.4 / 15.6.
 * ----------------------------------------------------------------------- */

function renderLoadingState() {
  const status = document.getElementById('movers-status');
  if (status) status.textContent = 'Loading movers data…';
}

function renderErrorState() {
  const status = document.getElementById('movers-status');
  if (status) {
    status.textContent = `Failed to load movers data: ${MoversState.error}`;
    status.classList.add('movers-status-error');
  }
}

function renderDataState() {
  const data = MoversState.data;
  const status = document.getElementById('movers-status');
  if (status) {
    status.classList.remove('movers-status-error');
    if (data.rows.length === 0) {
      status.textContent = `No movers data for ${data.meta.domain}. Run \`make daily DOMAIN=${data.meta.domain}\` to populate.`;
    } else {
      const exported = data.meta.exportedAt ? new Date(data.meta.exportedAt).toLocaleDateString() : '?';
      status.textContent = `${data.rows.length.toLocaleString()} entities · exported ${exported}`;
    }
  }
}

/* -------------------------------------------------------------------------
 * Initialization
 * ----------------------------------------------------------------------- */

async function initMovers() {
  MoversState.domain = resolveDomain();

  // Wire AppState shim so domain-switcher.js (which expects AppState.domain)
  // works on this page. Mirrors the dashboard.html pattern.
  if (typeof window.AppState === 'undefined') {
    window.AppState = {
      domain: MoversState.domain,
      domainConfig: { title: 'Movers' },
    };
  } else {
    window.AppState.domain = MoversState.domain;
  }

  // Set page title and toolbar heading.
  const domainEntry = (typeof KNOWN_DOMAINS !== 'undefined')
    ? KNOWN_DOMAINS.find(d => d.slug === MoversState.domain)
    : null;
  const domainLabel = domainEntry ? domainEntry.label : MoversState.domain;
  document.title = `Movers · ${domainLabel}`;
  const titleEl = document.querySelector('.app-title');
  if (titleEl) titleEl.textContent = `Movers · ${domainLabel}`;

  // Initialize the domain switcher dropdown if present.
  if (typeof initDomainSwitcher === 'function') {
    initDomainSwitcher();
  }

  // Theme toggle wire (shared idiom with dashboard.html).
  const themeToggle = document.getElementById('theme-toggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem('theme', next); } catch (e) {}
    });
  }

  await loadMoversData(MoversState.domain);
}

// Expose for tests + future modules.
if (typeof window !== 'undefined') {
  window.MoversState = MoversState;
  window.loadMoversData = loadMoversData;
  window.resolveDomain = resolveDomain;
  window.moversDataUrl = moversDataUrl;
}

document.addEventListener('DOMContentLoaded', initMovers);
