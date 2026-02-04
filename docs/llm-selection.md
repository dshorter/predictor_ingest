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
| GPT-4.1 Mini | Native `strict: true` | $0.40 / $1.60 | Best cost/quality for structured output |
| Gemini 2.5 Flash | Native schema enforcement | $0.15 / $0.60 | Cheapest viable option |
| Claude Haiku 3.5 | Tool use with schema | $0.80 / $4.00 | Anthropic's fast tier |

### Tier 3 — Future consideration (self-hosted)

| Model | Notes |
|-------|-------|
| Qwen3-14B | Strong few-shot relation extraction benchmarks |
| Gemma3-4B | Outperforms larger models on extraction tasks |

Relevant only if eliminating API costs becomes a goal.

### Estimated daily cost (20 docs/day)

| Model | Daily | Monthly |
|-------|-------|---------|
| Gemini 2.5 Flash | ~$0.04 | ~$1.10 |
| GPT-4.1 Mini | ~$0.10 | ~$2.90 |
| Claude Haiku 3.5 | ~$0.22 | ~$6.80 |

## Evaluation Plan

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

### Phase 3: Selection

Pick the model with:
- >= 90% schema pass rate (after post-processing)
- Acceptable benchmark scores for NER/RE tasks
- Reasonable cost

If two models tie on compliance, prefer the one with better inference benchmarks.
If compliance is comparable and inference is comparable, prefer lower cost.

## Evaluation Harness

The harness lives at `tests/test_llm_eval.py` and sample fixtures at
`tests/fixtures/llm_eval/`. See the harness code for usage instructions.

Run with: `pytest tests/test_llm_eval.py -v`
