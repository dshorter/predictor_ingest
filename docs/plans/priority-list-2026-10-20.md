---
read: full
status: proposed 2026-10-20, revised 2026-10-20 (evening) with operator direction on items 1 and 3, corrected 2026-10-21 after a check of the session's lists — ranked, nothing started; operator owns the order and each decision
---

# Predictor priorities — 2026-10-20

Written after the 2026-10-20 semiconductors health check and two-week spend
audit. API credits have been off since 2026-10-13 by operator choice, pending
that audit. Two operator directions shape the list: shut the film domain down
for now, and show any domain's existing data through a date picker without
creating false data from real data.

Revision 2026-10-20 (evening): item 1 gains the config-driven domain picker,
the inactive-domain modal and the status card; item 3 now archives the raw
downloads (upstream of the first LLM call), not the graph exports; export
compression moves to item 4; a run order is added.

Correction 2026-10-21: film does not clear ADR-011 D5's bar (item 1's ADR
note said it did); the modal's date was the wrong fact; the raw archive must
sweep film, whose daily run will be off; the "unreadable 10 GB" was accounted
for on 10-20; the disk is at 96% (1.6 GB free), not 94%; item 5's backfill
figures are dated and the 10-02 lapse is added back.

## The rule the list serves

A date in the picker shows only what the pipeline actually produced on that
date. Nothing is recomputed, re-filtered or rebuilt from today's database to
look like the past.

Today's explorer breaks that rule in three ways:

1. **The "As of" picker trims today's graph.** Choosing a past date filters the
   current export in the browser, so the view shows today's entity merges and
   today's trend scores under an old date.
2. **Pause days look like new days.** The daily run keeps exporting when no new
   data arrives. Semiconductors Movers fell from 8,548 rows (09-30) to 5,619
   (10-20) only because the 7-day window emptied.
3. **Export date ranges name the window, not the newest article.** The
   mentions, claims and dependencies views say "through 10-20"; the newest
   extracted semiconductors article is from 10-12. Only the trending view shows
   the snapshot badge.

Two facts rule out rebuilding past graphs from the database: entity merges are
not timestamped (entity_aliases has no date column), and film has 2 extracted
articles dated 2029 and 72 with no publish date.

What is real and dated: daily exports per domain (2026-08-21 to today; earlier
ones are in data/archive tarballs), trend_history rows per run date, and the
per-run logs, which record whether new extractions arrived.

## Top five

### 1. Shut film down; let a config file drive the domain picker

Why first: operator decision; film was 48% of recorded spend ($10.23 of $21.23
in the only funded stretch, 10-07 to 10-13) and adds about 67 MB a day to a
disk with 1.6 GB free (38 MB of exports, 29 MB of raw downloads; measured
2026-10-21). Semiconductors adds about 41 MB a day, so the disk has about two
weeks with film running and five to six without it.

Shutdown:

- Stop the 06:00 film timer. Needs sudo, so it ships as a script: disable,
  verify, restore on failure.
- Drop film from the staleness alert's default domain list
  (scripts/check_staleness.py), or it reports film as stale every 6 hours.
- Change the Makefile default (DOMAIN ?= film) to semiconductors, or a bare
  make daily restarts film's spend.
- Pin film's live files (web/data/graphs/live/film) to the 2026-10-14 export,
  its last run with new data. The 10-15 to 10-20 exports are pause re-runs.
- Add a dated amendment to ADR-011: the shutdown supersedes D1's hold, and D2
  (mentions-only film on Haiku) is shelved, not rejected. D5 stays blocked.
  Film's trend history restarted 09-13 after a 37-day gap, and ADR-010 D6
  treats the first 14 days after a restart as provisional. From 09-27 to 10-14
  film has 18 days of trend rows, only 12 of them with new data (the 10-03 to
  10-08 credit lapse sits inside); D5 needs 30. So the shutdown leaves the
  ADR-010 D10 Movers question unanswered for film, which is the outcome
  ADR-011's Consequences warned about, and a restart after a multi-week gap
  opens a new 14-day window. Film's resolve stage has also timed out every day
  since 09-02, so the frozen snapshot's entity merges are incomplete.
  (Corrected 2026-10-21: this note first said film had 32 continuous days and
  cleared the bar. That counted trend rows, including pause days, and ignored
  the dampening window.)

Domain picker:

- One domain config file replaces the hand-kept lists: KNOWN_DOMAINS in
  web/js/domain-switcher.js, the list in web/js/ontology.js, the fallback in
  web/dashboard.html, and film hard-coded as the default in nine places. The
  file holds decisions only: which domains exist, their labels, the default
  domain (semiconductors), and whether each is active. Desktop and mobile
  (web/mobile/index.html) both read it.
- Graph view: every domain stays in the menu. Choosing an inactive one opens a
  modal ("Film isn't being collected. Its data ends 2026-10-13.") with
  "Open in Movers" and "Stay"; the menu closes and the current domain stays. A
  direct link to an inactive domain gets the same modal.
- Movers view: inactive domains load, with a pull-down status card that says
  whether the data is current or, if not, when collection stopped. Film
  (10-14), AI (05-23) and biosafety (05-31) all have Movers data to show.
- The modal and card name the data-through date. Film's fetches keep running
  until its timer is off, so "collection stopped 10-14" would be false;
  10-14 is its last run with new data, and its data ends 10-13.
- The same card shows on both views for any domain whose data is not current.
  Semiconductors today is active but its data ends 10-12. The existing snapshot
  badge becomes the card's handle.
- The card's dates come from item 2's manifest, never from the config file.
  Active is a decision; current is a fact. A hand-typed date drifts the way
  web/data/dashboard/status.json has (still dated 2026-03-14).

Done when: no film run at 06:00 and no film staleness messages; every page
reads the one config file; a first visit with no domain in the link opens
semiconductors; film, AI and biosafety get the modal on Graph and the card on
Movers; semiconductors shows a card reading "data through 2026-10-12".

### 2. Build the snapshot manifest

Why second: the picker reads it, and it is what keeps false data out.

A generated per-domain index of real dates: run date, data-through date (newest
extracted article by fetch date), new extractions that run, methodology
version, and which export files exist. Built from run logs and the database;
never by recomputing scores.

- First cut, which item 1's card needs: the latest real run and data-through
  date per domain.
- Full manifest, which item 4's wheel needs: every real date.
- A date is listed only if its export exists on disk.
- Runs with no new extractions fold into the previous real date and are not
  offered on their own.
- Methodology or epoch changes are marked as breaks.
- Dates come from run date and fetch date, never publish date.
- Fix the exporters so dateRange ends at the newest included article; the
  existing snapshot badge then works on every view.
- Pause runs stop writing dated exports. Each one is a near-copy (about 17 MB a
  day for semiconductors while credits are off).

This is ADR-012 D3 (a missing run must not be substitutable by old output)
applied to the explorer. ADR-012 is still Proposed, so stopping pause-run
exports waits on the operator deciding ADR-012 D3; that decision settles the
rule for the pipeline too.

Done when: the semiconductors manifest's latest real run is 2026-10-13 (data
through 10-12) and film's is 2026-10-14 (data through 10-13).

### 3. Archive the raw downloads

Why third: the disk was at 94% (2.3 GB free) on 10-20 and is at 96% (1.6 GB
free) on 10-21; about half of that day's loss is one extra backup set taken
before the 10-20 reboot, which ages out 11-03. Raw downloads (data/raw) are
4.37 GB of HTML, film 2.46 GB and semiconductors 1.80 GB. The pipeline reads each file once, to make the cleaned text;
after that only scripts/repair_data.py reads them.

- First, switch RSS ingest's "already have it" check from file existence to
  the database (src/ingest/rss.py:286), as the Bluesky, EDGAR and patents
  ingesters already do. Today a missing raw file means the article is
  downloaded again and its row rewritten with INSERT OR REPLACE, which resets
  its status: a shelved article returns to the queue, and an extracted one is
  queued to be paid for again. No raw file moves before this change.
- Then, a one-time sweep of every domain's raw files older than 14 days,
  inactive domains included: film holds more than half the raw bytes and its
  daily run will be off, so a rule inside the daily pipeline never reaches it.
- After that, a rolling rule run by the daily pipeline for active domains:
  raw files older than 14 days go into one tar.zst per domain per month.
- Measured 2026-10-20 with zstd's long-range mode: all 4.37 GB of raw files
  compress to 81 MB (54×). The never-extracted files alone: film 1.30 GB to
  18 MB, semiconductors 0.59 GB to 9 MB.
- Verify each tarball against the originals before deleting anything, and
  keep a restore command beside it.
- Cleaned text (data/text, 236 MB) stays loose: it is what the docpack picker
  and any backfill read.
- Docpacks (data/docpacks, 232 MB) are also upstream of the LLM. Check what
  reads them before deciding.
- Docker was checked 2026-10-20: the weekly docker-prune.timer runs every
  Sunday and has reclaimed 0 B each week the journal holds (08-30 on), because
  /etc/docker/daemon.json caps the build cache at 10 GB and logs at 3 × 50 MB.
  Docker's data lives on its own 70 GB volume (12% used), not this disk.
- The root-only 10 GB was accounted for 2026-10-20 from the operator's sudo
  du: /var/backups 7.4 GB (6.5 GB of it 14 days of predictor database
  snapshots), the journal 1.9 GB (journald caps it at 2 GB, so it won't grow),
  and /root 1.9 GB (root's old Claude Code install is 868 MB of it). Since
  server-maintenance db399e3 the backup keeps one copy of an unchanged
  database, so film's daily 272 MB snapshot stops repeating once its timer is
  off and about 3.5 GB comes back over the following 14 days. Those host items
  are tracked in /opt/server-maintenance/TODO.md.

Done when: about 4 GB is freed (the disk near 84% on 10-21 figures), film's
raw files are swept, the 14-day rule runs with the daily pipeline, and a month
restored from its tarball matches the originals.

### 4. Date picker wheel on the manifest

Why fourth: it needs the full manifest from item 2.

- A wheel of the manifest's real dates for the chosen domain. Selecting one
  loads that date's archived export instead of filtering today's graph.
- Each date shows its data-through date and new-extraction count. A pause
  shows as one labeled gap ("no new data, 10-13 to 10-20").
- The Movers page uses the same wheel; trend_history per run date is real.
- Works for every domain in the config file, desktop and mobile.
- Retire the current "As of" filter, or relabel it "filter by article date" so
  it stops claiming to show the past.
- Export storage: dates the wheel offers are gzipped per file (about 20× on
  the file tested) and unzipped by the browser, so no Caddy change is needed;
  pause-day exports go into tarballs. Measured: all 61 days of film exports,
  3.5 GB, come to 84 MB as tar.zst; semiconductors, 1.6 GB, to 30 MB.

Done when: for every domain, each wheel date matches its archived export byte
for byte (a test asserts it), and no date shows data newer than its
data-through date.

### 5. Close the audit and plan the credit restart

Why fifth: credits stay off until the audit closes; with film off, this is
what remains.

- Projected burn without film: about $1.90 a day, down from about $3.50
  (recorded: semiconductors about $1.05 a day, sysadmin about $0.57 a run,
  Director about $0.20 a day).
- Check the 10-07 top-up against the $19.70 recorded for 10-07 to 10-13, to
  rule out spend from outside the box.
- Decide the semiconductors backfill for the paused days. As of 10-20: about
  $7.40 at the normal 25 a day, about $26 for all 696 waiting documents; both
  grow each day credits stay off. The docpack picker looks back only 7 days,
  so documents fetched before that need an explicit override. That includes
  the 402 left by the 10-02 to 10-07 lapse (about $5.50 at 25 a day).
- Add extraction freshness to the staleness alert, so the next stop shows up
  there and not only in the morning PARTIAL message.

Done when: credits are back on with a known daily burn, and the alert flags an
extraction stop within a day.

## Run order

1. Film shutdown: timer script, staleness list, Makefile default, pin the
   live files, ADR-011 note.
2. Manifest first cut and the date-range fix. Stopping pause-run exports
   waits on the ADR-012 D3 decision.
3. Domain config file, modal, status card, semiconductors as the default.
4. RSS check fix, then the raw archive.
5. Full manifest and the wheel, with export compression.
6. Close the audit and restart credits.

## Left off the list

Feed problems (The Register HTTP 500, Fabricated Knowledge silent 67 days, More
Than Moore silent 19 days, SEC_EDGAR_EMAIL unset), sysadmin cost per run, and
semiconductors entity growth (21,607, up 26% since 09-13; resolve has headroom).
They matter, but none blocks the goal.
