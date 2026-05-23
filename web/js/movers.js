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
  sortedRows: null,   // filtered + sorted view of data.rows for the active preset
  preset: null,       // active preset slug
  loading: false,
  error: null,
};

/* -------------------------------------------------------------------------
 * Presets (15.4)
 *
 * Each preset is a {sort, filter, description} tuple per the wireframe.
 * The sort/filter signatures take a row and return number / boolean.
 * The Custom preset is a placeholder until 15.5 ships its controls.
 *
 * Source of truth: docs/ux/movers-wireframe.md §"Preset chip group".
 * ----------------------------------------------------------------------- */

// Helper: stable comparator that pushes null-valued rows to the end.
function descBy(field) {
  return (a, b) => {
    const av = a[field];
    const bv = b[field];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return bv - av;
  };
}
function ascBy(field) {
  return (a, b) => {
    const av = a[field];
    const bv = b[field];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return av - bv;
  };
}

const PRESETS = [
  {
    slug: 'biggest-climbers',
    label: 'Biggest climbers',
    description: 'Entities that climbed the most ranks in the last 7d.',
    sort: descBy('rank_delta'),
    filter: (row) => (row.current_rank ?? 0) > 50,
  },
  {
    slug: 'just-appeared',
    label: 'Just appeared',
    description: 'Entities first seen in the last two weeks.',
    sort: ascBy('days_since_first_seen'),
    filter: (row) => (row.days_since_first_seen ?? Infinity) <= 14,
  },
  {
    slug: 'fastest-accelerators',
    label: 'Fastest accelerators',
    description: 'Entities with the steepest mention growth (min 3 mentions to filter noise).',
    sort: descBy('velocity_raw'),
    filter: (row) => (row.mention_count_7d ?? 0) >= 3,
  },
  {
    slug: 'emerging-consensus',
    label: 'Emerging consensus',
    description: 'Entities being picked up across many independent sources.',
    sort: descBy('distinct_sources_7d'),
    filter: (row) => (row.current_rank ?? 0) > 50,
  },
  {
    slug: 'sanity',
    label: 'Sanity reference',
    description: 'Top entities by raw 7d mention count — sanity check vs. the other lenses.',
    sort: descBy('mention_count_7d'),
    filter: () => true,
  },
  {
    slug: 'custom',
    label: 'Custom',
    description: 'Custom sort + filter controls coming in a future update.',
    sort: ascBy('current_rank'),
    filter: () => true,
  },
];

const DEFAULT_PRESET = 'biggest-climbers';

function findPreset(slug) {
  return PRESETS.find(p => p.slug === slug) || PRESETS.find(p => p.slug === DEFAULT_PRESET);
}

/** Read ?preset= from URL; fall back to default. */
function resolvePresetFromUrl() {
  const slug = new URLSearchParams(window.location.search).get('preset');
  return findPreset(slug).slug;
}

/** Apply a preset by slug: re-filter + re-sort, update URL, re-render. */
function applyPreset(slug, { pushUrl = true } = {}) {
  if (!MoversState.data) return;
  const preset = findPreset(slug);
  MoversState.preset = preset.slug;

  MoversState.sortedRows = MoversState.data.rows
    .filter(preset.filter)
    .sort(preset.sort);

  if (pushUrl) writePresetToUrl(preset.slug);
  renderPresetChips();           // updates which chip is active
  renderDescriptionStrip();
  renderTable();
}

function writePresetToUrl(slug) {
  const url = new URL(window.location.href);
  if (slug === DEFAULT_PRESET) {
    url.searchParams.delete('preset');
  } else {
    url.searchParams.set('preset', slug);
  }
  window.history.replaceState({ preset: slug }, '', url.toString());
}

/** Render the chip row above the table. Mounts/replaces inside #movers-presets. */
function renderPresetChips() {
  const mount = document.getElementById('movers-presets');
  if (!mount) return;
  const active = MoversState.preset || DEFAULT_PRESET;
  mount.innerHTML = PRESETS.map(p => `
    <button type="button"
            class="movers-chip${p.slug === active ? ' movers-chip-active' : ''}"
            data-preset="${escAttr(p.slug)}"
            title="${escAttr(p.description)}">
      ${escText(p.label)}
    </button>
  `).join('');
}

function renderDescriptionStrip() {
  const strip = document.getElementById('movers-preset-description');
  if (!strip) return;
  const preset = findPreset(MoversState.preset);
  strip.textContent = preset.description;
  // For Custom mode, show a different visual hint since controls aren't shipped yet.
  strip.classList.toggle('movers-preset-description-placeholder', preset.slug === 'custom');
}

function renderEmptyTable() {
  if (!MoversState.data) return '';
  const domain = MoversState.data.meta.domain;
  // Disambiguate: is the whole export empty, or did the active preset filter everything?
  if (MoversState.data.rows.length === 0) {
    return `
      <div class="movers-empty">
        <p>No movers data for <strong>${escText(domain)}</strong> yet.</p>
        <p class="movers-empty-hint">Run <code>make daily DOMAIN=${escText(domain)}</code> to populate.</p>
      </div>
    `;
  }
  const preset = findPreset(MoversState.preset);
  return `
    <div class="movers-empty">
      <p>No entities match <strong>${escText(preset.label)}</strong> for ${escText(domain)}.</p>
      <p class="movers-empty-hint">Try <strong>Sanity reference</strong> or another preset.</p>
    </div>
  `;
}

/** Delegated click on the chip row. Called once during initMovers. */
function initPresetChipDelegation() {
  const mount = document.getElementById('movers-presets');
  if (!mount) return;
  mount.addEventListener('click', (e) => {
    const chip = e.target.closest('[data-preset]');
    if (!chip) return;
    applyPreset(chip.dataset.preset);
  });
}

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
  renderPresetChips();
  applyPreset(MoversState.preset || resolvePresetFromUrl());
}

/* -------------------------------------------------------------------------
 * Table — 15.3
 *
 * Virtual scroll: render only the rows within ~50 of the viewport.
 * Spacer divs above/below preserve the scroll position. Single fixed
 * row height keeps the math simple.
 *
 * Default sort: by current_rank ascending (matches the JSON's natural
 * order). Preset chips (15.4) re-sort by mutating MoversState.sortedRows.
 * ----------------------------------------------------------------------- */

const ROW_HEIGHT = 44;        // px — must match .movers-row CSS
const OVERSCAN = 8;           // extra rows rendered above/below viewport

function renderTable() {
  if (!MoversState.data) return;
  const mount = document.getElementById('movers-table');
  if (!mount) return;

  if (!MoversState.sortedRows || MoversState.sortedRows.length === 0) {
    mount.innerHTML = renderEmptyTable();
    return;
  }

  mount.innerHTML = `
    <div class="movers-table">
      <div class="movers-table-header" role="row">
        <div class="movers-cell movers-cell-rank">#</div>
        <div class="movers-cell movers-cell-entity">Entity</div>
        <div class="movers-cell movers-cell-delta">Δ rank</div>
        <div class="movers-cell movers-cell-num">7d</div>
        <div class="movers-cell movers-cell-num">30d</div>
        <div class="movers-cell movers-cell-num">src 7d</div>
        <div class="movers-cell movers-cell-first">first</div>
      </div>
      <div class="movers-table-scroll" id="movers-scroll">
        <div class="movers-table-virtual" id="movers-virtual">
          <div class="movers-table-rows" id="movers-rows" role="rowgroup"></div>
        </div>
      </div>
    </div>
  `;

  const scroll = document.getElementById('movers-scroll');
  const virtual = document.getElementById('movers-virtual');
  const total = MoversState.sortedRows.length;
  virtual.style.height = (total * ROW_HEIGHT) + 'px';

  // Re-paint visible window on scroll. Use requestAnimationFrame to
  // coalesce rapid scroll events into a single render.
  let scheduled = false;
  function repaint() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      paintVisibleRows(scroll);
      scheduled = false;
    });
  }
  scroll.addEventListener('scroll', repaint);
  paintVisibleRows(scroll);
}

function paintVisibleRows(scrollEl) {
  const rows = MoversState.sortedRows;
  const total = rows.length;
  const viewportH = scrollEl.clientHeight;
  const scrollTop = scrollEl.scrollTop;

  const firstIdx = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const lastIdx = Math.min(total, Math.ceil((scrollTop + viewportH) / ROW_HEIGHT) + OVERSCAN);

  const container = document.getElementById('movers-rows');
  if (!container) return;
  container.style.transform = `translateY(${firstIdx * ROW_HEIGHT}px)`;
  container.innerHTML = rows.slice(firstIdx, lastIdx).map(renderRow).join('');
}

function renderRow(row) {
  const type = (row.type || 'Other');
  const typeClass = `badge-type-${type.toLowerCase()}`;
  const rank = row.current_rank ?? '—';
  const delta = renderRankDelta(row);
  const m7 = row.mention_count_7d ?? 0;
  const m30 = row.mention_count_30d ?? 0;
  const src7 = row.distinct_sources_7d ?? 0;
  const first = renderFirstSeen(row);

  return `
    <div class="movers-row" role="row" data-entity-id="${escAttr(row.entity_id)}">
      <div class="movers-cell movers-cell-rank">${rank}</div>
      <div class="movers-cell movers-cell-entity">
        <span class="badge ${typeClass}">${escText(type)}</span>
        <span class="movers-entity-label">${escText(row.label || row.entity_id)}</span>
      </div>
      <div class="movers-cell movers-cell-delta">${delta}</div>
      <div class="movers-cell movers-cell-num">${m7.toLocaleString()}</div>
      <div class="movers-cell movers-cell-num">${m30.toLocaleString()}</div>
      <div class="movers-cell movers-cell-num">${src7.toLocaleString()}</div>
      <div class="movers-cell movers-cell-first">${first}</div>
    </div>
  `;
}

function renderRankDelta(row) {
  if (row.is_new) {
    return `<span class="movers-new-badge">NEW</span>`;
  }
  const d = row.rank_delta;
  if (d == null) return '<span class="movers-delta-zero">—</span>';
  if (d > 0) return `<span class="movers-delta-up">↑${d}</span>`;
  if (d < 0) return `<span class="movers-delta-down">↓${Math.abs(d)}</span>`;
  return '<span class="movers-delta-zero">—</span>';
}

function renderFirstSeen(row) {
  const d = row.days_since_first_seen;
  if (d == null) return '—';
  const cls = d <= 14 ? 'movers-first-new' : '';
  const star = d <= 14 ? ' ★' : '';
  return `<span class="${cls}">${d}d${star}</span>`;
}

function escText(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function escAttr(s) {
  return escText(s).replace(/"/g, '&quot;');
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

  // Preset chip delegation — chips are rendered after data loads.
  initPresetChipDelegation();

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
  window.PRESETS = PRESETS;
  window.loadMoversData = loadMoversData;
  window.resolveDomain = resolveDomain;
  window.moversDataUrl = moversDataUrl;
  window.applyPreset = applyPreset;
  window.findPreset = findPreset;
}

document.addEventListener('DOMContentLoaded', initMovers);
