# Epic 1 Backend Handoff — Crowd-Aware Walking Route Planning (Final V3)

## Purpose

This is the final backend/data implementation handoff for the walking-only Epic 1 MVP.

V3 incorporates the completed V1B, V3B, V4B and V5B evidence and removes completed validation tasks from the implementation critical path.

Frontend/Figma work is intentionally out of scope.

## Final Product Scope

The system supports:

- walking route candidate generation through an external routing service;
- current pedestrian Crowd Exposure estimation;
- route-level Crowd Exposure comparison;
- explicit `SUPPORTED / LIMITED / NO_DATA` spatial coverage;
- a separate Local Condition indicator showing whether a location is busier/quieter than its own historical norm;
- user-selected crowd-avoidance preferences.

It does not claim to measure:

- persons/m² physical density;
- occupancy;
- clinical sensory tolerance;
- sensory safety;
- noise, construction or visual stimulation;
- public-transport crowding/routing.

## Final Core Decisions

### Crowd semantics

```text
Network percentile
→ primary Crowd Exposure / Crowd Level

Local historical percentile
→ separate Local Condition

MAX(Local, Network)
→ rejected
```

### Historical context

```text
Local:
Location_ID × HourDay × Day_Type

Network:
HourDay × Day_Type across eligible monitored observations

Day_Type:
Weekday / Weekend
```

V5 and V5B provide chronological holdout support for these structures.

### Crowd bands

```text
0–25      → VERY_LOW
>25–50    → LOW
>50–75    → MODERATE
>75–90    → HIGH
>90–100   → VERY_HIGH
```

These are statistical relative pedestrian-activity bands, not medical thresholds.

### Spatial support

```text
0–250 m    → SUPPORTED
250–300 m  → LIMITED
>300 m     → NO_DATA
```

Maximum radius: **300 m**.

### Final spatial weighting

V1B used the final Network percentile target.

At 300 m, `1/d` produced the lowest MAE and RMSE among the tested methods.

```text
w_i = 1 / max(distance_i, 1 m)
```

Weights are normalised across valid supporting sensors.

### Realtime no-record handling

```text
>=1 valid row in complete 15m window
→ OK

0 valid rows in complete 15m window
→ AMBIGUOUS_NO_RECORD
→ no current Crowd Exposure score
→ exclude from current Network ranking
```

No sensor-specific time-based stale threshold is used in MVP.

`STALE` is reserved for source/cache freshness failures detected operationally.

### Relocation handling for Local Condition

```text
Location 14
→ Local history usable in audited window.

Location 37
→ exclude 2024-08-08 through 2024-08-11;
   Local baseline starts 2024-08-12.

Location 47
→ Local Condition disabled until move date verified.

Location 181
→ Local Condition disabled until move date verified.
```

These restrictions do not require removing the count observations from the broader Network distribution.

### Route sampling

```text
50 m
```

remains the MVP configuration value, but is provisional until V7 can be run using real walking routes.

## Files

| File | Purpose |
|---|---|
| `00_V3_CHANGELOG_AND_IMPACT.md` | Exact V2→V3 evidence and change audit |
| `01_SCOPE_AND_DECISIONS.md` | Final implementation rules |
| `02_CROWD_ALGORITHM_SPEC.md` | Final backend scoring logic |
| `03_SPATIAL_SUPPORT_300M.md` | Final 300 m + 1/d spatial methodology |
| `04_IMPLEMENTATION_CONFIG.yaml` | Machine-readable final configuration/status |
| `05_DATABASE_SCHEMA.sql` | PostgreSQL/PostGIS schema |
| `06_ERD_LATEST.md` | ERD — Mermaid |
| `07_ERD_LATEST.dbml` | ERD — DBML |
| `08_REALTIME_INGESTION_SPEC.md` | Realtime ingestion and data-state logic |
| `09_INTERNAL_API_OPENAPI.yaml` | Backend API contract |
| `10_EXTERNAL_APIS.md` | External API references |
| `11_BACKEND_ACCEPTANCE_CRITERIA.md` | Given–When–Then backend ACs |
| `12_BACKEND_TEST_PLAN.md` | Backend tests/regression tests |
| `13_UNCERTAINTIES_AND_VALIDATION.md` | Only genuinely remaining non-blocking items |
| `14_ARCHITECTURE.md` | Backend architecture |
| `15_DEVELOPER_IMPLEMENTATION_ORDER.md` | Final implementation order |
| `16_ENV_EXAMPLE` | Environment/config template |
| `17_docker-compose.yml` | PostGIS development DB |
| `validation/validation_tasks.ipynb` | Only remaining code validation: V7 route sampling |
| `evidence/` | V1–V6 + V1B/V3B/V4B/V5B evidence |
| `fixtures/` | Synthetic backend test fixtures |

## Developer Rule

Anything marked `confirmed` or `adopted` in `04_IMPLEMENTATION_CONFIG.yaml` can be implemented now.

Remaining user/product validation items must stay configurable rather than being hard-coded as clinical truths.
