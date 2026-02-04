# Multi-Domain Futures

Post-V2 vision for applying the prediction framework beyond AI/ML.

---

## Transferability Assessment

Roughly 70-80% of the current system is domain-independent. Here is the
breakdown by component:

### Transfers directly (no changes)

- **Velocity / novelty / bridge scoring** — operates on mention counts and
  graph topology, not domain semantics
- **Composite trend ranking** — weighted combination of domain-agnostic signals
- **Corroboration weighting** — source diversity math
- **Retrospective validation protocol** — precision/recall/lead-time framework
- **Weight tuning protocol** — A/B testing procedure
- **Bias catalog** — source selection, extraction, volume, recency, publication,
  survivorship biases exist in every discourse domain
- **Entity resolution** — fuzzy name matching is domain-agnostic
- **Evidence model** — provenance (doc, snippet, URL) is universal
- **Graph export** — Cytoscape.js format is structural, not semantic
- **Pipeline orchestration** — ingest → clean → extract → resolve → export
- **Archive-first principle** — store raw, re-extract later
- **Asserted/inferred/hypothesis separation** — epistemic status applies everywhere

### Requires domain-specific swap

- **Entity type enum** — `Model`, `Dataset`, `Benchmark` are AI-specific
- **Relation taxonomy** — `TRAINED_ON`, `EVALUATED_ON` are AI-specific
- **Source list** — arXiv CS.AI, HF, OpenAI are AI sources
- **Extraction prompts** — tuned for AI terminology and entity recognition
- **Canonical ID prefixes** — `model:`, `dataset:` etc.
- **Ground truth sources** — Papers With Code, GitHub stars are AI-specific
- **Validation target calibration** — precision/recall baselines may differ by domain

---

## Candidate Domains

### Biotech / Pharma

```
Entity types:     Drug, Target, Pathway, Trial, Company, Researcher,
                  Disease, Biomarker, Technique, Regulatory_Body
Key relations:    TREATS, TARGETS, INHIBITS, PHASE_ADVANCED, APPROVED_BY,
                  FAILED_IN, PARTNERED_ON, FUNDED_BY
Sources:          PubMed RSS, FDA announcements, ClinicalTrials.gov,
                  BioCentury, STAT News, bioRxiv
Ground truth:     FDA approval timeline, Phase transition dates,
                  stock price movements post-announcement
Unique value:     Drug pipeline tracking; early detection of pivots
                  (indication changes, combination therapies)
```

### Cybersecurity

```
Entity types:     Vulnerability, Threat_Actor, Malware, Tool, Technique,
                  Vendor, Product, CVE, Campaign
Key relations:    EXPLOITS, PATCHES, ATTRIBUTED_TO, USES_TECHNIQUE,
                  TARGETS_SECTOR, MITIGATES, DISCLOSED_BY
Sources:          NVD RSS, CISA alerts, vendor security blogs,
                  threat intel feeds (MITRE ATT&CK updates), Krebs on Security
Ground truth:     CVE exploitation-in-the-wild dates, CISA KEV additions,
                  major breach timelines
Unique value:     Early warning on emerging attack patterns; tracking
                  which vulnerabilities are trending toward exploitation
```

### Climate / Energy

```
Entity types:     Technology, Company, Policy, Standard, Material,
                  Funding_Round, Project, Region, Emission_Source
Key relations:    FUNDED_BY, DEPLOYS, REGULATES, COMPETES_WITH,
                  DEPENDS_ON_MATERIAL, REDUCES_EMISSIONS, MANDATES
Sources:          DOE announcements, IRENA reports, Carbon Brief,
                  Canary Media, utility commission filings
Ground truth:     Deployment statistics, cost curves (LCOE),
                  policy enactment dates, investment totals
Unique value:     Tracking which clean energy technologies are
                  crossing from pilot to deployment phase
```

### Geopolitics / Policy

```
Entity types:     State, Leader, Organization, Treaty, Sanction,
                  Conflict, Election, Alliance, Policy
Key relations:    SANCTIONS, ALLIES_WITH, OPPOSES, NEGOTIATES,
                  DEPLOYS_TO, WITHDRAWS_FROM, MEDIATES
Sources:          Reuters World, AP, Foreign Affairs, SIPRI,
                  UN press releases, government gazette feeds
Ground truth:     Treaty signings, conflict escalation/de-escalation
                  events, election outcomes, sanction implementations
Unique value:     Detecting alliance shifts and policy momentum
                  before formal announcements
```

---

## Cross-Domain Opportunities

Once multiple domains run on the same framework:

### Shared entity bridging

Some entities span domains. A company like Google appears in AI (DeepMind
models), cybersecurity (Project Zero), climate (carbon neutrality pledges),
and geopolitics (antitrust regulation). Cross-domain bridge scores could
surface entities that are gaining structural importance across fields.

### Methodology benchmarking

Running the same scoring math across domains creates natural comparisons:
- Which domains have higher signal-to-noise?
- Which domains require more sources for reliable corroboration?
- Do optimal weights differ by domain, or is 0.40/0.30/0.30 universal?

### Transfer signals

A breakthrough in one domain often presages activity in adjacent ones:
- New AI technique → biotech adopts it for drug discovery (lag: months)
- New vulnerability class → policy response (lag: weeks to months)
- New material science result → energy deployment shifts (lag: years)

Detecting these cross-domain transfer patterns requires multi-domain
operation but uses the same velocity/novelty primitives.

---

## Prerequisites Before Multi-Domain

1. **Domain separation must be clean** — see `docs/architecture/domain-separation.md`
2. **Domain profile format must be defined** — YAML schema for entity types,
   relations, sources, ground truth
3. **Schema must be parameterized** — `extraction.json` currently hardcodes
   the AI entity type enum; needs to accept a domain profile
4. **Extraction prompts must be templated** — domain vocabulary injected,
   not embedded
5. **Validation must work for one domain first** — no point scaling what
   hasn't been proven

---

## Non-Goals

- We are not building a general-purpose knowledge graph platform
- We are not competing with domain-specific intelligence tools (Palantir,
  Recorded Future, etc.)
- Multi-domain is a natural extension of the architecture, not a pivot
- Each domain instance should be independently useful; cross-domain
  features are a bonus, not a requirement
