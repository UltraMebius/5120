# Crowd Algorithm Specification — Final V3

## 1. Historical Facts

Hourly natural key:

```text
(Location_ID, Sensing_Date, HourDay)
```

Source `ID` is retained for traceability only.

Derive:

```text
Day_Type =
Weekday if dayofweek(Sensing_Date) < 5
Weekend otherwise
```

---

## 2. Local Historical Percentile

Reference:

```text
Location_ID × HourDay × Day_Type
```

For one-hour count `x`:

```text
LocalPercentile =
100 × count(reference values <= x)
      / count(reference values)
```

Use:

```text
LocalPercentile
→ Local Condition only
```

Do not use it as the primary Crowd Level.

### Local-baseline relocation filter

Before calculating Local reference arrays:

```text
Location 37:
drop 2024-08-08 through 2024-08-11

Location 47:
do not build/publish Local baseline until move date verified

Location 181:
do not build/publish Local baseline until move date verified
```

Location 14's documented relocation predates the audited hourly range, so its Local history in the audited range is usable.

---

## 3. Network Historical Percentile

Reference:

```text
HourDay × Day_Type
across eligible monitored observations
```

For one-hour count `x`:

```text
NetworkHistoricalPercentile =
100 × count(network reference values <= x)
      / count(network reference values)
```

V5B confirms good chronological calibration.

This is historical Network Crowd Exposure context.

---

## 4. Current 15-Minute Network Crowd Exposure

### Complete window

```text
window_end =
floor(current Melbourne time to 15-minute boundary)

window_start =
window_end - 15 minutes
```

### Sensor state

After removing conflicted logical readings:

```text
>=1 valid row in complete sensor window
→ OK

0 valid rows in complete sensor window
→ AMBIGUOUS_NO_RECORD
```

Do not convert `AMBIGUOUS_NO_RECORD` into zero.

### Current count

For `OK` sensor:

```text
Current15mCount =
SUM(valid Total_of_Directions rows)
```

### Current Network percentile

Across `OK` eligible Outdoor sensors in the same complete window:

```text
Current15mNetworkPercentile =
empirical/rank percentile of Current15mCount
```

This is the primary live Crowd Exposure score:

```text
current_crowd_exposure_score
=
current_15m_network_percentile
```

---

## 5. Crowd Level

Apply to Network Crowd Exposure:

```text
<=25       → VERY_LOW
>25–50     → LOW
>50–75     → MODERATE
>75–90     → HIGH
>90        → VERY_HIGH
```

---

## 6. Local Condition

Apply to Local Historical Percentile:

```text
<=25       → MUCH_QUIETER_THAN_USUAL
>25–50     → QUIETER_THAN_USUAL
>50–75     → TYPICAL
>75–90     → BUSIER_THAN_USUAL
>90        → MUCH_BUSIER_THAN_USUAL
```

Do not combine Local and Network using MAX or a hidden escalation rule.

---

## 7. Spatial Point Estimation

Eligible route-support sensors:

```text
Location_Type = Outdoor
valid score for the metric being estimated
distance <= 300 m
```

Coverage:

```text
nearest valid sensor <= 250 m
→ SUPPORTED

250–300 m
→ LIMITED

>300 m or no valid score within 300 m
→ NO_DATA
```

### Final weighting

V1B confirms inverse-distance weighting at the adopted 300 m radius:

```text
w_i = 1 / max(d_i, 1 m)
```

Normalise:

```text
PointScore =
SUM(w_i × SensorScore_i)
/
SUM(w_i)
```

### Crowd Exposure point score

```text
SensorScore_i =
current_15m_network_percentile_i
```

### Local Condition point score

```text
SensorScore_i =
current_1h_local_historical_percentile_i
```

Never sum raw counts across spatially separate sensors.

---

## 8. Why 300 m Is Still Final

Using final Network-target 1/d validation:

```text
250m:
coverage 87.73%
MAE 17.0623

300m:
coverage 92.98%
MAE 17.2364

475m:
coverage 99.59%
MAE 16.7946
```

The 475 m model achieves better numerical coverage/error, but at the cost of a 58.3% larger spatial radius than 300 m.

Because the product estimates **local walking exposure**, the project deliberately limits spatial extrapolation.

300 m therefore remains the final maximum support radius.

---

## 9. Realtime Staleness

Do not infer a sensor outage from the duration of no-row windows.

V3B showed that candidate gap thresholds would classify many sensors as stale without proving actual device failure.

Final MVP:

```text
sensor no-row window
→ AMBIGUOUS_NO_RECORD
```

`STALE` is used only if the **source/current cache itself** fails an operational freshness requirement.

The freshness SLA is an operational configuration, not a crowd-model threshold.

---

## 10. Previous Complete-Hour Context

Where sufficient minute data are available:

```text
previous complete clock hour
→ aggregate one-hour count
→ Network historical percentile
→ Local historical percentile
```

Return separately.

Do not silently use it as a substitute for missing live 15-minute Crowd Exposure.

---

## 11. Route Scoring

Resample route geometry at equal distances.

MVP config:

```text
50 m
```

pending V7.

At every route sample:

```text
crowd_exposure_score
crowd_level
local_condition_score
local_condition
coverage_status
nearest_sensor_distance_m
supporting_sensor_count
```

Route metrics:

```text
supported_pct
limited_pct
no_data_pct

median_crowd_exposure_score
p75_crowd_exposure_score
maximum_crowd_exposure_score

pct_above_preference
pct_very_high
```

Recommended summary:

```text
route_crowd_level =
classify(P75 crowd exposure)
```

---

## 12. User Preferences

Configurable MVP mapping:

```text
AVOID_BUSY      <= 50
PREFER_QUIETER  <= 75
FLEXIBLE        <= 90
```

Apply to Network Crowd Exposure only.

Do not interpret the selected preference as medical severity.

---

## 13. Data / Error States

```text
OK
AMBIGUOUS_NO_RECORD
STALE
CONFLICTED
NO_DATA
ROUTING_SERVICE_ERROR
SOURCE_API_ERROR
```

`STALE` is source/cache freshness-related, not a sensor no-row-duration classification.

Any failure/uncertainty state must remain explicit and must never be converted into `VERY_LOW` or `LOW`.
