/**
 * Graph Filter
 *
 * Handles filtering of nodes and edges based on user criteria.
 * See docs/ux/search-filter.md for specification.
 */

class GraphFilter {
  constructor(cy) {
    this.cy = cy;
    this.filters = {
      dateStart: null,
      dateEnd: null,
      types: new Set([
        'Org', 'Person', 'Model', 'Tool', 'Dataset', 'Benchmark',
        'Paper', 'Repo', 'Tech', 'Topic', 'Event', 'Program', 'Location', 'Document', 'Other'
      ]),
      kinds: new Set(['asserted', 'inferred']),
      minConfidence: 0.3,
      viewPreset: 'trending'
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
      kinds: new Set(['asserted', 'inferred']),
      minConfidence: 0.3,
      viewPreset: 'trending'
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
 * Populate type filter checkboxes dynamically
 * @param {Object} cy - Cytoscape instance
 */
function populateTypeFilters(cy) {
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
}

/**
 * Initialize filter panel UI
 */
function initializeFilterPanel(filter) {
  // Populate type filters dynamically
  populateTypeFilters(filter.cy);

  // Date presets
  const datePresets = document.querySelectorAll('.date-presets button');
  datePresets.forEach(btn => {
    btn.addEventListener('click', () => {
      datePresets.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const days = btn.dataset.days;
      if (days === 'all') {
        filter.setDateRange(null, null);
      } else {
        const end = today();
        const start = new Date();
        start.setDate(start.getDate() - parseInt(days));
        filter.setDateRange(start.toISOString().split('T')[0], end);
      }
    });
  });

  // Entity type checkboxes
  const typeCheckboxes = document.querySelectorAll('[data-type]');
  typeCheckboxes.forEach(checkbox => {
    checkbox.addEventListener('change', () => {
      filter.toggleType(checkbox.dataset.type, checkbox.checked);
    });
  });

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
    // Repopulate type filters after reset
    populateTypeFilters(filter.cy);
    syncFilterUI(filter);
  });

  // Filter panel toggle
  document.getElementById('btn-filter')?.addEventListener('click', () => {
    const panel = document.getElementById('filter-panel');
    if (panel) {
      panel.classList.toggle('collapsed');
      document.getElementById('cy')?.classList.toggle('panel-right-open');
    }
  });
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
