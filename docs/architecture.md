# CalmWay Architecture

## System overview

CalmWay is a React single-page application backed by FastAPI and
PostgreSQL/PostGIS. Mapbox supplies place search, basemaps, and walking route
geometry. City of Melbourne pedestrian sensor datasets supply the crowd proxy.
CalmWay combines those sources; it does not ask Mapbox to calculate crowd
conditions and does not expose the backend Mapbox token to the browser.

```text
Browser
  React + TypeScript + React Router
  Mapbox Search Box API + Mapbox GL JS (public token)
       |
       | POST /api/v1/routes/options
       v
Vercel backend
  FastAPI + Pydantic
  multi-route generation and validation
  route sampling and pedestrian-flow evaluation
  route role selection
       |                         |
       | Mapbox Directions v5    | SQLAlchemy + psycopg
       v                         v
  Mapbox walking API       PostgreSQL/PostGIS (Neon in production)
                                  ^
                                  |
                         City of Melbourne ingestion
                         and scheduled current refresh
```

## Frontend

The frontend is under `frontend/` and uses React 18, React Router, Vite,
TypeScript, Mapbox GL JS, and browser `fetch`.

The active page flow is:

```text
Home -> Route Search -> Navigation (route selection overlay) -> Active Navigation -> Arrival -> Home
```

- `LocationSearchField` calls Mapbox Search Box `/suggest` and `/retrieve`
  directly with a public token, an English/Australia filter, Melbourne CBD
  proximity, and one search session token.
- The browser Geolocation API can provide a one-shot origin. The location is
  held only in React state and is not continuous tracking.
- `JourneyContext` stores the selected structured locations, returned route
  options, and exact confirmed route in memory. A missing confirmed route puts
  Navigation into route-selection mode. State is not persisted across a full
  browser refresh.
- `RouteMap` draws only backend-returned GeoJSON. Navigation selection mode
  draws all returned options and emphasises the focused candidate; Active
  Navigation draws only the confirmed route.
- The active API client calls `POST /api/v1/routes/options`. It never calls
  Mapbox Directions from the browser.

Compatibility frontend code for the older preference-aware walking response
remains in `frontend/src/services/api.ts`, `frontend/src/components/crowd/`,
and `frontend/src/utils/findLowerStimulationAlternative.ts`. It is not wired to
the active route pages.

## Backend API

The FastAPI application is exported from `backend/app/main.py`; Vercel imports
the same app through `backend/index.py`.

| Endpoint | Purpose | Current consumer |
| --- | --- | --- |
| `GET /health` | Process liveness without requiring database or Mapbox startup | Operations and smoke tests |
| `GET /docs` | Generated OpenAPI/Swagger UI | Developers |
| `GET /api/v1/crowd/point` | Read-only point crowd exposure from PostGIS | Diagnostic/API use |
| `POST /api/v1/routes/options` | One to three user-facing walking options with roles and pedestrian movements/min | Active React journey |
| `POST /api/v1/routes/walking` | Preference-aware P75 crowd ranking plus initial crowd-alert DTO | Implemented compatibility API; not called by active React pages |
| `POST /api/v1/internal/refresh-current-activity` | Bearer-authenticated current-activity refresh | Scheduled GitHub Actions workflow |

Services are constructed lazily so `/health` remains available when Mapbox or
database configuration is absent. Expected external failures are converted to
sanitised HTTP errors.

## Active route generation and role selection

`POST /api/v1/routes/options` follows this pipeline:

1. The backend calls Mapbox Directions with the `mapbox/walking` profile,
   full GeoJSON overview, steps, English instructions, and alternatives.
2. It normalises valid routes and rejects malformed distance, duration, or
   geometry data.
3. Candidate generation removes routes that are effectively the same corridor
   using symmetric 50 m route sampling, a 35 m spatial match tolerance, and an
   inclusive 85% match in both directions.
4. If needed and within a bounded request budget, lower-flow sensor waypoints
   may be used to request a meaningful alternative. The pipeline returns at
   most three routes.
5. Every retained route is sampled at 50 m plus exact endpoints. All samples
   across all routes are evaluated in a batched PostGIS flow query.
6. Live 15-minute movements/min and historical typical movements/min are
   aggregated independently into median, continuous P75, maximum, and coverage.
7. The selector uses a common evidence basis: live only when every candidate
   qualifies at 55% coverage, otherwise historical when every candidate
   qualifies, otherwise `UNKNOWN`.
8. It assigns `FASTEST`, and where evidence/candidate count permits,
   `CALMEST` and `BALANCED`. It also returns relative `LOWEST`, `MIDDLE`,
   `HIGHEST`, or `UNKNOWN` activity for accessible text and semantic colour.

The detailed decision order is in [Route Ranking](route-ranking.md).

## Preference-aware crowd evaluation

The separate `/api/v1/routes/walking` pipeline uses the same normalised Mapbox
geometry but evaluates each 50 m sample with `SpatialCrowdService`:

```text
route geometry
  -> cumulative-distance sampling
  -> point crowd exposure from current PostGIS materialisation
  -> route coverage gate
  -> continuous P75 aggregation
  -> preference comparison
  -> deterministic backend ranking
  -> one initial route-ahead alert decision at progress 0 m
```

The point engine discovers active outdoor sensors within 300 m. A nearest
usable sensor within 250 m is `SUPPORTED`; one over 250 m and at most 300 m is
`LIMITED`; otherwise the result is `NO_DATA`. Usable sensor percentiles are
combined with normalised inverse-distance weights
`1 / max(distance, 1 m)`. Network percentile is the crowd-exposure metric;
local historical percentile remains a separate local-condition signal.

## Data pipeline and storage

The authoritative database schema is
`handoff/epic1_backend_handoff_v3/05_DATABASE_SCHEMA.sql`. It enables PostGIS
and defines current sensor metadata, spatial locations, hourly observations,
raw minute observations, conflict views, historical baselines, current sensor
activity, and supporting spatial tables.

The data flow is:

```text
City sensor-location dataset
  -> sensor + sensor_location_current

City monthly hourly counts
  -> pedestrian_hourly_count
  -> sensor and network hour/day-type baselines

City past-hour minute counts
  -> raw minute observations and conflict handling
  -> previous complete 15-minute current window
  -> current_sensor_activity
  -> spatial point and route evaluation
```

The current refresh uses complete quarter-hour windows, preserves explicit
zero, distinguishes missing/stale/conflicted states, and never converts missing
data to a quiet score. The workflow in
`.github/workflows/refresh-current-activity.yml` calls the authenticated refresh
endpoint four times per hour at minutes 7, 22, 37, and 52 in the Melbourne
timezone.

The tracked `data/raw/` and `data/processed/` directories are staging areas for
controlled local work, not the production database. Runtime services use
PostgreSQL/PostGIS.

## Deployment architecture

- `calmway-frontend` is a Vercel Vite project rooted at `frontend/`.
  `frontend/vercel.json` rewrites SPA routes to `index.html`.
- `calmway-backend` is a Vercel FastAPI project rooted at `backend/`.
- Production persistence is a PostgreSQL/PostGIS database; the deployment guide
  documents Neon pooled runtime connections and direct administrative
  connections.
- Mapbox Search and GL use a browser-public token. Mapbox Directions uses a
  separate backend token.
- GitHub Actions stores only the scheduler secret reference and sends it as a
  Bearer credential to the backend refresh endpoint.

See [Deployment Guide](deployment-guide.md) for environment variables and
operational checks.

## Security and state boundaries

- Actual `.env`, `.env.local`, `.vercel`, database URLs, and tokens are ignored.
- Every `VITE_` value is public at build time; server secrets must never use
  that prefix.
- The internal refresh endpoint fails closed when `REFRESH_SECRET` is absent,
  compares credentials in constant time, and does not return internal errors.
- HTTP request paths do not write persistent local files or run ingestion at
  startup.
- Journey state and geolocation are in-memory browser state only.
