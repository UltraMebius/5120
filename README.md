# CalmWay

CalmWay is a responsive walking-route web application for sensory-sensitive
commuters in Melbourne CBD. The project has completed **Epic 1 Phase 2B**:
the Phase 1 page flow and contracts remain in place, and the FastAPI backend can
verify PostgreSQL/PostGIS, import current sensor locations and the frozen hourly
training window, and transactionally build Local and Network historical
baselines. Realtime ingestion and current crowd features remain placeholders.

## Phase 1 flow

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

## Implemented in Phase 1

- React Router page structure and a small Journey Context;
- responsive desktop/mobile UI for the complete Epic 1 flow;
- manual origin/destination fields and one-time browser current-location input;
- single-select LOW/MEDIUM/HIGH crowd preference UI;
- route options supporting any returned candidate count;
- active-navigation, alert, alternative, and arrival preview states;
- FastAPI domain enums, response schemas, service boundaries, and environment
  configuration;
- presentation-only mapping from five backend crowd levels to three UI levels;
- two clearly labelled mock routes through the legacy `GET /api/routes`
  compatibility endpoint.

## Not implemented yet

Phase 1 does **not** perform:

- City minute-count ingestion or current crowd calculation;
- current 15-minute Network Crowd Exposure scoring;
- City data writes, PostGIS spatial scoring, or business-data queries;
- Mapbox geocoding, maps, or Directions requests;
- real candidate-route evaluation and CalmWay ranking;
- continuous GPS navigation, periodic crowd re-evaluation, or rerouting;
- deployment.

The UI preview does not claim live data. Mapbox packages are deferred until
their first real use; only configuration and service boundaries exist now.

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
- route ranking by No Data %, preference exceedance %, P75 exposure, maximum
  exposure, then duration.

`NO_DATA` and `AMBIGUOUS_NO_RECORD` must never be converted to LOW or zero.
These are relative pedestrian-activity estimates, not persons/m², medical, or
safety thresholds.

See [the Simplified Chinese implementation plan](docs/final-epic1-implementation-plan-cn.md)
for the complete phase plan and scope decisions.

## Technology

- Frontend: React 18, React Router, Vite, TypeScript
- Backend: Python 3.12, FastAPI, Pydantic
- Final data architecture: PostgreSQL + PostGIS
- Final map/search/routing provider: Mapbox GL JS, Geocoding API v6, Directions
  API with `mapbox/walking`
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
cd frontend
npm run build
```

Later-phase tests for minute ingestion, current crowd scoring, PostGIS route
support, real route evaluation, GPS progress, and crowd-triggered rerouting are
intentionally deferred until those features exist.
