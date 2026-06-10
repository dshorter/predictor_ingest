# Site Topology Plan — uzelhub.com surfaces

**Status:** Phase A complete (2026-05-31). Phases B/C pending, no timeline.
**Agreed:** 2026-05-23 (dshorter + Claude). Ported into the repo 2026-06-10 —
this file is canonical; the agent-memory copy is a pointer.

The uzelhub.com box serves multiple surfaces from one root: the personal
landing / portfolio (`/opt/uzelhub-web/`), the predictor app, the Uzella API
proxy, and the Ghost blog (`blog.uzelhub.com`). This is the phased move-out
plan as the predictor approaches public-share readiness.

## Future-state topology (target)

```
uzelhub.com              = marketing site (planned, not yet built)
studio.uzelhub.com       = current portfolio / living site at root today
predictor.uzelhub.com    = predictor app (independent product)   ← LIVE (Phase A)
blog.uzelhub.com         = stays as-is
```

Predictor lives at `predictor.uzelhub.com` (independent product) rather than
`predictor.studio.uzelhub.com`. It may eventually move to the studio subdomain
if positioning shifts, but for now: independent.

## Phased plan

**Phase A — DONE 2026-05-31** (see
[predictor-prod-split.md](predictor-prod-split.md), archived runbook):
- Cloned `/opt/predictor_ingest` to `/opt/predictor_prod`, pinned to `main`
- Symlinked prod's generated-data dirs back to the dev tree
- New Caddy block: `predictor.uzelhub.com` → `/opt/predictor_prod/web`
- Dev URL `uzelhub.com/apps/predictor/` stays (no change)
- Auto-update: existing GitHub Action re-pointed at the prod tree

**Phase B — when ready, no specific timeline:**
- Move studio content to `studio.uzelhub.com`
- Root `uzelhub.com` becomes parking page or redirect to studio until the
  marketing site exists
- Studio gets no dev/prod split — change cadence too low to warrant it

**Phase C — when the marketing site is built:**
- Marketing site live at `uzelhub.com/`
- Studio + predictor stay at their subdomains
- Marketing gets its own prod/dev story when it warrants one

## Decisions confirmed 2026-05-23

| Question | Decision |
|---|---|
| Predictor URL | `predictor.uzelhub.com` (independent). Eventual move to `predictor.studio.uzelhub.com` possible but deferred. |
| Other surfaces' dev URLs | None needed yet |
| Studio prod/dev split timing | Not now, not Phase A, not Phase B — only when cadence or contributors change |
| Marketing site documented | Not in repo yet — marketing-from-studio mapping being worked out separately |
| Phase A dev URL | `uzelhub.com/apps/predictor/` stays as-is |

## Why each surface gets its own driver

Predictor needs prod/dev because it's public-facing AND changes hourly. Studio
doesn't (slow cadence, low risk of edit-and-live breakage). Marketing site is
future. Forcing one consolidated split across all surfaces would over-engineer
the surfaces that don't need it — each gets the split only when its own driver
demands it.
