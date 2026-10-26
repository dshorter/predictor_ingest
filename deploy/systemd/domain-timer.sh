#!/usr/bin/env bash
# domain-timer.sh — turn one domain's daily pipeline timer off or back on.
#
#   sudo /opt/predictor_ingest/deploy/systemd/domain-timer.sh off film            # stop film's daily run
#   sudo /opt/predictor_ingest/deploy/systemd/domain-timer.sh off film --dry-run  # show, change nothing
#   sudo /opt/predictor_ingest/deploy/systemd/domain-timer.sh on film             # restart it later
#
# Why (2026-10-26): the operator shut film down "for now" on 2026-10-20. Film
# is 48% of the funded week's spend and fetches ~29 MB of raw downloads a day
# onto a root disk at 98%. Its credits have been off since 10-13, so every run
# since has fetched, failed at submit, and paged.
#
# "off" disables and stops the timer. It does NOT delete the unit files, the
# database, or the data; "on" is the whole undo. The other domains' timers and
# the staleness pager are checked before and after and must come out unchanged.
#
# Note for "on": the timer has Persistent=true, so enabling it after a gap
# fires one catch-up run immediately. That run spends money if credits are on.

set -euo pipefail

usage() { echo "usage: $0 off|on DOMAIN [--dry-run]" >&2; exit 2; }

ACTION="${1:-}"; DOMAIN="${2:-}"; DRY_RUN=0
[[ "$ACTION" == "off" || "$ACTION" == "on" ]] || usage
[[ -n "$DOMAIN" ]] || usage
for arg in "${@:3}"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        *) echo "unknown argument: $arg" >&2; usage ;;
    esac
done

[[ $EUID -eq 0 ]] || { echo "must run as root (sudo)"; exit 1; }

TIMER="predictor-daily-${DOMAIN}.timer"
SERVICE="predictor-daily@${DOMAIN}.service"
[[ -f "/etc/systemd/system/$TIMER" ]] || { echo "no such timer: /etc/systemd/system/$TIMER" >&2; exit 1; }

# Every other predictor timer, so we can prove they were not touched.
OTHERS=$(systemctl list-unit-files 'predictor-*.timer' --no-legend | awk '{print $1}' | grep -vx "$TIMER" || true)

state() { echo "$(systemctl is-enabled "$1" 2>/dev/null || true)/$(systemctl is-active "$1" 2>/dev/null || true)"; }
snapshot_others() { for t in $OTHERS; do echo "$t $(state "$t")"; done; }

echo "=== $TIMER: $ACTION ==="
BEFORE=$(state "$TIMER")
OTHERS_BEFORE=$(snapshot_others)
echo "before: $TIMER $BEFORE   ($SERVICE: $(systemctl is-active "$SERVICE" 2>/dev/null || true))"
echo "others:"; echo "$OTHERS_BEFORE" | sed 's/^/  /'
echo

if [[ "$ACTION" == "off" ]]; then
    WANT="disabled/inactive"
    # Never cut a run off mid-batch: a submitted batch would be paid for and
    # never collected.
    case "$(systemctl is-active "$SERVICE" 2>/dev/null || true)" in
        active|activating)
            echo "$SERVICE is running right now. Re-run this after it finishes:" >&2
            echo "  journalctl -fu $SERVICE" >&2
            exit 1 ;;
    esac
else
    WANT="enabled/active"
fi

if [[ "$BEFORE" == "$WANT" ]]; then
    echo "already $WANT; nothing to do."
    exit 0
fi

if [[ $DRY_RUN -eq 1 ]]; then
    if [[ "$ACTION" == "off" ]]; then
        echo "[dry-run] would run: systemctl disable --now $TIMER"
        echo "[dry-run] would run: systemctl reset-failed $SERVICE (clears today's failed state)"
    else
        echo "[dry-run] would run: systemctl enable --now $TIMER"
        echo "[dry-run] Persistent=true: this fires one catch-up run of $SERVICE immediately"
    fi
    exit 0
fi

restore() {
    echo "FAILED — putting $TIMER back to $BEFORE" >&2
    if [[ "$BEFORE" == enabled/* ]]; then
        systemctl enable --now "$TIMER" || true
    else
        systemctl disable --now "$TIMER" || true
    fi
    echo "now: $TIMER $(state "$TIMER")" >&2
    exit 1
}
trap restore ERR

if [[ "$ACTION" == "off" ]]; then
    systemctl disable --now "$TIMER"
    systemctl reset-failed "$SERVICE" 2>/dev/null || true
else
    systemctl enable --now "$TIMER"
fi

# Verify: this timer reached the wanted state, and nothing else moved.
AFTER=$(state "$TIMER")
if [[ "$AFTER" != "$WANT" ]]; then
    echo "verify failed: $TIMER is $AFTER, wanted $WANT" >&2
    false
fi
OTHERS_AFTER=$(snapshot_others)
if [[ "$OTHERS_AFTER" != "$OTHERS_BEFORE" ]]; then
    echo "verify failed: another predictor timer changed state:" >&2
    diff <(echo "$OTHERS_BEFORE") <(echo "$OTHERS_AFTER") >&2 || true
    false
fi

trap - ERR

echo "after:  $TIMER $AFTER"
echo "others: unchanged"
echo
systemctl list-timers 'predictor-*' --all --no-pager
echo
if [[ "$ACTION" == "off" ]]; then
    echo "To turn it back on later (fires one catch-up run at once):"
    echo "  sudo $0 on $DOMAIN"
fi
echo "=== done ==="
