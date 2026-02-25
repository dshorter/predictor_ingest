# EXT-4: Cheap Model Escalation Analysis & Prompt Tuning

**Date:** 2026-02-25
**Scope:** `src/extract/prompts.py`, `docs/backlog.md`
**Branch:** `claude/debug-daily-process-AVGNa`
**Preceded by:** [pipeline-stall-scoring-overhaul.md](pipeline-stall-scoring-overhaul.md)

---

## Context

After the Feb 22 scoring overhaul (Root Cause 3 in the pipeline stall), the quality
gates and raised thresholds began doing their job — the cheap model (gpt-5-nano) was
now being escalated when its output was shallow. The question was: **how often?**

Three full daily pipeline runs (Feb 22–24) with 223 extractions in escalation mode
produced the first real dataset to answer that question.

---

## What the Data Showed

### Headline: 80% escalation rate

| Metric | Value |
|--------|-------|
| Total extractions | 223 |
| Kept at cheap (gpt-5-nano) | 59 (26%) |
| Escalated to specialist (Sonnet) | 164 (74%) |
| Escalation failed (both models) | 15 (7%) |
| Quality score avg (across kept) | 0.83 |
| Evidence fidelity avg | 0.806 |

The escalation system is barely saving anything. 4 out of 5 documents trigger the
specialist call, so the pipeline pays for **two** API calls on ~74% of documents.
Running Sonnet on everything would actually be cheaper.

### Failure mode breakdown

From the worst-50 quality scores (range 0.29–0.61) and gate failure reports:

**1. Orphan endpoints (dominant failure)**

Nano generates relation source/target names that don't match its own entity names.
Example: entity `"Google"` but relation target `"Google DeepMind"` — the endpoint
is orphaned. The 0% orphan tolerance gate catches these immediately.

This is a **prompt addressable** problem. The prompt tells nano to match entity names
in relations, but the instruction is buried in a sub-bullet of rule #2 and easy to
lose in context. A more prominent, explicit constraint could help.

**2. Evidence fidelity < 70%**

The snippet nano attributes to a relation doesn't appear in the source text. Average
fidelity is 0.806 — sounds fine — but the distribution is **bimodal**: documents either
score ~0.9 or ~0.4. The 0.7 floor catches the low cluster.

This is **partially prompt addressable**. Emphasizing that snippets must be direct
quotes (not paraphrases from the model's memory) could lift the low cluster.

**3. Zero-value extractions (no relations)**

The worst-scoring document (q=0.29) had 24 entities and 0 relations. Nano sometimes
produces a reasonable entity list but no relations at all — schema-valid but useless.

**4. High confidence + bad evidence**

Nano marks relations at 0.9+ confidence but the snippet doesn't support the claim.
This triggers the Gate D escalation (zero tolerance for >=0.8 confidence with
fabricated evidence).

### Model breakdown

Nearly all worst-50 entries were gpt-5-nano. One claude-sonnet failure at 0.58
(edge case, not systemic). The cheap model is the clear bottleneck.

---

## Decision: Lightweight Prompt Tuning

Three options were considered:

| Option | Impact | Risk |
|--------|--------|------|
| **A. Prompt tuning** | Medium-high (addresses root causes) | Low if changes are lightweight |
| **B. Threshold tuning** | Medium (change gates/scoring) | Medium (could mask real problems) |
| **C. Drop cheap-first** | Immediate (just run Sonnet) | Abandons cost savings permanently |

**Chose Option A** with a critical constraint: **don't overload the nano model.**

A cheaper, smaller model has limited instruction-following headroom. Piling on
constraints can cause it to "stress out" — following some rules while silently
dropping others. The approach is to add **three short, clear sentences** that
address the dominant failure modes, not a page of rules.

### Changes applied to `build_extraction_system_prompt()`

Three lines added to the Critical Rules section:

```
- Every relation source and target MUST exactly match an entity name in your entities list
- Evidence snippets MUST be direct quotes or close paraphrases from the document text, not recalled from memory
- Non-trivial documents should produce at least 3 relations connecting entities
```

### What was NOT changed

- No new sections, no expanded instructions, no structural reorganization
- No changes to the tool schema (already enforced by OpenAI strict mode)
- No changes to the single-message Anthropic prompt (`build_extraction_prompt`)
  — Sonnet doesn't have the same failure modes
- No threshold or gate changes — the current gates are catching real problems
- No model swap — nano stays as the understudy for now

---

## How to Measure Impact

After the next 2–3 daily runs (~100 extractions), compare:

| Metric | Before (Feb 22–24) | Target |
|--------|-------------------|--------|
| Escalation rate | 80% | < 50% |
| Orphan endpoint failures | dominant | reduced by half |
| Evidence fidelity avg | 0.806 | > 0.85 |
| Zero-relation extractions | present | near zero |

If the escalation rate doesn't drop below ~50%, the next step is Option C (drop
cheap-first and run Sonnet directly). The cost difference is small (~$8 vs $25/month)
and the complexity cost of maintaining the escalation path may not be worth it.

---

## Files Changed

| File | Change |
|------|--------|
| `src/extract/prompts.py` | Three lines added to Critical Rules in system prompt |
| `docs/backlog.md` | EXT-4 updated with analysis results and status |
| `docs/fix-details/README.md` | Index entry for this document |
| `docs/fix-details/ext4-cheap-model-escalation-analysis.md` | This document |

## Related Documentation

- [pipeline-stall-scoring-overhaul.md](pipeline-stall-scoring-overhaul.md) — The scoring overhaul that enabled this analysis
- [docs/llm-selection.md](../llm-selection.md) — Escalation mode architecture and cost model
- [docs/research/extract-quality-analysis.md](../research/extract-quality-analysis.md) — Quality gate design
- [docs/backlog.md](../backlog.md) — EXT-4 entry
