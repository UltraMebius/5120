# Team Guide

## Repository responsibilities

| Area | Location | Responsibility |
| --- | --- | --- |
| Frontend | `frontend/` | React pages, journey state, Mapbox browser search/map rendering, API validation, responsive UI |
| Backend | `backend/app/` | FastAPI endpoints, schemas, routing, crowd/flow services, repositories, configuration |
| Tests | `tests/`, `frontend/tests/` | Backend and frontend regression evidence |
| Operations | `.github/workflows/`, `scripts/` | Scheduled refresh and explicit local/import/evaluation tools |
| Database contract | `handoff/epic1_backend_handoff_v3/` | Frozen schema, data semantics, algorithm constraints, and evidence |
| Maintained documentation | `README.md`, `docs/`, `data/README.md`, `scripts/README.md` | Current product, engineering, testing, and operational guidance |

## Current product boundary

The active React journey uses `POST /api/v1/routes/options` and presents one to
three `CALMEST`/`FASTEST`/`BALANCED` route options using pedestrian movements
per minute. The preference-aware `POST /api/v1/routes/walking` endpoint and
initial alert engine remain implemented backend capabilities but are not wired
into the active React pages.

Do not describe the unused preference selector or alert panel as current
end-to-end behavior. When changing either API, update the relevant tests and
the boundary statement in README, acceptance criteria, architecture, route
ranking, and navigation-alert documentation.

## Frontend conventions

- Pages own screen composition; reusable components stay under
  `src/components/`.
- `JourneyContext` owns only the current in-memory journey. Do not introduce
  persistence without reviewing direct-link, privacy, and stale-data behavior.
- `services/api.ts` validates backend JSON before it reaches pages. Update
  validators and fixtures whenever a response schema changes.
- Browser place search and Mapbox GL use only
  `VITE_MAPBOX_PUBLIC_TOKEN`. Never expose `MAPBOX_ACCESS_TOKEN`.
- Route geometry, roles, order, and evidence come from the backend. Do not call
  Mapbox Directions or re-rank route options in React.
- Preserve null-versus-zero semantics and honest unavailable wording.
- Route differences must include text; colour alone is insufficient.
- Keep form labels, focus styles, keyboard operation, route guards, and
  selected-state semantics covered by tests.

## Backend conventions

- `api/` owns HTTP concerns and sanitised status mapping.
- `schemas/` owns Pydantic request/response contracts.
- `models/` owns domain records and enums.
- `services/routing/` owns Mapbox walking candidates, sampling, crowd/flow
  evaluation, route roles/ranking, and alert decisions.
- `services/crowd/` owns current activity, spatial Crowd Exposure, and
  pedestrian-flow evaluation.
- `services/ingestion/` and `services/baseline/` own explicit data preparation;
  no ingestion or scheduler runs at FastAPI startup.
- `repositories/` owns SQL/PostGIS access and transaction boundaries.
- Keep expected provider/database errors sanitised. Do not put URLs containing
  tokens, connection strings, raw sensor payloads, or secrets in logs.
- Preserve the authoritative 15-minute windows, data states, 250/300 m support,
  normalised inverse-distance weighting, 50 m route sampling, and null rules
  unless a reviewed data-science decision changes them.

## Data and database work

- Use the schema in
  `handoff/epic1_backend_handoff_v3/05_DATABASE_SCHEMA.sql`; do not invent a
  parallel SQLite or file-backed production path.
- Treat `data/raw/` and `data/processed/` as controlled local staging areas.
  Do not commit large downloads, temporary exports, or credentials.
- Run import/build scripts with `--dry-run` first where supported.
- Keep the frozen hourly baseline training window and relocation rules enforced
  by the implementation.
- Preserve explicit zeros, exact-payload deduplication, logical conflict
  records, and missing/stale/conflicted states.
- Use a direct database connection for schema/bulk administration and a pooled
  Neon URL for serverless request traffic.
- Review every script before pointing it at shared or production data. A
  successful test run does not authorise a production write.

## Git workflow

1. Start from the team-approved base branch and create/use the assigned feature
   branch.
2. Run `git status --short` before and after changes.
3. Pull or merge team changes only according to the agreed team workflow; do
   not rewrite another member's history.
4. Stage specific paths and inspect `git diff --cached` before committing.
5. Never stage `.env*`, `.vercel/`, virtual environments, `node_modules/`,
   `dist/`, database exports, tokens, or local editor files.
6. Run relevant tests and builds before requesting review.
7. Use a pull request for review when the team workflow requires it. Resolve
   conflicts by understanding both changes, not by blindly choosing one side.

Useful safety checks:

```bash
git branch --show-current
git status --short
git diff --check
git diff --cached
```

Avoid destructive recovery commands such as `git reset --hard` on a working
tree containing uncommitted team work.

## Validation expectations

For a normal change, run from the repository root and `frontend/` respectively:

```bash
python -m pytest -q
cd frontend
npm test
npm run build
```

Use focused tests during development, but run the applicable full suites before
handoff. External integration tests are opt-in; report skips honestly. See
[Testing Guide](testing-guide.md) for gates and smoke checks.

## Documentation maintenance

- Documentation is maintained in English.
- Describe source behavior, not phase plans or intended future behavior.
- Keep endpoint names, environment variables, commands, project names, and
  production URLs synchronized with code/configuration.
- Update [Acceptance Criteria](acceptance-criteria.md) when product status
  changes and distinguish backend-only from active end-to-end delivery.
- Update [Route Ranking](route-ranking.md) or
  [Navigation Alerts](navigation-alerts.md) when constants or decision logic
  change.
- Do not add a new phase-specific document when the information belongs in one
  of the maintained guides.
- Search for broken links and obsolete file references before deleting or
  renaming documentation.

## Secrets and local configuration

The root, backend, and frontend ignore rules protect local environment and
Vercel metadata. Preserve those rules.

- Copy safe placeholders from `.env.example`; never copy real values back into
  it.
- Assume every `VITE_` variable is public.
- Keep `DATABASE_URL`, backend Mapbox tokens, refresh secrets, Vercel
  credentials, and GitHub secrets out of source, docs, test snapshots, and
  screenshots.
- Rotate a secret immediately through the owning platform if exposure is
  suspected; do not commit a deletion and assume history is clean.

## Review checklist

- Behavior matches the active API contract.
- Null/no-data semantics remain truthful.
- Source and tests agree with documentation.
- Backend and frontend tests pass.
- Frontend production build passes.
- No secret or generated artifact is staged.
- No obsolete documentation link remains.
- Deployment/database changes include a rollback or recovery note.
