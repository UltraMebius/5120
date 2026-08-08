# CalmWay Architecture

## Planned Application Flow

```text
User
  -> React Frontend
  -> FastAPI Backend
  -> Route Service
  -> Pedestrian Data Service
  -> Sensory Service
  -> Processed Data
```

The current implementation includes the React frontend, FastAPI backend, and a temporary mock route response. The pedestrian-data and sensory-calculation layers are placeholders. Their real interfaces cannot be finalised until the processed dataset and its schema are confirmed.

## Planned Data Science Workflow

```text
Raw Open Data
  -> Data Science Processing
  -> data/processed/
  -> FastAPI Backend
```

No open dataset is currently bundled, downloaded, or assumed by the application.
