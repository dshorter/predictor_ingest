# systemd units — predictor pipeline (Sprint 20.2/20.4)

Six units: the three daily-run timers (the scheduler whose absence caused
the 06-23 semis stall and 07-01 film stall — every prior run was manual),
one shared per-domain service template, and the staleness pager that makes
any future silent stall page within hours instead of being discovered days
later. The three active domains (film, semiconductors, weapons_detection)
launch together — see the operator directive of 2026-07-22.

Install (requires sudo — one block):

```bash
sudo cp deploy/systemd/predictor-daily@.service \
        deploy/systemd/predictor-daily-film.timer \
        deploy/systemd/predictor-daily-semiconductors.timer \
        deploy/systemd/predictor-daily-weapons_detection.timer \
        deploy/systemd/predictor-staleness.service \
        deploy/systemd/predictor-staleness.timer \
        /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now predictor-daily-film.timer \
                           predictor-daily-semiconductors.timer \
                           predictor-daily-weapons_detection.timer \
                           predictor-staleness.timer
```

Verify: `systemctl list-timers 'predictor-*'` and
`journalctl -u predictor-daily@film.service -n 50`.

Schedule: film 06:00, semiconductors 06:45, weapons_detection 07:30
(staggered 45min apart — no batch-API contention, each domain's failure
visible before the next fires), staleness check every 6h.
`Persistent=true` fires missed runs after a reboot. The staleness pager's
active set is DEFAULT_DOMAINS in scripts/check_staleness.py (now
film,semiconductors,weapons_detection).

When fusion onboards (Sprint 20.18): copy predictor-daily-film.timer to
predictor-daily-fusion.timer (pick the next free slot, e.g. 08:15 —
07:30 is now weapons_detection), point its Unit= at
predictor-daily@fusion.service, and add fusion to DEFAULT_DOMAINS in
scripts/check_staleness.py.
