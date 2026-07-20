# Backlog

Items discovered during development and early operation. Grouped by area,
roughly prioritized within each group. Items will move out of here as they
get scheduled into work.

---

## Extraction & Prompt Tuning

> **Active thread:** Gate tuning and cheap-model escalation is an ongoing story.
> Current gate config per domain (what's enabled, what's disabled, and why) lives in
> **[operational-state.md](../backend/operational-state.md)** — read that first.
> The full history is in EXT-4 below.

### EXT-1: Entity type definitions missing from LLM prompt

**Observed:** 2026-02-21 | **Priority:** Medium (accumulate data first)

The system prompt lists entity types as a bare enum with no definitions,
examples, or disambiguation rules. The GLOSSARY.md has good descriptions
but they never reach the prompt. This causes inconsistent classification:

- **Model vs Tool** — "ChatGPT" tagged as Model in one doc, Tool in another
- **Tech vs Topic** — "machine learning" could go either way
- **Tech vs Model** — "LLMs" classified as both `tech:llms` and `model:llms`

**Likely fix:** Inject GLOSSARY definitions + disambiguation rules into
`build_extraction_system_prompt()` in `src/extract/__init__.py` (~line 237).
Also need entity resolution to merge duplicates already created.

**Waiting on:** More days of pipeline output to see the full pattern of
misclassifications before tuning.

### EXT-2: Density score prompt tuning

**Observed:** 2026-02-23 | **Priority:** Medium (wait for full backlog)

Density scores vary significantly by source type (arXiv papers vs blog posts
vs news articles). Prompt tuning should wait until the full backlog is
extracted so we have representative density numbers across all ~10 source
types. Tuning against partial data risks overfitting to academic content.

**Waiting on:** Backlog extraction to complete across all source types.

### EXT-3: Add confidence calibration guidance to extraction prompt

**Observed:** 2026-02-23 | **Priority:** Medium (wait for full backlog)

Sonnet produces uniformly high confidence scores (0.85–0.95) with low
variance, making the UI confidence slider almost useless as a filter. The
current prompt says `confidence: 0.0 to 1.0` but gives no rubric for what
different levels mean.

Contributing factors beyond model disposition:
- MAX aggregation in graph export ratchets confidence upward as more docs
  cover the same entities (`src/graph/__init__.py:359`)
- MENTIONS relations are hardcoded to 1.0 (`scripts/import_extractions.py:183`)
- Quality gates create survivorship bias toward high-confidence edges

**Likely fix:** Add explicit calibration rubric to the extraction prompt, e.g.:
- 0.5–0.7 for indirect/implied relationships
- 0.8+ only for explicitly stated facts with direct evidence
- Reserve 0.95+ for relationships stated in the document's headline/thesis

**Waiting on:** Full backlog extraction to establish baseline confidence
distribution across all source types before tuning.

### EXT-4: Cheap model escalation rate too high (80%)

**Observed:** 2026-02-24 | **Analyzed:** 2026-02-25 | **Priority:** Medium | **Status:** Active — Gates A+D disabled on film (2026-03-24); AI domain escalation rate still being measured

Analysis of 223 extractions (Feb 22–24) showed an 80% escalation rate — the cheap
model (gpt-5-nano) fails quality gates on 4 out of 5 documents, making the
cheap-first strategy more expensive than running Sonnet directly.

**Failure modes (ranked by frequency):**
1. Orphan endpoints — relation source/target doesn't match entity names (dominant)
2. Evidence fidelity < 70% — bimodal distribution, low cluster at ~0.4
3. Zero-value — entities extracted but zero relations
4. High confidence + bad evidence — 0.9+ confidence with fabricated snippets

**Action taken (2026-02-25):** Three lightweight prompt additions to
`build_extraction_system_prompt()` in `src/extract/prompts.py`:
- Explicit orphan constraint (source/target must match entity names)
- Evidence grounding (snippets must be quotes from text, not memory)
- Minimum relations (non-trivial docs should produce ≥3 relations)

**Measurement:** After ~100 more extractions, compare escalation rate (target < 50%),
orphan failures (target: halved), evidence fidelity (target avg > 0.85).

**Escalation path:** If rate stays above ~50%, drop cheap-first and run Sonnet
directly (Option C). Cost delta is small (~$8 vs $25/month).

**2026-03-21 update:** Film domain hit 89% escalation rate. Gate A (evidence fidelity)
was the dominant trigger — film trade press paraphrases heavily and nano fabricates
snippets, causing Gate D (high-conf + bad evidence) cascades too. Decision: run film
pure-Sonnet temporarily (`PIPELINE_FLAGS="--no-escalate"`).

**2026-03-23 update:** Reinstating escalation with Gate A removed as an
escalation trigger. `domains/film/domain.yaml` — `evidence_fidelity_min` set to `0.0`
(Gate A still runs and logs match_rate for calibration, but never forces escalation).
Gates B/C/D (orphan endpoints, zero-value, high-confidence-bad-evidence) remain
enforced. Tradeoff: edge detail panels will show evidence snippets that are not
verified against source text — they may be paraphrases or from nano's memory.
Requires `UNDERSTUDY_MODEL=gpt-5-nano` and `OPENAI_API_KEY` in environment.

**2026-03-24 update (current):** Gate D also disabled on film (`high_confidence_threshold: 0.0`).
Both A and D rely on snippet text-match, which can't distinguish paraphrase from
fabrication in trade press. Gates B (orphans) and C (zero-value) are now the only
active gates for film. See operational-state.md for current per-domain config.

**Details:** [docs/fix-details/ext4-cheap-model-escalation-analysis.md](docs/fix-details/ext4-cheap-model-escalation-analysis.md)

### EXT-5: `LOCATED_IN` relation type not in canonical taxonomy

**Observed:** 2026-03-08 | **Priority:** Low (monitor)

AI domain extraction produced a `LOCATED_IN` relation that failed schema
validation — this relation type is not in the V1 canonical taxonomy. The
cheap model invented it rather than mapping to an existing type or omitting.

**Options:**
- Add `LOCATED_IN` to the canonical taxonomy if it recurs and is useful
- Add a negative example to the extraction prompt ("do not invent relation types")
- Rely on existing validation to catch and reject (current behavior)

**Waiting on:** Monitor whether this recurs. If it's a one-off, no action needed.

### EXT-7: Publishers extracted as `Org` entities (Tom's Hardware, Future US)

**Observed:** 2026-05-19 (Sprint 14 smoke test) | **Priority:** Medium

The semiconductors Movers exporter surfaces `Tom's Hardware` at rank #1 and
`Future US` at rank #4 — both publishers being treated as `Org` entities
with high `trend_score`. They rank above Intel (#2), NVIDIA (#3), TSMC (#5)
because they appear in many documents as the *source*, not as a semantically
mentioned entity.

Same pattern likely affects every domain (e.g. Deadline / IndieWire / Variety
in film) but only became visible because Movers exposes the full scored
population, not just the trending top-50.

**Root cause:** The extraction prompt doesn't explicitly tell the LLM to
*not* extract the publication itself as an entity. The publication name
appears at the top of every article it scrapes, so the model treats it as
a salient `Org`.

**Options:**
- Add a negative example to per-domain `system.txt`: "Do not extract the
  publication itself (e.g. 'Tom's Hardware', 'Deadline') as an entity. The
  source is captured separately in `documents.source`."
- Post-extraction filter: maintain a `publishers.yaml` per domain and drop
  entities matching publisher names at import time.
- Use the existing `documents.source` column as a deny-list for entity
  names extracted from that source's articles.

**Impact:** Not a Movers bug — Sprint 14 surfaces this pre-existing noise,
it doesn't create it. Affects Current Landscape view too (publishers
appear in trending top-50). Worth fixing before the Movers UI ships
(Sprint 15) so users don't see "Tom's Hardware" as a #1 mover.

**Waiting on:** Decision on which option above (prompt, post-filter, or
deny-list). Probably the prompt negative-example as the cheapest first
attempt, then post-filter if the prompt-only fix doesn't stick.

---

## Entity Resolution

*(items will accumulate here)*

---

## Trend Scoring & Methodology

> **Active thread:** These items were surfaced by the 2026-06-10 trend-methodology
> and Movers/Landscape review. The decisions, restart runbook, and rationale live in
> **[adr-010-two-domain-restart.md](../architecture/adr-010-two-domain-restart.md)** —
> read that first. Each item below maps to a finding or follow-up in that ADR.

### TREND-1: Bridge score is computed and stored but unused

**Observed:** 2026-06-10 | **Priority:** Medium | **Ref:** ADR-010 review finding (bridge)

`compute_bridge_score` runs for every entity on every pass and the result is
persisted to `trend_history.bridge_score`, but the composite `trend_score`
uses an *activity* proxy (raw 7d mention count) instead — so the structural
signal is paid for and discarded. Decide one of: (a) wire bridge into the
composite, or (b) stop computing it per-run. Either way, `bridge_delta`
(change in bridge score over a 7d window) — the version that would actually
be a leading indicator — remains unbuilt and is the more valuable target if
bridge stays in.

**Where:** `src/trend/__init__.py` (`compute_bridge_score`, `get_trending`).

### TREND-2: Velocity window is not domain-configurable

**Observed:** 2026-06-10 | **Priority:** Medium | **Ref:** ADR-010 review finding (velocity window) + D3 follow-up

Novelty decay λ varies 3.5× across domains (0.02 semiconductors → 0.07 film),
but every domain uses the same hardcoded 7d/7d velocity ratio. A 7-day window
on semiconductors' 18-month process-node storylines mostly measures
publication-schedule noise. Promote the velocity window to a `trend_weights`
key in `domain.yaml` alongside λ. Natural companion to ADR-010 D3's follow-up
(promote the doc budget from `DEFAULT_BUDGET` constant to a `domain.yaml`
key) — same "hardcoded constant → per-domain key" change. The methodology's
planned multi-window blend (7d/14d/30d) is the larger V2 version.

**Where:** `src/trend/__init__.py` (`compute_velocity` window param),
`domains/*/domain.yaml`.

### TREND-3: Corroboration weighting not applied to the Landscape score

**Observed:** 2026-06-10 | **Priority:** Medium | **Ref:** ADR-010 review finding (corroboration); methodology §4.1

The composite `trend_score` cannot distinguish one source mentioning an
entity 20× from 20 independent sources mentioning it once — methodology §4.1's
source-count modifiers (1 src = 0.5×, 3+ = 1.0×, 3+/2+ categories = 1.25×)
remain unimplemented. The substrate now exists: `run_movers.py` already
computes `distinct_sources_7d` per entity. Wire an equivalent per-entity
source-diversity count into `get_trending` and apply the modifier.

**Where:** `src/trend/__init__.py` (`get_trending`); reuse the
`_distinct_sources_7d` query shape from `scripts/run_movers.py`.

### TREND-4: Movers lacks a movement-native score

**Observed:** 2026-06-10 | **Priority:** Low (defer until D10 proof-point) | **Ref:** ADR-010 finding 3 + open thread

`run_movers.py` ranks by the composite `trend_score` (0.4 velocity / 0.3
novelty / 0.3 activity, activity capped at 20), so `rank_delta` measures
movement *within a prominence-weighted ranking* — the same bias Movers was
built to escape. The uncapped `velocity_raw` column and "hide top 50" filter
partially compensate. A "pure movement" score that excludes activity is the
open thread. Recommend deferring until ADR-010 D10's film proof-point shows
whether the prominence bias actually distorts the Movers view in practice.

**Where:** `scripts/run_movers.py` (`_ranks_for_run` ordering).

### TREND-5: Source change log + transition dampening not implemented

**Observed:** 2026-06-10 | **Priority:** Medium | **Ref:** ADR-010 D6 (manual restart dampening); methodology §2.7–2.8

`config/source_changelog.yaml` (methodology §2.8) does not exist, and the
pipeline has no automated transition dampening after feed swaps (§2.7) — so
a velocity spike on the same day a source was added/removed is
indistinguishable from a real trend. ADR-010 D6 handles the *restart*
dampening manually for one event; this item is the standing mechanism for
future swaps. First entries belong in the log on restart day, when dead
feeds are removed (ADR-010 runbook item 2: Go Into The Story, SC Film
Commission).

**Where:** new `config/source_changelog.yaml`; consumed by velocity
calculation in `src/trend/__init__.py`.

---

## Graph Export & Visualization

### GEV-1: Cap bridge entity edge count to prevent artificial centrality

**Observed:** 2026-03-05 | **Priority:** Low (monitor first)

When a bridge entity is admitted to the trending view, ALL its edges to
trending entities are included — not just the minimum set needed to
reconnect isolated nodes. If a bridge entity happens to connect to many
trending entities (e.g., a Tech concept like "transformer" touching 8+
models), it could appear artificially central in the layout.

**Current behavior:** Bridge selection gate is conservative (must connect
2+ trending entities, at least one isolated), so the risk is low at
current graph scale. Node sizing also naturally de-emphasizes bridges
(velocity=0, trend_score=0).

**Possible fix:** After selecting bridge entities, limit each bridge's
edges to only those connecting isolated trending entities (plus one edge
to a non-isolated trending entity for connectivity). Drop edges to
already-connected trending entities.

**Update (2026-03-05):** Bridge entity support was added to the trending view
(commit b64ea8b). Bridge entities that connect 2+ trending nodes (where at least
one is isolated) are now admitted with `isBridge: true` metadata. The cap concern
remains valid — monitor whether any bridge accumulates disproportionate degree.

**Waiting on:** More daily pipeline runs to see whether any bridge entity
accumulates disproportionate degree in practice.

---

## Pipeline & Infrastructure

### PIPE-4: Test suite assumes AI domain; no push CI runs it anyway

**Observed:** 2026-07-19 (Sprint 20.4 session) | **Priority:** Medium

`make test` fails 22 tests under the current `DOMAIN ?= film` default:
~20 in test_extract/test_schema/test_resolve/test_integration/test_llm_eval
assume the AI domain's relation taxonomy (pass with `PREDICTOR_DOMAIN=ai`),
and 2 in test_source_type expect bluesky/reddit ImportErrors but the deps
are installed. Nothing catches this: the only workflow is release.yml
(tag-triggered); push CI was retired with deploy.yml on 2026-07-19.

**Action:** Pin taxonomy-dependent tests to their domain explicitly
(fixture setting PREDICTOR_DOMAIN=ai, not ambient default), fix or drop
the two import-error tests, then decide whether a push-triggered
verify.yml is wanted (uzelhub-web precedent).

### PIPE-3: Cross-document synthesis dropped to zero on 2026-03-27

**Observed:** 2026-03-27 (gist metrics review) | **Priority:** Medium

`funnel_stats` shows the synthesize stage produced 0 LLM calls, 0 corroborated
entities, and 0 inferred relations on 2026-03-27 — after being active Mar 23–26
(4–8 LLM calls/day, 3–20 entities corroborated). May be transient or may indicate
a regression in entity overlap thresholds after the batch pipeline transition.

**Action:** Check the next 2–3 runs. If synthesis stays at zero, investigate whether
the entity overlap pool is being filtered out by the batch collect path.

### PIPE-1: Extract stage timeout on large backlog

**Observed:** 2026-02-22 | **Priority:** Medium

When 358 backlog docs are bundled, the extract stage hits the 1800s (30 min)
timeout after processing only ~13 documents. Each cheap-model extraction
takes 80–150s, so the timeout caps throughput at ~12–20 docs per run.

**Options:**
- Raise extract timeout (but pipeline total time grows proportionally)
- Limit backlog batch size in `build_docpack.py` (e.g., 50 per run)
- Process backlog in chunks across multiple daily runs (self-draining)

**Current workaround:** The pipeline continues to import/resolve/export after
the timeout, and subsequent runs pick up where the backlog left off since
`--skip-existing` prevents re-extracting completed docs.

### PIPE-2: VentureBeat persistent 429 rate limiting

**Observed:** 2026-02-22 | **Priority:** Low

All 7 VentureBeat articles returned HTTP 429 (Too Many Requests). The ingest
stage makes no retry attempt by design (see `fetch_once()`). VentureBeat
articles remain in `status='error'` and are never retried on subsequent runs.

**Possible fix:** Add a `repair_data.py` option to reset retryable errors
(429, 5xx) back to a state that allows re-fetching on the next run.

---

## Sources & Ingestion

### SRC-3: Go Into The Story — 10 fetch errors per day

**Observed:** 2026-03-27 (gist metrics review) | **Priority:** High

Every daily run fetches 10 items from Go Into The Story, and all 10 are fetch
errors — consistently since at least 2026-03-20. Zero usable docs produced.
Feed URL may be dead, restructured, or blocking our User-Agent.

**Action:** Diagnose with `python scripts/diagnose_feeds.py`. If unreachable,
remove from `domains/film/feeds.yaml` or replace with an alternative screenwriting
blog.

**Update 2026-07-19 (source audit):** the fetch problem self-resolved — 80
docs ingested through 07-01, feed verified live from the pipeline UA. The
real problem moved downstream: **0 of 80 docs extracted**. Investigate
selection/extraction yield during the epoch-2 dampening window (ADR-010's
"known dead" claim about this feed was wrong).

### ~~SRC-4: SC Film Commission — unreachable since 2026-03-17~~ — DONE

**Resolved 2026-07-19 (source audit):** zero docs ever delivered since the
03-18 enable. Disabled in `domains/film/feeds.yaml` with a dated reason;
logged in `config/source_changelog.yaml`.

### SRC-6: USPTO patents feed — enabled, silent, zero docs ever

**Observed:** 2026-07-19 (source audit) | **Priority:** Medium

The USPTO Semiconductor Patents feed (type `patents`,
`src/ingest/patents.py`) was enabled since April and never delivered a
single document — the worst class of feed failure (enabled + silent).
Disabled 2026-07-19 at the audit batch.

**Action:** Diagnose the fetcher (API key? CPC query shape? rate limit
swallowed?) and re-enable only with a verified first delivery. The
feed-level zero-docs alerting that would have caught this now exists
(`scripts/check_staleness.py`), but only for feeds that have delivered
before — never-delivered feeds still need a post-enable check.

### SRC-5: Bluesky SE Film — very low extraction yield

**Observed:** 2026-03-27 (gist metrics review) | **Priority:** Low

Bluesky SE Film produces 0.7 relations/doc vs the source average of ~14. This is
expected — Bluesky posts are short and low-density. The source still provides
velocity signal (108 docs ingested). May not be worth extraction budget slots.

**Consideration:** Lower selection score weight for bluesky source type, or exclude
from extraction budget and keep as ingestion-only velocity signal.

### SRC-1: Anthropic Blog feed unreachable

**Observed:** 2026-02-22 | **Priority:** Low

The Anthropic Blog RSS feed (`https://www.anthropic.com/news/rss.xml`) was
unreachable during the pipeline run. This is intermittent — the feed has
worked in previous runs. Monitor for persistent failure.

### SRC-2: Verify feed freshness mid-day

**Observed:** 2026-02-22 | **Priority:** Medium

The 03:51 UTC pipeline run found 0 new articles across 11 feeds. This may
be correct (early morning, feeds hadn't rotated) but needs verification.

**Diagnostic:** Run `python scripts/diagnose_feeds.py` during business hours
to confirm feeds are returning new entries. If consistently showing 0 new,
investigate whether feed caching or the dedup mechanism is too aggressive.

---

## Graph Export & Visualization

### GEV-2: Search result forward/backward navigation

**Observed:** 2026-03-14 | **Priority:** Medium

When the search bar finds multiple matching nodes, there is no way to cycle
between them. Add forward/backward buttons (or keyboard shortcuts like
Ctrl+G / Ctrl+Shift+G) to step through search results one at a time, flying
the camera to each match in sequence.

**Files likely affected:** `web/js/search.js` (result iteration state),
`web/css/components/toolbar.css` (nav button styling)

### GEV-3: Slower pan/zoom animation timing

**Observed:** 2026-03-14 | **Priority:** Low

Pan and zoom animations (fly-to on search, fit-to on double-tap, neighborhood
zoom) happen too quickly. Increase `cy.animate()` duration parameters for a
more deliberate feel. Consider making duration proportional to travel distance
so short hops are snappy but long traversals feel smooth.

**Files likely affected:** `web/js/app.js`, `web/js/search.js` (anywhere
`cy.animate` is called)

### GEV-4: Shortest path discovery ("Six Degrees")

**Observed:** 2026-03-14 | **Priority:** Low (post-V1)

Select two nodes and show the shortest path between them, highlighting
intermediate entities and edges. Would surface non-obvious connections
(e.g., how an org relates to a model through 3 intermediate entities).

**Implementation:** Cytoscape.js has built-in `eles.dijkstra()` and
`eles.bfs()` for path-finding. UI would need a "select second node" mode
(e.g., shift-click after selecting the first node) and a path highlight
style. Could display path length and intermediate entity names in the
detail panel.

**Inspiration:** Oracle of Bacon / Six Degrees of Kevin Bacon.

### GEV-5: Relationship arrow direction incorrect for some verbs

**Observed:** 2026-03-21 | **Priority:** Medium

In the detail panel relationship list, the arrow direction (→ / ←) is
incorrect for some relationship verbs. The top arrow direction is correct
but others are inverted — e.g., showing "A → DIRECTED_BY → B" when the
semantic direction should be reversed.

**Root cause:** `renderRelationshipList()` in `panels.js` determines
direction by comparing `edge.source().id()` to `node.id()`, which reflects
graph storage order, not semantic direction. Some relation types have
inverted source/target conventions.

**Likely fix:** Add a `PASSIVE_RELATIONS` set (e.g., `DIRECTED_BY`,
`DISTRIBUTED_BY`, `PUBLISHED_BY`) that reverses the display arrow.
Alternatively, store canonical direction in the edge data during export.

**Files likely affected:** `web/js/panels.js` (`renderRelationshipList`)

**Checked 2026-07-11:** No `PASSIVE_RELATIONS` set or canonical-direction
field found in `panels.js` — still unimplemented, no target date set.

### GEV-6: Entity spotlight card (top-drop, forward/backward navigation)

**Observed:** 2026-03-21 | **Priority:** Medium | **Target:** 2026-03-22 (missed — still unbuilt as of 2026-07-11)

A second presentation mode for trending entities: a single-entity card
that drops from the top of the screen with a subtle bounce animation.
Shows one entity at a time with forward/backward navigation (card UI).

**Behavior:**
- Drops from top center, subtle animated bounce on entry
- Displays: entity name, type badge, velocity, full narrative
- Forward/backward arrows to step through trending entities
- Coexists with the hot list panel (different entry point)
- Keyboard: arrow keys cycle through entities when card is focused

**Design note:** This is a second panel style — keep the existing hot list
panel as-is. The spotlight card is a complementary view for focused
exploration of one entity at a time.

**Files likely affected:** New `web/js/spotlight.js`, new CSS in
`web/css/components/spotlight.css`, toolbar button or keyboard trigger in
`web/js/app.js`

### GEV-11: Toolbar right-side overflow — reorganize mixed-function controls

**Observed:** 2026-03-24 | **Priority:** Low (post-UI-strategy decision)

The toolbar right side is getting crowded with a mix of function categories:
UI interactions (theme, navigator), settings/config (domain), help, and
feature entry points (What's Hot). These are not naturally grouped and will
only get worse as features are added.

**Possible approaches to explore:**
- Overflow menu ("⋯" or gear icon) that collapses lower-priority controls
- Grouped icon clusters with subtle dividers (interactions | settings | help)
- Sidebar/drawer for settings-class controls, leaving only action controls in toolbar
- Right-click or long-press toolbar for meta-options (mobile pattern)

**Constraint:** No action until a broader UI strategy decision is made (e.g.,
Sprint 9 or later). This item tracks the problem and options so it's not lost.

**Files likely affected:** `web/index.html`, `web/css/components/toolbar.css`,
`web/js/app.js` (toolbar init)

### GEV-12: What's Hot toolbar button is a poor visual representation

**Observed:** 2026-03-24 | **Priority:** Low (blocked on UI strategy)

The fire emoji / icon used as the What's Hot entry point is a weak representation
of the feature — it doesn't clearly signal "trending entities" to a new user.

**No action until:** Broader toolbar reorganization decision (GEV-11) is made.
Redesigning this in isolation would likely be undone when the toolbar is
restructured. Hold here.

---

## Project Organization

### ORG-1: Domain-specific documentation space

**Observed:** 2026-03-14 | **Priority:** Low

Move domain-specific documentation into each domain's directory
(e.g., `domains/biosafety/docs/`). Currently all docs live in the
top-level `docs/` directory which is domain-agnostic. As domains
accumulate their own operational history, feed notes, and prompt
tuning observations, a per-domain docs space would keep things
organized.

**Consideration:** Top-level `docs/` stays for framework-level docs
(architecture, methodology, schema). Domain directories get their
own `docs/` for domain-specific operational content.

---

## Resolved

### ~~Biosafety select agents should be red~~ — DONE

**Resolved:** 2026-03-13. SelectAgent nodes now use red (#F43F5E) in biosafety
domain config. See `web/data/domains/biosafety.json`.

### ~~EXT-6: Biosafety specialist prompt missing required relation field specs~~ — DONE

**Resolved:** 2026-03-08. `system.txt`/`single_message.txt` prompts updated to
explicitly list required relation fields, matching the AI domain's structure.
Fixed the 0/5 specialist validation pass rate.

### ~~GEV-7: Panel text contrast — hardcoded grays~~ — DONE

**Resolved (found 2026-07-11, undated in code):** `panels.js` now uses semantic
utility classes (`text-secondary`, `bg-secondary`, etc.) mapped to
`--color-text-secondary` / `--color-bg-secondary` in `utilities.css`. No raw
`text-gray-*`/`bg-gray-*` classes remain.

### ~~GEV-8: Node tap handler fires during flyToHotNode~~ — DONE

**Resolved (found 2026-07-11, undated in code):** Both the tap handler and
`flyToHotNode` now route through a single shared `navigateToNode()` in
`panels.js` (select → highlight → zoom → panel), eliminating the double
panel-open race by construction rather than a guard flag.

### ~~GEV-9: Node visibility when panel overlaps graph~~ — DONE

**Resolved (found 2026-07-11, undated in code):** `zoomToNode()` in `panels.js`
now offsets the camera target via `getPanelOffset(targetZoom)` — the "A" fix
option from the original writeup.

### ~~GEV-10: Minimap jumps when panels open/close~~ — DONE

**Resolved (found 2026-07-11, undated in code):** `.navigator-container` in
`cytoscape.css` now has `transition: ... right var(--duration-slow) ease,
bottom var(--duration-slow) ease` — smooth repositioning instead of a jump.
