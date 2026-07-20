# Operational State

**Purpose:** Single source of truth for how each domain is currently configured to
run. Update this file whenever a domain's extraction mode, gate config, or model
changes — even temporarily. This prevents forensic reconstruction across git logs
and session notes.

**Last updated:** 2026-07-20

---

## ⚠️ TEMPORARY: 2x doc budgets during Anthropic's rate reduction (2026-07-20 → 2026-08-15)

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

**Scheduling:** No cron job is currently installed. The cron line (per-domain)
is documented in [automated-setup.md](automated-setup.md); installing it is
part of the ADR-010 restart work.

**Narratives:** Generated by `claude-haiku-4-5-20251001` via the Anthropic API.
Token usage is logged per call. Cost: ~$0.008/day for 10 narratives.

**Calibration report:** Runs automatically as the last pipeline stage. Logs
suggestions to `tuning_log` table. See `docs/backend/calibration-report.md`.

**Budget:** still a hardcoded framework constant
(`src/doc_select/__init__.py: DEFAULT_BUDGET` = 25/day). ADR-010 D3 sets
film ~35/day and semiconductors 20–25/day **at restart only** (mid-window
volume changes create velocity artifacts), and flags promoting the budget to
a `domain.yaml` key as a follow-up.

**Cost basis:** ~$0.012/doc at Sonnet 4.6 batch rates (ADR-010 D2 — the
$0.074/doc figure in `domain-fit-analysis.md` is superseded; first-30-day
plan for both restart domains is ~$35–45 total).

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
