# Backend Test Plan — Final V3

## 1. Regression Tests for Final Decisions

### Network Crowd bands

Test:

```text
0, 25, 25.0001, 50, 50.0001, 75, 75.0001, 90, 90.0001, 100
```

### Local / Network separation

Regression example from V2:

```text
count = 1
Local = 100
Network = 0.644792
```

Expected:

```text
Crowd Level = VERY_LOW
Local Condition = MUCH_BUSIER_THAN_USUAL
```

The test must fail if Crowd Level becomes Very High.

### Final 1/d weights

For distances:

```text
50, 100, 200, 300 m
```

verify:

```text
weight(50) > weight(100) > weight(200) > weight(300)
sum(normalised weights) = 1
```

### Coverage boundaries

```text
250.000 m → SUPPORTED
250.001 m → LIMITED
300.000 m → LIMITED
300.001 m → NO_DATA
```

---

## 2. Realtime Tests

### Complete 15m window with valid rows

Expected:

```text
OK
count = sum(valid rows)
included in Network rank
```

### Complete 15m window with zero valid rows

Expected:

```text
AMBIGUOUS_NO_RECORD
count = NULL
Network percentile = NULL
excluded from Network rank
```

### Repeated ambiguous windows

Expected:

```text
remain AMBIGUOUS_NO_RECORD at sensor level
```

unless an independent source/cache freshness state applies.

Do not infer sensor outage from elapsed no-row duration alone.

### Conflicted logical keys

Expected:

- raw rows preserved;
- logical key excluded from scoring.

---

## 3. Relocation Tests

### Location 37

Local-baseline builder must exclude:

```text
2024-08-08 through 2024-08-11
```

and include:

```text
2024-08-12 onward
```

### Location 47

Until move date verification:

```text
Local Historical Percentile = NULL
Local Condition = NULL
```

### Location 181

Until move date verification:

```text
Local Historical Percentile = NULL
Local Condition = NULL
```

### Network historical distribution

Valid count rows from 47/181 may remain in Network reference construction.

---

## 4. PostGIS Spatial Tests

Verify:

- Indoor sensors are excluded from Outdoor walking scoring.
- Sensors >300 m are excluded.
- 1/d weights are normalised.
- Dense sensor deployment does not cause raw-count inflation.
- No valid score within 300 m returns `NO_DATA`.

---

## 5. Historical Calibration Regression

Retain V5B as a reference benchmark for Network context:

```text
scored holdout = 100%
<=P25 ≈ 25.057%
<=P50 ≈ 49.911%
<=P75 ≈ 74.348%
<=P90 ≈ 90.119%
mean ≈ 50.284
median ≈ 50.124
```

Large deviations after pipeline changes require review.

---

## 6. Route Tests

Use fixed route fixtures once real route geometry exists.

Validate:

- Supported/Limited/No Data percentages;
- P75 Crowd Exposure;
- max Crowd Exposure;
- preference exceedance %;
- stable behaviour across route-sampling interval changes.

The only remaining code validation is V7 route-sampling stability on real routes.

---

## 7. Operational Monitoring Tests

Verify reporting of:

- last successful City data ingestion;
- last successful current-score build;
- current cache age;
- `OK` sensor count;
- `AMBIGUOUS_NO_RECORD` count;
- conflict count;
- routing API errors.

`STALE` belongs to source/cache freshness monitoring, not per-sensor no-row duration.
