# LLM Selection for Extraction Pipeline

## Decision Context

The pipeline (Mode A) requires an LLM to extract entities, relations, tech terms,
and dates from 10-20 AI-domain articles per day. Outputs must conform to
`schemas/extraction.json` — a nested JSON schema with 15 entity type enums,
31 relation type enums, conditional validation (asserted relations require
evidence), and numeric confidence scores.

## Selection Criteria (ordered by evaluation priority)

### 1. JSON schema compliance (measured directly)

The gating criterion. If output doesn't pass `validate_extraction()`, nothing
downstream works. We measure this directly using our own schema validator against
real articles.

**Why first:** This is quantifiable. We can run N articles through each candidate
and compute a pass rate without manual annotation.

**What we test:**
- Valid JSON parse (no trailing commas, no prose mixed in)
- All required fields present (`docId`, `extractorVersion`, `entities`, `relations`, `techTerms`, `dates`)
- Entity `type` values match the 15-value enum
- Relation `rel` values match the 31-value enum
- Relation `kind` is one of `asserted` | `inferred` | `hypothesis`
- `confidence` is a float in [0, 1]
- Asserted relations include non-empty `evidence` array
- Evidence objects contain required `docId`, `url`, `snippet`

**Mitigations available:** JSON mode / structured output APIs, retry on parse
failure, post-processing (strip markdown fences). These reduce but don't
eliminate the importance of native compliance.

### 2. Inference and classification quality (published benchmarks)

The higher-value but harder-to-measure criterion. Determines whether the model
correctly navigates the taxonomy:

- Entity typing: `Model` vs `Tool` vs `Tech`
- Relation classification: `USES_MODEL` vs `TRAINED_ON` vs `EVALUATED_ON`
- Kind assignment: `asserted` vs `inferred` vs `hypothesis`
- Evidence grounding: snippets must come from the actual source text

**Why second:** Reinventing NER/RE benchmarks from scratch is expensive. We rely
on published evaluations as a proxy, then spot-check a handful of extractions
manually to confirm the benchmarks translate to our specific taxonomy.

**Relevant benchmarks:**
- MMLU (general reasoning)
- IFEval (instruction following)
- StructEval (structured output generation)
- NER F1 on CoNLL/OntoNotes (entity recognition)
- Few-shot RE on TACRED/FewRel (relation extraction)

### 3. Evidence grounding (anti-hallucination)

Per CLAUDE.md: "Do not fabricate entities, dates, or relations." Every asserted
relation must include a `snippet` actually from the source text. Models prone to
hallucination generate plausible but fabricated evidence, which poisons the graph
silently — worse than a parse error because it goes undetected.

Evaluated via spot-check: do evidence snippets appear verbatim (or near-verbatim)
in the source document?

### 4. Cost efficiency

At 10-20 docs/day (~4K input + ~2K output tokens per doc), all candidate models
are under $10/month. Cost is not a primary differentiator at this scale, but
matters if volume grows.

### 5. API features

- **JSON mode / structured output:** Enforces valid JSON at the API level
- **JSON Schema enforcement:** Some APIs (OpenAI `strict: true`) can enforce
  our exact schema, eliminating most compliance failures
- **Retry behavior:** Rate limits, error rates, timeout characteristics

### 6. Context window

Most cleaned articles are 1-5K tokens. Prompt overhead is ~500 tokens. A 16K+
context window is sufficient. Not a differentiator for current models.

### 7. Latency

At 10-20 docs/day, sub-15s per document is comfortable. Not a primary concern
unless a model consistently exceeds 60s per extraction.

## Candidates

### Tier 1 — Baseline reference (generate gold-standard extractions)

| Model | JSON Enforcement | Cost (per 1M in/out) | Notes |
|-------|-----------------|----------------------|-------|
| GPT-4.1 | Native `strict: true` | $2.00 / $8.00 | Top structured output benchmarks |
| Claude Sonnet 4 | Tool use with schema | ~$3.00 / $15.00 | Strong evidence grounding |
| Gemini 2.5 Pro | Native schema enforcement | $1.25 / $10.00 | Large context window |

Use one of these to produce reference extractions for validating Tier 2 outputs.

### Tier 2 — Daily pipeline candidates

| Model | JSON Enforcement | Cost (per 1M in/out) | Notes |
|-------|-----------------|----------------------|-------|
| **GPT-5 nano** | Tool calling `strict: true` | $0.10 / $0.40 | **Current default understudy.** Cheapest OpenAI option with strict schema enforcement. Cheaper input than 4.1 nano, same output price. |
| GPT-4.1 nano | Tool calling `strict: true` | $0.10 / $0.40 ($0.025 cached input) | Lowest cached-input price |
| GPT-4.1 Mini | Tool calling `strict: true` | $0.40 / $1.60 | Stronger reasoning, 4x more expensive |
| Gemini 2.5 Flash | Native schema enforcement | $0.15 / $0.60 | Cheapest viable non-OpenAI option |
| Claude Haiku 3.5 | No strict schema | $0.80 / $4.00 | 41% schema pass rate in initial shadow run (invents relation types outside enum). Not viable without fuzzy mapping. |

**Implementation note:** OpenAI models use tool calling with `strict: true` via an
`emit_extraction` tool. This enforces the exact JSON Schema at the API level —
the model literally cannot produce invalid enum values. The extraction prompt is
split into a static system message (cacheable) and per-document user message to
maximize OpenAI's automatic prompt caching (kicks in at >= 1024 tokens).

### Tier 3 — Future consideration (self-hosted)

| Model | Notes |
|-------|-------|
| Qwen3-14B | Strong few-shot relation extraction benchmarks |
| Gemma3-4B | Outperforms larger models on extraction tasks |

Relevant only if eliminating API costs becomes a goal.

### Estimated daily cost (20 docs/day)

| Model | Daily | Monthly |
|-------|-------|---------|
| GPT-5 nano | ~$0.01 | ~$0.30 |
| GPT-4.1 nano | ~$0.01 | ~$0.30 |
| Gemini 2.5 Flash | ~$0.04 | ~$1.10 |
| GPT-4.1 Mini | ~$0.10 | ~$2.90 |
| Claude Haiku 3.5 | ~$0.22 | ~$6.80 |

## Recommended Approach: Shadow Mode

Rather than a staged tier selection process, we use **shadow mode** for continuous
validation with zero production risk.

### Architecture

```
Article
   ├── Primary (Sonnet) → extractions table → graph
   │
   └── Understudy (shadow) → extraction_comparison table → analysis
```

### How It Works

1. **Sonnet runs as primary** — produces actual extractions used in the pipeline
2. **Understudy runs in parallel** — same inputs, output goes to comparison table
3. **No errors raised for understudy** — failures are silently logged as data
4. **Learn over time** — accumulate real-world comparison data

### Why Shadow Mode

| Staged Tier Selection | Shadow Mode |
|-----------------------|-------------|
| Validate upfront, then trust | Continuous real-world comparison |
| Switch models, monitor for drift | Never switch, always have data |
| Tier 2 failures affect pipeline | Understudy failures are just data |
| Complex: when to re-baseline? | Simple: always have both |

### Cost

At 20 docs/day:
- Sonnet (primary): ~$25/month
- Understudy (shadow): ~$1-7/month
- **Total**: ~$26-32/month for continuous validation

### Comparison Stats Table

The `extraction_comparison` table captures:

```sql
CREATE TABLE extraction_comparison (
    doc_id TEXT,
    run_date TEXT,
    understudy_model TEXT,

    -- Did it work at all?
    schema_valid BOOLEAN,
    parse_error TEXT,

    -- Counts vs primary
    primary_entities INTEGER,
    understudy_entities INTEGER,
    primary_relations INTEGER,
    understudy_relations INTEGER,

    -- Match rates
    entity_overlap_pct REAL,
    relation_overlap_pct REAL,

    PRIMARY KEY (doc_id, understudy_model)
);
```

### Promotion Criteria

When comparison data shows an understudy consistently achieving:
- **Schema pass rate**: >= 95%
- **Entity overlap**: >= 85%
- **Relation overlap**: >= 80%

...over 100+ documents, it can be considered for primary promotion (cost savings).

Until then, Sonnet remains primary with zero quality risk.

### Escalation Mode (Post-Shadow Alternative)

Instead of a binary "promote or don't" decision, escalation mode lets the cheap
model handle most articles while Sonnet steps in only when quality is low.

**Architecture:**

```
Article → nano (cheap, strict schema) → score quality
                                            │
                                     quality >= 0.6 → keep nano result
                                            │
                                     quality <  0.6 → Sonnet → keep Sonnet result
```

**Quality signals scored (0-1 each, weighted):**

| Signal | Weight | Target | What it catches |
|--------|--------|--------|-----------------|
| **Relation type diversity** | 25% | 6 distinct types | Cheap models emit only 2–3 types (hardest to game) |
| Connectivity (semantic rel/entity ratio) | 20% | 0.5 | Found entities but no structural connections |
| Entity density (per 1K chars) | 15% | 5.0 | Missed entities |
| Evidence coverage (asserted with evidence) | 15% | 80% | Hallucinated relations |
| Tech terms present | 15% | ≥2 | Missed domain content |
| Average confidence | 10% | 0.85 | Model was guessing; variance penalty if flat-high |

*Confidence variance penalty:* If stddev < 0.05 and avg > 0.8, confidence is
penalised 30%. Uncalibrated models output ~0.9 for everything.

See [docs/fix-details/pipeline-stall-scoring-overhaul.md](fix-details/pipeline-stall-scoring-overhaul.md)
for the full rationale behind the Feb 2026 scoring overhaul.

**Cost impact:** If 70% of articles pass nano's quality check, monthly cost drops
from ~$25 (Sonnet on everything) to ~$8 (nano on 70% + Sonnet on 30%).

**Usage:**
```bash
make extract-escalate    # Run with escalation
make shadow-report       # See escalation stats in dashboard
```

Each extraction JSON includes `_extractedBy` (which model was used),
`_qualityScore` (combined score), and `_escalationReason` (if escalated).

---

## Initial Evaluation (Before Shadow Mode)

Use the evaluation harness to confirm understudy candidates are viable before
adding them to shadow mode.

### Phase 1: JSON schema compliance (automated)

Run the evaluation harness (`tests/test_llm_eval.py`):

1. Select 5-10 representative articles (arXiv abstract, HF blog post, OpenAI announcement)
2. Run each through candidate models using `build_extraction_prompt()`
3. Measure:
   - **Schema pass rate**: % passing `validate_extraction()` without modification
   - **Parse recovery rate**: % passing after post-processing (strip fences, inject docId)
   - **Field-level error breakdown**: which fields/enums fail most often
4. Compare across candidates

### Phase 2: Classification quality (benchmark review + spot-check)

1. Review published benchmark scores for shortlisted models
2. Manually review 3-5 extractions per model for:
   - Entity type accuracy
   - Relation type accuracy
   - Kind (asserted/inferred/hypothesis) appropriateness
   - Evidence snippet fidelity (does snippet appear in source text?)

### Phase 3: Add to Shadow Mode

Models passing Phase 1-2 can be added to the understudy pool for continuous
comparison against Sonnet production extractions.

## Evaluation Harness

The harness lives at `tests/test_llm_eval.py` and sample fixtures at
`tests/fixtures/llm_eval/`. See the harness code for usage instructions.

Run with: `pytest tests/test_llm_eval.py -v`
