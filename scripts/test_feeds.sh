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

    # Build output and update counters in the current shell (not a subshell)
    BLOCK=""
    BLOCK+="$(printf "%-35s [%s] (%s)\n" "$NAME" "$TAG" "$FTYPE")"$'\n'
    BLOCK+="$(printf "  URL: %s\n" "$URL")"$'\n'

    if [[ "$ENABLED" == "false" ]]; then
        BLOCK+="$(printf "  Skipped (disabled)\n")"$'\n'
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
            BLOCK+="$(printf "  HTTP: %s  Content-Type: %s\n" "$HTTP_CODE" "$CONTENT_TYPE")"$'\n'
            RSS_OK=$((RSS_OK + 1))
        else
            BLOCK+="$(printf "  HTTP: %s  *** PROBLEM ***\n" "$HTTP_CODE")"$'\n'
            RSS_PROBLEMS=$((RSS_PROBLEMS + 1))
        fi
    fi

    printf "%s\n" "$BLOCK" | tee -a "$OUTFILE"
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
    # Authenticate if BSKY_HANDLE + BSKY_APP_PASSWORD are set
    BSKY_AUTH_HEADER=""
    BSKY_ENDPOINT="https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"
    if [[ -n "${BSKY_HANDLE:-}" && -n "${BSKY_APP_PASSWORD:-}" ]]; then
        BSKY_TOKEN=$(curl -s --max-time 10 \
            -H "Content-Type: application/json" \
            -d "{\"identifier\": \"${BSKY_HANDLE}\", \"password\": \"${BSKY_APP_PASSWORD}\"}" \
            "https://bsky.social/xrpc/com.atproto.server.createSession" \
            2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('accessJwt',''))" 2>/dev/null) || BSKY_TOKEN=""
        if [[ -n "$BSKY_TOKEN" ]]; then
            BSKY_AUTH_HEADER="Authorization: Bearer ${BSKY_TOKEN}"
            BSKY_ENDPOINT="https://bsky.social/xrpc/app.bsky.feed.searchPosts"
            printf "  Bluesky: authenticated via BSKY_HANDLE\n" | tee -a "$OUTFILE"
        else
            printf "  Bluesky: auth failed, falling back to public API\n" | tee -a "$OUTFILE"
        fi
    else
        printf "  Bluesky: no credentials (BSKY_HANDLE not set), using public API\n" | tee -a "$OUTFILE"
        printf "  Note: public API may return 403 for search. Set BSKY_HANDLE + BSKY_APP_PASSWORD.\n" | tee -a "$OUTFILE"
    fi

    {
        printf "%-35s\n" "Bluesky Search API"
        printf "  Endpoint: %s\n" "$BSKY_ENDPOINT"
    } | tee -a "$OUTFILE"

    BSKY_OK=0
    BSKY_FAIL=0
    while IFS= read -r KW; do
        ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$KW'))")
        BSKY_URL="${BSKY_ENDPOINT}?q=${ENCODED}&limit=3&sort=latest"

        # Build curl args (with or without auth header)
        CURL_AUTH_ARGS=()
        if [[ -n "$BSKY_AUTH_HEADER" ]]; then
            CURL_AUTH_ARGS=(-H "$BSKY_AUTH_HEADER")
        fi

        # Retry up to 3 times with backoff for transient failures
        BSKY_RESP=""
        for ATTEMPT in 1 2 3; do
            BSKY_HTTP=$(curl -s -o /tmp/bsky_resp.json -w "%{http_code}" \
                --max-time 15 \
                -H "User-Agent: predictor-ingest/0.1 (feed-test)" \
                "${CURL_AUTH_ARGS[@]}" \
                "$BSKY_URL" 2>/dev/null) || BSKY_HTTP="000"
            if [[ "$BSKY_HTTP" == "200" ]]; then
                BSKY_RESP=$(cat /tmp/bsky_resp.json)
                break
            elif [[ "$BSKY_HTTP" == "429" || "$BSKY_HTTP" == "000" || "$BSKY_HTTP" == "5"* ]]; then
                # Retryable: rate limit, network error, server error
                if [[ $ATTEMPT -lt 3 ]]; then
                    DELAY=$((ATTEMPT * 2))
                    printf "  Keyword '%s': HTTP %s, retry %d in %ds...\n" "$KW" "$BSKY_HTTP" "$ATTEMPT" "$DELAY" >&2
                    sleep "$DELAY"
                fi
            else
                break  # Non-retryable error (4xx other than 429)
            fi
        done

        if [[ "$BSKY_HTTP" == "200" ]] && echo "$BSKY_RESP" | grep -q '"posts"'; then
            # grep -o can return exit 1 if no matches; guard with || true
            POST_COUNT=$(echo "$BSKY_RESP" | grep -o '"uri"' | wc -l || true)
            printf "  Keyword %-30s %d posts (HTTP %s)\n" "'${KW}':" "$POST_COUNT" "$BSKY_HTTP"
            BSKY_OK=$((BSKY_OK + 1))
        elif [[ "$BSKY_HTTP" == "200" ]] && echo "$BSKY_RESP" | grep -q '"error"'; then
            ERROR_MSG=$(echo "$BSKY_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('message','unknown'))" 2>/dev/null || echo "parse error")
            printf "  Keyword %-30s ERROR: %s\n" "'${KW}':" "$ERROR_MSG"
            BSKY_FAIL=$((BSKY_FAIL + 1))
        elif [[ "$BSKY_HTTP" != "200" && "$BSKY_HTTP" != "000" ]]; then
            printf "  Keyword %-30s HTTP %s *** PROBLEM ***\n" "'${KW}':" "$BSKY_HTTP"
            BSKY_FAIL=$((BSKY_FAIL + 1))
        else
            printf "  Keyword %-30s FAIL (unreachable after 3 attempts)\n" "'${KW}':"
            BSKY_FAIL=$((BSKY_FAIL + 1))
        fi
    done <<< "$BSKY_KEYWORDS" > >(tee -a "$OUTFILE")
    rm -f /tmp/bsky_resp.json

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
    # Authenticate if REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET are set
    REDDIT_AUTH_HEADER=""
    REDDIT_API_BASE="https://www.reddit.com"
    if [[ -n "${REDDIT_CLIENT_ID:-}" && -n "${REDDIT_CLIENT_SECRET:-}" ]]; then
        REDDIT_TOKEN=$(curl -s --max-time 10 \
            -u "${REDDIT_CLIENT_ID}:${REDDIT_CLIENT_SECRET}" \
            -d "grant_type=client_credentials" \
            -H "User-Agent: predictor-ingest/0.1 (feed-test; non-commercial research)" \
            "https://www.reddit.com/api/v1/access_token" \
            2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null) || REDDIT_TOKEN=""
        if [[ -n "$REDDIT_TOKEN" ]]; then
            REDDIT_AUTH_HEADER="Authorization: Bearer ${REDDIT_TOKEN}"
            REDDIT_API_BASE="https://oauth.reddit.com"
            printf "  Reddit: authenticated via OAuth (100 req/min)\n" | tee -a "$OUTFILE"
        else
            printf "  Reddit: OAuth token request failed, using unauthenticated API\n" | tee -a "$OUTFILE"
        fi
    else
        printf "  Reddit: no credentials (REDDIT_CLIENT_ID not set)\n" | tee -a "$OUTFILE"
        printf "  Note: unauthenticated access may return 403. See https://www.reddit.com/wiki/api/\n" | tee -a "$OUTFILE"
    fi

    {
        printf "%-35s\n" "Reddit API"
        printf "  Endpoint: %s/r/{subreddit}/new.json\n" "$REDDIT_API_BASE"
    } | tee -a "$OUTFILE"

    REDDIT_OK=0
    REDDIT_FAIL=0
    while IFS= read -r SUB; do
        [[ -z "$SUB" ]] && continue

        REDDIT_URL="${REDDIT_API_BASE}/r/${SUB}/new.json?limit=3&raw_json=1"

        # Build curl args (with or without auth header)
        RCURL_AUTH_ARGS=(-H "User-Agent: predictor-ingest/0.1 (feed-test; non-commercial research)")
        if [[ -n "$REDDIT_AUTH_HEADER" ]]; then
            RCURL_AUTH_ARGS+=(-H "$REDDIT_AUTH_HEADER")
        fi

        # Retry up to 3 times with backoff for transient/rate-limit failures
        R_HTTP_CODE="000"
        REDDIT_RESP=""
        for ATTEMPT in 1 2 3; do
            R_HTTP_CODE=$(curl -s -o /tmp/reddit_resp.json -w "%{http_code}" \
                --max-time 15 \
                "${RCURL_AUTH_ARGS[@]}" \
                "$REDDIT_URL" 2>/dev/null) || R_HTTP_CODE="000"
            if [[ "$R_HTTP_CODE" == "200" ]]; then
                REDDIT_RESP=$(cat /tmp/reddit_resp.json)
                break
            elif [[ "$R_HTTP_CODE" == "429" || "$R_HTTP_CODE" == "000" || "$R_HTTP_CODE" == "5"* ]]; then
                if [[ $ATTEMPT -lt 3 ]]; then
                    DELAY=$((ATTEMPT * 2))
                    printf "  r/%s: HTTP %s, retry %d in %ds...\n" "$SUB" "$R_HTTP_CODE" "$ATTEMPT" "$DELAY" >&2
                    sleep "$DELAY"
                fi
            else
                break
            fi
        done

        if [[ "$R_HTTP_CODE" == "200" ]]; then
            R_COUNT=$(echo "$REDDIT_RESP" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    posts = d.get('data', {}).get('children', [])
    print(len(posts))
except:
    print(0)
" 2>/dev/null) || R_COUNT="0"
            printf "  r/%-20s OK — %s posts returned (HTTP %s)\n" "$SUB" "$R_COUNT" "$R_HTTP_CODE"
            REDDIT_OK=$((REDDIT_OK + 1))
        elif [[ "$R_HTTP_CODE" != "000" ]]; then
            printf "  r/%-20s HTTP %s *** PROBLEM ***\n" "$SUB" "$R_HTTP_CODE"
            REDDIT_FAIL=$((REDDIT_FAIL + 1))
        else
            printf "  r/%-20s FAIL (unreachable after 3 attempts)\n" "$SUB"
            REDDIT_FAIL=$((REDDIT_FAIL + 1))
        fi

        # Be polite — Reddit rate limits aggressively
        sleep 1
    done <<< "$REDDIT_SUBS" > >(tee -a "$OUTFILE")
    rm -f /tmp/reddit_resp.json

    echo "" | tee -a "$OUTFILE"
else
    echo "  No Reddit feeds configured or all disabled." | tee -a "$OUTFILE"
fi

# ===== Summary =====
{
    echo "================================"
    echo "Summary"
    echo "  Section 1: RSS/Atom feeds — ${RSS_OK} OK, ${RSS_PROBLEMS} problems, ${RSS_DISABLED} disabled"
    echo "  Section 2: Bluesky keyword search — ${BSKY_OK:-0} OK, ${BSKY_FAIL:-0} problems"
    echo "  Section 3: Reddit subreddit JSON — ${REDDIT_OK:-0} OK, ${REDDIT_FAIL:-0} problems"
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
