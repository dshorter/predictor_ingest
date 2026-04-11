/**
 * Tooltip Management
 *
 * Hover tooltips for nodes and edges.
 * See docs/ux/interaction.md for specification.
 */

const TOOLTIP_DELAY = 400; // ms before showing
const TOOLTIP_OFFSET = 12; // px from cursor
const TOOLTIP_HIDE_DELAY = 200; // ms grace period before hiding (lets cursor reach tooltip)

let tooltipTimeout = null;
let tooltipHideTimeout = null;
let currentTooltipTarget = null;

/**
 * Initialize tooltip functionality
 */
function initializeTooltips(cy) {
  const tooltip = document.getElementById('tooltip');
  if (!tooltip) return;

  // Node hover - add .hover class for styling + show tooltip
  cy.on('mouseover', 'node', (e) => {
    clearTooltipTimeout();
    clearHideTimeout();
    currentTooltipTarget = e.target;
    e.target.addClass('hover');

    tooltipTimeout = setTimeout(() => {
      if (currentTooltipTarget === e.target) {
        showNodeTooltip(e.target, e.renderedPosition, tooltip);
      }
    }, TOOLTIP_DELAY);
  });

  cy.on('mouseout', 'node', (e) => {
    e.target.removeClass('hover');
    clearTooltipTimeout();
    scheduleHideTooltip(tooltip);
  });

  // Edge hover - add .hover class for styling + show tooltip
  cy.on('mouseover', 'edge', (e) => {
    clearTooltipTimeout();
    clearHideTimeout();
    currentTooltipTarget = e.target;
    e.target.addClass('hover');

    tooltipTimeout = setTimeout(() => {
      if (currentTooltipTarget === e.target) {
        showEdgeTooltip(e.target, e.renderedPosition, tooltip);
      }
    }, TOOLTIP_DELAY);
  });

  cy.on('mouseout', 'edge', (e) => {
    e.target.removeClass('hover');
    clearTooltipTimeout();
    scheduleHideTooltip(tooltip);
  });

  // Hide on pan/zoom
  cy.on('pan zoom', () => {
    clearTooltipTimeout();
    clearHideTimeout();
    hideTooltip(tooltip);
  });

  // Keep tooltip visible while cursor is over it
  tooltip.addEventListener('mouseenter', () => {
    clearHideTimeout();
  });

  tooltip.addEventListener('mouseleave', () => {
    hideTooltip(tooltip);
  });
}

/**
 * Clear pending tooltip show timeout
 */
function clearTooltipTimeout() {
  if (tooltipTimeout) {
    clearTimeout(tooltipTimeout);
    tooltipTimeout = null;
  }
  currentTooltipTarget = null;
}

/**
 * Clear pending tooltip hide timeout
 */
function clearHideTimeout() {
  if (tooltipHideTimeout) {
    clearTimeout(tooltipHideTimeout);
    tooltipHideTimeout = null;
  }
}

/**
 * Schedule tooltip hide after a grace period (lets cursor travel to tooltip)
 */
function scheduleHideTooltip(tooltip) {
  clearHideTimeout();
  tooltipHideTimeout = setTimeout(() => {
    hideTooltip(tooltip);
  }, TOOLTIP_HIDE_DELAY);
}

/**
 * Show tooltip for a node
 */
function showNodeTooltip(node, position, tooltip) {
  const data = node.data();

  const content = `
    <div class="tooltip-header">
      <span class="badge badge-type-${data.type.toLowerCase()}">${data.type}</span>
      <strong>${escapeHtml(data.label)}</strong>
    </div>
    <div class="tooltip-body">
      <div class="tooltip-row">
        <span class="tooltip-label">Connections:</span>
        <span>${node.degree()}</span>
      </div>
      ${data.velocity !== undefined ? `
        <div class="tooltip-row">
          <span class="tooltip-label">Velocity:</span>
          <span>${formatVelocity(data.velocity)}</span>
        </div>
      ` : ''}
      ${data.lastSeen ? `
        <div class="tooltip-row">
          <span class="tooltip-label">Last seen:</span>
          <span>${formatDate(data.lastSeen)}</span>
        </div>
      ` : ''}
    </div>
    <div class="tooltip-hint">Click for details</div>
  `;

  positionAndShowTooltip(tooltip, content, position);
}

/**
 * Show tooltip for an edge
 */
function showEdgeTooltip(edge, position, tooltip) {
  const data = edge.data();
  const sourceLabel = edge.source().data('label');
  const targetLabel = edge.target().data('label');

  const content = `
    <div class="tooltip-header">
      <span class="badge badge-kind-${data.kind}">${capitalize(data.kind)}</span>
      <strong>${formatRelation(data.rel)}</strong>
    </div>
    <div class="tooltip-body">
      <div class="tooltip-row">
        <span>${escapeHtml(truncateLabel(sourceLabel, 20))}</span>
        <span class="text-gray-400">→</span>
        <span>${escapeHtml(truncateLabel(targetLabel, 20))}</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-label">Confidence:</span>
        <span>${(data.confidence * 100).toFixed(0)}%</span>
      </div>
      ${data.evidence && data.evidence.length > 0 ? `
        <div class="tooltip-row">
          <span class="tooltip-label">Evidence:</span>
          <span>${data.evidence.length} source${data.evidence.length === 1 ? '' : 's'}</span>
        </div>
      ` : ''}
    </div>
    <div class="tooltip-hint">Click to view evidence</div>
  `;

  positionAndShowTooltip(tooltip, content, position);
}

/**
 * Return pixel widths consumed by open side panels so tooltips don't slide under them.
 */
function getOpenPanelOffsets() {
  const detailPanel = document.getElementById('detail-panel');
  const filterPanel = document.getElementById('filter-panel');
  const left = (detailPanel && !detailPanel.classList.contains('hidden'))
    ? (detailPanel.offsetWidth || 0) : 0;
  const right = (filterPanel && !filterPanel.classList.contains('collapsed'))
    ? (filterPanel.offsetWidth || 0) : 0;
  return { left, right };
}

/**
 * Position tooltip and make visible
 */
function positionAndShowTooltip(tooltip, content, position) {
  tooltip.innerHTML = content;
  tooltip.classList.add('visible');

  // Get container bounds
  const container = document.getElementById('cy');
  const containerRect = container.getBoundingClientRect();

  // Calculate position
  let x = containerRect.left + position.x + TOOLTIP_OFFSET;
  let y = containerRect.top + position.y + TOOLTIP_OFFSET;

  // Get tooltip dimensions after content is set
  const tooltipRect = tooltip.getBoundingClientRect();

  // Account for open side panels when computing available space
  const { left: panelLeft, right: panelRight } = getOpenPanelOffsets();
  const rightBound = window.innerWidth - panelRight - 10;
  const leftBound = panelLeft + 10;

  // Flip to left of cursor if tooltip would overflow right bound
  if (x + tooltipRect.width > rightBound) {
    x = containerRect.left + position.x - tooltipRect.width - TOOLTIP_OFFSET;
  }
  // Flip above cursor if tooltip would overflow bottom
  if (y + tooltipRect.height > window.innerHeight - 10) {
    y = containerRect.top + position.y - tooltipRect.height - TOOLTIP_OFFSET;
  }
  // Clamp so tooltip never slides under the left detail panel
  x = Math.max(leftBound, x);

  tooltip.style.left = `${x}px`;
  tooltip.style.top = `${y}px`;
}

/**
 * Hide tooltip
 */
function hideTooltip(tooltip) {
  if (tooltip) {
    tooltip.classList.remove('visible');
  }
}
