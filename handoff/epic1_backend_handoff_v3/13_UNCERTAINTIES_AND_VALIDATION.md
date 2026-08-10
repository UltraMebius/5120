# Final Remaining Items — V3

The core data/crowd algorithm is frozen for MVP implementation.

## Confirmed / Closed

| Decision | Final status |
|---|---|
| Primary Crowd metric = Network percentile | Confirmed |
| Local percentile = separate Local Condition | Confirmed |
| MAX(Local, Network) | Rejected |
| Local baseline = Sensor × Hour × Weekday/Weekend | Confirmed |
| Network temporal calibration | Confirmed by V5B |
| Crowd bands = 25 / 50 / 75 / 90 | MVP fixed relative bands |
| Max spatial radius = 300 m | Final |
| Core radius = 250 m | Final |
| >300 m = No Data | Final |
| Spatial weighting = 1/d | Confirmed by final-target V1B |
| Whole 15m no-row = zero | Rejected |
| Whole 15m no-row = AMBIGUOUS_NO_RECORD | Final |
| Sensor-specific stale timer | Not used in MVP |
| Location 37 Local-history start | 2024-08-12 |
| Location 47 Local Condition | Disabled pending move-date verification |
| Location 181 Local Condition | Disabled pending move-date verification |

## Remaining Code Validation

### V7 — Route Sampling Interval

Current config:

```text
50 m
```

This remains provisional because route-sampling stability cannot be tested without real walking route geometry.

When real routes exist, compare:

```text
25 m
50 m
75 m
100 m
```

This does not block backend implementation because the interval is configurable.

## Remaining Product/User Decisions

### Preference mapping

Current configurable MVP values:

```text
AVOID_BUSY      <= P50
PREFER_QUIETER  <= P75
FLEXIBLE        <= P90
```

Pedestrian-count data cannot prove that these are sensory tolerance thresholds.

Representative-user/product testing is required.

### Route ranking trade-off

Current provisional order:

1. lower No Data %;
2. lower % above preference;
3. lower P75 Crowd Exposure;
4. lower max Crowd Exposure;
5. shorter duration.

The final trade-off between predictability, crowd reduction and walking time is a user/product decision.

## Remaining Manual Data Facts

### Location 47

The note contains an upgrade date before the move phrase, but the physical move date is not explicitly verified.

Until verified:

```text
Local Condition disabled
```

### Location 181

The note says it moved from 380 Elizabeth Street but provides no date.

Until verified:

```text
Local Condition disabled
```

These two manual facts do not block the Network Crowd Exposure model or current spatial scoring.
