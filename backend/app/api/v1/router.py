"""Aggregates every v1 router.

Implemented: auth, reference data, fields (Phase 1); observations, images, AI
inference (Phase 2); weather and risk (Phase 3); GIS and hotspots, expert review
(Phase 4 + 5); advisory, follow-up (Phase 6 + 7); official dashboard (Phase 8).

Everything else remains a documented 501 boundary in `planned.py` until its phase.
"""

from fastapi import APIRouter

from app.api.v1 import (
    advisory,
    auth,
    catalog,
    dashboards,
    fields,
    followups,
    gis,
    observations,
    planned,
    reviews,
    weather_risk,
)

api_router = APIRouter()

# --- implemented ---
api_router.include_router(auth.router)
api_router.include_router(catalog.router)
api_router.include_router(fields.router)
api_router.include_router(observations.router)
api_router.include_router(weather_risk.router)
api_router.include_router(gis.router)
api_router.include_router(reviews.router)
api_router.include_router(advisory.router)
api_router.include_router(followups.router)
api_router.include_router(dashboards.router)

# --- route boundaries for later phases (all return 501) ---
api_router.include_router(planned.router)
