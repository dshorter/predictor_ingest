/**
 * Ontology Reference — shared logic
 *
 * Loaded by both web/ontology.html and web/mobile/ontology.html.
 * Each host page sets `window.__ontoBaseHref` if path prefixing is needed
 * (the mobile page sets it to '../').
 */

// ---------------------------------------------------------------------------
// Known domains — hardcoded registry.
// When we add a third domain, add it here. This drives the switcher UI
// everywhere (ontology page today, main app + dashboard later).
// ---------------------------------------------------------------------------
const KNOWN_DOMAINS = [
  { slug: 'ai',        label: 'AI / ML' },
  { slug: 'biosafety', label: 'Biosafety' },
];

// ---------------------------------------------------------------------------
// Theme
// ---------------------------------------------------------------------------
(function initTheme() {
  const stored = localStorage.getItem('theme');
  if (stored === 'dark' ||
      (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();

function toggleTheme() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  document.documentElement.setAttribute('data-theme', isDark ? 'light' : 'dark');
  localStorage.setItem('theme', isDark ? 'light' : 'dark');
}

// ---------------------------------------------------------------------------
// Domain resolution
// ---------------------------------------------------------------------------
function getDomainSlug() {
  return new URLSearchParams(window.location.search).get('domain') || 'ai';
}

function assetPath(relative) {
  const base = window.__ontoBaseHref || '';
  return base + relative;
}

// ---------------------------------------------------------------------------
// HTML helpers
// ---------------------------------------------------------------------------
function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function badge(text, cls) {
  return `<span class="badge ${cls || ''}">${esc(text)}</span>`;
}

// ---------------------------------------------------------------------------
// Domain switcher
// ---------------------------------------------------------------------------
function renderDomainSwitcher(currentSlug) {
  const tabs = KNOWN_DOMAINS.map(d => {
    const active = d.slug === currentSlug;
    const href = `?domain=${d.slug}`;
    return `<a class="domain-tab${active ? ' active' : ''}"
               href="${esc(href)}"
               data-domain="${esc(d.slug)}">${esc(d.label)}</a>`;
  }).join('');

  return `<nav id="domain-switcher" aria-label="Domain selector">${tabs}</nav>`;
}

function bindDomainSwitcher() {
  const nav = document.getElementById('domain-switcher');
  if (!nav) return;

  nav.addEventListener('click', function (e) {
    const tab = e.target.closest('.domain-tab');
    if (!tab) return;

    const slug = tab.dataset.domain;
    if (slug === getDomainSlug()) {
      e.preventDefault();
      return;
    }

    // Recast in-place: update URL and re-render without a full page reload
    e.preventDefault();
    const url = new URL(window.location);
    url.searchParams.set('domain', slug);
    history.pushState(null, '', url);
    load();
  });

  // Handle browser back/forward
  window.addEventListener('popstate', () => load());
}

// ---------------------------------------------------------------------------
// Render: domain meta
// ---------------------------------------------------------------------------
function renderDomainMeta(onto) {
  const d = onto.domain;
  const nClasses = onto.entityTypes.length;
  const nProps   = onto.relationGroups.reduce((s, g) => s + g.relations.length, 0)
                 + (onto.ungroupedRelations || []).length;
  const nAliases = Object.keys(onto.normalization || {}).length;

  return `
    <div id="domain-meta">
      <h2>${esc(d.name)}</h2>
      <p id="domain-description">${esc(d.description || '')}</p>
      <div class="meta-badges">
        ${badge(nClasses + ' entity types', 'badge-info')}
        ${badge(nProps + ' relations', 'badge-info')}
        ${badge(nAliases + ' aliases', 'badge-secondary')}
        ${badge('base: ' + onto.baseRelation, 'badge-secondary')}
        ${badge('escalation ≥ ' + onto.escalationThreshold, 'badge-secondary')}
      </div>
    </div>`;
}

// ---------------------------------------------------------------------------
// Render: classes panel
// ---------------------------------------------------------------------------
function renderClasses(onto) {
  const byName = {};
  for (const et of onto.entityTypes) byName[et.name] = et;

  const groups = onto.typeGroups || [];
  const allGroupedTypes = new Set(groups.flatMap(g => g.types));
  const ungrouped = onto.entityTypes.filter(et => !allGroupedTypes.has(et.name));

  function renderCard(et) {
    return `
      <div class="class-card">
        <span class="class-swatch" style="background:${esc(et.color)}"></span>
        <span class="class-name">${esc(et.name)}</span>
        <span class="class-prefix">${esc(et.canonicalIdPattern)}</span>
      </div>`;
  }

  let html = '';
  for (const group of groups) {
    const types = (group.types || []).map(n => byName[n]).filter(Boolean);
    if (!types.length) continue;
    html += `
      <div class="type-group-section">
        <p class="type-group-label">${esc(group.label)}</p>
        ${types.map(renderCard).join('')}
      </div>`;
  }
  if (ungrouped.length) {
    html += `
      <div class="type-group-section">
        <p class="type-group-label">Other</p>
        ${ungrouped.map(renderCard).join('')}
      </div>`;
  }

  return `
    <div id="classes-panel">
      <div class="onto-section-header">
        <h3>Entity Types</h3>
        <span class="section-count">${onto.entityTypes.length} total</span>
      </div>
      ${html}
    </div>`;
}

// ---------------------------------------------------------------------------
// Render: properties panel
// ---------------------------------------------------------------------------
function renderProperties(onto) {
  const allGroupProps = new Set(
    onto.relationGroups.flatMap(g => g.relations.map(r => r.rel))
  );
  let html = '';

  for (const group of onto.relationGroups) {
    if (!group.relations.length) continue;
    const rows = group.relations.map(r => {
      const nameClass = r.isBase ? 'rel-name is-base' : 'rel-name';
      const aliasCount = r.aliases.length;
      const pills = aliasCount
        ? r.aliases.map(a => `<span class="alias-pill">${esc(a)}</span>`).join('')
        : '<span class="alias-none">no aliases</span>';
      const baseBadge = r.isBase
        ? ' <span class="badge badge-info badge-inline">base</span>'
        : '';
      const countBadge = aliasCount > 0
        ? `<span class="alias-count">${aliasCount}</span>`
        : '';
      return `
        <div class="rel-row">
          <span class="${nameClass}">${esc(r.rel)}${baseBadge}${countBadge}</span>
          <span class="alias-pills">${pills}</span>
        </div>`;
    }).join('');

    html += `
      <div class="rel-group">
        <p class="rel-group-header">${esc(group.label)}</p>
        ${rows}
      </div>`;
  }

  // Ungrouped safety net
  const ungrouped = (onto.ungroupedRelations || []).filter(r => !allGroupProps.has(r));
  if (ungrouped.length) {
    const rows = ungrouped.map(r => `
      <div class="rel-row">
        <span class="rel-name">${esc(r)}</span>
      </div>`).join('');
    html += `
      <div class="rel-group">
        <p class="rel-group-header">Ungrouped</p>
        ${rows}
      </div>`;
  }

  const total = onto.relationGroups.reduce((s, g) => s + g.relations.length, 0)
              + ungrouped.length;

  return `
    <div id="properties-panel">
      <div class="onto-section-header">
        <h3>Relations</h3>
        <span class="section-count">${total} canonical · ${Object.keys(onto.normalization || {}).length} aliases</span>
      </div>
      ${html}
    </div>`;
}

// ---------------------------------------------------------------------------
// Render: quality contract
// ---------------------------------------------------------------------------
function fmtKey(k) {
  return k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function renderQualityCard(title, data, extra) {
  const rows = Object.entries(data).map(([k, v]) =>
    `<tr><td>${esc(fmtKey(k))}</td><td>${esc(v)}</td></tr>`
  ).join('');
  return `
    <div class="quality-card">
      <h4>${esc(title)}</h4>
      <table class="quality-table"><tbody>${rows}</tbody></table>
      ${extra || ''}
    </div>`;
}

function renderQuality(onto) {
  const weightsWithPct = {};
  let weightSum = 0;
  for (const [k, v] of Object.entries(onto.scoringWeights || {})) {
    weightsWithPct[k] = (v * 100).toFixed(0) + '%';
    weightSum += v;
  }
  const sumLine = `<div class="weight-total">total: ${(weightSum * 100).toFixed(0)}%</div>`;

  const escNote = `<div class="escalation-note">escalate if combined &lt; ${onto.escalationThreshold}</div>`;

  return `
    <div>
      <div class="onto-section-header">
        <h3>Extraction Quality Contract</h3>
        <span class="section-count">gates · thresholds · weights</span>
      </div>
      <div id="quality-section">
        ${renderQualityCard('Quality Thresholds', onto.qualityThresholds, escNote)}
        ${renderQualityCard('Gate Thresholds', onto.gateThresholds)}
        ${renderQualityCard('Scoring Weights', weightsWithPct, sumLine)}
      </div>
    </div>`;
}

// ---------------------------------------------------------------------------
// Main loader
// ---------------------------------------------------------------------------
async function load() {
  const slug = getDomainSlug();
  const url  = assetPath(`data/domains/${slug}.ontology.json`);

  const body    = document.getElementById('onto-body');
  const loading = document.getElementById('onto-loading');
  const errorEl = document.getElementById('onto-error');

  // Reset state for recast
  if (loading) loading.style.display = '';
  if (errorEl) { errorEl.style.display = 'none'; errorEl.textContent = ''; }

  // Update switcher active state immediately
  document.querySelectorAll('.domain-tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.domain === slug);
  });

  let onto;
  try {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status} — ${url}`);
    onto = await resp.json();
  } catch (err) {
    if (loading) loading.style.display = 'none';
    if (errorEl) {
      errorEl.style.display = '';
      errorEl.textContent = `Failed to load ontology: ${err.message}. Run: make export_ontology DOMAIN=${slug}`;
    }
    return;
  }

  // Update page title
  document.title = `${onto.domain.name} — Ontology Reference`;
  document.getElementById('domain-badge').textContent = onto.domain.slug;

  // Render
  try {
    body.innerHTML = `
      ${renderDomainMeta(onto)}
      <div id="onto-columns">
        ${renderClasses(onto)}
        ${renderProperties(onto)}
      </div>
      ${renderQuality(onto)}
    `;
  } catch (renderErr) {
    body.innerHTML = `
      <div id="onto-error" style="display:block">
        Render error: ${esc(renderErr.message)}. The ontology JSON may have an unexpected shape.
      </div>`;
  }
}

// ---------------------------------------------------------------------------
// Init — called by each host page after DOM is ready
// ---------------------------------------------------------------------------
function initOntologyPage() {
  // Wire up theme toggle
  const themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', toggleTheme);
  }

  // Inject domain switcher into header
  const header = document.getElementById('onto-header');
  if (header) {
    const slug = getDomainSlug();
    header.insertAdjacentHTML('afterend', renderDomainSwitcher(slug));
    bindDomainSwitcher();
  }

  // Load data
  load();
}

// Auto-init when script loads (both pages include this at end of body)
initOntologyPage();
