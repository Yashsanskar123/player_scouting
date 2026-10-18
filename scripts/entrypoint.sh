#!/bin/sh
# Container start-up: bring the database schema up to date (safe to repeat), then run the API.
# Set SCOUTIQ_AUTO_MIGRATE=false to skip (e.g. when migrations are run as a separate deploy step).
set -e
if [ "${SCOUTIQ_AUTO_MIGRATE:-true}" = "true" ]; then
  python -m src.db.migrate_cli upgrade
fi
exec "$@"
