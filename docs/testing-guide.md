# Testing Guide

## Prerequisites

- Python 3.12 or another version compatible with `backend/requirements.txt`;
- Node.js 20 or newer and npm;
- PostgreSQL with PostGIS for database-backed integration tests;
- local environment files based on `.env.example` when external services are
  required.

Never put real credentials in commands committed to the repository. Ordinary
unit tests use fakes and do not require City, Mapbox, or database access.

## Install dependencies

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
cd frontend
npm ci
cd ..
```

On macOS/Linux, activate with `source .venv/bin/activate` and use `/` in paths.
If PowerShell blocks `npm.ps1`, use `npm.cmd` for the same npm commands.

## Backend unit and mocked integration suite

From the repository root:

```powershell
python -m pytest -q
```

This is the standard backend regression command. Tests requiring a real
database, City endpoint, or Mapbox token are skipped unless their documented
prerequisites/gates are enabled. A skipped external integration is not evidence
that the external service passed.

Useful focused commands include:

```powershell
python -m pytest tests/test_route_options_api.py -q
python -m pytest tests/test_route_option_selection_service.py -q
python -m pytest tests/test_route_crowd_ranking_service.py -q
python -m pytest tests/test_route_crowd_alert_service.py -q
python -m pytest tests/test_internal_refresh_api.py -q
```

## Optional database and live integrations

Set `DATABASE_URL` to a controlled PostgreSQL/PostGIS database before running
database integration tests. Tests that write fixtures use their own rollback or
cleanup contracts; read each test before pointing it at shared data.

The repository uses these explicit gates:

| Gate | Test area | Additional requirement |
| --- | --- | --- |
| none beyond `DATABASE_URL` | database readiness | Existing authoritative schema |
| `RUN_CITY_SENSOR_INTEGRATION=1` | live City sensor locations | Network and database |
| `RUN_CITY_HOURLY_INTEGRATION=1` | bounded City hourly counts | Network and database |
| `RUN_CITY_MINUTE_INTEGRATION=1` | live City minute counts | Network and database |
| `RUN_BASELINE_INTEGRATION=1` | historical baseline rebuild | Populated controlled database |
| `RUN_CURRENT_ACTIVITY_INTEGRATION=1` | current activity | Prepared real observations |
| `RUN_SPATIAL_INTEGRATION=1` | spatial point evaluation | PostGIS data |
| `RUN_PEDESTRIAN_FLOW_INTEGRATION=1` | batched route flow | PostGIS data |
| `RUN_ROUTE_WAYPOINT_INTEGRATION=1` | waypoint discovery | PostGIS data |
| `RUN_ROUTE_CROWD_INTEGRATION=1` | route sample crowd evaluation | PostGIS data |
| `RUN_ROUTE_RANKING_INTEGRATION=1` | route crowd ranking | PostGIS data |
| `RUN_MAPBOX_DIRECTIONS_INTEGRATION=1` | live walking directions | `MAPBOX_ACCESS_TOKEN` and network |

Example for a temporary PowerShell session:

```powershell
$env:RUN_ROUTE_RANKING_INTEGRATION = "1"
python -m pytest tests/integration/test_route_crowd_postgis_integration.py -q
Remove-Item Env:RUN_ROUTE_RANKING_INTEGRATION
```

Do not enable all live gates automatically in a normal unit-test run.

## Frontend tests

From `frontend/`:

```powershell
npm test
```

This runs the test TypeScript configuration and Vitest once. Current coverage
includes API parsing, search validation/loading/errors, route-option semantics,
one/two/three-route behavior, map feature data, selected-route navigation,
arrival, guards, and no-refetch behavior.

## Frontend production build

From `frontend/`:

```powershell
npm run build
```

This runs TypeScript and the Vite production build. Vite may report its
large-chunk advisory; the command is successful only when it exits with status
zero.

## Start the local application

Backend, from the repository root:

```powershell
python -m uvicorn backend.app.main:app --reload
```

Frontend, from `frontend/` in a second terminal:

```powershell
npm run dev
```

Expected local URLs:

- frontend: `http://localhost:5173`;
- backend: `http://localhost:8000`;
- health: `http://localhost:8000/health`;
- OpenAPI UI: `http://localhost:8000/docs`.

## Local API smoke tests

Liveness requires no database or Mapbox configuration:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Point crowd evaluation requires a populated database:

```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/crowd/point?lat=-37.81&lon=144.96"
```

The active route-options contract requires backend Mapbox and database
configuration:

```powershell
$body = @{
  origin = @{ longitude = 144.9582; latitude = -37.8067 }
  destination = @{ longitude = 144.9691; latitude = -37.8179 }
} | ConvertTo-Json -Depth 3

Invoke-RestMethod `
  -Method Post `
  -ContentType "application/json" `
  -Body $body `
  -Uri http://localhost:8000/api/v1/routes/options
```

The preference-aware compatibility contract additionally requires a
preference and labels:

```powershell
$body = @{
  origin = @{ label = "Origin"; longitude = 144.9582; latitude = -37.8067 }
  destination = @{ label = "Destination"; longitude = 144.9691; latitude = -37.8179 }
  preference = "PREFER_QUIETER"
} | ConvertTo-Json -Depth 3

Invoke-RestMethod `
  -Method Post `
  -ContentType "application/json" `
  -Body $body `
  -Uri http://localhost:8000/api/v1/routes/walking
```

Do not smoke-test the internal refresh endpoint casually: a successful call is
a production-style write. Its authentication and failure behavior are covered
by `tests/test_internal_refresh_api.py`.

## Acceptance-criteria checks

### Active browser journey

1. Open Home and start a route search.
2. Verify empty and unselected place input is rejected accessibly.
3. Verify Mapbox suggestions can be selected and current location handles
   allow/deny states.
4. Search a Melbourne origin/destination and confirm one to three returned
   routes show role, movements/min or unavailable wording, duration, distance,
   and textual relative activity.
5. Verify all returned geometries appear on Route Options.
6. Select each option and confirm the active detail changes without a new route
   request.
7. Start Navigation and confirm only the exact selected route and a real
   backend instruction appear.
8. Return to options and verify context reuse, then finish/exit and verify
   journey reset.
9. Repeat at desktop and mobile viewports and with one-, two-, and three-route
   controlled responses.

### Preference ranking and alert backend

Use the focused pytest files above to verify the criteria in
`acceptance-criteria.md`. Do not claim end-to-end preference selection or alert
display from the current React pages; those capabilities are not wired into the
active journey.

## Deployed smoke tests

Read-only checks:

```powershell
Invoke-RestMethod https://calmway-backend.vercel.app/health
Invoke-WebRequest https://calmway-frontend.vercel.app/
```

Then use the deployed frontend to verify:

- Home and Mapbox place search load;
- route search reaches the deployed backend without a CORS failure;
- route options and maps render;
- direct SPA paths do not return a Vercel 404;
- browser console/network responses contain no backend token, database URL, or
  refresh secret.

Route API smoke tests can consume Mapbox quota and database capacity, so run
them deliberately. Never include credentials in captured output.
