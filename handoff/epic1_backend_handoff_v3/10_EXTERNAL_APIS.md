# External APIs

Verified against official service documentation/pages on 2026-08-10.

## 1. City of Melbourne Open Data — Explore API v2.1

Base:

```text
https://data.melbourne.vic.gov.au/api/explore/v2.1
```

The official Explore API supports REST `GET` access to dataset records and exports.

General records pattern:

```text
GET /catalog/datasets/{dataset_id}/records
```

Useful query parameters include:

```text
select
where
group_by
order_by
limit
offset
timezone
```

For bulk ingestion/export:

```text
GET /catalog/datasets/{dataset_id}/exports/csv
GET /catalog/datasets/{dataset_id}/exports/parquet
```

### Realtime minute pedestrian data

Dataset ID:

```text
pedestrian-counting-system-past-hour-counts-per-minute
```

Records endpoint:

```text
https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/pedestrian-counting-system-past-hour-counts-per-minute/records
```

Official dataset notes:

- minute-by-minute directional pedestrian counts;
- source refresh approximately every 15 minutes;
- a row may be absent for a sensor/minute when no pedestrians passed;
- sensor-location changes matter for interpretation.

### Historical hourly pedestrian data

Dataset ID:

```text
pedestrian-counting-system-monthly-counts-per-hour
```

Records endpoint:

```text
https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/pedestrian-counting-system-monthly-counts-per-hour/records
```

Use the project-audited natural key:

```text
Location_ID + Sensing_Date + HourDay
```

Do not use source `ID` as a database PK.

### Sensor locations

Dataset ID:

```text
pedestrian-counting-system-sensor-locations
```

Records endpoint:

```text
https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/pedestrian-counting-system-sensor-locations/records
```

The live sensor table is dynamic. Do not hard-code the number of sensors.

### Landmarks / POI

Dataset ID:

```text
landmarks-and-places-of-interest-including-schools-theatres-health-services-spor
```

Records endpoint:

```text
https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/landmarks-and-places-of-interest-including-schools-theatres-health-services-spor/records
```

Use as POI/orientation context only.

---

## 2. Walking Routing — openrouteservice

Recommended external routing option:

```text
openrouteservice Directions Service
```

Public API host:

```text
https://api.openrouteservice.org
```

Walking GeoJSON endpoint pattern:

```text
POST /v2/directions/foot-walking/geojson
```

Typical full endpoint:

```text
https://api.openrouteservice.org/v2/directions/foot-walking/geojson
```

Public API use requires an API key.

Coordinates are sent in:

```text
[longitude, latitude]
```

The service returns route geometry and route summary information.

### Candidate alternatives

openrouteservice supports an `alternative_routes` request object and the service configuration supports up to three alternatives.

A commonly documented request form is:

```json
{
  "coordinates": [
    [144.9631, -37.8136],
    [144.9712, -37.8080]
  ],
  "alternative_routes": {
    "target_count": 3,
    "share_factor": 0.6,
    "weight_factor": 2
  }
}
```

Because public service behaviour/configuration can change, verify the exact request in the current openrouteservice API Playground before production deployment.

### Recommended architecture

Use openrouteservice only to obtain valid walking route geometries and duration/distance.

Do **not** use its optional `quiet` or `noise` routing features as substitutes for this project's pedestrian-sensor crowd model.

Processing sequence:

```text
origin + destination
→ openrouteservice walking candidate geometries
→ this project's crowd engine
→ route crowd metrics
→ crowd-preference ranking
```

---

## 3. Source Documentation

City of Melbourne API console:

```text
https://data.melbourne.vic.gov.au/api-console/explore/v2.1/
```

openrouteservice Directions documentation:

```text
https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/
```
