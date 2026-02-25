"""Benchmark cheap model escalation rates without calling the specialist.

Dry-run tool: for each document in a docpack, calls the cheap model (e.g.
gpt-5-nano), parses the result, runs evaluate_extraction(), and tallies
escalation decisions.  No files are saved to data/extractions/ and no
specialist model is called.

Usage:
    python scripts/benchmark_cheap_model.py --docpack data/docpacks/daily_bundle_all.jsonl
    python scripts/benchmark_cheap_model.py --docpack data/docpacks/daily_bundle_all.jsonl --model gpt-5-nano --max-docs 10
    python scripts/benchmark_cheap_model.py --docpack data/docpacks/daily_bundle_all.jsonl --output results.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

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

from extract import (
    parse_extraction_response,
    evaluate_extraction,
    ExtractionError,
    EXTRACTOR_VERSION,
    ESCALATION_THRESHOLD,
)
from run_extract import load_docpack, extract_document


def run_benchmark(
    docpack_path: Path,
    model: str,
    max_docs: int | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Run cheap model on every doc and tally escalation decisions.

    Args:
        docpack_path: Path to JSONL docpack file
        model: Model ID for the cheap model
        max_docs: Cap on documents to process (None = all)
        output_path: Optional path to write per-doc JSONL results

    Returns:
        Summary dict with counts and distributions
    """
    docs = load_docpack(docpack_path)
    print(f"Loaded {len(docs)} documents from {docpack_path}")

    if max_docs:
        docs = docs[:max_docs]
        print(f"Limiting to first {max_docs} documents")

    print(f"Model: {model}")
    print(f"Escalation threshold: {ESCALATION_THRESHOLD}")
    print(f"Extractor version: {EXTRACTOR_VERSION}")
    print()

    # Accumulators
    total = 0
    accepted = 0
    escalated = 0
    parse_failed = 0
    api_failed = 0

    gate_failures: Counter = Counter()   # gate_name -> count
    reason_tally: Counter = Counter()    # decision_reason prefix -> count
    scores: list[float] = []
    durations: list[int] = []

    # Per-gate sub-scores (for accepted + escalated, not parse/api failures)
    fidelity_rates: list[float] = []
    orphan_rates: list[float] = []
    combined_scores: list[float] = []
    sub_scores: dict[str, list[float]] = {
        "density": [],
        "evidence": [],
        "confidence": [],
        "connectivity": [],
        "diversity": [],
        "tech": [],
    }

    out_fh = None
    if output_path:
        out_fh = open(output_path, "w", encoding="utf-8")

    for i, doc in enumerate(docs, 1):
        doc_id = doc.get("docId", f"unknown_{i}")
        source_text = doc.get("text", "")
        total += 1

        print(f"  [{i}/{len(docs)}] {doc_id}: ", end="", flush=True)

        # Step 1: Call cheap model
        try:
            response_text, duration_ms = extract_document(doc, model=model)
            durations.append(duration_ms)
        except Exception as e:
            print(f"API FAILED ({type(e).__name__}: {e})")
            api_failed += 1
            if out_fh:
                out_fh.write(json.dumps({
                    "docId": doc_id, "outcome": "api_failed",
                    "error": f"{type(e).__name__}: {e}",
                }) + "\n")
            if i < len(docs):
                time.sleep(0.5)
            continue

        # Step 2: Parse response
        try:
            extraction = parse_extraction_response(response_text, doc_id)
        except ExtractionError as e:
            print(f"PARSE FAILED ({e})")
            parse_failed += 1
            if out_fh:
                out_fh.write(json.dumps({
                    "docId": doc_id, "outcome": "parse_failed",
                    "error": str(e), "duration_ms": duration_ms,
                }) + "\n")
            if i < len(docs):
                time.sleep(0.5)
            continue

        # Step 3: Evaluate
        evaluation = evaluate_extraction(extraction, source_text)
        score = evaluation["quality"]["combined_score"]
        scores.append(score)
        combined_scores.append(score)

        # Collect sub-scores
        q = evaluation["quality"]
        sub_scores["density"].append(q.get("density_score", 0))
        sub_scores["evidence"].append(q.get("evidence_score", 0))
        sub_scores["confidence"].append(q.get("confidence_score", 0))
        sub_scores["connectivity"].append(q.get("connectivity_score", 0))
        sub_scores["diversity"].append(q.get("diversity_score", 0))
        sub_scores["tech"].append(q.get("tech_score", 0))

        # Collect gate metrics
        gates = evaluation["gates"]
        ev_fid = gates.get("evidence_fidelity", {})
        fidelity_rates.append(ev_fid.get("match_rate", 1.0))
        orp = gates.get("orphan_endpoints", {})
        orphan_rates.append(orp.get("orphan_rate", 0.0))

        # Tally outcome
        if evaluation["escalate"]:
            escalated += 1
            reason = evaluation["decision_reason"]
            # Bucket by prefix: "gate_failed" or "quality_low"
            prefix = reason.split(":")[0]
            reason_tally[prefix] += 1

            # Which specific gates failed?
            if not gates.get("overall_passed", True):
                for gate_name, gate_result in gates.get("gates", {}).items():
                    if not gate_result.get("passed", True):
                        gate_failures[gate_name] += 1

            n_ent = len(extraction.get("entities", []))
            n_rel = len(extraction.get("relations", []))
            print(f"ESCALATE q={score:.2f} ({evaluation['decision_reason'][:60]}) [{n_ent}e {n_rel}r {duration_ms}ms]")
        else:
            accepted += 1
            n_ent = len(extraction.get("entities", []))
            n_rel = len(extraction.get("relations", []))
            print(f"ACCEPT q={score:.2f} [{n_ent}e {n_rel}r {duration_ms}ms]")

        # Write per-doc detail
        if out_fh:
            out_fh.write(json.dumps({
                "docId": doc_id,
                "outcome": "escalate" if evaluation["escalate"] else "accept",
                "score": score,
                "decision_reason": evaluation["decision_reason"],
                "gates_passed": gates.get("overall_passed", True),
                "gate_details": {
                    k: v.get("passed", True)
                    for k, v in gates.get("gates", {}).items()
                },
                "quality": q,
                "n_entities": len(extraction.get("entities", [])),
                "n_relations": len(extraction.get("relations", [])),
                "n_tech_terms": len(extraction.get("techTerms", [])),
                "duration_ms": duration_ms,
            }) + "\n")

        if i < len(docs):
            time.sleep(0.5)

    if out_fh:
        out_fh.close()

    # Build summary
    evaluated = accepted + escalated  # docs that parsed successfully
    escalation_rate = (escalated / evaluated * 100) if evaluated else 0
    gate_fail_rate = (reason_tally.get("gate_failed", 0) / evaluated * 100) if evaluated else 0
    score_fail_rate = (reason_tally.get("quality_low", 0) / evaluated * 100) if evaluated else 0

    summary = {
        "model": model,
        "total_docs": total,
        "api_failed": api_failed,
        "parse_failed": parse_failed,
        "evaluated": evaluated,
        "accepted": accepted,
        "escalated": escalated,
        "escalation_rate_pct": round(escalation_rate, 1),
        "gate_fail_escalations": reason_tally.get("gate_failed", 0),
        "score_fail_escalations": reason_tally.get("quality_low", 0),
        "gate_fail_rate_pct": round(gate_fail_rate, 1),
        "score_fail_rate_pct": round(score_fail_rate, 1),
        "gate_failure_breakdown": dict(gate_failures),
        "score_stats": {},
        "duration_stats": {},
        "fidelity_stats": {},
        "sub_score_means": {},
    }

    if scores:
        summary["score_stats"] = {
            "mean": round(statistics.mean(scores), 3),
            "median": round(statistics.median(scores), 3),
            "stdev": round(statistics.stdev(scores), 3) if len(scores) > 1 else 0,
            "min": round(min(scores), 3),
            "max": round(max(scores), 3),
        }

    if durations:
        summary["duration_stats"] = {
            "mean_ms": round(statistics.mean(durations)),
            "median_ms": round(statistics.median(durations)),
            "p95_ms": round(sorted(durations)[int(len(durations) * 0.95)] if len(durations) >= 2 else durations[0]),
        }

    if fidelity_rates:
        summary["fidelity_stats"] = {
            "mean": round(statistics.mean(fidelity_rates), 3),
            "below_70pct": sum(1 for r in fidelity_rates if r < 0.70),
        }

    for key, vals in sub_scores.items():
        if vals:
            summary["sub_score_means"][key] = round(statistics.mean(vals), 3)

    return summary


def print_summary(summary: dict[str, Any]) -> None:
    """Print a human-readable summary table."""
    print()
    print("=" * 65)
    print(f"  BENCHMARK RESULTS — {summary['model']}")
    print("=" * 65)
    print()
    print(f"  Documents:      {summary['total_docs']}")
    print(f"  API failures:   {summary['api_failed']}")
    print(f"  Parse failures: {summary['parse_failed']}")
    print(f"  Evaluated:      {summary['evaluated']}")
    print()
    print(f"  Accepted:       {summary['accepted']}")
    print(f"  Escalated:      {summary['escalated']}")
    print(f"  ESCALATION RATE: {summary['escalation_rate_pct']:.1f}%")
    print()
    print("  Escalation breakdown:")
    print(f"    Gate failures:    {summary['gate_fail_escalations']}  ({summary['gate_fail_rate_pct']:.1f}%)")
    print(f"    Low score:        {summary['score_fail_escalations']}  ({summary['score_fail_rate_pct']:.1f}%)")
    print()

    if summary["gate_failure_breakdown"]:
        print("  Gate failure detail:")
        for gate, count in sorted(summary["gate_failure_breakdown"].items(), key=lambda x: -x[1]):
            print(f"    {gate}: {count}")
        print()

    if summary["score_stats"]:
        s = summary["score_stats"]
        print(f"  Quality scores:  mean={s['mean']:.3f}  median={s['median']:.3f}  "
              f"stdev={s['stdev']:.3f}  range=[{s['min']:.3f}, {s['max']:.3f}]")

    if summary["sub_score_means"]:
        parts = [f"{k}={v:.2f}" for k, v in summary["sub_score_means"].items()]
        print(f"  Sub-score means: {', '.join(parts)}")

    if summary["fidelity_stats"]:
        f = summary["fidelity_stats"]
        print(f"  Evidence fidelity: mean={f['mean']:.3f}  below_70%={f['below_70pct']}")

    if summary["duration_stats"]:
        d = summary["duration_stats"]
        print(f"  Latency:         mean={d['mean_ms']}ms  median={d['median_ms']}ms  p95={d['p95_ms']}ms")

    print()
    print("=" * 65)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark cheap model escalation rate (dry run, no specialist calls)."
    )
    parser.add_argument(
        "--docpack",
        required=True,
        help="Path to JSONL docpack file",
    )
    parser.add_argument(
        "--model",
        default="gpt-5-nano",
        help="Cheap model to benchmark (default: gpt-5-nano)",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="Maximum documents to process (default: all)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write per-doc JSONL results (optional)",
    )
    parser.add_argument(
        "--summary-json",
        default=None,
        help="Path to write summary as JSON (optional)",
    )
    args = parser.parse_args()

    docpack_path = Path(args.docpack)
    if not docpack_path.exists():
        print(f"ERROR: docpack not found: {docpack_path}")
        return 1

    output_path = Path(args.output) if args.output else None

    print(f"Benchmark cheap model — dry run (no specialist, no file saves)")
    print()

    summary = run_benchmark(
        docpack_path=docpack_path,
        model=args.model,
        max_docs=args.max_docs,
        output_path=output_path,
    )

    print_summary(summary)

    if args.summary_json:
        with open(args.summary_json, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"Summary written to {args.summary_json}")

    if output_path:
        print(f"Per-doc results written to {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
