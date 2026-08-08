# Team Guide

## Frontend developers: `frontend/`

Typical work:

- user interface;
- route search form;
- route cards and sensory badges; and
- calls to backend APIs.

## Backend developers: `backend/`

Typical work:

- FastAPI endpoints;
- service logic; and
- frontend/backend integration.

## Data Science developers: `data/`, `scripts/`, and `backend/app/services/pedestrian_service.py`

Typical work:

- dataset selection;
- data cleaning and transformation;
- processed dataset structure;
- documentation of fields; and
- helping the team define sensory thresholds from evidence.

Do not add assumed fields or thresholds before the final dataset is confirmed.

## Testing: `tests/`

Keep tests aligned with implemented behaviour. The current suite covers the health endpoint, mock route endpoint, and temporary sensory placeholder only.

## Documentation: `README.md` and `docs/`

Update setup instructions, architecture, acceptance criteria, and limitations whenever implementation decisions change.
