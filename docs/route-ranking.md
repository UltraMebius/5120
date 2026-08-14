# Route Ranking and Route-Option Selection

## Why two algorithms are documented

The repository currently exposes two backend route contracts with different
purposes:

- `POST /api/v1/routes/options` is used by the active React journey. It assigns
  `CALMEST`, `FASTEST`, and `BALANCED` roles using pedestrian movements per
  minute.
- `POST /api/v1/routes/walking` implements the earlier preference-aware Crowd
  Exposure ranking using a 0-100 percentile score, P75 aggregation, and
  Low/Medium/High preference thresholds. It remains implemented and tested but
  is not called by the active React pages.

They share route geometry and sampling concepts, but their metrics and output
contracts must not be mixed.

## Common route sampling

Both pipelines operate on backend-returned full GeoJSON `LineString` geometry.
`RouteSamplingService`:

1. validates WGS84 longitude/latitude pairs and rejects degenerate geometry;
2. measures each nonzero segment with the Haversine formula and accumulates
   distance along the route;
3. emits the origin at `0 m`, points at each configured interval, and the exact
   destination once;
4. linearly interpolates coordinates within the measured segment containing
   each target distance.

The default `ROUTE_SAMPLE_INTERVAL_M` is `50`. Sampling is independent of the
irregular vertex spacing returned by Mapbox.

## Active route-option algorithm

### Pedestrian-flow evidence

All retained route samples are evaluated in one batched PostGIS operation.
For each sample, live and historical values are kept separate:

- live flow is an eligible sensor's current complete 15-minute count divided by
  15;
- historical typical flow is the matching hourly baseline median divided by
  60;
- eligible nearby sensors are combined with normalised inverse-distance
  weighting;
- missing or invalid evidence remains `null`.

For each route and evidence source, numeric sample values produce:

- coverage: `100 * numeric sample count / total sample count`;
- median using continuous percentile interpolation at 0.50;
- P75 using continuous percentile interpolation at 0.75;
- maximum.

### Common comparison basis

The default minimum usable coverage is
`MINIMUM_ROUTE_CROWD_COVERAGE_PCT=55`.

The selector compares candidates only on a common basis:

1. `LIVE` when every candidate has at least 55% live coverage and a numeric
   live median/typical value;
2. otherwise `HISTORICAL_ESTIMATE` when every candidate has at least 55%
   historical coverage and a numeric historical median/typical value;
3. otherwise `UNKNOWN`.

It never mixes one route's live evidence with another route's historical
evidence in the same comparison.

### FASTEST

`FASTEST` is always the global minimum lexicographic key across all candidate
routes:

1. duration;
2. distance;
3. source index;
4. route ID.

This role is always assigned and is independent of the other roles. If the
overall shortest route is also the lowest displayed-flow route, that same
route is both `FASTEST` and `CALMEST`; a slower route is never relabelled as
`FASTEST` to make the role IDs distinct.

### CALMEST

`CALMEST` requires at least two candidates and a non-unknown common basis. It
uses the exact median/typical movements-per-minute value displayed by the
frontend. The minimum lexicographic key wins:

1. median/typical movements per minute;
2. P75, with missing last;
3. maximum, with missing last;
4. duration;
5. distance;
6. source index;
7. route ID.

### BALANCED

`BALANCED` requires at least three candidates and a non-unknown common basis.
Duration and displayed median/typical flow are independently min-max
normalised across the candidate set. Each route receives:

```text
balanced score = 0.5 * normalised duration + 0.5 * normalised typical flow
```

All candidates remain eligible, including a route already labelled `CALMEST`
or `FASTEST`. The route with the lowest key is selected by balanced score,
typical flow, duration, distance, source index, then route ID. Consequently,
one route may carry `BALANCED` together with either or both other roles.

### Response order and relative activity

Unique routes are returned by role order `CALMEST`, `FASTEST`, `BALANCED`,
followed by any remaining candidates in fastest-key order. Roles are attached
independently to their winning route IDs. When multiple roles select the same
route, that original route is returned once with multiple badges; it is not
duplicated or detached from its geometry, metrics, or navigation steps.

When at least two routes share usable evidence, relative pedestrian activity is
assigned from the same displayed-median ordering as `LOWEST`, `MIDDLE`, and
`HIGHEST`. Unknown evidence or a single route produces `UNKNOWN`. The
frontend's semantic green/orange/red/grey accents use this relative activity
value, not the role name.

## Preference-aware Crowd Exposure ranking

### Usable samples and coverage

The preference-aware `/api/v1/routes/walking` path evaluates every route sample
with `SpatialCrowdService`.

A numeric sample is usable only when:

- `coverageStatus` is `SUPPORTED` or `LIMITED`; and
- `crowdExposureScore` is a finite numeric value from 0 through 100.

`SUPPORTED` and `LIMITED` numeric samples have equal weight in route
aggregation. The separate percentages remain available as diagnostics.
`NO_DATA` never participates in a numeric calculation, even if an upstream
object is contradictory and contains a number.

```text
numericSampleCount = usable SUPPORTED + usable LIMITED samples
dataCoveragePct = 100 * numericSampleCount / totalSampleCount
noDataPct = 100 * NO_DATA sample count / totalSampleCount
```

The default minimum coverage is 55%. Equality is sufficient. Below 55%, the
route is `INSUFFICIENT_DATA`: its Mapbox distance, duration, geometry, and steps
remain usable, but P75, maximum, preference percentage, rank, and recommendation
are null/absent.

### Route crowd summary

For an evaluable route, usable scores are sorted and continuous percentile
interpolation is used:

```text
position = (n - 1) * q
lower = floor(position)
upper = ceil(position)

if lower == upper:
    percentile = values[lower]
else:
    fraction = position - lower
    percentile = values[lower] + fraction * (values[upper] - values[lower])
```

The route score is P75 (`q=0.75`). The service also calculates median, maximum,
percentage of usable samples above preference, and percentage classified
`VERY_HIGH`.

Internal Crowd Exposure bands are:

| Score | Internal level | Frontend level |
| --- | --- | --- |
| `<= 25` | `VERY_LOW` | `LOW` |
| `> 25` and `<= 50` | `LOW` | `LOW` |
| `> 50` and `<= 75` | `MODERATE` | `MEDIUM` |
| `> 75` and `<= 90` | `HIGH` | `HIGH` |
| `> 90` | `VERY_HIGH` | `HIGH` |

These are relative network-percentile bands, not people-per-square-metre or
medical thresholds.

### Low, Medium, and High preference thresholds

| UI preference | Backend enum | Default maximum preferred score |
| --- | --- | ---: |
| Low | `AVOID_BUSY` | 50 |
| Medium | `PREFER_QUIETER` | 75 |
| High | `FLEXIBLE` | 90 |

For numeric samples:

```text
pctAbovePreference =
  100 * count(score > threshold) / numericSampleCount
```

Equality is within preference. A route's preference status is
`WITHIN_PREFERENCE` when P75 is at or below the threshold and
`ABOVE_PREFERENCE` when P75 is above it. Preference is a soft constraint;
above-preference routes remain visible.

### Final deterministic ordering

Evaluable routes are sorted ascending by this exact lexicographic key:

1. `noDataPct`;
2. `pctAbovePreference`;
3. P75 Crowd Exposure;
4. maximum Crowd Exposure;
5. duration;
6. original Mapbox `routeIndex`.

There is no weighted composite score and no random ordering. Routes with
insufficient data follow all evaluable routes and preserve Mapbox route-index
order.

The first evaluable route is recommended even when all evaluable routes exceed
the preference. When no route reaches minimum coverage,
`recommendedRouteId` is `null` and ranking status is `INSUFFICIENT_DATA`.
Otherwise the current project-owned status is `PROVISIONAL`; `VALIDATED` is
reserved and is not emitted by this implementation.

All route evaluations in one ranking request must refer to one current crowd
materialisation. Mixed source windows are a consistency error, not an
insufficient-data result.

## No Data principle

`NO_DATA` means there is no defensible numeric estimate at that sample. It is
not zero, quiet, low, or safe. Both route contracts preserve null versus
numeric zero and avoid generating a positive recommendation from missing
evidence.

## Test evidence

Primary regression coverage is in:

- `tests/test_route_sampling_service.py`;
- `tests/test_route_pedestrian_flow_service.py`;
- `tests/test_route_option_selection_service.py`;
- `tests/test_route_crowd_evaluation_service.py`;
- `tests/test_route_crowd_ranking_service.py`;
- `tests/test_route_options_api.py`;
- `tests/test_routes_api.py`;
- `frontend/tests/routeJourney.test.tsx`.
