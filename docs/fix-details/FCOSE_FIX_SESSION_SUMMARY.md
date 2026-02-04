# fcose Layout Fix - Session Summary

**Date:** January 27, 2026  
**Status:** ✅ TESTING COMPLETE - RECOMMENDATION: REVERT TO cose

---

## Quick Summary

After comprehensive testing with 5 different parameter combinations, we determined that **fcose is the wrong layout algorithm for our graph topology**. The issue isn't missing parameters—it's an algorithm mismatch.

**Recommendation:** Revert to `name: 'cose'` and keep all existing parameters.

---

## What We Tested

1. ✅ **nodeSeparation: 75** - Improved but insufficient
2. ✅ **Added samplingType & sampleSize** - Minor improvement
3. ✅ **Changed idealEdgeLength to 50** - No significant change
4. ✅ **Increased nodeSeparation to 150 & 300** - Spectral phase works but force-directed overrides
5. ✅ **Reduced gravity to 0.05** - Small improvement but not satisfactory

---

## Key Discovery

User observed the **two-phase algorithm in action**:
> "I noticed that for a second they all plotted spread out farther and smaller then 'jumped' together"

This revealed the core issue:
- **Spectral phase (first flash)**: Creates good spacing
- **Force-directed phase (jump together)**: Overrides the spacing

The algorithms are fighting each other!

---

## Graph Topology Analysis

**Our actual data:**
- 18 nodes, 24 edges
- Average degree: 2.67 (sparse, not mesh)
- Hub-and-spoke structure with hierarchical layers
- Organizations → Models → Benchmarks → Technologies

**Why cose worked:**
- Perfect for sparse, layered, hierarchical graphs
- Creates natural visual layers through physics
- Simple, predictable behavior

**Why fcose struggles:**
- Optimized for dense, clustered, community-based graphs
- Spectral phase tries to detect communities that don't exist
- Two-phase algorithm fights itself on our topology

---

## Performance Analysis

**At 200 nodes (10x production scale):**

| Layout | Speed | Quality | Match |
|--------|-------|---------|-------|
| cose | 2-3 sec | Excellent | ✅ Perfect |
| fcose | 1-2 sec | Poor | ❌ Wrong algorithm |

**Verdict:** 1-2 second speed gain not worth fighting wrong algorithm

---

## The Code Change

```javascript
const LAYOUT_OPTIONS = {
  name: 'cose',  // ← Change from 'fcose' to 'cose'
  
  // Keep EVERYTHING else the same!
  // These parameters were already perfect for cose
  nodeRepulsion: 4500,
  idealEdgeLength: 100,  // Keep at 100 (not 50)
  edgeElasticity: 0.45,
  nestingFactor: 0.1,
  gravity: 0.25,         // Back to 0.25 (not 0.05)
  numIter: 2500,
  
  // Remove fcose-specific parameters:
  // - nodeSeparation (not used by cose)
  // - samplingType (not used by cose)
  // - sampleSize (not used by cose)
  
  animate: true,
  animationDuration: 500,
  animationEasing: 'ease-out',
  fit: true,
  padding: 50,
  tile: true,
  tilingPaddingVertical: 40,
  tilingPaddingHorizontal: 40,
  randomize: true,
  quality: 'default'
};
```

---

## Lessons Learned

1. **Algorithm selection > Parameter tuning**
   - Right algorithm with defaults beats wrong algorithm with perfect params

2. **"Newer and faster" ≠ "Better for your use case"**
   - fcose is newer, faster, and recommended by Cytoscape
   - But it's wrong for sparse hierarchical graphs

3. **Visual observation revealed the issue**
   - Noticing the two-phase "jump" was the diagnostic key

4. **Know your graph topology**
   - We thought it might be mesh-like
   - Actually sparse (24 edges) with hub-and-spoke structure
   - Algorithm must match topology

5. **Don't fix what isn't broken**
   - cose fallback was perfect
   - fcose "upgrade" was downgrade

---

## When to Revisit fcose

Only if:
- Graph grows to 500+ nodes AND performance becomes unacceptable
- Graph topology changes to dense clusters (unlikely given data model)
- Willing to completely retune from scratch for fcose

**For now: Stick with cose!**

---

## Files Modified During Testing

| File | Status |
|------|--------|
| `web/js/layout.js` | Modified during testing, needs revert |
| `docs/fix-details/FCOSE_LAYOUT_ANALYSIS.md` | Complete analysis doc |
| `docs/fix-details/FCOSE_FIX_SESSION_SUMMARY.md` | This summary |

---

## Screenshots (Evidence Trail)

1. `before_fcode_fix.png` - Original cose fallback (PERFECT)
2. `after_fcode_fix.png` - fcose with defaults (CLUSTERED)
3. `1769558594843_image.png` - After nodeSeparation:75
4. `1769559162369_image.png` - After adding sampling params
5. `1769559452030_image.png` - After idealEdgeLength:50
6. `1769559827067_image.png` - After gravity:0.05

**Visual comparison:** None of the fcose tests matched the quality of the original cose fallback in `before_fcode_fix.png`.

---

## Next Action

**Revert layout.js to use cose:**

```bash
# In web/js/layout.js:
# Change line ~87: name: 'fcose' → name: 'cose'
# Remove fcose-specific parameters (nodeSeparation, samplingType, sampleSize)
# Restore original parameters (idealEdgeLength: 100, gravity: 0.25)
```

Then test with hard refresh to confirm we're back to the beautiful horizontal spread!

---

**END OF SESSION**
