# Operational State

**Purpose:** Single source of truth for how each domain is currently configured to
run. Update this file whenever a domain's extraction mode, gate config, or model
changes — even temporarily. This prevents forensic reconstruction across git logs
and session notes.

**Last updated:** 2026-03-23

---

## How to Read This File

- **Extraction mode** — how the pipeline produces extractions for this domain
- **Models** — cheap (nano) and specialist (Sonnet) models in use
- **Gate overrides** — any departures from default gate behavior and why
- **Env requirements** — what must be set in `.env` or shell for this domain to work
- **Status notes** — temporary deviations, pending measurements, known issues

---

## AI Domain (`domains/ai/`)

| Field | Value |
|-------|-------|
| **Extraction mode** | Escalation: `gpt-5-nano` → `claude-sonnet-4-6-20260218` |
| **Escalation threshold** | 0.6 (quality score) |
| **Gate A — Evidence fidelity** | Active — `evidence_fidelity_min: 0.70` |
| **Gate B — Orphan endpoints** | Active — zero tolerance |
| **Gate C — Zero value** | Active — ≥1 entity for docs >500 chars |
| **Gate D — High-conf + bad evidence** | Active — threshold 0.8 |
| **Env required** | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `UNDERSTUDY_MODEL=gpt-5-nano` |
| **Status** | Stable. All gates nominal. |

**Run:**
```bash
make daily           # or
make daily DOMAIN=ai
```

---

## Biosafety Domain (`domains/biosafety/`)

| Field | Value |
|-------|-------|
| **Extraction mode** | Escalation: `gpt-5-nano` → `claude-sonnet-4-6-20260218` |
| **Escalation threshold** | 0.6 (quality score) |
| **Gate A — Evidence fidelity** | Active — `evidence_fidelity_min: 0.70` |
| **Gate B — Orphan endpoints** | Active — zero tolerance |
| **Gate C — Zero value** | Active — ≥1 entity for docs >500 chars |
| **Gate D — High-conf + bad evidence** | Active — threshold 0.8 |
| **Env required** | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `UNDERSTUDY_MODEL=gpt-5-nano` |
| **Status** | Stable. Added 2026-03-07. Specialist prompt issues resolved (EXT-6). |

**Run:**
```bash
make daily DOMAIN=biosafety
```

---

## Film Domain (`domains/film/`)

| Field | Value |
|-------|-------|
| **Extraction mode** | Escalation: `gpt-5-nano` → `claude-sonnet-4-6-20260218` |
| **Escalation threshold** | 0.55 (lowered — trade press yields lower density scores) |
| **Gate A — Evidence fidelity** | ⚠️ **DISABLED** — `evidence_fidelity_min: 0.0` |
| **Gate B — Orphan endpoints** | Active — zero tolerance |
| **Gate C — Zero value** | Active — ≥1 entity for docs >500 chars |
| **Gate D — High-conf + bad evidence** | ⚠️ **DISABLED** — `high_confidence_threshold: 0.0` |
| **Env required** | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `UNDERSTUDY_MODEL=gpt-5-nano` |
| **Status** | Gates A + D disabled 2026-03-24. See note below. |

**Gate A+D note:** Film trade press paraphrases heavily. Fidelity-based gates (A and D)
both fail on paraphrase-style output from nano — the snippet text-match check can't
distinguish paraphrase from fabrication in this domain. Gates B (orphan endpoints) and
C (zero-value) remain as the primary structural quality signal.

**Tradeoff:** High-confidence nano edges pass through without snippet verification.
Monitor graph quality manually on first few runs; re-enable Gate D if fabrications appear.

**History:**
- 2026-02-25: Prompt tuning (EXT-4) — added orphan/evidence/relation constraints
- 2026-03-17: Film domain launched; gate thresholds tuned for trade press
- 2026-03-21: Switched to pure-Sonnet temporarily (`--no-escalate`) — 89% escalation
- 2026-03-23: Reinstated escalation; Gate A disabled as escalation trigger
- 2026-03-24: Gate D disabled — paraphrase-heavy sources make fidelity check unreliable

**Ref:** `docs/fix-details/ext4-cheap-model-escalation-analysis.md`, `docs/backlog.md` EXT-4

**Run:**
```bash
make daily DOMAIN=film
```

---

## Default Pipeline Behavior (All Domains)

Unless overridden with `PIPELINE_FLAGS`:

- `--escalate` is always passed to `run_extract.py` — cheap model runs first
- `--copy-to-live` is on — graph JSON copied to `web/data/graphs/live/{domain}/`
- Budget: 20 docs target, stretch to 25 for high-quality overflow

**To run pure Sonnet (no cheap model):**
```bash
make daily DOMAIN=film PIPELINE_FLAGS="--no-escalate"
# Also: unset UNDERSTUDY_MODEL  (or leave unset — escalation will error gracefully)
```

---

## Update Protocol

When changing a domain's operational mode:
1. Update the table and status note in this file
2. Update `domains/{domain}/domain.yaml` if gate thresholds changed
3. Add a dated entry to `docs/backlog.md` under the relevant EXT- item
4. Reference this file in the commit message
