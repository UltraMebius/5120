# Final Evidence Summary — V1 to V6 plus V1B/V3B/V4B/V5B

## Primary Crowd Metric

V2 rejected `MAX(Local, Network)` after showing materially inflated High/Very High classifications and a counterexample where a count of 1 became MAX=100.

Final:

```text
Network percentile → Crowd Exposure
Local percentile → Local Condition
```

## Network Historical Stability — V5B

```text
holdout rows = 403,318
scored = 100%

<=P25 = 25.057%
<=P50 = 49.911%
<=P75 = 74.348%
<=P90 = 90.119%

mean = 50.284
median = 50.124
```

This supports Network percentile as the primary relative Crowd Exposure concept.

## Final Spatial Weighting — V1B

At 300 m:

```text
1/d:
MAE 17.2364
RMSE 21.9956

Gaussian150:
MAE 17.3453
RMSE 22.1058

Equal:
MAE 17.5218
RMSE 22.3740

1/d²:
MAE 17.5362
RMSE 22.4895

Nearest:
MAE 18.7329
RMSE 24.3699
```

Final:

```text
weighting = 1/d
```

## Final Radius

Using 1/d:

```text
250m coverage 87.73%, MAE 17.0623
300m coverage 92.98%, MAE 17.2364
475m coverage 99.59%, MAE 16.7946
```

300 m remains final because it balances strong support with locality.

## Realtime No-Record — V3/V3B

A no-row sensor window cannot be reliably classified as zero or device outage.

Final:

```text
whole complete 15m window has 0 valid rows
→ AMBIGUOUS_NO_RECORD
```

No sensor-specific time-based stale threshold is used.

## Relocation — V4B

```text
14 → explicit 2019 move, Local baseline usable in audited range

37 → move date 2024-08-12,
     exclude 2024-08-08 to 2024-08-11 from Local baseline

47 → move date ambiguous,
     Local Condition disabled until verified

181 → move date unknown,
      Local Condition disabled until verified
```

## POI Coverage — V6

```text
SUPPORTED = 47.11%
LIMITED   = 4.55%
NO_DATA   = 48.35%
```

This is landmark/POI support, not route or CBD area coverage.

## Remaining Validation

Only route-sampling stability V7 remains as a code validation once real route geometry exists.

Preference mapping and route ranking are user/product validation questions, not pedestrian-data questions.
