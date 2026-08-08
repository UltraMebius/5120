# CalmWay

## Project Overview

CalmWay is a Monash University FIT5120 practice project for a sensory-friendly navigation web application. It is intended to help sensory-sensitive commuters compare walking route options through Melbourne CBD using simple sensory indicators.

This repository is a small practice scaffold, not a complete navigation product.

## Current Practice Iteration Scope

This iteration only establishes the foundation for:

- entering an origin;
- entering a destination;
- displaying route options; and
- displaying a sensory indicator for each route.

Route results are temporary mock data. There is no real routing, pedestrian-data integration, or sensory calculation yet.

## Current User Story

**User Story 1.1**

As a sensory-sensitive commuter, I want to see a sensory indicator for different routes, so that I can choose a less overwhelming route.

## Acceptance Criteria

1. The user can enter an origin and destination.
2. The system can display at least two route options.
3. Each route can display a LOW, MEDIUM, or HIGH sensory indicator.
4. A lower-sensory route can be marked as recommended.

## Technology Stack

- Frontend: React, Vite, and TypeScript
- Backend: Python and FastAPI
- Testing: pytest and FastAPI TestClient

## Repository Structure

```text
.
|-- frontend/
|   |-- src/
|   |   |-- components/
|   |   |   |-- RouteCard.tsx
|   |   |   |-- RouteSearchForm.tsx
|   |   |   `-- SensoryBadge.tsx
|   |   |-- services/api.ts
|   |   |-- types/route.ts
|   |   |-- App.tsx
|   |   |-- main.tsx
|   |   `-- styles.css
|   |-- index.html
|   |-- package.json
|   |-- package-lock.json
|   |-- tsconfig.json
|   `-- vite.config.ts
|-- backend/
|   |-- app/
|   |   |-- api/routes.py
|   |   |-- services/
|   |   |   |-- pedestrian_service.py
|   |   |   |-- route_service.py
|   |   |   `-- sensory_service.py
|   |   |-- config.py
|   |   `-- main.py
|   `-- requirements.txt
|-- data/
|   |-- raw/.gitkeep
|   |-- processed/.gitkeep
|   `-- README.md
|-- scripts/
|   |-- process_data.py
|   `-- README.md
|-- tests/
|   |-- test_api.py
|   `-- test_sensory.py
|-- docs/
|   |-- acceptance-criteria.md
|   |-- architecture.md
|   `-- team-guide.md
|-- .env.example
|-- .gitignore
`-- README.md
```

## Folder Responsibilities

- `frontend/`: React user interface, form, route cards, sensory badges, and API calls.
- `backend/`: FastAPI endpoints and service-layer responsibilities.
- `data/`: placeholders for raw and processed data managed by the Data Science team.
- `scripts/`: future data cleaning, transformation, and validation tools.
- `tests/`: small backend API and placeholder sensory-service tests.
- `docs/`: acceptance criteria, architecture, and team guidance.

## Current Architecture

The intended flow is `React frontend -> FastAPI backend -> services -> processed data`. Only the frontend, API, and mock service response are active in this iteration. The processed-data integration and real sensory calculation are placeholders.

See [docs/architecture.md](docs/architecture.md) for more detail.

## Environment Requirements

- Node.js with npm
- Python 3.12, or another compatible modern Python 3 version

React and Vite are installed as project dependencies; no global installation is required.

## Frontend Setup

From the repository root in Windows PowerShell:

```powershell
cd frontend
npm install
npm run dev
```

The development site is normally available at `http://localhost:5173`. Start the backend separately so the form can load its mock routes.

## Backend Setup

From the repository root in Windows PowerShell:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The API is normally available at `http://localhost:8000`.

## Backend Health Check

With the backend running, request:

```text
GET http://localhost:8000/health
```

Expected response:

```json
{"status": "ok"}
```

## Running Tests

Install the backend requirements, then run this command from the repository root:

```powershell
python -m pytest
```

To verify the frontend separately:

```powershell
cd frontend
npm run build
```

## Data Science Workflow

The planned handoff is:

```text
Raw dataset -> data/raw/ -> processing scripts -> data/processed/ -> pedestrian_service.py
```

No dataset or schema is assumed in the current scaffold.

## Data Team Handover

Before real data integration begins, the Data Science team should provide:

- the final selected dataset;
- the processed data file;
- the processed data format;
- field definitions;
- the data source;
- update frequency, if known;
- an explanation of missing values; and
- recommendations for crowd or sensory thresholds, if applicable.

These details must be documented from the real handover rather than invented in advance.

## Development Status

Implemented now:

- repository scaffold;
- basic React user interface;
- basic FastAPI API and health check;
- mock route display; and
- project and team documentation.

Not implemented yet:

- real pedestrian data;
- real route generation;
- real sensory scoring;
- maps or geolocation;
- real-time crowd information;
- public transport integration;
- database or authentication;
- deployment infrastructure; or
- machine learning or generative AI.

## Git Collaboration Workflow

1. Work on a personal or feature branch.
2. Pull the latest `main` before major work.
3. Commit small, meaningful changes.
4. Push the personal branch.
5. Create a pull request.
6. Ask for peer review before merging into `main`.

## Limitations

CalmWay is currently a university practice prototype. Its mock sensory information is for demonstrating decision support only and does not provide medical, accessibility, or safety guarantees.
