# Epic 1 Acceptance Criteria

## Product boundary

CalmWay's sensory-aware design goal is to help sensory-sensitive pedestrians
make a more informed route choice. The measurable proxy currently available is
pedestrian crowd exposure. CalmWay does not measure noise, lighting, smell,
surface quality, weather, construction, or an individual's complete sensory
experience.

Two route contracts coexist in the current repository:

- The active React journey calls `POST /api/v1/routes/options`. It compares one
  to three routes using recent or historical pedestrian movements per minute
  and labels eligible routes as `CALMEST`, `FASTEST`, or `BALANCED`.
- `POST /api/v1/routes/walking` implements the preference-aware P75 crowd
  exposure ranking and initial route-ahead alert described by User Stories 1.2
  and 1.3. Its service and API behavior are tested, but the active React pages
  do not currently call this endpoint or render its preference/alert contract.

The status below is therefore deliberately split between backend capability
and the active end-to-end product. An acceptance criterion is not marked as
fully delivered merely because unused frontend code or a backend endpoint
exists.

## Epic 1: Sensory-Aware Route Planning and Navigation Support

### User Story 1.1

> As a sensory-sensitive commuter, I want to compare crowd-exposure
> information for different routes, so that I can choose the route that best
> matches my comfort level.

| Acceptance criterion | Current status | Verification evidence |
| --- | --- | --- |
| A search with valid structured origin and destination data returns one or more real walking routes with distance, duration, geometry, instructions, and crowd information. | Implemented end to end. | `frontend/src/services/api.ts`, `backend/app/api/routes.py`, `tests/test_route_options_api.py`, `frontend/tests/api.test.ts` |
| Route crowd exposure is calculated from uniformly spaced route samples. Only numeric `SUPPORTED` and `LIMITED` samples participate; `NO_DATA` is not converted to zero. | Implemented by the preference-aware backend pipeline. | `route_sampling_service.py`, `route_crowd_evaluation_service.py`, `route_crowd_ranking_service.py`, `tests/test_route_crowd_ranking_service.py` |
| A route below the minimum usable crowd-data coverage remains available with distance, duration, and geometry, but receives no fabricated crowd score or recommendation. | Implemented by `/api/v1/routes/walking`. The active `/routes/options` contract instead falls back from common recent data to common historical data, then to an honest unavailable state. | `tests/test_route_crowd_ranking_service.py`, `tests/test_routes_api.py`, `tests/test_route_option_selection_service.py` |
| A user can review a route in the Navigation selection overlay and explicitly select it. Active Navigation receives the exact selected backend route without refetching route options. | Implemented end to end. | `JourneyContext.tsx`, `NavigationPage.tsx`, `frontend/tests/routeJourney.test.tsx` |

**Story status:** implemented for route comparison and selection. The active
product presents pedestrian movements per minute rather than the
preference-aware P75 score.

### User Story 1.2

> As a sensory-sensitive commuter, I want routes with lower crowd exposure to
> be prioritised, so that I can reduce exposure to highly congested pedestrian
> areas.

| Acceptance criterion | Current status | Verification evidence |
| --- | --- | --- |
| Low, Medium, and High preferences map to maximum preferred crowd-exposure scores of 50, 75, and 90 respectively. Exposure is above preference only when `score > threshold`; equality is within preference. | Implemented and tested in the backend. Not selectable in the active React journey. | `backend/app/config.py`, `tests/test_route_crowd_ranking_service.py` |
| Evaluable routes are ordered by the documented crowd-aware lexicographic ranking, not simply by shortest duration. | Implemented by `/api/v1/routes/walking`. | `route_crowd_ranking_service.py`, `tests/test_route_crowd_ranking_service.py`, `tests/test_routes_api.py` |
| The best evaluable route is recommended even when every evaluable route is above the selected preference. If no route reaches the coverage threshold, no recommendation is fabricated. | Implemented by `/api/v1/routes/walking`. | `tests/test_route_crowd_ranking_service.py` |
| Routes above preference remain visible and retain their truthful metrics instead of being hard-filtered. | Implemented in the backend response contract. | `tests/test_routes_api.py` |

**Story status:** backend-complete but not end-to-end in the active frontend.
The current React journey uses role selection based on pedestrian movements per
minute rather than the preference-aware ranking response.

### User Story 1.3

> As a sensory-sensitive commuter, I want to receive an alert when crowd
> exposure on the route ahead exceeds my preferred threshold, so that I can
> make a more informed decision before continuing my journey.

| Acceptance criterion | Current status | Verification evidence |
| --- | --- | --- |
| The alert evaluation uses the selected Low, Medium, or High preference threshold. | Implemented in the backend; no active frontend preference selection. | `route_crowd_alert_service.py`, `tests/test_route_crowd_alert_service.py` |
| The upcoming section is `(current progress, current progress + 300 m]`. The current API evaluates once at an explicit progress of `0 m`. | Implemented and tested. This is a route-start assessment, not measured GPS progress. | `backend/app/api/routes.py`, `tests/test_route_crowd_alert_service.py`, `tests/test_routes_api.py` |
| `ALERT` is triggered by at least two consecutive usable route samples strictly above the selected threshold. A missing, nonnumeric, or at/below-threshold sample breaks the streak. | Implemented and tested. | `route_crowd_alert_service.py`, `tests/test_route_crowd_alert_service.py` |
| When usable evidence exists but no qualifying streak exists, the decision is `CLEAR`. With no usable evidence, the decision is `INSUFFICIENT_DATA`; missing evidence is never presented as clear. | Implemented and tested. | `tests/test_route_crowd_alert_service.py`, `tests/test_routes_api.py` |
| The active Navigation page renders the backend alert state to the user. | Not currently implemented end to end. `CrowdAlertPanel.tsx` and compatibility parsing code exist but are not referenced by the active page tree. | `frontend/src/pages/NavigationPage.tsx`, repository reference search |

**Story status:** the deterministic initial alert engine and API contract are
implemented; delivery in the active user journey is incomplete.

## Explicit exclusions

The current implementation does not provide:

- continuous GPS tracking or measured route progress;
- periodic or streaming crowd re-evaluation;
- automatic rerouting;
- generation of a new alternative after navigation starts;
- active current-route versus alternative-route switching in the current UI;
- medical, personal-safety, or comprehensive sensory guarantees.

Navigation is a static selected-route overview using backend-provided route
instructions. See [Navigation Alerts](navigation-alerts.md) for the precise
implemented engine boundary and [Route Ranking](route-ranking.md) for both
route-selection contracts.
