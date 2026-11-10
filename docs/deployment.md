# Continuous deployment

Every push to `main` is checked and, when every check passes, deployed to the server. Nothing is built on the server and no source code is kept there.

```
push to main
  -> lint, unit, postgis, audit, docker, stack, frontend, e2e   (.github/workflows/ci.yml)
  -> deploy job:
       build backend, frontend, proxy and certs images, publish them to ghcr.io under the commit hash
       send the release (compose file, docker/, image references) to the server over SSH
       server (deploy/remote.sh): dump the database, pull, start, wait for the health checks
       roll back to the previous images when the new ones do not become healthy
  -> check https://<site>/ready, the landing page and the news endpoint from outside
```

A push to any other branch, a pull request and the weekly schedule run the checks only. A failed check stops the deploy; a failed deploy leaves the previous release running and turns the run red.

To redeploy a commit, re-run the `deploy` job of its workflow run. To roll back, re-run the `deploy` job of an earlier green run, or revert the commit.

## What runs where

| Piece | Where | What it does |
| --- | --- | --- |
| `deploy` job | GitHub Actions, environment `production` | builds and publishes the images, sends the release |
| `deploy/poruch-deploy` | server, `~/bin/poruch-deploy` | the only command the CI key may run: accepts `deploy <40-hex commit hash>`, unpacks the archive from standard input, runs `remote.sh` |
| `deploy/remote.sh` | travels with every release | login, dump, pull, start, health wait, rollback, cleanup of old images |
| `~/apps/poruch/.env` | server only | secrets of the stack; never read by CI, never overwritten |
| `~/apps/poruch/.deploy.env` | server | image references of the running release (`.deploy.env.prev` is the one before) |
| `~/backups/poruch` | server | one database dump per release, the last ten kept |

The registry token is the short-lived `GITHUB_TOKEN` of the run. It is handed to the server only for the pull, written into a private Docker configuration that is deleted at the end, and is useless once the run finishes.

## One-time setup

1. **Deploy key.** Make a key pair used for nothing else: `ssh-keygen -t ed25519 -N '' -C poruch-ci -f poruch-ci`.
2. **Server.** Copy `deploy/poruch-deploy` to `~/bin/poruch-deploy` of the deploy user (`chmod 755`) and add one line to `~/.ssh/authorized_keys`, with the public key from step 1:

   ```
   command="/home/deploy/bin/poruch-deploy",restrict ssh-ed25519 AAAA... poruch-ci
   ```

   `restrict` switches off port forwarding, agent forwarding and a terminal; `command=` makes the key run the script whatever the client asks for.
3. **GitHub.** Create the environment `production` (Settings, Environments; add required reviewers there if a deploy should wait for a click) with:

   | Name | Kind | Value |
   | --- | --- | --- |
   | `DEPLOY_HOST` | secret | address of the server |
   | `DEPLOY_USER` | secret | the deploy user |
   | `DEPLOY_SSH_KEY` | secret | the private key from step 1 |
   | `DEPLOY_KNOWN_HOSTS` | secret | the server's line from `ssh-keyscan -t ed25519 <host>`, checked against a trusted source |
   | `SITE_URL` | variable | public address, such as `https://porych.life` |

4. **Packages.** The first run creates the four packages (`backend`, `frontend`, `proxy`, `certs`) under the repository. They are private by default; the run needs nothing more.

## Limits

- The server keeps the demo profile (`--profile demo`) it ran before CI took over, so each release also runs the idempotent demo seed.
- A migration that cannot be undone is not rolled back with the images. The dump taken before the release is the way back: `gunzip -c ~/backups/poruch/before-<hash>.sql.gz | docker compose exec -T db psql -U postgres <database>` after restoring into an empty database.
- Branch protection (required checks before a merge to `main`) is a repository setting and is not part of this change.
