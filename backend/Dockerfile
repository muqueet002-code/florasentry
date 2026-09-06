# FloraSentry V2 backend (TRD 37.1)
# Python 3.11 is pinned here regardless of the developer's local interpreter, so the
# runtime is identical in development, CI and deployment.

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System libraries:
#   libpq5        - PostgreSQL client library for psycopg
#   libgeos-c1v5  - GEOS, required by shapely
#   curl          - container healthcheck
# GDAL/PROJ are NOT installed: Phase 1 does all spatial work inside PostGIS. Add them
# only when a phase genuinely needs client-side geoprocessing (e.g. GeoPandas in the
# Phase 4 hotspot job).
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libpq5 \
        libgeos-c1v5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/app

# Dependency layer first, so source edits do not invalidate the pip cache.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install "."

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Run as a non-root user.
RUN useradd --create-home --uid 10001 florasentry \
    && mkdir -p /var/florasentry/media \
    && chown -R florasentry:florasentry /srv/app /var/florasentry
USER florasentry

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# The entrypoint runs `alembic upgrade head` before starting the API, so the
# database schema is always applied on deploy - see docker-entrypoint.sh.
ENTRYPOINT ["./docker-entrypoint.sh"]
