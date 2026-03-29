/**
 * Domain Switcher & Certificate
 *
 * Shared module for domain switching (dropdown) and "About this Domain"
 * certificate modal. Used by both desktop and mobile apps.
 *
 * Dependencies: AppState must be defined before this script loads.
 *
 * Usage:
 *   initDomainSwitcher()   — called during app init
 *   openDomainCertificate() — callable from help panel or dropdown
 *   closeDomainCertificate()
 */

// ---------------------------------------------------------------------------
// Known domains — single source of truth.
// When a new domain is added, add it here and it appears everywhere.
// ---------------------------------------------------------------------------
const KNOWN_DOMAINS = [
  { slug: 'ai',        label: 'AI / ML',    title: 'AI Trend Graph' },
  { slug: 'biosafety', label: 'Biosafety',  title: 'Biosafety Trend Graph' },
  { slug: 'film',      label: 'Film',       title: 'Film & Indie Cinema Trend Graph' },
];

// ---------------------------------------------------------------------------
// Domain switcher dropdown
// ---------------------------------------------------------------------------

/**
 * Initialize the domain switcher on the toolbar.
 * Wraps the existing .app-title in a clickable container with a dropdown.
 */
function initDomainSwitcher() {
  const titleEl = document.querySelector('.app-title');
  if (!titleEl) return;

  const currentSlug = (typeof AppState !== 'undefined' && AppState.domain) || 'film';

  // Wrap title in a clickable container
  const wrap = document.createElement('div');
  wrap.className = 'app-title-wrap';
  titleEl.parentNode.insertBefore(wrap, titleEl);
  wrap.appendChild(titleEl);

  // Add caret
  const caret = document.createElement('span');
  caret.className = 'domain-caret';
  caret.setAttribute('aria-hidden', 'true');
  caret.textContent = '\u25BE'; // ▾
  wrap.appendChild(caret);

  // Build dropdown
  const dropdown = document.createElement('div');
  dropdown.className = 'domain-dropdown';
  dropdown.id = 'domain-dropdown';

  for (const d of KNOWN_DOMAINS) {
    const isActive = d.slug === currentSlug;
    const item = document.createElement('a');
    item.className = 'domain-dropdown-item' + (isActive ? ' active' : '');
    item.href = '?domain=' + d.slug;
    item.dataset.domain = d.slug;
    item.innerHTML =
      '<span class="domain-item-check">' + (isActive ? '\u2713' : '') + '</span>' +
      '<span>' + escHtml(d.label) + '</span>';
    dropdown.appendChild(item);
  }

  // Separator + "About this Domain" action
  const sep = document.createElement('div');
  sep.className = 'domain-dropdown-sep';
  dropdown.appendChild(sep);

  const aboutBtn = document.createElement('button');
  aboutBtn.className = 'domain-dropdown-action';
  aboutBtn.type = 'button';
  aboutBtn.innerHTML = '<span>About this domain\u2026</span>';
  aboutBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    closeDomainDropdown();
    openDomainCertificate();
  });
  dropdown.appendChild(aboutBtn);

  wrap.appendChild(dropdown);

  // Toggle on click
  wrap.addEventListener('click', (e) => {
    // Don't toggle if clicking a link inside the dropdown
    if (e.target.closest('.domain-dropdown-item')) return;
    if (e.target.closest('.domain-dropdown-action')) return;
    toggleDomainDropdown();
  });

  // Domain links — navigate with window.location
  dropdown.addEventListener('click', (e) => {
    const item = e.target.closest('.domain-dropdown-item');
    if (!item) return;
    e.preventDefault();
    const slug = item.dataset.domain;
    if (slug === currentSlug) {
      closeDomainDropdown();
      return;
    }
    // Full page reload with new domain — clear sample/tour params
    const url = new URL(window.location);
    url.searchParams.set('domain', slug);
    url.searchParams.delete('sample');
    url.searchParams.delete('tour');
    window.location.href = url.toString();
  });

  // Close on click outside
  document.addEventListener('click', (e) => {
    if (!wrap.contains(e.target)) {
      closeDomainDropdown();
    }
  });

  // Close on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeDomainDropdown();
    }
  });

  // Inject the certificate overlay into the DOM (once)
  injectCertificateOverlay();
}

function toggleDomainDropdown() {
  const wrap = document.querySelector('.app-title-wrap');
  const dropdown = document.getElementById('domain-dropdown');
  if (!wrap || !dropdown) return;
  const isOpen = dropdown.classList.contains('open');
  dropdown.classList.toggle('open', !isOpen);
  wrap.classList.toggle('open', !isOpen);
}

function closeDomainDropdown() {
  const wrap = document.querySelector('.app-title-wrap');
  const dropdown = document.getElementById('domain-dropdown');
  if (dropdown) dropdown.classList.remove('open');
  if (wrap) wrap.classList.remove('open');
}

// ---------------------------------------------------------------------------
// Domain certificate modal
// ---------------------------------------------------------------------------

function injectCertificateOverlay() {
  if (document.getElementById('domain-certificate-overlay')) return;

  const overlay = document.createElement('div');
  overlay.id = 'domain-certificate-overlay';
  overlay.innerHTML = '<div id="domain-cert-content"></div>';

  // Close on backdrop click
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeDomainCertificate();
  });

  document.body.appendChild(overlay);
}

async function openDomainCertificate() {
  const overlay = document.getElementById('domain-certificate-overlay');
  const container = document.getElementById('domain-cert-content');
  if (!overlay || !container) {
    if (!document.getElementById('domain-certificate-overlay')) {
      console.warn('[cert] overlay not found, injecting now');
      injectCertificateOverlay();
      // Re-query after injection
      const retryOverlay = document.getElementById('domain-certificate-overlay');
      const retryContainer = document.getElementById('domain-cert-content');
      if (!retryOverlay || !retryContainer) {
        console.error('[cert] injection failed');
        return;
      }
      return openDomainCertificate();
    }
    console.error('[cert] container missing inside overlay');
    return;
  }

  const slug = (typeof AppState !== 'undefined' && AppState.domain) || 'film';

  // Try to load the ontology JSON for richer data
  // Resolve path relative to the site root (handles mobile/ subdirectory)
  let onto = null;
  try {
    const base = document.querySelector('base')?.href || '';
    const ontoPath = (base || '') + `data/domains/${slug}.ontology.json`;
    const resp = await fetch(ontoPath);
    if (!resp.ok) {
      // Retry with ../ prefix for subdirectory pages (e.g. mobile/)
      const altResp = await fetch(`../data/domains/${slug}.ontology.json`);
      if (altResp.ok) onto = await altResp.json();
    } else {
      onto = await resp.json();
    }
  } catch (_) { /* ontology is optional */ }

  // Fall back to AppState.domainConfig for basics
  const config = (typeof AppState !== 'undefined' && AppState.domainConfig) || {};
  const domainEntry = KNOWN_DOMAINS.find(d => d.slug === slug) || { label: slug, title: slug };

  // Build stats
  const entityCount = onto ? onto.entityTypes.length : (config.entityTypes || []).length;
  const relationCount = onto
    ? onto.relationGroups.reduce((s, g) => s + g.relations.length, 0)
      + (onto.ungroupedRelations || []).length
    : '—';
  const aliasCount = onto ? Object.keys(onto.normalization || {}).length : '—';

  const description = onto && onto.domain
    ? onto.domain.description || ''
    : '';

  // Entity type dots
  const types = onto ? onto.entityTypes : [];
  const typeDots = types.map(t =>
    `<span class="cert-type-dot"><span class="dot" style="background:${escHtml(t.color)}"></span>${escHtml(t.name)}</span>`
  ).join('');

  // Ontology link (resolve from site root, not current directory)
  const isSubdir = window.location.pathname.includes('/mobile/');
  const ontoHref = (isSubdir ? '../' : '') + `ontology.html?domain=${slug}`;

  container.innerHTML = `
    <div class="domain-cert">
      <button class="domain-cert-close" aria-label="Close" title="Close">&times;</button>

      <div class="cert-header">
        <div class="cert-label">Domain Profile</div>
        <h2 class="cert-title">${escHtml(config.title || domainEntry.title)}</h2>
        <span class="cert-slug">${escHtml(slug)}</span>
      </div>

      <div class="cert-divider"></div>

      <div class="cert-stats">
        <div>
          <div class="cert-stat-value">${entityCount}</div>
          <div class="cert-stat-label">Entity Types</div>
        </div>
        <div>
          <div class="cert-stat-value">${relationCount}</div>
          <div class="cert-stat-label">Relations</div>
        </div>
        <div>
          <div class="cert-stat-value">${aliasCount}</div>
          <div class="cert-stat-label">Aliases</div>
        </div>
      </div>

      ${description ? `
      <div class="cert-divider"></div>
      <p class="cert-description">${escHtml(description)}</p>
      ` : ''}

      ${typeDots ? `
      <div class="cert-divider"></div>
      <div class="cert-types">${typeDots}</div>
      ` : ''}

      <div class="cert-footer">
        <a class="btn" href="${escHtml(ontoHref)}">Full Ontology Reference</a>
      </div>
    </div>
  `;

  // Wire close button
  container.querySelector('.domain-cert-close')?.addEventListener('click', closeDomainCertificate);

  // Show
  overlay.classList.add('open');

  // Close on Escape
  const escHandler = (e) => {
    if (e.key === 'Escape') {
      closeDomainCertificate();
      document.removeEventListener('keydown', escHandler);
    }
  };
  document.addEventListener('keydown', escHandler);
}

function closeDomainCertificate() {
  const overlay = document.getElementById('domain-certificate-overlay');
  if (overlay) overlay.classList.remove('open');
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------
function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
