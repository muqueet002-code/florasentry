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

# (path, method, tag, feature name, delivering phase)
PLANNED_ENDPOINTS: list[tuple[str, str, str, str, str]] = [
    # Phase 2 - AI detection
    ("/observations", "POST", "observations", "Create observation", "Phase 2"),
    ("/observations", "GET", "observations", "List observations", "Phase 2"),
    ("/ai/analyze", "POST", "ai", "Stateless image analysis", "Phase 2"),
    ("/ai/models/active", "GET", "ai", "Active model metadata", "Phase 2"),
    # Phase 3 - weather and risk
    ("/weather/current", "GET", "weather", "Current weather", "Phase 3"),
    ("/weather/forecast", "GET", "weather", "Weather forecast", "Phase 3"),
    ("/risk/ruleset", "GET", "risk", "Active risk ruleset", "Phase 3"),
    # Phase 4 - GIS and hotspots
    ("/gis/observations", "GET", "gis", "Observation points layer", "Phase 4"),
    ("/gis/layers/{layer}", "GET", "gis", "Named map layer", "Phase 4"),
    ("/hotspots", "GET", "gis", "Hotspot list", "Phase 4"),
    # Phase 5 - expert validation
    ("/reviews/queue", "GET", "expert-review", "Expert review queue", "Phase 5"),
    ("/reviews/{review_id}/decision", "POST", "expert-review", "Expert decision", "Phase 5"),
    # Phase 6 - advisory
    ("/observations/{observation_id}/advisory", "GET", "advisory", "Advisory", "Phase 6"),
    # Phase 7 - follow-up
    ("/followups", "GET", "followups", "Follow-up list", "Phase 7"),
    # Phase 8 - dashboards
    ("/dashboards/farmer", "GET", "dashboards", "Farmer dashboard", "Phase 8"),
    ("/dashboards/expert", "GET", "dashboards", "Expert dashboard", "Phase 8"),
    ("/dashboards/official", "GET", "dashboards", "Official dashboard", "Phase 8"),
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
