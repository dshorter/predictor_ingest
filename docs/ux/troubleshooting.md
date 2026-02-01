# Troubleshooting

Common issues and solutions encountered during development.

---

## Layout Issues

### fcose Layout Extension Not Registered

**Fixed:** 2026-01-27 23:03:40 UTC  
**Detailed Fix Document:** [FCOSE_FIX.md](../fix-details/FCOSE_FIX.md)

**Symptoms:**
- Error dialog on app startup: "No such layout `fcose` found. Did you forget to import it and `cytoscape.use()` it?"
- Graph still appears (falling back to built-in 'cose' layout)
- Some controls don't work properly
- Layout quality is suboptimal

**Root Cause:**
The `cytoscape-fcose` extension was not being properly registered with Cytoscape before the application tried to use it. The original registration code ran at script load time but wasn't:
- Checking all possible global variable names
- Handling timing issues properly
- Verifying registration success
- Providing fallback behavior

**Solution:**

1. **Enhanced Registration Function** (`web/js/layout.js`)
   - Created robust `registerFcose()` function that:
     - Checks if Cytoscape is loaded
     - Tests if fcose is already registered (avoids double-registration)
     - Tries multiple global variable names: `cytoscapeFcose`, `window.cytoscapeFcose`, `fcose`
     - Returns success/failure status
     - Logs detailed information for debugging

2. **Multiple Registration Attempts**
   - Register when layout.js loads (immediate or DOMContentLoaded)
   - Re-register during app initialization (`web/js/app.js`)
   - Final registration check before running layout

3. **Improved Fallback Handling** (`web/js/layout.js`)
   - Better error handling in `runLayout()` function
   - Clearer logging when falling back to built-in 'cose' layout
   - Explicit test for fcose availability before use

4. **CDN Fallback** (`web/index.html`)
   - Added error handler to fcose script tag
   - Falls back to jsdelivr CDN if unpkg fails
   - Logs errors to console for debugging

5. **Debug Tools**
   - Added `window.debugFcose()` function (callable from browser console)
   - Automatically runs fcose check after 1 second
   - Provides detailed diagnostic information

**Files Modified:**
- `web/js/layout.js` - Enhanced registration and debugging
- `web/js/app.js` - Added registration check during app init
- `web/index.html` - Added CDN fallback

**Verification:**

After clearing browser cache and reloading:

1. Check browser console for:
   ```
   Running automatic fcose check...
   === FCOSE DEBUG INFO ===
   cytoscape available: true
   cytoscapeFcose available: true
   ✓ fcose layout is registered and working
   ```

2. Run manually in console if needed:
   ```javascript
   debugFcose()
   ```

3. Test controls:
   - Zoom in/out buttons
   - "Re-run layout" button
   - Filter panel
   - Search functionality

**Prevention:**

For future CDN-loaded extensions:
- Always create a dedicated registration function
- Test registration success before using extension
- Provide graceful fallback to built-in alternatives
- Add debug helpers for troubleshooting
- Consider multiple CDN sources as fallback
- Log registration attempts clearly

**Related Documentation:**
- See [layout-temporal.md](layout-temporal.md) for fcose configuration details
- See [implementation.md](implementation.md) for dependency management

---

## Selector Issues

### Colon Characters in Node IDs Break cy.$() Selectors

**Fixed:** 2026-01-28 UTC

**Symptoms:**
- Clicking "View" or "Expand" buttons in panels does nothing
- Console error: `Syntax error, unrecognized expression` or silent failures
- Affects any node with `:` in its ID (most entities: `org:openai`, `model:gpt-5`, `tool:langchain`, etc.)

**Root Cause:**
Cytoscape's `cy.$('#org:openai')` uses CSS selector syntax internally. The `#` selector treats `:` as a pseudo-class separator (`#org` + `:openai`), which fails. Since our canonical ID scheme uses colons extensively (`type:slug`), this breaks nearly all programmatic node selection.

**Solution:**
Use `cy.getElementById('org:openai')` instead of `cy.$('#org:openai')` everywhere. The `getElementById()` method does direct ID lookup without CSS parsing.

```javascript
// WRONG — breaks on colons
const node = cy.$(`#${nodeId}`);

// CORRECT — safe for any ID characters
const node = cy.getElementById(nodeId);
```

**Files Modified:**
- `web/js/panels.js` — All `selectNode()`, `expandNeighbors()`, `zoomToNode()` calls
- `web/js/graph.js` — `removeElements()` function

**Prevention:**
- Never use `cy.$('#...')` or `cy.$id()` with user-facing IDs that may contain colons, dots, or brackets
- Always use `cy.getElementById()` for single-node lookup by ID
- For batch operations, use `cy.collection()` + `.getElementById()` in a loop, or filter with `.filter()`

---

## Panel / Canvas Interaction Issues

### Evidence Panel Does Not Shrink the Graph Canvas

**Fixed:** 2026-01-28 UTC

**Symptoms:**
- Opening the bottom evidence panel overlaps the graph instead of shrinking it
- Graph nodes hidden behind the panel are not clickable
- Closing the panel doesn't restore full canvas height

**Root Cause:**
The Cytoscape container (`#cy`) had a fixed height. When the evidence panel opened, nothing told the container to shrink. Additionally, Cytoscape caches its container dimensions and doesn't automatically detect DOM size changes—you must call `cy.resize()` explicitly.

**Solution:**

1. **CSS classes** toggle canvas sizing when panels open:
   ```css
   #cy.panel-bottom-open {
     bottom: 240px;  /* evidence panel height */
   }
   ```

2. **`updateCyContainer()`** in `panels.js` toggles classes and calls `cy.resize()`:
   ```javascript
   function updateCyContainer() {
     const cyEl = document.getElementById('cy');
     const evidenceOpen = !document.getElementById('evidence-panel')
       ?.classList.contains('hidden');
     cyEl.classList.toggle('panel-bottom-open', evidenceOpen);
     setTimeout(() => window.cy.resize(), 50);
   }
   ```

3. **Called from** every panel open/close: `openEvidencePanel()`, `closeAllPanels()`, panel close buttons.

**Files Modified:**
- `web/css/graph/cytoscape.css` — Panel-aware sizing classes
- `web/js/panels.js` — `updateCyContainer()` function, panel open/close handlers

**Prevention:**
- Any new panel that affects canvas bounds must call `updateCyContainer()` on show/hide
- Always call `cy.resize()` after changing the Cytoscape container's dimensions
- Use a short `setTimeout` (50ms) to let the DOM settle before resize

---

## Styling Issues

### Cytoscape Ignores CSS Pseudo-Selectors (:hover, :focus)

**Fixed:** 2026-01-28 UTC

**Symptoms:**
- `:hover` styles defined in `getCytoscapeStyles()` have no effect
- Nodes and edges don't respond to mouse hover visually
- Tooltips appear (because they use JS events) but border/color changes don't

**Root Cause:**
Cytoscape.js does **not** support CSS pseudo-selectors like `:hover` or `:focus` in its stylesheet. It only supports its own pseudo-selectors (`:selected`, `:active`, `:grabbed`) and class-based selectors (`.myclass`). The Cytoscape docs list `:hover` in some examples but it is not reliably implemented.

**Solution:**
Use JavaScript events to add/remove classes, then target those classes in the Cytoscape stylesheet:

```javascript
// In tooltips.js — add .hover class via events
cy.on('mouseover', 'node', (e) => e.target.addClass('hover'));
cy.on('mouseout', 'node', (e) => e.target.removeClass('hover'));

// In styles.js — target the class, not pseudo-selector
{
  selector: 'node.hover',  // NOT 'node:hover'
  style: {
    'border-width': 3,
    'border-color': '#3B82F6'
  }
}
```

**Files Modified:**
- `web/js/styles.js` — Changed selectors from `node:hover`/`edge:hover` to `node.hover`/`edge.hover`
- `web/js/tooltips.js` — Added `addClass('hover')` / `removeClass('hover')` in mouseover/mouseout handlers

**Prevention:**
- Never use `:hover`, `:focus`, or other CSS pseudo-selectors in Cytoscape stylesheets
- Use only: `:selected`, `:active`, `:grabbed`, `:parent`, `:child`, or class-based selectors (`.className`)
- For any interactive state, add/remove classes via Cytoscape events

---

## [Future issues will be documented here]

**Organization Pattern:**

- **Quick Reference:** Keep concise issue summaries in this file (`docs/ux/troubleshooting.md`)
- **Detailed Docs:** Create separate `{ISSUE_NAME}_FIX.md` files in `docs/fix-details/` for:
  - Step-by-step fixes
  - Extensive code examples
  - Testing procedures
  - Long explanations
- **Link them together:** Reference detailed docs from this file

**When adding new issues:**

1. Include timestamp (UTC) - use `date -u +"%Y-%m-%d %H:%M:%S UTC"`
2. Document symptoms clearly
3. Explain root cause
4. Provide complete solution (or link to detailed doc)
5. List modified files
6. Include verification steps
7. Add prevention tips for similar issues
8. If creating a detailed fix doc, link it with: `**Detailed Fix Document:** [{NAME}_FIX.md](../fix-details/{NAME}_FIX.md)`
