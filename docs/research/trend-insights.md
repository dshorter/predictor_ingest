# Trend Insights — From Scores to Publishable Artifacts

**Purpose:** Define how the pipeline goes beyond ranked entity scores to produce
structured, evidence-backed *insight artifacts* that a reader can act on.

**Status:** Research / pre-implementation. Waiting on ≥30 days of pipeline data
for meaningful backtest (earliest ~late March 2026).

**Relationship to existing docs:**
- Extends [prediction-methodology.md](../methodology/prediction-methodology.md) §3–5
  (scoring → articulation layer)
- Builds on [extract-quality-analysis.md](extract-quality-analysis.md)
  (extraction quality → insight quality)
- Uses signals already collected by `src/trend/` (velocity, novelty, bridge)

---

## 1. The Gap

The current pipeline produces a ranked list of trending entities with composite
scores. That's useful for the graph UI (node sizing, halo effects) but not
directly publishable. A score of 0.73 doesn't tell a reader *what happened* or
*why it matters*.

**Insight articulation** bridges that gap: each top-scoring entity gets a
structured artifact explaining the signal in human terms.

---

## 2. Insight Template

Each insight artifact follows this structure:

```yaml
insight:
  entity_id: "model:mixtral-8x22b"
  title: "Mixtral 8x22B mentions accelerating across 4 sources"
  category: "corroborated_acceleration"   # see §3
  period: "2026-03-15 to 2026-03-22"
  signals:
    velocity: 3.2          # 7d ratio
    mention_count_7d: 14
    source_count: 4
    bridge_delta: +2.1     # if available
    novelty: 0.68
  evidence:
    - doc_id: "doc:abc123"
      source: "arXiv CS.AI"
      snippet: "We evaluate Mixtral 8x22B on..."
      published_at: "2026-03-18"
    - doc_id: "doc:def456"
      source: "Hugging Face Blog"
      snippet: "Mixtral 8x22B now available on..."
      published_at: "2026-03-20"
  so_what: "Cross-source acceleration suggests genuine adoption, not single-source hype."
  confidence: "high"       # high / medium / low
  generated_by: "deterministic"  # or "llm" — see §4
```

**Key fields:**
- `title` — one-line summary a reader can scan
- `category` — which insight pattern this matches (§3)
- `signals` — the numeric scores that triggered it
- `evidence` — specific documents backing the claim (reuses extraction provenance)
- `so_what` — why this matters; downstream areas affected
- `confidence` — based on corroboration level and data sufficiency
- `generated_by` — whether articulation was deterministic or LLM-assisted

---

## 3. Insight Categories

Five categories, ordered by how much data they require:

| Category | What it detects | Minimum data needed | Deterministic? |
|----------|----------------|---------------------|----------------|
| **Emerging entity** | New entity with rapid early mentions | 7 days, ≥3 mentions | Yes |
| **Corroborated acceleration** | Known entity accelerating across ≥3 sources | 14 days, ≥3 sources | Yes |
| **Bridge emergence** | Entity connecting previously separate clusters | 14 days, bridge_delta | Yes (graph metric) |
| **Adoption wave** | Cluster of INTEGRATES_WITH / DEPENDS_ON edges forming | 21 days, ≥5 integration relations | Yes (edge counting) |
| **Governance catalyst** | Regulatory entity gaining velocity + connected to tech entities | 14 days, regulatory source | Partially (entity type check) |

These map onto existing node types and relation taxonomy — no schema changes
required. "Emerging entity" uses novelty + velocity. "Corroborated acceleration"
uses velocity + source_count. "Bridge emergence" uses bridge_delta. "Adoption
wave" uses relation type filtering. "Governance catalyst" uses entity type +
velocity.

---

## 4. Deterministic vs LLM Articulation

A key question: how much of insight generation can be done without an LLM?

### What's deterministic (CPU-only)

- Entity detection (already extracted and resolved)
- Co-mention structure (already in relations)
- Velocity, novelty, bridge scores (already computed by `src/trend/`)
- Category assignment (threshold checks on the above signals)
- Title generation from templates (e.g., `"{entity} mentions accelerating across {n} sources"`)
- Evidence assembly (pull top-N documents by recency)
- Confidence assignment (based on corroboration level table in prediction-methodology.md §4.1)

### What benefits from LLM

- `so_what` field — explaining *why* a signal matters requires reasoning about
  context (what the entity does, what adjacent entities are affected)
- Title refinement — template titles are functional but not engaging
- Cross-insight synthesis — "these 3 insights are connected because..."

### Recommended approach

Start deterministic. Template-based titles and category-driven `so_what` stubs
can ship without any LLM cost. Add LLM refinement later if the templates feel
too mechanical — and measure whether readers actually prefer the LLM versions.

This follows the project's existing escalation philosophy: cheap pass first,
specialist only when quality requires it.

---

## 5. Evaluation

### Insight-level vs extraction-level

Current quality gates (evidence fidelity, orphan endpoints, etc.) evaluate at
the *extraction* level. Insight evaluation is a layer above:

| Level | Question | Current coverage |
|-------|----------|-----------------|
| Extraction | Is this valid structured data? | Yes (quality gates + scoring) |
| Insight | Does this tell a reader something useful and true? | **Not yet** |

### Insight quality rubric

| Dimension | Good | Acceptable | Poor |
|-----------|------|------------|------|
| **Accuracy** | All signals correct, evidence real | Signals correct, minor evidence gaps | Wrong signal or fabricated evidence |
| **Timeliness** | Detected before mainstream coverage | Detected same week as mainstream | Detected after mainstream |
| **Actionability** | Reader can act on `so_what` | Reader understands the trend | Reader learns nothing new |
| **Evidence sufficiency** | ≥3 documents, ≥2 sources | ≥2 documents, ≥1 source | Single uncorroborated mention |

### Backtest protocol

Once ≥30 days of data exist:

1. Freeze a snapshot of top-20 trending entities at day T
2. Generate insight artifacts for each using deterministic templates
3. At T+30, score each insight against what actually happened
4. Compute precision@10, lead time, false positive rate (same metrics as
   prediction-methodology.md §5.2)
5. Compare against raw score ranking — does articulation improve human
   assessment of which trends are real?

**Data prerequisite:** ~4-5 days of good pipeline data exist as of 2026-03-03.
Need ≥14 days for first velocity ratios, ≥30 days for a credible backtest.
The pipeline already collects everything needed — just needs time to accumulate.

---

## 6. Implementation Sequence

| Phase | What | Depends on | Earliest |
|-------|------|------------|----------|
| **A — Template spec** | Define title templates and `so_what` stubs per category | Nothing (pure doc) | Now |
| **B — Generator script** | `scripts/generate_insights.py` reads trend scores, applies templates, outputs JSONL | Phase A + `src/trend/` working | Mid-March |
| **C — Backtest harness** | Script that replays historical snapshots and scores insight accuracy | Phase B + ≥30 days data | Late March |
| **D — LLM refinement** | Optional: LLM polishes `so_what` and title for top-N insights | Phase B working + cost decision | Post-V1 |
| **E — UI integration** | Surface insights in "What's Hot" panel (Sprint 7) | Phase B + Sprint 7 | Per project plan |

Phase A can start immediately. Phases B-C align with the data accumulation
timeline. Phase D is explicitly optional — only pursue if deterministic templates
prove insufficient. Phase E ties into the existing Sprint 7 (What's Hot) work.

---

## 7. Relationship to Existing Components

| Existing component | How insights use it |
|--------------------|---------------------|
| `src/trend/` scoring | Input signals (velocity, novelty, bridge) |
| `src/extract/` provenance | Evidence snippets and document references |
| `src/resolve/` canonical IDs | Stable entity identifiers across insights |
| `src/graph/` export | Graph structure for bridge/cluster detection |
| Sprint 7 — What's Hot | UI surface for top insights |
| prediction-methodology.md §5 | Validation metrics (precision, lead time) |
| quality_runs / quality_metrics tables | Could extend to log insight-level quality |

---

## 8. Open Questions

1. **How many insights per day?** Top 5? Top 10? Or only those exceeding a
   confidence threshold? Probably threshold-based to avoid forcing weak insights.

2. **Storage format?** JSONL in `data/insights/` (consistent with extractions)?
   Or rows in SQLite `insights` table? Probably both — JSONL for export,
   SQLite for querying history.

3. **Insight deduplication across days?** An entity trending for 5 consecutive
   days shouldn't produce 5 identical insights. Need a "last insight date"
   check — only re-emit if signals changed meaningfully (e.g., new sources,
   velocity still rising).

4. **Who writes the `so_what` templates?** Domain-specific content that belongs
   in `domains/ai/` once Sprint 6 (domain modularization) lands. Until then,
   hardcode is fine — it's a small set of category-driven strings.
