#!/usr/bin/env python3
"""Backfill token_usage.billing_mode and recompute cost_usd. Idempotent.

    venv/bin/python scripts/backfill_billing_mode.py --dry-run
    venv/bin/python scripts/backfill_billing_mode.py

WHY THIS EXISTS
---------------
Two defects left the historical cost record wrong in opposite directions, and a
report that mixes corrected and uncorrected rows is worse than one that is
uniformly wrong -- you cannot tell which half to trust.

1. EXTRACTION WAS LOGGED AT ~2x. Extraction is the only stage that goes through
   the Batch API, which bills at half the listed rate, but cost_usd was computed
   at sync rates for every row. `billing_mode` (added 2026-08-31) fixes new rows;
   this fixes the old ones.

2. SONNET 5 ROWS LOGGED NULL. `claude-sonnet-5` was missing from _TOKEN_PRICES
   from the 2026-07-20 migration until 2026-08-29, so _compute_cost returned
   None -- 2,139 rows in film alone with no cost at all. Those rows still carry
   their token counts, so the cost is recoverable exactly; it was never lost,
   only never computed.

HOW billing_mode IS INFERRED
----------------------------
Not guessed. `stage = 'extraction'` IS the batch path: the only call site that
logs extraction is the batch-results loop in collect_batch.py, and the sync
fallback beside it logged nothing at all before today. Every other stage
(synthesis, narratives, disambiguation) is a plain messages.create.

So: extraction -> batch, everything else -> sync, for rows written before
2026-08-31. Rows written after carry a real value from the caller and are left
alone -- re-running this script must not re-stamp a fallback row as batch.

WHAT IT DOES NOT DO
-------------------
It does not invent rates for a model that has never been priced. A row whose
model is absent from _TOKEN_PRICES stays NULL and is reported as still-unpriced,
because a plausible-looking made-up number is the failure this whole arc is
about.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from db import _compute_cost, ensure_token_usage_table  # noqa: E402

# Rows created at or after the day billing_mode shipped carry a caller-supplied
# value. Only earlier rows are inferred.
CUTOVER = "2026-08-31"


def backfill(db_path: Path, dry: bool) -> tuple[int, int, int]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(token_usage)")}
    except sqlite3.OperationalError:
        return (0, 0, 0)
    if not cols:
        return (0, 0, 0)
    ensure_token_usage_table(conn)

    rows = conn.execute(
        """SELECT id, stage, model, input_tokens, output_tokens, cost_usd,
                  billing_mode, created_at
             FROM token_usage
            WHERE created_at IS NULL OR created_at < ?""",
        (CUTOVER,),
    ).fetchall()

    changed = unpriced = 0
    for r in rows:
        mode = "batch" if r["stage"] == "extraction" else "sync"
        cost = _compute_cost(r["model"], r["input_tokens"], r["output_tokens"], mode)
        if cost is None:
            unpriced += 1
        same_mode = r["billing_mode"] == mode
        same_cost = (
            cost is not None
            and r["cost_usd"] is not None
            and abs(r["cost_usd"] - cost) < 1e-12
        ) or (cost is None and r["cost_usd"] is None)
        if same_mode and same_cost:
            continue
        changed += 1
        if not dry:
            conn.execute(
                "UPDATE token_usage SET billing_mode = ?, cost_usd = ? WHERE id = ?",
                (mode, cost, r["id"]),
            )
    if not dry:
        conn.commit()
    conn.close()
    return (len(rows), changed, unpriced)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--db", help="one database (default: every data/db/*.db)")
    args = ap.parse_args()

    dbs = [Path(args.db)] if args.db else sorted((REPO / "data" / "db").glob("*.db"))
    if not dbs:
        print("no databases found", file=sys.stderr)
        return 1

    print("=== backfill billing_mode + cost_usd ===")
    if args.dry_run:
        print("*** DRY RUN ***")
    total_changed = total_unpriced = 0
    for db in dbs:
        seen, changed, unpriced = backfill(db, args.dry_run)
        if not seen:
            continue
        note = f"  {db.name:28} {seen:5} pre-cutover rows, {changed:5} updated"
        if unpriced:
            note += f", {unpriced} STILL UNPRICED (model not in _TOKEN_PRICES)"
        print(note)
        total_changed += changed
        total_unpriced += unpriced

    print(f"\n{total_changed} row(s) {'would be ' if args.dry_run else ''}updated")
    if total_unpriced:
        print(f"{total_unpriced} row(s) remain NULL -- their model has no rate on "
              f"file. Add it to _TOKEN_PRICES and re-run to price them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
