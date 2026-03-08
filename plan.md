# Plan: Fix Mobile Multi-Domain Gaps (Sprint 6/6B)

## Problem
The mobile web UI doesn't load domain configuration, so biosafety (and any future domain) renders with AI-hardcoded entity types, wrong type groups, no domain-specific colors, and broken filter checkbox binding on init.

## Changes

### 1. Add `loadDomainConfig()` to `web/mobile/js/app-mobile.js`
- Port desktop's `loadDomainConfig()` function (adapted from `web/js/app.js:35-84`)
- Fetches `../data/domains/{domain}.json`, falls back to `../data/domain.json`, then to hardcoded defaults
- Sets `AppState.domainConfig` with `domain`, `title`, `titleShort`, `entityTypes`, `typeGroups`, `typeColors`
- Injects domain-specific CSS color variables onto `document.documentElement`

### 2. Update `initializeApp()` in `app-mobile.js`
- Call `await loadDomainConfig()` right after `initTheme()`, before filter/graph init
- Replace the hardcoded `domainLabels` map with `AppState.domainConfig.titleShort || AppState.domainConfig.title`
- This ensures `GraphFilter` constructor reads `AppState.domainConfig.entityTypes` correctly

### 3. Fix `populateTypeFilters` call in `initializeMobileFilterPanel` (`panels-mobile.js:265`)
- Change `populateTypeFilters(filter.cy)` → `populateTypeFilters(filter.cy, filter)`
- Without the filter arg, type checkbox change listeners are never bound on initial load

### 4. Fix `GraphFilter.reset()` to use domain config types (`web/js/filter.js:193-206`)
- Replace the hardcoded 15-type array with a lookup of `AppState.domainConfig.entityTypes`
- Fall back to the current hardcoded list if no config is loaded
- This fix benefits both desktop and mobile

### 5. Add biosafety badge styles to `web/mobile/css/mobile.css`
- Add `.badge-type-selectagent`, `.badge-type-facility`, `.badge-type-regulation` badge color rules
- Use the colors from `biosafety.json` typeColors (red, orange, purple)

## Files Modified
1. `web/mobile/js/app-mobile.js` — add `loadDomainConfig()`, update `initializeApp()`
2. `web/mobile/js/panels-mobile.js` — fix `populateTypeFilters` call (one-line fix)
3. `web/js/filter.js` — fix `reset()` to use domain config types
4. `web/mobile/css/mobile.css` — add biosafety badge styles
