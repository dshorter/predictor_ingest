# Progressive Disclosure

The four-level information hierarchy: Overview → Explore → Detail → Evidence.

---

## Level 1: Overview (Default State)

The initial view shows a high-level summary optimized for trend detection:

```javascript
function showOverview(cy) {
  // Load trending view by default
  loadGraphView('trending');

  // Apply default filters
  const filter = new GraphFilter(cy);
  filter.setViewPreset('trending');
  filter.apply();

  // Run layout
  runLayout(cy, 'preset');  // V2: use preset if positions available

  // Fit to view
  cy.fit(50);

  // Update label visibility
  updateLabelVisibility(cy);
}
```

---

## Level 2: Explore (Click to Expand)

When user clicks a node, reveal its neighborhood:

```javascript
function expandNeighbors(node, depth = 1) {
  const cy = node.cy();

  // Get neighbors up to specified depth
  let toExpand = node;
  for (let i = 0; i < depth; i++) {
    toExpand = toExpand.closedNeighborhood();
  }

  // If neighbors are hidden (filtered out), show them
  toExpand.removeClass('filtered-out').show();

  // Animate expansion
  const originalPositions = {};
  toExpand.nodes().forEach(n => {
    originalPositions[n.id()] = n.position();

    // New nodes start at the clicked node's position
    if (!n.visible() || n.hasClass('just-expanded')) {
      n.position(node.position());
      n.addClass('just-expanded');
    }
  });

  // Run local layout for just the expanded nodes
  toExpand.layout({
    name: 'concentric',
    concentric: function(n) {
      return n.id() === node.id() ? 10 : 1;
    },
    minNodeSpacing: 50,
    animate: true,
    animationDuration: 300
  }).run();

  // Update label visibility
  updateLabelVisibility(cy);

  // Fit to show expanded neighborhood
  cy.animate({
    fit: {
      eles: toExpand,
      padding: 50
    },
    duration: 300
  });
}
```

---

## Level 3: Deep Dive (Detail Panel)

Full node metadata in a side panel:

```html
<aside id="detail-panel" class="panel hidden">
  <button class="panel-close">×</button>

  <div id="detail-content">
    <!-- Populated dynamically -->
  </div>
</aside>
```

```javascript
function openNodeDetailPanel(node) {
  const data = node.data();
  const panel = document.getElementById('detail-panel');
  const content = document.getElementById('detail-content');

  content.innerHTML = `
    <header class="detail-header">
      <span class="detail-type type-${data.type.toLowerCase()}">${data.type}</span>
      <h2 class="detail-title">${escapeHtml(data.label)}</h2>
      ${data.aliases && data.aliases.length > 0 ? `
        <div class="detail-aliases">
          Also known as: ${data.aliases.map(a => escapeHtml(a)).join(', ')}
        </div>
      ` : ''}
    </header>

    <section class="detail-section">
      <h3>Timeline</h3>
      <div class="detail-timeline">
        <div class="timeline-item">
          <span class="timeline-label">First seen</span>
          <span class="timeline-value">${formatDate(data.firstSeen)}</span>
          <span class="timeline-relative">${daysAgo(data.firstSeen)}</span>
        </div>
        <div class="timeline-item">
          <span class="timeline-label">Last seen</span>
          <span class="timeline-value">${formatDate(data.lastSeen)}</span>
          <span class="timeline-relative">${daysAgo(data.lastSeen)}</span>
        </div>
      </div>
    </section>

    <section class="detail-section">
      <h3>Activity</h3>
      <div class="detail-stats">
        <div class="stat">
          <span class="stat-value">${data.mentionCount7d || 0}</span>
          <span class="stat-label">Mentions (7d)</span>
        </div>
        <div class="stat">
          <span class="stat-value">${data.mentionCount30d || 0}</span>
          <span class="stat-label">Mentions (30d)</span>
        </div>
        <div class="stat">
          <span class="stat-value">${node.degree()}</span>
          <span class="stat-label">Connections</span>
        </div>
        <div class="stat ${data.velocity > 0.5 ? 'trending' : ''}">
          <span class="stat-value">${formatVelocity(data.velocity)}</span>
          <span class="stat-label">Velocity</span>
        </div>
      </div>
    </section>

    <section class="detail-section">
      <h3>Relationships (${node.connectedEdges().length})</h3>
      <div class="detail-relationships">
        ${renderRelationshipList(node)}
      </div>
    </section>

    <section class="detail-section">
      <h3>Source Documents</h3>
      <div class="detail-documents">
        ${renderDocumentList(node)}
      </div>
    </section>

    <footer class="detail-footer">
      <button class="btn" onclick="expandNeighbors(cy.$('#${data.id}'))">
        Expand neighbors
      </button>
      <button class="btn" onclick="zoomToNode(cy.$('#${data.id}'))">
        Center view
      </button>
    </footer>
  `;

  panel.classList.remove('hidden');
}

function renderRelationshipList(node) {
  const edges = node.connectedEdges();

  // Group by relationship type
  const grouped = {};
  edges.forEach(edge => {
    const rel = edge.data('rel');
    if (!grouped[rel]) grouped[rel] = [];
    grouped[rel].push(edge);
  });

  let html = '';
  for (const [rel, relEdges] of Object.entries(grouped)) {
    html += `
      <div class="relationship-group">
        <div class="relationship-type">${formatRelation(rel)}</div>
        <ul class="relationship-list">
          ${relEdges.slice(0, 5).map(edge => {
            const other = edge.source().id() === node.id()
              ? edge.target()
              : edge.source();
            const direction = edge.source().id() === node.id() ? '→' : '←';
            return `
              <li class="relationship-item" data-edge-id="${edge.id()}">
                <span class="rel-direction">${direction}</span>
                <span class="rel-target" onclick="selectNode('${other.id()}')">${other.data('label')}</span>
                <span class="rel-confidence">${(edge.data('confidence') * 100).toFixed(0)}%</span>
                <span class="rel-kind kind-${edge.data('kind')}">${edge.data('kind')}</span>
              </li>
            `;
          }).join('')}
          ${relEdges.length > 5 ? `
            <li class="relationship-more">
              +${relEdges.length - 5} more
            </li>
          ` : ''}
        </ul>
      </div>
    `;
  }

  return html;
}
```

---

## Level 4: Evidence Panel (Edge Detail)

Full provenance for a relationship:

```javascript
function openEvidencePanel(edge) {
  const data = edge.data();
  const sourceNode = edge.source();
  const targetNode = edge.target();

  const panel = document.getElementById('evidence-panel');
  const content = document.getElementById('evidence-content');

  // Fetch full evidence (may need async call if not embedded in edge data)
  const evidence = data.evidence || [];

  content.innerHTML = `
    <header class="evidence-header">
      <div class="evidence-relationship">
        <span class="evidence-entity">${sourceNode.data('label')}</span>
        <span class="evidence-rel">${formatRelation(data.rel)}</span>
        <span class="evidence-entity">${targetNode.data('label')}</span>
      </div>
      <div class="evidence-meta">
        <span class="evidence-kind kind-${data.kind}">${capitalize(data.kind)}</span>
        <span class="evidence-confidence">
          ${(data.confidence * 100).toFixed(0)}% confidence
        </span>
        <span class="evidence-date">
          First asserted: ${formatDate(data.firstSeen)}
        </span>
      </div>
    </header>

    <section class="evidence-section">
      <h3>Evidence (${evidence.length} source${evidence.length === 1 ? '' : 's'})</h3>
      <ul class="evidence-list">
        ${evidence.map((ev, idx) => `
          <li class="evidence-item">
            <div class="evidence-source">
              <span class="evidence-icon">📄</span>
              <span class="evidence-title">${escapeHtml(ev.title || 'Untitled')}</span>
            </div>
            <div class="evidence-pub">
              ${ev.source || 'Unknown source'} · ${formatDate(ev.published)}
            </div>
            <blockquote class="evidence-snippet">
              "${escapeHtml(ev.snippet)}"
            </blockquote>
            <a href="${ev.url}" target="_blank" class="evidence-link">
              View document →
            </a>
          </li>
        `).join('')}
      </ul>
      ${evidence.length === 0 ? `
        <p class="evidence-empty">
          No evidence snippets available for this relationship.
          This may be an inferred or hypothesis edge.
        </p>
      ` : ''}
    </section>

    <footer class="evidence-footer">
      <button class="btn" onclick="selectNode('${sourceNode.id()}')">
        View ${sourceNode.data('label')}
      </button>
      <button class="btn" onclick="selectNode('${targetNode.id()}')">
        View ${targetNode.data('label')}
      </button>
    </footer>
  `;

  panel.classList.remove('hidden');
}
```
