#!/usr/bin/env bash
# Smoke test of a running stack, through the reverse proxy only.
#
#   docker compose --profile demo up --build -d --wait
#   docker/smoke.sh              # the whole smoke test
#   docker/smoke.sh --fallback   # only the ranker fallback check (see below)
#
# Environment (all optional):
#   SMOKE_HOST     name the proxy is reached by (default localhost; must match PUBLIC_HOSTNAME)
#   HTTPS_PORT     host port of the HTTPS listener (default 8443)
#   HTTP_PORT      host port of the HTTP listener (default 8080)
#   API_DIRECT_PORT  host port where the API must NOT answer (default 8000)
#   COMPOSE_PROJECT_NAME  when set (and docker is available), the script also checks that the
#                  api, db and frontend containers of that project publish no host port
#   SEED_PASSWORD  password of the demo accounts. When set (stack started with the demo profile),
#                  the script signs in as SMOKE_DEMO_USER and checks that the feed is ordered
#                  by the learned ranker; without it that section is skipped
#   SMOKE_DEMO_USER  demo account to sign in as (default demo-0001@example.invalid)
#   SMOKE_COMPOSE  compose command for --fallback (default "docker compose"); add the options
#                  that the stack was started with, for example
#                  "docker compose --env-file my.env -p myproject --profile demo"
#
# --fallback: proves that the API keeps serving when the model artifact is gone. It checks that
# the feed is learned, empties the ranker_model volume, restarts the api container, checks that
# the feed is now ordered by the baseline (rank_source "baseline", no rank_influence), then
# trains the model again, restarts the api and checks that the feed is learned once more. It
# needs docker, python3 and SEED_PASSWORD, and does not use up the rate limits.
#
# The development certificate is self-signed, so curl runs with -k. The script registers a
# throw-away account on the example.invalid domain, and finishes by exhausting the login,
# registration and profile-edit rate limits of the calling address. Those budgets refill at
# 5 to 6 requests per minute, so a second run right after the first waits for them; it retries
# on 429 where that is expected.
set -euo pipefail

host="${SMOKE_HOST:-localhost}"
https_port="${HTTPS_PORT:-8443}"
http_port="${HTTP_PORT:-8080}"
direct_port="${API_DIRECT_PORT:-8000}"
base="https://${host}:${https_port}"
api="${base}/api/v1"

failures=0
body_file="$(mktemp)"
headers_file="$(mktemp)"
trap 'rm -f "$body_file" "$headers_file"' EXIT

pass() { printf 'ok    %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }

# check DESCRIPTION EXPECTED ACTUAL
check() {
    if [ "$2" = "$3" ]; then pass "$1"; else fail "$1 (expected $2, got $3)"; fi
}

# request METHOD URL [CURL ARGS...]: stores body and headers, prints the status code.
# Never fails the script on a transport error; a status of 000 is returned instead.
request() {
    local method="$1" url="$2"
    shift 2
    curl -sk -o "$body_file" -D "$headers_file" -w '%{http_code}' --max-time 20 \
        -X "$method" "$@" "$url" || true
}

# request_retry METHOD URL [CURL ARGS...]: like request, but waits out a rate limit left over
# from an earlier run (the budgets refill within a minute).
request_retry() {
    local status attempt=0
    while :; do
        status="$(request "$@")"
        if [ "$status" != "429" ] || [ "$attempt" -ge 8 ]; then
            printf '%s' "$status"
            return
        fi
        attempt=$((attempt + 1))
        sleep 13
    done
}

header() { grep -i "^$1:" "$headers_file" | head -n 1 | tr -d '\r' || true; }

has_header() {
    if [ -n "$(header "$2")" ]; then pass "$1: $2 present"; else fail "$1: $2 missing"; fi
}

json_field() { sed -n "s/.*\"$1\":\"\([^\"]*\)\".*/\1/p" "$body_file" | head -n 1; }

finish() {
    echo
    if [ "$failures" -eq 0 ]; then
        echo "smoke test passed"
    else
        echo "smoke test FAILED: $failures check(s)"
        exit 1
    fi
}

# demo_login: signs in as the demo account and sets $demo_header; fails the script without it.
demo_login() {
    local email="${SMOKE_DEMO_USER:-demo-0001@example.invalid}" status
    status="$(request_retry POST "$api/auth/login" -H 'Content-Type: application/json' \
        -d "{\"email\":\"${email}\",\"password\":\"${SEED_PASSWORD}\"}")"
    check "demo login" 200 "$status"
    demo_header="Authorization: Bearer $(json_field access_token)"
}

# check_feed EXPECTED: fetches the demo feed and checks its source, influence and fields.
# EXPECTED is "learned" or "baseline". The python helper reads the stored body and prints one
# line per violation.
check_feed() {
    local expected="$1" status problems
    status="$(request GET "$api/matches?limit=20" -H "$demo_header")"
    check "GET /matches for the demo account" 200 "$status"
    problems="$(python3 -I - "$expected" "$body_file" <<'PY'
import json, sys

expected, path = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as handle:
    feed = json.load(handle)
items = feed.get("items", [])
if not items:
    print("the feed is empty")
levels = {"raises", "neutral", "lowers"}
criteria = {"sport", "distance", "functional", "intensity"}


def keys(value):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key
            yield from keys(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from keys(inner)


for key in set(keys(feed)):
    if "score" in key.lower():
        print(f"a raw score field is exposed: {key}")
for item in items:
    if item.get("rank_source") != expected:
        print(f"rank_source is {item.get('rank_source')!r}, expected {expected!r}")
        break
for item in items:
    influence = item.get("rank_influence")
    if expected == "learned":
        if not isinstance(influence, dict) or set(influence) != criteria:
            print("rank_influence does not hold the four criteria")
            break
        if not set(influence.values()) <= levels:
            print("rank_influence holds a value outside raises, neutral, lowers")
            break
    elif influence is not None:
        print("rank_influence is present although the baseline ordered the feed")
        break
PY
    )"
    if [ -z "$problems" ]; then
        pass "feed is ordered by the $expected ranker, influence and fields are as expected"
    else
        while IFS= read -r line; do fail "feed: $line"; done <<<"$problems"
    fi
}

# wait_ready: waits until the application answers /ready through the proxy again.
wait_ready() {
    local attempt
    for attempt in $(seq 1 30); do
        if [ "$(request GET "$base/ready")" = "200" ]; then return 0; fi
        sleep 2
    done
    fail "the application did not become ready after the restart"
}

if [ "${1:-}" = "--fallback" ]; then
    : "${SEED_PASSWORD:?SEED_PASSWORD must be set (the demo accounts are needed)}"
    compose="${SMOKE_COMPOSE:-docker compose}"
    echo "== ranker fallback"
    demo_login
    check_feed learned
    # shellcheck disable=SC2086
    $compose run --rm --no-deps --entrypoint sh ranker-train \
        -c 'rm -f /var/lib/ranker/model.txt /var/lib/ranker/manifest.json' >/dev/null
    # shellcheck disable=SC2086
    $compose restart api >/dev/null
    wait_ready
    check_feed baseline
    # shellcheck disable=SC2086
    $compose run --rm --no-deps ranker-train >/dev/null
    # shellcheck disable=SC2086
    $compose restart api >/dev/null
    wait_ready
    check_feed learned
    finish
    exit 0
fi

echo "== transport"
status="$(request GET "$base/")"
check "HTTPS answers on $base" 200 "$status"
grep -q 'id="root"' "$body_file" && pass "the application shell is served" || fail "the application shell is missing"

if curl -s -o /dev/null --max-time 10 "$base/" 2>/dev/null; then
    fail "the development certificate should not be trusted by default"
else
    pass "certificate is self-signed (rejected without -k)"
fi

status="$(curl -s -o /dev/null -D "$headers_file" -w '%{http_code}' --max-time 10 "http://${host}:${http_port}/some/path?q=1" || true)"
check "HTTP redirects" 301 "$status"
check "redirect target is the HTTPS origin" "location: https://${host}:${https_port}/some/path?q=1" \
    "$(header location | tr '[:upper:]' '[:lower:]')"

echo "== routing"
status="$(request GET "$base/health")"
check "GET /health" 200 "$status"
check "/health body" '{"status":"ok"}' "$(tr -d ' ' <"$body_file")"
status="$(request GET "$base/ready")"
check "GET /ready (database reachable)" 200 "$status"
status="$(request GET "$base/profile/edit")"
check "history fallback serves the shell for a client route" 200 "$status"
status="$(request GET "$api/nothing-here")"
check "unknown API path is a JSON 404, not the shell" 404 "$status"
grep -q '<html' "$body_file" && fail "unknown API path returned HTML" || pass "unknown API path does not return HTML"
status="$(request GET "$api/taxonomy")"
check "GET /api/v1/taxonomy" 200 "$status"

echo "== security headers"
request GET "$base/" >/dev/null
for name in Content-Security-Policy X-Content-Type-Options X-Frame-Options Referrer-Policy Permissions-Policy; do
    has_header "shell" "$name"
done
csp="$(header content-security-policy)"
case "$csp" in
    *"script-src 'self';"*) pass "shell: script-src is 'self'" ;;
    *) fail "shell: script-src is not 'self'" ;;
esac
if printf '%s' "$csp" | grep -Eq "script-src[^;]*unsafe-inline"; then
    fail "shell: inline scripts are allowed"
else
    pass "shell: no inline scripts allowed"
fi
# The map tiles come from one named host, and its usage policy needs the site origin as Referer.
case "$csp" in
    *"img-src 'self' data: https://tile.openstreetmap.org;"*) pass "shell: img-src allows only self, data: and the OpenStreetMap tile host" ;;
    *) fail "shell: img-src is not the expected list" ;;
esac
check "shell: Referrer-Policy sends the origin to other origins" \
    "referrer-policy: strict-origin-when-cross-origin" "$(header referrer-policy | tr '[:upper:]' '[:lower:]')"
case "$(header permissions-policy)" in
    *"geolocation=(self)"*) pass "shell: geolocation is allowed for this origin only" ;;
    *) fail "shell: Permissions-Policy does not allow geolocation for this origin" ;;
esac
request GET "$api/taxonomy" >/dev/null
for name in Content-Security-Policy X-Content-Type-Options Cache-Control; do
    has_header "api" "$name"
done
check "api: Referrer-Policy stays no-referrer" \
    "referrer-policy: no-referrer" "$(header referrer-policy | tr '[:upper:]' '[:lower:]')"
if header server | grep -Eq '[0-9]'; then fail "Server header discloses a version: $(header server)"; else pass "Server header carries no version"; fi
[ -z "$(header x-powered-by)" ] && pass "no X-Powered-By header" || fail "X-Powered-By is present"

echo "== account flow through the proxy"
email="smoke-$(date +%s)-${RANDOM}@example.invalid"
password="smoke-password-$(date +%s)"
status="$(request_retry POST "$api/auth/register" -H 'Content-Type: application/json' \
    -d "{\"email\":\"${email}\",\"password\":\"${password}\"}")"
check "register" 201 "$status"
status="$(request_retry POST "$api/auth/login" -H 'Content-Type: application/json' \
    -d "{\"email\":\"${email}\",\"password\":\"${password}\"}")"
check "login" 200 "$status"
token="$(json_field access_token)"
[ -n "$token" ] && pass "an access token was issued" || fail "no access token in the login answer"

profile='{"display_name":"Smoke test","intensity":3,"latitude":50.4501,"longitude":30.5234,"sports":[{"sport":"swimming","skill":"beginner"}],"capabilities":[{"category":"mobility_lower","level":2}],"functional_data_consent":true}'
auth_header="Authorization: Bearer ${token}"
status="$(request_retry PUT "$api/profiles/me" -H 'Content-Type: application/json' -H "$auth_header" -d "$profile")"
check "PUT /profiles/me" 200 "$status"
status="$(request GET "$api/profiles/me" -H "$auth_header")"
check "GET /profiles/me" 200 "$status"
if grep -Eq '"(latitude|longitude|area_lat|area_lon)"' "$body_file"; then
    fail "the own-profile answer contains coordinates"
else
    pass "the own-profile answer contains no coordinates"
fi
status="$(request GET "$api/profiles/me")"
check "profile without a token is refused" 401 "$status"

if [ -n "${SEED_PASSWORD:-}" ]; then
    echo "== learned ranking (demo accounts)"
    demo_login
    check_feed learned
else
    echo "== learned ranking skipped: SEED_PASSWORD is not set"
fi

echo "== request size limit"
big="$(head -c 70000 /dev/zero | tr '\0' 'a')"
status="$(request POST "$api/auth/login" -H 'Content-Type: application/json' -d "{\"email\":\"${big}\",\"password\":\"x\"}")"
check "a 70 KB body is rejected by the proxy" 413 "$status"

echo "== isolation"
if curl -s -o /dev/null --max-time 3 "http://127.0.0.1:${direct_port}/health" 2>/dev/null; then
    fail "something answers on 127.0.0.1:${direct_port}; the API must not publish a host port"
else
    pass "the API does not answer on 127.0.0.1:${direct_port}"
fi
if command -v docker >/dev/null 2>&1 && [ -n "${COMPOSE_PROJECT_NAME:-}" ]; then
    for service in api db frontend; do
        ports="$(docker ps --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME}" \
            --filter "label=com.docker.compose.service=${service}" --format '{{.Ports}}' || true)"
        # A published port is shown as host:port->container/tcp; an exposed one has no arrow.
        case "$ports" in
            *"->"*) fail "the $service container publishes a host port: $ports" ;;
            *) pass "the $service container publishes no host port" ;;
        esac
    done
fi

# first_429 METHOD URL COUNT [CURL ARGS...]: position of the first 429 among COUNT requests
# sent back to back, 0 when none; also fails when a non-429 answer is unexpected.
first_429() {
    local method="$1" url="$2" count="$3" i status
    shift 3
    for ((i = 1; i <= count; i++)); do
        status="$(request "$method" "$url" "$@")"
        if [ "$status" = "429" ]; then
            printf '%s' "$i"
            return
        fi
    done
    printf '0'
}

in_range() { [ "$1" -ge "$2" ] && [ "$1" -le "$3" ]; }

echo "== rate limits (the budgets of this address are used up from here on)"
# Edits of the own profile: 6 per minute, burst 5, so the sixth request in a row (counting the
# PUT above as the first) is the last one served. One token can refill meanwhile.
position="$(first_429 PUT "$api/profiles/me" 10 -H 'Content-Type: application/json' -H "$auth_header" -d "$profile")"
if in_range "$position" 4 7; then pass "PUT /profiles/me is limited (429 on request $position of the burst)"; else fail "PUT /profiles/me limit: first 429 at $position (expected 4 to 7)"; fi
check "the limit answer is JSON" "application/json" "$(header content-type | sed 's/^[^:]*: *//; s/;.*//' | tr 'A-Z' 'a-z')"
[ -n "$(header retry-after)" ] && pass "the 429 answer carries Retry-After" || fail "the 429 answer has no Retry-After"

wrong='{"email":"nobody@example.invalid","password":"not-the-password"}'
position="$(first_429 POST "$api/auth/login" 10 -H 'Content-Type: application/json' -d "$wrong")"
if in_range "$position" 4 8; then pass "POST /auth/login is limited (429 on request $position)"; else fail "login limit: first 429 at $position (expected 4 to 8)"; fi

# An invalid body is answered 422 by the API but still counts against the budget.
position="$(first_429 POST "$api/auth/register" 10 -H 'Content-Type: application/json' -d '{}')"
if in_range "$position" 4 8; then pass "POST /auth/register is limited (429 on request $position)"; else fail "register limit: first 429 at $position (expected 4 to 8)"; fi

finish
