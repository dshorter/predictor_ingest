# Predictor dev/prod split — Sprint 18 Phase A

**Status:** Shipped 2026-05-31.
**Scope:** predictor app only. Studio (`uzelhub.com/`), the planned marketing
site, blog (`blog.uzelhub.com`), and the Uzella API proxy are unaffected.
**Future-state context:** see [`site-topology-plan`](../../../../../home/claude/.claude/projects/-opt-predictor-ingest/memory/site_topology_plan.md)
(in agent memory — phased move-out of all uzelhub.com surfaces).

---

## What's where

| URL | Filesystem path | Branch | Caddy block | Updated by |
|---|---|---|---|---|
| `https://predictor.uzelhub.com/` | `/opt/predictor_prod/web/` | `main` (pinned) | `predictor.uzelhub.com { … }` | GitHub Actions on merge to main |
| `https://uzelhub.com/apps/predictor/` | `/opt/predictor_ingest/web/` | whatever's checked out | `uzelhub.com { … handle_path /apps/predictor/* … }` | Manual edits, immediate (filesystem-direct serve) |

**Two clones of the same repo** at separate paths. Different remotes are *not* used — both `origin` is `git@github.com:dshorter/predictor_ingest.git`. The distinction is purely "which branch is checked out, and how does it update."

## Data sharing

The pipeline writes generated JSON only in the dev tree. Prod sees the same data via symlinks:

```
/opt/predictor_prod/web/data/graphs/live  →  /opt/predictor_ingest/web/data/graphs/live
/opt/predictor_prod/web/data/dashboard    →  /opt/predictor_ingest/web/data/dashboard
```

Both of those target dirs are gitignored (or untracked) in `predictor_ingest`, so `git checkout origin/main -- .` during deploys does *not* touch the symlinks. The pipeline runs in `/opt/predictor_ingest/` (where the DB lives), writes to those dirs, both URLs reflect the new data instantly.

## How prod updates

1. PR merges to `main` on GitHub
2. `.github/workflows/deploy.yml` triggers (push to `main`)
3. `appleboy/ssh-action` SSHes to the VPS as `root`
4. Runs `cd /opt/predictor_ingest && ./scripts/deploy.sh main`
5. `scripts/deploy.sh` reads `REPO_DIR="/opt/predictor_prod"` and operates there:
   - `git fetch origin main`
   - `git checkout origin/main -- .` (overwrites tracked files in prod tree)
   - `git reset origin/main` (moves prod's main pointer)
6. Logs to `/opt/predictor_prod/data/logs/deploy.log` and `journalctl -t predictor-deploy`

Manual trigger (when you don't want to wait or are testing):
- GitHub → Actions tab → "Deploy to VPS" workflow → **Run workflow** → branch: main

## How dev updates

Dev is **no longer auto-updated by merges to main** — that's the whole point of the split. To pull main into dev:

```bash
cd /opt/predictor_ingest
git checkout main
git pull --ff-only
```

…or you stay on a feature branch and your edits go live at `uzelhub.com/apps/predictor/` immediately on save. That's the day-to-day workflow.

## Cloudflare

`predictor.uzelhub.com` runs through Cloudflare's orange-cloud proxy. The procedure to set up was:

1. Add `predictor` A record pointing to the VPS public IP (178.156.207.242 at time of setup)
2. **Gray cloud** initially — Caddy needs direct port 80 reachability to complete Let's Encrypt's HTTP-01 challenge
3. Reload Caddy → cert provisions in ~10s
4. **Flip to orange cloud** — Cloudflare proxy in front, origin IP hidden, edge caching active

If we ever rotate domains or rebuild, that's the dance.

## Caddy block

Lives at the end of `/etc/caddy/Caddyfile`:

```caddy
predictor.uzelhub.com {
    encode gzip zstd

    root * /opt/predictor_prod/web
    file_server

    log {
        output file /var/log/caddy/predictor.uzelhub.com.log {
            roll_size 10mb
            roll_keep 5
        }
    }
}
```

Mirrors the `blog.uzelhub.com` block's structure. Logs to `/var/log/caddy/predictor.uzelhub.com.log`.

## Git ownership gotcha (encountered + solved 2026-05-31)

`/opt/predictor_prod/` is owned by `claude:claude` (I created it). But the GitHub Action SSHes as `root`. Git refuses to run in a repo dir not owned by the current user unless you explicitly trust it:

```bash
sudo git config --global --add safe.directory /opt/predictor_prod
```

This writes to `/root/.gitconfig`. Without it, deploys fail with `fatal: detected dubious ownership in repository at '/opt/predictor_prod'`. `/opt/predictor_ingest/` already had this set from when the original auto-deploy was wired up.

## Log file ownership gotcha (encountered + solved 2026-05-31)

The Caddy log file at `/var/log/caddy/predictor.uzelhub.com.log` was first created by systemd as `root:root` mode 600 during a failed reload attempt. The `caddy` user couldn't open it. Fix:

```bash
sudo chown caddy:caddy /var/log/caddy/predictor.uzelhub.com.log
sudo systemctl reload caddy
```

The directory `/var/log/caddy/` itself is correctly `caddy:caddy` — the problem only surfaced because the file got pre-created in a botched first attempt. If it happens again on a future fresh setup, same fix.

## Rollback

Prod is just a git checkout. If a bad commit lands on main and breaks prod:

```bash
# Option A: roll back to a known-good commit
sudo -u root git -C /opt/predictor_prod reset --hard <good-sha>
# Caddy serves the new state immediately

# Option B: revert the bad commit on GitHub, push, let auto-deploy do its thing
# (slower but creates a paper trail)
```

Option B is preferred unless prod is actively broken and you need it back now.

## What's NOT in this setup (intentional limits)

- **No build step.** Files in `/opt/predictor_prod/web/` are served as-is. No bundling, no minification, no SSG. If you ever add a build, it goes in `scripts/deploy.sh` between `git checkout` and the existing `mkdir -p` lines.
- **No staging environment.** "Dev" is where you work; "prod" is what users see. There's no intermediate environment. If you want one later, it's another clone at e.g. `/opt/predictor_staging/` plus another Caddy block at `staging.predictor.uzelhub.com`.
- **No health check after deploy.** The Action exits 0 if `deploy.sh` exits 0. Doesn't curl the prod URL to verify. Worth adding later — see the project plan.
- **No notification on deploy success/failure.** Same — possible follow-up.

## Verifying it works

End-to-end test, runnable any time:

```bash
# Prod tree HEAD matches main
git -C /opt/predictor_prod log -1 --oneline

# Prod URL serves
curl -sI https://predictor.uzelhub.com/movers.html?domain=film
# Expect: HTTP/2 200, server: cloudflare, cf-ray: …

# Symlinked data reachable
curl -sI https://predictor.uzelhub.com/data/graphs/live/film/movers.json
# Expect: HTTP/2 200, content-type: application/json
```

Last verified end-to-end: 2026-05-31 with PR #260 (Sprint 15 Movers V1) deploying cleanly.

## Loopback ports table addition

`/opt/_host/README.md` lists the loopback ports. Sprint 18 doesn't add any — Caddy serves predictor as a static site direct from disk, no backend process. The block in the Caddyfile is `root * /opt/predictor_prod/web` + `file_server`. If a future deploy-hook service is ever added (it isn't now — GitHub Actions handles deploys), claim port `3002` next after `uzella-proxy`'s `3001`.
