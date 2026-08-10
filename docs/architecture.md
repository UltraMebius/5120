# CalmWay Epic 1 Architecture

## Current Phase 3C structure

```text
React Route Search + Mapbox Search Box
  -> Journey Context
  -> POST /api/v1/routes/walking
  -> FastAPI walking routing service
  -> Mapbox Directions (walking, full GeoJSON)
  -> Journey Context route candidates
  -> shared RouteMap on Route Options and Navigation
```

The legacy `GET /api/routes` endpoint remains compatibility preview data, but it
is not used by the active Route Search flow. Phase 3C renders real Mapbox route
geometry without route-level Crowd Exposure or CalmWay ranking.

## Current frontend flow

```text
Future Home
  -> Route Search
  -> Route Options
  -> Active Navigation
       -> optional Crowd Alert state
  -> Arrival
  -> Future Home
```

The frontend stores only small journey state in React Context. Redux is not
used. Crowd Alert is a state of the Navigation page, not an independent route.

## Next backend/data integration

```text
City of Melbourne APIs
  -> scheduled ingestion and baseline jobs
  -> PostgreSQL + PostGIS
  -> current Network Crowd Exposure cache
  -> spatial crowd service

Mapbox Directions walking candidates
  -> route sampling
  -> spatial crowd service
  -> P75 route summary and configured ranking
  -> FastAPI
  -> React
```

Mapbox supplies walkable geometry, distance, duration, and maneuvers. CalmWay's
sensor-derived engine supplies crowd evidence and recommendation ranking. The
two responsibilities remain separate.

## Authoritative contracts

- Data/crowd algorithm: `handoff/epic1_backend_handoff_v3/`
- Starting database schema: `handoff/epic1_backend_handoff_v3/05_DATABASE_SCHEMA.sql`
- Backend API target: `handoff/epic1_backend_handoff_v3/09_INTERNAL_API_OPENAPI.yaml`
- Product integration plan: `docs/final-epic1-implementation-plan-cn.md`
