"""Shadow trend graphs: what would a model switch do to trending and Movers?

A shadow graph is the domain's graph rebuilt from scratch out of the stored
extraction files -- import, then resolve, then infer, the CPU steps of
``make daily`` -- in a copy of the database. For a set of documents the files
can be swapped for another model's extractions (a run directory from
scripts/compare_extraction_models.py). Two shadow graphs built the same way,
one from the production files and one with a window of documents swapped,
differ only in those files, so their trending and Movers lists show what the
switch would change.

Both graphs leave out the paid steps: no LLM disambiguation in resolve, no
synthesis, no narratives. A shadow graph built from the production files is
therefore close to the live graph, not identical to it: compare shadow with
shadow, and use the live graph only as a sanity check.

The live database and extraction files are only ever read.

    build   --name sonnet
    build   --name haiku --swap-run RUN_DIR --swap-arm haiku55_tuned
    compare --a sonnet --b haiku --as-of 2026-11-10

Output goes to data/experiments/shadow-graph/ (gitignored): <name>/graph.db,
<name>/extractions/ (symlinks), the step logs, build.json, and
compare-<a>-vs-<b>-<as_of>.md / .json.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _bootstrap_domain() -> None:
    """Set PREDICTOR_DOMAIN from --domain before any domain-aware import."""
    os.environ.setdefault("PREDICTOR_DOMAIN", "semiconductors")
    for i, arg in enumerate(sys.argv):
        if arg == "--domain" and i + 1 < len(sys.argv):
            os.environ["PREDICTOR_DOMAIN"] = sys.argv[i + 1]
        elif arg.startswith("--domain="):
            os.environ["PREDICTOR_DOMAIN"] = arg.split("=", 1)[1]


_bootstrap_domain()

from db import init_db  # noqa: E402
from extract import ExtractionError, parse_extraction_response  # noqa: E402
from trend import TrendScorer  # noqa: E402

SHADOW_DIR = Path("data") / "experiments" / "shadow-graph"
# Everything import/resolve/infer/trending write. Cleared in the copy so the
# graph is rebuilt from the files alone; documents and the ledgers stay.
GRAPH_TABLES = ("evidence", "relations", "entity_aliases", "entities", "trend_history")
TOP_N = 50              # run_trending.py default
MOVERS_WINDOW_DAYS = 7  # run_movers.py default
BASE_RELATION = "MENTIONS"


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def _swap_files(run: Path, arm: str, out: Path) -> tuple[dict[str, Path], dict[str, Any]]:
    """docId -> the arm's extraction file, repairing the ones that failed to parse.

    A result that failed only because an asserted relation came back with no
    evidence gets that relation dropped and is parsed again (the policy
    proposed for production, 2026-11-22), so the document is not missing from
    the shadow graph. Anything else that failed stays out, and is counted.
    """
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    docs = {d["docId"]: d for d in manifest["docs"]}
    files: dict[str, Path] = {}
    for doc_id in docs:
        f = run / "results" / arm / f"{doc_id}.json"
        if f.exists():
            files[doc_id] = f
    report: dict[str, Any] = {"documents": len(docs), "ok": len(files),
                              "repaired": [], "missing": []}
    by_idx = {f"{arm}-{d['idx']:03d}": d for d in manifest["docs"]}
    raw = {}
    for line in open(run / "raw.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r["custom_id"] in by_idx:
            raw[by_idx[r["custom_id"]]["docId"]] = r["message"]
    repaired_dir = out / "repaired"
    for doc_id, d in docs.items():
        if doc_id in files:
            continue
        msg = raw.get(doc_id)
        if msg is None:
            report["missing"].append(doc_id)
            continue
        try:
            text = next(b["text"] for b in msg["content"] if b.get("type") == "text")
            data = json.loads(text)
            keep, dropped = [], []
            for r in data.get("relations", []):
                if r.get("kind") == "asserted" and not r.get("evidence"):
                    dropped.append(f"{r.get('source')} {r.get('rel')} {r.get('target')}")
                else:
                    keep.append(r)
            data["relations"] = keep
            data.setdefault("notes", []).append(
                f"shadow repair: dropped {len(dropped)} asserted relation(s) with no evidence")
            doc = _load_doc(doc_id, Path(d["docpack"]))
            extraction = parse_extraction_response(json.dumps(data), doc_id, doc)
        except (StopIteration, json.JSONDecodeError, ExtractionError, ValueError, KeyError) as e:
            report["missing"].append(doc_id)
            print(f"  {doc_id}: not repairable ({e})")
            continue
        repaired_dir.mkdir(parents=True, exist_ok=True)
        f = repaired_dir / f"{doc_id}.json"
        f.write_text(json.dumps(extraction, indent=2, ensure_ascii=False), encoding="utf-8")
        files[doc_id] = f
        report["repaired"].append({"docId": doc_id, "dropped": dropped})
    return files, report


def _load_doc(doc_id: str, docpack: Path) -> dict[str, Any]:
    with open(docpack, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                if record["docId"] == doc_id:
                    return record
    raise KeyError(f"{doc_id} not in {docpack}")


def _run_step(name: str, cmd: list[str], out: Path) -> None:
    log = out / f"{name}.log"
    print(f"  [{name}] {' '.join(cmd[1:3])} ... (log: {log})", flush=True)
    with open(log, "w", encoding="utf-8") as f:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    if rc != 0:
        raise SystemExit(f"{name} failed (rc={rc}); see {log}")


def cmd_build(args: argparse.Namespace) -> int:
    domain = os.environ["PREDICTOR_DOMAIN"]
    out = SHADOW_DIR / args.name
    if (out / "graph.db").exists():
        print(f"{out} already has a graph; pick another --name or delete it")
        return 1
    out.mkdir(parents=True, exist_ok=True)
    live_db = Path("data") / "db" / f"{domain}.db"
    live_extractions = Path("data") / "extractions" / domain

    swap: dict[str, Path] = {}
    swap_report: dict[str, Any] = {}
    if args.swap_run:
        swap, swap_report = _swap_files(Path(args.swap_run), args.swap_arm, out)
        print(f"swap: {swap_report['ok']} parsed, {len(swap_report['repaired'])} repaired, "
              f"{len(swap_report['missing'])} missing of {swap_report['documents']}")

    # The extraction set: every production file, with the swapped documents
    # pointing at the other model's file. A swapped document whose result is
    # missing is left out entirely (production would have retried it), so
    # the window is never topped up with the model being replaced.
    ext_dir = out / "extractions"
    ext_dir.mkdir()
    linked = swapped = 0
    swap_docs = set(swap) | set(swap_report.get("missing", []))
    for f in sorted(live_extractions.glob("*.json")):
        doc_id = f.stem
        if doc_id in swap_docs:
            if doc_id in swap:
                (ext_dir / f.name).symlink_to(swap[doc_id].resolve())
                swapped += 1
            continue
        (ext_dir / f.name).symlink_to(f.resolve())
        linked += 1
    print(f"extractions: {linked} production files, {swapped} swapped")

    # Copy the live database (read-only open, SQLite's online backup) and
    # clear the graph tables.
    src = sqlite3.connect(f"file:{live_db}?mode=ro", uri=True)
    dst = sqlite3.connect(out / "graph.db")
    src.backup(dst)
    src.close()
    for table in GRAPH_TABLES:
        dst.execute(f"DELETE FROM {table}")
    dst.commit()
    dst.execute("VACUUM")
    dst.close()

    py = sys.executable
    db = str(out / "graph.db")
    _run_step("import", [py, "scripts/import_extractions.py", "--db", db,
                         "--extractions-dir", str(ext_dir), "--domain", domain], out)
    _run_step("resolve", [py, "scripts/run_resolve.py", "--db", db, "--domain", domain], out)
    _run_step("infer", [py, "scripts/run_infer.py", "--db", db, "--domain", domain], out)

    conn = sqlite3.connect(db)
    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("entities", "relations", "evidence")}
    conn.close()
    (out / "build.json").write_text(json.dumps({
        "name": args.name, "domain": domain, "swap_run": args.swap_run,
        "swap_arm": args.swap_arm, "production_files": linked, "swapped_files": swapped,
        "swap_report": swap_report, "counts": counts,
    }, indent=2), encoding="utf-8")
    print(f"built {out}: {counts}")
    return 0


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------

def _load_movers_module():
    spec = importlib.util.spec_from_file_location("run_movers", ROOT / "scripts" / "run_movers.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_movers"] = mod
    spec.loader.exec_module(mod)
    return mod


def score_graph(name: str, as_of: date) -> dict[str, Any]:
    """Trending (as of as_of) and Movers (as_of vs as_of - 7 days) for one graph.

    get_trending is production's selection; its score_all is pinned to the
    reference date, and the trend_history rows it writes (dated today) are
    re-dated to the reference date so run_movers' build_movers_rows reads
    them as two daily runs a week apart.
    """
    conn = init_db(SHADOW_DIR / name / "graph.db")
    scorer = TrendScorer(conn)
    today = date.today().isoformat()
    tops: dict[str, list[dict[str, Any]]] = {}
    for d in (as_of - timedelta(days=MOVERS_WINDOW_DAYS), as_of):
        if d.isoformat() == today:
            raise SystemExit("--as-of must be a past date")
        scorer.score_all = (lambda _d: (lambda as_of=None: TrendScorer.score_all(scorer, as_of=_d)))(d)
        conn.execute("DELETE FROM trend_history WHERE run_date = ?", (d.isoformat(),))
        top = scorer.get_trending(limit=TOP_N)
        conn.execute("UPDATE trend_history SET run_date = ? WHERE run_date = ?",
                     (d.isoformat(), today))
        conn.commit()
        tops[d.isoformat()] = top
    movers_rows, _ = _load_movers_module().build_movers_rows(conn, MOVERS_WINDOW_DAYS, BASE_RELATION)

    names = {r[0]: (r[1], r[2]) for r in conn.execute("SELECT entity_id, name, type FROM entities")}
    window_start = (as_of - timedelta(days=30)).isoformat()
    m30 = dict(conn.execute(
        """SELECT r.target_id, COUNT(*) FROM relations r JOIN documents d ON r.doc_id = d.doc_id
           WHERE r.rel = ? AND d.published_at >= ? AND d.published_at <= ?
           GROUP BY r.target_id""", (BASE_RELATION, window_start, as_of.isoformat())).fetchall())
    window_rel = conn.execute(
        """SELECT COUNT(*) FROM relations r JOIN documents d ON r.doc_id = d.doc_id
           WHERE r.rel != ? AND d.published_at >= ? AND d.published_at <= ?""",
        (BASE_RELATION, window_start, as_of.isoformat())).fetchone()[0]
    top_ids = [t["entity_id"] for t in tops[as_of.isoformat()]]
    top_set = set(top_ids)
    pairs = {frozenset((s, t)) for s, t in conn.execute(
        "SELECT source_id, target_id FROM relations WHERE rel != ?", (BASE_RELATION,))
        if s in top_set and t in top_set and s != t}
    conn.close()
    return {"top": top_ids, "scores": {t["entity_id"]: t for t in tops[as_of.isoformat()]},
            "movers": movers_rows, "names": names, "m30": m30,
            "window_relations": window_rel, "window_entities": len(m30),
            "trending_pairs": len(pairs)}


def _spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (vx * vy) if vx and vy else float("nan")


def _climbers(rows: list[dict[str, Any]], n: int = 20) -> list[dict[str, Any]]:
    """Movers' headline: biggest rank gains among entities with 2+ mentions this week."""
    eligible = [r for r in rows if r["rank_delta"] is not None and r["mention_count_7d"] >= 2]
    return sorted(eligible, key=lambda r: (-r["rank_delta"], r["entity_id"]))[:n]


def cmd_compare(args: argparse.Namespace) -> int:
    as_of = date.fromisoformat(args.as_of)
    a, b = score_graph(args.a, as_of), score_graph(args.b, as_of)
    label = lambda g, e: (g["names"].get(e) or (e, ""))[0]  # noqa: E731

    def overlap(k: int) -> int:
        return len(set(a["top"][:k]) & set(b["top"][:k]))

    shared = set(a["top"]) & set(b["top"])
    shifts = sorted(abs(a["top"].index(e) - b["top"].index(e)) for e in shared)
    # 30-day mentions on the entities that matter: either graph's top 100.
    top100 = set(sorted(a["m30"], key=lambda e: -a["m30"][e])[:100]) | \
        set(sorted(b["m30"], key=lambda e: -b["m30"][e])[:100])
    xs = [a["m30"].get(e, 0) for e in sorted(top100)]
    ys = [b["m30"].get(e, 0) for e in sorted(top100)]
    ratios = sorted(y / x for x, y in zip(xs, ys) if x)
    ca, cb = _climbers(a["movers"]), _climbers(b["movers"])
    climb_overlap = len({r["entity_id"] for r in ca} & {r["entity_id"] for r in cb})
    new_a = {r["entity_id"] for r in a["movers"] if r["is_new"] and r["mention_count_7d"] >= 2}
    new_b = {r["entity_id"] for r in b["movers"] if r["is_new"] and r["mention_count_7d"] >= 2}

    result = {
        "as_of": args.as_of, "a": args.a, "b": args.b,
        "trending_overlap": {"top10": overlap(10), "top20": overlap(20), "top50": overlap(50)},
        "shared_rank_shift_median": shifts[len(shifts) // 2] if shifts else None,
        "mentions_30d_top100": {"entities": len(top100), "spearman": round(_spearman(xs, ys), 3),
                                "median_ratio_b_over_a": round(ratios[len(ratios) // 2], 3) if ratios else None},
        "window_relations": {"a": a["window_relations"], "b": b["window_relations"]},
        "window_entities_mentioned": {"a": a["window_entities"], "b": b["window_entities"]},
        "trending_view_entity_pairs": {"a": a["trending_pairs"], "b": b["trending_pairs"]},
        "movers_top20_climbers_overlap": climb_overlap,
        "movers_new_entities": {"a": len(new_a), "b": len(new_b), "both": len(new_a & new_b)},
        "top_a": a["top"], "top_b": b["top"],
        "climbers_a": [r["entity_id"] for r in ca], "climbers_b": [r["entity_id"] for r in cb],
    }
    stem = SHADOW_DIR / f"compare-{args.a}-vs-{args.b}-{args.as_of}"
    stem.with_suffix(".json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [f"# Shadow graph comparison: {args.a} vs {args.b}, as of {args.as_of}", ""]
    o = result["trending_overlap"]
    lines += [
        f"- Trending top 10 shared: {o['top10']}/10; top 20: {o['top20']}/20; top 50: {o['top50']}/50",
        f"- Median rank shift of shared top-50 entities: {result['shared_rank_shift_median']}",
        f"- 30-day mention counts, top-100 entities ({len(top100)}): rank correlation "
        f"{result['mentions_30d_top100']['spearman']}, median {args.b}/{args.a} ratio "
        f"{result['mentions_30d_top100']['median_ratio_b_over_a']}",
        f"- Relations from window documents: {args.a} {a['window_relations']}, {args.b} {b['window_relations']}",
        f"- Entities mentioned in the window: {args.a} {a['window_entities']}, {args.b} {b['window_entities']}",
        f"- Linked entity pairs inside the trending top 50: {args.a} {a['trending_pairs']}, {args.b} {b['trending_pairs']}",
        f"- Movers, top 20 climbers shared: {climb_overlap}/20; new entities (2+ mentions): "
        f"{args.a} {len(new_a)}, {args.b} {len(new_b)}, both {len(new_a & new_b)}",
        "", f"| Rank | {args.a} | 7d | {args.b} | 7d |", "|---|---|---|---|---|",
    ]
    for i in range(TOP_N):
        ea = a["top"][i] if i < len(a["top"]) else None
        eb = b["top"][i] if i < len(b["top"]) else None
        cell = lambda g, e, other: (  # noqa: E731
            "" if e is None else (label(g, e) + ("" if e in other["top"] else " *")))
        lines.append(f"| {i + 1} | {cell(a, ea, b)} | {a['scores'][ea]['mention_count_7d'] if ea else ''} "
                     f"| {cell(b, eb, a)} | {b['scores'][eb]['mention_count_7d'] if eb else ''} |")
    lines += ["", "\\* = not in the other graph's top 50.", "",
              f"## Movers: top 20 climbers (2+ mentions this week)", "",
              f"| | {args.a} | rank change | {args.b} | rank change |", "|---|---|---|---|---|"]
    ids_b = {r["entity_id"] for r in cb}
    ids_a = {r["entity_id"] for r in ca}
    for i in range(20):
        ra = ca[i] if i < len(ca) else None
        rb = cb[i] if i < len(cb) else None
        lines.append(
            f"| {i + 1} | {label(a, ra['entity_id']) + ('' if ra['entity_id'] in ids_b else ' *') if ra else ''} "
            f"| {ra['rank_delta'] if ra else ''} "
            f"| {label(b, rb['entity_id']) + ('' if rb['entity_id'] in ids_a else ' *') if rb else ''} "
            f"| {rb['rank_delta'] if rb else ''} |")
    stem.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:10]))
    print(f"\nSaved {stem.with_suffix('.md')} and .json")
    return 0


def main() -> int:
    os.chdir(ROOT)
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--domain", default=os.environ.get("PREDICTOR_DOMAIN"))
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build")
    p.add_argument("--name", required=True)
    p.add_argument("--swap-run", default=None, help="compare_extraction_models run dir")
    p.add_argument("--swap-arm", default=None, help="arm whose results replace production files")
    p = sub.add_parser("compare")
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--as-of", required=True)
    args = parser.parse_args()
    if args.cmd == "build" and bool(args.swap_run) != bool(args.swap_arm):
        parser.error("--swap-run and --swap-arm go together")
    return cmd_build(args) if args.cmd == "build" else cmd_compare(args)


if __name__ == "__main__":
    raise SystemExit(main())
