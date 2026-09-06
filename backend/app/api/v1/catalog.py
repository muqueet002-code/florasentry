"""Reference-data endpoints: roles and the crop/agent catalogue (TRD 12.2, 12.5).

These are genuinely implemented in Phase 1 (they are read-only lookups over seeded
reference data) and give the frontend real data to render.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, get_db, get_language
from app.core.errors import NotFoundError
from app.core.rbac import role_matrix
from app.core.responses import success
from app.models.catalog import Crop, CropVariety, DiseasePestCatalog, GrowthStage

router = APIRouter(tags=["reference-data"])


def _localised(obj: object, field: str, lang: str) -> str:
    """Return `<field>_<lang>`, falling back to English (TRD 22.2)."""
    value = getattr(obj, f"{field}_{lang}", None)
    return value or getattr(obj, f"{field}_en")


@router.get("/roles", summary="Roles and their effective permissions")
def list_roles(_: CurrentUser = Depends(get_current_user)) -> dict[str, object]:
    """Served from the RBAC matrix in code, so it can never drift from enforcement."""
    return success(role_matrix())


@router.get("/crops", summary="Active crops")
def list_crops(
    lang: str = Depends(get_language),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> dict[str, object]:
    crops = db.execute(select(Crop).where(Crop.is_active.is_(True)).order_by(Crop.code)).scalars()
    return success(
        [
            {
                "id": str(c.id),
                "code": c.code,
                "name": _localised(c, "name", lang),
                "scientific_name": c.scientific_name,
                "available_languages": ["en", "hi", "mr"],
            }
            for c in crops
        ],
        filters_applied={"language": lang},
    )


@router.get("/crops/{crop_id}/varieties", summary="Varieties of a crop")
def list_varieties(
    crop_id: uuid.UUID,
    lang: str = Depends(get_language),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> dict[str, object]:
    if db.get(Crop, crop_id) is None:
        raise NotFoundError("Crop")
    rows = db.execute(
        select(CropVariety).where(CropVariety.crop_id == crop_id).order_by(CropVariety.code)
    ).scalars()
    return success(
        [
            {
                "id": str(v.id),
                "crop_id": str(v.crop_id),
                "code": v.code,
                "name": _localised(v, "name", lang),
                "duration_days": v.duration_days,
            }
            for v in rows
        ]
    )


@router.get("/crops/{crop_id}/growth-stages", summary="Ordered growth stages of a crop")
def list_growth_stages(
    crop_id: uuid.UUID,
    lang: str = Depends(get_language),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> dict[str, object]:
    if db.get(Crop, crop_id) is None:
        raise NotFoundError("Crop")
    rows = db.execute(
        select(GrowthStage).where(GrowthStage.crop_id == crop_id).order_by(GrowthStage.sequence)
    ).scalars()
    return success(
        [
            {
                "id": str(s.id),
                "crop_id": str(s.crop_id),
                "code": s.code,
                "name": _localised(s, "name", lang),
                "sequence": s.sequence,
                "typical_days_from_sowing_min": s.typical_days_from_sowing_min,
                "typical_days_from_sowing_max": s.typical_days_from_sowing_max,
            }
            for s in rows
        ]
    )


@router.get("/catalog/agents", summary="Diagnosable diseases, pests and disorders")
def list_agents(
    kind: str | None = Query(default=None, pattern="^(DISEASE|PEST|DISORDER|HEALTHY|UNKNOWN)$"),
    is_ai_supported: bool | None = Query(default=None),
    lang: str = Depends(get_language),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> dict[str, object]:
    """`is_ai_supported` is false for every row in Phase 1: no model is registered."""
    stmt = select(DiseasePestCatalog)
    if kind:
        stmt = stmt.where(DiseasePestCatalog.kind == kind)
    if is_ai_supported is not None:
        stmt = stmt.where(DiseasePestCatalog.is_ai_supported.is_(is_ai_supported))

    rows = db.execute(stmt.order_by(DiseasePestCatalog.code)).scalars()
    return success(
        [
            {
                "id": str(a.id),
                "code": a.code,
                "kind": a.kind,
                "name": _localised(a, "name", lang),
                "scientific_name": a.scientific_name,
                "is_ai_supported": a.is_ai_supported,
            }
            for a in rows
        ],
        filters_applied={"kind": kind, "is_ai_supported": is_ai_supported, "language": lang},
    )
