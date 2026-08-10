# Data folders

No City of Melbourne dataset is ingested or bundled in Phase 1.

The confirmed dataset IDs, data states, natural keys, historical contexts, and
processing rules are documented in `handoff/epic1_backend_handoff_v3/`. The
final application stores source and derived data in PostgreSQL/PostGIS rather
than treating `data/processed/` files as the production database.

## `data/raw/`

Reserved only for controlled local Data Science exploration. Preserve original
source files and document provenance; do not commit secrets or large downloads.

## `data/processed/`

Reserved for reproducible validation outputs or exchange artifacts. Backend
request-time services must ultimately use the authoritative PostGIS schema.
