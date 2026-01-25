# Design Tokens

The design foundation for a clean, professional UI. These tokens ensure visual consistency across all components.

**Philosophy:** Invisible good design. Nothing clever, nothing flashy—just intentional choices that make the tool feel solid and trustworthy.

-----

## Quick Reference

```css
/* Paste this at the top of your main CSS file */
:root {
  /* Spacing (4px base) */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;

  /* Typography */
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  --font-mono: "SF Mono", SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;

  --text-xs: 11px;
  --text-sm: 13px;
  --text-base: 14px;
  --text-md: 16px;
  --text-lg: 18px;
  --text-xl: 24px;
  --text-2xl: 30px;

  --leading-tight: 1.25;
  --leading-normal: 1.5;
  --leading-relaxed: 1.625;

  --weight-normal: 400;
  --weight-medium: 500;
  --weight-semibold: 600;
  --weight-bold: 700;

  /* Colors - Neutrals */
  --gray-50: #F9FAFB;
  --gray-100: #F3F4F6;
  --gray-200: #E5E7EB;
  --gray-300: #D1D5DB;
  --gray-400: #9CA3AF;
  --gray-500: #6B7280;
  --gray-600: #4B5563;
  --gray-700: #374151;
  --gray-800: #1F2937;
  --gray-900: #111827;

  /* Colors - Brand (Primary actions, links) */
  --blue-500: #3B82F6;
  --blue-600: #2563EB;
  --blue-700: #1D4ED8;

  /* Colors - Semantic */
  --color-success: #10B981;
  --color-warning: #F59E0B;
  --color-error: #EF4444;
  --color-info: #3B82F6;

  /* Colors - Entity Types (from visual-encoding.md) */
  --color-org: #4A90D9;
  --color-person: #50B4A8;
  --color-program: #6366F1;
  --color-tool: #8B5CF6;
  --color-model: #7C3AED;
  --color-dataset: #F59E0B;
  --color-benchmark: #D97706;
  --color-paper: #10B981;
  --color-repo: #059669;
  --color-tech: #EAB308;
  --color-topic: #64748B;
  --color-document: #9CA3AF;
  --color-event: #F43F5E;
  --color-location: #0EA5E9;
  --color-other: #A1A1AA;

  /* Colors - Graph-specific */
  --edge-default: #6B7280;
  --edge-new: #22C55E;
  --edge-hover: #3B82F6;
  --edge-selected: #2563EB;
  --edge-dimmed: #D1D5DB;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.07), 0 2px 4px rgba(0, 0, 0, 0.05);
  --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.1), 0 4px 6px rgba(0, 0, 0, 0.05);
  --shadow-xl: 0 20px 25px rgba(0, 0, 0, 0.1), 0 10px 10px rgba(0, 0, 0, 0.04);

  /* Borders */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;
  --radius-full: 9999px;

  --border-color: var(--gray-200);
  --border-color-hover: var(--gray-300);
  --border-width: 1px;

  /* Transitions */
  --duration-fast: 100ms;
  --duration-normal: 200ms;
  --duration-slow: 300ms;
  --easing-default: cubic-bezier(0.4, 0, 0.2, 1);
  --easing-in: cubic-bezier(0.4, 0, 1, 1);
  --easing-out: cubic-bezier(0, 0, 0.2, 1);

  /* Z-Index Scale */
  --z-dropdown: 100;
  --z-sticky: 200;
  --z-overlay: 300;
  --z-modal: 400;
  --z-tooltip: 500;

  /* Layout */
  --toolbar-height: 56px;
  --panel-width: 280px;
  --max-content-width: 1200px;
}
```

-----

## Spacing

Built on a 4px base unit. Use these, not arbitrary pixel values.

|Token       |Value|Usage                                 |
|------------|-----|--------------------------------------|
|`--space-1` |4px  |Tight internal spacing, icon gaps     |
|`--space-2` |8px  |Default internal padding, small gaps  |
|`--space-3` |12px |Comfortable padding, list item spacing|
|`--space-4` |16px |Standard padding, paragraph spacing   |
|`--space-5` |20px |Section padding (small)               |
|`--space-6` |24px |Section padding (medium)              |
|`--space-8` |32px |Section separation                    |
|`--space-10`|40px |Large section gaps                    |
|`--space-12`|48px |Major layout divisions                |
|`--space-16`|64px |Page-level spacing                    |

### Usage Guidelines

```css
/* ✓ Good */
.card {
  padding: var(--space-4);
  margin-bottom: var(--space-6);
}

.card-header {
  padding: var(--space-3) var(--space-4);
  gap: var(--space-2);
}

/* ✗ Bad */
.card {
  padding: 15px;
  margin-bottom: 22px;
}
```

### Common Patterns

```css
/* Tight: dense UI, compact lists */
gap: var(--space-1);  /* 4px */
padding: var(--space-2);  /* 8px */

/* Comfortable: default for most components */
gap: var(--space-2);  /* 8px */
padding: var(--space-3) var(--space-4);  /* 12px 16px */

/* Relaxed: panels, cards, sections */
gap: var(--space-4);  /* 16px */
padding: var(--space-4) var(--space-6);  /* 16px 24px */
```

-----

## Typography

### Font Stack

```css
/* Primary - UI text */
font-family: var(--font-sans);

/* Code, IDs, technical values */
font-family: var(--font-mono);
```

### Size Scale

|Token        |Size|Usage                                |
|-------------|----|-------------------------------------|
|`--text-xs`  |11px|Labels, badges, tertiary info        |
|`--text-sm`  |13px|Secondary text, captions, helper text|
|`--text-base`|14px|**Default body text**                |
|`--text-md`  |16px|Emphasized body, subheadings         |
|`--text-lg`  |18px|Panel titles, section headers        |
|`--text-xl`  |24px|Page titles                          |
|`--text-2xl` |30px|Hero/display (rarely used)           |

### Type Patterns

```css
/* Body text */
.body {
  font-size: var(--text-base);
  line-height: var(--leading-normal);
  color: var(--gray-700);
}

/* Secondary/helper text */
.helper {
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
  color: var(--gray-500);
}

/* Section header */
.section-title {
  font-size: var(--text-lg);
  font-weight: var(--weight-semibold);
  line-height: var(--leading-tight);
  color: var(--gray-900);
}

/* Small label */
.label {
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--gray-500);
}

/* Monospace for IDs, code */
.mono {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
}
```

-----

## Color System

### Neutrals (Gray Scale)

Use grays intentionally:

|Token       |Usage                          |
|------------|-------------------------------|
|`--gray-50` |Page background, subtle fills  |
|`--gray-100`|Card backgrounds, hover states |
|`--gray-200`|Borders, dividers              |
|`--gray-300`|Disabled borders, subtle icons |
|`--gray-400`|Placeholder text, disabled text|
|`--gray-500`|Secondary text, icons          |
|`--gray-600`|Body text (secondary)          |
|`--gray-700`|**Body text (primary)**        |
|`--gray-800`|Headings, emphasis             |
|`--gray-900`|High-contrast headings         |

```css
/* Text hierarchy */
.text-primary { color: var(--gray-700); }    /* Default body */
.text-secondary { color: var(--gray-500); }  /* Less important */
.text-tertiary { color: var(--gray-400); }   /* Hints, placeholders */
.text-heading { color: var(--gray-900); }    /* Titles */
```

### Interactive Colors

```css
/* Primary actions (buttons, links) */
.btn-primary {
  background: var(--blue-500);
  color: white;
}
.btn-primary:hover {
  background: var(--blue-600);
}
.btn-primary:active {
  background: var(--blue-700);
}

/* Links */
a {
  color: var(--blue-500);
}
a:hover {
  color: var(--blue-600);
}

/* Focus rings (accessibility) */
:focus-visible {
  outline: 2px solid var(--blue-500);
  outline-offset: 2px;
}
```

### Semantic Colors

```css
/* Status indicators */
.status-success { color: var(--color-success); }  /* #10B981 */
.status-warning { color: var(--color-warning); }  /* #F59E0B */
.status-error { color: var(--color-error); }      /* #EF4444 */
.status-info { color: var(--color-info); }        /* #3B82F6 */

/* Backgrounds for status */
.bg-success { background: #D1FAE5; }  /* green-100 equivalent */
.bg-warning { background: #FEF3C7; }  /* amber-100 equivalent */
.bg-error { background: #FEE2E2; }    /* red-100 equivalent */
.bg-info { background: #DBEAFE; }     /* blue-100 equivalent */
```

### Entity Type Colors

Defined in visual-encoding.md, exposed as tokens for consistency:

```css
/* Use in type badges, node colors, legends */
.type-org { background: var(--color-org); }
.type-person { background: var(--color-person); }
.type-model { background: var(--color-model); }
/* ... etc */
```

-----

## Shadows

Three levels, used consistently:

|Token        |Usage                                    |
|-------------|-----------------------------------------|
|`--shadow-sm`|Subtle depth: cards at rest, inputs      |
|`--shadow-md`|Interactive elements: dropdowns, popovers|
|`--shadow-lg`|Modals, floating panels                  |
|`--shadow-xl`|Rarely used, max emphasis                |

```css
/* Cards */
.card {
  box-shadow: var(--shadow-sm);
}
.card:hover {
  box-shadow: var(--shadow-md);
}

/* Dropdowns, tooltips */
.dropdown {
  box-shadow: var(--shadow-md);
}

/* Modal overlays */
.modal {
  box-shadow: var(--shadow-lg);
}
```

-----

## Border Radius

|Token          |Value |Usage                                    |
|---------------|------|-----------------------------------------|
|`--radius-sm`  |4px   |Small elements: badges, chips, checkboxes|
|`--radius-md`  |6px   |**Default**: buttons, inputs, cards      |
|`--radius-lg`  |8px   |Panels, larger cards                     |
|`--radius-xl`  |12px  |Modals, prominent containers             |
|`--radius-full`|9999px|Pills, avatars, circular elements        |

```css
/* Buttons and inputs */
.btn, .input {
  border-radius: var(--radius-md);
}

/* Badges */
.badge {
  border-radius: var(--radius-sm);
}

/* Panels */
.panel {
  border-radius: var(--radius-lg);
}

/* Pills */
.pill {
  border-radius: var(--radius-full);
}
```

-----

## Transitions

### Duration

|Token              |Value|Usage                                  |
|-------------------|-----|---------------------------------------|
|`--duration-fast`  |100ms|Micro-interactions: hover color changes|
|`--duration-normal`|200ms|**Default**: most transitions          |
|`--duration-slow`  |300ms|Panel slides, larger movements         |

### Easing

|Token             |Usage                       |
|------------------|----------------------------|
|`--easing-default`|General purpose, balanced   |
|`--easing-out`    |Elements entering (slide in)|
|`--easing-in`     |Elements exiting (slide out)|

### Common Patterns

```css
/* Interactive element (button, link) */
.btn {
  transition: background-color var(--duration-fast) var(--easing-default),
              box-shadow var(--duration-fast) var(--easing-default);
}

/* Panel open/close */
.panel {
  transition: transform var(--duration-slow) var(--easing-out),
              opacity var(--duration-normal) var(--easing-out);
}

/* Tooltip fade */
.tooltip {
  transition: opacity var(--duration-fast) var(--easing-default);
}
```

### Reduced Motion

Always respect user preference:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }
}
```

-----

## Z-Index

A predictable stacking system:

|Token         |Value|Usage                   |
|--------------|-----|------------------------|
|`--z-dropdown`|100  |Dropdowns, select menus |
|`--z-sticky`  |200  |Sticky headers, toolbar |
|`--z-overlay` |300  |Panel overlays, sidebars|
|`--z-modal`   |400  |Modal dialogs           |
|`--z-tooltip` |500  |Tooltips (always on top)|

```css
#toolbar {
  z-index: var(--z-sticky);
}

#filter-panel {
  z-index: var(--z-overlay);
}

#tooltip {
  z-index: var(--z-tooltip);
}
```

-----

## CSS Architecture

### Naming Convention

Use simple, flat class names. No strict BEM, but consistent patterns:

```css
/* Component */
.panel { }

/* Component element (single dash) */
.panel-header { }
.panel-content { }
.panel-footer { }

/* Component modifier (double dash) */
.panel--collapsed { }
.panel--wide { }

/* State (separate class) */
.panel.is-open { }
.panel.is-loading { }

/* Utility (prefix with u-) */
.u-hidden { display: none; }
.u-sr-only { /* screen reader only */ }
```

### File Organization

```
web/css/
├── tokens.css          # All CSS custom properties
├── reset.css           # Minimal reset (box-sizing, margins)
├── base.css            # Body, typography defaults, links
├── components/
│   ├── button.css
│   ├── input.css
│   ├── panel.css
│   ├── toolbar.css
│   ├── tooltip.css
│   ├── badge.css
│   └── ...
├── graph/
│   ├── cytoscape.css   # Cytoscape container styles
│   └── overlays.css    # Graph-specific overlays
├── utilities.css       # Small utility classes
└── main.css            # Imports all above in order
```

### Import Order

```css
/* main.css */
@import 'tokens.css';
@import 'reset.css';
@import 'base.css';

@import 'components/button.css';
@import 'components/input.css';
@import 'components/panel.css';
/* ... other components ... */

@import 'graph/cytoscape.css';
@import 'graph/overlays.css';

@import 'utilities.css';
```

-----

## Component States

Every interactive component should handle these states:

|State       |Visual Treatment                         |
|------------|-----------------------------------------|
|**Default** |Base appearance                          |
|**Hover**   |Subtle background/border change          |
|**Focus**   |Visible focus ring (`outline`)           |
|**Active**  |Pressed/clicked feedback                 |
|**Disabled**|Reduced opacity, `cursor: not-allowed`   |
|**Loading** |Spinner or skeleton, disabled interaction|
|**Error**   |Red border, error message below          |
|**Empty**   |Helpful message, optional action         |

### Example: Button States

```css
.btn {
  background: var(--gray-100);
  border: var(--border-width) solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-base);
  font-weight: var(--weight-medium);
  color: var(--gray-700);
  cursor: pointer;
  transition: background-color var(--duration-fast) var(--easing-default),
              border-color var(--duration-fast) var(--easing-default);
}

.btn:hover {
  background: var(--gray-200);
  border-color: var(--border-color-hover);
}

.btn:focus-visible {
  outline: 2px solid var(--blue-500);
  outline-offset: 2px;
}

.btn:active {
  background: var(--gray-300);
}

.btn:disabled,
.btn.is-disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}

.btn.is-loading {
  color: transparent;
  pointer-events: none;
  position: relative;
}

.btn.is-loading::after {
  content: '';
  position: absolute;
  /* spinner styles */
}
```

-----

## Responsive Breakpoints

Mobile-first approach with three breakpoints:

```css
/* Mobile first (default styles) */
.panel {
  width: 100%;
}

/* Tablet (640px+) */
@media (min-width: 640px) {
  .panel {
    width: var(--panel-width);
  }
}

/* Desktop (1024px+) */
@media (min-width: 1024px) {
  /* Full layout */
}

/* Wide (1280px+) */
@media (min-width: 1280px) {
  /* Extra space utilization */
}
```

|Breakpoint|Target                               |
|----------|-------------------------------------|
|< 640px   |Mobile (single column, stacked)      |
|640px+    |Tablet (side panels, toolbar visible)|
|1024px+   |Desktop (full layout)                |
|1280px+   |Wide (optional, extra space)         |

-----

## Accessibility Checklist

Every component should meet:

- [ ] **Color contrast**: 4.5:1 for text, 3:1 for UI elements
- [ ] **Focus visible**: Clear focus indicator on keyboard navigation
- [ ] **Touch targets**: Minimum 44×44px for interactive elements
- [ ] **Reduced motion**: Respect `prefers-reduced-motion`
- [ ] **Screen reader**: Proper ARIA labels, live regions for updates
- [ ] **Keyboard**: All interactions possible without mouse

-----

## Anti-Patterns

**Don’t do these:**

```css
/* ✗ Magic numbers */
padding: 13px 17px;
margin-top: 22px;

/* ✗ Hardcoded colors */
color: #374151;
background: #3B82F6;

/* ✗ Inline styles for tokens */
<div style="padding: 16px">

/* ✗ Overriding with !important */
.special { padding: 20px !important; }

/* ✗ Deep nesting */
.panel .panel-content .panel-section .panel-item .panel-label { }

/* ✗ Generic class names */
.container { }
.wrapper { }
.content { }
```

**Do these instead:**

```css
/* ✓ Use tokens */
padding: var(--space-3) var(--space-4);
margin-top: var(--space-5);

/* ✓ Reference color variables */
color: var(--gray-700);
background: var(--blue-500);

/* ✓ Flat, specific selectors */
.panel-label { }

/* ✓ Scoped, meaningful names */
.filter-panel { }
.evidence-card { }
.graph-toolbar { }
```

-----

## Summary

The tokens in this document are the vocabulary for the UI. Everything visual should trace back to these values:

- **Spacing**: Multiples of 4px via `--space-*`
- **Type**: Sizes from `--text-xs` to `--text-2xl`
- **Color**: Grays for text/borders, blues for interaction, semantic colors for status
- **Depth**: Three shadow levels
- **Shape**: Four radius options
- **Motion**: Three durations, respect reduced motion

When in doubt: **be boring**. Consistent beats clever. If something looks off, check if it’s using the tokens. If not, that’s probably why.