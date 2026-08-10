# Epic 1 Acceptance Scope

## User Story 1.1

Users can enter a walking origin and destination, select one crowd tolerance,
compare one to three available route candidates, and see a LOW/MEDIUM/HIGH
crowd indicator for each route.

## User Story 1.2

The final backend evaluates high pedestrian-activity exposure and recommends a
route using the authoritative CalmWay ranking, rather than choosing the
shortest candidate by default.

## User Story 1.3

During final active navigation, the remaining route is periodically evaluated
against the latest complete 15-minute crowd window. If upcoming exposure
exceeds the selected preference, the navigation page shows an alert and offers
a lower-stimulation route when one is available, or lets the user continue.

## Phase 1 acceptance boundary

Phase 1 establishes the full screen/state flow, typed contracts, configuration,
backend packages, and explicit preview data. Real Mapbox routes, City data,
PostGIS scoring, crowd ranking, GPS navigation, periodic evaluation, and
rerouting are not yet acceptance claims.

## Phase 6B implementation and test mapping

This section records the final implementation honestly; it does not rewrite the
historical user stories above. New reliability scenarios are labelled `Phase 6B
robustness check` in `phase6b-acceptance-test-matrix-cn.md`.

| Historical requirement | Final status | Implementation/test evidence |
|---|---|---|
| User Story 1.1 | Implemented with an explicit data-availability constraint | Structured origin/destination, one selected LOW/MEDIUM/HIGH tolerance, and returned route cards were verified in the controlled browser journey. With numeric coverage, cards present a frontend crowd level; without it, the product shows `Crowd information unavailable` instead of fabricating a level. Backend evidence: `tests/test_routes_api.py`, `tests/test_route_crowd_ranking_service.py`. |
| User Story 1.2 | Implemented | The backend owns crowd aggregation, deterministic ranking, and recommendation. Evidence: `tests/test_route_crowd_ranking_service.py`, `tests/test_routes_api.py`. |
| User Story 1.3 | **Not implemented in full** | Navigation presents the initial route-ahead decision calculated at exactly 0 m and can switch to an eligible route already returned by Search. Periodic evaluation against newer 15-minute windows, live progress, and automatic rerouting are not implemented. Evidence for the implemented subset: `tests/test_route_crowd_alert_service.py`, `tests/test_routes_api.py`, and the Phase 6B controlled browser audit. |
| Phase 1 acceptance boundary | Historical boundary, subsequently advanced through Phases 2–6 | Real Search Box, walking routes, PostGIS crowd scoring, route ranking, initial alert, and the complete static overview journey are now integrated. Live GPS/progress behavior remains outside the claim. |

### Immutable backend acceptance mapping

The handoff criteria remain authoritative and unchanged.

| Handoff criteria | Primary regression evidence |
|---|---|
| AC-B01–B02 | `tests/test_hourly_count_ingestion.py`, `tests/test_hourly_count_repository.py`, database schema integration |
| AC-B03–B05 | `tests/test_minute_ingestion.py`, `tests/test_current_activity_service.py` |
| AC-B06–B07 | `tests/test_current_activity_service.py`, `tests/test_crowd_contract.py` |
| AC-B08–B11 | `tests/test_spatial_crowd_service.py`, `tests/test_spatial_repository.py`, controlled PostGIS integration |
| AC-B12–B16 | `tests/test_current_activity_service.py` |
| AC-B17–B20 | `tests/test_historical_baseline_service.py`, `tests/test_baseline_repository.py` |
| AC-B21 | `tests/test_current_activity_service.py`, `tests/test_crowd_contract.py` |
| AC-B22 | `tests/test_route_sampling_service.py` |
| AC-B23 | `tests/test_route_crowd_ranking_service.py`, `tests/test_routes_api.py` |
| AC-B24 | `tests/test_route_crowd_evaluation_service.py`, `tests/test_walking_routing_service.py`, `tests/test_routes_api.py` |

Phase 6B full regression result: **251 passed, 8 skipped, 0 failed**. The
skipped tests require explicitly enabled live City, Mapbox, or controlled
database integration conditions; the read-only database readiness test ran and
passed.

Crowd levels are relative pedestrian-activity estimates. They do not represent
persons/m² density, medical tolerance, or a safety guarantee.
