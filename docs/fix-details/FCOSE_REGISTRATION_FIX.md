# fcose Registration Fix

**Date:** January 2026  
**Issue:** fcose layout extension not registering properly  
**Status:** ✅ RESOLVED

---

## The Original Problem

When trying to use the fcose layout, Cytoscape threw an error:

```
Error: Can not apply layout: No such layout `fcose` found. 
Did you forget to import it and `cytoscape.use()` it?
```

**Impact:**
- fcose layout not available
- App falling back to basic cose layout
- Error dialog shown to users

---

## Root Cause

The fcose extension needs to be **registered** with Cytoscape before it can be used:

```javascript
// This is required but was missing:
cytoscape.use(cytoscapeFcose);
```

**The Challenge:**
- fcose loaded from CDN as `cytoscapeFcose` global
- Registration must happen AFTER both libraries load
- Timing issues with async script loading
- Different CDN versions may expose different global names

---

## The Solution

Created a robust `registerFcose()` function that:

1. Checks if Cytoscape is loaded
2. Tests if fcose is already registered
3. Tries multiple possible global variable names
4. Provides debug logging
5. Handles timing with DOMContentLoaded

### Implementation

**File:** `web/js/layout.js`

```javascript
/**
 * Register fcose extension with Cytoscape
 * Need to ensure registration happens after libraries load
 */
function registerFcose() {
  if (typeof cytoscape === 'undefined') {
    console.error('Cytoscape not loaded');
    return false;
  }

  // Check if already registered
  try {
    const testLayout = cytoscape({ elements: [] }).layout({ name: 'fcose' });
    console.log('fcose already registered');
    return true;
  } catch (e) {
    // Not registered yet, try to register
  }

  // Try different possible global variable names from the CDN
  if (typeof cytoscapeFcose !== 'undefined') {
    console.log('Registering fcose via cytoscapeFcose');
    cytoscape.use(cytoscapeFcose);
    return true;
  } else if (typeof window.cytoscapeFcose !== 'undefined') {
    console.log('Registering fcose via window.cytoscapeFcose');
    cytoscape.use(window.cytoscapeFcose);
    return true;
  } else if (typeof fcose !== 'undefined') {
    console.log('Registering fcose via fcose');
    cytoscape.use(fcose);
    return true;
  } else {
    console.warn('fcose extension not found in global scope');
    return false;
  }
}

// Try to register when script loads
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', registerFcose);
} else {
  registerFcose();
}

// Debug helper function - can be called from browser console
window.debugFcose = function() {
  console.log('=== FCOSE DEBUG INFO ===');
  console.log('cytoscape available:', typeof cytoscape !== 'undefined');
  console.log('cytoscapeFcose available:', typeof cytoscapeFcose !== 'undefined');
  console.log('window.cytoscapeFcose available:', typeof window.cytoscapeFcose !== 'undefined');
  console.log('fcose available:', typeof fcose !== 'undefined');
  
  if (typeof cytoscape !== 'undefined') {
    try {
      const testCy = cytoscape({ elements: [] });
      const testLayout = testCy.layout({ name: 'fcose' });
      console.log('✓ fcose layout is registered and working');
      return true;
    } catch (e) {
      console.error('✗ fcose layout test failed:', e.message);
      return false;
    }
  } else {
    console.error('✗ Cytoscape not available');
    return false;
  }
};

// Auto-run debug check after a short delay to let everything load
setTimeout(() => {
  console.log('Running automatic fcose check...');
  window.debugFcose();
}, 1000);
```

### Also call in runLayout()

```javascript
function runLayout(cy, options = {}) {
  // Ensure fcose is registered before trying to use it
  registerFcose();
  
  const layoutOptions = {
    ...LAYOUT_OPTIONS,
    ...options
  };
  
  const layout = cy.layout(layoutOptions);
  layout.run();
}
```

---

## How It Works

### 1. Script Loading Order

```html
<!-- In web/index.html -->
<script src="https://unpkg.com/cytoscape@3.30.4/dist/cytoscape.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/cytoscape-fcose@2.2.0/cytoscape-fcose.js"></script>
<script src="js/layout.js"></script>
```

### 2. CDN Behavior

The fcose CDN script creates a global variable:
- Typically: `cytoscapeFcose`
- Sometimes: `window.cytoscapeFcose`
- Rarely: `fcose`

Our function tries all three!

### 3. Timing Handling

**Problem:** Scripts load asynchronously

**Solution:** Multiple registration attempts
- On DOMContentLoaded
- Before first layout use
- With debug function for manual testing

### 4. Idempotent Registration

The function can be called multiple times safely:
1. Check if already registered (via test layout)
2. If yes, return early
3. If no, attempt registration

---

## Testing

### Browser Console

```javascript
// Check registration status
window.debugFcose()

// Expected output:
// === FCOSE DEBUG INFO ===
// cytoscape available: true
// cytoscapeFcose available: true
// window.cytoscapeFcose available: true
// fcose available: false
// ✓ fcose layout is registered and working
```

### Visual Confirmation

1. Open app in browser
2. Check console for: `"fcose already registered"` or `"Registering fcose via..."`
3. Verify graph renders without error dialog
4. No red error messages in console

---

## Why This Approach?

### Robustness
- Handles different CDN versions
- Works across browsers
- Survives script reordering
- Self-correcting with multiple attempts

### Debuggability
- Clear console logging
- Debug function for troubleshooting
- Automatic health check on load

### Maintainability
- Single function handles all registration
- Easy to test in console
- Well-documented behavior

---

## Known Limitations

1. **Requires CDN global variable**
   - Won't work with bundlers without modification
   - Assumes fcose creates global

2. **Timing still matters**
   - Both scripts must load before registration
   - Rare race conditions possible

3. **No graceful degradation built into registration**
   - If registration fails, layout will error
   - Caller should handle fallback to 'cose'

---

## Future Improvements

### Better Fallback Handling

```javascript
function runLayout(cy, options = {}) {
  const registered = registerFcose();
  
  const layoutOptions = {
    ...LAYOUT_OPTIONS,
    ...options
  };
  
  // Fallback to cose if fcose not available
  if (!registered && layoutOptions.name === 'fcose') {
    console.warn('fcose not available, falling back to cose');
    layoutOptions.name = 'cose';
  }
  
  const layout = cy.layout(layoutOptions);
  layout.run();
}
```

### Bundler Support

For webpack/rollup/vite:

```javascript
import cytoscape from 'cytoscape';
import fcose from 'cytoscape-fcose';

cytoscape.use(fcose);
```

---

## Related Issues

- **Layout Quality Issue:** See [FCOSE_LAYOUT_ANALYSIS.md](FCOSE_LAYOUT_ANALYSIS.md)
  - After fixing registration, discovered fcose produces worse layout than cose
  - Led to comprehensive algorithm analysis and recommendation to revert to cose

---

## References

- **fcose GitHub:** https://github.com/iVis-at-Bilkent/cytoscape.js-fcose
- **fcose CDN:** https://cdn.jsdelivr.net/npm/cytoscape-fcose@2.2.0/
- **Cytoscape Extensions:** https://js.cytoscape.org/#extensions/layout-extensions

---

**Status:** ✅ Registration error FIXED  
**Note:** See FCOSE_LAYOUT_ANALYSIS.md for why we ultimately reverted to cose despite fixing registration
