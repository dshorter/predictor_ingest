# FCOSE Layout Fix

**Fixed:** 2026-01-27 23:03:40 UTC

## Problem
The application was showing an error: "No such layout `fcose` found. Did you forget to import it and `cytoscape.use()` it?"

Although the chart still appeared (falling back to the built-in 'cose' layout), many controls were not working properly.

## Root Cause
The cytoscape-fcose extension was not being properly registered with Cytoscape before the application tried to use it. The original registration code ran at script load time but wasn't checking all possible global variable names or handling timing issues.

## Changes Made

### 1. Enhanced fcose Registration (`web/js/layout.js`)
- Created a robust `registerFcose()` function that:
  - Checks if Cytoscape is loaded
  - Tests if fcose is already registered
  - Tries multiple global variable names (`cytoscapeFcose`, `window.cytoscapeFcose`, `fcose`)
  - Returns success/failure status
  - Logs detailed information about the registration process

### 2. Multiple Registration Attempts
- Registers fcose when layout.js loads (either immediately or on DOMContentLoaded)
- Registers fcose during app initialization (`web/js/app.js`)
- Registers fcose right before running the layout

### 3. Improved Layout Fallback (`web/js/layout.js`)
- Better error handling in `runLayout()` function
- Clearer logging when falling back to built-in 'cose' layout
- Explicit check for fcose availability before using it

### 4. CDN Fallback (`web/index.html`)
- Added error handler to fcose script tag
- Falls back to jsdelivr CDN if unpkg fails
- Logs errors to console for debugging

### 5. Debug Tools
- Added `window.debugFcose()` function callable from browser console
- Automatically runs fcose check after 1 second
- Provides detailed diagnostic information:
  - Whether Cytoscape is loaded
  - Which fcose global variables are available
  - Whether fcose layout actually works

## Testing

1. **Open the application** in your browser
2. **Check the browser console** - you should see:
   ```
   Running automatic fcose check...
   === FCOSE DEBUG INFO ===
   cytoscape available: true
   cytoscapeFcose available: true
   ✓ fcose layout is registered and working
   ```

3. **If there are still issues**, run in the console:
   ```javascript
   debugFcose()
   ```
   This will show what's available and what's not.

4. **Test the controls**:
   - Try zooming in/out
   - Try the "Re-run layout" button
   - Try filtering nodes
   - Try searching

## Expected Behavior

- ✅ No error dialog on startup
- ✅ fcose layout is used (better graph arrangement than basic 'cose')
- ✅ All controls work properly
- ✅ Console shows successful fcose registration

## Fallback Behavior

If fcose still cannot be loaded (e.g., CDN is down):
- Application will automatically fall back to built-in 'cose' layout
- Warning will be logged to console
- Application will still function, just with a different (less optimal) layout algorithm

## Debugging

If you still see errors:

1. Check browser console for specific error messages
2. Run `debugFcose()` in console to see diagnostic info
3. Check Network tab to see if fcose script loaded successfully
4. Check if browser is blocking the CDN (some ad blockers or corporate firewalls block unpkg)
5. Try accessing the fcose CDN URL directly in browser:
   - https://unpkg.com/cytoscape-fcose@2.2.0/cytoscape-fcose.js
   - https://cdn.jsdelivr.net/npm/cytoscape-fcose@2.2.0/cytoscape-fcose.js

## Files Modified

1. `web/js/layout.js` - Enhanced registration and debugging
2. `web/js/app.js` - Added registration check during app init
3. `web/index.html` - Added CDN fallback

## Next Steps

1. Clear browser cache (Ctrl+Shift+R or Cmd+Shift+R)
2. Reload the application
3. Check console for success messages
4. Test all functionality

If issues persist, the console logs will provide specific information about what's failing.
