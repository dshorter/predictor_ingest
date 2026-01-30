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
