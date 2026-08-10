# Team Guide

## Frontend: `frontend/`

- pages own Route Search, Route Options, Navigation, and Arrival;
- Crowd Alert stays inside Navigation state;
- Journey Context stores only the current journey;
- `services/mapbox.ts` is the future Mapbox boundary;
- never expose a backend Mapbox token through a `VITE_` variable.

## Backend: `backend/`

- `api/` owns HTTP endpoints;
- `schemas/` owns validated API shapes;
- `models/` owns domain enums;
- `services/crowd/` will own the frozen crowd algorithm;
- `services/routing/` will own Mapbox walking candidates and CalmWay ranking;
- `services/navigation/` will own remaining-route checks and rerouting;
- `repositories/` and `db/` will own PostgreSQL/PostGIS access.

## Data Science handoff

`handoff/epic1_backend_handoff_v3/` is authoritative. Do not replace its
Network percentile, separate Local Condition, 300 m support limit, normalised
1/d weighting, no-data rules, P75 route summary, or ranking order.

## Tests and documentation

Keep existing tests passing, add contract tests before implementing later-phase
algorithm work, and update documentation whenever a preview becomes real.
