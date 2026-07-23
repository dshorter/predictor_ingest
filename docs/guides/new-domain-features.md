# Configuring LLM Features for a New Domain

This guide walks through configuring the four LLM-powered features for a new
domain.  Answer each question — the answers map directly to YAML values in
your `domains/<slug>/domain.yaml` file.

> **Audience**: Future Claude sessions and human developers adding domains.
> All features are opt-in per domain via the `features:` section of domain.yaml.

---

## Quick Reference: How Domains Differ

| Setting | AI/ML | Film | Biotech (future) | Cyber (future) |
|---------|-------|------|-------------------|----------------|
| Disambiguation | enabled | enabled | enabled | enabled |
| Lower bound | 0.40 | 0.40 | 0.35 | 0.45 |
| Inference | **disabled** | enabled | enabled | enabled |
| Confidence discount | n/a | 0.8 | 0.5 | 0.7 |
| Synthesis | disabled | enabled | enabled | enabled |
| Patterns | n/a | corroboration, events | corroboration, trials | threats, attribution |
| Narratives | enabled | enabled | enabled | enabled |
| Narrative style | technical | concise | clinical | analytical |

---

## Section 1: Feature Flags — What to Enable

### Q1: Entity Disambiguation

> Does your domain have entities that appear under different names?
> (e.g., "Greta Gerwig" / "Gerwig", "GPT-4" / "GPT4")

- **YES** → `llm_disambiguation.enabled: true`
- **NO** → `llm_disambiguation.enabled: false`

Most domains benefit from disambiguation.  It costs ~$0.25/month (nano tier).

### Q2: Relation Inference

> Are there implicit relationships between entities that are rarely
> stated explicitly in articles?

- **YES** → `relation_inference.enabled: true`
- **NO** → `relation_inference.enabled: false`

**Key insight**: The AI/ML domain **disables** this because its extraction
prompt captures semantic relations directly from technical prose.  The Film
domain **enables** it because trade press implies many relationships (e.g.,
"Director works with Studio" is implied by production credits, never stated).

Inference is CPU-only (zero LLM cost) unless `require_llm_validation: true`.

### Q3: Cross-Document Synthesis

> Do your sources frequently cover the same events/entities from
> different angles?

- **YES** → `cross_document_synthesis.enabled: true` (high value)
- **NO** → `cross_document_synthesis.enabled: false` (low ROI)

This is the most expensive feature (~$3-5/month, specialist model).  Enable
it when multiple outlets cover the same events — film premieres, security
incidents, clinical trial results.

### Q4: Trend Narratives

> Will your UI show trending entities?

- **YES** → `trend_narratives.enabled: true`
- **NO** → `trend_narratives.enabled: false`

Cheapest feature (~$0.03/month).  Generates "What's Hot and WHY" text for
the top trending entities in `trending.json`.

---

## Section 2: Disambiguation Tuning

### Q5: How ambiguous are entity names?

| Ambiguity Level | Example | `similarity_lower_bound` |
|-----------------|---------|--------------------------|
| Very ambiguous (people, common acronyms) | "WHO" the org vs "WHO" in text | `0.30` |
| Moderately ambiguous (companies, tools) | "A24" vs "A24 Films" | `0.40` |
| Rarely ambiguous (unique names) | Chemical compounds, model IDs | `0.60` |

### Q6: Which entity types need disambiguation most?

Only types listed here will be evaluated (empty = all types):

```yaml
# Film
entity_types_to_disambiguate: [Person, Studio, Production]

# AI/ML
entity_types_to_disambiguate: [Org, Model, Tool]

# Biotech
entity_types_to_disambiguate: [Org, Person, Program]

# Cyber
entity_types_to_disambiguate: [Org, Tool, Person]
```

### Q7: Cost control

- `max_pairs_per_run: 50` — caps how many gray-zone pairs are sent to the LLM
- `batch_size: 15` — pairs per LLM call (higher = fewer calls, more tokens)
- Decisions are cached in `disambiguation_decisions` table — same pair never re-evaluated

---

## Section 3: Inference Rules

### Q8: What implicit relationship chains exist?

Define rules in `domains/<slug>/inference_rules.yaml`.  Each rule has:
- **antecedents**: relation patterns to match (1 or 2)
- **consequent**: the new relation to infer
- **confidence_discount**: multiply antecedent confidences by this factor

**Film examples:**
```yaml
inference_rules:
  - name: "director_studio_via_production"
    description: "Person directs Production distributed by Studio → Person partners with Studio"
    antecedents:
      - {source_type: Person, rel: DIRECTS, target_type: Production}
      - {source_type: Production, rel: DISTRIBUTES, target_type: Distributor}
    consequent:
      rel: PARTNERS_WITH
      source: "antecedent[0].source"
      target: "antecedent[1].target"
    confidence_discount: 0.8
```

**Biotech example:**
```yaml
  - name: "drug_tissue_via_protein"
    antecedents:
      - {source_type: Drug, rel: TARGETS, target_type: Protein}
      - {source_type: Protein, rel: EXPRESSED_IN, target_type: Tissue}
    consequent:
      rel: INDICATED_FOR
      source: "antecedent[0].source"
      target: "antecedent[1].target"
    confidence_discount: 0.5
```

### Q9: How aggressive should inference be?

| Style | `confidence_discount` | `max_inferences_per_run` | Use when |
|-------|-----------------------|--------------------------|----------|
| Conservative | 0.5–0.6 | 100 | High-precision domains (AI/ML, biotech) |
| Moderate | 0.7–0.8 | 500 | Trade press domains (film, geopolitics) |
| Aggressive | 0.9 | 1000 | Exploratory / breadth-first analysis |

---

## Section 4: Synthesis Patterns

### Q10: What cross-document patterns matter?

Choose from these framework-supported patterns:

| Pattern | Description | Good for |
|---------|-------------|----------|
| `corroboration` | Same entity in 2+ docs = higher confidence | All domains |
| `implicit_relations` | Relations implied across docs | Film deals, geopolitics |
| `event_clustering` | Multiple docs about same event | Film festivals, cyber incidents |
| `benchmark_comparison` | Papers comparing on same benchmark | AI/ML |
| `threat_clustering` | Multiple sources on same threat | Cybersecurity |
| `attribution_chains` | Cross-source attack attribution | Cybersecurity |

**Film**: `["corroboration", "implicit_relations", "event_clustering"]`
**AI/ML**: `["corroboration", "benchmark_comparison"]`
**Cyber**: `["corroboration", "threat_clustering", "attribution_chains"]`

---

## Section 5: Narrative Style

### Q11: What tone suits your domain's audience?

| Style | Example Output |
|-------|---------------|
| `concise` | "Greta Gerwig is trending after 3 articles this week about her new Warner Bros project, up from zero mentions last period." |
| `technical` | "GPT-5 shows a 4.2x velocity spike driven by benchmark results on MMLU-Pro and 2 new integration announcements." |
| `analytical` | "NATO expansion trending due to corroborated reports from 3 independent sources on new member state negotiations." |
| `clinical` | "BNT162b4 variant shows 2.1x mention increase following Phase III efficacy data from 3 independent trial sites." |
| `headline` | "Gerwig's Warner Bros Move Dominates Trade Coverage" |

Create a domain-specific prompt at `domains/<slug>/prompts/narrative_system.txt`
for fine-grained tone control.

---

## Section 6: Complete Template

Copy this into your `domain.yaml` and fill in the blanks:

```yaml
# --- LLM Leverage Features ---
features:
  llm_disambiguation:
    enabled: ___              # true/false (Q1)
    similarity_lower_bound: ___  # 0.30–0.60 (Q5)
    similarity_upper_bound: 0.85
    max_pairs_per_run: 50
    batch_size: 15
    entity_types_to_disambiguate: [___]  # (Q6)

  relation_inference:
    enabled: ___              # true/false (Q2)
    confidence_discount: ___  # 0.5–0.9 (Q9)
    max_inferences_per_run: ___  # 100–1000 (Q9)
    rules_file: "inference_rules.yaml"

  cross_document_synthesis:
    enabled: ___              # true/false (Q3)
    batch_size: 5
    min_shared_entities: 1
    max_batches_per_run: 10
    synthesis_patterns: [___]  # (Q10)

  trend_narratives:
    enabled: ___              # true/false (Q4)
    top_n: 10
    max_tokens_per_narrative: 100
    style: "___"              # (Q11)
```

---

## Prompt Templates Checklist

For each enabled feature, create the corresponding prompt template in
`domains/<slug>/prompts/`:

| Feature | File | Required? |
|---------|------|-----------|
| Disambiguation | `disambiguate_system.txt` | Optional (has defaults) |
| Narratives | `narrative_system.txt` | Optional (has defaults) |
| Synthesis | `synthesis_system.txt` | Optional (has defaults) |

All templates support `{entity_types}`, `{relation_types}`, and other
domain-profile placeholders.  See `domains/film/prompts/` for examples.

---

## Verification After Configuration

Run these checks after adding features to a new domain:

```bash
# 1. Dry-run pipeline to verify config loads
python3 scripts/run_pipeline.py --domain <slug> --dry-run

# 2. Run full pipeline
python3 scripts/run_pipeline.py --domain <slug>

# 3. Check disambiguation results
sqlite3 data/db/<slug>.db "SELECT llm_verdict, COUNT(*) FROM disambiguation_decisions GROUP BY llm_verdict"

# 4. Check inferred relations
sqlite3 data/db/<slug>.db "SELECT COUNT(*) FROM relations WHERE kind='inferred'"

# 5. Check narratives
sqlite3 data/db/<slug>.db "SELECT entity_id, narrative FROM trend_narratives ORDER BY run_date DESC LIMIT 5"

# 6. Check synthesis
sqlite3 data/db/<slug>.db "SELECT COUNT(*) FROM synthesis_runs"
```

---

## Section 7: Web Client Hooks

The pipeline config above makes the domain *run*; this section makes it *show
up correctly in the web client* (`web/`). A domain that skips these renders as
flat gray nodes with an empty "About this domain" modal — the pipeline looks
fine, the UI looks broken.

### Q12: Is the domain listed in ALL THREE registries?

The domain enumeration is duplicated in three places — miss one and that
surface silently drifts (this is exactly how the dashboard fallback went stale
at ai+biosafety while the real switcher had all five):

| File | Shape | Purpose |
|------|-------|---------|
| `web/js/domain-switcher.js` (`KNOWN_DOMAINS`) | `{slug, label, title}` | Canonical — the switcher dropdown on every graph page |
| `web/js/ontology.js` (`KNOWN_DOMAINS`) | `{slug, label}` | The ontology page's own switcher |
| `web/dashboard.html` (inline `KNOWN_DOMAINS` fallback) | `{slug, label, title}` | Used only if `domain-switcher.js` fails to load — keep it synced anyway |

### Q13: Do the two per-domain data files exist?

| File | How to create | Without it |
|------|---------------|-----------|
| `web/data/domains/<slug>.json` | **Hand-authored.** Config the client reads for node colors + legend grouping: `title`, `titleShort`, `entityTypes`, `typeGroups`, `typeColors` (one hex per entity type). Copy an existing one (e.g. `semiconductors.json`) and adapt. | All entity types default to gray `#9CA3AF`; the client falls back to an empty config (generic title, no legend groups). |
| `web/data/domains/<slug>.ontology.json` | **Generated:** `python scripts/export_ontology.py --domain <slug>` (or `make export_ontology DOMAIN=<slug>`). Reads `<slug>.json` for colors, so author that FIRST. | The "About this domain" modal has no description and the ontology page is empty. |

The live graph views (`web/data/graphs/live/<slug>/{claims,dependencies,mentions,movers,trending}.json`)
are produced by the pipeline's `copy-to-live` stage — no manual step. They're
gitignored and reach prod via a symlink, so they need no commit.

### Q14: Will it reach prod?

`web/data/domains/*.json` and `*.ontology.json` are **git-tracked** → they
reach `predictor.uzelhub.com` on the next `main` pull + `make deploy-prod`.
Live graph data is symlinked from dev, so it's served on prod the moment the
pipeline writes it — nothing to deploy.

### Web verification

```bash
# All three registries include the slug
grep -c "<slug>" web/js/domain-switcher.js web/js/ontology.js web/dashboard.html

# Both per-domain data files exist and are valid JSON
for f in web/data/domains/<slug>.json web/data/domains/<slug>.ontology.json; do
  python3 -c "import json; json.load(open('$f')); print('OK', '$f')"
done

# No entity type defaulted to gray (means <slug>.json was missing/incomplete)
python3 -c "import json; \
  ets=json.load(open('web/data/domains/<slug>.ontology.json'))['entityTypes']; \
  print('gray-defaulted:', [e['name'] for e in ets if e['color']=='#9CA3AF'] or 'none')"
```
