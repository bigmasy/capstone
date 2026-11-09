# Poruch ("Nearby")

A web platform that helps veterans find training partners for adaptive sport by what people can do, not by diagnosis. It is the engineering part of my master's thesis (Neoversity, MSc in Computer Science, Software Engineering). The explanatory note is a separate document, written in Ukrainian.

Status: a working MVP with synthetic demo data. There are no real users, and the ranking model shipped with the demo is trained on synthetic data only (see [Limitations](#limitations)).

## What it does

- **Profile without a diagnosis.** A user lists sports with a self-rated level, a usual intensity, a training area and, only with explicit consent, how independently they do a few everyday actions (a 0 to 4 self-assessment) and which equipment they use.
- **Coarse location.** The place is chosen from a list of cities and districts or on a map. Only the centre of a grid cell of about 4 x 4 km is stored. Other users see a district and a distance band (under 5, 5-10, 10-25, over 25 km), never a coordinate.
- **Ranked partners with an explanation.** A feed of candidates scored by sport, distance, intensity and functional compatibility. Every card says where the points come from. The functional criterion is shown as a level (low, medium, high) only. A learned ranker (LightGBM) can reorder the feed; when no usable model artifact exists, the weighted baseline is used.
- **Invitations.** A pending, accepted, declined, cancelled or expired invitation. A contact is shown to the other side only after the invitation is accepted, and both sides need a contact to send or accept one.
- **Delete everything with one button.** Removing the account removes the profile, the functional data and the invitations.

## Architecture

A modular monolith. The dependency direction is enforced by 10 import-linter contracts.

```
api (routes, schemas)  ->  services (use cases)  ->  repository / database
                                  |
                              domain (pure logic: scoring, privacy rules, invitation state machine)
                                  |
                              ranking (LightGBM, model artifact, read only)
```

- Backend: Python 3.12, FastAPI, SQLAlchemy 2 (async) with asyncpg, Alembic, Pydantic v2, Argon2id password hashes, short-lived JWT access tokens, PostgreSQL 16 with PostGIS 3.4.
- Frontend: React 19, TypeScript (strict), Vite, React Router, Redux Toolkit with RTK Query, Formik and Yup, CSS Modules. The interface is in Ukrainian and follows WCAG 2.1 AA, checked automatically.
- Infrastructure: Docker Compose, an nginx reverse proxy with TLS, rate limits, security headers and a content security policy. Containers run without root, with all capabilities dropped and a read-only file system. The database has separate roles for migrations and for the API.
- The model artifact is a LightGBM text model with a manifest and a SHA-256 checksum. No object serialization is used.

The OpenAPI contract is generated from the application (`python -m app.tools.export_openapi`) and kept in [docs/api/openapi.json](docs/api/openapi.json). The client builds its types from it with `npm run gen:api`.

## Run it

You need Docker with Compose.

```sh
cp .env.example .env        # then fill in every value, see the comments in that file
docker compose --profile demo up --build
```

Open <https://localhost:8443> and accept the warning once (a self-signed development certificate). The `demo` profile adds 200 synthetic accounts named `demo-0001@example.invalid` and so on; their shared password is the `SEED_PASSWORD` you set. Without `--profile demo` you start with an empty database and register yourself.

The one-shot `ranker-train` service trains the demo ranker on synthetic data when the stack starts. Only the proxy publishes a port, and by default only on 127.0.0.1. The header of [docker-compose.yml](docker-compose.yml) lists every variable.

## Develop and test

Backend (from `backend/`):

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt -r requirements-ml.txt
ruff check . && ruff format --check . && mypy app && lint-imports
pytest -q
```

Tests that need PostgreSQL with PostGIS are skipped unless `TEST_DATABASE_URL` is set.

Frontend (from `frontend/`, Node 22 or newer):

```sh
npm ci
npm run gen:api     # builds src/api/schema.d.ts from docs/api/openapi.json; not committed
npm run lint && npm run typecheck && npm test && npm run build
```

End-to-end and accessibility checks run in a real browser against a started stack with the demo profile:

```sh
npx playwright install chromium
E2E_DEMO_PASSWORD=<the SEED_PASSWORD> npm run e2e
```

Continuous integration ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs lint, type checks, tests on Python 3.11 and 3.12, the PostGIS migrations, image builds, a dependency audit, a smoke test of the whole stack and the end-to-end suite.

## Offline experiment

The thesis compares the learned ranker with the weighted baselines on synthetic data. The code lives in `backend/app/experiment`, and the protocol is part of the explanatory note.

```sh
cd backend
python -m app.experiment h1 --config full --world interactions   # also: additive, baseline_like
python -m app.experiment h2 --config full
python -m app.experiment train --config demo --out ./model       # the demo model
```

Runs are deterministic. Each result file records the seeds, the library versions and a fingerprint of the generated population.

## Limitations

- The data are synthetic. The experiment shows how the methods behave in a simulated world, not how they would behave with real people.
- The ranking model in the demo is trained on synthetic data. The product does not yet collect real feedback and does not retrain.
- Accessibility was checked automatically and by scripted scenarios in Chromium. A screen reader and a real phone were not used.
- There are no usability tests with people and no industrial load tests.
- Not implemented: chat, e-mail notifications, password recovery, identity or veteran-status verification, calendar export. The district list covers Kyiv only.
- The map loads tiles from OpenStreetMap only when the user asks for a map; the tile server then sees the viewed area and the IP address.

## Project layout

```
backend/    API, domain, ranking, experiment code, migrations, tests
frontend/   React client, end-to-end tests
docker/     proxy, database role setup, stack smoke test
docs/       API contract, work plan
```

## License

No license has been chosen yet; all rights are reserved until one is added.
