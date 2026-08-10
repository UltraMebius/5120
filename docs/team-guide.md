# Team Guide

## Frontend: `frontend/`

- pages own Route Search, Route Options, Navigation, and Arrival;
- Crowd Alert stays inside Navigation state;
- Journey Context stores only the current journey;
- `services/mapbox.ts` owns browser-safe Mapbox Search Box configuration and
  place retrieval; `components/map/` owns Mapbox GL JS rendering;
- never expose a backend Mapbox token through a `VITE_` variable.

## Backend: `backend/`

- `api/` owns HTTP endpoints;
- `schemas/` owns validated API shapes;
- `models/` owns domain enums;
- `services/crowd/` will own the frozen crowd algorithm;
- `services/routing/` owns Mapbox walking candidates, pure uniform sampling,
  in-process sample-level crowd evaluation, route aggregation, and backend-only
  deterministic recommendation ranking;
- `services/navigation/` will own remaining-route checks and rerouting;
- `repositories/` and `db/` will own PostgreSQL/PostGIS access.

## Data Science handoff

`handoff/epic1_backend_handoff_v3/` is authoritative. Do not replace its
Network percentile, separate Local Condition, 300 m support limit, normalised
1/d weighting, no-data rules, P75 route summary, or ranking order.
`docs/phase4-route-ranking-decisions.md` supplements only the product decisions
that the immutable handoff marked provisional or pending user validation.

## Tests and documentation

Keep existing tests passing, add contract tests before implementing later-phase
algorithm work, and update documentation whenever a preview becomes real.
