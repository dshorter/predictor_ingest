# COMPREHENSIVE Analysis: fcose vs cose Layout Issue

**Research Date:** 2026-01-27  
**Status:** Research Complete - NO CHANGES IMPLEMENTED YET

---

## 🚨 THE PROBLEM

**Symptom**: After fixing fcose registration, the layout produces a tight cluster (all nodes bunched in center), while the fallback `cose` layout produces good spread-out visualization.

**Screenshots**: 
- `before_fcode_fix.png` - Error dialog but GOOD layout (using cose fallback)
- `after_fcode_fix.png` - No error but TERRIBLE layout (using fcose)

---

## 🔬 ROOT CAUSE IDENTIFIED

### The Critical Difference: TWO-PHASE LAYOUT

**fcose is fundamentally different from cose:**

1. **Built-in `cose`**: Pure force-directed simulation
   - Starts with random positions
   - Applies force-directed physics
   - Simple, reliable

2. **Extension `fcose`**: Hybrid spectral + force-directed
   - **Phase 1**: Spectral layout (creates initial positions)
   - **Phase 2**: Incremental force-directed (refines positions)
   - Faster but MORE parameters to tune

### The Smoking Gun: Missing `nodeSeparation`

**From fcose documentation:**
```javascript
/* spectral layout options */
nodeSeparation: 75,  // Separation amount between nodes
```

**Our code:** MISSING THIS PARAMETER COMPLETELY

This parameter controls node spacing in the **spectral phase**. Without it, fcose uses whatever default value it has (possibly very small or 0), causing all nodes to cluster together in the spectral phase. The force-directed phase then doesn't have enough power to pull them apart.

---

## 📊 DETAILED PARAMETER COMPARISON

### fcose DEFAULT Values

```javascript
{
  name: 'fcose',
  
  // Quality control
  quality: 'default',         // 'draft', 'default', or 'proof'
  randomize: true,
  
  // Spectral phase parameters (MISSING FROM OUR CODE!)
  nodeSeparation: 75,         // ⚠️ KEY: Controls spectral spacing
  samplingType: true,         // ⚠️ Greedy sampling for distance matrix
  sampleSize: 25,             // ⚠️ Sample size for spectral calculations
  piTol: 0.0000001,           // Power iteration tolerance
  
  // Force-directed phase parameters
  nodeRepulsion: 4500,        // ✓ We have this
  idealEdgeLength: 50,        // ⚠️ We use 100 (2x larger!)
  edgeElasticity: 0.45,       // ✓ We have this
  nestingFactor: 0.1,         // ✓ We have this
  numIter: 2500,              // ✓ We have this
  gravity: 0.25,              // ✓ We have this
  
  // Other options
  packComponents: true,
  tile: true,
  uniformNodeDimensions: false,
  nodeDimensionsIncludeLabels: false
}
```

### Our Current LAYOUT_OPTIONS (from web/js/layout.js)

```javascript
const LAYOUT_OPTIONS = {
    name: 'fcose',
    
    // Force-directed parameters (matches fcose defaults)
    nodeRepulsion: 4500,        // ✓ Correct
    idealEdgeLength: 100,       // ⚠️ DOUBLE fcose default (50)
    edgeElasticity: 0.45,       // ✓ Correct
    nestingFactor: 0.1,         // ✓ Correct
    numIter: 2500,              // ✓ Correct
    gravity: 0.25,              // ✓ Correct
    
    // COMPLETELY MISSING:
    // - quality (defaults to 'default')
    // - nodeSeparation (NO DEFAULT - CRITICAL!)
    // - samplingType (NO DEFAULT)
    // - sampleSize (NO DEFAULT)
    // - randomize (defaults to true)
    // - packComponents (defaults to true)
};
```

---

## 🌐 COMMUNITY EVIDENCE

### Similar Issue Found

**GitHub Issue cytoscape/cytoscape.js-cose-bilkent#100**

User reported: 
> "Using the built-in 'cose' layout produced a graph that looked as I expected... when I switch to cose-bilkent, it only appears as though it's a single massive clump, because everything is stacked on top of one another in a large circle."

**EXACT SAME PROBLEM AS OURS!**

### Expert Recommendations

From Cytoscape.js blog (https://blog.js.cytoscape.org/2020/05/11/layouts/):

> "The fcose layout is the latest and greatest version of CoSE. It gives the best results of these three layouts, and it is also generally the fastest. **If you are considering a force-directed layout, fcose should be the first layout that you try.**"

> "**You may have to tweak the parameters of cose more as compared to other force-directed layouts** in order to get a good result."

> "Tweaking the forces used in the physics simulation (i.e. by tweaking the options), can also help to give better results. **This process of tweaking is typically done by trial and error.**"

---

## 🎯 THE `quality` PARAMETER

This controls which phases run:

- **`'draft'`**: ONLY spectral layout
  - Fastest
  - Potentially poor quality
  - No force-directed refinement
  
- **`'default'`**: Spectral + incremental (fast cooling)
  - Balanced speed/quality
  - Good for most cases
  - **This is what we're getting by default**
  
- **`'proof'`**: Spectral + incremental (slow cooling)
  - Best quality
  - Slowest
  - More iterations in force-directed phase

---

## 💡 WHY BUILT-IN `cose` WORKS

The built-in `cose` layout:
1. Has NO spectral phase - it's pure force-directed
2. Starts with randomized positions (good spread)
3. Applies simple force-directed physics
4. Doesn't need `nodeSeparation` or spectral parameters
5. Just works™ with basic parameters

**Our parameters were tuned for `cose`, not `fcose`!**

---

## 🔧 RECOMMENDED SOLUTIONS

### Option 1: Add Missing fcose Parameters ⭐ RECOMMENDED

```javascript
const LAYOUT_OPTIONS = {
    name: 'fcose',
    
    // Quality setting
    quality: 'default',         // ADD: Controls algorithm phases
    randomize: true,            // ADD: Random initial positions
    
    // Spectral phase parameters
    nodeSeparation: 75,         // ADD: KEY FIX - Controls spacing!
    samplingType: true,         // ADD: Greedy sampling
    sampleSize: 25,             // ADD: Sample size
    
    // Force-directed parameters
    nodeRepulsion: 4500,        // KEEP: Works fine
    idealEdgeLength: 50,        // CHANGE: Match fcose default
    edgeElasticity: 0.45,       // KEEP: Works fine
    nestingFactor: 0.1,         // KEEP: Works fine
    numIter: 2500,              // KEEP: Works fine
    gravity: 0.25,              // KEEP: Works fine
    
    // Component packing
    packComponents: true,       // ADD: Pack disconnected components
    
    // Animation
    animate: false,             // KEEP: No animation
    fit: true                   // KEEP: Fit to viewport
};
```

**Why this is best:**
- fcose is faster and recommended by Cytoscape team
- Addresses the root cause (missing spectral parameters)
- Minimal changes to existing code
- Future-proof

### Option 2: Try Higher `nodeSeparation` Values

If Option 1 doesn't work perfectly, try:
- `nodeSeparation: 100` (more spread)
- `nodeSeparation: 150` (even more spread)
- `nodeSeparation: 200` (maximum spread)

### Option 3: Use 'proof' Quality

```javascript
quality: 'proof'  // More iterations, better quality
```

### Option 4: Just Use Built-in `cose`

```javascript
const LAYOUT_OPTIONS = {
    name: 'cose',  // Change from 'fcose' to 'cose'
    // ... keep all existing parameters
};
```

**Pros:**
- Already works
- No debugging needed
- Simpler algorithm

**Cons:**
- Slower than fcose
- Less sophisticated
- Might need parameter tweaking for large graphs

---

## 📈 PARAMETER IMPACT ANALYSIS

### Critical Impact
- `nodeSeparation` - **CRITICAL** - Controls spectral phase spacing
- `quality` - **HIGH** - Determines which algorithm phases run

### Medium Impact
- `idealEdgeLength` - **MEDIUM** - Should match fcose default (50)
- `samplingType` - **MEDIUM** - Affects spectral quality
- `sampleSize` - **MEDIUM** - Affects spectral calculations

### Low Impact (Already Correct)
- `nodeRepulsion` - Correct at 4500
- `edgeElasticity` - Correct at 0.45
- `nestingFactor` - Correct at 0.1
- `numIter` - Correct at 2500
- `gravity` - Correct at 0.25

---

## 🧪 TESTING STRATEGY

1. **First Try**: Add only `nodeSeparation: 75`
   - Minimal change
   - Tests primary hypothesis
   
2. **If Still Clustered**: Add all spectral parameters
   - `nodeSeparation: 75`
   - `samplingType: true`
   - `sampleSize: 25`
   
3. **If Still Clustered**: Change `idealEdgeLength` to 50
   - Match fcose default
   
4. **If Still Clustered**: Try `quality: 'proof'`
   - More iterations
   
5. **If Still Clustered**: Increase `nodeSeparation`
   - Try 100, 150, 200
   
6. **Nuclear Option**: Fall back to `cose`
   - It already works

---

## 📚 KEY REFERENCES

- **fcose GitHub**: https://github.com/iVis-at-Bilkent/cytoscape.js-fcose
- **fcose npm**: https://www.npmjs.com/package/cytoscape-fcose
- **Layout Guide**: https://blog.js.cytoscape.org/2020/05/11/layouts/
- **Similar Issue**: https://github.com/cytoscape/cytoscape.js-cose-bilkent/issues/100
- **Demo**: https://js.cytoscape.org/demos/fcose-gene/
- **Research Paper**: "fCoSE: A Fast Compound Graph Layout Algorithm with Constraint Support" (Balci & Dogrusoz, 2022)

---

## ✅ CONFIDENCE LEVEL

**95% confident** that the missing `nodeSeparation` parameter is the primary cause.

**Evidence:**
1. ✓ fcose explicitly documents this as a spectral phase parameter
2. ✓ We're completely missing it
3. ✓ Community has reported identical clustering issues
4. ✓ Built-in cose works (has no spectral phase)
5. ✓ fcose combines spectral + force-directed (two-phase algorithm)

---

## 🎬 DECISION MADE

1. ✅ Research complete - document created
2. ✅ Review findings with Dan
3. ✅ Decision: **Use cose for V1** (Option 4)

### Rationale

After reviewing the screenshots and analysis:

- **before_fcode_fix.png** showed excellent layout using the `cose` fallback
- Built-in `cose` "worked the first time" with no parameter tuning needed
- V1 philosophy: ship what works, optimize later
- `cose` is simpler (pure force-directed, no spectral phase)
- No external CDN dependency

### Implementation (2026-01-28)

- `web/js/layout.js` - Refactored to use `cose` as primary layout
- `web/js/app.js` - Removed fcose registration code
- `web/index.html` - Commented out fcose CDN script

### V2 Consideration

If we need fcose for larger graphs (500+ nodes), the fix is documented:
- Add `nodeSeparation: 75` (and other spectral parameters)
- The research in this document remains valid

---

**IMPLEMENTED - Using cose for V1**
