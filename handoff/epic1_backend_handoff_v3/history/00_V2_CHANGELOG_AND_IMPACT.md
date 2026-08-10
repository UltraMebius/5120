# V2 Change Impact Audit

## Purpose

This document identifies exactly which files from the original backend handoff are affected by the V1–V6 validation results and what changed.

The V2 package preserves the original walking-only scope, dataset boundaries, 300 m spatial-support logic, PostgreSQL/PostGIS architecture, ingestion design, and external API choices unless the new evidence directly affects them.

## New Evidence Used

- `V1_spatial_weighting_comparison.csv`
- `V2_dual_score_aggregation_summary.csv`
- `V2_largest_local_network_disagreements.csv`
- `V3_realtime_window_presence_summary.csv`
- `V3_realtime_sensor_window_matrix.csv`
- `V4_relocation_impact_summary.csv`
- `V5_temporal_holdout_summary.csv`
- `V5_temporal_holdout_by_group.csv`
- `V6_landmark_coverage_summary.csv`
- `V6_landmark_outdoor_sensor_coverage.csv`

## Original Files Requiring Replacement

| Original file | Why it is affected |
|---|---|
| `00_README.md` | Old README states MAX(Local, Network) and inverse-distance weighting |
| `01_SCOPE_AND_DECISIONS.md` | Core score semantics and spatial weighting changed |
| `02_CROWD_ALGORITHM_SPEC.md` | MAX score must be removed; Network and Local outputs must be separated |
| `03_SPATIAL_SUPPORT_300M.md` | 300 m remains, but weighting evidence and the changed scoring target need an addendum |
| `04_IMPLEMENTATION_CONFIG.yaml` | Machine-readable scoring/weighting/status values changed |
| `05_DATABASE_SCHEMA.sql` | Old schema stores conservative/MAX fields instead of separate Network Crowd Exposure and Local Condition |
| `06_ERD_LATEST.md` | ERD must match revised schema |
| `07_ERD_LATEST.dbml` | DBML must match revised schema |
| `08_REALTIME_INGESTION_SPEC.md` | V3 changes no-record handling and MAX is removed |
| `09_INTERNAL_API_OPENAPI.yaml` | API must expose Crowd Exposure and Local Condition separately |
| `11_BACKEND_ACCEPTANCE_CRITERIA.md` | ACs must enforce Network-based Crowd Level and V3 no-record rule |
| `12_BACKEND_TEST_PLAN.md` | Tests must cover Gaussian weighting, V2 counterexample, and no-record state |
| `13_UNCERTAINTIES_AND_VALIDATION.md` | V1–V6 statuses changed |
| `15_DEVELOPER_IMPLEMENTATION_ORDER.md` | Implementation steps must use revised model |
| `16_ENV_EXAMPLE` | Weighting configuration changes |
| `fixtures/README.md` | Fixture semantics change |
| `fixtures/point_response_examples.json` | Response fields change |
| `validation/validation_tasks.ipynb` | Original V4 parser is flawed; final Network target needs new regression checks; V7 should skip cleanly |

## Original Files Not Requiring Content Changes

| File | Reason |
|---|---|
| `10_EXTERNAL_APIS.md` | V1–V6 do not alter the selected external APIs |
| `14_ARCHITECTURE.md` | Overall ingestion → DB → scoring → spatial → routing architecture is unchanged |
| `17_docker-compose.yml` | PostGIS development environment is unchanged |
| `fixtures/minute_conflict_example.json` | Minute conflict semantics are unchanged |
| `fixtures/route_evaluation_request.json` | Route request shape remains usable |

## Key V2 Decisions

### 1. Reject MAX(Local, Network) as Crowd Level

V2 showed that `MAX(Local, Network)` strongly inflates upper categories:

- High: **22.76%**
- Very High: **17.60%**
- High + Very High: **40.35%**

Concrete real-data counterexample:

```text
Location_ID = 124
Total_of_Directions = 1
Local percentile = 100
Network percentile = 0.644792
MAX = 100
```

Using MAX would label one observed movement as `VERY_HIGH`.

Therefore:

- **Network percentile** is the primary Crowd Exposure measure.
- **Local percentile** remains a separate “compared with usual here” indicator.
- Local unusualness must not automatically escalate Crowd Level.

### 2. Spatial weighting

At 300 m, V1 produced:

| Method | MAE | RMSE | Median AE |
|---|---:|---:|---:|
| Equal | **17.288** | **22.518** | 13.767 |
| Gaussian σ=150 m | 17.316 | 22.567 | **13.731** |
| 1/d | 17.472 | 22.789 | 13.805 |
| 1/d² | 17.868 | 23.369 | 13.944 |
| Nearest | 19.367 | 25.536 | 14.873 |

Equal weighting had the minimum MAE, but Gaussian σ=150 m had virtually identical error while preserving spatial decay. It is therefore the current **MVP default**.

Important sequencing note: V1 used the previous combined/MAX target. Since V2 changes the primary target to Network percentile, V1B must re-run radius/weighting cross-validation on the final Network target before production freeze.

### 3. Realtime no-record handling

V3 showed:

- median zero-row 15-minute window rate: **3.41%**
- 38/100 Outdoor sensors: at least 10%
- 21/100: at least 20%
- 10/100: at least 30%
- 3/100: at least 50%
- Sensor 108: **100% zero-row windows** in the observed snapshot

Therefore a whole 15-minute window with no rows must **not** be converted to zero crowd.

V2 rule:

```text
whole complete 15m window has zero rows
→ AMBIGUOUS_NO_RECORD
→ exclude from current Network ranking
```

An exact transition from `AMBIGUOUS_NO_RECORD` to `STALE` remains an operational uncertainty.

### 4. Relocation parser correction

The original V4 parser selected the first date in a note. This fails for multi-event notes.

Example:

```text
Sensor 37:
Pushbox Upgrade, 30/06/2023.
Move from 174 to 260 Lygon Street (12/08/2024)
```

The movement-associated date is **12/08/2024**, not 30/06/2023.

The revised validation notebook uses phrase-aware date association and leaves ambiguous associations for manual review.

### 5. Historical baseline temporal support

V5 chronological holdout:

- training: 2024-08-08 to 2026-02-07
- holdout: 2026-02-08 to 2026-08-07
- scoreable holdout: **99.30%**
- ≤P25: **25.70%**
- ≤P50: **49.26%**
- ≤P75: **71.93%**
- ≤P90: **86.50%**
- mean percentile: **51.10**
- median percentile: **50.96**

This strongly supports the `Location_ID × HourDay × Day_Type` Local baseline while showing some upper-tail drift. The baseline should be periodically rebuilt.

A separate V5B Network holdout is added because Network percentile is now more important.

### 6. Landmark/POI support

V6 using Outdoor sensors:

- Supported (≤250 m): **114 / 242 = 47.11%**
- Limited (250–300 m): **11 / 242 = 4.55%**
- No Data (>300 m): **117 / 242 = 48.35%**

This is **POI coverage only**, not route coverage or CBD land-area coverage.
