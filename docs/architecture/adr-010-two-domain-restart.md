# ADR-010: Two-Domain Restart (Film + Semiconductors) Under the Two-Lens Model

**Status:** Proposed (restart process is a first draft)
**Date:** 2026-06-10
**Deciders:** dshorter, Claude
**Supersedes:** cost figures in [domain-fit-analysis.md](../methodology/domain-fit-analysis.md) §Cost Model
**Companion docs:** [movers-vs-current-landscape.md](../free-text/movers-vs-current-landscape.md),
[movers-and-focus-mode.md](../plans/movers-and-focus-mode.md),
[prediction-methodology.md](../methodology/prediction-methodology.md)

## Context

The pipeline has been dormant for several weeks. As of the Sprint 14 smoke
test (2026-05-19): AI and biosafety had **zero** `trend_history` rows and no
documents in 30 days; film was 43 days stale (last run 2026-04-06, ~98K
`trend_history` rows); semiconductors was the only live domain (through
2026-05-11, ~36K rows). To exercise the Movers exporter during the smoke
test, **synthetic `trend_history` snapshots** (run dates 2026-05-19 and
2026-05-12) were inserted by pure SQL into the stale domains' databases.
Those rows are still present and will fabricate `rank_delta` values on the
first real Movers export unless removed.

A full review of the trend methodology and the Movers/Landscape split
(session 2026-06-10) established the findings below, which this ADR turns
into decisions.

### Review findings (summary)

1. **The validation framework is unimplemented.** The methodology defines
   retrospective validation (precision@K, lead time, weight tuning), but no
   snapshot-comparison script exists. All scoring weights remain untested
   hypotheses. This is the highest-leverage unbuilt component.
2. **Chatter sources contribute zero signal today.** `MENTIONS` edges are
   produced only by `scripts/import_extractions.py` as a byproduct of LLM
   extraction. Ingest-only source types (`bluesky`, `reddit` per
   `src/ingest/source_policy.py`) never reach the importer, so they produce
   no mention counts, no velocity, and no Movers signal. This is a
   **deliberately deferred capability, not a bug**: the decision to skip LLM
   extraction for chatter was correct (Movers needs no relations), but the
   cheap substitute path — a non-LLM mention tagger — was never built.
   Every quantitative column in `movers.json` traces back to `MENTIONS`
   edges, so until the tagger exists, chatter feeds are inert.
3. **Movers rank Δ inherits Landscape prominence bias.** `run_movers.py`
   ranks by the composite `trend_score` (0.4 velocity / 0.3 novelty /
   0.3 activity), so movement is measured within a prominence-weighted
   ranking. The uncapped `velocity_raw` column and "hide top 50" filter
   partially compensate; a movement-native score remains an open thread.
4. **The cost basis in planning docs is stale.** `domain-fit-analysis.md`
   budgets at $0.074/doc; the Batch API task records (2026-03-28: 782 docs
   ≈ $8–10 at Sonnet 4.6 batch rates) put the current figure at
   **~$0.012/doc**. ADR-008 made batch the default for all domains.
5. **The 20–25 docs/day guideline has lost two of its three rationales.**
   Cost (batch pricing makes +25 docs/day ≈ $4.50/month) and local
   throughput (batch is async) no longer bind. What survives: the 10–30/day
   statistical floor, `doc_select`'s role as a quality filter, downstream
   resolve load, and the need to hold volume constant within a velocity
   window. The budget is currently a hardcoded framework constant
   (`src/doc_select/__init__.py: DEFAULT_BUDGET/DEFAULT_STRETCH_MAX`), the
   only major tuning knob not in `domain.yaml`.
6. **Domain fitness is still graded on one axis.** The fitness checklist
   (Sprint 13.1) and `domain-fit-analysis.md` use Landscape criteria only
   (persistence, corroboration, island rate). The Movers reframe
   re-diagnoses film's "failure" as high-Movers shape, but the central
   claim — that film's Movers output is signal rather than relabeled churn
   — has **never been tested on real data** (the smoke test used synthetic
   priors).
7. **Model-inferred domain onboarding shifts the bias risk upstream.**
   Ontologies for new domains are inferred by the model at near-zero cost
   (see the pre-filled "Biotech (future)" column in
   [new-domain-features.md](../guides/new-domain-features.md)). The
   remaining human-critical work is **source selection**: model-proposed
   feed lists skew toward consensus outlets (training-data prevalence),
   which structurally under-weight the adventurous, low-prestige sources
   where lead time originates. Source suggestions must be treated as a
   conservative baseline to be adversarially supplemented, not a finished
   list.

## Decisions

### D1 — Restart film + semiconductors; leave AI and biosafety dormant

Semiconductors resumes as the Landscape archetype (freshest data, best
external ground truth, purpose-built inference rules). Film resumes as the
Movers proof-point (deepest history, maximal lens contrast). AI would be a
full cold start that teaches nothing new about the framework; biosafety has
the lowest volume and hardest validation. Both stay paused.

### D2 — Budget on the Batch API cost basis (~$0.012/doc)

Plan of record for the first 30 days, both domains:

| Item | Estimate |
|---|---|
| Extraction (~1,500 docs @ ~$0.012) | ~$19 |
| Synthesis (specialist tier, 2 domains) | ~$6–10 |
| Narratives + disambiguation | ~$1 |
| One-time restart backlog (~600–1,000 docs) | ~$8–15 |
| **Total** | **~$35–45** |

Synthesis is the swing variable; it may be disabled for the first two weeks
without affecting velocity baselines or the Movers proof-point. The
$0.074/doc figure in `domain-fit-analysis.md` is superseded and should be
corrected once week-1 actuals land (see D8).

### D3 — Per-domain doc budgets: film 35/day, semiconductors 20–25/day

Film's budget rises to ~35 (denser graph + Movers breadth; prior analysis in
`new-llm-strategies.txt` already recommended this). Semiconductors keeps
20–25 (8 feeds, selectivity benefits the Landscape lens). Budgets change
**at restart only** — changing volume mid-window creates velocity artifacts
for the same reason source swaps do (methodology §2.7).

**Follow-up:** promote the budget from a hardcoded constant to a
`domain.yaml` key alongside the other per-domain calibration parameters.

### D4 — Chatter mention tagger is a named prerequisite, not a bug fix

The ingest-only design for chatter sources stands. Before any chatter feed
is counted on to contribute Movers signal (and before chatter is cited as a
source-bias mitigation), build the deferred half: a **non-LLM mention
tagger** that alias/string-matches resolved entities against ingest-only
document text and emits `MENTIONS` edges (no relations, zero tokens).
Acceptance check: a `MENTIONS` edge whose `doc_id` traces to a
`bluesky`/`reddit` `source_type` exists in the DB (today this returns zero
rows).

### D5 — Synthetic `trend_history` cleanup is restart item zero

Before the first post-restart run, on the VPS, for **ai, film, biosafety**
(NOT semiconductors — 2026-05-12 falls inside its real history):

```sql
-- Verify: bootstrap rows have all component scores zeroed
SELECT run_date, COUNT(*) AS rows,
       SUM(velocity = 0 AND novelty = 0 AND bridge_score = 0) AS synthetic_looking
FROM trend_history
GROUP BY run_date ORDER BY run_date DESC;

-- Cleanup
DELETE FROM trend_history WHERE run_date IN ('2026-05-19', '2026-05-12');
```

The zeroed-component fingerprint distinguishes bootstrap rows from real ones
if dates alone are ambiguous. A stale synthetic prior is worse than a cold
start: cold start honestly reports "NEW"; a synthetic prior manufactures
plausible-looking rank deltas.

### D6 — 14-day dampening window after restart

All velocity ratios and Movers `rank_delta` values in the first 14 days
post-restart are provisional artifacts (per methodology §2.7 transition
logic — a multi-week gap is a corpus re-initialization). Trending and Movers
output in this window is flagged, not trusted. Daily snapshots ARE collected
from day 1 so the validation dataset starts clean.

### D7 — Retrospective validation script is the top engineering priority

`trend_history` already persists daily full-population snapshots; the
missing piece is the comparison script (snapshot at T vs. outcomes at T+Δ,
producing precision@10/@20, recall, lead time, false-positive rate per
methodology §5). Added to its design: a **first-surfacing-source log** —
for each confirmed trend, record which source surfaced it first and how many
days ahead of consensus outlets. This single instrument validates both the
scoring weights and the source list (are the adventurous sources earning
their keep?).

### D8 — Documentation reconciliation

- Correct the cost model in `domain-fit-analysis.md` with measured batch
  actuals after week 1.
- Update `prediction-methodology.md` §3.4 to match the Sprint 13 code
  (exponential novelty decay, corpus-normalized rarity, min-mentions
  velocity gate, capped first-appearance velocity) and generalize §2.2
  beyond the original 3-source AI framing.
- Correct the `source_policy.py` docstring claim that ingest-only sources
  "contribute to mention counts" — or close the gap via D4, whichever lands
  first.

### D9 — Two-axis domain fitness model (design follow-up)

Replace the Landscape-only fitness checklist with two scores per domain:
a **Landscape score** (persistence, corroboration, connectivity) and a
**Movers score** (churn rate, first-appearance frequency, velocity dynamic
range). Current mapping: semiconductors high-L/moderate-M; AI high/high;
film low-L/high-M (hypothesized — D10 tests it); biosafety
moderate-L/distinctive-M ("just appeared" regulatory events). Each
`domain.yaml` should eventually declare a primary lens, driving defaults
(landing view, upstream gate emphasis).

### D10 — The film Movers proof-point is the restart's qualitative gate

Sprint 14.8's acceptance check ("film Movers surfaces meaningfully different
entities than its trending top-50") is re-run on **real data** after the
dampening window. High churn produces a mechanically impressive Movers table
whether or not there is signal; the proof-point distinguishes emergence from
relabeled island noise. Outcome feeds D9's film scores and the decision to
re-promote film from stress-test to flagship Movers domain.

### D11 — Biopharma is the next domain candidate, after the restart proves out

Biopharma drug development is the strongest next-domain candidate: the same
staged-pipeline shape as semiconductors (preclinical → Phase 1/2/3 →
NDA/BLA → PDUFA → approval), a bounded canonicalizable entity vocabulary
(candidates, companies, targets, indications, NCT trial IDs), natural
inference rules, and dense free trade press. Its decisive advantage is
**ground truth**: ClinicalTrials.gov and FDA outcomes are structured, dated,
publicly confirmable events — the best validation substrate of any domain,
which directly serves D7. Onboarding cost is low because the ontology is
model-inferred (the "Biotech (future)" column in
[new-domain-features.md](../guides/new-domain-features.md) is already
sketched); the real cost is feed vetting and exercising the unused
`edgar`/`patents`-style filing-source path in `source_policy.py`.

**Not started until film + semiconductors restart is stable and D7 exists.**
The binding constraint on domain count is validation, not construction — a
domain you cannot check against ground truth generates plausible output you
cannot trust. Two caveats to watch at onboarding: (a) the model knows
biopharma well, so extraction bias toward famous entities will be stronger
than it was in film — watch first-appearance recall on small-cap biotech;
(b) model-proposed feeds will skew to consensus outlets (D-finding 7) —
adversarially supplement with practitioner-edge sources.

## Restart Process — First Draft (starts at item zero)

Ordered runbook for resuming film + semiconductors. Items 0–3 run on the
VPS before any pipeline invocation; the rest is the first daily cycle and
the two-week provisional window. This is a first draft — refine against
reality on first execution.

**0. Clean synthetic `trend_history` (D5).** For ai, film, biosafety only:
   run the verify query, confirm the zeroed-component fingerprint, then
   `DELETE FROM trend_history WHERE run_date IN ('2026-05-19','2026-05-12')`.
   Do NOT touch semiconductors. This is item zero because a stale synthetic
   prior is worse than a cold start.

**1. Inspect the cleaned backlog before spending.** For each restart domain:
   `SELECT COUNT(*) FROM documents WHERE status='cleaned'`. Confirm the count
   is the expected restart catch-up (~600–1,000 across both), not film's old
   1,057-doc backlog sitting unprocessed — if the latter, decide explicitly
   whether to spend ~$10–12 clearing it or defer it.

**2. Verify feeds resolve (no spend).** `python scripts/diagnose_feeds.py
   --domain film` and `--domain semiconductors`. Remove known-dead feeds
   (e.g. Go Into The Story, SC Film Commission per prior notes) before the
   first ingest so they don't pollute the run log.

**3. Set per-domain budgets (D3).** Film 35/day, semiconductors 20–25/day.
   Until the budget is a `domain.yaml` key, this is a `DEFAULT_BUDGET`
   override at invocation. Lock the value now; do not change it again inside
   the 14-day window (D6).

**4. First ingest + backlog submit.** `make daily DOMAIN=semiconductors` and
   `make daily DOMAIN=film`; `make backlog` for the catch-up docs. Batch
   submit returns rc=2 (EXIT_PENDING) — expected. Collect next day.

**5. Snapshot from day one (D6/D7).** Confirm `trend_history` is being
   written daily for both domains. The validation dataset starts now even
   though the validation script (D7) doesn't exist yet — the data must be
   clean from the first real run or the first T+30 evaluation is unusable.

**6. Flag the 14-day window (D6).** Trending and Movers output through
   restart-day + 14 is provisional. Do not read early `rank_delta` /
   `velocity_raw` as signal; everything looks "NEW" and every ratio is a
   re-initialization artifact.

**7. Watch cost vs. plan (D2/D8).** After the first full cycle, read the
   per-stage token cost in the health report. If it tracks ~$0.012/doc,
   the D2 budget holds; if synthesis dominates, disable it for the window.
   Capture week-1 actuals to correct `domain-fit-analysis.md`.

**8. Qualitative gate at day 14+ (D10).** Re-run the film Movers
   proof-point on real (post-dampening) data: does film's Movers table
   surface meaningfully different entities than its trending top-50, and are
   they real emergence rather than relabeled island churn? Outcome feeds D9
   and the film re-promotion decision.

## Consequences

**Positive.** A clean, honest restart: no fabricated movement, correct cost
basis, per-domain budgets, and a validation dataset that begins clean from
day one. The two-lens contrast (semiconductors Landscape vs. film Movers) is
set up as a real experiment with a defined qualitative gate. Biopharma is
queued behind a validation-first gate rather than spun up on enthusiasm.

**Negative / costs.** Several findings convert to named work items rather
than being resolved here: the chatter mention tagger (D4), the validation
script (D7), the `domain.yaml` budget key (D3 follow-up), the two-axis
fitness model (D9), and the doc reconciliation (D8). Until D4 lands, chatter
feeds remain inert and cannot be cited as bias mitigation. Until D7 lands,
all scoring weights stay unvalidated — the restart produces output whose
quality cannot yet be measured, only collected for later evaluation.

**Risks.** The 14-day provisional window depends on discipline not to
over-read early output. The film proof-point (D10) may fail — high churn can
look like signal — in which case D9's film scores and the flagship-Movers
re-promotion are off the table, and that is a valid, informative outcome
rather than a failure of the restart.

## Status / Next Action

**Proposed.** The restart process is a first draft pending first execution on
the VPS. Decisions D1–D3, D5–D6 are actionable immediately. D4, D7, D9 are
engineering/design follow-ups to schedule. D11 (biopharma) is gated on a
stable restart plus D7. First concrete action: item 0 (synthetic cleanup) on
the next VPS session.