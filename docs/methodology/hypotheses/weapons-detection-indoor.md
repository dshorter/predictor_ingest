---
read: full
status: pre-registered 2026-07-20, before first extraction batch
---

# Pre-registered hypothesis — Weapons Detection Systems (Indoor)

Written before any data, per the standing rule in
`docs/methodology/domain-candidates.md` ("score first, pre-register a
named hypothesis... before first data") and the Sprint 20.15 pattern used
for fusion. This domain was onboarded 2026-07-20 **out of the queue order**
recorded in that registry (fusion → biopharma → this) — an explicit
operator decision to jump ahead, not a change to the underlying doctrine.
Jumping the queue changes *when* this domain gets built; it doesn't
exempt it from being graded the same way fusion will be.

## What this domain is expected to prove

At high coverage fraction (an estimated ~15 curated sources capturing the
majority of a genuinely small ecosystem — indoor gunshot/visual/screening
vendors selling to transit, school, hospital, venue, and workplace
buyers) with calendar-anchored ground truth (RFP awards, pilot
evaluation reports, two public tickers' quarterly filings), this
pipeline can:

1. **Surface vendor-buyer deployment events before they consolidate into
   trade-press roundups** — a school district procurement or transit
   pilot should appear in the graph (via `PROCURES`/`PILOTS`/
   `DEPLOYED_TO`) from primary/buyer-side trade press (StateScoop,
   K-12 Dive) at least as early as, and often before, security-industry
   trade press picks it up as a trend piece.
2. **Keep the controversy axis structurally visible rather than let it
   get drowned by vendor volume** — the `DISPUTES`/`RESPONDS_TO`/
   `EVALUATES` relations should produce a non-trivial, non-zero edge
   count tying watchdog sources (ACLU, EFF, MacArthur Justice Center) to
   the same Product nodes vendor press is name-dropping favorably. If
   this edge set stays empty after a full dampening window, either the
   watchdog sources aren't delivering (an ingestion problem) or the
   extraction prompt is failing to capture disputed claims as such (a
   prompt problem) — the pre-registration exists so that failure gets
   diagnosed rather than quietly accepted as "no controversy."
3. **Confirm the tripwire disposition** — this domain's own scoring
   (see the registry entry) predicted Landscape+tripwire as the right
   shape, Movers as secondary, because the entity set is small enough
   that *detecting a new deployment* is the value, not *ranking movement
   among existing entities*. Prediction: after 30 days, the number of
   distinct entities with `mention_count_30d > 0` will be small enough
   (order of dozens, not hundreds) that Movers' ranking machinery
   produces mostly ties and noise — evidence for building the Sprint 21
   tripwire ledger view rather than leaning on Movers here.

## Scores predicted now (20.13 grades these later)

Copied from the registry entry's disposition, restated as falsifiable
numbers to check against once data exists:

| Axis | Predicted | What would falsify it |
|---|---|---|
| Coverage fraction | High (best of any candidate scored to date) | If the "not adopted" gap (SecurityInfoWatch/Mass Transit/general security-integrator trade) turns out to carry a large fraction of real deployment announcements, coverage fraction is lower than predicted |
| Calendar ground truth | Strong, fusion-grade | If EVLV/SSTI quarterly filings don't actually name specific deployments/contracts (i.e., filings are financial boilerplate with no entity-rich text), this axis over-promised |
| Velocity behavior | Bursty, incident-correlated — `sustained` (20.8) more informative than raw velocity | If velocity instead tracks procurement cycles cleanly with little incident noise, the domain is better-behaved than predicted (a good problem) |
| Graduation rate (Movers → Landscape, per 20.13) | Low — most Movers entries should be one-off new entities that never "graduate," because the buyer set churns slowly | If graduation rate is comparable to film's, this domain isn't as sparse as scored and belongs on the ranking track after all |

## Budget and window

Registry estimate: 5–12 docs/day. `domain.yaml` sets `doc_selection.budget: 10,
stretch_max: 15`. Per D6/20.18's pattern, output should be flagged
provisional for a 14-day dampening window from first ingest
(2026-07-20), with daily snapshots collected from day 1 so the
validation dataset starts clean — this hypothesis page is graded no
earlier than 2026-08-03.

## What would make this a failed experiment (stated up front)

- If, after dampening, coverage fraction is actually low because the
  "not adopted" trade-press gap (transit-safety and general
  security-integrator press) turns out to be where most real news
  lives — the domain would need a scrape-based source (not RSS) to be
  viable, changing its cost profile.
- If the controversy axis produces zero `DISPUTES`/`RESPONDS_TO` edges
  after 30 days despite watchdog sources delivering documents — a
  prompt-tuning problem, not a domain-selection problem, but one that
  would mean the domain isn't yet proving what it was chosen to prove.
- If Movers/Landscape both stay this thin even past dampening, the
  domain confirms its own tripwire disposition — a *successful*
  falsification of "this could be a ranking domain," which is exactly
  why Sprint 21's ledger view exists as an alternative shape.
