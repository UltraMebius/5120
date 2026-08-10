# V3 Final Handoff — Change Impact Audit

## Purpose

V3 is the final backend/data handoff based on the completed V1B, V3B, V4B and V5B results.

It is built directly from V2. Files not affected by the new evidence are preserved from V2 rather than rewritten.

## Final New Evidence

### V1B — Final Network-target spatial validation

At the already adopted 300 m radius:

| Method | Coverage | MAE | RMSE | Median AE |
|---|---:|---:|---:|---:|
| **1/d** | 92.98% | **17.2364** | **21.9956** | 14.1196 |
| Gaussian σ=150 m | 92.98% | 17.3453 | 22.1058 | 14.3178 |
| Equal | 92.98% | 17.5218 | 22.3740 | 14.4313 |
| 1/d² | 92.98% | 17.5362 | 22.4895 | **14.0273** |
| Nearest | 92.98% | 18.7329 | 24.3699 | 14.4892 |

The final target is **Network percentile**, so this result supersedes the earlier V1 weighting comparison that used the rejected MAX target.

Final spatial weighting:

```text
inverse-distance weighting
w_i = 1 / max(d_i, 1 m)
```

At 300 m, 1/d has the best MAE and RMSE among the tested methods.

### Radius remains 300 m

Using 1/d on the final Network target:

```text
250 m:
coverage 87.73%
MAE 17.0623
RMSE 21.9694

300 m:
coverage 92.98%
MAE 17.2364
RMSE 21.9956

475 m:
coverage 99.59%
MAE 16.7946
RMSE 21.0813
```

250→300 m gains about **5.26 percentage points** of predictive support with only about **0.174 MAE points** additional error.

475 m improves numerical error and coverage, but requires a **58.3% larger radius than 300 m** and materially weakens locality. The project retains 300 m because this is a local walking-exposure estimator, not a CBD-wide smoothing model.

Final spatial rule:

```text
0–250 m    → SUPPORTED
250–300 m  → LIMITED
>300 m     → NO_DATA
```

### V3B — No sensor-specific stale threshold

The descriptive gap analysis shows that arbitrary no-row duration cut-offs would label substantial numbers of sensors as stale:

| Candidate gap | Sensors reaching/exceeding it |
|---:|---:|
| 30 min | 50% |
| 60 min | 32% |
| 90 min | 23% |
| 120 min | 14% |
| 180 min | 11% |
| 240 min | 9% |
| 360 min | 6% |

These data do not identify which gaps are actual outages.

Final MVP rule:

```text
complete 15m window has >=1 valid row
→ OK

complete 15m window has 0 valid rows
→ AMBIGUOUS_NO_RECORD
→ exclude from current Network ranking
```

No sensor-specific `STALE_AFTER_N_MINUTES` rule is used in MVP.

`STALE` is reserved for source/cache freshness failures determined by operational monitoring, not inferred from a sensor's no-row duration.

### V4B — Relocation handling

Phrase-aware review produced:

- **Location 14** — explicit relocation 2019-10-02, before the audited hourly window.
- **Location 37** — physical move date correctly associated with **2024-08-12**.
- **Location 47** — date remains ambiguous relative to the move phrase.
- **Location 181** — moved-from note has no associated date.

Final Local-baseline rule:

```text
Location 14
→ Local baseline allowed for audited 2024–2026 window.

Location 37
→ exclude 2024-08-08 through 2024-08-11 from its Local baseline;
   use observations from 2024-08-12 onward.

Location 47
→ do not publish Local Condition until the move date is manually verified.

Location 181
→ do not publish Local Condition until the move date is verified.
```

These restrictions apply to **Local Condition**, because Local percentile assumes a stable physical location.

They do not require deleting those valid count observations from the broader Network percentile distribution.

### V5B — Network historical stability confirmed

Chronological holdout:

- training: 2024-08-08 → 2026-02-07
- holdout: 2026-02-08 → 2026-08-07
- scored holdout: **403,318 / 403,318 = 100%**

Observed Network percentile calibration:

| CDF threshold | Holdout result |
|---|---:|
| ≤P25 | **25.057%** |
| ≤P50 | **49.911%** |
| ≤P75 | **74.348%** |
| ≤P90 | **90.119%** |
| Mean percentile | **50.284** |
| Median percentile | **50.124** |

This is very close to the expected empirical percentile distribution.

Therefore:

```text
Network percentile
→ confirmed primary Crowd Exposure metric
```

The statistical crowd bands:

```text
0–25      VERY_LOW
>25–50    LOW
>50–75    MODERATE
>75–90    HIGH
>90–100   VERY_HIGH
```

are frozen for the MVP as relative pedestrian-activity bands.

They are not clinical sensory thresholds.

## V2 Files Actually Changed in V3

- `00_README.md`
- `01_SCOPE_AND_DECISIONS.md`
- `02_CROWD_ALGORITHM_SPEC.md`
- `03_SPATIAL_SUPPORT_300M.md`
- `04_IMPLEMENTATION_CONFIG.yaml`
- `08_REALTIME_INGESTION_SPEC.md`
- `09_INTERNAL_API_OPENAPI.yaml`
- `11_BACKEND_ACCEPTANCE_CRITERIA.md`
- `12_BACKEND_TEST_PLAN.md`
- `13_UNCERTAINTIES_AND_VALIDATION.md`
- `15_DEVELOPER_IMPLEMENTATION_ORDER.md`
- `16_ENV_EXAMPLE`
- `fixtures/README.md`
- `fixtures/point_response_examples.json`
- `validation/validation_tasks.ipynb`
- `evidence/V1_V6_RESULTS_SUMMARY.md`

## V2 Files Intentionally Preserved Unchanged

The following were not changed because the new results do not alter their structure or purpose:

- `05_DATABASE_SCHEMA.sql`
- `06_ERD_LATEST.md`
- `07_ERD_LATEST.dbml`
- `10_EXTERNAL_APIS.md`
- `14_ARCHITECTURE.md`
- `17_docker-compose.yml`
- `fixtures/minute_conflict_example.json`
- `fixtures/route_evaluation_request.json`

The V2 database schema already separated Network Crowd Exposure from Local Condition and did not hard-code the spatial weighting method, so no schema/ERD rewrite is required.

## Remaining Non-Blocking Items

Only these remain genuinely unresolved:

1. **Route sampling interval** — 50 m remains provisional until real route geometries are available for V7.
2. **Preference mapping** — `AVOID_BUSY / PREFER_QUIETER / FLEXIBLE` requires representative-user/product validation.
3. **Route ranking trade-off** — the relative importance of unknown coverage, crowd reduction and longer walking time requires user/product validation.
4. **Sensor 47 and 181 move dates** — until verified, their Local Condition is disabled.

None of these prevents backend/database implementation.
