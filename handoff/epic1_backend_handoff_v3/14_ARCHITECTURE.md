# Backend Architecture

```mermaid
flowchart LR

    COM[City of Melbourne Explore API]
    ORS[openrouteservice Walking Directions]

    ING[15-min Ingestion Worker]
    REF[Reference Data Refresh]
    HIST[Historical Import / Refresh]

    PG[(PostgreSQL + PostGIS)]

    BASE[Baseline Builder]
    CUR[Current Sensor Scoring Job]
    SPAT[Spatial Crowd Engine]
    ROUTE[Route Evaluation / Ranking Service]
    API[Backend REST API]

    COM --> ING
    COM --> REF
    COM --> HIST

    ING --> PG
    REF --> PG
    HIST --> PG

    PG --> BASE
    BASE --> PG

    PG --> CUR
    CUR --> PG

    PG --> SPAT
    ORS --> ROUTE
    SPAT --> ROUTE

    ROUTE --> API
    SPAT --> API
    PG --> API
```

## Processing Separation

### Scheduled jobs

- minute ingestion: every 15 min;
- current score materialisation: after successful minute ingestion;
- sensor metadata refresh: daily;
- historical hourly refresh: scheduled upsert;
- baseline rebuild: when historical data materially changes.

### Request-time services

- point crowd estimate;
- route geometry evaluation;
- walking-route candidate generation;
- route crowd metrics/ranking.

### Important

The routing service supplies **walkable geometry**.

The project crowd engine supplies **pedestrian activity evidence**.

Do not ask the routing engine to replace the project's sensor-derived crowd model.
