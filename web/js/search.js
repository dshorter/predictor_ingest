/**
 * Search Functionality
 *
 * Handles searching and highlighting nodes in the graph.
 * See docs/ux/search-filter.md for specification.
 */

let searchTimeout;

/**
 * Initialize search functionality
 */
function initializeSearch(cy) {
  const searchInput = document.getElementById('search-input');
  const searchClear = document.getElementById('search-clear');
  const resultsCount = document.getElementById('search-results-count');

  if (!searchInput) return;

  // Debounced search on input
  searchInput.addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      performSearch(cy, e.target.value);
    }, 150);
  });

  // Enter key: zoom to results
  searchInput.addEventListener('keydown', (e) => {
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
      searchInput.value = '';
      performSearch(cy, '');
      searchInput.blur();
    }
  });

  // Clear button
  if (searchClear) {
    searchClear.addEventListener('click', () => {
      searchInput.value = '';
      performSearch(cy, '');
      searchInput.focus();
    });
  }
}

/**
 * Perform search and update graph
 */
function performSearch(cy, query) {
  const trimmedQuery = query.trim().toLowerCase();
  const resultsCount = document.getElementById('search-results-count');
  const searchClear = document.getElementById('search-clear');

  if (!trimmedQuery) {
    // Clear search
    cy.elements().removeClass('search-match').removeClass('dimmed');
    if (resultsCount) resultsCount.textContent = '';
    if (searchClear) searchClear.hidden = true;
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
    if (resultsCount) {
      resultsCount.textContent = `${matches.length} node${matches.length === 1 ? '' : 's'}`;
    }

    // Announce to screen readers
    announceToScreenReader(`Found ${matches.length} matching nodes`);
  } else {
    cy.elements().addClass('dimmed');
    if (resultsCount) resultsCount.textContent = 'No matches';
    announceToScreenReader('No matching nodes found');
  }

  // Show clear button
  if (searchClear) searchClear.hidden = false;
}

/**
 * Clear search and reset graph
 */
function clearSearch(cy) {
  const searchInput = document.getElementById('search-input');
  if (searchInput) {
    searchInput.value = '';
  }
  performSearch(cy, '');
}
