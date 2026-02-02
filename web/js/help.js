/**
 * Help Panel Management
 *
 * Handles the in-app help documentation panel with tabbed content and accordion sections.
 */

/**
 * Initialize help panel functionality
 */
function initializeHelp() {
  const panel = document.getElementById('help-panel');
  const closeBtn = panel?.querySelector('.panel-close');
  const tabs = document.querySelectorAll('.help-tab');
  const tabPanes = document.querySelectorAll('.help-tab-pane');

  if (!panel) {
    console.warn('Help panel not found in DOM');
    return;
  }

  // Populate content
  populateHelpContent();

  // Close button
  closeBtn?.addEventListener('click', () => {
    closeHelpPanel();
  });

  // Tab switching
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetId = tab.dataset.tab;
      switchTab(targetId);
    });
  });

  // Close on Escape key (when help panel is visible)
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !panel.classList.contains('hidden')) {
      closeHelpPanel();
      e.stopPropagation(); // Prevent other Escape handlers
    }
  });

  // Close on click outside (optional)
  document.addEventListener('click', (e) => {
    if (!panel.classList.contains('hidden') &&
        !panel.contains(e.target) &&
        !e.target.closest('#btn-help')) {
      closeHelpPanel();
    }
  });

  console.log('Help panel initialized');
}

/**
 * Populate help content from HelpContent object
 */
function populateHelpContent() {
  // Quick Start tab
  const quickStartPane = document.getElementById('help-quick-start');
  if (quickStartPane && HelpContent.quickStart) {
    quickStartPane.innerHTML = HelpContent.quickStart;
  }

  // Topics tab (accordion)
  const topicsPane = document.getElementById('help-topics');
  if (topicsPane && HelpContent.topics) {
    const accordion = document.createElement('div');
    accordion.className = 'help-accordion';

    // Create a details element for each topic
    for (const [key, topic] of Object.entries(HelpContent.topics)) {
      const details = document.createElement('details');
      details.id = `help-topic-${key}`;

      const summary = document.createElement('summary');
      summary.textContent = topic.title;

      const content = document.createElement('div');
      content.className = 'help-accordion-content';
      content.innerHTML = topic.content;

      details.appendChild(summary);
      details.appendChild(content);
      accordion.appendChild(details);
    }

    topicsPane.appendChild(accordion);
  }

  // Add click handler for internal links that open specific topics
  document.querySelectorAll('.help-content a[href^="#"]').forEach(link => {
    link.addEventListener('click', (e) => {
      const href = link.getAttribute('href');
      if (href && href !== '#') {
        e.preventDefault();
        // Extract topic ID from onclick attribute if present
        const onclick = link.getAttribute('onclick');
        if (onclick && onclick.includes('openTopicSection')) {
          const match = onclick.match(/openTopicSection\('([^']+)'\)/);
          if (match) {
            openTopicSection(match[1]);
          }
        }
      }
    });
  });
}

/**
 * Switch to a specific tab
 */
function switchTab(tabId) {
  const tabs = document.querySelectorAll('.help-tab');
  const tabPanes = document.querySelectorAll('.help-tab-pane');

  tabs.forEach(tab => {
    if (tab.dataset.tab === tabId) {
      tab.classList.add('active');
    } else {
      tab.classList.remove('active');
    }
  });

  tabPanes.forEach(pane => {
    if (pane.id === `help-${tabId}`) {
      pane.classList.add('active');
    } else {
      pane.classList.remove('active');
    }
  });

  // Announce to screen readers
  announceToScreenReader(`Switched to ${tabId} tab`);
}

/**
 * Open help panel
 */
function openHelpPanel(options = {}) {
  const panel = document.getElementById('help-panel');
  const detailPanel = document.getElementById('detail-panel');

  if (!panel) return;

  // Close detail panel if open (mutually exclusive)
  if (detailPanel && !detailPanel.classList.contains('hidden')) {
    detailPanel.classList.add('hidden');
  }

  // Show help panel
  panel.classList.remove('hidden');

  // Update cy container
  updateCyContainer();

  // Context-sensitive opening
  if (options.section) {
    openTopicSection(options.section);
  } else if (options.tab) {
    switchTab(options.tab);
  }

  // Announce to screen readers
  announceToScreenReader('Help panel opened');
}

/**
 * Close help panel
 */
function closeHelpPanel() {
  const panel = document.getElementById('help-panel');
  if (!panel) return;

  panel.classList.add('hidden');

  // Update cy container
  updateCyContainer();

  // Announce to screen readers
  announceToScreenReader('Help panel closed');
}

/**
 * Toggle help panel open/closed
 */
function toggleHelpPanel() {
  const panel = document.getElementById('help-panel');
  if (!panel) return;

  if (panel.classList.contains('hidden')) {
    openHelpPanel();
  } else {
    closeHelpPanel();
  }
}

/**
 * Open a specific topic section in the Topics tab
 */
function openTopicSection(topicKey) {
  // Switch to Topics tab
  switchTab('topics');

  // Open the specific details element
  const details = document.getElementById(`help-topic-${topicKey}`);
  if (details) {
    details.open = true;

    // Scroll to the section
    setTimeout(() => {
      details.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  }
}

/**
 * Context-sensitive help
 * Opens help with relevant section based on current UI state
 */
function openContextSensitiveHelp() {
  const cy = window.cy;
  if (!cy) {
    openHelpPanel();
    return;
  }

  // If a node is selected, open "Reading the Graph" or "Interacting with Nodes"
  const selectedNodes = cy.$(':selected').nodes();
  if (selectedNodes.length > 0) {
    openHelpPanel({ tab: 'topics', section: 'nodes' });
    return;
  }

  // If filter panel is open, open "Filtering" section
  const filterPanel = document.getElementById('filter-panel');
  if (filterPanel && !filterPanel.classList.contains('collapsed')) {
    openHelpPanel({ tab: 'topics', section: 'filtering' });
    return;
  }

  // If search is active, open "Search" section
  const searchInput = document.getElementById('search-input');
  if (searchInput && searchInput.value.trim()) {
    openHelpPanel({ tab: 'topics', section: 'search' });
    return;
  }

  // Default: open Quick Start
  openHelpPanel({ tab: 'quick-start' });
}
