# Data staging directories

CalmWay does not bundle City of Melbourne downloads or production database
exports in Git. Runtime and reproducible application data are stored in
PostgreSQL/PostGIS using the schema under
`handoff/epic1_backend_handoff_v3/05_DATABASE_SCHEMA.sql`.

## `data/raw/`

Reserved for controlled local source downloads or data-science exploration.
Preserve source provenance and licensing notes alongside any local file. Do not
commit credentials, large downloads, database dumps, or temporary API payloads.

## `data/processed/`

Reserved for reproducible local validation outputs or reviewed exchange
artifacts. A processed file must not replace the authoritative PostGIS tables
used by request-time services.

Both directories intentionally contain tracked `.gitkeep` placeholders. No
data file was removed during the final cleanup because no obsolete or duplicate
payload was present.

Use `scripts/` for ingestion and evaluation. Current data flow and safety rules
are documented in `README.md`, `docs/architecture.md`,
`docs/testing-guide.md`, and `docs/team-guide.md`.
