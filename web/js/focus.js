/**
 * Focus Mode (Sprint 14B)
 *
 * Locked-neighborhood focus state. When active, the graph dims everything
 * outside the focused entities and their 1-hop neighbors. Clicking a
 * peripheral (visible, non-focused) node expands the focused set instead
 * of falling back to the full graph view.
 *
 * State lives on FocusState (module global). URL ?focus=<id>[,<id>...]
 * round-trips via replaceState so reload + back/forward work.
 *
 * Dimming uses .focus-dimmed (Cytoscape class) — separate from
 * .neighborhood-dimmed per docs/ux/troubleshooting.md (dimming contexts
 * must not be mixed).
 */

const FocusState = {
  focusedIds: new Set(),
  active: false
};

/** True when focus mode is currently engaged. */
function isFocusActive() {
  return FocusState.active;
}

/**
 * Enter focus mode on a single entity. Pushes the URL so the browser
 * history records the transition.
 */
function enterFocus(cy, entityId, { pushUrl = true } = {}) {
  if (!cy || !entityId) return;
  const node = cy.getElementById(entityId);
  if (!node || node.length === 0) return;

  FocusState.focusedIds = new Set([entityId]);
  FocusState.active = true;

  applyFocusStyling(cy);
  renderFocusChip(cy);

  if (pushUrl) writeFocusToUrl({ replace: false });
}

/**
 * Expand focus to include another entity (e.g., the user clicked a
 * peripheral neighbor). No-op if already focused. Updates URL in place.
 */
function expandFocus(cy, entityId) {
  if (!cy || !entityId || !FocusState.active) return;
  if (FocusState.focusedIds.has(entityId)) return;

  FocusState.focusedIds.add(entityId);
  applyFocusStyling(cy);
  renderFocusChip(cy);
  writeFocusToUrl({ replace: true });
}

/** Exit focus mode. Clears state, styling, chip, and URL param. */
function exitFocus(cy, { pushUrl = true } = {}) {
  FocusState.focusedIds = new Set();
  FocusState.active = false;

  if (cy) clearFocusStyling(cy);
  hideFocusChip();

  if (pushUrl) writeFocusToUrl({ replace: false });
}

/**
 * Dim everything that isn't a focused node, its 1-hop neighbors, or an
 * edge between visible nodes. Idempotent — always clears first.
 */
function applyFocusStyling(cy) {
  if (!cy) return;
  clearFocusStyling(cy);

  const visibleNodes = cy.collection();
  let acc = visibleNodes;
  FocusState.focusedIds.forEach(id => {
    const n = cy.getElementById(id);
    if (n && n.length > 0) {
      acc = acc.union(n.closedNeighborhood('node'));
    }
  });

  const visibleNodeIds = new Set();
  acc.forEach(n => visibleNodeIds.add(n.id()));

  cy.nodes().forEach(n => {
    if (!visibleNodeIds.has(n.id())) n.addClass('focus-dimmed');
  });

  // Edges visible only when BOTH endpoints are visible.
  cy.edges().forEach(e => {
    const srcVisible = visibleNodeIds.has(e.source().id());
    const tgtVisible = visibleNodeIds.has(e.target().id());
    if (!(srcVisible && tgtVisible)) e.addClass('focus-dimmed');
  });
}

function clearFocusStyling(cy) {
  if (!cy) return;
  cy.elements().removeClass('focus-dimmed');
}

/**
 * True when the given node id is dimmed-but-visible (a 1-hop neighbor
 * of a focused node, but not itself focused). Used by the tap handler
 * to decide whether a click should expand focus.
 */
function isPeripheralNeighbor(cy, nodeId) {
  if (!cy || !FocusState.active) return false;
  if (FocusState.focusedIds.has(nodeId)) return false;

  const node = cy.getElementById(nodeId);
  if (!node || node.length === 0) return false;
  if (node.hasClass('focus-dimmed')) return false;

  return true;
}

/* -------------------------------------------------------------------------
 * Focus chip UI
 * ----------------------------------------------------------------------- */

/** Create the chip element lazily, mounted into #main-content. */
function ensureFocusChip() {
  let chip = document.getElementById('focus-chip');
  if (chip) return chip;

  chip = document.createElement('div');
  chip.id = 'focus-chip';
  chip.className = 'focus-chip hidden';
  chip.setAttribute('role', 'status');
  chip.setAttribute('aria-live', 'polite');
  chip.innerHTML = `
    <span class="focus-chip-label">Focused: <span class="focus-chip-text"></span></span>
    <button type="button" class="focus-chip-close"
            aria-label="Exit focus mode" title="Exit focus mode (Esc)">&times;</button>
  `;

  const main = document.getElementById('main-content') || document.body;
  main.appendChild(chip);

  chip.querySelector('.focus-chip-close').addEventListener('click', () => {
    exitFocus(window.cy);
  });
  return chip;
}

function renderFocusChip(cy) {
  const chip = ensureFocusChip();
  if (!FocusState.active || FocusState.focusedIds.size === 0) {
    chip.classList.add('hidden');
    return;
  }

  const ids = Array.from(FocusState.focusedIds);
  const firstId = ids[0];
  const firstNode = cy?.getElementById(firstId);
  const firstLabel = (firstNode && firstNode.length > 0)
    ? (firstNode.data('label') || firstId)
    : firstId;

  const text = ids.length === 1
    ? firstLabel
    : `${firstLabel} + ${ids.length - 1} more`;

  const textEl = chip.querySelector('.focus-chip-text');
  if (textEl) textEl.textContent = text;
  chip.classList.remove('hidden');
}

function hideFocusChip() {
  const chip = document.getElementById('focus-chip');
  if (chip) chip.classList.add('hidden');
}

/* -------------------------------------------------------------------------
 * URL state
 * ----------------------------------------------------------------------- */

/**
 * Write current focus state to ?focus= in the URL. Uses replaceState
 * for expand/exit (intra-mode), pushState only when entering for the
 * first time (so Back returns to non-focus view).
 */
function writeFocusToUrl({ replace = false } = {}) {
  const url = new URL(window.location.href);
  if (FocusState.active && FocusState.focusedIds.size > 0) {
    url.searchParams.set('focus', Array.from(FocusState.focusedIds).join(','));
  } else {
    url.searchParams.delete('focus');
  }

  const method = replace ? 'replaceState' : 'pushState';
  window.history[method]({ focus: Array.from(FocusState.focusedIds) }, '', url.toString());
}

/**
 * Parse ?focus= from current URL. Returns array of ids (empty if absent).
 */
function readFocusFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const raw = params.get('focus');
  if (!raw) return [];
  return raw.split(',').map(s => s.trim()).filter(Boolean);
}

/**
 * Called from app.js once the graph is loaded. If ?focus= is in the URL,
 * enter focus mode without pushing a new history entry.
 */
function initFocusFromUrl(cy) {
  if (!cy) return;
  const ids = readFocusFromUrl();
  if (ids.length === 0) return;

  const validIds = ids.filter(id => {
    const n = cy.getElementById(id);
    return n && n.length > 0;
  });

  if (validIds.length === 0) {
    // URL referenced an entity not on the canvas — strip the bad param.
    const url = new URL(window.location.href);
    url.searchParams.delete('focus');
    window.history.replaceState({}, '', url.toString());
    return;
  }

  FocusState.focusedIds = new Set(validIds);
  FocusState.active = true;
  applyFocusStyling(cy);
  renderFocusChip(cy);
}

/**
 * Handle back/forward — sync focus state from the new URL.
 */
function onFocusPopState(cy) {
  const ids = readFocusFromUrl();
  if (ids.length === 0) {
    FocusState.focusedIds = new Set();
    FocusState.active = false;
    if (cy) clearFocusStyling(cy);
    hideFocusChip();
    return;
  }

  FocusState.focusedIds = new Set(ids);
  FocusState.active = true;
  if (cy) {
    applyFocusStyling(cy);
    renderFocusChip(cy);
  }
}

/**
 * Wire global focus handlers (Esc to exit, popstate sync). Called once
 * from app.js init.
 */
function initFocusGlobalHandlers(cy) {
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (!FocusState.active) return;
    // Don't fire if a search input is focused — Esc there should clear search
    const active = document.activeElement;
    if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA')) return;
    exitFocus(cy);
    e.preventDefault();
  });

  window.addEventListener('popstate', () => onFocusPopState(cy));
}

// Expose for tests and cross-module access
if (typeof window !== 'undefined') {
  window.FocusState = FocusState;
  window.isFocusActive = isFocusActive;
  window.enterFocus = enterFocus;
  window.expandFocus = expandFocus;
  window.exitFocus = exitFocus;
  window.isPeripheralNeighbor = isPeripheralNeighbor;
  window.applyFocusStyling = applyFocusStyling;
  window.initFocusFromUrl = initFocusFromUrl;
  window.initFocusGlobalHandlers = initFocusGlobalHandlers;
}
