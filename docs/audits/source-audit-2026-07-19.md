---
read: full
status: audit complete 2026-07-19; recommendations pending operator sign-off — feed changes apply at the epoch-2 restart (§2.7: source changes only at window boundaries)
---

# Source-List Audit — film & semiconductors (2026-07-19)

Three-way reconciliation, run as Sprint-20 prep before the epoch-2 restart
(the one cheap moment to change source lists, per methodology §2.7):

1. **Incumbent** — `domains/{film,semiconductors}/feeds.yaml` as configured
2. **Blind inference** — a fresh source list proposed by a subagent given only
   the domain specs + §2.5/2.6 criteria, barred from the repo
   ([blind-source-inference-2026-07-19.md](blind-source-inference-2026-07-19.md))
3. **Measured reality** — per-source docs/extraction/freshness from the domain
   DBs (documents table, all history)

Interpretation rule: sources stable across both independent inferences are
robust picks; sources that flip between them are inference noise — decided by
the measurements, not by either model's opinion.

---

## Film

**Incumbent:** 27 configured, 20 ever delivered.
**Blind:** 30 proposed (14 verified live during the exercise).
**Overlap (robust core, ~11):** IndieWire, Deadline, Filmmaker Magazine,
No Film School, John August, Go Into The Story, Film Independent, Sundance
Institute, Georgia Entertainment, r/Filmmakers, a Bluesky film slot.

### Where measurement settles inference disagreements

| Source | Incumbent | Blind | Measured | Verdict |
|---|---|---|---|---|
| Variety, THR | in | **excluded** (PMC overlap w/ Deadline; independence rule) | 277 + 295 docs, but same-story overlap w/ Deadline plausible | **Drop or keyword-scope**: three PMC-adjacent wires is volume, not coverage |
| Hope For Film (Ted Hope) | in | excluded ("rumor-grade") | 78 docs, 17 extracted, q 0.76 | **Keep** — delivers steadily |
| Project Casting | in | not proposed | 66 docs, 29 extracted, **q 0.88 (best in domain)** | **Keep** — measurement trumps both inferences |
| Script Magazine | in | not proposed | 65 docs, 21 extracted, q 0.84 | **Keep** |
| Charleston City Paper | in | not proposed | 245 docs but **q 0.59 (worst)** | **Cut or filter hard** — volume w/o quality |
| Go Into The Story | in ("known dead" per ADR-010) | **proposed, verified live** | 80 docs through 07-01, **0 extracted** | ADR's "dead" claim is wrong; real problem is selection/extraction yield. **Keep, investigate yield** |
| ArtsATL | in | not proposed | 18 docs, 0 extracted, **date bug (doc stamped 2029)** | **Fix date parse or cut** |
| Sundance Institute | in | proposed (feed unconfirmed) | stalled 2026-03-17 | **Fix feed or accept coverage via trades** |

### Never delivered (incumbent) — all honestly disabled with dated reasons
ScreenAnarchy (404), Nashville Scene (429), Atlanta Film and TV, SC Film
Commission, r/Atlanta + r/Filmmakers + r/indiefilm (pending Reddit creds).
The Reddit credential gap kills the whole chatter category — blind list
assumes it works; it has never worked in this domain.

### Blind-only additions worth adopting (priority order)
1. **SaportaReport** (verified; keyword-filter) — civic/real-estate side of
   the Atlanta studio build-out; nothing in the incumbent covers it
2. **GPB film coverage** — the *politics* of the GA incentive; deliberate
   bias-check on Georgia Entertainment's boosterism
3. **MovieMaker** (verified) — regional/sub-A24 festival tier
4. **Hammer to Nail** (verified) — micro-budget tier, pure anti-consensus
5. **The Film Stage** (verified) — festival/specialty-distribution, PMC-independent
6. **Stephen Follows** (verified) — original quantitative analysis, high novelty
7. **CineD** (verified) — EU production-tech counterweight
8. **The Ankler** — industry-economics analysis (paywalled previews)
9. Screen Daily / Cineuropa — sales & markets coverage is the acknowledged
   gap in BOTH lists; Screen Daily's feed returns an empty skeleton, so
   Cineuropa (403-to-bots; test from pipeline) is the practical pick
10. Institutional/scrape targets (SAGindie, GA.org film office, guild
    newsrooms) — bank as future work; scraper cost, bursty value

### Operational findings (film)
- **Tollbit gating**: IndieWire/Deadline 402 non-browser UAs as of this
  audit. The pipeline's Deadline ingest worked through 07-01 (when film
  ingest stopped) — verify the UA still passes before the restart, or the
  two highest-volume feeds die silently at relaunch.
- Film ingest itself has been stalled since ~07-01 (18 days) — same class
  of silent stall as semis' 06-23 (Sprint 20.2/20.3 scope).

---

## Semiconductors

**Incumbent:** 30 configured, **8 ever delivered.** The differentiated tier-1
primary layer (5× per-company EDGAR, 3× IR feeds, earnings transcripts) is
`enabled: false`, and `ir_rss`/`earnings` fetcher types were never
implemented — designed, never built. Worse class: USPTO patents + both
Reddits are **enabled and silently delivering zero**.
**Blind:** 29 proposed (12 verified live).
**Overlap (robust core):** SemiEngineering, SemiWiki, Chips and Cheese,
SemiAnalysis, The Chip Letter, EE Times, The Register, a Bluesky slot.

### Where measurement settles inference disagreements

| Source | Incumbent | Blind | Measured | Verdict |
|---|---|---|---|---|
| Tom's Hardware | in (#2 by volume) | **excluded** ("30/day consumer noise for 3/day relevance") | 174 docs, 171 extracted (98% yield) | **Keep but add keyword filter** — it's the volume backbone, and extraction yield says docs are usable; blind's noise concern argues filtering, not removal |
| Real World Tech | in | excluded (dormant for years) | 0 docs ever | **Cut** — both agree once data speaks |
| SemiAnalysis | in | in, but **flagged: feed lags site ~10 months, heavy paywall** | 29 docs, last 06-23 | **Keep, verify feed freshness** at restart |
| EE Times | in (disabled 04-15, unreachable) | proposed | 0 docs | **Retry once from pipeline UA**, then decide |

### The two structural gaps (both lists agree by omission/commission)
1. **Policy/geopolitics: the incumbent has ZERO live policy sources** in a
   domain whose stated central tension includes export controls, and whose
   ontology has a Policy entity type. Blind fills it with a cluster:
   **Federal Register search-RSS** (primary regulatory text; the single
   highest-value add of this audit), ChinaTalk, CSIS, Interconnected (the
   deliberate non-DC counterweight). Adopt at least FR + ChinaTalk.
2. **Analyst/data: nothing incumbent.** TrendForce (verified RSS index)
   brings HBM/memory pricing + CoWoS capacity from Taiwan. Adopt.

### Blind-only additions worth adopting (priority order)
1. **Federal Register "semiconductor" search-RSS** — primary source for BIS
   rules/CHIPS notices (403'd the audit's fetcher; test from pipeline)
2. **TrendForce** (verified) — analyst/data category currently empty
3. **More Than Moore** (verified) — process-conference reporting (IEDM/VLSI)
4. **ChinaTalk** (verified) — export-control policy debate venue
5. **The Next Platform** (verified) — accelerator/datacenter economics leg
6. **IEEE Spectrum semiconductors topic feed** (verified) — research bridge
7. **Fabricated Knowledge** (verified) — equipment/memory cycle analysis
8. **ServeTheHome** (verified) — hands-on accelerator/server coverage
9. **NVIDIA Blog** (verified; filter marketing) — first-party from the
   dominant AI-compute vendor
10. **Bits & Chips / Semiconductor Digest** — EU-litho + manufacturing-ops
    coverage (feeds unconfirmed; verify first)

### Cuts / fixes (semis)
- Cut: Real World Tech (dormant), and per blind verification do NOT adopt
  AnandTech (dead 2024-08), WikiChip Fuse (server down), Asianometry
  (stale since 2025-01)
- Fix or explicitly disable the silent-zero feeds: USPTO patents (fetcher
  exists, enabled, zero docs — diagnose), r/semiconductors + r/chipdesign
  (unauth fallback demonstrably not working)
- Decide the disabled tier-1 layer: the `edgar` fetcher WORKS (generic
  feed delivered 26 docs) → enabling the 5 per-company EDGAR feeds is
  config-only. `ir_rss`/`earnings` need fetchers written — defer or drop
  the config stubs so the list stops overstating itself

---

## Cross-cutting recommendations

1. **Apply all changes at the restart, in one batch** (§2.7) and log every
   add/drop/substitution in a source change log per §2.8 (the
   `config/source_changelog.yaml` the methodology promised never existed —
   create it as part of this batch).
2. **Reddit is a decision, not a default**: two domains carry Reddit feeds
   that have never delivered (missing creds in film; broken unauth fallback
   in semis). Either provision credentials once, properly, or drop the
   feeds everywhere and stop pretending chatter coverage exists.
3. **Zero-items-for-N-days alert** in the ingester (blind finding: feeds
   can be valid-but-empty, e.g. Screen Daily). Complements 20.4's
   staleness paging — same disease, feed-level instead of domain-level.
4. **Verify bot-gated feeds from the pipeline's own UA** before the
   restart: Tollbit-gated PMC trades (film), SemiEngineering/SIA/Federal
   Register/Cineuropa/theASC (403'd the audit fetcher, healthy sites).
5. **Coverage profiles (§2.6)**: neither domain has them. The blind
   deliverable's per-source entries are ~80% of a coverage profile —
   harvest them when building the final feeds.yaml.
