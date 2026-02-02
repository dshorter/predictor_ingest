/**
 * Help Panel Content
 *
 * All help text for the in-app documentation panel.
 * Organized by tab and section.
 */

const HelpContent = {
  // Quick Start Tab - Single-page onboarding
  quickStart: `
    <div class="help-section">
      <h3>What am I looking at?</h3>
      <p>
        This is a <strong>knowledge graph of AI trends</strong> extracted from news articles,
        research papers, and blog posts. Nodes represent entities (organizations, models, tools, etc.)
        and edges represent relationships between them.
      </p>
      <ul>
        <li><strong>Nodes</strong> = entities (OpenAI, GPT-5, datasets, papers, etc.)</li>
        <li><strong>Edges</strong> = relationships (launched, uses, trained on, etc.)</li>
        <li><strong>Node size</strong> = activity level (mentions and velocity)</li>
        <li><strong>Node color</strong> = entity type (blue = Org, violet = Model, etc.)</li>
      </ul>
    </div>

    <div class="help-section">
      <h3>Basic Navigation</h3>
      <table class="help-table">
        <tr>
          <td class="help-action">Pan the graph</td>
          <td>Click + drag on background</td>
        </tr>
        <tr>
          <td class="help-action">Zoom</td>
          <td>Scroll wheel</td>
        </tr>
        <tr>
          <td class="help-action">Select a node</td>
          <td>Click any node</td>
        </tr>
        <tr>
          <td class="help-action">Deselect</td>
          <td>Click background or press <kbd>Escape</kbd></td>
        </tr>
        <tr>
          <td class="help-action">Fit to view</td>
          <td>Click ⊡ button or double-click background</td>
        </tr>
      </table>
    </div>

    <div class="help-section">
      <h3>Try It Now</h3>
      <div class="help-prompt">
        <p>👆 <strong>Click any node</strong> to see its details and highlight its neighborhood</p>
        <p>🔍 <strong>Type a name</strong> in the search box to find entities</p>
        <p>📊 <strong>Switch to Claims view</strong> using the View dropdown to see entity-to-entity relationships</p>
      </div>
    </div>

    <div class="help-section">
      <h3>Keyboard Shortcuts</h3>
      <table class="help-table">
        <tr>
          <td><kbd>/</kbd></td>
          <td>Focus search box</td>
        </tr>
        <tr>
          <td><kbd>Escape</kbd></td>
          <td>Clear selection / close panel</td>
        </tr>
        <tr>
          <td><kbd>Arrow keys</kbd></td>
          <td>Navigate between connected nodes</td>
        </tr>
        <tr>
          <td><kbd>?</kbd></td>
          <td>Toggle this help panel</td>
        </tr>
        <tr>
          <td><kbd>+</kbd> / <kbd>-</kbd></td>
          <td>Zoom in / out</td>
        </tr>
        <tr>
          <td><kbd>0</kbd></td>
          <td>Fit graph to view</td>
        </tr>
      </table>
    </div>
  `,

  // Topics Tab - Accordion sections
  topics: {
    views: {
      title: 'Views',
      content: `
        <p>The graph has <strong>four view modes</strong>, each showing a different slice of the data:</p>

        <h4>Trending</h4>
        <p>
          Shows entities with <strong>high velocity</strong> (acceleration of mentions) and <strong>novelty</strong> (new or rare).
          This view is filtered to nodes with velocity > 0.1 to reduce clutter and focus on active trends.
        </p>
        <ul>
          <li><strong>When to use:</strong> Discovering emerging trends and hot topics</li>
          <li><strong>Signal:</strong> Velocity = ratio of recent mentions (7d) to previous mentions (7-14d ago)</li>
        </ul>

        <h4>Claims</h4>
        <p>
          Shows <strong>entity-to-entity relationships</strong> like "OpenAI launched GPT-5" or "Model X trained on Dataset Y".
          This view excludes document nodes to focus on semantic connections.
        </p>
        <ul>
          <li><strong>When to use:</strong> Understanding how entities relate to each other</li>
          <li><strong>Edge types:</strong> LAUNCHED, USES_MODEL, TRAINED_ON, PARTNERED_WITH, etc.</li>
        </ul>

        <h4>Mentions</h4>
        <p>
          Shows <strong>document-to-entity connections</strong>, revealing which sources mention which entities.
          Document nodes are included and connect to the entities they discuss.
        </p>
        <ul>
          <li><strong>When to use:</strong> Tracing claims back to source documents</li>
          <li><strong>Edge type:</strong> MENTIONS (document mentions entity)</li>
        </ul>

        <h4>Dependencies</h4>
        <p>
          Shows <strong>technical dependency relationships</strong> like USES_TECH, DEPENDS_ON, REQUIRES, INTEGRATES_WITH.
          Useful for understanding the technology stack and infrastructure.
        </p>
        <ul>
          <li><strong>When to use:</strong> Analyzing technical architecture and tool dependencies</li>
        </ul>
      `
    },

    reading: {
      title: 'Reading the Graph',
      content: `
        <h4>Node Size</h4>
        <p>
          Larger nodes indicate <strong>higher activity</strong>, calculated from:
        </p>
        <ul>
          <li><strong>Velocity</strong> (primary) — acceleration of mentions over time</li>
          <li><strong>Recency boost</strong> — new nodes (≤7 days) get a 50% size boost</li>
          <li><strong>Degree</strong> (connections) — hub nodes are larger</li>
        </ul>
        <p class="help-note">
          📏 Size range: 20-80px. A node with velocity 2.0 and 10 connections will be ~3x larger than a low-activity node.
        </p>

        <h4>Node Color (Entity Type)</h4>
        <div class="color-legend">
          <div class="color-item"><span class="color-swatch" style="background: #4A90D9;"></span> Blue = Org (companies, agencies)</div>
          <div class="color-item"><span class="color-swatch" style="background: #7C3AED;"></span> Violet = Model (AI/ML models)</div>
          <div class="color-item"><span class="color-swatch" style="background: #50B4A8;"></span> Teal = Person (individuals)</div>
          <div class="color-item"><span class="color-swatch" style="background: #8B5CF6;"></span> Purple = Tool (software, platforms)</div>
          <div class="color-item"><span class="color-swatch" style="background: #F59E0B;"></span> Orange = Dataset (training data)</div>
          <div class="color-item"><span class="color-swatch" style="background: #10B981;"></span> Green = Paper (research papers)</div>
          <div class="color-item"><span class="color-swatch" style="background: #EAB308;"></span> Gold = Tech (technologies, techniques)</div>
          <div class="color-item"><span class="color-swatch" style="background: #64748B;"></span> Slate = Topic (abstract themes)</div>
        </div>
        <p class="help-note">
          <a href="#" onclick="openTopicSection('glossary'); return false;">See full list of 15 entity types →</a>
        </p>

        <h4>Node Opacity (Recency)</h4>
        <p>Nodes <strong>fade as they age</strong>, creating a visual "heat map" of recent activity:</p>
        <ul>
          <li>0-7 days: <strong>full opacity</strong> (active)</li>
          <li>7-30 days: 85% opacity (recent)</li>
          <li>30-90 days: 55% opacity (fading)</li>
          <li>90+ days: 25% opacity (ghost node)</li>
        </ul>

        <h4>Edge Style (Relationship Kind)</h4>
        <table class="help-table">
          <tr>
            <td><strong>Solid line</strong></td>
            <td><span class="badge badge-kind-asserted">Asserted</span> — directly stated in source documents</td>
          </tr>
          <tr>
            <td><strong>Dashed line</strong></td>
            <td><span class="badge badge-kind-inferred">Inferred</span> — derived from multiple sources or reasoning</td>
          </tr>
          <tr>
            <td><strong>Dotted line</strong></td>
            <td><span class="badge badge-kind-hypothesis">Hypothesis</span> — speculative; needs verification</td>
          </tr>
        </table>

        <h4>Edge Thickness (Confidence)</h4>
        <p>
          Thicker edges = <strong>higher confidence</strong> (0.5px at 0% confidence → 4px at 100% confidence).
          Confidence is based on evidence quality and source count.
        </p>

        <h4>Edge Color</h4>
        <ul>
          <li><strong>Gray</strong> (#6B7280) — default</li>
          <li><strong>Green</strong> (#22C55E) — new edge (first seen &lt;7 days ago)</li>
          <li><strong>Blue</strong> (#3B82F6) — hover/selected</li>
        </ul>
      `
    },

    nodes: {
      title: 'Interacting with Nodes',
      content: `
        <h4>Click to Select + Highlight Neighborhood</h4>
        <p>
          Clicking a node <strong>selects it</strong> and highlights its 1-hop neighborhood (directly connected nodes and edges).
          Everything else is dimmed to opacity 0.15.
        </p>
        <ul>
          <li>The <strong>detail panel</strong> opens on the left with full node information</li>
          <li><strong>Connected nodes</strong> stay visible; non-neighbors are dimmed</li>
          <li>Click background or press <kbd>Escape</kbd> to clear</li>
        </ul>
        <p class="help-note">
          ℹ️ If a search is active, neighborhood highlighting is skipped to avoid visual conflicts.
        </p>

        <h4>Hover for Quick Preview</h4>
        <p>
          Hovering shows a <strong>tooltip</strong> with key stats (mentions, velocity, first/last seen).
          Hover does <em>not</em> dim the graph — that's intentional to avoid visual noise during casual browsing.
        </p>

        <h4>Detail Panel Contents</h4>
        <p>When you click a node, the detail panel shows:</p>
        <ul>
          <li><strong>Entity type badge</strong> and label</li>
          <li><strong>Aliases</strong> (alternative names)</li>
          <li><strong>Timeline:</strong> first seen and last seen dates</li>
          <li><strong>Activity metrics:</strong> mention counts (7d, 30d), connections, velocity</li>
          <li><strong>Relationships:</strong> grouped list of connected entities (up to 5 per type)</li>
        </ul>
        <p>
          Click <strong>"Expand"</strong> to reveal hidden neighbors, or <strong>"Center"</strong> to zoom to the node.
        </p>

        <h4>Double-Click to Zoom</h4>
        <p>
          Double-click a node to <strong>zoom to its neighborhood</strong> (1-hop neighbors fit to viewport with padding).
        </p>

        <h4>Arrow Keys to Navigate</h4>
        <p>
          When a node is selected, use <kbd>←</kbd> <kbd>→</kbd> <kbd>↑</kbd> <kbd>↓</kbd> to jump to the nearest neighbor in that direction.
          The new node is selected and its neighborhood is highlighted.
        </p>
      `
    },

    edges: {
      title: 'Interacting with Edges',
      content: `
        <h4>Click to View Evidence</h4>
        <p>
          Clicking an edge opens the <strong>evidence panel</strong> at the bottom, showing:
        </p>
        <ul>
          <li><strong>Relationship:</strong> source → target (e.g., "OpenAI → GPT-5")</li>
          <li><strong>Relation type:</strong> LAUNCHED, USES_MODEL, etc.</li>
          <li><strong>Kind:</strong> asserted / inferred / hypothesis</li>
          <li><strong>Confidence score:</strong> 0-100%</li>
          <li><strong>Evidence snippets:</strong> short quotes from source documents with links</li>
        </ul>

        <h4>What Are Evidence Snippets?</h4>
        <p>
          Every <strong>asserted</strong> relationship includes one or more <strong>evidence snippets</strong> — short quotes
          (≤200 chars) from the source documents that support the claim. Each snippet includes:
        </p>
        <ul>
          <li>Document title and source (e.g., "Hugging Face Blog")</li>
          <li>Published date</li>
          <li>Quote in context</li>
          <li>Link to view the full document</li>
        </ul>
        <p class="help-note">
          🔍 Inferred and hypothesis edges may not have snippets, as they're derived from reasoning rather than direct quotes.
        </p>

        <h4>Understanding Confidence Scores</h4>
        <p>
          Confidence (0-100%) reflects:
        </p>
        <ul>
          <li><strong>Evidence quality</strong> — clear, direct statements score higher</li>
          <li><strong>Source count</strong> — multiple independent sources increase confidence</li>
          <li><strong>Extractor certainty</strong> — how confident the AI was in the extraction</li>
        </ul>
        <p>
          Edges below the minimum confidence threshold (default 30%) are filtered out.
          You can adjust this in the filter panel.
        </p>

        <h4>Asserted vs Inferred vs Hypothesis</h4>
        <table class="help-table">
          <tr>
            <td><strong>Asserted</strong></td>
            <td>Directly stated in source documents. Always includes evidence snippets. High reliability.</td>
          </tr>
          <tr>
            <td><strong>Inferred</strong></td>
            <td>Derived from multiple sources or logical reasoning. May lack direct quotes. Medium reliability.</td>
          </tr>
          <tr>
            <td><strong>Hypothesis</strong></td>
            <td>Speculative connection that needs verification. Hidden by default in filters. Low reliability.</td>
          </tr>
        </table>
        <p class="help-note">
          ⚙️ Toggle these on/off in the <strong>Filter panel</strong> (gear icon).
        </p>
      `
    },

    search: {
      title: 'Search',
      content: `
        <h4>How Search Works</h4>
        <p>
          The search box (top center) searches across:
        </p>
        <ul>
          <li><strong>Node labels</strong> (e.g., "OpenAI", "GPT-5")</li>
          <li><strong>Aliases</strong> (alternative names like "OpenAI Inc")</li>
          <li><strong>Entity types</strong> (e.g., "Model", "Dataset")</li>
        </ul>
        <p>
          Search is <strong>partial match</strong> and <strong>case-insensitive</strong> — typing "gpt" will match "GPT-4", "GPT-5", etc.
        </p>

        <h4>Using Search</h4>
        <ol>
          <li>Press <kbd>/</kbd> to focus the search box (or just click it)</li>
          <li>Type your query — results update as you type</li>
          <li>Matching nodes stay visible; non-matches are dimmed</li>
          <li>The <strong>result count</strong> appears next to the search box</li>
          <li>Press <kbd>Enter</kbd> to <strong>zoom to fit</strong> all matching nodes</li>
          <li>Press <kbd>Escape</kbd> or click the ✕ to clear search</li>
        </ol>

        <h4>Search Tips</h4>
        <ul>
          <li><strong>Broad queries</strong> ("model") will match all Model-type entities</li>
          <li><strong>Specific queries</strong> ("gpt-4") narrow to exact matches</li>
          <li>Search also matches <strong>edges between matches</strong> (dimming is node-based)</li>
        </ul>
        <p class="help-note">
          ℹ️ While a search is active, <strong>neighborhood highlighting is disabled</strong> to avoid visual conflicts.
          Clear the search to re-enable click-to-highlight.
        </p>
      `
    },

    filtering: {
      title: 'Filtering',
      content: `
        <h4>Opening the Filter Panel</h4>
        <p>
          Click the <strong>gear icon</strong> (⚙) in the top-right toolbar to open the filter panel.
          It slides in from the right and can be closed by clicking the icon again or clicking outside.
        </p>

        <h4>Filter Types</h4>

        <h5>1. Date Range</h5>
        <p>
          Filter nodes by <strong>last seen date</strong>. Use preset buttons (7d / 30d / 90d / All) to quickly
          filter to recent activity, or choose a custom range with the date inputs.
        </p>
        <ul>
          <li><strong>7d</strong> — entities mentioned in the last 7 days</li>
          <li><strong>30d</strong> — entities mentioned in the last 30 days</li>
          <li><strong>90d</strong> — entities mentioned in the last 90 days</li>
          <li><strong>All</strong> — no date filtering</li>
        </ul>

        <h5>2. Entity Types</h5>
        <p>
          Show/hide nodes by <strong>entity type</strong> (Org, Person, Model, Tool, Dataset, etc.).
          Use the checkboxes or click <strong>"All"</strong> / <strong>"None"</strong> buttons for bulk selection.
        </p>

        <h5>3. Relationship Kind</h5>
        <p>
          Show/hide edges by <strong>epistemic status</strong>:
        </p>
        <ul>
          <li><strong>Asserted</strong> — directly stated in sources (checked by default)</li>
          <li><strong>Inferred</strong> — derived from reasoning (checked by default)</li>
          <li><strong>Hypothesis</strong> — speculative (unchecked by default)</li>
        </ul>

        <h5>4. Minimum Confidence</h5>
        <p>
          Set a <strong>confidence threshold</strong> (0-100%) to hide low-confidence edges.
          Default is 30%. Slide to the right to show only high-confidence relationships.
        </p>

        <h4>Applying Filters</h4>
        <p>
          After adjusting filters, click <strong>"Apply"</strong> to update the graph.
          Filtered-out nodes and edges are hidden (not just dimmed).
        </p>
        <p>
          Click <strong>"Reset"</strong> to clear all filters and return to the default view.
        </p>

        <h4>How Filters Combine</h4>
        <p>
          All filters use <strong>AND logic</strong> — a node must pass <em>all</em> active filters to be shown.
          For example: "Org type + last 30 days + confidence ≥50%" will show only Orgs with recent activity and high-confidence edges.
        </p>
      `
    },

    dataTiers: {
      title: 'Data Tiers',
      content: `
        <h4>What Are Data Tiers?</h4>
        <p>
          The <strong>Data dropdown</strong> in the toolbar controls which dataset is loaded.
          This is primarily a <strong>development and demo feature</strong> for testing performance at different scales.
        </p>

        <h4>Available Tiers</h4>
        <table class="help-table">
          <tr>
            <td><strong>Original (~15)</strong></td>
            <td>Hand-curated initial dataset; very small</td>
          </tr>
          <tr>
            <td><strong>Small (~15)</strong></td>
            <td>Generated sample with ~15 nodes for quick testing</td>
          </tr>
          <tr>
            <td><strong>Medium (~150)</strong></td>
            <td>Default; realistic size for daily exploration (150 nodes, ~250 edges)</td>
          </tr>
          <tr>
            <td><strong>Large (~500)</strong></td>
            <td>Large dataset for testing filter and layout performance</td>
          </tr>
          <tr>
            <td><strong>Stress (~2000)</strong></td>
            <td>Stress test dataset; may be slow on older hardware</td>
          </tr>
        </table>

        <h4>When to Change Tiers</h4>
        <p>
          Most users should stay on <strong>Medium</strong>. Switch tiers if:
        </p>
        <ul>
          <li>You want a <strong>quick overview</strong> (use Small)</li>
          <li>You're exploring a <strong>full multi-week dataset</strong> (use Large)</li>
          <li>You're testing <strong>performance optimizations</strong> (use Stress)</li>
        </ul>
        <p class="help-note">
          ⚠️ Stress tier (2000+ nodes) may freeze on slower devices. Use filters to reduce visible nodes.
        </p>
      `
    },

    glossary: {
      title: 'Glossary',
      content: `
        <h4>Entity Types (15 Total)</h4>
        <dl class="help-glossary">
          <dt>Org</dt>
          <dd>Organizations: companies, agencies, institutions (e.g., OpenAI, Google, CDC)</dd>

          <dt>Person</dt>
          <dd>Individuals: researchers, executives, public figures (e.g., Sam Altman, Demis Hassabis)</dd>

          <dt>Program</dt>
          <dd>Government or corporate programs (e.g., DARPA AI Next, EU AI Act implementation)</dd>

          <dt>Tool</dt>
          <dd>Software tools and platforms (e.g., TensorFlow, PyTorch, LangChain)</dd>

          <dt>Model</dt>
          <dd>AI/ML models (e.g., GPT-4, Claude, Llama, Stable Diffusion)</dd>

          <dt>Dataset</dt>
          <dd>Training or evaluation datasets (e.g., ImageNet, The Pile, LAION-5B)</dd>

          <dt>Benchmark</dt>
          <dd>Evaluation benchmarks and leaderboards (e.g., MMLU, HumanEval, GLUE)</dd>

          <dt>Paper</dt>
          <dd>Research papers and publications (e.g., "Attention Is All You Need")</dd>

          <dt>Repo</dt>
          <dd>Code repositories (e.g., GitHub repos, open-source projects)</dd>

          <dt>Tech</dt>
          <dd>Technologies, techniques, or concepts (e.g., "transformers", "RLHF", "diffusion")</dd>

          <dt>Topic</dt>
          <dd>Abstract topics and themes (e.g., "AI safety", "multimodal learning")</dd>

          <dt>Document</dt>
          <dd>Source documents: news articles, blog posts, reports (usually hidden in Claims view)</dd>

          <dt>Event</dt>
          <dd>Conferences, product launches, incidents (e.g., "NeurIPS 2025", "GPT-5 launch event")</dd>

          <dt>Location</dt>
          <dd>Geographic locations (e.g., "San Francisco", "EU", "Beijing")</dd>

          <dt>Other</dt>
          <dd>Uncategorized entities that don't fit above types</dd>
        </dl>

        <h4>Relationship Kinds (Epistemic Status)</h4>
        <dl class="help-glossary">
          <dt>Asserted</dt>
          <dd>Directly stated in source documents. Includes evidence snippets. Highest reliability.</dd>

          <dt>Inferred</dt>
          <dd>Derived from multiple sources or reasoning. Medium reliability. May lack direct quotes.</dd>

          <dt>Hypothesis</dt>
          <dd>Speculative connection that needs verification. Low reliability. Hidden by default.</dd>
        </dl>

        <h4>Key Metrics</h4>
        <dl class="help-glossary">
          <dt>Velocity</dt>
          <dd>
            Acceleration of mentions over time. Calculated as the ratio of recent mentions (7d) to previous mentions (7-14d ago).
            Values typically range 0-3. High velocity (>1.5) indicates rapid growth.
          </dd>

          <dt>Novelty</dt>
          <dd>
            How new or rare an entity is. Calculated from days since first seen + rarity proxy (inverse mention count).
            New entities (&lt;7 days old) score highest.
          </dd>

          <dt>Confidence</dt>
          <dd>
            Quality score for relationships (0-100%). Based on evidence quality, source count, and extractor certainty.
            Higher = more reliable.
          </dd>

          <dt>First Seen</dt>
          <dd>
            The earliest date this entity appeared in the ingested documents.
          </dd>

          <dt>Last Seen</dt>
          <dd>
            The most recent date this entity was mentioned. Nodes fade as last seen ages (visual heat map).
          </dd>
        </dl>
      `
    }
  }
};

// Export for use in help.js
if (typeof module !== 'undefined' && module.exports) {
  module.exports = HelpContent;
}
