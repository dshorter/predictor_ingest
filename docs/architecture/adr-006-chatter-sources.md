# ADR-006: Chatter Sources — Extending Ingest Beyond RSS

**Status:** Accepted
**Date:** 2026-03-17
**Deciders:** dshorter, Claude (Opus 4.6)
**Sprint:** 7 (Regional Lens + Chatter Sources)

## Context

The pipeline ingests exclusively via RSS feeds. This captures structured
editorial content (trade press, blogs, institutional announcements) but misses
informal industry "chatter" — practitioner commentary, audience reactions,
rumor propagation, early sentiment signals.

For the film domain's Southeast focus, chatter sources are especially valuable:
local industry conversations happen on social platforms more than in trade press.
The question: **Can we capture social chatter without paid API costs?**

## Decision

Extend `src/ingest/` with new fetcher modules for three source types, prioritized
by cost and signal quality:

### Tier 1: Zero code changes (immediate)

**Substack newsletters** — every Substack is already an RSS feed. Add film-focused
Substack URLs directly to `domains/film/feeds.yaml`. The existing RSS fetcher
handles them with no modification.

### Tier 2: New fetcher modules (Sprint 7A)

**Bluesky (AT Protocol)**
- Free public firehose, no authentication required
- Supports keyword filtering at the stream level
- New module: `src/ingest/bluesky.py`
- Maps posts to document schema: title = first line, text = full post,
  published_at = post timestamp, url = AT URI
- Geographic filtering natural: subscribe to `Atlanta OR Trilith OR ...`

**Reddit (free API tier)**
- 100 requests/minute free, no commercial use restriction at this volume
- New module: `src/ingest/reddit.py`
- Target subreddits: r/Atlanta, r/Filmmakers, r/boxoffice, r/NewOrleans
- Maps posts + top comments to document schema
- Self-posts and comment threads are the signal; link posts are echo

### Tier 3: Evaluated but deferred

| Source | Cost | Why deferred |
|--------|------|-------------|
| Mastodon | Free | Low volume for film industry; revisit if community grows |
| YouTube comments | Free (10k units/day) | High noise, extraction cost not justified for V1 |
| Letterboxd | Free (RSS) | Audience sentiment, not industry chatter; may add to Tier 1 later |
| Comment sections | Free (scraping) | Most trades killed comments; fragile, low volume |
| Twitter/X | Paid ($100/mo minimum) | Cost exceeds budget constraint |

## Implementation

### Schema changes

Add `source_type` column to documents table:

```sql
ALTER TABLE documents ADD COLUMN source_type TEXT NOT NULL DEFAULT 'rss';
```

Valid values: `rss`, `bluesky`, `reddit`, `substack` (substack uses RSS fetcher
but tagged differently for provenance).

### Fetcher interface

Each new fetcher module implements the same contract as `src/ingest/rss.py`:

```python
def fetch(feed_config: dict, db: Database, limit: int) -> list[dict]:
    """Fetch documents from source, return list of document dicts.

    Each dict has: url, title, text, published_at, source_name, source_type,
    content_hash. Caller handles dedup via content_hash and DB insert.
    """
```

### Rate limiting

| Source | Limit | Implementation |
|--------|-------|---------------|
| RSS | 1 req/sec per domain | Existing `time.sleep(1)` in rss.py |
| Bluesky | No formal limit | Firehose is streaming; keyword filter reduces volume |
| Reddit | 100 req/min | Token bucket in reddit.py, 600ms between requests |

### Pipeline integration

`scripts/run_pipeline.py` ingest stage calls fetchers based on `feeds.yaml` config:

```yaml
# New feed entry format for non-RSS sources
- name: "Bluesky Film Chatter"
  type: bluesky                    # dispatches to bluesky.py
  keywords: ["Atlanta film", "Trilith", "Georgia production", ...]
  enabled: true
  tier: 2
  signal: community

- name: "r/Filmmakers"
  type: reddit                     # dispatches to reddit.py
  subreddit: "Filmmakers"
  enabled: true
  tier: 2
  signal: community
```

The `type` field in feeds.yaml already exists (values: `rss`, `atom`). Extending
to `bluesky` and `reddit` is a natural evolution.

## Alternatives Considered

### A. Paid social media APIs (rejected)

Twitter/X API ($100/mo), Instagram Graph API (business accounts only).

**Why rejected:** Budget constraint is hundredths-of-a-cent per transaction or free.
Paid APIs are not justified at current pipeline scale.

### B. Web scraping of social platforms (rejected)

Scrape Twitter/Instagram/TikTok directly.

**Why rejected:** Violates project safety/legal policy (respect ToS). Fragile.
Legally risky. The free API options (Bluesky, Reddit) provide equivalent signal.

### C. Single unified social fetcher (rejected)

One module that handles all social platforms via adapter pattern.

**Why rejected:** Over-engineering. Each platform has fundamentally different APIs
(AT Protocol firehose vs Reddit REST vs RSS). Separate focused modules are simpler
and independently testable.

## Consequences

### Positive
- **Captures informal signals** — practitioner chatter, early rumors, sentiment
  shifts that trade press takes days/weeks to reflect.
- **Zero or near-zero cost** — all selected sources are free at our volume.
- **Regional filtering is natural** — Bluesky keyword filter and Reddit subreddit
  selection inherently scope to geographic/topical communities.
- **Domain-agnostic** — fetcher modules are framework code. Any domain can add
  Bluesky/Reddit sources via feeds.yaml config.
- **Incremental adoption** — Substack requires zero code changes (Tier 1).
  Bluesky/Reddit are independent modules (Tier 2). Can ship in stages.

### Negative
- **Noise** — social content is noisier than editorial. Quality gates (evidence
  fidelity, orphan endpoints) will escalate more extractions. May need a
  `source_type`-aware quality threshold adjustment.
- **Volume spikes** — Bluesky firehose can produce bursts. Budget/stretch limits
  in article selection will cap extraction, but raw document storage grows faster.
- **Short-form content** — social posts are typically <500 chars. The `word_count`
  scoring signal penalizes short docs (ramp 0→0.5 below 200 words). May need a
  `source_type`-aware scoring curve, or accept that social posts score lower and
  rely on bench backfill.
- **New test surface** — each fetcher needs mocked API tests. Network tests need
  `@pytest.mark.network` marking.

## Related
- [ADR-005](adr-005-regional-lens.md) — Regional lens (same sprint)
- [domain-separation.md](domain-separation.md) — Fetcher modules are framework code, not domain-specific
- [source-selection-strategy.md](../source-selection-strategy.md) — Existing tier model for RSS feeds
