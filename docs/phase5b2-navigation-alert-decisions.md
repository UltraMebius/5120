# CalmWay Phase 5B-2 navigation alert decisions

## Status and boundary

This record owns the MVP product and engineering decisions for presenting the
Phase 5B-1 decision on Navigation and switching to an eligible route that was
already returned by the same walking-route search. These decisions are
provisional project policy, not a data-science-validated model or a medical or
sensory-safety assessment. The immutable V3 handoff is unchanged.

Navigation is still a static route overview. Phase 5B-2 stops before continuous
GPS, measured progress, map matching, turn advancement, off-route detection,
arrival detection, and automatic rerouting.

## One evaluation and one route response

`POST /api/v1/routes/walking` remains the only route request. For each Mapbox
candidate, the Phase 3E `RouteCrowdEvaluation` created for Phase 4 is retained
alongside its aggregation result. The API passes that exact evaluation to
`RouteCrowdAlertService.evaluate_ahead(...)`; it does not sample the geometry,
evaluate spatial points, or query PostGIS again.

The initial call always uses `current_progress_meters=0`. This means “assess
from the route start,” not “the browser measured the user at zero.” Each route
receives a frontend-safe `initialCrowdAlert` DTO with the Phase 5B-1 state,
reason, preference, threshold, look-ahead distance, evidence counts/coverage,
above-preference percentage, and nullable trigger distances/count/maximum. It
does not expose sample arrays, sensor details, database internals, or GPS data.

## Navigation states

- `ALERT` displays a prominent contained panel headed “Busier pedestrian
  activity ahead.” It describes preference-based pedestrian activity and uses
  only the backend’s returned look-ahead and trigger distances. It never says
  danger, unsafe, hazard, or medical risk.
- `CLEAR` keeps normal navigation visible and adds only a subtle statement that
  no alert is currently triggered from the available route-ahead data. It does
  not guarantee a quiet, uncrowded, or safe route.
- `INSUFFICIENT_DATA` shows “Crowd monitoring unavailable” while retaining the
  Mapbox route, distance, duration, and first normalized step. It is not
  displayed as LOW or CLEAR and does not create a recommendation.

“Continue current route” acknowledges and dismisses the alert card for that
route during the current in-memory Navigation session. It does not change the
backend decision, crowd condition, route geometry, or database. Acknowledgement
is route-specific and is never persisted.

## Existing lower-stimulation alternative rule

The action is offered only when the current route has a numeric Phase 4 P75 and
the first candidate found in existing backend order satisfies every condition:

1. it has a different route ID;
2. it is already present in the same walking-route response;
3. its Phase 4 rank and P75 are non-null;
4. its preference status is not `INSUFFICIENT_DATA`;
5. its initial Phase 5B-1 decision is `CLEAR`; and
6. its P75 is strictly lower than the current route’s P75.

The frontend performs a linear first-match scan and never sorts or reranks. A
single route, a current route without numeric P75, or an insufficient/unclear/
not-strictly-lower candidate produces no button. No route is fabricated.

Selecting the action replaces `JourneyContext.selectedRoute` with that exact
existing object. The current RouteMap, distance, duration, and first normalized
Mapbox step react to the selection. It causes no API, Mapbox Search, Mapbox
Directions, spatial, or database request. This is an **existing alternative
route switch**, not live or automatic rerouting.

## Real-data and test policy

The real current materialisation may contain zero numeric samples. Normal
Navigation must therefore support `INSUFFICIENT_DATA` without blocking route
use. Controlled backend API fixtures cover all three decision states, and a
browser fetch stub can exercise presentation and route switching without
altering production data. There is no production “force alert” control and no
random or fake production decision.

A future live-navigation phase may supply measured progress to the already-pure
Phase 5B-1 service and define re-evaluation cadence and stale-alert behavior.
Phase 5B-2 does not infer progress or reserve those policy decisions.
