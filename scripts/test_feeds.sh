#!/usr/bin/env bash
# Test all feed URLs AND API endpoints from a domain's feeds.yaml,
# then upload results as a GitHub gist.
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
    echo "SECTION 1: RSS / Atom Feeds"
    echo "--------------------------------"
    echo ""
} | tee "$OUTFILE"

# Extract feed entries: name, url, enabled status, type
# Simple grep-based parsing (no yaml library needed)
paste -d'|' \
    <(grep -E '^\s+- name:' "$FEEDS_FILE" | sed 's/.*name: *"\?\([^"]*\)"\?.*/\1/') \
    <(grep -E '^\s+url:' "$FEEDS_FILE" | sed 's/.*url: *"\?\([^"]*\)"\?.*/\1/') \
    <(grep -E '^\s+enabled:' "$FEEDS_FILE" | sed 's/.*enabled: *//') \
    <(grep -E '^\s+type:' "$FEEDS_FILE" | sed 's/.*type: *//') \
| while IFS='|' read -r name url enabled ftype; do
    # Skip non-RSS types (tested in Section 2)
    ftype=$(echo "$ftype" | tr -d '[:space:]')
    if [[ "$ftype" == "bluesky" || "$ftype" == "reddit" ]]; then
        continue
    fi

    # Status indicator
    if [[ "$enabled" == "false" ]]; then
        tag="DISABLED"
    else
        tag="enabled"
    fi

    printf "%-35s [%s]\n" "$name" "$tag"
    printf "  URL: %s\n" "$url"

    # Single request: grab both http_code and content_type
    read -r http_code content_type < <(curl -sL -o /dev/null \
        -w "%{http_code} %{content_type}" \
        --max-time 15 \
        -H "User-Agent: predictor-ingest/0.1 (feed-test)" \
        "$url" 2>/dev/null || echo "FAIL unknown")

    if [[ "$http_code" == "200" ]]; then
        printf "  HTTP: %s  Content-Type: %s\n" "$http_code" "$content_type"
    else
        printf "  HTTP: %s  *** PROBLEM ***\n" "$http_code"
    fi
    printf "\n"
done | tee -a "$OUTFILE"

# --- Section 2: API endpoints (Bluesky, Reddit) ---
{
    echo ""
    echo "SECTION 2: API Endpoints"
    echo "--------------------------------"
    echo ""
} | tee -a "$OUTFILE"

# Bluesky public search API
{
    printf "%-35s\n" "Bluesky Public Search API"
    printf "  Endpoint: https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts\n"

    # Test with a simple query
    BSKY_RESP=$(curl -s --max-time 15 \
        -H "User-Agent: predictor-ingest/0.1 (feed-test)" \
        "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=indie+film&limit=3" \
        2>/dev/null) || BSKY_RESP="FAIL"

    if echo "$BSKY_RESP" | grep -q '"posts"'; then
        POST_COUNT=$(echo "$BSKY_RESP" | grep -o '"uri"' | wc -l)
        printf "  Status: OK — returned %d posts for test query 'indie film'\n" "$POST_COUNT"
    elif echo "$BSKY_RESP" | grep -q '"error"'; then
        ERROR_MSG=$(echo "$BSKY_RESP" | grep -o '"message":"[^"]*"' | head -1)
        printf "  Status: ERROR — %s\n" "$ERROR_MSG"
    else
        printf "  Status: FAIL — could not reach endpoint\n"
    fi

    # Test domain-specific keywords from bluesky.py defaults
    for kw in "Atlanta film production" "Trilith Studios" "Southeast film"; do
        ENCODED=$(printf '%s' "$kw" | sed 's/ /+/g')
        KW_RESP=$(curl -s --max-time 10 \
            -H "User-Agent: predictor-ingest/0.1 (feed-test)" \
            "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=${ENCODED}&limit=3&sort=latest" \
            2>/dev/null) || KW_RESP="FAIL"
        KW_COUNT=$(echo "$KW_RESP" | grep -o '"uri"' | wc -l)
        printf "  Keyword '%s': %d posts\n" "$kw" "$KW_COUNT"
    done
    printf "\n"
} | tee -a "$OUTFILE"

# Reddit JSON API
{
    printf "%-35s\n" "Reddit JSON API"
    printf "  Endpoint: https://www.reddit.com/r/{subreddit}/new.json\n"

    # Test subreddits relevant to film domain
    for sub in "Atlanta" "Filmmakers" "boxoffice" "indiefilm"; do
        REDDIT_HTTP=$(curl -sL -o /dev/null -w "%{http_code}" \
            --max-time 15 \
            -H "User-Agent: predictor-ingest/0.1 (feed-test; non-commercial research)" \
            "https://www.reddit.com/r/${sub}/new.json?limit=3&raw_json=1" \
            2>/dev/null || echo "FAIL")

        if [[ "$REDDIT_HTTP" == "200" ]]; then
            # Count posts in response
            REDDIT_RESP=$(curl -s --max-time 15 \
                -H "User-Agent: predictor-ingest/0.1 (feed-test; non-commercial research)" \
                "https://www.reddit.com/r/${sub}/new.json?limit=3&raw_json=1" \
                2>/dev/null) || REDDIT_RESP=""
            R_COUNT=$(echo "$REDDIT_RESP" | grep -o '"kind": "t3"' | wc -l)
            printf "  r/%-20s HTTP: %s  Posts: %d\n" "$sub" "$REDDIT_HTTP" "$R_COUNT"
        else
            printf "  r/%-20s HTTP: %s  *** PROBLEM ***\n" "$sub" "$REDDIT_HTTP"
        fi
        # Be polite — Reddit rate limits aggressively
        sleep 1
    done
    printf "\n"
} | tee -a "$OUTFILE"

# Reddit OAuth check (if credentials are set)
{
    if [[ -n "${REDDIT_CLIENT_ID:-}" && -n "${REDDIT_CLIENT_SECRET:-}" ]]; then
        printf "Reddit OAuth: credentials found (REDDIT_CLIENT_ID set)\n"
        TOKEN_HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
            --max-time 10 \
            -u "${REDDIT_CLIENT_ID}:${REDDIT_CLIENT_SECRET}" \
            -d "grant_type=client_credentials" \
            -H "User-Agent: predictor-ingest/0.1 (feed-test)" \
            "https://www.reddit.com/api/v1/access_token" \
            2>/dev/null || echo "FAIL")
        printf "  OAuth token request: HTTP %s\n" "$TOKEN_HTTP"
    else
        printf "Reddit OAuth: no credentials (REDDIT_CLIENT_ID not set)\n"
        printf "  Using unauthenticated JSON API (10 req/min limit)\n"
    fi
    printf "\n"
} | tee -a "$OUTFILE"

# --- Summary ---
{
    echo "================================"
    echo "Summary"
    echo "  Section 1: RSS/Atom feeds from ${FEEDS_FILE}"
    echo "  Section 2: Bluesky search API + Reddit JSON API"
    echo ""
    echo "Feeds/endpoints returning non-200 or FAIL need investigation."
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
GIST_URL=$(gh gist create --public -d "predictor_ingest ${DOMAIN} feed+API health $(date '+%Y-%m-%d %H:%M')" "$OUTFILE")
echo "Gist created: $GIST_URL"
echo ""
echo "Done. Share the gist URL above."
