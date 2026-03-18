#!/usr/bin/env bash
# Test all feed URLs from a domain's feeds.yaml
# Usage: ./scripts/test_feeds.sh [domain]
# Default domain: film

set -euo pipefail

DOMAIN="${1:-film}"
FEEDS_FILE="domains/${DOMAIN}/feeds.yaml"

if [[ ! -f "$FEEDS_FILE" ]]; then
    echo "ERROR: $FEEDS_FILE not found"
    exit 1
fi

echo "Testing feeds from $FEEDS_FILE"
echo "================================"
echo ""

# Extract feed entries: name, url, enabled status
# Simple grep-based parsing (no yaml library needed)
paste -d'|' \
    <(grep -E '^\s+- name:' "$FEEDS_FILE" | sed 's/.*name: *"\?\([^"]*\)"\?.*/\1/') \
    <(grep -E '^\s+url:' "$FEEDS_FILE" | sed 's/.*url: *"\?\([^"]*\)"\?.*/\1/') \
    <(grep -E '^\s+enabled:' "$FEEDS_FILE" | sed 's/.*enabled: *//') \
| while IFS='|' read -r name url enabled; do
    # Status indicator
    if [[ "$enabled" == "false" ]]; then
        tag="DISABLED"
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
        # Check if response looks like XML/RSS
        content_type=$(curl -sL -o /dev/null -w "%{content_type}" \
            --max-time 15 \
            -H "User-Agent: predictor-ingest/0.1 (feed-test)" \
            "$url" 2>/dev/null || echo "unknown")
        printf "  HTTP: %s  Content-Type: %s\n" "$http_code" "$content_type"
    else
        printf "  HTTP: %s  *** PROBLEM ***\n" "$http_code"
    fi
    echo ""
done

echo "================================"
echo "Done. Feeds returning non-200 or FAIL need investigation."
