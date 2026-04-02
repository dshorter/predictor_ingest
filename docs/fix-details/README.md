# Fix Details - Documentation Index

This folder contains detailed documentation of issues encountered and resolved during development.

---

## fcose Layout Issue (January 2026)

**Problem:** fcose layout appeared to produce poor results (tight clustering) compared to the cose fallback.

**Root Cause:** fcose was **never actually loading**. Two missing CDN dependencies (`layout-base`, `cose-base`) caused a silent crash, and the detection logic checked for a nonexistent global variable instead of testing layout availability.

**Resolution:** Fixed dependency chain and detection. fcose now runs properly with `nodeSeparation: 75` as the key spectral phase parameter.

### What Actually Happened

1. **fcose CDN script crashed on load** - missing `layout-base` and `cose-base` dependencies
2. **Detection checked wrong thing** - looked for `cytoscapeFcose` global (doesn't exist when auto-registered)
3. **Silent fallback to cose** - every "fcose test" was actually running cose
4. **"Perfect" before screenshot** was just lucky random starting positions before any layout algorithm ran
5. **"Algorithm mismatch" conclusion was wrong** - fcose was never tested, so comparing fcose vs cose was comparing cose vs cose

### The Fix (3 parts)

1. Added CDN dependencies in correct order: `layout-base` → `cose-base` → `cytoscape-fcose`
2. Changed detection to test layout availability instead of checking global variables
3. Added `nodeSeparation: 75` parameter (controls spectral phase spacing)

### Documents

1. **[FCOSE_LAYOUT_ANALYSIS.md](FCOSE_LAYOUT_ANALYSIS.md)** - Comprehensive analysis
   - Root cause investigation
   - Parameter research
   - Decision log

2. **[FCOSE_FIX.md](FCOSE_FIX.md)** - Original registration error fix

### Screenshots

- `before_fcode_fix.png` - Lucky random positions (cose fallback, error interrupted init)
- `after_fcode_fix.png` - cose with tight params (fcose still not loading)
- `after-revert.png` - cose with adjusted params (still not fcose)
- `latest.png` - fcose actually running with nodeSeparation: 75

---

## Key Takeaways

**The Real Lesson:**
- "It's not working" and "it's the wrong algorithm" are different diagnoses
- Silent failures (missing dependencies) can lead to wrong conclusions
- Always verify the tool is actually running before evaluating its output
- The CDN dependency chain matters: `layout-base` → `cose-base` → `fcose`

---

## Timeline

- **2026-01-27 Early:** Discovered layout degradation after fcose registration fix
- **2026-01-27 Mid:** Root cause analysis (incomplete - didn't check if fcose actually loaded)
- **2026-01-27 Late:** Concluded "algorithm mismatch" - switched to cose
- **2026-01-29:** Opus session discovered fcose had never loaded (missing CDN deps)
- **2026-01-29:** Added layout-base + cose-base dependencies
- **2026-01-29:** Fixed detection (test layout availability vs check global var)
- **2026-01-29:** fcose runs for first time ever - immediately better results

---

**Status:** RESOLVED - fcose working with parameter tuning in progress

---

## Stale `__pycache__` on VPS Deployment (February 2026)

**Problem:** After updating `DEFAULT_DELAY` from `1.0` to `10.0` in
`src/ingest/rss.py`, the VPS kept using the old value. Import raised
`AttributeError: module 'ingest.rss' has no attribute 'DEFAULT_DELAY'`.

**Root Cause:** Python loaded a stale `.pyc` from `__pycache__/` compiled from
an older revision (before `DEFAULT_DELAY` existed at module level). The
editable install (`pip install -e .`) didn't invalidate the cache.

**Resolution:** Nuke `__pycache__` dirs + re-run `pip install -e .`.

**Document:** [STALE_PYCACHE_FIX.md](STALE_PYCACHE_FIX.md)

**Key Takeaway:** When a module attribute that exists in the `.py` file raises
`AttributeError`, the first suspect is stale bytecode cache, not the source.

**Status:** RESOLVED — 2026-02-18

---

## Daily Pipeline Stall & Quality Scoring Overhaul (February 2026)

**Problem:** Pipeline processed the same 3 TechCrunch articles on every run.
368 cleaned documents were permanently stranded. The cheap model (gpt-5-nano)
scored q=0.82–1.00 on every extraction, triggering zero escalations to the
specialist model.

**Root Causes:**
1. Docpack builder filtered by exact `published_at` date — backlog docs with
   older dates never matched any daily run
2. Extract stage loaded stale docpack files from previous runs
3. Quality scoring thresholds were trivially easy for any model to max out

**Resolution:**
1. Backlog fallback in `build_docpack.py` with 6-month cutoff
2. Pipeline tracks docpack output count; skips extract on empty docpack
3. Quality scoring overhauled: raised thresholds, added relation type diversity
   signal (25% weight), added confidence variance penalty

**Documents:**
- [pipeline-stall-scoring-overhaul.md](pipeline-stall-scoring-overhaul.md) — Root causes and code-level fixes
- [2026-02-22-session-research-summary.md](2026-02-22-session-research-summary.md) — Full research session: investigation arc, simulated scoring benchmarks, documentation overhaul

**Key Takeaway:** When a scoring function produces scores that cluster near the
maximum, the thresholds are set to "minimum acceptable" rather than "target."
Proportional scoring against meaningful targets is more discriminating than
binary pass/fail against low floors.

**Status:** RESOLVED — 2026-02-22

---

## EXT-4: Cheap Model Escalation Analysis & Prompt Tuning (February 2026)

**Problem:** After the scoring overhaul, the cheap model (gpt-5-nano) triggered
escalation on 80% of documents — making the cheap-first strategy more expensive
than running the specialist directly.

**Root Causes:** Orphan endpoints (dominant), bimodal evidence fidelity, zero-value
extractions, and high-confidence fabricated evidence. All traced to the nano model's
weaker instruction-following, not to gate miscalibration.

**Resolution:** Three lightweight prompt additions to the system prompt's Critical
Rules section — explicit orphan constraint, evidence grounding, minimum relations.
Designed to be short and clear enough not to overload the nano model's context.

**Document:** [ext4-cheap-model-escalation-analysis.md](ext4-cheap-model-escalation-analysis.md)

**Key Takeaway:** Scoring and gates can diagnose quality problems, but they can't
fix them — that requires prompt tuning. However, prompt tuning on a cheap model has
limited headroom. Adding constraints must be balanced against the model's capacity
to follow them all simultaneously.

**Status:** IN PROGRESS — prompt tuning applied 2026-02-25, measuring over next ~100 extractions

---

## CI/CD Disk Exhaustion Saga (March 2026)

**Problem:** GitHub Actions CI/CD runs began failing with disk space errors,
preventing deployments for ~24 hours across PRs #141–#149.

**Root Cause:** The deploy workflow's `docker build` step used a stale context
referencing `/opt/ai-agent-platform/docker-compose.yml` — an unrelated Docker
project on the VPS. Docker was pulling in a 664MB build context from a project
that had nothing to do with predictor_ingest.

**Investigation timeline (7 PRs over ~24 hours):**
1. Disabled pip cache (`--no-cache-dir`) — no effect
2. Removed .NET/Android/GHC/CodeQL toolcache — marginal improvement
3. Added `docker image prune` — accidentally killed the `appleboy/ssh-action`
   container used for deployment
4. Added `.dockerignore` — discovered the real problem was the Docker context path
5. Traced to stale Docker reference pulling in an unrelated project (664MB)
6. Reverted all deploy fixes back to known working state
7. Final fix: stripped deploy workflow to just checkout + SSH (removed Python/pip/pytest
   from deploy entirely); switched to `jlumbroso/free-disk-space` action for CI

**Key Takeaways:**
- Multiple incremental fixes obscured the root cause. Each "improvement" masked
  the real problem and introduced new side effects.
- When disk space is the issue, investigate *what* is consuming it before optimizing
  caching. The 664MB Docker context was the dominant factor.
- The deploy workflow didn't need Python/pip/pytest — it just needed to SSH into the
  VPS. Simplifying the workflow was the real fix.
- `docker image prune` in CI can kill action containers (e.g., `appleboy/ssh-action`)
  that are still running.

**Status:** RESOLVED — 2026-03-10

---

## Orphan Edges in Graph Export (March 2026)

**Problem:** Graph export produced edges referencing nodes that had been filtered
out by view or date range, crashing the Cytoscape client with "target node not found"
errors.

**Root Cause:** The export pipeline filtered nodes (by view criteria or date range)
but did not strip edges whose source or target was no longer in the filtered node set.

**Resolution:** Added orphan edge stripping to both `scripts/run_export.py` and
`scripts/run_trending.py` — after node filtering, any edge whose source or target
is not in the final node set is removed before writing the JSON output.

**Key Takeaway:** Whenever graph nodes are filtered, edges must be filtered in the
same pass. This applies to every export path (mentions, claims, dependencies, trending).

**Status:** RESOLVED — 2026-03-05

---

## Trending View Bridge Entity Isolation (March 2026)

**Problem:** The trending view was rejecting "bridge" entities — non-trending entities
that connect trending nodes to each other. Without bridges, trending nodes that shared
connections through intermediate entities appeared as isolated clusters.

**Root Cause:** The trending node selection algorithm only admitted entities with
trending scores above threshold. Bridge entities (which may not be trending themselves
but serve as connectors) were excluded, fragmenting the graph.

**Resolution:** Added bridge entity support to the trending node selection: after
selecting trending nodes, identify non-trending entities that connect 2+ trending nodes
(where at least one would otherwise be isolated). Admit these as bridge nodes with
`isBridge: true` metadata so the UI can style them differently (e.g., smaller, no
velocity halo).

**Key Takeaway:** Trend-filtering a graph requires both a relevance filter (trending
score) and a connectivity filter (bridge detection). Pure relevance filtering produces
fragmented views that lose the "why it matters" context.

**Status:** RESOLVED — 2026-03-05

---

## Mobile Multi-Domain Routing Bugs (March 2026)

**Problem:** After Sprint 6B added biosafety domain support, the mobile web client
had five separate bugs related to domain routing and initialization.

**Failure modes:**
1. Mobile didn't load domain config or rebind filter panel entity types
2. Safari "string did not match pattern" error on date parsing during init
   (ISO date format with timezone offset)
3. AI sample data shown when viewing non-AI domains (hardcoded sample data path)
4. Mobile `?domain=biosafety` URL parameter ignored entirely (domain derived from
   `AppState` which defaulted to AI)

**Resolution:** Each was fixed independently:
1. Domain config fetch + filter panel rebuild wired into mobile init
2. Date parsing normalized to strip timezone suffixes before `new Date()`
3. Sample data path made domain-aware
4. URL parameter made authoritative source for domain selection on mobile

**Key Takeaway:** When adding multi-domain support, test the mobile client separately —
it has its own initialization path that doesn't share code with desktop. Desktop domain
routing can work perfectly while mobile silently falls back to defaults.

**Status:** RESOLVED — 2026-03-09

---

## Biosafety Extraction Template Bugs (March 2026)

**Problem:** First biosafety domain extractions failed validation at multiple points.

**Failure modes (in order of discovery):**
1. **Missing relation field specs** (EXT-6): Biosafety prompts didn't explicitly list
   required relation fields, causing LLM to omit `rel`, `source`, or `target` properties
2. **Evidence field type mismatch:** LLM returned evidence as a single object instead of
   an array, failing schema validation
3. **Python format string collision:** Literal `{` and `}` characters in prompt templates
   (used for JSON examples) were interpreted as Python `.format()` placeholders, causing
   `KeyError` on cheap model extraction path
4. **Missing normalization entries:** `PUBLISHED_BY` relation and `day` date resolution
   not in biosafety domain's normalization maps

**Resolutions:**
1. Updated biosafety prompts to match AI domain's explicit field-by-field specification
2. Schema validation updated to coerce single evidence objects to arrays
3. Escaped literal braces in prompt templates (`{{` / `}}`)
4. Added `PUBLISHED_BY` and `day` to biosafety `domain.yaml` normalization maps

**Key Takeaway:** When creating extraction prompts for a new domain, start by copying
the working domain's prompt structure verbatim, then customize vocabulary. The structure
(field specs, JSON examples with properly escaped braces, critical rules section) is
as important as the domain-specific content. The `domains/_template/` scaffolding should
include prompt templates with all structural elements pre-populated.

**Status:** RESOLVED — 2026-03-09

---

## Biosafety Normalization Gap & New Domain Lessons (March 2026)

**Problem:** Biosafety domain had 32% nano accept rate (vs ~70% for AI domain).
22 escalations to Sonnet in a single batch. Health report showed orphan endpoints
and unknown relation types as top failure modes.

**Root Cause:** The biosafety `domain.yaml` normalization map had good semantic
synonyms (OVERSEES→REGULATES, SUPERVISES→REGULATES) but was completely missing
tense variants (past tense, gerund, base form) that nano produces regardless of
domain. The AI domain had accumulated these through months of iterative tuning.
The biosafety domain was new and hadn't gone through that cycle yet.

**What was NOT the problem:** Gate thresholds (identical between domains),
framework code (domain-agnostic), the biosafety ontology itself (well-designed),
or the LLM model (same behavior in both domains).

**Resolution:**
1. Added 34 manual tense entries to biosafety normalization (immediate fix)
2. Built `scripts/generate_normalization.py` — auto-generates tense variants from
   any domain's canonical relation list (prevents recurrence)
3. Updated `domains/_template/` to include generator step in setup workflow
4. Documented the "Shakespeare rule" in lessons learned

**Documents:**
- [new-domain-lessons-learned.md](new-domain-lessons-learned.md) — Full analysis,
  the two-category framework (domain voice vs LLM grammar), setup checklist
- `scripts/generate_normalization.py` — Tense variant generator
- `scripts/test_normalization_coverage.py` — Normalization coverage analyzer
- `scripts/compare_normalization.py` — Before/after quality gate comparison

**Key Takeaway:** Separate "domain modeling" (creative, emergent — entity types,
canonical relations, semantic synonyms, scoring weights) from "LLM output
handling" (mechanical, predictable — tense variants, gerunds, \_BY inversions).
Automate the latter. Let the former emerge from the source material.

**Status:** RESOLVED — 2026-03-16

---

## Trending Node Flame Glow (April 2026)

**Issue:** [dshorter/predictor_ingest#226](https://github.com/dshorter/predictor_ingest/issues/226)

**Problem:** Trending nodes on the graph had no visual connection to the What's Hot
panel. The hot panel used an animated flame gradient border (red-orange → gold), but
graph nodes used a static type-colored underlay halo only for high-velocity nodes
(velocity > 2). Users couldn't visually correlate panel items with their graph nodes.

**What Changed:**
1. **Animated flame glow** on trending graph nodes — cycles through the same
   red-orange (`#FF4500`) → dark orange (`#FF8C00`) → gold (`#FFD700`) gradient
   as the hot-panel border, with matching 3-second animation cycle
2. **Correct trending criteria** — glow targets the same top-N entities as the
   What's Hot panel (ranked by `trend_score`, the composite of 40% velocity +
   30% novelty + 30% activity), not a naive velocity > 0 filter
3. **Design tokens** — added `--flame-red`, `--flame-orange`, `--flame-gold` to
   `tokens.css` (light + dark themes), read via `getCSSVar()` in `styles.js`
4. **No polling** — node collection happens once at startup since data is
   batch-updated overnight; only the underlay color animates per frame
5. **Accessibility** — `prefers-reduced-motion` gets a static warm glow instead

**Files Modified:**
- `web/js/styles.js` — `startFlameGlow()`, `stopFlameGlow()`, `_collectHotNodes()`
- `web/js/app.js` — wired `startFlameGlow()` into init after What's Hot panel
- `web/css/tokens.css` — flame color design tokens

**Key Takeaway:** When adding visual effects that echo an existing UI element,
reuse the exact same data source (here `getHotList()`) rather than approximating
the criteria with a simpler selector. The flame colors should also come from the
same tokens so they stay in sync if the palette changes.

**Status:** RESOLVED — 2026-04-02
