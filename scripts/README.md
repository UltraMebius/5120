# Data processing scripts

`process_data.py` remains a Phase 1 no-op. It does not download, transform, or
score City of Melbourne data.

`check_database.py` is the Phase 2A-1 read-only PostgreSQL/PostGIS readiness
check. It verifies connectivity, versions, and the authoritative public tables;
it never creates schema objects or loads data.

`import_sensor_locations.py` is the Phase 2A-2 current sensor metadata importer.
Use `--dry-run` to inspect the live City JSON fields and validation result
without database writes. A normal run transactionally upserts only `sensor` and
`sensor_location_current`.

`import_hourly_counts.py` is the Phase 2A-3 bounded historical-hour importer.
Both dates remain mandatory. Phase 2B freezes the production baseline training
window at `2024-08-10` through `2026-02-07` inclusive. The importer streams a
server-filtered official CSV, preserves zero counts, reports unknown historical
IDs, and upserts known-sensor rows in batches. For the full window, use the
resumable date chunks documented in `docs/hourly-count-ingestion-cn.md`.

`build_historical_baselines.py` is the Phase 2B baseline job. Its dates are not
configurable: it always uses the approved frozen training window. `--dry-run`
performs source coverage and eligibility checks without writes. A normal run
transactionally replaces only `sensor_hour_daytype_baseline` and
`network_hour_daytype_baseline`, then verifies their keys, statistics, dates,
relocation rules, zero participation, and logical checksums.

`refresh_current_activity.py` is the manual Phase 2C minute refresh. It fetches
only the previous complete hour plus the complete current 15-minute window,
stores exact-new raw payloads, preserves logical conflicts, and transactionally
replaces only `current_sensor_activity`. Use `--dry-run` for a no-write preview
and `--as-of` with an offset-aware ISO timestamp for repeatable window checks.
No scheduler or raw retention deletion is introduced in Phase 2C.

`evaluate_crowd_point.py` is the read-only Phase 2D point evaluator. It accepts
WGS84 longitude/latitude, discovers current sensor support with PostGIS,
applies the adopted 250/300 m coverage rule and normalised `1/d` weighting, and
prints the current window and uncertainty explicitly. `--debug` adds only the
contributing sensor IDs, metre distances, scores, and normalised weights. It
does not call the City API, Mapbox, or write `spatial_activity_cache`.

All ingestion and baseline jobs must follow the complete rules in
`handoff/epic1_backend_handoff_v3/`, including exact-payload deduplication,
conflict preservation, complete 15-minute windows, relocation restrictions,
and separate Network and Local percentiles. One-off file processing must not
replace the final PostgreSQL/PostGIS architecture.
