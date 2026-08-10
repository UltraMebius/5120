# CalmWay Phase 5B-1 crowd-alert decisions

## Status and scope

This record contains project-approved MVP product and engineering decisions for
the Phase 5B-1 ahead-of-route crowd-alert engine. They are provisional
heuristics, not empirically or scientifically validated data-science findings.
The frozen `handoff/epic1_backend_handoff_v3/` snapshot remains unchanged.

Phase 5B-1 returns a pure decision from an existing Phase 3E
`RouteCrowdEvaluation`. It does not add live navigation, an HTTP endpoint,
frontend alert UI, alternative-route selection, persistence, or new external
requests. Phase 5B-2 owns UI and alternative-route actions.

## Look-ahead window and progress

- The configured MVP look-ahead distance is 300 metres.
- The window is `(current_progress_meters, current_progress_meters + 300]`.
- A sample exactly at current progress is excluded; a sample exactly 300 metres
  ahead is included.
- Near the route end, only real remaining samples are evaluated. No samples are
  fabricated.
- At or after the route end there are no samples ahead, so the decision is
  `INSUFFICIENT_DATA` with reason `NO_SAMPLES_AHEAD`.
- `current_progress_meters` must be supplied by the caller. Zero is a valid,
  explicit start-of-route value; the service never claims it came from GPS.

## Usable evidence and preference

A sample is usable only when its coverage status is `SUPPORTED` or `LIMITED`
and its crowd exposure score is numeric. Both support classes are eligible for
the MVP. `NO_DATA` is never converted to zero, a crowd level, or clear evidence.

The service reuses the authoritative project preference configuration:

| UI tolerance | Internal preference | Maximum preferred score |
|---|---|---:|
| LOW | `AVOID_BUSY` | 50 |
| MEDIUM | `PREFER_QUIETER` | 75 |
| HIGH | `FLEXIBLE` | 90 |

Only `score > threshold` is above preference. Equality remains within
preference.

## Trigger heuristic

`ALERT` requires at least two consecutive above-preference usable samples in
the look-ahead window. Consecutive means adjacent Phase 3D route sample indexes
in the preserved route order. A `NO_DATA` sample, a nonnumeric sample, or a
usable sample at/below threshold breaks the streak. The two-sample rule is a
project MVP heuristic intended to avoid an alert for one isolated point; its
rough relationship to a sustained section follows the approximately 50-metre
sampling interval and is not a validated scientific claim.

The first qualifying streak in route order is the trigger. If that first streak
continues for three or more samples, the returned trigger spans the complete
streak. Later qualifying streaks do not replace the nearer trigger.

## Decision semantics and diagnostics

- `ALERT`: a qualifying consecutive streak exists.
- `CLEAR`: at least one usable numeric sample exists, but no qualifying streak
  exists. This only means that no trigger was found in currently usable data; it
  does not claim the route is safe or uncrowded.
- `INSUFFICIENT_DATA`: the window has zero usable numeric samples, including an
  empty ahead window. It is never converted to `CLEAR`.

Mixed numeric and `NO_DATA` windows use the numeric evidence that exists. The
result retains total, numeric, `SUPPORTED`, `LIMITED`, and `NO_DATA` counts plus
coverage. Look-ahead coverage is numeric usable samples divided by all samples
in the window. Above-preference percentage uses only numeric usable samples as
its denominator. When a denominator does not exist, the metric is `null`, not a
fabricated zero.

The result also carries deterministic window bounds, preference and threshold,
the maximum available window exposure, and nullable trigger indexes,
distances, count, first/second exposures, and trigger maximum. It contains no
street names, reverse-geocoded data, database errors, or user GPS metadata.

## Static navigation limitation

Navigation remains static. Phase 5B-1 does not use `watchPosition`, stream GPS,
move a user marker, map-match, snap to the route, advance turns, infer progress,
reroute, or detect arrival. A future caller may explicitly provide measured
progress; until then, evaluating at `0` means only a deterministic route-start
decision. Phase 5B-2 will decide how to expose this domain result in the UI and
how an alternative-route action should work.
