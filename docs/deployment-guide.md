# Deployment Guide

## Production projects and URLs

CalmWay is deployed as two separate Vercel projects:

| Project | Root directory | Production URL |
| --- | --- | --- |
| `calmway-backend` | `backend` | `https://calmway-backend.vercel.app` |
| `calmway-frontend` | `frontend` | `https://calmway-frontend.vercel.app` |

Both URLs returned HTTP 200 during the repository cleanup verification on
2026-08-13; the backend `/health` response was `{"status":"ok"}`. A successful
health response proves process liveness, not Mapbox/database route readiness.

## Safety rules

- Never commit `.env`, `.env.local`, `.vercel`, tokens, database URLs, or Vercel
  credentials.
- Use a public Mapbox token only in `VITE_MAPBOX_PUBLIC_TOKEN`.
- Keep `MAPBOX_ACCESS_TOKEN`, `DATABASE_URL`, and `REFRESH_SECRET` server-side.
- Configure Preview and Production values separately.
- Apply database schema/data operations explicitly; a Vercel deployment does
  not run migrations, ingestion, or baseline jobs at startup.

## Backend deployment

### Vercel configuration

The backend root is `backend/`. `backend/index.py` re-exports the single
FastAPI application from `app.main`, and `.python-version` requests Python
3.12. No `vercel.json` is required for the native FastAPI detection.

From `backend/` with the Vercel CLI authenticated:

```bash
vercel link
vercel --prod
```

When linking, choose or enter project `calmway-backend`. The generated
`backend/.vercel/` metadata is local and ignored.

### Required production environment variables

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL/PostGIS runtime URL. Use a Neon pooled URL for Vercel requests. |
| `MAPBOX_ACCESS_TOKEN` | Secret backend token for Mapbox Directions. |
| `FRONTEND_ORIGINS` | Comma-separated exact frontend origins allowed by CORS, including the production frontend URL. |
| `REFRESH_SECRET` | High-entropy Bearer secret for the internal current-activity refresh endpoint. |

`DATABASE_URL` accepts `postgresql://` (normalised to psycopg 3) or
`postgresql+psycopg://`. SQLite and other databases are rejected. Use a direct
Neon connection for schema administration or bulk ingestion and the pooled
connection for Vercel runtime traffic. When Vercel supplies `VERCEL=1`, the
application limits each warm SQLAlchemy engine to one reusable connection and
delegates broad pooling to Neon.

### Optional/defaulted backend variables

These names are read by the current source and normally use the defaults shown
in `.env.example` or `backend/app/config.py`:

| Variable | Default/use |
| --- | --- |
| `APP_TIMEZONE` | `Australia/Melbourne` |
| `MAPBOX_DIRECTIONS_PROFILE` | `mapbox/walking`; other profiles are rejected by the client |
| `MAPBOX_DIRECTIONS_TIMEOUT_SECONDS` | `15` seconds |
| `AVOID_BUSY_MAX_PREFERRED_SCORE` | `50` |
| `PREFER_QUIETER_MAX_PREFERRED_SCORE` | `75` |
| `FLEXIBLE_MAX_PREFERRED_SCORE` | `90` |
| `MAX_SPATIAL_SUPPORT_RADIUS_M` | `300` |
| `CORE_SPATIAL_SUPPORT_RADIUS_M` | `250` |
| `SPATIAL_WEIGHT_METHOD` | `inverse_distance` |
| `SPATIAL_WEIGHT_POWER` | `1` |
| `SPATIAL_DISTANCE_FLOOR_M` | `1` |
| `ROUTE_SAMPLE_INTERVAL_M` | `50` |
| `MINIMUM_ROUTE_CROWD_COVERAGE_PCT` | `55` |
| `ROUTE_ALERT_LOOK_AHEAD_DISTANCE_M` | `300` |
| `ROUTE_ALERT_REQUIRED_CONSECUTIVE_SAMPLES` | `2` |
| `CITY_DATA_BASE_URL` | City of Melbourne Explore API v2.1 base URL |
| `CITY_DATA_TIMEOUT_SECONDS` | `30` seconds |
| `CITY_MINUTE_DATASET_ID` | Past-hour per-minute pedestrian counts |
| `CITY_HOURLY_DATASET_ID` | Monthly per-hour pedestrian counts |
| `CITY_SENSOR_DATASET_ID` | Pedestrian sensor locations |
| `MINUTE_INGESTION_INTERVAL_MINUTES` | `15` |
| `SOURCE_CACHE_STALE_AFTER_MINUTES` | Unset by default; must be a positive integer when set |

Do not set `VERCEL` manually; the platform owns it.

### Database readiness

The production database must already have PostGIS and the schema in
`handoff/epic1_backend_handoff_v3/05_DATABASE_SCHEMA.sql`. Verify with a direct
administrative connection before deployment. Runtime requests must not be used
to create or migrate schema.

### Backend smoke tests

After deployment:

```bash
curl --fail-with-body https://calmway-backend.vercel.app/health
curl --fail-with-body https://calmway-backend.vercel.app/docs
```

Then deliberately test `GET /api/v1/crowd/point` and
`POST /api/v1/routes/options` with controlled coordinates. A route request
verifies database, backend Mapbox, and response integration but consumes
external capacity. Confirm errors and logs do not expose secrets.

## Frontend deployment

### Vercel configuration

The frontend root is `frontend/`. Vercel should detect Vite, run
`npm run build`, and publish `dist/`. `frontend/vercel.json` rewrites all paths
to `/index.html` so React Router handles direct links and refreshes.

From `frontend/`:

```bash
vercel link
vercel --prod
```

When linking, choose or enter project `calmway-frontend`. The generated
`frontend/.vercel/` metadata remains ignored.

### Frontend environment variables

| Variable | Production setting | Exposure |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `https://calmway-backend.vercel.app` without a trailing slash | Public build-time value |
| `VITE_MAPBOX_PUBLIC_TOKEN` | Browser-safe Mapbox public token | Public build-time value |
| `VITE_HOME_ROUTE` | Optional; defaults to `/home` | Public build-time value |

The source also reads `VITE_AVOID_BUSY_MAX_PREFERRED_SCORE`,
`VITE_PREFER_QUIETER_MAX_PREFERRED_SCORE`, and
`VITE_FLEXIBLE_MAX_PREFERRED_SCORE` in compatibility crowd-preference types.
The active React journey does not render that selector. If the compatibility
flow is intentionally re-enabled, keep these public values aligned with the
backend thresholds (defaults 50/75/90).

Every `VITE_` variable is embedded in the browser bundle. Never put a backend
Mapbox token, Neon URL, refresh secret, or Vercel credential in one.

### Frontend smoke tests

After deployment:

1. open and refresh `/home`, `/routes/search`, `/routes/options`, `/navigation`,
   and `/arrival`;
2. confirm no path receives a platform 404 (guard redirects are expected when
   journey context is absent);
3. select Mapbox suggestions and complete a real route-options request;
4. confirm the browser uses the production backend and receives no CORS error;
5. inspect the bundle/network responses for accidental server secrets.

## CORS deployment order

1. Deploy or obtain the backend URL.
2. Configure frontend `VITE_API_BASE_URL` and deploy the frontend.
3. Add the exact frontend production and required preview origins to backend
   `FRONTEND_ORIGINS`.
4. redeploy the backend if its environment changed;
5. run the browser end-to-end smoke test.

Do not use `*` for production CORS and do not include path components in an
origin.

## Scheduled current-activity refresh

`.github/workflows/refresh-current-activity.yml` runs at minutes 7, 22, 37,
and 52 each hour in `Australia/Melbourne` and supports manual dispatch. It
calls:

```text
POST https://calmway-backend.vercel.app/api/v1/internal/refresh-current-activity
Authorization: Bearer <secret>
```

Configure the GitHub Actions secret `CALMWAY_REFRESH_SECRET` with the same value
as backend `REFRESH_SECRET`. The workflow has read-only repository permissions,
a five-minute timeout, and non-cancelling concurrency. A response body of
`{"status":"ok","updated":N}` indicates the endpoint completed; validate
source freshness and database state separately.

## Rollback

- Use Vercel's deployment history to promote the last known healthy frontend or
  backend deployment.
- Roll back application deployments independently.
- Do not roll back database data merely because an application deployment is
  rolled back unless a separate, reviewed data recovery plan requires it.
- Disable the GitHub Actions workflow before rotating or repairing a broken
  refresh secret/endpoint if repeated writes are unsafe.
- Re-run health, CORS, route, map, and direct-link checks after rollback.
