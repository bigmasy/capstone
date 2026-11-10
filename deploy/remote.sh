#!/usr/bin/env bash
# Runs on the server, started by the forced command of the CI deploy key (deploy/poruch-deploy).
#
#   remote.sh <commit sha> <staging directory>
#
# The staging directory holds what CI sent: docker-compose.yml, docker/, images.env (the image
# references of this commit) and the credentials CI uses to pull them. The script
#   1. logs in to the registry with a throw-away Docker config, so nothing stays on disk;
#   2. dumps the database, keeping the last ten dumps;
#   3. switches the stack to the new images and waits until every service is healthy;
#   4. on a failure, puts the previous images back and exits non-zero, so CI shows a red run;
#   5. removes the images of older releases, keeping the new one and the one before it.
#
# Secrets of the stack stay in ~/apps/poruch/.env; this script never reads or prints them.
set -euo pipefail

sha="$1"
stage="$2"
app="${APP_DIR:-$HOME/apps/poruch}"
backups="${BACKUP_DIR:-$HOME/backups/poruch}"
registry_prefix="$(sed -n 's#^BACKEND_IMAGE=\(.*\)/backend:.*#\1#p' "$stage/images.env")"

log() { printf '[deploy %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
fail() { log "ERROR: $*"; exit 1; }

[[ -n "$registry_prefix" ]] || fail "images.env does not name the backend image"
cd "$app"
# The very first CI release finds no record of a previous one; an empty file keeps compose happy
[[ -f .deploy.env ]] || : > .deploy.env

stack() {
  docker compose --env-file .env --env-file .deploy.env --profile demo "$@"
}

log "release ${sha:0:12}"

# 1. Registry login in a private Docker config that is deleted with the staging directory
export DOCKER_CONFIG="$stage/docker-config"
mkdir -p "$DOCKER_CONFIG"
docker login ghcr.io --username "$(cat "$stage/registry.user")" --password-stdin \
  < "$stage/registry.token" > /dev/null

# 2. Configuration files that the containers mount or read from the repository
install -m 644 "$stage/docker-compose.yml" docker-compose.yml
mkdir -p docker
cp -a "$stage/docker/." docker/

# 3. Database dump before anything changes (skipped on the very first deploy)
if stack ps --status running --services 2> /dev/null | grep -qx db; then
  mkdir -p "$backups"
  dump="$backups/before-${sha:0:12}.sql.gz"
  stack exec -T db sh -c 'pg_dump -U postgres "$POSTGRES_DB"' | gzip > "$dump"
  chmod 600 "$dump"
  log "database dumped to $dump ($(du -h "$dump" | cut -f1))"
  ls -1t "$backups"/before-*.sql.gz | tail -n +11 | xargs -r rm -f
fi

# 4. Switch to the new images; keep the old reference for a rollback
[[ -s .deploy.env ]] && cp .deploy.env .deploy.env.prev || true
cp "$stage/images.env" .deploy.env
chmod 600 .deploy.env

rollback() {
  if [[ -s .deploy.env.prev ]]; then
    log "rolling back to the previous release"
    cp .deploy.env.prev .deploy.env
    stack up -d --remove-orphans --wait --wait-timeout 300 || log "rollback did not come up either"
  else
    log "no previous release to roll back to"
  fi
}

if ! stack pull --quiet; then
  rollback
  fail "could not pull the images"
fi

if ! stack up -d --remove-orphans --wait --wait-timeout 300; then
  stack ps || true
  stack logs --no-color --tail 40 api || true
  rollback
  fail "the new release did not become healthy"
fi

# 5. Old images of this project only; other applications on the host are not touched
keep="$(cat .deploy.env .deploy.env.prev 2> /dev/null | sed 's/^[A-Z_]*=//' || true)"
docker image ls --format '{{.Repository}}:{{.Tag}}' \
  | grep -F "$registry_prefix/" \
  | grep -vxF -f <(printf '%s\n' "$keep") \
  | xargs -r docker image rm > /dev/null 2>&1 || true

log "release ${sha:0:12} is running"
stack ps --format 'table {{.Service}}\t{{.Status}}'
