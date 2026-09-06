#!/bin/sh
# Container entrypoint: apply pending Alembic migrations, then start the API.
#
# Render (and any other platform that just runs the image) never invokes Alembic on
# its own, so without this step a freshly provisioned Postgres database is left with
# no schema at all ("relation \"users\" does not exist"). Running the upgrade here,
# every time the container starts, keeps the deployed schema in sync with whatever
# migration is committed - the same guarantee docker-compose.yml gives locally with
# its dedicated one-shot `migrate` service.
set -e

echo "Running database migrations (alembic upgrade head)..."
alembic upgrade head

echo "Starting FloraSentry backend..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
