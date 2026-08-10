# Realtime Ingestion and Processing Specification — Final V3

## 1. Polling

### Minute pedestrian source

```text
poll every 15 minutes
```

The source records are minute-level. The polling interval is not the measurement unit.

### Sensor metadata

Recommended daily refresh/upsert.

### Historical hourly data

Scheduled refresh/upsert using:

```text
(Location_ID, Sensing_Date, HourDay)
```

as the natural key.

---

## 2. Raw Minute Ingestion

For every source row:

1. normalise timestamp;
2. ensure sensor master exists;
3. calculate deterministic payload hash;
4. insert exact-new raw row;
5. suppress exact repeated payloads from repeated polling;
6. preserve distinct payloads sharing the same logical timestamp.

Do not use:

```text
(Location_ID, Sensing_DateTime)
```

as the raw primary key.

---

## 3. Conflict Handling

Conflict:

```text
same Location_ID
same Sensing_DateTime
different payload
```

Conflicted rows remain in raw storage but are excluded from current aggregates.

Never silently:

```text
sum
average
pick one
```

---

## 4. Timezone

Use:

```text
Australia/Melbourne
```

for:

- Day_Type;
- HourDay;
- 15-minute window boundaries;
- complete-hour boundaries.

Do not hard-code UTC+10.

---

## 5. Complete 15-Minute Window

```text
window_end =
floor(current Melbourne time to 15-minute boundary)

window_start =
window_end - 15 minutes
```

Use:

```text
[window_start, window_end)
```

---

## 6. Final V3 No-Record Rule

After conflict exclusion:

### At least one valid row

```text
data_state = OK
current_15m_count = SUM(valid rows)
```

### Zero valid rows for the entire complete window

```text
data_state = AMBIGUOUS_NO_RECORD
current_15m_count = NULL
current_15m_network_percentile = NULL
```

The sensor is excluded from the current Network ranking.

Do not interpret the whole-window absence as zero pedestrian activity.

---

## 7. Why No Sensor-Specific Stale Threshold Is Used

V3B tested the operational impact of candidate no-row durations:

| Candidate threshold | Sensors whose max gap reached it |
|---:|---:|
| 30 min | 50% |
| 60 min | 32% |
| 90 min | 23% |
| 120 min | 14% |
| 180 min | 11% |
| 240 min | 9% |
| 360 min | 6% |

These are gap durations, not verified outage labels.

Therefore the MVP does **not** infer:

```text
sensor has no rows for N minutes
→ sensor is definitely stale/broken
```

`STALE` is reserved for an operational source/cache freshness failure, such as the current data pipeline no longer refreshing successfully.

Its SLA threshold belongs to deployment/monitoring configuration rather than the pedestrian crowd algorithm.

---

## 8. Current Network Crowd Exposure

For one complete 15-minute window:

1. select eligible Outdoor sensors;
2. retain only `OK` sensors;
3. calculate each sensor's current 15-minute count;
4. rank those current counts across the observed eligible sensors;
5. store:

```text
current_15m_network_percentile
current_crowd_exposure_score
current_crowd_level
```

V3 identity:

```text
current_crowd_exposure_score
=
current_15m_network_percentile
```

---

## 9. Previous Complete-Hour Historical Context

Where sufficient minute data exist:

```text
previous complete clock hour
→ aggregate minute observations
→ one-hour Network historical percentile
→ one-hour Local historical percentile
```

Store separately:

```text
current_1h_network_historical_percentile
current_1h_local_historical_percentile
current_local_condition
```

Do not:

- compare 15-minute total directly with hourly history;
- combine Network and Local using MAX;
- silently replace missing live 15-minute Crowd Exposure with the previous-hour metric.

---

## 10. Local Baseline Relocation Rules

When calculating Local historical percentile:

### Location 14

```text
allow audited 2024–2026 rows
```

because the explicit relocation date is 2019-10-02.

### Location 37

```text
exclude:
2024-08-08
2024-08-09
2024-08-10
2024-08-11

allow:
2024-08-12 onward
```

### Location 47

```text
do not publish Local Condition
until physical move date is manually verified
```

### Location 181

```text
do not publish Local Condition
until physical move date is verified
```

These rules do not require deleting otherwise valid count observations from Network historical distributions.

---

## 11. Baseline Refresh

V5 and V5B support the Local and Network historical structures.

Rebuild baseline summaries periodically after historical data refresh.

Do not recalculate the complete historical baselines every 15 minutes.

---

## 12. Current Sensor Materialisation

After each successful ingestion cycle:

1. determine latest complete 15-minute window;
2. assign current data state;
3. compute current Network percentile for `OK` Outdoor sensors;
4. classify Crowd Level;
5. reconstruct previous complete hour where possible;
6. calculate Network historical context;
7. calculate Local historical context only where Local baseline is eligible;
8. classify Local Condition;
9. upsert `current_sensor_activity`.

---

## 13. Monitoring

Record:

```text
last successful source pull
last successful score build
rows received
rows inserted
exact duplicates skipped
conflicts detected
count of OK sensors
count of AMBIGUOUS_NO_RECORD sensors
```

Operational monitoring may also report `STALE` when the source/cache exceeds the deployment freshness SLA.

That SLA is not part of the crowd-model thresholds.
