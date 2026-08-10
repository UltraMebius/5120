# CalmWay Epic 1 Architecture

## Current Phase 1 structure

```text
React Router pages
  -> Journey Context
  -> frontend service boundaries
  -> FastAPI API
  -> typed schemas
  -> crowd / routing / navigation service boundaries
```

The current `GET /api/routes` endpoint and its two route records are explicit
compatibility preview data. They keep the full UI flow runnable but do not call
Mapbox, read City data, calculate Crowd Exposure, or rank real routes.

## Final frontend flow

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

## Final backend/data flow

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
