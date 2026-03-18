#!/usr/bin/env bash
# Test all feed URLs AND API endpoints from a domain's feeds.yaml,
# then upload results as a GitHub gist.
# Usage: ./scripts/test_feeds.sh [domain]
# Default domain: film
#
# Requires: curl, python3 (with PyYAML), gh (GitHub CLI, authenticated)
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

# Parse feeds.yaml with Python (reliable, handles all feed types)
FEED_JSON=$(python3 -c "
import yaml, json, sys
with open('$FEEDS_FILE') as f:
    data = yaml.safe_load(f)
feeds = data.get('feeds', [])
json.dump(feeds, sys.stdout)
")

FEED_COUNT=$(echo "$FEED_JSON" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")

# ===== Section 1: RSS / Atom Feeds =====
{
    echo "SECTION 1: RSS / Atom Feeds"
    echo "--------------------------------"
    echo ""
} | tee -a "$OUTFILE"

RSS_TOTAL=0
RSS_OK=0
RSS_PROBLEMS=0
RSS_DISABLED=0

# Iterate RSS/atom feeds
for i in $(seq 0 $((FEED_COUNT - 1))); do
    ENTRY=$(echo "$FEED_JSON" | python3 -c "
import json, sys
feeds = json.load(sys.stdin)
f = feeds[$i]
ftype = f.get('type', 'rss')
if ftype not in ('rss', 'atom'):
    sys.exit(0)
print(f.get('name', 'unnamed'))
print(f.get('url', ''))
print(str(f.get('enabled', True)).lower())
print(ftype)
")

    # Skip non-RSS entries (Python exits silently for bluesky/reddit)
    [[ -z "$ENTRY" ]] && continue

    NAME=$(echo "$ENTRY" | sed -n '1p')
    URL=$(echo "$ENTRY" | sed -n '2p')
    ENABLED=$(echo "$ENTRY" | sed -n '3p')
    FTYPE=$(echo "$ENTRY" | sed -n '4p')

    RSS_TOTAL=$((RSS_TOTAL + 1))

    if [[ "$ENABLED" == "false" ]]; then
        TAG="DISABLED"
        RSS_DISABLED=$((RSS_DISABLED + 1))
    else
        TAG="enabled"
    fi

    {
        printf "%-35s [%s] (%s)\n" "$NAME" "$TAG" "$FTYPE"
        printf "  URL: %s\n" "$URL"

        if [[ "$ENABLED" == "false" ]]; then
            printf "  Skipped (disabled)\n\n"
        else
            # Single request: grab both http_code and content_type
            CURL_OUT=$(curl -sL -o /dev/null \
                -w "%{http_code} %{content_type}" \
                --max-time 15 \
                -H "User-Agent: predictor-ingest/0.1 (feed-test)" \
                "$URL" 2>/dev/null) || CURL_OUT="FAIL unknown"
            HTTP_CODE=$(echo "$CURL_OUT" | awk '{print $1}')
            CONTENT_TYPE=$(echo "$CURL_OUT" | awk '{print $2}')

            if [[ "$HTTP_CODE" == "200" ]]; then
                printf "  HTTP: %s  Content-Type: %s\n" "$HTTP_CODE" "$CONTENT_TYPE"
                RSS_OK=$((RSS_OK + 1))
            else
                printf "  HTTP: %s  *** PROBLEM ***\n" "$HTTP_CODE"
                RSS_PROBLEMS=$((RSS_PROBLEMS + 1))
            fi
            printf "\n"
        fi
    } | tee -a "$OUTFILE"
done

{
    echo "RSS/Atom summary: ${RSS_OK} OK, ${RSS_PROBLEMS} problems, ${RSS_DISABLED} disabled (of ${RSS_TOTAL} total)"
    echo ""
} | tee -a "$OUTFILE"

# ===== Section 2: Bluesky API =====
{
    echo ""
    echo "SECTION 2: API Endpoints"
    echo "--------------------------------"
    echo ""
} | tee -a "$OUTFILE"

# Collect Bluesky keywords from feeds.yaml
BSKY_KEYWORDS=$(echo "$FEED_JSON" | python3 -c "
import json, sys
feeds = json.load(sys.stdin)
for f in feeds:
    if f.get('type') == 'bluesky' and f.get('enabled', True):
        for kw in f.get('keywords', []):
            print(kw)
")

if [[ -n "$BSKY_KEYWORDS" ]]; then
    {
        printf "%-35s\n" "Bluesky Public Search API"
        printf "  Endpoint: https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts\n"
    } | tee -a "$OUTFILE"

    while IFS= read -r KW; do
        ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$KW'))")
        BSKY_RESP=$(curl -s --max-time 15 \
            -H "User-Agent: predictor-ingest/0.1 (feed-test)" \
            "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=${ENCODED}&limit=3&sort=latest" \
            2>/dev/null) || BSKY_RESP="FAIL"

        if echo "$BSKY_RESP" | grep -q '"posts"'; then
            POST_COUNT=$(echo "$BSKY_RESP" | grep -o '"uri"' | wc -l)
            printf "  Keyword %-30s %d posts\n" "'${KW}':" "$POST_COUNT"
        elif echo "$BSKY_RESP" | grep -q '"error"'; then
            ERROR_MSG=$(echo "$BSKY_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('message','unknown'))" 2>/dev/null || echo "parse error")
            printf "  Keyword %-30s ERROR: %s\n" "'${KW}':" "$ERROR_MSG"
        else
            printf "  Keyword %-30s FAIL (unreachable)\n" "'${KW}':"
        fi
    done <<< "$BSKY_KEYWORDS" | tee -a "$OUTFILE"

    echo "" | tee -a "$OUTFILE"
else
    echo "  No Bluesky feeds configured or all disabled." | tee -a "$OUTFILE"
fi

# ===== Section 3: Reddit API =====
REDDIT_SUBS=$(echo "$FEED_JSON" | python3 -c "
import json, sys
feeds = json.load(sys.stdin)
for f in feeds:
    if f.get('type') == 'reddit' and f.get('enabled', True):
        print(f.get('subreddit', ''))
")

if [[ -n "$REDDIT_SUBS" ]]; then
    {
        printf "%-35s\n" "Reddit JSON API"
        printf "  Endpoint: https://www.reddit.com/r/{subreddit}/new.json\n"
    } | tee -a "$OUTFILE"

    while IFS= read -r SUB; do
        [[ -z "$SUB" ]] && continue

        REDDIT_RESP=$(curl -s --max-time 15 \
            -H "User-Agent: predictor-ingest/0.1 (feed-test; non-commercial research)" \
            "https://www.reddit.com/r/${SUB}/new.json?limit=3&raw_json=1" \
            2>/dev/null) || REDDIT_RESP="FAIL"

        REDDIT_HTTP=$(echo "$REDDIT_RESP" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    posts = d.get('data', {}).get('children', [])
    print(f'200 {len(posts)}')
except:
    print('FAIL 0')
" 2>/dev/null) || REDDIT_HTTP="FAIL 0"

        R_STATUS=$(echo "$REDDIT_HTTP" | awk '{print $1}')
        R_COUNT=$(echo "$REDDIT_HTTP" | awk '{print $2}')

        if [[ "$R_STATUS" == "200" ]]; then
            printf "  r/%-20s OK — %s posts returned\n" "$SUB" "$R_COUNT"
        else
            printf "  r/%-20s *** PROBLEM ***\n" "$SUB"
        fi

        # Be polite — Reddit rate limits aggressively
        sleep 1
    done <<< "$REDDIT_SUBS" | tee -a "$OUTFILE"

    echo "" | tee -a "$OUTFILE"

    # Reddit OAuth check
    {
        if [[ -n "${REDDIT_CLIENT_ID:-}" && -n "${REDDIT_CLIENT_SECRET:-}" ]]; then
            printf "  Reddit OAuth: credentials found (REDDIT_CLIENT_ID set)\n"
            TOKEN_HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
                --max-time 10 \
                -u "${REDDIT_CLIENT_ID}:${REDDIT_CLIENT_SECRET}" \
                -d "grant_type=client_credentials" \
                -H "User-Agent: predictor-ingest/0.1 (feed-test)" \
                "https://www.reddit.com/api/v1/access_token" \
                2>/dev/null || echo "FAIL")
            printf "  OAuth token request: HTTP %s\n" "$TOKEN_HTTP"
        else
            printf "  Reddit OAuth: no credentials (REDDIT_CLIENT_ID not set)\n"
            printf "  Using unauthenticated JSON API (10 req/min limit)\n"
        fi
    } | tee -a "$OUTFILE"

    echo "" | tee -a "$OUTFILE"
else
    echo "  No Reddit feeds configured or all disabled." | tee -a "$OUTFILE"
fi

# ===== Summary =====
{
    echo "================================"
    echo "Summary"
    echo "  Section 1: RSS/Atom feeds — ${RSS_OK} OK, ${RSS_PROBLEMS} problems, ${RSS_DISABLED} disabled"
    echo "  Section 2: Bluesky keyword search API"
    echo "  Section 3: Reddit subreddit JSON API"
    echo ""
    echo "Entries returning FAIL or PROBLEM need investigation."
} | tee -a "$OUTFILE"

echo ""
echo "Results saved to: $OUTFILE"

# --- Upload as gist ---
if ! command -v gh &>/dev/null; then
    echo "NOTE: gh (GitHub CLI) not found. Share $OUTFILE manually."
    exit 0
fi

if ! gh auth status &>/dev/null; then
    echo "NOTE: gh not authenticated. Run 'gh auth login' first."
    exit 0
fi

echo "Creating gist..."
GIST_URL=$(gh gist create --public -d "predictor_ingest ${DOMAIN} feed+API health $(date '+%Y-%m-%d %H:%M')" "$OUTFILE")
echo "Gist created: $GIST_URL"
echo ""
echo "Done. Share the gist URL above."
