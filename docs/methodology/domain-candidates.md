# Domain Candidates — scored against the pond-sizing criteria

Registry of proposed domains, each scored against the five criteria from the
2026-07-03 methodology review before any onboarding work. Rule (standing):
score first, pre-register a named hypothesis (Sprint 20.15 pattern) before
first data, and sequence new domains after fusion validates or breaks the
criteria themselves. Onboarding is cheap (`domains/_template/`); scoring is
cheaper. The five criteria: coverage FRACTION not volume; concentrated early
signal in identifiable niche sources; calendar-anchored ground truth;
recurring actors with churning attachments; relationships carry signal.

Queue as of 2026-07-19: **fusion** (chosen 2026-07-03, Sprint 20 Track C,
pre-registration = 20.15) → **biopharma** (ADR-010 D11, deferred until fusion
reports) → candidates below in operator-priority order.

**2026-07-20 — queue jumped by operator directive:** weapons-detection-indoor
was onboarded (`domains/weapons_detection/`) before fusion has run its own
pre-registration (20.15) or produced a validation cycle. This is a
deliberate reorder, not a change to the standing rule — the rule still
holds for whatever comes after this. Pre-registered hypothesis:
[docs/methodology/hypotheses/weapons-detection-indoor.md](hypotheses/weapons-detection-indoor.md)
(read: full). First ingest fired 2026-07-20; 14-day dampening window
applies (graded no earlier than 2026-08-03).

---

## weapons-detection-indoor — ONBOARDED 2026-07-20 (scored 2026-07-19, operator + external requester)

**Scope:** indoor weapons detection as one ecosystem — acoustic gunshot
detection (AmberBox, Shooter Detection Systems/Alarm.com, Databuoy), visual
AI detection (ZeroEyes, Omnilert), walk-through screening (Evolv, Xtract One,
CEIA) — all selling to the same buyers (transit agencies, schools, hospitals,
venues). **No single-venue lens** — subway stations were the requester's
illustrative example, not a focus; the buyer base spans transit, schools,
hospitals, venues, and workplaces equally, and the source list should
cover them all. (If a venue lens ever proves wanted, add it later the way
film added the Southeast — lenses narrow well but un-narrow poorly.)
**Outdoor exposure:** a deliberate
tripwire sliver only — SoundThinking SEC filings (the `edgar` fetcher already
works), watchdog aggregators (MacArthur Justice Center, EFF) who do the
per-city collection, 2–3 flagship cities. NOT outdoor coverage.

**Scores:**

| Criterion | Score | Notes |
|---|---|---|
| Coverage fraction | **Excellent** — best of any candidate yet | ~15 curated sources plausibly capture the majority of the niche's discourse |
| Concentrated niche sources | **Strong** | Security trade press (Campus Safety, Security Systems News, SecurityInfoWatch), transit trades (Mass Transit, Metro), IPVM (paywalled crown jewel — adversarial independent research on exactly this space) |
| Calendar ground truth | **Strong (fusion-grade)** | Dated pilots with mandated evaluation reports (NYC subway scanner pilot), RFP→award procurement, TWO pure-play public tickers (EVLV, SSTI) reporting quarterly, council votes, ISC West/GSX annually |
| Recurring actors, churning attachments | **Yes** | ~dozens of vendors × churning agency/district deployments; vendor-wins-contract edge is the core signal |
| Relationships carry signal | **Yes, plus a controversy axis** | Accuracy disputes / surveillance criticism (ACLU, EFF, MacArthur studies) — skeptic sources are the anti-consensus layer built in |

**Disposition:** Landscape + tripwire; Movers secondary (entity set small —
detection of new deployments/attachments/policy shifts is the value, not
ranking). Estimated steady-state volume 5–12 docs/day (pond-sized).

**Known weaknesses (stated up front):** near-zero practitioner chatter (no
Reddit/Bluesky worth a slot); volume is bursty around incidents — velocity
spikes will partly track news cycles of tragedies, so the `sustained` flag
(20.8) matters more than raw velocity here, and consumers of the output
should know that.

**Rejected alternative framing** (considered 2026-07-19): "gunshot detection,
indoor + outdoor" — keeps the technology coherent but fails criterion 2
(outdoor discourse lives in a per-city local-journalism long tail with no
stable feed shoreline → coverage fraction collapses) and criterion 4 (outdoor
acoustic is near-monoculture: one dominant vendor × many cities — Movers over
a one-vendor market is meaningless). The outdoor story's center is civic
controversy/litigation, which is a policy-tracker shape, not this pipeline's.
The tripwire sliver above keeps its spine in view.

**Next steps when its turn comes:** blind source-verification pass (the
2026-07-19 audit pattern, docs/audits/), pre-registered hypothesis page,
`domains/_template/` onboarding. Not before fusion reports.
