# ADR-012: Which Stages Get a Wall-Clock Cap, and What Firing One Means

**Status:** Proposed (decision requested; §D1–D3 are independent and can be taken separately)
**Date:** 2026-09-13
**Deciders:** dshorter, Claude
**Amends:** none — this is the first statement of stage-cap policy; the current numbers were never decided, they accreted
**Follows from:** [TREND-0](../backlog.md) (fixed `ec72e70`), [ADR-011](adr-011-movers-only-film-and-cost-governance.md) §Context
**Companion docs:** [silent-instruments-2026-08-29.md](/opt/ai-agent-platform/docs/uzelhub-crew/silent-instruments-2026-08-29.md),
director ledger 2026-08-11 "A cap sized once, against data that grows, is a silent capability loss"

## Context

Fixing TREND-0 on 2026-09-13 took film's `trending` stage from an extrapolated
2,654s to 1.88s. That closes the incident and leaves the design question it
exposed untouched: the 600s cap that converted a slow stage into a 38-day
outage is still the default for seven of twelve stages, and nothing about it was
ever decided.

**Three findings, each verifiable today.**

**1. The cap is sized by nothing.** `scripts/run_pipeline.py` resolves each
stage's limit as `stage.get("timeout", 600)`. Five stages carry a deliberate
number; seven inherit 600 by omission:

| stage | cap | fatal | spends money | blocks on something external |
|---|---|---|---|---|
| `ingest` | 2700 | **True** | no | yes — RSS fetches |
| `collect` | 1200 | False | no (results already paid) | yes — polls Batch API |
| `submit` | 120 | False | **yes** — commits spend | yes |
| `import` | 1800 | False | no | no |
| `resolve` | 1800 | False | **yes** — LLM disambiguation | yes |
| `synthesize` | **600\*** | False | **yes** — LLM synthesis | yes |
| `trending` | **600\*** | False | only with `--narratives` | only with `--narratives` |
| `export` | **600\*** | False | no | no |
| `movers` | **600\*** | False | no | no |
| `infer` | **600\*** | False | no | no |
| `docpack` | **600\*** | False | no | no |
| `calibration` | **600\*** | False | no | no |

\* inherited from the default, not chosen.

The number is uncorrelated with hazard in both directions. `synthesize` makes
unbounded LLM calls and is the stage that most deserves a considered cap — it
inherits the default. `export`, `movers`, `infer`, `docpack` and `trending`
(without narratives) are pure local SQLite and deserve no cap at all — they get
the same 600.

**2. The cap guards a hazard these stages do not have.** A wall-clock cap is the
right instrument when overrun is *itself* the harm: money burning, a socket that
may never answer, a queue backing up behind you. For local compute, overrun is
merely slow — and the cap converts "slow" into "no data," which is strictly
worse. `src/trend/` contains no network call of any kind: grep across
`anthropic`, `openai`, `api_key`, `requests.`, `httpx`, `urlopen`, `client.`
returns nothing. Narratives are the only paid part of that stage and they are
behind an opt-in `--narratives` flag, which the daily runner passes and the
scoring half does not need.

So `trending`'s 600s cap could not have prevented a single cent of spend or a
single hung socket. What it bought was a 38-day film outage (2026-08-06 →
2026-09-13) and a 7-day semiconductors outage (from 2026-09-06), both invisible
downstream.

**3. The harm was not the cap. It was that firing one is indistinguishable from
success.** `scripts/run_movers.py` states its own precondition in prose and never
enforces it. The module docstring:

> Run order: this script must run AFTER scripts/run_trending.py for the
> same date, since it depends on today's trend_history rows.

What the code does instead (line 278):

```python
today_run_date = _most_recent_run_date(conn)   # SELECT MAX(run_date) FROM trend_history
if not today_run_date:
    return [], {...}
```

The variable is named `today_run_date`; it holds whatever the newest row is. The
only guard is for an entirely empty table. There is no recency check anywhere in
the module — `grep -niE "stale|too old|freshness"` finds nothing. So when
`trending` produces no rows, movers computes a perfectly well-formed Movers table
from 38-day-old scores, exits 0, and records nothing about which run_date it used.

Eleven of twelve stages are `fatal: False`, so the pipeline continues past the gap
and the downstream stages consume stale input as though it were fresh.

The invariant was known well enough to write down. It was simply never made
checkable — which is the same failure as the cap itself, one layer over.

This is the half that did the damage, and it is orthogonal to the cap numbers.
Re-sizing every timeout without fixing it only changes the date the lie starts.

**4. A backstop already exists one layer up, which makes local-compute caps
redundant as well as harmful.** `predictor-daily@.service` carries
`TimeoutStartSec=2h`, and its own comment records the reasoning: a hard crash
that never reaches the pipeline's own pager "is still caught by the staleness
pager (predictor-staleness.timer) within hours — silent no-data stalls are its
job." Both instruments worked correctly throughout this incident. The staleness
pager named all three current conditions every six hours, including two nobody
had written down. Nothing here needed a better detector.

## Decisions

### D1: A stage gets a wall-clock cap only if overrun is itself harmful

Two qualifying hazards, and a stage must have at least one:

- **It can spend money.** An unbounded LLM loop costs real dollars per second.
- **It can block on something external that may never answer.** A socket, an
  API poll, a remote queue.

Local compute over our own SQLite has neither. It gets no per-stage cap; the
unit's `TimeoutStartSec=2h` is its backstop, which is the correct layer for
"this run is wedged" because it cannot be crossed by ordinary growth.

Applying the rule to the table above:

| cap | no cap |
|---|---|
| `ingest`, `collect`, `submit`, `resolve`, `synthesize`, `trending` *only when* `--narratives` | `import`, `infer`, `export`, `movers`, `docpack`, `calibration`, `trending` without narratives |

`resolve` and `synthesize` keep caps because they make LLM calls. Note that
`resolve`'s 1800s cap is currently firing daily on film (12 consecutive days
from 2026-09-02) — that is a separate item and D1 does not resolve it, but D1
does say the cap there is legitimate in kind, unlike `trending`'s.

### D2: Delete the 600s default. An unset cap means no cap, not a number nobody chose

`stage.get("timeout", 600)` is the mechanism by which seven stages acquired a
limit no one reasoned about. Replace it with an explicit `"timeout": None` for
uncapped stages, so that adding a stage forces the D1 question rather than
silently inheriting an answer.

Where a cap does apply, the number is derived and the derivation is recorded
inline — measured typical duration, the headroom multiple, and the date measured.
A cap with no recorded basis is the thing this ADR exists to stop.

**This is the general form of a law already on the books.** The director ledger's
2026-08-11 entry, "A cap sized once, against data that grows, is a silent
capability loss," logged this as a law after three instances — the calendar's 40k
read ceiling, `leads.yaml` at 10% visibility, `project-plan.md` at 44%. Film's
600s timeout is the fourth instance and semiconductors the fifth. That entry's
fix is the model to copy and was never generalised: it did not merely raise the
ceiling, it added a test that **fails when a document meant to be read whole
outgrows the limit**. A growth tripwire, not a bigger number.

### D3: A stage that produced nothing must not be substitutable by old output

Three changes, in priority order. D3 matters more than D1 and D2 and should land
first if only one lands:

1. **Consumers read a named run, or fail.** `_most_recent_run_date` becomes "the rows
   for the requested `run_date`, else abort with a message naming what is
   missing." A missing run is an error, never a silent substitution.
2. **Artifacts carry their provenance.** Every exported artifact records the
   `run_date` its data was computed from, so a stale serve is visible in the file
   itself rather than only by querying the database behind it.
3. **Re-examine `fatal: False` on the graph stages.** A run whose `trending`
   produced no rows should not proceed to `movers` as though it had. This is not
   a blanket argument for fatality — partial runs are often the right outcome —
   but "continue" must not mean "continue pretending."

## Consequences

- Six stages lose a cap they should never have had. The `2h` unit timeout and the
  6-hourly staleness pager remain, so a genuinely wedged run is still caught —
  by instruments that ordinary data growth cannot trip.
- `synthesize` gains a deliberate cap where it currently inherits one. Its number
  has to be measured; this ADR does not invent it.
- D3 converts a class of silent staleness into loud failure. Expect it to surface
  gaps that have been invisible: `weapons_detection` has scored a corpus frozen
  since 2026-08-28 for 16 days, and under D3 that would have failed visibly
  instead of publishing fresh-looking scores over dead input.
- Adding a stage becomes a decision rather than a default.

## What this ADR exists to prevent

A guard whose failure mode is worse than the thing it guards, sized by a number
nobody chose, firing silently against data that was always going to grow.

The specific trap: the obvious reading of this incident is "600s was too small."
It was not too small. It was the wrong instrument for that stage, and it would
still be the wrong instrument at 6,000s — that would merely have moved the freeze
to a larger graph, which is precisely what TREND-0 predicted and what happened to
semiconductors with nobody touching the number at all.
