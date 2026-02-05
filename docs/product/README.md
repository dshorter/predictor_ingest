# AI Trend Graph — Product Guide

An interactive knowledge graph that surfaces emerging AI trends before they become obvious. The graph ingests articles from research, open-source, and industry sources daily, extracts entities and relationships, and visualizes them as a living map where patterns — new clusters, fading topics, unexpected bridges — become visible at a glance.

---

## What You're Looking At

The AI Trend Graph is a force-directed network where **nodes are entities** (organizations, models, technologies, datasets, people) and **edges are relationships** between them (created, uses, trained on, funded, etc.). The graph is not static — it updates daily as new articles are ingested, so the landscape shifts over time.

The default view shows **Trending** entities: the nodes with the highest recent velocity, novelty, or bridging activity. This is the starting point for spotting what's moving.

> **Screenshot: `overview.png`**
> *Full application with the Trending view loaded. Show the toolbar at top, the graph canvas in center, and the filter panel collapsed on the right. Include a mix of node sizes and colors to demonstrate the visual encoding. Ideally capture a state with 30-50 nodes where clusters and isolated nodes are both visible.*

---

## Views

The graph offers four views, each a different lens on the same underlying data.

### Trending

The default. Filtered to entities with the highest velocity (accelerating mentions), novelty (recently appeared), or bridge score (connecting otherwise separate clusters). This is where you look first.

> **Screenshot: `view-trending.png`**
> *Trending view with ~30-40 nodes. Larger nodes should be prominent in the center. Show at least 2-3 visible clusters and a few bridge edges connecting them. The view selector in the toolbar should show "Trending" selected.*

### Claims

The full semantic graph: entity-to-entity relationships like "OpenAI CREATED GPT-5" or "Meta USES_TECH transformer." This is the richest view but can be dense.

> **Screenshot: `view-claims.png`**
> *Claims view showing a denser graph (~100+ nodes). The increased density compared to Trending should be obvious. Show the graph stats in the toolbar reflecting the higher node/edge count.*

### Mentions

Document-to-entity edges. Every article that mentions an entity gets a MENTIONS edge. Useful for tracing provenance — which sources are talking about which entities.

> **Screenshot: `view-mentions.png`**
> *Mentions view. Document nodes (type "Document") should be visible alongside entity nodes. The bipartite structure — documents on one side, entities on the other — should be apparent.*

### Dependencies

A filtered view showing only dependency-type relationships: USES_TECH, USES_MODEL, USES_DATASET, TRAINED_ON, EVALUATED_ON, DEPENDS_ON, REQUIRES. This view answers "what depends on what?" and reveals the supply chain of AI.

> **Screenshot: `view-dependencies.png`**
> *Dependencies view showing technology dependency chains. Ideally capture a cluster where a model depends on a dataset, uses a technology, and is evaluated on a benchmark — a clear chain of dependencies.*

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

> **Screenshot: `node-colors.png`**
> *A section of the graph showing at least 5-6 different node types with their distinct colors. Ideally show an Org (blue), Model (violet), Tech (teal), and a few others in close proximity so the color coding is obvious. Include a hover tooltip on one node showing its type.*

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

> **Screenshot: `edge-styles.png`**
> *Close-up of a section showing different edge styles: at least one solid (asserted), one dashed (inferred), and if possible one dotted (hypothesis). Show varying thicknesses. If any green (new) edges are visible, include them. Zoom in enough that the line styles are clearly distinguishable.*

---

## Interacting with the Graph

### Click a Node

Clicking a node does two things:

1. **Highlights its neighborhood** — connected nodes and edges stay fully visible; everything else dims to 15% opacity. This instantly shows you what an entity is connected to.
2. **Opens the detail panel** on the left with full metadata: entity type, aliases, first/last seen dates, and a list of all relationships.

Click the canvas background to clear the selection and restore full visibility.

> **Screenshot: `click-node.png`**
> *A node selected with neighborhood highlighting active. The selected node and its immediate neighbors should be bright; the rest of the graph should be visibly dimmed. The detail panel should be open on the left showing the node's metadata and relationship list.*

### Click an Edge

Clicking an edge opens the **evidence panel** at the bottom, showing the provenance for that relationship: the source article(s), publication dates, evidence snippets (direct quotes), and confidence score. This is how you verify a claim — every asserted edge traces back to a specific passage in a specific article.

> **Screenshot: `click-edge.png`**
> *An edge selected with the evidence panel open at the bottom. The panel should show at least one evidence entry with a snippet, source URL, and publication date. The graph canvas should be visibly shorter to accommodate the panel.*

### Hover

Hovering over a node shows a tooltip with the entity label, type, and key metrics (velocity, first seen, last seen). Hovering over an edge shows the relationship type, confidence, and kind.

> **Screenshot: `hover-tooltip.png`**
> *A tooltip visible on a hovered node showing its label, type, and metrics. The node should have a visible hover border highlight (blue border). Keep it simple — just the tooltip and the highlighted node.*

### Search

The search box in the toolbar (also activated with `/` keyboard shortcut) filters nodes by label or alias. Matching nodes stay bright; non-matches dim. Press Enter to zoom the camera to fit all matches. Press Escape or click the X to clear.

> **Screenshot: `search.png`**
> *Search in action with a term typed (e.g., "transformer" or "openai"). Matching nodes should be bright with the rest dimmed. The search results count should be visible next to the input. Show 2-3 matches highlighted in the graph.*

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

> **Screenshot: `filter-panel.png`**
> *The filter panel expanded on the right side. Show all four filter sections: Date Range (with preset buttons), Entity Types (with checkboxes), Relationship Kind (asserted/inferred/hypothesis toggles), and Confidence threshold (slider). The panel should be fully visible with the graph behind it.*

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

> **Screenshot: `toolbar.png`**
> *The full toolbar in isolation or with a thin strip of the graph below it. Label the key elements: View selector, Data tier selector, Search box, graph stats, zoom buttons, layout button, theme toggle, filter toggle, help button.*

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

> **Screenshot: `dark-mode.png`**
> *The application in dark mode with a graph loaded. Show enough of the interface — toolbar, graph, and ideally one panel — to demonstrate that the full UI adapts to the dark theme. Pair with a light mode screenshot if space allows.*

> **Screenshot: `light-mode.png`**
> *Same or similar graph state in light mode, for comparison with the dark mode screenshot above.*

---

## Understanding Trends

The Trending view surfaces entities based on three signals:

### Velocity

How fast is an entity accelerating? Velocity compares recent mention frequency (7-day window) against a longer baseline (30-day window). A high velocity means something is being talked about more than usual — a model release, a policy announcement, a breakthrough paper.

### Novelty

How new is this entity? Recently appeared entities with few historical mentions score high on novelty. This catches things that didn't exist in the graph a week ago — a newly announced model, a just-published dataset, a startup that just emerged.

### Bridge Score

Is this entity connecting previously separate parts of the graph? Bridge nodes sit between clusters that don't otherwise interact. A technology that suddenly connects a government program to an open-source project, or a researcher bridging two separate fields, scores high here. These are often the most interesting signals — they indicate cross-pollination or convergence.

> **Screenshot: `trend-signals.png`**
> *The Trending view with annotations (can be added post-capture) pointing out: (1) a large node labeled as "high velocity," (2) a recently appeared node labeled as "high novelty," and (3) a node connecting two clusters labeled as "bridge." This may work better as an annotated composite rather than a raw screenshot.*

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
