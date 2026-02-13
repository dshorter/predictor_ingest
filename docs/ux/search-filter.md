# Search and Filter

Search box, filter panel, and the GraphFilter class implementation.

## Date Filtering Overview

Date filtering operates on **article publication dates** (`published_at`),
not pipeline fetch timestamps. This ensures that retroactive imports of older
articles land in the correct time window, and that trend scores match
real-world publication velocity. See
[docs/architecture/date-filtering.md](../architecture/date-filtering.md) for
the full rationale.

**Default window:** 30 days (`DEFAULT_DATE_WINDOW_DAYS` in
`src/config/__init__.py` and `web/js/app.js`). The UI activates this
automatically on load via `applyDefaultDateFilter()`. Users can switch to
7d / 90d / All using the preset buttons in the filter panel.

**Server-side vs. client-side:** The export pipeline applies date filtering
at the SQL level (backend). The web client applies a second pass via
`GraphFilter.apply()` on `firstSeen` / `lastSeen` node attributes. Both
layers use the same semantic: an entity is "active" if its observation range
overlaps the selected window.

---

## Search Box (Always Visible)

Position at top of UI, always accessible:

```html
<div id="search-container">
  <input
    type="text"
    id="search-input"
    placeholder="Search nodes..."
    autocomplete="off"
  />
  <span id="search-results-count"></span>
  <button id="search-clear" title="Clear search">×</button>
</div>
```

---

## Search Implementation

```javascript
let searchTimeout;

document.getElementById('search-input').addEventListener('input', function(e) {
  clearTimeout(searchTimeout);

  // Debounce search
  searchTimeout = setTimeout(() => {
    performSearch(e.target.value);
  }, 150);
});

function performSearch(query) {
  const trimmedQuery = query.trim().toLowerCase();

  if (!trimmedQuery) {
    // Clear search
    cy.elements().removeClass('search-match').removeClass('dimmed');
    document.getElementById('search-results-count').textContent = '';
    return;
  }

  // Find matching nodes
  const matches = cy.nodes().filter(node => {
    const label = (node.data('label') || '').toLowerCase();
    const aliases = (node.data('aliases') || []).map(a => a.toLowerCase());
    const type = (node.data('type') || '').toLowerCase();

    return label.includes(trimmedQuery) ||
           aliases.some(alias => alias.includes(trimmedQuery)) ||
           type.includes(trimmedQuery);
  });

  // Update UI
  cy.elements().removeClass('search-match');

  if (matches.length > 0) {
    // Highlight matches
    matches.addClass('search-match');

    // Include edges between matches
    const matchEdges = matches.edgesWith(matches);
    matchEdges.addClass('search-match');

    // Dim non-matches
    cy.elements().not('.search-match').addClass('dimmed');

    // Show count
    document.getElementById('search-results-count').textContent =
      `${matches.length} node${matches.length === 1 ? '' : 's'}`;
  } else {
    cy.elements().addClass('dimmed');
    document.getElementById('search-results-count').textContent = 'No matches';
  }
}

// Enter key: zoom to fit results
document.getElementById('search-input').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') {
    const matches = cy.nodes('.search-match');
    if (matches.length > 0) {
      cy.animate({
        fit: {
          eles: matches,
          padding: 50
        },
        duration: 300
      });
    }
  }

  // Escape: clear search
  if (e.key === 'Escape') {
    this.value = '';
    performSearch('');
    this.blur();
  }
});
```

---

## Filter Panel

Collapsible sidebar with comprehensive filtering:

```html
<aside id="filter-panel" class="panel collapsed">
  <button id="filter-toggle" class="panel-toggle">
    <span class="icon">⚙</span>
    <span class="label">Filters</span>
  </button>

  <div class="panel-content">
    <!-- Date Range -->
    <section class="filter-section">
      <h3>Date Range</h3>
      <div class="date-range-inputs">
        <input type="date" id="filter-date-start" />
        <span>to</span>
        <input type="date" id="filter-date-end" />
      </div>
      <input
        type="range"
        id="filter-date-slider"
        min="0"
        max="100"
        class="date-slider"
      />
      <div class="date-presets">
        <button data-days="7">7d</button>
        <button data-days="30">30d</button>
        <button data-days="90">90d</button>
        <button data-days="all">All</button>
      </div>
    </section>

    <!-- Entity Types -->
    <section class="filter-section">
      <h3>Entity Types</h3>
      <div class="checkbox-grid">
        <label><input type="checkbox" data-type="Org" checked /> Org</label>
        <label><input type="checkbox" data-type="Person" checked /> Person</label>
        <label><input type="checkbox" data-type="Model" checked /> Model</label>
        <label><input type="checkbox" data-type="Tool" checked /> Tool</label>
        <label><input type="checkbox" data-type="Dataset" checked /> Dataset</label>
        <label><input type="checkbox" data-type="Benchmark" checked /> Benchmark</label>
        <label><input type="checkbox" data-type="Paper" checked /> Paper</label>
        <label><input type="checkbox" data-type="Repo" checked /> Repo</label>
        <label><input type="checkbox" data-type="Tech" checked /> Tech</label>
        <label><input type="checkbox" data-type="Topic" checked /> Topic</label>
        <label><input type="checkbox" data-type="Document" /> Document</label>
        <label><input type="checkbox" data-type="Event" checked /> Event</label>
        <label><input type="checkbox" data-type="Location" checked /> Location</label>
        <label><input type="checkbox" data-type="Other" checked /> Other</label>
      </div>
      <div class="type-actions">
        <button id="select-all-types">All</button>
        <button id="select-no-types">None</button>
      </div>
    </section>

    <!-- Relationship Kind -->
    <section class="filter-section">
      <h3>Relationship Kind</h3>
      <label><input type="checkbox" data-kind="asserted" checked /> Asserted</label>
      <label><input type="checkbox" data-kind="inferred" checked /> Inferred</label>
      <label><input type="checkbox" data-kind="hypothesis" /> Hypothesis</label>
    </section>

    <!-- Confidence Threshold -->
    <section class="filter-section">
      <h3>Minimum Confidence</h3>
      <input
        type="range"
        id="filter-confidence"
        min="0"
        max="100"
        value="30"
      />
      <span id="confidence-value">30%</span>
    </section>

    <!-- View Presets -->
    <section class="filter-section">
      <h3>Show</h3>
      <label>
        <input type="radio" name="view-preset" value="all" />
        All nodes
      </label>
      <label>
        <input type="radio" name="view-preset" value="trending" checked />
        Trending only
      </label>
      <label>
        <input type="radio" name="view-preset" value="new" />
        New (last 7 days)
      </label>
    </section>

    <!-- Actions -->
    <section class="filter-actions">
      <button id="apply-filters" class="primary">Apply Filters</button>
      <button id="reset-filters">Reset All</button>
    </section>
  </div>
</aside>
```

---

## GraphFilter Class

```javascript
class GraphFilter {
  constructor(cy) {
    this.cy = cy;
    this.filters = {
      dateStart: null,
      dateEnd: null,
      types: new Set([
        'Org', 'Person', 'Model', 'Tool', 'Dataset', 'Benchmark',
        'Paper', 'Repo', 'Tech', 'Topic', 'Event', 'Location', 'Other'
      ]),
      kinds: new Set(['asserted', 'inferred']),
      minConfidence: 0.3,
      viewPreset: 'trending'
    };
  }

  setDateRange(start, end) {
    this.filters.dateStart = start;
    this.filters.dateEnd = end;
  }

  toggleType(type, enabled) {
    if (enabled) {
      this.filters.types.add(type);
    } else {
      this.filters.types.delete(type);
    }
  }

  toggleKind(kind, enabled) {
    if (enabled) {
      this.filters.kinds.add(kind);
    } else {
      this.filters.kinds.delete(kind);
    }
  }

  setMinConfidence(value) {
    this.filters.minConfidence = value;
  }

  setViewPreset(preset) {
    this.filters.viewPreset = preset;
  }

  apply() {
    const { cy, filters } = this;

    // Start with all elements visible
    cy.elements().removeClass('filtered-out');

    // Filter nodes
    cy.nodes().forEach(node => {
      let visible = true;

      // Type filter
      if (!filters.types.has(node.data('type'))) {
        visible = false;
      }

      // Date filter (by lastSeen)
      if (visible && filters.dateStart) {
        const lastSeen = node.data('lastSeen');
        if (lastSeen && lastSeen < filters.dateStart) {
          visible = false;
        }
      }

      if (visible && filters.dateEnd) {
        const firstSeen = node.data('firstSeen');
        if (firstSeen && firstSeen > filters.dateEnd) {
          visible = false;
        }
      }

      // View preset filters
      if (visible && filters.viewPreset === 'trending') {
        const velocity = node.data('velocity') || 0;
        if (velocity < 0.1) {
          visible = false;
        }
      }

      if (visible && filters.viewPreset === 'new') {
        const firstSeen = node.data('firstSeen');
        if (!isNewNode(firstSeen)) {
          visible = false;
        }
      }

      if (!visible) {
        node.addClass('filtered-out');
      }
    });

    // Filter edges
    cy.edges().forEach(edge => {
      let visible = true;

      // Kind filter
      if (!filters.kinds.has(edge.data('kind'))) {
        visible = false;
      }

      // Confidence filter
      const confidence = edge.data('confidence') || 0;
      if (confidence < filters.minConfidence) {
        visible = false;
      }

      // Hide edges connected to hidden nodes
      if (edge.source().hasClass('filtered-out') ||
          edge.target().hasClass('filtered-out')) {
        visible = false;
      }

      if (!visible) {
        edge.addClass('filtered-out');
      }
    });

    // Update visibility
    cy.elements('.filtered-out').hide();
    cy.elements().not('.filtered-out').show();

    // Update label visibility for remaining nodes
    updateLabelVisibility(cy);

    // Emit event for UI updates
    this.cy.emit('filtersApplied', this.getActiveFilterCount());
  }

  reset() {
    this.filters = {
      dateStart: null,
      dateEnd: null,
      types: new Set([
        'Org', 'Person', 'Model', 'Tool', 'Dataset', 'Benchmark',
        'Paper', 'Repo', 'Tech', 'Topic', 'Event', 'Location', 'Other'
      ]),
      kinds: new Set(['asserted', 'inferred']),
      minConfidence: 0.3,
      viewPreset: 'trending'
    };
    this.apply();
  }

  getActiveFilterCount() {
    let count = 0;
    if (this.filters.dateStart || this.filters.dateEnd) count++;
    if (this.filters.types.size < 14) count++;
    if (this.filters.kinds.size < 3) count++;
    if (this.filters.minConfidence > 0) count++;
    if (this.filters.viewPreset !== 'all') count++;
    return count;
  }
}
```

---

## Filter Panel Styles

```css
.filtered-out {
  display: none !important;
}

#filter-panel {
  position: absolute;
  right: 0;
  top: 60px;  /* Below toolbar */
  bottom: 0;
  width: 280px;
  background: white;
  border-left: 1px solid #E5E7EB;
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.05);
  transition: transform 0.3s ease;
  z-index: 100;
  overflow-y: auto;
}

#filter-panel.collapsed {
  transform: translateX(240px);
}

#filter-panel.collapsed .panel-content {
  opacity: 0;
  pointer-events: none;
}

.panel-toggle {
  position: absolute;
  left: -40px;
  top: 10px;
  width: 40px;
  height: 40px;
  background: white;
  border: 1px solid #E5E7EB;
  border-right: none;
  border-radius: 8px 0 0 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.panel-content {
  padding: 16px;
  transition: opacity 0.2s ease;
}

.filter-section {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #F3F4F6;
}

.filter-section h3 {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  color: #6B7280;
  margin-bottom: 12px;
}

.checkbox-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.checkbox-grid label {
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.date-presets {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.date-presets button {
  flex: 1;
  padding: 6px;
  font-size: 12px;
  border: 1px solid #E5E7EB;
  background: white;
  border-radius: 4px;
  cursor: pointer;
}

.date-presets button:hover {
  background: #F9FAFB;
}

.date-presets button.active {
  background: #3B82F6;
  color: white;
  border-color: #3B82F6;
}

.filter-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.filter-actions button {
  flex: 1;
  padding: 10px;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
}

.filter-actions button.primary {
  background: #3B82F6;
  color: white;
  border: none;
}

.filter-actions button:not(.primary) {
  background: white;
  border: 1px solid #E5E7EB;
}
```
