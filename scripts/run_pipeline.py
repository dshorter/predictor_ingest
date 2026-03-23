"""Orchestrate the full daily pipeline and produce a structured run log.

Runs all stages in order:
  1. ingest     — fetch RSS feeds
  2. docpack    — bundle cleaned docs for extraction
  3. extract    — LLM extraction (if API key available)
  4. import     — import extraction JSON into DB
  5. synthesize — cross-document synthesis (LLM, domain-configurable)
  6. resolve    — entity resolution / deduplication + LLM disambiguation
  7. infer      — rule-based relation inference (domain-configurable)
  8. export     — export Cytoscape.js graph views
  9. trending   — compute and export trending view with narratives

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


def load_dotenv() -> None:
    """Load .env file from project root if it exists."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.replace("\r", "").strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("\"'").strip()
                    if key and key not in os.environ:
                        os.environ[key] = value


load_dotenv()


def utc_now() -> str:
    """Return current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_stage(
    name: str,
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int | None = 600,
    stream: bool = False,
) -> dict:
    """Run a pipeline stage as a subprocess.

    Args:
        name: Human-readable stage name
        cmd: Command and arguments
        cwd: Working directory
        env: Environment variables (merged with os.environ)
        timeout: Maximum seconds before killing (None = no timeout)
        stream: If True, print stdout/stderr lines in real-time
                (prefixed with stage name) while still capturing them.

    Returns:
        Dict with status, duration, output, and returncode
    """
    import select
    import io

    merged_env = {**os.environ}
    if env:
        merged_env.update(env)

    start = time.monotonic()

    if not stream:
        # Original captured mode for quick stages
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

    # Streaming mode: show output in real-time while capturing it
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            env=merged_env,
        )

        # Read both streams without blocking using select()
        streams = {proc.stdout: stdout_lines, proc.stderr: stderr_lines}
        while streams:
            # Check timeout (skip if timeout is None)
            elapsed = time.monotonic() - start
            if timeout is not None and elapsed > timeout:
                proc.kill()
                proc.wait()
                captured_out = "".join(stdout_lines)
                captured_err = "".join(stderr_lines)
                captured_err += f"\nStage {name} timed out after {timeout}s"
                duration = time.monotonic() - start
                return {
                    "stage": name,
                    "status": "timeout",
                    "returncode": -1,
                    "duration_sec": round(duration, 1),
                    "stdout": captured_out,
                    "stderr": captured_err,
                }

            if timeout is not None:
                remaining = max(0.1, timeout - elapsed)
                poll_interval = min(1.0, remaining)
            else:
                poll_interval = 1.0
            try:
                readable, _, _ = select.select(
                    list(streams.keys()), [], [], poll_interval
                )
            except (ValueError, OSError):
                break

            for stream_obj in readable:
                line = stream_obj.readline()
                if not line:
                    # EOF on this stream
                    streams.pop(stream_obj, None)
                    continue
                buf = streams.get(stream_obj)
                if buf is not None:
                    buf.append(line)
                # Print with stage prefix — stdout gets "  " indent, stderr gets "  WARN:"
                if stream_obj is proc.stdout:
                    print(f"  {line.rstrip()}", flush=True)
                else:
                    print(f"  WARN: {line.rstrip()}", flush=True)

        proc.wait(timeout=10)
        duration = time.monotonic() - start
        return {
            "stage": name,
            "status": "ok" if proc.returncode == 0 else "error",
            "returncode": proc.returncode,
            "duration_sec": round(duration, 1),
            "stdout": "".join(stdout_lines),
            "stderr": "".join(stderr_lines),
        }

    except Exception as e:
        duration = time.monotonic() - start
        return {
            "stage": name,
            "status": "error",
            "returncode": -1,
            "duration_sec": round(duration, 1),
            "stdout": "".join(stdout_lines),
            "stderr": "".join(stderr_lines) + f"\n{e}",
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
        # Count feeds checked: "[N/M] Processing feed: ..." or legacy "Processing feed: ..."
        # Strip optional "[N/M] " prefix before matching
        check_lower = re.sub(r"^\[\d+/\d+\]\s*", "", lower)
        if check_lower.startswith("processing feed:") or check_lower.startswith("processing:"):
            stats["feedsChecked"] += 1
            # Track current feed name for error association
            # Split on "Processing feed:" (or "Processing:") to get the feed name
            feed_part = re.split(r"processing(?:\s+feed)?:", line.strip(), flags=re.IGNORECASE)
            current_feed = feed_part[-1].strip() if len(feed_part) > 1 else ""
            # Strip limit suffix like " (limit 50)" and elapsed time like " (elapsed 42s)"
            current_feed = re.sub(r"\s*\((?:limit \d+|elapsed [^)]+)\)\s*", "", current_feed).strip()
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
    stats = {"docsBundled": 0, "qualifiedTotal": 0, "qualifiedExcluded": 0}
    for line in stdout.splitlines():
        if "bundled" in line.lower():
            for word in line.split():
                if word.isdigit():
                    stats["docsBundled"] = int(word)
                    break
        # "Qualified: 42 total, 17 excluded by budget"
        if line.startswith("Qualified:"):
            parts = line.split(",")
            for part in parts:
                part = part.strip()
                for word in part.split():
                    if word.isdigit():
                        if "total" in part:
                            stats["qualifiedTotal"] = int(word)
                        elif "excluded" in part:
                            stats["qualifiedExcluded"] = int(word)
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
        "unmappedRelationTypes": [],
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
        # Capture unmapped relation types (e.g., "Unmapped relation types: WORKS_ON (1), LOCATED_IN (2)")
        if line.startswith("Unmapped relation types:"):
            import re
            for m in re.finditer(r"([A-Z_]+)\s*\((\d+)\)", line):
                stats["unmappedRelationTypes"].append(
                    {"type": m.group(1), "count": int(m.group(2))}
                )
    return stats


def parse_import_output(stdout: str) -> dict:
    """Parse import stage stdout for stats."""
    stats = {
        "filesImported": 0,
        "entitiesNew": 0,
        "entitiesResolved": 0,
        "relations": 0,
        "mentionsGenerated": 0,
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
        # "- 12 relations" (but not lines containing "evidence" or "mentions")
        if "relations" in line.lower() and "evidence" not in line.lower() and "mentions" not in line.lower() and line.strip().startswith("-"):
            for word in line.split():
                if word.isdigit():
                    stats["relations"] = int(word)
                    break
        # "- 28 mentions (doc→entity)"
        if "mentions" in line.lower() and line.strip().startswith("-"):
            for word in line.split():
                if word.isdigit():
                    stats["mentionsGenerated"] = int(word)
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
    """Parse trending stage stdout for stats.

    Expected narrative lines from narratives.py:
        - N LLM narratives returned
        - N narratives mapped to entity IDs
        - N name mismatches dropped (LLM name not in context)
        - N narrative context skipped (entity_id not in entities table)
    """
    import re as _re
    stats = {
        "trendingNodes": 0,
        "trendingEdges": 0,
        "narrativesGenerated": 0,
        "narrativesLlmReturned": 0,
        "narrativesMapped": 0,
        "narrativesMismatches": 0,
        "narrativesContextSkipped": 0,
    }
    for line in stdout.splitlines():
        lower = line.strip().lower()
        if "nodes" in lower and "edges" in lower:
            for i, word in enumerate(line.split()):
                if word.isdigit():
                    words = line.split()
                    idx = words.index(word)
                    if idx + 1 < len(words) and "node" in words[idx + 1]:
                        stats["trendingNodes"] = int(word)
                    elif idx + 1 < len(words) and "edge" in words[idx + 1]:
                        stats["trendingEdges"] = int(word)
        # "Generated narratives for 10 entities"
        elif "generated narratives" in lower:
            m = _re.search(r"(\d+)", line)
            if m:
                stats["narrativesGenerated"] = int(m.group(1))
        elif "llm narratives returned" in lower:
            m = _re.search(r"(\d+)", line)
            if m:
                stats["narrativesLlmReturned"] = int(m.group(1))
        elif "narratives mapped to entity" in lower:
            m = _re.search(r"(\d+)", line)
            if m:
                stats["narrativesMapped"] = int(m.group(1))
        elif "name mismatches dropped" in lower:
            m = _re.search(r"(\d+)", line)
            if m:
                stats["narrativesMismatches"] = int(m.group(1))
        elif "narrative context skipped" in lower:
            m = _re.search(r"(\d+)", line)
            if m:
                stats["narrativesContextSkipped"] = int(m.group(1))
    return stats


def parse_synthesize_output(stdout: str) -> dict:
    """Parse synthesize stage stdout for stats.

    Expected output format from run_synthesize.py:
        Synthesis complete:
          - 3 document clusters processed
          - 5 entities corroborated
          - 2 relations inferred
          - 3 LLM calls
          - 1234ms
    """
    import re
    stats = {
        "batchesProcessed": 0,
        "entitiesCorroborated": 0,
        "relationsInferred": 0,
        "llmCalls": 0,
        "durationMs": 0,
    }
    for line in stdout.splitlines():
        lower = line.strip().lower()
        if "document clusters processed" in lower or "clusters processed" in lower:
            m = re.search(r"(\d+)", line)
            if m:
                stats["batchesProcessed"] = int(m.group(1))
        elif "entities corroborated" in lower:
            m = re.search(r"(\d+)", line)
            if m:
                stats["entitiesCorroborated"] = int(m.group(1))
        elif "relations inferred" in lower:
            m = re.search(r"(\d+)", line)
            if m:
                stats["relationsInferred"] = int(m.group(1))
        elif "llm calls" in lower:
            m = re.search(r"(\d+)", line)
            if m:
                stats["llmCalls"] = int(m.group(1))
        elif lower.endswith("ms") and lower.startswith("-"):
            m = re.search(r"(\d+)ms", lower)
            if m:
                stats["durationMs"] = int(m.group(1))
    return stats


def parse_resolve_output(stdout: str) -> dict:
    """Parse resolve stage stdout for stats.

    Expected output format from run_resolve.py:
        Resolution pass complete:
          - 42 entities checked
          - 3 merges performed
          - 12 gray-zone pairs evaluated by LLM
          - 2 LLM-confirmed merges
          - 8 kept separate
          - 2 uncertain
    """
    import re
    stats = {
        "entitiesChecked": 0,
        "mergesPerformed": 0,
        "disambigPairsEvaluated": 0,
        "disambigMerges": 0,
        "disambigKeptSeparate": 0,
        "disambigUncertain": 0,
    }
    for line in stdout.splitlines():
        lower = line.strip().lower()
        if "entities checked" in lower:
            m = re.search(r"(\d+)", line)
            if m:
                stats["entitiesChecked"] = int(m.group(1))
        elif "merges performed" in lower:
            m = re.search(r"(\d+)", line)
            if m:
                stats["mergesPerformed"] = int(m.group(1))
        elif "gray-zone pairs evaluated" in lower or "pairs evaluated" in lower:
            m = re.search(r"(\d+)", line)
            if m:
                stats["disambigPairsEvaluated"] = int(m.group(1))
        elif "llm-confirmed merges" in lower or "confirmed merges" in lower:
            m = re.search(r"(\d+)", line)
            if m:
                stats["disambigMerges"] = int(m.group(1))
        elif "kept separate" in lower:
            m = re.search(r"(\d+)", line)
            if m:
                stats["disambigKeptSeparate"] = int(m.group(1))
        elif "uncertain" in lower and "merges" not in lower:
            m = re.search(r"(\d+)", line)
            if m:
                stats["disambigUncertain"] = int(m.group(1))
    return stats


def parse_infer_output(stdout: str) -> dict:
    """Parse infer stage stdout for stats.

    Expected output format from run_infer.py:
        Inference pass complete:
          - 5 rules evaluated
          - 12 relations inferred
          - 3 skipped (already existed)
          - 450ms
    """
    import re
    stats = {
        "rulesEvaluated": 0,
        "relationsInferred": 0,
        "relationsSkipped": 0,
        "durationMs": 0,
    }
    for line in stdout.splitlines():
        lower = line.strip().lower()
        if "rules evaluated" in lower:
            m = re.search(r"(\d+)", line)
            if m:
                stats["rulesEvaluated"] = int(m.group(1))
        elif "relations inferred" in lower:
            m = re.search(r"(\d+)", line)
            if m:
                stats["relationsInferred"] = int(m.group(1))
        elif "skipped" in lower and ("already existed" in lower or "relations" in lower):
            m = re.search(r"(\d+)", line)
            if m:
                stats["relationsSkipped"] = int(m.group(1))
        elif lower.endswith("ms") and lower.startswith("-"):
            m = re.search(r"(\d+)ms", lower)
            if m:
                stats["durationMs"] = int(m.group(1))
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


def _persist_run_stats(db_path: Path, run_log: dict, domain: str) -> None:
    """Write pipeline_runs and funnel_stats rows to the database."""
    try:
        import sqlite3
        if not db_path.exists():
            return
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        stages = run_log.get("stages", {})
        ingest = stages.get("ingest", {})
        docpack = stages.get("docpack", {})
        extract = stages.get("extract", {})
        imp = stages.get("import", {})
        synthesize = stages.get("synthesize", {})
        resolve = stages.get("resolve", {})
        infer = stages.get("infer", {})
        export = stages.get("export", {})
        trending = stages.get("trending", {})

        run_date = run_log.get("runDate", "")

        # Ensure new columns exist (additive migration — safe to repeat)
        _ensure_pipeline_runs_columns(conn)

        # pipeline_runs — core columns + new feature columns
        conn.execute(
            """INSERT OR REPLACE INTO pipeline_runs
               (run_date, domain, status, duration_sec, started_at, completed_at,
                docs_ingested, docs_selected, docs_excluded, docs_extracted,
                docs_escalated, entities_new, entities_resolved, relations_added,
                nodes_exported, edges_exported, trending_nodes, error_message,
                synthesis_batches, synthesis_corroborated, synthesis_relations,
                disambig_pairs, disambig_merges, disambig_kept_separate,
                infer_rules, infer_relations, infer_skipped,
                narratives_generated, resolve_merges)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_date, domain, run_log.get("status", "unknown"),
             run_log.get("durationSec"), run_log.get("startedAt"),
             run_log.get("completedAt"),
             ingest.get("newDocsFound", 0),
             docpack.get("docsBundled", 0),
             docpack.get("qualifiedExcluded", 0),
             extract.get("docsExtracted", 0),
             extract.get("escalated", 0),
             imp.get("entitiesNew", 0),
             imp.get("entitiesResolved", 0),
             imp.get("relations", 0),
             export.get("totalNodes", 0),
             export.get("totalEdges", 0),
             trending.get("trendingNodes", 0),
             "; ".join(run_log.get("failedStages", [])),
             # New feature columns
             synthesize.get("batchesProcessed", 0),
             synthesize.get("entitiesCorroborated", 0),
             synthesize.get("relationsInferred", 0),
             resolve.get("disambigPairsEvaluated", 0),
             resolve.get("disambigMerges", 0),
             resolve.get("disambigKeptSeparate", 0),
             infer.get("rulesEvaluated", 0),
             infer.get("relationsInferred", 0),
             infer.get("relationsSkipped", 0),
             trending.get("narrativesGenerated", 0),
             resolve.get("mergesPerformed", 0)),
        )

        # funnel_stats — one row per stage (now includes synthesize, resolve, infer)
        funnel_data = [
            ("ingest", ingest.get("newDocsFound", 0) + ingest.get("duplicatesSkipped", 0),
             ingest.get("newDocsFound", 0), ingest.get("duplicatesSkipped", 0) + ingest.get("fetchErrors", 0),
             json.dumps({"duplicates": ingest.get("duplicatesSkipped", 0),
                         "fetch_errors": ingest.get("fetchErrors", 0)})),
            ("select", docpack.get("qualifiedTotal", 0), docpack.get("docsBundled", 0),
             docpack.get("qualifiedExcluded", 0),
             json.dumps({"budget_exceeded": docpack.get("qualifiedExcluded", 0)})),
            ("extract", docpack.get("docsBundled", 0), extract.get("docsExtracted", 0),
             extract.get("validationErrors", 0),
             json.dumps({"validation_errors": extract.get("validationErrors", 0),
                         "escalated": extract.get("escalated", 0)})),
            ("import", extract.get("docsExtracted", 0), imp.get("filesImported", 0),
             imp.get("errors", 0) if isinstance(imp.get("errors"), int) else 0,
             None),
            ("synthesize", synthesize.get("batchesProcessed", 0),
             synthesize.get("relationsInferred", 0) + synthesize.get("entitiesCorroborated", 0),
             0,
             json.dumps({"llm_calls": synthesize.get("llmCalls", 0),
                         "entities_corroborated": synthesize.get("entitiesCorroborated", 0),
                         "relations_inferred": synthesize.get("relationsInferred", 0)})),
            ("resolve", resolve.get("entitiesChecked", 0),
             resolve.get("mergesPerformed", 0) + resolve.get("disambigMerges", 0),
             0,
             json.dumps({"fuzzy_merges": resolve.get("mergesPerformed", 0),
                         "disambig_pairs": resolve.get("disambigPairsEvaluated", 0),
                         "disambig_merges": resolve.get("disambigMerges", 0),
                         "disambig_kept_separate": resolve.get("disambigKeptSeparate", 0)})),
            ("infer", infer.get("rulesEvaluated", 0),
             infer.get("relationsInferred", 0),
             infer.get("relationsSkipped", 0),
             json.dumps({"rules_evaluated": infer.get("rulesEvaluated", 0),
                         "relations_skipped": infer.get("relationsSkipped", 0)})),
            ("export", imp.get("filesImported", 0), export.get("totalNodes", 0), 0, None),
            ("trending", export.get("totalNodes", 0), trending.get("trendingNodes", 0), 0,
             json.dumps({"narratives": trending.get("narrativesGenerated", 0)})
             if trending.get("narrativesGenerated", 0) else None),
        ]
        for stage, docs_in, docs_out, docs_dropped, drop_reasons in funnel_data:
            conn.execute(
                """INSERT OR REPLACE INTO funnel_stats
                   (run_date, domain, stage, docs_in, docs_out, docs_dropped, drop_reasons)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (run_date, domain, stage, docs_in, docs_out, docs_dropped, drop_reasons),
            )

        conn.commit()
        conn.close()
    except Exception:
        pass  # analytics should never break the pipeline


def _ensure_pipeline_runs_columns(conn: sqlite3.Connection) -> None:
    """Add new feature columns to pipeline_runs if they don't exist yet.

    Safe to call repeatedly — each ALTER TABLE is wrapped in a try/except
    that silently handles the 'duplicate column' case.
    """
    new_columns = [
        ("synthesis_batches", "INTEGER DEFAULT 0"),
        ("synthesis_corroborated", "INTEGER DEFAULT 0"),
        ("synthesis_relations", "INTEGER DEFAULT 0"),
        ("disambig_pairs", "INTEGER DEFAULT 0"),
        ("disambig_merges", "INTEGER DEFAULT 0"),
        ("disambig_kept_separate", "INTEGER DEFAULT 0"),
        ("infer_rules", "INTEGER DEFAULT 0"),
        ("infer_relations", "INTEGER DEFAULT 0"),
        ("infer_skipped", "INTEGER DEFAULT 0"),
        ("narratives_generated", "INTEGER DEFAULT 0"),
        ("resolve_merges", "INTEGER DEFAULT 0"),
    ]
    existing = {row[1] for row in conn.execute("PRAGMA table_info(pipeline_runs)").fetchall()}
    for col_name, col_def in new_columns:
        if col_name not in existing:
            try:
                conn.execute(f"ALTER TABLE pipeline_runs ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass  # column already exists (race condition or schema mismatch)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the full daily pipeline with structured logging."
    )
    parser.add_argument(
        "--db", default=None,
        help="Path to SQLite database (default: data/db/{domain}.db)",
    )
    parser.add_argument(
        "--date", default=date.today().isoformat(),
        help="Pipeline date, YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--graphs-dir", default=None,
        help="Graph output directory (default: data/graphs/{domain})",
    )
    parser.add_argument(
        "--log-dir", default=None,
        help="Log output directory (default: data/logs/{domain})",
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
        "--budget", type=int, default=None,
        help="Extraction budget: target number of docs to extract per run. "
             "Enables quality-based selection in docpack stage. "
             "Goal: 10-20, stretch up to budget+5 for high-quality docs.",
    )
    parser.add_argument(
        "--no-escalate", action="store_true",
        help="Disable escalation mode; run primary model only (no cheap model, no shadow)",
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
        "--no-timeout", action="store_true",
        help="Disable all stage timeouts (useful for self-hosted servers)",
    )
    parser.add_argument(
        "--domain", default="ai",
        help="Domain slug to use (default: ai). Loads config from domains/<slug>/.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be run without executing",
    )
    args = parser.parse_args()

    # Set active domain before any module imports that read the profile
    from domain import set_active_domain
    os.environ["PREDICTOR_DOMAIN"] = args.domain
    set_active_domain(args.domain)

    # Derive domain-scoped paths if not explicitly provided
    from util.paths import get_db_path, get_docpacks_dir, get_graphs_dir, get_logs_dir
    if args.db is None:
        args.db = str(get_db_path(args.domain))

    project_root = Path(__file__).resolve().parents[1]
    run_date = args.date
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    db_path = args.db
    # Domain-scoped graph output: data/graphs/{domain}/
    graphs_dir = args.graphs_dir or str(get_graphs_dir(args.domain))
    # Domain-scoped log output: data/logs/{domain}/
    if args.log_dir is None:
        args.log_dir = str(get_logs_dir(args.domain))
    docpack_path = str(get_docpacks_dir(args.domain) / f"daily_bundle_{run_date}.jsonl")
    docpack_label = run_date

    # Initialize run log
    run_log: dict = {
        "runDate": run_date,
        "runId": run_id,
        "domain": args.domain,
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
            "name": "repair",
            "cmd": [
                sys.executable, "scripts/repair_data.py",
                "--db", db_path,
                "--fix",
            ],
            "parse": lambda s: {},
            "fatal": False,
        },
        {
            "name": "ingest",
            "cmd": [
                sys.executable, "-m", "ingest.run_all",
                "--config", f"domains/{args.domain}/feeds.yaml",
                "--db", db_path,
                "--skip-existing",
            ],
            "parse": parse_ingest_output,
            "fatal": True,
            "timeout": 2700,  # 45 min — feeds × delay; extra buffer for slow networks
            "stream": True,  # show per-article progress in real-time
        },
        {
            "name": "docpack",
            "cmd": [
                sys.executable, "scripts/build_docpack.py",
                "--db", db_path,
                "--date", run_date,
                "--label", docpack_label,
            ] + (["--budget", str(args.budget)] if args.budget else []),
            "parse": parse_docpack_output,
            "fatal": False,
        },
        {
            "name": "extract",
            "cmd": [
                sys.executable, "scripts/run_extract.py",
                "--docpack", docpack_path,
                "--db", db_path,
            ] + ([] if args.no_escalate else ["--escalate"]),
            "parse": parse_extract_output,
            "fatal": False,
            "skip": args.skip_extract,
            "timeout": 10800,  # 3 hours — escalation mode can run 100+ docs × 30-120s each
            "stream": True,   # show per-doc progress in real-time
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
            "name": "synthesize",
            "cmd": [
                sys.executable, "scripts/run_synthesize.py",
                "--db", db_path,
                "--run-date", run_date,
                "--domain", args.domain,
            ],
            "parse": parse_synthesize_output,
            "fatal": False,
        },
        {
            "name": "resolve",
            "cmd": [
                sys.executable, "scripts/run_resolve.py",
                "--db", db_path,
                "--llm-disambiguate",
            ],
            "parse": parse_resolve_output,
            "fatal": False,
        },
        {
            "name": "infer",
            "cmd": [
                sys.executable, "scripts/run_infer.py",
                "--db", db_path,
                "--run-date", run_date,
                "--domain", args.domain,
            ],
            "parse": parse_infer_output,
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
                "--narratives",
            ],
            "parse": parse_trending_output,
            "fatal": False,
        },
    ]

    if args.dry_run:
        print("DRY RUN — domain routing diagnostic:")
        print(f"  args.domain:        {args.domain}")
        print(f"  PREDICTOR_DOMAIN:   {os.environ.get('PREDICTOR_DOMAIN', '(not set)')}")
        from domain import get_active_domain, get_active_profile
        profile = get_active_profile()
        print(f"  Active domain:      {get_active_domain()}")
        print(f"  Profile name:       {profile.get('name', '?')}")
        print(f"  Entity types:       {len(profile.get('entity_types', []))} types")
        print(f"  Feeds config:       domains/{args.domain}/feeds.yaml")
        feeds_path = project_root / "domains" / args.domain / "feeds.yaml"
        print(f"  Feeds file exists:  {feeds_path.exists()}")
        print(f"  DB path:            {db_path}")
        print(f"  Graphs dir:         {graphs_dir}")
        print()
        print("Would execute:")
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
    docpack_bundled = None  # track whether docpack produced docs

    print(f"=== Pipeline run {run_id} ({run_date}) ===")
    print(f"  Domain: {args.domain}")
    print(f"  DB: {db_path}")
    print(f"  Graphs: {graphs_dir}")
    print(f"  Feeds: domains/{args.domain}/feeds.yaml")
    print(f"  Docpack: {docpack_path}")
    print(f"  PREDICTOR_DOMAIN env: {os.environ.get('PREDICTOR_DOMAIN', '(not set)')}")
    if args.no_timeout:
        print("  Stage timeouts: DISABLED")

    # Show DB document status summary for diagnostics
    try:
        import sqlite3
        db_full = project_root / db_path
        if db_full.exists():
            diag_conn = sqlite3.connect(db_full)
            diag_conn.row_factory = sqlite3.Row
            rows = diag_conn.execute(
                "SELECT status, COUNT(*) as cnt FROM documents GROUP BY status"
            ).fetchall()
            if rows:
                status_parts = [f"{r['status']}={r['cnt']}" for r in rows]
                print(f"  DB docs: {', '.join(status_parts)}")
            else:
                print("  DB docs: (empty)")
            diag_conn.close()
        else:
            print(f"  DB: {db_path} (new)")
    except Exception:
        pass  # diagnostics should never block the pipeline

    print()

    try:
        for stage in stages:
            name = stage["name"]

            if stage.get("skip", False):
                print(f"[{name}] SKIPPED")
                run_log["stages"][name] = {"status": "skipped"}
                continue

            # Skip extract if docpack bundled 0 docs and no fresh docpack exists
            if name == "extract" and docpack_bundled == 0:
                docpack_file = project_root / docpack_path
                if not docpack_file.exists():
                    print(f"[{name}] SKIPPED (no docpack file)")
                    run_log["stages"][name] = {"status": "skipped", "reason": "no_docpack"}
                    continue

            stage_timeout = None if args.no_timeout else stage.get("timeout", 600)
            stage_stream = stage.get("stream", False)
            print(f"[{name}] Running...", flush=True)
            result = run_stage(name, stage["cmd"], cwd=project_root,
                               timeout=stage_timeout, stream=stage_stream)

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

            # Track docpack output so extract can be skipped when empty
            if name == "docpack":
                docpack_bundled = stage_stats.get("docsBundled", 0)

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
            # Copy to domain-scoped live directory
            live_dir = project_root / args.web_live_dir / args.domain
            copied = copy_graphs_to_live(
                Path(graphs_dir), run_date, live_dir
            )
            if copied:
                print(f"\nCopied graphs to {args.web_live_dir}/{args.domain}/")
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

    # Persist pipeline_runs and funnel_stats to DB
    _persist_run_stats(project_root / db_path, run_log, args.domain)

    # Print summary
    print()
    stage_summary = []
    ingest = run_log["stages"].get("ingest", {})
    extract = run_log["stages"].get("extract", {})
    export = run_log["stages"].get("export", {})
    synthesize_s = run_log["stages"].get("synthesize", {})
    resolve_s = run_log["stages"].get("resolve", {})
    infer_s = run_log["stages"].get("infer", {})
    trending_s = run_log["stages"].get("trending", {})

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

    # Feature highlights (non-zero only)
    feature_parts = []
    synth_batches = synthesize_s.get("batchesProcessed", 0)
    if synth_batches:
        feature_parts.append(f"synth={synth_batches}batches/{synthesize_s.get('relationsInferred', 0)}rels")
    merges = resolve_s.get("mergesPerformed", 0) + resolve_s.get("disambigMerges", 0)
    if merges:
        feature_parts.append(f"resolve={merges}merges")
    infer_rels = infer_s.get("relationsInferred", 0)
    if infer_rels:
        feature_parts.append(f"infer={infer_rels}rels")
    narr = trending_s.get("narrativesGenerated", 0)
    if narr:
        feature_parts.append(f"narratives={narr}")
    if feature_parts:
        print(f"  Features: {' | '.join(feature_parts)}")

    # Warn about unmapped relation types (normalization gaps)
    unmapped = extract.get("unmappedRelationTypes", [])
    if unmapped:
        types_str = ", ".join(f"{u['type']}({u['count']})" for u in unmapped)
        print(f"  ⚠ Unmapped relation types: {types_str}  → add to domain.yaml normalization")

    print(f"Log: {log_path}")

    return 0 if overall_status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
