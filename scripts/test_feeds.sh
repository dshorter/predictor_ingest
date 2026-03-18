#!/usr/bin/env bash
# Test all feed URLs from a domain's feeds.yaml and upload results as a GitHub gist.
# Usage: ./scripts/test_feeds.sh [domain]
# Default domain: film
#
# Requires: curl, gh (GitHub CLI, authenticated)
set -euo pipefail

DOMAIN="${1:-film}"
FEEDS_FILE="domains/${DOMAIN}/feeds.yaml"
OUTDIR="data/feed_test_$(date +%Y%m%d_%H%M%S)"
OUTFILE="$OUTDIR/feed_health_${DOMAIN}.txt"

if [[ ! -f "$FEEDS_FILE" ]]; then
    echo "ERROR: $FEEDS_FILE not found"
    exit 1
fi

mkdir -p "$OUTDIR"

# Write header
{
    echo "Feed Health Check — domain: ${DOMAIN}"
    echo "Run: $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "File: ${FEEDS_FILE}"
    echo "================================"
    echo ""
} | tee "$OUTFILE"

# Counters
TOTAL=0
OK=0
PROBLEMS=0
DISABLED_COUNT=0

# Extract feed entries: name, url, enabled status
# Simple grep-based parsing (no yaml library needed)
paste -d'|' \
    <(grep -E '^\s+- name:' "$FEEDS_FILE" | sed 's/.*name: *"\?\([^"]*\)"\?.*/\1/') \
    <(grep -E '^\s+url:' "$FEEDS_FILE" | sed 's/.*url: *"\?\([^"]*\)"\?.*/\1/') \
    <(grep -E '^\s+enabled:' "$FEEDS_FILE" | sed 's/.*enabled: *//') \
| while IFS='|' read -r name url enabled; do
    TOTAL=$((TOTAL + 1))

    # Status indicator
    if [[ "$enabled" == "false" ]]; then
        tag="DISABLED"
        DISABLED_COUNT=$((DISABLED_COUNT + 1))
    else
        tag="enabled"
    fi

    printf "%-35s [%s]\n" "$name" "$tag"
    printf "  URL: %s\n" "$url"

    # Test the URL
    http_code=$(curl -sL -o /dev/null -w "%{http_code}" \
        --max-time 15 \
        -H "User-Agent: predictor-ingest/0.1 (feed-test)" \
        "$url" 2>/dev/null || echo "FAIL")

    if [[ "$http_code" == "200" ]]; then
        # Check content-type in same request
        content_type=$(curl -sL -o /dev/null -w "%{content_type}" \
            --max-time 15 \
            -H "User-Agent: predictor-ingest/0.1 (feed-test)" \
            "$url" 2>/dev/null || echo "unknown")
        printf "  HTTP: %s  Content-Type: %s\n" "$http_code" "$content_type"
        OK=$((OK + 1))
    else
        printf "  HTTP: %s  *** PROBLEM ***\n" "$http_code"
        PROBLEMS=$((PROBLEMS + 1))
    fi
    printf "\n"
done | tee -a "$OUTFILE"

# Summary
{
    echo "================================"
    echo "Summary: tested feeds from ${FEEDS_FILE}"
    echo "  See results above for per-feed details."
    echo ""
    echo "Feeds returning non-200 or FAIL need investigation."
} | tee -a "$OUTFILE"

echo ""
echo "Results saved to: $OUTFILE"

# --- Upload as gist ---
if ! command -v gh &>/dev/null; then
    echo "ERROR: gh (GitHub CLI) not found. Share $OUTFILE manually."
    exit 1
fi

if ! gh auth status &>/dev/null; then
    echo "ERROR: gh not authenticated. Run 'gh auth login' first."
    exit 1
fi

echo "Creating gist..."
GIST_URL=$(gh gist create --public -d "predictor_ingest ${DOMAIN} feed health $(date '+%Y-%m-%d %H:%M')" "$OUTFILE")
echo "Gist created: $GIST_URL"
echo ""
echo "Done. Share the gist URL above."
