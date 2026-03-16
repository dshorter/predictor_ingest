# New Domain Setup: Lessons Learned

*Added 2026-03-16 after biosafety domain normalization gap analysis.*

## The Shakespeare Rule

> Let every domain find its own voice. Just make sure it uses proper grammar.

Domains should discover their own ontology — entity types, canonical relations,
scoring weights, suppressed entities — from their source material. But every
domain must handle the **mechanical patterns** that LLMs produce regardless of
subject matter. These are two different categories of knowledge and should be
treated differently during setup.

---

## Two Categories of Domain Knowledge

### 1. Domain Voice (let it emerge organically)

These should come from reading 20–30 representative documents and asking
"what are the nouns and verbs here?" Don't start from another domain and
modify — start from the source material.

| Element | How it should emerge | Example |
|---------|---------------------|---------|
| **Entity types** | What kinds of things does this domain talk about? | Biosafety: `SelectAgent`, `Facility`, `Regulation` |
| **Canonical relations** | What verbs connect them? | Biosafety: `STORES`, `TRANSFERS`, `INSPECTS` |
| **Semantic synonyms** | What other words mean the same thing in this domain? | `OVERSEES → REGULATES` (requires domain judgment) |
| **Scoring weights** | What matters more — evidence fidelity or relation diversity? | Biosafety weights evidence 0.20 (vs AI's 0.15) |
| **Suppressed entities** | What's too generic to be useful here? | Biosafety: "pathogen", "agent"; AI: "model", "tool" |
| **Prompt examples** | What does a good extraction look like for this content? | Domain-specific snippets and entity patterns |

**Do NOT** copy another domain's taxonomy and relabel it. A biosafety knowledge
graph that looks like an AI knowledge graph with different names is not useful —
it means the ontology was forced rather than discovered.

### 2. LLM Grammar (enforce mechanically)

These are patterns in how LLMs produce output, independent of domain. Every LLM
will do these things, and every domain must handle them.

| Pattern | What happens | Fix |
|---------|-------------|-----|
| **Past tense** | Canonical `STORES` → LLM outputs `STORED` | Normalization map |
| **Gerund form** | Canonical `MONITORS` → LLM outputs `MONITORING` | Normalization map |
| **Passive/`_BY` inversion** | Canonical `OPERATES` → LLM outputs `OPERATED_BY` | Normalization map |
| **Date resolution drift** | LLM outputs `week`, `season`, `decade` instead of `range` | Framework-level map (already shared) |
| **Evidence hallucination** | Snippet not from source text | Quality gates (already shared) |
| **Orphan endpoints** | Relation source/target doesn't match any entity | Quality gates (already shared) |

**These must be generated, not hand-authored.** After defining canonical relations,
run the tense-variant generator to populate the mechanical normalization entries:

```bash
python scripts/generate_normalization.py domains/<your-domain>/domain.yaml
```

This is not optional. The AI domain accumulated 63 tense mappings through months
of iterative failure. The biosafety domain launched without them and hit a 32%
nano accept rate. After adding them: the normalization map went from 69 → 103
entries, and the uncovered relation-type failures dropped to near zero.

---

## The Biosafety Post-Mortem

**Symptom:** 32% nano accept rate (vs ~70%+ for AI domain). 22 escalations to
Sonnet in a single batch. Health report showed orphan endpoints and unknown
relation types as top failure modes.

**Root cause:** The biosafety `domain.yaml` normalization map had good *semantic*
synonyms (OVERSEES→REGULATES, SUPERVISES→REGULATES) but was completely missing
*tense variants* (REGULATED, REGULATING, STORED, STORING, etc.). The AI domain
had these because it went through months of iterative tuning. Biosafety was new
and hadn't hit those failures yet.

**What was NOT the problem:**
- Gate thresholds (identical between domains)
- Framework normalization code (domain-agnostic, works correctly)
- The biosafety ontology itself (entity types and canonical relations were well-chosen)
- The LLM model (nano behaves the same way in both domains)

**Fix:** Added systematic tense coverage (24 past-tense + 10 gerund mappings)
plus the `generate_normalization.py` script to prevent this for future domains.

**Lesson:** Separate "domain modeling" (creative, emergent) from "LLM output
handling" (mechanical, predictable). Automate the latter.

---

## New Domain Setup Checklist

### Phase 1: Discovery (organic)
- [ ] Read 20–30 representative documents from the domain
- [ ] List the nouns (→ entity types) and verbs (→ canonical relations)
- [ ] Identify semantic synonyms that require domain judgment
- [ ] Note what's too generic to be useful (→ suppressed entities)
- [ ] Write 2–3 example extractions by hand to test the taxonomy

### Phase 2: Mechanical Setup (automated)
- [ ] Run `scripts/generate_normalization.py` to add tense variants
- [ ] Validate: all normalization targets must be canonical types
- [ ] Review generated entries — remove any that collide with semantic meanings
  (e.g., if `CONTAINED` means something different from `CONTAINS` in your domain)
- [ ] Run `python -m pytest tests/test_domain_profile.py`

### Phase 3: Calibration (iterative)
- [ ] Extract 10–20 documents with nano
- [ ] Run `scripts/test_normalization_coverage.py` to check for uncovered variants
- [ ] Add any domain-specific semantic synonyms the LLM produces
- [ ] Tune scoring weights based on what matters in this domain
- [ ] Compare accept rate against AI domain baseline (~70%)

---

## Architectural Boundaries

| Layer | What lives here | Who maintains it |
|-------|----------------|-----------------|
| **Framework** (`src/`) | Date resolution map, quality gates, normalization application logic, scoring formula | Shared — changes affect all domains |
| **Domain config** (`domains/X/domain.yaml`) | Entity types, canonical relations, semantic synonyms, scoring weights | Domain author |
| **Generated** (via script) | Tense variants, gerund forms, `_BY` inversions | Auto-generated from canonical list |
| **Prompts** (`domains/X/prompts/`) | Extraction instructions, examples, domain vocabulary | Domain author |

The generated layer sits between framework and domain config. It's deterministic
output from domain-specific input. If a generated entry conflicts with a semantic
meaning in the domain, the domain author removes it and adds the correct mapping
manually.
