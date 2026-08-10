# Scope and Final Backend Decisions — V3

## 1. Epic Scope

### Epic 1 — Crowd-Aware Walking Route Planning

The MVP supports walking-route comparison using relative pedestrian activity.

### In scope

- walking route candidate generation;
- current Crowd Exposure;
- historical Network context;
- separate Local Condition;
- route exposure metrics;
- crowd-preference-based ranking;
- landmarks as POI/orientation context;
- explicit coverage and data states.

### Out of scope

- public transport;
- persons/m² density;
- occupancy;
- medical/clinical sensory thresholds;
- noise;
- construction/disruption;
- visual stimulation;
- sensory-safe certification.

---

## 2. Final Crowd Semantics

### Primary Crowd Exposure

```text
Network percentile
```

This compares pedestrian volume with the monitored network under the relevant temporal context.

It is the basis for `Crowd Level`.

### Local Condition

```text
Local historical percentile
```

This compares the location with its own history.

It is presented separately.

### Rejected

```text
MAX(Local percentile, Network percentile)
```

V2 showed this can classify extremely small counts as Very High when a normally quiet sensor is unusually active.

---

## 3. Final Historical Context

### Local

```text
Location_ID × HourDay × Day_Type
```

### Network

```text
HourDay × Day_Type
across eligible monitored observations
```

### Day type

```text
Weekday
Weekend
```

V5 supports the Local structure.

V5B confirms the Network historical calibration:

- scored holdout = 100%;
- ≤P25 = 25.057%;
- ≤P50 = 49.911%;
- ≤P75 = 74.348%;
- ≤P90 = 90.119%;
- mean percentile = 50.284;
- median percentile = 50.124.

---

## 4. Final Crowd Bands

Applied to Network Crowd Exposure:

| Percentile | Crowd Level |
|---:|---|
| 0–25 | Very Low |
| >25–50 | Low |
| >50–75 | Moderate |
| >75–90 | High |
| >90–100 | Very High |

These are relative statistical bands.

They are not clinical thresholds.

---

## 5. Local Condition Bands

Applied only to Local Historical Percentile:

| Local percentile | Local Condition |
|---:|---|
| 0–25 | Much quieter than usual |
| >25–50 | Quieter than usual |
| >50–75 | Typical |
| >75–90 | Busier than usual |
| >90–100 | Much busier than usual |

Local Condition does not automatically change Crowd Level.

---

## 6. Final Spatial Support

Only `Outdoor` sensors directly support outdoor walking-route estimates.

```text
nearest valid Outdoor sensor <= 250 m
→ SUPPORTED

250 m < nearest valid Outdoor sensor <= 300 m
→ LIMITED

nearest valid Outdoor sensor > 300 m
→ NO_DATA
```

Do not extend the radius until a sensor is found.

Do not interpret `NO_DATA` as Low.

---

## 7. Final Spatial Weighting

V1B re-ran the test using the final Network percentile target.

At 300 m:

| Method | MAE | RMSE |
|---|---:|---:|
| **1/d** | **17.2364** | **21.9956** |
| Gaussian150 | 17.3453 | 22.1058 |
| Equal | 17.5218 | 22.3740 |
| 1/d² | 17.5362 | 22.4895 |
| Nearest | 18.7329 | 24.3699 |

Final weighting:

```text
w_i = 1 / max(d_i, 1 m)
```

Then:

```text
SpatialScore =
SUM(w_i × Score_i)
/
SUM(w_i)
```

For Crowd Exposure:

```text
Score_i = Network Crowd Exposure percentile
```

For Local Condition:

```text
Score_i = Local Historical Percentile
```

The two outputs remain separate.

---

## 8. Realtime Current Crowd Exposure

For each complete 15-minute sensor window:

```text
>=1 valid unconflicted source row
→ OK
→ sum valid rows
→ include in current Network ranking

0 valid rows
→ AMBIGUOUS_NO_RECORD
→ current count NULL
→ current Network percentile NULL
→ exclude from ranking
```

No sensor-specific stale duration threshold is used.

`STALE` only represents source/cache freshness problems detected by operational monitoring.

---

## 9. Complete-Hour Historical Context

The previous complete clock hour may be reconstructed from minute data and compared with hourly history.

Return separately:

```text
current_1h_network_historical_percentile
current_1h_local_historical_percentile
```

Do not compare a 15-minute total directly with hourly historical percentiles.

Do not use MAX.

---

## 10. Relocation Rules

Local historical percentile assumes stable physical location.

Final MVP handling:

### Location 14

Explicit move: 2019-10-02.

Audited hourly data begin 2024-08-08.

```text
Local baseline allowed.
```

### Location 37

Verified movement-associated date from note:

```text
2024-08-12
```

Hourly data begin 2024-08-08.

```text
Exclude 2024-08-08 through 2024-08-11
from Location 37 Local baseline.

Use 2024-08-12 onward.
```

### Location 47

Move date remains ambiguous.

```text
Local Condition disabled
until date manually verified.
```

### Location 181

Move date unavailable.

```text
Local Condition disabled
until date verified.
```

### Network baseline

These restrictions are Local-baseline restrictions.

The valid pedestrian-count observations may remain in the broader Network distribution because Network percentile does not assume that a given `Location_ID` represented one unchanged physical site across the entire period.

---

## 11. Preference Mapping

MVP configurable values:

```text
AVOID_BUSY      → preferred Network score <= 50
PREFER_QUIETER  → preferred Network score <= 75
FLEXIBLE        → preferred Network score <= 90
```

These remain product/user validation choices, not statistically derived sensory thresholds.

---

## 12. Route Evaluation

Current sampling configuration:

```text
50 m
```

This is provisional until real route geometry is available for V7.

Route outputs:

- Supported / Limited / No Data %;
- median Crowd Exposure;
- P75 Crowd Exposure;
- maximum Crowd Exposure;
- % above preference;
- % Very High;
- optional Local Condition context.

Recommended route Crowd Level:

```text
classify(P75 Network Crowd Exposure)
```

---

## 13. Route Ranking

Current provisional ordering:

1. lower `No Data %`;
2. lower `% above preference`;
3. lower P75 Network Crowd Exposure;
4. lower maximum Network Crowd Exposure;
5. shorter duration.

This is deliberately configurable because the final trade-off must be tested with users rather than inferred from pedestrian-count data.
