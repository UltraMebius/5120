# Navigation Crowd Alerts

## Current delivery status

The repository contains a complete, deterministic backend alert engine and
exposes its initial decision through `POST /api/v1/routes/walking`. The active
React journey currently calls `POST /api/v1/routes/options`; its
`NavigationPage` renders route guidance and the selected route but does not
render the alert contract.

Accordingly, the sections below describe implemented backend behavior, not a
claim that alerts are currently visible to users. `CrowdAlertPanel.tsx`, the
walking-response parser, and the lower-stimulation alternative helper remain in
the frontend tree as unreferenced compatibility code.

## Evaluation input

`RouteCrowdAlertService` receives an existing ordered
`RouteCrowdEvaluation`. It performs no Mapbox request, route sampling, database
query, City API call, or persistence. The `/api/v1/routes/walking` endpoint
reuses the exact per-route sample evaluation already created for ranking.

The service requires:

- a route evaluation with contiguous, increasing sample indexes/distances;
- one backend `CrowdPreference`;
- an explicit nonnegative current progress value;
- configured look-ahead distance and required consecutive sample count.

The API calls it once with `current_progress_meters=0.0`. This means
"evaluate from the route start"; it is not a browser/GPS measurement.

## Route-ahead section

The default `ROUTE_ALERT_LOOK_AHEAD_DISTANCE_M` is `300` metres. For progress
`p`, the evaluated section is:

```text
(p, p + 300 m]
```

- A sample exactly at current progress is excluded.
- A sample exactly 300 m ahead is included.
- A sample beyond 300 m is excluded.
- Near the destination, only real remaining samples are used.
- At or after route end, there are no samples ahead and the result is
  `INSUFFICIENT_DATA` with reason `NO_SAMPLES_AHEAD`.

No route samples are fabricated to fill a short window.

## Usable samples and thresholds

A sample is usable when its status is `SUPPORTED` or `LIMITED` and its Crowd
Exposure score is numeric. Both support classes are eligible. `NO_DATA`, a
missing number, or a nonnumeric value does not become zero or clear evidence.

The thresholds are the same as preference-aware route ranking:

| User preference | Backend enum | Alert threshold |
| --- | --- | ---: |
| Low | `AVOID_BUSY` | 50 |
| Medium | `PREFER_QUIETER` | 75 |
| High | `FLEXIBLE` | 90 |

Only `score > threshold` is above preference. Equality is not an exceedance.

## Exact alert trigger

The default `ROUTE_ALERT_REQUIRED_CONSECUTIVE_SAMPLES` is `2`.

`ALERT` requires at least two adjacent route-sample indexes in the look-ahead
window with usable scores strictly above the threshold. Consecutive is based on
the original route sample indexes, not merely adjacent rows after missing data
is removed.

Any of these breaks a streak:

- `NO_DATA`;
- a supported/limited sample without a numeric score;
- a score equal to or below the threshold.

The first qualifying streak in route order is the trigger. If that streak
continues beyond two samples, the returned trigger spans the complete streak.
A later streak does not replace the nearer one.

The two-sample rule is a project-owned MVP heuristic. At the default 50 m
sampling interval it reduces one-point alerts, but it has not been validated as
a clinical or scientific sensory threshold.

## Decision states

### `ALERT`

Returned when a qualifying consecutive streak exists. The response includes
the trigger start/end distances, sample count, maximum trigger exposure,
window evidence counts, look-ahead coverage, and percentage above preference.

### `CLEAR`

Returned when at least one usable numeric sample exists but no qualifying
streak exists. `CLEAR` means only that the configured trigger was not found in
the available look-ahead evidence; it is not a safety or quietness guarantee.

Mixed usable and `NO_DATA` windows can return `CLEAR`. Coverage and percentage
diagnostics remain explicit.

### `INSUFFICIENT_DATA`

Returned when the window contains no samples or no usable numeric sample.
Reasons are:

- `NO_SAMPLES_AHEAD`;
- `NO_USABLE_LOOK_AHEAD_CROWD_DATA`.

With no total samples, coverage is `null`. With samples but no numeric evidence,
coverage is `0`. Above-preference percentage and exposure metrics remain
`null`; insufficient data is never converted to `CLEAR`.

## API response boundary

Each walking route receives `initialCrowdAlert` with:

- decision and reason;
- preference and numeric threshold;
- explicit progress (`0`) and look-ahead distance;
- total and numeric sample counts;
- look-ahead coverage and percentage above preference;
- nullable trigger distances, count, and maximum.

It does not expose raw route samples, sensor identifiers, database details,
street reverse-geocoding, or GPS metadata.

## Inactive alternative-route helper

The unreferenced `findLowerStimulationAlternative` helper scans the existing
backend route order and would return the first different route that has:

1. non-null rank and P75;
2. non-insufficient preference status;
3. an initial `CLEAR` decision; and
4. a P75 strictly lower than the selected route.

It does not sort, refetch, create a route, or call Mapbox. Because the active
Navigation page uses the route-options contract and does not invoke this helper,
route switching is not a current user-facing capability.

## Explicit limitations

The current implementation does not:

- call `watchPosition` or continuously track GPS;
- map-match a user to the route;
- infer or update route progress;
- periodically rerun the alert engine;
- stream new sensor data into an active browser journey;
- dynamically reroute or automatically switch routes;
- detect off-route movement or arrival.

The active Navigation screen is a static overview of the exact selected route
and its backend-provided first usable instruction.

## Test evidence

- `tests/test_route_crowd_alert_service.py` verifies window boundaries,
  thresholds, streak behavior, all decisions, partial evidence, diagnostics,
  validation, and deterministic ordering.
- `tests/test_routes_api.py` verifies the public initial-alert DTO for all
  decision states and progress `0`.
- `frontend/tests/routeJourney.test.tsx` verifies current selected-route
  navigation behavior; it does not assert a crowd alert because that UI is not
  active.
