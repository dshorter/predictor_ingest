#!/usr/bin/env python3
"""Sept 1 cost boundary — the timed edits that must land before the 06:00 run.

    venv/bin/python scripts/sept1_cost_boundary.py --dry-run
    venv/bin/python scripts/sept1_cost_boundary.py --only budgets

RUN ON THE EVENING OF 2026-08-31. Not earlier: every day through Aug 31 bills
at Sonnet 5 introductory rates ($2/$10), so cutting sooner discards cheap
capacity for no saving (ops calendar: predictor-sept1-hold-net-cost).

WHY 0.63x AND NOT THE 0.75x IN THE TODO
---------------------------------------
The todo's model assumed the intro period was running at 0.87 of the
pre-migration baseline. Measured from token_usage, it is running at 1.06 --
6% ABOVE, not 13% below. Everything downstream inherited that 19-point gap.
Reconstructed per active run-day, film + semiconductors:

    pre-migration (Apr, Sonnet 4.6)   $5.04/day   index 1.00
    now (Sonnet 5, intro, 1x)         $5.32/day   index 1.06
    Sept 1 at 1x, standard rates      $7.97/day   index 1.58
    Sept 1 at 0.75x                   $5.98/day   index 1.19  <- not flat
    Sept 1 at 0.63x                   $5.02/day   index 1.00  <- flat

The todo's OTHER number checks out exactly: flat-vs-intro-period was given as
0.67x, and $5.32/$7.97 = 0.667. The reasoning was sound; one input was wrong.

MODES
-----
film-untouched  semis 17/21, weapons 10/15, FILM UNCHANGED   <-- default
uniform         film 22/25, semis 13/16    -- both to 0.63x, as the todo reads
film-weighted   film 18/20, semis 17/21    -- same spend, semis keeps more

WHY THE DEFAULT DOES NOT CUT FILM
---------------------------------
Film is 65% of Sonnet 5 spend, so cutting it is the obvious lever and it is the
wrong one. Movers is built from mention counts over a 7-day window
(activity_factor = min(mention_count_7d, 20) / 20), so halving film's documents
halves its mention counts and moves the rankings. The volume IS the signal.

The cheap lever for film is per-document cost, not document count: 79% of
film's cost is output tokens, and a Movers-only pass on Haiku drops the
relation payload and the rate together -- roughly an order of magnitude,
without touching the mention stream.

So the flat-cost target is met by making film cheap, not smaller. Until that
lands, spend sits near 1.4x rather than 1.0x -- a few tens of dollars, against
corrupting the measurement that decides whether film is worth keeping.

Cutting now would also need undoing later: two mid-window volume changes, two
velocity artifacts (methodology 2.7), in the domain under evaluation.

`uniform` and `film-weighted` remain for the case where Movers-only is
abandoned.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLATFORM_PRICING = Path("/opt/ai-agent-platform/pipelines/blog_pipeline/pricing.py")

MODES = {
    # mode: {domain: (budget, stretch_max)}. A domain absent from a mode is
    # left exactly as it is.
    #
    # DEFAULT. Film's budget must NOT move under the Movers-only plan: Movers
    # is built from mention counts over a 7-day window, so cutting documents
    # cuts the signal. A cut now would also have to be undone when the Haiku
    # mentions path lands -- two mid-window volume changes, two velocity
    # artifacts, in the one domain whose signal is being evaluated. Decided
    # 2026-08-29; this table is where that decision lives.
    "film-untouched": {"semiconductors": (17, 21)},

    # Only if Movers-only is abandoned and film goes back to earning its
    # Landscape keep on relation quality. Both reach ~0.63x by cutting volume.
    "uniform":        {"film": (22, 25), "semiconductors": (13, 16)},
    "film-weighted":  {"film": (18, 20), "semiconductors": (17, 21)},
}
# weapons_detection returns to its documented normal either way. It is NOT part
# of the flat-cost math: it has no pre-migration baseline (its first-ever run
# was already at 2x) and it billed $1.89 across the whole period -- $0.09/day.
WEAPONS = (10, 15)


def edit(path: Path, old: str, new: str, dry: bool, label: str) -> bool:
    text = path.read_text()
    if new in text and old not in text:
        print(f"  = {label}: already applied")
        return True
    if old not in text:
        print(f"  ! {label}: PATTERN NOT FOUND -- edit by hand", file=sys.stderr)
        return False
    if dry:
        print(f"  [dry-run] {label}: {old.strip()!r} -> {new.strip()!r}")
        return True
    path.write_text(text.replace(old, new, 1))
    print(f"  + {label}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=sorted(MODES), default="film-untouched")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--only",
        choices=("all", "budgets", "rates"),
        default="all",
        help=(
            "Split the two halves. Budgets MAY run early -- a day of it forfeits "
            "about $2 of cheap capacity. Rates MUST NOT: intro pricing runs "
            "through 2026-08-31, so bumping the tables before Sept 1 logs real "
            "spend 50%% above what is actually charged, and PREDICTOR_MAX_COST_USD "
            "reads those tables."
        ),
    )
    args = ap.parse_args()
    do_budgets = args.only in ("all", "budgets")
    do_rates = args.only in ("all", "rates")
    dry, ok = args.dry_run, True

    budgets = dict(MODES[args.mode])
    budgets["weapons_detection"] = WEAPONS
    print(f"=== Sept 1 cost boundary — mode: {args.mode} ===")
    if dry:
        print("*** DRY RUN ***")

    if do_budgets:
        print("\n-- domain budgets --")
        for dom, (b, s) in budgets.items():
            y = REPO / "domains" / dom / "domain.yaml"
            cur = re.search(r"doc_selection:\s*\n\s*budget:\s*(\d+)\s*\n\s*stretch_max:\s*(\d+)",
                            y.read_text())
            if not cur:
                print(f"  ! {dom}: doc_selection block not found", file=sys.stderr)
                ok = False
                continue
            print(f"  {dom}: {cur.group(1)}/{cur.group(2)} -> {b}/{s}")
            ok &= edit(y, cur.group(0),
                       f"doc_selection:\n  budget: {b}\n  stretch_max: {s}",
                       dry, f"{dom}/domain.yaml")

        print("\n-- test assertion --")
        t = REPO / "tests" / "test_select.py"
        ttext = t.read_text()
        for dom, (b, s) in budgets.items():
            m = re.search(
                r'budget_from_profile\(load_domain_profile\("' + dom + r'"\)\) == \(\d+, \d+\)',
                ttext)
            if not m:
                print(f"  ! test_select.py::{dom}: assertion not found", file=sys.stderr)
                ok = False
                continue
            new = f'budget_from_profile(load_domain_profile("{dom}")) == ({b}, {s})'
            ok &= edit(t, m.group(0), new, dry, f"test_select.py::{dom}")
            if not dry:
                ttext = t.read_text()

    if not do_rates:
        print("\n-- rate tables: SKIPPED (--only budgets) --")
        print("   Intro pricing runs through 2026-08-31. Run --only rates on the")
        print("   evening of the 31st, before the 06:00 ET run on Sept 1.")
        print("\n=== done ===" if ok else "\n=== INCOMPLETE ===")
        return 0 if ok else 1

    print("\n-- rate tables: Sonnet 5 intro ends, $2/$10 -> $3/$15 --")
    dbf = REPO / "src" / "db" / "__init__.py"
    dbtext = dbf.read_text()
    if '"claude-sonnet-5"' in dbtext:
        ok &= edit(dbf, '"claude-sonnet-5":          (2.00, 10.00),',
                   '"claude-sonnet-5":          (3.00, 15.00),',
                   dry, "predictor _TOKEN_PRICES (bump)")
    else:
        # No sonnet-5 row has ever existed here, so _compute_cost has returned
        # None for every call since PRIMARY_MODEL switched on 2026-07-20 --
        # 2,139 rows in film alone with a NULL cost_usd. Insert, do not bump.
        anchor = '    "claude-sonnet-4-6":        (3.00, 15.00),'
        ok &= edit(dbf, anchor,
                   '    "claude-sonnet-5":          (3.00, 15.00),\n' + anchor,
                   dry, "predictor _TOKEN_PRICES (INSERT — fixes NULL cost logging)")
    if PLATFORM_PRICING.exists():
        ok &= edit(PLATFORM_PRICING,
                   '"claude-sonnet-5": (2.00, 10.00),',
                   '"claude-sonnet-5": (3.00, 15.00),',
                   dry, "ai-agent-platform pricing.py (CROSS-REPO)")

    print("\n-- verify --")
    print("  venv/bin/python -m pytest tests/test_select.py -q")
    print("  git -C /opt/predictor_ingest diff --stat")
    print("  git -C /opt/ai-agent-platform diff --stat")
    print("\n=== done ===" if ok else "\n=== INCOMPLETE — see errors above ===")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
