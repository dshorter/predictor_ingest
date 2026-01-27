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
