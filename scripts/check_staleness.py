"""Pipeline staleness pager (Sprint 20.4).

Pages the operator (via notify-telegram, [PREDICTOR] prefix) when an
active domain has gone quiet: no new documents or no new trend_history
row within the threshold. Also flags individual enabled feeds that have
stopped delivering (audit 2026-07-19 cross-cut #3: feeds can be
valid-but-empty, so domain-level volume hides single-feed death).

The 2026-06-23 semiconductors stall ran 9+ days unnoticed; this script
exists so that never happens again.

Designed to run from a systemd timer (deploy/systemd/). Alert paging is
rate-limited through a state file so a persistent stall re-pages daily,
not every timer tick. A crash of this script itself is caught by the
unit's OnFailure= hook.

Usage:
    python scripts/check_staleness.py                  # dry run, print only
    python scripts/check_staleness.py --notify         # page if stale
    python scripts/check_staleness.py --domains film   # override active set
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

# Domains the pager watches. Fusion joins at 20.18.
DEFAULT_DOMAINS = "film,semiconductors,weapons_detection"

# Domain-level: no new docs or no new trend_history row for this long.
DEFAULT_MAX_AGE_HOURS = 48

# Feed-level: an enabled feed that has delivered before but not for this long.
DEFAULT_FEED_MAX_AGE_DAYS = 14

# Re-page intervals while a condition persists.
DOMAIN_REPAGE_HOURS = 24
FEED_REPAGE_HOURS = 7 * 24

STATE_FILE = ROOT / "data" / "health" / "staleness_state.json"
NOTIFY = "/usr/local/sbin/notify-telegram"
AGENT_NAME = "PREDICTOR"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _age_hours(stamp: str | None, now: datetime) -> float | None:
    """Age in hours of an ISO date or datetime string. None if unparseable."""
    if not stamp:
        return None
    text = stamp.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 3600.0


def _fmt_age(hours: float) -> str:
    return f"{hours / 24:.1f}d" if hours >= 48 else f"{hours:.0f}h"


def check_domain(domain: str, max_age_hours: float, feed_max_age_days: float,
                 now: datetime) -> dict[str, str]:
    """Return {state_key: alert_text} for one domain.

    Keys are stable ("domain:film:docs", "feed:film/Deadline") so re-page
    limiting survives changing ages in the alert text.

    Feed-level alerts are suppressed while the domain-level ingest alert
    fires: they exist to catch single-feed death amid a healthy domain,
    and a full stall would otherwise echo once per feed.
    """
    db_path = ROOT / "data" / "db" / f"{domain}.db"
    if not db_path.exists():
        return {f"domain:{domain}:db": f"{domain}: database missing ({db_path})"}

    conn = sqlite3.connect(str(db_path))
    try:
        alerts: dict[str, str] = {}

        last_doc = conn.execute("SELECT MAX(fetched_at) FROM documents").fetchone()[0]
        doc_age = _age_hours(last_doc, now)
        if doc_age is None:
            alerts[f"domain:{domain}:docs"] = f"{domain}: no documents ever ingested"
        elif doc_age > max_age_hours:
            alerts[f"domain:{domain}:docs"] = (
                f"{domain}: no new docs for {_fmt_age(doc_age)} (last {last_doc[:10]})"
            )

        try:
            last_run = conn.execute("SELECT MAX(run_date) FROM trend_history").fetchone()[0]
        except sqlite3.OperationalError:
            last_run = None
        run_age = _age_hours(last_run, now)
        if run_age is None:
            alerts[f"domain:{domain}:trend"] = f"{domain}: no trend_history rows"
        elif run_age > max_age_hours:
            alerts[f"domain:{domain}:trend"] = (
                f"{domain}: no trend_history row for {_fmt_age(run_age)} (last {last_run})"
            )

        ingest_stalled = f"domain:{domain}:docs" in alerts
        feeds_path = ROOT / "domains" / domain / "feeds.yaml"
        if feeds_path.exists() and not ingest_stalled:
            with open(feeds_path, "r", encoding="utf-8") as f:
                feeds = (yaml.safe_load(f) or {}).get("feeds", [])
            last_by_source = dict(conn.execute(
                "SELECT source, MAX(fetched_at) FROM documents GROUP BY source"
            ).fetchall())
            for feed in feeds:
                if not feed.get("enabled", False):
                    continue
                name = feed.get("name", "?")
                last = last_by_source.get(name)
                if last is None:
                    # Never delivered: known at configuration time, not a
                    # regression — journal only, never paged.
                    continue
                age = _age_hours(last, now)
                if age is not None and age > feed_max_age_days * 24:
                    alerts[f"feed:{domain}/{name}"] = (
                        f"{domain}/{name}: silent for {_fmt_age(age)} (last {last[:10]})"
                    )
        return alerts
    finally:
        conn.close()


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def due_for_page(state: dict, key: str, repage_hours: float, now: datetime) -> bool:
    age = _age_hours(state.get(key), now)
    return age is None or age >= repage_hours


def page(message: str) -> None:
    """Send via notify-telegram. Delivery problems are its problem (exit 0)."""
    subprocess.run([NOTIFY, AGENT_NAME, message], check=False, timeout=30)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domains", default=DEFAULT_DOMAINS,
                        help=f"Comma-separated active domains (default: {DEFAULT_DOMAINS})")
    parser.add_argument("--max-age-hours", type=float, default=DEFAULT_MAX_AGE_HOURS,
                        help="Domain-level staleness threshold (default: 48)")
    parser.add_argument("--feed-max-age-days", type=float, default=DEFAULT_FEED_MAX_AGE_DAYS,
                        help="Feed-level staleness threshold (default: 14)")
    parser.add_argument("--notify", action="store_true",
                        help="Actually page via notify-telegram (default: print only)")
    args = parser.parse_args()

    now = _now()
    state = load_state()
    to_page: list[str] = []
    all_alerts: list[str] = []

    for domain in [d.strip() for d in args.domains.split(",") if d.strip()]:
        for key, alert in check_domain(
                domain, args.max_age_hours, args.feed_max_age_days, now).items():
            all_alerts.append(alert)
            repage = FEED_REPAGE_HOURS if key.startswith("feed:") else DOMAIN_REPAGE_HOURS
            if due_for_page(state, key, repage, now):
                to_page.append(alert)
                state[key] = now.isoformat()

    if not all_alerts:
        print(f"staleness: all domains fresh ({args.domains})")
        return 0

    for alert in all_alerts:
        print(f"STALE: {alert}")

    if args.notify and to_page:
        page("staleness: " + "; ".join(to_page))
        save_state(state)
    elif args.notify:
        # Everything stale was already paged recently; keep state as-is.
        print("(all alerts within re-page window, not paging)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
