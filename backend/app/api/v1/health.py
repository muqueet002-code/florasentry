"""Health and readiness endpoints (TRD 33.5).

/health   - liveness plus a component breakdown. Always 200 while the process is alive;
            the BODY reports degradation. This is how an operator learns the system is
            degraded before a user does.
/ready    - readiness. 200 only when the database (and PostGIS) are reachable, so an
            orchestrator does not route traffic to a broken instance.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.core.responses import success
from app.db.session import check_database, check_postgis

router = APIRouter(tags=["health"])


def _component_status() -> dict[str, Any]:
    db_ok, db_error = check_database()
    postgis_ok, postgis_version = check_postgis() if db_ok else (False, None)

    return {
        "database": {"ok": db_ok, "error": db_error},
        "postgis": {"ok": postgis_ok, "version": postgis_version},
        # Phase 1 ships no model and no weather provider. Reported honestly rather
        # than omitted, so the absence is visible instead of implied working.
        "ai_model": {
            "ok": False,
            "state": "NOT_CONFIGURED",
            "detail": "No model registered. AI inference lands in Phase 2.",
        },
        "weather_provider": {
            "ok": False,
            "state": "NOT_CONFIGURED",
            "detail": "No provider selected (TRD decision D5). Weather lands in Phase 3.",
        },
    }


@router.get("/health", summary="Liveness and component status")
def health() -> dict[str, Any]:
    components = _component_status()
    degraded = not components["database"]["ok"] or not components["postgis"]["ok"]
    return success(
        {
            "status": "DEGRADED" if degraded else "OK",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "git_sha": settings.GIT_SHA,
            "environment": settings.APP_ENV,
            "components": components,
        }
    )


@router.get("/health/ready", summary="Readiness probe")
def ready(response: Response) -> dict[str, Any]:
    db_ok, db_error = check_database()
    postgis_ok, postgis_version = check_postgis() if db_ok else (False, None)
    is_ready = db_ok and postgis_ok

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return success(
        {
            "ready": is_ready,
            "checks": {
                "database": {"ok": db_ok, "error": db_error},
                "postgis": {"ok": postgis_ok, "version": postgis_version},
            },
        }
    )
