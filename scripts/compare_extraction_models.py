#!/usr/bin/env python3
"""Compare extraction across models and evidence formats on real documents.

Built 2026-11-14 to answer two questions before production extraction
changes: can a cheaper model (Claude Haiku 5.5, a twentieth of Sonnet 5's
price) hold quality, and can evidence be a sentence number instead of a
quoted snippet? Each arm re-extracts the same sampled documents, and every
result is scored against the Sonnet 5 extraction already on disk.

Nothing here touches the pipeline. Results land under data/experiments/ and
are never imported. The live database is read-only except for the
token_usage rows that record what the experiment spent (stage
'experiment'), so the spend is as visible as any pipeline call.

Subcommands, in order:

  plan     pick documents, estimate cost, write manifest.json      (no API)
  submit   one Batch API job covering every arm x document          (PAID)
  collect  fetch results, parse them, log spend to token_usage      (no new spend)
  score    compare every arm with the stored baseline, write report (no API)

  python scripts/compare_extraction_models.py plan
  python scripts/compare_extraction_models.py submit --run <dir> --dry-run
  python scripts/compare_extraction_models.py submit --run <dir> --yes
  python scripts/compare_extraction_models.py collect --run <dir>
  python scripts/compare_extraction_models.py score --run <dir>

Read the sonnet5 row first: it is Sonnet re-extracting the same documents,
so its agreement with the baseline is the ceiling. A cheaper arm is "as
good as Sonnet" when it matches that row, not when it reaches 100%.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))


def _load_dotenv() -> None:
    """Load the project .env without overriding the environment.

    Same rules as scripts/collect_batch.py: the timers get the key this
    way, not from the shell, so an interactive run needs it too.
    """
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.replace("\r", "").strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'").strip()
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()


def _bootstrap_domain() -> None:
    """Set PREDICTOR_DOMAIN from --domain before any domain-aware import."""
    os.environ.setdefault("PREDICTOR_DOMAIN", "semiconductors")
    for i, arg in enumerate(sys.argv):
        if arg == "--domain" and i + 1 < len(sys.argv):
            os.environ["PREDICTOR_DOMAIN"] = sys.argv[i + 1]
        elif arg.startswith("--domain="):
            os.environ["PREDICTOR_DOMAIN"] = arg.split("=", 1)[1]


_bootstrap_domain()

from db import _compute_cost, init_db, log_token_usage  # noqa: E402
from extract import (  # noqa: E402
    ANTHROPIC_EXTRACTION_SCHEMA,
    EXTRACTOR_VERSION,
    ExtractionError,
    build_extraction_prompt,
    parse_extraction_response,
    run_quality_gates,
)
from extract.sentence_evidence import (  # noqa: E402
    number_sentences,
    resolve_sentence_evidence,
)
from resolve import EntityResolver, generate_canonical_id, normalize_name  # noqa: E402

EXPERIMENTS_DIR = Path("data") / "experiments" / "extraction-compare"
MAX_TOKENS = 32000          # same ceiling as submit_batch.py
RESOLVE_THRESHOLD = 0.85    # same as import_extractions.py
STAGE = "experiment"


# ---------------------------------------------------------------------------
# Arms
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Arm:
    model: str
    evidence: str                    # "snippet" | "sentence"
    thinking: Optional[dict]         # None = omit the parameter
    note: str
    tuning: Optional[str] = None     # key into PROMPT_TUNINGS, or None
    effort: Optional[str] = None     # output_config.effort, or None to omit


# Extra prompt text for the tuning arms, inserted just before "## Critical
# Rules". Experiment-only: production prompts stay in domains/<slug>/prompts/.
#
# haiku_v1 targets what Haiku 5.5 missed on the 2026-11-22-n50-seed1 run
# (production prompt, thinking off): 72% of the baseline's entities kept
# against Sonnet's 87%. The misses were not positional (they sat in the second
# half of the article no more often than kept entities did). They were
# selectivity: 51 locations and 43 orgs (many government bodies) dropped
# outright, and half of the missed Topics went into techTerms instead. A
# quarter of a sample of Haiku's extra entities were page furniture (related
# headlines, affiliate notices).
PROMPT_TUNINGS: dict[str, str] = {
    "haiku_v1": """## Coverage
Extract EVERY specific named entity the document mentions, including ones that appear only once or in passing:
- every company, organization, government body or agency (e.g. "Dutch government", "Commerce Department"), university, and person
- every location named: countries, regions, states and cities (e.g. "China", "Netherlands", "Austin")
- every named product, chip, memory or interface standard (e.g. "DDR5", "GDDR7"), software, framework, and model
- named fields or subjects the article discusses (e.g. "quantum computing", "data sovereignty") as Topic entities

## Entity vs techTerms
If a term fits one of the entity types above, it is an entity, not a techTerm. techTerms[] is only for generic concepts that fit no entity type. A term may appear in both lists.

## Not entities
Ignore page furniture: headlines of other articles, navigation menus, newsletter and subscription prompts, ad and affiliate notices (e.g. "Amazon Services LLC Associates Program"). A headline or article title is never an entity.

## Relations
Extract every relation the text states between two of your entities, wherever it appears in the document.

""",
}

# haiku_v2 = haiku_v1 plus what round 1 (2026-11-22-haiku-r1-seed1) showed.
# Relations stayed at 26% kept against Sonnet's 51%. A third of the missed
# relations had both entities found but no link, and Haiku spent its relations
# on the document-level labels (MENTIONS, REPORTED_BY, ANNOUNCES) where Sonnet
# used DESIGNS, DEPENDS_ON and SUPPLIES. The prompt names the labels but never
# defines them; the definitions below are the comments on relation_taxonomy in
# domains/semiconductors/domain.yaml. Footer publishers (Future US Inc,
# AspenCore) were still being taken as entities.
PROMPT_TUNINGS["haiku_v2"] = PROMPT_TUNINGS["haiku_v1"].replace(
    """A headline or article title is never an entity.
""",
    """A headline or article title is never an entity. The site's own publisher, its parent company, and sister sites listed in the page footer (e.g. "Future US Inc", "AspenCore") are not entities unless the article is about them.
""",
).replace(
    """## Relations
Extract every relation the text states between two of your entities, wherever it appears in the document.
""",
    """## Relations
Extract every relation the text states between two of your entities, wherever it appears in the document. When two of your entities are connected in the text, link them. Use the most specific label the text supports:
- DESIGNS: company or person designs a chip or architecture
- MANUFACTURES: fab or company makes a chip
- FABRICATES: fab runs a process node in production
- LICENSES: company licenses an architecture (Arm, RISC-V)
- BUILT_ON: chip built on an architecture (H100 BUILT_ON Hopper)
- USES_PROCESS: chip made on a process node (H100 USES_PROCESS TSMC N4)
- USES_PACKAGING: chip or product uses a packaging technology (H100 USES_PACKAGING CoWoS)
- USES_MATERIAL: process node or chip uses a material
- INTEGRATES: chip or product integrates another chip or component (chiplets, HBM stacks)
- POWERS: chip powers a product or application
- SUPPLIES: company supplies another company (TSMC SUPPLIES NVIDIA)
- DEPENDS_ON: company or chip depends on a company, material or technology
- SOURCES_FROM: company procures from a company or location
- ACQUIRES, INVESTS_IN, PARTNERS_WITH, SPINS_OUT; FOUNDED: person founds a company
- WORKS_AT: person works at a company or organization (one for every named person whose employer the text gives)
- LEADS: person leads a company, project or team
- PRESENTS: person or company presents at an event; PRESENTED_AT: chip or research presented at an event
- RESTRICTS, EXEMPTS, TARGETS: a policy restricts, exempts, or is aimed at a company, technology or location; GOVERNS: org or policy governs a topic or industry; COMPLIES_WITH: company complies with a policy
- BENCHMARKS: comparative evaluation. COMPETES_WITH and OUTPERFORMS are hypothesis only.
- MENTIONS, CITES, ANNOUNCES, REPORTED_BY are document-level: use them only when no specific label fits.
""",
)
assert PROMPT_TUNINGS["haiku_v2"].count("DESIGNS:") == 1 and "Future US Inc" in PROMPT_TUNINGS["haiku_v2"]


ARMS: dict[str, Arm] = {
    "sonnet5": Arm("claude-sonnet-5", "snippet", {"type": "disabled"},
                   "production 2.1.0; the control (Sonnet's own run-to-run agreement)"),
    "haiku55": Arm("claude-haiku-5-5", "snippet", {"type": "disabled"},
                   "Claude Haiku 5.5, production prompt"),
    "sonnet5_sentences": Arm("claude-sonnet-5", "sentence", {"type": "disabled"},
                             "Sonnet 5, evidence cited by sentence number"),
    "haiku55_sentences": Arm("claude-haiku-5-5", "sentence", {"type": "disabled"},
                             "Haiku 5.5, evidence cited by sentence number"),
    # Haiku 4.5 takes no thinking parameter to stay off (it is off by default).
    "haiku45": Arm("claude-haiku-4-5", "snippet", None,
                   "Claude Haiku 4.5 (previous generation), production prompt"),
    # Haiku 5.5 tuning round 1 (2026-11-22). Its default is adaptive thinking
    # at effort medium; the arms above turn thinking off.
    "haiku55_think": Arm("claude-haiku-5-5", "snippet", {"type": "adaptive"},
                         "Haiku 5.5, production prompt, thinking on (effort medium)",
                         effort="medium"),
    "haiku55_tuned": Arm("claude-haiku-5-5", "snippet", {"type": "disabled"},
                         "Haiku 5.5, tuned prompt haiku_v1, thinking off",
                         tuning="haiku_v1"),
    "haiku55_tuned_think": Arm("claude-haiku-5-5", "snippet", {"type": "adaptive"},
                               "Haiku 5.5, tuned prompt haiku_v1, thinking on (effort medium)",
                               tuning="haiku_v1", effort="medium"),
    "haiku55_tuned_high": Arm("claude-haiku-5-5", "snippet", {"type": "adaptive"},
                              "Haiku 5.5, tuned prompt haiku_v1, thinking on (effort high)",
                              tuning="haiku_v1", effort="high"),
    # Round 2: thinking stays off (round 1: it lowered entity recall).
    "haiku55_tuned2": Arm("claude-haiku-5-5", "snippet", {"type": "disabled"},
                          "Haiku 5.5, tuned prompt haiku_v2, thinking off",
                          tuning="haiku_v2"),
}
DEFAULT_ARMS = ["sonnet5", "haiku55", "sonnet5_sentences", "haiku55_sentences"]

# Output-token factor for the sentence arms in the cost ESTIMATE only: quotes
# are ~13% of extraction output and become a few tokens each.
SENTENCE_OUTPUT_FACTOR = 0.88


def sentence_schema() -> dict[str, Any]:
    """The production schema with evidence items replaced by a sentence number."""
    schema = copy.deepcopy(ANTHROPIC_EXTRACTION_SCHEMA)
    relation = schema["properties"]["relations"]["items"]
    relation["properties"]["evidence"]["items"] = {
        "type": "object",
        "required": ["sentence"],
        "additionalProperties": False,
        "properties": {
            "sentence": {
                "type": "integer",
                "description": "Number of the [S#] sentence that states the relation",
            },
        },
    }
    return schema


def _sub_once(text: str, pattern: str, replacement: str) -> str:
    """Replace exactly one regex match, or fail loudly if the template moved."""
    matches = list(re.finditer(pattern, text, flags=re.M))
    if len(matches) != 1:
        raise RuntimeError(
            f"sentence-arm prompt rewrite expected 1 match for {pattern!r}, "
            f"found {len(matches)} -- the domain's single_message.txt changed"
        )
    m = matches[0]
    return text[: m.start()] + m.expand(replacement) + text[m.end():]


def build_prompt(doc: dict[str, Any], arm: Arm) -> tuple[str, Optional[list[str]]]:
    """The user prompt for one arm, plus the numbered sentences if it cites them."""
    if arm.evidence == "snippet":
        prompt = build_extraction_prompt(doc, EXTRACTOR_VERSION)
        if arm.tuning:
            prompt = _sub_once(prompt, r"^## Critical Rules$",
                               PROMPT_TUNINGS[arm.tuning].replace("\\", r"\\")
                               + "## Critical Rules")
        return prompt, None
    numbered, sentences = number_sentences(doc.get("text") or "")
    prompt = build_extraction_prompt({**doc, "text": numbered}, EXTRACTOR_VERSION)
    prompt = _sub_once(
        prompt, r"^(\s*)- snippet: .*$",
        r"\1- sentence: the number of the [S#] sentence that states the relation "
        r"(an integer, e.g. 12 for [S12])",
    )
    prompt = _sub_once(
        prompt, r"^- Asserted relations MUST include evidence with a snippet .*$",
        "- Asserted relations MUST include evidence citing the [S#] number of a "
        "sentence that states the relation",
    )
    prompt = _sub_once(
        prompt, r"^## Document Text\n",
        "## Document Text\nEvery sentence is numbered [S1], [S2], ...; cite these "
        "numbers as evidence.\n\n",
    )
    return prompt, sentences


def request_params(doc: dict[str, Any], arm: Arm) -> dict[str, Any]:
    prompt, _ = build_prompt(doc, arm)
    schema = sentence_schema() if arm.evidence == "sentence" else ANTHROPIC_EXTRACTION_SCHEMA
    params: dict[str, Any] = {
        "model": arm.model,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
        "output_config": {"format": {"type": "json_schema", "schema": schema}},
    }
    if arm.thinking is not None:
        params["thinking"] = arm.thinking
    if arm.effort is not None:
        params["output_config"]["effort"] = arm.effort
    return params


# ---------------------------------------------------------------------------
# Run directory
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_manifest(run: Path) -> dict[str, Any]:
    return json.loads((run / "manifest.json").read_text(encoding="utf-8"))


def save_manifest(run: Path, manifest: dict[str, Any]) -> None:
    tmp = run / "manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    tmp.replace(run / "manifest.json")


def docpack_index(domain: str) -> dict[str, Path]:
    """docId -> the newest docpack holding it (the text the baseline saw)."""
    index: dict[str, Path] = {}
    for path in sorted((Path("data") / "docpacks" / domain).glob("daily_bundle_*.jsonl")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    index[json.loads(line)["docId"]] = path
    return index


def load_doc(doc_id: str, docpack: Path) -> dict[str, Any]:
    with open(docpack, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                if record["docId"] == doc_id:
                    return record
    raise KeyError(f"{doc_id} not in {docpack}")


def baseline_path(domain: str, doc_id: str) -> Path:
    return Path("data") / "extractions" / domain / f"{doc_id}.json"


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

def cmd_plan(args: argparse.Namespace) -> int:
    domain = os.environ["PREDICTOR_DOMAIN"]
    arms = args.arms.split(",")
    unknown = [a for a in arms if a not in ARMS]
    if unknown:
        print(f"unknown arm(s): {unknown}; choose from {sorted(ARMS)}")
        return 1

    conn = sqlite3.connect(f"file:{Path('data') / 'db' / f'{domain}.db'}?mode=ro", uri=True)
    rows = conn.execute(
        """SELECT doc_id, SUM(input_tokens), SUM(output_tokens), SUM(cost_usd),
                  GROUP_CONCAT(DISTINCT billing_mode), GROUP_CONCAT(DISTINCT model)
           FROM token_usage
           WHERE stage = 'extraction' AND created_at >= date('now', ?)
           GROUP BY doc_id""",
        (f"-{args.days} days",),
    ).fetchall()
    packs = docpack_index(domain)
    # Baseline must be one batch Sonnet 5 extraction of the full docpack text:
    # sync-fallback extractions saw a truncated 12k-char text.
    eligible = sorted(
        r for r in rows
        if r[4] == "batch" and r[5] == "claude-sonnet-5"
        and r[0] in packs and baseline_path(domain, r[0]).exists()
    )
    # A confirmation run samples documents the tuning never saw.
    excluded: set[str] = set()
    for prior in args.exclude_run or []:
        excluded |= {d["docId"] for d in load_manifest(Path(prior))["docs"]}
    if excluded:
        before = len(eligible)
        eligible = [r for r in eligible if r[0] not in excluded]
        print(f"excluded {before - len(eligible)} documents used by {len(args.exclude_run)} earlier run(s)")
    if len(eligible) < args.n:
        print(f"only {len(eligible)} eligible documents in the last {args.days} days")
        return 1
    sample = random.Random(args.seed).sample(eligible, args.n)
    sample.sort()

    docs = []
    estimate = {a: 0.0 for a in arms}
    baseline_cost = 0.0
    for idx, (doc_id, tin, tout, cost, *_rest) in enumerate(sample):
        doc = load_doc(doc_id, packs[doc_id])
        snippet_prompt, _ = build_prompt(doc, ARMS["sonnet5"])
        docs.append({"idx": idx, "docId": doc_id, "docpack": str(packs[doc_id]),
                     "baseline_input_tokens": tin, "baseline_output_tokens": tout,
                     "baseline_cost_usd": cost})
        baseline_cost += cost or 0.0
        for a in arms:
            arm = ARMS[a]
            fin = fout = 1.0
            if arm.evidence == "sentence":
                sentence_prompt, _ = build_prompt(doc, arm)
                fin = len(sentence_prompt) / max(len(snippet_prompt), 1)
                fout = SENTENCE_OUTPUT_FACTOR
            c = _compute_cost(arm.model, int(tin * fin), int(tout * fout), "batch")
            if c is None:
                print(f"no rate for {arm.model} -- add it to db._TOKEN_PRICES first")
                return 1
            estimate[a] += c

    run_id = args.run_id or f"{datetime.now().strftime('%Y-%m-%d')}-n{args.n}-seed{args.seed}"
    run = EXPERIMENTS_DIR / run_id
    if (run / "manifest.json").exists():
        print(f"{run} already has a manifest; pass a different --run-id")
        return 1
    run.mkdir(parents=True)
    manifest = {
        "created_at": _now(), "domain": domain, "extractor_version": EXTRACTOR_VERSION,
        "seed": args.seed, "days": args.days, "n": args.n, "arms": arms,
        "docs": docs, "estimate_usd": {a: round(v, 4) for a, v in estimate.items()},
        "baseline_cost_usd": round(baseline_cost, 4),
        "batch_id": None, "submitted_at": None, "collected_at": None, "logged": [],
    }
    save_manifest(run, manifest)

    print(f"Run: {run}")
    print(f"{args.n} documents sampled from {len(eligible)} eligible "
          f"(last {args.days} days, seed {args.seed}):")
    print("  by source:", ", ".join(f"{s} {n}" for s, n in Counter(
        d["docId"].split("_", 1)[1].rsplit("_", 1)[0] for d in docs).most_common(6)))
    print(f"Baseline (stored Sonnet 5) cost for these docs: ${baseline_cost:.2f}")
    print("Estimated cost per arm (batch rates, from the baseline's token counts):")
    for a in arms:
        print(f"  {a:<20} ${estimate[a]:.2f}   {ARMS[a].note}")
    print(f"  {'total':<20} ${sum(estimate.values()):.2f}")
    print("Haiku's own tokenizer may count differently; the estimate uses Sonnet 5's counts.")
    if any(ARMS[a].thinking and ARMS[a].thinking.get("type") == "adaptive" for a in arms):
        print("Thinking arms: the estimate leaves out thinking tokens, which bill as output.")
    print(f"Next: submit --run {run} --dry-run")
    return 0


# ---------------------------------------------------------------------------
# submit
# ---------------------------------------------------------------------------

def build_requests(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    requests = []
    for d in manifest["docs"]:
        doc = load_doc(d["docId"], Path(d["docpack"]))
        for a in manifest["arms"]:
            requests.append({
                "custom_id": f"{a}-{d['idx']:03d}",
                "params": request_params(doc, ARMS[a]),
            })
    return requests


def cmd_submit(args: argparse.Namespace) -> int:
    run = Path(args.run)
    manifest = load_manifest(run)
    if manifest["batch_id"]:
        print(f"already submitted as {manifest['batch_id']} at {manifest['submitted_at']}")
        return 1
    requests = build_requests(manifest)
    with open(run / "requests.jsonl", "w", encoding="utf-8") as f:
        for r in requests:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    total = sum(manifest["estimate_usd"].values())
    print(f"{len(requests)} requests ({len(manifest['docs'])} docs x "
          f"{len(manifest['arms'])} arms), estimated ${total:.2f}; saved {run / 'requests.jsonl'}")

    if args.dry_run or not args.yes:
        sample = next((r for r in requests if r["custom_id"].startswith(
            next((a for a in manifest["arms"] if ARMS[a].evidence == "sentence"),
                 manifest["arms"][0]))), requests[0])
        p = sample["params"]
        content = p["messages"][0]["content"]
        print(f"\nSample request {sample['custom_id']}: model={p['model']}, "
              f"thinking={p.get('thinking', 'omitted')}, prompt {len(content):,} chars")
        i = content.find("evidence:")
        print("  evidence instruction:", content[i:i + 160].replace("\n", " | ") if i >= 0 else "?")
        print("  evidence schema:", json.dumps(
            p["output_config"]["format"]["schema"]["properties"]["relations"]
            ["items"]["properties"]["evidence"]["items"]))
        if not args.yes:
            print("\nNothing sent. Re-run with --yes to submit (this spends money).")
        return 0

    import anthropic
    client = anthropic.Anthropic()
    batch = client.beta.messages.batches.create(requests=requests)
    manifest["batch_id"] = batch.id
    manifest["submitted_at"] = _now()
    save_manifest(run, manifest)
    print(f"Submitted {batch.id}. Collect with: collect --run {run}")
    return 0


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------

def _text_of(message) -> str:
    for block in message.content:
        if getattr(block, "type", None) == "text":
            return block.text
    raise ValueError("no text block in response")


def parse_arm_output(text: str, doc: dict[str, Any], arm: Arm) -> tuple[dict, dict]:
    """Parse one arm's raw output into a validated extraction (+ sentence stats)."""
    stats: dict[str, int] = {}
    if arm.evidence == "sentence":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ExtractionError(f"Failed to parse JSON: {e}") from e
        _, sentences = number_sentences(doc.get("text") or "")
        stats = resolve_sentence_evidence(data, sentences)
        text = json.dumps(data)
    extraction = parse_extraction_response(text, doc["docId"], doc)
    return extraction, stats


def cmd_collect(args: argparse.Namespace) -> int:
    run = Path(args.run)
    manifest = load_manifest(run)
    if not manifest["batch_id"]:
        print("not submitted yet")
        return 1

    import anthropic
    client = anthropic.Anthropic()
    batch = client.beta.messages.batches.retrieve(manifest["batch_id"])
    if batch.processing_status != "ended":
        print(f"{batch.id} still {batch.processing_status}: {batch.request_counts}")
        return 2

    domain = manifest["domain"]
    docs = {f"{d['idx']:03d}": d for d in manifest["docs"]}
    conn = init_db(Path("data") / "db" / f"{domain}.db")
    run_date = datetime.now().strftime("%Y-%m-%d")
    logged = set(manifest["logged"])
    outcomes = []
    raw_f = open(run / "raw.jsonl", "w", encoding="utf-8")

    for result in client.beta.messages.batches.results(batch.id):
        arm_name, idx = result.custom_id.rsplit("-", 1)
        arm, d = ARMS[arm_name], docs[idx]
        doc = load_doc(d["docId"], Path(d["docpack"]))
        out = {"arm": arm_name, "docId": d["docId"], "status": result.result.type,
               "detail": "", "input_tokens": 0, "output_tokens": 0, "cost_usd": None,
               "stop_reason": None, "sentence_stats": {}}
        if result.result.type == "succeeded":
            msg = result.result.message
            raw_f.write(json.dumps({"custom_id": result.custom_id,
                                    "message": msg.to_dict()}, ensure_ascii=False) + "\n")
            usage = msg.usage
            out.update(input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                       stop_reason=msg.stop_reason,
                       cost_usd=_compute_cost(arm.model, usage.input_tokens,
                                              usage.output_tokens, "batch"))
            if result.custom_id not in logged:
                # Billed whether or not it parses; same ledger as the pipeline.
                log_token_usage(conn, run_date, STAGE, arm.model, usage.input_tokens,
                                usage.output_tokens, doc_id=d["docId"], billing_mode="batch")
                logged.add(result.custom_id)
            if msg.stop_reason == "refusal":
                out["status"], out["detail"] = "refusal", str(getattr(msg, "stop_details", ""))
            elif msg.stop_reason == "max_tokens":
                out["status"], out["detail"] = "truncated", f"hit max_tokens ({MAX_TOKENS})"
            else:
                try:
                    extraction, stats = parse_arm_output(_text_of(msg), doc, arm)
                    arm_dir = run / "results" / arm_name
                    arm_dir.mkdir(parents=True, exist_ok=True)
                    (arm_dir / f"{d['docId']}.json").write_text(
                        json.dumps(extraction, indent=2, ensure_ascii=False), encoding="utf-8")
                    out["status"], out["sentence_stats"] = "ok", stats
                except (ExtractionError, ValueError) as e:
                    out["status"], out["detail"] = "parse_error", str(e)[:300]
        else:
            err = getattr(result.result, "error", None)
            out["detail"] = str(err)[:300] if err else ""
        outcomes.append(out)
    raw_f.close()

    with open(run / "outcomes.jsonl", "w", encoding="utf-8") as f:
        for o in outcomes:
            f.write(json.dumps(o) + "\n")
    manifest["logged"] = sorted(logged)
    manifest["collected_at"] = _now()
    save_manifest(run, manifest)

    by_arm: dict[str, Counter] = defaultdict(Counter)
    cost: dict[str, float] = defaultdict(float)
    for o in outcomes:
        by_arm[o["arm"]][o["status"]] += 1
        cost[o["arm"]] += o["cost_usd"] or 0.0
    for a in manifest["arms"]:
        print(f"  {a:<20} {dict(by_arm[a])}  ${cost[a]:.3f}")
    print(f"  spent ${sum(cost.values()):.2f} (logged to token_usage as stage '{STAGE}')")
    print(f"Next: score --run {run}")
    return 0


# ---------------------------------------------------------------------------
# score
# ---------------------------------------------------------------------------

class Canon:
    """Read-only entity resolution, the same lookup import uses, cached."""

    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
        self.resolver = EntityResolver(self.conn, threshold=RESOLVE_THRESHOLD)
        self.cache: dict[tuple[str, str], str] = {}

    def __call__(self, name: str, etype: str) -> str:
        key = (name, etype)
        if key not in self.cache:
            self.cache[key] = (self.resolver.resolve(name, etype)
                               or generate_canonical_id(name, etype))
        return self.cache[key]


def summarize(extraction: dict[str, Any], canon) -> dict[str, Any]:
    """The sets the comparison works on: canonical entities and relations."""
    name_to_id: dict[str, str] = {}
    entities: set[str] = set()
    names: set[str] = set()
    for e in extraction.get("entities", []):
        cid = canon(e["name"], e.get("type") or "Other")
        entities.add(cid)
        names.add(normalize_name(e["name"]))
        name_to_id[e["name"]] = cid
        for alias in e.get("aliases") or []:
            name_to_id.setdefault(alias, cid)
    triples: set[tuple[str, str, str]] = set()
    kinds: dict[tuple[str, str, str], str] = {}
    for r in extraction.get("relations", []):
        s = name_to_id.get(r["source"]) or canon(r["source"], "Other")
        t = name_to_id.get(r["target"]) or canon(r["target"], "Other")
        triple = (s, r["rel"], t)
        triples.add(triple)
        kinds[triple] = r.get("kind")
    return {"entities": entities, "names": names, "triples": triples,
            "pairs": {frozenset((s, t)) for s, _, t in triples}, "kinds": kinds}


def compare(base: dict[str, Any], arm: dict[str, Any]) -> dict[str, int]:
    """Overlap counts for one document (summed across documents later)."""
    matched = base["triples"] & arm["triples"]
    return {
        "ent_base": len(base["entities"]), "ent_arm": len(arm["entities"]),
        "ent_both": len(base["entities"] & arm["entities"]),
        "name_base": len(base["names"]), "name_both": len(base["names"] & arm["names"]),
        "rel_base": len(base["triples"]), "rel_arm": len(arm["triples"]),
        "rel_both": len(matched),
        "pair_base": len(base["pairs"]), "pair_both": len(base["pairs"] & arm["pairs"]),
        "kind_both": len(matched),
        "kind_same": sum(base["kinds"][t] == arm["kinds"][t] for t in matched),
    }


GATE_LABELS = {
    "evidence_fidelity": "Evidence fidelity (quote)",
    "high_confidence_bad_evidence": "High confidence, bad quote (quote)",
    "orphan_endpoints": "Orphan endpoints",
    "zero_value": "Zero value",
}


def _pct(num: int, den: int) -> str:
    return f"{100 * num / den:.0f}%" if den else "--"


def cmd_score(args: argparse.Namespace) -> int:
    run = Path(args.run)
    manifest = load_manifest(run)
    domain = manifest["domain"]
    outcomes = [json.loads(l) for l in open(run / "outcomes.jsonl", encoding="utf-8")]
    status = {(o["arm"], o["docId"]): o for o in outcomes}
    canon = Canon(Path("data") / "db" / f"{domain}.db")

    base_sum: dict[str, dict] = {}
    base_gates: dict[str, bool] = {}
    gate_fails: dict[str, Counter] = {"baseline": Counter()}
    texts: dict[str, str] = {}
    for d in manifest["docs"]:
        doc = load_doc(d["docId"], Path(d["docpack"]))
        texts[d["docId"]] = doc.get("text") or ""
        base = json.loads(baseline_path(domain, d["docId"]).read_text(encoding="utf-8"))
        base_sum[d["docId"]] = summarize(base, canon)
        g = run_quality_gates(base, texts[d["docId"]])
        base_gates[d["docId"]] = g["overall_passed"]
        gate_fails["baseline"].update(k for k, v in g["gates"].items() if not v["passed"])

    n_docs = len(manifest["docs"])
    base_cost = manifest["baseline_cost_usd"] / n_docs
    base_out = sum(d["baseline_output_tokens"] for d in manifest["docs"]) / n_docs
    rows, by_type, missed, scores = [], {}, {}, {}
    for a in manifest["arms"]:
        arm = ARMS[a]
        tot: Counter = Counter()
        type_base: Counter = Counter()
        type_hit: Counter = Counter()
        miss: Counter = Counter()
        ok = gates_ok = 0
        gate_fails[a] = Counter()
        fidelity: list[float] = []
        sstats: Counter = Counter()
        arm_outcomes = [o for o in outcomes if o["arm"] == a]
        for d in manifest["docs"]:
            o = status.get((a, d["docId"]))
            if not o or o["status"] != "ok":
                continue
            ok += 1
            ext = json.loads((run / "results" / a / f"{d['docId']}.json").read_text(encoding="utf-8"))
            gates = run_quality_gates(ext, texts[d["docId"]])
            gates_ok += gates["overall_passed"]
            gate_fails[a].update(k for k, v in gates["gates"].items() if not v["passed"])
            fr = gates["gates"]["evidence_fidelity"].get("match_rate")
            if fr is not None:
                fidelity.append(fr)
            s = summarize(ext, canon)
            b = base_sum[d["docId"]]
            tot.update(compare(b, s))
            for cid in b["entities"]:
                t = cid.split(":", 1)[0]
                type_base[t] += 1
                if cid in s["entities"]:
                    type_hit[t] += 1
                else:
                    miss[cid] += 1
            sstats.update(o.get("sentence_stats") or {})
        out_tok = sum(o["output_tokens"] for o in arm_outcomes) / max(len(arm_outcomes), 1)
        cost = sum(o["cost_usd"] or 0 for o in arm_outcomes) / max(len(arm_outcomes), 1)
        failures = Counter(o["status"] for o in arm_outcomes if o["status"] != "ok")
        scores[a] = {
            "model": arm.model, "evidence": arm.evidence, "completed": ok, "docs": n_docs,
            "failures": dict(failures), "gates_passed": gates_ok,
            "gate_failures": dict(gate_fails[a]), **tot,
            "fidelity_mean": sum(fidelity) / len(fidelity) if fidelity else None,
            "output_tokens_per_doc": out_tok, "cost_per_doc": cost,
            "sentence_stats": dict(sstats),
        }
        rows.append(
            f"| {a} | {arm.model} | {arm.evidence} | {ok}/{n_docs} | {_pct(gates_ok, ok)} "
            f"| {_pct(tot['ent_both'], tot['ent_base'])} | {_pct(tot['ent_both'], tot['ent_arm'])} "
            f"| {_pct(tot['name_both'], tot['name_base'])} "
            f"| {_pct(tot['rel_both'], tot['rel_base'])} | {_pct(tot['pair_both'], tot['pair_base'])} "
            f"| {_pct(tot['kind_same'], tot['kind_both'])} "
            f"| {out_tok:,.0f} | ${cost:.4f} ({cost / base_cost:.2f}x) |"
        )
        by_type[a] = (type_base, type_hit)
        missed[a] = miss

    lines = [
        f"# Extraction comparison, {run.name}",
        "",
        f"{n_docs} {domain} documents sampled (seed {manifest['seed']}) from batch "
        f"Sonnet 5 extractions in the {manifest['days']} days before {manifest['created_at'][:10]}. "
        f"Baseline: that stored Sonnet 5 extraction. Baseline passed all gates on "
        f"{_pct(sum(base_gates.values()), n_docs)} of documents; output tokens/doc "
        f"{base_out:,.0f}; cost/doc ${base_cost:.4f}.",
        "",
        "Read every arm against the sonnet5 row: that is Sonnet re-extracting the same "
        "documents, so its agreement with the baseline is the ceiling, not 100%.",
        "",
        "| Arm | Model | Evidence | Completed | All gates passed | Entities kept | "
        "Entities that match baseline | Names kept (any type) | Relations kept | "
        "Links kept (any label) | Kind agrees | Output tokens/doc | Cost/doc (vs baseline) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        "Entities kept = share of the baseline's resolved entities the arm also found "
        "(what trending counts as mentions). Names kept ignores the entity type, so the "
        "gap between the two columns is type disagreement. Links kept counts a relation "
        "between the same two entities whatever its label.",
        "",
        "## Gate failures (documents)",
        "",
        "The two quote gates (evidence fidelity, high-confidence-bad-evidence) check that "
        "quotes appear in the text. Sentence arms copy the quote from the text, so they "
        "pass those by construction: compare them on the structural gates only.",
        "",
        "| | " + " | ".join(GATE_LABELS.values()) + " |",
        "|---|" + "---|" * len(GATE_LABELS),
        *(f"| {who} | " + " | ".join(str(gate_fails[who][g]) for g in GATE_LABELS) + " |"
          for who in ["baseline", *manifest["arms"]]),
        "",
        "## Entities kept, by baseline type",
        "",
    ]
    all_types = Counter()
    for tb, _ in by_type.values():
        all_types.update(tb)
    top_types = [t for t, _ in all_types.most_common(10)]
    if top_types and manifest["arms"]:
        first = manifest["arms"][0]
        lines.append("| Type | Baseline count | " + " | ".join(manifest["arms"]) + " |")
        lines.append("|---|---|" + "---|" * len(manifest["arms"]))
        for t in top_types:
            cells = [_pct(by_type[a][1][t], by_type[a][0][t]) for a in manifest["arms"]]
            lines.append(f"| {t} | {by_type[first][0][t]} | " + " | ".join(cells) + " |")
    lines += ["", "## Most-missed baseline entities (documents missed)", ""]
    for a in manifest["arms"]:
        top = ", ".join(f"{cid} ({n})" for cid, n in missed[a].most_common(8)) or "none"
        lines.append(f"- **{a}:** {top}")
    lines += ["", "## Failures and sentence citations", ""]
    for a in manifest["arms"]:
        sc = scores[a]
        extra = ""
        if sc["sentence_stats"]:
            st = sc["sentence_stats"]
            extra = (f"; citations {st.get('cited', 0)}, invalid {st.get('invalid', 0)}, "
                     f"sentences over 200 chars {st.get('over_200', 0)}, "
                     f"cut at 400 {st.get('truncated', 0)}, "
                     f"relations dropped {st.get('relations_dropped', 0)}")
        fid = f"{sc['fidelity_mean']:.0%}" if sc["fidelity_mean"] is not None else "--"
        lines.append(f"- **{a}:** failures {sc['failures'] or 'none'}; "
                     f"evidence fidelity {fid}{extra}")

    report = "\n".join(lines) + "\n"
    (run / "report.md").write_text(report, encoding="utf-8")
    (run / "scores.json").write_text(json.dumps(scores, indent=2) + "\n", encoding="utf-8")
    print(report)
    print(f"Saved {run / 'report.md'} and {run / 'scores.json'}")
    return 0


# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--domain", default=os.environ.get("PREDICTOR_DOMAIN"))
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]),
                        help="repo root holding data/ (default: this script's repo)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="pick documents and estimate cost (no API)")
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--arms", default=",".join(DEFAULT_ARMS))
    p.add_argument("--run-id", default=None)
    p.add_argument("--exclude-run", action="append", default=None,
                   help="earlier run dir whose documents to leave out (repeatable)")

    p = sub.add_parser("submit", help="submit the batch (spends money with --yes)")
    p.add_argument("--run", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true")

    p = sub.add_parser("collect", help="fetch and parse results, log spend")
    p.add_argument("--run", required=True)

    p = sub.add_parser("score", help="compare arms with the baseline (no API)")
    p.add_argument("--run", required=True)

    args = parser.parse_args()
    os.chdir(args.root)
    return {"plan": cmd_plan, "submit": cmd_submit,
            "collect": cmd_collect, "score": cmd_score}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
