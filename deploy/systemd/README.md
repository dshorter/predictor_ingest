# systemd units — predictor pipeline (Sprint 20.2/20.4)

Four units: the two daily-run timers (the scheduler whose absence caused
the 06-23 semis stall and 07-01 film stall — every prior run was manual),
and the staleness pager that makes any future silent stall page within
hours instead of being discovered days later.

Install (requires sudo — one block):

```bash
sudo cp deploy/systemd/predictor-daily@.service \
        deploy/systemd/predictor-daily-film.timer \
        deploy/systemd/predictor-daily-semiconductors.timer \
        deploy/systemd/predictor-staleness.service \
        deploy/systemd/predictor-staleness.timer \
        /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now predictor-daily-film.timer \
                           predictor-daily-semiconductors.timer \
                           predictor-staleness.timer
```

Verify: `systemctl list-timers 'predictor-*'` and
`journalctl -u predictor-daily@film.service -n 50`.

Schedule: film 06:00, semiconductors 06:45 (staggered — no batch-API
contention, film failures visible before semis fires), staleness check
every 6h. `Persistent=true` fires missed runs after a reboot.

When fusion onboards (Sprint 20.18): copy predictor-daily-film.timer to
predictor-daily-fusion.timer (pick a slot, e.g. 07:30), point its Unit=
at predictor-daily@fusion.service, and add fusion to the staleness
check's --domains (see predictor-staleness.service ExecStart or
DEFAULT_DOMAINS in scripts/check_staleness.py).
