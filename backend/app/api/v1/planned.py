"""Route boundaries for modules that land in later phases.

WHY THESE EXIST
Every route here returns HTTP 501 with a machine-readable body naming the feature and
the phase that will deliver it. Nothing returns a fabricated result.

The point is to fix the URL contract now, so that:
  - the frontend can wire navigation against stable paths;
  - OpenAPI documents the intended surface honestly;
  - a later phase implements a module by REPLACING a stub, not by inventing a path.

If you are implementing one of these phases: delete the corresponding stub registration
below and mount the real router in `app/api/v1/router.py`.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import NotImplementedForPhaseError

router = APIRouter()

# Phases 2-7 are implemented; their entries were removed from this list and their real
# routers mounted in `router.py`. That is the intended lifecycle: a phase deletes its
# stub rather than adding a parallel path.
#
# (path, method, tag, feature name, delivering phase)
PLANNED_ENDPOINTS: list[tuple[str, str, str, str, str]] = [
    # Farmer/expert home screens already surface their own relevant data (fields,
    # review queue, advisory, follow-up); only the official monitoring view was in
    # scope for Phase 8, and it is now a real router (see `dashboards.py`).
    ("/dashboards/farmer", "GET", "dashboards", "Farmer dashboard", "Phase 8"),
    ("/dashboards/expert", "GET", "dashboards", "Expert dashboard", "Phase 8"),
]


def _make_handler(feature: str, phase: str):
    def _handler() -> None:
        raise NotImplementedForPhaseError(feature, phase)

    _handler.__doc__ = f"NOT IMPLEMENTED. '{feature}' is planned for {phase}."
    return _handler


for path, method, tag, feature, phase in PLANNED_ENDPOINTS:
    router.add_api_route(
        path,
        _make_handler(feature, phase),
        methods=[method],
        tags=[tag],
        status_code=501,
        summary=f"[{phase}] {feature} - not implemented",
        description=(
            f"Route boundary only. `{feature}` is scheduled for {phase} and returns "
            "HTTP 501 until then. It never returns placeholder or simulated data."
        ),
    )
