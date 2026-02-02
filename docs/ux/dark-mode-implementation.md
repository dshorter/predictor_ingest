# Dark/Light Theme Implementation Guide

Mechanical instructions for a Sonnet session. All design decisions are made —
this is pure refactoring. Do not improvise colors or add features beyond what
is listed here.

---

## Overview

- Add semantic color variables to `tokens.css`
- Add dark palette via `[data-theme="dark"]` selector
- Auto-detect OS preference with manual toggle override
- Refactor hardcoded colors in CSS (11 values) and JS (28 values)
- Wire Cytoscape styles to read from CSS variables at runtime
- Total: ~6 files modified, 1 new function, ~200 lines added

---

## Step 1: Add Semantic Variables to `tokens.css`

The help panel CSS already references these (with fallbacks). Define them
formally in `:root` so all files can use them. Add this block AFTER the
existing `Colors - Graph-specific` section:

```css
/* ==========================================================================
   Colors - Semantic Surface (light mode defaults)
   ========================================================================== */
--color-bg-primary: #FFFFFF;
--color-bg-secondary: #F9FAFB;       /* gray-50 */
--color-bg-tertiary: #F3F4F6;        /* gray-100 */
--color-bg-info: #EFF6FF;
--color-text-primary: #1F2937;        /* gray-800 */
--color-text-secondary: #6B7280;      /* gray-500 */
--color-text-tertiary: #9CA3AF;       /* gray-400 */
--color-border-primary: #D1D5DB;      /* gray-300 */
--color-border-secondary: #E5E7EB;    /* gray-200 */
--color-primary: #3B82F6;             /* blue-500 */
--color-focus-ring: rgba(59, 130, 246, 0.2);
--color-overlay: rgba(255, 255, 255, 0.9);
--color-overlay-heavy: rgba(255, 255, 255, 0.95);
--color-badge-success-bg: #D1FAE5;
--color-badge-warning-bg: #FEF3C7;
--color-badge-error-bg: #FEE2E2;
--color-badge-info-bg: #DBEAFE;

/* Cytoscape-specific (used by styles.js via getComputedStyle) */
--cy-text-color: #1F2937;
--cy-text-outline: #FFFFFF;
--cy-node-border: #D1D5DB;
--cy-node-border-hover: #3B82F6;
--cy-node-border-selected: #2563EB;
--cy-node-overlay-selected: #3B82F6;
--cy-node-border-highlighted: #F59E0B;
--cy-node-border-new: #22C55E;
```

---

## Step 2: Add Dark Palette

Add this block at the END of `tokens.css`, AFTER the `:root` block closes:

```css
[data-theme="dark"] {
  --color-bg-primary: #111827;          /* gray-900 */
  --color-bg-secondary: #1F2937;        /* gray-800 */
  --color-bg-tertiary: #374151;         /* gray-700 */
  --color-bg-info: #1E3A5F;
  --color-text-primary: #F3F4F6;        /* gray-100 */
  --color-text-secondary: #9CA3AF;      /* gray-400 */
  --color-text-tertiary: #6B7280;       /* gray-500 */
  --color-border-primary: #4B5563;      /* gray-600 */
  --color-border-secondary: #374151;    /* gray-700 */
  --color-primary: #60A5FA;             /* blue-400 — brighter for dark bg */
  --color-focus-ring: rgba(96, 165, 250, 0.3);
  --color-overlay: rgba(17, 24, 39, 0.9);
  --color-overlay-heavy: rgba(17, 24, 39, 0.95);
  --color-badge-success-bg: #064E3B;
  --color-badge-warning-bg: #78350F;
  --color-badge-error-bg: #7F1D1D;
  --color-badge-info-bg: #1E3A5F;

  /* Cytoscape dark overrides */
  --cy-text-color: #F3F4F6;
  --cy-text-outline: #111827;
  --cy-node-border: #4B5563;
  --cy-node-border-hover: #60A5FA;
  --cy-node-border-selected: #3B82F6;
  --cy-node-overlay-selected: #60A5FA;
  --cy-node-border-highlighted: #FBBF24;
  --cy-node-border-new: #34D399;

  /* Override grays used directly */
  --gray-50: #1F2937;
  --gray-100: #374151;
  --gray-200: #4B5563;
  --gray-300: #6B7280;
  --gray-800: #F3F4F6;
  --gray-900: #F9FAFB;

  /* Override border/shadow */
  --border-color: var(--gray-300);
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.4), 0 2px 4px rgba(0, 0, 0, 0.2);
  --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.4), 0 4px 6px rgba(0, 0, 0, 0.2);
}
```

**Note on entity type colors:** The 15 entity colors (`--color-org`, etc.) and
5 edge colors (`--edge-default`, etc.) are the SAME in dark mode. They are
already mid-tone saturated colors that work on both light and dark backgrounds.
Do NOT change them. If testing reveals any are hard to read on dark, adjust
only those specific ones.

---

## Step 3: Replace Hardcoded Colors in CSS Files

### `badge.css` — 6 replacements

| Line | Old | New |
|------|-----|-----|
| 26 | `background-color: #D1FAE5` | `background-color: var(--color-badge-success-bg)` |
| 31 | `background-color: #FEF3C7` | `background-color: var(--color-badge-warning-bg)` |
| 36 | `background-color: #FEE2E2` | `background-color: var(--color-badge-error-bg)` |
| 41 | `background-color: #DBEAFE` | `background-color: var(--color-badge-info-bg)` |
| 128 | `background-color: #FEF3C7` | `background-color: var(--color-badge-warning-bg)` |
| 133 | `background-color: #DBEAFE` | `background-color: var(--color-badge-info-bg)` |

### `tooltip.css` — 2 replacements

| Line | Old | New |
|------|-----|-----|
| 134 | `background-color: #FEF3C7` | `background-color: var(--color-badge-warning-bg)` |
| 139 | `background-color: #D1FAE5` | `background-color: var(--color-badge-success-bg)` |

### `overlays.css` — 3 replacements

| Line | Old | New |
|------|-----|-----|
| 17 | `rgba(255, 255, 255, 0.9)` | `var(--color-overlay)` |
| 53 | `rgba(255, 255, 255, 0.95)` | `var(--color-overlay-heavy)` |
| 84 | `#FEF3C7` | `var(--color-badge-warning-bg)` |

### `input.css` — 2 replacements

| Line | Old | New |
|------|-----|-----|
| 35 | `rgba(59, 130, 246, 0.1)` | `var(--color-focus-ring)` |
| 62 | `rgba(59, 130, 246, 0.1)` | `var(--color-focus-ring)` |

### `toolbar.css` — 1 replacement

| Line | Old | New |
|------|-----|-----|
| 107 | `rgba(59, 130, 246, 0.1)` | `var(--color-focus-ring)` |

### `help-panel.css` — 0 replacements

Already uses `var(--color-*, fallback)` syntax. Once tokens.css defines the
variables, the fallbacks become unused. **No changes needed** — the fallbacks
are harmless and provide backwards compatibility.

### Total CSS: 14 mechanical find-and-replace operations across 4 files

---

## Step 4: Refactor `styles.js` — Cytoscape Colors from CSS Variables

Cytoscape.js does NOT use CSS — it has its own style objects in JS. Colors
must be read from CSS variables at runtime via `getComputedStyle`.

### 4a. Add a helper function (top of `styles.js`)

```javascript
/**
 * Read a CSS custom property value from :root.
 * Returns the trimmed string value or the fallback if not found.
 */
function getCSSVar(name, fallback) {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name).trim();
  return value || fallback;
}
```

### 4b. Replace hardcoded `nodeTypeColors` (lines 9-25)

```javascript
function getNodeTypeColors() {
  return {
    'Org': getCSSVar('--color-org', '#4A90D9'),
    'Person': getCSSVar('--color-person', '#50B4A8'),
    'Program': getCSSVar('--color-program', '#6366F1'),
    'Tool': getCSSVar('--color-tool', '#8B5CF6'),
    'Model': getCSSVar('--color-model', '#7C3AED'),
    'Dataset': getCSSVar('--color-dataset', '#F59E0B'),
    'Benchmark': getCSSVar('--color-benchmark', '#D97706'),
    'Paper': getCSSVar('--color-paper', '#10B981'),
    'Repo': getCSSVar('--color-repo', '#059669'),
    'Tech': getCSSVar('--color-tech', '#EAB308'),
    'Topic': getCSSVar('--color-topic', '#64748B'),
    'Document': getCSSVar('--color-document', '#9CA3AF'),
    'Event': getCSSVar('--color-event', '#F43F5E'),
    'Location': getCSSVar('--color-location', '#0EA5E9'),
    'Other': getCSSVar('--color-other', '#A1A1AA')
  };
}
```

### 4c. Replace hardcoded `edgeColors` (lines 28-34)

```javascript
function getEdgeColors() {
  return {
    default: getCSSVar('--edge-default', '#6B7280'),
    new: getCSSVar('--edge-new', '#22C55E'),
    hover: getCSSVar('--edge-hover', '#3B82F6'),
    selected: getCSSVar('--edge-selected', '#2563EB'),
    dimmed: getCSSVar('--edge-dimmed', '#D1D5DB')
  };
}
```

### 4d. Replace hardcoded inline hex values in the Cytoscape stylesheet

Inside `getCytoscapeStyles()`, replace each hardcoded hex with a `getCSSVar` call:

| Line | Old | New |
|------|-----|-----|
| 138 | `'color': '#1F2937'` | `'color': getCSSVar('--cy-text-color', '#1F2937')` |
| 139 | `'text-outline-color': '#FFFFFF'` | `'text-outline-color': getCSSVar('--cy-text-outline', '#FFFFFF')` |
| 143 | `'border-color': '#D1D5DB'` | `'border-color': getCSSVar('--cy-node-border', '#D1D5DB')` |
| 153 | `'border-color': '#3B82F6'` | `'border-color': getCSSVar('--cy-node-border-hover', '#3B82F6')` |
| 167 | `'border-color': '#2563EB'` | `'border-color': getCSSVar('--cy-node-border-selected', '#2563EB')` |
| 169 | `'overlay-color': '#3B82F6'` | `'overlay-color': getCSSVar('--cy-node-overlay-selected', '#3B82F6')` |
| 181 | `'border-color': '#F59E0B'` | `'border-color': getCSSVar('--cy-node-border-highlighted', '#F59E0B')` |
| 208 | `'border-color': '#22C55E'` | `'border-color': getCSSVar('--cy-node-border-new', '#22C55E')` |

### 4e. Make `nodeTypeColors` and `edgeColors` dynamic

Every reference to `nodeTypeColors[type]` in the stylesheet function must
call `getNodeTypeColors()` at stylesheet build time. The simplest approach:

```javascript
function getCytoscapeStyles() {
  const nodeTypeColors = getNodeTypeColors();
  const edgeColors = getEdgeColors();
  // ... rest of function unchanged, uses local nodeTypeColors/edgeColors
}
```

This means `getCytoscapeStyles()` reads fresh CSS variable values each time
it's called.

---

## Step 5: Refactor `help/content.js` — Inline Color Swatches

Lines 158-165 have inline `style="background: #HEX"` for color legend swatches.

Replace each with the corresponding CSS variable:

```html
<span class="color-swatch" style="background: var(--color-org);"></span>
<span class="color-swatch" style="background: var(--color-model);"></span>
<span class="color-swatch" style="background: var(--color-person);"></span>
<span class="color-swatch" style="background: var(--color-tool);"></span>
<span class="color-swatch" style="background: var(--color-dataset);"></span>
<span class="color-swatch" style="background: var(--color-paper);"></span>
<span class="color-swatch" style="background: var(--color-tech);"></span>
<span class="color-swatch" style="background: var(--color-topic);"></span>
```

Lines 204-206 have hex codes in text descriptions. These are documentation
text, not styling — leave them as-is (the hex values are informational).

---

## Step 6: Theme Toggle + OS Detection

### 6a. Add to `app.js` (in the initialization section)

```javascript
/**
 * Initialize theme from OS preference or saved preference.
 * Saved preference (localStorage) overrides OS detection.
 */
function initTheme() {
  const saved = localStorage.getItem('theme');
  if (saved) {
    document.documentElement.setAttribute('data-theme', saved);
  } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
  // else: no attribute = light mode (default)

  // Listen for OS theme changes (only if no saved preference)
  window.matchMedia('(prefers-color-scheme: dark)')
    .addEventListener('change', (e) => {
      if (!localStorage.getItem('theme')) {
        document.documentElement.setAttribute(
          'data-theme', e.matches ? 'dark' : 'light'
        );
        reapplyGraphStyles();
      }
    });
}

/**
 * Toggle theme between light and dark. Saves to localStorage.
 */
function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  reapplyGraphStyles();
}

/**
 * Re-read CSS variables and reapply Cytoscape styles.
 * Must be called after any theme change.
 */
function reapplyGraphStyles() {
  if (AppState.cy) {
    AppState.cy.style(getCytoscapeStyles());
    AppState.cy.style().update();
  }
}
```

Call `initTheme()` at the top of `initializeApp()`, BEFORE any graph rendering.

### 6b. Add toggle button to `index.html`

In the `toolbar-right` div, add before the settings button:

```html
<button id="theme-toggle" class="toolbar-btn" title="Toggle dark/light mode">
  <span id="theme-icon">☀</span>
</button>
```

### 6c. Wire the button (in `app.js` initialization)

```javascript
document.getElementById('theme-toggle')?.addEventListener('click', () => {
  toggleTheme();
  const icon = document.getElementById('theme-icon');
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  icon.textContent = isDark ? '☀' : '☾';
});
```

Set initial icon state after `initTheme()`:
```javascript
const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
const themeIcon = document.getElementById('theme-icon');
if (themeIcon) themeIcon.textContent = isDark ? '☀' : '☾';
```

---

## Step 7: Base Element Dark Styles

Add to `base.css` (or wherever `body`/`html` base styles are):

```css
html {
  background-color: var(--color-bg-primary);
  color: var(--color-text-primary);
}
```

Verify the existing `body` styles in `base.css` use token variables for
`background-color` and `color`. If they use hardcoded values, replace them.

---

## File Change Summary

| File | Action | Changes |
|------|--------|---------|
| `web/css/tokens.css` | Modify | Add ~18 semantic variables + dark `[data-theme]` block (~60 lines) |
| `web/css/components/badge.css` | Modify | 6 hex → var() replacements |
| `web/css/components/tooltip.css` | Modify | 2 hex → var() replacements |
| `web/css/components/input.css` | Modify | 2 rgba → var() replacements |
| `web/css/components/toolbar.css` | Modify | 1 rgba → var() replacement |
| `web/css/graph/overlays.css` | Modify | 3 hex/rgba → var() replacements |
| `web/css/base.css` | Modify | Verify/add bg-color + color using semantic vars |
| `web/js/styles.js` | Modify | Add `getCSSVar()`, convert static objects to functions, 8 inline hex → getCSSVar() |
| `web/js/app.js` | Modify | Add `initTheme()`, `toggleTheme()`, `reapplyGraphStyles()`, button wiring |
| `web/index.html` | Modify | Add theme toggle button |
| `web/help/content.js` | Modify | 8 inline style hex → var() references |
| `web/css/components/help-panel.css` | No changes | Already uses var() with fallbacks |

---

## Testing Checklist

1. Load page in light mode — verify no visual regressions
2. Load page in dark mode (set OS to dark) — verify auto-detection works
3. Click theme toggle — verify immediate switch, no flash
4. Reload — verify localStorage persistence
5. Check all 4 graph views in dark mode — node colors visible, labels readable
6. Check panels (detail, evidence, help) in dark mode
7. Check tooltips, badges, search box, filter panel in dark mode
8. Check overlays (loading, error, warning) in dark mode
9. Verify Cytoscape graph background is dark (not white rectangle on dark page)
10. Remove localStorage entry — verify falls back to OS preference

---

## Do NOT

- Change entity type colors (they work on both backgrounds)
- Change edge colors (same reason)
- Add any new features beyond theme toggle
- Refactor file structure or move code between files
- Add a "system" theme option (OS auto-detect already handles this)
- Add transition animations between themes (keep it simple for V1)
