# Trend Insights: North Star, Ladder Architecture, and Evaluation Artifacts

## This is a research-only document  

## 1) Why we’re doing this
The goal is **unique, genuinely useful trend insights**—signals that feel *special* (early, corroborated, structurally meaningful), not generic “AI is trending” noise.

Metrics like a **0.6 extraction score** are only useful insofar as they correlate with *insight quality*. Adding many free sources is not automatically valuable if the system can’t turn them into distinct insights.

We also value **analysis artifacts** (definitions, rubrics, evaluation plans, coverage maps) even if implementation is delayed due to cost.

---

## 2) What “great trend insights” means (operational definition)
A “great” insight has most of these properties:

1. **Lead time**: flags an emerging development *before it’s obvious/mainstream*.
2. **Non-noise**: avoids plausible-looking but low-signal chatter.
3. **Corroboration**: appears across multiple independent sources and/or source categories.
4. **Structural importance**: changes graph structure (e.g., becomes a bridge/hub; links previously separate clusters).
5. **Auditability**: when making specific causal claims, includes provenance/evidence.

This separates:
- **Trend detection** (ranking entities/edges/clusters)
- **Insight articulation** (human-readable “what/why/so what” with links/evidence)

---

## 3) Desired architecture (cost-aware ladder)
Preferred ladder:

1) **Heavy deterministic/CPU** (scale + breadth)
2) **Cheap model** (fill in semantics when CPU is insufficient)
3) **Specialist model** (only when needed for uniquely high-quality insights)

However, we must be honest: if achieving unique insights requires **specialist-only**, we need to discover that early.

Key question:
- *What is the cheapest architecture that reliably produces the “great insight” criteria above?*

---

## 4) How to reason about deterministic value
Deterministic extraction can often deliver strong:
- **Entity detection + normalization**
- **Mention and corroboration statistics**
- **Velocity/novelty** signals
- **Co-mention structure** (as a proxy for clusters)

Deterministic extraction struggles with:
- nuanced semantic relations (directionality, implicit causality)
- disambiguation and entity linking across aliasing
- “bridge” insights that depend on non-trivial typed edges

Therefore the ladder should be tested empirically, not assumed.

---

## 5) Insight taxonomy (what we want to output)
These are types of insights the system should aim to produce:

### A) Emerging entity signals
- **Novel entrant**: new model/tool/org appears and quickly gains mentions.
- **Resurgence**: older entity re-accelerates after dormancy.

### B) Corroborated acceleration
- **Cross-source acceleration**: entity rises across multiple independent sources.
- **Category spread**: entity moves from one source category to another (e.g., papers → production docs).

### C) Structural/graph signals
- **Bridge emergence**: entity increasingly connects clusters that were previously separate.
- **Cluster formation**: multiple entities co-appear as a new cohesive topic cluster.

### D) Adoption/implementation signals
- **Integration wave**: repeated “integrates with / supports / depends on” edges.
- **Open-source traction**: release cadence and adoption proxies spike.

### E) Governance/policy catalysts
- **Policy trigger**: regulatory/standards mentions correlate with downstream adoption or discourse changes.

---

## 6) Insight template (the artifact we publish)
Each published insight should be rendered as:

- **Title**: concise, specific
- **What changed (1–2 sentences)**: the trend statement
- **Time window**: e.g., last 7 days vs prior 21
- **Primary subject**: entity / cluster
- **Signals**:
  - Velocity score
  - Novelty score
  - Corroboration score (distinct sources)
  - Structural score (bridge/cluster)
- **Evidence**:
  - Top 3–8 supporting documents (diverse sources)
  - For asserted semantic claims: include quoted snippets or spans
- **So what**:
  - why it matters; likely downstream areas affected
- **Confidence**:
  - low/med/high + rationale (corroboration + evidence)

---

## 7) Evaluation plan (decide if specialist-only is needed)
Run a backtest on the same historical corpus using **four modes**:

1) **CPU-only**
2) **CPU → cheap model** (only when CPU “interestingness” trigger fires)
3) **CPU → cheap → specialist escalation** (ideal ladder)
4) **Specialist-only baseline**

### Evaluate at the insight level (not extraction score)
For each mode, measure:
- **Precision@K** (top 10/20 insights per week)
- **Lead time** (days earlier than mainstream recognition)
- **False positives** (flash-in-pan chatter)
- **Diversity** (insights span subdomains; not all LLM/news)
- **Auditability** (asserted claims backed by evidence)

### Human adjudication rubric
Each insight scored 0–3 on:
- Uniqueness
- Usefulness
- Evidence quality
- Early-ness
- Actionability

Outcome we care about:
- If CPU/cheap modes match specialist on precision + lead time, specialist-only is unnecessary.
- If specialist-only uniquely produces high-quality structural/bridge insights, we accept specialist-heavy costs for that tier of insights.

---

## 8) Source-type flexibility strategy (keep complexity additive)
Avoid a domain×source-type explosion by using **layered config**:

- Base defaults
- Domain profile overrides
- Source-type profile overrides (news, papers, releases, social, etc.)
- Feed-specific overrides

This keeps code complexity mostly additive; the multiplication risk is mainly in tuning and QA, which can be managed with per-source-type dashboards and sampling.

---

## 9) Immediate “analysis artifacts” to produce (even if we delay implementation)
1) Finalized insight taxonomy + templates
2) Evaluation rubric + backtest protocol
3) Source coverage map (what each source category contributes)
4) Deterministic sufficiency checklist (what CPU must reliably output)
5) Decision thresholds: when to escalate, and what insight types require specialist

