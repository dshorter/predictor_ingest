/**
 * Tooltip Management
 *
 * Hover tooltips for nodes and edges.
 * See docs/ux/interaction.md for specification.
 */

const TOOLTIP_DELAY = 400; // ms before showing
const TOOLTIP_OFFSET = 12; // px from cursor

let tooltipTimeout = null;
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
    hideTooltip(tooltip);
  });

  // Edge hover - add .hover class for styling + show tooltip
  cy.on('mouseover', 'edge', (e) => {
    clearTooltipTimeout();
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
    hideTooltip(tooltip);
  });

  // Hide on pan/zoom
  cy.on('pan zoom', () => {
    clearTooltipTimeout();
    hideTooltip(tooltip);
  });
}

/**
 * Clear pending tooltip timeout
 */
function clearTooltipTimeout() {
  if (tooltipTimeout) {
    clearTimeout(tooltipTimeout);
    tooltipTimeout = null;
  }
  currentTooltipTarget = null;
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
          <span>${formatVelocity(data.velocity, data.mentionCount7d, data.mentionCount30d)}</span>
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

  // Adjust if tooltip would overflow viewport
  if (x + tooltipRect.width > window.innerWidth - 10) {
    x = containerRect.left + position.x - tooltipRect.width - TOOLTIP_OFFSET;
  }
  if (y + tooltipRect.height > window.innerHeight - 10) {
    y = containerRect.top + position.y - tooltipRect.height - TOOLTIP_OFFSET;
  }

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
