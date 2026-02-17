"""Orchestrate the full daily pipeline and produce a structured run log.

Runs all stages in order:
  1. ingest  — fetch RSS feeds
  2. docpack — bundle cleaned docs for extraction
  3. extract — LLM extraction (if API key available)
  4. import  — import extraction JSON into DB
  5. resolve — entity resolution / deduplication
  6. export  — export Cytoscape.js graph views
  7. trending — compute and export trending view

Writes a JSON run log to data/logs/pipeline_YYYY-MM-DD.json and prints
a one-liner summary suitable for cron email capture.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def utc_now() -> str:
    """Return current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_stage(
    name: str,
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 600,
) -> dict:
    """Run a pipeline stage as a subprocess.

    Args:
        name: Human-readable stage name
        cmd: Command and arguments
        cwd: Working directory
        env: Environment variables (merged with os.environ)
        timeout: Maximum seconds before killing

    Returns:
        Dict with status, duration, output, and returncode
    """
    merged_env = {**os.environ}
    if env:
        merged_env.update(env)

    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=merged_env,
            timeout=timeout,
        )
        duration = time.monotonic() - start
        return {
            "stage": name,
            "status": "ok" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "duration_sec": round(duration, 1),
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - start
        return {
            "stage": name,
            "status": "timeout",
            "returncode": -1,
            "duration_sec": round(duration, 1),
            "stdout": "",
            "stderr": f"Stage {name} timed out after {timeout}s",
        }
    except Exception as e:
        duration = time.monotonic() - start
        return {
            "stage": name,
            "status": "error",
            "returncode": -1,
            "duration_sec": round(duration, 1),
            "stdout": "",
            "stderr": str(e),
        }


def _extract_int_before(text: str, label: str, stats: dict, key: str) -> None:
    """Find the integer immediately before `label` in text and add it to stats[key]."""
    idx = text.find(label)
    if idx < 0:
        return
    before = text[:idx].strip().split()
    if before and before[-1].isdigit():
        stats[key] += int(before[-1])


def parse_ingest_output(stdout: str, stderr: str = "") -> dict:
    """Parse ingest stage stdout (and optionally stderr) for stats.

    Args:
        stdout: Captured stdout from ingest subprocess
        stderr: Captured stderr from ingest subprocess (for diagnostics)

    Returns:
        Dict with feed-level stats and per-feed error details.
    """
    import re

    stats = {
        "feedsChecked": 0,
        "feedsReachable": 0,
        "feedsUnreachable": 0,
        "newDocsFound": 0,
        "duplicatesSkipped": 0,
        "fetchErrors": 0,
    }
    errored_feeds: list[str] = []
    current_feed: str = ""

    for line in stdout.splitlines():
        lower = line.lower().strip()
        # Count feeds checked: "Processing feed: ..." or legacy "Processing: ..."
        if lower.startswith("processing feed:") or lower.startswith("processing:"):
            stats["feedsChecked"] += 1
            # Track current feed name for error association
            current_feed = line.strip().split(":", 1)[-1].strip()
            # Strip limit suffix like " (limit 50)"
            current_feed = re.sub(r"\s*\(limit \d+\)\s*$", "", current_feed)
        # Per-feed success: "Feed OK: N new documents, M duplicates skipped"
        if "feed ok" in lower:
            stats["feedsReachable"] += 1
            _extract_int_before(lower, "new documents", stats, "newDocsFound")
            _extract_int_before(lower, "duplicates skipped", stats, "duplicatesSkipped")
        # Per-feed unreachable: "Feed UNREACHABLE: ..."
        if "feed unreachable" in lower:
            stats["feedsUnreachable"] += 1
            feed_name = line.strip().split(":", 1)[-1].strip() if ":" in line else current_feed
            errored_feeds.append(f"{feed_name} (unreachable)")
        # Per-feed crash: "Feed CRASHED: ..."
        if "feed crashed" in lower:
            stats["feedsUnreachable"] += 1
            stats["fetchErrors"] += 1
            feed_name = line.strip().split(":", 1)[-1].strip() if ":" in line else current_feed
            errored_feeds.append(f"{feed_name} (crashed)")
        # Per-feed errors: "Feed errors: N fetch errors, ..."
        if "feed errors:" in lower:
            stats["feedsReachable"] += 1  # feed was reachable but had article fetch errors
            _extract_int_before(lower, "fetch errors", stats, "fetchErrors")
            _extract_int_before(lower, "saved", stats, "newDocsFound")
            _extract_int_before(lower, "duplicates skipped", stats, "duplicatesSkipped")
            errored_feeds.append(f"{current_feed} (fetch errors)")
        # Summary line: "Fetched N items, skipped M, errors E. Feeds reachable: R/T."
        if "feeds reachable:" in lower:
            m = re.search(r"feeds reachable:\s*(\d+)/(\d+)", lower)
            if m:
                summary_reachable = int(m.group(1))
                summary_total = int(m.group(2))
                # Always use summary as authoritative for reachable count
                if summary_reachable > stats["feedsReachable"]:
                    stats["feedsReachable"] = summary_reachable
                # Derive unreachable from summary if not counted per-feed
                summary_unreachable = summary_total - summary_reachable
                if summary_unreachable > stats["feedsUnreachable"]:
                    stats["feedsUnreachable"] = summary_unreachable
            # Extract fetch errors from summary: "errors N"
            err_match = re.search(r"errors\s+(\d+)", lower)
            if err_match:
                summary_errors = int(err_match.group(1))
                if summary_errors > stats["fetchErrors"]:
                    stats["fetchErrors"] = summary_errors
            continue  # Don't process summary line further (avoid false positives)
        # Legacy: "Saved N new documents"
        if ("new documents" in lower or "saved" in lower) and "feed ok" not in lower and "feed errors:" not in lower:
            for word in line.split():
                if word.isdigit():
                    stats["newDocsFound"] += int(word)
                    break
        # Legacy: "Skipping N existing duplicates"
        if "skip" in lower and ("exist" in lower or "duplicate" in lower) and "feed ok" not in lower and "feed errors:" not in lower:
            for word in line.split():
                if word.isdigit():
                    stats["duplicatesSkipped"] += int(word)
                    break

    # Parse stderr for feed-specific diagnostic errors
    for line in stderr.splitlines():
        lower = line.lower().strip()
        # Collect bozo exceptions as feed warnings
        if "bozo_exception=" in lower and "diag" in lower:
            # Extract feed URL from preceding [diag] line for context
            exc_part = line.strip().split("bozo_exception=")[-1] if "bozo_exception=" in line else ""
            if exc_part:
                errored_feeds.append(f"bozo: {exc_part[:80]}")

    if errored_feeds:
        stats["erroredFeeds"] = errored_feeds
    return stats


def parse_docpack_output(stdout: str) -> dict:
    """Parse docpack stage stdout for stats."""
    stats = {"docsBundled": 0}
    for line in stdout.splitlines():
        if "bundled" in line.lower():
            for word in line.split():
                if word.isdigit():
                    stats["docsBundled"] = int(word)
                    break
    return stats


def parse_extract_output(stdout: str) -> dict:
    """Parse extract stage stdout for stats."""
    stats = {
        "docsExtracted": 0,
        "entitiesFound": 0,
        "relationsFound": 0,
        "validationErrors": 0,
        "escalated": 0,
    }
    for line in stdout.splitlines():
        if line.startswith("Done."):
            parts = line.split(",")
            for part in parts:
                part = part.strip()
                if "Succeeded" in part:
                    for word in part.split():
                        if word.isdigit():
                            stats["docsExtracted"] = int(word)
                            break
                if "Failed" in part:
                    for word in part.split():
                        if word.isdigit():
                            stats["validationErrors"] = int(word)
                            break
                if "Escalated" in part:
                    for word in part.split():
                        if "/" in word and word.split("/")[0].isdigit():
                            stats["escalated"] = int(word.split("/")[0])
                            break
                        elif word.isdigit():
                            stats["escalated"] = int(word)
                            break
        # Count entities/relations from individual doc lines
        if "entities" in line and "relations" in line:
            parts = line.split("(")
            if len(parts) > 1:
                inner = parts[-1].rstrip(")")
                for token in inner.split(","):
                    token = token.strip()
                    if "entit" in token:
                        for w in token.split():
                            if w.isdigit():
                                stats["entitiesFound"] += int(w)
                                break
                    if "relation" in token:
                        for w in token.split():
                            if w.isdigit():
                                stats["relationsFound"] += int(w)
                                break
    return stats


def parse_import_output(stdout: str) -> dict:
    """Parse import stage stdout for stats."""
    stats = {
        "filesImported": 0,
        "entitiesNew": 0,
        "entitiesResolved": 0,
        "relations": 0,
        "evidenceRecords": 0,
    }
    import re
    for line in stdout.splitlines():
        if "imported" in line.lower() and "extraction" in line.lower():
            for word in line.split():
                if word.isdigit():
                    stats["filesImported"] = int(word)
                    break
        # Match "4 new" pattern specifically
        new_match = re.search(r"(\d+)\s+new", line.lower())
        if new_match:
            stats["entitiesNew"] = int(new_match.group(1))
        resolved_match = re.search(r"(\d+)\s+resolved", line.lower())
        if resolved_match:
            stats["entitiesResolved"] = int(resolved_match.group(1))
        # "- 12 relations" (but not lines containing "evidence")
        if "relations" in line.lower() and "evidence" not in line.lower() and line.strip().startswith("-"):
            for word in line.split():
                if word.isdigit():
                    stats["relations"] = int(word)
                    break
        if "evidence" in line.lower() and line.strip().startswith("-"):
            for word in line.split():
                if word.isdigit():
                    stats["evidenceRecords"] = int(word)
                    break
    return stats


def parse_export_output(stdout: str) -> dict:
    """Parse export stage stdout for stats."""
    stats = {"views": [], "totalNodes": 0, "totalEdges": 0}
    for line in stdout.splitlines():
        if "nodes" in line.lower() and "edges" in line.lower():
            view_name = ""
            nodes = 0
            edges = 0
            if "-" in line:
                view_name = line.split("-")[-1].strip().split()[0] if "-" in line else ""
            for i, word in enumerate(line.split()):
                if word.startswith("(") and word[1:].isdigit():
                    nodes = int(word[1:])
                elif word.isdigit():
                    # Check context
                    words = line.split()
                    idx = words.index(word) if word in words else -1
                    if idx >= 0 and idx + 1 < len(words) and "node" in words[idx + 1]:
                        nodes = int(word)
                    elif idx >= 0 and idx + 1 < len(words) and "edge" in words[idx + 1]:
                        edges = int(word)
            stats["totalNodes"] += nodes
            stats["totalEdges"] += edges
            if view_name:
                stats["views"].append(view_name)
    return stats


def parse_trending_output(stdout: str) -> dict:
    """Parse trending stage stdout for stats."""
    stats = {"trendingNodes": 0, "trendingEdges": 0}
    for line in stdout.splitlines():
        if "nodes" in line.lower() and "edges" in line.lower():
            for i, word in enumerate(line.split()):
                if word.isdigit():
                    words = line.split()
                    idx = words.index(word)
                    if idx + 1 < len(words) and "node" in words[idx + 1]:
                        stats["trendingNodes"] = int(word)
                    elif idx + 1 < len(words) and "edge" in words[idx + 1]:
                        stats["trendingEdges"] = int(word)
    return stats


def copy_graphs_to_live(graphs_dir: Path, run_date: str, web_live_dir: Path) -> bool:
    """Copy today's graph output to web/data/graphs/live/ for the UI.

    Args:
        graphs_dir: Base graphs directory (data/graphs)
        run_date: Today's date string (YYYY-MM-DD)
        web_live_dir: Target directory (web/data/graphs/live)

    Returns:
        True if copy succeeded
    """
    source_dir = graphs_dir / run_date
    if not source_dir.exists():
        return False

    web_live_dir.mkdir(parents=True, exist_ok=True)
    for json_file in source_dir.glob("*.json"):
        shutil.copy2(json_file, web_live_dir / json_file.name)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the full daily pipeline with structured logging."
    )
    parser.add_argument(
        "--db", default="data/db/predictor.db",
        help="Path to SQLite database (default: data/db/predictor.db)",
    )
    parser.add_argument(
        "--date", default=date.today().isoformat(),
        help="Pipeline date, YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--graphs-dir", default="data/graphs",
        help="Graph output directory (default: data/graphs)",
    )
    parser.add_argument(
        "--log-dir", default="data/logs",
        help="Log output directory (default: data/logs)",
    )
    parser.add_argument(
        "--web-live-dir", default="web/data/graphs/live",
        help="Web client live graph directory (default: web/data/graphs/live)",
    )
    parser.add_argument(
        "--skip-extract", action="store_true",
        help="Skip extraction stage (Mode B: manual extraction workflow)",
    )
    parser.add_argument(
        "--no-escalate", action="store_true",
        help="Disable escalation mode; run primary model on all docs with shadow comparison instead",
    )
    parser.add_argument(
        "--copy-to-live", action="store_true", default=True,
        help="Copy graph output to web/data/graphs/live/ after export (default: True)",
    )
    parser.add_argument(
        "--no-copy-to-live", action="store_false", dest="copy_to_live",
        help="Do NOT copy graph output to web/data/graphs/live/ after export",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be run without executing",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    run_date = args.date
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    db_path = args.db
    graphs_dir = args.graphs_dir
    docpack_path = f"data/docpacks/daily_bundle_{run_date}.jsonl"

    # Initialize run log
    run_log: dict = {
        "runDate": run_date,
        "runId": run_id,
        "startedAt": utc_now(),
        "durationSec": 0,
        "status": "running",
        "stages": {},
    }

    # Lock file for safe-reboot awareness
    lock_path = project_root / "data" / "pipeline.lock"

    # Define pipeline stages
    stages = [
        {
            "name": "ingest",
            "cmd": [
                sys.executable, "-m", "ingest.rss",
                "--config", "config/feeds.yaml",
                "--db", db_path,
                "--skip-existing",
            ],
            "parse": parse_ingest_output,
            "fatal": True,
        },
        {
            "name": "docpack",
            "cmd": [
                sys.executable, "scripts/build_docpack.py",
                "--db", db_path,
                "--date", run_date,
            ],
            "parse": parse_docpack_output,
            "fatal": False,
        },
        {
            "name": "extract",
            "cmd": [
                sys.executable, "scripts/run_extract.py",
                "--docpack", docpack_path,
                "--db", db_path,
            ] + (["--shadow", "--parallel"] if args.no_escalate else ["--escalate"]),
            "parse": parse_extract_output,
            "fatal": False,
            "skip": args.skip_extract,
        },
        {
            "name": "import",
            "cmd": [
                sys.executable, "scripts/import_extractions.py",
                "--db", db_path,
            ],
            "parse": parse_import_output,
            "fatal": False,
        },
        {
            "name": "resolve",
            "cmd": [
                sys.executable, "scripts/run_resolve.py",
                "--db", db_path,
            ],
            "parse": lambda s: {},
            "fatal": False,
        },
        {
            "name": "export",
            "cmd": [
                sys.executable, "scripts/run_export.py",
                "--db", db_path,
                "--output-dir", graphs_dir,
                "--date", run_date,
            ],
            "parse": parse_export_output,
            "fatal": False,
        },
        {
            "name": "trending",
            "cmd": [
                sys.executable, "scripts/run_trending.py",
                "--db", db_path,
                "--output-dir", f"{graphs_dir}/{run_date}",
            ],
            "parse": parse_trending_output,
            "fatal": False,
        },
    ]

    if args.dry_run:
        print("DRY RUN — would execute:")
        for stage in stages:
            skip = stage.get("skip", False)
            label = " [SKIP]" if skip else ""
            print(f"  {stage['name']}{label}: {' '.join(stage['cmd'])}")
        return 0

    # Create lock file
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch()

    pipeline_start = time.monotonic()
    overall_status = "success"
    failed_stages = []

    print(f"=== Pipeline run {run_id} ({run_date}) ===")
    print()

    try:
        for stage in stages:
            name = stage["name"]

            if stage.get("skip", False):
                print(f"[{name}] SKIPPED")
                run_log["stages"][name] = {"status": "skipped"}
                continue

            print(f"[{name}] Running...", flush=True)
            result = run_stage(name, stage["cmd"], cwd=project_root)

            # Parse stage-specific stats (ingest parser also uses stderr)
            if name == "ingest":
                stage_stats = stage["parse"](result["stdout"], result["stderr"])
            else:
                stage_stats = stage["parse"](result["stdout"])

            run_log["stages"][name] = {
                "status": result["status"],
                "duration_sec": result["duration_sec"],
                **stage_stats,
            }

            # Always save raw stdout/stderr for diagnostics
            if result["stdout"].strip():
                run_log["stages"][name]["stdout"] = result["stdout"][-2000:]
            if result["stderr"].strip():
                run_log["stages"][name]["stderr"] = result["stderr"][-2000:]

            if result["status"] == "ok":
                # For ingest: always show key feed stats even when 0
                if name == "ingest":
                    errored = stage_stats.pop("erroredFeeds", [])
                    key_stats = ["feedsChecked", "feedsReachable", "feedsUnreachable",
                                 "newDocsFound", "fetchErrors"]
                    parts = []
                    for k in key_stats:
                        v = stage_stats.get(k, 0)
                        parts.append(f"{k}={v}")
                    # Add non-zero secondary stats
                    for k, v in stage_stats.items():
                        if v and k not in key_stats:
                            parts.append(f"{k}={v}")
                    stats_str = ", ".join(parts)
                    print(f"[{name}] OK ({result['duration_sec']}s) — {stats_str}")
                    # Print errored feed names
                    for feed_err in errored:
                        print(f"  ERR: {feed_err}")
                else:
                    stats_str = ", ".join(f"{k}={v}" for k, v in stage_stats.items() if v) or "ok"
                    print(f"[{name}] OK ({result['duration_sec']}s) — {stats_str}")
                # Print stderr warnings even on success (more lines for ingest)
                if result["stderr"].strip():
                    max_warn = 10 if name == "ingest" else 5
                    stderr_lines = result["stderr"].strip().splitlines()
                    # For ingest, show error-related lines first, then last N
                    if name == "ingest":
                        err_lines = [l for l in stderr_lines
                                     if any(kw in l.lower() for kw in
                                            ["bozo", "unreachable", "error", "crash", "fail"])]
                        other_lines = [l for l in stderr_lines[-max_warn:]
                                       if l not in err_lines]
                        warn_lines = err_lines + other_lines
                    else:
                        warn_lines = stderr_lines[-max_warn:]
                    for line in warn_lines[:max_warn]:
                        print(f"  WARN: {line.strip()}")
            else:
                error_msg = result["stderr"][-200:] if result["stderr"] else "unknown error"
                print(f"[{name}] FAILED (rc={result['returncode']}): {error_msg}")
                run_log["stages"][name]["error"] = error_msg
                failed_stages.append(name)

                if stage["fatal"]:
                    overall_status = "failed"
                    print(f"\nFatal stage '{name}' failed. Aborting pipeline.")
                    break

        # Copy graphs to live directory if requested
        if args.copy_to_live and overall_status != "failed":
            copied = copy_graphs_to_live(
                Path(graphs_dir), run_date, project_root / args.web_live_dir
            )
            if copied:
                print(f"\nCopied graphs to {args.web_live_dir}/")
            else:
                print(f"\nWARNING: No graphs found for {run_date} to copy")

    finally:
        # Remove lock file
        lock_path.unlink(missing_ok=True)

    # Finalize run log
    total_duration = time.monotonic() - pipeline_start
    if overall_status != "failed" and failed_stages:
        overall_status = "partial"

    run_log["durationSec"] = round(total_duration, 1)
    run_log["status"] = overall_status
    run_log["completedAt"] = utc_now()
    if failed_stages:
        run_log["failedStages"] = failed_stages

    # Write log file
    log_dir = project_root / args.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"pipeline_{run_date}.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(run_log, f, indent=2, ensure_ascii=False)

    # Print summary
    print()
    stage_summary = []
    ingest = run_log["stages"].get("ingest", {})
    extract = run_log["stages"].get("extract", {})
    export = run_log["stages"].get("export", {})

    new_docs = ingest.get("newDocsFound", "?")
    entities = extract.get("entitiesFound", "?")
    relations = extract.get("relationsFound", "?")
    unreachable = ingest.get("feedsUnreachable", 0)
    feeds = f"{ingest.get('feedsReachable', '?')}/{ingest.get('feedsChecked', '?')}"
    if unreachable:
        feeds += f" ({unreachable} unreachable)"

    status_icon = {"success": "OK", "partial": "PARTIAL", "failed": "FAILED"}.get(
        overall_status, overall_status
    )
    summary = (
        f"{status_icon} {run_date}: {new_docs} docs, "
        f"{entities} entities, {relations} relations | "
        f"{feeds} feeds | {run_log['durationSec']}s"
    )
    print(summary)
    print(f"Log: {log_path}")

    return 0 if overall_status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
