# turotel-qa

Turkish hotel-review aspect sentiment, complaint root-cause and action recommendation.
Plan: `docs/PROJE_PLANI.md`, data layer: `docs/VERI_KATMANI.md`, task order: `roadmap/`.

## Setup

```
cp .env.example .env            # local non-secret dev defaults; put the real Jev key only in .env
uv sync
docker compose up -d            # Postgres + pgvector and Neo4j, bound to 127.0.0.1
uv run alembic upgrade head     # the only source of Postgres DDL (tables and views)
```

## Tests

```
uv run python -m turotel.db.testing    # starts the test Neo4j, sets up turotel_test, runs pytest
```

Tests use a separate Postgres database (name must end in `_test`) and a separate Neo4j
(`127.0.0.1:7688`, `test` compose profile); they refuse anything else.

## Neo4j is derived data: never write to it by hand

Postgres is the source of truth. The Neo4j graph is always rebuilt from Postgres by the
rebuild script (Task 5.2), which first applies the constraints in
`src/turotel/recommend/graph_schema.py` and then deletes and reloads the whole graph.
Hand-written nodes or relationships would be wiped by the next rebuild and are never a valid result.
