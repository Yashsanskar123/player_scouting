# Deploying with PostgreSQL

SQLite remains the zero-setup default for local use. For shared use, run PostgreSQL.

## Docker Compose (API + PostgreSQL)
```
cp .env.example .env            # set POSTGRES_PASSWORD, SCOUTIQ_AUTH_SECRET, admin bootstrap, CORS origin
docker compose up -d --build
docker compose run --rm api python -m src.db.ingest     # first run only: loads the player data
```
The API container applies database migrations on every start (`SCOUTIQ_AUTO_MIGRATE=false` to skip) and exposes a health check.
It runs as user id 1000 so a bind-mounted `./data` stays writable on a typical Linux host.

## Without Docker
```
pip install -r requirements.txt -r requirements-postgres.txt -c requirements-lock.txt
export DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
python -m src.db.migrate_cli upgrade      # create / update the schema (safe to repeat)
python -m src.db.ingest                   # load the processed player data
python -m src.api.app
```

## Migrations
`migrations/` holds Alembic revisions: `0001` is the baseline (creates anything missing, so it is safe on an older
database), `0002` adds the Scout Workspace columns. Migrations are additive; there are no downgrades, so take a backup
(`pg_dump`) before upgrading. `python -m src.db.migrate_cli current` shows the schema version.

## Moving from SQLite to PostgreSQL
Shortlists, notes, users and the audit log live in the database; the player data is re-loadable. To keep your existing
shortlists, export them first (Scout Workspace -> Export to Excel), run the steps above, and re-create them, or copy the
tables with a tool such as `pgloader`. The player tables are rebuilt by `src.db.ingest`.

## What was verified
All API endpoints used by the app were exercised against PostgreSQL 16 with the real 28,436-row dataset, and the
`tests/test_postgres.py` suite runs in CI against a PostgreSQL service. The Docker image itself is built in CI; it was
not built in the environment where this was authored, so treat the first `docker compose up` as the real acceptance test.
