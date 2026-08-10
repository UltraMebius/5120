# Data processing scripts

`process_data.py` remains a Phase 1 no-op. It does not download, transform, or
score City of Melbourne data.

`check_database.py` is the Phase 2A-1 read-only PostgreSQL/PostGIS readiness
check. It verifies connectivity, versions, and the authoritative public tables;
it never creates schema objects or loads data.

Later ingestion and baseline jobs must follow the complete rules in
`handoff/epic1_backend_handoff_v3/`, including exact-payload deduplication,
conflict preservation, complete 15-minute windows, relocation restrictions,
and separate Network and Local percentiles. One-off file processing must not
replace the final PostgreSQL/PostGIS architecture.
