# systemd units

Install (requires sudo; do this AT the epoch-2 restart, not before —
both domains are known-stale until then and would page immediately):

```bash
sudo cp deploy/systemd/predictor-staleness.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now predictor-staleness.timer
```

Verify: `systemctl list-timers predictor-staleness.timer` and
`journalctl -u predictor-staleness.service`.

When fusion onboards (Sprint 20.18), add it to the watched set:
either edit `DEFAULT_DOMAINS` in `scripts/check_staleness.py` or add
`--domains film,semiconductors,fusion` to the service's ExecStart.
