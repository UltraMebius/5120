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

Crowd levels are relative pedestrian-activity estimates. They do not represent
persons/m² density, medical tolerance, or a safety guarantee.
