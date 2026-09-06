# FloraSentry V2 — Technical Requirements Document (TRD)

---

## 1. DOCUMENT CONTROL

| Field | Value |
|---|---|
| **Document title** | FloraSentry V2 — Technical Requirements Document (TRD) |
| **Project name** | FloraSentry V2 |
| **SIH problem statement** | SIH26131 — Early detection and management of crop diseases and pest infestations |
| **Theme** | Agriculture, FoodTech & Rural Development |
| **Target geography** | Maharashtra, India (MVP); architecture is region-extensible |
| **Version** | 1.0 |
| **Status** | Draft for implementation — Phase 0 output (Architecture & Data Strategy). No code written. |
| **Intended audience** | Backend engineers, frontend engineers, ML engineers, GIS engineers, DevOps, AI coding agents, SIH evaluators |
| **Source PRD** | `FloraSentry_V2_PRD-2.md` (FloraSentry V2 — Product Requirements Document) |
| **Last updated** | 2026-09-05 |
| **Supersedes** | None |

### 1.1 Labelling conventions used in this document

| Label | Meaning |
|---|---|
| *(unlabelled)* | Directly derived from the PRD or from the codebase audit. |
| **TECHNICAL RECOMMENDATION** | Not specified in the PRD. An engineering choice made by the architect; changeable without violating the PRD. |
| **REQUIRES DECISION** | Cannot be determined from the PRD or codebase. A human must decide before the affected work begins. |
| **TO BE BENCHMARKED** | A performance number that must be measured on real hardware, not guessed. |

### 1.2 Non-invention statement

This document contains no invented datasets, third-party API details, government data sources, model accuracy figures, scientific validation, production infrastructure, credentials, or field observations. Wherever such a thing would normally appear, a `REQUIRES DECISION` marker appears instead.

---

## 2. CODEBASE AUDIT (Phase 0 prerequisite)

### 2.1 Audit scope and method

Directory audited: `C:\Users\HARUN RASHID\Downloads\Florasentry`
Method: full recursive file listing, hidden-file listing, VCS detection.

### 2.2 Audit result

```
Florasentry/
└── FloraSentry_V2_PRD-2.md      (the PRD only)
```

**Finding: the project directory contains no source code.** No frontend, no backend, no migration, no AI code, no configuration, no tests, no dependency manifest (`package.json`, `requirements.txt`, `pyproject.toml`), and no version control (`.git` absent).

### 2.3 Component status matrix

| Area | Item | Status | Evidence |
|---|---|---|---|
| Frontend | Framework / version | **MISSING** | No `package.json`, no `src/`, no JS/TS files |
| Frontend | Routing | **MISSING** | — |
| Frontend | Component structure | **MISSING** | — |
| Frontend | State management | **MISSING** | — |
| Frontend | Styling system | **MISSING** | No Tailwind config |
| Frontend | API client | **MISSING** | — |
| Frontend | Reusable components | **MISSING** | PRD §18 mentions "existing reusable FloraSentry components"; none present here |
| Backend | Project structure | **MISSING** | No Python package |
| Backend | FastAPI configuration | **MISSING** | — |
| Backend | Existing endpoints | **MISSING** | — |
| Database | Setup / connection | **MISSING** | — |
| Database | ORM | **MISSING** | — |
| Database | Migrations | **MISSING** | No `alembic/` |
| Security | Authentication | **MISSING** | — |
| Security | Authorization | **MISSING** | — |
| Media | Image handling | **MISSING** | — |
| AI | Model code / weights | **MISSING** | No `.pt`, `.pth`, `.onnx` files |
| GIS | Map implementation | **MISSING** | — |
| Config | Environment configuration | **MISSING** | No `.env`, `.env.example` |
| DevOps | Deployment setup | **MISSING** | No Dockerfile, compose file, or CI config |
| QA | Testing setup | **MISSING** | — |
| Data | Mock / demo data | **MISSING** | — |

**IMPLEMENTED:** none. **PARTIALLY IMPLEMENTED:** none. **MOCKED:** none. **BROKEN:** none. **DEPRECATED:** none. **MISSING:** all of the above.

### 2.4 Consequence for this TRD

FloraSentry V2 is specified as a **greenfield build**. Phase 1 begins with repository initialisation.

> **REQUIRES DECISION — Existence of a FloraSentry V1 codebase.**
> The PRD refers to "FloraSentry **V2**" and to "existing reusable FloraSentry components". If a V1 repository exists elsewhere, supply it before Phase 1. Answer:
> 1. Does a V1 repository exist? Where?
> 2. Which V1 components are reused verbatim, adapted, or discarded?
> 3. Is any V1 schema or data migrated into V2?
>
> **Default assumed here if unanswered:** no V1 code is reused; V2 is built new. All structures below remain valid targets even if V1 components are later dropped in.

---

## 3. TECHNICAL OBJECTIVES

| # | PRD goal | Technical objective | Verifiable when |
|---|---|---|---|
| T1 | Detect symptoms earlier using AI | Image-inference pipeline behind `POST /api/v1/observations` returning class + confidence + model version, persisted to `ai_predictions` | An uploaded image produces a stored `ai_predictions` row referencing a stored image row |
| T2 | Combine AI with crop, field, weather, history | A `ContextEngine` assembling a typed `RiskContext` from six repositories before risk evaluation | `RiskContext` unit test builds a complete context from seeded fixtures |
| T3 | Locally relevant risk assessment | Configurable, rule-based, explainable `RiskEngine` writing `risk_assessments` with machine-readable `contributing_factors` | Given fixed inputs the engine is deterministic and every score component is traceable |
| T4 | Map observations, identify hotspots | PostGIS storage + `HotspotEngine` producing polygons separating CONFIRMED / PREDICTED / SIGNAL | GeoJSON layers render in Leaflet with correct type separation |
| T5 | Route uncertain cases to experts | Confidence gate transitioning `verification_status` to `PENDING_REVIEW` and enqueueing `expert_reviews` | A low-confidence prediction never surfaces as a diagnosis in any API response |
| T6 | Multilingual IPM advisory | Template-driven `AdvisoryEngine` with `en`/`hi`/`mr` keys, no hard-coded user-facing strings | Switching `Accept-Language` returns the same advisory in a different language, same structure |
| T7 | Track follow-ups and outcomes | `followups` linking parent to child observation with an outcome enum | A follow-up chain of depth ≥ 2 is queryable in one request |
| T8 | Official surveillance dashboards | Indexed aggregation endpoints with mandatory confirmed-vs-predicted separation | No KPI merges confirmed and predicted into one undifferentiated number |
| T9 | Feedback loop from confirmations | Export turning `CONFIRMED`/`CORRECTED` observations into a versioned field-validation dataset manifest | A manifest generates with provenance for every included image |
| T10 | Provenance integrity | Non-nullable `source_type` on every observation-bearing table, surfaced in every API response and UI element | No observation response omits `source_type`; no map point renders without a provenance badge |

### 3.1 Cross-cutting objectives

| # | Objective |
|---|---|
| T11 | **Modular monolith.** One deployable FastAPI app, internally partitioned. No microservices in MVP (PRD §4, §18). |
| T12 | **Replaceability.** AI model, weather provider and risk engine each sit behind an interface, swappable without touching callers. |
| T13 | **Truthfulness by construction.** It must be structurally impossible to present a prediction as a confirmation, or demo data as real. Enforced by constraints, not convention. |
| T14 | **Demonstrability.** The complete PRD §23 flow runs end-to-end in one demo environment inside the SIH time budget. |

---

## 4. SYSTEM ARCHITECTURE

### 4.1 Architectural style

**Modular monolith.** One FastAPI process serves all HTTP APIs and hosts all business modules in-process. One background worker (same codebase, different entrypoint) handles deferred work. One PostgreSQL+PostGIS database. One object/file store for images.

Rationale (PRD §4, §18, §27.7): microservices add deployment, observability and transaction complexity with no MVP benefit. Module boundaries are enforced in code so any module can later be extracted if genuinely required.

### 4.2 High-level system diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             CLIENTS                                       │
│  Farmer PWA   Expert Console   Official Dashboard   Admin Console         │
│  (React + Tailwind + Leaflet, single SPA, role-routed)                    │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ HTTPS / JSON  (JWT Bearer)
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      REVERSE PROXY (Nginx / Caddy)                        │
│  TLS · gzip · static SPA · /api → backend · /media → signed image reads    │
└───────────────────────────────┬──────────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    FastAPI APPLICATION (modular monolith)                 │
│                                                                           │
│  API LAYER (routers)   auth · users · farmers · fields · crops ·          │
│                        observations · images · ai · weather · risk ·      │
│                        gis · hotspots · reviews · advisories ·            │
│                        followups · traps · sensors · dashboards ·         │
│                        sources · admin · health                           │
│  ─────────────────────────────────────────────────────────────────────    │
│  SERVICE LAYER (business logic, transaction boundary)                     │
│    AuthService  ObservationService  ContextEngine  InferenceService       │
│    WeatherService  RiskEngine  GisService  HotspotEngine                  │
│    ReviewService  AdvisoryEngine  FollowupService  DashboardService       │
│    ProvenanceService  AuditService  NotificationService                   │
│  ─────────────────────────────────────────────────────────────────────    │
│  REPOSITORY LAYER (all SQL / PostGIS access; no SQL above this line)      │
│  ─────────────────────────────────────────────────────────────────────    │
│  ADAPTERS   ModelRunner(ABC) · WeatherProvider(ABC) · Storage(ABC)        │
└───────┬──────────────────┬───────────────────┬───────────────┬───────────┘
        │                  │                   │               │
        ▼                  ▼                   ▼               ▼
┌───────────────┐  ┌──────────────┐   ┌────────────────┐  ┌──────────────┐
│ PostgreSQL 16 │  │ Object /file │   │ Weather        │  │ Basemap tiles│
│  + PostGIS 3  │  │ store        │   │ provider       │  │ (frontend    │
│  (system of   │  │ (images)     │   │ (REQUIRES      │  │  direct)     │
│   record)     │  │              │   │  DECISION)     │  │              │
└───────────────┘  └──────────────┘   └────────────────┘  └──────────────┘
        ▲
        │
┌───────┴───────────────────────────────────────────────────────────────────┐
│  BACKGROUND WORKER (same image, different entrypoint)                      │
│  hotspot recomputation · weather refresh · followup due-scan ·             │
│  notification dispatch · demo-data seed/reset · dataset export             │
└───────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Core observation flow (PRD §7.1 / §23, expressed technically)

```
[1]  Client  POST /api/v1/observations  (multipart: image + JSON context)
       │      Auth: JWT (FARMER or EXTENSION_WORKER)
       ▼
[2]  ObservationService.create()  — opens DB transaction
       ├─ validate: field ownership, crop/variety/stage consistency, GPS sanity
       ├─ ImageService.store()   → object store; writes observation_images row
       ├─ writes observations row  (status=PROCESSING, source_type=FIELD_OBSERVATION,
       │                            geom = ST_SetSRID(ST_MakePoint(lon,lat),4326))
       └─ commits  →  returns 202 Accepted with observation_id
       ▼
[3]  InferenceService.run(image)          [synchronous by default; see §15.6]
       ├─ image validation (format, size, decodability, blur/darkness heuristics)
       ├─ preprocessing (resize, normalise)
       ├─ ModelRunner.predict()  → [(class, confidence), ...], model_version
       └─ writes ai_predictions row
       ▼
[4]  Confidence gate  (thresholds from ai_model_registry, configurable)
       ├─ conf ≥ HIGH  → verification_status = PREDICTED   (preliminary assessment)
       ├─ conf <  HIGH → verification_status = PENDING_REVIEW
       │                 + expert_reviews row created (queued)
       └─ image rejected / unsupported → status = UNSUPPORTED_IMAGE, no advisory
       ▼
[5]  WeatherService.get_context(lat, lon, at)
       ├─ cache hit  (weather_observations / weather_forecasts, TTL-fresh) → use
       ├─ cache miss → WeatherProvider.fetch() → persist → use
       └─ provider failure → use stale row, mark is_stale=true; else weather=null
       ▼
[6]  ContextEngine.build(observation)
       → RiskContext { ai_signal, crop, variety, growth_stage, weather,
                       nearby_history (PostGIS), field_context, trap/sensor signals }
       ▼
[7]  RiskEngine.evaluate(RiskContext)
       → writes risk_assessments { score, level, forecast_period,
                                   contributing_factors JSONB, explanation_key,
                                   ruleset_version, uncertainty }
       ▼
[8]  AdvisoryEngine.generate(observation, prediction, risk)
       → writes advisories { advisory_type, content, language, confidence_at_gen,
                             verification_status_at_gen, ruleset_version }
       ▼
[9]  FollowupService.schedule(observation, risk.level)
       → writes followups { scheduled_for, status=SCHEDULED }
       ▼
[10] Hotspot invalidation
       → marks the affected spatial/time bucket dirty; worker recomputes hotspots
       ▼
[11] Client polls GET /api/v1/observations/{id} until a terminal status, then renders:
     prediction + confidence + provenance badge + risk + advisory + map
```

### 4.4 Trust rules embedded in the flow

| Rule | Enforcement point |
|---|---|
| A prediction is never a diagnosis | Step [4]: `verification_status` is a separate column from `ai_predictions.predicted_class`; serialisers always emit both |
| Demo data is never real data | Step [2]: `source_type` is `NOT NULL`; the demo seeder can only write `DEMO_SIMULATION` |
| Stale weather is labelled | Step [5]: `is_stale` propagates into `risk_assessments` and into the advisory |
| Risk is decision support, not validated science | Step [7]: every row carries `ruleset_version` and `method='RULE_BASED_V1'`; UI shows a standing disclaimer |
| Every map point has provenance | Step [10]: the layer serialiser refuses to emit a feature lacking `source_type` |

---

## 5. ARCHITECTURE COMPONENTS

Each component is a module inside the monolith. Format: responsibility / inputs / outputs / dependencies / technologies / interfaces / failure behaviour.

### 5.1 Authentication

- **Responsibility:** Issue and verify credentials; mint and rotate tokens; expose the current principal to all other components.
- **Inputs:** phone/username/email + password; refresh token.
- **Outputs:** access token (JWT), refresh token, `CurrentUser` `{user_id, role, farmer_id?, district_code?}`.
- **Dependencies:** `users` table, password hasher, `AuditService`.
- **Technologies:** FastAPI, `python-jose` (JWT), `passlib[argon2]`.
- **Interfaces:** `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`; dependency `get_current_user()`.
- **Failure behaviour:** invalid credentials → `401 AUTH_INVALID_CREDENTIALS`, constant-time comparison, no user-existence disclosure; expired token → `401 AUTH_TOKEN_EXPIRED` so the client can silently refresh; repeated failures → rate-limited `429`.

### 5.2 User / Role Management

- **Responsibility:** CRUD on users; role assignment; deactivation; role-scoped visibility.
- **Inputs:** admin-authored user records; role enum.
- **Outputs:** user records; effective permission set.
- **Dependencies:** Authentication, Audit.
- **Technologies:** SQLAlchemy, Pydantic.
- **Interfaces:** `/users`, `/users/{id}`, `/users/{id}/role`, `/roles`.
- **Failure behaviour:** demoting the last ADMIN is refused (`409 LAST_ADMIN`); deactivation is soft (`is_active=false`), never a hard delete, to preserve audit integrity.

### 5.3 Field Management

- **Responsibility:** Own farmer fields, their location (point plus optional polygon), area, soil context and administrative linkage.
- **Inputs:** name, centroid lat/lon, optional GeoJSON polygon, area, soil type, irrigation type, district/taluka.
- **Outputs:** field records with PostGIS geometry; field-level risk and observation history.
- **Dependencies:** GIS Service, Farmer records.
- **Technologies:** GeoAlchemy2, Shapely, PostGIS.
- **Interfaces:** `/fields` CRUD, `/fields/{id}/observations`, `/fields/{id}/risk`.
- **Failure behaviour:** invalid/self-intersecting polygon → `422 GEOMETRY_INVALID` (`ST_IsValid`, with `ST_MakeValid` repair only as an explicit opt-in); coordinates outside the operating bbox → `422 COORDINATES_OUT_OF_BOUNDS`.

### 5.4 Crop Context

- **Responsibility:** Serve the controlled vocabulary of crops, varieties and growth stages; validate consistency.
- **Inputs:** seeded reference data; user selection.
- **Outputs:** validated `{crop_id, variety_id, growth_stage_id}`; stage-specific risk parameters.
- **Dependencies:** none (leaf reference module).
- **Technologies:** SQLAlchemy; seed fixtures.
- **Interfaces:** `/crops`, `/crops/{id}/varieties`, `/crops/{id}/growth-stages`.
- **Failure behaviour:** variety not belonging to the crop → `422 CROP_CONTEXT_MISMATCH`; growth stage is optional and degrades risk confidence rather than failing.

### 5.5 Observation Management

- **Responsibility:** The central aggregate. Owns creation, lifecycle status, provenance, geometry, and orchestration of inference → weather → risk → advisory → follow-up.
- **Inputs:** field, crop context, image(s), GPS, optional severity/notes, observation type.
- **Outputs:** `observations` row plus downstream rows; a GIS-visible feature.
- **Dependencies:** Image, AI, Weather, Risk, Advisory, Follow-up, GIS, Provenance, Audit.
- **Technologies:** FastAPI, SQLAlchemy, PostGIS.
- **Interfaces:** `/observations` CRUD + `/observations/{id}/status`.
- **Failure behaviour:** partial pipeline failure never loses the observation — the row persists with a degraded status (`AI_FAILED`, `RISK_UNAVAILABLE`) and a `processing_errors` JSONB. The observation stays on the map and stays reviewable.

### 5.6 Image Management

- **Responsibility:** Validate, normalise, store and serve observation images; strip unsafe metadata; supply preprocessed tensors to inference.
- **Inputs:** multipart upload.
- **Outputs:** stored original + thumbnail; `observation_images` row with checksum, dimensions, EXIF-derived capture time/GPS where present.
- **Dependencies:** Storage adapter, Authentication (signed access).
- **Technologies:** Pillow, OpenCV, content sniffing.
- **Interfaces:** `Storage.put/get/delete/sign`; `POST /observations/{id}/images`; `GET /images/{id}` (signed).
- **Failure behaviour:** content-type mismatch, oversize, or undecodable → `422 IMAGE_INVALID`, nothing written; storage failure → `503 STORAGE_UNAVAILABLE` and the transaction rolls back so no orphan row survives.

### 5.7 AI Inference

- **Responsibility:** Turn a validated image into a class, a confidence, an optional severity, and a recorded model version.
- **Inputs:** preprocessed image tensor, model version selector.
- **Outputs:** `ai_predictions` row `{predicted_class, confidence, top_k, severity?, model_version, inference_ms}`.
- **Dependencies:** Image Management, `ai_model_registry`.
- **Technologies:** PyTorch; Ultralytics/YOLO where a detection (not classification) task is required; OpenCV.
- **Interfaces:** `ModelRunner` ABC (`load`, `predict`, `metadata`); `POST /ai/analyze` (stateless test endpoint); `GET /ai/models`.
- **Failure behaviour:** model load failure at boot → the app starts in `AI_DEGRADED` mode, `/health` reports it, observations are accepted and routed straight to `PENDING_REVIEW`; inference exception → no prediction row, observation status `AI_FAILED`, expert review queued. **The system never fabricates a prediction.**

### 5.8 Weather Service

- **Responsibility:** Provide current, forecast and (where the chosen provider supports it) historical weather for a coordinate, with caching and provenance.
- **Inputs:** lat/lon, timestamp or horizon.
- **Outputs:** normalised weather DTO; persisted `weather_observations` / `weather_forecasts` rows.
- **Dependencies:** `WeatherProvider` adapter, cache tables.
- **Technologies:** `httpx` (async), retry with backoff.
- **Interfaces:** `WeatherProvider` ABC; `/weather/current`, `/weather/forecast`, `/weather/historical`.
- **Failure behaviour:** four-tier degradation — (1) fresh cache, (2) live fetch, (3) stale cache flagged `is_stale=true`, (4) `weather=null` with `WEATHER_UNAVAILABLE` recorded in risk factors. Risk is still computed without weather, at reduced confidence. The API never returns invented weather.

### 5.9 Risk Engine

- **Responsibility:** Produce an explainable risk score/level from the assembled context.
- **Inputs:** `RiskContext`. **Outputs:** `risk_assessments` row with machine-readable contributing factors.
- **Dependencies:** Context Engine, GIS (nearby history), Weather, Crop Context.
- **Technologies:** pure Python + YAML rule configuration for MVP; scikit-learn / XGBoost reserved for a future `MLRiskEngine`.
- **Interfaces:** `RiskEngine` ABC (`evaluate(RiskContext) -> RiskResult`); `/risk/*`.
- **Failure behaviour:** missing inputs reduce achievable confidence and are listed as `missing_factors`; the engine never silently substitutes defaults. Rule-config load error → `503 RISK_UNAVAILABLE`, observation persists with `RISK_UNAVAILABLE`.

### 5.10 GIS Service

- **Responsibility:** All spatial reads/writes: geometry construction, validation, spatial filtering, admin-region resolution, GeoJSON serialisation.
- **Inputs:** coordinates, bboxes, radii, admin codes, filters. **Outputs:** GeoJSON `FeatureCollection`s; spatial query results.
- **Dependencies:** PostGIS.
- **Technologies:** PostGIS 3.x, GeoAlchemy2, Shapely, GeoPandas (offline analytics only), QGIS (data preparation only, not runtime).
- **Interfaces:** `/gis/observations`, `/gis/layers/{layer}`, `/gis/nearby`.
- **Failure behaviour:** unbounded queries refused (`422 BBOX_REQUIRED`) rather than allowed to scan the table; query timeout → `504 GIS_TIMEOUT` with a narrow-the-window hint.

### 5.11 Hotspot Engine

- **Responsibility:** Aggregate observations spatially and temporally into hotspot and zone polygons, separating CONFIRMED / PREDICTED / SIGNAL.
- **Inputs:** observations in a space/time window, severity, verification status, weights.
- **Outputs:** `hotspots`, `priority_zones` rows with polygon geometry and a factor breakdown.
- **Dependencies:** GIS Service, Risk Engine outputs.
- **Technologies:** PostGIS `ST_ClusterDBSCAN` / `ST_ConcaveHull`; scheduled worker.
- **Interfaces:** `/hotspots`, `/gis/priority-zones`, worker job `recompute_hotspots`.
- **Failure behaviour:** insufficient points → an empty collection with `reason: INSUFFICIENT_DATA`, never a fabricated hotspot; recomputation failure leaves the previous snapshot in place, its `computed_at` making staleness visible.

### 5.12 Expert Validation

- **Responsibility:** Manage the review queue and the confirm/correct/reject/refer lifecycle with a complete audit trail.
- **Inputs:** queued observations; expert decision payloads.
- **Outputs:** `expert_reviews` rows; updated `observations.verification_status`; regenerated advisory when the diagnosis changes.
- **Dependencies:** Observation Management, Advisory Engine, Audit.
- **Technologies:** FastAPI, SQLAlchemy, optimistic claim locking.
- **Interfaces:** `/reviews/queue`, `/reviews/{id}/claim`, `/reviews/{id}/decision`, `/reviews/{id}/refer`.
- **Failure behaviour:** concurrent claims → second gets `409 REVIEW_ALREADY_CLAIMED`; stale claims expire after a configurable TTL and return to the queue.

### 5.13 Advisory Engine

- **Responsibility:** Generate IPM-first, multilingual, provenance-bearing guidance.
- **Inputs:** diagnosis (predicted or confirmed), confidence, verification status, risk level, crop context, language.
- **Outputs:** `advisories` rows referencing versioned templates.
- **Dependencies:** Risk Engine, Expert Validation, Localisation.
- **Technologies:** template + rule tables in PostgreSQL; key interpolation.
- **Interfaces:** `/advisories`, `/observations/{id}/advisory`.
- **Failure behaviour:** no matching template → a safe generic advisory (`ADVISORY_GENERIC_FALLBACK`) recommending expert consultation; never an empty or invented recommendation. Missing language → falls back to `en` with `language_fallback: true`.

### 5.14 Follow-up

- **Responsibility:** Schedule follow-ups, link parent and child observations, record outcome.
- **Inputs:** parent observation, risk level, expert instruction, farmer submission.
- **Outputs:** `followups` rows; outcome enum; comparison metadata.
- **Dependencies:** Observation Management, Notification.
- **Technologies:** worker due-scan job.
- **Failure behaviour:** an overdue follow-up is marked `MISSED`, never deleted, preserving the monitoring record.

### 5.15 Dashboard / Analytics

- **Responsibility:** Serve role-scoped aggregates and trends.
- **Inputs:** filters (date range, crop, agent, district, verification status).
- **Outputs:** KPI objects and time series that always separate confirmed from predicted.
- **Dependencies:** all read models. **Technologies:** parameterised SQL, optional materialised views.
- **Failure behaviour:** slow aggregate → `504` with a narrower-range hint; widget failures are isolated so one failing KPI does not blank the dashboard.

### 5.16 Data Provenance

- **Responsibility:** Guarantee every stored fact records its origin, creator, verifier, and model/ruleset version.
- **Inputs:** the creation context of every write. **Outputs:** provenance columns and a serialised `provenance` block in API responses.
- **Dependencies:** every write path.
- **Failure behaviour:** a write lacking provenance is a programming error — enforced by `NOT NULL` constraints and a shared `ProvenanceMixin`; it fails loudly at the database, not silently.

### 5.17 Audit Logging

- **Responsibility:** Immutable business-event record: who did what, to which entity, when, from where.
- **Inputs:** service-layer events. **Outputs:** append-only `audit_logs` rows.
- **Dependencies:** Authentication.
- **Failure behaviour:** audit-write failure for a security-relevant event (login, role change, expert decision) aborts the transaction; for a low-severity event it logs an operational error and continues.

### 5.18 Notification (SHOULD-HAVE per PRD §22)

- **Responsibility:** In-app alerts for high risk, nearby confirmed cases, follow-up due, expert response.
- **Interfaces:** `/notifications`, `/notifications/{id}/read`.
- **Technologies:** in-app only for MVP (DB-backed inbox + client polling).
- **Failure behaviour:** dispatch failure is retried with backoff and deduplicated by `(user_id, dedupe_key)` so a farmer is never spammed (PRD §15).

> **REQUIRES DECISION — SMS/WhatsApp/push channels.** The PRD lists alerts but names no channel or vendor. No gateway is assumed. MVP is in-app only unless a provider and budget are decided.

---

## 6. DETAILED BACKEND ARCHITECTURE

### 6.1 Repository layout

The audit found no existing code, so the structure is proposed in full, adapted to this system's actual modules.

```
florasentry/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app factory, router mount, lifespan
│   │   ├── api/
│   │   │   ├── deps.py              # shared dependencies (db, current_user, rbac)
│   │   │   └── v1/
│   │   │       ├── router.py        # aggregates all v1 routers
│   │   │       ├── auth.py   users.py   farmers.py   fields.py   crops.py
│   │   │       ├── observations.py  images.py  ai.py  weather.py
│   │   │       ├── risk.py   gis.py   hotspots.py   reviews.py
│   │   │       ├── advisories.py  followups.py  traps.py  sensors.py
│   │   │       ├── dashboards.py  sources.py  notifications.py
│   │   │       └── admin.py  health.py
│   │   ├── core/
│   │   │   ├── config.py            # pydantic-settings, env-driven
│   │   │   ├── security.py          # hashing, JWT encode/decode
│   │   │   ├── rbac.py              # role → permission matrix
│   │   │   ├── errors.py            # exception types + handlers
│   │   │   ├── responses.py         # envelope helpers
│   │   │   ├── logging.py           # structured logging
│   │   │   ├── pagination.py
│   │   │   └── i18n.py              # language negotiation
│   │   ├── db/
│   │   │   ├── session.py           # engine, session factory
│   │   │   ├── base.py              # declarative base + mixins
│   │   │   └── seeds/               # reference data seeders
│   │   ├── models/                  # SQLAlchemy ORM
│   │   │   ├── user.py  farmer.py  field.py  crop.py  observation.py
│   │   │   ├── prediction.py  catalog.py  weather.py  risk.py
│   │   │   ├── review.py  advisory.py  followup.py  spatial.py
│   │   │   └── provenance.py  audit.py  notification.py
│   │   ├── schemas/                 # Pydantic v2 request/response models
│   │   ├── repositories/            # ALL SQL/PostGIS lives here
│   │   ├── services/
│   │   │   ├── observation_service.py  context_engine.py
│   │   │   ├── review_service.py       followup_service.py
│   │   │   ├── dashboard_service.py    provenance_service.py
│   │   │   └── audit_service.py        notification_service.py
│   │   ├── ai/
│   │   │   ├── interface.py         # ModelRunner ABC + DTOs
│   │   │   ├── registry.py          # version → runner resolution
│   │   │   ├── preprocessing.py     validation.py
│   │   │   ├── runners/             # torch_classifier.py, yolo_detector.py, stub.py
│   │   │   └── inference_service.py
│   │   ├── gis/
│   │   │   └── geometry.py  queries.py  layers.py  hotspot_engine.py
│   │   ├── risk/
│   │   │   ├── interface.py  rule_engine.py  factors.py
│   │   │   └── rulesets/ruleset_v1.yaml
│   │   ├── advisory/
│   │   │   └── engine.py  templates.py  ipm_rules.py
│   │   ├── integrations/
│   │   │   ├── weather/ (interface.py, cache.py, providers/)
│   │   │   └── storage/ (interface.py, local.py, s3_compatible.py)
│   │   ├── workers/
│   │   │   ├── scheduler.py
│   │   │   └── jobs/ (hotspots.py, weather_refresh.py, followup_scan.py,
│   │   │              notifications.py, dataset_export.py)
│   │   └── locales/                 # backend-owned dynamic content: en/hi/mr
│   ├── alembic/versions/
│   ├── tests/ (unit/, integration/, api/, gis/, ai/, e2e/, factories/)
│   ├── scripts/ (seed_reference_data.py, seed_demo_data.py, reset_demo_data.py,
│   │             export_field_dataset.py)
│   └── pyproject.toml   alembic.ini   Dockerfile   .env.example
├── frontend/                        # see §7
├── docker-compose.yml
├── docs/  (PRD, this TRD, ADRs, API docs)
└── .github/workflows/ci.yml
```

### 6.2 Layer contract (strict)

| Layer | May call | May NOT do |
|---|---|---|
| Router | Services, schemas, deps | Contain business rules; execute SQL; query ORM models directly |
| Service | Repositories, other services (via interface), adapters | Build HTTP responses; import FastAPI request objects |
| Repository | ORM models, SQL, PostGIS | Contain business rules; call services |
| Adapter | External SDK/HTTP | Touch the database (except designated cache repositories) |

Enforced in review and by an import-linter rule in CI. **TECHNICAL RECOMMENDATION.**

### 6.3 Dependency injection

FastAPI's `Depends` is the only DI mechanism. `app/api/deps.py` provides:

```python
def get_db() -> Iterator[Session]            # scoped session, commit/rollback per request
def get_current_user(...) -> CurrentUser     # decodes JWT, loads active user
def require_roles(*roles) -> Callable        # RBAC guard factory
def get_observation_service(db=Depends(get_db)) -> ObservationService
def get_weather_provider() -> WeatherProvider     # resolved from settings
def get_model_runner() -> ModelRunner             # resolved from ai_model_registry
def get_language(accept_language: str | None) -> str
```

Adapters are chosen by configuration, never at the import site — this is what makes the model, weather provider and risk engine replaceable (T12).

### 6.4 Configuration

`pydantic-settings` `Settings`, instantiated once, injected everywhere. All values from environment (§36). Fail-fast: the app refuses to boot on a missing required secret rather than starting with a silent default. Insecure defaults are permitted only when `APP_ENV=local`.

### 6.5 Error handling

```
FloraSentryError
├── ValidationError        → 422
├── AuthenticationError    → 401
├── AuthorizationError     → 403
├── NotFoundError          → 404
├── ConflictError          → 409
├── RateLimitError         → 429
├── ExternalServiceError   → 502/503   (WeatherUnavailable, StorageUnavailable)
├── AIError                → 503       (ModelUnavailable, InferenceFailed)
├── GISError               → 422/503/504
└── InternalError          → 500
```

Handlers convert each into the standard envelope (§11). A catch-all handler logs unhandled exceptions with the request `trace_id` and returns a generic 500; stack traces are never returned to clients.

### 6.6 Transaction policy

One transaction per request, opened by `get_db`, committed on success and rolled back on any exception. Long-running steps (inference, external HTTP) run **outside** the write transaction: the observation is committed first (step [2] of §4.3), then enrichment steps commit independently. An observation is therefore never lost because a downstream service failed.

---

## 7. FRONTEND ARCHITECTURE

### 7.1 Stack

React 18 (Vite), TypeScript, Tailwind CSS, React Router v6, TanStack Query (server state), React Hook Form + Zod (forms), Leaflet + React-Leaflet (maps), react-i18next (localisation), Recharts (charts). **TECHNICAL RECOMMENDATION** for every library except React, Tailwind and Leaflet, which the PRD fixes.

Single SPA, role-routed — not four applications. Shared auth, API client, map and provenance components; one build, one deployment for the SIH demo.

### 7.2 Route structure

```
/                         → role-aware redirect
/login  /register  /language

FARMER (role: FARMER)
  /app                    Home: field summary, weather, active alerts
  /app/fields             /app/fields/new     /app/fields/:id
  /app/check              Check Crop Health (the core capture wizard)
  /app/observations       /app/observations/:id   (result + advisory + map)
  /app/alerts             /app/advisory/:id
  /app/followups          /app/followups/:id/submit
  /app/expert-help        /app/profile

EXPERT (roles: EXTENSION_WORKER, LAB_EXPERT)
  /expert                 Queue dashboard
  /expert/queue           filterable review queue
  /expert/cases/:id       case workspace: image, AI result, context, map, decision
  /expert/referrals       lab referral inbox (LAB_EXPERT)
  /expert/followups

OFFICIAL (role: OFFICIAL)
  /official               KPI overview (confirmed vs predicted, always separated)
  /official/map           full-screen GIS with layer control
  /official/hotspots      /official/priority-zones
  /official/trends        /official/coverage      /official/reports

ADMIN (role: ADMIN)
  /admin/users  /admin/roles  /admin/catalog  /admin/models
  /admin/data-sources  /admin/demo-data  /admin/audit
```

### 7.3 Directory structure

```
frontend/src/
├── app/            router.tsx, providers.tsx, guards.tsx
├── api/            client.ts (axios + interceptors), endpoints/*.ts, types.ts
├── hooks/          queries + mutations (useObservations, useRiskForField, ...)
├── components/
│   ├── ui/         Button, Card, Modal, Toast, Skeleton, EmptyState, Table
│   ├── provenance/ ProvenanceBadge, ConfidenceMeter, VerificationStatusChip,
│   │               DemoDataBanner, StaleDataNotice
│   ├── map/        MapContainer, ObservationLayer, HotspotLayer, RiskZoneLayer,
│   │               FieldPolygonLayer, LayerControl, MapLegend, LocationPicker
│   ├── capture/    ImageCapture, ImagePreview, GpsCapture, CropContextSelector
│   ├── charts/     TrendChart, DistributionChart, KpiTile
│   └── layout/     AppShell, FarmerNav, ExpertNav, OfficialNav, LanguageSwitcher
├── features/       farmer/, expert/, official/, admin/   (page components)
├── i18n/           index.ts, locales/{en,hi,mr}/*.json
├── stores/         auth.ts, language.ts, mapPrefs.ts   (Zustand)
└── lib/            formatters, geo helpers, validators
```

### 7.4 State management

| State kind | Mechanism |
|---|---|
| Server data (observations, fields, layers) | TanStack Query — caching, retry, background refetch, optimistic updates |
| Auth session (token, user, role) | Zustand store; access token in memory, refresh token per §13.4 |
| Language preference | Zustand + `localStorage`, mirrored to the user profile on the server |
| Map layer toggles / filters | Zustand (session-scoped) with URL query-param sync so a map view is shareable |
| Form state | React Hook Form, local to the form |

No Redux. **TECHNICAL RECOMMENDATION** — the server-state library removes most of what Redux would do here.

### 7.5 API layer

One axios instance with:
- a request interceptor attaching `Authorization: Bearer` and `Accept-Language`;
- a response interceptor unwrapping the success envelope and converting the error envelope into a typed `ApiError`;
- a single-flight 401 handler that refreshes once and replays queued requests, logging out on refresh failure;
- TypeScript types generated from the backend OpenAPI schema (`openapi-typescript`), so contract drift is a build error rather than a runtime bug. **TECHNICAL RECOMMENDATION.**

### 7.6 The capture flow (the most important farmer screen)

A four-step wizard at `/app/check`, designed for a low-end Android phone on a poor connection:

1. **Field & crop context** — field selector; crop, variety, growth stage from the server catalogue.
2. **Image** — `<input type="file" accept="image/*" capture="environment">`; client-side downscale to the configured max edge and JPEG re-encode before upload to cut bandwidth; live quality hints (too dark / too blurry) via a canvas Laplacian-variance check. **TECHNICAL RECOMMENDATION.**
3. **Location** — `navigator.geolocation` with accuracy display; manual map-pin fallback when permission is denied or accuracy is poor; `gps_accuracy_m` and `location_method` are sent to the server.
4. **Notes & submit** — optional severity and free text; upload with a real progress bar (PRD §20 requires clear progress).

After submit the client polls the observation until a terminal status, then renders prediction, confidence meter, **verification status chip**, risk card with contributing factors, advisory, map, and the scheduled follow-up date.

### 7.7 Map components

All map screens compose the same primitives. Layers are fetched as GeoJSON from `/gis/*` and rendered with:
- distinct styling for CONFIRMED (solid), PREDICTED (dashed/hollow) and SIGNAL (faint), enforced by a shared style function so no screen can render them alike by accident;
- a mandatory legend explaining every symbol;
- clustering for dense point layers;
- bbox- and zoom-driven refetch, debounced, so the client never requests unbounded data;
- a `DemoDataBanner` whenever any visible feature has `source_type = DEMO_SIMULATION`.

### 7.8 Loading, empty and error states

Every data-bound view implements four states: loading (skeleton, not a full-page spinner), empty (says what to do next), error (message from the error envelope plus retry), and degraded (e.g. "Weather unavailable — risk calculated without weather"). Degraded state is a first-class UI concept here, because the backend deliberately degrades rather than failing.

### 7.9 Provenance in the UI (PRD §8, §27.8)

A `ProvenanceBadge` is mandatory on observation cards, observation detail, every map popup, the expert case view, and every dashboard list row. It renders `source_type`, `verification_status`, confidence (when a prediction is involved), model version, and verifier/verified-at when present. Demo data gets a distinct colour and the label **"Simulated demo data — not a real field observation"**, in the active language.

---

## 8. DATABASE TECHNICAL DESIGN

PostgreSQL 16 with PostGIS 3.4. **TECHNICAL RECOMMENDATION** on exact versions; any PostgreSQL ≥ 14 with PostGIS ≥ 3.2 satisfies the requirements.

### 8.1 Global conventions

| Convention | Rule |
|---|---|
| Primary keys | `UUID` (`gen_random_uuid()`), column `id`. Demo and real records can then be generated independently without collisions, and IDs are not enumerable. |
| Timestamps | `TIMESTAMPTZ`, UTC. `created_at DEFAULT now() NOT NULL`; `updated_at` maintained by trigger. |
| Soft delete | `deleted_at TIMESTAMPTZ NULL` on user-owned entities; audit and prediction tables are never deleted. |
| Enums | Native PostgreSQL `ENUM` for closed vocabularies; lookup tables where values are administrable. |
| Provenance mixin | `source_type`, `created_by`, `created_at`, plus `verified_by`/`verified_at` where verification applies. |
| Naming | snake_case, plural tables, `fk_`/`ix_`/`uq_`/`ck_`/`gix_` constraint and index prefixes. |
| Numbers | `NUMERIC` for area/score/measurements, never `FLOAT`. |
| Geometry | `geometry(<Type>, 4326)`; see §9. |

### 8.2 Enumerated types

```sql
CREATE TYPE user_role AS ENUM
  ('FARMER','EXTENSION_WORKER','LAB_EXPERT','OFFICIAL','ADMIN');

CREATE TYPE source_type AS ENUM
  ('FIELD_OBSERVATION','PUBLIC_DATA','GOVERNMENT_DATA','EXPERT_VALIDATION','DEMO_SIMULATION');

CREATE TYPE verification_status AS ENUM
  ('PREDICTED','PENDING_REVIEW','CONFIRMED','CORRECTED','REJECTED','LAB_REFERRED');

CREATE TYPE observation_status AS ENUM
  ('PROCESSING','COMPLETED','AI_FAILED','UNSUPPORTED_IMAGE','RISK_UNAVAILABLE');

CREATE TYPE observation_type AS ENUM ('IMAGE','PEST_TRAP','SENSOR','MANUAL_REPORT');
CREATE TYPE risk_level        AS ENUM ('LOW','MEDIUM','HIGH');
CREATE TYPE hotspot_type      AS ENUM ('CONFIRMED','PREDICTED','SIGNAL');
CREATE TYPE followup_status   AS ENUM ('SCHEDULED','DUE','SUBMITTED','MISSED','CLOSED');
CREATE TYPE followup_outcome  AS ENUM ('BETTER','SAME','WORSE','UNCERTAIN');
CREATE TYPE review_state      AS ENUM ('QUEUED','CLAIMED','DECIDED','REFERRED','EXPIRED');
CREATE TYPE agent_kind        AS ENUM ('DISEASE','PEST','DISORDER','HEALTHY','UNKNOWN');
CREATE TYPE language_code     AS ENUM ('en','hi','mr');
```

### 8.3 Table specifications

Only tables with a concrete technical need are defined. Where a PRD candidate entity would produce an empty or redundant table, that is stated with a rationale (§8.4).

---

#### `users`

Purpose: authentication principal and role holder for all five user types.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| phone | VARCHAR(20) | YES | — | UNIQUE; primary login identifier for farmers |
| email | CITEXT | YES | — | UNIQUE; login for expert/official/admin |
| username | VARCHAR(64) | YES | — | UNIQUE |
| password_hash | TEXT | NO | — | Argon2id |
| full_name | VARCHAR(150) | NO | — | |
| role | user_role | NO | 'FARMER' | |
| preferred_language | language_code | NO | 'en' | |
| district_code | VARCHAR(20) | YES | — | FK → admin_regions(code); scopes OFFICIAL visibility |
| is_active | BOOLEAN | NO | true | |
| last_login_at | TIMESTAMPTZ | YES | — | |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |
| deleted_at | TIMESTAMPTZ | YES | — | soft delete |

Constraints: `CHECK (phone IS NOT NULL OR email IS NOT NULL OR username IS NOT NULL)`.
Indexes: `uq_users_phone`, `uq_users_email`, `uq_users_username`, `ix_users_role`, `ix_users_district_code`.

> **Note on `roles` as a table.** The PRD lists "Role" as an entity. The MVP has five fixed roles with fixed permissions; a `roles` table plus a join table adds joins and migration burden with no MVP gain. **TECHNICAL RECOMMENDATION:** implement roles as the `user_role` enum plus a code-level permission matrix (§13.5). A `roles`/`permissions` table is the documented upgrade path if per-deployment custom roles are ever needed. A read-only `GET /roles`, served from the enum, still satisfies PRD §17.

---

#### `farmers`

Purpose: agricultural profile attached to a `FARMER` user. Separate from `users` so authentication data and farming data have different lifecycles and access rules.

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | NO | PK |
| user_id | UUID | NO | FK → users(id) ON DELETE RESTRICT, UNIQUE |
| village | VARCHAR(120) | YES | |
| taluka | VARCHAR(120) | YES | |
| district_code | VARCHAR(20) | YES | FK → admin_regions(code) |
| land_holding_ha | NUMERIC(8,2) | YES | CHECK ≥ 0 |
| primary_crop_id | UUID | YES | FK → crops(id) |
| created_at / updated_at | TIMESTAMPTZ | NO | |

Indexes: `uq_farmers_user_id`, `ix_farmers_district_code`.
Privacy: no Aadhaar, no bank details, no government ID — see §30.

---

#### `admin_regions`

Purpose: administrative boundaries for district/taluka filtering and official scoping.

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | NO | PK |
| code | VARCHAR(20) | NO | UNIQUE |
| name | VARCHAR(150) | NO | |
| level | VARCHAR(20) | NO | 'STATE' / 'DISTRICT' / 'TALUKA' |
| parent_id | UUID | YES | FK → admin_regions(id) |
| geom | geometry(MultiPolygon,4326) | YES | boundary |
| source_type | source_type | NO | provenance of the boundary dataset |
| source_reference | TEXT | YES | dataset name/version as loaded |

Indexes: `gix_admin_regions_geom` (GIST), `ix_admin_regions_level`, `ix_admin_regions_parent_id`.

> **REQUIRES DECISION — boundary dataset.** No administrative-boundary dataset is named in the PRD and none is assumed here. Select and verify a licensed source before Phase 4, then record its exact name, version, licence and retrieval date in `data_sources`. Until then, `admin_regions` may be seeded only with clearly labelled placeholder rows carrying `source_type = 'DEMO_SIMULATION'`.

---

#### `crops`, `crop_varieties`, `growth_stages`

`crops`: `id` UUID PK; `code` VARCHAR(40) UNIQUE; `name_en`/`name_hi`/`name_mr` VARCHAR(120) NOT NULL; `scientific_name` VARCHAR(150) NULL; `is_active` BOOLEAN NOT NULL DEFAULT true.

`crop_varieties`: `id` UUID PK; `crop_id` UUID NOT NULL FK → crops ON DELETE CASCADE; `code` VARCHAR(60) NOT NULL; `name_en/hi/mr`; `duration_days` INT NULL; `notes` TEXT NULL. UNIQUE `(crop_id, code)`; index `ix_crop_varieties_crop_id`.

`growth_stages`: `id` UUID PK; `crop_id` UUID NOT NULL FK → crops; `code` VARCHAR(40) NOT NULL; `name_en/hi/mr`; `sequence` SMALLINT NOT NULL; `typical_days_from_sowing_min`/`_max` INT NULL; `susceptibility_notes` TEXT NULL. UNIQUE `(crop_id, code)` and `(crop_id, sequence)`.

> **REQUIRES DECISION — supported crop list.** PRD §11 requires an explicit, limited, defensible class list but enumerates no crops. Fix the MVP crop set (jointly with the AI class list) before Phase 2. Nothing in this TRD assumes any particular crop.

---

#### `fields`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| farmer_id | UUID | NO | — | FK → farmers(id) ON DELETE CASCADE |
| name | VARCHAR(120) | NO | — | |
| centroid | geometry(Point,4326) | NO | — | always present |
| boundary | geometry(Polygon,4326) | YES | — | optional (PRD §10) |
| area_ha | NUMERIC(10,3) | YES | — | CHECK > 0; may be computed from boundary |
| soil_type | VARCHAR(60) | YES | — | |
| irrigation_type | VARCHAR(60) | YES | — | |
| district_code | VARCHAR(20) | YES | — | FK → admin_regions(code); resolved on write |
| current_crop_id | UUID | YES | — | FK → crops(id) |
| current_variety_id | UUID | YES | — | FK → crop_varieties(id) |
| sowing_date | DATE | YES | — | enables growth-stage inference |
| source_type | source_type | NO | 'FIELD_OBSERVATION' | |
| created_by | UUID | NO | — | FK → users(id) |
| created_at / updated_at / deleted_at | TIMESTAMPTZ | | now() | |

Constraints: `ck_fields_boundary_valid CHECK (boundary IS NULL OR ST_IsValid(boundary))`; `ck_fields_centroid_in_boundary CHECK (boundary IS NULL OR ST_Contains(boundary, centroid))`.
Indexes: `gix_fields_centroid`, `gix_fields_boundary` (GIST), `ix_fields_farmer_id`, `ix_fields_district_code`.

---

#### `disease_pest_catalog`

Purpose: single catalogue of diagnosable agents. **The PRD lists `diseases`, `pests` and `symptoms` separately; diseases and pests share every structural column and differ only by a kind discriminator.** One table with `kind agent_kind` avoids two mutually exclusive nullable FKs in `ai_predictions`, `expert_reviews`, `advisories`, `hotspots` and `observations`. **TECHNICAL RECOMMENDATION.**

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | NO | PK |
| code | VARCHAR(80) | NO | UNIQUE; also the AI class label |
| kind | agent_kind | NO | DISEASE / PEST / DISORDER / HEALTHY / UNKNOWN |
| name_en / name_hi / name_mr | VARCHAR(150) | NO | |
| scientific_name | VARCHAR(150) | YES | |
| description_key | VARCHAR(120) | YES | i18n key |
| is_ai_supported | BOOLEAN | NO | true only for classes the active model can output |
| created_at | TIMESTAMPTZ | NO | |

`agent_crops` (join): `agent_id`, `crop_id`, PK `(agent_id, crop_id)` — which agents affect which crops.

`symptoms`: `id` UUID PK; `code` VARCHAR(60) UNIQUE; `name_en/hi/mr`; `body_part` VARCHAR(40) NULL.
`agent_symptoms` (join): `agent_id`, `symptom_id`, `typicality` SMALLINT NULL, PK `(agent_id, symptom_id)`. Symptoms keep their own table because the expert UI and advisory templates reference them independently of any single agent.

---

#### `observations`

Purpose: the central record. Every map point, risk assessment, advisory and follow-up hangs off this table.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| farmer_id | UUID | YES | — | FK → farmers(id); null when an extension worker reports without a farmer profile |
| reported_by | UUID | NO | — | FK → users(id) |
| field_id | UUID | YES | — | FK → fields(id); null for an ad-hoc roadside observation |
| crop_id | UUID | YES | — | FK → crops(id) |
| variety_id | UUID | YES | — | FK → crop_varieties(id) |
| growth_stage_id | UUID | YES | — | FK → growth_stages(id) |
| observation_type | observation_type | NO | 'IMAGE' | |
| latitude | NUMERIC(9,6) | NO | — | CHECK between -90 and 90 |
| longitude | NUMERIC(9,6) | NO | — | CHECK between -180 and 180 |
| geom | geometry(Point,4326) | NO | — | generated from lat/lon on write |
| gps_accuracy_m | NUMERIC(7,2) | YES | — | reported by the device |
| location_method | VARCHAR(20) | NO | 'DEVICE_GPS' | DEVICE_GPS / MAP_PIN / FIELD_CENTROID |
| district_code | VARCHAR(20) | YES | — | resolved by point-in-polygon on write |
| observed_at | TIMESTAMPTZ | NO | now() | when the farmer saw it |
| reported_severity | SMALLINT | YES | — | CHECK 1..5, farmer-reported |
| notes | TEXT | YES | — | |
| status | observation_status | NO | 'PROCESSING' | pipeline state |
| verification_status | verification_status | NO | 'PREDICTED' | truth state |
| final_agent_id | UUID | YES | — | FK → disease_pest_catalog; set only on CONFIRMED/CORRECTED |
| source_type | source_type | NO | — | provenance; NOT NULL by design |
| original_source_ref | TEXT | YES | — | for imported/public data |
| data_source_id | UUID | YES | — | FK → data_sources(id) |
| parent_observation_id | UUID | YES | — | FK → observations(id); set for follow-ups |
| processing_errors | JSONB | YES | — | degraded-step details |
| created_at / updated_at / deleted_at | TIMESTAMPTZ | | now() | |

Constraints:
- `ck_obs_final_agent_requires_verification CHECK (final_agent_id IS NULL OR verification_status IN ('CONFIRMED','CORRECTED'))` — **a database-level guarantee that a prediction can never masquerade as a confirmed diagnosis.**
- geometry/lat-lon consistency enforced by a `BEFORE INSERT OR UPDATE` trigger that derives `geom` from `latitude`/`longitude`.

Indexes: `gix_observations_geom` (GIST); `ix_obs_observed_at`; `ix_obs_verification_status`; `ix_obs_source_type`; `ix_obs_crop_id`; `ix_obs_field_id`; `ix_obs_farmer_id`; `ix_obs_district_code`; composite `ix_obs_district_observed_at (district_code, observed_at DESC)`; composite `ix_obs_status_verif (status, verification_status)`; `ix_obs_parent`.

---

#### `observation_images`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | NO | PK |
| observation_id | UUID | NO | FK → observations ON DELETE CASCADE |
| storage_key | TEXT | NO | object-store key, not a public URL |
| thumbnail_key | TEXT | YES | |
| original_filename | VARCHAR(255) | YES | sanitised |
| mime_type | VARCHAR(50) | NO | validated by content sniffing, not extension |
| size_bytes | BIGINT | NO | CHECK > 0 |
| width_px / height_px | INT | YES | |
| checksum_sha256 | CHAR(64) | NO | duplicate detection |
| exif_captured_at | TIMESTAMPTZ | YES | |
| exif_latitude / exif_longitude | NUMERIC(9,6) | YES | compared against reported GPS |
| quality_flags | JSONB | YES | e.g. `{"blur_score":..,"too_dark":true}` |
| is_primary | BOOLEAN | NO | DEFAULT true |
| uploaded_by | UUID | NO | FK → users(id) |
| created_at | TIMESTAMPTZ | NO | |

Indexes: `ix_obs_images_observation_id`, `ix_obs_images_checksum`.
Binary image data is **not** stored here (PRD §20) — only keys.

---

#### `ai_model_registry`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | NO | PK |
| model_version | VARCHAR(60) | NO | UNIQUE, e.g. `crop-clf-v0.1.0` |
| task | VARCHAR(30) | NO | CLASSIFICATION / DETECTION |
| framework | VARCHAR(30) | NO | pytorch / ultralytics |
| runner_class | VARCHAR(120) | NO | import path of the `ModelRunner` implementation |
| artifact_key | TEXT | NO | weights location |
| artifact_checksum | CHAR(64) | NO | |
| input_size | VARCHAR(20) | NO | e.g. `224x224` |
| class_list | JSONB | NO | ordered labels mapping to `disease_pest_catalog.code` |
| high_confidence_threshold | NUMERIC(4,3) | NO | configurable per model |
| low_confidence_threshold | NUMERIC(4,3) | NO | |
| training_dataset_ref | TEXT | YES | dataset manifest id |
| evaluation_metrics | JSONB | YES | **populated only from an actual evaluation run; never pre-filled** |
| is_active | BOOLEAN | NO | exactly one active per task |
| notes | TEXT | YES | known limitations |
| created_at | TIMESTAMPTZ | NO | |

`CREATE UNIQUE INDEX uq_active_model_per_task ON ai_model_registry(task) WHERE is_active;`

---

#### `ai_predictions`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | NO | PK |
| observation_id | UUID | NO | FK → observations ON DELETE CASCADE |
| image_id | UUID | YES | FK → observation_images |
| model_version | VARCHAR(60) | NO | FK → ai_model_registry(model_version) |
| predicted_agent_id | UUID | YES | FK → disease_pest_catalog; null when the class is unmapped |
| predicted_class | VARCHAR(80) | NO | raw model label, always kept |
| confidence | NUMERIC(5,4) | NO | CHECK 0..1 |
| top_k | JSONB | YES | `[{"class":..,"confidence":..}, ...]` |
| severity_estimate | NUMERIC(5,4) | YES | optional (PRD §6.2) |
| is_low_confidence | BOOLEAN | NO | computed against the model's threshold |
| bbox_geojson | JSONB | YES | detection output when task = DETECTION |
| inference_ms | INT | YES | |
| runtime_device | VARCHAR(20) | YES | cpu / cuda |
| created_at | TIMESTAMPTZ | NO | |

Immutable — a re-run creates a new row, preserving prediction history for model comparison.
Indexes: `ix_ai_pred_observation_id`, `ix_ai_pred_model_version`, `ix_ai_pred_confidence`.

---

#### `weather_observations` / `weather_forecasts`

Shared columns: `id` UUID PK; `provider` VARCHAR(40) NOT NULL; `latitude`/`longitude` NUMERIC(9,6) NOT NULL; `grid_cell` VARCHAR(40) NOT NULL (rounded-coordinate cache key); `geom` geometry(Point,4326) NOT NULL; `temperature_c`, `humidity_pct`, `rainfall_mm`, `wind_speed_ms`, `wind_direction_deg`, `pressure_hpa` NUMERIC NULL; `raw_payload` JSONB NULL; `fetched_at` TIMESTAMPTZ NOT NULL; `source_type` source_type NOT NULL.

`weather_observations` adds `observed_at` TIMESTAMPTZ NOT NULL; UNIQUE `(provider, grid_cell, observed_at)`.
`weather_forecasts` adds `forecast_for` and `forecast_issued_at` TIMESTAMPTZ NOT NULL; UNIQUE `(provider, grid_cell, forecast_for, forecast_issued_at)`.

Indexes: `ix_weather_obs_cell_time (grid_cell, observed_at DESC)`; `gix_weather_obs_geom`; equivalents on forecasts.
Grid rounding lets fields within a few kilometres share one cache entry, cutting provider calls by an order of magnitude. **TECHNICAL RECOMMENDATION:** round to 2 decimal places (~1.1 km); tune after measuring.

---

#### `risk_assessments`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | NO | PK |
| observation_id | UUID | YES | FK → observations |
| field_id | UUID | YES | FK → fields |
| agent_id | UUID | YES | FK → disease_pest_catalog; risk is agent-specific when known |
| risk_score | NUMERIC(5,2) | NO | CHECK 0..100 |
| risk_level | risk_level | NO | derived from configurable bands |
| forecast_period_start / _end | TIMESTAMPTZ | NO | |
| contributing_factors | JSONB | NO | `[{"factor":"RAINFALL_7D","value":..,"weight":..,"contribution":..}]` |
| missing_factors | JSONB | YES | inputs that were unavailable |
| explanation_key | VARCHAR(120) | NO | i18n key for the human sentence |
| explanation_params | JSONB | YES | interpolation values |
| uncertainty | NUMERIC(4,3) | YES | 0..1, from input completeness |
| method | VARCHAR(40) | NO | `RULE_BASED_V1` |
| ruleset_version | VARCHAR(40) | NO | |
| weather_is_stale | BOOLEAN | NO | DEFAULT false |
| computed_at | TIMESTAMPTZ | NO | |

Constraint: `ck_risk_target CHECK (observation_id IS NOT NULL OR field_id IS NOT NULL)`.
Indexes: `ix_risk_observation_id`, `ix_risk_field_computed (field_id, computed_at DESC)`, `ix_risk_level`.

---

#### `expert_reviews`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | NO | PK |
| observation_id | UUID | NO | FK → observations |
| prediction_id | UUID | YES | FK → ai_predictions — the prediction under review |
| state | review_state | NO | QUEUED → CLAIMED → DECIDED/REFERRED/EXPIRED |
| priority | SMALLINT | NO | DEFAULT 3; derived from risk level and confidence |
| queued_at | TIMESTAMPTZ | NO | |
| claimed_by | UUID | YES | FK → users(id) |
| claimed_at | TIMESTAMPTZ | YES | |
| claim_expires_at | TIMESTAMPTZ | YES | |
| decision | verification_status | YES | CONFIRMED / CORRECTED / REJECTED / LAB_REFERRED |
| corrected_agent_id | UUID | YES | FK → disease_pest_catalog; required when decision = CORRECTED |
| confirmed_severity | SMALLINT | YES | CHECK 1..5 |
| expert_notes | TEXT | YES | |
| decided_at | TIMESTAMPTZ | YES | |
| referred_to_lab | BOOLEAN | NO | DEFAULT false |
| lab_reference_code | VARCHAR(60) | YES | |
| lab_result_agent_id | UUID | YES | FK → disease_pest_catalog |
| lab_result_notes | TEXT | YES | |
| lab_result_at | TIMESTAMPTZ | YES | |
| version | INT | NO | DEFAULT 1 — optimistic locking for claims |

Constraint: `ck_review_corrected_requires_agent CHECK (decision <> 'CORRECTED' OR corrected_agent_id IS NOT NULL)`.
Indexes: `ix_reviews_state_priority (state, priority, queued_at)` for queue pops; `ix_reviews_observation_id`; `ix_reviews_claimed_by`.

---

#### `advisories`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | NO | PK |
| observation_id | UUID | NO | FK → observations |
| agent_id | UUID | YES | FK → disease_pest_catalog |
| template_id | UUID | YES | FK → advisory_templates |
| language | language_code | NO | |
| content | JSONB | NO | rendered structured sections (§21.3) |
| confidence_at_generation | NUMERIC(5,4) | YES | frozen at generation time |
| verification_status_at_generation | verification_status | NO | frozen |
| risk_level_at_generation | risk_level | YES | frozen |
| advisory_ruleset_version | VARCHAR(40) | NO | |
| is_superseded | BOOLEAN | NO | DEFAULT false — set when an expert correction regenerates it |
| generated_at | TIMESTAMPTZ | NO | |

Freezing confidence and verification status is deliberate: an advisory must always read as "this is what we advised, on this evidence, at this time" (PRD §13).
Indexes: `ix_advisories_observation_id`; partial `ix_advisories_active ON advisories(observation_id) WHERE NOT is_superseded`.

`advisory_templates`: `id` UUID PK; `agent_id` UUID NULL FK (null = generic); `crop_id` UUID NULL FK; `min_risk_level` risk_level NULL; `applies_to_verification` verification_status[] NULL; `sections` JSONB NOT NULL (i18n keys per section); `version` VARCHAR(40) NOT NULL; `is_active` BOOLEAN NOT NULL; `source_reference` TEXT NULL; `created_at`.

> **REQUIRES DECISION — advisory content source.** Advisory text is agronomic guidance with real-world consequences, and the PRD forbids unsupported pesticide prescriptions. Nominate the authority for advisory content (e.g. a named agricultural university's extension material, a state IPM package of practices) and record it in `advisory_templates.source_reference` and `data_sources`. **No advisory content is invented in this TRD.** Until a source is nominated, only the generic IPM-and-refer-to-expert fallback template may ship.

---

#### `interventions`

Purpose: what the farmer actually did — this is what makes follow-up outcomes interpretable.

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | NO | PK |
| observation_id | UUID | NO | FK → observations |
| advisory_id | UUID | YES | FK → advisories |
| intervention_type | VARCHAR(40) | NO | CULTURAL / MECHANICAL / BIOLOGICAL / CHEMICAL / OTHER |
| description | TEXT | YES | farmer-entered free text |
| applied_at | TIMESTAMPTZ | NO | |
| recorded_by | UUID | NO | FK → users(id) |
| created_at | TIMESTAMPTZ | NO | |

Chemical interventions are recorded only as farmer-reported history. The system does not prescribe them.

---

#### `followups`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | NO | PK |
| parent_observation_id | UUID | NO | FK → observations |
| followup_observation_id | UUID | YES | FK → observations; set on submission |
| scheduled_for | DATE | NO | |
| due_window_days | SMALLINT | NO | DEFAULT 3 |
| status | followup_status | NO | 'SCHEDULED' |
| outcome | followup_outcome | YES | BETTER / SAME / WORSE / UNCERTAIN |
| outcome_source | VARCHAR(20) | YES | FARMER_REPORTED / EXPERT_ASSESSED / AI_COMPARED |
| comparison_metadata | JSONB | YES | §23.4 |
| assessed_by | UUID | YES | FK → users(id) |
| notes | TEXT | YES | |
| created_at / updated_at | TIMESTAMPTZ | NO | |

Indexes: `ix_followups_status_scheduled (status, scheduled_for)` for the due-scan job; `ix_followups_parent`.

---

#### `pest_trap_observations`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | NO | PK |
| observation_id | UUID | NO | FK → observations (envelope, type = PEST_TRAP) |
| trap_type | VARCHAR(40) | NO | PHEROMONE / LIGHT / STICKY / OTHER |
| target_agent_id | UUID | YES | FK → disease_pest_catalog |
| catch_count | INT | NO | CHECK ≥ 0 |
| trap_installed_at | TIMESTAMPTZ | YES | |
| counted_at | TIMESTAMPTZ | NO | |
| exposure_hours | NUMERIC(7,2) | YES | enables catch-per-day normalisation |
| trap_identifier | VARCHAR(60) | YES | the farmer's own label |
| created_at | TIMESTAMPTZ | NO | |

---

#### `sensor_observations`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | NO | PK |
| observation_id | UUID | NO | FK → observations (type = SENSOR) |
| device_id | VARCHAR(80) | YES | |
| sensor_type | VARCHAR(40) | NO | SOIL_MOISTURE / LEAF_WETNESS / AIR_TEMP / HUMIDITY / OTHER |
| metric_key | VARCHAR(40) | NO | |
| metric_value | NUMERIC(12,4) | NO | |
| unit | VARCHAR(20) | NO | |
| measured_at | TIMESTAMPTZ | NO | |
| ingestion_method | VARCHAR(20) | NO | MANUAL_ENTRY / API_PUSH / FILE_IMPORT |
| created_at | TIMESTAMPTZ | NO | |

No IoT hardware is required: the MVP path is `MANUAL_ENTRY`, and the schema is already correct for a future `API_PUSH` (§24).

---

#### `hotspots`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | NO | PK |
| hotspot_type | hotspot_type | NO | CONFIRMED / PREDICTED / SIGNAL |
| agent_id | UUID | YES | FK → disease_pest_catalog |
| crop_id | UUID | YES | FK → crops |
| geom | geometry(Polygon,4326) | NO | cluster hull |
| centroid | geometry(Point,4326) | NO | |
| observation_count | INT | NO | |
| confirmed_count | INT | NO | DEFAULT 0 |
| predicted_count | INT | NO | DEFAULT 0 |
| avg_severity | NUMERIC(4,2) | YES | |
| intensity_score | NUMERIC(5,2) | NO | |
| window_start / window_end | TIMESTAMPTZ | NO | |
| algorithm | VARCHAR(40) | NO | e.g. `DBSCAN_V1` |
| algorithm_params | JSONB | NO | eps, minPts, weights — full reproducibility |
| computed_at | TIMESTAMPTZ | NO | |
| is_current | BOOLEAN | NO | DEFAULT true |

Indexes: `gix_hotspots_geom` (GIST); partial `ix_hotspots_current ON hotspots(hotspot_type, agent_id) WHERE is_current`.
Snapshots are retained rather than overwritten, so historical spread can be shown (PRD §6.6).

---

#### `priority_zones`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | NO | PK |
| geom | geometry(Polygon,4326) | NO | |
| admin_region_id | UUID | YES | FK → admin_regions |
| priority_rank | SMALLINT | NO | 1 = highest |
| priority_score | NUMERIC(5,2) | NO | |
| drivers | JSONB | NO | why this zone ranks here |
| confirmed_case_count | INT | NO | |
| predicted_case_count | INT | NO | |
| pending_review_count | INT | NO | |
| window_start / window_end | TIMESTAMPTZ | NO | |
| computed_at | TIMESTAMPTZ | NO | |
| is_current | BOOLEAN | NO | DEFAULT true |

---

#### `data_sources`

Purpose: the register that makes PRD §7.2 enforceable — no dataset may be used until registered and verified.

| Column | Type | Null | Notes |
|---|---|---|---|
| id | UUID | NO | PK |
| code | VARCHAR(60) | NO | UNIQUE |
| name | VARCHAR(200) | NO | |
| source_type | source_type | NO | |
| category | VARCHAR(40) | NO | BOUNDARY / WEATHER / CROP_STATS / TRAINING_DATA / ADVISORY_CONTENT / OTHER |
| provider_name | VARCHAR(150) | YES | |
| url | TEXT | YES | |
| licence | VARCHAR(120) | YES | |
| version_or_release | VARCHAR(60) | YES | |
| retrieved_at | TIMESTAMPTZ | YES | |
| is_verified | BOOLEAN | NO | DEFAULT false |
| verified_by | UUID | YES | FK → users(id) |
| verified_at | TIMESTAMPTZ | YES | |
| notes | TEXT | YES | |

Rule: any UI element rendering data attributed to a source must resolve that source here; a source with `is_verified = false` must be labelled unverified in the UI. This implements "No dataset/API should be represented as official or live without verification" (PRD §7.2).

---

#### `audit_logs`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | BIGSERIAL | NO | PK (append-only, high-volume) |
| actor_user_id | UUID | YES | null for system actions |
| actor_role | user_role | YES | |
| action | VARCHAR(80) | NO | e.g. `EXPERT_DECISION`, `ROLE_CHANGED`, `DEMO_DATA_RESET` |
| entity_type | VARCHAR(60) | NO | |
| entity_id | UUID | YES | |
| before_state | JSONB | YES | |
| after_state | JSONB | YES | |
| ip_address | INET | YES | |
| user_agent | TEXT | YES | |
| trace_id | VARCHAR(64) | YES | correlates with operational logs |
| created_at | TIMESTAMPTZ | NO | |

The application database role has no `UPDATE`/`DELETE` grant on this table.
Indexes: `ix_audit_entity (entity_type, entity_id)`, `ix_audit_actor_time (actor_user_id, created_at DESC)`, `ix_audit_action_time (action, created_at DESC)`.

---

#### `notifications`

`id` UUID PK; `user_id` UUID NOT NULL FK; `type` VARCHAR(40) NOT NULL; `title_key`/`body_key` VARCHAR(120) NOT NULL; `params` JSONB; `entity_type`/`entity_id`; `severity` VARCHAR(20); `dedupe_key` VARCHAR(120) NOT NULL; `read_at` TIMESTAMPTZ NULL; `created_at`. UNIQUE `(user_id, dedupe_key)` prevents spam (PRD §15). Index `ix_notifications_user_unread (user_id, created_at DESC) WHERE read_at IS NULL`.

### 8.4 Entities deliberately not given their own table

| PRD entity | Decision | Rationale |
|---|---|---|
| Role | Enum + permission matrix | Five fixed roles; a table adds joins with no MVP benefit |
| Disease / Pest | Merged into `disease_pest_catalog` with `kind` | Identical structure; avoids duplicated nullable FKs across five tables |
| Image (generic) | `observation_images` only | Images exist only in an observation context in the MVP |
| Weather (single entity) | Split into observations + forecasts | Different natural keys and different cache-invalidation rules |

---

## 9. POSTGIS DESIGN

### 9.1 SRID policy

**Storage SRID: 4326 (WGS84).** All geometry columns are `geometry(<Type>, 4326)`. GPS input is WGS84, GeoJSON is WGS84, Leaflet is WGS84 — anything else forces conversions at both ends.

**Measurement:** never measure in degrees.
- `geography` casting for distances and small buffers: `ST_DWithin(geom::geography, point::geography, radius_m)` — accurate, index-usable, no projection choice needed. **Preferred.**
- A projected metric CRS for area and clustering: EPSG:32643 / 32644 (UTM 43N/44N cover Maharashtra) via `ST_Transform`, used inside the hotspot job where DBSCAN needs metres. **TECHNICAL RECOMMENDATION** — confirm the zone(s) against the deployment extent.

### 9.2 Geometry inventory

| Table.column | Type | SRID | Index | Notes |
|---|---|---|---|---|
| `observations.geom` | Point | 4326 | GIST | the primary spatial workhorse |
| `fields.centroid` | Point | 4326 | GIST | always present |
| `fields.boundary` | Polygon | 4326 | GIST | optional; validated |
| `admin_regions.geom` | MultiPolygon | 4326 | GIST | boundaries |
| `hotspots.geom` | Polygon | 4326 | GIST | cluster hulls |
| `hotspots.centroid` | Point | 4326 | GIST | label placement |
| `priority_zones.geom` | Polygon | 4326 | GIST | |
| `weather_observations.geom` | Point | 4326 | GIST | grid-cell centre |

### 9.3 Index strategy

```sql
CREATE INDEX gix_observations_geom ON observations USING GIST (geom);

-- Partial spatial indexes for the two hottest map queries:
CREATE INDEX gix_obs_geom_confirmed ON observations USING GIST (geom)
  WHERE verification_status IN ('CONFIRMED','CORRECTED') AND deleted_at IS NULL;
CREATE INDEX gix_obs_geom_real ON observations USING GIST (geom)
  WHERE source_type <> 'DEMO_SIMULATION' AND deleted_at IS NULL;

-- Composite for the dominant filter pattern (area + time):
CREATE INDEX ix_obs_district_time ON observations (district_code, observed_at DESC);
```

`ANALYZE` after bulk seeding; `VACUUM` scheduled. **TECHNICAL RECOMMENDATION:** verify each map query with `EXPLAIN (ANALYZE, BUFFERS)` during Phase 4 — do not assume the planner uses the index.

### 9.4 Required spatial queries

**A. Observations within radius (nearby observations)**
```sql
SELECT o.* FROM observations o
WHERE ST_DWithin(o.geom::geography,
                 ST_SetSRID(ST_MakePoint(:lon,:lat),4326)::geography, :radius_m)
  AND o.observed_at >= :since
  AND o.deleted_at IS NULL
  AND (:include_demo OR o.source_type <> 'DEMO_SIMULATION')
ORDER BY o.geom <-> ST_SetSRID(ST_MakePoint(:lon,:lat),4326)
LIMIT :limit;
```
KNN `<->` ordering keeps the sort index-assisted.

**B. Observations inside a field**
```sql
SELECT o.* FROM observations o JOIN fields f ON f.id = :field_id
WHERE (f.boundary IS NOT NULL AND ST_Contains(f.boundary, o.geom))
   OR (f.boundary IS NULL AND ST_DWithin(o.geom::geography, f.centroid::geography, :fallback_m));
```

**C. Observations inside an administrative area** — prefer the denormalised `district_code` (resolved on write); fall back to `ST_Intersects` against `admin_regions.geom` for arbitrary polygons.

**D. Viewport (bbox) query for the map** — `o.geom && ST_MakeEnvelope(:minx,:miny,:maxx,:maxy,4326)`, always combined with a time window and a row limit.

**E. Confirmed cases near a location** — query A plus `verification_status IN ('CONFIRMED','CORRECTED')`. Feeds the risk engine's `nearby_confirmed_cases` factor and the "nearby confirmed case" alert.

**F. Disease/pest-specific filtering** — join on `COALESCE(o.final_agent_id, p.predicted_agent_id)`, and **the API must return which of the two matched**, so the UI can distinguish a confirmed match from a predicted one.

**G. Time-window filtering** — every spatial endpoint requires an explicit or defaulted window; unbounded time is rejected.

**H. Clustering for hotspots**
```sql
SELECT ST_ClusterDBSCAN(ST_Transform(geom, :metric_srid), eps := :eps_m, minpoints := :min_pts)
         OVER () AS cluster_id, id, verification_status, reported_severity
FROM observations
WHERE observed_at BETWEEN :start AND :end AND deleted_at IS NULL;
```
then per cluster: `ST_ConcaveHull(ST_Collect(geom), 0.8)`, falling back to `ST_ConvexHull`, and to `ST_Buffer` of the centroid for clusters of fewer than 3 points.

### 9.5 Spatial guardrails

| Guardrail | Rule |
|---|---|
| Bounded reads | Every `/gis/*` endpoint requires bbox **or** (centre + radius ≤ `GIS_MAX_RADIUS_M`) **or** an admin-region code. Unbounded → `422 BBOX_REQUIRED`. |
| Row cap | Hard `LIMIT` (`GIS_MAX_FEATURES`, default 5000). On overflow the response sets `truncated: true` and the client is told to zoom in or aggregate. |
| Statement timeout | Per-request `SET LOCAL statement_timeout` on GIS endpoints → `504 GIS_TIMEOUT` rather than a hung worker. |
| Validity | `ST_IsValid` on every incoming polygon; repair only on explicit opt-in. |
| Coordinate sanity | Reject `(0,0)`, out-of-range values, and coordinates outside `GIS_OPERATING_BBOX`. |
| Precision | Coordinates stored at 6 decimal places (~0.11 m); more is false precision for phone GPS. |

---

## 10. DATA PROVENANCE ARCHITECTURE

Implements PRD §8 and principle §27.8 ("Every map point should have provenance").

### 10.1 The provenance contract

| Field | Type | Meaning |
|---|---|---|
| `source_type` | enum, **NOT NULL** | FIELD_OBSERVATION / PUBLIC_DATA / GOVERNMENT_DATA / EXPERT_VALIDATION / DEMO_SIMULATION |
| `created_by` | UUID | who introduced the record (null only for system-derived records, which then set `created_by_system`) |
| `created_at` | timestamptz, NOT NULL | when |
| `verification_status` | enum, NOT NULL on observations | the truth state |
| `verified_by` | UUID, NULL | the expert, once verified |
| `verified_at` | timestamptz, NULL | when verified |
| `model_version` | varchar, NULL | which model produced the prediction |
| `original_source_ref` | text, NULL | external identifier for imported data |
| `confidence` | numeric, NULL | model confidence, if any |
| `data_source_id` | UUID, NULL | FK → `data_sources` for imported datasets |

### 10.2 Enforcement (not convention)

1. **Database:** `source_type` is `NOT NULL` with no default on `observations`. A write that forgets it fails.
2. **ORM:** a `ProvenanceMixin` supplies the columns; every observation-like model inherits it.
3. **Service:** `ProvenanceService.stamp(entity, context)` is the only sanctioned way to populate them; it derives `source_type` from the authenticated principal and the entry path (API vs seeder vs importer).
4. **Serialiser:** the shared `ProvenanceOut` sub-model is a **required** field of every observation-bearing response schema, so it cannot be forgotten.
5. **GeoJSON:** the layer serialiser raises if a feature's properties lack `source_type`.
6. **Seeder:** `scripts/seed_demo_data.py` hard-codes `source_type='DEMO_SIMULATION'` and refuses to run when `APP_ENV=production` unless `ALLOW_DEMO_SEED_IN_PROD=true`.
7. **Test:** an integration test asserts no `observations` row has `source_type IS NULL`, and a contract test asserts every observation-returning endpoint emits a provenance block.

### 10.3 Derived-record provenance

| Derived record | Provenance carried |
|---|---|
| `risk_assessments` | `method`, `ruleset_version`, `weather_is_stale`, `missing_factors`, plus the source observation |
| `hotspots` | `algorithm`, `algorithm_params`, `window`, `computed_at`, counts split confirmed/predicted |
| `advisories` | `advisory_ruleset_version`, `confidence_at_generation`, `verification_status_at_generation` |

A hotspot computed from a set that includes demo observations must expose it: `algorithm_params.included_demo_data = true`, and the frontend labels the hotspot accordingly. Default for official dashboards is `include_demo = false`.

### 10.4 Frontend presentation of provenance

| Provenance state | UI treatment |
|---|---|
| FIELD_OBSERVATION + CONFIRMED | Solid marker, green "Expert confirmed" chip, verifier name and date |
| FIELD_OBSERVATION + CORRECTED | Solid marker, "Corrected by expert" chip showing the original prediction beside the correction |
| FIELD_OBSERVATION + PREDICTED | Hollow/dashed marker, amber "AI prediction — not confirmed" chip, confidence meter, model version |
| FIELD_OBSERVATION + PENDING_REVIEW | Dashed marker, "Awaiting expert review" chip |
| FIELD_OBSERVATION + REJECTED | Hidden from default map layers; visible only in the expert/admin audit view |
| DEMO_SIMULATION | Distinct colour, striped pattern, "Simulated demo data" chip, plus a persistent page banner |
| PUBLIC_DATA / GOVERNMENT_DATA | Distinct marker, source name from `data_sources`, plus an "unverified source" warning when `is_verified = false` |

Every map carries a legend listing all applicable states. A judge asking "is this real data?" must be able to answer from the screen alone.

---

## 11. API RESPONSE FORMAT

Defined before the endpoint catalogue because every endpoint refers to it.

### 11.1 Conventions

- Base path `/api/v1`; version in the path, breaking changes mean `/api/v2`.
- Plural, lowercase resource names; sub-resources nested one level (`/observations/{id}/advisory`).
- `POST` create, `GET` read, `PATCH` partial update, `PUT` full replace, `DELETE` soft-delete.
- Timestamps ISO-8601 UTC with `Z`. All list endpoints paginate.
- Every response carries `X-Trace-Id`, echoed in `meta.trace_id`.

### 11.2 Success envelope

```json
{
  "success": true,
  "data": { },
  "meta": { "trace_id": "0f2c...", "timestamp": "2026-09-05T10:15:00Z" }
}
```

Paginated list:
```json
{
  "success": true,
  "data": [ ],
  "meta": {
    "trace_id": "...", "timestamp": "...",
    "pagination": { "page": 1, "page_size": 20, "total_items": 137, "total_pages": 7 },
    "filters_applied": { "district_code": "...", "from": "...", "to": "..." },
    "truncated": false
  }
}
```

### 11.3 Error envelope

```json
{
  "success": false,
  "error": {
    "code": "OBSERVATION_NOT_FOUND",
    "message": "Observation not found.",
    "message_key": "errors.observation_not_found",
    "details": [ { "field": "field_id", "issue": "does_not_exist" } ],
    "retriable": false
  },
  "meta": { "trace_id": "...", "timestamp": "..." }
}
```

`message_key` lets the frontend localise the error instead of showing an English server string (PRD §14).

### 11.4 Error catalogue

| HTTP | `code` | When | Retriable |
|---|---|---|---|
| 400 | `BAD_REQUEST` | Malformed request | no |
| 401 | `AUTH_REQUIRED` | Missing token | no |
| 401 | `AUTH_TOKEN_EXPIRED` | Expired access token — client should refresh | yes (after refresh) |
| 401 | `AUTH_INVALID_CREDENTIALS` | Bad login | no |
| 403 | `FORBIDDEN_ROLE` | Role lacks the permission | no |
| 403 | `FORBIDDEN_OWNERSHIP` | Right role, another user's record | no |
| 404 | `<ENTITY>_NOT_FOUND` | Missing resource | no |
| 409 | `REVIEW_ALREADY_CLAIMED` | Concurrent expert claim | yes |
| 409 | `DUPLICATE_OBSERVATION` | Same image checksum, same field, inside the dedupe window | no |
| 409 | `LAST_ADMIN` | Would remove the final admin | no |
| 413 | `IMAGE_TOO_LARGE` | Over the size limit | no |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | Disallowed content type | no |
| 422 | `VALIDATION_ERROR` | Field-level validation failed (`details` populated) | no |
| 422 | `IMAGE_INVALID` | Undecodable/corrupt image | no |
| 422 | `CROP_CONTEXT_MISMATCH` | Variety/stage not valid for the crop | no |
| 422 | `GEOMETRY_INVALID` | Invalid polygon | no |
| 422 | `COORDINATES_OUT_OF_BOUNDS` | Outside the operating bbox | no |
| 422 | `BBOX_REQUIRED` | Unbounded spatial query | no |
| 429 | `RATE_LIMITED` | Over quota (`Retry-After` set) | yes |
| 500 | `INTERNAL_ERROR` | Unhandled — generic message only | yes |
| 502 | `WEATHER_PROVIDER_ERROR` | Provider returned an error | yes |
| 503 | `WEATHER_UNAVAILABLE` | No live and no cached weather | yes |
| 503 | `AI_MODEL_UNAVAILABLE` | No model loaded | yes |
| 503 | `AI_INFERENCE_FAILED` | Inference raised | yes |
| 503 | `STORAGE_UNAVAILABLE` | Object store unreachable | yes |
| 503 | `RISK_UNAVAILABLE` | Ruleset unloadable | yes |
| 504 | `GIS_TIMEOUT` | Spatial query exceeded the timeout | yes |

### 11.5 Degraded-success responses

Some operations succeed while a sub-step fails. These return `200`/`201` with a `warnings` array — not errors; the UI renders them as degraded state:

```json
{
  "success": true,
  "data": { "id": "...", "status": "COMPLETED", "risk": { } },
  "warnings": [
    { "code": "WEATHER_STALE", "message_key": "warnings.weather_stale",
      "detail": { "fetched_at": "2026-09-04T06:00:00Z" } }
  ],
  "meta": { }
}
```

Warning codes: `WEATHER_STALE`, `WEATHER_UNAVAILABLE`, `AI_LOW_CONFIDENCE`, `RISK_PARTIAL_INPUTS`, `LANGUAGE_FALLBACK`, `HOTSPOT_INSUFFICIENT_DATA`, `DEMO_DATA_INCLUDED`.

`DEMO_DATA_INCLUDED` is how the UI knows to show the demo banner.

---

## 12. API SPECIFICATION

All endpoints are under `/api/v1`. All use the envelope of §11. `Auth` column: `—` public, `JWT` any authenticated user, or the list of permitted roles.

Notation used in the tables: `P` = FARMER, `E` = EXTENSION_WORKER, `L` = LAB_EXPERT, `O` = OFFICIAL, `A` = ADMIN.

### 12.1 Authentication

| Method | URL | Purpose | Auth | Request | Response | Codes |
|---|---|---|---|---|---|---|
| POST | `/auth/register` | Self-register a farmer | — | `{full_name, phone, password, preferred_language, village?, district_code?}` | `{user, tokens}` | 201, 409 (duplicate phone), 422 |
| POST | `/auth/login` | Obtain tokens | — | `{identifier, password}` | `{access_token, refresh_token, expires_in, user}` | 200, 401, 429 |
| POST | `/auth/refresh` | Rotate tokens | refresh token | `{refresh_token}` | `{access_token, refresh_token, expires_in}` | 200, 401 |
| POST | `/auth/logout` | Revoke the refresh token | JWT | `{refresh_token}` | `{revoked: true}` | 204, 401 |
| GET | `/auth/me` | Current principal | JWT | — | `{user, permissions[]}` | 200, 401 |
| POST | `/auth/change-password` | Change own password | JWT | `{current_password, new_password}` | `{changed: true}` | 200, 401, 422 |

Validation: password minimum length and complexity per §13.2; `identifier` accepts phone, email or username.
DB effects: `users` insert on register; `last_login_at` update on login; `refresh_tokens` insert/revoke; `audit_logs` entry for register, login-failure and password change.

Non-admin registration creates only `FARMER` accounts. Expert, official and admin accounts are created by an admin (`POST /users`) — self-service registration must never mint a privileged role.

### 12.2 Users and roles

| Method | URL | Purpose | Auth |
|---|---|---|---|
| GET | `/users` | List/filter users (`role`, `district_code`, `is_active`, `q`) | A |
| POST | `/users` | Create a user with any role | A |
| GET | `/users/{id}` | User detail | A, or self |
| PATCH | `/users/{id}` | Update profile fields | A, or self (non-role fields only) |
| PATCH | `/users/{id}/role` | Change role | A |
| POST | `/users/{id}/deactivate` | Soft-deactivate | A |
| GET | `/roles` | Enumerate roles and their permissions | JWT |

Errors: `409 LAST_ADMIN` on demoting/deactivating the final admin. Every write here produces an `audit_logs` entry with `before_state`/`after_state`.

### 12.3 Farmers

| Method | URL | Purpose | Auth |
|---|---|---|---|
| GET | `/farmers/me` | Own farmer profile | P |
| PATCH | `/farmers/me` | Update own profile | P |
| GET | `/farmers` | List farmers (filter by district) | E, O, A |
| GET | `/farmers/{id}` | Farmer detail | E, O, A, or self |

`O` sees only farmers within their `district_code` scope (§13.6).

### 12.4 Fields

| Method | URL | Purpose | Auth | Notes |
|---|---|---|---|---|
| GET | `/fields` | List own fields (P) or scoped fields (E/O/A) | JWT | filters: `farmer_id`, `district_code`, `crop_id` |
| POST | `/fields` | Create a field | P, E | body: `{name, latitude, longitude, boundary?(GeoJSON Polygon), area_ha?, soil_type?, irrigation_type?, current_crop_id?, current_variety_id?, sowing_date?}` |
| GET | `/fields/{id}` | Field detail + current crop + latest risk | owner, E, O, A | |
| PATCH | `/fields/{id}` | Update | owner, E, A | |
| DELETE | `/fields/{id}` | Soft-delete | owner, A | refuses if observations exist unless `?cascade=false` acknowledged |
| GET | `/fields/{id}/observations` | Observations in this field | owner, E, O, A | spatial query B (§9.4) |
| GET | `/fields/{id}/risk` | Latest and historical field risk | owner, E, O, A | |
| POST | `/fields/{id}/crop` | Assign/change the current crop context | owner, E | |

Validation: `422 GEOMETRY_INVALID`, `422 COORDINATES_OUT_OF_BOUNDS`, `422 CROP_CONTEXT_MISMATCH`.
DB effects: `fields` row with `centroid` (and `boundary`) geometry; `district_code` resolved by point-in-polygon on write.

### 12.5 Crops (reference data)

| Method | URL | Purpose | Auth |
|---|---|---|---|
| GET | `/crops` | List active crops (localised names) | JWT |
| GET | `/crops/{id}/varieties` | Varieties of a crop | JWT |
| GET | `/crops/{id}/growth-stages` | Ordered growth stages | JWT |
| GET | `/catalog/agents` | Diseases/pests (filter `kind`, `crop_id`, `is_ai_supported`) | JWT |
| GET | `/catalog/symptoms` | Symptom vocabulary | JWT |
| POST/PATCH | `/admin/catalog/*` | Manage reference data | A |

Localisation: names are returned in the negotiated language with an `available_languages` array.

### 12.6 Observations

| Method | URL | Purpose | Auth |
|---|---|---|---|
| POST | `/observations` | Create an observation (the core write) | P, E |
| GET | `/observations` | List/filter | JWT (role-scoped) |
| GET | `/observations/{id}` | Full detail: prediction, risk, advisory, review, follow-up, provenance | owner, E, L, O, A |
| GET | `/observations/{id}/status` | Lightweight poll target | owner, E, A |
| PATCH | `/observations/{id}` | Update notes/severity (not diagnosis) | owner (before review), E, A |
| DELETE | `/observations/{id}` | Soft-delete | owner (before review), A |
| POST | `/observations/{id}/reanalyze` | Re-run inference with the current active model | E, A |

**`POST /observations`** — `multipart/form-data`:

| Part | Type | Required | Notes |
|---|---|---|---|
| `image` | file | when `observation_type=IMAGE` | see §14 |
| `payload` | JSON | yes | see below |

```json
{
  "field_id": "uuid|null",
  "crop_id": "uuid|null",
  "variety_id": "uuid|null",
  "growth_stage_id": "uuid|null",
  "observation_type": "IMAGE|PEST_TRAP|SENSOR|MANUAL_REPORT",
  "latitude": 19.123456,
  "longitude": 74.654321,
  "gps_accuracy_m": 8.4,
  "location_method": "DEVICE_GPS|MAP_PIN|FIELD_CENTROID",
  "observed_at": "2026-09-05T09:12:00Z",
  "reported_severity": 3,
  "notes": "string|null",
  "trap": { "trap_type": "...", "catch_count": 12, "counted_at": "...", "exposure_hours": 24 },
  "sensor": { "sensor_type": "...", "metric_key": "...", "metric_value": 0.0, "unit": "...", "measured_at": "..." }
}
```

Response `202 Accepted`:
```json
{ "success": true,
  "data": { "id": "uuid", "status": "PROCESSING", "verification_status": "PREDICTED",
            "poll_url": "/api/v1/observations/{id}/status" },
  "meta": { } }
```

Validation: field ownership; crop/variety/stage consistency; coordinate range and operating bbox; `observed_at` not in the future beyond a small clock-skew allowance; image required for `IMAGE`; `trap` required for `PEST_TRAP`; `sensor` required for `SENSOR`.
Errors: `422 VALIDATION_ERROR`, `422 IMAGE_INVALID`, `409 DUPLICATE_OBSERVATION`, `403 FORBIDDEN_OWNERSHIP`, `503 STORAGE_UNAVAILABLE`.
DB effects: `observations` + `observation_images` (+ `pest_trap_observations` / `sensor_observations`) inserted; downstream `ai_predictions`, `risk_assessments`, `advisories`, `followups`, `expert_reviews` written asynchronously by the pipeline; `audit_logs` entry.

**`GET /observations` filters:** `field_id`, `farmer_id`, `crop_id`, `agent_id`, `verification_status`, `status`, `source_type`, `district_code`, `from`, `to`, `include_demo` (default `false` for `O`, `true` for `P`/`E` viewing their own data), `page`, `page_size`, `sort`.

**`GET /observations/{id}` response shape (abbreviated):**
```json
{
  "id": "uuid",
  "status": "COMPLETED",
  "verification_status": "PENDING_REVIEW",
  "crop_context": { "crop": {}, "variety": {}, "growth_stage": {} },
  "location": { "latitude": 0, "longitude": 0, "accuracy_m": 8.4,
                "method": "DEVICE_GPS", "district_code": "..." },
  "images": [ { "id": "uuid", "url": "/api/v1/images/{id}", "thumbnail_url": "...",
                "quality_flags": {} } ],
  "prediction": { "predicted_class": "...", "agent": {}, "confidence": 0.61,
                  "is_low_confidence": true, "top_k": [], "model_version": "crop-clf-v0.1.0",
                  "severity_estimate": null },
  "weather": { "temperature_c": 0, "humidity_pct": 0, "rainfall_mm_24h": 0,
               "is_stale": false, "fetched_at": "..." },
  "risk": { "score": 0, "level": "MEDIUM", "forecast_period": {},
            "contributing_factors": [], "missing_factors": [],
            "explanation": "localised sentence", "uncertainty": 0.2,
            "method": "RULE_BASED_V1", "ruleset_version": "v1.0.0" },
  "advisory": { "id": "uuid", "language": "mr", "sections": {} },
  "review": { "state": "QUEUED", "decision": null, "expert": null },
  "followup": { "id": "uuid", "scheduled_for": "2026-09-12", "status": "SCHEDULED" },
  "provenance": { "source_type": "FIELD_OBSERVATION", "created_by": {}, "created_at": "...",
                  "verified_by": null, "verified_at": null,
                  "model_version": "crop-clf-v0.1.0", "data_source": null },
  "processing_errors": null
}
```

The `prediction` block and the `verification_status` field are separate and both always present. A client cannot render a diagnosis without also having the verification status in hand.

### 12.7 Images

| Method | URL | Purpose | Auth |
|---|---|---|---|
| POST | `/observations/{id}/images` | Add an image to an existing observation | owner, E |
| GET | `/images/{id}` | Fetch the image (signed/authorised) | owner, E, L, O, A |
| GET | `/images/{id}/thumbnail` | Fetch the thumbnail | same |
| DELETE | `/images/{id}` | Remove a non-primary image | owner (pre-review), A |

Images are never publicly addressable; see §14.6.

### 12.8 AI

| Method | URL | Purpose | Auth |
|---|---|---|---|
| POST | `/ai/analyze` | Stateless inference on an uploaded image (no observation created) — for testing and the expert console | E, L, A |
| GET | `/ai/models` | List registered models | E, L, O, A |
| GET | `/ai/models/active` | The active model, its class list and thresholds | JWT |
| POST | `/admin/ai/models` | Register a model version | A |
| POST | `/admin/ai/models/{version}/activate` | Activate a model version | A |

`POST /ai/analyze` response: `{predicted_class, agent, confidence, top_k, is_low_confidence, model_version, inference_ms}`, plus a mandatory `disclaimer_key` so no caller can present it as a diagnosis.
Errors: `503 AI_MODEL_UNAVAILABLE`, `503 AI_INFERENCE_FAILED`, `422 IMAGE_INVALID`.

### 12.9 Weather

| Method | URL | Purpose | Auth |
|---|---|---|---|
| GET | `/weather/current?lat=&lon=` | Current conditions | JWT |
| GET | `/weather/forecast?lat=&lon=&days=` | Forecast | JWT |
| GET | `/weather/historical?lat=&lon=&from=&to=` | Historical, **only if the selected provider supports it** | JWT |
| GET | `/fields/{id}/weather` | Weather for a field's centroid | owner, E, O, A |

Every weather response includes `{provider, fetched_at, is_stale, cache_hit}`. If historical data is unsupported by the configured provider the endpoint returns `501 NOT_IMPLEMENTED` with `message_key: errors.weather_historical_unsupported` — it does not synthesise values.
Errors: `502 WEATHER_PROVIDER_ERROR`, `503 WEATHER_UNAVAILABLE`, `429 RATE_LIMITED`.

### 12.10 Risk

| Method | URL | Purpose | Auth |
|---|---|---|---|
| GET | `/risk/observations/{id}` | Risk for an observation | owner, E, O, A |
| GET | `/risk/fields/{id}` | Latest field risk | owner, E, O, A |
| GET | `/risk/fields/{id}/history?from=&to=` | Risk time series | owner, E, O, A |
| POST | `/risk/recalculate` | Force recalculation for an observation or field | E, A |
| GET | `/risk/ruleset` | The active ruleset version, factors and thresholds (transparency) | E, O, A |

`GET /risk/ruleset` exists so an expert or a judge can inspect exactly how a score was produced — this is the concrete implementation of "Explainability over black-box claims" (PRD §27.2).

### 12.11 GIS

| Method | URL | Purpose | Auth |
|---|---|---|---|
| GET | `/gis/observations` | Observation points as GeoJSON | JWT (role-scoped) |
| GET | `/gis/fields` | Field points/polygons as GeoJSON | JWT |
| GET | `/gis/layers/{layer}` | A named layer: `confirmed_cases`, `predicted_cases`, `risk_zones`, `hotspots`, `priority_zones` | JWT |
| GET | `/gis/nearby?lat=&lon=&radius_m=&days=` | Nearby observations (query A) | JWT |
| GET | `/gis/admin-regions?level=&parent_code=` | Boundaries as GeoJSON | JWT |

Common parameters: `bbox=minx,miny,maxx,maxy` **or** `lat`+`lon`+`radius_m` **or** `district_code`; `from`, `to`; `crop_id`; `agent_id`; `verification_status`; `include_demo` (default false for `O`); `limit`.

Response is a GeoJSON `FeatureCollection`; every feature's `properties` carries at minimum `{id, source_type, verification_status, agent_code, confidence, observed_at, match_basis}` where `match_basis` is `CONFIRMED_AGENT` or `PREDICTED_AGENT` (§9.4-F). Envelope metadata carries `truncated` and `include_demo`.
Errors: `422 BBOX_REQUIRED`, `504 GIS_TIMEOUT`.

### 12.12 Hotspots

| Method | URL | Purpose | Auth |
|---|---|---|---|
| GET | `/hotspots` | Current hotspots (filters: `hotspot_type`, `agent_id`, `crop_id`, `district_code`, window) | E, O, A |
| GET | `/hotspots/{id}` | Detail with the contributing observation ids | E, O, A |
| GET | `/hotspots/history?from=&to=` | Past snapshots for spread analysis | O, A |
| POST | `/admin/hotspots/recompute` | Trigger recomputation | A |
| GET | `/gis/priority-zones` | Ranked priority intervention zones | O, A |

Every hotspot response carries `algorithm`, `algorithm_params`, `computed_at`, `confirmed_count`, `predicted_count` and `included_demo_data`. When there is not enough data the response is an empty collection with `meta.reason = "INSUFFICIENT_DATA"`.

### 12.13 Expert review

| Method | URL | Purpose | Auth |
|---|---|---|---|
| GET | `/reviews/queue` | Pending queue, priority-ordered (filters: `district_code`, `crop_id`, `agent_id`, `min_priority`) | E, L, A |
| GET | `/reviews/{id}` | Case detail: image, prediction, context, weather, risk, nearby cases | E, L, A |
| POST | `/reviews/{id}/claim` | Claim the case | E, L |
| POST | `/reviews/{id}/release` | Release a claim | claimant, A |
| POST | `/reviews/{id}/decision` | Confirm / correct / reject | claimant |
| POST | `/reviews/{id}/refer` | Refer to a laboratory | claimant |
| POST | `/reviews/{id}/lab-result` | Record a lab result | L |
| GET | `/reviews/history?observation_id=` | Full review history for an observation | E, L, O, A |

`POST /reviews/{id}/decision` body:
```json
{ "decision": "CONFIRMED|CORRECTED|REJECTED",
  "corrected_agent_id": "uuid|null",
  "confirmed_severity": 3,
  "expert_notes": "string" }
```
Validation: `corrected_agent_id` required when `decision = CORRECTED`; the caller must hold an unexpired claim.
DB effects: `expert_reviews` updated; `observations.verification_status` and `final_agent_id` updated; the existing advisory marked `is_superseded` and a new one generated; hotspot recomputation invalidated; `audit_logs` entry with `action = EXPERT_DECISION`.
Errors: `409 REVIEW_ALREADY_CLAIMED`, `403 FORBIDDEN_OWNERSHIP` (not the claimant), `422 VALIDATION_ERROR`.

### 12.14 Advisory

| Method | URL | Purpose | Auth |
|---|---|---|---|
| GET | `/observations/{id}/advisory` | Current advisory in the negotiated language | owner, E, L, O, A |
| GET | `/advisories/{id}` | Advisory by id | same |
| GET | `/advisories?observation_id=&include_superseded=` | History | owner, E, A |
| POST | `/advisories/regenerate` | Regenerate for an observation | E, A |
| GET | `/admin/advisory-templates` / POST / PATCH | Manage templates | A |

Language: `Accept-Language` header, overridable by `?lang=`. Response carries `language`, `language_fallback` and `advisory_ruleset_version`.

### 12.15 Interventions and follow-up

| Method | URL | Purpose | Auth |
|---|---|---|---|
| POST | `/observations/{id}/interventions` | Record what the farmer did | owner, E |
| GET | `/observations/{id}/interventions` | List | owner, E, L, O, A |
| GET | `/followups` | List (filters `status`, `due_before`, `farmer_id`) | owner, E, A |
| GET | `/followups/{id}` | Detail with the parent observation | owner, E, A |
| POST | `/followups/{id}/submit` | Submit the follow-up observation (creates a child observation) | owner, E |
| POST | `/followups/{id}/assess` | Expert assessment of the outcome | E, A |
| GET | `/followups/{id}/comparison` | Side-by-side parent/child comparison metadata | owner, E, A |
| POST | `/observations/{id}/followups` | Manually schedule an extra follow-up | owner, E |

`POST /followups/{id}/submit` accepts the same multipart shape as `POST /observations`, plus `{outcome: BETTER|SAME|WORSE|UNCERTAIN, notes}`. It creates a new `observations` row with `parent_observation_id` set, runs the full pipeline on it, and updates the `followups` row to `SUBMITTED`.

### 12.16 Pest traps and sensors

| Method | URL | Purpose | Auth |
|---|---|---|---|
| POST | `/traps/observations` | Record a trap count (creates the observation envelope) | P, E |
| GET | `/traps/observations` | List/filter trap counts | JWT (scoped) |
| GET | `/traps/series?field_id=&from=&to=` | Catch-per-day time series | owner, E, O, A |
| POST | `/sensors/observations` | Manual sensor reading | P, E |
| POST | `/sensors/ingest` | Batch ingest (future device path) | E, A (device key: **REQUIRES DECISION**) |
| GET | `/sensors/series?field_id=&metric_key=&from=&to=` | Sensor time series | owner, E, O, A |

### 12.17 Dashboards

| Method | URL | Purpose | Auth |
|---|---|---|---|
| GET | `/dashboards/farmer` | Farmer KPIs and recent activity | P |
| GET | `/dashboards/expert` | Queue depth, decisions made, agreement/correction counts | E, L |
| GET | `/dashboards/official` | Surveillance KPIs | O, A |
| GET | `/dashboards/official/trends` | Time series by agent/crop/district | O, A |
| GET | `/dashboards/official/distribution` | Distribution by agent, crop, district | O, A |
| GET | `/dashboards/official/coverage` | Surveillance coverage metrics | O, A |

Shared filters: `from`, `to`, `district_code`, `crop_id`, `agent_id`, `include_demo` (default false for `O`). See §25 for the exact metric definitions.

### 12.18 Data sources, notifications, admin, health

| Method | URL | Purpose | Auth |
|---|---|---|---|
| GET | `/data-sources` | List registered sources with verification status | JWT |
| GET | `/data-sources/{code}` | Source detail | JWT |
| POST/PATCH | `/admin/data-sources` | Register/update a source | A |
| POST | `/admin/data-sources/{id}/verify` | Mark verified (records `verified_by`/`verified_at`) | A |
| GET | `/notifications` | Own inbox | JWT |
| POST | `/notifications/{id}/read` | Mark read | JWT |
| GET | `/admin/audit-logs` | Query the audit trail | A |
| POST | `/admin/demo-data/seed` | Seed demo data | A |
| POST | `/admin/demo-data/reset` | Delete all `DEMO_SIMULATION` rows | A |
| GET | `/health` | Liveness + component status | — |
| GET | `/health/ready` | Readiness (DB, storage, model) | — |

`GET /health` returns `{status, components: {database, storage, ai_model, weather_provider}, version, git_sha}` — the AI component reports `AI_DEGRADED` when no model is loaded, which is how the demo operator knows before a judge does.

---

## 13. AUTHENTICATION & AUTHORIZATION

### 13.1 Mechanism

Stateless JWT access tokens plus stored, rotating refresh tokens. **TECHNICAL RECOMMENDATION** — the PRD requires authentication but does not name a mechanism.

| Token | Lifetime | Storage | Contents |
|---|---|---|---|
| Access | 30 min (`JWT_ACCESS_TTL_MIN`) | client memory | `sub` (user id), `role`, `jti`, `iat`, `exp`, `farmer_id?`, `district_code?` |
| Refresh | 14 days (`JWT_REFRESH_TTL_DAYS`) | see §13.4 | opaque random string, hashed in `refresh_tokens` |

Algorithm HS256 with a single strong secret for MVP; RS256 is the documented upgrade path if tokens ever need to be verified by a separate service.

`refresh_tokens` table: `id` UUID PK; `user_id` FK; `token_hash` CHAR(64) UNIQUE; `issued_at`; `expires_at`; `revoked_at` NULL; `replaced_by` UUID NULL; `user_agent`; `ip_address`. Rotation on every refresh, with reuse detection: presenting an already-rotated token revokes the whole chain and writes an audit entry.

### 13.2 Password handling

- Argon2id via `passlib`, per-password salt, parameters from configuration.
- Minimum 8 characters; rejected if it appears in a small bundled common-password list. **TECHNICAL RECOMMENDATION** — kept deliberately light because the primary users are farmers on feature-limited phones; the tradeoff is stated rather than hidden.
- Never logged, never returned, never included in an audit `before_state`/`after_state`.
- Login comparison is constant-time and the error message is identical for unknown user and wrong password.

> **REQUIRES DECISION — OTP login.** Phone-based OTP is the conventional Indian pattern for farmer-facing apps and would remove passwords entirely, but it requires an SMS gateway (vendor, cost, DLT registration). No gateway is assumed here. If one is approved, add it as an alternative `AuthProvider` behind the same `AuthService` interface; password login stays for expert/official/admin.

### 13.3 Protected routes and endpoints

Backend: `Depends(get_current_user)` on every non-public route; `Depends(require_roles(...))` where a role restriction applies; ownership checks in the service layer (a farmer may only touch their own fields, observations and follow-ups).

Frontend: a `RequireAuth` guard and a `RequireRole` guard wrap route groups. **Frontend guards are UX only** — every rule is independently enforced server-side, because a client-side guard is not a security control.

### 13.4 Refresh-token storage on the client

> **REQUIRES DECISION — refresh token transport.**
> Two acceptable options, with the tradeoff stated rather than assumed:
> - **(a) `httpOnly; Secure; SameSite=Lax` cookie** — immune to XSS token theft, requires CSRF protection on state-changing requests and a same-site deployment.
> - **(b) `localStorage`** — simpler, works across origins, but readable by any injected script.
>
> **TECHNICAL RECOMMENDATION: option (a)** for anything beyond the demo, with the access token held only in memory. Option (b) is acceptable for a hackathon demo **if** the team records the choice explicitly. Whichever is chosen must be recorded in an ADR, not left implicit.

### 13.5 Role permission matrix

| Capability | FARMER | EXTENSION_WORKER | LAB_EXPERT | OFFICIAL | ADMIN |
|---|:--:|:--:|:--:|:--:|:--:|
| Register self | ✔ | — | — | — | ✔ (creates any) |
| Manage own profile | ✔ | ✔ | ✔ | ✔ | ✔ |
| Create/edit own fields | ✔ | ✔ (on behalf) | — | — | ✔ |
| View own fields/observations | ✔ | ✔ | — | — | ✔ |
| View others' observations | — | ✔ (scoped) | ✔ (referred cases) | ✔ (scoped, aggregate + detail) | ✔ |
| Create observation | ✔ | ✔ | — | — | ✔ |
| Upload image | ✔ | ✔ | ✔ (lab image) | — | ✔ |
| Run `/ai/analyze` | — | ✔ | ✔ | — | ✔ |
| Claim/decide a review | — | ✔ | ✔ | — | ✔ |
| Refer to lab | — | ✔ | ✔ | — | ✔ |
| Record a lab result | — | — | ✔ | — | ✔ |
| View review queue | — | ✔ | ✔ | ✔ (counts only) | ✔ |
| View own advisory | ✔ | ✔ | ✔ | ✔ | ✔ |
| Regenerate advisory | — | ✔ | — | — | ✔ |
| Submit follow-up | ✔ | ✔ | — | — | ✔ |
| Assess follow-up outcome | — | ✔ | ✔ | — | ✔ |
| Official dashboards | — | partial | — | ✔ | ✔ |
| Hotspots / priority zones | — | ✔ | — | ✔ | ✔ |
| Manage users/roles | — | — | — | — | ✔ |
| Manage catalog/models/templates | — | — | — | — | ✔ |
| Manage data sources | — | — | — | — | ✔ |
| Seed/reset demo data | — | — | — | — | ✔ |
| Read audit logs | — | — | — | — | ✔ |

Implemented as a single dict in `core/rbac.py`, exposed via `GET /roles`, and asserted directly by the RBAC test matrix (§34.3) so the table and the code cannot drift apart.

### 13.6 Data-scoping rules (beyond role)

| Role | Scope |
|---|---|
| FARMER | Only rows where `farmer_id` = own farmer id |
| EXTENSION_WORKER | Rows in the districts assigned to the worker (`users.district_code`, extensible to a many-to-many assignment table) |
| LAB_EXPERT | Only observations referred to a lab, plus their own decisions |
| OFFICIAL | Rows within `users.district_code`; a state-level official has `district_code = NULL`, meaning statewide |
| ADMIN | Unrestricted, every access audited |

Scoping is applied in the repository layer as a mandatory query filter derived from `CurrentUser`, not sprinkled through routers — so a new endpoint inherits scoping by construction.

---

## 14. IMAGE STORAGE & PROCESSING

### 14.1 Accepted formats and limits

| Property | Value | Configurable via |
|---|---|---|
| Formats | JPEG, PNG, WebP | `IMAGE_ALLOWED_MIME` |
| Max upload size | 10 MB | `IMAGE_MAX_BYTES` |
| Min dimensions | 224 × 224 px | `IMAGE_MIN_EDGE_PX` |
| Max dimensions | 8000 × 8000 px (guards against decompression bombs) | `IMAGE_MAX_EDGE_PX` |
| Max images per observation | 5 | `IMAGE_MAX_PER_OBSERVATION` |

**TECHNICAL RECOMMENDATION** on all numbers; they balance rural bandwidth against usable detail and should be revisited after field testing.

### 14.2 Validation pipeline (in order, fail fast)

1. Content-length pre-check before reading the body.
2. Extension check (cheap reject).
3. **Magic-byte content sniffing** — the declared `Content-Type` is not trusted.
4. Decode with Pillow inside a size guard; a decode failure → `422 IMAGE_INVALID`.
5. Dimension bounds check.
6. `Image.verify()` followed by a full re-open, to reject truncated files.
7. SHA-256 checksum; duplicate detection against the same field within `IMAGE_DEDUPE_WINDOW_HOURS` → `409 DUPLICATE_OBSERVATION`.
8. Quality heuristics (recorded, not fatal): Laplacian variance for blur, mean luminance for exposure, dominant-colour check for obviously non-plant images. Results go into `quality_flags` and, when severe, set observation status `UNSUPPORTED_IMAGE`.

**Never** trust or execute file contents; never use the client filename as a storage path; sanitise it and store only for display.

### 14.3 Preprocessing

Two derived artefacts, both created at upload:
- **Storage original** — EXIF orientation applied, then EXIF stripped except capture time and GPS (which are copied to database columns first), re-encoded to JPEG quality 85, longest edge capped at `IMAGE_STORE_MAX_EDGE_PX` (2048). Stripping metadata is a privacy control (§30).
- **Thumbnail** — 320 px longest edge, for lists and map popups.

Inference preprocessing is separate and model-specific (§15.3), performed in memory from the stored original — never from the thumbnail.

### 14.4 Storage strategy

A `Storage` adapter with two implementations:

```python
class Storage(ABC):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def sign_url(self, key: str, ttl_seconds: int) -> str | None: ...
```

- `LocalStorage` — a mounted directory outside the web root, keys used as relative paths. Default for local development and the SIH demo.
- `S3CompatibleStorage` — any S3-compatible object store (MinIO, or a cloud provider once one is chosen). **REQUIRES DECISION — the production object store and region.**

Key scheme: `observations/{yyyy}/{mm}/{observation_id}/{image_id}.jpg`, thumbnails under `.../thumb_{image_id}.jpg`. Date-partitioned so retention and archival are simple directory or lifecycle operations.

Binary image data is **not** stored in database rows (PRD §20). The database stores keys, checksums and metadata only.

### 14.5 Metadata captured

`mime_type`, `size_bytes`, `width_px`, `height_px`, `checksum_sha256`, `exif_captured_at`, `exif_latitude`, `exif_longitude`, `quality_flags`, `uploaded_by`, `created_at`.

EXIF GPS, when present, is compared against the reported GPS; a discrepancy beyond `IMAGE_EXIF_GPS_TOLERANCE_M` is recorded in `quality_flags.gps_mismatch_m` and surfaced to the reviewing expert. This is a data-integrity signal, not a rejection.

### 14.6 Secure access

Images are never publicly addressable. `GET /images/{id}` authenticates the caller, checks ownership/role scope, then either streams the bytes (LocalStorage) or issues a short-lived signed URL (S3-compatible, TTL `IMAGE_SIGNED_URL_TTL_SEC`, default 300 s). Storage keys are UUID-based, so they are unguessable even if a signed URL leaks after expiry.

### 14.7 Cleanup and retention

| Situation | Behaviour |
|---|---|
| Observation soft-deleted | Image rows retained; files retained until the retention window elapses |
| Observation hard-deleted (admin) | Files deleted, an audit entry written |
| Orphan files (upload succeeded, transaction rolled back) | A nightly worker job deletes storage keys with no matching `observation_images` row, older than 24 h |
| Demo data reset | All `DEMO_SIMULATION` images deleted with their rows |
| Retention window | `IMAGE_RETENTION_DAYS`, **REQUIRES DECISION** — depends on the data-retention policy in §30 |

---

## 15. AI/ML TECHNICAL DESIGN

### 15.1 Design principle

The model is a **replaceable component behind an interface**, not a hard-coded dependency (T12, PRD §11). Nothing above the interface knows the framework, the architecture, or the class list.

### 15.2 The model interface

```python
@dataclass(frozen=True)
class PredictionResult:
    predicted_class: str
    confidence: float                      # 0..1
    top_k: list[tuple[str, float]]
    severity_estimate: float | None = None
    boxes: list[dict] | None = None        # detection tasks only
    inference_ms: int = 0

class ModelRunner(ABC):
    @abstractmethod
    def load(self, artifact_path: str) -> None: ...
    @abstractmethod
    def predict(self, image: np.ndarray) -> PredictionResult: ...
    @abstractmethod
    def metadata(self) -> ModelMetadata: ...   # version, task, class_list, input_size
    @abstractmethod
    def warmup(self) -> None: ...
```

Provided implementations:
- `TorchClassifierRunner` — PyTorch image classification.
- `YoloDetectorRunner` — Ultralytics detection, for pest counting or lesion localisation where classification is insufficient.
- `StubRunner` — a deterministic, clearly-labelled stub used in tests and in CI. **It sets `model_version = "stub-v0"` and every consumer treats stub output as non-diagnostic.** This exists so Phases 3–9 can be built and tested before a trained model is available, without anyone mistaking stub output for a real prediction.

### 15.3 Inference pipeline

```
stored original bytes
  → decode (OpenCV/Pillow)
  → colour-space normalisation (BGR→RGB)
  → resize / letterbox to the model's declared input_size
  → normalise (per-model mean/std from ModelMetadata)
  → batch of 1 → ModelRunner.predict()
  → map raw class label → disease_pest_catalog.code (via ai_model_registry.class_list)
  → confidence gate (§15.5)
  → persist ai_predictions
```

Preprocessing parameters live in `ModelMetadata`, not in the calling code, so a model swap cannot silently break preprocessing.

### 15.4 Model loading and lifecycle

- Loaded once at application startup (FastAPI `lifespan`), held in a module-level singleton, warmed with a synthetic tensor so the first real request does not pay initialisation cost.
- The active version comes from `ai_model_registry` where `is_active` is true; the artefact checksum is verified against `artifact_checksum` before loading. A mismatch aborts loading and reports `AI_DEGRADED` — a silently swapped weights file must not go unnoticed.
- `POST /admin/ai/models/{version}/activate` flips the active row and triggers a reload; the old model stays loaded until the new one is ready, so activation causes no request failures.
- Torch runs in `eval()` mode with `torch.inference_mode()`, and thread counts are pinned via `TORCH_NUM_THREADS` to keep CPU inference predictable alongside the API workers.

### 15.5 Confidence thresholds and behaviour

Thresholds are **per model**, stored in `ai_model_registry`, never hard-coded:

| Band | Condition | Observation outcome |
|---|---|---|
| High | `confidence ≥ high_confidence_threshold` | `verification_status = PREDICTED`; preliminary assessment shown with an "AI prediction, not confirmed" label; advisory generated; expert review offered but not forced |
| Low | `confidence < high_confidence_threshold` | `verification_status = PENDING_REVIEW`; `expert_reviews` row queued; the UI shows "Awaiting expert review" and a **cautious** advisory only |
| Very low | `confidence < low_confidence_threshold` | As above, plus the predicted class is de-emphasised in the UI and the advisory becomes the generic "consult an expert" fallback |

> **REQUIRES DECISION — threshold values.** Correct thresholds can only be set from a validation-set confidence distribution, which does not exist until a model is trained. Seeding a number here would be inventing accuracy. The values must be derived in Phase 2 from an actual evaluation run and recorded in `ai_model_registry` with the evaluation that justified them.

### 15.6 Synchronous vs asynchronous inference

**MVP: synchronous** inside the request that follows observation creation. Simpler, no queue infrastructure, and gives the farmer an immediate result — which the demo needs.

**TECHNICAL RECOMMENDATION:** keep `InferenceService` behind an interface so a queue can be introduced without touching callers, and put a semaphore (`AI_MAX_CONCURRENT_INFERENCE`) in front of it so a burst of uploads cannot exhaust CPU and stall the API. If measured inference time exceeds the interactive budget (§31), move to the worker and have the client poll `/observations/{id}/status` — an endpoint that already exists precisely so this change requires no client rewrite.

### 15.7 Unsupported and poor-quality images

| Case | Detection | Behaviour |
|---|---|---|
| Not an image | Magic-byte sniffing | `422 IMAGE_INVALID`, nothing stored |
| Corrupt/truncated | Decode failure | `422 IMAGE_INVALID` |
| Too blurry / too dark | Quality heuristics (§14.2) | Stored, flagged, farmer asked to retake; inference still runs but the result is marked low-quality |
| Not a plant | **No reliable detector exists in the MVP** | Handled by the confidence gate and expert review, not by a claimed "not a plant" classifier. **A rejection class must not be invented.** |
| Class outside the supported list | The model can only emit its own class list | The response includes the supported class list; the UI states the supported scope explicitly |

**TECHNICAL RECOMMENDATION:** if training data permits, add an explicit `UNKNOWN`/`NOT_A_LEAF` class to a future model version. This is a training decision, not something the serving code can fake.

### 15.8 Inference error handling

| Failure | Behaviour |
|---|---|
| No model loaded | `503 AI_MODEL_UNAVAILABLE`; observation is still created and routed to `PENDING_REVIEW` |
| Exception during inference | No `ai_predictions` row; observation status `AI_FAILED`; `processing_errors` records the exception class (never the stack trace); review queued; metric `ai_inference_failures_total` incremented |
| Timeout (`AI_INFERENCE_TIMEOUT_SEC`) | Same as an exception, with reason `TIMEOUT` |
| Out of memory | Same, plus an operational alert |

**In no failure path does the system produce a fabricated prediction.**

### 15.9 Model metadata surfaced to users

Every prediction shown in the UI carries the model version, and `GET /ai/models/active` returns the class list, thresholds, training-dataset reference and known limitations. Where `evaluation_metrics` is null the UI shows "Not yet evaluated" — **it never shows a placeholder accuracy figure.**

---

## 16. AI DATASET ARCHITECTURE

### 16.1 Dataset separation

Four strictly separated sets, per PRD §7.3 and §26:

| Set | Purpose | Origin | May be mixed with others? |
|---|---|---|---|
| **Training** | Fit model parameters | Public plant-disease datasets (**REQUIRES DECISION** — which, with licence) | No |
| **Validation** | Tune hyperparameters and thresholds | Held out from the same distribution as training | No |
| **Test** | Final held-out evaluation | Held out, never seen during development | **Never** |
| **Field validation** | Measure real-world performance | Real images from platform observations | Never used for training in the same version that is evaluated against it |
| **Expert confirmed** | The growth pool for future training | Observations with `verification_status ∈ {CONFIRMED, CORRECTED}` | Only after the quality gate in §16.4 |

A controlled public dataset is **not** field data, and its accuracy is **not** field accuracy (PRD §7.3, §26 "Over-reliance on controlled datasets"). Every dataset manifest records this distinction explicitly.

### 16.2 On-disk layout

```
datasets/
├── raw/<source_code>/<version>/          # untouched downloads; never edited in place
├── processed/
│   └── <dataset_id>/
│       ├── manifest.json
│       ├── train/<class_code>/*.jpg
│       ├── val/<class_code>/*.jpg
│       └── test/<class_code>/*.jpg
├── field_validation/<export_id>/
│   ├── manifest.json
│   └── images/*.jpg
└── exports/                              # generated by scripts/export_field_dataset.py
```

Datasets are **not** stored in the application database or in Git. Large files are tracked by manifest and checksum. **TECHNICAL RECOMMENDATION:** DVC or a plain checksummed manifest; a hackathon team can start with the manifest alone.

### 16.3 Manifest schema (required for every dataset)

```json
{
  "dataset_id": "plantvillage-subset-2026-09-01",
  "created_at": "2026-09-01T00:00:00Z",
  "created_by": "user or script",
  "source_type": "PUBLIC_DATA | FIELD_OBSERVATION | EXPERT_VALIDATION",
  "data_source_code": "must resolve to data_sources.code",
  "licence": "as stated by the source",
  "class_list": ["..."],
  "class_mapping": { "raw_label": "disease_pest_catalog.code" },
  "counts": { "train": 0, "val": 0, "test": 0 },
  "split_method": "stratified | by_field | by_farmer | temporal",
  "split_seed": 42,
  "image_checksums": "path to a checksum file",
  "is_field_data": false,
  "known_limitations": "free text — required, not optional",
  "provenance_notes": "how these images were obtained"
}
```

The `known_limitations` field is mandatory. A dataset with no stated limitations may not be registered — this is the mechanism that stops "controlled dataset accuracy" from silently becoming "field accuracy".

### 16.4 The confirmed-observation feedback loop (PRD §3.9, §27.10)

```
observation (CONFIRMED or CORRECTED by an expert)
  → quality gate
  → candidate pool
  → periodic export (scripts/export_field_dataset.py)
  → manifest + images
  → offline training/evaluation (outside the application)
  → new model version registered in ai_model_registry
  → activated by an admin
```

**Quality gate — an observation enters the candidate pool only if all hold:**
1. `verification_status ∈ {CONFIRMED, CORRECTED}`.
2. `source_type = FIELD_OBSERVATION` (never `DEMO_SIMULATION`).
3. At least one image passing the quality heuristics (not flagged blurry or dark).
4. `final_agent_id` is set and maps to a known catalogue code.
5. The expert who decided it is not the same user who reported it (no self-confirmation).
6. Farmer consent for research use is recorded (§30).
7. Not already included in a previous export (tracked by image checksum).

**Splitting rule:** field-validation splits are grouped **by field, and preferably by farmer** — never a random image-level split. Images from one field in both train and test would leak and inflate the result. This is a stated methodological requirement, not an optimisation.

### 16.5 What this architecture deliberately does not do

- It does not automatically retrain. Retraining is an explicit human-run offline step.
- It does not promote a new model automatically. Activation is an audited admin action.
- It does not claim that accumulated confirmations improve accuracy. It only makes the improvement **possible and traceable**.

---

## 17. WEATHER INTEGRATION

### 17.1 Provider abstraction

```python
@dataclass(frozen=True)
class WeatherReading:
    observed_at: datetime
    temperature_c: float | None
    humidity_pct: float | None
    rainfall_mm: float | None
    wind_speed_ms: float | None
    wind_direction_deg: float | None
    pressure_hpa: float | None
    raw: dict

class WeatherProvider(ABC):
    name: str
    supports_historical: bool          # declared, never assumed

    @abstractmethod
    async def get_current(self, lat: float, lon: float) -> WeatherReading: ...
    @abstractmethod
    async def get_forecast(self, lat: float, lon: float, days: int) -> list[WeatherReading]: ...
    @abstractmethod
    async def get_historical(self, lat, lon, start, end) -> list[WeatherReading]: ...
        # raises NotSupportedError when supports_historical is False
```

`supports_historical` is a declared capability. `GET /weather/historical` returns `501` when the configured provider does not support it, rather than fabricating values.

> **REQUIRES DECISION — weather provider.** The PRD requires weather and requires the provider to be replaceable, but names none, and this TRD will not invent one. Before Phase 3 the team must choose a provider and verify, from its own documentation: available variables, forecast horizon and resolution, historical support, rate limits, licence/terms for this use, and cost. Record the answer in `data_sources` and in an ADR. Until then, implement `WeatherProvider` plus a `FixtureWeatherProvider` that serves **clearly labelled** fixture data with `source_type = DEMO_SIMULATION`, so Phases 3–9 are unblocked without anyone mistaking fixtures for live weather.

### 17.2 Request flow

```
WeatherService.get_context(lat, lon, at)
  1. grid_cell = round(lat, 2), round(lon, 2)
  2. cache lookup: weather_observations where grid_cell matches and
     observed_at within WEATHER_CACHE_TTL_MIN
       hit  → return {data, cache_hit: true, is_stale: false}
  3. miss → provider.get_current()  (timeout WEATHER_TIMEOUT_SEC, retries with backoff)
       success → persist → return {cache_hit: false, is_stale: false}
  4. provider failure → most recent row for the cell within WEATHER_STALE_MAX_HOURS
       found → return {is_stale: true, fetched_at: ...}
  5. nothing → return None  →  caller records WEATHER_UNAVAILABLE
```

The same pattern applies to forecasts, keyed additionally by `forecast_for`.

### 17.3 Caching parameters

| Parameter | Default | Env |
|---|---|---|
| Grid rounding | 2 decimal places (~1.1 km) | `WEATHER_GRID_PRECISION` |
| Current-weather TTL | 60 min | `WEATHER_CACHE_TTL_MIN` |
| Forecast TTL | 180 min | `WEATHER_FORECAST_TTL_MIN` |
| Maximum acceptable staleness | 24 h | `WEATHER_STALE_MAX_HOURS` |
| Request timeout | 8 s | `WEATHER_TIMEOUT_SEC` |
| Retries | 2, exponential backoff with jitter | `WEATHER_MAX_RETRIES` |

All **TECHNICAL RECOMMENDATION**s; tune once the provider's rate limits are known.

### 17.4 Scheduled refresh

A worker job refreshes weather for every **active field cell** (a cell containing at least one field with a recent observation) on `WEATHER_REFRESH_CRON`. This keeps the cache warm so the interactive path is usually a cache hit, and it bounds provider calls to the number of distinct cells rather than the number of observations.

### 17.5 Rate limits and API keys

- The key comes only from `WEATHER_API_KEY`; it is never committed, never logged, never returned in an error body, and is redacted by the logging filter.
- A token-bucket limiter caps outbound calls at `WEATHER_MAX_CALLS_PER_MIN`; exhaustion serves cached/stale data rather than erroring.
- Provider `429`/`5xx` responses are retried with backoff and then fall through to the stale path.
- A circuit breaker opens after `WEATHER_BREAKER_FAILURES` consecutive failures and stays open for `WEATHER_BREAKER_RESET_SEC`, so a dead provider does not add latency to every observation.

### 17.6 Failure semantics summary

| Situation | API result | Risk engine | UI |
|---|---|---|---|
| Fresh cache | 200, `cache_hit: true` | full weather factors | normal |
| Live fetch | 200, `cache_hit: false` | full weather factors | normal |
| Stale cache | 200 + warning `WEATHER_STALE` | factors used, `weather_is_stale = true` | "Weather data from {time} — may be outdated" |
| Nothing available | 503 `WEATHER_UNAVAILABLE` on the weather endpoint; observation still succeeds with warning `WEATHER_UNAVAILABLE` | weather factors listed in `missing_factors`, uncertainty raised | "Risk calculated without weather data" |

Weather is never invented, and its absence is never hidden.

---

## 18. RISK ENGINE

### 18.1 Interface

```python
class RiskEngine(ABC):
    version: str
    @abstractmethod
    def evaluate(self, ctx: RiskContext) -> RiskResult: ...
```

MVP implementation: `RuleBasedRiskEngine`, driven entirely by `risk/rulesets/ruleset_v1.yaml`. Future implementation: `MLRiskEngine` (scikit-learn / XGBoost), swapped by configuration with no caller changes (PRD §6.5).

### 18.2 Inputs — `RiskContext`

```python
@dataclass(frozen=True)
class RiskContext:
    observation: ObservationSummary            # id, geom, observed_at, severity
    ai_signal: AiSignal | None                 # class, confidence, low-confidence flag
    crop: CropRef | None
    variety: VarietyRef | None
    growth_stage: GrowthStageRef | None        # sequence + susceptibility
    weather_current: WeatherReading | None
    weather_forecast: list[WeatherReading]     # may be empty
    weather_is_stale: bool
    nearby_history: NearbyHistory              # counts by status/agent within radius+window
    field_context: FieldContext | None         # soil, irrigation, area
    trap_signal: TrapSignal | None             # catch-per-day, trend
    sensor_signals: list[SensorSignal]
```

`ContextEngine.build()` assembles this from the repositories, populating `missing_factors` for anything unavailable. **No field is silently defaulted** — a missing input is recorded as missing.

### 18.3 Rule configuration

```yaml
ruleset_version: "v1.0.0"
method: "RULE_BASED_V1"
disclaimer_key: "risk.prototype_disclaimer"

levels:                # score → level bands (configurable)
  LOW:    { min: 0,  max: 33 }
  MEDIUM: { min: 34, max: 66 }
  HIGH:   { min: 67, max: 100 }

factors:
  ai_signal:
    weight: 0.30
    rules:
      - when: { has_prediction: true, is_low_confidence: false }
        score_expr: "confidence * 100"
      - when: { has_prediction: true, is_low_confidence: true }
        score_expr: "confidence * 60"      # an uncertain signal contributes less
      - when: { has_prediction: false }
        score: null                        # contributes nothing; listed as missing

  weather:
    weight: 0.25
    rules:
      - when: { humidity_pct: { gte: 80 }, temperature_c: { between: [20, 30] } }
        score: 80
        explanation_key: "risk.factor.humid_warm"
      - when: { rainfall_mm_7d: { gte: 50 } }
        score: 70
        explanation_key: "risk.factor.recent_rain"
      # ... further bands

  growth_stage:      { weight: 0.15 }
  nearby_confirmed:  { weight: 0.20 }
  trap_signal:       { weight: 0.10 }

missing_factor_policy: "renormalise"   # reweight present factors; raise uncertainty
uncertainty:
  base: 0.05
  per_missing_factor: 0.15
  max: 0.9
```

> **REQUIRES DECISION — factor weights and thresholds.** The weights and bands above are **structural placeholders showing the mechanism, not agronomic recommendations.** Real values must come from an agronomist or from published, cited disease-favourability guidance for the chosen crops, and the source must be recorded in `data_sources` with `category = ADVISORY_CONTENT`. **This TRD does not invent epidemiological thresholds.**

### 18.4 Scoring algorithm

```
present = [f for f in factors if f.score is not None]
missing = [f for f in factors if f.score is None]

if missing_factor_policy == "renormalise":
    total_w = sum(f.weight for f in present)
    score = sum(f.score * f.weight for f in present) / total_w      # 0..100
else:
    score = sum(f.score * f.weight for f in factors)                 # missing count as 0

level       = band(score)
uncertainty = min(base + per_missing * len(missing), max)
```

The engine is **deterministic** — the same context always yields the same score, which is what makes it testable and explainable.

### 18.5 Outputs — `RiskResult`

```json
{
  "risk_score": 62.4,
  "risk_level": "MEDIUM",
  "forecast_period": { "start": "2026-09-05T00:00:00Z", "end": "2026-09-12T00:00:00Z" },
  "contributing_factors": [
    { "factor": "WEATHER_HUMIDITY", "value": 86, "weight": 0.25, "contribution": 20.0,
      "explanation_key": "risk.factor.humid_warm" },
    { "factor": "NEARBY_CONFIRMED", "value": 3, "weight": 0.20, "contribution": 14.0,
      "explanation_key": "risk.factor.nearby_confirmed" }
  ],
  "missing_factors": [ { "factor": "TRAP_SIGNAL", "reason": "NO_TRAP_DATA" } ],
  "explanation_key": "risk.summary.medium",
  "explanation_params": { "top_factors": ["humidity", "nearby_confirmed"] },
  "uncertainty": 0.2,
  "method": "RULE_BASED_V1",
  "ruleset_version": "v1.0.0",
  "disclaimer_key": "risk.prototype_disclaimer",
  "weather_is_stale": false
}
```

`contribution` values sum to `risk_score`, so a user can read exactly why a score is what it is. The explanation sentence is assembled client-side from `explanation_key` + `explanation_params`, so it is localised (PRD §14) rather than an English string from the server.

### 18.6 Forecast period

MVP evaluates a 7-day forward window (`RISK_FORECAST_DAYS`), using the forecast weather when available and current weather otherwise. Longer horizons are deferred (PRD §22 FUTURE).

### 18.7 Recalculation triggers

| Trigger | Scope |
|---|---|
| New observation | That observation, plus its field |
| Expert decision changes the diagnosis | That observation and its field (the agent changed, so the risk changed) |
| Scheduled daily job | Every field with an observation in the last `RISK_ACTIVE_WINDOW_DAYS` |
| A nearby case is confirmed | Fields within `RISK_NEARBY_RADIUS_M` of the confirmed case |
| Manual `POST /risk/recalculate` | As requested |

Recalculation always inserts a **new** `risk_assessments` row; history is never overwritten, so risk trend charts are real history rather than a reconstruction.

### 18.8 Honesty constraints

- Every response and every UI surface carries `disclaimer_key` → "Prototype decision-support logic; not scientifically validated."
- `method` and `ruleset_version` are stored on every row, so any past score can be reproduced.
- The engine never claims a prediction of an outbreak; it produces a **risk signal**.
- `GET /risk/ruleset` exposes the full active configuration for inspection.

---

## 19. GIS & HOTSPOT ENGINE

### 19.1 The three signal classes

The PRD requires confirmed and predicted to be distinguishable. This TRD uses three, because a trap/sensor signal is neither:

| Class | Definition | Source |
|---|---|---|
| **CONFIRMED** | An expert (or lab) has confirmed or corrected the diagnosis | `verification_status ∈ {CONFIRMED, CORRECTED}` |
| **PREDICTED** | AI produced a class; no expert has verified it | `verification_status ∈ {PREDICTED, PENDING_REVIEW}` |
| **SIGNAL** | Indirect evidence without an image diagnosis | Trap counts, sensor thresholds, high risk scores without a confirmed case |

These are never merged into one count, one colour, or one polygon.

### 19.2 Spatial aggregation and clustering

```
Input:  observations in [window_start, window_end], optionally filtered by agent/crop/district
Step 1: partition by hotspot class (CONFIRMED / PREDICTED / SIGNAL) — clustered separately
Step 2: transform to the metric CRS (§9.1)
Step 3: ST_ClusterDBSCAN(eps = HOTSPOT_EPS_M, minpoints = HOTSPOT_MIN_POINTS)
Step 4: per cluster —
          geom      = ST_ConcaveHull(ST_Collect(geom), 0.8)
                      → ST_ConvexHull fallback
                      → ST_Buffer(centroid, HOTSPOT_MIN_RADIUS_M) for < 3 points
          counts    = total, confirmed, predicted
          severity  = weighted mean of available severities
          intensity = §19.4
Step 5: transform back to 4326; write hotspots rows; mark prior snapshot is_current = false
```

**REQUIRES DECISION — clustering parameters.** `HOTSPOT_EPS_M` and `HOTSPOT_MIN_POINTS` determine what counts as a hotspot and therefore what officials act on. They must be chosen against real observation density, not guessed. Defaults for the demo are configurable and clearly labelled as demo settings.

### 19.3 Time windows

| Window | Default | Use |
|---|---|---|
| Active | 14 days | The default map view |
| Recent | 30 days | Trend comparison |
| Season | Configurable | Seasonal analysis |
| Historical | Arbitrary range | Spread animation over snapshots |

Every hotspot row records its own `window_start`/`window_end`, so two snapshots are never compared across mismatched windows.

### 19.4 Intensity scoring

```
intensity = w_count      * normalise(observation_count)
          + w_confirmed  * (confirmed_count / max(observation_count, 1))
          + w_severity   * normalise(avg_severity)
          + w_recency    * recency_weight(window_end - latest_observed_at)
```

Weights come from configuration (`HOTSPOT_WEIGHTS`), are stored in `algorithm_params` on every row, and default to giving confirmed observations materially more weight than predicted ones — a cluster of unverified predictions must not outrank a cluster of confirmed cases. **TECHNICAL RECOMMENDATION** on the exact weights; the *principle* (confirmed outweighs predicted) is a PRD requirement.

### 19.5 Risk zones vs hotspots vs priority zones

| Layer | Built from | Answers |
|---|---|---|
| **Hotspots** | Observation clusters | "Where are cases concentrated?" |
| **Risk zones** | Interpolated/aggregated `risk_assessments` over fields, grouped by admin region or grid cell | "Where is risk elevated, whether or not cases are reported?" |
| **Priority zones** | Hotspots + risk zones + pending-review backlog + surveillance gaps | "Where should limited staff go first?" |

Priority scoring:
```
priority = a*confirmed_density + b*risk_level_mean + c*pending_review_backlog
         + d*(1 - surveillance_coverage)
```
`drivers` on each `priority_zones` row records each term's contribution, so an official can see *why* a zone ranks where it does rather than trusting a bare number.

### 19.6 Layer generation and serving

- Hotspots, risk zones and priority zones are **precomputed** by the worker (`recompute_hotspots` on `HOTSPOT_CRON`, plus event-driven invalidation on a new confirmed case) and served from tables — never computed inside a request.
- Observation points are **queried live**, bounded by bbox/radius and time window.
- All layers serve GeoJSON; every feature carries provenance properties (§10.4).
- **TECHNICAL RECOMMENDATION:** if point volume outgrows GeoJSON, add MVT vector tiles via `ST_AsMVT` behind the same endpoint contract. Not needed at MVP scale.
- Responses set `Cache-Control` per layer: precomputed layers may be cached for minutes; live observation queries are not cached.

### 19.7 Frontend layer contract

```
GET /gis/layers/confirmed_cases?bbox=&from=&to=&agent_id=&include_demo=false
→ FeatureCollection {
    features: [ { type: "Feature",
                  geometry: {...},
                  properties: { id, source_type, verification_status, agent_code,
                                agent_name, confidence, observed_at, severity,
                                match_basis, model_version } } ],
    meta: { layer, count, truncated, include_demo, computed_at }
  }
```

A shared style function maps `verification_status` + `source_type` to symbology, so CONFIRMED, PREDICTED, SIGNAL and DEMO can never be styled identically by accident on any screen.

### 19.8 Honesty constraints

- Hotspot detection is decision support, not validated outbreak detection (PRD §10). Every hotspot response carries a disclaimer key, and the UI renders it.
- A hotspot built from any demo observation is labelled as such.
- When data is insufficient, the API returns an empty collection with `INSUFFICIENT_DATA` — **it never lowers `min_points` to manufacture a hotspot for a demo.**

---

## 20. EXPERT VALIDATION

### 20.1 State machine

```
                    ┌──────────────────────────────┐
   AI prediction ───┤ confidence ≥ high threshold  ├──→ PREDICTED
                    └──────────────────────────────┘        │
                                                            │ farmer or worker
                    ┌──────────────────────────────┐        │ requests review
   AI prediction ───┤ confidence < high threshold  ├──→ PENDING_REVIEW ←┘
   AI failure    ───┤ or inference failed          │        │
                    └──────────────────────────────┘        │ expert claims
                                                            ▼
                                                      (review CLAIMED)
                                                            │
                  ┌──────────────┬────────────────┬─────────┴──────┐
                  ▼              ▼                ▼                ▼
              CONFIRMED      CORRECTED        REJECTED        LAB_REFERRED
                  │              │                │                │
                  │              │                │                ▼
                  │              │                │        (lab result recorded)
                  │              │                │                │
                  └──────────────┴────────────────┴────────────────┘
                                     │
                              final_agent_id set
                              (except REJECTED)
                              advisory regenerated
                              hotspots invalidated
```

### 20.2 Review states vs verification statuses

Two distinct concepts, deliberately kept apart:
- `expert_reviews.state` — the **workflow** state (QUEUED, CLAIMED, DECIDED, REFERRED, EXPIRED).
- `observations.verification_status` — the **truth** state (PREDICTED, PENDING_REVIEW, CONFIRMED, CORRECTED, REJECTED, LAB_REFERRED).

Merging them would make "an expert is currently looking at this" indistinguishable from "this is what we believe is true".

### 20.3 Queue mechanics

**Priority** (computed at enqueue, refreshed by the worker):
```
priority = f(risk_level, confidence_gap, observation_age, nearby_confirmed_count)
```
High risk + low confidence + old + near confirmed cases ⇒ highest priority. Priority is recomputed daily so an ageing case rises rather than starving.

**Claiming:** `POST /reviews/{id}/claim` performs an optimistic update `WHERE state='QUEUED' AND version=:version`; zero rows updated ⇒ `409 REVIEW_ALREADY_CLAIMED`. Claims carry `claim_expires_at` (`REVIEW_CLAIM_TTL_MIN`, default 30 min); a worker job expires stale claims back to `QUEUED` and audits it, so no case is lost to an expert who closed their laptop.

**Filtering:** by district (matching the expert's scope), crop, agent, priority, age.

### 20.4 Expert actions

| Action | Effect on the observation | Advisory | Notes |
|---|---|---|---|
| **CONFIRM** | `verification_status = CONFIRMED`; `final_agent_id = predicted_agent_id` | Regenerated with confirmed status | Requires the prediction to have a mapped agent |
| **CORRECT** | `verification_status = CORRECTED`; `final_agent_id = corrected_agent_id` | Regenerated for the corrected agent | The original prediction is retained and shown alongside |
| **REJECT** | `verification_status = REJECTED`; `final_agent_id` stays null | Superseded, not regenerated | Removed from default map layers; retained for audit and for model-error analysis |
| **REFER TO LAB** | `verification_status = LAB_REFERRED` | A referral advisory is issued | Creates a lab referral with a reference code |

Every action writes an `audit_logs` row containing before/after state and the expert's identity, satisfying PRD §21.

### 20.5 Lab referral

`POST /reviews/{id}/refer` body: `{lab_reference_code?, reason, sample_notes}`. The system generates `lab_reference_code` when the expert does not supply one. A `LAB_EXPERT` sees referred cases at `/expert/referrals` with the full case context (images, prediction, crop context, location, weather, risk, nearby cases) and records the outcome via `POST /reviews/{id}/lab-result`, which sets `final_agent_id` from the lab result and moves the observation to `CONFIRMED` or `CORRECTED` accordingly.

> **REQUIRES DECISION — laboratory integration.** Whether referrals are handled entirely in-app or exchanged with an external laboratory system is not specified in the PRD. The MVP assumes **in-app only**; no external lab API is invented.

### 20.6 Audit trail

Every review action records: actor, role, timestamp, prior status, new status, prior agent, new agent, notes, and the model version under review. `GET /reviews/history?observation_id=` returns the full chain, and the farmer's observation detail screen shows a plain-language version ("Reviewed by {expert} on {date}: diagnosis corrected from X to Y").

### 20.7 Expert-unavailable behaviour

If nothing is claimed within `REVIEW_SLA_HOURS`, the observation stays `PENDING_REVIEW` and the farmer's UI continues to show "Awaiting expert review" with a cautious advisory. **The system never auto-promotes a prediction to a confirmation because no expert was available.** The queue-age metric is surfaced on the expert and official dashboards so the backlog is visible rather than silent.

---

## 21. ADVISORY ENGINE

### 21.1 Selection algorithm

```
inputs: agent (final_agent_id or predicted_agent_id), crop, growth stage,
        risk_level, verification_status, confidence, language

1. Candidate templates where:
     (agent_id = agent OR agent_id IS NULL)
     AND (crop_id = crop OR crop_id IS NULL)
     AND (min_risk_level IS NULL OR risk_level >= min_risk_level)
     AND (applies_to_verification IS NULL OR verification_status = ANY(applies_to_verification))
     AND is_active
2. Rank by specificity: agent+crop > agent > crop > generic
3. Take the most specific; if none → ADVISORY_GENERIC_FALLBACK
4. Render section keys in the requested language (fallback en)
5. Persist with frozen confidence / verification_status / risk_level / ruleset_version
```

### 21.2 Confidence-aware framing

The same agent produces a **differently framed** advisory depending on verification status. This is the mechanism that implements "The system must not present an uncertain AI prediction as a confirmed diagnosis" (PRD §6.8).

| Verification status | Framing | Action guidance |
|---|---|---|
| CONFIRMED / CORRECTED | "Expert-confirmed: {agent}" | Full IPM guidance for that agent |
| PREDICTED (high confidence) | "Possible {agent} — AI assessment, not confirmed" | Preventive and monitoring actions; low-regret measures only; confirmation encouraged |
| PENDING_REVIEW (low confidence) | "Uncertain — awaiting expert review" | General crop-hygiene guidance and a clear prompt to seek expert help; **no agent-specific treatment** |
| REJECTED | "Earlier assessment was not supported" | Prompt to resubmit with a better image |
| LAB_REFERRED | "Sample referred for laboratory diagnosis" | Containment and monitoring guidance while awaiting the result |

### 21.3 Advisory content structure

```json
{
  "observation_summary": { "title_key": "...", "params": {} },
  "diagnosis": { "agent_name": "...", "verification_status": "PREDICTED",
                 "confidence": 0.78, "confidence_label_key": "advisory.confidence.moderate",
                 "disclaimer_key": "advisory.not_confirmed" },
  "risk_context": { "level": "MEDIUM", "explanation_key": "...", "params": {} },
  "recommended_actions": {
    "cultural":   [ { "key": "...", "params": {} } ],
    "mechanical": [ ],
    "biological": [ ],
    "monitoring": [ ]
  },
  "prevention":       [ { "key": "..." } ],
  "safe_input_use":   { "key": "advisory.safe_input_general", "params": {} },
  "when_to_seek_help":[ { "key": "..." } ],
  "followup":         { "recommended_days": 7, "what_to_look_for_key": "..." },
  "provenance": { "advisory_ruleset_version": "v1.0.0", "template_id": "uuid",
                  "source_reference": "as recorded in data_sources",
                  "generated_at": "...", "language": "mr", "language_fallback": false }
}
```

Content is stored as **keys plus parameters**, never as rendered sentences, so a single advisory record renders in any supported language and translations can be corrected without regenerating advisories.

### 21.4 IPM ordering (PRD §6.8)

Sections are always presented in this order, and the order is enforced by the schema rather than by template authors:
1. Cultural practices → 2. Mechanical/physical controls → 3. Biological controls → 4. Monitoring → 5. Prevention → 6. Safe input use (general guidance only) → 7. When to seek expert/lab help.

### 21.5 What the advisory engine will not do

- It will not name a pesticide, dose, or spray schedule. `safe_input_use` carries only general safety guidance (read the label, observe pre-harvest intervals, use protective equipment, consult a licensed advisor) — never a prescription. This is a direct PRD constraint (§4, §13, §26).
- It will not issue agent-specific treatment guidance for an unconfirmed low-confidence prediction.
- It will not generate content that is not traceable to a registered `advisory_templates.source_reference`.

### 21.6 Regeneration and history

An advisory is regenerated when the expert changes the diagnosis, the lab result arrives, or the risk level crosses a band. The prior advisory is marked `is_superseded = true` and retained, so the farmer (and an auditor) can see exactly what was advised at each point. `GET /advisories?observation_id=&include_superseded=true` returns the chain.

### 21.7 Fallback behaviour

| Situation | Result |
|---|---|
| No matching template | `ADVISORY_GENERIC_FALLBACK` — crop hygiene, monitoring, and consult an expert |
| Requested language missing for a key | Key served in `en`, response sets `language_fallback: true`, the UI shows a small note |
| No agent identified at all | Generic monitoring advisory plus a prompt to resubmit or seek help |

An advisory is never empty and never fabricated.

---

## 22. MULTILINGUAL ARCHITECTURE

### 22.1 Division of responsibility

| Content type | Owner | Mechanism |
|---|---|---|
| UI chrome (labels, buttons, nav, validation text) | Frontend | `react-i18next` JSON bundles |
| Reference data names (crops, varieties, stages, agents, symptoms) | Backend database | `name_en` / `name_hi` / `name_mr` columns |
| Advisory content | Backend | i18n keys in `advisory_templates.sections` + `locales/{lang}.json` |
| Risk explanations | Backend | `explanation_key` + `explanation_params`, rendered client-side |
| API error messages | Both | Server sends `message_key`; the client renders the localised string |
| Free text (farmer notes, expert notes) | Neither | Stored as entered; **never machine-translated** — an expert's clinical note must not be silently altered |

### 22.2 Language negotiation

```
1. Explicit ?lang= query parameter          (highest precedence)
2. Accept-Language header
3. users.preferred_language                  (persisted preference)
4. DEFAULT_LANGUAGE = "en"                   (final fallback)
```

The negotiated language is returned in every localised response so the client can detect a fallback.

### 22.3 Frontend structure

```
src/i18n/locales/
├── en/  common.json  auth.json  farmer.json  expert.json  official.json
│       admin.json    advisory.json  risk.json  errors.json  map.json
├── hi/  (same files)
└── mr/  (same files)
```

Key convention: `namespace.section.element` — e.g. `farmer.check.step_image_title`, `errors.observation_not_found`, `risk.factor.humid_warm`, `provenance.demo_simulation`.

Rules:
- No user-facing string literal in a component (PRD §14). Enforced by an ESLint rule (`i18next/no-literal-string`) in CI. **TECHNICAL RECOMMENDATION.**
- A missing key in development throws loudly; in production it falls back to `en` and logs.
- Number, date and unit formatting via `Intl`, using the active locale.
- A CI check fails the build when `hi` or `mr` is missing a key present in `en`, so a language cannot silently rot.

### 22.4 Backend locale files

`app/locales/{en,hi,mr}.json` hold advisory, risk-explanation and notification strings. They are versioned with the code and reloaded at startup. The backend renders these only for channels that cannot render keys themselves (notifications, exports); for API responses the backend prefers to send keys and let the client render.

### 22.5 Adding a language

1. Add the code to the `language_code` enum (a migration).
2. Add `name_<code>` columns to reference tables, or move to a normalised `translations` table if the language count grows beyond ~5. **TECHNICAL RECOMMENDATION:** column-per-language is correct for three languages; a `translations(entity_type, entity_id, field, lang, value)` table becomes worthwhile beyond that.
3. Add the frontend locale directory and the backend locale file.
4. CI's missing-key check will list exactly what remains untranslated.

> **REQUIRES DECISION — translation authorship.** Accurate Hindi and Marathi agronomic terminology requires a competent human translator; machine translation of disease names and safety guidance is a real-world risk. Nominate who provides and reviews the `hi` and `mr` content.

---

## 23. FOLLOW-UP SYSTEM

### 23.1 Scheduling

| Trigger | Default interval | Env |
|---|---|---|
| HIGH risk observation | 3 days | `FOLLOWUP_DAYS_HIGH` |
| MEDIUM risk | 7 days | `FOLLOWUP_DAYS_MEDIUM` |
| LOW risk | 14 days | `FOLLOWUP_DAYS_LOW` |
| Expert instruction | As specified by the expert | — |
| Farmer-initiated | Any date | — |

**TECHNICAL RECOMMENDATION** on intervals; they should be tuned per agent once agronomic guidance is available (§21 source decision).

A worker job runs daily: `SCHEDULED` → `DUE` when `scheduled_for <= today`; `DUE` → `MISSED` when `scheduled_for + due_window_days < today`. Both transitions emit a notification (`followup_due`, `followup_missed`) subject to the deduplication rule in §5.18.

### 23.2 Submission flow

```
Farmer opens /app/followups/{id}/submit
  → prefilled with the parent's field, crop, variety, growth stage (stage may be advanced)
  → captures a new image, ideally from a similar angle (the parent thumbnail is shown as a guide)
  → selects the perceived outcome: BETTER / SAME / WORSE / UNCERTAIN
  → POST /followups/{id}/submit
      1. creates a NEW observation with parent_observation_id set
      2. runs the full pipeline (AI → weather → risk → advisory)
      3. updates the followup row: followup_observation_id, status=SUBMITTED,
         outcome, outcome_source=FARMER_REPORTED
      4. computes comparison_metadata (§23.4)
      5. schedules the next follow-up when risk remains MEDIUM or HIGH
```

The follow-up is a **first-class observation**, so it appears on the map, feeds hotspots, and is itself reviewable — a follow-up showing a worsening condition is exactly the case an expert should see.

### 23.3 Follow-up chains

`parent_observation_id` forms a chain. `GET /observations/{id}?include_chain=true` returns the full lineage — original, every follow-up, each with its prediction, risk and outcome — so an expert can see the trajectory in one view rather than reconstructing it.

Depth is capped at `FOLLOWUP_MAX_CHAIN` (default 10) to prevent unbounded recursion; beyond that a new independent observation is created.

### 23.4 Comparison metadata

```json
{
  "days_since_parent": 7,
  "parent": { "observation_id": "uuid", "predicted_class": "...", "confidence": 0.81,
              "risk_score": 62.4, "reported_severity": 3,
              "verification_status": "CONFIRMED", "image_id": "uuid" },
  "current": { "observation_id": "uuid", "predicted_class": "...", "confidence": 0.44,
               "risk_score": 38.1, "reported_severity": 2,
               "verification_status": "PREDICTED", "image_id": "uuid" },
  "deltas": { "risk_score": -24.3, "reported_severity": -1, "confidence": -0.37 },
  "same_agent_predicted": true,
  "interventions_between": [ { "type": "CULTURAL", "applied_at": "..." } ],
  "outcome": "BETTER",
  "outcome_source": "FARMER_REPORTED",
  "comparison_caveat_key": "followup.comparison_caveat"
}
```

**Important honesty constraint:** the deltas are **descriptive**, not causal. `comparison_caveat_key` renders a note that the change may be due to the intervention, natural progression, weather, or differences in how the photograph was taken. The system does not claim treatment efficacy, and it does not compute image-similarity scores it cannot justify.

### 23.5 Outcome semantics

| Outcome | Meaning | Who can set it |
|---|---|---|
| BETTER | Condition appears improved | Farmer, expert |
| SAME | No visible change | Farmer, expert |
| WORSE | Condition appears worse | Farmer, expert |
| UNCERTAIN | Cannot tell | Farmer, expert, or the system when data is insufficient |

`outcome_source` distinguishes `FARMER_REPORTED` from `EXPERT_ASSESSED` from `AI_COMPARED`, because these carry very different weight. An expert assessment supersedes a farmer report on the same follow-up, and both are retained.

A `WORSE` outcome raises the review priority of the follow-up observation automatically.

---

## 24. PEST TRAP / SENSOR ARCHITECTURE

### 24.1 The generic observation envelope

Trap counts and sensor readings are **not** parallel systems. Both create a row in `observations` (with `observation_type = PEST_TRAP` or `SENSOR`) plus a row in their detail table. This single design decision means traps and sensors automatically inherit: geometry and map presence, provenance, district resolution, risk-engine input, hotspot participation, follow-up linkage, and role scoping — with no duplicated code.

```
                    observations  (geometry, time, provenance, field, crop)
                          │
      ┌───────────────────┼────────────────────┬─────────────────────┐
      ▼                   ▼                    ▼                     ▼
observation_images  pest_trap_observations  sensor_observations  (manual report:
  (type=IMAGE)        (type=PEST_TRAP)        (type=SENSOR)       no detail row)
```

### 24.2 Pest traps in the MVP

Manual entry only. `POST /traps/observations`:

```json
{ "field_id": "uuid", "latitude": 0, "longitude": 0,
  "trap_type": "PHEROMONE", "target_agent_id": "uuid|null",
  "catch_count": 12, "trap_installed_at": "...", "counted_at": "...",
  "exposure_hours": 24, "trap_identifier": "Trap-A", "notes": "..." }
```

Derived metric: `catch_per_day = catch_count / (exposure_hours / 24)`, computed on read so a change to the formula does not require a backfill.

`GET /traps/series` returns a per-trap time series that the frontend renders as a trend chart — a rising catch trend is the classic early-warning signal and feeds the risk engine's `trap_signal` factor (§18.2).

> **REQUIRES DECISION — economic threshold levels (ETLs).** Whether a given catch-per-day is actionable is crop-, pest- and region-specific agronomic knowledge. The schema supports thresholds (`agent_thresholds` can be added as a small reference table), but **no threshold values are invented here.** Until a cited source is supplied, the system charts the trend and does not declare an ETL breach.

### 24.3 Sensor readiness (no hardware required)

Three ingestion paths, all writing the same rows:

| Path | Status | Auth |
|---|---|---|
| `MANUAL_ENTRY` via `POST /sensors/observations` | MVP | Farmer/worker JWT |
| `FILE_IMPORT` via a CSV upload in the admin console | MVP | Admin |
| `API_PUSH` via `POST /sensors/ingest` | Schema-ready; endpoint stubbed and disabled by default | **REQUIRES DECISION — device authentication** |

`POST /sensors/ingest` batch shape (defined now so a future integration needs no schema change):
```json
{ "device_id": "string", "field_id": "uuid|null",
  "latitude": 0, "longitude": 0,
  "readings": [ { "sensor_type": "LEAF_WETNESS", "metric_key": "leaf_wetness_pct",
                  "metric_value": 82.5, "unit": "%", "measured_at": "..." } ] }
```

> **REQUIRES DECISION — device authentication for `API_PUSH`.** Options include a per-device API key, mutual TLS, or a signed payload. No IoT platform, broker or protocol is assumed, and none is invented here. The endpoint remains disabled (`SENSOR_INGEST_ENABLED=false`) until this is decided.

### 24.4 Deliberate non-goals

The MVP does not implement MQTT, device provisioning, firmware management, device shadows, or a time-series database. The PRD explicitly excludes building an IoT ecosystem (§4). The contribution here is that the **data model and API contract are already correct** for that future, so adopting it later is an addition rather than a rewrite.

---

## 25. DASHBOARD & ANALYTICS

### 25.1 The governing rule

**Predicted cases and confirmed cases are never combined into a single number.** Every count, every chart series, and every map layer in every dashboard is either explicitly confirmed, explicitly predicted, or explicitly both-shown-separately. A KPI that says "142 cases" without saying which kind is a defect, not a design choice — it is the single most likely way this system could mislead an official into acting on unverified data.

The same rule applies to demo data: `include_demo` defaults to `false` for officials, and any response that includes demo rows carries the `DEMO_DATA_INCLUDED` warning and a separate `demo_count`.

### 25.2 Shared query contract

All dashboard endpoints accept the same filter set, validated identically:

| Filter | Type | Default | Notes |
|---|---|---|---|
| `from` / `to` | ISO date | last 30 days | A window is always applied; unbounded time is rejected |
| `district_code` | string | the caller's scope | An official cannot widen beyond their scope |
| `crop_id` | UUID | all | |
| `agent_id` | UUID | all | Matched on `COALESCE(final_agent_id, predicted_agent_id)`, with `match_basis` reported |
| `verification_status` | enum[] | all | |
| `include_demo` | bool | `false` for OFFICIAL, `true` for own-data views | |
| `granularity` | enum | `day` | `day` / `week` / `month`, for time series |

Every dashboard response echoes `filters_applied` in `meta`, so a screenshot of a dashboard is self-describing — a judge can see exactly what was and was not counted.

### 25.3 Farmer dashboard (`GET /dashboards/farmer`)

| Widget | Source | Query shape |
|---|---|---|
| My fields | `fields` | count + list for the farmer |
| Active observations | `observations` | count where status not terminal, or awaiting review |
| Latest crop-health status per field | `observations` + `risk_assessments` | latest row per field (`DISTINCT ON (field_id) … ORDER BY observed_at DESC`) |
| Current risk per field | `risk_assessments` | latest per field, with level and top factors |
| Current weather | `weather_observations` | cache lookup for the field's grid cell, with staleness |
| Pending follow-ups | `followups` | where status in (SCHEDULED, DUE) |
| Unread alerts | `notifications` | unread count |
| Awaiting expert review | `observations` | count where `verification_status='PENDING_REVIEW'` |

Framing for the farmer is deliberately plain: "2 reports waiting for an expert" rather than a status enum. The verification distinction is preserved, but expressed in ordinary language.

### 25.4 Expert dashboard (`GET /dashboards/expert`)

| Widget | Source | Purpose |
|---|---|---|
| Queue depth | `expert_reviews` where state='QUEUED' | Current workload |
| Oldest queued case age | `min(queued_at)` | The SLA signal (§20.7) |
| My claimed cases | `expert_reviews` where `claimed_by`=me and state='CLAIMED' | Work in progress |
| Decisions made (window) | `expert_reviews` grouped by `decision` | Throughput |
| Confirmation vs correction rate | counts of CONFIRMED / CORRECTED / REJECTED ÷ total decided | **The AI-quality signal required by PRD §21** |
| Low-confidence share | `ai_predictions` where `is_low_confidence` ÷ total | Model health |
| Referrals awaiting lab result | `expert_reviews` where referred and `lab_result_at IS NULL` | Nothing lost in referral |
| Cases by crop / agent / district | grouped counts | Where attention is needed |

The confirmation-rate widget is deliberately prominent: it is the honest, human-derived measure of how the model is actually performing on real field images, and it accumulates without anyone having to claim an accuracy figure.

### 25.5 Official dashboard (`GET /dashboards/official` and sub-endpoints)

**Headline KPIs** — each returned as a pair, never a sum:

```json
{
  "cases": { "confirmed": 42, "predicted_unconfirmed": 118, "pending_review": 37,
             "rejected": 9, "total_observations": 206 },
  "coverage": { "reporting_farmers": 88, "fields_with_observations": 131,
                "districts_reporting": 4, "observations_per_active_field": 1.6 },
  "risk": { "fields_high": 21, "fields_medium": 64, "fields_low": 46 },
  "hotspots": { "confirmed": 3, "predicted": 7, "signal": 2 },
  "backlog": { "pending_reviews": 37, "oldest_pending_hours": 61 },
  "demo": { "included": false, "demo_count": 0 },
  "window": { "from": "...", "to": "..." }
}
```

**Sub-endpoints**

| Endpoint | Returns | Query shape |
|---|---|---|
| `/dashboards/official/trends` | Time series of confirmed and predicted counts, as **two separate series**, by `granularity` | `date_trunc(granularity, observed_at)` grouped by `verification_status` class |
| `/dashboards/official/distribution` | Counts by agent, by crop, by district | grouped counts, each split confirmed/predicted |
| `/dashboards/official/coverage` | Surveillance coverage | active fields ÷ registered fields; districts reporting ÷ districts in scope; median days since last observation per field |
| `/gis/layers/*` | Map layers | §19.7 |
| `/gis/priority-zones` | Ranked intervention zones with driver breakdown | §19.5 |

**Surveillance coverage** deserves a note: it measures *how much of the area is actually being observed*, which is the honest counterweight to a case count. A district with zero confirmed cases and zero observations is not a healthy district — it is an unmonitored one, and the dashboard must make that visible rather than showing a reassuring zero.

### 25.6 Query implementation notes

- Every aggregation is a parameterised SQL query in the repository layer, index-backed per §8 and §9, and bounded by the time window.
- Grouping by verification class uses a shared SQL expression so "confirmed" means exactly the same thing in every widget:
  ```sql
  CASE WHEN verification_status IN ('CONFIRMED','CORRECTED') THEN 'CONFIRMED'
       WHEN verification_status IN ('PREDICTED','PENDING_REVIEW') THEN 'PREDICTED'
       ELSE 'OTHER' END AS case_class
  ```
- **TECHNICAL RECOMMENDATION:** if a dashboard query exceeds its latency budget on real data, add a materialised view refreshed by the worker (`dashboard_daily_counts`), keyed by `(date, district_code, crop_id, agent_id, case_class, source_type)`. Do not add it pre-emptively — measure first (§31).
- Widget failures are isolated: each widget resolves independently so one slow aggregate degrades a single tile rather than blanking the page.

### 25.7 Export

`GET /dashboards/official/export?format=csv` returns the filtered aggregate as CSV for offline use, with the applied filters and the demo-inclusion flag written into the file header — so an exported file cannot be separated from the caveats that apply to it.

---

## 26. REAL DATA PIPELINE

### 26.1 End-to-end path

```
[Client]        Farmer/worker on a mobile browser
                  ↓  multipart POST /api/v1/observations   (JWT)
[Validation]    schema · ownership · crop-context consistency · GPS sanity
                · image content sniffing · duplicate checksum check
                  ↓
[Image store]   object store write + observation_images row (checksum, EXIF, quality flags)
                  ↓
[Persistence]   observations row: source_type=FIELD_OBSERVATION, geom (SRID 4326),
                district resolved by point-in-polygon, status=PROCESSING
                  ↓  (transaction committed — the observation is now safe)
[AI]            preprocessing → ModelRunner.predict → ai_predictions row
                → confidence gate → verification_status (PREDICTED | PENDING_REVIEW)
                  ↓
[Weather]       cache lookup → provider fetch → weather rows (or stale/absent, labelled)
                  ↓
[Context]       ContextEngine assembles RiskContext (includes PostGIS nearby-history query)
                  ↓
[Risk]          RuleBasedRiskEngine → risk_assessments row with contributing factors
                  ↓
[Advisory]      AdvisoryEngine → advisories row (frozen confidence + verification status)
                  ↓
[Follow-up]     FollowupService → followups row (interval from risk level)
                  ↓
[GIS]           hotspot bucket invalidated → worker recomputes hotspots/zones
                  ↓
[Notify]        high-risk / nearby-confirmed notifications (deduplicated)
                  ↓
[Expert]        if PENDING_REVIEW → expert_reviews queued → decision → status updated
                → advisory regenerated → hotspots invalidated again
                  ↓
[Dashboards]    official metrics recount, with confirmed and predicted kept separate
                  ↓
[Feedback]      CONFIRMED/CORRECTED observations become candidates for the
                field-validation dataset, subject to the §16.4 quality gate
```

### 26.2 How real data differs from demo data — at every layer

| Layer | Real field observation | Demo/simulated observation |
|---|---|---|
| **Database** | `source_type = 'FIELD_OBSERVATION'`; `created_by` is a real user; images exist in the object store; `location_method` reflects an actual capture | `source_type = 'DEMO_SIMULATION'`; `created_by` is the demo seeder account; images are placeholders or absent; coordinates are generated |
| **Write path** | Only via the authenticated API | Only via `scripts/seed_demo_data.py` or `POST /admin/demo-data/seed` (admin-only, audited) |
| **API** | Returned by default everywhere | Excluded by default from official dashboards and official map layers; included only when `include_demo=true`, and the response then carries the `DEMO_DATA_INCLUDED` warning |
| **Aggregations** | Counted in official KPIs | Counted separately; every KPI response carries `demo_included: true|false` and, when demo is included, a separate `demo_count` |
| **Hotspots** | Contribute normally | `algorithm_params.included_demo_data = true` on any hotspot they touched |
| **Model feedback** | Eligible for the dataset pool after the §16.4 gate | **Permanently ineligible** — the gate rejects `DEMO_SIMULATION` outright |
| **UI** | Standard markers and badges | Distinct colour, striped pattern, "Simulated demo data" chip, page-level banner |
| **Deletion** | Normal retention rules | Removable in bulk by `POST /admin/demo-data/reset` |

### 26.3 Data-quality checks on the real path

| Check | Action on failure |
|---|---|
| GPS accuracy worse than `GPS_MAX_ACCURACY_M` | Accepted, flagged `low_gps_accuracy`, shown to the expert |
| Coordinates outside `GIS_OPERATING_BBOX` | `422 COORDINATES_OUT_OF_BOUNDS` |
| Coordinates at exactly (0,0) | Rejected as a null-island artefact |
| EXIF GPS far from reported GPS | Flagged `gps_mismatch_m`, surfaced to the expert |
| `observed_at` in the future | `422 VALIDATION_ERROR` beyond the clock-skew allowance |
| Same image checksum, same field, inside the dedupe window | `409 DUPLICATE_OBSERVATION` |
| Observation point far outside its declared field boundary | Accepted, flagged `outside_field_boundary` |

These flags are advisory signals for the reviewing expert, not silent rejections — except where the data is definitively invalid.

### 26.4 Offline and poor-connectivity behaviour

**TECHNICAL RECOMMENDATION** (the PRD does not specify offline support): the farmer client is a PWA that queues a submission in IndexedDB when the network is unavailable and retries on reconnect, with an idempotency key so a retry cannot create a duplicate observation. Offline capture is genuinely valuable in the field, but it is a MEDIUM-priority enhancement — the demo flow does not depend on it, so it should not block Phase 9.

---

## 27. DEMO DATA STRATEGY

### 27.1 Purpose and boundary

Per PRD §7.4, simulated observations may be used to demonstrate map and hotspot behaviour when real observations are insufficient. They must be explicitly marked `DEMO_SIMULATION`, and provenance must be preserved in both database and UI. **Demo data exists to demonstrate functionality, never to imply findings.**

### 27.2 Generator design

`scripts/seed_demo_data.py`, parameterised and reproducible:

```
--districts <codes>       # which admin regions to place points in
--crops <codes>           # from the seeded catalogue only
--agents <codes>          # from the catalogue; is_ai_supported respected
--count <n>               # number of observations
--window-days <n>         # spread over the last n days
--clusters <n>            # number of spatial clusters, so hotspots are demonstrable
--confirmed-ratio <0..1>  # share receiving a simulated expert confirmation
--seed <int>              # deterministic: the same seed reproduces the same dataset
--dry-run                 # print what would be created
```

Guarantees enforced in code:
1. Every row gets `source_type = 'DEMO_SIMULATION'`. This is hard-coded, not a parameter.
2. Points are generated **inside real administrative boundaries** (`ST_GeneratePoints` / rejection sampling against `admin_regions.geom`), so the map looks plausible rather than showing points in the sea. Where boundaries are not yet loaded, generation is refused rather than falling back to a random bounding box.
3. Crop, variety, growth stage and agent are drawn only from seeded reference data — nothing invented at seed time.
4. Timestamps are spread over the window with a realistic diurnal skew.
5. Clusters are generated with a configurable spread so DBSCAN has something to find.
6. Simulated expert confirmations are attributed to a clearly named demo expert account (`demo.expert@…`), never to a real user.
7. The script refuses to run when `APP_ENV=production` unless `ALLOW_DEMO_SEED_IN_PROD=true` is explicitly set, and it always writes an `audit_logs` entry.

> **REQUIRES DECISION — demo image content.** Whether demo observations carry placeholder images, images from a public dataset (licence permitting), or no image at all. Whatever is chosen, the image must be labelled as demo content and must never enter the training pool (§16.4).

### 27.3 Reset

`POST /admin/demo-data/reset` (and `scripts/reset_demo_data.py`) deletes, in FK-safe order, every row where `source_type = 'DEMO_SIMULATION'` and every dependent row, plus their storage objects, then recomputes hotspots. It reports the counts deleted and writes an audit entry.

Because provenance is a hard column rather than a naming convention, **the reset is exact** — it cannot accidentally delete a real observation, and it cannot leave demo residue behind.

### 27.4 Seed data taxonomy

| Seed script | Content | `source_type` | Run in production? |
|---|---|---|---|
| `seed_reference_data.py` | Crops, varieties, growth stages, agents, symptoms, advisory templates, roles | `PUBLIC_DATA` or `GOVERNMENT_DATA` per its registered `data_sources` row | Yes — required |
| `seed_admin_regions.py` | Administrative boundaries | Per the source dataset | Yes, once the dataset decision is made |
| `seed_demo_users.py` | One demo account per role | n/a (users are not observations) | Demo only |
| `seed_demo_data.py` | Simulated observations, predictions, reviews, follow-ups | `DEMO_SIMULATION` | Demo only |

Reference data is **not** demo data — it is a real controlled vocabulary and is required for the system to function.

### 27.5 UI labelling (non-negotiable)

1. A page-level banner on any screen where demo data is visible.
2. A per-record chip on every card, row and map popup.
3. Distinct map symbology (colour plus a pattern, so the distinction survives greyscale printing and colour-blind viewers).
4. Dashboard KPIs display demo counts separately and never fold them into a headline figure.
5. Layer toggles for demo data are labelled "Simulated demo data", not "sample" or "test".

### 27.6 SIH demo integrity

For the SIH demonstration, the recommended posture is: **at least one genuinely real end-to-end observation captured live**, with demo data providing the surrounding density needed to make hotspots and dashboards meaningful. The presenter should be able to point at the screen and say which is which — the UI makes that possible without any verbal caveat. This directly implements PRD §27.1 ("Real data over impressive fake data").

---

## 28. EXTERNAL INTEGRATIONS

### 28.1 Integration register

| Integration | Purpose | Data exchanged | Protocol | Auth | Failure strategy | Caching | MVP / Future |
|---|---|---|---|---|---|---|---|
| **Weather provider** (**REQUIRES DECISION**) | Current, forecast, and possibly historical weather | Out: lat/lon, time. In: temperature, humidity, rainfall, wind, pressure | HTTPS REST (JSON) | API key in a header or query parameter, per the chosen provider | 4-tier degradation (§17.6); circuit breaker | DB-backed cache, TTL 60/180 min, grid-cell keyed | **MVP** |
| **Basemap tiles** (**REQUIRES DECISION**) | Leaflet base layer | Out: tile coordinates. In: raster/vector tiles | HTTPS tiles | Per provider terms; some require attribution and/or a key | Map renders with a blank base layer; all data layers still work | Browser cache | **MVP** |
| **Object storage** | Image storage | Image bytes | Local filesystem, or S3-compatible HTTPS | Filesystem permissions, or access key/secret | `503 STORAGE_UNAVAILABLE`; the transaction rolls back so no orphan row | n/a | **MVP** (local for the demo) |
| **Reverse geocoding** | Human-readable place names | Out: lat/lon. In: place name | HTTPS REST | Per provider | Degrade to coordinates and district code only | Long-lived DB cache, keyed by rounded coordinates | **Future (optional)** |
| **Administrative boundaries** (**REQUIRES DECISION**) | District/taluka polygons | Bulk geospatial file | One-off download, loaded via `ogr2ogr`/GeoPandas | Per licence | Load-time failure blocks Phase 4; no runtime dependency | Loaded into PostGIS once | **MVP (data, not a live API)** |
| **SMS / WhatsApp / push** | Alerts | Out: message | Per vendor | Per vendor | In-app notifications only; nothing is lost | n/a | **Future** |
| **IoT sensor ingest** | Field sensor readings | In: readings batch | HTTPS POST (`/sensors/ingest`) | **REQUIRES DECISION** | Endpoint disabled by default | n/a | **Future (contract defined now)** |
| **Government crop/disease datasets** (**REQUIRES DECISION**) | Contextual reference data | Bulk files or APIs | Per source | Per source | Absent → the feature is simply not offered | Loaded into PostGIS, registered in `data_sources` | **Future** |

### 28.2 Integration rules

1. Every integration is reached through an adapter interface. No router or service ever calls an external HTTP client directly.
2. Every integration is registered in `data_sources` with its licence, version and verification status before its data is displayed.
3. No integration is on the critical write path. An observation is saved before any external call is made.
4. Every outbound call has an explicit timeout, bounded retries with jittered backoff, and a circuit breaker.
5. Secrets come only from environment variables and are redacted from logs.
6. Every outbound failure is logged with the integration name, status code and latency, and increments a counter (§33).

### 28.3 What is deliberately not integrated

No satellite imagery (PRD §4), no external laboratory system (§20.5), no payment gateway, no national outbreak database (PRD §4), and no third-party identity provider. Each is either explicitly out of scope in the PRD or would require a verified partner that does not exist yet.

---

## 29. SECURITY REQUIREMENTS

### 29.1 Authentication and session security

- Argon2id password hashing; no plaintext or reversible storage anywhere.
- Short-lived access tokens; rotating refresh tokens with reuse detection (§13.1).
- Login rate limiting per IP and per identifier; progressive delay on repeated failure.
- Account deactivation is soft, immediate, and invalidates all refresh tokens for that user.
- Every authentication event (success, failure, refresh reuse, logout) is audited.

### 29.2 Authorization

- Server-side enforcement on every endpoint; client-side guards are UX only.
- Role checks **and** ownership/scope checks — a farmer with a valid token must not read another farmer's observation.
- Scoping filters live in the repository layer, so new endpoints inherit them rather than re-implementing them.
- Direct object references are UUIDs, not sequential integers, so IDs cannot be enumerated.
- The RBAC matrix (§13.5) is asserted by an automated test matrix covering every endpoint × every role.

### 29.3 Input validation

- Pydantic v2 models validate every request body; unknown fields are rejected (`extra="forbid"`).
- Explicit bounds on every numeric field (latitude, longitude, severity, counts, pagination).
- Enum fields accept only enum members.
- String length caps on every text field, to bound both storage and rendering cost.
- GeoJSON validated structurally and then by `ST_IsValid`.
- Free text is stored escaped and rendered as text, never as HTML.

### 29.4 SQL injection protection

- SQLAlchemy ORM and Core with bound parameters throughout.
- Raw SQL is permitted only for PostGIS operations that the ORM cannot express, and only with bound parameters — never f-strings or string concatenation.
- Sort and filter fields are validated against an allow-list before reaching a query, so a `sort` parameter cannot inject an expression.
- The application database role has no DDL privileges; migrations run under a separate role.

### 29.5 File-upload security

Covered in §14.2. Key points: magic-byte sniffing rather than trusting `Content-Type`; size and dimension caps to defeat decompression bombs; re-encoding through Pillow (which strips embedded payloads); storage outside the web root; no execution permissions on the storage directory; original filenames sanitised and never used as a path; access always mediated by an authorising endpoint.

### 29.6 CORS

`CORS_ALLOWED_ORIGINS` is an explicit list — never `*` in any deployed environment. Credentials allowed only for the configured frontend origin. Methods and headers restricted to what the client actually uses. Preflight cached for 10 minutes.

### 29.7 Secrets management

- All secrets from environment variables; `.env` is git-ignored; only `.env.example` (with empty values) is committed.
- The application refuses to boot if `JWT_SECRET` is missing, shorter than 32 characters, or equal to the example value — a weak-secret demo deployment is prevented rather than warned about.
- Logging filters redact any value whose key matches `password|secret|token|key|authorization`.
- Secrets never appear in error responses, audit payloads, or client-visible configuration.
- **REQUIRES DECISION — production secret store** (environment variables on the host, or a managed secret manager) once the hosting decision is made.

### 29.8 Transport and headers

TLS everywhere in deployed environments (HTTP permitted only for local development). Security headers set at the proxy: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and a Content-Security-Policy restricting script sources and permitting the chosen tile host. **TECHNICAL RECOMMENDATION.**

### 29.9 Rate limiting

| Endpoint group | Limit | Env |
|---|---|---|
| `/auth/login`, `/auth/register` | 5 / min / IP, 10 / hour / identifier | `RATE_LIMIT_AUTH` |
| `POST /observations`, image upload | 20 / hour / user | `RATE_LIMIT_UPLOAD` |
| `/ai/analyze` | 30 / hour / user | `RATE_LIMIT_AI` |
| `/gis/*` | 120 / min / user | `RATE_LIMIT_GIS` |
| Default | 300 / min / user | `RATE_LIMIT_DEFAULT` |

**TECHNICAL RECOMMENDATION** on the values. In-process limiting for the MVP single instance; a shared store is required if the app is ever scaled horizontally — noted so the limitation is known rather than discovered.

### 29.10 Audit trail

Audited actions: authentication events, role and permission changes, user create/deactivate, expert decisions and referrals, lab results, model registration and activation, advisory template changes, data-source registration and verification, demo data seed and reset, admin reads of audit logs, and any hard delete. The application role holds no `UPDATE`/`DELETE` grant on `audit_logs`.

### 29.11 Known MVP limitations (stated, not hidden)

- No multi-factor authentication.
- No field-level encryption at rest beyond what the database and disk provide.
- In-process rate limiting does not survive horizontal scaling.
- No automated dependency-vulnerability scanning beyond the CI step in §35.
- No penetration test has been performed.

These are recorded here deliberately: an SIH judge asking about security limitations should get an accurate answer, not a claim.

---

## 30. PRIVACY REQUIREMENTS

### 30.1 Data minimisation

Collected: name, phone (or email/username), preferred language, village/taluka/district, land holding, field geometry, crop context, observation images, GPS, notes.

**Explicitly not collected:** Aadhaar or any government identity number, bank or payment details, precise home address, date of birth, gender, caste, income, biometric data, or contacts. If a future requirement demands any of these, it needs an explicit purpose, a legal basis, and a schema change — it cannot arrive incidentally.

### 30.2 Sensitivity classification

| Data | Sensitivity | Handling |
|---|---|---|
| Farmer name and phone | Personal | Visible to the farmer, the scoped extension worker, and admins. **Never** exposed in official aggregate views or map popups. |
| Field location (precise) | Personal + locational | Visible to the owner, the scoped worker, and admins. Officials see aggregated or coarsened locations by default (§30.3). |
| Observation GPS | Personal + locational | Same as field location. |
| Observation images | Potentially identifying (faces, homes, documents may be captured incidentally) | Access-controlled; never public; EXIF stripped after extraction. |
| Expert identity | Professional | Shown on decisions for accountability; contact details are not exposed to farmers. |
| Aggregate counts by district | Low | Freely visible to officials. |

### 30.3 Location privacy for official views

> **TECHNICAL RECOMMENDATION.** Officials need spatial patterns, not individual farm addresses. The default official map layer therefore serves **aggregated** geometry — hotspot polygons, risk zones, and points snapped to a configurable grid (`OFFICIAL_LOCATION_PRECISION`, default ~500 m) — rather than exact field coordinates. Exact coordinates are available to officials only for a specific observation they open, and that access is audited.
>
> This is not stated in the PRD, so it is offered as a recommendation rather than imposed; the team may disable it via configuration. It costs nothing at the demo and materially reduces the risk of exposing individual farms.

### 30.4 Access control summary

| Who | Can see |
|---|---|
| Farmer | Only their own data |
| Extension worker | Farmers and observations within their assigned district scope |
| Lab expert | Only cases referred to a lab, plus their own decisions |
| Official | Aggregates within their district scope; individual records only on explicit, audited access |
| Admin | Everything, fully audited |

### 30.5 Retention

> **REQUIRES DECISION — retention periods.** The PRD does not specify them, and inventing a policy would be inventing a compliance posture. The team must decide, per category:
>
> | Category | Suggested consideration |
> |---|---|
> | Observation images | Longest — they are the model-improvement asset. Balance against storage cost and consent. |
> | Observation records | Retain for trend analysis; may outlive images. |
> | Weather cache | Short (e.g. one season) — regenerable from the provider. |
> | Audit logs | Longest of all; audit value depends on longevity. |
> | Deactivated user data | Governed by the deletion-request policy below. |
>
> Once decided, encode as `*_RETENTION_DAYS` environment variables and implement as worker jobs. Retention must not be silently unlimited.

### 30.6 Consent and user rights

- Registration presents a clear statement of what is collected and why, in the user's language.
- **Separate, optional consent** for research/model-training use of images (`farmers.research_consent BOOLEAN DEFAULT false`). The §16.4 quality gate requires it. Consent is opt-in, revocable, and its absence blocks training use without blocking the farmer's normal use of the app.
- Data export: a farmer can request their own data (`GET /farmers/me/export`) as JSON plus their images.
- Deletion: a farmer may request account deletion. **REQUIRES DECISION** — whether observations are anonymised (retaining the epidemiological value while severing the personal link) or deleted outright. Anonymisation is the **TECHNICAL RECOMMENDATION**, since the public-health value of the observation is independent of who reported it, but this is a policy call.

### 30.7 Third-party exposure

Only coordinates are sent to the weather provider — never names, phone numbers, images, or user identifiers. Basemap tile requests reveal viewport coordinates to the tile provider; this is inherent to web mapping and should be disclosed in the privacy notice. No user data is sent to any analytics or advertising service.

---

## 31. PERFORMANCE REQUIREMENTS

Targets are stated where a defensible engineering basis exists. Where a number would be guesswork, the entry is **TO BE BENCHMARKED** — per the PRD's instruction that performance should be measured, not fabricated.

### 31.1 API latency targets

| Operation | Target (p95) | Basis |
|---|---|---|
| `GET` simple resource by id | < 200 ms | Single indexed lookup |
| `GET /observations` (paginated, 20 rows) | < 400 ms | Indexed filter + count |
| `POST /observations` (persist + respond `202`) | < 1.5 s | Dominated by the image upload, excluding inference |
| `GET /gis/observations` (bbox, ≤ 1000 features) | < 800 ms | GIST-indexed bbox query + GeoJSON serialisation |
| `GET /hotspots` (precomputed) | < 300 ms | Table read, no computation |
| Dashboard KPI endpoint | < 1 s | Indexed aggregation over a bounded window |
| `POST /auth/login` | < 500 ms | Argon2 verification dominates and is intentionally slow |

All **TECHNICAL RECOMMENDATION** targets for a modest single instance; they are goals to measure against, not measurements.

### 31.2 AI inference

**TO BE BENCHMARKED.** Inference time depends entirely on the model architecture, input size, and whether the deployment has a GPU — none of which is decided yet. Guessing a millisecond figure would be inventing performance.

What *is* specified:
- Measure `inference_ms` on every prediction and store it, so the number comes from production rather than a spreadsheet.
- If measured p95 exceeds `AI_SYNC_BUDGET_MS` (default 5000), switch to the asynchronous path (§15.6) — the decision rule is defined even though the number is not.
- Concurrency is capped by `AI_MAX_CONCURRENT_INFERENCE` so inference cannot starve the API.
- The model is warmed at startup so the first user does not pay initialisation cost.

### 31.3 Image upload

| Metric | Target |
|---|---|
| Client-side downscale before upload | Longest edge ≤ 1600 px, JPEG q80 — typically well under 1 MB |
| Upload time on a 1 Mbps connection | **TO BE BENCHMARKED** in real field conditions |
| Server-side processing (validate, strip, thumbnail) | < 500 ms for a 2 MP image on modest CPU — **TO BE BENCHMARKED** |
| Progress feedback | Required at all times (PRD §20) |

### 31.4 GIS query performance

| Query | Target | Enabler |
|---|---|---|
| Radius query, 10 km, 30-day window | < 300 ms | `ST_DWithin` on `geography` + GIST index |
| Bbox viewport query, ≤ 5000 features | < 800 ms | Partial GIST indexes (§9.3) |
| Hotspot recomputation | Background only; never in a request | Worker job |
| Point-in-polygon district resolution on write | < 50 ms | GIST index on `admin_regions.geom` |

Verification method: `EXPLAIN (ANALYZE, BUFFERS)` on each query with a realistic row count, checked into `docs/perf/`. A target without a query plan behind it is not accepted.

### 31.5 Database and indexing

Every query in the codebase must be satisfiable by an index. The indexes in §8 and §9 are the minimum. A CI check runs `EXPLAIN` on a set of representative queries and fails the build on an unexpected sequential scan over `observations`. **TECHNICAL RECOMMENDATION.**

### 31.6 Concurrency

| Metric | MVP target | Notes |
|---|---|---|
| Concurrent users | 50 (demo) / 200 (pilot) | **TO BE BENCHMARKED** against the chosen host |
| Concurrent inference | `AI_MAX_CONCURRENT_INFERENCE` (default 2) | Bounded by CPU |
| DB connection pool | 20 + 10 overflow | Tune to the host's connection limit |
| Uvicorn workers | `CPU_COUNT` (bounded) | Fewer if inference is in-process, since it competes for CPU |

### 31.7 Frontend performance

| Metric | Target |
|---|---|
| First contentful paint, 3G, mid-range Android | < 3 s — **TO BE BENCHMARKED** |
| JS bundle, initial route | < 300 KB gzipped, via route-based code splitting |
| Map with 1000 markers | Smooth pan/zoom via clustering |
| Time to interactive after login | < 2 s on a broadband connection |

### 31.8 Benchmarking plan

Because most of the above is a target rather than a measurement, Phase 10 includes an explicit benchmarking task: seed a realistic dataset (10k observations, 500 fields, 5k images), run each endpoint under a load tool, record p50/p95/p99 into `docs/perf/baseline.md`, and replace every **TO BE BENCHMARKED** entry with a real number and the hardware it was measured on. Only then may any performance claim be made to a judge.

---

## 32. RELIABILITY & FAILURE HANDLING

### 32.1 Governing principle

**The observation must survive.** Everything downstream of persistence — inference, weather, risk, advisory, hotspots — is enrichment. Enrichment may fail; the farmer's report must not be lost, and the failure must be visible rather than disguised.

### 32.2 Failure matrix

| Failure | Detection | System behaviour | User sees | Recovery |
|---|---|---|---|---|
| **AI model not loaded** | Startup checksum/load failure; `/health` reports `AI_DEGRADED` | Observations accepted, routed to `PENDING_REVIEW` | "Automatic analysis unavailable — sent for expert review" | Admin reactivates a model version; hot reload, no restart |
| **Inference exception/timeout** | Exception or timeout in `InferenceService` | No prediction row; status `AI_FAILED`; review queued; `processing_errors` records the reason | Same as above, plus a retry option | `POST /observations/{id}/reanalyze` |
| **Weather provider down** | Timeout, `5xx`, or open circuit breaker | Stale cache if within `WEATHER_STALE_MAX_HOURS`, else weather omitted; risk still computed | "Weather from {time}" or "Risk calculated without weather" | Automatic on the next successful fetch; scheduled refresh backfills |
| **Weather rate limit** | `429` | Serve cached/stale data; the outbound limiter throttles | Stale-data notice | Automatic |
| **Database unreachable** | Connection failure | `503` on every endpoint; readiness probe fails | Full-page "Service temporarily unavailable" with retry | Connection pool recovery; restart if needed |
| **Database slow / lock contention** | Statement timeout | `504` on the affected endpoint only | Timeout message with a narrower-filter hint | Query tuning; the timeout prevents cascade |
| **Image upload — storage down** | Adapter exception | `503 STORAGE_UNAVAILABLE`; transaction rolled back; **no orphan observation row** | "Could not save the photo — please try again" | Client retries with the same idempotency key |
| **Image upload — network drop mid-upload** | Incomplete request | Request fails; nothing persisted | Progress bar shows failure; retry offered | Client retries; the checksum dedupe prevents a double record |
| **GIS query timeout** | `statement_timeout` | `504 GIS_TIMEOUT` for that layer only | That layer fails to load; other layers still render; retry offered | Narrow the bbox or time window |
| **Hotspot recomputation fails** | Worker job exception | Previous snapshot remains `is_current`; error logged and alerted | Hotspots shown with their (older) `computed_at` timestamp | Next scheduled run, or a manual trigger |
| **No expert available** | Queue age exceeds `REVIEW_SLA_HOURS` | Observation stays `PENDING_REVIEW`; **never auto-promoted** | "Awaiting expert review" plus a cautious advisory | Queue-age metric surfaced on expert and official dashboards |
| **Advisory template missing** | No candidate template | Generic fallback advisory | A general advisory recommending expert consultation | Admin adds the template |
| **Translation key missing** | Lookup miss | Falls back to `en`; warning `LANGUAGE_FALLBACK` | English text with a small "not yet translated" note | Translator adds the key; CI catches it beforehand |
| **Client offline** | Browser network state | Submission queued locally (§26.4, if implemented); read views serve cached data | Offline banner; queued-submission count | Automatic retry on reconnect |
| **Worker process down** | No heartbeat | Scheduled jobs do not run; API remains fully functional | Hotspots and follow-up transitions become stale, with visible timestamps | Restart the worker; jobs are idempotent and catch up |

### 32.3 Degradation ladder

```
FULL          all components healthy
  ↓ weather provider down
WEATHER_STALE weather from cache, labelled
  ↓ weather cache exhausted
NO_WEATHER    risk computed without weather, uncertainty raised, factor listed as missing
  ↓ AI unavailable
AI_DEGRADED   observations accepted, all routed to expert review
  ↓ worker down
STALE_DERIVED hotspots and follow-up transitions stale, timestamps visible
  ↓ database down
UNAVAILABLE   the only true outage
```

Each rung is reported by `/health` and, where user-visible, rendered in the UI. **The system's honesty about its own state is a product feature, not just an operational one.**

### 32.4 Idempotency

- `POST /observations` accepts an `Idempotency-Key` header; a repeat within `IDEMPOTENCY_TTL_MIN` returns the original result instead of creating a duplicate.
- Image checksum deduplication provides a second layer of protection.
- Every worker job is idempotent — recomputing hotspots or rescanning follow-ups twice produces the same state.
- Expert decisions use optimistic locking, so a double-submitted decision is rejected rather than applied twice.

### 32.5 Backups

- Nightly `pg_dump` (schema plus data) retained per `BACKUP_RETENTION_DAYS`.
- The object store is backed up on the same schedule (or relies on the provider's durability, once chosen).
- **A backup is not a backup until a restore has been tested.** Phase 10 includes an actual restore into a scratch database, and the result is recorded.
- **REQUIRES DECISION — backup destination and retention**, dependent on the hosting decision.

---

## 33. LOGGING & MONITORING

### 33.1 Two separate streams

| | Operational logs | Business audit logs |
|---|---|---|
| **Question answered** | "Is the system working?" | "Who did what to this record?" |
| **Destination** | stdout (JSON), collected by the platform | `audit_logs` table |
| **Audience** | Developers, operators | Admins, auditors, evaluators |
| **Retention** | Short (days to weeks) | Long (§30.5) |
| **Mutability** | Rotated and discarded | Append-only, no update/delete grant |
| **Contains PII** | No — identifiers only | Yes, deliberately and access-controlled |

Conflating the two is a common failure; keeping them apart is a requirement here.

### 33.2 Structured operational logging

JSON lines to stdout, one event per line:

```json
{ "ts": "2026-09-05T10:15:00.123Z", "level": "INFO", "logger": "app.api.observations",
  "event": "observation_created", "trace_id": "0f2c...", "user_id": "uuid",
  "role": "FARMER", "observation_id": "uuid", "duration_ms": 842,
  "status_code": 202, "path": "/api/v1/observations", "method": "POST" }
```

Every request carries a `trace_id` (from `X-Request-Id` if supplied, otherwise generated), which is returned to the client, written into audit rows, and included in every log line for that request — so a user reporting a problem can quote a single id that resolves the whole story.

Levels: `DEBUG` local only; `INFO` lifecycle events; `WARNING` degradation (stale weather, low confidence, language fallback); `ERROR` failed operations; `CRITICAL` component unavailability.

### 33.3 Domain-specific logging

| Domain | Logged | Purpose |
|---|---|---|
| AI inference | model version, confidence, `inference_ms`, device, success/failure, failure reason | Low-confidence rate and failure rate (PRD §21) |
| Weather | provider, cache hit/miss, staleness, latency, status code, breaker state | Provider availability tracking (PRD §21) |
| GIS | query type, feature count, duration, truncation | Spot slow or unbounded queries |
| Risk | ruleset version, missing factors, computed level | Detect systematically missing inputs |
| Auth | success/failure, reason class, IP, user agent | Detect credential attacks |
| External calls | integration, status, latency, retry count | Integration health |

Redaction: a logging filter strips any field whose key matches `password|secret|token|key|authorization|phone|email`. Coordinates are logged only at reduced precision.

### 33.4 Metrics

Counters: `observations_created_total{source_type}`, `ai_predictions_total{model_version}`, `ai_low_confidence_total`, `ai_inference_failures_total`, `expert_decisions_total{decision}`, `weather_requests_total{result}`, `api_requests_total{path,method,status}`, `advisories_generated_total`, `followups_submitted_total`.

Histograms: `api_request_duration_seconds{path}`, `ai_inference_duration_seconds`, `gis_query_duration_seconds{query_type}`, `weather_request_duration_seconds`.

Gauges: `review_queue_depth`, `review_queue_oldest_age_hours`, `ai_model_loaded`, `weather_breaker_open`, `db_pool_in_use`.

Derived business metrics required by PRD §21: low-confidence rate = `ai_low_confidence_total / ai_predictions_total`; expert confirmation rate = `expert_decisions_total{CONFIRMED} / expert_decisions_total`; failed inference rate; weather availability.

**TECHNICAL RECOMMENDATION:** expose these at `/metrics` in Prometheus format via `prometheus-fastapi-instrumentator`. For the MVP a Prometheus server is optional — the endpoint alone lets anyone `curl` real numbers, which is far better than claiming them.

### 33.5 Health endpoints

- `GET /health` — liveness plus a component breakdown `{database, storage, ai_model, weather_provider}`, app version and git SHA. Always `200` when the process is alive; the body reports degradation.
- `GET /health/ready` — readiness: `200` only when the database and storage are reachable. Returns `503` otherwise so an orchestrator does not route traffic to a broken instance.

### 33.6 Alerting (MVP-appropriate)

**TECHNICAL RECOMMENDATION:** no paging infrastructure for a hackathon MVP. Instead: log `CRITICAL` for component unavailability, surface degraded state on the admin dashboard, and have the demo operator check `/health` before the demonstration. Real alerting is a post-pilot concern and should not consume MVP time.

---

## 34. TESTING STRATEGY

### 34.1 Test pyramid and tooling

| Level | Tool | Scope | Target |
|---|---|---|---|
| Unit | `pytest` | Pure functions: risk rules, confidence gating, advisory selection, provenance stamping, geometry helpers | Fast, no I/O, the bulk of the suite |
| Integration | `pytest` + a real PostGIS test database (Docker) | Repositories, spatial queries, transactions, migrations | Real database — never SQLite, since PostGIS is central |
| API | `pytest` + `httpx.AsyncClient` | Endpoint contracts, RBAC, validation, error envelopes | Every endpoint |
| Frontend unit | Vitest + React Testing Library | Components, hooks, formatters | Provenance and map components prioritised |
| E2E | Playwright | The full PRD §23 flow across roles | The demo flow, guaranteed |
| Security | `pytest` matrix + `pip-audit`/`npm audit` | RBAC matrix, injection attempts, upload abuse | Every endpoint × every role |

Coverage target: **TECHNICAL RECOMMENDATION** — 80 % on `services/`, `risk/`, `advisory/` and `ai/` (the logic that decides what a farmer is told); lower elsewhere. Coverage is a signal, not a goal in itself.

### 34.2 Test data

- `factory-boy` factories for every entity, defaulting to valid, realistic values.
- A `conftest.py` fixture creating a transactional test database, rolled back per test.
- Deterministic geometry fixtures (fixed coordinates inside a fixture admin region) so spatial assertions are exact.
- `StubRunner` for AI, returning a fixed prediction so pipeline tests do not require model weights.
- `FixtureWeatherProvider` returning fixed readings, plus a `FailingWeatherProvider` for degradation tests.

### 34.3 Critical scenarios (each is a named, required test)

**Low-confidence AI result**
```
GIVEN an active model with high_confidence_threshold = 0.75
WHEN an observation yields confidence 0.42
THEN observations.verification_status = 'PENDING_REVIEW'
 AND an expert_reviews row exists in state QUEUED
 AND GET /observations/{id} shows is_low_confidence = true
 AND the advisory contains NO agent-specific treatment guidance
 AND no response field presents the prediction as a diagnosis
```

**Expert correction**
```
GIVEN an observation PREDICTED as agent A
WHEN an expert submits decision=CORRECTED with corrected_agent_id=B
THEN verification_status='CORRECTED' AND final_agent_id=B
 AND the original prediction row is unchanged (immutability)
 AND the previous advisory is is_superseded=true
 AND a new advisory exists for agent B
 AND an audit_logs row exists with action='EXPERT_DECISION' and both states
 AND hotspot recomputation has been invalidated
```

**Confirmed observation appears correctly**
```
GIVEN a CONFIRMED observation inside a bbox
WHEN GET /gis/layers/confirmed_cases is called with that bbox
THEN the feature is present with verification_status='CONFIRMED'
 AND properties.match_basis='CONFIRMED_AGENT'
 AND it is ABSENT from the predicted_cases layer
```

**Simulated data provenance**
```
GIVEN seeded demo observations
WHEN an OFFICIAL calls GET /dashboards/official (default filters)
THEN demo rows are excluded from the headline counts
 AND meta.demo_included = false
WHEN the same call is made with include_demo=true
THEN warnings contains DEMO_DATA_INCLUDED
 AND every returned demo feature has source_type='DEMO_SIMULATION'
AND no demo observation passes the §16.4 training-eligibility gate
```

**Invalid GPS**
```
lat=91           → 422 VALIDATION_ERROR
lat=0, lon=0     → 422 COORDINATES_OUT_OF_BOUNDS   (null island)
outside operating bbox → 422 COORDINATES_OUT_OF_BOUNDS
gps_accuracy_m = 500   → accepted, flagged low_gps_accuracy, visible to the expert
```

**Duplicate observation**
```
GIVEN an image with checksum X submitted for field F
WHEN the identical image is submitted for field F inside the dedupe window
THEN 409 DUPLICATE_OBSERVATION and no second observation row is created
WHEN it is submitted for a DIFFERENT field
THEN it is accepted (the same photo may legitimately be sent about another plot)
```

**Weather failure**
```
GIVEN a FailingWeatherProvider and no cached weather
WHEN an observation is created
THEN the observation is created successfully (201/202)
 AND risk_assessments exists with 'WEATHER' in missing_factors
 AND uncertainty is higher than the equivalent with weather present
 AND the response carries warning WEATHER_UNAVAILABLE
 AND no invented weather value appears anywhere in the response
```

**GIS filtering**
```
Seed observations across two districts, two crops, two agents, two time windows.
Assert each filter combination returns exactly the expected set:
  district_code · crop_id · agent_id · verification_status · from/to · radius · bbox
Assert an unbounded query returns 422 BBOX_REQUIRED.
Assert include_demo=false excludes DEMO_SIMULATION rows.
```

**Follow-up workflow**
```
Create observation → follow-up scheduled with the interval matching the risk level
Advance the clock → the due-scan job moves SCHEDULED → DUE and emits one notification
Submit the follow-up → a child observation exists with parent_observation_id set
                    → the pipeline ran on the child
                    → followups.status='SUBMITTED', outcome recorded
                    → comparison_metadata contains deltas AND the causal caveat key
Skip the window     → status becomes MISSED, the record is retained
```

**Additional required tests:** concurrent review claim (one succeeds, one gets 409); RBAC matrix (every endpoint × every role); malicious upload (a renamed executable, an oversized image, a decompression bomb — all rejected); token expiry and refresh rotation with reuse detection; language fallback; last-admin protection; migration up/down on a fresh database.

### 34.4 GIS-specific testing

Requires a real PostGIS instance. Tests assert: SRID is 4326 on every geometry column; `ST_DWithin` on `geography` returns metre-accurate results against hand-computed fixtures; a point-in-polygon district resolution is correct at a boundary; DBSCAN clustering produces the expected cluster count for a fixture point set; concave-hull fallbacks trigger correctly for 1-, 2- and 3-point clusters; an invalid polygon is rejected; the GeoJSON serialiser raises when provenance is absent.

### 34.5 AI testing

With `StubRunner`: the full pipeline, both confidence branches, mapping from raw class to catalogue code, prediction immutability, and correct handling of an unmapped class.

With a real model (once one exists): loading and checksum verification, output shape and range, deterministic output for a fixed input, preprocessing correctness, and inference timing recorded for §31.2. **No test asserts an accuracy figure until a real evaluation run produces one.**

### 34.6 End-to-end scenario (Playwright)

The PRD §23 flow, automated: farmer registers → creates a field → runs the capture wizard → sees prediction, confidence, risk and advisory → the observation appears on the map with the correct provenance badge → an expert logs in, claims the case, corrects the diagnosis → the farmer sees the corrected diagnosis and the regenerated advisory → the follow-up is scheduled and submitted → the official dashboard shows the confirmed case, separately from predicted ones.

This single test is the strongest defence against a broken demo, and it should be run before every demonstration.

### 34.7 What is not tested (stated honestly)

No load testing beyond the §31.8 benchmark; no penetration testing; no cross-browser matrix beyond current Chrome and Android Chrome; no accessibility audit beyond basic semantic HTML and contrast checks. These are acknowledged gaps, not silent ones.

---

## 35. CI/CD

### 35.1 Pipeline (GitHub Actions)

```
on: [push, pull_request]

job: backend
  1. checkout · setup Python 3.11 · cache deps
  2. lint       ruff check .           (fail on error)
  3. format     ruff format --check .
  4. types      mypy app/              (non-blocking initially, blocking once clean)
  5. security   pip-audit
  6. services   postgres:16 + postgis   (service container)
  7. migrate    alembic upgrade head    (proves migrations apply to a clean DB)
  8. test       pytest --cov=app --cov-fail-under=<threshold>
  9. archive    coverage report

job: frontend
  1. checkout · setup Node 20 · cache
  2. lint       eslint .   (includes the no-literal-string i18n rule)
  3. types      tsc --noEmit
  4. i18n       scripts/check-translations.js   (fails on a key present in en but missing in hi/mr)
  5. security   npm audit --audit-level=high
  6. test       vitest run --coverage
  7. build      vite build

job: e2e            (needs: backend, frontend)
  docker compose up → seed reference + demo data → playwright test → upload traces on failure

job: deploy         (only on main, only if all above pass)
  build images → push → migrate → deploy → smoke-test /health
```

### 35.2 Migration policy

- Every schema change is an Alembic migration; no manual DDL in any environment.
- Migrations run as a separate step before the application starts, under a role with DDL privileges (the application role has none).
- Every migration must be reversible, and `downgrade` is tested in CI.
- Destructive changes are two-phase: add the new column and backfill in one release, drop the old column in a later one — so a rollback never loses data.
- Enum additions use `ALTER TYPE ... ADD VALUE` (safe); enum removals require a full type rebuild and are avoided.

### 35.3 Environments

| Environment | Purpose | Database | Demo data | AI model |
|---|---|---|---|---|
| `local` | Development | Local Docker PostGIS | Yes | `StubRunner` or a real model |
| `ci` | Automated tests | Ephemeral service container | Seeded per test | `StubRunner` |
| `demo` | The SIH demonstration | Managed instance (**REQUIRES DECISION**) | Yes, clearly labelled | The real model |
| `production` | Future pilot | Managed instance | **No** (guarded) | The real model |

### 35.4 Deployment topology (MVP)

```
docker-compose.yml
├── db        postgis/postgis:16-3.4   (named volume)
├── backend   FastAPI (uvicorn)        → depends_on: db
├── worker    same image, worker entrypoint → depends_on: db
├── frontend  nginx serving the built SPA
└── proxy     nginx/caddy: TLS, /api → backend, / → frontend
```

One `docker compose up` brings up the entire system. This is deliberate: a demo that requires a multi-step deployment is a demo that fails at the wrong moment.

> **REQUIRES DECISION — hosting.** No cloud provider, region, instance size, or managed-database choice is assumed. Compose runs anywhere from a laptop to a single VM. Once hosting is decided, add the deploy job's target and the production secret store (§29.7).

### 35.5 Release discipline

- Semantic version tags; the git SHA is baked into the image and returned by `/health`.
- The main branch is always deployable; feature branches with PR review.
- A pre-demo checklist (run as a script): migrations current, reference data seeded, demo data seeded and labelled, model active and loaded, `/health` all-green, E2E suite passing.

---

## 36. ENVIRONMENT CONFIGURATION

All configuration is environment-driven. `.env.example` is committed with **empty** secret values; `.env` is git-ignored. The application validates configuration at startup and refuses to boot on a missing or unsafe required value.

### 36.1 Application

| Variable | Example | Required | Notes |
|---|---|---|---|
| `APP_ENV` | `local` | yes | `local` / `ci` / `demo` / `production` — gates unsafe defaults |
| `APP_NAME` | `FloraSentry V2` | no | |
| `APP_VERSION` | `2.0.0` | no | injected at build time |
| `GIT_SHA` | — | no | injected at build; returned by `/health` |
| `DEBUG` | `false` | no | must be false outside `local` |
| `LOG_LEVEL` | `INFO` | no | |
| `LOG_FORMAT` | `json` | no | `json` / `console` |
| `API_BASE_PATH` | `/api/v1` | no | |
| `DEFAULT_LANGUAGE` | `en` | no | |
| `SUPPORTED_LANGUAGES` | `en,hi,mr` | no | |

### 36.2 Database

| Variable | Example | Required |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://user:pass@db:5432/florasentry` | **yes** |
| `DATABASE_POOL_SIZE` | `20` | no |
| `DATABASE_MAX_OVERFLOW` | `10` | no |
| `DATABASE_POOL_TIMEOUT_SEC` | `30` | no |
| `DATABASE_STATEMENT_TIMEOUT_MS` | `15000` | no |
| `DATABASE_ECHO` | `false` | no — never true outside `local` |
| `MIGRATION_DATABASE_URL` | separate DDL-privileged role | no |

### 36.3 Authentication

| Variable | Example | Required | Notes |
|---|---|---|---|
| `JWT_SECRET` | — | **yes** | ≥ 32 chars; boot fails if missing, short, or equal to the example |
| `JWT_ALGORITHM` | `HS256` | no | |
| `JWT_ACCESS_TTL_MIN` | `30` | no | |
| `JWT_REFRESH_TTL_DAYS` | `14` | no | |
| `PASSWORD_MIN_LENGTH` | `8` | no | |
| `ARGON2_TIME_COST` / `_MEMORY_COST` / `_PARALLELISM` | `2` / `65536` / `2` | no | |
| `REFRESH_TOKEN_COOKIE_ENABLED` | `true` | no | per the §13.4 decision |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | **yes** | comma-separated; never `*` |

### 36.4 Storage and images

| Variable | Example | Required |
|---|---|---|
| `STORAGE_BACKEND` | `local` | yes (`local` / `s3`) |
| `STORAGE_LOCAL_PATH` | `/var/florasentry/media` | if `local` |
| `S3_ENDPOINT_URL` / `S3_BUCKET` / `S3_REGION` | — | if `s3` |
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | — | if `s3` |
| `IMAGE_MAX_BYTES` | `10485760` | no |
| `IMAGE_ALLOWED_MIME` | `image/jpeg,image/png,image/webp` | no |
| `IMAGE_MIN_EDGE_PX` / `IMAGE_MAX_EDGE_PX` | `224` / `8000` | no |
| `IMAGE_STORE_MAX_EDGE_PX` | `2048` | no |
| `IMAGE_THUMBNAIL_EDGE_PX` | `320` | no |
| `IMAGE_MAX_PER_OBSERVATION` | `5` | no |
| `IMAGE_DEDUPE_WINDOW_HOURS` | `24` | no |
| `IMAGE_SIGNED_URL_TTL_SEC` | `300` | no |
| `IMAGE_RETENTION_DAYS` | — | **REQUIRES DECISION** (§30.5) |

### 36.5 AI

| Variable | Example | Required | Notes |
|---|---|---|---|
| `AI_ENABLED` | `true` | no | `false` routes everything to expert review |
| `AI_MODEL_ARTIFACT_DIR` | `/var/florasentry/models` | yes if enabled | |
| `AI_DEFAULT_MODEL_VERSION` | — | no | otherwise the active registry row is used |
| `AI_DEVICE` | `cpu` | no | `cpu` / `cuda` |
| `AI_MAX_CONCURRENT_INFERENCE` | `2` | no | |
| `AI_INFERENCE_TIMEOUT_SEC` | `30` | no | |
| `AI_SYNC_BUDGET_MS` | `5000` | no | above this, move to the async path |
| `TORCH_NUM_THREADS` | `2` | no | |

Confidence thresholds are **not** environment variables — they live per model in `ai_model_registry`, so a model swap carries its own thresholds.

### 36.6 Weather

| Variable | Example | Required |
|---|---|---|
| `WEATHER_PROVIDER` | `fixture` | yes (`fixture` until the §17.1 decision) |
| `WEATHER_API_KEY` | — | if a live provider |
| `WEATHER_BASE_URL` | — | if a live provider |
| `WEATHER_TIMEOUT_SEC` | `8` | no |
| `WEATHER_MAX_RETRIES` | `2` | no |
| `WEATHER_CACHE_TTL_MIN` | `60` | no |
| `WEATHER_FORECAST_TTL_MIN` | `180` | no |
| `WEATHER_STALE_MAX_HOURS` | `24` | no |
| `WEATHER_GRID_PRECISION` | `2` | no |
| `WEATHER_MAX_CALLS_PER_MIN` | `30` | no |
| `WEATHER_BREAKER_FAILURES` / `_RESET_SEC` | `5` / `300` | no |
| `WEATHER_REFRESH_CRON` | `0 */3 * * *` | no |

### 36.7 Risk, GIS and hotspots

| Variable | Example |
|---|---|
| `RISK_RULESET_PATH` | `app/risk/rulesets/ruleset_v1.yaml` |
| `RISK_FORECAST_DAYS` | `7` |
| `RISK_NEARBY_RADIUS_M` | `5000` |
| `RISK_NEARBY_WINDOW_DAYS` | `30` |
| `RISK_ACTIVE_WINDOW_DAYS` | `30` |
| `GIS_OPERATING_BBOX` | `72.6,15.6,80.9,22.1` (**REQUIRES DECISION** — confirm the intended extent) |
| `GIS_MAX_FEATURES` | `5000` |
| `GIS_MAX_RADIUS_M` | `50000` |
| `GIS_QUERY_TIMEOUT_MS` | `10000` |
| `GIS_METRIC_SRID` | `32643` |
| `HOTSPOT_EPS_M` | `2000` (**REQUIRES DECISION** — §19.2) |
| `HOTSPOT_MIN_POINTS` | `3` (**REQUIRES DECISION**) |
| `HOTSPOT_MIN_RADIUS_M` | `500` |
| `HOTSPOT_WINDOW_DAYS` | `14` |
| `HOTSPOT_CRON` | `*/30 * * * *` |
| `OFFICIAL_LOCATION_PRECISION_M` | `500` (§30.3) |

### 36.8 Workflow, follow-up and demo

| Variable | Example |
|---|---|
| `REVIEW_CLAIM_TTL_MIN` | `30` |
| `REVIEW_SLA_HOURS` | `48` |
| `FOLLOWUP_DAYS_HIGH` / `_MEDIUM` / `_LOW` | `3` / `7` / `14` |
| `FOLLOWUP_MAX_CHAIN` | `10` |
| `FOLLOWUP_SCAN_CRON` | `0 6 * * *` |
| `ALLOW_DEMO_SEED_IN_PROD` | `false` |
| `DEMO_SEED_DEFAULT_COUNT` | `200` |
| `SENSOR_INGEST_ENABLED` | `false` |
| `IDEMPOTENCY_TTL_MIN` | `60` |
| `RATE_LIMIT_AUTH` / `_UPLOAD` / `_AI` / `_GIS` / `_DEFAULT` | see §29.9 |
| `BACKUP_RETENTION_DAYS` | **REQUIRES DECISION** |

### 36.9 Frontend (Vite — `VITE_` prefixed values are public)

| Variable | Example | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | |
| `VITE_APP_ENV` | `local` | |
| `VITE_DEFAULT_LANGUAGE` | `en` | |
| `VITE_MAP_TILE_URL` | — | **REQUIRES DECISION** (§28.1) |
| `VITE_MAP_ATTRIBUTION` | — | required by most tile providers' terms |
| `VITE_MAP_DEFAULT_CENTER` / `_ZOOM` | `19.75,75.71` / `7` | |
| `VITE_MAX_IMAGE_EDGE_PX` | `1600` | client-side downscale target |
| `VITE_ENABLE_OFFLINE_QUEUE` | `false` | §26.4 |

**Never** put a secret behind `VITE_` — every such value is compiled into the public bundle.

### 36.10 Startup validation

At boot, `Settings` asserts: required variables present; `JWT_SECRET` length and not-the-example; `DEBUG` false outside `local`; `CORS_ALLOWED_ORIGINS` not `*`; `DATABASE_URL` parseable; the storage path writable or the S3 bucket reachable; `AI_MODEL_ARTIFACT_DIR` present when `AI_ENABLED`; the risk ruleset file parseable; `GIS_OPERATING_BBOX` well-formed. A failure aborts startup with a precise message naming the variable. **A misconfigured system must not start and pretend to work.**

---

## 37. DEPLOYMENT

### 37.1 Container images

- **Backend:** multi-stage Python 3.11-slim; system packages for GDAL/GEOS/PROJ (PostGIS client), Pillow and OpenCV; non-root user; dependencies installed in a builder stage; model artefacts mounted as a volume, **not** baked into the image (they are large and change independently).
- **Worker:** the same image, different entrypoint — guaranteeing identical code and dependencies.
- **Frontend:** Node build stage → static assets served by nginx.

### 37.2 Startup order

`db` (healthcheck: `pg_isready` + PostGIS extension present) → migration job (`alembic upgrade head`) → `backend` and `worker` → `proxy`. `depends_on` with health conditions, so nothing starts against a database that is not ready.

### 37.3 First-run bootstrap

```bash
docker compose up -d db
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python scripts/seed_reference_data.py
docker compose run --rm backend python scripts/seed_admin_regions.py      # after the dataset decision
docker compose run --rm backend python scripts/create_admin_user.py       # prompts, never a default password
docker compose run --rm backend python scripts/seed_demo_data.py --seed 42 --count 200
docker compose up -d
```

There is deliberately **no default admin password**. A seeded `admin/admin` is how demo systems become real breaches.

### 37.4 Pre-demo checklist (`scripts/predemo_check.py`)

1. `/health` reports all components healthy.
2. Migrations at head.
3. Reference data present (crops, agents, advisory templates).
4. An AI model is registered, active, checksum-verified and loaded.
5. Weather provider reachable, or the fixture provider deliberately configured.
6. Demo data seeded and every row labelled `DEMO_SIMULATION`.
7. At least one non-demo observation exists (the real end-to-end proof).
8. Hotspots computed and non-empty.
9. The E2E suite passes.
10. All four role logins work.

The script prints a pass/fail table. Run it before every demonstration.

---

## 38. PHASE-BY-PHASE IMPLEMENTATION PLAN

Mapped to PRD §24, with the concrete deliverables and exit criteria an implementing developer or coding agent needs. **Each phase must exit green before the next begins.**

### Phase 0 — Architecture & Data Strategy ✅ *(this document)*
Deliverables: codebase audit (§2), architecture (§4–§7), database design (§8–§9), API contracts (§11–§12), AI strategy (§15–§16), GIS strategy (§19), MVP scope. No implementation.
**Exit:** this TRD reviewed, and the blocking decisions in §40 triaged.

### Phase 1 — Backend foundation + database
Build: repository scaffold (§6.1); Docker Compose with PostGIS; Alembic; all models and migrations (§8); `users`, `farmers`, `fields`, crop catalogue; JWT auth and RBAC (§13); the response/error envelope (§11); image upload and storage (§14); observation create/read **without** enrichment; reference-data seeder; health endpoints; the API and integration test harness.
**Exit:** a farmer can register, log in, create a field, and create an observation with an image; the observation is stored with valid geometry and provenance; RBAC tests pass for every implemented endpoint.

### Phase 2 — AI detection
Build: `ModelRunner` interface and `StubRunner`; `ai_model_registry`; image validation and preprocessing; `InferenceService`; `ai_predictions` persistence; the confidence gate; `AI_DEGRADED` handling; `/ai/*` endpoints; the real model runner once weights exist.
**Exit:** an uploaded image produces a stored prediction with confidence and model version; low confidence routes to `PENDING_REVIEW`; every AI failure path degrades correctly; thresholds derived from an actual evaluation run (§15.5).

### Phase 3 — Weather + risk
Build: `WeatherProvider` interface, `FixtureWeatherProvider`, the real provider once decided; the weather cache and the four-tier degradation; `ContextEngine`; `RuleBasedRiskEngine` with the YAML ruleset; `risk_assessments`; `/weather/*` and `/risk/*`.
**Exit:** an observation yields a risk score with a complete, auditable factor breakdown; the weather-failure test passes with no invented data; `GET /risk/ruleset` returns the active configuration.

### Phase 4 — GIS + hotspots
Build: the admin-region loader; all spatial queries (§9.4); the guardrails (§9.5); `/gis/*`; `HotspotEngine` and the worker job; `hotspots` and `priority_zones`; the GeoJSON serialiser with mandatory provenance.
**Exit:** every filter combination in the §34.3 GIS test returns exactly the expected set; hotspots separate confirmed from predicted; an unbounded query is refused; `EXPLAIN` plans checked into `docs/perf/`.

### Phase 5 — Expert validation
Build: the review queue with priority; claim/release with optimistic locking and TTL expiry; confirm/correct/reject/refer; lab result recording; audit trail; status transitions with advisory invalidation.
**Exit:** the concurrent-claim test passes; a correction updates status, agent, advisory and audit trail; no path auto-promotes a prediction to a confirmation.

### Phase 6 — Advisory + multilingual
Build: `advisory_templates`; the selection algorithm; confidence-aware framing; the IPM section ordering; regeneration and supersession; backend locale files; `react-i18next` with `en`/`hi`/`mr`; the i18n CI checks.
**Exit:** the same observation returns a structurally identical advisory in all three languages; a low-confidence case yields no agent-specific treatment guidance; no user-facing literal string remains in the frontend.

### Phase 7 — Follow-up
Build: `followups`; scheduling by risk level; the due-scan worker; submission creating a child observation; comparison metadata with the causal caveat; outcome recording; chain retrieval.
**Exit:** the full follow-up workflow test passes, including the `MISSED` path and a chain of depth ≥ 2.

### Phase 8 — Dashboards
Build: the farmer, expert and official dashboard services; trend, distribution and coverage endpoints; the confirmed/predicted separation; the demo-inclusion flags; indexed aggregation queries.
**Exit:** no KPI merges confirmed with predicted; `include_demo` behaves correctly in both directions; every dashboard query is index-backed.

### Phase 9 — Frontend integration
Build: the full SPA — all four role UIs, the capture wizard, map components, provenance components, dashboards, advisory rendering, follow-up submission, loading/empty/error/degraded states, generated API types.
**Exit:** every backend capability is reachable from the UI; every observation-bearing surface renders a provenance badge; degraded states render correctly when the backend degrades.

### Phase 10 — Testing + deployment
Build: complete the test pyramid; the Playwright E2E flow; the security test matrix; the §31.8 benchmark run; CI pipeline; the demo deployment; a tested backup restore; `predemo_check.py`.
**Exit:** CI green; E2E passing; every **TO BE BENCHMARKED** entry replaced with a measured number and its hardware; the pre-demo checklist passes end to end.

### Phase 11 — SIH demo preparation
Build: the demo dataset with provenance; the rehearsed demo script; architecture explanation materials; the SIH requirement-mapping table; a documented limitations list; prepared answers to likely judge questions; the future roadmap.
**Exit:** the demo runs end to end, from a clean environment, in under the allotted time, twice in a row.

---

## 39. SIH REQUIREMENT TRACEABILITY

| SIH26131 need | PRD reference | TRD implementation | Phase |
|---|---|---|---|
| Early detection of crop disease | §3.1, §6.2 | AI inference pipeline (§15), observation flow (§4.3) | 2 |
| Early detection of pest infestation | §6.2, §22 | Catalogue `kind=PEST` (§8.3), pest traps (§24) | 2, 7 |
| Management guidance | §6.8, §13 | Advisory engine, IPM-ordered (§21) | 6 |
| Contextual risk | §6.5, §12 | Context engine + rule-based risk engine (§18) | 3 |
| Weather integration | §6.4 | Provider abstraction with degradation (§17) | 3 |
| Geographic intelligence | §6.6, §10 | PostGIS design (§9), hotspot engine (§19) | 4 |
| Expert validation | §6.7 | Review workflow and state machine (§20) | 5 |
| Official surveillance | §6.10 | Dashboards with confirmed/predicted separation (§12.17, §25) | 8 |
| Multilingual access | §14 | i18n architecture, en/hi/mr (§22) | 6 |
| Follow-up monitoring | §6.9 | Follow-up system with outcomes (§23) | 7 |
| Data trustworthiness | §8, §27 | Provenance enforced at DB, service, serialiser and UI (§10) | 1 onward |
| Reduced inappropriate pesticide use | §2, §13 | IPM-first advisories; no pesticide prescriptions (§21.5) | 6 |
| Model improvement over time | §3.9, §27.10 | Confirmed-observation feedback loop with a quality gate (§16.4) | 10+ |

---

## 40. OPEN DECISIONS REGISTER

Every `REQUIRES DECISION` in this document, with its blocking phase. **These are the questions a developer cannot answer alone.**

| # | Decision | Section | Blocks | Severity |
|---|---|---|---|---|
| D1 | Does a FloraSentry V1 codebase exist, and what is reused? | §2.4 | Phase 1 | **High** |
| D2 | The supported crop list for the MVP | §8.3 | Phase 1 (seed data), Phase 2 | **High** |
| D3 | The AI class list and the training dataset (with licence) | §16.1 | Phase 2 | **High** |
| D4 | Confidence threshold values, from a real evaluation run | §15.5 | Phase 2 | **High** |
| D5 | The weather provider (variables, limits, historical support, terms, cost) | §17.1 | Phase 3 | **High** |
| D6 | Risk factor weights and thresholds, with an agronomic source | §18.3 | Phase 3 | **High** |
| D7 | The administrative-boundary dataset (source, licence, version) | §8.3 | Phase 4 | **High** |
| D8 | Hotspot clustering parameters (`eps`, `min_points`) | §19.2 | Phase 4 | Medium |
| D9 | The advisory content source/authority | §8.3, §21 | Phase 6 | **High** |
| D10 | Who authors and reviews the Hindi and Marathi content | §22.5 | Phase 6 | Medium |
| D11 | Refresh-token transport: cookie or localStorage | §13.4 | Phase 1 | Medium |
| D12 | OTP login and an SMS gateway — in or out of scope | §13.2 | Phase 1 | Medium |
| D13 | Notification channels beyond in-app | §5.18 | Phase 8 | Low |
| D14 | Data-retention periods per category | §30.5 | Phase 10 | Medium |
| D15 | Account-deletion policy: anonymise or delete | §30.6 | Phase 10 | Medium |
| D16 | The map tile provider and its attribution terms | §28.1 | Phase 9 | Medium |
| D17 | Production object storage and region | §14.4 | Phase 10 | Medium |
| D18 | Hosting, and the production secret store | §35.4, §29.7 | Phase 10 | Medium |
| D19 | Backup destination and retention | §32.5 | Phase 10 | Medium |
| D20 | Demo image content and its licence | §27.2 | Phase 11 | Low |
| D21 | Device authentication for sensor `API_PUSH` | §24.3 | Future | Low |
| D22 | Pest economic threshold levels, with a cited source | §24.2 | Future | Low |
| D23 | Laboratory system integration — in-app only, or external | §20.5 | Future | Low |
| D24 | The confirmed operating bounding box (`GIS_OPERATING_BBOX`) | §36.7 | Phase 4 | Low |

**Recommended immediate action:** resolve D1–D4 before Phase 1 begins, and D5–D7 and D9 before Phase 3. The rest can be settled inside their phase without stalling work.

---

## 41. GLOSSARY

| Term | Meaning in this system |
|---|---|
| **Observation** | A single field report — image, trap count, sensor reading, or manual note — with location, time, crop context and provenance. The central entity. |
| **Agent** | A diagnosable cause: a disease, pest, or disorder. Held in `disease_pest_catalog`. |
| **Prediction** | AI output. Never a diagnosis. |
| **Confirmation** | An expert's or laboratory's verified determination. |
| **Verification status** | The truth state of an observation (PREDICTED → CONFIRMED, etc.). |
| **Review state** | The workflow state of an expert review (QUEUED → DECIDED, etc.). Distinct from verification status. |
| **Provenance** | Where a record came from, who made it, who verified it, and under which model/ruleset version. |
| **Source type** | The provenance category: FIELD_OBSERVATION, PUBLIC_DATA, GOVERNMENT_DATA, EXPERT_VALIDATION, DEMO_SIMULATION. |
| **Hotspot** | A spatio-temporal cluster of observations, typed CONFIRMED / PREDICTED / SIGNAL. Decision support, not validated outbreak detection. |
| **Risk zone** | An area of elevated modelled risk, whether or not cases are reported there. |
| **Priority zone** | A ranked area for intervention, combining cases, risk, backlog and surveillance gaps. |
| **Signal** | Indirect evidence (trap counts, sensors, risk) without a diagnosed case. |
| **Degraded mode** | The system running with a component unavailable, saying so plainly rather than hiding it. |
| **Ruleset version** | The identifier of the risk configuration used to compute a given score, stored on every assessment. |
| **Field-validation dataset** | Real platform images with expert-confirmed labels, used to measure real-world performance — distinct from any controlled public dataset. |

---

## 42. DOCUMENT CLOSING NOTES

This TRD is a specification, not a claim of implementation. As of this version:

- **No code has been written.** The project directory contains the PRD and this document.
- **No model exists**, so no accuracy is stated anywhere in this document.
- **No weather provider, boundary dataset, training dataset, or advisory source has been selected**, so none is named.
- **No performance number has been measured**, so every performance figure is labelled as either a target or **TO BE BENCHMARKED**.
- **Twenty-four decisions remain open** and are registered in §40 with their blocking phases.

Everything above is either derived from the PRD, derived from the codebase audit, or explicitly labelled as a technical recommendation or an open decision. That separation is itself a requirement of this project: FloraSentry V2's central product claim is that it distinguishes what is known from what is predicted from what is simulated — and its own technical documentation is held to the same standard.
