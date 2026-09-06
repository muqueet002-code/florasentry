"""Official/extension dashboard (Phase 8).

One aggregated read, built entirely from data Phases 1-7 already produce: no new
model, no new predictive logic, no new GIS engine (see `app.services.dashboard_service`
and `app.gis.hotspots`, both reused as-is). `VIEW_OFFICIAL_DASHBOARD` gates the route,
then the same district/role scope as every other observation query applies underneath -
an OFFICIAL never sees outside their own district here, exactly as on the map.

The observation detail an official opens from this dashboard is served by the existing
`GET /observations/{id}` (+ `/advisory`, `+ /followups?observation_id=`) - there is no
separate "official observation" endpoint, so the official, the farmer and the expert
are always looking at the same record.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_db, require_permission
from app.core.rbac import Permission
from app.core.responses import success
from app.services.dashboard_service import DashboardService

router = APIRouter(tags=["dashboards"])


@router.get("/dashboards/official", summary="Official/extension monitoring dashboard")
def official_dashboard(
    include_demo: bool = Query(default=False),
    current: CurrentUser = Depends(require_permission(Permission.VIEW_OFFICIAL_DASHBOARD)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = DashboardService(db)
    return success(service.official_overview(current, include_demo=include_demo))
