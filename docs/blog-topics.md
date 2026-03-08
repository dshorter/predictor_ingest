# Blog Topics Backlog

Topics and themes from the predictor_ingest journey, captured for potential
writeups. Not full entries — just seeds with links to relevant code/docs.

---

## Building the Pipeline

1. **Archive-First Data Architecture**
   Why we store raw HTML before extracting anything. Re-extraction as schemas
   improve. `src/ingest/`, `src/clean/`, CLAUDE.md §Archive-first.

2. **The Pipeline Stall Saga (PRs #74–#91)**
   Debugging why `make daily` kept processing the same 3 docs. Root cause:
   `fetched_at` vs `published_at` filtering, dedup logic, status field wiring.
   [docs/fix-details/](docs/fix-details/), [date-filtering.md](docs/architecture/date-filtering.md).

3. **LLM Extraction Quality Gates — Zero Tokens, CPU-Only**
   Building quality checks that catch bad extractions without calling an LLM.
   Evidence fidelity, orphan endpoints, zero-value detection.
   [extract-quality-analysis.md](docs/research/extract-quality-analysis.md), `src/extract/`.

4. **Relation Normalization: Taming LLM Output**
   LLMs invent relation types. How 70+ normalization mappings funnel them into
   canonical types. PR #99 (near-miss normalization). `domain.yaml` §normalization.

5. **Mode A vs Mode B: With and Without an API Key**
   The docpack workflow for manual extraction via ChatGPT web. Why downstream
   steps shouldn't care where extractions came from.
   [manual-workflow-plan.md](docs/backend/manual-workflow-plan.md).

## The UI Journey (Sprints 1–5)

6. **From Dead Code to Working Features (Sprint 1)**
   Features that were built but never wired up: `.new` class, `dbltap` handlers,
   `prefers-reduced-motion`. The embarrassment-to-fix ratio metric.

7. **Cytoscape.js Gotchas — A Field Guide**
   Colons in IDs break CSS selectors. No pseudo-selectors. Manual `cy.resize()`.
   fcose dependency loading order. [troubleshooting.md](docs/ux/troubleshooting.md).

8. **Building a Design System Inside a Static Site**
   CSS custom properties, design tokens, dark mode, Lucide SVG icons — all in a
   single HTML file with zero build tools. Sprints 2–4.

9. **Panel Overlay vs Panel Shrink: A Layout Decision**
   PR #118 changed panels from shrinking the graph to overlaying it. Why this
   simplified everything and killed a whole category of resize bugs.

## Architecture & Domain Separation

10. **The 70/30 Split: Domain-Agnostic by Design**
    How we identified that 70% of the pipeline is domain-independent. The boundary
    definition. The grep-audit test that enforces it.
    [domain-separation.md](docs/architecture/domain-separation.md).

11. **Plugin Architecture Without Plugins**
    No abstract base classes, no plugin registries. Just a YAML profile and a
    directory convention. `domains/_template/`, `domain-profile.json` schema.
    Sprint 6 implementation notes.

12. **Standing Up a Second Domain in One Session**
    From "what if biosafety?" to 13 feeds, 14 entity types, 35 relations, and a
    working domain profile — all in Sprint 6B. What broke, what transferred
    cleanly, what surprised us.

13. **The Convergence Narrative: Five Vectors Meeting Mid-March**
    How insights, sources, cost spectrum, plugin architecture, and connectors all
    converge at the same point. An ADR in narrative form.
    [convergence-narrative.md](docs/architecture/convergence-narrative.md).

## Trend Scoring & Signals

14. **Velocity, Novelty, Bridge: Three Signals for Emerging Trends**
    The math behind trend scoring. Why velocity alone is noisy. How bridge nodes
    reveal cross-domain connections. `src/trend/`, [prediction-methodology.md](docs/methodology/prediction-methodology.md).

15. **Insight Articulation: From Scores to Sentences**
    Templates, categories, "so what" stubs. Deterministic generation for V1,
    LLM-enhanced for V2. [trend-insights.md](docs/research/trend-insights.md).

16. **Source Selection Strategy: Primary, Secondary, Echo**
    Why you need all three tiers. Primary for ground truth, echo for velocity
    signal. Entity overlap as a design goal, not a bug.
    [source-selection-strategy.md](docs/source-selection-strategy.md).

## Process & Meta

17. **Sprint Planning with AI: The Project Plan as Living Document**
    How `docs/project-plan.md` evolved from backlog dump to stability-ordered
    sprint plan with model assignments. ~2 sprints/day pace.

18. **The Cost Spectrum: Haiku → Sonnet → Opus for Extraction**
    Why cheap models are good enough for most docs. Escalation mode. Shadow
    scoring. [llm-selection.md](docs/llm-selection.md).

19. **Debugging Remotely via Gist Snapshots**
    `collect_diagnostics.sh`, `collect_metrics_gist.sh` — shipping a compact
    database snapshot for async debugging. PRs #85–#89.

20. **Multi-Domain Content Frequency: AI vs Biosafety**
    AI generates ~50–100 articles/day across feeds. Biosafety is ~5–15/day with
    longer relevance cycles. How this changes trend scoring parameters
    (max_age_days, activity_cap, velocity weighting).

---

*Last updated: 2026-03-07*
