# Toolbar and Global Controls

Toolbar layout and global control implementation.

---

## Toolbar Layout

```html
<header id="toolbar">
  <div class="toolbar-left">
    <h1 class="app-title">AI Trend Graph</h1>

    <div class="toolbar-group">
      <label>View:</label>
      <select id="view-selector">
        <option value="trending">Trending</option>
        <option value="claims">Claims</option>
        <option value="mentions">Mentions</option>
        <option value="dependencies">Dependencies</option>
      </select>
    </div>

    <div class="toolbar-group">
      <label>Date:</label>
      <select id="date-selector">
        <!-- Populated dynamically -->
      </select>
    </div>
  </div>

  <div class="toolbar-center">
    <div id="search-container">
      <input type="text" id="search-input" placeholder="Search nodes..." />
      <span id="search-results-count"></span>
    </div>
  </div>

  <div class="toolbar-right">
    <button id="btn-zoom-in" title="Zoom in">+</button>
    <button id="btn-zoom-out" title="Zoom out">−</button>
    <button id="btn-fit" title="Fit to view">⊡</button>
    <button id="btn-layout" title="Re-run layout">↻</button>
    <button id="btn-fullscreen" title="Fullscreen">⛶</button>
  </div>
</header>
```

---

## Toolbar Implementation

```javascript
// View selector
document.getElementById('view-selector').addEventListener('change', async (e) => {
  const view = e.target.value;
  const date = document.getElementById('date-selector').value;
  await loadGraphView(view, date);
});

// Date selector
document.getElementById('date-selector').addEventListener('change', async (e) => {
  const date = e.target.value;
  const view = document.getElementById('view-selector').value;
  await loadGraphView(view, date);
});

// Zoom controls
document.getElementById('btn-zoom-in').addEventListener('click', () => {
  cy.zoom({
    level: cy.zoom() * 1.2,
    renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 }
  });
});

document.getElementById('btn-zoom-out').addEventListener('click', () => {
  cy.zoom({
    level: cy.zoom() / 1.2,
    renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 }
  });
});

// Fit to view
document.getElementById('btn-fit').addEventListener('click', () => {
  cy.animate({
    fit: { padding: 30 },
    duration: 300
  });
});

// Re-run layout
document.getElementById('btn-layout').addEventListener('click', () => {
  runForceDirectedLayout(cy);
});

// Fullscreen
document.getElementById('btn-fullscreen').addEventListener('click', () => {
  const container = document.getElementById('app');
  if (document.fullscreenElement) {
    document.exitFullscreen();
  } else {
    container.requestFullscreen();
  }
});
```

---

## Toolbar Styling

```css
#toolbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 60px;
  background: white;
  border-bottom: 1px solid #E5E7EB;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  z-index: 200;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.toolbar-center {
  flex: 1;
  max-width: 400px;
  margin: 0 24px;
}

.app-title {
  font-size: 18px;
  font-weight: 600;
  color: #1F2937;
  margin: 0;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-group label {
  font-size: 13px;
  color: #6B7280;
}

.toolbar-group select {
  padding: 6px 12px;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  font-size: 13px;
  background: white;
  cursor: pointer;
}

#search-container {
  position: relative;
  width: 100%;
}

#search-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  font-size: 14px;
}

#search-input:focus {
  outline: none;
  border-color: #3B82F6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

#search-results-count {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 12px;
  color: #6B7280;
}

.toolbar-right button {
  width: 36px;
  height: 36px;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  background: white;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.toolbar-right button:hover {
  background: #F9FAFB;
}

.toolbar-right button:active {
  background: #F3F4F6;
}
```
