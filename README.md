# CalmWay

CalmWay is a responsive walking-route web application for sensory-sensitive
commuters in Melbourne CBD. The project has completed **Epic 1 Phase 5B-2**. The
frontend can use a one-shot browser geolocation or search for a real Mapbox
starting point, request real walking candidates from the FastAPI backend,
preview each returned LineString on Mapbox GL JS, and reuse the selected route
on the static Navigation screen. The backend measures
and uniformly samples those LineStrings at the configured interval, evaluates
each sample with the Phase 2D crowd point engine, then applies the project-
approved coverage, P75, preference, and deterministic ranking policy.
The same per-route evaluation now also produces an initial route-ahead decision
at 0 m, which Navigation presents without claiming live GPS progress. An alert
may offer a strictly eligible route already present in the original response.

## Current Epic 1 flow

```text
Future Home
  -> Route Search
  -> Route Options
  -> Active Navigation
  -> optional Crowd Alert state
  -> Arrival
  -> configurable Home route
```

Frontend routes:

- `/routes/search`
- `/routes/options`
- `/navigation`
- `/arrival`

The root route temporarily redirects to Route Search. The Home page belongs to
another team member; `VITE_HOME_ROUTE` is the integration boundary and no Home
page is implemented here.

## Implemented through Phase 5B-2

- React Router page structure and a small Journey Context;
- responsive desktop/mobile UI for the complete Epic 1 flow;
- Mapbox Search Box place/POI selection with structured coordinates;
- one-shot browser geolocation as an honest, in-memory structured route origin;
- single-select LOW/MEDIUM/HIGH crowd preference UI;
- real Mapbox Directions walking candidates through `POST /api/v1/routes/walking`;
- route cards supporting the actual returned candidate count;
- real basemaps, full GeoJSON route lines, endpoint markers, and fitted bounds on
  Route Options and Navigation;
- pure, deterministic cumulative-distance route sampling at the configured
  interval, without Mapbox, crowd, database, or frontend coupling;
- ordered sample-level crowd evaluation by composing the route sampler directly
  with the authoritative PostGIS spatial point service;
- 55% configurable route coverage gating, continuous-interpolation P75 route
  scoring, soft tolerance comparison, and deterministic backend ranking;
- honest insufficient-data route cards and backend-owned CalmWay recommendation;
- a pure, deterministic ahead-of-route `ALERT` / `CLEAR` /
  `INSUFFICIENT_DATA` decision engine with explicit partial-data diagnostics;
- initial Navigation alert, clear, and unavailable states using the backend
  decision at exactly 0 m route progress;
- route-specific in-memory alert acknowledgement and strict switching to the
  first eligible, real lower-P75 alternative in existing backend order;
- PostgreSQL/PostGIS ingestion, baselines, current activity, and point-level
  crowd evaluation from Phases 2A–2D.

## Not implemented yet

The application still does **not** perform:

- continuous GPS navigation, periodic crowd re-evaluation, or rerouting;
- live progress-driven crowd re-evaluation;
- deployment.

The Navigation screen is explicitly a static route overview and does not claim
live user position or route progress.

## Crowd algorithm source of truth

The authoritative backend/data package is
`handoff/epic1_backend_handoff_v3/`. Phase 1 does not reimplement or simplify
its algorithm. The frozen contract includes:

- primary Crowd Exposure: current complete 15-minute **Network percentile**;
- Local Historical Percentile as a separate Local Condition (never `MAX`);
- backend bands at 25/50/75/90 across five internal levels;
- `SUPPORTED <=250 m`, `LIMITED >250–300 m`, otherwise `NO_DATA`;
- normalised inverse-distance weighting `1 / max(distance, 1 m)`;
- 50 m configurable route sampling and P75 route summary;
- project-approved MVP route evaluation at 55% numeric coverage;
- route ranking by No Data %, preference exceedance %, P75 exposure, maximum
  exposure, duration, then Mapbox route index.

`NO_DATA` and `AMBIGUOUS_NO_RECORD` must never be converted to LOW or zero.
These are relative pedestrian-activity estimates, not persons/m², medical, or
safety thresholds.

See [the Simplified Chinese implementation plan](docs/final-epic1-implementation-plan-cn.md)
for the complete phase plan and scope decisions.

## Technology

- Frontend: React 18, React Router, Vite, TypeScript
- Backend: Python 3.12, FastAPI, Pydantic
- Final data architecture: PostgreSQL + PostGIS
- Map/search/routing provider: Mapbox GL JS, Search Box API, and Directions API
  with `mapbox/walking`
- Tests: pytest and FastAPI TestClient

Database access uses SQLAlchemy 2.x with psycopg 3. See the
[Simplified Chinese database development guide](docs/database-development-cn.md)
for safe Docker lifecycle, configuration, and verification commands. The
[sensor-location ingestion guide](docs/sensor-location-ingestion-cn.md) documents
the live source mapping, dry run, transactional import, and spatial checks.
The [hourly-count ingestion guide](docs/hourly-count-ingestion-cn.md) documents
the frozen training-window import, zero-count semantics, unknown IDs, and
idempotency. The [historical baseline guide](docs/historical-baselines-cn.md)
documents model eligibility, relocation rules, exact statistics, the baseline
builder, and database verification.
The [current activity guide](docs/current-activity-cn.md) documents the bounded
minute source, missing/conflict semantics, exact windows, dual percentiles,
manual refresh, and SQL verification.
The [spatial point engine guide](docs/spatial-crowd-engine-cn.md) documents
PostGIS neighbour discovery, the adopted 250/300 m support rule, normalised
inverse-distance weighting, point uncertainty, and manual verification.
The [Mapbox place-search guide](docs/mapbox-search-phase3a-cn.md),
[walking-directions guide](docs/mapbox-directions-phase3b-cn.md), and
[route-visualisation guide](docs/mapbox-route-visualization-phase3c-cn.md)
document the active Phase 3 frontend/backend route flow. The [uniform route
sampling guide](docs/route-sampling-phase3d-cn.md) documents Phase 3D geometry
measurement, interpolation, endpoint rules, and offline verification. The
[route sample crowd evaluation guide](docs/route-sample-crowd-evaluation-phase3e-cn.md)
documents Phase 3E service composition, coverage/null propagation, controlled
PostGIS testing, and real current-state verification. The [Phase 4 route-ranking
decision record](docs/phase4-route-ranking-decisions.md) documents coverage,
continuous P75, tolerance, deterministic tie-breaks, insufficient-data behavior,
backend recommendation ownership, and reproduction commands.
The [Phase 5A geolocation-origin guide](docs/geolocation-origin-phase5a-cn.md)
documents the one-shot permission flow, source model, privacy boundary, HTTPS
requirement, and real/simulated browser checks.
The [Phase 5B-1 decision record](docs/phase5b-crowd-alert-decisions.md) and
[Simplified Chinese implementation guide](docs/route-crowd-alert-phase5b1-cn.md)
document the provisional 300 m/two-consecutive-sample heuristic, decision
semantics, diagnostics, and static-navigation boundary.
The [Phase 5B-2 Navigation decision record](docs/phase5b2-navigation-alert-decisions.md)
and [Simplified Chinese Navigation guide](docs/navigation-crowd-alert-phase5b2-cn.md)
document initial progress, the three UI states, acknowledgement, and the strict
existing-alternative switch rule.

Use Node.js 20 or newer for the frontend and Python 3.12 (or another compatible
modern Python 3 release) for the backend.

## Local setup

Create local environment files from `.env.example` as needed. Keep all actual
`.env` files untracked and never place a server token in a `VITE_` variable.

Backend, from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.app.main:app --reload
```

Frontend, in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Local URLs:

- frontend: `http://localhost:5173`
- backend: `http://localhost:8000`
- health check: `GET http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`

## Verification

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe .\scripts\check_database.py
.\.venv\Scripts\python.exe .\scripts\import_sensor_locations.py --dry-run
.\.venv\Scripts\python.exe .\scripts\import_hourly_counts.py --dry-run --start-date 2024-08-10 --end-date 2026-02-07
.\.venv\Scripts\python.exe .\scripts\build_historical_baselines.py --dry-run
.\.venv\Scripts\python.exe .\scripts\build_historical_baselines.py
.\.venv\Scripts\python.exe .\scripts\refresh_current_activity.py --dry-run
.\.venv\Scripts\python.exe .\scripts\refresh_current_activity.py
.\.venv\Scripts\python.exe .\scripts\evaluate_crowd_point.py --longitude 144.96 --latitude -37.81
.\.venv\Scripts\python.exe .\scripts\evaluate_route_crowd_alert.py
cd frontend
npm run build
```

Later-phase tests for real route evaluation, GPS progress, and crowd-triggered
rerouting are intentionally deferred until those features exist.
