# AI Trend Graph — Product Guide

An interactive knowledge graph that surfaces emerging AI trends before they become obvious. The graph ingests articles from research, open-source, and industry sources daily, extracts entities and relationships, and visualizes them as a living map where patterns — new clusters, fading topics, unexpected bridges — become visible at a glance.

---

## What You're Looking At

The AI Trend Graph is a force-directed network where **nodes are entities** (organizations, models, technologies, datasets, people) and **edges are relationships** between them (created, uses, trained on, funded, etc.). The graph is not static — it updates daily as new articles are ingested, so the landscape shifts over time.

The default view shows **Trending** entities: the nodes with the highest recent velocity, novelty, or bridging activity. This is the starting point for spotting what's moving.

<!-- Capture: Full application with Trending view loaded. Toolbar at top, graph canvas in center, filter panel collapsed. Mix of node sizes/colors. 30-50 nodes with visible clusters. -->
![Overview of the AI Trend Graph application](images/overview.png)

---

## Views

The graph offers four views, each a different lens on the same underlying data.

### Trending

The default. Filtered to entities with the highest velocity (accelerating mentions), novelty (recently appeared), or bridge score (connecting otherwise separate clusters). This is where you look first.

<!-- Capture: Trending view with ~30-40 nodes. Larger nodes prominent in center. 2-3 visible clusters with bridge edges. View selector shows "Trending". -->
![Trending view showing high-velocity entities](images/view-trending.png)

### Claims

The full semantic graph: entity-to-entity relationships like "OpenAI CREATED GPT-5" or "Meta USES_TECH transformer." This is the richest view but can be dense.

<!-- Capture: Claims view with ~100+ nodes. Noticeably denser than Trending. Graph stats in toolbar show higher counts. -->
![Claims view showing the full semantic graph](images/view-claims.png)

### Mentions

Document-to-entity edges. Every article that mentions an entity gets a MENTIONS edge. Useful for tracing provenance — which sources are talking about which entities.

<!-- Capture: Mentions view. Document nodes visible alongside entity nodes. Bipartite structure apparent. -->
![Mentions view showing document-to-entity relationships](images/view-mentions.png)

### Dependencies

A filtered view showing only dependency-type relationships: USES_TECH, USES_MODEL, USES_DATASET, TRAINED_ON, EVALUATED_ON, DEPENDS_ON, REQUIRES. This view answers "what depends on what?" and reveals the supply chain of AI.

<!-- Capture: Dependencies view with technology dependency chains. Show a cluster: model → dataset → technology → benchmark chain. -->
![Dependencies view showing technology supply chains](images/view-dependencies.png)

---

## Reading the Graph

### Node Size = Velocity

Larger nodes are accelerating — they're being mentioned more frequently in recent articles compared to their historical baseline. A suddenly large node in the Trending view means something is happening right now.

### Node Color = Entity Type

Each entity type has a consistent color across all views:

| Color | Type | What it represents |
|-------|------|--------------------|
| Blue | Org | Organizations (OpenAI, Google DeepMind, DARPA) |
| Violet | Model | AI models (GPT-4, Gemini, Llama) |
| Teal | Tech | Technologies and methods (Transformer, RLHF, RAG) |
| Green | Dataset | Training and evaluation datasets |
| Amber | Benchmark | Evaluation benchmarks (MMLU, HumanEval) |
| Rose | Person | Researchers, executives |
| Slate | Paper | Research papers |
| Cyan | Repo | Code repositories |
| Orange | Tool | Software tools (LangChain, vLLM) |
| Indigo | Topic | Research topics and themes |
| Pink | Event | Conferences, launches |
| Lime | Program | Government or institutional programs |
| Gray | Document | Source articles |

<!-- Capture: Section of graph with 5-6 different node types. Show Org (blue), Model (violet), Tech (teal), others. Hover tooltip on one node showing type. -->
![Node color coding by entity type](images/node-colors.png)

### Node Opacity = Recency

Nodes fade as they age. An entity last seen 90 days ago appears more transparent than one seen today. This makes active topics visually pop while dormant ones recede without disappearing — you can still see where they are on the map, but your eye is drawn to what's current.

### Edge Style = Confidence Level

| Style | Meaning |
|-------|---------|
| Solid line | **Asserted** — directly stated in a source article with evidence |
| Dashed line | **Inferred** — derived from co-occurrence or indirect signals |
| Dotted line | **Hypothesis** — speculative, needs verification |

### Edge Thickness = Confidence Score

Thicker edges have higher confidence scores (ranging from 0.5px to 4px). A thick solid edge is a well-supported claim; a thin dotted edge is a tentative guess.

### Edge Color

Gray by default. Green edges are new — added within the last 7 days. Green edges on the Trending view are where the action is.

<!-- Capture: Close-up showing edge styles. At least one solid (asserted), one dashed (inferred), one dotted (hypothesis) if possible. Varying thicknesses. Green new edges if visible. Zoom in so line styles are clear. -->
![Edge styles showing confidence levels](images/edge-styles.png)

---

## Interacting with the Graph

### Click a Node

Clicking a node does two things:

1. **Highlights its neighborhood** — connected nodes and edges stay fully visible; everything else dims to 15% opacity. This instantly shows you what an entity is connected to.
2. **Opens the detail panel** on the left with full metadata: entity type, aliases, first/last seen dates, and a list of all relationships.

Click the canvas background to clear the selection and restore full visibility.

<!-- Capture: Node selected with neighborhood highlighting. Selected node and neighbors bright, rest dimmed. Detail panel open on left showing metadata and relationships. -->
![Clicking a node highlights its neighborhood and shows details](images/click-node.png)

### Click an Edge

Clicking an edge opens the **evidence panel** at the bottom, showing the provenance for that relationship: the source article(s), publication dates, evidence snippets (direct quotes), and confidence score. This is how you verify a claim — every asserted edge traces back to a specific passage in a specific article.

<!-- Capture: Edge selected with evidence panel open at bottom. Panel shows evidence entry with snippet, source URL, publication date. Graph canvas shorter to accommodate panel. -->
![Clicking an edge shows provenance and evidence](images/click-edge.png)

### Hover

Hovering over a node shows a tooltip with the entity label, type, and key metrics (velocity, first seen, last seen). Hovering over an edge shows the relationship type, confidence, and kind.

<!-- Capture: Tooltip visible on hovered node showing label, type, metrics. Node has visible hover highlight (blue border). -->
![Hover tooltip showing node details](images/hover-tooltip.png)

### Search

The search box in the toolbar (also activated with `/` keyboard shortcut) filters nodes by label or alias. Matching nodes stay bright; non-matches dim. Press Enter to zoom the camera to fit all matches. Press Escape or click the X to clear.

<!-- Capture: Search active with term typed (e.g., "transformer" or "openai"). Matching nodes bright, rest dimmed. Search results count visible. 2-3 matches highlighted. -->
![Search filtering and highlighting matching nodes](images/search.png)

### Keyboard Navigation

| Key | Action |
|-----|--------|
| `/` | Focus search box |
| `Escape` | Clear search or close panel |
| Arrow keys | Navigate between nodes when graph is focused |
| `+` / `-` | Zoom in / out |

---

## Filtering

The filter panel (toggle with the gear icon in the toolbar) lets you narrow the graph to exactly what you care about.

<!-- Capture: Filter panel expanded on right. Show all four sections: Date Range (preset buttons), Entity Types (checkboxes), Relationship Kind (toggles), Confidence threshold (slider). Panel fully visible with graph behind. -->
![Filter panel with all filter options](images/filter-panel.png)

### Date Range

Preset buttons filter to entities seen within the last 7, 30, or 90 days, or show all. This controls temporal scope — use 7d to focus on what's happening this week, 30d for the recent month, All for the full history.

### Entity Types

Checkboxes for each entity type. Uncheck types you're not interested in to declutter the view. For example, uncheck "Document" and "Paper" to focus on organizations, models, and technologies.

### Relationship Kind

Toggle which confidence levels of edges are visible:

- **Asserted** (on by default) — evidence-backed claims
- **Inferred** (on by default) — derived relationships
- **Hypothesis** (off by default) — speculative connections

Turn on Hypothesis to see the speculative layer; turn off Inferred to see only hard evidence.

### Confidence Threshold

A slider (default 30%) that hides edges below the threshold. Raise it to see only high-confidence relationships; lower it to see everything including low-confidence signals.

---

## Toolbar Controls

<!-- Capture: Full toolbar (can include thin strip of graph below). Consider annotating: View selector, Data selector, Search box, graph stats, zoom buttons, layout button, theme toggle, filter toggle, help button. -->
![Toolbar controls](images/toolbar.png)

| Control | What it does |
|---------|--------------|
| **View selector** | Switch between Trending, Claims, Mentions, Dependencies |
| **Data selector** | Choose dataset size (for testing/demo purposes) |
| **Search** | Filter and highlight nodes by name |
| **Graph stats** | Shows current node and edge count |
| **Zoom +/-** | Zoom in or out |
| **Fit** | Reset zoom to fit all visible nodes |
| **Re-run layout** | Recalculate node positions (force-directed) |
| **Theme toggle** | Switch between dark and light mode |
| **Filter toggle** | Open/close the filter panel |
| **Help** | Quick start guide and keyboard shortcuts |

---

## Dark Mode

The application supports both light and dark themes, toggled from the toolbar. The graph colors are designed to work well in both modes.

<!-- Capture: Application in dark mode with graph loaded. Show toolbar, graph, and one panel if possible. -->
![Dark mode theme](images/dark-mode.png)

<!-- Capture: Same or similar graph state in light mode for comparison. -->
![Light mode theme](images/light-mode.png)

---

## Understanding Trends

The Trending view surfaces entities based on three signals:

### Velocity

How fast is an entity accelerating? Velocity compares recent mention frequency (7-day window) against a longer baseline (30-day window). A high velocity means something is being talked about more than usual — a model release, a policy announcement, a breakthrough paper.

### Novelty

How new is this entity? Recently appeared entities with few historical mentions score high on novelty. This catches things that didn't exist in the graph a week ago — a newly announced model, a just-published dataset, a startup that just emerged.

### Bridge Score

Is this entity connecting previously separate parts of the graph? Bridge nodes sit between clusters that don't otherwise interact. A technology that suddenly connects a government program to an open-source project, or a researcher bridging two separate fields, scores high here. These are often the most interesting signals — they indicate cross-pollination or convergence.

<!-- Capture: Trending view. Consider post-capture annotations: (1) large node = "high velocity", (2) recently appeared node = "high novelty", (3) node connecting clusters = "bridge". May work better as annotated composite. -->
![Trend signals: velocity, novelty, and bridge score](images/trend-signals.png)

---

## Typical Workflows

### Morning Check: "What's new today?"

1. Open the app (defaults to Trending view)
2. Scan for large nodes — these have the highest velocity
3. Look for green edges — these are new relationships added today
4. Click interesting nodes to see their connections and source articles

### Deep Dive: "Tell me about this entity"

1. Search for the entity name
2. Click the matching node to see its detail panel
3. Review the relationship list — what does it connect to?
4. Click edges to read the evidence snippets and source articles
5. Switch to Claims view for the full relationship context

### Supply Chain Analysis: "What depends on what?"

1. Switch to the Dependencies view
2. Look for hub nodes with many dependency edges
3. Click a technology node to see what models/tools depend on it
4. Follow the chains: Model → trained on Dataset → evaluated on Benchmark

### Spotting Convergence: "Are these fields connecting?"

1. Start in the Trending view
2. Look for bridge nodes or long edges connecting separate clusters
3. Click bridge nodes to inspect which clusters they connect
4. Switch to Claims view for the full picture of cross-domain relationships

---

## Technical Notes

- The graph is a static site — no backend server required. It loads pre-exported JSON files.
- Layout is force-directed (fcose algorithm) and recalculated on each load. Node positions are not yet persistent across sessions (planned for V2).
- Performance is optimized for up to ~2,000 nodes. Beyond that, the client auto-filters to the trending subset.
- The application is keyboard-navigable and includes screen reader support.
