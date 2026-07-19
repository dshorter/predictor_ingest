# Blind Source-Selection Exercise — Proposed Feed Lists

Prepared 2026-07-19, from brief + web research only. No incumbent list consulted; no files under /opt read.

Verification legend: **[V]** = feed fetched and returned valid RSS/Atom with recent entries during this exercise. **[V-blocked]** = feed exists but our fetcher was bot-blocked (403/402/redirect-to-gate); expect it to work in a real feed reader UA, but test from the pipeline. **[U]** = unverified. Volume estimates are docs/day unless noted.

Operational note discovered during verification: **PMC-owned trades (IndieWire, Deadline, and presumably Variety) now redirect non-browser clients to a Tollbit gate (HTTP 402)**. Their feeds exist but the pipeline's fetcher UA matters. Budget time for this or expect silent feed death.

---

# DOMAIN 1 — Film & Independent Cinema (target ~35 docs/day)

## Proposed sources

### Trade press / journalism

1. **IndieWire** — https://www.indiewire.com/feed/ **[V-blocked — Tollbit 402]**
   - Category: trade press. Entities: Person, Studio, Production, Festival, Distributor, Award, Topic.
   - Volume: 15–25/day raw — **cap or use section feeds** (e.g. /c/film/festivals/feed) or it dominates the corpus.
   - Rationale: the center of gravity for indie/festival/distribution reporting; best acquisition-deal coverage.

2. **Deadline** — https://deadline.com/feed/ **[V-blocked — Tollbit 402]**
   - Category: trade press. Entities: Person, Studio, Production, Agency, Distributor, Org (guilds), Event (strikes).
   - Volume: 40+/day raw — **must be capped/filtered** (keyword filter: indie, festival, acquisition, Georgia/Atlanta).
   - Rationale: fastest wire for deals, casting, guild/labor news; project-level dev→production announcements the pipeline needs for entity continuity.

3. **The Ankler** — https://theankler.com/feed **[V]** (entries truncated; paywalled beyond preview)
   - Category: trade analysis/newsletter. Entities: Studio, Distributor, Person, Topic (business models).
   - Volume: ~1–2/day. Rationale: contrarian industry-economics analysis; catches structural change (streamer retrenchment, indie financing shifts) before the wires frame it. **Flag: paywalled** — previews only, still signal-bearing.

4. **Filmmaker Magazine** — https://www.filmmakermagazine.com/feed **[V]** (entries July 2026)
   - Category: trade/craft hybrid (IFP/Gotham-adjacent). Entities: Person (directors/producers), Production, Festival, Fund (labs), Topic.
   - Volume: ~1–2/day. Rationale: the canonical indie-production magazine; "25 New Faces" and lab coverage = early-stage entity discovery.

5. **MovieMaker Magazine** — https://www.moviemaker.com/feed/ **[V]** (entries July 2026)
   - Category: trade press (lower prestige). Entities: Person, Festival ("50 Festivals Worth the Entry Fee"), Production, Location (best places to live/work as a moviemaker — regional production).
   - Volume: ~2–3/day. Rationale: covers the sub-A24 tier of indie filmmaking and regional/festival ecosystems the prestige trades ignore.

6. **The Film Stage** — https://thefilmstage.com/feed/ **[V]** (entries July 2026)
   - Category: journalism (festival/distribution). Entities: Production, Festival, Distributor, Person.
   - Volume: ~4–6/day. Rationale: reliable festival-lineup and specialty-distribution (Criterion, restoration, arthouse release) coverage; independent of PMC.

7. **Screen Daily (Screen International)** — https://www.screendaily.com/ ; feed https://www.screendaily.com/25.rss **[flagged: feed fetched but returned an EMPTY skeleton — no items; site is registration/paywalled]**
   - Category: trade press (international). Entities: Festival, Production, Distributor, Event (markets: EFM, Cannes Marché, AFM).
   - Volume: would be ~5–10/day if working. Rationale: only strong English source for sales/markets. **Marginal as-is** — include only if the feed populates from pipeline; otherwise Cineuropa (below) partially covers.

### Practitioner / craft blogs

8. **No Film School** — https://nofilmschool.com/rss.xml **[V]** (entries July 2026)
   - Category: practitioner. Entities: Tech (cameras, AI tools), Person, Topic (craft), Genre.
   - Volume: ~4–6/day. Rationale: the largest practitioner community publication; gear/AI-tool adoption signals originate here before trades notice.

9. **John August** — https://johnaugust.com/feed **[V]** (entries July 2026)
   - Category: practitioner (screenwriting). Entities: Person, Org (WGA), Topic, Tech (Highland).
   - Volume: ~2–3/week. Rationale: working A-list screenwriter; Scriptnotes transcripts carry WGA/business ground truth from inside the guild.

10. **Go Into The Story (The Black List blog)** — https://gointothestory.blcklst.com/feed **[V]** (entries July 2026)
    - Category: practitioner (screenwriting). Entities: Person (emerging writers), Topic, Fund (fellowships/labs).
    - Volume: ~1–2/day. Rationale: Black List adjacency = spec market and emerging-writer discovery.

11. **CineD** — https://www.cined.com/feed/ **[V]** (entries July 2026)
    - Category: practitioner/tech. Entities: Tech (cameras, lights, gimbals, LED volume adjacent), Topic.
    - Volume: ~3–4/day. Rationale: camera/production-tech announcements with hands-on depth; independent (EU-based) counterweight to US gear blogs.

12. **Dear Producer (Rebecca Green)** — https://dearproducer.com/feed/ **[V]** (entries monthly)
    - Category: practitioner (producing). Entities: Person (producers), Fund, Topic (producer economics).
    - Volume: ~1–2/month — **low; acceptable as a depth source, don't expect daily docs.**
    - Rationale: the honest indie-producer-economics voice; sustainability-of-producing debates start here.

13. **Stephen Follows — Film Data and Education** — https://stephenfollows.com/feed/ **[V]** (entries July 2026)
    - Category: specialist analysis. Entities: Topic, Genre, Festival (statistical), Distributor.
    - Volume: ~2–3/week. Rationale: quantitative film-industry analysis; novelty-signal gold (his findings are original data, never syndicated).

14. **American Cinematographer (ASC)** — https://theasc.com/ ; feed https://theasc.com/feed **[U — 403 to our fetcher]**
    - Category: craft (cinematography). Entities: Person (DPs), Tech (cameras, LED volume), Production.
    - Volume: ~2–4/week. Rationale: authoritative on virtual production/LED volume adoption. Marginal if feed stays blocked.

### Primary sources / institutional

15. **Film Independent** — https://www.filmindependent.org/feed/ **[V]** (entries July 2026)
    - Category: primary/institutional. Entities: Fund (labs, grants), Person (fellows), Award (Spirit Awards), Festival.
    - Volume: ~2–4/month. Rationale: lab cohorts and Spirit Award pipelines = earliest structured entity introductions.

16. **Sundance Institute — news** — https://www.sundance.org/blogs/ **[U — feed not confirmed]**
    - Category: primary/institutional. Entities: Festival, Fund (labs), Person.
    - Volume: ~2–4/month. Rationale: lab/grant announcements are development-stage primary data. If no feed, scrape or drop; festival lineups will arrive via IndieWire/Film Stage anyway (redundancy exists).

17. **SAGindie** — https://www.sagindie.org/ (blog: /blog/, WordPress — feed likely /feed/) **[U]**
    - Category: primary/institutional (SAG-AFTRA's indie arm). Entities: Org, Fund (state incentives — they maintain per-state production-incentive pages), Location, Production.
    - Volume: ~2–4/month. Rationale: guild-side view of low-budget production and the only maintained cross-state incentive reference tied to a guild.

18. **Georgia Department of Economic Development — Film office news** — https://www.georgia.org/press-releases **[U — no confirmed feed; may need scraping]**
    - Category: primary source. Entities: Fund (GA tax incentive), Location, Production, Policy-adjacent Events.
    - Volume: ~1–3/month relevant. Rationale: incentive-program changes are the single highest-leverage variable for the Southeast lens; must come from the primary source, not secondhand.

19. **WGA / SAG-AFTRA / DGA newsrooms** — https://www.wga.org/news-events/news , https://www.sagaftra.org/news , https://www.dga.org/News **[U — none appear to offer RSS; scrape targets, not feeds]**
    - Category: primary source. Entities: Org, Event (strikes, negotiations), Topic (AI provisions).
    - Volume: bursty (near-zero to 5/day in negotiation season). Rationale: labor events are the biggest structural-change signals in this domain; do not rely on trade paraphrase alone. **Honest flag: these are scraper work, not RSS — cost/benefit is only justified for WGA + SAG-AFTRA; DGA optional.**

### Southeast US lens (strategic focus)

20. **Georgia Entertainment** — https://www.georgiaentertainment.com/feed/ **[V]** (entries July 2026: Tyler Perry Studios virtual production, Savannah, Daytime Emmys)
    - Category: regional trade. Entities: Studio (Tyler Perry, Trilith, Assembly), Production, Location (ATL/Savannah), Fund (incentives), Tech (stages).
    - Volume: ~1–2/day. Rationale: the working daily news source for the Georgia production economy; exactly the low-prestige regional trade a model-default list omits.

21. **Oz Magazine** — https://ozmagazine.com/ **[flagged: NO working RSS feed found — /feed/ returns a tracking pixel]**
    - Category: regional trade (Atlanta crew/vendor B2B, bi-monthly print). Entities: Person (crew), Studio, Location.
    - Rationale: deep Atlanta crew-base coverage. **Recommend: monitor via scrape or skip; without a feed it's marginal for this pipeline.**

22. **SaportaReport** — https://saportareport.com/feed/ **[V]** (top item on fetch day was an Atlanta film-festival story)
    - Category: regional journalism (Atlanta civic/business). Entities: Location, Studio (real-estate/stage deals), Org, Festival (local).
    - Volume: ~4–6/day total, **~10–20% film-relevant — apply keyword filter** (film, studio, soundstage, production, festival).
    - Rationale: catches the civic/real-estate side of Atlanta's studio build-out (Invest Atlanta bonds, rezonings) that entertainment trades never cover.

23. **GPB News — film industry coverage** — https://www.gpb.org/news/articles/film-industry **[U — site has film-industry tag; feed URL unconfirmed]**
    - Category: regional journalism (public broadcaster). Entities: Location, Fund (incentive politics in the GA legislature), Production, Org.
    - Volume: ~2–4/week relevant. Rationale: covers the *politics* of the GA film incentive (annual legislative fights) with original reporting; independent of the boosterish regional trades — a deliberate bias check on #20.

24. **Atlanta Film Festival / Film Impact Georgia** — https://www.atlantafilmfestival.com/ , https://www.filmimpactgeorgia.org/ **[U — Squarespace sites; try `?format=rss` on blog paths]**
    - Category: primary/institutional (regional). Entities: Festival, Person (SE filmmakers), Fund (FIG grants).
    - Volume: low (~2–5/month combined). Rationale: entity discovery for Southeast filmmakers before they surface nationally. Marginal individually; worth it combined for the strategic lens.

### Community / chatter (pipeline's Bluesky/Reddit slots)

25. **Reddit r/Filmmakers** — https://www.reddit.com/r/Filmmakers/.rss **[U — reddit blocks our verification fetcher, but /.rss endpoints are standard and work with a proper UA]**
    - Entities: Tech, Topic (working conditions, rates), Location (where's the work). Volume: sample top ~5/day.
    - Rationale: ground truth on what working crew actually experience (e.g. "Atlanta is dead/busy" signals precede trade coverage).

26. **Reddit r/Screenwriting** — https://www.reddit.com/r/Screenwriting/.rss **[U — same caveat]**
    - Entities: Topic (spec market, contests, AI anxiety), Fund (fellowships). Volume: sample top ~3/day.

27. **Bluesky — curated film-industry list/feed** (e.g. a hand-built list of ~50 indie producers, festival programmers, distribution people; much of "Film Twitter" migrated here)
    - Entities: Person, Festival, Topic. Volume: sample ~5/day. Rationale: festival programmers and indie distributors are unusually candid on Bluesky; earliest rumor tier.

### Specialist newsletters

28. **Sub-Genre (Brian Newman)** — https://sub-genre.com/newsletter **[flagged: NO RSS — email-only, archives on site; biweekly]**
    - Category: specialist newsletter (brand-funded film, distribution innovation). Entities: Distributor, Topic, Fund.
    - Rationale: the sharpest thinker on post-theatrical indie distribution. **Ingest via email-to-feed bridge (e.g. Kill the Newsletter) or scrape archive page; otherwise skip — noted honestly as extra plumbing.**

29. **Hammer to Nail** — https://www.hammertonail.com/feed/ **[V]** (entries July 2026)
    - Category: specialist (micro-budget/truly-indie reviews + festival reports). Entities: Person, Production, Festival (regional/genre fests).
    - Volume: ~3–4/week. Rationale: covers the no-distribution tier of American indie film that even IndieWire skips; pure anti-consensus coverage.

30. **Cineuropa** — https://cineuropa.org/en/ (RSS index at /en/rss/) **[U — 403 to our fetcher; RSS known to exist]**
    - Category: trade (European). Entities: Festival (EU fests), Fund (co-production, MEDIA), Distributor, Production.
    - Volume: ~8–10/day raw — filter to news category. Rationale: co-production and European festival/market coverage; the partial Screen Daily substitute given #7's feed problems.

### Considered and excluded (so the list isn't padded)
- **Variety / THR**: heavy overlap with Deadline+IndieWire (independence principle — PMC syndication overlap with Deadline is real); Tollbit-gated; adds volume, not coverage.
- **World of Reel, Ted Hope's newsletter**: genuinely interesting but rumor-grade / intermittent; revisit if festival-rumor recall proves weak.
- **ProductionHUB, Backstage**: listing/services sites, low signal density for trend extraction.

## Category balance — Domain 1

| Category | Sources | Est. docs/day (post-filter/cap) |
|---|---|---|
| Trade press/journalism | IndieWire, Deadline (capped), Ankler, Filmmaker, MovieMaker, Film Stage, (Screen Daily) | ~14–16 |
| Practitioner/craft | No Film School, John August, GITS, CineD, Dear Producer, ASC | ~7–9 |
| Primary/institutional | Film Independent, Sundance, SAGindie, GA film office, guild newsrooms | ~1–2 (bursty) |
| Southeast regional | Georgia Entertainment, SaportaReport (filtered), GPB, ATLFF/FIG, (Oz) | ~3–4 |
| Community/chatter | r/Filmmakers, r/Screenwriting, Bluesky list | ~10–13 sampled |
| Specialist newsletters/analysis | Stephen Follows, Hammer to Nail, Sub-Genre, Cineuropa | ~2–3 |
| **Total** | | **~35–42 → tune caps to ~35** |

Topic redundancy check: festivals (IndieWire, Film Stage, Hammer to Nail, Cineuropa ✓); distribution (IndieWire, Ankler, Sub-Genre, Stephen Follows ✓); screenwriting (August, GITS, r/Screenwriting ✓); production tech (No Film School, CineD, ASC ✓); GA incentive (GA.org, GPB, Georgia Entertainment ✓); labor/guilds (Deadline, guild newsrooms, John August ✓). No single-source topics; weakest pair is sales/markets (Screen Daily broken + Cineuropa unverified) — flagged.

## Deliberately anti-consensus picks — Domain 1
- **Georgia Entertainment, Oz, SaportaReport, GPB, ATLFF/FIG** — a five-source regional stack. Default model lists give you zero Southeast sources; the strategic lens demands the boosterish trade (GE), the skeptical public broadcaster (GPB), and the civic-money angle (Saporta) as mutually correcting.
- **MovieMaker over Variety** — deliberately trading a prestige trade for the outlet that covers regional festivals and working-class filmmaking.
- **Hammer to Nail** — micro-budget cinema is where genre/aesthetic trends incubate; no prestige list includes it.
- **Dear Producer, Sub-Genre** — practitioner economics from producers/distribution consultants rather than journalists; low volume, high novelty.
- **Reddit crew chatter** — labor-market ground truth vs. press-release reality.

---

# DOMAIN 2 — Semiconductors & Chips (target ~20–25 docs/day)

## Proposed sources

### Trade press / journalism

1. **Semiconductor Engineering** — https://semiengineering.com/feed/ **[V-blocked — 403 to our fetcher; feed is real and active]**
   - Category: trade (deep technical). Entities: ProcessNode, Packaging, Tool (EDA), Material/equipment, Fab, Org (standards).
   - Volume: ~5–8/day. Rationale: the only trade that covers process/packaging/EDA/test at engineering depth daily; closest thing to a backbone source for the fab→architecture end.

2. **EE Times** — https://www.eetimes.com/feed/ **[U — fetch timed out; feed presumed live]**
   - Category: trade. Entities: Company, Chip, Material/equipment, Policy (some).
   - Volume: ~4–6/day. Rationale: broad electronics-industry reporting with original interviews; overlaps SemiEngineering but with more business angle.

3. **The Register** — https://www.theregister.com/headlines.atom **[V — redirects to their API feed remapper; canonical]**
   - Category: journalism. Entities: Company, Chip, Policy, Topic.
   - Volume: full feed ~25/day — **keyword-filter to chip/semiconductor/GPU/TSMC/Intel/etc., yielding ~3–4/day.** (Section-level feed /hardware/headlines.atom returned 404 — use the filtered full feed.)
   - Rationale: irreverent, genuinely independent reporting on chip business + export-control enforcement stories; not a press-release repeater.

4. **The Next Platform** — https://www.nextplatform.com/feed/ **[V]** (entries July 2026)
   - Category: trade/analysis. Entities: Chip (accelerators), Company, Architecture, Topic (AI infrastructure economics).
   - Volume: ~1–2/day. Rationale: the best public analysis of accelerator/datacenter compute economics — the "AI workload demand" leg of the domain's central tension.

5. **HPCwire** — https://www.hpcwire.com/feed/ **[V]** (entries July 2026)
   - Category: trade. Entities: Chip, Company, Architecture, Event (SC, ISC), Person.
   - Volume: ~3–5/day, press-release-heavy — **consider filtering PR reposts.** Rationale: HPC/AI compute wire; catches vendor announcements and national-lab deployments.

6. **Semiconductor Digest** — https://www.semiconductordigest.com/ (WordPress; feed likely /feed/) **[U]**
   - Category: trade (low-prestige, manufacturing-focused). Entities: Fab, Material/equipment, Packaging, Company.
   - Volume: ~2–3/day. Rationale: fab-construction, equipment-order, and materials news that consumer-tech outlets skip. Marginal if feed check fails — but the coverage gap it fills (manufacturing ops) is real.

7. **Bits & Chips** — https://bits-chips.com/ **[U — feed unconfirmed]**
   - Category: trade (Dutch/European). Entities: Material/equipment (ASML, ASM, imec), Company, ProcessNode.
   - Volume: ~1–2/day. Rationale: reports from ASML/imec's backyard with sources US outlets lack; the equipment/litho leg deserves a non-US source.

### Practitioner / specialist analysis

8. **SemiWiki** — https://semiwiki.com/feed/ **[V]** (entries July 2026: CoWoS vs EMIB, TSMC capex)
   - Category: practitioner forum/blog collective. Entities: Tool (EDA), Company, ProcessNode, Packaging, Person.
   - Volume: ~3–5/day. Rationale: written by semiconductor professionals (EDA/IP industry veterans); EDA coverage essentially unavailable elsewhere at this frequency.

9. **Chips and Cheese** — https://chipsandcheese.com/feed **[V]** (entries July 2026)
   - Category: practitioner (microarchitecture deep dives). Entities: Architecture, Chip, Company.
   - Volume: ~1–2/week. Rationale: independent die-level/ISA analysis (e.g., reading LLVM commits to infer unannounced GPU architectures) — original primary-ish research, never syndicated.

10. **More Than Moore (Ian Cutress)** — https://morethanmoore.substack.com/feed **[V]** (entries July 2026: High-NA EUV, CFET)
    - Category: specialist newsletter. Entities: ProcessNode, Packaging, Material/equipment (EUV), Company, Event coverage.
    - Volume: ~1–2/week. Rationale: ex-AnandTech senior editor; attends the process-technology conferences (IEDM, VLSI) and reports them properly.

11. **Fabricated Knowledge (Doug O'Laughlin)** — https://www.fabricatedknowledge.com/feed **[V]** (partially paywalled)
    - Category: specialist newsletter (semis investing). Entities: Company, Material/equipment, Topic (cycles, capex).
    - Volume: ~1/week. Rationale: financial-analyst lens on equipment/memory cycles; complements engineering sources. **Flag: paid tier truncated.**

12. **SemiAnalysis (Dylan Patel)** — https://www.semianalysis.com/ ; feed https://www.semianalysis.com/feed **[V but flagged: feed's newest items were ~10 months old at check — feed lags site, and content is heavily paywalled]**
    - Category: specialist analysis. Entities: Chip, Packaging (CoWoS/HBM), Fab, Company, Topic (AI capex).
    - Volume: ~1–2/week (free tier). Rationale: most-cited independent AI-silicon supply-chain analysis; even truncated previews carry entity-rich signal. **Marginal as an RSS citizen — verify feed freshness from the pipeline before counting on it.**

13. **ServeTheHome** — https://www.servethehome.com/feed/ **[V]** (entries July 2026)
    - Category: practitioner (server/accelerator hardware hands-on). Entities: Chip, Company, Architecture, Packaging (DIMM/HBM trends).
    - Volume: ~2–4/day. Rationale: physical hands-on with accelerators/servers at trade shows; catches SKUs and platform details before official launches.

14. **The Chip Letter** — https://thechipletter.substack.com/feed **[U — Substack feeds are reliably present; not individually fetched]**
    - Category: specialist newsletter (architecture history + current analysis). Entities: Architecture, Company, Person.
    - Volume: ~1/week. Rationale: context/novelty source; low volume, honest marginal — include only if newsletter slots remain.

15. **IEEE Spectrum — semiconductors topic** — https://spectrum.ieee.org/feeds/topic/semiconductors.rss **[V]** (entries July 2026)
    - Category: specialist journalism (research-adjacent). Entities: ProcessNode, Material, Architecture, Org (IEEE conferences).
    - Volume: ~3–5/week. Rationale: bridges research (ISSCC/IEDM results) into accessible reporting; topic-scoped feed keeps volume clean.

### Primary sources

16. **NVIDIA Blog** — https://blogs.nvidia.com/feed/ **[V]** (entries July 2026)
    - Category: primary (vendor). Entities: Chip (Rubin, Jetson), Architecture, Company partnerships.
    - Volume: ~1–3/day, **marketing-heavy — filter out GeForce NOW/gaming fluff.** Rationale: the dominant AI-compute vendor's own announcements, first-party.

17. **TSMC press releases** — https://pr.tsmc.com/english/news **[U — RSS unconfirmed; may need scraping]**
    - Category: primary. Entities: Fab, ProcessNode, Packaging, Location (Arizona/Kumamoto/Dresden).
    - Volume: ~1–3/week. Rationale: node/fab/capex announcements from the source; everything downstream is paraphrase.

18. **Intel Newsroom** — https://newsroom.intel.com/ **[U — RSS unconfirmed]**
    - Category: primary. Entities: ProcessNode (18A/14A), Fab, Chip, Person (exec churn).
    - Volume: ~2–4/week. Rationale: the US-fab side of the process race, first-party.

19. **ASML press/investor news** — https://www.asml.com/en/news **[U — RSS unconfirmed]**
    - Category: primary. Entities: Material/equipment (EUV, High-NA), Company, Policy (export licenses discussed in earnings).
    - Volume: ~1–2/week. Rationale: litho monopoly; their earnings commentary moves the whole equipment sector. If no feed: their quarterly cadence makes scraping cheap.

20. **Federal Register — "semiconductor" search feed** — https://www.federalregister.gov/documents/search.rss?conditions%5Bterm%5D=semiconductor **[V-blocked — our fetcher hit bot-detection, but FR search-RSS is a documented, stable feature]**
    - Category: primary (regulatory). Entities: Policy (BIS export rules, CHIPS awards), Org, Location.
    - Volume: ~1–3/week. Rationale: export-control rules and CHIPS notices as published law, hours-to-days before/independent of press interpretation. The single highest-value primary source in the domain.

21. **SIA (Semiconductor Industry Association) blog/news** — https://www.semiconductors.org/latest-news/ **[V-blocked — 403; WordPress feed likely]**
    - Category: primary (industry org). Entities: Policy, Org, Topic (global sales data — monthly WSTS numbers).
    - Volume: ~2–4/month. Rationale: monthly sales data + the industry's official policy positions.

22. **SEMI news** — https://www.semi.org/en/news-media-press-releases **[U]**
    - Category: primary (equipment/materials org). Entities: Material/equipment (billings data), Fab (fab-forecast reports), Event (SEMICON).
    - Volume: ~2–4/month. Rationale: equipment billings and fab-count forecasts are structural indicators. Marginal — include if feed exists, else quarterly scrape.

### Analyst / data

23. **TrendForce press center** — RSS index verified at https://www.trendforce.com/presscenter/rss.html **[V-page — pick the semiconductor/DRAM category feeds from that index]**
    - Category: analyst (Taiwan). Entities: Packaging (HBM), Company (memory), Chip, Topic (pricing).
    - Volume: ~1–2/day. Rationale: memory/HBM pricing and CoWoS capacity estimates — supply-chain quantification from a Taiwan vantage point.

24. **Counterpoint Research insights** — https://www.counterpointresearch.com/insights/ **[U — feed unconfirmed]**
    - Category: analyst. Entities: Company, Chip (smartphone/foundry share), Topic.
    - Volume: ~2–3/week. Honest marginal: overlaps TrendForce; include only if TrendForce category feeds prove too memory-centric.

### Geopolitics / policy analysis

25. **ChinaTalk (Jordan Schneider)** — https://www.chinatalk.media/feed **[V]** (entries July 2026)
    - Category: specialist newsletter (policy). Entities: Policy, Company (SMIC, Huawei), Person, Location (China).
    - Volume: ~2–3/week. Rationale: the working policy community's venue for export-control debate; interviews the actual BIS/industry people.

26. **CSIS — strategic technologies / chip analysis** — https://www.csis.org/analysis **[U — site RSS unconfirmed]**
    - Category: think tank. Entities: Policy, Location, Org.
    - Volume: ~1–2/week relevant. Rationale: Gregory Allen's export-control reports are primary references in the policy debate. If no clean feed, filter their analysis listing by scrape.

27. **Interconnected (Kevin Xu)** — https://interconnected.blog/ (feed: /feed.xml or /rss) **[U]**
    - Category: specialist newsletter. Entities: Company (Chinese semis, open-source stack), Policy, Topic.
    - Volume: ~1/week. Rationale: bilingual China-tech reading of chip policy — deliberate counterweight to the DC-consensus framing of #25/#26.

### Community / chatter

28. **Reddit r/hardware** — https://www.reddit.com/r/hardware/.rss **[U — reddit blocks our verifier; standard endpoint]**
    - Entities: Chip, Architecture, Company. Volume: sample top ~3–4/day. Rationale: fastest aggregation of leaks/benchmarks; comment quality high for a big sub.

29. **Bluesky — chip/semiconductor practitioner list** (hand-built list: chip architects, process engineers, semis analysts)
    - Entities: Person, Architecture, Topic. Volume: sample ~2–3/day. Rationale: post-Twitter chip commentary is fragmented; a curated Bluesky list is cheap coverage of conference chatter (Hot Chips, ISSCC weeks).

### Considered and excluded / defunct flags
- **AnandTech — DEFUNCT** (ceased publication Aug 2024). Any incumbent list still carrying it is dead weight.
- **WikiChip Fuse — suspect defunct**: server refused connections during this exercise (ECONNREFUSED). Do not include without a live check.
- **Asianometry Substack — stale**: feed's last entry Jan 2025 ("A New Start" — moved under Stratechery Plus, paywalled). The YouTube channel remains active but isn't RSS-article material. Excluded.
- **Real World Tech** — dormant for years; excluded.
- **DigiTimes Asia** — genuinely valuable Taiwan supply-chain reporting but hard-paywalled with no useful feed; excluded with regret (TrendForce + Bits & Chips partially substitute).
- **Tom's Hardware** (feed at /feeds.xml, verified-by-redirect) — excluded by default: 30+/day of consumer-tech volume for maybe 3/day of relevance; add only with aggressive filtering if leak-coverage recall proves weak.
- **Stratechery** — paywalled, and its chip takes are downstream of sources already listed.

## Category balance — Domain 2

| Category | Sources | Est. docs/day (post-filter) |
|---|---|---|
| Trade press/journalism | SemiEngineering, EE Times, Register (filtered), Next Platform, HPCwire (filtered), Semi Digest, Bits & Chips | ~12–14 |
| Practitioner/analysis | SemiWiki, Chips & Cheese, More Than Moore, Fabricated Knowledge, SemiAnalysis, STH, Chip Letter, IEEE Spectrum | ~5–7 |
| Primary sources | NVIDIA (filtered), TSMC, Intel, ASML, Federal Register, SIA, SEMI | ~1–2 (bursty) |
| Analyst/data | TrendForce, (Counterpoint) | ~1–2 |
| Geopolitics/policy | ChinaTalk, CSIS, Interconnected | ~0.5–1 |
| Community/chatter | r/hardware, Bluesky list | ~5–7 sampled |
| **Total** | | **~25–30 → tune filters to ~22** |

Topic redundancy check: process nodes (SemiEngineering, More Than Moore, IEEE Spectrum, TSMC/Intel primary ✓); packaging/HBM (SemiEngineering, SemiWiki, TrendForce, SemiAnalysis ✓); accelerators (Next Platform, STH, HPCwire, Chips & Cheese, NVIDIA ✓); export controls (Federal Register, ChinaTalk, CSIS, Register ✓); EDA (SemiWiki + SemiEngineering — **only two strong sources; acceptable but thin, flagged**); equipment/litho (ASML, Bits & Chips, Fabricated Knowledge, SEMI ✓); memory (TrendForce, Fabricated Knowledge, STH ✓).

## Deliberately anti-consensus picks — Domain 2
- **Federal Register search-RSS** — primary regulatory text instead of (or ahead of) reporters' summaries of BIS rules; almost no curated list includes it.
- **Semiconductor Digest & Bits & Chips** — low-prestige manufacturing/European trades covering fab construction and litho-neighborhood news that Bloomberg-tier coverage flattens.
- **SemiWiki** — practitioner forum energy, EDA-industry insiders; prestige lists take Stratechery instead and lose all EDA coverage.
- **Chips and Cheese** — independent reverse-engineering of architectures from public artifacts; original signal, zero syndication.
- **Interconnected** — a China-fluent, non-DC read on export controls to keep the policy cluster from being a monoculture (FR + CSIS + ChinaTalk all orbit Washington).
- **TrendForce Taiwan analyst wire** — pricing/capacity numbers from the supply chain's home turf rather than Western re-reporting.

---

## Cross-domain operational flags (from verification, 2026-07-19)
1. **Tollbit gating (film)**: IndieWire/Deadline feeds 402 for non-browser clients. Test with the pipeline's actual UA before assuming coverage.
2. **403-to-bots but healthy (both)**: SemiEngineering, SIA, Cineuropa, theASC, Federal Register — these blocked this exercise's fetcher; most work in real feed readers. Verify from the pipeline, not from a browser.
3. **Empty-but-valid feeds**: Screen Daily's 25.rss returns a valid skeleton with zero items — a feed that parses fine and delivers nothing. Add a "zero items for N days" alert to the ingester if it doesn't already have one.
4. **Confirmed dead/stale**: AnandTech (dead), WikiChip Fuse (server down), Asianometry Substack (stale since Jan 2025), Oz Magazine (no feed), Sub-Genre (email-only).
