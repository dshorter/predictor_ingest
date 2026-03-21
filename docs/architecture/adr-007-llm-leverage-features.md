# ADR-007: LLM Leverage Features — Four Post-Extraction Graph Enrichment Stages

**Status:** Accepted
**Date:** 2026-03-20
**Deciders:** dshorter, Claude (Opus 4.6)
**Sprint:** 8 (LLM Leverage + Instrumentation)

## Context

After Sprint 7 established multi-domain extraction with quality gates, the film
domain's first health report revealed structural weaknesses in the knowledge graph:

- **88.3% uncorroborated entities** — most entities appear in only 1 document
- **38.3% island entities** — entities with zero semantic (non-MENTIONS) relations
- **0 entity merges** — the fuzzy matcher (0.85 threshold) was too conservative
  for gray-zone pairs like "Greta Gerwig" vs "Gerwig"
- **No "why" context** — trending view showed velocity scores but no explanation

These are not extraction quality problems — they're structural limitations of
single-document, single-pass extraction. The graph has the raw material but
lacks the cross-document reasoning that a human analyst would naturally apply.

## Decision

Add four new pipeline stages between import and export, each independently
toggleable per domain via `features:` in `domain.yaml`:

### Feature 1: Entity Disambiguation (`src/resolve/disambiguate.py`)

**Problem:** Fuzzy string matching at 0.85 threshold misses gray-zone pairs
(similarity 0.40–0.85) where names differ but refer to the same entity.

**Solution:** After fuzzy resolution, collect gray-zone pairs and send batches
to a nano-tier LLM with a domain-specific disambiguation prompt. The LLM
returns `merge` / `keep_separate` / `uncertain` verdicts.

**Why per-domain:** Entity disambiguation requires domain judgment. "Fox" and
"Fox Searchlight" are different in film but might be the same in a news domain.
Each domain's `disambiguate_system.txt` prompt encodes these rules.

**Configuration knobs:**
- `entity_types_to_disambiguate` — which types to evaluate (film: Person,
  Studio, Production; AI: Org, Model, Tool; biosafety: Org, Facility, SelectAgent)
- `similarity_lower_bound` / `similarity_upper_bound` — gray zone bounds
- `batch_size` — LLM batch size for cost control

### Feature 2: Trend Narratives (`src/trend/narratives.py`)

**Problem:** The trending view shows "what's hot" but not "why it's hot."
Sprint 8's UI panel needs a 1-2 sentence explanation per trending entity.

**Solution:** After trend scoring, send the top-N trending entities with their
context (scores, recent articles, relations) to a nano-tier LLM to generate
brief "WHY" narratives. Narratives are cached in `trend_narratives` table.

**Why per-domain:** Narrative style varies — film uses trade-press tone
("A24 is trending after 3 Sundance acquisitions"), biosafety uses regulatory
tone ("USAMRIID trending after revised select agent inventory procedures"),
AI uses technical tone. Each domain's `narrative_system.txt` controls this.

**Configuration knobs:**
- `style` — "concise" (film), "technical" (AI), "regulatory" (biosafety)
- `top_n` — how many entities get narratives
- `max_tokens_per_narrative` — cost control

### Feature 3: Relation Inference (`src/infer/__init__.py`)

**Problem:** 38.3% island entities exist because single-document extraction
can't see transitive chains. If Article A says "Gerwig directs Barbie" and
Article B says "Barbie premieres at Venice," no single doc states "Gerwig
participates at Venice."

**Solution:** A pure-CPU rule engine evaluates domain-defined inference rules
against the graph. Rules specify antecedent patterns (1 or 2 relations) and
a consequent relation to create when matched. No LLM needed.

**Why per-domain:** Inference rules are domain ontology, not framework logic.
Film rules chain creative roles through productions to festivals. Biosafety
rules chain regulatory oversight through facilities to select agents. AI domain
disables inference entirely (strict semantic extraction preferred).

**Configuration knobs:**
- `rules_file` — YAML file in `domains/<slug>/` defining rules
- `confidence_discount` — multiplier for inferred relation confidence
- `max_inferences_per_run` — safety limit

### Feature 4: Cross-Document Synthesis (`src/synthesize/__init__.py`)

**Problem:** 88.3% of entities appear in only 1 document. Cross-document
connections (corroboration, implicit relations) are invisible to per-doc extraction.

**Solution:** Group today's documents by shared entities (greedy clustering),
then send each cluster to a specialist LLM to find cross-document connections.
Returns corroborated entities (confidence boost) and inferred relations.

**Why per-domain:** Synthesis patterns are domain-specific. Film looks for
"deal chains" (acquisition + distribution + festival). Biosafety looks for
"regulatory chains" (oversight + containment + transfer). AI domain disables
synthesis (trade press articles are largely self-contained).

**Configuration knobs:**
- `synthesis_patterns` — which patterns to look for
- `batch_size` / `max_batches_per_run` — cost control
- `min_shared_entities` — clustering threshold

## Pipeline Order

```
repair → ingest → docpack → extract → import
  → synthesize (Feature 4)    # cross-doc connections BEFORE resolution
  → resolve + disambiguate    # merge duplicates including new connections
  → infer (Feature 3)         # rule-based inference on clean, resolved graph
  → export → trending + narratives (Feature 2)
```

Synthesize runs before resolve so that cross-document relations inform
disambiguation decisions. Inference runs after resolve so rules operate on
the canonical (merged) entity graph.

## Domain Configuration Matrix

| Feature | Film | AI | Biosafety | Rationale |
|---|---|---|---|---|
| Disambiguation | ✅ Person, Studio, Production | ✅ Org, Model, Tool | ✅ Org, Facility, SelectAgent | All domains have alias-prone entities |
| Inference | ✅ 5 rules (creative→festival chains) | ❌ disabled | ✅ 6 rules (regulatory chains) | AI prefers strict semantic extraction |
| Synthesis | ✅ deal chains, event clustering | ❌ disabled | ✅ regulatory chains, corroboration | AI articles are self-contained |
| Narratives | ✅ concise/trade-press | ✅ technical | ✅ regulatory | All domains benefit from "why" context |

This matrix illustrates why `features:` lives in `domain.yaml` rather than
framework config — each domain has a different optimal recipe based on its
source characteristics and ontology structure.

## Instrumentation

All four features are wired into the existing observability stack:

**Pipeline logs** (`pipeline_YYYY-MM-DD.json`):
- Each stage has a dedicated output parser capturing structured stats
- New stages appear in the `stages` object alongside existing ones

**Database** (`pipeline_runs` table):
- 11 new columns: `synthesis_batches`, `synthesis_corroborated`,
  `synthesis_relations`, `disambig_pairs`, `disambig_merges`,
  `disambig_kept_separate`, `infer_rules`, `infer_relations`,
  `infer_skipped`, `narratives_generated`, `resolve_merges`
- Additive migration via `_ensure_pipeline_runs_columns()` for existing DBs

**Funnel stats** (`funnel_stats` table):
- 3 new stage rows: `synthesize`, `resolve`, `infer`
- Each includes detailed `drop_reasons` JSON

**Health report** (`section_llm_features()`):
- Per-feature activity breakdown with 7d recency
- Island entity rate and uncorroborated rate as key effectiveness metrics
- Warnings for anomalies (e.g., zero merges from many evaluations)

**Dashboard JSON** (`status.json`, `runs.json`):
- 9 new KPIs in status, 6 new per-run metrics in run history

**Feature-specific tables** (created by each feature module):
- `disambiguation_decisions` — per-pair LLM verdicts
- `synthesis_runs` — per-batch synthesis results
- `inference_runs` — per-run inference stats
- `trend_narratives` — cached entity narratives (entity_id + run_date PK)

## Consequences

### Positive
- Each feature is independently toggleable — zero risk to existing domains
- Domain separation preserved: all domain-specific logic in `domains/<slug>/`
- CPU-only inference (Feature 3) adds no API cost
- Full observability from day one — no blind spots in the new stages

### Negative
- Features 1, 2, 4 add LLM API cost (mitigated by nano-tier models and batch limits)
- stdout→parser pattern adds maintenance burden per stage (acknowledged tech debt;
  see "structured sidecar JSON" idea for future pipeline v2)
- Inference rules require domain expertise to author correctly

### Risks
- Disambiguation merges are irreversible in the current schema — bad merges
  contaminate the graph. Mitigated by `uncertain` verdict (no action taken)
  and conservative confidence thresholds.
- Inference rules can create spurious relations if antecedent patterns are too
  broad. Mitigated by `confidence_discount` and `max_inferences_per_run` limits.
