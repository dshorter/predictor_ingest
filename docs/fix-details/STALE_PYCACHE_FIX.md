# Stale `__pycache__` on VPS Deployment (February 2026)

**Problem:** After updating `DEFAULT_DELAY` from `1.0` to `10.0` in
`src/ingest/rss.py` (to avoid CDN rate-limiting), the VPS continued using the
old value. `python -c "from ingest import rss; print(rss.DEFAULT_DELAY)"`
raised `AttributeError: module 'ingest.rss' has no attribute 'DEFAULT_DELAY'`.

**Root Cause:** Python's `__pycache__/*.pyc` bytecode files were stale. The
`.pyc` had been compiled from an older revision of the module (before
`DEFAULT_DELAY` existed at module level). Because `pip install -e .` creates a
`.egg-link` that points Python at the source tree, the import system found the
cached `.pyc` first and never re-compiled the updated `.py`.

This happens when:
1. The `.pyc` timestamp check (`st_mtime`) doesn't detect a change — common
   after `git pull` or `git checkout` which can preserve timestamps, or after
   file moves/copies.
2. The editable install's `.egg-link` path resolution interacts with stale
   `__pycache__` dirs scattered in the source tree.

**Resolution:**

```bash
# 1. Nuke all bytecode caches
find /opt/predictor_ingest -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null

# 2. Re-install editable package
cd /opt/predictor_ingest && pip install -e .

# 3. Verify
python -c "from ingest import rss; print('DEFAULT_DELAY:', rss.DEFAULT_DELAY)"
```

**Diagnostic command:** Always check which file Python is actually loading:
```bash
python -c "from ingest import rss; print(rss.__file__)"
```

If the `__file__` path doesn't point to your updated source, the import is
resolving from somewhere unexpected.

---

## Prevention

- After `git pull` on the VPS, run `find . -name "__pycache__" -exec rm -rf {} +`
  before running the pipeline.
- Consider adding `export PYTHONDONTWRITEBYTECODE=1` to the cron environment
  on the VPS (small perf cost, eliminates the class of bug entirely).
- The `scripts/run_pipeline.py` could clear `__pycache__` as a pre-flight step.

---

## Key Takeaway

When a Python module attribute that *clearly exists in the source file* raises
`AttributeError` at import time, the first thing to check is **stale bytecode
cache**. The `.py` file on disk is irrelevant if Python loads a `.pyc` compiled
from an older version.

---

**Status:** RESOLVED — 2026-02-18
