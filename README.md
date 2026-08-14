# CalmWay

## Overview

CalmWay is a responsive walking-route application for Melbourne. It helps
people compare route distance, duration, and pedestrian activity before
choosing a route. The sensory-aware product goal is broader than the current
measurement: pedestrian crowd exposure is the only sensory proxy currently
implemented.

The active React journey searches real Mapbox places, accepts an optional
one-shot current location, requests one to three backend-generated walking
options, draws their exact backend geometry, and preserves the selected route
through static route guidance and arrival.

## Problem Statement

The fastest pedestrian route is not always the most comfortable route for a
person who is sensitive to crowded environments. Conventional route planners
usually optimise time and distance without explaining pedestrian activity.
CalmWay combines walking geometry with City of Melbourne pedestrian sensor
evidence so users can compare a calmer, faster, or balanced option where the
available data supports that distinction.

## Target Users

- sensory-sensitive commuters and visitors;
- people who prefer to avoid heavily used pedestrian corridors;
- anyone who wants pedestrian activity context alongside time and distance.

CalmWay is an informational university MVP. It is not a medical device,
accessibility guarantee, personal-safety service, or comprehensive measure of
sensory conditions.

## UN SDG Alignment

CalmWay supports the intent of UN Sustainable Development Goal 11,
**Sustainable Cities and Communities**, by exploring more inclusive pedestrian
mobility and access to urban space. It also has a secondary relationship to
SDG 3, **Good Health and Well-being**, through informed route choice. These are
design alignments, not evidence that the MVP has measured population-level SDG
impact.

## Current Scope

The active frontend flow is:

```text
Home -> Route Search -> Navigation (route selection overlay) -> Active Navigation -> Arrival -> Home
```

The active frontend calls `POST /api/v1/routes/options`. It presents up to three
real route candidates with backend-assigned `CALMEST`, `FASTEST`, and
`BALANCED` roles, typical pedestrian movements per minute, evidence source,
relative pedestrian activity, duration, distance, and route geometry.

The repository also retains `POST /api/v1/routes/walking`, a tested backend API
that performs Low/Medium/High preference-aware Crowd Exposure ranking and
returns one initial route-ahead alert decision. The active React pages no
longer call that endpoint and do not currently render a preference selector or
alert panel. This backend-only boundary is documented rather than presented as
an end-to-end feature.

## User Stories

### User Story 1.1

As a sensory-sensitive commuter, I want to compare crowd-exposure information
for different routes, so that I can choose the route that best matches my
comfort level.

Current status: route comparison and explicit route selection are implemented
end to end. The active UI displays pedestrian movements per minute; the
preference-aware API exposes percentile-based Crowd Exposure separately.

### User Story 1.2

As a sensory-sensitive commuter, I want routes with lower crowd exposure to be
prioritised, so that I can reduce exposure to highly congested pedestrian
areas.

Current status: the deterministic preference-aware ranking and recommendation
are implemented and tested in `/api/v1/routes/walking`, but are not the active
frontend route contract.

### User Story 1.3

As a sensory-sensitive commuter, I want to receive an alert when crowd exposure
on the route ahead exceeds my preferred threshold, so that I can make a more
informed decision before continuing my journey.

Current status: the backend initial alert engine is implemented and tested at
explicit progress `0 m`; alert presentation is not wired into the active React
Navigation page. See [Acceptance Criteria](docs/acceptance-criteria.md) for the
criterion-by-criterion status.

## Key Features

- Mapbox place/POI suggestions and structured location retrieval;
- one-shot browser geolocation for the origin, with permission/error handling;
- backend-only Mapbox walking Directions requests with full GeoJSON and steps;
- bounded generation of one to three meaningful route candidates;
- 50 m cumulative-distance route sampling plus exact endpoints;
- batched PostgreSQL/PostGIS pedestrian-flow evaluation;
- recent 15-minute sensor estimates with historical typical-flow fallback;
- deterministic `CALMEST`, `FASTEST`, and `BALANCED` role assignment;
- honest unavailable states when candidates lack a common evidence basis;
- map fitting for all candidates in Navigation selection mode and selected-only Active Navigation geometry;
- exact selected-route reuse without a route-options refetch;
- backend-provided static route guidance and one-screen arrival/reset flow;
- separate tested P75 preference ranking and initial alert backend contract;
- authenticated scheduled current-activity refresh.

## System Architecture

```text
React + Vite + TypeScript
  |-- Mapbox Search Box and Mapbox GL JS (public browser token)
  |-- POST /api/v1/routes/options
  v
FastAPI
  |-- Mapbox Directions (secret backend token)
  |-- route candidate generation and distinctness
  |-- route sampling and pedestrian-flow evaluation
  |-- route role selection
  v
PostgreSQL/PostGIS
  ^
  |-- City sensor locations
  |-- historical hourly counts and baselines
  |-- current minute observations and materialised activity
```

The frontend never calls Mapbox Directions. Backend route geometry is the
single geometry source used by the maps. For service boundaries, both route
contracts, storage, and deployment topology, see
[Architecture](docs/architecture.md).

## Technology Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 18, React Router, TypeScript, Vite, Mapbox GL JS |
| Backend | Python 3.12, FastAPI, Pydantic, httpx |
| Database | PostgreSQL, PostGIS, SQLAlchemy 2, psycopg 3 |
| External APIs | Mapbox Search Box, Mapbox Directions v5, City of Melbourne Explore API v2.1 |
| Testing | pytest, Vitest, Testing Library, jsdom |
| Deployment | Vercel frontend/backend, Neon PostgreSQL/PostGIS, GitHub Actions refresh |

## Data Sources

The configured City of Melbourne datasets are:

| Purpose | Dataset ID |
| --- | --- |
| Sensor locations | `pedestrian-counting-system-sensor-locations` |
| Past-hour minute counts | `pedestrian-counting-system-past-hour-counts-per-minute` |
| Historical hourly counts | `pedestrian-counting-system-monthly-counts-per-hour` |

Historical hourly data builds hour/day-type sensor and network baselines. The
minute source builds a complete recent 15-minute materialisation. Data states
distinguish valid observations, ambiguous absence, stale source data,
conflicts, and no data. Explicit zero remains a real zero; missing data remains
null.

Mapbox supplies search results, walkable routes, distance, duration, full
geometry, and maneuver instructions. It does not supply CalmWay pedestrian
activity.

The production source of record is PostgreSQL/PostGIS. `data/raw/` and
`data/processed/` are empty tracked staging directories for controlled local
work; no production dataset is bundled in Git.

## Crowd Evaluation

### Active pedestrian-flow comparison

Each route is sampled at the configured 50 m interval. Nearby active outdoor
sensors contribute separately to recent and historical movements/min estimates
using normalised inverse-distance weighting. Route-level median, continuous
P75, maximum, and coverage are calculated for each source.

The active route selector uses recent evidence only when every candidate has at
least 55% coverage and a numeric recent median, which is the typical
movements/min value shown in the UI. Otherwise it uses historical evidence when
every candidate qualifies. If neither common basis exists, crowd comparison is
unavailable rather than mixed or fabricated.

### Preference-aware Crowd Exposure

The separate `/api/v1/routes/walking` path evaluates a 0-100 current network
percentile at every sample. A nearest usable sensor within 250 m is
`SUPPORTED`; one over 250 m and at most 300 m is `LIMITED`; otherwise it is
`NO_DATA`. Only numeric supported/limited samples participate in route
aggregation.

Network Crowd Exposure and local historical condition remain separate. The
scores are relative pedestrian-activity indicators, not persons per square
metre, clinical tolerance, or a guarantee that every point has the displayed
number of people.

## Route Ranking

The active route-options contract assigns semantic characteristics to the
original route IDs:

- `CALMEST` to the lowest common-source median shown as typical movements/min,
  then P75, maximum, duration, distance, source index, and route ID ties;
- `FASTEST` to the global minimum exact duration, then distance, source index,
  and route ID ties;
- `BALANCED` to the best remaining route, after excluding the `CALMEST` and
  `FASTEST` route IDs, using an equal-weight normalised duration and displayed
  median-flow score.

`CALMEST` and `FASTEST` are absolute properties and may belong to the same
route. `BALANCED` remains a distinct practical trade-off whenever another
eligible route exists. Every route still appears once with its original
geometry and navigation data. With an unknown comparison basis, only overall
`FASTEST` is assigned.

The preference-aware walking contract applies a 55% numeric coverage gate,
then orders evaluable routes by No Data percentage, percentage above the
selected preference, P75 Crowd Exposure, maximum exposure, duration, and
Mapbox route index. Above-preference routes remain visible. If every route is
insufficient, no recommendation is fabricated.

See [Route Ranking](docs/route-ranking.md) for exact formulas, thresholds,
tie-breaking, and No Data handling.

## Navigation Crowd Alerts

The backend alert engine evaluates the route section
`(current progress, current progress + 300 m]` using the preference thresholds
50/75/90. An alert requires at least two consecutive usable samples strictly
above the threshold. Usable evidence without that streak is `CLEAR`; no usable
evidence is `INSUFFICIENT_DATA`.

The API currently evaluates once at explicit progress `0 m`. It does not claim
GPS-derived progress. The active Navigation page does not render this alert
contract. See [Navigation Alerts](docs/navigation-alerts.md) for exact behavior
and limitations.

## Project Structure

```text
.
|-- .github/workflows/       Scheduled current-activity refresh
|-- backend/
|   |-- app/api/             FastAPI endpoints
|   |-- app/db/              Engine lifecycle and database errors
|   |-- app/models/          Domain records and enums
|   |-- app/repositories/    SQL/PostGIS access
|   |-- app/schemas/         Pydantic API contracts
|   |-- app/services/        Ingestion, crowd, routing, and baselines
|   |-- index.py             Vercel FastAPI entry point
|   `-- requirements.txt
|-- data/                    Empty tracked local staging directories
|-- docs/                    Maintained English documentation
|-- frontend/
|   |-- src/components/      UI, route, crowd, and map components
|   |-- src/context/         In-memory journey state
|   |-- src/pages/           Home, Search, Navigation, Arrival
|   |-- src/services/        API, Mapbox search, geolocation
|   `-- tests/               Vitest/Testing Library tests
|-- handoff/                 Frozen backend/data contract and schema
|-- scripts/                 Explicit import, refresh, and evaluation tools
`-- tests/                   Backend unit and opt-in integration tests
```

## Environment Variables

Copy safe placeholders from `.env.example` to ignored local environment files.
Do not edit the template with real credentials.

Required for the active local end-to-end journey:

| Variable | Location | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | frontend | FastAPI base URL; defaults to `http://localhost:8000` |
| `VITE_MAPBOX_PUBLIC_TOKEN` | frontend | Browser-safe Mapbox Search/GL token |
| `DATABASE_URL` | backend | PostgreSQL/PostGIS SQLAlchemy URL |
| `MAPBOX_ACCESS_TOKEN` | backend | Secret Mapbox Directions token |
| `FRONTEND_ORIGINS` | backend | Comma-separated browser origins allowed by CORS |

Operational/optional variables include `REFRESH_SECRET`, `APP_TIMEZONE`,
`VITE_HOME_ROUTE`, route sampling/coverage settings, spatial radii/weighting,
preference thresholds, alert settings, City dataset settings, Mapbox Directions
profile/timeout, minute interval, and optional source-staleness threshold.

All `VITE_` values are public in the browser bundle. See
[Deployment Guide](docs/deployment-guide.md) for the verified complete list and
production settings.

## Local Setup

### 1. Install backend dependencies

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

### 2. Install frontend dependencies

```powershell
cd frontend
npm ci
cd ..
```

Use Node.js 20 or newer. If PowerShell blocks `npm.ps1`, run the equivalent
`npm.cmd` command.

### 3. Configure environment

Use `.env.example` as a reference. Put frontend values in `frontend/.env` and
backend values in `backend/.env`, or set process environment variables. Both
locations are ignored by Git.

### 4. Prepare PostgreSQL/PostGIS

Create a controlled PostgreSQL database, enable PostGIS, and apply:

```powershell
psql $env:DATABASE_URL -f handoff/epic1_backend_handoff_v3/05_DATABASE_SCHEMA.sql
```

On macOS/Linux:

```bash
psql "$DATABASE_URL" -f handoff/epic1_backend_handoff_v3/05_DATABASE_SCHEMA.sql
```

Then use the scripts described in `scripts/README.md` to import sensor
locations/hourly counts, build historical baselines, and refresh current
activity. Run `--dry-run` first where supported. Do not point write scripts at a
shared/production database without explicit approval.

## Running the Application

Start FastAPI from the repository root:

```powershell
python -m uvicorn backend.app.main:app --reload
```

Start Vite in another terminal:

```powershell
cd frontend
npm run dev
```

Local endpoints:

- frontend: `http://localhost:5173`;
- backend: `http://localhost:8000`;
- health: `http://localhost:8000/health`;
- Swagger/OpenAPI: `http://localhost:8000/docs`.

## Testing

Backend, from the repository root:

```powershell
python -m pytest -q
```

Frontend, from `frontend/`:

```powershell
npm test
npm run build
```

Live City, Mapbox, and PostGIS integration tests are opt-in and require
explicit environment gates. See [Testing Guide](docs/testing-guide.md) for
focused commands, all gates, API smoke requests, acceptance checks, and
deployed checks.

## Production Deployment

The two current Vercel projects are `calmway-backend` and
`calmway-frontend`. From each project root after configuring the correct Vercel
environment:

```bash
vercel link
vercel --prod
```

The frontend requires production API/public Mapbox values. The backend requires
the pooled PostgreSQL/PostGIS URL, secret Directions token, exact frontend CORS
origin, and refresh secret. The database schema and data must already exist;
deployment does not run ingestion or migrations.

See [Deployment Guide](docs/deployment-guide.md) before deploying.

## Production URLs

- Frontend: `https://calmway-frontend.vercel.app`
- Backend: `https://calmway-backend.vercel.app`
- Health: `https://calmway-backend.vercel.app/health`
- API documentation: `https://calmway-backend.vercel.app/docs`

The frontend root and backend health endpoint returned HTTP 200 when verified
on 2026-08-13. Availability can change; run the documented smoke checks for a
current deployment decision.

## API Documentation

FastAPI generates the OpenAPI schema and Swagger UI at `/docs`.

Current public/operational endpoints:

- `GET /health`;
- `GET /api/v1/crowd/point?lat=...&lon=...`;
- `POST /api/v1/routes/options` (active frontend contract);
- `POST /api/v1/routes/walking` (preference-aware compatibility contract);
- `POST /api/v1/internal/refresh-current-activity` (Bearer-authenticated
  operational write).

Use the schemas generated by the deployed backend rather than copying request
or response payloads from old phase documents.

## Known Limitations

- Pedestrian crowd exposure is only one sensory proxy.
- Sensor coverage is spatially and temporally limited.
- Recent estimates depend on complete published City source windows and may lag
  wall-clock time.
- Historical fallback is a typical hourly baseline, not live observation.
- The active frontend does not expose Low/Medium/High crowd preference.
- Preference-aware P75 ranking and initial alert decisions are backend-only in
  the current active journey.
- Navigation does not continuously track GPS, map-match, advance maneuvers,
  detect off-route movement, or periodically re-evaluate crowd conditions.
- No dynamic rerouting or automatic alternative-route switching is active.
- Journey state is in memory and is lost on full refresh.
- Roles are relative to the returned candidate set, not an absolute guarantee
  of calmness.
- The project is an MVP and has not been clinically or scientifically validated
  as a sensory-accessibility intervention.

## Repository Documentation

- [Acceptance Criteria](docs/acceptance-criteria.md)
- [Architecture](docs/architecture.md)
- [Route Ranking](docs/route-ranking.md)
- [Navigation Alerts](docs/navigation-alerts.md)
- [Testing Guide](docs/testing-guide.md)
- [Deployment Guide](docs/deployment-guide.md)
- [Team Guide](docs/team-guide.md)

The frozen backend/data handoff remains under
`handoff/epic1_backend_handoff_v3/`; maintained product and engineering guidance
is kept in the seven English documents above.
