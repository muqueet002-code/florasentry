"""Aggregates every v1 router.

Implemented in Phase 1: auth, reference data (roles/crops/agents), fields.
Everything else is a documented 501 boundary in `planned.py` until its phase.
"""

from fastapi import APIRouter

from app.api.v1 import auth, catalog, fields, planned

api_router = APIRouter()

# --- implemented ---
api_router.include_router(auth.router)
api_router.include_router(catalog.router)
api_router.include_router(fields.router)

# --- route boundaries for later phases (all return 501) ---
api_router.include_router(planned.router)
