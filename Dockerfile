# Backend API image. Runs as a non-root user, applies database migrations on start-up
# (SCOUTIQ_AUTO_MIGRATE) and reports health. Works with SQLite (default) or PostgreSQL
# (see docker-compose.yml). TLS termination / a reverse proxy are expected in front of it.
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt requirements-postgres.txt requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-postgres.txt -c requirements-lock.txt

COPY . .

# Non-root user. uid 1000 matches the usual Linux host user, so a bind-mounted ./data stays writable.
RUN useradd --uid 1000 --create-home scoutiq && chown -R scoutiq:scoutiq /app
USER scoutiq

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 CMD ["python", "scripts/healthcheck.py"]

EXPOSE 8010

# Run as a module (not `python src/api/app.py`) so the `src.*` absolute
# imports resolve correctly -- running it as a bare script would put
# src/api/ on sys.path instead of the project root and fail with
# ModuleNotFoundError.
#
# This does NOT run the data pipeline or DB ingest automatically. Before
# `docker compose up`, either run the pipeline + ingest steps from the
# README locally and mount ./data, or exec into the running container and
# run them there.
ENTRYPOINT ["sh", "/app/scripts/entrypoint.sh"]
CMD ["python", "-m", "src.api.app"]
