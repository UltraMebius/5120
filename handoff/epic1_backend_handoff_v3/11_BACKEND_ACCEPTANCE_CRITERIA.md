# Backend Acceptance Criteria — Final V3

## AC-B01 — Hourly key

**Given** hourly rows are loaded,  
**When** they are stored,  
**Then** `(Location_ID, Sensing_Date, HourDay)` must be unique and source `ID` must not be the database PK.

## AC-B02 — Day type

**Given** a valid date,  
**When** historical context is prepared,  
**Then** `Day_Type` must be `Weekday` or `Weekend`.

## AC-B03 — Minute exact-repeat handling

**Given** an identical minute payload is returned by repeated polling,  
**When** it is ingested again,  
**Then** it must not be inserted twice.

## AC-B04 — Minute conflict preservation

**Given** distinct payloads share the same `(Location_ID, Sensing_DateTime)`,  
**When** they are ingested,  
**Then** all raw payloads must be preserved and the logical key must be flagged as conflicted.

## AC-B05 — Conflict exclusion

**Given** a logical minute key is conflicted,  
**When** current metrics are calculated,  
**Then** the conflicted logical readings must not enter the processed aggregate.

## AC-B06 — Primary Crowd Exposure

**Given** a valid Network percentile exists,  
**When** Crowd Level is produced,  
**Then** Crowd Level must be based on Network percentile and not `MAX(Local, Network)`.

## AC-B07 — Local Condition separate

**Given** Local percentile is high while Network percentile is low,  
**When** the backend responds,  
**Then** Crowd Level must remain based on Network percentile and Local Condition must be returned separately.

## AC-B08 — Final spatial weighting

**Given** multiple valid Outdoor sensors lie within 300 m,  
**When** a point score is calculated,  
**Then** the system must apply normalised inverse-distance weighting:

```text
w_i = 1 / max(distance_i, 1 m)
```

and must not sum raw counts.

## AC-B09 — Supported radius

**Given** the nearest valid Outdoor sensor is ≤250 m,  
**When** a point is evaluated,  
**Then** `coverageStatus = SUPPORTED`.

## AC-B10 — Limited radius

**Given** the nearest valid Outdoor sensor is >250 m and ≤300 m,  
**When** a point is evaluated,  
**Then** `coverageStatus = LIMITED`.

## AC-B11 — No Data radius

**Given** no valid Outdoor sensor score exists within 300 m,  
**When** a point is evaluated,  
**Then** `coverageStatus = NO_DATA` and no Low/Very Low classification may be fabricated.

## AC-B12 — Whole-window no-row state

**Given** a sensor has zero valid rows in the entire complete 15-minute window,  
**When** current scoring runs,  
**Then**:
- `dataState = AMBIGUOUS_NO_RECORD`;
- current count = `NULL`;
- current Network percentile = `NULL`;
- the sensor is excluded from current Network ranking.

## AC-B13 — No sensor-specific stale timer

**Given** a sensor has repeated `AMBIGUOUS_NO_RECORD` windows,  
**When** MVP crowd scoring runs,  
**Then** it must not automatically become `STALE` solely because a fixed no-row duration has elapsed.

## AC-B14 — Source/cache stale

**Given** the current source/cache exceeds the deployment freshness SLA,  
**When** the backend serves current data,  
**Then** it may return `STALE` according to operational monitoring configuration.

## AC-B15 — 15-minute vs hourly time scale

**Given** a current 15-minute total,  
**When** historical context is calculated,  
**Then** the 15-minute total must not be directly compared with the hourly historical distribution.

## AC-B16 — Complete-hour context

**Given** sufficient minute rows are available,  
**When** one-hour historical context is calculated,  
**Then** a complete clock hour must be reconstructed before Network/Local historical percentile calculation.

## AC-B17 — Location 37 Local baseline

**Given** Location 37 Local history is built,  
**When** the baseline is generated,  
**Then** rows dated 2024-08-08 through 2024-08-11 must be excluded and Local history must begin from 2024-08-12.

## AC-B18 — Location 47 Local Condition

**Given** Location 47's physical move date remains unverified,  
**When** Local Condition is requested,  
**Then** Local Condition must be unavailable rather than calculated from potentially mixed-location history.

## AC-B19 — Location 181 Local Condition

**Given** Location 181's move date is unavailable,  
**When** Local Condition is requested,  
**Then** Local Condition must be unavailable.

## AC-B20 — Network history retains valid counts

**Given** valid historical count rows belong to sensors with uncertain move dates,  
**When** Network historical distribution is constructed,  
**Then** those valid counts may remain because Network percentile does not require stable per-sensor location identity.

## AC-B21 — Crowd bands

**Given** a valid Network Crowd Exposure score,  
**When** it is classified,  
**Then**:
- `<=25 → VERY_LOW`
- `>25–50 → LOW`
- `>50–75 → MODERATE`
- `>75–90 → HIGH`
- `>90 → VERY_HIGH`.

## AC-B22 — Route sampling

**Given** a route geometry,  
**When** route exposure is evaluated,  
**Then** it must be sampled by equal distance rather than by count of nearby sensors.

## AC-B23 — Preference meaning

**Given** a user selects a preference,  
**When** it is applied,  
**Then** it must alter route comparison using Network Crowd Exposure and must not be represented as a medical diagnosis.

## AC-B24 — Failure states

**Given** source/routing data are unavailable or unsupported,  
**When** the backend responds,  
**Then** uncertainty/error must remain explicit and must not be converted into Low crowd.
