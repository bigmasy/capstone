#!/usr/bin/env bash
# Waits until a started stack is ready.
#
#   docker compose --profile demo up --build --detach
#   docker/wait-stack.sh
#
# Ready means: every service that keeps running is running and, when it has a health check,
# healthy; every one-shot service (migrate, ranker-train, seed, certs) has exited with status 0.
# A one-shot that failed, or a service that did not get there in time, fails the script and
# prints the state of each service.
#
# Why not `docker compose up --wait`: it reports a one-shot container that has already finished
# as "exited (0)" and fails, depending on whether the container ended before or after compose
# looked. The stack job and the end-to-end job of CI hit that now and then.
#
# Environment (all optional):
#   COMPOSE        compose command with its options (default "docker compose --profile demo")
#   WAIT_TIMEOUT   seconds to wait (default 300)
#   ONE_SHOT       space-separated names of the one-shot services
set -euo pipefail

compose="${COMPOSE:-docker compose --profile demo}"
timeout="${WAIT_TIMEOUT:-300}"
one_shot=" ${ONE_SHOT:-migrate ranker-train seed certs} "
deadline=$((SECONDS + timeout))

while true; do
  pending=""
  failed=""
  report=""
  while IFS='|' read -r service state health code; do
    [[ -n "$service" ]] || continue
    report+="  $service: $state${health:+, $health}${code:+, exit $code}"$'\n'
    if [[ "$one_shot" == *" $service "* ]]; then
      case "$state" in
        exited) [[ "$code" == 0 ]] || failed+=" $service(exit $code)" ;;
        dead) failed+=" $service(dead)" ;;
        *) pending+=" $service($state)" ;;
      esac
    else
      case "$state" in
        running) [[ -z "$health" || "$health" == healthy ]] || pending+=" $service($health)" ;;
        *) pending+=" $service($state)" ;;
      esac
    fi
  done < <($compose ps -a --format '{{.Service}}|{{.State}}|{{.Health}}|{{.ExitCode}}')

  if [[ -n "$failed" ]]; then
    printf 'wait-stack: failed:%s\n%s' "$failed" "$report" >&2
    exit 1
  fi
  if [[ -z "$pending" && -n "$report" ]]; then
    printf 'wait-stack: ready\n%s' "$report"
    exit 0
  fi
  if ((SECONDS >= deadline)); then
    printf 'wait-stack: not ready after %ss, waiting for:%s\n%s' "$timeout" "$pending" "$report" >&2
    exit 1
  fi
  sleep 3
done
