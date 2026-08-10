# Final Backend Implementation Order — V3

## Phase 1 — Database

Use the unchanged V2 PostgreSQL/PostGIS schema:

```text
05_DATABASE_SCHEMA.sql
```

Load:

- sensors;
- historical hourly facts;
- landmarks.

Derive `Day_Type`.

---

## Phase 2 — Historical Context

Build:

```text
sensor_hour_daytype_baseline
network_hour_daytype_baseline
```

Apply Local relocation eligibility:

```text
14 → allowed
37 → 2024-08-12 onward only
47 → Local disabled
181 → Local disabled
```

Do not remove otherwise valid count observations from Network historical distributions solely because Local move-date history is uncertain.

---

## Phase 3 — Realtime Ingestion

Every 15 minutes:

1. create ingestion run;
2. retrieve minute data;
3. deduplicate exact repeated payloads;
4. preserve logical conflicts;
5. exclude conflicted readings from scoring;
6. assign each sensor:
   - `OK`, or
   - `AMBIGUOUS_NO_RECORD`.

No sensor-specific time-based stale threshold is used.

---

## Phase 4 — Current Network Crowd Exposure

For `OK` Outdoor sensors in the same complete 15-minute window:

```text
current_15m_count
→ Network percentile
→ Crowd Level
```

Store:

```text
current_crowd_exposure_score
=
current_15m_network_percentile
```

---

## Phase 5 — Separate Historical Context

Where the previous complete hour is reconstructable:

```text
1h count
→ Network historical percentile
→ Local historical percentile if eligible
→ Local Condition
```

No MAX combination.

---

## Phase 6 — Spatial Engine

Final configuration:

```text
max radius = 300 m
core radius = 250 m
weighting = inverse distance 1/d
distance floor = 1 m
```

For each target point:

1. query valid Outdoor sensors within 300 m;
2. classify Supported/Limited/No Data;
3. normalise 1/d weights;
4. aggregate Network Crowd Exposure;
5. optionally aggregate Local Condition separately.

---

## Phase 7 — Walking Routing

Integrate walking route service.

Current route sampling:

```text
50 m
```

Keep configurable.

Return route exposure metrics.

---

## Phase 8 — Route Preference / Ranking

Use current configurable preference mapping and provisional ranking.

Do not encode these values as medical truths.

---

## Phase 9 — Optional V7

When real route geometry exists:

```text
run validation/validation_tasks.ipynb
```

to compare 25/50/75/100 m route sampling.

This is the only remaining code validation in the handoff.

---

## Phase 10 — Operational Monitoring

Monitor:

- source ingestion success;
- current cache freshness;
- scoring freshness;
- conflicts;
- current `OK` / `AMBIGUOUS_NO_RECORD` counts;
- routing failures.

Use `STALE` only for source/cache freshness failures according to deployment SLA.
