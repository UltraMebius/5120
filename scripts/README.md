# Data ingestion and evaluation scripts

Run scripts from the repository root with the configured Python environment.
Any command that writes data should first be reviewed against the target
database and run with `--dry-run` when supported.

## Database and ingestion

`process_data.py` is a retained no-op placeholder. It does not download,
transform, or score City of Melbourne data.

`check_database.py` is a read-only PostgreSQL/PostGIS readiness check. It
verifies connectivity, versions, and authoritative public tables; it never
creates schema objects or loads data.

`import_sensor_locations.py` imports current sensor metadata. `--dry-run`
inspects and validates live City JSON without writes. A normal run
transactionally upserts only `sensor` and `sensor_location_current`.

`import_hourly_counts.py` is the bounded historical-hour importer. Start and end
dates are mandatory. The approved baseline training window is `2024-08-10`
through `2026-02-07` inclusive. It streams server-filtered official CSV,
preserves zero counts, reports unknown historical IDs, and upserts known-sensor
rows in batches. Split a long import into explicit non-overlapping date ranges
and verify each run before continuing.

`build_historical_baselines.py` always uses the approved frozen training
window. `--dry-run` checks source coverage and model eligibility without
writes. A normal run transactionally replaces only
`sensor_hour_daytype_baseline` and `network_hour_daytype_baseline`, then verifies
keys, statistics, dates, relocation rules, zero participation, and logical
checksums.

`refresh_current_activity.py` is the manual minute refresh. It fetches only the
previous complete hour plus the complete current 15-minute window, stores
exact-new raw payloads, preserves logical conflicts, and transactionally
replaces only `current_sensor_activity`. Use `--dry-run` for a no-write preview
and `--as-of` with an offset-aware ISO timestamp for repeatable checks. The
scheduled production equivalent is documented in
`docs/deployment-guide.md`.

## Read-only evaluation tools

`evaluate_crowd_point.py` accepts WGS84 longitude/latitude, discovers current
sensor support with PostGIS, applies the 250/300 m coverage rule and normalised
inverse-distance weighting, and prints the source window and uncertainty.
`--debug` adds only contributing sensor IDs, metre distances, scores, and
normalised weights. It does not call City/Mapbox or write
`spatial_activity_cache`.

`sample_route_geometry.py` reads an existing GeoJSON `LineString`, applies the
configured route-sampling interval, and prints route length, sample count,
endpoints, and concise spacing. It does not call external services or the
database.

`evaluate_route_crowd.py` loads an existing GeoJSON route, composes route
sampling with `SpatialCrowdService`, and prints support-state counts and endpoint
results. `--details` prints every ordered sample. It does not refresh City data,
call CalmWay over HTTP, aggregate a route score, or write data.

`evaluate_route_ranking.py` is the preference-aware end-to-end ranking
verifier. It fetches real Mapbox walking candidates, evaluates samples, and
prints concise coverage, P75, preference status, rank, and recommendation. It
does not refresh City data, print credentials, or persist route results.

`evaluate_route_crowd_alert.py` passes controlled in-memory evaluations into the
pure look-ahead engine and verifies `ALERT`, `CLEAR`, and
`INSUFFICIENT_DATA`. It does not use GPS, Mapbox, City APIs, HTTP, or the
database.

All ingestion/baseline jobs must preserve the frozen handoff rules, including
exact-payload deduplication, conflict preservation, complete 15-minute windows,
relocation restrictions, and separate network/local percentiles. One-off files
must not replace the PostgreSQL/PostGIS architecture.

See `docs/testing-guide.md` for commands and integration gates, and
`docs/team-guide.md` for database/write safety.
