/**
 * Touch Gesture Handling
 *
 * Bottom sheet swipe gestures and long-press detection.
 * Coordinates with Cytoscape's built-in touch handling.
 */

/**
 * Bottom sheet touch controller.
 * Manages swipe-to-snap behavior on the bottom sheet element.
 *
 * @param {HTMLElement} sheet - The bottom sheet container
 * @param {Object} options - Configuration
 * @param {Function} options.onStateChange - Called with new state: 'hidden'|'peek'|'half'|'full'
 */
function BottomSheetTouch(sheet, options) {
  this.sheet = sheet;
  this.onStateChange = options.onStateChange || function() {};

  // Snap points as fraction of sheet height visible (0 = hidden, 1 = full)
  this.snapPoints = {
    hidden: 0,
    peek: 100,     // px from bottom
    half: null,    // computed from CSS var
    full: null     // computed from CSS var
  };

  this.currentState = 'hidden';
  this.startY = 0;
  this.startTranslateY = 0;
  this.isDragging = false;
  this.dragVelocity = 0;
  this.lastY = 0;
  this.lastTime = 0;

  this._onTouchStart = this._handleTouchStart.bind(this);
  this._onTouchMove = this._handleTouchMove.bind(this);
  this._onTouchEnd = this._handleTouchEnd.bind(this);

  this._computeSnapPoints();
  this._bind();
}

BottomSheetTouch.prototype._computeSnapPoints = function() {
  var sheetHeight = this.sheet.offsetHeight || window.innerHeight * 0.85;
  this.snapPoints.half = window.innerHeight * 0.4;
  this.snapPoints.full = sheetHeight;
};

BottomSheetTouch.prototype._bind = function() {
  var handle = this.sheet.querySelector('.bottom-sheet-handle');
  if (handle) {
    handle.addEventListener('touchstart', this._onTouchStart, { passive: false });
  }
  // Also allow dragging from the top of the content area
  this.sheet.addEventListener('touchstart', this._onTouchStart, { passive: false });
};

BottomSheetTouch.prototype.destroy = function() {
  var handle = this.sheet.querySelector('.bottom-sheet-handle');
  if (handle) {
    handle.removeEventListener('touchstart', this._onTouchStart);
  }
  this.sheet.removeEventListener('touchstart', this._onTouchStart);
  document.removeEventListener('touchmove', this._onTouchMove);
  document.removeEventListener('touchend', this._onTouchEnd);
};

BottomSheetTouch.prototype._handleTouchStart = function(e) {
  // Only drag from the handle, or from content when scrolled to top
  var handle = this.sheet.querySelector('.bottom-sheet-handle');
  var content = this.sheet.querySelector('.bottom-sheet-content');
  var isHandle = handle && handle.contains(e.target);
  var isContentAtTop = content && content.scrollTop <= 0;

  if (!isHandle && !isContentAtTop) return;
  // If content is scrollable and not at top, let native scroll handle it
  if (!isHandle && content && content.scrollTop > 0) return;

  this._computeSnapPoints();

  var touch = e.touches[0];
  this.startY = touch.clientY;
  this.lastY = touch.clientY;
  this.lastTime = Date.now();
  this.isDragging = false;
  this.dragVelocity = 0;

  // Get current translateY from the computed transform
  var transform = window.getComputedStyle(this.sheet).transform;
  if (transform && transform !== 'none') {
    var matrix = transform.match(/matrix.*\((.+)\)/);
    if (matrix) {
      var values = matrix[1].split(', ');
      this.startTranslateY = parseFloat(values[values.length - 1]);
    } else {
      this.startTranslateY = 0;
    }
  } else {
    this.startTranslateY = this.sheet.offsetHeight; // fully hidden
  }

  document.addEventListener('touchmove', this._onTouchMove, { passive: false });
  document.addEventListener('touchend', this._onTouchEnd, { passive: true });
};

BottomSheetTouch.prototype._handleTouchMove = function(e) {
  var touch = e.touches[0];
  var deltaY = touch.clientY - this.startY;

  // Start dragging after 5px threshold
  if (!this.isDragging && Math.abs(deltaY) > 5) {
    this.isDragging = true;
    this.sheet.classList.add('dragging');
  }

  if (!this.isDragging) return;

  e.preventDefault();

  // Calculate velocity for momentum
  var now = Date.now();
  var dt = now - this.lastTime;
  if (dt > 0) {
    this.dragVelocity = (touch.clientY - this.lastY) / dt;
  }
  this.lastY = touch.clientY;
  this.lastTime = now;

  // Apply transform — sheet height is the maximum translateY (fully hidden)
  var sheetHeight = this.sheet.offsetHeight;
  var newTranslateY = this.startTranslateY + deltaY;
  // Clamp: don't go above full (15% from top) or below hidden
  var minTranslate = sheetHeight * 0.15;  // full state offset
  newTranslateY = Math.max(minTranslate, Math.min(sheetHeight, newTranslateY));

  this.sheet.style.transform = 'translateY(' + newTranslateY + 'px)';
};

BottomSheetTouch.prototype._handleTouchEnd = function() {
  document.removeEventListener('touchmove', this._onTouchMove);
  document.removeEventListener('touchend', this._onTouchEnd);

  this.sheet.classList.remove('dragging');

  if (!this.isDragging) return;
  this.isDragging = false;

  // Get current position
  var transform = window.getComputedStyle(this.sheet).transform;
  var currentTranslateY = this.sheet.offsetHeight;
  if (transform && transform !== 'none') {
    var matrix = transform.match(/matrix.*\((.+)\)/);
    if (matrix) {
      var values = matrix[1].split(', ');
      currentTranslateY = parseFloat(values[values.length - 1]);
    }
  }

  var sheetHeight = this.sheet.offsetHeight;
  var visibleHeight = sheetHeight - currentTranslateY;

  // Factor in velocity for momentum-based snapping
  // Positive velocity = dragging down (toward hidden)
  // Negative velocity = dragging up (toward full)
  var momentumBoost = this.dragVelocity * 150;
  var adjustedVisible = visibleHeight - momentumBoost;

  // Determine closest snap point
  var peekH = this.snapPoints.peek;
  var halfH = this.snapPoints.half;
  var fullH = this.snapPoints.full;

  var newState;

  // Strong downward flick = dismiss
  if (this.dragVelocity > 0.5) {
    newState = 'hidden';
  }
  // Strong upward flick = full
  else if (this.dragVelocity < -0.5) {
    newState = 'full';
  }
  // Otherwise snap to nearest
  else if (adjustedVisible < peekH / 2) {
    newState = 'hidden';
  } else if (adjustedVisible < (peekH + halfH) / 2) {
    newState = 'peek';
  } else if (adjustedVisible < (halfH + fullH) / 2) {
    newState = 'half';
  } else {
    newState = 'full';
  }

  // Clear inline transform and let CSS classes handle it
  this.sheet.style.transform = '';
  this.setState(newState);
};

/**
 * Set bottom sheet state programmatically.
 * @param {string} state - 'hidden'|'peek'|'half'|'full'
 */
BottomSheetTouch.prototype.setState = function(state) {
  this.sheet.classList.remove('peek', 'half', 'full');

  if (state !== 'hidden') {
    this.sheet.classList.add(state);
  }

  this.currentState = state;
  this.onStateChange(state);
};

/**
 * Get current state.
 * @returns {string}
 */
BottomSheetTouch.prototype.getState = function() {
  return this.currentState;
};


/**
 * Long-press detector for Cytoscape nodes.
 *
 * @param {Object} cy - Cytoscape instance
 * @param {Object} options
 * @param {number} options.duration - Long-press duration in ms (default 500)
 * @param {Function} options.onLongPress - Called with (node, position)
 */
function LongPressDetector(cy, options) {
  this.cy = cy;
  this.duration = (options && options.duration) || 500;
  this.onLongPress = (options && options.onLongPress) || function() {};
  this._timer = null;
  this._startPos = null;
  this._bind();
}

LongPressDetector.prototype._bind = function() {
  var self = this;

  this.cy.on('tapstart', 'node', function(e) {
    self._startPos = e.position;
    self._timer = setTimeout(function() {
      // Verify finger hasn't moved too far (10px threshold)
      self.onLongPress(e.target, e.renderedPosition);
    }, self.duration);
  });

  this.cy.on('tapdrag', 'node', function(e) {
    if (self._timer && self._startPos) {
      var dx = e.position.x - self._startPos.x;
      var dy = e.position.y - self._startPos.y;
      if (Math.sqrt(dx * dx + dy * dy) > 10) {
        clearTimeout(self._timer);
        self._timer = null;
      }
    }
  });

  this.cy.on('tapend', function() {
    if (self._timer) {
      clearTimeout(self._timer);
      self._timer = null;
    }
  });
};

LongPressDetector.prototype.destroy = function() {
  if (this._timer) {
    clearTimeout(this._timer);
  }
};
