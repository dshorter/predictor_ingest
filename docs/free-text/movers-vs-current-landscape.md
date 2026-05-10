# Movers vs. Current Landscape — Working Notes

*Free-text capture. Stream-of-consciousness. Will be updated as the thinking
evolves. No code yet — this session is intellectual output, not implementation.*

*Started: 2026-05-10*

---

## Where this started

Looked at what the existing "trend view" actually does. The mechanics:

- `scripts/run_trending.py` calls `TrendScorer.score_all()` to score every
  entity in the DB, then takes the **top 50** (`--top-n`, fixed cutoff —
  not a percentile).
- `trend_score` is a weighted blend pulled from the domain profile:
  `0.4 × velocity + 0.3 × novelty + 0.3 × activity`.
  - `velocity` = 7d mentions vs. prior 7d, capped at 5.0
  - `novelty` = recency + rarity, decayed
  - `activity` = raw 7d mention count, capped at 20
- Edges retained only if **both endpoints** are in the top 50. Then a
  bridge-entity layer is pulled in (non-trending entities that connect ≥2
  trending entities, where ≥1 is otherwise isolated) to keep the graph from
  fragmenting into a dust cloud.

So the final view is "top 50 by trend_score + non-trending bridges that exist
purely to reconnect the graph."

## The complaint that opened the conversation

In AI and semiconductors, the top-50 view shows the entities you'd expect —
Anthropic, OpenAI, Google, NVIDIA, TSMC, etc. The view *confirms* what's
prominent; it doesn't *surprise*. Genuine new movers — something that climbed
from rank 140 to rank 75, or just appeared this week — don't break into the
top 50. The view's job, as currently scored, is essentially impossible to do
well: it's trying to be both "show me what matters" (which favors established
players) and "show me what's emerging" (which favors low-volume risers), and
the scoring weights the former.

Activity at 0.3 weight, with a cap of 20 raw mentions, is enough to keep
established entities pinned to the top. Velocity at 0.4 weight is capped at
5.0, so a fast climber with low absolute volume can still lose to a Google
sitting at the activity cap with flat velocity. The blend is structurally
biased toward "hot AND established."

## The reframe

Two different questions, two different views. We were trying to make one view
answer both.

- **Current Landscape** — state, curated, relational, point-in-time.
  Graph-native. Answers "what's the shape of what matters in this domain
  right now?" The current trending.json + Cytoscape view is this. It's
  a perfectly legitimate view, it was just mis-named.

- **Movers** — change, comprehensive, time-aware, tabular. Answers "what's
  *moving* in this domain?" Including (especially) movement that hasn't yet
  surfaced into prominence. The 140→75 climber. The just-appeared entity.
  The slow accumulator that no single day's snapshot would flag.

One is **state**, the other is **change**. One is **graph-native**, the other
is **table-native**. One is **curated** (top N), the other is **comprehensive**
(all entities, sortable, filterable). The graph view literally cannot do the
Movers job — ranking and small multiples can, a node-link diagram cannot.

The term "trending" is doing two jobs and doing neither well. Retire it
entirely. Use **Current Landscape** and **Movers** going forward.

## What's Hot is already a proto-tabular Current Landscape

`web/js/whats-hot.js:21-59` — `getHotList()` iterates `cy.nodes()`, meaning
it reads the *same* trending.json that the graph renders, sorts by
`trend_score`, and slices the top 10. So:

- Same data source as the graph (top 50 prominence)
- Same scoring (existing trend_score blend)
- Same selection (already-curated set)
- Just a different rendering — list instead of graph

Architecturally: Current Landscape has *two* renderings today (graph + What's
Hot list), drawn from one feed (`trending.json`). Movers will need a *third*
rendering (table) drawn from a *new feed* — one that exposes rank Δ over time
and the full entity set, not just the prominence top-N.

The split that matters isn't graph-vs-table. It's prominence-feed vs.
movement-feed. Table just happens to be the natural shape for the latter.

## Where the Movers feed comes from

Some of the substrate already exists:

- `trend_history` table is written daily by `_save_trend_history` in
  `src/trend/__init__.py:338`. That's the foundation for rank Δ over 7 days,
  "biggest jumpers since last week," "just appeared," etc. Not new
  infrastructure — already there.
- `score_all()` already scores every entity in the DB. The top-50 cutoff is
  applied *after* scoring. So a Movers feed could be derived from the same
  pass, just without the slice.

What would be new: a different ranking dimension. Rank Δ. First-seen-recency.
Velocity sorted independently of activity. Possibly a "pure movement" score
that *doesn't* mix in activity at all, since activity is precisely the thing
suppressing emerging signal.

## Two architecture questions — held for later

These are real and need to be answered, but not now:

1. Is the Movers table a peer view to the graph (tab/toggle), or a side
   panel inside the existing trending view?
2. When sort/filter and click into an entity in the table, does the graph
   *replace* its current top-50 layout with that entity's 1-hop
   neighborhood, or open a focused subview alongside?

The answer affects export shape. Right now the graph is hard-bound to the 50
nodes shipped in `trending.json` — a row for entity #200 has no neighborhood
data on the client. Either (a) Movers is its own page that flips the graph
into "focus this entity" mode and loads neighborhoods on demand, or (b) the
export grows to ship a flatter "all entities + scores" feed alongside the
current trending.json. Both reasonable; different complexity.

---

## Reconsiderations the new paradigm forces

The Movers lens makes us go back and reconsider decisions that were made
through the (only-then-existing) Current Landscape lens.

### Film domain — wrong diagnosis, not a domain failure

Film was deprioritized as not-fitting the model. The diagnosis in
`docs/methodology/domain-fit-analysis.md`:

- 36.9% island rate (entities with zero connections) — CRITICAL
- 19% entity overlap vs. 30% target — LOW
- "Every week introduces new productions, new crew attachments, new festival
  selections — entities that appear once and never recur."
- "The denominator grows as fast as corroborations, keeping overlap
  permanently suppressed around 18–19%."

Re-read those numbers through the Movers lens. *That's not a domain failure.
That's film being all movement, no landscape.* The metrics by which it was
judged — overlap, edges/node, island rate — are Current Landscape metrics.
They demand persistent, recurring entities forming a stable graph. Movers
wants the opposite: high churn, things appearing for the first time, novelty.

Film should arguably be the **flagship Movers domain**, not the
deprioritized stress-test castoff. AI and semiconductors have the long,
recurring entities suited for Current Landscape. Film has the constant flux
suited for Movers. Both lenses cross-checking each other is probably the
healthiest endgame.

Worth considering: re-promote film from "stress-test domain" to a real
product domain once Movers exists.

### Bluesky — memory was off, but the underlying point holds

Initial framing was that Bluesky had been "cut." That's not actually what
happened. Verified state:

- `domains/film/feeds.yaml:227-229` — Bluesky SE Film: `enabled: true`
- `domains/semiconductors/feeds.yaml:260-262` — Bluesky Semiconductors:
  `enabled: true`
- AI domain `feeds.yaml` — Bluesky was never added at all (probably what
  was being remembered)

What *did* happen is documented in `docs/backlog.md:256-265` (SRC-5):
Bluesky SE Film produces 0.7 relations/doc vs. source average of ~14.
Posts are short and low-density, so the extractor gets little
relationship data out of them.

The proposed remediation in SRC-5 is exactly the Movers-native pattern:

> "Lower selection score weight for bluesky source type, or **exclude from
> extraction budget and keep as ingestion-only velocity signal.**"

Bluesky is a poor source for *graph edges* but a perfectly good source for
*mention counts*, which is what velocity (and Movers) needs. The pipeline
currently has no "ingest, count for velocity, don't waste tokens trying to
extract relations" mode. That's a real architectural gap, and Movers is
the use case that justifies filling it.

Reddit fits the same pattern. Probably other chatter sources too.

### The synthesizing observation

The pipeline's quality gates, source-pruning logic, and domain-fit metrics
are all calibrated for what makes a good Current Landscape. By those metrics:

- Film fails (high churn, low overlap, high island rate)
- Bluesky underperforms (low relations/doc)
- Sources get downgraded for not corroborating

But all of those produce **strong movement signal**, which is precisely the
substrate Movers feeds on. We've been discarding good signal because we only
had one lens.

This may extend beyond film and Bluesky. Worth a sweep of other downgraded
sources and domains once Movers is real.

---

## Open threads / parking lot

Things to come back to once we keep talking:

- **Two architecture questions** (peer view vs. panel; click-into entity
  behavior) — held above
- **Scoring for Movers** — same scores re-presented, or a new formula?
  Probably new. Rank Δ over 7 days is the obvious starting point.
  Activity weight likely drops to zero or near-zero for the Movers score,
  since activity is the thing suppressing what we want to see.
- **What's Hot's future** — keep it as a Current Landscape sub-rendering,
  retire it, or merge into a unified entity panel?
- **Re-promote film domain** — once Movers is real, film stops being a
  stress-test domain and becomes the flagship for the new lens.
- **"Ingest-only / velocity-only" source mode** — pipeline flag that lets
  Bluesky/Reddit/other chatter sources contribute mention counts without
  consuming extraction budget. Architectural gap.
- **Sweep of other downgraded sources/domains** through the Movers lens.
  Likely there's good signal we've quietly written off.
- **Cross-domain bridges in Movers** — does a Movers view make cross-domain
  emergence easier to spot? (Same entity moving in semi *and* AI feeds, etc.)
- **Naming** — "Current Landscape" / "Movers" feels right, but reserve the
  right to rename. "Landscape" might be too geographic. "Movers" is plain
  but possibly too unspecific. Live with it for a while.

---

*This doc is a working artifact, not a spec. Update freely.*
