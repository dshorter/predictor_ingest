/**
 * Utility Functions
 *
 * Helper functions used across the application.
 */

/**
 * Format a date string for display
 * @param {string} dateStr - ISO date string
 * @returns {string} Formatted date
 */
function formatDate(dateStr) {
  if (!dateStr) return 'Unknown';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
}

/**
 * Calculate days between two dates
 * @param {string} dateStr - ISO date string
 * @param {Date} [toDate=new Date()] - End date
 * @returns {number} Number of days
 */
function daysBetween(dateStr, toDate = new Date()) {
  if (!dateStr) return Infinity;
  const from = new Date(dateStr);
  const diff = toDate - from;
  return Math.floor(diff / (1000 * 60 * 60 * 24));
}

/**
 * Get "X days ago" string
 * @param {string} dateStr - ISO date string
 * @returns {string}
 */
function daysAgo(dateStr) {
  const days = daysBetween(dateStr);
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  if (days < 30) return `${Math.floor(days / 7)} weeks ago`;
  if (days < 365) return `${Math.floor(days / 30)} months ago`;
  return `${Math.floor(days / 365)} years ago`;
}

/**
 * Check if a node is new (first seen within 7 days)
 * @param {string} firstSeenDate - ISO date string
 * @returns {boolean}
 */
function isNewNode(firstSeenDate) {
  return daysBetween(firstSeenDate) <= 7;
}

/**
 * Truncate a label to max length
 * @param {string} label - Text to truncate
 * @param {number} maxLength - Maximum characters
 * @returns {string}
 */
function truncateLabel(label, maxLength) {
  if (!label) return '';
  if (label.length <= maxLength) return label;
  return label.substring(0, maxLength - 1) + '…';
}

/**
 * Escape HTML entities
 * @param {string} str - String to escape
 * @returns {string}
 */
function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Capitalize first letter
 * @param {string} str
 * @returns {string}
 */
function capitalize(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

/**
 * Format relation name (SNAKE_CASE to Title Case)
 * @param {string} rel - Relation name
 * @returns {string}
 */
function formatRelation(rel) {
  if (!rel) return '';
  return rel.split('_').map(word =>
    word.charAt(0) + word.slice(1).toLowerCase()
  ).join(' ');
}

/**
 * Format velocity as percentage
 * @param {number} velocity
 * @returns {string}
 */
function formatVelocity(velocity) {
  if (velocity === undefined || velocity === null) return '0%';
  return `${(velocity * 100).toFixed(0)}%`;
}

/**
 * Debounce a function
 * @param {Function} fn - Function to debounce
 * @param {number} delay - Delay in ms
 * @returns {Function}
 */
function debounce(fn, delay) {
  let timeoutId;
  return function (...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * Get today's date as ISO string (date only)
 * @returns {string}
 */
function today() {
  return new Date().toISOString().split('T')[0];
}

/**
 * Announce message to screen readers
 * @param {string} message
 */
function announceToScreenReader(message) {
  const announcer = document.getElementById('sr-announcer');
  if (announcer) {
    announcer.textContent = message;
  }
}

/**
 * Show loading overlay
 */
function showLoading() {
  const overlay = document.getElementById('loading-overlay');
  if (overlay) overlay.classList.remove('hidden');
}

/**
 * Hide loading overlay
 */
function hideLoading() {
  const overlay = document.getElementById('loading-overlay');
  if (overlay) overlay.classList.add('hidden');
}

/**
 * Show error overlay
 * @param {string} message - Error message to display
 */
function showError(message) {
  const overlay = document.getElementById('error-overlay');
  const messageEl = document.getElementById('error-message');
  if (overlay && messageEl) {
    messageEl.textContent = message;
    overlay.classList.remove('hidden');
  }
}

/**
 * Hide error overlay
 */
function hideError() {
  const overlay = document.getElementById('error-overlay');
  if (overlay) overlay.classList.add('hidden');
}
