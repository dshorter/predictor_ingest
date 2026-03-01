/**
 * Graph Filter
 *
 * Handles filtering of nodes and edges based on user criteria.
 * See docs/ux/search-filter.md for specification.
 */

class GraphFilter {
  constructor(cy) {
    this.cy = cy;
    // Derive initial viewPreset from the active view so the velocity
    // filter is only applied when actually on the trending view.
    const initialView = (typeof AppState !== 'undefined' && AppState.currentView) || 'trending';
    this.filters = {
      dateStart: null,
      dateEnd: null,
      types: new Set([
        'Org', 'Person', 'Model', 'Tool', 'Dataset', 'Benchmark',
        'Paper', 'Repo', 'Tech', 'Topic', 'Event', 'Program', 'Location', 'Document', 'Other'
      ]),
      // 'hypothesis' edges are intentionally OFF by default. They are
      // speculative claims not backed by direct evidence; showing them
      // by default would clutter the base graph with low-signal noise.
      // Users can enable them via the Relationship Kind filter panel.
      kinds: new Set(['asserted', 'inferred']),
      minConfidence: 0.3,
      viewPreset: initialView === 'trending' ? 'trending' : 'all'
    };
  }

  /**
   * Set date range filter
   */
  setDateRange(start, end) {
    this.filters.dateStart = start;
    this.filters.dateEnd = end;
  }

  /**
   * Toggle an entity type
   */
  toggleType(type, enabled) {
    if (enabled) {
      this.filters.types.add(type);
    } else {
      this.filters.types.delete(type);
    }
  }

  /**
   * Set all types at once
   */
  setTypes(types) {
    this.filters.types = new Set(types);
  }

  /**
   * Toggle a relationship kind
   */
  toggleKind(kind, enabled) {
    if (enabled) {
      this.filters.kinds.add(kind);
    } else {
      this.filters.kinds.delete(kind);
    }
  }

  /**
   * Set minimum confidence threshold
   */
  setMinConfidence(value) {
    this.filters.minConfidence = value;
  }

  /**
   * Set view preset (all, trending, new)
   */
  setViewPreset(preset) {
    this.filters.viewPreset = preset;
  }

  /**
   * Apply all filters to the graph
   */
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
    if (typeof updateLabelVisibility === 'function') {
      updateLabelVisibility(cy);
    }

    // Emit event for UI updates
    this.cy.emit('filtersApplied', { count: this.getActiveFilterCount() });
  }

  /**
   * Reset all filters to defaults
   */
  reset() {
    this.filters = {
      dateStart: null,
      dateEnd: null,
      types: new Set([
        'Org', 'Person', 'Model', 'Tool', 'Dataset', 'Benchmark',
        'Paper', 'Repo', 'Tech', 'Topic', 'Event', 'Program', 'Location', 'Document', 'Other'
      ]),
      // 'hypothesis' intentionally excluded — see constructor comment.
      kinds: new Set(['asserted', 'inferred']),
      minConfidence: 0.3,
      viewPreset: 'all'  // safe default; caller sets view-specific preset
    };
    this.apply();
  }

  /**
   * Get count of active (non-default) filters
   */
  getActiveFilterCount() {
    let count = 0;
    if (this.filters.dateStart || this.filters.dateEnd) count++;
    if (this.filters.types.size < 15) count++;  // Less than all 15 types
    if (this.filters.kinds.size < 3) count++;
    if (this.filters.minConfidence > 0) count++;
    if (this.filters.viewPreset !== 'all') count++;
    return count;
  }

  /**
   * Get current filter state (for UI sync)
   */
  getState() {
    return { ...this.filters };
  }
}

/**
 * Populate type filter checkboxes dynamically.
 * Re-generates the HTML and re-attaches change listeners so counts
 * stay in sync whenever the underlying graph data changes.
 *
 * @param {Object} cy - Cytoscape instance
 * @param {GraphFilter} [filter] - optional filter instance for re-binding
 */
function populateTypeFilters(cy, filter) {
  const typeFiltersContainer = document.getElementById('type-filters');
  if (!typeFiltersContainer) return;

  // All 15 entity types from the specification
  const allTypes = [
    'Org', 'Person', 'Model', 'Tool', 'Dataset',
    'Benchmark', 'Paper', 'Repo', 'Tech', 'Topic',
    'Event', 'Program', 'Location', 'Document', 'Other'
  ];

  // Get types that actually exist in the current graph
  const existingTypes = new Set();
  cy.nodes().forEach(node => {
    existingTypes.add(node.data('type'));
  });

  // Generate checkboxes for all types
  typeFiltersContainer.innerHTML = allTypes.map(type => {
    const disabled = !existingTypes.has(type);
    const count = disabled ? 0 : cy.nodes(`[type="${type}"]`).length;

    return `
      <label class="checkbox-label ${disabled ? 'text-gray-400' : ''}">
        <input
          type="checkbox"
          data-type="${type}"
          ${disabled ? 'disabled' : 'checked'}
        />
        ${type} ${count > 0 ? `(${count})` : ''}
      </label>
    `;
  }).join('');

  // Re-attach change listeners after regenerating the HTML
  if (filter) {
    typeFiltersContainer.querySelectorAll('[data-type]').forEach(cb => {
      cb.addEventListener('change', () => {
        filter.toggleType(cb.dataset.type, cb.checked);
      });
    });
  }
}

/**
 * Initialize filter panel UI
 */
function initializeFilterPanel(filter) {
  // Populate type filters dynamically (pass filter for event binding)
  populateTypeFilters(filter.cy, filter);

  // --- Data source radios ---
  const dataSourceRadios = document.querySelectorAll('input[name="data-source"]');
  const sampleTierList = document.getElementById('sample-tier-list');

  dataSourceRadios.forEach(radio => {
    radio.addEventListener('change', async () => {
      const isSample = radio.value === 'sample';

      // Show/hide sample tier list
      if (sampleTierList) {
        sampleTierList.classList.toggle('hidden', !isSample);
      }

      // Switch data source
      const tier = isSample ? AppState.currentTier : null;
      await switchDataSource(radio.value, tier);
    });
  });

  // --- Sample tier radios ---
  const tierRadios = document.querySelectorAll('input[name="sample-tier"]');
  tierRadios.forEach(radio => {
    radio.addEventListener('change', async () => {
      await switchDataSource('sample', radio.value);
    });
  });

  // --- Date presets (calculate from anchor) ---
  const datePresets = document.querySelectorAll('.date-presets button');
  datePresets.forEach(btn => {
    btn.addEventListener('click', () => {
      const days = btn.dataset.days;
      AppState.activePresetDays = (days === 'all') ? null : parseInt(days);
      applyDateFilterFromAnchor();
    });
  });

  // Entity type checkbox change listeners are now attached inside
  // populateTypeFilters() so they survive HTML regeneration.

  // Select all/none types
  document.getElementById('select-all-types')?.addEventListener('click', () => {
    const checkboxes = document.querySelectorAll('[data-type]:not([disabled])');
    checkboxes.forEach(cb => {
      cb.checked = true;
      filter.toggleType(cb.dataset.type, true);
    });
  });

  document.getElementById('select-no-types')?.addEventListener('click', () => {
    const checkboxes = document.querySelectorAll('[data-type]:not([disabled])');
    checkboxes.forEach(cb => {
      cb.checked = false;
      filter.toggleType(cb.dataset.type, false);
    });
  });

  // Kind checkboxes
  const kindCheckboxes = document.querySelectorAll('[data-kind]');
  kindCheckboxes.forEach(checkbox => {
    checkbox.addEventListener('change', () => {
      filter.toggleKind(checkbox.dataset.kind, checkbox.checked);
    });
  });

  // Confidence slider
  const confidenceSlider = document.getElementById('filter-confidence');
  const confidenceValue = document.getElementById('confidence-value');
  if (confidenceSlider && confidenceValue) {
    confidenceSlider.addEventListener('input', () => {
      const value = parseInt(confidenceSlider.value) / 100;
      confidenceValue.textContent = `${confidenceSlider.value}%`;
      filter.setMinConfidence(value);
    });
  }

  // Apply button
  document.getElementById('apply-filters')?.addEventListener('click', () => {
    filter.apply();
  });

  // Reset button
  document.getElementById('reset-filters')?.addEventListener('click', () => {
    filter.reset();

    // Restore view-appropriate preset so trending velocity filter
    // only applies on the trending view, not on claims/mentions/etc.
    const currentView = AppState.currentView || 'trending';
    filter.setViewPreset(currentView === 'trending' ? 'trending' : 'all');

    // Reset anchor to today and preset to 30d
    AppState.anchorDate = today();
    AppState.activePresetDays = 30;
    const dateInput = document.getElementById('date-anchor');
    if (dateInput) dateInput.value = AppState.anchorDate;
    applyDateFilterFromAnchor();

    // Repopulate type filters after reset (pass filter for event re-binding)
    populateTypeFilters(filter.cy, filter);
    syncFilterUI(filter);
  });

  // NOTE: Filter panel toggle is handled in app.js to avoid duplicate handlers
}

/**
 * Sync filter UI with filter state
 */
function syncFilterUI(filter) {
  const state = filter.getState();

  // Sync type checkboxes
  document.querySelectorAll('[data-type]').forEach(cb => {
    cb.checked = state.types.has(cb.dataset.type);
  });

  // Sync kind checkboxes
  document.querySelectorAll('[data-kind]').forEach(cb => {
    cb.checked = state.kinds.has(cb.dataset.kind);
  });

  // Sync confidence slider
  const slider = document.getElementById('filter-confidence');
  const value = document.getElementById('confidence-value');
  if (slider && value) {
    slider.value = Math.round(state.minConfidence * 100);
    value.textContent = `${slider.value}%`;
  }
}

/**
 * Initialize filters (wrapper function called by app.js)
 * @param {Object} cy - Cytoscape instance
 * @returns {GraphFilter} The filter instance
 */
function initializeFilters(cy) {
  const filter = new GraphFilter(cy);
  initializeFilterPanel(filter);
  return filter;
}
