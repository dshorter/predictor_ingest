#!/usr/bin/env python3
"""Generate dashboard JSON files for web/dashboard.html.

Reads pipeline logs, SQLite DB, trending graph, and feed config to produce:
  web/data/dashboard/status.json  — last run KPIs
  web/data/dashboard/runs.json    — 30-day run history
  web/data/dashboard/quality.json — quality gate + model metrics
  web/data/dashboard/feeds.json   — feed health

Usage:
  python scripts/generate_dashboard_json.py [--db PATH] [--logs-dir PATH]

Add to pipeline:
  make dashboard-data
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Add src/ to import path
sys.path.insert(0, str(ROOT / "src"))


def load_pipeline_logs(logs_dir: Path, n: int = 30) -> list[dict]:
    """Load last N pipeline logs sorted newest-first."""
    logs = []
    for f in sorted(logs_dir.glob("pipeline_*.json"), reverse=True)[:n]:
        try:
            data = json.loads(f.read_text())
            logs.append(data)
        except Exception:
            pass
    return logs


def build_status(logs: list[dict], graphs_live: Path) -> dict:
    """Overall system status from the most recent pipeline log."""
    base = {"available": False, "generatedAt": _now()}

    if not logs:
        return base

    latest = logs[0]
    stages = latest.get("stages", {})
    ingest = stages.get("ingest", {})
    extract = stages.get("extract", {})
    imp = stages.get("import", {})
    export_s = stages.get("export", {})

    # Node/edge counts: prefer export stage, fall back to live trending meta
    nodes = export_s.get("totalNodes")
    edges = export_s.get("totalEdges")
    if nodes is None:
        for fname in ("trending.json", "mentions.json", "claims.json"):
            p = graphs_live / fname
            if p.exists():
                try:
                    meta = json.loads(p.read_text()).get("meta", {})
                    nodes = nodes or meta.get("nodeCount")
                    edges = edges or meta.get("edgeCount")
                    if nodes is not None:
                        break
                except Exception:
                    pass

    docpack_stage = stages.get("docpack", {})
    docs_bundled = docpack_stage.get("docsBundled", 0) or 0
    docs_extracted = extract.get("docsExtracted", 0) or 0
    backlog = max(0, docs_bundled - docs_extracted) if (docs_bundled or docs_extracted) else None

    return {
        "available": True,
        "generatedAt": _now(),
        "domain": latest.get("domain"),
        "lastRunDate": latest.get("runDate"),
        "lastRunStatus": latest.get("status", "unknown"),
        "lastRunDurationSec": latest.get("durationSec"),
        "totalNodesLatest": nodes,
        "totalEdgesLatest": edges,
        "feedsChecked": ingest.get("feedsChecked"),
        "feedsReachable": ingest.get("feedsReachable"),
        "feedsUnreachable": ingest.get("feedsUnreachable"),
        "erroredFeeds": ingest.get("erroredFeeds", []),
        "newDocsLastRun": ingest.get("newDocsFound"),
        "entitiesLastRun": extract.get("entitiesFound") or imp.get("entitiesNew"),
        "relationsLastRun": extract.get("relationsFound") or imp.get("relations"),
        "backlog": backlog,
        "qualifiedTotal": docpack_stage.get("qualifiedTotal"),
        "qualifiedExcluded": docpack_stage.get("qualifiedExcluded"),
    }


def build_runs(logs: list[dict]) -> dict:
    """30-day run history, oldest-first for charting."""
    runs = []
    for log in reversed(logs):
        stages = log.get("stages", {})
        ingest = stages.get("ingest", {})
        extract = stages.get("extract", {})
        imp = stages.get("import", {})
        export_s = stages.get("export", {})

        stage_summary = {}
        for name, s in stages.items():
            stage_summary[name] = {
                "status": s.get("status"),
                "duration_sec": s.get("duration_sec"),
            }

        docpack_s = stages.get("docpack", {})
        runs.append({
            "date": log.get("runDate"),
            "domain": log.get("domain"),
            "status": log.get("status", "unknown"),
            "durationSec": log.get("durationSec"),
            "newDocs": ingest.get("newDocsFound", 0),
            "docsBundled": docpack_s.get("docsBundled", 0),
            "qualifiedTotal": docpack_s.get("qualifiedTotal"),
            "qualifiedExcluded": docpack_s.get("qualifiedExcluded"),
            "feedsReachable": ingest.get("feedsReachable"),
            "feedsChecked": ingest.get("feedsChecked"),
            "entities": extract.get("entitiesFound") or imp.get("entitiesNew"),
            "relations": extract.get("relationsFound") or imp.get("relations"),
            "nodes": export_s.get("totalNodes"),
            "edges": export_s.get("totalEdges"),
            "stages": stage_summary,
        })

    return {"runs": runs, "generatedAt": _now()}


def build_quality(db_path: Path) -> dict:
    """Quality gate + model metrics from SQLite."""
    result: dict = {"available": False, "generatedAt": _now()}

    if not db_path.exists():
        return result

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        if "quality_runs" not in tables or "quality_metrics" not in tables:
            conn.close()
            return result

        result["available"] = True

        # Gate pass rates (all time)
        gate_rows = conn.execute("""
            SELECT metric_name,
                   ROUND(AVG(CASE WHEN passed THEN 1.0 ELSE 0.0 END), 4) AS pass_rate,
                   COUNT(*) AS total
            FROM quality_metrics
            WHERE metric_name IN (
                'evidence_fidelity_rate', 'orphan_rate',
                'zero_value', 'high_conf_bad_evidence'
            )
            GROUP BY metric_name
            ORDER BY metric_name
        """).fetchall()
        result["gates"] = [dict(r) for r in gate_rows]

        # Per-model quality
        model_rows = conn.execute("""
            SELECT model,
                   COUNT(*)                                                AS runs,
                   ROUND(AVG(quality_score), 4)                           AS avg_score,
                   ROUND(MIN(quality_score), 4)                           AS min_score,
                   ROUND(MAX(quality_score), 4)                           AS max_score,
                   ROUND(AVG(CAST(duration_ms AS FLOAT)), 1)              AS avg_duration_ms,
                   SUM(CASE WHEN decision = 'escalate' THEN 1 ELSE 0 END) AS escalated,
                   SUM(CASE WHEN decision = 'reject'   THEN 1 ELSE 0 END) AS rejected
            FROM quality_runs
            WHERE model IS NOT NULL
            GROUP BY model
            ORDER BY runs DESC
        """).fetchall()
        result["models"] = [dict(r) for r in model_rows]

        # Daily quality trend (last 14 days)
        trend_rows = conn.execute("""
            SELECT DATE(started_at)          AS day,
                   ROUND(AVG(quality_score), 4) AS avg_score,
                   COUNT(*)                  AS runs
            FROM quality_runs
            WHERE started_at >= DATE('now', '-14 days')
              AND quality_score IS NOT NULL
            GROUP BY day
            ORDER BY day
        """).fetchall()
        result["dailyTrend"] = [dict(r) for r in trend_rows]

        # Summary
        summary_row = conn.execute("""
            SELECT COUNT(*)                                                AS total_runs,
                   ROUND(AVG(quality_score), 4)                           AS overall_avg,
                   SUM(CASE WHEN decision = 'escalate' THEN 1 ELSE 0 END) AS total_escalated,
                   SUM(CASE WHEN decision = 'reject'   THEN 1 ELSE 0 END) AS total_rejected
            FROM quality_runs
        """).fetchone()
        result["summary"] = dict(summary_row) if summary_row else {}

        conn.close()

    except Exception as e:
        result["error"] = str(e)

    return result


def _parse_feeds_yaml(path: Path) -> list[dict]:
    """Parse feeds.yaml, using PyYAML if available, regex fallback otherwise.

    The fallback handles the simple key: value structure of feeds.yaml
    without any external dependency.
    """
    text = path.read_text()

    # Try PyYAML first
    try:
        import yaml  # type: ignore[import]
        cfg = yaml.safe_load(text)
        return cfg.get("feeds", [])
    except Exception:
        pass

    # Regex fallback: split on feed entry boundaries ("  - ") and parse
    # simple scalar key: value pairs.  Handles str/bool/int values.
    import re
    feeds: list[dict] = []
    # Each entry begins with an optional leading newline + "  - "
    entries = re.split(r"(?:^|\n)  - ", text)
    for entry in entries[1:]:  # skip preamble before first "  - "
        feed: dict = {}
        for line in entry.splitlines():
            m = re.match(r"[ \t]+(\w+):\s*(.*)", line)
            if not m:
                continue
            key, raw = m.group(1), m.group(2).strip().strip("\"'")
            if raw.lower() == "true":
                feed[key] = True
            elif raw.lower() == "false":
                feed[key] = False
            elif re.fullmatch(r"\d+", raw):
                feed[key] = int(raw)
            elif raw and not raw.startswith("#"):
                feed[key] = raw
        if feed.get("name"):
            feeds.append(feed)
    return feeds


def build_feeds(logs: list[dict], config_path: Path) -> dict:
    """Feed list from config, overlaid with reachability data from logs."""
    result: dict = {
        "available": False,
        "generatedAt": _now(),
        "feeds": [],
        "lastRunFeeds": {},
    }

    # Parse feeds.yaml (PyYAML or regex fallback)
    feeds_cfg: list[dict] = []
    if config_path.exists():
        try:
            feeds_cfg = _parse_feeds_yaml(config_path)
            result["available"] = True
        except Exception as e:
            result["parse_error"] = str(e)

    # Build per-feed error counts from logs
    error_counts: dict[str, int] = {}
    for log in logs:
        errored = log.get("stages", {}).get("ingest", {}).get("erroredFeeds", [])
        for entry in errored:
            # Entry format: "feed_name (reason)" or just "feed_name"
            name = entry.split("(")[0].strip() if entry else ""
            if name:
                error_counts[name] = error_counts.get(name, 0) + 1

    num_logs = len(logs)
    for feed in feeds_cfg:
        name = feed.get("name", "")
        result["feeds"].append({
            "name": name,
            "url": feed.get("url", ""),
            "tier": feed.get("tier", ""),
            "signal": feed.get("signal", ""),
            "enabled": feed.get("enabled", True),
            "errored_runs": error_counts.get(name, 0),
            "total_runs": num_logs,
        })

    # Latest run feed summary
    if logs:
        ingest = logs[0].get("stages", {}).get("ingest", {})
        result["lastRunFeeds"] = {
            "checked": ingest.get("feedsChecked"),
            "reachable": ingest.get("feedsReachable"),
            "unreachable": ingest.get("feedsUnreachable"),
            "erroredFeeds": ingest.get("erroredFeeds", []),
        }

    return result


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate dashboard JSON for web/dashboard.html")
    parser.add_argument("--domain", default=None,
                        help="Domain slug (default: ai or PREDICTOR_DOMAIN env var)")
    parser.add_argument("--db", default=None,
                        help="Path to SQLite database (default: data/db/{domain}.db)")
    parser.add_argument("--logs-dir", default=None,
                        help="Directory containing pipeline_*.json logs")
    parser.add_argument("--out-dir", default=str(ROOT / "web" / "data" / "dashboard"),
                        help="Output directory for dashboard JSON files")
    args = parser.parse_args()

    from util.paths import get_db_path, get_logs_dir
    if args.db is None:
        args.db = str(get_db_path(args.domain))
    if args.logs_dir is None:
        args.logs_dir = str(get_logs_dir(args.domain))

    db_path = Path(args.db)
    logs_dir = Path(args.logs_dir)
    out_dir = Path(args.out_dir)
    graphs_live = ROOT / "web" / "data" / "graphs" / "live"

    out_dir.mkdir(parents=True, exist_ok=True)

    logs = load_pipeline_logs(logs_dir)
    print(f"Loaded {len(logs)} pipeline log(s) from {logs_dir}")

    status = build_status(logs, graphs_live)
    (out_dir / "status.json").write_text(json.dumps(status, indent=2))
    print(f"  status.json  — lastRun={status.get('lastRunDate')}  status={status.get('lastRunStatus')}")

    runs = build_runs(logs)
    (out_dir / "runs.json").write_text(json.dumps(runs, indent=2))
    print(f"  runs.json    — {len(runs['runs'])} run(s)")

    quality = build_quality(db_path)
    (out_dir / "quality.json").write_text(json.dumps(quality, indent=2))
    print(f"  quality.json — available={quality['available']}")

    feeds = build_feeds(logs, ROOT / "config" / "feeds.yaml")
    (out_dir / "feeds.json").write_text(json.dumps(feeds, indent=2))
    print(f"  feeds.json   — {len(feeds['feeds'])} feed(s)")

    print(f"\nDashboard data written to {out_dir}/")
    print("Open web/dashboard.html to view.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
