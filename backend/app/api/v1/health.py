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
from app.db.session import SessionLocal, check_database, check_postgis

router = APIRouter(tags=["health"])


def _component_status() -> dict[str, Any]:
    db_ok, db_error = check_database()
    postgis_ok, postgis_version = check_postgis() if db_ok else (False, None)

    return {
        "database": {"ok": db_ok, "error": db_error},
        "postgis": {"ok": postgis_ok, "version": postgis_version},
        "ai_model": _ai_status(db_ok),
        "weather_provider": {
            "ok": settings.WEATHER_PROVIDER != "none",
            "state": ("DISABLED" if settings.WEATHER_PROVIDER == "none" else "CONFIGURED"),
            "provider": settings.WEATHER_PROVIDER,
            # "CONFIGURED" means a provider is selected, not that it answered just now.
            # Live reachability is reported per request via is_stale / unavailable.
            "detail": None,
        },
    }


def _ai_status(db_ok: bool) -> dict[str, Any]:
    """Real model state. No weights ship with this repository, so the honest
    answer here is normally AI_MODEL_UNAVAILABLE - never an implied 'working'."""
    if not db_ok:
        return {
            "ok": False,
            "state": "UNKNOWN",
            "detail": "Database unavailable; model registry cannot be read.",
        }
    from app.ai.inference_service import model_status

    session = SessionLocal()
    try:
        status_payload = model_status(session)
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "state": "UNKNOWN", "detail": type(exc).__name__}
    finally:
        session.close()
    return {
        "ok": bool(status_payload["ok"]),
        "state": status_payload["state"],
        "detail": status_payload.get("detail"),
        "model_version": status_payload.get("model_version"),
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
