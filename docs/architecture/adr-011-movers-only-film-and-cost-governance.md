# ADR-011: Movers-Only Film, Per-Domain Models, and Cost Governance by Property

**Status:** Accepted (decisions made 2026-08-26..30; §D5 and §D6 are blocked, not open)
**Date:** 2026-08-30
**Deciders:** dshorter, Claude
**Amends:** [ADR-010](adr-010-two-domain-restart.md) §D3 (per-domain doc budgets), §D7 (validation priority), §D10 (film Movers proof-point)
**Companion docs:** [operational-state.md](../backend/operational-state.md),
[silent-instruments-2026-08-29.md](/opt/ai-agent-platform/docs/uzelhub-crew/silent-instruments-2026-08-29.md),
[ext4-cheap-model-escalation-analysis.md](../fix-details/ext4-cheap-model-escalation-analysis.md)

## Context

A housekeeping session spanning 2026-08-26 to 2026-08-30 measured what the
restart domains actually cost and found the plan and the reality had diverged.
Everything below rests on reconstruction from `token_usage`, not estimates.

**Film is 65% of extraction spend** — $153.25 against semiconductors' $79.42 and
weapons_detection's $1.89, ~$234 total in five weeks against ADR-010 D2's
first-30-day plan of $35–45. D2's ~$0.012/doc basis is an order of magnitude
low: film measures **$0.1063/doc**, semiconductors **$0.0849/doc**.

**79% of film's cost is output tokens.** Film runs 1.55x semiconductors'
documents at 1.25x the cost per document; the per-document premium is the
entity-plus-relation extraction payload, not document size — film's documents
are *smaller* (7,007 input tokens/call against 12,615).

**Film's Movers output has been frozen since 2026-08-06.** The `trending` stage
times out at 600s because `score_all()` issues one query per entity — 27,846 for
film, 14,594 for semiconductors — and film crossed the limit as its graph grew.
`run_movers.py` reads `trend_history` with `run_date <= ?`, so it silently
re-serves the last good snapshot and exits 0.

The obvious lever — cut film's document budget — is the wrong one, for a reason
specific to the lens film exists to prove.

## Decisions

### D1 — Film's document budget does not move (amends ADR-010 D3)

Film stays at 35/40. D3 permits budget changes at restart boundaries; this
decision says film's budget must not change **even at a boundary**, while the
Movers proof-point (ADR-010 D10) is outstanding.

Movers is built from mention counts over a 7-day window —
`activity_factor = min(mention_count_7d, activity_cap) / activity_cap`, with
`activity_cap: 20`. Halving film's documents roughly halves its mention counts,
pushes entities under the cap, and moves the rankings. **The volume is the
measurement.** Cutting it would evaluate a degraded corpus and generalise the
result to the full one, which is precisely the error D10 exists to prevent
("high churn produces a mechanically impressive Movers table whether or not
there is signal").

A cut would also need undoing when D2 below lands — two mid-window volume
changes, two velocity artifacts (methodology §2.7), in the one domain under
evaluation.

**Cost of holding:** roughly 1.4x the pre-migration baseline rather than 1.0x
until D2 lands — a few tens of dollars. Accepted deliberately.

Semiconductors and weapons_detection are unaffected and move on the Sept 1
boundary (17/21 and 10/15). Executable form: the `film-untouched` default in
`scripts/sept1_cost_boundary.py`.

### D2 — Film's lever is per-document cost: Movers-only on Haiku

Film's cheap path is to stop paying for what Movers does not consume. ADR-010
D4 already records that **"Movers needs no relations"**; relations are the bulk
of film's output tokens. A mentions-only extraction on Haiku 4.5 ($1/$5 against
Sonnet 5's $3/$15 from Sept 1) drops the relation payload and the rate together
— roughly an order of magnitude, with the mention stream untouched.

The evidence that a cheap model can carry this is already on file.
`ext4-cheap-model-escalation-analysis.md` records every failure of the cheap
model as a **relation** failure — endpoints not matching its own entity names,
snippets absent from source, overconfident relations — and states plainly:
*"Nano sometimes produces a reasonable entity list but no relations at all —
schema-valid but useless."* Useless for the graph is the product for Movers.

**Not the zero-token string tagger** of ADR-010 D4, for film. Film's entity
vocabulary contains ordinary English words — `Bad`, `Plane`, `Dutch`, `RED` —
because film titles are ordinary words. A string matcher would emit a MENTIONS
edge for "Plane" whenever an article mentions an aircraft, and Movers is
entirely mention-driven, so that is a fabricated trend rather than noise at the
margin. D4's tagger remains correct for semiconductors, whose vocabulary is
acronyms and part numbers.

**Gate:** the existing shadow harness, understudy switched to Haiku, at least
100 film documents, with `entity_overlap_pct` **stratified** — short and
common-word entities held to their own threshold. A global 85% would pass while
exactly the ambiguous cases broke.

### D3 — Per-domain model selection is config, not an exception

Model resolution is `domain.yaml` → `PRIMARY_MODEL` → framework default, via
`domain.model_from_profile(profile, stage)`. Stages: `extraction`, `synthesis`,
`narratives`. Declared in `schemas/domain-profile.json`.

The predictor is domain-agnostic. The alternative considered — a per-instance
systemd `EnvironmentFile` giving film its own model — would have put
domain-specific behaviour in a sidecar keyed on a systemd instance name,
outside the config system entirely. This closes ADR-010 D3's follow-up pattern
("promote from a hardcoded constant to a `domain.yaml` key") for models, the way
Sprint 20.5 closed it for budgets.

Relations-off is a `features:` entry (`relation_extraction: {enabled: false}`),
matching `llm_disambiguation` and `relation_inference`. Note that `domain.yaml`
already declares `base_relation: MENTIONS`, validated against the canonical
taxonomy — so "Movers-only" is expressible in existing vocabulary as *extract
the base relation only*. No new concept is introduced.

### D4 — Cost governance is scoped by property, not by category

`PREDICTOR_MAX_COST_USD` (default 15) halts a run when one `run_date`'s spend
passes it, enforced at `log_token_usage` — the single point every billable call
passes — rather than between stages, because the overrun it exists for happened
*inside* one stage.

Every agent in the crew already carried a ceiling. The predictor did not,
because governance had been scoped to things called "agents"; the predictor is a
pipeline, so it was excluded by category rather than by decision, while
outspending all of them combined. **The test is "does it call a paid API
unattended", not "is it an agent."** Apply it to anything new.

A ceiling is only as good as its rate table: `claude-sonnet-5` was missing from
`_TOKEN_PRICES` from 2026-07-20, so cost logged NULL for five weeks and a
$31.28 runaway day on 07-23 was invisible. A new model joins `_TOKEN_PRICES` in
the same commit that starts using it, and an unpriced model now warns rather
than failing open.

### D5 — ADR-010 D10's proof-point cannot currently be run (blocked)

Recorded so it is not mistaken for an open task. Film's `trend_history` is two
disconnected blocks — 03-20..04-06 and 07-19..08-06 — separated by a 104-day
dormancy, and ADR-010 D6's 14-day dampening window covers all but four days of
the second. **Film has four trustworthy snapshots, ever.**

D10's gate therefore cannot be evaluated until `trending` completes again and
30 days of post-dampening history accumulate. Fixing `score_all` is a
prerequisite for the film decision, not a performance nicety.

### D6 — Build ADR-010 D7's validation script against semiconductors first

D7 names the retrospective comparison script the top engineering priority and
is unchanged. What changes is where it is proven: semiconductors has **28
continuous post-dampening snapshots** and crosses Δ=30 on 2026-08-31; film has
four. Build and debug it against the domain that can exercise it, then apply it
to film once film has history.

Note also that §5.3's ground-truth sources are all AI-domain — Papers With Code,
GitHub star velocity, SOTA tables — and none applies to film. The
flash-in-the-pan versus confirmed-trend distinction is measurable from
`trend_history` alone and needs no external source; lead time and
mainstream-adoption do, and film's equivalents (box office, festival lineups,
greenlight announcements) have never been specified.

## Consequences

- Flat spend on Sept 1 is **not** achieved by the budget cut. It is achieved
  when D2 lands. The interim is accepted at ~1.4x.
- `score_all` becomes a prerequisite rather than a cleanup: it blocks D2's
  observability, D5's evidence, and film's contribution to D6.
- Film's fate stays genuinely open. D2 makes it cheap enough that the decision
  need not be rushed; D5 and D6 are what will eventually settle it. If Movers
  proves out, film is worth its reduced cost. If it does not, film is turned
  off having actually answered the question rather than having been starved
  into an unmeasurable state.
- ADR-010 D2's cost basis is superseded by the measured figures in Context.

## What this ADR exists to prevent

D1 was decided on 2026-08-29, recorded in a retrospective, and then contradicted
a day later by a script whose default still cut film — because a narrative
document is not where this project stores decisions. It is stored here now.
