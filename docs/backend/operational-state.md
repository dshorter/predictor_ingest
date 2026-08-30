# Operational State

**Purpose:** Single source of truth for how each domain is currently configured to
run. Update this file whenever a domain's extraction mode, gate config, or model
changes — even temporarily. This prevents forensic reconstruction across git logs
and session notes.

**Last updated:** 2026-07-20

---

## Extraction model: PRIMARY_MODEL is now claude-sonnet-5 (2026-07-20)

> **Updated 2026-08-29 — model selection is no longer env-only.** Resolution
> order is now `domain.yaml` → `PRIMARY_MODEL` → framework default, via
> `domain.model_from_profile(profile, stage)`. A domain that omits the block
> inherits, so naming a model for one domain cannot move another. Stages:
> `extraction`, `synthesis`, `narratives`.
>
> ```yaml
> # domains/<slug>/domain.yaml
> models:
>   extraction: claude-haiku-4-5-20251001
> ```
>
> Same shape `doc_selection` uses for per-domain budgets, and it closes
> ADR-010 D3's follow-up for models the way Sprint 20.5 closed it for budgets.
> Declared in `schemas/domain-profile.json`. **No live domain pins a model
> today** — record it here when one does.

Pipeline-wide default (all domains — `PRIMARY_MODEL` is a single env var). Was `claude-sonnet-4-6`. Motivated by Sonnet 5's intro
pricing (~33% off through 2026-08-31 — verified against both the
project's own `pricing.py` analog research and the claude-api skill's
cached rate table; earlier "50% off" framing was a misremember).
**Unlike the doc-budget bump above, this is not meant to revert** —
once intro pricing ends 2026-09-01, Sonnet 5 costs the same as Sonnet
4.6 already did, and it's a real quality upgrade, so there's no reason
to go back. No calendar VTODO for this one.

Every Anthropic call site PRIMARY_MODEL feeds (`scripts/submit_batch.py`,
`submit_backlog.py`, `run_extract.py`, `collect_batch.py`,
`src/synthesize/__init__.py`) was checked for Sonnet-5 breaking changes
first — none pass sampling params, `budget_tokens`, or assistant
prefill, so nothing needed fixing there. One default *did* need an
explicit override: Sonnet 5 runs adaptive thinking when `thinking` is
omitted (4.6 defaulted to off), so all five call sites now pass
`thinking: {"type": "disabled"}` explicitly to keep cost and output
budget behavior unchanged.

**Follow-up:** watch quality-gate pass rates for the next couple of
weeks and recalibrate `gate_thresholds` per-domain if Sonnet 5's output
shape differs enough to need it (the domains' own gate comments already
say "re-calibrate after 2 weeks of Sonnet-only runs if needed" — this
is that moment, one model-generation early).

---

## ⚠️ SUPERSEDED: 2x doc budgets (2026-07-20 → 2026-08-15)

> **Corrected 2026-08-29, from measurement rather than plan.**
>
> 1. **The film/semiconductors bump never happened.** It was scheduled for
>    2026-08-02 and the VTODO was never actioned; `domain.yaml` still reads
>    35/40 and 20/25. Only `weapons_detection` ever ran at 2x, and it billed
>    $1.89 across the whole period.
> 2. **The end date was wrong.** Both the table below and the VTODOs say
>    2026-08-15, inherited from an early "50% off through mid-August" reading
>    that the section above already corrects to ~33% through **2026-08-31**.
> 3. **The Sept 1 target is 0.63x, not 0.75x.** The ops-calendar item assumed
>    the intro period ran at 0.87 of the pre-migration baseline; reconstructed
>    from `token_usage`, it runs at **1.06**. Flat-vs-pre-migration is 0.63x.
>    The item's *other* figure was exactly right: flat-vs-intro-period was
>    given as 0.67x and measures 0.667.
>
> 4. **Film's budget does not move.** [ADR-011](../architecture/adr-011-movers-only-film-and-cost-governance.md) D1, amending ADR-010 D3. Film is 65% of spend,
>    so cutting it is the obvious lever and the wrong one: Movers is built from
>    mention counts over a 7-day window, so cutting documents cuts the signal —
>    the volume *is* the measurement. Film's cheap lever is per-document cost
>    (79% of its cost is output tokens; a Movers-only pass on Haiku drops the
>    relation payload and the rate together), not document count. Cutting now
>    would also need undoing when that lands: two mid-window volume changes,
>    two velocity artifacts, in the domain under evaluation. Until Haiku lands,
>    spend sits near 1.4x rather than 1.0x — a few tens of dollars against
>    corrupting the measurement that decides whether film is worth keeping.
>
> Execution lives in `scripts/sept1_cost_boundary.py` (dry-runnable), default
> mode `film-untouched`: semiconductors 17/21, weapons_detection 10/15, film
> unchanged at 35/40. `uniform` and `film-weighted` remain in that script for
> the case where Movers-only is abandoned. The rate-table half is split behind
> `--only rates` and must not run before the evening of 08-31 — bumping the
> tables early logs real spend 50% above what is charged, and the cost ceiling
> reads them. The table below is kept as the historical record of what was
> planned.

Operator directive 2026-07-20: Anthropic is running a 50% rate reduction
through mid-August. Original plan doubled `doc_selection.budget`/
`stretch_max` in all three active domains immediately — **reconsidered
same day** once the ADR-010 D3 artifact risk was raised: mid-window
volume changes distort velocity for every entity simultaneously (a
corpus-wide step, not entity-specific signal) until both comparison
windows sit on the new budget, ~1-2 weeks. No run had yet consumed the
higher budget for any domain, so this was still a free decision at the
time, not a fix.

**Resolution:** stagger the activation by domain, per whether a
pre-change baseline actually exists to distort.

| Domain | Normal | Active now | Effective 2026-08-02 | Reverts 2026-08-15 |
|---|---|---|---|---|
| film | 35 / 40 | 35 / 40 (unchanged) | **70 / 80** | back to 35 / 40 |
| semiconductors | 20 / 25 | 20 / 25 (unchanged) | **40 / 50** | back to 20 / 25 |
| weapons_detection | 10 / 15 | **20 / 30** | (already active) | back to 10 / 15 |

- **film/semiconductors:** the bump is delayed until 2026-08-02, when
  the epoch-2 dampening window (D6, 14 days from the 2026-07-19 restart)
  closes — a deliberate ADR-010-correct boundary, not a random mid-window
  day. Captures 2026-08-02 → 2026-08-15 of the discount at zero avoidable
  artifact risk.
- **weapons_detection:** kept at 2x from its very first run. There is no
  prior-budget baseline for this domain — its first-ever extraction was
  already at the higher budget, so there's nothing for a later window to
  discontinuously jump against. Zero artifact risk regardless of timing.

**Ops calendar VTODOs** (`/opt/ai-agent-platform/ops/calendar-add`) are
the durable reminders, not this doc:
- `predictor-apply-2x-budget-film-semis-2026@ai-agent-platform` — due
  2026-08-02, bump film/semiconductors' `domain.yaml` to 70/80 and 40/50.
- `predictor-revert-2x-budget-2026@ai-agent-platform` — due 2026-08-15,
  restore all three domains' `domain.yaml` to their Normal column above
  (weapons_detection's 2x window is shorter than the other two's delayed
  one, but all three end on the same date).

Revert `tests/test_select.py::TestBudgetFromProfile::
test_active_domain_profiles_carry_d3_budgets` alongside each domain.yaml
change (it currently asserts the "Active now" column).

---

## Cost governance (added 2026-08-29)

**`PREDICTOR_MAX_COST_USD`** (default **15**) halts a run when one `run_date`'s
spend passes it. Enforced in `log_token_usage`, not between stages, because the
overrun it exists for happened *inside* a single stage: on 2026-07-23 film's
40-document batch ran nine times, $31.28 in a day against a ~$5 norm. Set to
`0` to disable.

Every other agent on the box already had a ceiling (`SCOUT_MAX_COST_USD` and
friends). The predictor did not, because governance had been scoped to things
called "agents" — the predictor is a pipeline, so it was excluded by category
rather than by decision, while outspending all of them combined.

**A ceiling is only as good as the rate table.** `claude-sonnet-5` was missing
from `_TOKEN_PRICES` from 2026-07-20, so `_compute_cost` returned `None` and
2,139 calls in film alone logged a NULL cost — five weeks unmetered, and a null
cost cannot breach a budget. Fixed, and an unpriced model now emits a warning
once per process instead of failing open. **Add every new model to
`_TOKEN_PRICES` in the same commit that starts using it.**

`claude-haiku-4-5` was also corrected from (0.25, 1.25) — Haiku 3.5's rate — to
**(1.00, 5.00)**, a 4x understatement.

---

## Current Global Status (2026-06-10)

**The pipeline is dormant in all four domains.** No cron job is installed; the
last production runs were semiconductors (~2026-05-11) and film (2026-04-06).
AI and biosafety have had no documents in 30+ days as of the 2026-05-19
Sprint 14 smoke test.

**Restart plan:** [ADR-010](../architecture/adr-010-two-domain-restart.md)
(2026-06-10) restarts **film + semiconductors** under the two-lens model.
AI and biosafety stay dormant (D1).

⚠️ **Pre-restart landmine (ADR-010 D5):** the Sprint 14 smoke test inserted
**synthetic `trend_history` snapshots** (run dates `2026-05-19` and
`2026-05-12`) into the **ai, film, and biosafety** databases. They must be
deleted before the first real post-restart run or they will fabricate
`rank_delta` values. Do **NOT** run the cleanup against semiconductors —
2026-05-12 falls inside its real history. SQL is in ADR-010 D5.

**Post-restart dampening (D6):** all velocity ratios and Movers `rank_delta`
values in the first 14 days after restart are provisional artifacts. Flag,
don't trust.

**Where it runs:** the pipeline runs in the **dev** tree
(`/opt/predictor_ingest`); the prod site at `predictor.uzelhub.com` serves the
same generated JSON via symlinks. See the "Deployment Topology" section of
[CLAUDE.md](../../CLAUDE.md).

---

## How to Read This File

- **Extraction mode** — how the pipeline produces extractions for this domain
- **Models** — extraction model and narrative model in use
- **Gate overrides** — any departures from default gate behavior and why
- **Env requirements** — what must be set in `.env` or shell for this domain to work
- **Status notes** — temporary deviations, pending measurements, known issues

---

## AI Domain (`domains/ai/`)

| Field | Value |
|-------|-------|
| **Extraction mode** | Anthropic Batch API (`claude-sonnet-4-6-20260218`) — ADR-008 |
| **Narrative model** | `claude-haiku-4-5-20251001` (switched from `gpt-5-nano` 2026-03-27) |
| **Gate A — Evidence fidelity** | Active — `evidence_fidelity_min: 0.70` |
| **Gate B — Orphan endpoints** | Active — zero tolerance |
| **Gate C — Zero value** | Active — ≥1 entity for docs >500 chars |
| **Gate D — High-conf + bad evidence** | Active — threshold 0.8 |
| **Env required** | `ANTHROPIC_API_KEY` |
| **Status** | **DORMANT** — no documents in 30+ days as of 2026-05-19; zero `trend_history` rows before the synthetic inserts. No restart planned (ADR-010 D1: full cold start, teaches nothing new). ⚠️ Contains synthetic `trend_history` rows — D5 cleanup applies. |

---

## Biosafety Domain (`domains/biosafety/`)

| Field | Value |
|-------|-------|
| **Extraction mode** | Anthropic Batch API (`claude-sonnet-4-6-20260218`) — ADR-008 |
| **Narrative model** | `claude-haiku-4-5-20251001` (switched from `gpt-5-nano` 2026-03-27) |
| **Gate A — Evidence fidelity** | Active — `evidence_fidelity_min: 0.70` |
| **Gate B — Orphan endpoints** | Active — zero tolerance |
| **Gate C — Zero value** | Active — ≥1 entity for docs >500 chars |
| **Gate D — High-conf + bad evidence** | Active — threshold 0.8 |
| **Env required** | `ANTHROPIC_API_KEY` |
| **Status** | **DORMANT** — no documents in 30+ days as of 2026-05-19. No restart planned (ADR-010 D1: lowest volume, hardest validation). ⚠️ Contains synthetic `trend_history` rows — D5 cleanup applies. |

---

## Film Domain (`domains/film/`)

| Field | Value |
|-------|-------|
| **Extraction mode** | Anthropic Batch API (`claude-sonnet-4-6-20260218`) — ADR-008 |
| **Narrative model** | `claude-haiku-4-5-20251001` (switched from `gpt-5-nano` 2026-03-27) |
| **Gate A — Evidence fidelity** | ⚠️ **DISABLED** — `evidence_fidelity_min: 0.0` |
| **Gate B — Orphan endpoints** | Active — zero tolerance |
| **Gate C — Zero value** | Active — ≥1 entity for docs >500 chars |
| **Gate D — High-conf + bad evidence** | ⚠️ **DISABLED** — `high_confidence_threshold: 0.0` |
| **Env required** | `ANTHROPIC_API_KEY` |
| **Status** | **DORMANT since 2026-04-06** (~98K real `trend_history` rows — deepest history of any domain). **Restart planned** per ADR-010 as the Movers proof-point (D10). Budget rises to **~35 docs/day at restart** (D3). ⚠️ Contains synthetic `trend_history` rows — D5 cleanup applies before first run. |

**Gate A+D note:** Film trade press paraphrases heavily. Fidelity-based gates (A and D)
both fail on paraphrase-style output — the snippet text-match check can't
distinguish paraphrase from fabrication in this domain. Gates B (orphan endpoints) and
C (zero-value) remain as the primary structural quality signal.

**History:**
- 2026-02-25: Prompt tuning (EXT-4) — added orphan/evidence/relation constraints
- 2026-03-17: Film domain launched; gate thresholds tuned for trade press
- 2026-03-21: Switched to pure-Sonnet temporarily (`--no-escalate`) — 89% escalation
- 2026-03-23: Reinstated escalation; Gate A disabled as escalation trigger
- 2026-03-24: Gate D disabled — paraphrase-heavy sources make fidelity check unreliable
- 2026-03-25: ADR-008 — Anthropic Batch API replaces two-tier escalation for all domains
- 2026-03-27: Narrative model switched from `gpt-5-nano` to `claude-haiku-4-5-20251001`
- 2026-03-27: Calibration report wired into pipeline as automatic final stage
- 2026-04-06: Last production run before dormancy
- 2026-05-19: Sprint 14 smoke test inserted synthetic `trend_history` snapshots (cleanup required — ADR-010 D5)
- 2026-06-10: ADR-010 — restart planned (Movers proof-point), budget → ~35/day

**Ref:** `docs/fix-details/ext4-cheap-model-escalation-analysis.md`, `docs/backlog.md` EXT-4

**Run:**
```bash
make daily DOMAIN=film
```

---

## Semiconductors Domain (`domains/semiconductors/`)

| Field | Value |
|-------|-------|
| **Extraction mode** | Anthropic Batch API (`claude-sonnet-4-6-20260218`) — ADR-008 |
| **Narrative model** | `claude-haiku-4-5-20251001` |
| **Gate A — Evidence fidelity** | Active — `evidence_fidelity_min: 0.70` |
| **Gate B — Orphan endpoints** | Active — zero tolerance |
| **Gate C — Zero value** | Active — ≥1 entity for docs >500 chars |
| **Gate D — High-conf + bad evidence** | Active — threshold 0.8 |
| **Env required** | `ANTHROPIC_API_KEY` |
| **Status** | **DORMANT since ~2026-05-11** — was the last live domain (~36K real `trend_history` rows). **Restart planned** per ADR-010 as the Landscape archetype (D1). Budget stays 20–25 docs/day (D3). **No synthetic rows** — do NOT run the D5 cleanup here (2026-05-12 falls inside its real history). |

All four gates active at defaults — semiconductor trade press is precise and
technical, so evidence fidelity is expected to hold. Calibrate after the first
two weeks of post-restart runs.

**Run:**
```bash
make daily DOMAIN=semiconductors
```

---

## Default Pipeline Behavior (All Domains)

**Default domain:** `film` (set in `Makefile` line 4, `scripts/run_pipeline.py`, and `src/domain/__init__.py`). Changed from `ai` on 2026-03-24.

**Extraction architecture (ADR-008):** All domains use the Anthropic Batch API. The
old two-tier escalation (`gpt-5-nano` → `claude-sonnet-4-6`) has been removed. The
daily pipeline follows a staggered handoff:

1. **Today's run:** `collect` retrieves yesterday's batch results → `import` → `resolve` → `export` → `trending`
2. **Then:** `ingest` → `docpack` → `submit` submits today's batch
3. **Finally:** `calibration` report runs and logs suggestions to `tuning_log`

Batches typically complete within 1–21 hours (Anthropic SLA: 24h).

**Scheduling:** LIVE since 2026-07-22 as **systemd timers**, not cron —
`predictor-daily@{film,semiconductors,weapons_detection}` at 06:00 / 06:45 /
07:30 ET, plus `predictor-staleness.timer`. The unit deliberately carries no
`OnFailure=`: `run_pipeline.py` pages `[PREDICTOR]` on every outcome with a
richer summary, and the staleness pager backstops a hard crash. Units live in
`/etc/systemd/system/`, outside this repo.

**Narratives:** Generated by `claude-haiku-4-5-20251001` via the Anthropic API.
Token usage is logged per call. Cost: **~$0.032/day** for 10 narratives —
corrected 2026-08-29, the old ~$0.008 figure derived from the 4x-low Haiku rate.

**Calibration report:** Runs automatically as the last pipeline stage. Logs
suggestions to `tuning_log` table. See `docs/backend/calibration-report.md`.

**Budget:** per-domain in `domain.yaml` under `doc_selection` since Sprint 20.5
— ADR-010 D3's follow-up is closed. `src/doc_select/__init__.py:
DEFAULT_BUDGET` (25/day) is now only the fallback for a domain that omits the
key. Live: film 35/40, semiconductors 20/25, weapons_detection 20/30. Change at
window boundaries only — mid-window volume changes create velocity artifacts.

**Cost basis: measured, 2026-08-29.** ADR-010 D2's ~$0.012/doc was a Sonnet 4.6
batch-rate estimate and is an order of magnitude low for the restart domains.
Reconstructed from `token_usage` (extraction only, Sonnet 5 intro rates):

| Domain | Docs | $/doc | Period total |
|---|---|---|---|
| film | 1,415 | **$0.1063** | $153.25 |
| semiconductors | 914 | **$0.0849** | $79.42 |
| weapons_detection | — | — | $1.89 |

Total since the 07-20 migration: **~$234 in five weeks**, against a
first-30-day plan of $35–45. Film is ~65% of it, and **79% of film's cost is
output tokens** — extraction emits entities *and* relations, and relations
dominate. That is why the cheap lever for a Movers-only domain is per-document
output, not document volume.

**Article text is capped at 50,000 characters** (`src/ingest/rss.py:
MAX_TEXT_CHARS`, per-feed `max_chars:` override), mirroring the EDGAR guard.
Uncapped SemiWiki posts were arriving at ~115K input tokens against an ~11K
median — 2.8% of semiconductors' calls, 11.5% of its spend.

**Env required (all domains):** `ANTHROPIC_API_KEY` only. `OPENAI_API_KEY` is no
longer needed for extraction or narratives (still works if set — narrative model
can be overridden via `--narrative-model`).

---

## Update Protocol

When changing a domain's operational mode:
1. Update the table and status note in this file
2. Update `domains/{domain}/domain.yaml` if gate thresholds changed
3. Add a dated entry to `docs/backlog.md` under the relevant EXT- item
4. Reference this file in the commit message
