/**
 * Mobile Panel Management
 *
 * Bottom sheet detail/evidence panels and full-screen filter modal.
 * Reuses GraphFilter logic from shared filter.js; rebuilds the UI for mobile.
 */

/* ============================================================
   Bottom Sheet — Node Detail
   ============================================================ */

/**
 * Open bottom sheet with node detail content.
 * @param {Object} node - Cytoscape node
 */
function openNodeDetailSheet(node) {
  var data = node.data();
  var content = document.getElementById('bottom-sheet-content');
  if (!content) return;

  content.innerHTML =
    '<header class="sheet-header">' +
      '<div>' +
        '<span class="badge badge-type-' + data.type.toLowerCase() + '">' + data.type + '</span>' +
        '<h2 class="sheet-title">' + escapeHtml(data.label) + '</h2>' +
        (data.aliases && data.aliases.length > 0
          ? '<p class="sheet-subtitle">Also: ' + data.aliases.map(function(a) { return escapeHtml(a); }).join(', ') + '</p>'
          : '') +
      '</div>' +
    '</header>' +

    '<section>' +
      '<div class="stats-grid">' +
        '<div class="stat-card">' +
          '<div class="stat-value">' + (data.mentionCount7d || 0) + '</div>' +
          '<div class="stat-label">Mentions (7d)</div>' +
        '</div>' +
        '<div class="stat-card">' +
          '<div class="stat-value">' + (data.mentionCount30d || 0) + '</div>' +
          '<div class="stat-label">Mentions (30d)</div>' +
        '</div>' +
        '<div class="stat-card">' +
          '<div class="stat-value">' + node.degree() + '</div>' +
          '<div class="stat-label">Connections</div>' +
        '</div>' +
        '<div class="stat-card">' +
          '<div class="stat-value">' + formatVelocity(data.velocity) + '</div>' +
          '<div class="stat-label">Velocity</div>' +
        '</div>' +
      '</div>' +
    '</section>' +

    '<section>' +
      '<div class="relationship-group-title">TIMELINE</div>' +
      '<div style="display:flex;justify-content:space-between;font-size:var(--text-sm);padding:var(--space-2) 0">' +
        '<span style="color:var(--color-text-secondary)">First seen</span>' +
        '<span>' + formatDate(data.firstSeen) + '</span>' +
      '</div>' +
      '<div style="display:flex;justify-content:space-between;font-size:var(--text-sm);padding:var(--space-2) 0">' +
        '<span style="color:var(--color-text-secondary)">Last seen</span>' +
        '<span>' + formatDate(data.lastSeen) + '</span>' +
      '</div>' +
    '</section>' +

    '<section>' +
      '<div class="relationship-group-title">RELATIONSHIPS (' + node.connectedEdges().length + ')</div>' +
      renderMobileRelationshipList(node) +
    '</section>' +

    '<div class="sheet-actions">' +
      '<button class="btn" onclick="mobileExpandNeighbors(\'' + data.id + '\')">Expand</button>' +
      '<button class="btn" onclick="mobileCenterNode(\'' + data.id + '\')">Center</button>' +
    '</div>';

  // Show sheet in half-expanded state
  if (window.MobileApp && window.MobileApp.sheetTouch) {
    window.MobileApp.sheetTouch.setState('half');
  }
}

/**
 * Open bottom sheet with edge evidence content.
 * @param {Object} edge - Cytoscape edge
 */
function openEdgeEvidenceSheet(edge) {
  var data = edge.data();
  var sourceNode = edge.source();
  var targetNode = edge.target();
  var content = document.getElementById('bottom-sheet-content');
  if (!content) return;

  var evidence = data.evidence || [];

  content.innerHTML =
    '<header class="sheet-header">' +
      '<div>' +
        '<div style="display:flex;align-items:center;gap:var(--space-2);flex-wrap:wrap">' +
          '<span>' + escapeHtml(sourceNode.data('label')) + '</span>' +
          '<span style="color:var(--color-text-tertiary)">&rarr;</span>' +
          '<span>' + escapeHtml(targetNode.data('label')) + '</span>' +
        '</div>' +
        '<div style="display:flex;align-items:center;gap:var(--space-2);margin-top:var(--space-2)">' +
          '<span class="badge badge-kind-' + data.kind + '">' + capitalize(data.kind) + '</span>' +
          '<span style="font-size:var(--text-sm);color:var(--color-text-secondary)">' + formatRelation(data.rel) + '</span>' +
          '<span style="font-size:var(--text-sm);color:var(--color-text-secondary)">' + (data.confidence * 100).toFixed(0) + '% confidence</span>' +
        '</div>' +
      '</div>' +
    '</header>' +

    '<section class="evidence-accordion">' +
      '<div class="relationship-group-title">EVIDENCE (' + evidence.length + ' source' + (evidence.length === 1 ? '' : 's') + ')</div>' +
      (evidence.length > 0
        ? evidence.map(function(ev, i) {
            var title = ev.title || formatDocId(ev.docId) || 'Untitled';
            var source = ev.source || extractDomain(ev.url) || 'Unknown source';
            return (
              '<div class="evidence-item' + (i === 0 ? ' open' : '') + '">' +
                '<button class="evidence-toggle" onclick="toggleEvidence(this)">' +
                  '<span>' + escapeHtml(title) + '</span>' +
                  '<span class="arrow">&#x25B6;</span>' +
                '</button>' +
                '<div class="evidence-body">' +
                  '<div class="evidence-meta">' + escapeHtml(source) + ' &middot; ' + formatDate(ev.published) + '</div>' +
                  '<div class="evidence-snippet">&ldquo;' + escapeHtml(ev.snippet) + '&rdquo;</div>' +
                  (ev.url
                    ? '<a href="' + ev.url + '" target="_blank" rel="noopener" class="evidence-link">View document &rarr;</a>'
                    : '') +
                '</div>' +
              '</div>'
            );
          }).join('')
        : '<p style="font-size:var(--text-sm);color:var(--color-text-tertiary)">No evidence snippets available.</p>'
      ) +
    '</section>' +

    '<div class="sheet-actions">' +
      '<button class="btn" onclick="mobileSelectNode(\'' + sourceNode.id() + '\')">' + truncateLabel(sourceNode.data('label'), 12) + '</button>' +
      '<button class="btn" onclick="mobileSelectNode(\'' + targetNode.id() + '\')">' + truncateLabel(targetNode.data('label'), 12) + '</button>' +
    '</div>';

  if (window.MobileApp && window.MobileApp.sheetTouch) {
    window.MobileApp.sheetTouch.setState('half');
  }
}

/**
 * Render relationship list for mobile bottom sheet.
 */
function renderMobileRelationshipList(node) {
  var edges = node.connectedEdges();
  if (edges.length === 0) {
    return '<p style="font-size:var(--text-sm);color:var(--color-text-tertiary)">No relationships</p>';
  }

  var grouped = {};
  edges.forEach(function(edge) {
    var rel = edge.data('rel');
    if (!grouped[rel]) grouped[rel] = [];
    grouped[rel].push(edge);
  });

  var html = '';
  for (var rel in grouped) {
    var relEdges = grouped[rel];
    html += '<div class="relationship-group">';
    html += '<div class="relationship-group-title">' + formatRelation(rel) + '</div>';

    var shown = relEdges.slice(0, 5);
    shown.forEach(function(edge) {
      var other = edge.source().id() === node.id() ? edge.target() : edge.source();
      var direction = edge.source().id() === node.id() ? '&rarr;' : '&larr;';
      html +=
        '<div class="relationship-item" onclick="mobileSelectNode(\'' + other.id() + '\')">' +
          '<span class="relationship-direction">' + direction + '</span>' +
          '<span class="relationship-label">' + escapeHtml(other.data('label')) + '</span>' +
          '<span class="badge badge-kind-' + edge.data('kind') + '" style="font-size:var(--text-xs)">' + edge.data('kind') + '</span>' +
        '</div>';
    });

    if (relEdges.length > 5) {
      html += '<div style="font-size:var(--text-xs);color:var(--color-text-tertiary);padding:var(--space-1) var(--space-2)">+' + (relEdges.length - 5) + ' more</div>';
    }

    html += '</div>';
  }

  return html;
}

/**
 * Toggle evidence accordion item.
 */
function toggleEvidence(button) {
  var item = button.closest('.evidence-item');
  if (item) {
    item.classList.toggle('open');
  }
}

/**
 * Dismiss the bottom sheet.
 */
function dismissBottomSheet() {
  if (window.MobileApp && window.MobileApp.sheetTouch) {
    window.MobileApp.sheetTouch.setState('hidden');
  }
}

/* ============================================================
   Mobile navigation helpers (called from onclick in sheet HTML)
   ============================================================ */

function mobileSelectNode(nodeId) {
  if (!window.cy) return;
  var node = window.cy.getElementById(nodeId);
  if (node.length > 0) {
    window.cy.elements().unselect();
    node.select();
    clearNeighborhoodHighlight(window.cy);
    highlightNeighborhood(window.cy, node);
    window.cy.animate({ center: { eles: node }, duration: 300 });
    openNodeDetailSheet(node);
  }
}

function mobileExpandNeighbors(nodeId) {
  if (!window.cy) return;
  var node = window.cy.getElementById(nodeId);
  if (node.length > 0) {
    var neighborhood = node.closedNeighborhood();
    neighborhood.removeClass('filtered-out').show();
    window.cy.animate({
      fit: { eles: neighborhood, padding: 50 },
      duration: 300
    });
    if (typeof updateLabelVisibility === 'function') {
      updateLabelVisibility(window.cy);
    }
  }
}

function mobileCenterNode(nodeId) {
  if (!window.cy) return;
  var node = window.cy.getElementById(nodeId);
  if (node.length > 0) {
    window.cy.animate({
      center: { eles: node },
      zoom: 2,
      duration: 300
    });
  }
}

/* ============================================================
   Filter Modal
   ============================================================ */

/**
 * Initialize the mobile filter modal UI.
 * Wires up the same GraphFilter logic with mobile-specific UI.
 * @param {GraphFilter} filter - The shared filter instance
 */
function initializeMobileFilterPanel(filter) {
  // Populate type filters dynamically
  populateTypeFilters(filter.cy);

  // --- Data source radios ---
  var dataSourceRadios = document.querySelectorAll('input[name="data-source"]');
  var sampleTierList = document.getElementById('sample-tier-list');

  dataSourceRadios.forEach(function(radio) {
    radio.addEventListener('change', function() {
      var isSample = radio.value === 'sample';
      if (sampleTierList) {
        sampleTierList.classList.toggle('hidden', !isSample);
      }
      var tier = isSample ? AppState.currentTier : null;
      switchDataSource(radio.value, tier);
    });
  });

  // --- Sample tier radios ---
  var tierRadios = document.querySelectorAll('input[name="sample-tier"]');
  tierRadios.forEach(function(radio) {
    radio.addEventListener('change', function() {
      switchDataSource('sample', radio.value);
    });
  });

  // --- Date presets in filter modal ---
  var filterPresets = document.querySelectorAll('.filter-modal .date-presets button');
  filterPresets.forEach(function(btn) {
    btn.addEventListener('click', function() {
      var days = btn.dataset.days;
      AppState.activePresetDays = (days === 'all') ? null : parseInt(days);
      // Sync active class
      filterPresets.forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
    });
  });

  // Entity type checkboxes
  var typeCheckboxes = document.querySelectorAll('[data-type]');
  typeCheckboxes.forEach(function(checkbox) {
    checkbox.addEventListener('change', function() {
      filter.toggleType(checkbox.dataset.type, checkbox.checked);
    });
  });

  // Select all/none
  var selectAll = document.getElementById('select-all-types');
  if (selectAll) {
    selectAll.addEventListener('click', function() {
      document.querySelectorAll('[data-type]:not([disabled])').forEach(function(cb) {
        cb.checked = true;
        filter.toggleType(cb.dataset.type, true);
      });
    });
  }

  var selectNone = document.getElementById('select-no-types');
  if (selectNone) {
    selectNone.addEventListener('click', function() {
      document.querySelectorAll('[data-type]:not([disabled])').forEach(function(cb) {
        cb.checked = false;
        filter.toggleType(cb.dataset.type, false);
      });
    });
  }

  // Kind checkboxes
  var kindCheckboxes = document.querySelectorAll('[data-kind]');
  kindCheckboxes.forEach(function(checkbox) {
    checkbox.addEventListener('change', function() {
      filter.toggleKind(checkbox.dataset.kind, checkbox.checked);
    });
  });

  // Confidence slider
  var confidenceSlider = document.getElementById('filter-confidence');
  var confidenceValue = document.getElementById('confidence-value');
  if (confidenceSlider && confidenceValue) {
    confidenceSlider.addEventListener('input', function() {
      var value = parseInt(confidenceSlider.value) / 100;
      confidenceValue.textContent = confidenceSlider.value + '%';
      filter.setMinConfidence(value);
    });
  }

  // Apply button — apply filters and close modal
  var applyBtn = document.getElementById('apply-filters');
  if (applyBtn) {
    applyBtn.addEventListener('click', function() {
      applyDateFilterFromAnchor();
      filter.apply();
      updateStatsDisplay(window.cy);
      closeMobileFilterModal();
    });
  }

  // Reset button
  var resetBtn = document.getElementById('reset-filters');
  if (resetBtn) {
    resetBtn.addEventListener('click', function() {
      filter.reset();
      // Restore view-appropriate preset so trending velocity filter
      // only applies on the trending view, not on claims/mentions/etc.
      var currentView = AppState.currentView || 'trending';
      filter.setViewPreset(currentView === 'trending' ? 'trending' : 'all');
      AppState.anchorDate = today();
      AppState.activePresetDays = 30;
      var dateInput = document.getElementById('date-anchor');
      if (dateInput) dateInput.value = AppState.anchorDate;
      applyDateFilterFromAnchor();
      populateTypeFilters(filter.cy);
      syncFilterUI(filter);
      updateStatsDisplay(window.cy);
    });
  }

  // Close button
  var closeBtn = document.getElementById('filter-modal-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', closeMobileFilterModal);
  }
}

/**
 * Open the filter modal.
 */
function openMobileFilterModal() {
  var modal = document.getElementById('filter-modal');
  if (modal) {
    modal.classList.remove('hidden');
    // Trigger reflow, then animate in
    modal.offsetHeight;
    modal.classList.add('visible');
  }
}

/**
 * Close the filter modal.
 */
function closeMobileFilterModal() {
  var modal = document.getElementById('filter-modal');
  if (modal) {
    modal.classList.remove('visible');
    // Re-add hidden after transition
    setTimeout(function() {
      if (!modal.classList.contains('visible')) {
        modal.classList.add('hidden');
      }
    }, 300);
  }
}
