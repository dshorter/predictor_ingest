# Domain Separation Architecture

This document defines the boundary between **domain-independent framework**
and **domain-specific configuration** in the prediction pipeline. Any session
working on this codebase should preserve this separation.

---

## Why This Matters

The scoring math, validation protocol, and pipeline architecture contain
**zero AI-specific logic**. The same framework applies to biotech, climate,
cybersecurity, fintech, geopolitics, or any domain where structured claims
are extracted from a corpus over time. Keeping this separation clean means:

1. New domains can be added by supplying a domain profile, not by forking
2. Framework improvements (better scoring, validation, etc.) benefit all domains
3. Domain experts configure their profile without touching scoring internals

---

## The Boundary

### Domain-Independent (DO NOT add domain-specific content here)

| Component | Location | What it does |
|-----------|----------|--------------|
| Velocity scoring | `src/trend/` | Mention frequency rate-of-change |
| Novelty scoring | `src/trend/` | Age + rarity composite |
| Bridge scoring | `src/trend/` | Structural centrality proxy |
| Composite ranking | `src/trend/` | Weighted combination of signals |
| Corroboration weighting | `src/trend/` (planned) | Source diversity modifier |
| Entity resolution | `src/resolve/` | Fuzzy matching + alias merging |
| Schema validation | `src/schema/` | JSON Schema conformance checks |
| Graph export | `src/graph/` | Cytoscape.js element generation |
| Evidence model | `src/db/` | Provenance storage (docId, snippet, URL) |
| Validation framework | `docs/methodology/` | Precision/recall targets, retrospective protocol |
| Weight tuning protocol | `docs/methodology/` | A/B testing procedure for score weights |
| Bias catalog | `docs/methodology/` | Known biases and mitigations |
| Pipeline orchestration | `scripts/`, `Makefile` | Ingest → clean → extract → resolve → export |

**Rule:** These components must never reference specific entity types, relation
names, or source URLs. They operate on the abstractions (entities have types,
relations have canonical names, sources have categories).

### Domain-Specific (lives in config and schemas)

| Component | Location | What it contains |
|-----------|----------|-----------------|
| Entity type enum | `schemas/extraction.json` | The set of node types (e.g., `Model`, `Dataset`) |
| Relation taxonomy | `schemas/extraction.json` + `CLAUDE.md` | Canonical relation names (e.g., `TRAINED_ON`) |
| Source list | `config/feeds.yaml` | RSS feeds and source metadata |
| Source categories | `config/feeds.yaml` | Category labels for corroboration scoring |
| Extraction prompts | `src/extract/` | LLM prompts tuned for domain vocabulary |
| Canonical ID prefixes | `src/util/` | Slug prefixes (e.g., `model:`, `org:`) |
| Ground truth sources | `docs/methodology/` | External validation references |

**Rule:** When adding a new domain, these are the **only** files that should
change. If you find yourself modifying scoring logic for a domain-specific
reason, you're coupling the framework to the domain — stop and reconsider.

---

## Current Domain Profile: AI/ML

```
Domain:           AI and Machine Learning
Entity types:     Org, Person, Program, Tool, Model, Dataset, Benchmark,
                  Paper, Repo, Tech, Topic, Event, Location, Document, Other
Key relations:    TRAINED_ON, USES_MODEL, USES_DATASET, EVALUATED_ON,
                  USES_TECH, DEPENDS_ON, INTEGRATES_WITH, MEASURES
Source categories: Academic (arXiv), Open-source (HF), Industry (OpenAI)
ID prefixes:      org:, person:, model:, tool:, dataset:, benchmark:,
                  paper:, repo:, tech:, topic:, doc:
Ground truth:     Papers With Code, GitHub star velocity, Google Trends
```

---

## How to Add a New Domain

1. **Copy the template:** `cp -r domains/_template domains/<your-domain>`

2. **Edit `domain.yaml`** — fill in:
   - Entity types and their ID prefixes
   - Relation taxonomy (canonical names + normalization map)
   - Quality thresholds tuned for your domain's expected density
   - Suppressed entities (generic terms to filter out)

3. **Customize `prompts/`** — adapt system/user prompt templates for your
   domain vocabulary and specificity rules

4. **Configure `feeds.yaml`** — add RSS feeds relevant to your domain

5. **Configure `views.yaml`** — define which relations appear in each graph view

6. **Validate:** `python -m pytest tests/test_domain_profile.py`

7. **Run:** `make daily --domain <your-domain>`

The JSON Schema for extraction output is generated dynamically from your
`domain.yaml` profile — no need to create a separate schema file.

See `domains/ai/` for the complete working example.

---

## Enforcement

New sessions should check this boundary when making changes:

- Adding a new entity type? → `domains/<domain>/domain.yaml` only
- Adding a new relation? → `domains/<domain>/domain.yaml` + `CLAUDE.md` taxonomy
- Changing scoring math? → Must remain entity-type-agnostic
- Adding a source? → `domains/<domain>/feeds.yaml` only
- Changing extraction prompts? → `domains/<domain>/prompts/` only
- Modifying validation targets? → `docs/methodology/` only

If a change touches both sides of the boundary, it likely needs to be split
into a framework change and a domain config change.
