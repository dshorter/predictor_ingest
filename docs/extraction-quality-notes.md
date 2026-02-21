# Extraction Quality Notes

Observations from running the pipeline. These are not bugs — they're
tuning opportunities to address once we have enough real data to see
patterns clearly.

---

## 1. Entity type ambiguity: no definitions in the extraction prompt

**Observed:** 2026-02-21
**Status:** Noted; waiting for more data

The system prompt lists entity types as a bare enum:

```
Org, Person, Program, Tool, Model, Dataset, Benchmark, Paper, Repo,
Document, Tech, Topic, Event, Location, Other
```

No definitions, no examples, no disambiguation rules. The GLOSSARY.md
has good descriptions (e.g., "Model = the trained weights; Tool = the
product/interface that wraps a model") but they never make it into the
prompt. This causes inconsistent classification:

- **Model vs Tool** — "ChatGPT" classified as Model in one doc, Tool in
  another, depending on context ("ChatGPT responded…" vs "users opened
  ChatGPT…").
- **Tech vs Topic** — "machine learning" could go either way.
- **Tech vs Model** — "LLMs" classified as both `tech:llms` and
  `model:llms`.

**Likely fix:** Inject the GLOSSARY definitions and explicit disambiguation
rules into `build_extraction_system_prompt()`. For example:

> - **Model** = the trained weights (GPT-4, GPT-4o, LLaMA 3, Claude 3.5 Sonnet)
> - **Tool** = the product/interface wrapping a model (ChatGPT, Claude.ai, Copilot)
> - When ambiguous between Model and Tool, prefer **Tool** if the text
>   describes a user-facing product.

**Where to change:** `src/extract/__init__.py`, lines ~237–279
(`build_extraction_system_prompt`).

**Depends on:** Entity resolution also needs to merge the duplicates that
have already been created (e.g., consolidate `model:chatgpt` and
`tool:chatgpt` into one canonical node).

---

<!-- Add new observations below this line -->
