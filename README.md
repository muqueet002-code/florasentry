# FloraSentry V2

**AI-assisted crop health decision support for farmers, extension workers and agriculture officials.**

| | |
|---|---|
| **SIH Problem Statement** | SIH26131 — Early detection and management of crop diseases and pest infestations |
| **Theme** | Agriculture, FoodTech & Rural Development |
| **Team** | ASTRIX (S83) |
| **Target geography** | Maharashtra, India (MVP) |
| **Current status** | **Phases 1–10 complete — SIH demo-ready.** See [what's implemented](#phase-1-scope) and [what is *not* built](#not-implemented-yet). |

---

## What FloraSentry V2 is

A field-oriented platform that turns a single crop-health observation into a
geographically and contextually informed decision-support signal, by combining:

> AI detection + real field observations + weather + crop context + GIS + risk
> forecasting + expert validation + IPM advisory + follow-up monitoring

Its guiding principle, from the PRD:

> **Detection is not the destination. Decision support is.**

Two rules follow from that, and they are enforced in the schema rather than left to
convention:

1. **An AI prediction is never a confirmed diagnosis.** A database check constraint
   makes it impossible to record an accepted diagnosis on an observation that no expert
   has confirmed or corrected.
2. **Simulated data is never presented as real.** `source_type` is `NOT NULL` with no
   default on every observation-bearing table, so an unattributed record cannot be
   written at all.

---

## ⚠️ Read this before demoing

The full farmer → AI/risk → map → expert validation → advisory → follow-up → official
dashboard flow is implemented and tested end to end (see
[the end-to-end test](backend/tests/integration/test_end_to_end.py)).

One thing is deliberately **not** shipped: **no AI model weights**. This repository
never trained or evaluated a model, so `ai_model_registry` has no active row. This is
not a missing feature so much as an honest limitation stated up front — every
observation degrades exactly the way the product design requires: it is stored, its
weather/risk/GIS/advisory/follow-up pipeline runs in full, and it is routed to
`PENDING_REVIEW` for a human rather than a fabricated result (`GET /health` and
`GET /ai/models/active` report `AI_MODEL_UNAVAILABLE` honestly). An expert can still
confirm/correct any case by hand, so the review → advisory → follow-up → dashboard
story is fully demonstrable without one.

Run `python scripts/seed_demo_data.py` for a ready-made set of clearly-labelled
`DEMO_SIMULATION` examples (low/medium risk, an expert-corrected case, a hotspot
cluster, a worsening follow-up) plus three demo logins — see
[Demo data](#demo-data) below.

A handful of things remain genuinely unresolved product/legal decisions rather than
code gaps — a map tile provider (TRD D16), an authoritative crop/disease vocabulary
(TRD D2/D3), and human-reviewed Hindi/Marathi translations (TRD D10) — each is called
out where it applies rather than worked around.

There is no accuracy figure anywhere in this repository, because no model has been
trained or evaluated.

---

## Architecture

A **modular monolith** (PRD §18, TRD §4.1): one FastAPI process, internally partitioned,
plus one background worker sharing the same image. No microservices.

```
┌──────────────────────────────────────────────────────────────┐
│  React SPA (role-routed: farmer / expert / official / admin) │
│  React 19 · TypeScript · Vite · Tailwind v4 · TanStack Query │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTPS/JSON · JWT Bearer
┌───────────────────────────▼──────────────────────────────────┐
│  FastAPI application                                          │
│    routers  → services → repositories → PostgreSQL/PostGIS    │
│    adapters (model runner, weather provider, storage) behind  │
│    interfaces, resolved from configuration                    │
└───────────────────────────┬──────────────────────────────────┘
                            │
              ┌─────────────▼─────────────┐
              │  PostgreSQL 16 + PostGIS 3 │
              └────────────────────────────┘
```

**Strict layering.** Routers hold no business logic. Services execute no SQL.
Repositories hold no business rules. External integrations sit behind adapters. This is
what makes later phases additive rather than a rewrite.

Full technical detail: [`FloraSentry_V2_TRD.md`](FloraSentry_V2_TRD.md).
Product detail: [`FloraSentry_V2_PRD-2.md`](FloraSentry_V2_PRD-2.md).

---

## Repository structure

```
florasentry/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI app factory, middleware, trace IDs
│   │   ├── api/
│   │   │   ├── deps.py          DI: db session, current user, RBAC guards
│   │   │   └── v1/              routers (auth, catalog, fields, health, planned)
│   │   ├── core/                config, security, rbac, errors, responses, logging
│   │   ├── db/                  session, declarative base + mixins, seeds
│   │   ├── models/              SQLAlchemy ORM (18 tables)
│   │   ├── schemas/             Pydantic v2 request/response models
│   │   ├── repositories/        ALL SQL and PostGIS access
│   │   ├── services/            business logic (auth, fields, audit)
│   │   ├── ai/ gis/ risk/       module boundaries for Phases 2–4 (empty)
│   │   ├── advisory/            module boundary for Phase 6 (empty)
│   │   ├── integrations/        weather + storage adapter boundaries (empty)
│   │   └── workers/             worker entrypoint; no jobs registered yet
│   ├── alembic/versions/        migrations (0001_initial)
│   ├── scripts/                 seed_reference_data, create_admin_user
│   └── tests/                   unit · api · integration (124 tests)
├── frontend/
│   └── src/
│       ├── api/                 axios client, envelope unwrapping, endpoints
│       ├── app/                 router, guards, providers
│       ├── components/          ui · provenance · layout
│       ├── features/            auth · farmer · expert · official · admin
│       ├── i18n/locales/        en · hi · mr
│       └── stores/              auth, language (Zustand)
├── docker-compose.yml
└── .github/workflows/ci.yml
```

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Docker + Compose | any recent | The only hard requirement for the Docker path |
| Python | 3.11+ | For running the backend directly |
| Node.js | 20+ | For running the frontend directly |

The backend is developed against Python 3.11 (pinned in the Dockerfile) and has been
verified on 3.14 locally.

---

## Quick start (Docker)

```bash
git clone <repository-url> && cd florasentry
cp backend/.env.example backend/.env      # then edit backend/.env
docker compose up -d
```

Compose runs migrations automatically before the backend starts. Then seed the
reference vocabulary and create an admin:

```bash
docker compose exec backend python scripts/seed_reference_data.py
docker compose exec -it backend python scripts/create_admin_user.py \
  --email admin@example.org --name "Site Admin"
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API docs (Swagger) | http://localhost:8000/docs |
| Health | http://localhost:8000/health |

**Port conflicts.** If 5432, 8000 or 5173 are already in use, set `POSTGRES_PORT`,
`BACKEND_PORT` or `FRONTEND_PORT` in a root `.env` file.

---

## Demo data

For a live walkthrough without manually creating accounts and observations first, seed
a small set of clearly-marked `DEMO_SIMULATION` examples:

```bash
docker compose exec backend env DEMO_PASSWORD='<choose-one>' python scripts/seed_demo_data.py
```

This is idempotent (safe to re-run) and never hardcodes a password — it reads
`DEMO_PASSWORD`, same as `create_admin_user.py` reads `ADMIN_PASSWORD`. It creates:

- three logins (`+911000000001` farmer, `+911000000002` extension worker,
  `+911000000003` official — same password for all three) so a demo can switch roles
  without touching the database;
- a normal/low-risk observation, an elevated/medium-risk one, and an
  expert-**CORRECTED** case (produced via a real review decision, not faked);
- a small cluster of nearby reports that forms a real hotspot under the same PostGIS
  clustering the map uses;
- a follow-up submitted with outcome `WORSENED`, so the official dashboard's
  "needing attention" list has something to show.

Every risk score here comes from calling the real `RuleBasedRiskEngine` against
synthetic-but-labelled inputs — never an invented number — and no AI model is
registered or faked. See the script's own docstring for the full reasoning, including
why an isolated demo observation cannot honestly reach a HIGH risk score. All of it is
excluded from every real query by default (`include_demo=false` everywhere) and
visibly marked wherever it does show up (the fuchsia striped provenance styling).

---

## Running locally (without Docker)

### Database

```bash
docker compose up -d db
```

A PostGIS-enabled PostgreSQL is required. A plain `postgres` image will **not** work:
the schema uses geometry columns, spatial indexes and PostGIS check constraints.

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # Windows;  source .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"

cp .env.example .env            # set DATABASE_URL and JWT_SECRET
alembic upgrade head
python scripts/seed_reference_data.py

uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

---

## Database

PostgreSQL 16 + PostGIS 3.4. Conventions: UUID primary keys, `TIMESTAMPTZ` in UTC,
soft delete on user-owned entities, native enums, `NUMERIC` for measurements, and
SRID 4326 for every geometry column.

**18 tables:** `users`, `refresh_tokens`, `farmers`, `fields`, `admin_regions`, `crops`,
`crop_varieties`, `growth_stages`, `disease_pest_catalog`, `agent_crops`, `symptoms`,
`agent_symptoms`, `observations`, `observation_images`, `ai_model_registry`,
`ai_predictions`, `data_sources`, `audit_logs`.

The AI tables are created but **empty** — they exist so Phase 2 adds a pipeline, not a
schema migration.

### Migrations

```bash
cd backend
alembic upgrade head            # apply
alembic downgrade base          # roll back (verified reversible)
alembic current                 # show current revision
alembic check                   # fail if the ORM has drifted from the migrations
alembic revision -m "message"   # new migration
```

Never modify the database outside a migration. `alembic check` runs in CI to catch drift.

---

## Running tests

### Backend

```bash
cd backend
pytest                                  # all
pytest tests/unit tests/api             # no database needed
pytest -m integration                   # requires PostGIS
```

Two tiers:

- **Unit / API** run with no database — they prove the app boots and reports its own
  degradation when the database is unreachable.
- **Integration** (`@pytest.mark.integration`) need real PostGIS and **skip** (not fail)
  when none is reachable. SQLite is never used as a substitute: it would silently not
  enforce the geometry types and check constraints that carry the product guarantees.

Point them at a specific database with `TEST_DATABASE_URL`.

### Frontend

```bash
cd frontend
npm test          # vitest (includes the translation-completeness check)
npm run lint
npm run typecheck
npm run build
```

The i18n test **fails the build** if `hi` or `mr` is missing a key that `en` has, so a
language cannot silently rot.

---

## Authentication

JWT access tokens (30 min) plus rotating refresh tokens (14 days) with reuse detection:
presenting an already-rotated token revokes the entire chain and writes an audit entry.
Passwords are hashed with Argon2id; only the SHA-256 hash of a refresh token is stored.

**Roles:** `FARMER`, `EXTENSION_WORKER`, `LAB_EXPERT`, `OFFICIAL`, `ADMIN`.

Self-registration always creates a `FARMER`. Privileged accounts are created by an
admin — there is no `role` field on the registration endpoint.

The permission matrix lives in `backend/app/core/rbac.py`, is served by `GET /roles`,
and is asserted directly by the test suite, so the documentation and the enforcement
cannot drift apart. **Frontend route guards are UX only**; every rule is enforced
server-side.

```bash
# register, then log in
curl -X POST localhost:8000/api/v1/auth/register -H 'Content-Type: application/json' \
  -d '{"full_name":"Test Farmer","phone":"+919876500011","password":"a-good-password"}'

curl -X POST localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"identifier":"+919876500011","password":"a-good-password"}'
```

---

## API conventions

Every response uses one envelope:

```jsonc
// success
{ "success": true, "data": {…}, "meta": { "trace_id": "…", "timestamp": "…" } }

// error — message_key lets the client localise instead of showing a server string
{ "success": false,
  "error": { "code": "FIELD_NOT_FOUND", "message": "…",
             "message_key": "errors.field_not_found", "details": [], "retriable": false },
  "meta": { "trace_id": "…" } }
```

Every response carries `X-Trace-Id`, which also appears in every log line and audit row
for that request — one id resolves the whole story of a reported problem.

---

## Phase 1 scope

**Implemented and working (Phases 1–9, hardened in Phase 10):**

- Repository structure, modular-monolith layering, strict layer boundaries
- FastAPI application: DI, config validation, structured JSON logging with redaction,
  exception hierarchy, standard envelope, CORS, trace IDs
- PostgreSQL + PostGIS with Alembic migrations (applied, reversible, drift-checked)
- Authentication: register, login, refresh rotation with reuse detection, logout,
  change password, `/auth/me`
- RBAC: five roles, a permission matrix, reusable guards, ownership/district scoping
  applied in the repository layer
- Fields CRUD, reference data (crops, growth stages, agent catalogue), audit logging
- **Observation pipeline** (Phase 2): image upload, validation, the `ModelRunner`
  interface with a confidence gate, honest `AI_MODEL_UNAVAILABLE` degradation
- **Weather + risk** (Phase 3): a live weather integration and a deterministic,
  explainable, configurable rule-based risk engine
- **GIS** (Phase 4): bbox/nearby spatial queries, PostGIS DBSCAN hotspot detection
- **Expert review** (Phase 5): a priority-ordered queue, confirm/correct/reject —
  never overwrites the original AI prediction
- **Advisory** (Phase 6): a deterministic, configurable IPM-oriented rule engine,
  localised into en/hi/mr
- **Follow-up** (Phase 7): scheduling, outcome tracking, reusing the same
  observation pipeline for a follow-up's own image/context/risk
- **Official dashboard** (Phase 8): overview metrics, disease/pest summary, priority
  areas (from the same hotspot engine), recent activity — all read from data the
  above modules already produced, all demo-data-aware
- A demo-data seed script (`scripts/seed_demo_data.py`) covering every scenario type
  below, clearly marked `DEMO_SIMULATION` throughout
- React SPA: routing for all five roles, guards, API client with single-flight token
  refresh, auth store, provenance components, loading/empty/error/degraded states,
  en/hi/mr localisation
- Docker development environment, CI pipeline, a full backend + frontend automated
  test suite (see [Running tests](#running-tests))

---

## Not implemented yet

Each of these has a route boundary returning **HTTP 501** and a UI screen that says so.
Nothing here returns fabricated data. All are deliberately out of scope for the SIH
prototype, not overlooked.

| Capability | Notes |
|---|---|
| Farmer/expert landing "dashboards" beyond their existing home screens | Their real functionality (fields/check-health, review queue) is already reachable via navigation; a second summary screen was judged unnecessary |
| Official trends/priority-zone screens beyond the dashboard's own priority-areas list | Would duplicate the dashboard; out of scope |
| Notifications, offline capture | Not started |
| Admin user/catalogue/data-source management UI | RBAC and the underlying tables exist; no admin UI was built |
| A trained AI model | No weights ship with this repository — see [the section above](#️-read-this-before-demoing) |

---

## Implementation decisions

Where the TRD left something open or its suggestion did not hold up, the choice and its
reason are recorded here and in the relevant source file.

| Decision | Choice | Why |
|---|---|---|
| Password hashing | `argon2-cffi` instead of `passlib[argon2]` | passlib 1.7.4 imports the stdlib `crypt` module, removed in Python 3.13. Same Argon2id algorithm; security property unchanged. |
| JWT library | `PyJWT` instead of `python-jose` | Actively maintained. Token claims, algorithm and lifetimes are exactly as the TRD specifies. |
| Refresh-token storage (TRD D11) | `localStorage` | Needs no cookie/CSRF plumbing for the demo. **Tradeoff stated, not hidden:** readable by injected script. An httpOnly cookie is the recommendation beyond the demo; the swap is confined to `stores/auth.ts`. |
| `admin_regions` (TRD D7) | Table created, ships **empty** | No boundary dataset has been selected or licence-verified. No boundary data is invented. District resolution is deferred to Phase 4. |
| Reference catalogue (TRD D2/D3) | Small provisional vocabulary, `is_verified=false` | Gives the crop-context UI something real to bind to. Registered in `data_sources` as unverified; every agent has `is_ai_supported=false` since no model exists. |
| Hindi/Marathi text (TRD D10) | Machine-assisted draft, flagged in-file | Each locale file carries a `_TRANSLATION_NOTE` requiring human review before any farmer-facing use. Agronomic and safety terminology in later phases must never be machine-translated. |
| Unimplemented endpoints | HTTP 501 naming the phase | Fixes the URL contract now without returning fake results. |
| Map tile provider (TRD D16) | Unset by default | No provider's terms have been verified, so the app does not silently call a third party. |

---

## Security notes

- No secrets are committed. `.env` is git-ignored; only `.env.example` (with empty
  values) is tracked, and CI fails the build if an env file or a stray `JWT_SECRET`
  appears.
- The application **refuses to boot** outside `APP_ENV=local` if `JWT_SECRET` is
  missing, short, or still the example value; if `DEBUG` is true; or if CORS is `*`.
- There is no default admin password. `create_admin_user.py` prompts or reads
  `ADMIN_PASSWORD` from the environment.
- Logs redact anything matching `password|secret|token|key|authorization|phone|email`.
- Uploaded-image handling, rate limiting and multi-factor auth are **not** implemented
  in Phase 1.

---

## Current status

All ten planned phases are complete. Phase 10 validated the full farmer → AI/risk →
map → expert → advisory → follow-up → official-dashboard flow end to end, fixed the
genuine issues that surfaced (see `git log` for the Phase 10 commits), and added the
demo-data seed script. What's left is not code: the TRD decisions D2/D3 (an
authoritative crop/disease vocabulary), D16 (a map tile provider whose terms have been
verified), and D10 (human-reviewed Hindi/Marathi translation) are still open, and
training/evaluating a real AI model was never in scope for this prototype.
