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
